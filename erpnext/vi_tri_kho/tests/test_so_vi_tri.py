"""Engine ghi sổ vị trí.

Sổ CHỈ GHI THÊM. Không sửa dòng, không xoá dòng — kể cả khi huỷ chứng từ
(huỷ ghi bút toán đảo, xem Task 9). `Location Balance` chỉ là bộ đệm, dựng
lại được từ sổ bất cứ lúc nào; đó là đường thoát khi nghi ngờ số liệu, nên
`dung_lai_ton_vi_tri()` phải có test riêng chứ không được coi là hàm phụ.

Vòng sửa 1: thêm test cho 4 việc điều phối yêu cầu —
(1) unique index (o, vat_tu, so_lo) trên Location Balance ở tầng DB,
(2) so_lo lưu chuỗi rỗng thay vì NULL,
(3) _cong_don_ton phải nguyên tử (không đọc-rồi-ghi) khi ghi đồng thời,
(4) bỏ ignore_links khỏi đường ghi Location Ledger Entry — sổ phải từ chối
    chứng từ/mã không có thật thay vì âm thầm chấp nhận.
Vì (4), `_ghi()` giờ dùng chung_tu thật (trỏ tới chính Storage Location `o`
vừa tạo) và tạo Batch thật cho so_lo thay vì chuỗi giả.
"""

import threading

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.vi_tri_kho.vitri import so

KHO = "Kho Miyano - MYN"


def _o(ma_o):
	if not frappe.db.exists("Storage Location", ma_o):
		frappe.get_doc({
			"doctype": "Storage Location", "ma_o": ma_o, "kho": KHO,
		}).insert(ignore_permissions=True)
	return ma_o


def _tao_item(ma, co_lo=False):
	if not frappe.db.exists("Item", ma):
		frappe.get_doc({
			"doctype": "Item", "item_code": ma, "item_name": ma,
			"item_group": "All Item Groups", "stock_uom": "Nos", "is_stock_item": 1,
			"has_batch_no": 1 if co_lo else 0,
		}).insert(ignore_permissions=True)
	elif co_lo and not frappe.db.get_value("Item", ma, "has_batch_no"):
		frappe.db.set_value("Item", ma, "has_batch_no", 1)
	return ma


def _tao_lo(vat_tu, ma_lo):
	"""Batch thật cho `so_lo`. Bắt buộc từ khi bỏ `ignore_links` khỏi
	`ghi_dong_so` (Việc 4 vòng sửa 1): `so_lo` là Link -> Batch, sổ vị trí
	giờ từ chối số lô không có bản ghi Batch thật đứng sau."""
	_tao_item(vat_tu, co_lo=True)
	if not frappe.db.exists("Batch", ma_lo):
		frappe.get_doc({
			"doctype": "Batch", "batch_id": ma_lo, "item": vat_tu,
		}).insert(ignore_permissions=True)
	return ma_lo


def _ghi(o, vat_tu, so_lo, so_luong, chung_tu=None):
	if so_lo:
		_tao_lo(vat_tu, so_lo)
	if chung_tu is None:
		# Trỏ tới chính bản ghi Storage Location `o` — bản ghi CÓ THẬT, luôn
		# sẵn sàng vì `o` đã được `_o()` tạo trước khi gọi `_ghi()`. Thay cho
		# "TEST-CT-1" giả trước đây: từ khi bỏ ignore_links (Việc 4), sổ
		# kiểm tra chứng từ có thật.
		chung_tu = o
	return so.ghi_dong_so(
		o=o, kho=KHO, vat_tu=vat_tu, so_lo=so_lo, so_luong=so_luong,
		chung_tu_type="Storage Location", chung_tu=chung_tu, chung_tu_row="row-1",
		sle=None, ngay="2026-09-09", thoi_diem="2026-09-09 08:00:00",
		company="Miyano Việt Nam",
	)


