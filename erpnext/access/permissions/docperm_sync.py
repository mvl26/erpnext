"""Custom DocPerm writer — brings each matrix DocType's Custom DocPerm rows to the expanded matrix by diff.

Only rows of *managed* roles (3.1, 3.3, ``All``, ``Desk User``) are ever deleted or changed. Rows of every
other role (assetcore and the like) are left exactly as they are (spec section 12, Bước 3, step 2).
"""

from collections import Counter

import frappe
from frappe.permissions import setup_custom_perms

from erpnext.access.permissions.expand import PermRow, expand_doctype
from erpnext.access.permissions.matrix import Matrix
from erpnext.access.permissions.site import DocTypeInfo, SiteInfo

PTYPES = (
	"select",
	"read",
	"write",
	"create",
	"delete",
	"submit",
	"cancel",
	"amend",
	"report",
	"export",
	"import",
	"share",
	"print",
	"email",
)
AUTO_ROLES = ("All", "Desk User")
# Holder of an all-zero row that keeps a DocType locked when the matrix grants nobody anything: with no
# Custom DocPerm row at all frappe falls back to the standard DocPerm. Administrator bypasses permissions,
# and it is not a managed role, so the row is never deleted on a later run.
LOCK_ROLE = "Administrator"

Key = tuple[str, int, bool]


def managed_roles(m: Matrix) -> frozenset[str]:
	names = {name for role in m.roles.values() for name in role.names}
	names.update(m.rules.get("retired_roles", ()))
	names.update(AUTO_ROLES)
	return frozenset(names)


def _key(r: PermRow) -> Key:
	return (r.role, r.permlevel, r.if_owner)


def _merge(rows) -> list[PermRow]:
	"""One row per (role, permlevel, if_owner), ptypes unioned, in a stable order."""
	merged: dict[Key, set[str]] = {}
	for r in rows:
		merged.setdefault(_key(r), set()).update(r.ptypes)
	return [PermRow(role, level, frozenset(p), owner) for (role, level, owner), p in sorted(merged.items())]


def _select_perms(table: str, doctype: str, roles=None) -> list[dict]:
	t = frappe.qb.DocType(table)
	q = (
		frappe.qb.from_(t)
		.select(t.name, t.role, t.permlevel, t.if_owner, *[t[p] for p in PTYPES])
		.where(t.parent == doctype)
		.orderby(t.creation)
		.orderby(t.name)
	)
	if roles is not None:
		if not roles:
			return []
		q = q.where(t.role.isin(sorted(roles)))
	return q.run(as_dict=True)


def _as_row(d: dict) -> PermRow:
	return PermRow(d.role, int(d.permlevel or 0), frozenset(p for p in PTYPES if d[p]), bool(d.if_owner))


def _standard_rows(doctype: str, roles) -> list[PermRow]:
	"""The DocType's own (standard, ``tabDocPerm``) rows for ``roles``, copied as they are."""
	return [_as_row(d) for d in _select_perms("DocPerm", doctype, roles)]


def desired_rows(m: Matrix, doctype: str, info: DocTypeInfo) -> list[PermRow]:
	"""Rows the managed roles must have on ``doctype``; may also carry standard rows of ``keep_standard_rows``."""
	entry = m.doctypes[doctype]
	if entry.state == "keep_standard":
		return _merge(_standard_rows(doctype, managed_roles(m)))
	copied = set(entry.keep_standard_rows)
	if info.app == "frappe" and doctype not in m.rules.get("g10_exceptions", ()):
		copied.update(AUTO_ROLES)  # G10 — frappe DocTypes keep their standard All / Desk User rows
	return _merge([*expand_doctype(m, doctype, info), *_standard_rows(doctype, copied)])


def _values(ptypes) -> dict[str, int]:
	return {p: int(p in ptypes) for p in PTYPES}


def _insert(doctype: str, key: Key, ptypes):
	role, permlevel, if_owner = key
	frappe.get_doc(
		{
			"doctype": "Custom DocPerm",
			"parent": doctype,
			"role": role,
			"permlevel": permlevel,
			"if_owner": int(if_owner),
			**_values(ptypes),
		}
	).insert(ignore_permissions=True)


def _delete(name: str):
	frappe.delete_doc("Custom DocPerm", name, ignore_permissions=True, force=True, delete_permanently=True)


def _sync_doctype(m: Matrix, doctype: str, info: DocTypeInfo, managed: frozenset[str]) -> Counter:
	c = Counter()
	expanded = m.doctypes[doctype].state != "keep_standard"
	if expanded:
		if setup_custom_perms(doctype):  # first touch — frappe copies the standard rows in
			c["inserted"] += frappe.db.count("Custom DocPerm", {"parent": doctype})
	elif not frappe.db.exists("Custom DocPerm", {"parent": doctype}):
		return c  # keep_standard and never customised — the standard rows already apply

	desired = {_key(r): r.ptypes for r in desired_rows(m, doctype, info)}
	site = _select_perms("Custom DocPerm", doctype)
	if expanded and not desired and all(d.role in managed for d in site):
		desired[(LOCK_ROLE, 0, False)] = frozenset()

	present: set[Key] = set()
	for d in site:
		current = _as_row(d)
		key = _key(current)
		if current.role not in managed:
			present.add(key)  # foreign row — never touched
			continue
		if key in present or key not in desired:  # duplicate, or not wanted
			_delete(d.name)
			c["deleted"] += 1
			continue
		present.add(key)
		if current.ptypes != desired[key]:
			doc = frappe.get_doc("Custom DocPerm", d.name)
			doc.update(_values(desired[key]))
			doc.save(ignore_permissions=True)
			c["deleted"] += 1
			c["inserted"] += 1

	for key, ptypes in desired.items():
		if key not in present:
			_insert(doctype, key, ptypes)
			c["inserted"] += 1
	return c


def sync_docperms(m: Matrix, site: SiteInfo) -> Counter:
	"""Write Custom DocPerm for every matrix DocType the site has. Returns counts ``inserted`` / ``deleted``."""
	managed = managed_roles(m)
	if LOCK_ROLE in managed:
		frappe.throw(f"{LOCK_ROLE} must not be a managed role")
	total = Counter(inserted=0, deleted=0)
	for doctype in sorted(m.doctypes):
		info = site.doctypes.get(doctype)
		if info is None:
			continue  # validate already warns about matrix DocTypes the site does not have
		c = _sync_doctype(m, doctype, info, managed)
		if c["inserted"] or c["deleted"]:
			frappe.clear_cache(doctype=doctype)
		total.update(c)
	return total
