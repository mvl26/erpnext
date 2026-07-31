# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Vietnam go-live: standard Role Profiles for the Miyano operating team.

``ensure_vn_role_profiles()`` creates the department Role Profiles a VN deployment
assigns to real users at go-live (users themselves are created in the runbook, not
here). Idempotent: re-running only adds missing roles and never duplicates.
"""

import frappe

# Role Profile (tiếng Việt) -> the standard ERPNext roles it grants.
VN_ROLE_PROFILES = {
	"Kế toán": ["Accounts User"],
	"Kế toán trưởng": ["Accounts Manager", "Accounts User"],
	"Thủ kho": ["Stock User"],
	"Bán hàng": ["Sales User"],
	"Mua hàng": ["Purchase User"],
	"Quản lý": ["Accounts Manager", "Sales Manager", "Purchase Manager", "Stock Manager"],
}


def ensure_vn_role_profiles():
	"""Create/extend the VN department Role Profiles (idempotent). Returns their names."""
	return [_ensure_role_profile(name, roles) for name, roles in VN_ROLE_PROFILES.items()]


def _ensure_role_profile(name, roles):
	roles = [r for r in roles if frappe.db.exists("Role", r)]

	if frappe.db.exists("Role Profile", name):
		profile = frappe.get_doc("Role Profile", name)
	else:
		profile = frappe.new_doc("Role Profile")
		profile.role_profile = name

	have = {r.role for r in profile.roles}
	added = False
	for role in roles:
		if role not in have:
			profile.append("roles", {"role": role})
			added = True

	if profile.is_new():
		profile.flags.ignore_permissions = True
		profile.insert()
	elif added:
		profile.flags.ignore_permissions = True
		profile.save()
	return name
