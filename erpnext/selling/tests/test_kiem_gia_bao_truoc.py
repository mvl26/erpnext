# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Báo trước khi đổi giá (YC4, Đợt 2 bước 2.1-2.4; spec mục 6.2, 14; tình huống T1-T12)."""

import frappe
from frappe.utils import add_days

from erpnext.selling.kiem_gia.bao_truoc import CHO_GUI, DA_GUI, DA_XAC_NHAN, gui_thong_bao_doi_gia
from erpnext.selling.tests.test_kiem_gia_cau_hinh import dam_bao_vai_tro
from erpnext.selling.tests.test_kiem_gia_chung_tu import KiemChungTuCase

GIAM_DOC = "_KG Giám đốc"
EMAIL = "himedic.demo@example.com"


class BaoTruocCase(KiemChungTuCase):
	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.set_user, "Administrator")
		dam_bao_vai_tro(self, GIAM_DOC)
		frappe.db.set_single_value("Selling Settings", "vai_tro_sua_ty_le_lai", GIAM_DOC)
		frappe.clear_document_cache("Selling Settings", "Selling Settings")
		self.cho = self.price_list("Chờ", buying=0)
		self.item_a = self.item(100000)
		self.cu = self.gia(self.ban, self.item_a, 101000, add_days(self.d, -30))
		self.bat_bao_truoc()
		self.giam_doc = self.nguoi("gd", ["Sales Master Manager", "Sales Manager", GIAM_DOC])
		self.nhan_vien = self.nguoi("nv", ["Sales Master Manager", "Sales Manager", "Sales User"])

	def bat_bao_truoc(self, **values):
		pl = frappe.get_doc("Price List", self.ban)
		pl.update(
			{
				"bao_truoc_khi_doi_gia": 1,
				"so_ngay_bao_truoc": 7,
				"bang_gia_cho": self.cho,
				"email_nhan_thong_bao": EMAIL,
				**values,
			}
		)
		return pl.save(ignore_permissions=True)

	def nguoi(self, label, roles):
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

	def gia(self, price_list, item, rate, valid_from, **fields):
		return frappe.get_doc(
			{
				"doctype": "Item Price",
				"price_list": price_list,
				"item_code": item,
				"uom": "_KG Cái",
				"price_list_rate": rate,
				"valid_from": valid_from,
				"currency": self.currency,
				**fields,
			}
		).insert(ignore_permissions=True)

	def as_user(self, user, fn, *args, **kwargs):
		frappe.set_user(user)
		try:
			return fn(*args, **kwargs)
		finally:
			frappe.set_user("Administrator")


class TestCaiDatBangGia(BaoTruocCase):
	"""2.1"""

	def test_pending_list_is_required(self):
		self.assertRaisesRegex(frappe.ValidationError, "Bảng giá chờ", self.bat_bao_truoc, bang_gia_cho=None)

	def test_pending_list_cannot_be_the_main_list_or_a_buying_list(self):
		self.assertRaises(frappe.ValidationError, self.bat_bao_truoc, bang_gia_cho=self.ban)
		self.assertRaises(frappe.ValidationError, self.bat_bao_truoc, bang_gia_cho=self.mua)

	def test_one_pending_list_serves_one_main_list(self):
		khac = frappe.get_doc(
			{
				"doctype": "Price List",
				"price_list_name": f"_KG Bán 2 {self.sfx}",
				"selling": 1,
				"currency": self.currency,
				"enabled": 1,
				"bao_truoc_khi_doi_gia": 1,
				"bang_gia_cho": self.cho,
			}
		)
		self.assertRaisesRegex(frappe.ValidationError, "đang dùng cho", khac.insert, ignore_permissions=True)

	def test_staff_cannot_switch_the_rule_off(self):
		pl = frappe.get_doc("Price List", self.ban)
		pl.bao_truoc_khi_doi_gia = 0

		self.assertRaises(
			frappe.PermissionError, self.as_user, self.nhan_vien, pl.save, ignore_permissions=True
		)

	def test_director_can_change_the_settings(self):
		pl = frappe.get_doc("Price List", self.ban)
		pl.so_ngay_bao_truoc = 10

		self.as_user(self.giam_doc, pl.save, ignore_permissions=True)

	def test_t4_sales_documents_cannot_use_the_pending_list(self):
		so = frappe.get_doc(
			{
				"doctype": "Sales Order",
				"company": self.company,
				"customer": self.khach,
				"transaction_date": self.d,
				"delivery_date": add_days(self.d, 7),
				"selling_price_list": self.cho,
				"currency": self.currency,
				"ignore_pricing_rule": 1,
				"items": [self.row(self.item_a, 101000)],
			}
		)
		self.assertRaisesRegex(frappe.ValidationError, "bảng giá chờ", so.insert, ignore_permissions=True)


