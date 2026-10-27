# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Submit Sales Order có giá lệch (BA12 R04, R05, R08, D03, D05; nghiệm thu A04, A05; PO chốt
Q1, Q10).

Không còn chế độ "Chặn" hay bước duyệt: lệch thì cảnh báo, vẫn lưu được; Submit chỉ cần
lý do (R04/R08) và, với dòng có giá đề xuất khác bảng giá, đủ 3 thông tin khách chấp
thuận (R05). Nhân viên bán hàng thường tự Submit được.
"""

import json

import frappe

from erpnext.controllers.accounts_controller import update_child_qty_rate
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note, make_sales_invoice
from erpnext.selling.kiem_gia.thong_bao_gia_moi import lay_thong_bao_gia_moi
from erpnext.selling.tests.test_kiem_gia_cau_hinh import dam_bao_vai_tro
from erpnext.selling.tests.test_kiem_gia_chung_tu import KiemChungTuCase

GIAM_DOC = "_KG Giám đốc"
EMAIL = "nguoidatdon.kg@example.com"


class SubmitCase(KiemChungTuCase):
	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.set_user, "Administrator")
		self.nhan_vien = self.nguoi("nv", "Sales User")

	def nguoi(self, label, *roles):
		return (
			frappe.get_doc(
				{
					"doctype": "User",
					"email": f"_kg_{label}_{self.sfx}@example.com",
					"first_name": f"KG {label}",
					"send_welcome_email": 0,
					"roles": [{"role": r} for r in roles],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def as_user(self, user, fn, *args):
		frappe.set_user(user)
		try:
			return fn(*args)
		finally:
			frappe.set_user("Administrator")

	def submit_as_staff(self, so):
		so.reload()
		self.as_user(self.nhan_vien, so.submit)

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
		item = self.item(123457, gia_ban=124691.57)
		so = self.so([self.row(item, 125000)], ly_do_lech_gia="Khách mua số lượng lớn")
		self.submit_as_staff(so)
		self.assertEqual(frappe.db.get_value("Sales Order", so.name, "docstatus"), 1)

	def test_d03_a_mismatched_order_can_still_be_saved(self):
		so = self.so([self.row(self.item(123457), 125000)])
		so.save()
		self.assertEqual(so.docstatus, 0)

	def test_r08_no_buying_price_needs_a_reason(self):
		so = self.so([self.row(self.item(gia_hd=None, gia_ban=100000), 100000)])
		self.assertRaisesRegex(frappe.ValidationError, "chưa có giá mua", self.submit_as_staff, so)
		so.reload()
		so.ly_do_lech_gia = "Hàng NCC mới, chưa có báo giá"
		so.save()
		self.submit_as_staff(so)

	def test_matching_order_needs_nothing(self):
		self.submit_as_staff(self.so([self.row(self.item(123457, gia_ban=124691.57), 124691.57)]))

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
		return self.so([self.row(item, 124691.57)])

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

	def test_q2_item_missing_from_the_customer_list_needs_the_details(self):
		so = self.so([self.row(self.item(123457), 124691.57)])
		self.assertRaisesRegex(frappe.ValidationError, "chấp thuận", self.submit_as_staff, so)
		so.reload()
		self.chap_thuan(so.items[0])
		so.save()
		self.submit_as_staff(so)


class TestNguoiNhapChapThuan(SubmitCase):
	"""Q1: nhân viên nhập, hệ thống ghi người nhập và thời điểm; sau Submit, ô đã điền chỉ
	Giám đốc sửa."""

	def setUp(self):
		super().setUp()
		dam_bao_vai_tro(self, GIAM_DOC)
		frappe.db.set_single_value("Selling Settings", "vai_tro_sua_ty_le_lai", GIAM_DOC)
		self.giam_doc = self.nguoi("gd", "Sales User", GIAM_DOC)
		item = self.item(123457, gia_ban=120000)
		self.so_a = self.so([self.row(item, 124691.57)])

	def nhap(self, user, **values):
		so = frappe.get_doc("Sales Order", self.so_a.name)
		self.chap_thuan(so.items[0], **values)
		self.as_user(user, so.save)
		return frappe.db.get_value(
			"Sales Order Item",
			so.items[0].name,
			["cho_chap_thuan", "nguoi_nhap_chap_thuan", "thoi_diem_nhap_chap_thuan", "so_van_ban_gia"],
			as_dict=True,
		)

	def test_q1_staff_enters_and_the_system_records_who_and_when(self):
		self.assertEqual(self.so_a.items[0].cho_chap_thuan, 1)

		d = self.nhap(self.nhan_vien)

		self.assertEqual((d.cho_chap_thuan, d.nguoi_nhap_chap_thuan), (0, self.nhan_vien))
		self.assertTrue(d.thoi_diem_nhap_chap_thuan)

	def test_q1_who_and_when_cannot_be_typed_in(self):
		self.nhap(self.nhan_vien)
		so = frappe.get_doc("Sales Order", self.so_a.name)
		so.items[0].nguoi_nhap_chap_thuan = "Administrator"
		so.items[0].cho_chap_thuan = 1
		so.save()

		d = frappe.db.get_value(
			"Sales Order Item", so.items[0].name, ["nguoi_nhap_chap_thuan", "cho_chap_thuan"], as_dict=True
		)
		self.assertEqual((d.nguoi_nhap_chap_thuan, d.cho_chap_thuan), (self.nhan_vien, 0))

	def test_q1_after_submit_filled_details_only_the_director_changes(self):
		self.nhap(self.nhan_vien)
		self.submit_as_staff(self.so_a)

		self.assertRaisesRegex(
			frappe.PermissionError, "Giám đốc", self.nhap, self.nhan_vien, so_van_ban_gia="VB-02/2026"
		)
		d = self.nhap(self.giam_doc, so_van_ban_gia="VB-02/2026")
		self.assertEqual((d.so_van_ban_gia, d.nguoi_nhap_chap_thuan), ("VB-02/2026", self.giam_doc))

	def test_q1_attachment_required_when_switched_on(self):
		frappe.db.set_single_value("Selling Settings", "bat_buoc_dinh_kem_van_ban_gia", 1)
		self.assertEqual(self.nhap(self.nhan_vien).cho_chap_thuan, 1)
		with self.assertRaisesRegex(frappe.ValidationError, "Tệp văn bản chấp thuận"):
			self.submit_as_staff(self.so_a)

		self.assertEqual(self.nhap(self.nhan_vien, tep_van_ban_gia="/files/_kg_vb.pdf").cho_chap_thuan, 0)
		self.submit_as_staff(self.so_a)


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
		item = self.item(123457, gia_ban=124691.57)
		so = self.so([self.row(item, 124691.57)])
		self.submit_as_staff(so)
		d = so.items[0]
		rows = [
			{"docname": d.name, "item_code": d.item_code, "qty": 1, "rate": d.rate, "uom": d.uom},
			{
				"item_code": self.item(100000, gia_ban=101000),
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
		item = self.item(123457, gia_ban=124691.57)
		so = self.so([self.row(item, 124691.57)])
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


class TestChoChapThuan(SubmitCase):
	"""Q10: "Update Items" thêm dòng khác bảng giá không bị chặn; dòng chờ khách chấp thuận,
	chưa tạo được Phiếu giao / Hóa đơn bán; nhập đủ trên SO đã Submit thì mở khóa và gửi thông
	báo giá mới bổ sung."""

	def setUp(self):
		super().setUp()
		item = self.item(123457, gia_ban=124691.57)
		self.moi = self.item(100000, gia_ban=90000)  # đề xuất 101.000 khác bảng giá 90.000
		self.so_a = self.so([self.row(item, 124691.57)], contact_email=EMAIL)
		self.submit_as_staff(self.so_a)
		d = self.so_a.items[0]
		frappe.clear_messages()
		self.update_items(
			self.so_a,
			[
				{
					"docname": d.name,
					"item_code": d.item_code,
					"qty": 1,
					"rate": d.rate,
					"uom": d.uom,
					"conversion_factor": 1,
					"delivery_date": str(d.delivery_date),
				},
				{
					"item_code": self.moi,
					"qty": 1,
					"rate": 101000,
					"uom": "_KG Cái",
					"delivery_date": str(self.d),
				},
			],
		)
		self.so_a.reload()
		self.dong_moi = self.so_a.items[1]

	def test_q10_update_items_passes_and_the_new_row_waits(self):
		self.assertEqual((self.dong_moi.khac_bang_gia, self.dong_moi.cho_chap_thuan), (1, 1))
		self.assertEqual(self.so_a.items[0].cho_chap_thuan, 0)
		self.assertIn("chờ khách chấp thuận", self.canh_bao())
		self.assertEqual(lay_thong_bao_gia_moi(self.so_a.name)["dong"], [])

	def hoa_don(self):
		si = make_sales_invoice(self.so_a.name)
		# Site test có thể chưa đặt tài khoản doanh thu mặc định cho công ty.
		tk = frappe.db.get_value(
			"Account", {"company": self.company, "account_type": "Income Account", "is_group": 0}, "name"
		)
		for d in si.items:
			d.income_account = d.income_account or tk
		return si

	def test_q10_delivery_note_and_invoice_are_blocked_for_the_waiting_row(self):
		for phieu in (make_delivery_note(self.so_a.name), self.hoa_don()):
			self.assertRaisesRegex(frappe.ValidationError, "chưa chấp thuận", phieu.insert)

	def test_q10_other_rows_can_still_be_delivered(self):
		dn = make_delivery_note(self.so_a.name)
		dn.items = [d for d in dn.items if d.so_detail != self.dong_moi.name]
		dn.insert()
		self.assertEqual(len(dn.items), 1)

	def test_q10_filling_the_details_releases_the_row_and_sends_a_supplement(self):
		so = frappe.get_doc("Sales Order", self.so_a.name)
		self.chap_thuan(so.items[1])
		self.as_user(self.nhan_vien, so.save)

		d = frappe.db.get_value(
			"Sales Order Item", self.dong_moi.name, ["cho_chap_thuan", "nguoi_nhap_chap_thuan"], as_dict=True
		)
		self.assertEqual((d.cho_chap_thuan, d.nguoi_nhap_chap_thuan), (0, self.nhan_vien))
		thu = frappe.get_all(
			"Communication",
			filters={"reference_doctype": "Sales Order", "reference_name": so.name},
			fields=["subject", "content", "recipients"],
		)
		self.assertEqual(len(thu), 1)
		self.assertIn("bổ sung", thu[0].subject)
		self.assertIn(self.moi, thu[0].content)
		self.assertIn(EMAIL, thu[0].recipients)
		self.assertEqual([r["item_code"] for r in lay_thong_bao_gia_moi(so.name)["dong"]], [self.moi])
		make_delivery_note(so.name).insert()
		self.hoa_don().insert()

	def test_q10_saving_again_sends_nothing_more(self):
		so = frappe.get_doc("Sales Order", self.so_a.name)
		self.chap_thuan(so.items[1])
		so.save()
		so.reload()
		so.save()
		self.assertEqual(
			frappe.db.count("Communication", {"reference_doctype": "Sales Order", "reference_name": so.name}),
			1,
		)
