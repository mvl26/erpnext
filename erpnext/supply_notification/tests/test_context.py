# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Ngữ cảnh mẫu: hộp cát (NF2), định dạng giá trị, biến dựng sẵn, Quill."""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.supply_notification import content, context
from erpnext.supply_notification.tests import fixtures


class TestSandbox(FrappeTestCase):
	def test_template_cannot_reach_frappe(self):
		point = fixtures.build_point(notify_owner=1, subject_template="{{ frappe.session.user }}")
		order = fixtures.make_sales_order(submit=False)

		built = content.build(point, order)

		self.assertNotIn("Administrator", built.subject)

	def test_template_cannot_write_to_the_document(self):
		"""AC-10: mẫu gọi db_set không thực thi và chứng từ không đổi."""
		point = fixtures.build_point(
			notify_owner=1,
			subject_template="{{ doc.db_set('status', 'Closed') }}",
		)
		order = fixtures.make_sales_order()

		content.build(point, order)

		self.assertNotEqual(frappe.db.get_value("Sales Order", order.name, "status"), "Closed")

	def test_saving_a_template_that_calls_a_method_is_refused(self):
		"""Hộp cát chặn lúc chạy; kiểm V2 chặn ngay lúc lưu cho người cấu hình biết."""
		with self.assertRaises(frappe.ValidationError) as caught:
			fixtures.make_point(notify_owner=1, subject_template="{{ doc.db_set('status', 'X') }}")

		self.assertIn("không gọi được hàm", str(caught.exception))

	def test_context_document_is_a_plain_dict(self):
		point = fixtures.make_point(notify_owner=1)
		order = fixtures.make_sales_order(submit=False)

		ctx = context.build(point, order)

		self.assertIsInstance(ctx["doc"], dict)
		self.assertFalse(callable(ctx["doc"].get("db_set")))
		self.assertFalse(callable(ctx["doc"].get("submit")))

	def test_mutating_the_context_is_refused(self):
		point = fixtures.build_point(notify_owner=1, subject_template="{{ doc.update({'x': 1}) }}")
		order = fixtures.make_sales_order(submit=False)

		self.assertEqual(content.build(point, order).subject, "[Thử]")


class TestBuiltinVariables(FrappeTestCase):
	def test_party_amount_and_date_come_from_the_configured_fields(self):
		point = fixtures.make_point(
			notify_owner=1,
			party_field="customer_name",
			amount_field="grand_total",
			main_date_field="transaction_date",
		)
		order = fixtures.make_sales_order(submit=False, qty=2, rate=1500000)

		ctx = context.build(point, order)

		self.assertEqual(ctx["ten_doi_tac"], fixtures.CUSTOMER)
		self.assertIn("3.000.000", ctx["so_tien"])
		self.assertRegex(ctx["ngay"], r"^\d{2}-\d{2}-\d{4}$")

	def test_legacy_aliases_still_resolve(self):
		point = fixtures.make_point(notify_owner=1, party_field="customer_name")
		order = fixtures.make_sales_order(submit=False)

		ctx = context.build(point, order)

		self.assertEqual(ctx["party_name"], ctx["ten_doi_tac"])
		self.assertEqual(ctx["amount"], ctx["so_tien"])

	def test_owner_name_is_a_person_not_an_email(self):
		point = fixtures.make_point(notify_owner=1)
		order = fixtures.make_sales_order(submit=False)
		order.owner = "Administrator"

		self.assertEqual(
			context.build(point, order)["ten_nguoi_tao"],
			frappe.db.get_value("User", "Administrator", "full_name"),
		)

	def test_days_left_comes_from_the_milestone(self):
		point = fixtures.make_point(reference_doctype="Purchase Invoice", notify_owner=1)
		invoice = fixtures.make_purchase_invoice(submit=False)

		self.assertEqual(context.build(point, invoice, milestone="d3")["so_ngay_con_lai"], 3)
		self.assertEqual(context.build(point, invoice, milestone="q1")["so_ngay_con_lai"], -1)

	def test_due_date_falls_back_to_the_source_document(self):
		point = fixtures.make_point(reference_doctype="Payment Request", notify_owner=1)
		invoice = fixtures.make_purchase_invoice(due_in_days=10)

		request = frappe.new_doc("Payment Request")
		request.reference_doctype = "Purchase Invoice"
		request.reference_name = invoice.name

		self.assertTrue(context.build(point, request)["han_thanh_toan"])

	def test_party_name_is_found_even_without_configuration(self):
		point = fixtures.make_point(reference_doctype="Purchase Order", notify_owner=1, party_field=None)
		order = fixtures.make_purchase_order(submit=False)

		self.assertEqual(context.build(point, order)["ten_doi_tac"], fixtures.SUPPLIER)