class TestChanSuaBangGiaChinh(BaoTruocCase):
	"""2.2, 2.3 (T2, T3, T10)"""

	def test_new_price_in_the_pending_list_is_waiting(self):
		ip = self.gia(self.cho, self.item_a, 105000, self.d)

		self.assertEqual(ip.trang_thai_thong_bao, CHO_GUI)

	def test_t3_adding_straight_to_the_main_list_is_blocked(self):
		self.assertRaisesRegex(
			frappe.ValidationError,
			"bảng giá chờ",
			self.gia,
			self.ban,
			self.item_a,
			105000,
			add_days(self.d, 7),
		)

	def test_t2_editing_an_existing_price_is_blocked(self):
		for field, value in (
			("price_list_rate", 99000),
			("valid_from", add_days(self.d, -1)),
			("valid_upto", add_days(self.d, 30)),
		):
			ip = frappe.get_doc("Item Price", self.cu.name)
			ip.set(field, value)
			self.assertRaisesRegex(frappe.ValidationError, "Không sửa được", ip.save, ignore_permissions=True)

	def test_moving_a_price_out_of_the_main_list_is_blocked(self):
		ip = frappe.get_doc("Item Price", self.cu.name)
		ip.price_list = self.cho

		self.assertRaises(frappe.ValidationError, ip.save, ignore_permissions=True)

	def test_deleting_a_main_list_price_is_blocked(self):
		self.assertRaisesRegex(
			frappe.ValidationError,
			"Không xóa",
			self.as_user,
			self.nhan_vien,
			frappe.delete_doc,
			"Item Price",
			self.cu.name,
			ignore_permissions=True,
		)

	def test_pending_prices_can_be_edited_and_deleted(self):
		ip = self.gia(self.cho, self.item_a, 105000, self.d)
		ip.price_list_rate = 104000
		ip.save(ignore_permissions=True)

		frappe.delete_doc("Item Price", ip.name, ignore_permissions=True)

	def test_t10_same_start_date_as_a_main_list_price_is_blocked(self):
		self.assertRaisesRegex(
			frappe.ValidationError,
			"chồng lên",
			self.gia,
			self.cho,
			self.item_a,
			105000,
			add_days(self.d, -30),
		)

	def test_t10_two_pending_prices_on_the_same_date_are_blocked(self):
		# Hai dòng giống hệt nhau thì ERPNext đã chặn (trùng Item Price); khác Hiệu lực đến thì
		# ERPNext để lọt, T10 chặn.
		self.gia(self.cho, self.item_a, 105000, add_days(self.d, 7))

		self.assertRaisesRegex(
			frappe.ValidationError,
			"chồng lên",
			self.gia,
			self.cho,
			self.item_a,
			106000,
			add_days(self.d, 7),
			valid_upto=add_days(self.d, 40),
		)

	def test_t10_an_end_date_that_would_bring_the_old_price_back_is_blocked(self):
		# Hết hạn thì giá cũ (không có Hiệu lực đến) tự áp lại mà khách không được báo.
		self.assertRaisesRegex(
			frappe.ValidationError,
			"chồng lên",
			self.gia,
			self.cho,
			self.item_a,
			105000,
			add_days(self.d, 7),
			valid_upto=add_days(self.d, 30),
		)

	def test_t10_an_end_date_running_into_the_next_price_is_blocked(self):
		moi = self.item(50000)
		self.gia(self.cho, moi, 50500, add_days(self.d, 7), valid_upto=add_days(self.d, 40))

		self.assertRaisesRegex(
			frappe.ValidationError, "chồng lên", self.gia, self.cho, moi, 51000, add_days(self.d, 20)
		)

	def test_t10_what_is_not_an_overlap(self):
		# Giá sau không hạn thay giá trước (T1b); giá có hạn mà không còn giá nào khác; giá riêng
		# của một khách là dòng khác.
		self.gia(self.cho, self.item_a, 105000, add_days(self.d, 7))
		self.gia(self.cho, self.item(50000), 50500, add_days(self.d, 7), valid_upto=add_days(self.d, 40))
		self.gia(self.cho, self.item_a, 104000, add_days(self.d, -30), customer=self.khach)

	def test_unrelated_price_lists_are_untouched(self):
		ip = self.gia(self.mua, self.item_a, 90000, self.d)
		ip.price_list_rate = 91000
		ip.save(ignore_permissions=True)
		frappe.delete_doc("Item Price", ip.name, ignore_permissions=True)


