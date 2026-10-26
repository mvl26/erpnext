"""Settings, 2FA per role and the Module Profile "MVL PDA" (spec 11.5).

Every write is diffed — a value is only written when it differs, so a second run writes nothing.
Singles go through ``frappe.db.set_single_value`` (no Settings controller runs), so a field whose
controller must fire on change needs its own handling.
"""

import frappe

from erpnext.access.permissions.matrix import Matrix

TWO_FA_CODES = ("SYS", "AM", "HM")
APPS = ("frappe", "erpnext", "hrms")


# --- precondition checks for guarded settings (pure reads) ---


def no_negative_bins() -> bool:
	return not frappe.db.sql("select 1 from `tabBin` where actual_qty < 0 limit 1")


def no_open_orders_with_rate_mismatch() -> bool:
	"""No submitted, open Sales Order has a submitted invoice line billed at a different rate."""
	return not frappe.db.sql(
		"""select 1 from `tabSales Order` so
		join `tabSales Order Item` soi on soi.parent = so.name
		join `tabSales Invoice Item` sii on sii.so_detail = soi.name and sii.docstatus = 1
		where so.docstatus = 1 and so.status not in ('Closed', 'Completed') and sii.rate != soi.rate
		limit 1"""
	)


def password_policy_ok() -> bool:
	"""Payroll Settings.password_policy is non-empty and formats against Employee fieldnames.

	Mirrors hrms salary_slip: ``policy_template.format(**employee)``.
	"""
	policy = frappe.db.get_single_value("Payroll Settings", "password_policy")
	if not policy or not policy.strip():
		return False
	dummy = {df.fieldname: "x" for df in frappe.get_meta("Employee").fields}
	try:
		policy.format(**dummy)
	except (KeyError, ValueError, IndexError, AttributeError):
		return False
	return True


CHECKS = {
	"no_negative_bins": no_negative_bins,
	"no_open_orders_with_rate_mismatch": no_open_orders_with_rate_mismatch,
	"password_policy_ok": password_policy_ok,
}


def _same(current, wanted) -> bool:
	if current in (None, ""):
		current = "" if isinstance(wanted, str) else 0
	if isinstance(wanted, str) or isinstance(current, str):
		return str(current or "") == str(wanted or "")
	return float(current) == float(wanted)


def _apply_single(doctype: str, field: str, wanted) -> bool:
	if _same(frappe.db.get_single_value(doctype, field), wanted):
		return False
	frappe.db.set_single_value(doctype, field, wanted)
	return True


def sync_two_factor_roles(m: Matrix) -> int:
	changed = 0
	for code in TWO_FA_CODES:
		for name in m.role_names(code):
			if frappe.db.get_value("Role", name, "two_factor_auth") is None:
				continue
			if not frappe.utils.cint(frappe.db.get_value("Role", name, "two_factor_auth")):
				frappe.db.set_value("Role", name, "two_factor_auth", 1)
				changed += 1
	return changed


def sync_settings(m: Matrix) -> list[str]:
	"""Apply ``m.settings``; returns audit lines for what was skipped."""
	audit = []
	settings = m.settings
	guarded = settings.get("guarded", {})
	for target, values in settings.items():
		if target == "guarded":
			continue
		if "::" in target:
			doctype, name = target.split("::", 1)
			if not frappe.db.exists(doctype, name):
				audit.append(f"{target}: not found, skipped")
				continue
			for field, wanted in values.items():
				if not _same(frappe.db.get_value(doctype, name, field), wanted):
					frappe.db.set_value(doctype, name, field, wanted)
			continue
		for field, wanted in values.items():
			check = guarded.get(f"{target}.{field}")
			if check and not _same(frappe.db.get_single_value(target, field), wanted):
				fn = CHECKS.get(check)
				if fn is None:
					audit.append(f"{target}.{field}: not applied, unknown check {check}")
					continue
				if not fn():
					audit.append(f"{target}.{field}: not applied, precondition {check} failed")
					continue
			_apply_single(target, field, wanted)
	sync_two_factor_roles(m)
	return audit


def sync_module_profiles(m: Matrix) -> None:
	for name, cfg in m.module_profiles.items():
		allow = set(cfg["allow_modules"])
		blocked = sorted(
			frappe.get_all("Module Def", filters={"app_name": ["in", APPS]}, pluck="name"),
		)
		blocked = [x for x in blocked if x not in allow]
		if frappe.db.exists("Module Profile", name):
			doc = frappe.get_doc("Module Profile", name)
			if {r.module for r in doc.block_modules} == set(blocked):
				continue
			doc.set("block_modules", [])
		else:
			doc = frappe.get_doc({"doctype": "Module Profile", "module_profile_name": name})
		for module in blocked:
			doc.append("block_modules", {"module": module})
		doc.save(ignore_permissions=True)
