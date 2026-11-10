# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Mẫu email hóa đơn chính thức theo mẫu Miyano (phân tích "Tự gửi HĐĐT", mục 4)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from erpnext.einvoice.actions import _render_template
from erpnext.einvoice.builder import create_from_sales_invoice
from erpnext.einvoice.constants import STATUS_ISSUED
from erpnext.einvoice.fast_settings import get_settings
from erpnext.einvoice.invoice_email import cc_for, email_context, sender_for
from erpnext.einvoice.setup import (
	_PREVIOUS_ISSUED_HTML,
	ISSUED_HTML,
	ISSUED_SUBJECT,
	ISSUED_TEMPLATE,
	upgrade_issued_template,
)
from erpnext.einvoice.tests.test_fast_client import configure
from erpnext.einvoice.tests.test_fixtures import LOOKUP_CODE, attach_official_xml, make_sales_invoice

FEI = "Fast EInvoice Document"
TAX_CODE = "TEST0000000020260908T154940190TEST"
KEY_SEARCH = "AQAAAGdsR7FQfhxF8IACz4v01==008254"


def use_miyano_template():
	"""Mẫu trên site chỉ đổi khi migrate — test dựng đúng mẫu mới trong giao dịch của mình."""
	template = frappe.get_doc("Email Template", ISSUED_TEMPLATE)
	template.update({"subject": ISSUED_SUBJECT, "response_html": ISSUED_HTML, "response": ISSUED_HTML})
	template.flags.ignore_permissions = True
	template.save()


