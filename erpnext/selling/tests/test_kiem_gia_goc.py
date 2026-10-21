# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Giá gốc, giá chuẩn và báo cáo đối chiếu giá bán ↔ giá mua (thiết kế mục 6.1.3-6.1.4, 13).

Mã G.. trong tên test là tình huống ở mục 7.1 của spec
`docs/superpowers/specs/2026-10-21-kiem-gia-ban-bao-gia-doi-soat-design.md`.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, nowdate

from erpnext.selling.kiem_gia.gia_goc import (
	CAO_HON,
	CHUA_XAC_DINH,
	CO_GIA_GOC,
	KHONG_CO_GIA_MUA,
	KHOP,
	NHIEU_GIA,
	THAP_HON,
	so_sanh,
	tim_gia_goc,
	tinh_gia_chuan,
)
from erpnext.selling.report.doi_chieu_gia_ban_gia_mua.doi_chieu_gia_ban_gia_mua import execute
from erpnext.stock.tests.test_item_code_rule import use_naming_mode

D = None


class KiemGiaCase(FrappeTestCase):
	def setUp(self):
		global D
		D = getdate(nowdate())
		frappe.db.savepoint("kiem_gia_test")
		self.addCleanup(frappe.db.rollback, save_point="kiem_gia_test")
		use_naming_mode(self, "Item Code")
		self.sfx = frappe.generate_hash(length=6)
		for uom in ("_KG Cái", "_KG Hộp"):
			if not frappe.db.exists("UOM", uom):
				frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert(ignore_permissions=True)
		self.ncc_a = self.supplier("A")
		self.ncc_b = self.supplier("B")

	def supplier(self, label):
		doc = frappe.new_doc("Supplier")
		doc.supplier_name = f"_KG NCC {label} {self.sfx}"
		doc.supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
		return doc.insert(ignore_permissions=True).name

	def item(self, default_supplier=None, hop=None):
		doc = frappe.new_doc("Item")
		doc.item_code = f"_KG-{frappe.generate_hash(length=8)}"
		doc.item_name = doc.item_code
		doc.item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
		doc.stock_uom = "_KG Cái"
		doc.is_stock_item = 1
		if hop:
			doc.append("uoms", {"uom": "_KG Hộp", "conversion_factor": hop})
		if default_supplier:
			doc.append("supplier_items", {"supplier": default_supplier, "is_default": 1})
		return doc.insert(ignore_permissions=True).name

	def price_list(self, label, buying=1, enabled=1):
		name = f"_KG {label} {self.sfx}"
		if not frappe.db.exists("Price List", name):
			frappe.get_doc(
				{
					"doctype": "Price List",
					"price_list_name": name,
					"buying": buying,
					"selling": 0 if buying else 1,
					"currency": "VND",
					"enabled": enabled,
				}
			).insert(ignore_permissions=True)
		return name

	def price(self, price_list, item, rate, valid_from, uom="_KG Cái", supplier=None, valid_upto=None):
		return (
			frappe.get_doc(
				{
					"doctype": "Item Price",
					"price_list": price_list,
					"item_code": item,
					"uom": uom,
					"price_list_rate": rate,
					"valid_from": valid_from,
					"valid_upto": valid_upto,
					"supplier": supplier,
					"currency": "VND",
				}
			)
			.insert(ignore_permissions=True)
			.name
		)


class TestTimGiaGoc(KiemGiaCase):
	def test_g17_default_supplier_price_wins_over_a_newer_general_price(self):
		item = self.item(default_supplier=self.ncc_a)
		ip = self.price(self.price_list("Mua A"), item, 100000, add_days(D, -60), supplier=self.ncc_a)
		self.price(self.price_list("Mua chung"), item, 98000, add_days(D, -10))

		kq = tim_gia_goc(item, D)

		self.assertEqual(kq.trang_thai, CO_GIA_GOC)
		self.assertEqual(kq.gia_goc, 100000)
		self.assertEqual(kq.item_price, ip)
		self.assertEqual(kq.supplier, self.ncc_a)

	def test_g18_without_default_supplier_the_newest_price_wins(self):
		item = self.item()
		self.price(self.price_list("Mua B"), item, 50000, add_days(D, -90), supplier=self.ncc_b)
		self.price(self.price_list("Mua chung"), item, 52000, add_days(D, -20))

		self.assertEqual(tim_gia_goc(item, D).gia_goc, 52000)

	def test_default_supplier_without_a_valid_price_falls_back_to_the_newest(self):
		item = self.item(default_supplier=self.ncc_a)
		self.price(self.price_list("Mua A"), item, 100000, add_days(D, 5), supplier=self.ncc_a)
		self.price(self.price_list("Mua chung"), item, 98000, add_days(D, -10))

		self.assertEqual(tim_gia_goc(item, D).gia_goc, 98000)

	def test_g19_two_different_prices_on_the_same_newest_date_are_not_guessed(self):
		item = self.item()
		self.price(self.price_list("Mua A"), item, 20000, add_days(D, -15), supplier=self.ncc_a)
		self.price(self.price_list("Mua B"), item, 21000, add_days(D, -15), supplier=self.ncc_b)

		kq = tim_gia_goc(item, D)

		self.assertEqual(kq.trang_thai, NHIEU_GIA)
		self.assertIsNone(kq.gia_goc)

	def test_two_equal_prices_on_the_same_date_are_not_ambiguous(self):
		item = self.item()
		self.price(self.price_list("Mua A"), item, 20000, add_days(D, -15), supplier=self.ncc_a)
		self.price(self.price_list("Mua B"), item, 20000, add_days(D, -15), supplier=self.ncc_b)

		self.assertEqual(tim_gia_goc(item, D).gia_goc, 20000)

	def test_g20_no_buying_price(self):
		item = self.item()
		self.price(self.price_list("Bán", buying=0), item, 30000, add_days(D, -5))

		self.assertEqual(tim_gia_goc(item, D).trang_thai, KHONG_CO_GIA_MUA)

	def test_g21_a_future_price_applies_only_from_its_date(self):
		item = self.item(default_supplier=self.ncc_a)
		pl = self.price_list("Mua A")
		self.price(pl, item, 100000, add_days(D, -60), supplier=self.ncc_a)
		self.price(pl, item, 105000, add_days(D, 5), supplier=self.ncc_a)

		self.assertEqual(tim_gia_goc(item, D).gia_goc, 100000)
		self.assertEqual(tim_gia_goc(item, add_days(D, 5)).gia_goc, 105000)

	def test_expired_prices_and_disabled_price_lists_are_ignored(self):
		item = self.item()
		self.price(self.price_list("Mua A"), item, 1, add_days(D, -30), valid_upto=add_days(D, -1))
		# ERPNext không cho thêm giá vào bảng giá đang tắt: thêm trước, tắt sau.
		tat = self.price_list("Mua tắt")
		self.price(tat, item, 2, add_days(D, -5))
		frappe.db.set_value("Price List", tat, "enabled", 0)

		self.assertEqual(tim_gia_goc(item, D).trang_thai, KHONG_CO_GIA_MUA)

	def test_g11_a_price_per_box_is_converted_to_the_stock_uom(self):
		item = self.item(hop=10)
		self.price(self.price_list("Mua A"), item, 1000000, add_days(D, -5), uom="_KG Hộp")

		self.assertEqual(tim_gia_goc(item, D).gia_goc, 100000)


