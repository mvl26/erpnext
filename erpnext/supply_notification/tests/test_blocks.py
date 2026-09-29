# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Bảy khối nội dung dựng sẵn: cột, trần dòng, địa chỉ, chữ ký, phạm vi."""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.supply_notification import blocks, content, context
from erpnext.supply_notification.tests import fixtures


class TestItemTable(FrappeTestCase):
	def test_default_columns_when_nothing_is_configured(self):
		point = fixtures.make_point(notify_owner=1, body_template="{{ bang_mat_hang() }}")
		order = fixtures.make_sales_order(submit=False)

		body = content.build(point, order).body

		for label in ("Mã vật tư", "Tên hàng", "Số lượng", "ĐVT"):
			self.assertIn(label, body)
		self.assertIn(fixtures.ITEM_CODE, body)

	def test_chosen_columns_keep_their_order_and_labels(self):
		point = fixtures.make_point(
			reference_doctype="Purchase Order",
			notify_owner=1,
			body_template="{{ bang_mat_hang() }}",
			item_columns=[("stt", "STT"), ("item_name", "Tên hàng"), ("schedule_date", "Ngày cần hàng")],
		)
		order = fixtures.make_purchase_order(submit=False)

		body = content.build(point, order).body

		self.assertLess(body.index("STT"), body.index("Tên hàng"))
		self.assertLess(body.index("Tên hàng"), body.index("Ngày cần hàng"))
		self.assertNotIn("Mã vật tư", body)
		self.assertIn("<td>1</td>", body)

	def test_quantities_drop_the_trailing_zero(self):
		point = fixtures.make_point(notify_owner=1, body_template="{{ bang_mat_hang() }}")
		order = fixtures.make_sales_order(submit=False, qty=5)

		self.assertIn("<td>5</td>", content.build(point, order).body)

	def test_row_limit_comes_from_settings(self):
		fixtures.set_settings(max_item_rows=1)
		point = fixtures.make_point(notify_owner=1, body_template="{{ bang_mat_hang() }}")
		order = fixtures.make_sales_order(submit=False)
		order.append("items", dict(order.items[0].as_dict(), name=None, item_code=fixtures.ensure_item()))

		body = content.build(point, order).body

		self.assertIn("dòng nữa", body)

	def test_document_without_the_table_renders_nothing(self):
		point = fixtures.make_point(
			reference_doctype="Payment Entry", notify_owner=1, body_template="{{ bang_mat_hang() }}"
		)
		entry = frappe.new_doc("Payment Entry")

		self.assertEqual(content.build(point, entry).body, "")


class TestFactTable(FrappeTestCase):
	def test_rows_use_builtin_variables_and_labels(self):
		point = fixtures.make_point(
			reference_doctype="Purchase Invoice",
			notify_owner=1,
			amount_field="outstanding_amount",
			main_date_field="due_date",
			body_template="{{ khoi_so_lieu() }}",
			fact_rows=[("so_tien", "Số còn nợ", 0), ("so_ngay_con_lai", "Còn lại", 0)],
		)
		invoice = fixtures.make_purchase_invoice(submit=False)

		body = content.build(point, invoice, milestone="d7").body

		self.assertIn("Số còn nợ", body)
		self.assertIn("7 ngày", body)

	def test_overdue_milestone_reads_as_overdue(self):
		point = fixtures.make_point(
			reference_doctype="Purchase Invoice",
			notify_owner=1,
			body_template="{{ khoi_so_lieu() }}",
			fact_rows=[("so_ngay_con_lai", "Còn lại", 0)],
		)
		invoice = fixtures.make_purchase_invoice(submit=False)

		self.assertIn("quá hạn 2 ngày", content.build(point, invoice, milestone="q2").body)

	def test_empty_rows_are_dropped(self):
		point = fixtures.make_point(
			notify_owner=1,
			body_template="{{ khoi_so_lieu() }}",
			fact_rows=[("han_thanh_toan", "Hạn thanh toán", 0)],
		)
		order = fixtures.make_sales_order(submit=False)

		self.assertEqual(content.build(point, order).body, "")

	def test_fallback_row_only_shows_when_the_row_above_is_empty(self):
		point = fixtures.make_point(
			notify_owner=1,
			main_date_field="transaction_date",
			body_template="{{ khoi_so_lieu() }}",
			fact_rows=[("han_thanh_toan", "Hạn thanh toán", 0), ("ngay", "Ngày", 1)],
		)
		order = fixtures.make_sales_order(submit=False)

		body = content.build(point, order).body
		self.assertIn("Ngày", body)
		self.assertNotIn("Hạn thanh toán", body)


class TestAddressAndSignature(FrappeTestCase):
	def test_address_block_reads_the_linked_address(self):
		address = fixtures.ensure_address(contact_name="Chị Lan")
		point = fixtures.make_point(
			reference_doctype="Purchase Order",
			notify_owner=1,
			address_field="shipping_address",
			body_template="{{ dia_chi_giao_hang() }}",
		)
		order = fixtures.make_purchase_order(submit=False, shipping_address=address)

		body = content.build(point, order).body

		self.assertIn("Số 1 đường Thử", body)
		self.assertIn("Người nhận:", body)
		self.assertIn("0900 000 000", body)

	def test_address_block_is_silent_when_the_document_has_no_address(self):
		point = fixtures.make_point(
			reference_doctype="Purchase Order",
			notify_owner=1,
			address_field="shipping_address",
			body_template="{{ dia_chi_giao_hang() }}",
		)
		order = fixtures.make_purchase_order(submit=False)

		self.assertEqual(content.build(point, order).body, "")

	def test_signature_shows_the_document_owner(self):
		point = fixtures.make_point(notify_owner=1, body_template="{{ chu_ky() }}")
		order = fixtures.make_sales_order(submit=False)

		body = content.build(point, order).body

		self.assertIn(frappe.db.get_value("User", order.owner, "full_name"), body)


class TestScope(FrappeTestCase):
	def test_internal_blocks_are_missing_from_external_content(self):
		point = fixtures.make_point(notify_owner=1)
		order = fixtures.make_sales_order(submit=False)

		ctx = context.build(point, order, scope=context.SCOPE_EXTERNAL)

		for name in context.INTERNAL_ONLY_BLOCKS:
			self.assertNotIn(name, ctx)

	def test_open_document_link_points_at_the_form(self):
		point = fixtures.make_point(notify_owner=1, body_template="{{ nut_mo_chung_tu() }}")
		order = fixtures.make_sales_order(submit=False)

		self.assertIn("/app/sales-order/", content.build(point, order).body.lower())

	def test_report_link_and_feedback_block_render(self):
		point = fixtures.make_point(
			notify_owner=1,
			body_template='{{ link_bao_cao("Stock Balance") }}{{ khoi_phan_hoi("Xác nhận giúp") }}',
		)
		order = fixtures.make_sales_order(submit=False)

		body = content.build(point, order).body

		self.assertIn("Stock%20Balance", body.replace("Stock Balance", "Stock%20Balance"))
		self.assertIn("Xác nhận giúp", body)


class TestBlockHelpers(FrappeTestCase):
	def test_address_text_is_one_line_without_html(self):
		address = fixtures.ensure_address()
		text = blocks.address_text(address)

		self.assertNotIn("<", text)
		self.assertIn("Số 1 đường Thử", text)
