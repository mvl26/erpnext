# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Custom field trên Delivery Note (mục C5) và hai Role của Giai đoạn 2."""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.einvoice.constants import STATUSES
from erpnext.einvoice.setup import (
	ROLE_CHIEF,
	ROLE_STAFF,
	is_chief_accountant,
	setup_einvoice,
)

FEI = "Fast EInvoice Document"


class TestEInvoiceSetup(FrappeTestCase):
	def tearDown(self):
		frappe.db.rollback()

	# --- Custom field trên Delivery Note (C5) -----------------------------

	def test_delivery_note_carries_the_einvoice_fields(self):
		meta = frappe.get_meta("Delivery Note")
		self.assertEqual(meta.get_field("fast_einvoice").options, FEI)
		self.assertEqual(meta.get_field("fast_invoice_no").fieldtype, "Data")
		self.assertEqual(meta.get_field("fast_einvoice_status").fieldtype, "Select")
		self.assertEqual(meta.get_field("fast_key_search").fieldtype, "Data")

	def test_einvoice_fields_are_read_only_on_the_delivery_note(self):
		"""Số hóa đơn và mã tra cứu do Fast cấp — gõ tay là làm sai chứng từ."""
		meta = frappe.get_meta("Delivery Note")
		for fieldname in ("fast_einvoice", "fast_invoice_no", "fast_einvoice_status", "fast_key_search"):
			self.assertEqual(meta.get_field(fieldname).read_only, 1, fieldname)

	def test_status_mirror_offers_the_same_states_as_the_document(self):
		options = frappe.get_meta("Delivery Note").get_field("fast_einvoice_status").options.split("\n")
		self.assertEqual(options, ["", *STATUSES])

	def test_lookup_key_is_hidden_as_a_backup_copy(self):
		self.assertEqual(frappe.get_meta("Delivery Note").get_field("fast_key_search").hidden, 1)

	def test_invoice_number_is_filterable_from_the_list(self):
		"""Đặc tả C5: hiện trên list view để lọc nhanh."""
		self.assertEqual(frappe.get_meta("Delivery Note").get_field("fast_invoice_no").in_standard_filter, 1)

	# --- Hai Role ---------------------------------------------------------

	def test_both_roles_exist(self):
		self.assertTrue(frappe.db.exists("Role", ROLE_STAFF))
		self.assertTrue(frappe.db.exists("Role", ROLE_CHIEF))

	def test_staff_can_prepare_invoices_but_not_delete_them(self):
		perms = frappe.permissions.get_all_perms(ROLE_STAFF)
		fei = [p for p in perms if p.parent == FEI]
		self.assertTrue(fei, "Kế toán HĐĐT chưa có quyền nào trên chứng từ HĐĐT")
		self.assertEqual(fei[0].write, 1)
		self.assertEqual(fei[0].create, 1)
		self.assertEqual(fei[0].delete, 0)

	def test_chief_accountant_may_delete(self):
		perms = frappe.permissions.get_all_perms(ROLE_CHIEF)
		fei = [p for p in perms if p.parent == FEI]
		self.assertTrue(fei, "Kế toán trưởng HĐĐT chưa có quyền nào trên chứng từ HĐĐT")
		self.assertEqual(fei[0].delete, 1)

	def test_logs_are_readable_but_not_writable_by_either_role(self):
		for role in (ROLE_STAFF, ROLE_CHIEF):
			log_perms = [p for p in frappe.permissions.get_all_perms(role) if p.parent == "Fast EInvoice Log"]
			self.assertTrue(log_perms, role)
			self.assertEqual(log_perms[0].read, 1, role)
			self.assertEqual(log_perms[0].write, 0, role)

	# --- Cổng quyền phát hành ---------------------------------------------

	def test_issuing_rights_are_limited_to_the_chief_accountant(self):
		"""Nút cấp 3 (phát hành, hủy) chỉ dành cho kế toán trưởng."""
		user = _ensure_user("fei-staff@example.com", ROLE_STAFF)
		with _as(user):
			self.assertFalse(is_chief_accountant())

		chief = _ensure_user("fei-chief@example.com", ROLE_CHIEF)
		with _as(chief):
			self.assertTrue(is_chief_accountant())

	# --- Chạy lại không nhân đôi ------------------------------------------

	def test_setup_is_idempotent(self):
		before = frappe.db.count("Custom Field", {"fieldname": ["like", "fast_%"], "dt": "Delivery Note"})
		setup_einvoice()
		after = frappe.db.count("Custom Field", {"fieldname": ["like", "fast_%"], "dt": "Delivery Note"})
		self.assertEqual(before, after)


def _ensure_user(email, role):
	if not frappe.db.exists("User", email):
		user = frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0}
		)
		user.flags.ignore_permissions = True
		user.insert()
	else:
		user = frappe.get_doc("User", email)
	if role not in [r.role for r in user.roles]:
		user.append("roles", {"role": role})
		user.flags.ignore_permissions = True
		user.save()
	return email


class _as:
	"""Đổi tạm session user."""

	def __init__(self, user):
		self.user = user

	def __enter__(self):
		self.previous = frappe.session.user
		frappe.set_user(self.user)

	def __exit__(self, *exc):
		frappe.set_user(self.previous)