class _TuDonSauMoiBai(FrappeTestCase):
	"""Cô lập từng bài test bằng savepoint DB.

	`FrappeTestCase` chỉ rollback theo LỚP (`addClassCleanup`), không theo
	từng bài (`setUp`/`tearDown`). `tong_ton_vi_tri()` cộng dồn trên TOÀN kho
	cho một (mặt hàng, lô) — không giới hạn theo `o` của riêng bài test — nên
	nếu hai bài trong cùng lớp dùng chung mặt hàng/lô mà không cô lập, bài sau
	sẽ cộng dồn cả dữ liệu bài trước và assertion sai lệch dù engine đúng.
	Dùng savepoint để mỗi bài bắt đầu từ đúng trạng thái `setUpClass`.
	"""

	def setUp(self):
		self._sp_so_vi_tri = f"sp_{self._testMethodName}"
		frappe.db.savepoint(self._sp_so_vi_tri)
		super().setUp()

	def tearDown(self):
		frappe.db.rollback(save_point=self._sp_so_vi_tri)
		super().tearDown()


class TestGhiSo(_TuDonSauMoiBai):
	def setUp(self):
		super().setUp()
		_tao_item("_Test Item VT")
		_tao_item("_Test Item Khong Lo")
		_tao_item("_Test Item VT2")

	def test_ghi_mot_dong_thi_ton_o_tang(self):
		o = _o("K19Z30010101")
		_ghi(o, "_Test Item VT", "LO-A", 10)
		self.assertEqual(so.ton_o(o, "_Test Item VT", "LO-A"), 10)

	def test_ghi_am_thi_ton_giam(self):
		o = _o("K19Z30010102")
		_ghi(o, "_Test Item VT", "LO-A", 10)
		_ghi(o, "_Test Item VT", "LO-A", -4)
		self.assertEqual(so.ton_o(o, "_Test Item VT", "LO-A"), 6)

	def test_hai_lo_khac_nhau_khong_gop_lam_mot(self):
		o = _o("K19Z30010103")
		_ghi(o, "_Test Item VT", "LO-A", 10)
		_ghi(o, "_Test Item VT", "LO-B", 5)
		self.assertEqual(so.ton_o(o, "_Test Item VT", "LO-A"), 10)
		self.assertEqual(so.ton_o(o, "_Test Item VT", "LO-B"), 5)
		self.assertEqual(so.tong_ton_vi_tri(KHO, "_Test Item VT", "LO-A"), 10)

	def test_hang_khong_lo_dung_so_lo_rong(self):
		o = _o("K19Z30010104")
		_ghi(o, "_Test Item Khong Lo", None, 7)
		self.assertEqual(so.ton_o(o, "_Test Item Khong Lo", None), 7)
		# tong_ton_vi_tri cũng phải chuẩn hoá so_lo=None giống ton_o — không
		# chỉ kiểm bằng cách đọc code, phải có assertion thật.
		self.assertEqual(so.tong_ton_vi_tri(KHO, "_Test Item Khong Lo", None), 7)

	def test_tong_ton_cong_qua_nhieu_o(self):
		a, b = _o("K19Z30010105"), _o("K19Z30010106")
		_ghi(a, "_Test Item VT2", "LO-C", 3)
		_ghi(b, "_Test Item VT2", "LO-C", 4)
		self.assertEqual(so.tong_ton_vi_tri(KHO, "_Test Item VT2", "LO-C"), 7)

	def test_tu_choi_chung_tu_khong_ton_tai(self):
		"""Việc 4: bỏ ignore_links khỏi đường ghi sổ. Trước đây `ghi_dong_so`
		âm thầm chấp nhận `chung_tu` không có thật — sổ vị trí là nguồn sự
		thật cho Task 5-10, không được hở như vậy."""
		o = _o("K19Z30010112")
		with self.assertRaises(frappe.LinkValidationError):
			so.ghi_dong_so(
				o=o, kho=KHO, vat_tu="_Test Item VT", so_lo=None, so_luong=1,
				chung_tu_type="Storage Location", chung_tu="KHONG-TON-TAI-XYZ",
				chung_tu_row="row-1", sle=None, ngay="2026-09-09",
				thoi_diem="2026-09-09 08:00:00", company="Miyano Việt Nam",
			)

	def test_so_lo_luu_chuoi_rong_khong_phai_null(self):
		"""Việc 2: so_lo của hàng không quản lý lô phải là chuỗi rỗng '',
		KHÔNG phải NULL, ở cả Location Ledger Entry lẫn Location Balance —
		đọc thẳng bằng SQL, không suy luận qua ifnull()."""
		o = _o("K19Z30010113")
		ten = _ghi(o, "_Test Item Khong Lo", None, 5)

		gia_tri_so_sql = frappe.db.sql(
			"select so_lo from `tabLocation Ledger Entry` where name=%s", (ten,)
		)[0][0]
		self.assertEqual(
			gia_tri_so_sql, "",
			"so_lo trong Location Ledger Entry phải là chuỗi rỗng, không phải NULL",
		)

		gia_tri_ton_sql = frappe.db.sql(
			"select so_lo from `tabLocation Balance` where o=%s and vat_tu=%s",
			(o, "_Test Item Khong Lo"),
		)[0][0]
		self.assertEqual(
			gia_tri_ton_sql, "",
			"so_lo trong Location Balance phải là chuỗi rỗng, không phải NULL",
		)

	def test_da_huy_duoc_ghi_dung_va_khong_can_tro_ton(self):
		"""`da_huy` là tham số cuối cùng trong hợp đồng chưa có bài nào đụng
		tới — Task 9 sẽ dùng nó cho bút toán đảo. Ghi với da_huy=1 phải ghi
		đúng cờ và vẫn cộng dồn tồn bình thường (bản thân ghi_dong_so không
		diễn giải ý nghĩa của da_huy, chỉ lưu lại — xem docstring module)."""
		o = _o("K19Z30010114")
		ten = so.ghi_dong_so(
			o=o, kho=KHO, vat_tu="_Test Item VT", so_lo=None, so_luong=-3,
			chung_tu_type="Storage Location", chung_tu=o, chung_tu_row="row-1",
			sle=None, ngay="2026-09-09", thoi_diem="2026-09-09 08:00:00",
			company="Miyano Việt Nam", da_huy=1,
		)
		self.assertEqual(frappe.db.get_value("Location Ledger Entry", ten, "da_huy"), 1)
		self.assertEqual(so.ton_o(o, "_Test Item VT", None), -3)


