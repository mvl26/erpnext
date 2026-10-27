# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tìm giá mua theo BA12 D07 (báo giá đợt, rồi HĐ nguyên tắc) và làm tròn giá đề xuất (R03)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days

from erpnext.selling.kiem_gia.gia_goc import (
	BAO_GIA_DOT,
	CAO_HON,
	CHUA_CO_GIA_MUA,
	HD_NGUYEN_TAC,
	KHOP,
	THAP_HON,
	lam_tron_dong,
	ncc_cua_bang_gia,
	so_sanh,
	tim_gia_mua,
	tinh_gia_de_xuat,
)
from erpnext.selling.tests.test_kiem_gia_chung_tu import KiemChungTuCase


class TestTimGiaMua(KiemChungTuCase):
	def tim(self, item, ncc=None, ngay=None):
		return tim_gia_mua(item, ncc or self.ncc, ngay or self.d, self.company)

	def test_d07_contract_price_when_there_is_no_batch_quotation(self):
		item = self.item(123457)
		kq = self.tim(item)
		self.assertEqual((kq.gia_kho, kq.nguon), (123457, HD_NGUYEN_TAC))

	def test_d07_valid_batch_quotation_wins(self):
		item = self.item(123457)
		sq = self.bao_gia(item, 125000, valid_till=add_days(self.d, 10))
		kq = self.tim(item)
		self.assertEqual((kq.gia_kho, kq.nguon, kq.chung_tu), (125000, BAO_GIA_DOT, sq.name))

	def test_expired_batch_quotation_falls_back_to_the_contract(self):
		item = self.item(123457)
		self.bao_gia(item, 125000, ngay=add_days(self.d, -20), valid_till=add_days(self.d, -1))
		self.assertEqual(self.tim(item).nguon, HD_NGUYEN_TAC)

	def test_quotation_without_an_end_date_stays_valid(self):
		item = self.item(123457)
		self.bao_gia(item, 125000, ngay=add_days(self.d, -90))
		self.assertEqual(self.tim(item).nguon, BAO_GIA_DOT)

	def test_quotation_dated_after_the_order_is_ignored(self):
		item = self.item(123457)
		self.bao_gia(item, 125000, ngay=add_days(self.d, 1))
		self.assertEqual(self.tim(item).nguon, HD_NGUYEN_TAC)

	def test_draft_cancelled_and_stopped_quotations_are_ignored(self):
		item = self.item(123457)
		self.bao_gia(item, 1, submit=False)
		self.bao_gia(item, 2).cancel()
		dung = self.bao_gia(item, 3)
		frappe.db.set_value("Supplier Quotation", dung.name, "status", "Stopped")
		self.assertEqual(self.tim(item).gia_kho, 123457)

	def test_newest_quotation_wins(self):
		item = self.item(123457)
		self.bao_gia(item, 130000, ngay=add_days(self.d, -10))
		self.bao_gia(item, 125000, ngay=add_days(self.d, -2))
		self.assertEqual(self.tim(item).gia_kho, 125000)

	def test_another_suppliers_quotation_is_ignored(self):
		item = self.item(123457)
		self.bao_gia(item, 99000, ncc=self.supplier())
		self.assertEqual(self.tim(item).nguon, HD_NGUYEN_TAC)

	def test_quotation_per_box_is_converted_to_the_stock_uom(self):
		item = self.item(None, hop=10)
		self.bao_gia(item, 50000, uom="_KG Hộp", cf=10)
		self.assertEqual(self.tim(item).gia_kho, 5000)

	def test_quotation_discount_is_taken_into_account(self):
		item = self.item(None)
		sq = self.bao_gia(item, 100000, submit=False)
		sq.apply_discount_on = "Net Total"
		sq.additional_discount_percentage = 10
		sq.save()
		sq.submit()
		self.assertEqual(self.tim(item).gia_kho, 90000)

	def test_two_prices_in_the_newest_quotation_are_not_guessed(self):
		item = self.item(None)
		sq = self.bao_gia(item, 100000, submit=False)
		sq.append(
			"items",
			{
				"item_code": item,
				"qty": 1,
				"uom": "_KG Cái",
				"conversion_factor": 1,
				"rate": 90000,
				"warehouse": self.warehouse,
			},
		)
		sq.save()
		sq.submit()
		kq = self.tim(item)
		self.assertEqual(kq.trang_thai, CHUA_CO_GIA_MUA)
		self.assertIn(sq.name, kq.ly_do)

	def test_contract_needs_the_supplier_on_the_price_row(self):
		item = self.item(None)
		frappe.get_doc(
			{
				"doctype": "Item Price",
				"price_list": self.mua,
				"item_code": item,
				"uom": "_KG Cái",
				"price_list_rate": 100000,
				"valid_from": add_days(self.d, -5),
			}
		).insert(ignore_permissions=True)
		self.assertEqual(self.tim(item).trang_thai, CHUA_CO_GIA_MUA)

	def test_newest_contract_price_in_force_wins(self):
		item = self.item(100000)
		self.gia_hd(item, 110000, valid_from=add_days(self.d, -3))
		self.gia_hd(item, 120000, valid_from=add_days(self.d, 3))
		self.assertEqual(self.tim(item).gia_kho, 110000)
		self.assertEqual(self.tim(item, ngay=add_days(self.d, 3)).gia_kho, 120000)

	def test_two_contract_prices_on_the_same_date_are_not_guessed(self):
		item = self.item(100000)
		khac = self.price_list(f"Mua 2 - {self.ncc}", buying=1)
		self.gia_hd(item, 105000, price_list=khac)
		self.assertEqual(self.tim(item).trang_thai, CHUA_CO_GIA_MUA)

	def test_expired_contract_and_disabled_price_list_are_ignored(self):
		item = self.item(None)
		ip = self.gia_hd(item, 100000)
		frappe.db.set_value("Item Price", ip, "valid_upto", add_days(self.d, -1))
		self.assertEqual(self.tim(item).trang_thai, CHUA_CO_GIA_MUA)
		frappe.db.set_value("Item Price", ip, "valid_upto", None)
		frappe.db.set_value("Price List", self.mua, "enabled", 0)
		self.assertEqual(self.tim(item).trang_thai, CHUA_CO_GIA_MUA)

	def test_contract_per_box_is_converted_to_the_stock_uom(self):
		item = self.item(None, hop=10)
		self.gia_hd(item, 50000, uom="_KG Hộp")
		self.assertEqual(self.tim(item).gia_kho, 5000)

	def test_no_supplier(self):
		kq = tim_gia_mua(self.item(None, ncc=""), None, self.d, self.company)
		self.assertEqual(kq.trang_thai, CHUA_CO_GIA_MUA)