class TestGuiThongBao(BaoTruocCase):
	"""2.4 (T1, T1b, T6, T7, T12)"""

	def gui(self, user=None):
		return self.as_user(user or self.giam_doc, gui_thong_bao_doi_gia, self.ban)

	def test_only_the_director_can_send(self):
		self.gia(self.cho, self.item_a, 105000, add_days(self.d, 7))

		self.assertRaises(frappe.PermissionError, self.gui, self.nhan_vien)

	def test_t1b_send_moves_the_price_and_keeps_the_old_one(self):
		moi = self.gia(self.cho, self.item_a, 105000, add_days(self.d, 7))

		r = self.gui()

		moi.reload()
		self.assertEqual((moi.price_list, moi.trang_thai_thong_bao), (self.ban, DA_GUI))
		self.assertEqual((moi.so_ngay_bao_truoc, moi.bao_gap), (7, 0))
		self.assertEqual(str(moi.ngay_gui_thong_bao), str(self.d))
		self.assertEqual(moi.thong_bao, r["thong_bao"])
		self.assertTrue(frappe.db.exists("Item Price", self.cu.name))
		self.assertFalse(frappe.get_all("Item Price", filters={"price_list": self.cho}))

	def test_one_email_lists_old_and_new_prices(self):
		item_b = self.item(50000)
		self.gia(self.cho, self.item_a, 105000, add_days(self.d, 7))
		self.gia(self.cho, item_b, 50500, add_days(self.d, 10))

		r = self.gui()

		comm = frappe.get_doc("Communication", r["thong_bao"])
		self.assertEqual((comm.reference_doctype, comm.reference_name), ("Price List", self.ban))
		self.assertIn(EMAIL, comm.recipients)
		self.assertIn(self.item_a, comm.content)
		self.assertIn(item_b, comm.content)
		self.assertIn("101.000", comm.content.replace(",", "."))
		self.assertEqual(r["so_dong"], 2)

	def test_t1_short_notice_warns_and_flags_but_does_not_block(self):
		moi = self.gia(self.cho, self.item_a, 105000, add_days(self.d, 3))
		frappe.clear_messages()

		r = self.gui()

		moi.reload()
		self.assertEqual(
			(moi.bao_gap, moi.so_ngay_bao_truoc, str(moi.valid_from)), (1, 3, str(add_days(self.d, 3)))
		)
		self.assertEqual(r["bao_gap"], 1)
		self.assertIn("thiếu 4 ngày", " ".join(str(m.get("message")) for m in frappe.get_message_log()))

	def test_t6_a_price_cut_also_goes_through_notice(self):
		moi = self.gia(self.cho, self.item_a, 95000, add_days(self.d, 7))

		self.gui()

		self.assertEqual(frappe.db.get_value("Item Price", moi.name, "trang_thai_thong_bao"), DA_GUI)

	def test_d2_4_a_date_in_the_past_blocks_and_nothing_moves(self):
		qua_khu = self.gia(self.cho, self.item_a, 105000, add_days(self.d, -1))
		tuong_lai = self.gia(self.cho, self.item(1000), 1010, add_days(self.d, 7))

		self.assertRaisesRegex(frappe.ValidationError, "Sửa ngày hiệu lực", self.gui)
		self.assertEqual(frappe.db.get_value("Item Price", qua_khu.name, "price_list"), self.cho)
		self.assertEqual(frappe.db.get_value("Item Price", tuong_lai.name, "price_list"), self.cho)

	def test_draft_dated_today_can_be_sent_as_short_notice(self):
		moi = self.gia(self.cho, self.item_a, 105000, self.d)

		self.gui()

		self.assertEqual(
			frappe.db.get_value("Item Price", moi.name, ["so_ngay_bao_truoc", "bao_gap"]), (0, 1)
		)

	def test_t10_an_overlap_left_in_the_pending_list_blocks_sending(self):
		# Giá chờ lập trước khi có kiểm T10 (hoặc ghi thẳng DB): lúc gửi vẫn bị chặn, không dòng nào chuyển.
		dau = self.gia(self.cho, self.item_a, 105000, add_days(self.d, 7))
		sau = frappe.get_doc(
			{
				"doctype": "Item Price",
				"price_list": self.cho,
				"item_code": self.item_a,
				"uom": "_KG Cái",
				"price_list_rate": 106000,
				"valid_from": add_days(self.d, 7),
				"valid_upto": add_days(self.d, 40),
				"currency": self.currency,
			}
		)
		sau.flags.tu_thong_bao_doi_gia = True
		sau.insert(ignore_permissions=True)

		self.assertRaisesRegex(frappe.ValidationError, "chồng khoảng ngày", self.gui)
		self.assertEqual(frappe.db.get_value("Item Price", dau.name, "price_list"), self.cho)
		self.assertEqual(frappe.db.get_value("Item Price", sau.name, "price_list"), self.cho)

	def test_nothing_to_send_or_no_email(self):
		self.assertRaisesRegex(frappe.ValidationError, "không có giá", self.gui)
		self.gia(self.cho, self.item_a, 105000, add_days(self.d, 7))
		frappe.db.set_value("Price List", self.ban, "email_nhan_thong_bao", "")
		self.assertRaisesRegex(frappe.ValidationError, "Email nhận", self.gui)

	def test_t7_recording_the_customer_confirmation(self):
		moi = self.gia(self.cho, self.item_a, 105000, add_days(self.d, 7))
		self.gui()
		moi.reload()

		moi.ngay_xac_nhan = self.d
		self.as_user(self.nhan_vien, moi.save, ignore_permissions=True)
		self.assertEqual(moi.trang_thai_thong_bao, DA_XAC_NHAN)

		moi.ngay_xac_nhan = None
		moi.save(ignore_permissions=True)
		self.assertEqual(moi.trang_thai_thong_bao, DA_GUI)

	def test_sent_price_cannot_be_edited_afterwards(self):
		moi = self.gia(self.cho, self.item_a, 105000, add_days(self.d, 7))
		self.gui()
		moi.reload()
		moi.price_list_rate = 106000

		self.assertRaisesRegex(frappe.ValidationError, "Không sửa được", moi.save, ignore_permissions=True)

	def test_t1b_sales_order_takes_the_price_by_its_date(self):
		from erpnext.stock.get_item_details import get_price_list_rate_for

		self.gia(self.cho, self.item_a, 110000, add_days(self.d, 7))
		self.gui()

		def gia_ngay(n):
			return get_price_list_rate_for(
				frappe._dict(
					price_list=self.ban,
					uom="_KG Cái",
					transaction_date=add_days(self.d, n),
					customer=self.khach,
					qty=1,
					conversion_factor=1,
				),
				self.item_a,
			)

		self.assertEqual((gia_ngay(6), gia_ngay(7)), (101000, 110000))