class InvoiceEmailBase(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure(token="TOKEN-ABC", token_time=now_datetime())
		use_miyano_template()
		self.si = make_sales_invoice()
		self.fei = frappe.get_doc(FEI, create_from_sales_invoice(self.si.name))
		frappe.db.set_value(
			FEI,
			self.fei.name,
			{
				"status": STATUS_ISSUED,
				"fast_key_search": KEY_SEARCH,
				"fast_invoice_no": "4",
				"fast_pattern": "1",
				"fast_serial": "C26TAA",
				"fast_signed_date": "2026-09-08",
				"fast_lookup_code": LOOKUP_CODE,
				"fast_lookup_url": "https://tinvoice.fast.com.vn:8000/",
				"tax_verification_code": TAX_CODE,
			},
		)
		self.fei.reload()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def _render(self, user=None):
		self.fei.reload()
		settings = get_settings()
		hd = email_context(self.fei, settings, sender_for(settings, user))
		return _render_template(ISSUED_TEMPLATE, self.fei, extra_context={"hd": hd})


class TestIssuedEmailContent(InvoiceEmailBase):
	def test_renders_number_symbol_tax_code_and_lookup_code(self):
		message = self._render()["message"]
		for expected in ("4", "1C26TAA", TAX_CODE, LOOKUP_CODE, "TRA CỨU", "08/09/2026"):
			self.assertIn(expected, message)

	def test_the_long_api_key_is_never_shown(self):
		self.assertNotIn(KEY_SEARCH, self._render()["message"])

	def test_subject_follows_the_miyano_pattern(self):
		self.assertEqual(
			self._render()["subject"],
			f"CÔNG TY TNHH MIYANO VIỆT NAM gửi hóa đơn điện tử số 4 cho {self.fei.customer_name}",
		)

	def test_the_lookup_link_points_to_the_fast_portal(self):
		self.assertIn('href="https://tinvoice.fast.com.vn:8000/"', self._render()["message"])

	def test_settings_lookup_url_is_the_fallback(self):
		configure(lookup_url="https://tracuu.example/")
		frappe.db.set_value(FEI, self.fei.name, "fast_lookup_url", "")
		self.assertIn('href="https://tracuu.example/"', self._render()["message"])

	def test_no_lookup_block_without_a_lookup_code(self):
		frappe.db.set_value(FEI, self.fei.name, "fast_lookup_code", "")
		self.assertNotIn("TRA CỨU", self._render()["message"])

	def test_tax_code_row_hidden_until_the_tax_office_answers(self):
		frappe.db.set_value(FEI, self.fei.name, "tax_verification_code", "")
		self.assertNotIn("Mã của cơ quan thuế", self._render()["message"])

	def test_po_and_due_date_rows_hidden_when_empty(self):
		frappe.db.set_value("Sales Invoice", self.si.name, {"po_no": "", "due_date": None})
		message = self._render()["message"]
		self.assertNotIn("Theo hợp đồng/đơn hàng", message)
		self.assertNotIn("Hạn thanh toán", message)

	def test_po_and_due_date_rows_show_when_set(self):
		frappe.db.set_value("Sales Invoice", self.si.name, {"po_no": "PO-BV-778", "due_date": "2026-10-31"})
		message = self._render()["message"]
		self.assertIn("PO-BV-778", message)
		self.assertIn("31/10/2026", message)

	def test_xml_sentence_follows_the_attachment(self):
		self.assertIn("tải file XML (hóa đơn điện tử gốc) tại trang tra cứu", self._render()["message"])

		attach_official_xml(self.fei.name)
		self.assertIn("hóa đơn dạng PDF và file XML", self._render()["message"])

	def test_no_esign_promise(self):
		self.assertNotIn("ký điện tử", self._render()["message"])

	def test_no_public_erp_link(self):
		frappe.db.set_value(FEI, self.fei.name, "public_pdf_url", "http://miyano/files/x.pdf")
		self.assertNotIn("http://miyano/files/x.pdf", self._render()["message"])

	def test_buyer_name_in_the_greeting(self):
		frappe.db.set_value(FEI, self.fei.name, "buyer", "Chị Lan")
		self.assertIn("Kính gửi: Chị Lan", self._render()["message"])

	def test_greeting_falls_back_to_quy_khach(self):
		frappe.db.set_value(FEI, self.fei.name, "buyer", "")
		self.assertIn("Kính gửi: Quý khách", self._render()["message"])

	def test_signature_carries_the_settings_contact(self):
		configure(
			invoice_sender_name="Nguyễn Văn A",
			invoice_sender_phone="0901234567",
			invoice_sender_email="hd@miyano.vn",
		)
		message = self._render()["message"]
		for expected in ("Nguyễn Văn A", "0901234567", "hd@miyano.vn"):
			self.assertIn(expected, message)


class TestSenderAndCc(InvoiceEmailBase):
	def test_automatic_sender_comes_from_settings(self):
		configure(invoice_sender_name="Nguyễn Văn A", invoice_sender_email="hd@miyano.vn")
		self.assertEqual(
			sender_for(get_settings(), None), {"name": "Nguyễn Văn A", "phone": "", "email": "hd@miyano.vn"}
		)

	def test_administrator_counts_as_automatic(self):
		configure(invoice_sender_name="Nguyễn Văn A")
		self.assertEqual(sender_for(get_settings(), "Administrator")["name"], "Nguyễn Văn A")

	def test_manual_sender_is_the_logged_in_user_with_settings_fallback(self):
		configure(invoice_sender_phone="0901234567", invoice_sender_email="hd@miyano.vn")
		email = f"_test_hddt_{frappe.generate_hash(length=6)}@miyano.vn"
		user = frappe.get_doc({"doctype": "User", "email": email, "first_name": "Trần Thị B"})
		user.flags.ignore_permissions = True
		user.insert()

		self.assertEqual(
			sender_for(get_settings(), email), {"name": "Trần Thị B", "phone": "0901234567", "email": email}
		)

	def test_cc_merges_settings_and_dialog_without_duplicates(self):
		configure(invoice_email_cc="kt@miyano.vn")
		self.assertEqual(cc_for(get_settings(), "KT@miyano.vn; khac@x.vn"), ["kt@miyano.vn", "khac@x.vn"])

	def test_cc_accepts_a_list(self):
		configure(invoice_email_cc="")
		self.assertEqual(cc_for(get_settings(), ["a@x.vn", " ", "b@x.vn"]), ["a@x.vn", "b@x.vn"])


class TestTemplateUpgrade(FrappeTestCase):
	"""Patch chỉ thay mẫu khi mẫu còn nguyên bản hệ thống tạo (mục 4.2)."""

	def setUp(self):
		frappe.db.rollback()

	def tearDown(self):
		frappe.db.rollback()

	def _set_template(self, html, subject="[Hóa đơn điện tử] Số {{ doc.fast_invoice_no }} — Miyano Việt Nam"):
		template = frappe.get_doc("Email Template", ISSUED_TEMPLATE)
		template.update({"subject": subject, "response_html": html, "response": html})
		template.flags.ignore_permissions = True
		template.save()

	def test_original_template_is_upgraded(self):
		self._set_template(_PREVIOUS_ISSUED_HTML)

		self.assertTrue(upgrade_issued_template())
		template = frappe.get_doc("Email Template", ISSUED_TEMPLATE)
		self.assertEqual(template.subject, ISSUED_SUBJECT)
		self.assertEqual(template.response_html, ISSUED_HTML)

	def test_whitespace_differences_still_count_as_original(self):
		self._set_template(_PREVIOUS_ISSUED_HTML.replace("\n", "\n\n  "))
		self.assertTrue(upgrade_issued_template())

	def test_hand_edited_template_is_kept(self):
		self._set_template("<p>Mẫu riêng của kế toán</p>")

		self.assertFalse(upgrade_issued_template())
		self.assertEqual(
			frappe.db.get_value("Email Template", ISSUED_TEMPLATE, "response_html"),
			"<p>Mẫu riêng của kế toán</p>",
		)

	def test_an_already_upgraded_template_is_left_alone(self):
		self._set_template(ISSUED_HTML, subject=ISSUED_SUBJECT)
		self.assertFalse(upgrade_issued_template())
		self.assertEqual(frappe.db.get_value("Email Template", ISSUED_TEMPLATE, "response_html"), ISSUED_HTML)
