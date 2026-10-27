# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Báo cáo đối soát giá mua - giá bán theo SO (BA12 A08, D05) và báo cáo đối chiếu bảng giá."""

import frappe
from frappe.utils import add_days

from erpnext.selling.kiem_gia.gia_goc import CAO_HON, CHUA_CO_GIA_MUA, KHOP, THAP_HON
from erpnext.selling.report.doi_chieu_gia_ban_gia_mua.doi_chieu_gia_ban_gia_mua import (
	KHONG_CO_HE_SO,
)
from erpnext.selling.report.doi_chieu_gia_ban_gia_mua.doi_chieu_gia_ban_gia_mua import (
	execute as doi_chieu,
)
from erpnext.selling.report.doi_soat_gia_mua_gia_ban.doi_soat_gia_mua_gia_ban import execute as doi_soat
from erpnext.selling.tests.test_kiem_gia_chung_tu import KiemChungTuCase


class TestDoiSoatTheoSO(KiemChungTuCase):
	def setUp(self):
		super().setUp()
		self.item_a = self.item(123457)
		self.gia_ban(self.item_a, 120000)
		self.so_a = self.so([self.row(self.item_a, 125000)], ly_do_lech_gia="Giá khuyến mãi")
		d = self.so_a.items[0]
		d.so_van_ban_gia, d.nguoi_dai_dien_kh, d.ngay_chap_thuan_gia = "VB-09/2026", "Ông B", self.d
		self.so_a.save()
		self.so_a.submit()

	def chay(self, **filters):
		return doi_soat(
			{"from_date": add_days(self.d, -1), "to_date": self.d, "customer": self.khach, **filters}
		)[1]

	def test_a08_every_required_column(self):
		r = self.chay()[0]
		self.assertEqual(
			{
				k: r[k]
				for k in (
					"sales_order",
					"item_code",
					"ncc",
					"nguon_gia_mua",
					"gia_mua",
					"he_so",
					"gia_ban",
					"gia_bang_gia",
					"chenh_lech",
					"ly_do",
					"so_van_ban",
				)
			},
			{
				"sales_order": self.so_a.name,
				"item_code": self.item_a,
				"ncc": self.ncc,
				"nguon_gia_mua": "HĐ nguyên tắc",
				"gia_mua": 123457,
				"he_so": 1.01,
				"gia_ban": 125000,
				"gia_bang_gia": 120000,
				"chenh_lech": 308.43,
				"ly_do": "Giá khuyến mãi",
				"so_van_ban": "VB-09/2026",
			},
		)

	def test_filters_by_customer_and_period(self):
		self.assertEqual(self.chay(customer=self.customer(he_so=1.01)), [])
		self.assertEqual(self.chay(from_date=add_days(self.d, 1), to_date=add_days(self.d, 2)), [])

	def test_drafts_only_on_request(self):
		self.so([self.row(self.item(100000), 101000)])
		self.assertEqual(len(self.chay()), 1)
		self.assertEqual(len(self.chay(gom_nhap=1)), 2)

	def test_only_mismatches(self):
		khop = self.so([self.row(self.item(100000, gia_ban=101000), 101000)])
		khop.submit()
		self.assertEqual([r.sales_order for r in self.chay(chi_lech=1)], [self.so_a.name])

	def test_sales_user_can_open_the_report(self):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": f"_kg_nvbh_{self.sfx}@example.com",
				"first_name": "Nhân viên bán hàng",
				"send_welcome_email": 0,
				"roles": [{"role": "Sales User"}],
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user(user.name)

		self.assertTrue(frappe.get_doc("Report", "Doi Soat Gia Mua Gia Ban").is_permitted())

	def test_q1_who_entered_the_acceptance_and_when(self):
		r = self.chay()[0]

		self.assertEqual((r.chap_thuan, r.nguoi_nhap_chap_thuan), ("Đủ", "Administrator"))
		self.assertTrue(r.thoi_diem_nhap_chap_thuan)

	def test_q2_missing_list_price_is_blank_and_the_row_waits(self):
		so = self.so([self.row(self.item(100000), 101000)])
		r = next(r for r in self.chay(gom_nhap=1) if r.sales_order == so.name)

		self.assertEqual((r.gia_bang_gia, r.ngoai_bang_gia, r.chap_thuan), (None, 1, "Chờ chấp thuận"))
		self.assertEqual([r.sales_order for r in self.chay(gom_nhap=1, cho_chap_thuan=1)], [so.name])

	def test_d05_later_buying_price_shows_only_in_the_report(self):
		self.gia_hd(self.item_a, 130000, valid_from=self.d)
		r = self.chay()[0]

		self.assertEqual(frappe.db.get_value("Sales Order Item", self.so_a.items[0].name, "gia_mua"), 123457)
		self.assertEqual((r.gia_mua, r.gia_mua_hien_tai, r.gia_mua_doi), (123457, 130000, 6543))

	def test_customers_without_coefficient_are_not_listed(self):
		so = self.so([self.row(self.item(100000), 1)], customer=self.customer())
		so.submit()
		self.assertEqual(self.chay(customer=so.customer), [])


class TestDoiChieuBangGia(KiemChungTuCase):
	def chay(self, **filters):
		return {r.item_code: r for r in doi_chieu({"price_list": self.ban, "ngay": self.d, **filters})[1]}

	def test_each_selling_price_is_classified_with_the_customer_coefficient(self):
		khop, cao, thap, khong_gia = self.item(100000), self.item(100000), self.item(100000), self.item(None)
		self.gia_ban(khop, 101000)
		self.gia_ban(cao, 102000)
		self.gia_ban(thap, 100000)
		self.gia_ban(khong_gia, 1)
		kq = self.chay()

		self.assertEqual(kq[khop].trang_thai, KHOP)
		self.assertEqual((kq[cao].trang_thai, kq[cao].chenh_lech), (CAO_HON, 1000))
		self.assertEqual(kq[thap].trang_thai, THAP_HON)
		self.assertEqual(kq[khong_gia].trang_thai, CHUA_CO_GIA_MUA)
		self.assertEqual(kq[khop].customer, self.khach)

	def test_trial_coefficient(self):
		item = self.item(100000)
		self.gia_ban(item, 105000)
		self.assertEqual(self.chay(he_so=1.05)[item].trang_thai, KHOP)

	def test_customer_without_coefficient(self):
		item = self.item(100000)
		self.gia_ban(item, 105000)
		self.assertEqual(self.chay(customer=self.customer())[item].trang_thai, KHONG_CO_HE_SO)
