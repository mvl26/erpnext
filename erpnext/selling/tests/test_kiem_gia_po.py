# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Cảnh báo PO lập từ SO có giá cao hơn giá mua đã dùng ở SO (spec 6.1.3 bước 5; tình huống G22)."""

import frappe
from frappe.utils import add_days

from erpnext.selling.doctype.sales_order.sales_order import make_purchase_order
from erpnext.selling.tests.test_kiem_gia_chung_tu import KiemChungTuCase


class TestKiemGiaPO(KiemChungTuCase):
	def so_da_submit(self, item, rate=101000, **row):
		so = self.so([self.row(item, rate, **row)], ly_do_lech_gia="Thử")
		so.submit()
		return so

	def po(self, so, rate, uom="_KG Cái", conversion_factor=1, taxes=(), link=True):
		d = so.items[0]
		row = {
			"item_code": d.item_code,
			"qty": 1,
			"uom": uom,
			"conversion_factor": conversion_factor,
			"rate": rate,
			"warehouse": self.warehouse,
			"schedule_date": add_days(self.d, 7),
		}
		if link:
			row.update(sales_order=so.name, sales_order_item=d.name)
		frappe.clear_messages()
		return frappe.get_doc(
			{
				"doctype": "Purchase Order",
				"supplier": self.ncc,
				"company": self.company,
				"transaction_date": self.d,
				"schedule_date": add_days(self.d, 7),
				"currency": self.currency,
				"items": [row],
				"taxes": list(taxes),
			}
		).insert(ignore_permissions=True)

	def canh_bao(self):
		return " ".join(
			str(m.get("message")) for m in frappe.get_message_log() if m.get("title") == "Kiểm giá mua"
		)

	def test_g22_higher_purchase_price_warns_but_saves(self):
		item = self.item(100000)
		po = self.po(self.so_da_submit(item), 103000)

		self.assertTrue(po.name)
		self.assertIn(item, self.canh_bao())
		self.assertIn("3000", self.canh_bao())

	def test_g22_through_the_standard_po_from_so_button(self):
		item = self.item(100000)
		so = self.so_da_submit(item)
		po = make_purchase_order(so.name, selected_items=[{"item_code": item, "supplier": self.ncc}])
		po.supplier = self.ncc
		po.schedule_date = add_days(self.d, 7)
		po.items[0].rate = 103000
		frappe.clear_messages()
		po.insert(ignore_permissions=True)

		self.assertEqual(po.items[0].sales_order_item, so.items[0].name)
		self.assertIn(item, self.canh_bao())

	def test_same_or_lower_price_does_not_warn(self):
		so = self.so_da_submit(self.item(100000))
		self.po(so, 100000)
		self.assertFalse(self.canh_bao())
		self.po(so, 99000)
		self.assertFalse(self.canh_bao())

	def test_buying_by_the_box_is_compared_per_unit(self):
		item = self.item(100000, hop=10)
		so = self.so_da_submit(item)

		self.po(so, 1000000, uom="_KG Hộp", conversion_factor=10)
		self.assertFalse(self.canh_bao())
		self.po(so, 1010000, uom="_KG Hộp", conversion_factor=10)
		self.assertIn("10000", self.canh_bao())

	def test_tax_inclusive_po_is_compared_before_tax(self):
		account = frappe.db.get_value(
			"Account", {"company": self.company, "account_type": "Tax", "is_group": 0}, "name"
		)
		if not account:
			self.skipTest("Công ty test chưa có tài khoản thuế")
		tax = {
			"category": "Total",
			"add_deduct_tax": "Add",
			"charge_type": "On Net Total",
			"account_head": account,
			"description": "VAT 10%",
			"rate": 10,
			"included_in_print_rate": 1,
		}

		self.po(self.so_da_submit(self.item(100000)), 110000, taxes=[tax])

		self.assertFalse(self.canh_bao())

	def test_po_not_made_from_a_sales_order_is_not_checked(self):
		self.po(self.so_da_submit(self.item(100000)), 200000, link=False)

		self.assertFalse(self.canh_bao())

	def test_sales_order_row_without_a_buying_price_is_skipped(self):
		self.po(self.so_da_submit(self.item(None), 5000), 999999)

		self.assertFalse(self.canh_bao())

	def test_nothing_when_switched_off(self):
		so = self.so_da_submit(self.item(100000))
		self.bat(0)

		self.po(so, 200000)

		self.assertFalse(self.canh_bao())
