# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Kiểm giá bán trên Quotation và Sales Order (spec mục 6.1.4-6.1.7, tình huống mục 7.1)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, nowdate

from erpnext.selling.kiem_gia.gia_goc import CAO_HON, CHUA_XAC_DINH, KHOP, THAP_HON
from erpnext.selling.kiem_gia.kiem_chung_tu import BO_QUA
from erpnext.stock.tests.test_item_code_rule import use_naming_mode


class KiemChungTuCase(FrappeTestCase):
	def setUp(self):
		self.addCleanup(frappe.clear_document_cache, "Selling Settings", "Selling Settings")
		self.addCleanup(frappe.clear_document_cache, "Stock Settings", "Stock Settings")
		frappe.db.savepoint("kiem_gia_chung_tu")
		self.addCleanup(frappe.db.rollback, save_point="kiem_gia_chung_tu")
		use_naming_mode(self, "Item Code")
		# Như production (P7): chứng từ không tự thêm/ghi đè Item Price.
		frappe.db.set_single_value(
			"Stock Settings",
			{"auto_insert_price_list_rate_if_missing": 0, "update_existing_price_list_rate": 0},
		)
		frappe.clear_document_cache("Stock Settings", "Stock Settings")
		self.d = getdate(nowdate())
		self.sfx = frappe.generate_hash(length=6)
		self.company = frappe.db.get_value("Company", {}, "name")
		self.currency = frappe.get_cached_value("Company", self.company, "default_currency")
		self.warehouse = frappe.db.get_value("Warehouse", {"company": self.company, "is_group": 0}, "name")
		for uom in ("_KG Cái", "_KG Hộp"):
			if not frappe.db.exists("UOM", uom):
				frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert(ignore_permissions=True)
		self.bat(1)
		frappe.db.set_single_value("Selling Settings", "ty_le_lai_mac_dinh", 1)
		self.mua = self.price_list("Mua", buying=1)
		self.ban = self.price_list("Bán", buying=0)
		self.khach = self.customer()

	def bat(self, value):
		frappe.db.set_single_value("Selling Settings", "bat_kiem_gia_ban", value)
		frappe.clear_document_cache("Selling Settings", "Selling Settings")

	def price_list(self, label, buying):
		return (
			frappe.get_doc(
				{
					"doctype": "Price List",
					"price_list_name": f"_KG {label} {self.sfx}",
					"buying": buying,
					"selling": 0 if buying else 1,
					"currency": self.currency,
					"enabled": 1,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def customer(self, **fields):
		return (
			frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": f"_KG Khách {frappe.generate_hash(length=6)}",
					"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
					"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name"),
					**fields,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def item(self, gia_mua=100000, hop=None, customer_items=()):
		doc = frappe.new_doc("Item")
		doc.item_code = f"_KG-{frappe.generate_hash(length=8)}"
		doc.item_name = doc.item_code
		doc.item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
		doc.stock_uom = "_KG Cái"
		doc.is_stock_item = 1
		if hop:
			doc.append("uoms", {"uom": "_KG Hộp", "conversion_factor": hop})
		for row in customer_items:
			doc.append("customer_items", row)
		doc.insert(ignore_permissions=True)
		if gia_mua is not None:
			self.gia_mua(doc.name, gia_mua)
		return doc.name

	def gia_mua(self, item, rate, valid_from=None):
		return (
			frappe.get_doc(
				{
					"doctype": "Item Price",
					"price_list": self.mua,
					"item_code": item,
					"uom": "_KG Cái",
					"price_list_rate": rate,
					"valid_from": valid_from or add_days(self.d, -30),
					"currency": self.currency,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def row(self, item, rate, uom="_KG Cái", **fields):
		return {
			"item_code": item,
			"qty": 1,
			"uom": uom,
			"rate": rate,
			"warehouse": self.warehouse,
			"delivery_date": add_days(self.d, 7),
			**fields,
		}

	def so(self, rows, customer=None, taxes=()):
		return frappe.get_doc(
			{
				"doctype": "Sales Order",
				"company": self.company,
				"customer": customer or self.khach,
				"transaction_date": self.d,
				"delivery_date": add_days(self.d, 7),
				"selling_price_list": self.ban,
				"currency": self.currency,
				"ignore_pricing_rule": 1,
				"items": rows,
				"taxes": list(taxes),
			}
		).insert(ignore_permissions=True)


class TestKiemGiaSalesOrder(KiemChungTuCase):
	def test_g1_matching_price(self):
		item = self.item(100000)
		d = self.so([self.row(item, 101000)]).items[0]

		self.assertEqual(d.trang_thai_gia, KHOP)
		self.assertEqual((d.gia_goc, d.gia_chuan, d.chenh_lech, d.ty_le_lai_ap_dung), (100000, 101000, 0, 1))
		self.assertEqual(frappe.db.get_value("Item Price", d.nguon_gia_goc, "item_code"), item)

	def test_g2_higher_and_lower_prices_are_flagged(self):
		cao, thap = self.item(100000), self.item(100000)
		so = self.so([self.row(cao, 101500), self.row(thap, 100500)])

		self.assertEqual((so.items[0].trang_thai_gia, so.items[0].chenh_lech), (CAO_HON, 500))
		self.assertEqual((so.items[1].trang_thai_gia, so.items[1].chenh_lech), (THAP_HON, -500))

	def test_result_is_stored_in_the_database(self):
		so = self.so([self.row(self.item(100000), 101500)])

		stored = frappe.db.get_value(
			"Sales Order Item", so.items[0].name, ["trang_thai_gia", "chenh_lech"], as_dict=True
		)
		self.assertEqual((stored.trang_thai_gia, stored.chenh_lech), (CAO_HON, 500))

	def test_g3_customer_rate(self):
		khach = self.customer(ty_le_lai_rieng=1, ty_le_lai=2)

		self.assertEqual(self.so([self.row(self.item(100000), 102000)], khach).items[0].trang_thai_gia, KHOP)

	def test_g4_item_customer_rate(self):
		item = self.item(
			100000, customer_items=[{"customer_name": self.khach, "ty_le_lai_rieng": 1, "ty_le_lai": 0.5}]
		)

		d = self.so([self.row(item, 100500)]).items[0]

		self.assertEqual((d.trang_thai_gia, d.ty_le_lai_ap_dung), (KHOP, 0.5))

	def test_g9_customer_switched_off(self):
		khach = self.customer(kiem_gia_ban=0)

		self.assertEqual(self.so([self.row(self.item(100000), 1)], khach).items[0].trang_thai_gia, BO_QUA)

	def test_g10_free_item_is_skipped(self):
		item = self.item(100000)

		d = self.so([self.row(item, 0, is_free_item=1)]).items[0]

		self.assertEqual(d.trang_thai_gia, BO_QUA)

	def test_g16_zero_rate_that_is_not_free_is_flagged(self):
		self.assertEqual(self.so([self.row(self.item(100000), 0)]).items[0].trang_thai_gia, THAP_HON)

	def test_g11_selling_by_the_box(self):
		item = self.item(100000, hop=10)

		d = self.so([self.row(item, 1010000, uom="_KG Hộp", conversion_factor=10)]).items[0]

		self.assertEqual((d.trang_thai_gia, d.gia_goc), (KHOP, 1000000))

	def test_g20_no_buying_price(self):
		d = self.so([self.row(self.item(None), 5000)]).items[0]

		self.assertEqual(d.trang_thai_gia, CHUA_XAC_DINH)
		self.assertTrue(d.ghi_chu_gia)

	def test_g14_saving_again_uses_the_new_buying_price(self):
		item = self.item(100000)
		so = self.so([self.row(item, 101000)])
		self.gia_mua(item, 110000, valid_from=self.d)

		so.save(ignore_permissions=True)

		self.assertEqual(so.items[0].trang_thai_gia, THAP_HON)
		self.assertEqual(so.items[0].gia_chuan, 111100)

	def test_g12_rate_used_is_kept_on_the_row(self):
		so = self.so([self.row(self.item(100000), 101000)])
		frappe.db.set_single_value("Selling Settings", "ty_le_lai_mac_dinh", 3)

		self.assertEqual(frappe.db.get_value("Sales Order Item", so.items[0].name, "ty_le_lai_ap_dung"), 1)

	def test_nothing_is_checked_when_switched_off(self):
		self.bat(0)

		d = self.so([self.row(self.item(100000), 1)]).items[0]

		self.assertFalse(d.trang_thai_gia)

	def test_tax_inclusive_price_is_compared_before_tax(self):
		account = frappe.db.get_value(
			"Account", {"company": self.company, "account_type": "Tax", "is_group": 0}, "name"
		)
		if not account:
			self.skipTest("Công ty test chưa có tài khoản thuế")
		tax = {
			"charge_type": "On Net Total",
			"account_head": account,
			"description": "VAT 10%",
			"rate": 10,
			"included_in_print_rate": 1,
		}

		d = self.so([self.row(self.item(100000), 111100)], taxes=[tax]).items[0]

		self.assertEqual((d.net_rate, d.trang_thai_gia), (101000, KHOP))

	def test_a_warning_lists_the_rows_that_differ(self):
		frappe.clear_messages()
		self.so([self.row(self.item(100000), 101000), self.row(self.item(100000), 99000)])

		messages = " ".join(str(m.get("message")) for m in frappe.get_message_log())
		self.assertIn("Dòng 2", messages)
		self.assertNotIn("Dòng 1", messages)


class TestKiemGiaQuotation(KiemChungTuCase):
	def quotation(self, rows, quotation_to="Customer", party_name=None):
		return frappe.get_doc(
			{
				"doctype": "Quotation",
				"company": self.company,
				"quotation_to": quotation_to,
				"party_name": party_name or self.khach,
				"transaction_date": self.d,
				"valid_till": add_days(self.d, 30),
				"selling_price_list": self.ban,
				"currency": self.currency,
				"ignore_pricing_rule": 1,
				"items": rows,
			}
		).insert(ignore_permissions=True)

	def test_quotation_rows_are_checked(self):
		q = self.quotation([self.row(self.item(100000), 101000), self.row(self.item(100000), 100000)])

		self.assertEqual([d.trang_thai_gia for d in q.items], [KHOP, THAP_HON])

	def test_g15_a_lead_gets_the_default_rate(self):
		lead = frappe.get_doc(
			{"doctype": "Lead", "first_name": f"_KG Lead {self.sfx}", "company_name": f"_KG Cty {self.sfx}"}
		).insert(ignore_permissions=True)

		d = self.quotation([self.row(self.item(100000), 101000)], "Lead", lead.name).items[0]

		self.assertEqual((d.trang_thai_gia, d.ty_le_lai_ap_dung), (KHOP, 1))
