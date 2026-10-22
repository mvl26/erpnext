# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Custom field trên Sales Invoice (mục C5), field bản 2.0 trên Delivery Note, hai Role, hai mẫu email."""

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

	# --- Custom field trên Sales Invoice (C5) -----------------------------

	def test_sales_invoice_carries_the_einvoice_copy(self):
		meta = frappe.get_meta("Sales Invoice")
		self.assertEqual(meta.get_field("fast_invoice_no").fieldtype, "Data")
		self.assertEqual(meta.get_field("fast_einvoice_status").fieldtype, "Select")
		self.assertEqual(meta.get_field("fast_key_search").fieldtype, "Data")
		self.assertEqual(meta.get_field("fast_einvoice_pdf_url").fieldtype, "Data")

	def test_there_is_no_link_back_to_the_einvoice(self):
		"""Hai Link trỏ vòng từng làm không xóa được nháp, không hủy được chứng từ nguồn."""
		meta = frappe.get_meta("Sales Invoice")
		links = [f.fieldname for f in meta.fields if f.fieldtype == "Link" and f.options == FEI]
		self.assertEqual(links, [])

	def test_the_copy_is_read_only_and_never_copied(self):
		"""Số hóa đơn do Fast cấp; `no_copy` để hóa đơn trả hàng / sửa lại không mang theo số."""
		meta = frappe.get_meta("Sales Invoice")
		for fieldname in (
			"fast_invoice_no",
			"fast_einvoice_status",
			"fast_key_search",
			"fast_einvoice_pdf_url",
		):
			with self.subTest(fieldname=fieldname):
				self.assertEqual(meta.get_field(fieldname).read_only, 1)
				self.assertEqual(meta.get_field(fieldname).no_copy, 1)

	def test_status_mirror_offers_the_same_states_as_the_document(self):
		options = frappe.get_meta("Sales Invoice").get_field("fast_einvoice_status").options.split("\n")
		self.assertEqual(options, ["", *STATUSES])

	def test_lookup_key_is_hidden_as_a_backup_copy(self):
		self.assertEqual(frappe.get_meta("Sales Invoice").get_field("fast_key_search").hidden, 1)

	def test_invoice_number_is_filterable_from_the_list(self):
		"""Đặc tả C5: hiện trên list view để lọc nhanh."""
		self.assertEqual(frappe.get_meta("Sales Invoice").get_field("fast_invoice_no").in_standard_filter, 1)

	# --- Field bản 2.0 trên Delivery Note: ẩn, không xóa -------------------

	def test_delivery_note_keeps_its_v2_fields_hidden(self):
		"""Sáu hóa đơn bản 2.0 vẫn ghi vào đây — xóa là mất dấu, hiện ra là hai nơi cùng nói về hóa đơn."""
		meta = frappe.get_meta("Delivery Note")
		for fieldname in ("fast_einvoice", "fast_invoice_no", "fast_einvoice_status", "fast_key_search"):
			with self.subTest(fieldname=fieldname):
				self.assertTrue(meta.has_field(fieldname))
				self.assertEqual(meta.get_field(fieldname).hidden, 1)

	# --- Mẫu email ----------------------------------------------------------

	def test_email_templates_name_the_sales_invoice(self):
		"""Bản ghi mới không có phiếu giao: tiêu đề nêu `doc.delivery_note` sẽ ra trống.

		Chỉ mẫu bản nháp nêu chứng từ nguồn; mẫu hóa đơn chính thức theo mẫu Miyano
		nêu số hóa đơn, không nêu chứng từ nguồn — nhưng cũng không được nêu phiếu giao.
		"""
		from erpnext.einvoice.setup import DRAFT_TEMPLATE, ISSUED_TEMPLATE

		for name in (DRAFT_TEMPLATE, ISSUED_TEMPLATE):
			with self.subTest(template=name):
				template = frappe.get_doc("Email Template", name)
				text = f"{template.subject} {template.response_html or template.response}"
				self.assertNotIn("{{ doc.delivery_note }}", text)
				if name == DRAFT_TEMPLATE:
					self.assertIn("doc.sales_invoice", text)

	def test_a_v2_template_is_retargeted(self):
		from erpnext.einvoice.setup import _retarget_to_sales_invoice

		name = f"_Test HĐĐT mẫu {frappe.generate_hash(length=6)}"
		frappe.get_doc(
			{
				"doctype": "Email Template",
				"name": name,
				"subject": "[BẢN NHÁP hóa đơn] {{ doc.delivery_note }} — Miyano Việt Nam",
				"use_html": 1,
				"response_html": "<p>hóa đơn cho phiếu giao\n<b>{{ doc.delivery_note }}</b> để</p>",
			}
		).insert(ignore_permissions=True)

		_retarget_to_sales_invoice(name)

		template = frappe.get_doc("Email Template", name)
		self.assertIn("{{ doc.sales_invoice or doc.delivery_note }}", template.subject)
		self.assertNotIn("cho phiếu giao\n", template.response_html)

	def test_a_rendered_subject_shows_the_sales_invoice(self):
		from erpnext.einvoice.setup import DRAFT_TEMPLATE

		subject = frappe.db.get_value("Email Template", DRAFT_TEMPLATE, "subject")
		rendered = frappe.render_template(subject, {"doc": frappe._dict(sales_invoice="ACC-SINV-2026-00011")})
		self.assertIn("ACC-SINV-2026-00011", rendered)

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
		def count():
			return frappe.db.count(
				"Custom Field",
				{"fieldname": ["like", "fast_%"], "dt": ["in", ["Delivery Note", "Sales Invoice"]]},
			)

		before = count()
		setup_einvoice()
		self.assertEqual(before, count())


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
