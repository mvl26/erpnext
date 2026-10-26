"""Roles and Role Profiles — creates the new roles (3.1), keeps ``desk_access`` right, and makes every
``RP-*`` profile (plus the combined ERP + assetcore ones) hold exactly the roles the matrix says (section 4).

Roles are never disabled here — retiring the 3.3 roles belongs to the cutover.
"""

import frappe

from erpnext.access.permissions.matrix import Matrix


def combined_profile_name(erp: str, assetcore: str) -> str:
	return f"{erp}+AC-{assetcore}"


def sync_roles(m: Matrix) -> int:
	"""Create missing matrix roles (``is_custom = 1``) and set ``desk_access`` where it differs.

	Roles outside the matrix are not touched. Returns the number of roles created or changed.
	"""
	changed = 0
	for role in m.roles.values():
		desk = int(role.desk_access)
		for name in role.names:
			current = frappe.db.get_value("Role", name, "desk_access")
			if current is None and not frappe.db.exists("Role", name):
				frappe.get_doc(
					{"doctype": "Role", "role_name": name, "desk_access": desk, "is_custom": 1}
				).insert(ignore_permissions=True)
				changed += 1
			elif int(current or 0) != desk:
				doc = frappe.get_doc("Role", name)
				doc.desk_access = desk
				doc.save(ignore_permissions=True)
				changed += 1
	return changed


def _set_profile_roles(name: str, roles) -> bool:
	"""Make Role Profile ``name`` hold exactly ``roles``; save only when the set differs."""
	wanted = list(dict.fromkeys(roles))
	if frappe.db.exists("Role Profile", name):
		doc = frappe.get_doc("Role Profile", name)
		if {r.role for r in doc.roles} == set(wanted) and len(doc.roles) == len(wanted):
			return False
		doc.set("roles", [])
		for role in wanted:
			doc.append("roles", {"role": role})
		doc.save(ignore_permissions=True)
		return True
	doc = frappe.get_doc({"doctype": "Role Profile", "role_profile": name})
	for role in wanted:
		doc.append("roles", {"role": role})
	doc.insert(ignore_permissions=True)
	return True


def sync_role_profiles(m: Matrix) -> list[str]:
	"""Bring every ``RP-*`` profile and every combined profile to the matrix.

	A combined profile whose assetcore profile is missing on the site is skipped; one warning line per
	skipped profile is returned (an empty list when all went well).
	"""
	for profile in m.role_profiles:
		_set_profile_roles(profile, m.profile_roles(profile))

	warnings: list[str] = []
	for pair in m.combined_profiles:
		erp, assetcore = pair["erp"], pair["assetcore"]
		if not frappe.db.exists("Role Profile", assetcore):
			warnings.append(
				f"Combined profile {combined_profile_name(erp, assetcore)} skipped — "
				f"assetcore Role Profile {assetcore!r} not found on site"
			)
			continue
		ac_roles = [r.role for r in frappe.get_doc("Role Profile", assetcore).roles]
		_set_profile_roles(combined_profile_name(erp, assetcore), [*m.profile_roles(erp), *ac_roles])
	return warnings