class TestDangTrongThoiHanBaoGia(BaoTruocCase):
	"""2.6 (T9)"""

	def setUp(self):
		super().setUp()
		from erpnext.selling.kiem_gia.kiem_chung_tu import DANG_CHO

		self.DANG_CHO = DANG_CHO
		# Giá mua tăng: giá đề xuất 111.100, Himedic vẫn 101.000 tới khi báo xong.
		self.gia_hd(self.item_a, 110000, valid_from=self.d)

	def test_without_a_new_price_the_row_is_a_mismatch(self):
		self.assertEqual(self.so([self.row(self.item_a, 101000)]).items[0].trang_thai_gia, "Thấp hơn")

	def test_t9_pending_new_price_means_within_the_notice_period(self):
		self.gia(self.cho, self.item_a, 111100, self.d)

		d = self.so([self.row(self.item_a, 101000)]).items[0]

		self.assertEqual(d.trang_thai_gia, self.DANG_CHO)
		self.assertEqual((d.chenh_lech_gia, d.khac_bang_gia), (-10100, 0))
		self.assertIn("chờ gửi", d.ghi_chu_gia)

	def test_sent_but_not_yet_effective_price_also_counts(self):
		self.gia(self.cho, self.item_a, 111100, add_days(self.d, 7))
		self.as_user(self.giam_doc, gui_thong_bao_doi_gia, self.ban)

		d = self.so([self.row(self.item_a, 101000)]).items[0]

		self.assertEqual(d.trang_thai_gia, self.DANG_CHO)
		self.assertIn("đã báo", d.ghi_chu_gia)

	def test_within_the_notice_period_needs_no_reason_nor_acceptance(self):
		self.gia(self.cho, self.item_a, 111100, self.d)
		so = self.so([self.row(self.item_a, 101000)])

		so.submit()

		self.assertEqual(so.docstatus, 1)

	def test_q7_selling_the_new_price_early_needs_acceptance(self):
		self.gia(self.cho, self.item_a, 111100, self.d)
		so = self.so([self.row(self.item_a, 111100)])
		d = so.items[0]

		self.assertEqual((d.trang_thai_gia, d.khac_bang_gia, d.cho_chap_thuan), ("Khớp", 1, 1))
		self.assertRaisesRegex(frappe.ValidationError, "chấp thuận", so.submit)

	def test_q7_any_other_price_is_a_normal_mismatch(self):
		self.gia(self.cho, self.item_a, 111100, self.d)
		so = self.so([self.row(self.item_a, 105000)])
		d = so.items[0]

		self.assertEqual((d.trang_thai_gia, d.khac_bang_gia), ("Thấp hơn", 1))
		self.assertIn("vẫn tính là lệch", d.ghi_chu_gia)
		self.assertRaisesRegex(frappe.ValidationError, "Lý do lệch giá", so.submit)


