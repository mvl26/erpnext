"""Shared test fixtures for the access package."""

import json

import frappe

from erpnext.access.permissions.matrix import MATRIX_DIR, DocTypeEntry, Matrix, RoleDef


def _load_json(name: str) -> dict:
	return json.loads((MATRIX_DIR / name).read_text(encoding="utf-8"))


def small_matrix(
	doctypes: dict[str, DocTypeEntry] | None = None,
	rules: dict | None = None,
	custom_fields: dict | None = None,
	workflows: dict | None = None,
) -> Matrix:
	"""A Matrix with the real roles/packs and rules, but a handful of DocType entries built in code.

	Pass ``doctypes`` or ``rules`` to replace the defaults entirely; ``custom_fields`` and ``workflows``
	default to empty.
	"""
	roles_data = _load_json("roles.json")
	roles = {
		code: RoleDef(
			code=code,
			names=tuple(raw["names"]),
			desk_access=int(raw["desk_access"]),
			is_new=bool(raw.get("is_new", False)),
		)
		for code, raw in roles_data["roles"].items()
	}
	if doctypes is None:
		doctypes = {
			"Purchase Order": DocTypeEntry(
				state="matrix", perms={"PU": "CRWP", "PM": "CRWSXAPE", "STU": "R"}, workflow="WF-PO"
			),
			"Supplier": DocTypeEntry(state="matrix", perms={"PM": "CRWI", "PU": "R"}),
			"Company": DocTypeEntry(state="ref_master", perms={"AM": "RW"}, pda=True),
			"Salary Slip": DocTypeEntry(
				state="matrix", perms={"EMP": "R R1", "HM": "CRWSXAPE W1"}, scope={"EMP": "e"}
			),
			"Employee Grievance": DocTypeEntry(state="matrix", perms={"HM": "CRW"}),
			"Interview Feedback": DocTypeEntry(state="matrix", perms={"EMP": "CRWS"}, scope={"EMP": "o"}),
			"BOM": DocTypeEntry(state="g1_only"),
			"ToDo": DocTypeEntry(state="keep_standard"),
		}
	return Matrix(
		roles=roles,
		packs=roles_data.get("packs", {}),
		role_profiles=roles_data.get("role_profiles", {}),
		combined_profiles=roles_data.get("combined_profiles", []),
		doctypes=doctypes,
		rules=rules if rules is not None else _load_json("rules.json")["rules"],
		custom_fields=custom_fields or {},
		workflows=workflows or {},
	)


def require_test_site(case) -> None:
	"""Skip a test that activates a real Workflow — the Redis "workflow" hash is shared with production."""
	if not frappe.conf.get("mvl_rbac_test_site"):
		case.skipTest("cần site test (Q8)")


def make_user(*roles, prefix: str = "rbac") -> str:
	"""Insert a throwaway desk User holding ``roles`` (inside the test transaction); return its email."""
	email = f"{prefix}-{frappe.generate_hash(length=8)}@example.com"
	user = frappe.get_doc({"doctype": "User", "email": email, "first_name": prefix, "send_welcome_email": 0})
	user.insert(ignore_permissions=True)
	if roles:
		user.add_roles(*roles)
	frappe.clear_cache(user=email)
	return email
