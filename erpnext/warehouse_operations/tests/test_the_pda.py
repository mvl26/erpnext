"""Thẻ PDA: cấp, thu hồi, và đăng nhập bằng thẻ (spec 2026-09-23 §5).

NGƯỜI DÙNG THỬ KHÔNG XOÁ ĐƯỢC BẰNG ROLLBACK: `User.insert()` tự `commit()`
bên trong (xem ghi chú Frappe v15 của dự án), nên helper dưới đây dựng MỘT
tài khoản cố định rồi dùng lại — không tạo tài khoản mới mỗi lần chạy.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

DIEM_TEST = "test_the_pda"
NGUOI_KHO = "9p-thukho@miyano.test"
NGUOI_NGOAI = "9p-ngoaikho@miyano.test"


def _nguoi(email: str, vai_tro: list[str]) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"send_welcome_email": 0,
				"enabled": 1,
			}
		).insert(ignore_permissions=True)
	u = frappe.get_doc("User", email)
	u.enabled = 1
	co = {r.role for r in u.roles}
	for r in vai_tro:
		if r not in co:
			u.append("roles", {"role": r})
	u.save(ignore_permissions=True)
	return email


class TestCapThe(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		_nguoi(NGUOI_KHO, ["Stock User"])
		_nguoi(NGUOI_NGOAI, ["Accounts User"])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point=DIEM_TEST)

	def test_cap_the_tra_ma_12_ky_tu_dung_bang_chu(self):
		from erpnext.warehouse_operations.vitri.the_pda import BANG_CHU, DO_DAI_MA, cap_the

		kq = cap_the(NGUOI_KHO)
		self.assertEqual(len(kq["ma"]), DO_DAI_MA)
		self.assertTrue(set(kq["ma"]) <= set(BANG_CHU), kq["ma"])
		self.assertEqual(kq["the"], NGUOI_KHO)

	def test_chi_luu_ban_bam_khong_luu_ma_goc(self):
		from erpnext.warehouse_operations.vitri.the_pda import bam, cap_the

		ma = cap_the(NGUOI_KHO)["ma"]
		doc = frappe.get_doc("PDA Badge", NGUOI_KHO)
		self.assertEqual(doc.ma_bam, bam(doc.muoi, ma))
		self.assertNotIn(ma, frappe.as_json(doc.as_dict()))

	def test_cap_lai_thi_the_cu_chet(self):
		from erpnext.warehouse_operations.vitri.the_pda import bam, cap_the

		ma_cu = cap_the(NGUOI_KHO)["ma"]
		muoi_cu = frappe.db.get_value("PDA Badge", NGUOI_KHO, "muoi")
		ma_moi = cap_the(NGUOI_KHO)["ma"]
		muoi_moi = frappe.db.get_value("PDA Badge", NGUOI_KHO, "muoi")
		self.assertNotEqual(ma_cu, ma_moi)
		self.assertNotEqual(muoi_cu, muoi_moi, "cấp lại phải sinh MUỐI mới, không giữ muối cũ")
		self.assertEqual(
			frappe.db.get_value("PDA Badge", NGUOI_KHO, "ma_bam"), bam(muoi_moi, ma_moi)
		)

	def test_thu_hoi_tat_hieu_luc(self):
		from erpnext.warehouse_operations.vitri.the_pda import cap_the, thu_hoi

		cap_the(NGUOI_KHO)
		thu_hoi(NGUOI_KHO)
		self.assertEqual(frappe.db.get_value("PDA Badge", NGUOI_KHO, "con_hieu_luc"), 0)

	def test_nguoi_khong_co_vai_tro_kho_bi_chan(self):
		from erpnext.warehouse_operations.vitri.the_pda import cap_the

		with self.assertRaisesRegex(frappe.ValidationError, "vai trò kho"):
			cap_the(NGUOI_NGOAI)

	def test_tai_khoan_bi_khoa_bi_chan(self):
		from erpnext.warehouse_operations.vitri.the_pda import cap_the

		frappe.db.set_value("User", NGUOI_KHO, "enabled", 0)
		with self.assertRaisesRegex(frappe.ValidationError, "đang bị khoá"):
			cap_the(NGUOI_KHO)

	def test_thu_kho_khong_tu_cap_the_cho_minh(self):
		from erpnext.warehouse_operations.vitri.the_pda import cap_the

		frappe.set_user(NGUOI_KHO)
		with self.assertRaises(frappe.PermissionError):
			cap_the(NGUOI_KHO)

	def test_thu_hoi_tai_khoan_da_bi_khoa(self):
		from erpnext.warehouse_operations.vitri.the_pda import cap_the, thu_hoi

		cap_the(NGUOI_KHO)
		frappe.db.set_value("User", NGUOI_KHO, "enabled", 0)
		kq = thu_hoi(NGUOI_KHO)
		self.assertEqual(kq["con_hieu_luc"], 0)
		self.assertEqual(frappe.db.get_value("PDA Badge", NGUOI_KHO, "con_hieu_luc"), 0)

	def test_thu_hoi_nguoi_da_mat_vai_tro_kho(self):
		from erpnext.warehouse_operations.vitri.the_pda import cap_the, thu_hoi

		cap_the(NGUOI_KHO)
		u = frappe.get_doc("User", NGUOI_KHO)
		u.roles = []
		u.save(ignore_permissions=True)
		kq = thu_hoi(NGUOI_KHO)
		self.assertEqual(kq["con_hieu_luc"], 0)
		self.assertEqual(frappe.db.get_value("PDA Badge", NGUOI_KHO, "con_hieu_luc"), 0)

	def test_thu_hoi_cho_nguoi_chua_tung_co_the(self):
		from erpnext.warehouse_operations.vitri.the_pda import thu_hoi

		with self.assertRaisesRegex(frappe.ValidationError, "chưa từng được cấp"):
			thu_hoi(NGUOI_NGOAI)


def _gia_lap_request() -> None:
	"""Dựng lại bối cảnh HTTP request mà `frappe.app.init_request` dựng lúc có request thật.

	`dang_nhap_bang_the` gọi `frappe.local.login_manager.login_as(...)`, và
	`LoginManager.__init__` (`apps/frappe/frappe/auth.py:114`) đọc `frappe.local.request.path`.
	Đường chạy thật (súng quét PDA gọi qua HTTP) luôn đi qua `frappe.app.init_request`, nơi dựng
	sẵn `frappe.local.request`, `frappe.local.request_ip`, `frappe.local.cookie_manager` rồi mới
	tới `frappe.local.login_manager` (xem `HTTPRequest.__init__`, cùng file, dòng ~33-51). Chạy
	`bench run-tests` thì không có request nào cả nên phải tự dựng đủ khung đó — thiếu một bước
	là `AttributeError` ngay khi tạo `LoginManager()`. Cách dựng dưới đây giống hệt cách chính
	các bài test của Frappe làm (`frappe/tests/test_client.py:127`,
	`frappe/tests/test_api.py:114`): dùng `frappe.utils.set_request` để có một `werkzeug.Request`
	thật (có `.path`, `.method`, `.cookies`, `.scheme`...) rồi mới tạo `CookieManager` +
	`LoginManager`. KHÔNG được sửa `dang_nhap_bang_the` hay `LoginManager` để né việc này — đó
	là cửa sau chỉ mở ra vì thiếu request, và đường chạy thật không bao giờ thiếu request.

	Còn đặt cả `frappe.local.form_dict.cmd`: `@frappe.rate_limit` (thật ra `frappe.rate_limiter.
	rate_limit`) khoá bộ đếm theo `f"rl:{frappe.form_dict.cmd}:{ip}"`. Trên đường chạy thật,
	`frappe.api.v1` gán `form_dict.cmd = <method>` TRƯỚC khi gọi hàm whitelist (`frappe/api/
	v1.py:39`) — route `/api/method/<dotted>` luôn đi qua đó. Gọi thẳng hàm Python trong test thì
	không ai gán `cmd` cả, mọi lần quét (kể cả của các bài test KHÁC dùng `@rate_limit` không
	`key=`) sẽ dùng chung một khoá `"rl:None:127.0.0.1"` trong Redis thật (Redis không theo giao
	dịch DB, `rollback` không dọn được) — vài lần chạy lại bộ test trong 60 giây là dính giới hạn
	oan, không phải vì bài test này gọi sai. Gán đúng `cmd` là mô phỏng ĐÚNG đường thật, không
	phải né giới hạn.
	"""
	from frappe.auth import CookieManager, LoginManager
	from frappe.utils import set_request

	cmd = "erpnext.warehouse_operations.vitri.the_pda.dang_nhap_bang_the"
	set_request(method="POST", path=f"/api/method/{cmd}")
	frappe.local.request_ip = "127.0.0.1"
	frappe.local.cookie_manager = CookieManager()
	frappe.local.login_manager = LoginManager()
	frappe.local.form_dict.cmd = cmd

	# Bộ đếm của `@rate_limit` sống trong Redis thật, NGOÀI giao dịch DB — `frappe.db.rollback()`
	# không dọn được nó. Chạy LẠI module test này (hay cả suite) nhiều lần liên tiếp trong vòng
	# 60 giây sẽ cộng dồn bộ đếm từ lần chạy trước sang lần này và có thể vượt hạn mức dù không
	# bài nào gọi sai — tự kiểm chứng bằng `redis-cli -p <cổng redis_cache> --scan --pattern
	# "*rl:*dang_nhap_bang_the*"`. Không bài test nào trong lớp này kiểm CHÍNH hành vi giới hạn
	# tần suất, nên xoá khoá này trước mỗi lần giả lập request là an toàn: chỉ đảm bảo phần đếm
	# không rò từ lần `bench run-tests` trước sang lần này, không xoá bớt phạm vi kiểm tra nào.
	frappe.cache.delete_value(f"rl:{cmd}:127.0.0.1")


class TestDangNhapBangThe(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint(DIEM_TEST)
		_nguoi(NGUOI_KHO, ["Stock User"])
		# Mốc giờ để `tearDown` biết dòng `Error Log` nào là do CHÍNH bài test này tạo ra (xem
		# lý do cần mốc này ở `tearDown`, đoạn về bảng MyISAM).
		self._batdau_test = frappe.utils.now()
		# Ghi nhớ ba trường mà một lần đăng nhập THẬT sẽ ghi đè + COMMIT ngay trong
		# `Session.start()` (`apps/frappe/frappe/sessions.py:280-291`), để `tearDown` khôi phục
		# lại đúng giá trị này khi savepoint không cứu được (xem lý do đầy đủ ở `tearDown`).
		# Đọc SAU dòng `_nguoi()` ở trên, không phải trước: `last_login`/`last_ip` là fieldtype
		# "Read Only", và `.save()` bất kỳ trên User (kể cả `_nguoi()` ở trên, chẳng liên quan
		# gì đăng nhập) đã tự quy đổi `None` thành chuỗi rỗng `""` cho hai trường này
		# (`BaseDocument.get_valid_dict()`, `frappe/model/base_document.py:406-407`) — nên đừng
		# ngạc nhiên nếu giá trị ghi nhớ/khôi phục ở đây là `""` chứ không phải `None`; đó là
		# hành vi có sẵn của `_nguoi()`, không phải do đăng nhập bằng thẻ gây ra.
		self._nguoi_kho_truoc_test = frappe.db.get_value(
			"User", NGUOI_KHO, ["last_login", "last_ip", "last_active"], as_dict=True
		)

	def tearDown(self):
		frappe.set_user("Administrator")
		try:
			frappe.db.rollback(save_point=DIEM_TEST)
		except frappe.db.OperationalError:
			# Quét ĐÚNG mã thì `dang_nhap_bang_the` gọi `login_manager.login_as(...)`, và bên
			# trong đó `Session.start()` LUÔN `frappe.db.commit()` một khi đăng nhập không phải
			# Guest (`apps/frappe/frappe/sessions.py:296`) — để phiên sống sót ngay cả khi phần
			# còn lại của request sau đó lỗi. COMMIT đóng hẳn giao dịch hiện tại, xoá sạch mọi
			# savepoint đã đặt trong đó — kể cả `DIEM_TEST` đặt ở `setUp` — nên `rollback` tới
			# savepoint đó ném `SAVEPOINT ... does not exist`. Đây là hành vi thật của framework
			# (giống bẫy "DDL tự commit" đã gặp ở test khác), không phải lỗi ở test này hay ở
			# `dang_nhap_bang_the` — KHÔNG được bỏ dòng `login_as` để né commit, vì đó chính là
			# cách đăng nhập thật hoạt động.
			#
			# Nhưng erptest.local là CSDL DÙNG CHUNG cho nhiều agent thi công tuần tự — cái gì
			# đã COMMIT không được để lại làm rác thật ngoài savepoint, dù "vô hại về logic".
			# Có BA thứ commit thật, không chỉ PDA Badge/Sessions:
			#   1. `frappe.db.rollback()` thường chỉ dọn được phần SAU commit đó (dòng
			#      `set_value` cập nhật `lan_dung_cuoi`/`thiet_bi_cuoi` ở cuối
			#      `dang_nhap_bang_the`) — phải dọn TAY phần đã commit trước đó.
			#   2. `Session.start()` (dòng 280-291, CÙNG commit ở dòng 296) đã ghi đè
			#      `User.last_login`, `last_ip`, `last_active` của NGUOI_KHO — ba trường này
			#      không nằm trong savepoint, phải khôi phục lại đúng giá trị đã ghi nhớ ở
			#      `setUp`.
			#   3. `clear_sessions(..., force=True)` ngay dưới đây tự nó gọi `delete_session()`
			#      → `add_authentication_log()` chèn MỘT dòng `Activity Log` ("Force Logged out
			#      by the user") rồi tự `frappe.db.commit()` (`frappe/sessions.py:99`) — dòng đó
			#      cũng là rác thật, phải xoá sau khi gọi.
			from frappe.sessions import clear_sessions

			frappe.db.rollback()
			if frappe.db.exists("PDA Badge", NGUOI_KHO):
				frappe.delete_doc("PDA Badge", NGUOI_KHO, ignore_permissions=True, force=True)
			clear_sessions(user=NGUOI_KHO, force=True)
			if self._nguoi_kho_truoc_test:
				frappe.db.set_value(
					"User", NGUOI_KHO, self._nguoi_kho_truoc_test, update_modified=False
				)
			frappe.db.delete("Activity Log", {"user": NGUOI_KHO})
			frappe.db.commit()

		# `dang_nhap_bang_the` gọi `frappe.log_error(...)` ở MỌI ca quét hỏng (mã sai/thẻ thu
		# hồi/tài khoản khoá/mất vai trò/vượt tần suất) — 5 bài trong lớp này CỐ Ý quét hỏng, và
		# `test_vuot_nguong_tan_suat_bi_chan` tự nó gọi tới 10 lần. `tabError Log` là bảng
		# **MyISAM**, không phải InnoDB (`SHOW TABLE STATUS LIKE 'tabError Log'` xác nhận
		# `Engine: MyISAM`) — MyISAM KHÔNG hỗ trợ giao dịch/savepoint, nên MỌI INSERT vào đó
		# COMMIT NGAY LẬP TỨC, bất kể `frappe.db.rollback()` hay `try/except` ở trên chạy nhánh
		# nào. Đây KHÔNG phải hệ quả của việc đăng nhập thật commit (khác hẳn mục 1-3 ở trên) —
		# nó xảy ra ở CẢ những bài không bao giờ đăng nhập, nên phải dọn ở đây, VÔ ĐIỀU KIỆN,
		# ngoài `try/except`. Lọc theo mốc giờ `self._batdau_test` (đặt ở `setUp`) để chỉ xoá
		# đúng dòng do CHÍNH bài test này tạo ra, không đụng vào Error Log của người khác đang
		# thao tác thật trên cùng site dùng chung.
		frappe.db.delete(
			"Error Log",
			{"method": "vi_tri_kho: the_pda sai ma", "creation": [">=", self._batdau_test]},
		)
		frappe.db.commit()

	def _ma(self):
		from erpnext.warehouse_operations.vitri.the_pda import cap_the

		return cap_the(NGUOI_KHO)["ma"]

	def test_quet_dung_thi_dang_nhap_dung_nguoi(self):
		from erpnext.warehouse_operations.vitri.the_pda import dang_nhap_bang_the

		ma = self._ma()
		frappe.set_user("Guest")
		_gia_lap_request()
		kq = dang_nhap_bang_the(ma)
		self.assertEqual(kq["di_toi"], "/app/pda-home")
		self.assertEqual(frappe.session.user, NGUOI_KHO)

	def test_phien_het_sau_12_tieng(self):
		from datetime import datetime, timedelta, timezone

		from erpnext.warehouse_operations.vitri.the_pda import GIO_MOT_CA, dang_nhap_bang_the

		ma = self._ma()
		frappe.set_user("Guest")
		_gia_lap_request()
		dang_nhap_bang_the(ma)
		het = datetime.fromisoformat(frappe.local.session_obj.data.data.get("session_end"))
		cach = het - datetime.now(timezone.utc)
		self.assertAlmostEqual(cach.total_seconds(), GIO_MOT_CA * 3600, delta=120)

	def test_ma_sai_bi_chan_bang_mot_cau_bao(self):
		from erpnext.warehouse_operations.vitri.the_pda import dang_nhap_bang_the

		self._ma()
		frappe.set_user("Guest")
		_gia_lap_request()
		with self.assertRaisesRegex(frappe.AuthenticationError, "Thẻ không dùng được"):
			dang_nhap_bang_the("ZZZZZZZZZZZZ")
		self.assertEqual(frappe.session.user, "Guest")

	def test_the_da_thu_hoi_bi_chan(self):
		from erpnext.warehouse_operations.vitri.the_pda import dang_nhap_bang_the, thu_hoi

		ma = self._ma()
		thu_hoi(NGUOI_KHO)
		frappe.set_user("Guest")
		_gia_lap_request()
		with self.assertRaisesRegex(frappe.AuthenticationError, "Thẻ không dùng được"):
			dang_nhap_bang_the(ma)

	def test_chu_the_bi_khoa_thi_bi_chan(self):
		from erpnext.warehouse_operations.vitri.the_pda import dang_nhap_bang_the

		ma = self._ma()
		frappe.db.set_value("User", NGUOI_KHO, "enabled", 0)
		frappe.set_user("Guest")
		_gia_lap_request()
		with self.assertRaisesRegex(frappe.AuthenticationError, "Thẻ không dùng được"):
			dang_nhap_bang_the(ma)

	def test_mat_vai_tro_kho_thi_the_cu_het_tac_dung(self):
		from erpnext.warehouse_operations.vitri.the_pda import dang_nhap_bang_the

		ma = self._ma()
		u = frappe.get_doc("User", NGUOI_KHO)
		u.roles = [r for r in u.roles if r.role not in ("Stock User", "Stock Manager")]
		u.save(ignore_permissions=True)
		frappe.set_user("Guest")
		_gia_lap_request()
		with self.assertRaisesRegex(frappe.AuthenticationError, "Thẻ không dùng được"):
			dang_nhap_bang_the(ma)

	def test_ghi_lan_quet_cuoi(self):
		from erpnext.warehouse_operations.vitri.the_pda import dang_nhap_bang_the

		ma = self._ma()
		frappe.set_user("Guest")
		_gia_lap_request()
		dang_nhap_bang_the(ma)
		frappe.set_user("Administrator")
		self.assertIsNotNone(frappe.db.get_value("PDA Badge", NGUOI_KHO, "lan_dung_cuoi"))

	def test_thu_hoi_dong_phien_dang_mo(self):
		"""Mục 5 đợt sửa cuối: `thu_hoi` đã gọi `clear_sessions(force=True)` từ trước, nhưng
		chưa từng có bài nào canh PHIÊN thật sự biến mất khỏi `tabSessions` — các bài cũ chỉ
		kiểm cờ `con_hieu_luc`. Dùng `_gia_lap_request()` để đăng nhập thật bằng thẻ trước."""
		from erpnext.warehouse_operations.vitri.the_pda import dang_nhap_bang_the, thu_hoi

		ma = self._ma()
		frappe.set_user("Guest")
		_gia_lap_request()
		dang_nhap_bang_the(ma)
		self.assertGreater(
			frappe.db.count("Sessions", {"user": NGUOI_KHO}),
			0,
			"đăng nhập bằng thẻ phải để lại một dòng trong tabSessions",
		)
		frappe.set_user("Administrator")
		thu_hoi(NGUOI_KHO)
		self.assertEqual(
			frappe.db.count("Sessions", {"user": NGUOI_KHO}),
			0,
			"thu hồi thẻ phải xoá sạch phiên đang mở của chủ thẻ",
		)

	def test_cap_lai_the_dong_phien_dang_mo_bang_the_cu(self):
		"""Mục 4 đợt sửa cuối: phản xạ tự nhiên khi MẤT THẺ là bấm 'Cấp thẻ & in' NGAY, không
		phải bấm 'Thu hồi' trước — nên `cap_the` cũng phải đóng phiên cũ, không chỉ `thu_hoi`.
		Trước bản sửa này, phiên mở bằng thẻ CŨ sống tới hết 12 tiếng dù thẻ đã đổi."""
		from erpnext.warehouse_operations.vitri.the_pda import cap_the, dang_nhap_bang_the

		ma_1 = self._ma()
		frappe.set_user("Guest")
		_gia_lap_request()
		dang_nhap_bang_the(ma_1)
		self.assertGreater(
			frappe.db.count("Sessions", {"user": NGUOI_KHO}),
			0,
			"đăng nhập bằng thẻ lần 1 phải để lại một dòng trong tabSessions",
		)
		# Đổi sang Administrator TRƯỚC khi cấp lại: `frappe.set_user` gán `session.sid` thành
		# chính chuỗi tên tài khoản (`frappe/__init__.py::set_user`), khác hẳn sid thật (một
		# chuỗi ngẫu nhiên) mà `login_as` vừa sinh cho NGUOI_KHO — nên `keep_current=True`
		# trong `cap_the` không thể vô tình "chừa lại" đúng phiên PDA vừa tạo ở trên; nó chỉ
		# chừa phiên của CHÍNH người gọi `cap_the` (ở đây là Administrator, không tồn tại
		# trong tabSessions), đúng ca "cấp thẻ cho NGƯỜI KHÁC" mà chú thích trong `cap_the`
		# đã nói tới.
		frappe.set_user("Administrator")
		cap_the(NGUOI_KHO)
		self.assertEqual(
			frappe.db.count("Sessions", {"user": NGUOI_KHO}),
			0,
			"cấp lại thẻ phải đóng phiên đang mở bằng thẻ CŨ",
		)

	def test_vuot_nguong_tan_suat_bi_chan(self):
		"""Kiểm THẬT lớp phòng thủ chính của endpoint cho khách này: chặn tần suất.

		Sáu bài trên đều gọi `_gia_lap_request()` trước MỖI lần quét, mà hàm đó tự xoá khoá
		Redis của `@rate_limit` để mô phỏng đúng một request độc lập — nên không bài nào trong
		số đó từng thật sự chạm ngưỡng `limit=10, seconds=60`. Bài này CỐ Ý gọi
		`_gia_lap_request()` đúng MỘT lần (chỉ để có bối cảnh request + khoá Redis sạch ban
		đầu), rồi gọi thẳng `dang_nhap_bang_the` liên tiếp KHÔNG xoá khoá giữa các lần — đúng
		như súng quét thật gửi nhiều lần liên tiếp từ cùng một IP. Toàn bộ 11 lần đều dùng mã
		sai nên không lần nào chạm `login_as` (không Session nào được tạo, không có gì để
		COMMIT) — nhánh `except` dọn rác trong `tearDown` không bị kích hoạt, `tearDown` dọn
		sạch bằng savepoint như bình thường.
		"""
		from erpnext.warehouse_operations.vitri.the_pda import dang_nhap_bang_the

		cmd = "erpnext.warehouse_operations.vitri.the_pda.dang_nhap_bang_the"
		khoa = f"rl:{cmd}:127.0.0.1"
		frappe.set_user("Guest")
		_gia_lap_request()
		try:
			so_lan_ma_sai = 0
			lan_vuot_nguong = None
			for lan in range(1, 12):
				try:
					dang_nhap_bang_the("MA_SAI_KHONG_TON_TAI")
				except frappe.RateLimitExceededError:
					lan_vuot_nguong = lan
					break
				except frappe.AuthenticationError:
					so_lan_ma_sai += 1
			# Chốt ĐÚNG ranh giới `limit=10`, không chỉ "có ném gì đó": nếu khoá Redis bị rò từ
			# bài/lần chạy trước (đúng thứ lỗi cả task này đang chống), giới hạn sẽ nổ sớm hơn
			# lần gọi thứ 11 — `assertTrue` đơn thuần sẽ KHÔNG bắt được ca đó vì vẫn có ngoại lệ
			# nào đó được ném ra. Khẳng định đúng 10 lần đầu là mã sai bình thường, và chính lần
			# gọi thứ 11 mới vượt ngưỡng.
			self.assertEqual(so_lan_ma_sai, 10, "phải đúng 10 lần đầu là mã sai bình thường")
			self.assertEqual(lan_vuot_nguong, 11, "phải vượt ngưỡng đúng ở lần gọi thứ 11")
		finally:
			# Dọn khoá Redis của CHÍNH bài test này — không nằm trong giao dịch DB nên
			# `tearDown`/savepoint không đụng tới được, và nếu để lại thì bài chạy kế tiếp
			# (trong cùng lần `bench run-tests` này hay lần sau, trong vòng 60 giây) có thể ăn
			# `RateLimitExceededError` oan trên máy dev thật.
			frappe.cache.delete_value(khoa)