class TestNccCuaBangGia(KiemChungTuCase):
	"""Giá trong bảng giá mua riêng của một NCC (Nhà cung cấp → Bảng giá mặc định) phải ghi đúng
	NCC đó: giá HĐ nguyên tắc được nhận theo ô Nhà cung cấp, không theo tên bảng giá."""

	def setUp(self):
		super().setUp()
		frappe.db.set_value("Supplier", self.ncc, "default_price_list", self.mua)

	def test_the_price_list_owner_is_found(self):
		self.assertEqual(ncc_cua_bang_gia(self.mua), self.ncc)
		self.assertIsNone(ncc_cua_bang_gia(self.ban))

	def test_a_price_for_another_supplier_is_refused(self):
		item = self.item(None)
		self.assertRaises(frappe.ValidationError, self.gia_hd, item, 100000, ncc=self.supplier())

	def test_a_price_list_shared_by_several_suppliers_is_not_checked(self):
		frappe.db.set_value("Supplier", self.supplier(), "default_price_list", self.mua)
		self.gia_hd(self.item(None), 100000, ncc=self.supplier())

		self.assertIsNone(ncc_cua_bang_gia(self.mua))


class TestLamTron(FrappeTestCase):
	def test_r03_example(self):
		self.assertEqual(tinh_gia_de_xuat(123457, 1.01), 124692)
		self.assertEqual(tinh_gia_de_xuat(125000, 1.01), 126250)

	def test_half_a_dong_rounds_up(self):
		self.assertEqual(lam_tron_dong(124691.5), 124692)
		self.assertEqual(lam_tron_dong(124692.5), 124693)
		self.assertEqual(lam_tron_dong(124691.49), 124691)

	def test_applies_to_every_currency(self):
		self.assertEqual(tinh_gia_de_xuat(99.5, 1.01), 100)

	def test_compare(self):
		self.assertEqual(so_sanh(124692, 124692), (0, KHOP))
		self.assertEqual(so_sanh(124692.49, 124692), (0, KHOP))
		self.assertEqual(so_sanh(125000, 124692), (308, CAO_HON))
		self.assertEqual(so_sanh(124691, 124692), (-1, THAP_HON))
