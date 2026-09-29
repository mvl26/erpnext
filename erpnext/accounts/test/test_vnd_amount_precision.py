# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Thành tiền làm tròn đồng nguyên, đơn giá giữ số lẻ — để ERP khớp HĐĐT.

HĐĐT làm tròn thành tiền và tiền thuế **từng dòng** rồi mới cộng. Nếu ERP giữ
số lẻ ở dòng và chỉ làm tròn Tổng cuối (Rounded Total) thì hai bên lệch nhau
1 đồng — ví dụ ở `TestInvoiceMatchesEInvoice`.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

COMPANY = "Miyano"
VAT_ACCOUNT = "33311 - Thuế GTGT đầu ra - M"

# (DocType, trường) phải làm tròn đồng nguyên.
WHOLE_DONG_FIELDS = (
	("Sales Invoice Item", "amount"),
	("Sales Invoice Item", "net_amount"),
	("Sales Invoice Item", "base_net_amount"),
	("Sales Invoice", "net_total"),
	("Sales Invoice", "total_taxes_and_charges"),
	("Sales Invoice", "grand_total"),
	("Sales Invoice", "outstanding_amount"),
	("Sales Taxes and Charges", "tax_amount"),
	("Purchase Order Item", "amount"),
	("Purchase Invoice", "grand_total"),
	("Purchase Taxes and Charges", "tax_amount"),
	("Payment Entry", "paid_amount"),
	("GL Entry", "debit"),
	("GL Entry", "credit"),
	("Stock Ledger Entry", "stock_value_difference"),
	("Fast EInvoice Line", "amount"),
	("Fast EInvoice Line", "tax_amount"),
)

# Đơn giá (tính trên một đơn vị) — không được làm tròn về đồng nguyên.
UNIT_PRICE_FIELDS = (
	("Sales Invoice Item", "rate"),
	("Sales Invoice Item", "price_list_rate"),
	("Sales Invoice Item", "net_rate"),
	("Sales Invoice Item", "discount_amount"),
	("Purchase Order Item", "rate"),
	("Item Price", "price_list_rate"),
	("Stock Ledger Entry", "valuation_rate"),
	("Fast EInvoice Line", "price"),
)


class TestFieldPrecision(FrappeTestCase):
	def test_amount_fields_round_to_whole_dong(self):
		for doctype, fieldname in WHOLE_DONG_FIELDS:
			df = frappe.get_meta(doctype).get_field(fieldname)
			self.assertEqual(str(df.precision), "0", f"{doctype}.{fieldname}")

	def test_unit_prices_keep_their_decimals(self):
		for doctype, fieldname in UNIT_PRICE_FIELDS:
			df = frappe.get_meta(doctype).get_field(fieldname)
			self.assertNotEqual(str(df.precision), "0", f"{doctype}.{fieldname}")


class TestInvoiceMatchesEInvoice(FrappeTestCase):
	def _invoice(self, *lines, tax_rate=8):
		si = frappe.new_doc("Sales Invoice")
		si.update({"company": COMPANY, "currency": "VND", "conversion_rate": 1, "plc_conversion_rate": 1})
		for idx, (item, qty, rate) in enumerate(lines, start=1):
			si.append(
				"items",
				{
					"idx": idx,
					"item_code": item,
					"item_name": item,
					"qty": qty,
					"rate": rate,
					"price_list_rate": rate,
				},
			)
		si.append(
			"taxes",
			{
				"charge_type": "On Net Total",
				"account_head": VAT_ACCOUNT,
				"description": "VAT",
				"rate": tax_rate,
			},
		)
		si.calculate_taxes_and_totals()
		return si

	def test_lines_tax_and_total_are_whole_dong(self):
		"""Hai dòng đơn giá lẻ, VAT 8% — đúng ví dụ từng lệch 1 đồng với HĐĐT."""
		si = self._invoice(("A", 3, 33333.33), ("B", 7, 12345.67))

		# 99.999,99 → 100.000 ; 86.419,69 → 86.420
		self.assertEqual([row.amount for row in si.items], [100000, 86420])
		self.assertEqual([row.rate for row in si.items], [33333.33, 12345.67])
		self.assertEqual(si.net_total, 186420)
		# Thuế theo dòng: 8.000 + 6.913,6 → 6.914
		self.assertEqual(si.taxes[0].tax_amount, 14914)
		self.assertEqual(si.grand_total, 201334)
		self.assertEqual(si.rounding_adjustment, 0)

	def test_row_wise_tax_is_what_the_einvoice_prints(self):
		"""Tiền thuế hóa đơn = tổng tiền thuế đã làm tròn của từng dòng."""
		si = self._invoice(("A", 1, 10.5), ("B", 1, 10.5), ("C", 1, 10.5), tax_rate=10)

		# Mỗi dòng 10,5 → 11 (nửa lên); thuế mỗi dòng 1,1 → 1 ; tổng thuế 3 chứ không phải 3,3.
		self.assertEqual([row.amount for row in si.items], [11, 11, 11])
		self.assertEqual(si.taxes[0].tax_amount, 3)
		self.assertEqual(si.grand_total, 36)
