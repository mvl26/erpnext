# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Supplier Quotation -> bảng giá mua (spec mục 6.1.3, 6.1.7; bước 1.6, tình huống G23)."""

import frappe
from frappe.utils import add_days

from erpnext.selling.kiem_gia.bao_gia_ncc import ghi_chu
from erpnext.selling.kiem_gia.gia_goc import KHOP, tim_gia_goc
from erpnext.selling.tests.test_kiem_gia_chung_tu import KiemChungTuCase


class TestBaoGiaNCC(KiemChungTuCase):
	def setUp(self):
		super().setUp()
		self.ncc = self.supplier(self.mua)

	def supplier(self, price_list=None):
		doc = frappe.new_doc("Supplier")
		doc.supplier_name = f"_KG NCC {frappe.generate_hash(length=6)}"
		doc.supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
		doc.default_price_list = price_list
		return doc.insert(ignore_permissions=True).name

	def sq(self, rows, supplier=None, ngay=None, buying_price_list=None, taxes=(), submit=True):
		doc = frappe.get_doc(
			{
				"doctype": "Supplier Quotation",
				"supplier": supplier or self.ncc,
				"company": self.company,
				"transaction_date": ngay or self.d,
				"currency": self.currency,
				"buying_price_list": buying_price_list or self.mua,
				"items": [{"qty": 10, "uom": "_KG Cái", "warehouse": self.warehouse, **row} for row in rows],
				"taxes": list(taxes),
			}
		).insert(ignore_permissions=True)
		if submit:
			doc.submit()
		return doc

	def gia_ncc(self, item, ngay=None):
		return frappe.get_all(
			"Item Price",
			filters={"item_code": item, "buying": 1, "supplier": self.ncc, "valid_from": ngay or self.d},
			fields=["name", "price_list", "price_list_rate", "uom", "note"],
		)

	def test_g23_submit_adds_a_new_price_row_and_keeps_the_old_one(self):
		item = self.item(100000)
		sq = self.sq([{"item_code": item, "rate": 107000}])

		rows = self.gia_ncc(item)
		self.assertEqual(len(rows), 1)
		self.assertEqual((rows[0].price_list, rows[0].price_list_rate), (self.mua, 107000))
		self.assertEqual(rows[0].note, ghi_chu(sq.name))
		self.assertEqual(frappe.db.count("Item Price", {"item_code": item, "buying": 1}), 2)

	def test_the_check_uses_the_quoted_price_from_its_date(self):
		item = self.item(100000)
		self.sq([{"item_code": item, "rate": 107000}])

		self.assertEqual(tim_gia_goc(item, self.d).gia_goc, 107000)
		self.assertEqual(tim_gia_goc(item, add_days(self.d, -1)).gia_goc, 100000)
		self.assertEqual(self.so([self.row(item, 108070)]).items[0].trang_thai_gia, KHOP)

	def test_without_a_supplier_price_list_the_quotation_list_is_used(self):
		ncc = self.supplier()
		chung = self.price_list("Mua chung", buying=1)
		item = self.item(None)

		self.sq([{"item_code": item, "rate": 5000}], supplier=ncc, buying_price_list=chung)

		self.assertEqual(
			frappe.db.get_value("Item Price", {"item_code": item, "supplier": ncc}, "price_list"), chung
		)

	def test_g11_a_box_price_is_stored_per_stock_unit(self):
		item = self.item(None, hop=10)

		self.sq([{"item_code": item, "rate": 1000000, "uom": "_KG Hộp", "conversion_factor": 10}])

		row = self.gia_ncc(item)[0]
		self.assertEqual((row.uom, row.price_list_rate), ("_KG Cái", 100000))

	def test_same_day_same_price_is_not_duplicated(self):
		item = self.item(None)
		self.sq([{"item_code": item, "rate": 5000}])
		self.sq([{"item_code": item, "rate": 5000}])

		self.assertEqual(len(self.gia_ncc(item)), 1)

	def test_same_day_new_price_replaces_an_unused_row(self):
		item = self.item(None)
		self.sq([{"item_code": item, "rate": 5000}])
		sq2 = self.sq([{"item_code": item, "rate": 5200}])

		rows = self.gia_ncc(item)
		self.assertEqual(len(rows), 1)
		self.assertEqual((rows[0].price_list_rate, rows[0].note), (5200, ghi_chu(sq2.name)))

	def test_same_day_price_already_used_by_a_sales_order_is_kept(self):
		item = self.item(None)
		self.sq([{"item_code": item, "rate": 5000}])
		self.so([self.row(item, 5050)]).submit()

		frappe.clear_messages()
		self.sq([{"item_code": item, "rate": 5200}])

		self.assertEqual(self.gia_ncc(item)[0].price_list_rate, 5000)
		self.assertIn("Giữ nguyên", " ".join(str(m.get("message")) for m in frappe.get_message_log()))

	def test_two_different_prices_for_one_item_are_skipped(self):
		item = self.item(None)

		self.sq([{"item_code": item, "rate": 5000}, {"item_code": item, "rate": 5100}])

		self.assertFalse(self.gia_ncc(item))

	def test_cancel_removes_unused_rows(self):
		item = self.item(None)
		sq = self.sq([{"item_code": item, "rate": 5000}])

		sq.cancel()

		self.assertFalse(self.gia_ncc(item))

	def test_cancel_keeps_rows_used_by_a_sales_order(self):
		item = self.item(None)
		sq = self.sq([{"item_code": item, "rate": 5000}])
		self.so([self.row(item, 5050)]).submit()

		sq.cancel()

		self.assertEqual(len(self.gia_ncc(item)), 1)

	def test_draft_quotation_writes_nothing(self):
		item = self.item(None)

		self.sq([{"item_code": item, "rate": 5000}], submit=False)

		self.assertFalse(self.gia_ncc(item))

	def test_tax_inclusive_quotation_stores_the_price_before_tax(self):
		account = frappe.db.get_value(
			"Account", {"company": self.company, "account_type": "Tax", "is_group": 0}, "name"
		)
		if not account:
			self.skipTest("Công ty test chưa có tài khoản thuế")
		item = self.item(None)
		tax = {
			"category": "Total",
			"add_deduct_tax": "Add",
			"charge_type": "On Net Total",
			"account_head": account,
			"description": "VAT 10%",
			"rate": 10,
			"included_in_print_rate": 1,
		}

		self.sq([{"item_code": item, "rate": 110000}], taxes=[tax])

		self.assertEqual(self.gia_ncc(item)[0].price_list_rate, 100000)
