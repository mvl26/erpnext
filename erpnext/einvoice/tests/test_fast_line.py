# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Child table `Fast EInvoice Line` — mục C3 của đặc tả.

Thứ tự trường ở đây **chính là thứ tự cột** `structure.detail` trong payload gửi
Fast (Phần I). Đảo thứ tự là đảo dữ liệu sang cột khác mà Fast vẫn nhận, nên có
test khóa thứ tự lại.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.einvoice.constants import PROCESS_TYPE_CODES, TAX_RATE_CODES

LINE = "Fast EInvoice Line"

# Đúng thứ tự cột `structure.detail` — Phần I của đặc tả.
DETAIL_FIELDS = (
	"process_type",
	"item_code",
	"item_name",
	"uom",
	"is_promotion",
	"qty",
	"price",
	"amount",
	"discount_rate",
	"discount_amount",
	"tax_rate",
	"tax_amount",
)


class TestFastEInvoiceLine(FrappeTestCase):
	def test_item_code_links_to_the_item_catalogue(self):
		"""Mã hàng phải trỏ vào danh mục, không phải ô gõ tay.

		Gõ tay thì mã trên hóa đơn lệch mã trong kho, và không có đường nào tự
		điền tên hàng / đơn vị tính từ hồ sơ Item.
		"""
		field = frappe.get_meta(LINE).get_field("item_code")
		self.assertEqual(field.fieldtype, "Link")
		self.assertEqual(field.options, "Item")

	def test_item_code_is_not_mandatory_at_schema_level(self):
		"""Dòng ghi chú và dòng chiết khấu không trỏ tới hàng nào trong danh mục.

		Bắt buộc chuyển xuống quy tắc 8 của `validation.py`, chỉ áp cho dòng hàng
		hóa (tính chất 1) và hàng đặc trưng (tính chất 5).
		"""
		self.assertFalse(frappe.get_meta(LINE).get_field("item_code").reqd)

	def test_line_is_a_child_table(self):
		self.assertTrue(frappe.get_meta(LINE).istable)

	def test_detail_columns_appear_in_the_order_fast_expects(self):
		meta = frappe.get_meta(LINE)
		ordered = [f.fieldname for f in meta.fields if f.fieldname in DETAIL_FIELDS]
		self.assertEqual(ordered, list(DETAIL_FIELDS))

	def test_note_and_line_number_exist_outside_the_detail_columns(self):
		"""Hai thẻ tùy chọn: có trường để dùng, nhưng không nằm trong 12 cột chuẩn."""
		meta = frappe.get_meta(LINE)
		self.assertEqual(meta.get_field("note").fieldtype, "Data")
		self.assertEqual(meta.get_field("line_number").fieldtype, "Int")

	def test_process_type_defaults_to_goods_and_never_empty(self):
		"""Đặc tả C3 #1: ProcessType không được rỗng (lỗi 836)."""
		field = frappe.get_meta(LINE).get_field("process_type")
		self.assertEqual(field.default, "1")
		self.assertEqual(field.reqd, 1)
		self.assertEqual(field.options.split("\n"), list(PROCESS_TYPE_CODES))

	def test_tax_rate_offers_exactly_the_fast_code_set(self):
		field = frappe.get_meta(LINE).get_field("tax_rate")
		self.assertEqual(field.options.split("\n"), list(TAX_RATE_CODES))

	def test_money_fields_are_currency_and_quantity_is_float(self):
		meta = frappe.get_meta(LINE)
		for fieldname in ("price", "amount", "discount_amount", "tax_amount"):
			self.assertEqual(meta.get_field(fieldname).fieldtype, "Currency", fieldname)
		self.assertEqual(meta.get_field("qty").fieldtype, "Float")
		self.assertEqual(meta.get_field("discount_rate").fieldtype, "Float")

	def test_required_line_fields_match_the_spec(self):
		"""``item_code`` cố ý không có trong danh sách này — xem quy tắc 8.

		Nó chỉ bắt buộc với dòng hàng hóa và hàng đặc trưng, nên bắt buộc phải gác
		theo tính chất dòng ở `validation.py`, không phải bằng ``reqd`` của schema.
		"""
		meta = frappe.get_meta(LINE)
		for fieldname in ("process_type", "item_name", "uom", "qty", "tax_rate"):
			self.assertEqual(meta.get_field(fieldname).reqd, 1, fieldname)

	def test_adjustment_lines_may_carry_negative_amounts(self):
		"""Hóa đơn điều chỉnh giảm truyền số âm — không được chặn bằng non_negative."""
		meta = frappe.get_meta(LINE)
		for fieldname in ("qty", "price", "amount", "tax_amount"):
			self.assertFalse(meta.get_field(fieldname).non_negative, fieldname)