class TestGiaChuan(FrappeTestCase):
	def test_g1_one_percent(self):
		self.assertEqual(tinh_gia_chuan(100000, 1, 1, 4), 101000)

	def test_g3_customer_rate(self):
		self.assertEqual(tinh_gia_chuan(100000, 1, 2, 4), 102000)

	def test_g6_rounding_follows_the_field_precision(self):
		self.assertEqual(tinh_gia_chuan(12345.67, 1, 1, 4), 12469.1267)
		self.assertEqual(tinh_gia_chuan(12345.67, 10, 1, 2), 124691.27)

	def test_compare(self):
		self.assertEqual(so_sanh(101000, 101000, 4), (0, KHOP))
		self.assertEqual(so_sanh(52000, 52520, 4), (-520, THAP_HON))
		self.assertEqual(so_sanh(101500, 101000, 4), (500, CAO_HON))


class TestBaoCaoDoiChieu(KiemGiaCase):
	def rows(self, price_list, **filters):
		_columns, data = execute({"price_list": price_list, "ngay": D, **filters})
		return {(r.item_code, r.uom): r for r in data}

	def test_report_classifies_each_selling_price(self):
		mua = self.price_list("Mua A")
		ban = self.price_list("Bán H", buying=0)
		khop, thap, cao, khong = (self.item() for _ in range(4))
		hop = self.item(hop=10)
		for item, gia_mua in ((khop, 100000), (thap, 52000), (cao, 10000), (hop, 12345.67)):
			self.price(mua, item, gia_mua, add_days(D, -30))
		self.price(ban, khop, 101000, add_days(D, -10))
		self.price(ban, thap, 52000, add_days(D, -10))
		self.price(ban, cao, 20000, add_days(D, -10))
		self.price(ban, khong, 3000, add_days(D, -10))
		self.price(ban, hop, 124691.267, add_days(D, -10), uom="_KG Hộp")

		rows = self.rows(ban)

		self.assertEqual(rows[(khop, "_KG Cái")].trang_thai, KHOP)
		self.assertEqual(rows[(thap, "_KG Cái")].trang_thai, THAP_HON)
		self.assertEqual(rows[(thap, "_KG Cái")].chenh_lech, -520)
		self.assertEqual(rows[(cao, "_KG Cái")].trang_thai, CAO_HON)
		self.assertEqual(rows[(cao, "_KG Cái")].ty_le_lai_thuc, 100)
		self.assertEqual(rows[(khong, "_KG Cái")].trang_thai, CHUA_XAC_DINH)
		self.assertEqual(rows[(hop, "_KG Hộp")].gia_chuan, tinh_gia_chuan(12345.67, 10, 1, self.precision()))

	def test_report_uses_the_selling_price_in_force_on_the_date(self):
		mua = self.price_list("Mua A")
		ban = self.price_list("Bán H", buying=0)
		item = self.item()
		self.price(mua, item, 100000, add_days(D, -30))
		self.price(ban, item, 99000, add_days(D, -20))
		self.price(ban, item, 101000, add_days(D, -5))
		self.price(ban, item, 120000, add_days(D, 7))

		row = self.rows(ban)[(item, "_KG Cái")]

		self.assertEqual(row.gia_ban, 101000)
		self.assertEqual(row.trang_thai, KHOP)

	def test_only_mismatches_and_custom_margin(self):
		mua = self.price_list("Mua A")
		ban = self.price_list("Bán H", buying=0)
		item = self.item()
		self.price(mua, item, 100000, add_days(D, -30))
		self.price(ban, item, 101000, add_days(D, -5))

		self.assertNotIn((item, "_KG Cái"), self.rows(ban, chi_hien_lech=1))
		self.assertEqual(self.rows(ban, ty_le_lai=2)[(item, "_KG Cái")].trang_thai, THAP_HON)

	def precision(self):
		return frappe.get_precision("Item Price", "price_list_rate")