class TestSoChiGhiThem(_TuDonSauMoiBai):
	def setUp(self):
		super().setUp()
		_tao_item("_Test Item VT3")

	def test_ghi_khong_sua_dong_cu(self):
		o = _o("K19Z30010107")
		t1 = _ghi(o, "_Test Item VT3", "LO-D", 5)
		_ghi(o, "_Test Item VT3", "LO-D", -2)
		self.assertEqual(frappe.db.get_value("Location Ledger Entry", t1, "so_luong"), 5)
		self.assertEqual(
			frappe.db.count("Location Ledger Entry", {"o": o, "vat_tu": "_Test Item VT3"}), 2
		)


class TestDungLaiTon(_TuDonSauMoiBai):
	def setUp(self):
		super().setUp()
		_tao_item("_Test Item VT4")
		_tao_item("_Test Item VT5")

	def test_pha_bo_dem_roi_dung_lai_thi_dung(self):
		o = _o("K19Z30010108")
		_ghi(o, "_Test Item VT4", "LO-E", 12)
		_ghi(o, "_Test Item VT4", "LO-E", -5)

		# cố tình phá bộ đệm
		frappe.db.set_value(
			"Location Balance",
			{"o": o, "vat_tu": "_Test Item VT4", "so_lo": "LO-E"},
			"so_luong", 999,
		)
		self.assertEqual(so.ton_o(o, "_Test Item VT4", "LO-E"), 999)

		so_dong = so.dung_lai_ton_vi_tri(KHO)
		self.assertEqual(so.ton_o(o, "_Test Item VT4", "LO-E"), 7)
		# Hợp đồng: trả về SỐ DÒNG đã dựng, không phải None/True.
		self.assertIsInstance(so_dong, int)
		self.assertGreaterEqual(so_dong, 1)

	def test_dung_lai_khong_de_lai_dong_thua(self):
		o = _o("K19Z30010109")
		_ghi(o, "_Test Item VT5", "LO-F", 4)
		frappe.get_doc({
			"doctype": "Location Balance", "o": o, "kho": KHO,
			"vat_tu": "_Test Item VT5", "so_lo": "LO-MA", "so_luong": 100,
		}).insert(ignore_permissions=True)

		so.dung_lai_ton_vi_tri(KHO)
		self.assertFalse(
			frappe.db.exists("Location Balance", {"o": o, "so_lo": "LO-MA"}),
			"dòng tồn không có dấu vết trong sổ phải bị xoá khi dựng lại",
		)

	def test_dung_lai_khong_loc_kho_van_dung_va_tra_int(self):
		"""`dung_lai_ton_vi_tri()` không tham số — nhánh dựng lại TOÀN site,
		đường mà người vận hành thật sự dùng khi nghi ngờ số liệu trên diện
		rộng. Các bài khác chỉ gọi `dung_lai_ton_vi_tri(KHO)`, nhánh này chưa
		ai kiểm chứng nếu bỏ qua bài này.
		"""
		o = _o("K19Z30010110")
		_ghi(o, "_Test Item VT5", "LO-G", 3)
		# phá bộ đệm bằng cách xoá thẳng dòng tồn — không qua engine.
		frappe.db.sql("delete from `tabLocation Balance` where o=%s", (o,))
		self.assertEqual(so.ton_o(o, "_Test Item VT5", "LO-G"), 0)

		so_dong = so.dung_lai_ton_vi_tri()
		self.assertIsInstance(so_dong, int)
		self.assertGreaterEqual(so_dong, 1)
		self.assertEqual(so.ton_o(o, "_Test Item VT5", "LO-G"), 3)


