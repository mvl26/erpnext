"""User Permission rows from ``user_permission_rules`` and ``user_scope`` (spec section 10).

Only users listed in ``user_scope`` are managed for the per-user types (Warehouse, Price List, Issue Type,
Customer, Supplier): their scope is known. A rule with fixed ``values`` (Stock Entry Type) applies those
values to every enabled user holding one of its roles. User Permissions on the ``_remove_allow`` types are
deleted site-wide, for every user.
"""

from collections import Counter

import frappe

REMOVE_KEY = "_remove_allow"

Key = tuple[str, str, str, str | None, int]  # user, allow, for_value, applicable_for, apply_to_all_doctypes


def _rules(m) -> dict[str, dict]:
	return {allow: rule for allow, rule in m.user_permission_rules.items() if allow != REMOVE_KEY}


def _role_names(m, codes) -> set[str]:
	return {name for code in codes for name in m.role_names(code)}


def _roles_of(users) -> dict[str, set[str]]:
	roles: dict[str, set[str]] = {user: set() for user in users}
	if not roles:
		return roles
	rows = frappe.get_all(
		"Has Role", filters={"parenttype": "User", "parent": ("in", list(roles))}, fields=["parent", "role"]
	)
	for row in rows:
		roles[row.parent].add(row.role)
	return roles


def _holders(role_names: set[str]) -> list[str]:
	"""Enabled users holding any of ``role_names``."""
	if not role_names:
		return []
	parents = frappe.get_all(
		"Has Role", filters={"parenttype": "User", "role": ("in", list(role_names))}, pluck="parent"
	)
	if not parents:
		return []
	return frappe.get_all("User", filters={"name": ("in", parents), "enabled": 1}, pluck="name")


def _rows_for(allow: str, rule: dict, user: str, values) -> set[Key]:
	apply_all = int(bool(rule.get("apply_to_all", 0)))
	targets = [None] if apply_all else list(rule.get("applicable_for") or [])
	return {(user, allow, value, target, apply_all) for value in values for target in targets}


def _desired(m, audit: list[str]) -> tuple[set[Key], set[tuple[str, str]]]:
	"""The rows that must exist, and the (user, allow) pairs this sync manages."""
	listed = [user for user in m.user_scope if frappe.db.exists("User", user)]
	wanted: set[Key] = set()
	managed: set[tuple[str, str]] = set()
	for allow, rule in _rules(m).items():
		rule_roles = _role_names(m, rule.get("roles", []))
		fixed = rule.get("values")
		users = list(dict.fromkeys([*listed, *(_holders(rule_roles) if fixed is not None else [])]))
		roles = _roles_of(users)
		for user in users:
			managed.add((user, allow))
			if roles[user] & rule_roles:
				values = fixed if fixed is not None else m.user_scope[user].get(allow) or []
				for value in values:
					if frappe.db.exists(allow, value):
						wanted |= _rows_for(allow, rule, user, [value])
					else:
						audit.append(f"{user} — {allow} {value} không tồn tại, bỏ qua")
	return wanted, managed


def _existing(managed: set[tuple[str, str]]) -> dict[Key, str]:
	if not managed:
		return {}
	rows = frappe.get_all(
		"User Permission",
		filters={
			"user": ("in", sorted({user for user, _ in managed})),
			"allow": ("in", sorted({allow for _, allow in managed})),
		},
		fields=["name", "user", "allow", "for_value", "applicable_for", "apply_to_all_doctypes"],
	)
	found: dict[Key, str] = {}
	for r in rows:
		if (r.user, r.allow) in managed:
			found[
				(r.user, r.allow, r.for_value, r.applicable_for or None, int(r.apply_to_all_doctypes))
			] = r.name
	return found


def _insert(key: Key) -> None:
	user, allow, value, target, apply_all = key
	frappe.get_doc(
		{
			"doctype": "User Permission",
			"user": user,
			"allow": allow,
			"for_value": value,
			"apply_to_all_doctypes": apply_all,
			"applicable_for": target,
		}
	).insert(ignore_permissions=True)


def _remove_unwanted_types(m) -> int:
	names = frappe.get_all(
		"User Permission",
		filters={"allow": ("in", list(m.user_permission_rules.get(REMOVE_KEY) or []))},
		pluck="name",
	)
	for name in names:
		frappe.delete_doc("User Permission", name, ignore_permissions=True, force=True)
	return len(names)


def sync_user_permissions(m, audit: list[str] | None = None) -> Counter:
	"""Make User Permissions match the rules (returns Counter ``inserted``, ``deleted``; callers may ignore it).

	A scope value whose record does not exist is skipped and reported on ``audit`` (validate does not check it).
	"""
	counter: Counter = Counter()
	wanted, managed = _desired(m, audit if audit is not None else [])
	have = _existing(managed)
	for key, name in have.items():
		if key not in wanted:
			frappe.delete_doc("User Permission", name, ignore_permissions=True, force=True)
			counter["deleted"] += 1
	for key in sorted(wanted - set(have), key=str):
		_insert(key)
		counter["inserted"] += 1
	counter["deleted"] += _remove_unwanted_types(m)
	return counter


def users_without_scope(m) -> list[str]:
	"""Enabled users holding a per-user rule role but absent from ``user_scope`` (their scope is unknown)."""
	role_names: set[str] = set()
	for rule in _rules(m).values():
		if "values" not in rule:
			role_names |= _role_names(m, rule.get("roles", []))
	return sorted(set(_holders(role_names)) - set(m.user_scope))