class TestFormatting(FrappeTestCase):
	def test_truong_formats_by_fieldtype(self):
		point = fixtures.make_point(notify_owner=1, subject_template="{{ truong('grand_total') }}")
		order = fixtures.make_sales_order(submit=False, qty=1, rate=1234567)

		self.assertIn("1.234.567", content.build(point, order).subject)

	def test_html_in_master_data_is_stripped(self):
		point = fixtures.make_point(notify_owner=1, party_field="customer_name")
		order = fixtures.make_sales_order(submit=False)
		order.customer_name = "<script>alert(1)</script>Khach"

		self.assertEqual(context.build(point, order)["ten_doi_tac"], "alert(1)Khach")

	def test_body_escapes_values_but_keeps_template_html(self):
		point = fixtures.make_point(
			notify_owner=1,
			body_template="<p>{{ doc.customer_name }}</p>",
		)
		order = fixtures.make_sales_order(submit=False)
		order.customer_name = "<b>Khach</b>"

		body = content.build(point, order).body

		self.assertIn("<p>", body)
		self.assertNotIn("<b>Khach</b>", body)


class TestQuillCompatibility(FrappeTestCase):
	def test_escaped_operators_inside_jinja_tags_are_restored(self):
		self.assertEqual(
			context.unescape_jinja("{% if so_tien &gt; 0 %}x{% endif %}"),
			"{% if so_tien > 0 %}x{% endif %}",
		)

	def test_html_outside_the_tags_is_left_alone(self):
		self.assertEqual(
			context.unescape_jinja("<p>a &amp; b</p>{{ doc.name }}"),
			"<p>a &amp; b</p>{{ doc.name }}",
		)

	def test_a_quill_saved_condition_renders(self):
		point = fixtures.make_point(
			notify_owner=1,
			amount_field="grand_total",
			body_template="{% if doc.grand_total &gt; 100 %}<p>Đơn lớn</p>{% endif %}",
		)
		order = fixtures.make_sales_order(submit=False, qty=1, rate=1000)

		self.assertIn("Đơn lớn", content.build(point, order).body)


class TestSnippets(FrappeTestCase):
	def test_snippet_is_inserted(self):
		name = fixtures.make_snippet(content="<p>Hotline 0900</p>")
		point = fixtures.make_point(notify_owner=1, body_template=f'{{{{ mau("{name}") }}}}')
		order = fixtures.make_sales_order(submit=False)

		self.assertIn("Hotline 0900", content.build(point, order).body)

	def test_internal_snippet_is_dropped_from_external_content(self):
		name = fixtures.make_snippet(content="<p>Chỉ nội bộ</p>", scope="Nội bộ")
		point = fixtures.make_point(notify_owner=1)
		order = fixtures.make_sales_order(submit=False)

		ctx = context.build(point, order, scope=context.SCOPE_EXTERNAL)

		self.assertEqual(str(ctx["mau"](name)), "")


class TestValidationHelpers(FrappeTestCase):
	def test_variables_used_lists_template_names(self):
		self.assertEqual(context.variables_used("{{ ten_doi_tac }} {{ doc.name }}"), {"ten_doi_tac", "doc"})

	def test_fields_used_sees_both_forms(self):
		self.assertEqual(
			context.fields_used("{{ doc.supplier_name }} {{ truong('grand_total') }}"),
			{"supplier_name", "grand_total"},
		)

	def test_broken_syntax_is_reported_in_vietnamese(self):
		with self.assertRaises(frappe.ValidationError) as caught:
			context.validate_syntax("{{ doc.name ", "Tiêu đề")

		self.assertIn("lỗi cú pháp", str(caught.exception))
