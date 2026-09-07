# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.supply_notification import content
from erpnext.supply_notification.tests import fixtures


class TestContentContext(FrappeTestCase):
	def test_sales_order_context_uses_vietnamese_formats(self):
		point = frappe.get_doc("Supply Notification Point", "NTF-01")
		order = fixtures.make_sales_order(submit=False, qty=2, rate=1500000)

		context = content.build_context(point, order)

		self.assertEqual(context["party_name"], fixtures.CUSTOMER)
		self.assertIn("3.000.000", context["amount"])
		self.assertRegex(context["date"], r"^\d{2}-\d{2}-\d{4}$")

	def test_owner_name_is_a_person_not_an_email(self):
		point = frappe.get_doc("Supply Notification Point", "NTF-01")
		order = fixtures.make_sales_order(submit=False)
		order.owner = "Administrator"

		self.assertEqual(
			content.build_context(point, order)["owner_name"],
			frappe.db.get_value("User", "Administrator", "full_name"),
		)

	def test_reminder_context_carries_days_left(self):
		point = frappe.get_doc("Supply Notification Point", "NTF-06")
		invoice = fixtures.make_purchase_invoice(submit=False)

		self.assertEqual(content.build_context(point, invoice, milestone="d3")["days_left"], 3)

	def test_payment_request_due_falls_back_to_source_document(self):
		point = frappe.get_doc("Supply Notification Point", "NTF-11")
		invoice = fixtures.make_purchase_invoice(due_in_days=10)

		request = frappe.new_doc("Payment Request")
		request.reference_doctype = "Purchase Invoice"
		request.reference_name = invoice.name

		self.assertEqual(content.build_context(point, request)["due"], content.formatdate(invoice.due_date))

	def test_due_is_empty_when_there_is_nothing_to_look_up(self):
		point = frappe.get_doc("Supply Notification Point", "NTF-11")

		self.assertEqual(content.build_context(point, frappe.new_doc("Payment Request"))["due"], "")


class TestContentRendering(FrappeTestCase):
	def test_subject_carries_prefix_and_document_number(self):
		point = frappe.get_doc("Supply Notification Point", "NTF-01")
		order = fixtures.make_sales_order(submit=False)

		subject = content.subject(point, content.build_context(point, order))

		self.assertIn(content.PREFIX, subject)
		self.assertIn(fixtures.CUSTOMER, subject)

	def test_internal_body_lists_items_and_links(self):
		point = frappe.get_doc("Supply Notification Point", "NTF-01")
		order = fixtures.make_sales_order(submit=False)
		context = content.build_context(point, order)

		body = content.internal_body(point, order, context)

		self.assertIn(fixtures.ITEM_CODE, body)
		self.assertIn("/app/sales-order/", body.lower())
		self.assertIn(content.STOCK_REPORT_PATH, body)

	def test_money_document_shows_facts_instead_of_items(self):
		point = frappe.get_doc("Supply Notification Point", "NTF-06")
		invoice = fixtures.make_purchase_invoice(submit=False)
		context = content.build_context(point, invoice, milestone="d7")

		body = content.internal_body(point, invoice, context)

		self.assertIn("Số còn nợ", body)
		self.assertIn("7 ngày", body)

	def test_external_body_has_no_internal_link_and_keeps_closing(self):
		point = frappe.get_doc("Supply Notification Point", "NTF-07")
		point.external_closing = "Hotline Miyano: 0900 000 000"
		order = fixtures.make_sales_order(submit=False)
		context = content.build_context(point, order)

		body = content.external_body(point, order, context)

		self.assertNotIn("/app/", body)
		self.assertIn("Hotline Miyano", body)

	def test_broken_template_falls_back_to_the_seeded_wording(self):
		point = frappe.get_doc("Supply Notification Point", "NTF-01")
		point.subject_template = "{{ doc.khong_co_ham() }}"
		order = fixtures.make_sales_order(submit=False)

		subject = content.subject(point, content.build_context(point, order))

		self.assertIn("đề nghị kiểm tra tồn kho", subject)

	def test_sandbox_blocks_reaching_into_frappe(self):
		point = frappe.get_doc("Supply Notification Point", "NTF-01")
		point.subject_template = "{{ frappe.db.get_value('User', 'Administrator', 'api_secret') }}"
		order = fixtures.make_sales_order(submit=False)

		subject = content.subject(point, content.build_context(point, order))

		self.assertIn("Đơn bán hàng", subject)

	def test_html_in_master_data_is_stripped_from_values(self):
		point = frappe.get_doc("Supply Notification Point", "NTF-01")
		order = fixtures.make_sales_order(submit=False)
		order.customer_name = "<script>alert(1)</script>Khach"

		self.assertEqual(content.build_context(point, order)["party_name"], "alert(1)Khach")
