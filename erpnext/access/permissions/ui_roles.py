"""Report, Page and Workspace role writer (spec 11.2 R1 to R3, 11.6, 11.8).

Developer mode is on, so saving a standard Report, Page or public Workspace would export JSON into app
source trees. Reports and Pages are therefore only ever touched through ``Custom Role`` documents, and
Workspace roles are written as ``Has Role`` child rows directly. Every writer diffs first: a second run
changes nothing.
"""

import frappe
from frappe.utils import now

from erpnext.access.permissions.cells import MatrixError
from erpnext.access.permissions.matrix import Matrix
from erpnext.access.permissions.site import SiteInfo

LOCK_CODE = "LK"


def _role_names(m: Matrix, codes) -> list[str]:
	names: list[str] = []
	for code in codes:
		for name in m.role_names(code):
			if name not in names:
				names.append(name)
	return names


def _set_custom_role(field: str, name: str, roles: list[str], ref_doctype: str | None = None) -> bool:
	"""Make the Custom Role of a report/page hold exactly ``roles``. True if something was written."""
	if not roles:
		# an empty Custom Role is ignored by frappe, which would silently unlock the standard roles
		raise MatrixError(f"{field} {name!r}: no roles resolved, refusing to write an empty Custom Role")
	existing = frappe.get_all("Custom Role", filters={field: name}, pluck="name", order_by="creation, name")
	changed = False
	for extra in existing[1:]:  # duplicates would be unioned by frappe
		frappe.delete_doc("Custom Role", extra, ignore_permissions=True, force=True)
		changed = True
	existing = existing[:1]
	if not existing:
		values = {"doctype": "Custom Role", field: name, "roles": [{"role": r} for r in roles]}
		if ref_doctype:
			values["ref_doctype"] = ref_doctype
		frappe.get_doc(values).insert(ignore_permissions=True)
		return True
	doc = frappe.get_doc("Custom Role", existing[0])
	if {r.role for r in doc.roles} == set(roles) and len(doc.roles) == len(roles):
		return changed
	doc.set("roles", [{"role": r} for r in roles])
	doc.save(ignore_permissions=True)
	return True


def sync_report_roles(m: Matrix, site: SiteInfo, warnings: list[str] | None = None) -> list[str]:
	"""Lock every report of the site (role ``LK``) except the ones the matrix lists.

	Returns the sorted names of the reports left locked, for audit. Reports listed in the matrix but absent
	from the site are reported as warning lines appended to the optional ``warnings`` list.
	"""
	if warnings is not None:
		warnings.extend(
			f"Report {r!r} is in the matrix but not on the site — skipped"
			for r in sorted(m.reports)
			if r not in site.reports
		)
	lock = _role_names(m, [LOCK_CODE])
	locked = []
	for report, ref_doctype in sorted(site.reports.items()):
		if report in m.reports:
			roles = _role_names(m, m.reports[report])
		else:
			roles = lock
			locked.append(report)
		_set_custom_role("report", report, roles, ref_doctype)
	return locked


def sync_page_roles(m: Matrix) -> list[str]:
	"""Give each listed page its Custom Role. Pages not listed keep frappe's standard roles.

	Returns warning lines for listed pages that do not exist on the site.
	"""
	warnings = []
	for page, codes in m.pages.items():
		if not frappe.db.exists("Page", page):
			warnings.append(f"Page {page!r} is in the matrix but not on the site — skipped")
			continue
		roles = _role_names(m, codes)
		_set_custom_role("page", page, roles)
		# frappe unions the Custom Role with the page's standard roles, so it can only widen access
		standard = frappe.get_all("Has Role", filters={"parenttype": "Page", "parent": page}, pluck="role")
		extra = sorted(set(standard) - set(roles))
		if extra:
			warnings.append(
				f"{page} — 11.8: role chuẩn {', '.join(extra)} nằm ngoài ma trận, Custom Role chỉ mở rộng"
			)
	return warnings


def sync_workspace_roles(m: Matrix) -> list[str]:
	"""Set the roles of each listed workspace (``Has Role`` rows, no document save).

	Returns warning lines for listed workspaces that do not exist on the site.
	"""
	warnings = []
	changed = False
	has_role = frappe.qb.DocType("Has Role")
	for workspace, codes in m.workspaces.items():
		if not frappe.db.exists("Workspace", workspace):
			warnings.append(f"Workspace {workspace!r} is in the matrix but not on the site — skipped")
			continue
		wanted = _role_names(m, codes)
		rows = frappe.get_all(
			"Has Role",
			filters={"parenttype": "Workspace", "parentfield": "roles", "parent": workspace},
			fields=["name", "role", "idx"],
			order_by="idx, name",
		)
		seen: set[str] = set()
		stale = []
		for r in rows:  # roles outside the matrix, and repeats of a role already kept
			if r.role not in wanted or r.role in seen:
				stale.append(r.name)
			seen.add(r.role)
		if stale:
			frappe.qb.from_(has_role).delete().where(has_role.name.isin(stale)).run()
			changed = True
		present = {r.role for r in rows if r.name not in stale}
		idx = max([r.idx for r in rows if r.name not in stale], default=0)
		for role in wanted:
			if role in present:
				continue
			idx += 1
			stamp = now()
			frappe.qb.into(has_role).columns(
				"name",
				"owner",
				"creation",
				"modified",
				"modified_by",
				"docstatus",
				"idx",
				"parent",
				"parentfield",
				"parenttype",
				"role",
			).insert(
				frappe.generate_hash(length=10),
				frappe.session.user,
				stamp,
				stamp,
				frappe.session.user,
				0,
				idx,
				workspace,
				"roles",
				"Workspace",
				role,
			).run()
			changed = True
	if changed:
		frappe.clear_cache()
	return warnings