class TestRangBuocDuyNhat(_TuDonSauMoiBai):
	"""Việc 1 (spec §5.3): unique index (o, vat_tu, so_lo) ở tầng DB.

	Lớp Python một mình không đủ tin cậy khi có ghi đồng thời — xem
	`TestCongDonTonNguyenTu` để thấy hậu quả thật (dòng ma) khi thiếu index
	này. Bài dưới đây chỉ kiểm DB có thật sự chặn hay không, không đụng tới
	engine.
	"""

	def setUp(self):
		super().setUp()
		_tao_item("_Test Item VT9")

	def test_trung_khoa_bi_chan_o_tang_db(self):
		o = _o("K19Z30010111")
		frappe.get_doc({
			"doctype": "Location Balance", "o": o, "kho": KHO,
			"vat_tu": "_Test Item VT9", "so_lo": "", "so_luong": 1,
		}).insert(ignore_permissions=True)

		with self.assertRaises(Exception) as ctx:
			frappe.get_doc({
				"doctype": "Location Balance", "o": o, "kho": KHO,
				"vat_tu": "_Test Item VT9", "so_lo": "", "so_luong": 1,
			}).insert(ignore_permissions=True)
		self.assertIn(
			"duplicate", str(ctx.exception).lower(),
			"phải có unique index (o, vat_tu, so_lo) chặn ở tầng DB",
		)