class TestNhacViec(BaoTruocCase):
	"""2.7 (T11): điểm nhắc NTF-14, NTF-15 của Supply Notification."""

	def setUp(self):
		# Đăng ký trước super().setUp(): chạy SAU rollback, để cache không giữ "enabled" của test.
		self.addCleanup(
			frappe.clear_document_cache, "Supply Notification Settings", "Supply Notification Settings"
		)
		super().setUp()
		for code in ("NTF-14", "NTF-15"):
			if not frappe.db.exists("Supply Notification Point", code):
				self.skipTest(f"Chưa có điểm {code} (chạy migrate để gieo điểm mặc định)")
		frappe.db.set_single_value("Supply Notification Settings", "enabled", 1)
		frappe.clear_document_cache("Supply Notification Settings", "Supply Notification Settings")
		self.moi = self.gia(self.cho, self.item_a, 105000, add_days(self.d, 7))
		self.as_user(self.giam_doc, gui_thong_bao_doi_gia, self.ban)

	def diem(self, code):
		# Site test có thể chưa có tài khoản email gửi đi: chỉ kiểm kênh trong hệ thống.
		point = frappe.get_doc("Supply Notification Point", code)
		point.send_email = 0
		point.send_inapp = 1
		return point

	def nhac(self, code, today):
		from erpnext.supply_notification.reminders import run_point

		run_point(self.diem(code), today)
		return frappe.get_all(
			"Supply Notification Dispatch Log",
			filters={"point": code, "reference_name": self.moi.name},
			fields=["recipients", "status"],
		)

	def test_t11_two_days_after_sending_without_confirmation_reminds_the_sender(self):
		logs = self.nhac("NTF-14", add_days(self.d, 2))

		self.assertEqual(len(logs), 1)
		self.assertIn(self.giam_doc, logs[0].recipients)

	def test_no_reminder_once_the_customer_has_confirmed(self):
		self.moi.reload()
		self.moi.ngay_xac_nhan = self.d
		self.moi.save(ignore_permissions=True)

		self.assertFalse(self.nhac("NTF-14", add_days(self.d, 2)))

	def test_the_day_before_the_new_price_applies(self):
		logs = self.nhac("NTF-15", add_days(self.d, 6))

		self.assertEqual(len(logs), 1)
		self.assertIn(self.giam_doc, logs[0].recipients)

	def test_pending_drafts_do_not_trigger_reminders(self):
		nhap = self.gia(self.cho, self.item_a, 106000, add_days(self.d, 1))
		from erpnext.supply_notification.reminders import run_point

		run_point(self.diem("NTF-15"), self.d)

		self.assertFalse(frappe.db.exists("Supply Notification Dispatch Log", {"reference_name": nhap.name}))


