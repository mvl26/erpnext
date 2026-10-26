"""Read-only audit report (spec 12, Bước 3.8, plus R-12 and R-22). Nothing here writes: it only lists."""

import frappe

from erpnext.access.permissions.matrix import Matrix
from erpnext.access.permissions.site import SiteInfo

SHOWN = 15
LOCK_CODE = "LK"
SUPER_ADMIN_ROLE = "AssetCore Super Admin"
IT_PROFILE_PREFIX = "RP-IT-QT"
INTERNAL_SKIP = ("Administrator", "Guest")


def _line(title: str, items) -> list[str]:
	"""One audit line: ``title: n — a, b, c, ...``; nothing when ``items`` is empty."""
	items = sorted({str(i) for i in items})
	if not items:
		return []
	more = f", ... (+{len(items) - SHOWN})" if len(items) > SHOWN else ""
	return [f"{title}: {len(items)} — {', '.join(items[:SHOWN])}{more}"]


def _active_employees() -> list[dict]:
	return frappe.get_all(
		"Employee",
		filters={"status": "Active"},
		fields=[
			"name",
			"department",
			"user_id",
			"leave_approver",
			"expense_approver",
			"reports_to",
			"shift_request_approver",
		],
	)


def _department_approvers(parentfield: str | None = None) -> list[dict]:
	filters = {"parenttype": "Department"}
	if parentfield:
		filters["parentfield"] = parentfield
	return frappe.get_all("Department Approver", filters=filters, fields=["parent", "approver"])


def employees_missing_fields(employees) -> list[str]:
	out: list[str] = []
	for field in ("user_id", "leave_approver", "expense_approver"):
		out += _line(f"Employee thiếu {field}", [e.name for e in employees if not e[field]])
	return out


def _profile_roles(profile: str | None) -> set[str]:
	if not profile or not frappe.db.exists("Role Profile", profile):
		return set()
	return {r.role for r in frappe.get_doc("Role Profile", profile).roles}


def approvers_without_tbp(m: Matrix, employees) -> list[str]:
	tbp = {name for code in m.packs["TBP"] for name in m.role_names(code)}
	reports_to_users = {
		frappe.db.get_value("Employee", e.reports_to, "user_id") for e in employees if e.reports_to
	}
	approvers = {
		*(e.leave_approver for e in employees),
		*(e.expense_approver for e in employees),
		*(e.shift_request_approver for e in employees),
		*(a.approver for a in _department_approvers()),
		*reports_to_users,
	} - {None, ""}
	bad = []
	for user in approvers:
		profile = frappe.db.get_value("User", user, "role_profile_name")
		if not tbp <= _profile_roles(profile):
			bad.append(f"{user} ({profile or 'không có profile'})")
	return _line("Người duyệt có profile không chứa TBP (DH, LA, EA)", bad)


def business_trip_coo_without_ap(m: Matrix) -> list[str]:
	ap = set(m.role_names("AP"))
	coos = set(frappe.get_all("Business Trip", filters={"approver_coo": ("is", "set")}, pluck="approver_coo"))
	bad = []
	for user in coos:
		held = set(frappe.get_all("Has Role", filters={"parenttype": "User", "parent": user}, pluck="role"))
		if not held & ap:
			bad.append(user)
	return _line("approver_coo của Business Trip không có AP", bad)


def departments_without_approver() -> list[str]:
	with_rows = {a.parent for a in _department_approvers()}
	names = frappe.get_all("Department", filters={"is_group": 0}, pluck="name")
	return _line("Department chưa có approver", [d for d in names if d not in with_rows])


def employees_without_shift_approver(employees) -> list[str]:
	covered = {a.parent for a in _department_approvers("shift_request_approver")}
	bad = [e.name for e in employees if not e.shift_request_approver and e.department not in covered]
	return _line("Employee chưa có người duyệt ca", bad)


def locked_reports(m: Matrix, site: SiteInfo) -> list[str]:
	return _line("Report đang bị khóa theo R1", [r for r in site.reports if r not in m.reports])


def authorization_rules() -> list[str]:
	rules = frappe.get_all("Authorization Rule", pluck="name")
	return _line("Authorization Rule còn tồn tại", rules)


def super_admins_outside_it() -> list[str]:
	users = frappe.get_all(
		"Has Role", filters={"parenttype": "User", "role": SUPER_ADMIN_ROLE}, pluck="parent"
	)
	bad = []
	for user in set(users) - set(INTERNAL_SKIP):
		profile = frappe.db.get_value("User", user, "role_profile_name") or ""
		if not profile.startswith(IT_PROFILE_PREFIX):
			bad.append(user)
	return _line(f"User có {SUPER_ADMIN_ROLE} ngoài IT-QT", bad)


def internal_users_without_profile() -> list[str]:
	users = frappe.get_all(
		"User",
		filters={"enabled": 1, "user_type": "System User", "name": ("not in", INTERNAL_SKIP)},
		fields=["name", "role_profile_name"],
	)
	return _line("User nội bộ chưa có Role Profile", [u.name for u in users if not u.role_profile_name])


def undeclared_permlevel_fields(m: Matrix, site: SiteInfo) -> list[str]:
	bad = []
	for name, info in site.doctypes.items():
		entry = m.doctypes.get(name)
		declared = {
			f
			for level in (entry.permlevel.values() if entry else ())
			for f in level.get("fields", [])
			if "." not in f
		}
		bad += [f"{name}.{f}" for f in info.high_permlevel_fields - declared]
	return _line("Trường perm level > 0 chưa khai báo ở 11.1", bad)


def mismatched_combined_profiles(m: Matrix) -> list[str]:
	"""R-12: combined ``RP-*+AC-*`` profiles whose roles differ from ERP profile + current assetcore profile."""
	from erpnext.access.permissions.profiles import combined_profile_name

	bad = []
	for pair in m.combined_profiles:
		ac_roles = _profile_roles(pair["assetcore"])
		if not ac_roles:
			continue
		name = combined_profile_name(pair["erp"], pair["assetcore"])
		if _profile_roles(name) != set(m.profile_roles(pair["erp"])) | ac_roles:
			bad.append(name)
	return _line("R-12 profile ghép lệch so với hợp role hiện tại", bad)


def employees_without_reports_to(employees) -> list[str]:
	"""R-22: exactly one root is allowed; list the roots found."""
	roots = [e.name for e in employees if not e.reports_to]
	if len(roots) == 1:
		return []
	if not roots and employees:
		return ["R-22 không có nút gốc — cây reports_to có vòng"]
	return _line("R-22 Employee thiếu reports_to (chỉ được đúng một nút gốc)", roots)


def run_audit(m: Matrix, site: SiteInfo) -> list[str]:
	employees = _active_employees()
	return [
		*employees_missing_fields(employees),
		*approvers_without_tbp(m, employees),
		*business_trip_coo_without_ap(m),
		*departments_without_approver(),
		*employees_without_shift_approver(employees),
		*locked_reports(m, site),
		*authorization_rules(),
		*super_admins_outside_it(),
		*internal_users_without_profile(),
		*undeclared_permlevel_fields(m, site),
		*mismatched_combined_profiles(m),
		*employees_without_reports_to(employees),
	]