class TestCongDonTonNguyenTu(FrappeTestCase):
	"""Việc 3: `_cong_don_ton` phải nguyên tử — mô phỏng ghi đồng thời bằng
	2 CONNECTION DB THẬT (2 luồng, mỗi luồng tự `frappe.connect()`), không
	phải giả lập bằng cách gọi hàm hai lần liên tiếp trong cùng transaction
	(cách đó không bao giờ lộ ra race, vì không có gì để "đua" cả).

	Lớp này KHÔNG dùng savepoint cô lập (`_TuDonSauMoiBai`) vì hai luồng
	thật cần dữ liệu nền được COMMIT để cùng thấy — savepoint chỉ tồn tại
	trong transaction của luồng chính, hai luồng của bài test không thấy
	được. Vì vậy phải tự dọn dữ liệu bằng tay ở tearDownClass, có commit.

	Cách hai luồng không "va" nhau giả tạo: mỗi luồng chỉ gọi
	`frappe.db.commit()` ở cuối, sau khi đã đọc/ghi xong. Trong lúc đó,
	InnoDB (REPEATABLE READ) đảm bảo luồng kia không thấy được thay đổi
	CHƯA COMMIT — nên cả hai luồng chắc chắn cùng thấy "chưa có dòng tồn"
	trước khi ghi, đúng kịch bản race thật, không phụ thuộc may rủi lịch
	chạy của hệ điều hành.

	- Trước khi sửa (không có unique index, `_cong_don_ton` đọc-rồi-ghi):
	  cả hai luồng cùng insert -> 2 dòng `Location Balance` cho một khoá
	  (dòng ma), KHÔNG luồng nào báo lỗi. Test RED ở `assertEqual(..., 1)`.
	- Sau khi sửa (unique index + upsert nguyên tử một câu SQL): luồng ghi
	  sau tự động cộng dồn vào dòng luồng trước vừa tạo, không luồng nào
	  báo lỗi, kết quả đúng 1 dòng với tổng đúng.
	"""

	O = "K19Z30010115"
	VAT_TU = "_Test Item VT Race"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("Item", cls.VAT_TU):
			frappe.get_doc({
				"doctype": "Item", "item_code": cls.VAT_TU, "item_name": cls.VAT_TU,
				"item_group": "All Item Groups", "stock_uom": "Nos", "is_stock_item": 1,
			}).insert(ignore_permissions=True)
		if not frappe.db.exists("Storage Location", cls.O):
			frappe.get_doc({
				"doctype": "Storage Location", "ma_o": cls.O, "kho": KHO,
			}).insert(ignore_permissions=True)
		# BẮT BUỘC commit: hai luồng của bài test dùng connection riêng, chỉ
		# thấy được dữ liệu đã commit của luồng chính.
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.db.delete("Location Ledger Entry", {"o": cls.O})
		frappe.db.delete("Location Balance", {"o": cls.O})
		frappe.db.delete("Storage Location", {"name": cls.O})
		frappe.db.delete("Item", {"name": cls.VAT_TU})
		frappe.db.commit()
		super().tearDownClass()

	def test_hai_luong_ghi_dong_thoi_khong_sinh_dong_ma(self):
		site = frappe.local.site
		loi = []

		def ghi(so_luong, chung_tu_row):
			try:
				frappe.connect(site=site)
				so.ghi_dong_so(
					o=self.O, kho=KHO, vat_tu=self.VAT_TU, so_lo=None,
					so_luong=so_luong, chung_tu_type="Storage Location",
					chung_tu=self.O, chung_tu_row=chung_tu_row, sle=None,
					ngay="2026-09-09", thoi_diem="2026-09-09 08:00:00",
					company="Miyano Việt Nam",
				)
				frappe.db.commit()
			except Exception as e:  # noqa: BLE001 — cần bắt để báo ra luồng chính
				loi.append(e)
			finally:
				frappe.destroy()

		t1 = threading.Thread(target=ghi, args=(5, "race-1"))
		t2 = threading.Thread(target=ghi, args=(3, "race-2"))
		t1.start()
		t2.start()
		t1.join(timeout=30)
		t2.join(timeout=30)

		self.assertFalse(loi, f"ghi đồng thời không được ném lỗi giữa chừng: {loi}")

		so_dong = frappe.db.count("Location Balance", {"o": self.O, "vat_tu": self.VAT_TU})
		self.assertEqual(
			so_dong, 1,
			"hai luồng ghi cùng khoá (o, vat_tu, so_lo) phải gộp thành đúng 1 "
			"dòng tồn, không được sinh dòng ma",
		)
		self.assertEqual(so.ton_o(self.O, self.VAT_TU, None), 8)
