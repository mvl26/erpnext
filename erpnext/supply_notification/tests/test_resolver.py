# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.supply_notification import resolver
from erpnext.supply_notification.setup import default_company, root_department


def make_user(enabled=1) -> str:
	email = f"sn-{frappe.generate_hash(length=10)}@example.com"
	user = frappe.new_doc("User")
	user.email = email
	user.first_name = "Nguoi"
	user.last_name = frappe.generate_hash(length=4)
	user.enabled = enabled
	user.send_welcome_email = 0
	user.insert(ignore_permissions=True)
	return user.name


def make_department(is_group=0, parent=None, disabled=0) -> str:
	doc = frappe.new_doc("Department")
	doc.department_name = f"Phong {frappe.generate_hash(length=6)}"
	doc.company = default_company()
	doc.is_group = is_group
	doc.disabled = disabled
	doc.parent_department = parent or root_department()
	doc.insert(ignore_permissions=True)
	return doc.name


def make_employee(department, user_id=None, status="Active") -> str:
	gender = frappe.get_all("Gender", pluck="name", limit=1)
	doc = frappe.new_doc("Employee")
	doc.first_name = f"NV {frappe.generate_hash(length=5)}"
	doc.company = default_company()
	doc.status = status
	doc.gender = gender[0] if gender else None
	doc.date_of_birth = "1990-01-01"
	doc.date_of_joining = "2020-01-01"
	doc.department = department
	doc.user_id = user_id
	if status == "Left":
		doc.relieving_date = "2024-01-01"
	doc.insert(ignore_permissions=True)
	return doc.name


def make_point(**kwargs) -> "frappe.Document":
	doc = frappe.new_doc("Supply Notification Point")
	doc.code = f"NTF-T-{frappe.generate_hash(length=6)}"
	doc.title = "Điểm thử"
	doc.reference_doctype = "Sales Order"
	doc.trigger_event = "Submit"
	doc.subject_template = "Thử {{ doc.name }}"
	doc.send_email = 1
	doc.send_inapp = 1
	for department in kwargs.pop("departments", []):
		doc.append("departments", {"department": department})
	for user in kwargs.pop("users", []):
		doc.append("users", {"user": user})
	doc.update(kwargs)
	doc.insert(ignore_permissions=True)
	return doc


class TestResolverDepartments(FrappeTestCase):
	def test_expand_includes_child_departments(self):
		parent = make_department(is_group=1)
		child = make_department(parent=parent)

		self.assertEqual(resolver.expand_departments([parent]), {parent, child})

	def test_expand_drops_disabled_department(self):
		department = make_department(disabled=1)

		self.assertEqual(resolver.expand_departments([department]), set())

	def test_expand_handles_empty_input(self):
		self.assertEqual(resolver.expand_departments([]), set())
		self.assertEqual(resolver.expand_departments([None]), set())

	def test_users_in_departments_needs_active_employee_with_account(self):
		department = make_department()
		linked = make_user()
		make_employee(department, user_id=linked)
		make_employee(department, user_id=None)
		resigned = make_user()
		make_employee(department, user_id=resigned, status="Left")

		self.assertEqual(resolver.users_in_departments([department]), {linked})

	def test_employees_without_user_reports_the_gap(self):
		department = make_department()
		make_employee(department, user_id=None)

		self.assertEqual(len(resolver.employees_without_user([department])), 1)


class TestResolverRecipients(FrappeTestCase):
	def test_filter_valid_drops_system_and_disabled_users(self):
		active = make_user()
		blocked = make_user(enabled=0)

		names = {row.name for row in resolver.filter_valid({active, blocked, "Administrator", "Guest"})}

		self.assertEqual(names, {active})

	def test_resolve_merges_departments_and_named_users(self):
		department = make_department()
		from_department = make_user()
		make_employee(department, user_id=from_department)
		named = make_user()
		point = make_point(departments=[department], users=[named])

		names = {row.name for row in resolver.resolve(point)}

		self.assertEqual(names, {from_department, named})

	def test_resolve_deduplicates_the_same_person(self):
		department = make_department()
		user = make_user()
		make_employee(department, user_id=user)
		point = make_point(departments=[department], users=[user])

		self.assertEqual([row.name for row in resolver.resolve(point)], [user])

	def test_resolve_adds_document_owner_only_when_flagged(self):
		named = make_user()
		owner = make_user()
		doc = frappe.new_doc("Sales Order")
		doc.owner = owner

		without = make_point(users=[named], notify_owner=0)
		self.assertEqual({row.name for row in resolver.resolve(without, doc)}, {named})

		with_owner = make_point(users=[named], notify_owner=1)
		self.assertEqual({row.name for row in resolver.resolve(with_owner, doc)}, {named, owner})


class TestResolverPreview(FrappeTestCase):
	def test_preview_lists_recipients_with_source(self):
		department = make_department()
		user = make_user()
		make_employee(department, user_id=user)
		point = make_point(departments=[department])

		result = resolver.preview(point.name)

		self.assertEqual([row["user"] for row in result["recipients"]], [user])
		self.assertEqual(result["recipients"][0]["sources"], [resolver.SOURCE_DEPARTMENT])

	def test_preview_warns_when_employees_have_no_account(self):
		department = make_department()
		make_employee(department, user_id=None)
		point = make_point(departments=[department])

		warnings = " ".join(resolver.preview(point.name)["warnings"])

		self.assertIn("chưa gắn tài khoản", warnings)

	def test_preview_warns_when_point_disabled(self):
		point = make_point(users=[make_user()], enabled=0)

		self.assertTrue(any("đang tắt" in w for w in resolver.preview(point.name)["warnings"]))


class TestResolverExternalEmail(FrappeTestCase):
	def test_prefers_contact_email_on_document(self):
		doc = frappe.new_doc("Purchase Order")
		doc.contact_email = "ncc@example.com"

		self.assertEqual(resolver.external_email(doc), "ncc@example.com")

	def test_uses_email_to_for_payment_request(self):
		doc = frappe.new_doc("Payment Request")
		doc.email_to = "khach@example.com"

		self.assertEqual(resolver.external_email(doc), "khach@example.com")

	def test_falls_back_to_primary_contact_of_party(self):
		supplier = frappe.new_doc("Supplier")
		supplier.supplier_name = f"NCC {frappe.generate_hash(length=6)}"
		supplier.insert(ignore_permissions=True)

		contact = frappe.new_doc("Contact")
		contact.first_name = "Lien he"
		contact.is_primary_contact = 1
		contact.append("email_ids", {"email_id": "primary@example.com", "is_primary": 1})
		contact.append("links", {"link_doctype": "Supplier", "link_name": supplier.name})
		contact.insert(ignore_permissions=True)

		doc = frappe.new_doc("Purchase Order")
		doc.supplier = supplier.name

		self.assertEqual(resolver.external_email(doc), "primary@example.com")

	def test_returns_none_when_nothing_is_configured(self):
		supplier = frappe.new_doc("Supplier")
		supplier.supplier_name = f"NCC {frappe.generate_hash(length=6)}"
		supplier.insert(ignore_permissions=True)

		doc = frappe.new_doc("Purchase Order")
		doc.supplier = supplier.name

		self.assertIsNone(resolver.external_email(doc))
