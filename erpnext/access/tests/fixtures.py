"""Fixture users for the RBAC permission sweep — one real User per Role Profile."""

import re

import frappe


def _slug(profile: str) -> str:
	return re.sub(r"[^a-z0-9]+", "-", profile.lower()).strip("-") or "profile"


def make_employee_for(user: str | None, department: str | None = None, **fields) -> str:
	"""Insert a minimal Employee linked to ``user`` (inside the test transaction); return its name.

	On a synced site the matrix makes ``leave_approver`` and ``expense_approver`` mandatory (Property Setters);
	they are filled with Administrator unless passed in ``fields``.
	"""
	meta = frappe.get_meta("Employee")
	for approver in ("leave_approver", "expense_approver"):
		field = meta.get_field(approver)
		if field and field.reqd:
			fields.setdefault(approver, "Administrator")
	gender = frappe.db.get_value("Gender", {}, "name")
	if not gender:
		frappe.throw("make_employee_for needs at least one Gender record on the site")
	company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
	doc = frappe.get_doc(
		{
			"doctype": "Employee",
			"first_name": "Rbac",
			"last_name": frappe.generate_hash(length=6),
			"gender": gender,
			"date_of_birth": "1990-01-01",
			"date_of_joining": "2020-01-01",
			"company": company,
			"status": "Active",
			"user_id": user,
			"department": department,
			**fields,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def make_profile_user(profile: str) -> str:
	"""Insert a throwaway User on Role Profile ``profile`` (roles come from the profile); return its email.

	A linked Employee is created when the profile includes the Employee role.
	"""
	email = f"rbac-{_slug(profile)}-{frappe.generate_hash(length=6)}@example.com"
	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": "Rbac",
			"send_welcome_email": 0,
			"role_profile_name": profile,
		}
	)
	user.insert(ignore_permissions=True)
	if "Employee" in {r.role for r in user.roles}:
		make_employee_for(email)
	frappe.clear_cache(user=email)
	return email
