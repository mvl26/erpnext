# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Submit Sales Order có giá lệch (BA12 R04, R05, R08, D03, D05; nghiệm thu A04, A05).

Không còn chế độ "Chặn" hay bước duyệt: lệch thì cảnh báo, vẫn lưu được; Submit chỉ cần
lý do (R04/R08) và, với dòng có giá đề xuất khác bảng giá, đủ 3 thông tin khách chấp
thuận (R05). Nhân viên bán hàng thường tự Submit được.
"""

import json

import frappe

from erpnext.controllers.accounts_controller import update_child_qty_rate
from erpnext.selling.tests.test_kiem_gia_chung_tu import KiemChungTuCase


class SubmitCase(KiemChungTuCase):
	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.set_user, "Administrator")
		self.nhan_vien = (
			frappe.get_doc(
				{
					"doctype": "User",
					"email": f"_kg_nv_{self.sfx}@example.com",
					"first_name": "KG nv",
					"send_welcome_email": 0,
					"roles": [{"role": "Sales User"}],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def submit_as_staff(self, so):
		frappe.set_user(self.nhan_vien)
		try:
			so.reload()
			so.submit()
		finally:
			frappe.set_user("Administrator")

	def chap_thuan(self, d, **values):
		values = {
			"so_van_ban_gia": "VB-01/2026",
			"nguoi_dai_dien_kh": "Ông A",
			"ngay_chap_thuan_gia": self.d,
			**values,
		}
		for f, v in values.items():
			d.set(f, v)

	def update_items(self, so, rows):
		frappe.set_user(self.nhan_vien)
		try:
			update_child_qty_rate("Sales Order", json.dumps(rows), so.name)
		finally:
			frappe.set_user("Administrator")

	def update_items_bi_chan(self, so, rows, regex):
		"""Như một request thật: bị chặn thì mọi thay đổi của lần gọi đó được hoàn tác."""
		frappe.db.savepoint("update_items")
		try:
			self.assertRaisesRegex(frappe.ValidationError, regex, self.update_items, so, rows)
		finally:
			frappe.db.rollback(save_point="update_items")


class TestLyDo(SubmitCase):
	def test_a04_mismatch_without_a_reason_is_blocked(self):
		so = self.so([self.row(self.item(123457), 125000)])
		self.assertRaisesRegex(frappe.ValidationError, "Lý do lệch giá", self.submit_as_staff, so)

	def test_a04_with_a_reason_staff_submits_without_any_approval(self):
		so = self.so([self.row(self.item(123457), 125000)], ly_do_lech_gia="Khách mua số lượng lớn")
		self.submit_as_staff(so)
		self.assertEqual(frappe.db.get_value("Sales Order", so.name, "docstatus"), 1)

	def test_d03_a_mismatched_order_can_still_be_saved(self):
		so = self.so([self.row(self.item(123457), 125000)])
		so.save()
		self.assertEqual(so.docstatus, 0)

	def test_r08_no_buying_price_needs_a_reason(self):
		so = self.so([self.row(self.item(gia_hd=None), 100000)])
		self.assertRaisesRegex(frappe.ValidationError, "chưa có giá mua", self.submit_as_staff, so)
		so.reload()
		so.ly_do_lech_gia = "Hàng NCC mới, chưa có báo giá"
		so.save()
		self.submit_as_staff(so)

	def test_matching_order_needs_nothing(self):
		self.submit_as_staff(self.so([self.row(self.item(123457), 124692)]))

	def test_customer_without_coefficient_needs_nothing(self):
		self.submit_as_staff(self.so([self.row(self.item(123457), 1)], customer=self.customer()))

	def test_switched_off_needs_nothing(self):
		so = self.so([self.row(self.item(123457), 1)])
		self.bat(0)
		self.submit_as_staff(so)


class TestChapThuan(SubmitCase):
	def so_khac_bang_gia(self):
		item = self.item(123457)
		self.gia_ban(item, 120000)
		return self.so([self.row(item, 124692)])

	def test_a05_missing_any_of_the_three_details_is_blocked(self):
		so = self.so_khac_bang_gia()
		for thieu in ("so_van_ban_gia", "nguoi_dai_dien_kh", "ngay_chap_thuan_gia"):
			so.reload()
			self.chap_thuan(so.items[0], **{thieu: None})
			so.save()
			with self.assertRaisesRegex(frappe.ValidationError, "chấp thuận") as ctx:
				self.submit_as_staff(so)
			label = frappe.get_meta("Sales Order Item").get_label(thieu)
			self.assertIn(label, str(ctx.exception))

	def test_a05_all_three_details_let_it_through(self):
		so = self.so_khac_bang_gia()
		self.chap_thuan(so.items[0])
		so.save()
		self.submit_as_staff(so)

	def test_details_are_per_row(self):
		item2 = self.item(100000)
		self.gia_ban(item2, 90000)
		so = self.so_khac_bang_gia()
		so.append("items", self.row(item2, 101000))
		so.save()
		self.chap_thuan(so.items[0])
		so.save()
		with self.assertRaisesRegex(frappe.ValidationError, "Dòng 2"):
			self.submit_as_staff(so)

	def test_reason_and_acceptance_are_both_needed_when_both_apply(self):
		item = self.item(123457)
		self.gia_ban(item, 120000)
		so = self.so([self.row(item, 125000)])
		self.chap_thuan(so.items[0])
		so.save()
		self.assertRaisesRegex(frappe.ValidationError, "Lý do lệch giá", self.submit_as_staff, so)


class TestCongKhachHang(SubmitCase):
	def test_portal_user_gets_a_generic_message(self):
		from erpnext.selling.kiem_gia.kiem_chung_tu import kiem_truoc_submit

		so = self.so([self.row(self.item(123457), 1)])
		khach_web = frappe.get_doc(
			{
				"doctype": "User",
				"email": f"_kg_web_{self.sfx}@example.com",
				"first_name": "KG web",
				"user_type": "Website User",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
		frappe.set_user(khach_web.name)
		with self.assertRaises(frappe.ValidationError) as ctx:
			kiem_truoc_submit(so)
		self.assertNotIn("Thấp hơn", str(ctx.exception))
		self.assertIn("Miyano kiểm tra giá", str(ctx.exception))


class TestUpdateItems(SubmitCase):
	def test_new_mismatched_row_needs_a_reason(self):
		item = self.item(123457)
		so = self.so([self.row(item, 124692)])
		self.submit_as_staff(so)
		d = so.items[0]
		rows = [
			{"docname": d.name, "item_code": d.item_code, "qty": 1, "rate": d.rate, "uom": d.uom},
			{
				"item_code": self.item(100000),
				"qty": 1,
				"rate": 90000,
				"uom": "_KG Cái",
				"delivery_date": str(self.d),
			},
		]
		self.update_items_bi_chan(so, rows, "Lý do lệch giá")

		frappe.db.set_value("Sales Order", so.name, "ly_do_lech_gia", "Giá khuyến mãi")
		self.update_items(so, rows)
		so.reload()
		self.assertEqual(so.items[1].trang_thai_gia, "Thấp hơn")

	def test_changing_a_rate_is_checked_again(self):
		item = self.item(123457)
		so = self.so([self.row(item, 124692)])
		self.submit_as_staff(so)
		d = so.items[0]
		rows = [{"docname": d.name, "item_code": d.item_code, "qty": 1, "rate": 130000, "uom": d.uom}]
		self.update_items_bi_chan(so, rows, "Lý do lệch giá")

	def test_d05_untouched_rows_of_an_old_order_are_not_rechecked(self):
		self.bat(0)
		cu = self.item(100000)
		so = self.so([self.row(cu, 1), self.row(self.item(100000), 101000)])
		so.submit()  # Submit khi chưa bật kiểm: dòng 1 lệch, không có lý do
		self.bat(1)
		d = so.items[1]
		self.update_items(
			so,
			[
				# Form "Update Items" luôn gửi kèm ngày giao; thiếu thì ERPNext coi là dòng đã đổi.
				{
					"docname": so.items[0].name,
					"item_code": cu,
					"qty": 1,
					"rate": 1,
					"uom": "_KG Cái",
					"conversion_factor": 1,
					"delivery_date": str(so.items[0].delivery_date),
				},
				{"docname": d.name, "item_code": d.item_code, "qty": 2, "rate": 101000, "uom": d.uom},
			],
		)
		self.assertEqual(frappe.db.get_value("Sales Order Item", d.name, "qty"), 2)
		self.assertFalse(frappe.db.get_value("Sales Order Item", so.items[0].name, "trang_thai_gia"))

	def test_new_row_that_differs_from_the_price_list_is_blocked(self):
		item = self.item(123457)
		moi = self.item(100000)
		self.gia_ban(moi, 90000)
		so = self.so([self.row(item, 124692)])
		self.submit_as_staff(so)
		d = so.items[0]
		rows = [
			{"docname": d.name, "item_code": d.item_code, "qty": 1, "rate": d.rate, "uom": d.uom},
			{"item_code": moi, "qty": 1, "rate": 101000, "uom": "_KG Cái", "delivery_date": str(self.d)},
		]
		self.update_items_bi_chan(so, rows, "chấp thuận")