class TestBaoCaoBaoGap(BaoTruocCase):
	"""2.8 (T12): báo cáo Thong Bao Doi Gia Bao Gap."""

	def rows(self, **filters):
		from erpnext.selling.report.thong_bao_doi_gia_bao_gap.thong_bao_doi_gia_bao_gap import execute

		return {r.name: r for r in execute({"price_list": self.ban, **filters})[1]}

	def test_t12_short_notice_rows_with_missing_days_and_orders_sold(self):
		gap = self.gia(self.cho, self.item_a, 105000, add_days(self.d, 3))
		du = self.gia(self.cho, self.item(1000), 1010, add_days(self.d, 7))
		self.as_user(self.giam_doc, gui_thong_bao_doi_gia, self.ban)
		row = {
			**self.row(self.item_a, 105000),
			"delivery_date": add_days(self.d, 10),
			# R05: giá bảng giá (105.000 đã báo) khác giá đề xuất theo hệ số (101.000).
			"so_van_ban_gia": "VB-01",
			"nguoi_dai_dien_kh": "Ông A",
			"ngay_chap_thuan_gia": self.d,
		}
		frappe.get_doc(
			{
				"doctype": "Sales Order",
				"company": self.company,
				"customer": self.khach,
				"transaction_date": add_days(self.d, 3),
				"delivery_date": add_days(self.d, 10),
				"selling_price_list": self.ban,
				"currency": self.currency,
				"ignore_pricing_rule": 1,
				"items": [row],
				"ly_do_lech_gia": "Bán theo giá mới đã báo",  # R04: cao hơn giá đề xuất
			}
		).insert(ignore_permissions=True).submit()

		rows = self.rows(chi_bao_gap=1)

		self.assertIn(gap.name, rows)
		self.assertNotIn(du.name, rows)  # đủ 7 ngày: chỉ hiện khi bỏ lọc báo gấp
		self.assertEqual((rows[gap.name].thieu, rows[gap.name].so_don), (4, 1))
		self.assertIn(du.name, self.rows(chi_bao_gap=0))
		# Bỏ tích trên giao diện: Frappe không gửi bộ lọc Check bằng 0.
		self.assertIn(du.name, self.rows())

	def test_confirmed_rows_can_be_hidden(self):
		gap = self.gia(self.cho, self.item_a, 105000, add_days(self.d, 3))
		self.as_user(self.giam_doc, gui_thong_bao_doi_gia, self.ban)
		gap.reload()
		gap.ngay_xac_nhan = self.d
		gap.save(ignore_permissions=True)

		self.assertEqual(self.rows()[gap.name].trang_thai_thong_bao, "Đã xác nhận")
		self.assertNotIn(gap.name, self.rows(chua_xac_nhan=1))
