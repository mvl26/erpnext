"""Phiếu xếp / chuyển vị trí — spec 2026-09-14.

Bài học đắt nhất của module này: một phép kiểm sai làm lệch tồn theo Ô mà
TỔNG vẫn đúng, nên `doi_soat` vẫn báo khớp và không gì bật lên. Vì vậy gần
như mọi bài ở đây có CHỐT ÂM đi kèm — khẳng định cả cái phải đổi lẫn cái
phải còn nguyên.

CHƯA ĐO ĐƯỢC, đừng đọc file này như thể đã đo: ca TƯƠNG TRANH (hai phiếu
cùng rút một lô ra khỏi một ô). Nó cần hai kết nối CSDL thật và `commit()`
tường minh, mà bài test nào `commit()` thì phải tự dọn cả những nút tổ tiên
do NestedSet sinh ra — nếu không, rác của nó làm bài ở file KHÁC đỏ giả
(đã xảy ra một lần trong dự án này). Hiện phép chặn tồn âm dựa vào khoá
dòng chỉ mục của InnoDB trong `INSERT ... ON DUPLICATE KEY UPDATE` — lập
luận từ cơ chế, KHÔNG phải từ phép đo.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now, nowdate

from erpnext.vi_tri_kho.vitri import so

KHO = "Kho Miyano - MYN"
CTY = "Miyano Việt Nam"


def _o(ma_o, **kw):
	if not frappe.db.exists("Storage Location", ma_o):
		frappe.get_doc({"doctype": "Storage Location", "ma_o": ma_o, "kho": KHO, **kw}).insert(
			ignore_permissions=True
		)
	return ma_o


def _vat_tu(ma, co_lo=True):
	if not frappe.db.exists("Item", ma):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": ma,
				"item_name": ma,
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"has_batch_no": 1 if co_lo else 0,
				"create_new_batch": 1 if co_lo else 0,
			}
		).insert(ignore_permissions=True)
	return ma


def _lo(ma, vat_tu):
	if not frappe.db.exists("Batch", ma):
		frappe.get_doc({"doctype": "Batch", "batch_id": ma, "item": vat_tu}).insert(ignore_permissions=True)
	return ma


def _gan(vat_tu, vi_tri, kho=KHO):
	"""Gán vị trí cố định — cần cho các bài kiểm gợi ý theo tem (Task 4)."""
	if not frappe.db.exists("Item Location Preference", vat_tu):
		frappe.get_doc(
			{"doctype": "Item Location Preference", "vat_tu": vat_tu, "kho": kho, "vi_tri": vi_tri}
		).insert(ignore_permissions=True)
	return vat_tu


def _phieu(dong, kho=KHO, **kw):
	"""Dựng phiếu CHƯA lưu. `dong` là list dict(vat_tu, so_lo, tu_o, den_o, so_luong)."""
	return frappe.get_doc({"doctype": "Location Transfer", "kho": kho, "items": dong, **kw})


class _BoKiemOTem:
	"""Các lớp dưới kiểm CƠ CHẾ chuyển ô (sổ hai chiều, huỷ, tồn âm, nhánh
	tắt...) với ô tuỳ ý — không nói về luật "xếp đúng ô trên tem" (19/09/2026),
	luật đó có bài riêng ở `test_o_tem.py`. Tắt luật cho CẢ LỚP."""

	@classmethod
	def setUpClass(cls):
		from erpnext.vi_tri_kho.vitri.o_tem import CO_BO_KIEM_TEST

		cls._co_cu = frappe.flags.get(CO_BO_KIEM_TEST)
		frappe.flags[CO_BO_KIEM_TEST] = True
		super().setUpClass()

	@classmethod
	def tearDownClass(cls):
		from erpnext.vi_tri_kho.vitri.o_tem import CO_BO_KIEM_TEST

		frappe.flags[CO_BO_KIEM_TEST] = cls._co_cu
		super().tearDownClass()


class TestPhepKiemCoBan(_BoKiemOTem, FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.vt = _vat_tu("9X-VT-CO-LO", co_lo=True)
		cls.vt_khong_lo = _vat_tu("9X-VT-KHONG-LO", co_lo=False)
		cls.lo = _lo("9X-LO-01", cls.vt)
		cls.a = _o("9X01010101")
		cls.b = _o("9X01010102")

	def _dong(self, **kw):
		m = {"vat_tu": self.vt, "so_lo": self.lo, "tu_o": self.a, "den_o": self.b, "so_luong": 5}
		m.update(kw)
		return [m]

	def test_phieu_khong_co_dong_bi_tu_choi(self):
		with self.assertRaises(frappe.ValidationError):
			_phieu([]).insert(ignore_permissions=True)

	def test_so_luong_am_bi_tu_choi(self):
		"""Số âm là phiếu ngược trá hình — bắt lập phiếu riêng cho rõ ai
		chuyển cái gì đi đâu.

		Chỉ kiểm số ÂM ở đây, không kiểm 0: `so_luong` cố ý KHÔNG đặt
		`reqd = 1` trong JSON (xem controller) nên 0 cũng phải do phép kiểm
		của mình bắt — bài dưới lo phần đó, tách ra để mỗi bài chết vì đúng
		một lý do.
		"""
		with self.assertRaises(frappe.ValidationError):
			_phieu(self._dong(so_luong=-5)).insert(ignore_permissions=True)

	def test_so_luong_bang_khong_bi_tu_choi(self):
		with self.assertRaises(frappe.ValidationError):
			_phieu(self._dong(so_luong=0)).insert(ignore_permissions=True)

	def test_tu_o_trung_den_o_bi_tu_choi(self):
		with self.assertRaises(frappe.ValidationError):
			_phieu(self._dong(den_o=self.a)).insert(ignore_permissions=True)

	def test_o_thuoc_kho_khac_bi_tu_choi(self):
		"""Điều kiện để bất biến §3 tự giữ — xem spec §3, không phải quy tắc
		nghiệp vụ tuỳ chọn."""
		khac = "Hàng trả về - MYN"
		if not frappe.db.exists("Storage Location", "9Y01010101"):
			frappe.get_doc({"doctype": "Storage Location", "ma_o": "9Y01010101", "kho": khac}).insert(
				ignore_permissions=True
			)
		with self.assertRaises(frappe.ValidationError):
			_phieu(self._dong(den_o="9Y01010101")).insert(ignore_permissions=True)

	def test_den_o_la_nut_nhom_bi_tu_choi(self):
		with self.assertRaises(frappe.ValidationError):
			_phieu(self._dong(den_o="9X0101")).insert(ignore_permissions=True)

	def test_hang_co_lo_ma_bo_trong_so_lo_bi_tu_choi(self):
		"""K9 chiều thiếu — dòng sổ `so_lo = ''` không bao giờ khớp lô thật."""
		with self.assertRaises(frappe.ValidationError):
			_phieu(self._dong(so_lo=None)).insert(ignore_permissions=True)

	def test_hang_khong_lo_ma_dien_lo_cung_bi_tu_choi(self):
		"""K9 chiều thừa — CHỐT ÂM của bài trên.

		PHẢI khớp THÔNG ĐIỆP, không chỉ khớp loại ngoại lệ. Đo được bằng đột
		biến: lô dùng ở đây thuộc mặt hàng khác, nên khi gỡ bỏ phép kiểm K9
		thì K10 ("lô không thuộc mặt hàng") nổ thay và bài vẫn xanh — xanh vì
		một lý do hoàn toàn khác với thứ nó mang tên.
		"""
		with self.assertRaisesRegex(frappe.ValidationError, "không quản lý lô"):
			_phieu(self._dong(vat_tu=self.vt_khong_lo)).insert(ignore_permissions=True)

	def test_lo_khong_thuoc_mat_hang_bi_tu_choi(self):
		vt2 = _vat_tu("9X-VT-CO-LO-2", co_lo=True)
		lo2 = _lo("9X-LO-02", vt2)
		with self.assertRaises(frappe.ValidationError):
			_phieu(self._dong(so_lo=lo2)).insert(ignore_permissions=True)

	def test_kho_chua_bat_quan_ly_vi_tri_bi_tu_choi(self):
		"""K1. Ô nguồn/đích phải thuộc CHÍNH kho chưa bật, nếu không K2 ("ô
		thuộc kho khác") nổ trước và bài xanh vì lý do khác — đo được bằng
		đột biến gỡ K1: bản trước vẫn xanh. Khớp cả thông điệp cho chắc.
		"""
		khac = "Hàng trả về - MYN"
		for ma in ("9Y02010101", "9Y02010102"):
			if not frappe.db.exists("Storage Location", ma):
				frappe.get_doc({"doctype": "Storage Location", "ma_o": ma, "kho": khac}).insert(
					ignore_permissions=True
				)
		dong = [
			{
				"vat_tu": self.vt,
				"so_lo": self.lo,
				"tu_o": "9Y02010101",
				"den_o": "9Y02010102",
				"so_luong": 5,
			}
		]
		with self.assertRaisesRegex(frappe.ValidationError, "chưa bật quản lý vị trí"):
			_phieu(dong, kho=khac).insert(ignore_permissions=True)

	def test_phieu_hop_le_luu_va_duyet_duoc(self):
		"""Đối chứng: mọi phép kiểm trên CHỈ chặn cái sai.

		Phải nạp tồn cho ô nguồn trước — từ Task 2 việc duyệt ghi sổ thật, và
		một phiếu lấy hàng từ ô rỗng thì bị chặn tồn âm từ chối, đúng như
		thiết kế.
		"""
		_nap(self.a, self.vt, self.lo, 20)
		p = _phieu(self._dong())
		p.insert(ignore_permissions=True)
		p.submit()
		self.assertEqual(p.docstatus, 1)


def _nap(o, vat_tu, so_lo, sl):
	"""Nạp tồn thẳng vào một ô để dựng TIỀN ĐỀ cho bài test.

	KHÔNG phải cách dùng thật — đường thật là hook nhập kho hoặc chính phiếu
	này. Ở đây cần đặt sẵn hàng vào một ô cụ thể mà không phải dựng cả một
	Purchase Receipt.
	"""
	so.ghi_dong_so(
		o=o,
		kho=KHO,
		vat_tu=vat_tu,
		so_lo=so_lo,
		so_luong=sl,
		chung_tu_type=None,
		chung_tu=None,
		chung_tu_row="NAP-TIEN-DE-TEST",
		sle=None,
		ngay=nowdate(),
		thoi_diem=now(),
		company=CTY,
	)


class TestGhiSo(_BoKiemOTem, FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.vt = _vat_tu("9X-GS-VT", co_lo=True)
		cls.lo = _lo("9X-GS-LO", cls.vt)
		cls.a = _o("9X02010101")
		cls.b = _o("9X02010102")

	def _dong(self, sl=10, **kw):
		m = {"vat_tu": self.vt, "so_lo": self.lo, "tu_o": self.a, "den_o": self.b, "so_luong": sl}
		m.update(kw)
		return [m]

	def test_duyet_thi_chuyen_dung_hai_o(self):
		_nap(self.a, self.vt, self.lo, 30)
		truoc_a = so.ton_o(self.a, self.vt, self.lo)
		truoc_b = so.ton_o(self.b, self.vt, self.lo)
		tong_truoc = so.tong_ton_vi_tri(KHO, self.vt, self.lo)

		p = _phieu(self._dong(10))
		p.insert(ignore_permissions=True)
		p.submit()

		self.assertEqual(so.ton_o(self.a, self.vt, self.lo), truoc_a - 10)
		self.assertEqual(so.ton_o(self.b, self.vt, self.lo), truoc_b + 10)
		# CHỐT ÂM — bất biến §3: tổng của kho KHÔNG được đổi.
		self.assertEqual(so.tong_ton_vi_tri(KHO, self.vt, self.lo), tong_truoc)

	def test_khong_sinh_stock_ledger_entry_nao(self):
		"""CHỐT ÂM quan trọng nhất của cả tính năng.

		Đếm TOÀN BỘ bảng SLE, không đếm theo chứng từ này: đếm theo chứng từ
		thì luôn ra 0 dù hook có chạy hay không, và bài trở thành vô nghĩa.

		Sinh SLE sẽ kích lại `Stock Ledger Entry.on_submit` → `ghi_so_vi_tri`
		dồn hàng vào ZZZ-CHUA-XEP một lần nữa, đúng thứ phiếu vừa gỡ ra.
		"""
		_nap(self.a, self.vt, self.lo, 30)
		truoc = frappe.db.count("Stock Ledger Entry")
		p = _phieu(self._dong(10))
		p.insert(ignore_permissions=True)
		p.submit()
		self.assertEqual(frappe.db.count("Stock Ledger Entry"), truoc)

	def test_rut_qua_ton_bi_tu_choi_va_khong_ghi_gi(self):
		_nap(self.a, self.vt, self.lo, 5)
		truoc_a = so.ton_o(self.a, self.vt, self.lo)
		truoc_dong = frappe.db.count("Location Ledger Entry")

		p = _phieu(self._dong(999))
		p.insert(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			p.submit()

		# CHỐT ÂM: rollback phải SẠCH. Ô âm là hỏng nặng — `doi_soat` báo
		# `o_am` và "Đồng bộ lại" cố ý ném lỗi thay vì chữa.
		self.assertEqual(so.ton_o(self.a, self.vt, self.lo), truoc_a)
		self.assertEqual(frappe.db.count("Location Ledger Entry"), truoc_dong)

	def test_lay_ra_roi_tra_lai_cung_o_van_duyet_duoc(self):
		"""Đối chứng cho spec §7.2: kiểm theo KẾT QUẢ RÒNG sau khi ghi xong cả
		phiếu, không kiểm sau từng dòng.

		Ô A chỉ có 10; dòng 1 lấy 10 đi, dòng 2 trả 10 về. Kiểm sau từng dòng
		sẽ từ chối oan phiếu hợp lệ này.
		"""
		_nap(self.a, self.vt, self.lo, 10)
		p = _phieu(
			[
				{"vat_tu": self.vt, "so_lo": self.lo, "tu_o": self.a, "den_o": self.b, "so_luong": 10},
				{"vat_tu": self.vt, "so_lo": self.lo, "tu_o": self.b, "den_o": self.a, "so_luong": 10},
			]
		)
		p.insert(ignore_permissions=True)
		p.submit()
		self.assertEqual(p.docstatus, 1)


class TestHuyPhieu(_BoKiemOTem, FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.vt = _vat_tu("9X-HP-VT", co_lo=True)
		cls.lo = _lo("9X-HP-LO", cls.vt)
		cls.a = _o("9X03010101")
		cls.b = _o("9X03010102")

	def _phieu_da_duyet(self, sl=10):
		p = _phieu([{"vat_tu": self.vt, "so_lo": self.lo, "tu_o": self.a, "den_o": self.b, "so_luong": sl}])
		p.insert(ignore_permissions=True)
		p.submit()
		return p

	def test_huy_dao_dung_hai_chieu(self):
		_nap(self.a, self.vt, self.lo, 30)
		truoc_a = so.ton_o(self.a, self.vt, self.lo)
		truoc_b = so.ton_o(self.b, self.vt, self.lo)

		p = self._phieu_da_duyet(10)
		p.cancel()

		self.assertEqual(so.ton_o(self.a, self.vt, self.lo), truoc_a)
		self.assertEqual(so.ton_o(self.b, self.vt, self.lo), truoc_b)

	def test_huy_ghi_them_chu_khong_xoa_dong_cu(self):
		"""Sổ là append-only — `dung_lai_ton_vi_tri()` dựng lại bộ đệm bằng
		cách cộng TOÀN BỘ sổ, nên xoá dòng cũ vẫn ra đúng số mà mất sạch dấu
		vết. Giữ cả hai chiều để đọc lại được lịch sử."""
		_nap(self.a, self.vt, self.lo, 30)
		p = self._phieu_da_duyet(10)
		sau_duyet = frappe.db.count("Location Ledger Entry", {"chung_tu": p.name})
		self.assertEqual(sau_duyet, 2)
		p.cancel()
		self.assertEqual(frappe.db.count("Location Ledger Entry", {"chung_tu": p.name}), 4)
		self.assertEqual(
			frappe.db.count("Location Ledger Entry", {"chung_tu": p.name, "da_huy": 1}),
			2,
			"hai bút toán đảo phải mang cờ da_huy = 1 để phân biệt với bút toán gốc",
		)

	def test_huy_khi_o_dich_da_bi_xuat_het_bi_chan(self):
		"""Hàng đã xếp vào ô đích có thể đã bị lấy đi mất; lúc đó huỷ sẽ đẩy ô
		đích xuống âm. Phải chặn, và không được ghi gì.

		Đây là bài DUY NHẤT bắt được đột biến "gom `cham` chỉ ô nguồn" — ở
		đường duyệt ô đích chỉ cộng thêm nên không bao giờ âm.
		"""
		_nap(self.a, self.vt, self.lo, 30)
		p = self._phieu_da_duyet(10)
		_nap(self.b, self.vt, self.lo, -10)  # ô đích bị xuất sạch phần vừa xếp
		truoc = frappe.db.count("Location Ledger Entry")
		with self.assertRaises(frappe.ValidationError):
			p.cancel()
		self.assertEqual(frappe.db.count("Location Ledger Entry"), truoc)


class TestNhanhNgungDung(_BoKiemOTem, FrappeTestCase):
	"""Hai chiều NGƯỢC NHAU, và cả hai đều cố ý.

	Chiều VÀO bị chặn: vá đúng bất đối xứng ghi trong
	`QUYET-DINH-thi-cong-cay-vi-tri.md` — `fefo.py` là nơi DUY NHẤT lọc
	`disabled`, đường nhập không lọc gì, nên hàng vẫn chảy VÀO một dãy đã tắt
	trong khi không ô nào trong dãy đó xuất RA được, mà đối soát vẫn xanh vì
	nó chỉ so tổng.

	Chiều RA được phép: đó là đường DUY NHẤT gỡ hàng khỏi một dãy đang tháo
	kệ. Cấm nốt chiều này thì hàng kẹt vĩnh viễn.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.vt = _vat_tu("9X-ND-VT", co_lo=True)
		cls.lo = _lo("9X-ND-LO", cls.vt)
		cls.a = _o("9X04010101")
		cls.b = _o("9X06010101")  # DÃY khác hẳn, để tắt cả dãy 9X06
		cls.b2 = _o("9X06010102")  # cùng dãy với b, dùng cho bài cấp NHÁNH

	def setUp(self):
		"""Trả mọi cờ `disabled` về 0 trước MỖI bài.

		`FrappeTestCase` rollback theo LỚP, không theo từng bài — cờ một bài
		bật lên còn nguyên ở bài sau. Đo được: không có setUp này thì
		`test_xep_vao_o_duoi_nhanh_da_tat_cung_bi_chan` xanh nhờ ô lá tự nó
		đang tắt từ bài trước, chứ KHÔNG phải nhờ vế tổ tiên — đột biến bỏ hẳn
		vế tổ tiên vẫn xanh.
		"""
		for ten in (self.a, self.b, self.b2, "9X04", "9X06", "9X0601"):
			if frappe.db.exists("Storage Location", ten):
				frappe.db.set_value("Storage Location", ten, "disabled", 0, update_modified=False)

	def _p(self, tu_o, den_o):
		return _phieu([{"vat_tu": self.vt, "so_lo": self.lo, "tu_o": tu_o, "den_o": den_o, "so_luong": 5}])

	def test_xep_vao_o_dang_tat_bi_chan(self):
		frappe.db.set_value("Storage Location", self.b, "disabled", 1)
		_nap(self.a, self.vt, self.lo, 20)
		with self.assertRaisesRegex(frappe.ValidationError, "Ngừng dùng"):
			self._p(self.a, self.b).insert(ignore_permissions=True)

	def test_xep_vao_o_duoi_nhanh_da_tat_cung_bi_chan(self):
		"""Tắt cả DÃY `9X06`; ô lá bên dưới tự nó vẫn `disabled = 0`.

		Thiếu bài này thì một phép kiểm chỉ đọc `disabled` của chính ô lá vẫn
		xanh ở bài trên — mà đó đúng là lỗi `fefo.py` từng mắc trước Task 4.
		"""
		frappe.db.set_value("Storage Location", "9X06", "disabled", 1)
		_nap(self.a, self.vt, self.lo, 20)
		# Dùng b2 chứ không dùng b: b là ô mà bài khác tắt trực tiếp, nên nếu
		# lỡ còn sót cờ thì bài này lại xanh vì lý do khác.
		with self.assertRaisesRegex(frappe.ValidationError, "Ngừng dùng"):
			self._p(self.a, self.b2).insert(ignore_permissions=True)

	def test_lay_RA_khoi_o_dang_tat_van_duoc(self):
		"""CHỐT ÂM, và là cả lý do tính năng này tồn tại."""
		_nap(self.a, self.vt, self.lo, 20)
		frappe.db.set_value("Storage Location", self.a, "disabled", 1)
		p = self._p(self.a, self.b)
		p.insert(ignore_permissions=True)
		p.submit()
		self.assertEqual(p.docstatus, 1)

	def test_lay_RA_khoi_nhanh_da_tat_cung_duoc(self):
		"""Chốt âm cấp nhánh: tắt cả DÃY chứa ô nguồn thì vẫn gỡ hàng ra được."""
		_nap(self.a, self.vt, self.lo, 20)
		frappe.db.set_value("Storage Location", "9X04", "disabled", 1)
		p = self._p(self.a, self.b)
		p.insert(ignore_permissions=True)
		p.submit()
		self.assertEqual(p.docstatus, 1)


class TestBayF8TrongNhanhBiTat(FrappeTestCase):
	"""Khoá phép chứa CHẶT trong `cay.nhanh_bi_tat`.

	Bản ghi chưa hội tụ mang `lft = rgt = 0`. Nới `<` `>` thành `<=` `>=` thì
	mọi bản ghi 0/0 coi nhau là tổ tiên của nhau — đo thật trên site: ô hệ
	thống nhận 128 "tổ tiên" giả, đủ để chặn mọi phiếu xuất của cả kho.

	Không có bài này thì đột biến nới phép chứa SỐNG SÓT: với cây lành, một
	nút chứa chính nó hay không đều cho cùng kết quả, vì vế `tt.name = o` đã
	lo phần đó.
	"""

	def test_hai_ban_ghi_chua_hoi_tu_khong_coi_nhau_la_to_tien(self):
		from erpnext.vi_tri_kho.vitri.cay import nhanh_bi_tat

		tat = _o("9X08010101")
		lanh = _o("9X09010101")
		frappe.db.set_value("Storage Location", tat, "disabled", 1, update_modified=False)
		for ten in (tat, lanh):
			frappe.db.set_value("Storage Location", ten, {"lft": 0, "rgt": 0}, update_modified=False)

		self.assertIsNone(
			nhanh_bi_tat(lanh),
			"một bản ghi 0/0 đang tắt bị coi là tổ tiên của một bản ghi 0/0 khác — đúng bẫy F8",
		)

	def test_van_bat_dung_to_tien_that(self):
		"""Đối chứng: siết chặt KHÔNG được làm mất khả năng bắt tổ tiên thật."""
		from erpnext.vi_tri_kho.vitri.cay import nhanh_bi_tat

		la = _o("9X10010101")
		frappe.db.set_value("Storage Location", "9X10", "disabled", 1, update_modified=False)
		self.assertEqual(nhanh_bi_tat(la), "9X10")


class TestLayHangChuaXep(_BoKiemOTem, FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.vt = _vat_tu("9X-LC-VT", co_lo=True)
		cls.lo = _lo("9X-LC-LO", cls.vt)
		cls.zzz = frappe.db.get_value("Storage Location", {"la_o_chua_xep": 1, "kho": KHO}, "name")
		cls.o_that = _o("9X11010101")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_tra_ve_hang_dang_o_o_chua_xep(self):
		from erpnext.vi_tri_kho.vitri.xep import hang_chua_xep

		_nap(self.zzz, self.vt, self.lo, 7)
		dong = [d for d in hang_chua_xep(KHO) if d["vat_tu"] == self.vt]
		self.assertEqual(len(dong), 1)
		self.assertEqual(dong[0]["tu_o"], self.zzz)
		self.assertEqual(dong[0]["so_luong"], 7)
		self.assertEqual(dong[0]["so_lo"], self.lo)

	def test_khong_tra_ve_hang_o_o_that(self):
		"""CHỐT ÂM: nút này chỉ kéo hàng CHƯA xếp. Thiếu bài này thì một đột
		biến bỏ điều kiện `la_o_chua_xep` sẽ kéo cả kho vào phiếu."""
		from erpnext.vi_tri_kho.vitri.xep import hang_chua_xep

		_nap(self.o_that, self.vt, self.lo, 9)
		o = {d["tu_o"] for d in hang_chua_xep(KHO)}
		self.assertNotIn(self.o_that, o)

	def test_khong_tra_ve_hang_cua_kho_khac(self):
		"""CHỐT ÂM thứ hai: lọc theo kho phải chịu lực.

		Kế hoạch đã ghi sẵn rằng đột biến bỏ `lb.kho = %(kho)s` có thể không
		bị bắt nếu không có bài này.
		"""
		from erpnext.vi_tri_kho.vitri.xep import hang_chua_xep

		khac = "Hàng trả về - MYN"
		zzz_khac = frappe.db.get_value("Storage Location", {"la_o_chua_xep": 1, "kho": khac}, "name")
		if not zzz_khac:
			# Kho kia chưa bật quản lý vị trí nên chưa có ô này. Tự dựng chứ
			# KHÔNG skipTest: bỏ qua thì đột biến "bỏ lọc theo kho" không bị
			# bắt, và bài mang tên chốt âm lại không chốt gì cả.
			zzz_khac = "ZZZ-CHUA-XEP-" + khac
			frappe.get_doc(
				{
					"doctype": "Storage Location",
					"ma_o": zzz_khac,
					"kho": khac,
					"la_o_chua_xep": 1,
					"thu_tu_lay_hang": 9999,
				}
			).insert(ignore_permissions=True)
		so.ghi_dong_so(
			o=zzz_khac, kho=khac, vat_tu=self.vt, so_lo=self.lo, so_luong=11,
			chung_tu_type=None, chung_tu=None, chung_tu_row="NAP-TIEN-DE-TEST",
			sle=None, ngay=nowdate(), thoi_diem=now(), company=CTY,
		)
		o = {d["tu_o"] for d in hang_chua_xep(KHO)}
		self.assertNotIn(zzz_khac, o)

	def test_ma_rat_dai_khong_lam_no_luoi_an_toan(self):
		"""Vòng sửa 2/5 (điều phối, Important) — cùng bẫy vá ở `quet.py`, nhưng
		ĐÂY LÀ MÀN HÌNH THỦ KHO DÙNG HẰNG NGÀY (nút "Lấy hàng chưa xếp").

		`Error Log.method` là `Data(140)`. Ép `goi_y_o` ném lỗi VÀ dùng một
		(mặt hàng, lô) đủ dài để tiêu đề ghép thô `({vat_tu}/{so_lo})` vượt
		140 — nếu `cat_tieu_de` bị gỡ, `frappe.log_error()` NẰM TRONG khối
		`except` (dựng lên đúng để "một (mặt hàng, lô) hỏng không được làm
		sập cả danh sách") sẽ tự ném `CharacterLengthExceededError`, văng ra
		NGOÀI khối đó — sập nguyên nút "Lấy hàng chưa xếp" cho CẢ kho, không
		chỉ một dòng.
		"""
		from erpnext.vi_tri_kho.vitri import xep as xep_mod
		from erpnext.vi_tri_kho.vitri.goi_y import goi_y_o as goi_y_o_that
		from erpnext.vi_tri_kho.vitri.nhat_ky_loi import TRAN_DO_DAI_TIEU_DE
		from erpnext.vi_tri_kho.vitri.xep import hang_chua_xep

		v_dai = _vat_tu("V" * 60, co_lo=True)
		lo_dai = _lo("L" * 60, v_dai)
		_nap(self.zzz, v_dai, lo_dai, 3)

		# `KHO` là kho THẬT (dữ liệu có sẵn trên site, xem docstring
		# `test_van_chi_goi_goi_y_mot_lan_cho_moi_lo` ở trên): patch
		# `goi_y_o` ném lỗi VÔ ĐIỀU KIỆN sẽ chạm MỌI (mặt hàng, lô) khác đang
		# chờ xếp trong kho thật — không chỉ sai số đếm `Error Log` (đã từng
		# sai ở đây, sửa rồi), mà còn THẬT SỰ GHI hàng chục dòng Error Log
		# giả cho dữ liệu SẢN XUẤT thật mỗi lần chạy bài này (đã đo: `log_
		# error` không nằm trong giao dịch bị `FrappeTestCase` rollback —
		# Error Log của nó SỐNG SÓT qua rollback, thấy rõ khi đếm lại sau
		# suite). Chỉ ném lỗi cho ĐÚNG `v_dai` của bài này; mọi (mặt hàng, lô)
		# khác gọi hàm THẬT — hành vi giống hệt không có patch.
		def _goi_y_o_gia_lap(vat_tu, kho, so_lo=None):
			if vat_tu == v_dai:
				raise RuntimeError("giả lập lỗi gán")
			return goi_y_o_that(vat_tu, kho, so_lo)

		with patch.object(xep_mod, "goi_y_o", side_effect=_goi_y_o_gia_lap):
			dong = hang_chua_xep(KHO)

		dong_cua_no = [d for d in dong if d["vat_tu"] == v_dai]
		self.assertEqual(len(dong_cua_no), 1, "danh sách vẫn phải trả về, không sập")
		self.assertIsNone(dong_cua_no[0]["den_o"], "goi_y_o lỗi thì không có ô gợi ý")

		# Đối chứng: `log_error` phải THẬT SỰ ghi được MỘT dòng cho đúng
		# (v_dai, lo_dai) này (không phải "không ném lỗi vì log_error đã âm
		# thầm hỏng theo cách khác"), và tiêu đề dòng đó phải nằm trong trần.
		# Điểm cắt (133 ký tự thô + đuôi) rơi SAU trọn `v_dai` (60 ký tự,
		# ngay sau tiền tố ~39 ký tự) nên tìm bằng LIKE trên chính `v_dai`
		# vẫn khớp đúng dòng, dù tiêu đề đã bị cắt phần đuôi (`so_lo`).
		dong_error_log = frappe.get_all(
			"Error Log", filters={"method": ["like", f"%{v_dai}%"]}, pluck="method"
		)
		self.assertEqual(len(dong_error_log), 1, "chỉ v_dai bị ép lỗi, phải đúng một dòng")
		self.assertLessEqual(len(dong_error_log[0]), TRAN_DO_DAI_TIEU_DE)

		# Dọn NGAY dòng Error Log vừa cố ý tạo ra: nó KHÔNG bị `FrappeTestCase`
		# rollback (xem ghi chú ở trên) nên phải tự xoá, không để rác trên
		# CSDL thật (yêu cầu kế hoạch: dọn dữ liệu thử, đếm lại).
		frappe.db.delete("Error Log", {"method": ["like", f"%{v_dai}%"]})

	def test_nguoi_khong_co_vai_tro_bi_chan(self):
		from erpnext.vi_tri_kho.vitri.xep import hang_chua_xep

		ten = "xep-khong-quyen@mo-phong.local"
		if not frappe.db.exists("User", ten):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": ten,
					"first_name": "Xep",
					"send_welcome_email": 0,
					"roles": [],
				}
			).insert(ignore_permissions=True)
		frappe.set_user(ten)
		with self.assertRaises(frappe.PermissionError):
			hang_chua_xep(KHO)

	def test_stock_user_dung_duoc(self):
		"""Đối chứng: thủ kho PHẢI dùng được — đây là việc hằng ngày của họ."""
		from erpnext.vi_tri_kho.vitri.xep import hang_chua_xep

		ten = "xep-thu-kho@mo-phong.local"
		if not frappe.db.exists("User", ten):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": ten,
					"first_name": "Thu Kho Xep",
					"send_welcome_email": 0,
					"roles": [{"role": "Stock User"}],
				}
			).insert(ignore_permissions=True)
		frappe.set_user(ten)
		self.assertIsInstance(hang_chua_xep(KHO), list)

	def test_hai_lo_cung_mat_hang_co_the_ra_hai_o_khac_nhau(self):
		"""Khoá đệm phải là (mặt hàng, lô), không phải mặt hàng.

		Trước khối C, một mặt hàng nhiều lô cho ra MỘT gợi ý chung — đúng khi
		căn cứ duy nhất là vị trí gán. Từ khi tem ghi lại ô đã in (§8), hai lô
		của cùng một mặt hàng có thể có hai ô in tem khác nhau, và đệm theo mặt
		hàng sẽ lấy gợi ý của lô ĐẦU TIÊN gán cho cả hai — tức nửa số tem nói dối.
		"""
		from erpnext.vi_tri_kho.vitri.xep import hang_chua_xep

		v = _vat_tu("9X-LC-2LO-VT", co_lo=True)
		a = _o("9X12010101")
		b = _o("9X12010102")
		# Gán cả tầng chứa cả hai ô cho mặt hàng — cả a lẫn b đều là ứng viên
		# hợp lệ của goi_y_o, khác nhau chỉ ở ô nào tem của TỪNG lô đã in.
		_gan(v, "9X120101")
		lo1 = _lo("9X-LC-2LO-01", v)
		lo2 = _lo("9X-LC-2LO-02", v)
		frappe.db.set_value("Batch", lo1, "custom_o_in_tem", a)
		frappe.db.set_value("Batch", lo2, "custom_o_in_tem", b)
		_nap(self.zzz, v, lo1, 5)
		_nap(self.zzz, v, lo2, 5)

		theo_lo = {d["so_lo"]: d["den_o"] for d in hang_chua_xep(KHO) if d["vat_tu"] == v}
		self.assertEqual(theo_lo[lo1], a)
		self.assertEqual(theo_lo[lo2], b)
		self.assertNotEqual(
			theo_lo[lo1],
			theo_lo[lo2],
			"đệm theo (mặt hàng, lô): hai lô cùng mặt hàng nhưng hai tem khác ô "
			"phải ra hai gợi ý khác nhau",
		)

	def test_van_chi_goi_goi_y_mot_lan_cho_moi_lo(self):
		"""Không được bỏ đệm đi: một kho có thể có hàng trăm dòng.

		Dựng hai dòng CÙNG (mặt hàng, lô) nhưng khác Ô NGUỒN — cần hai ô "chưa
		xếp vị trí" trong cùng kho, một tình huống biên nhưng hợp lệ về dữ
		liệu — để có hai dòng thật sự đệm được cùng một khoá, rồi đếm số lần
		`goi_y_o` bị gọi.
		"""
		from erpnext.vi_tri_kho.vitri import xep as xep_mod
		from erpnext.vi_tri_kho.vitri.xep import hang_chua_xep

		v = _vat_tu("9X-LC-CACHE-VT", co_lo=True)
		lo = _lo("9X-LC-CACHE-LO", v)
		zzz2 = "9X-ZZZ-CHUA-XEP-2"
		if not frappe.db.exists("Storage Location", zzz2):
			frappe.get_doc(
				{
					"doctype": "Storage Location",
					"ma_o": zzz2,
					"kho": KHO,
					"la_o_chua_xep": 1,
					"thu_tu_lay_hang": 9998,
				}
			).insert(ignore_permissions=True)
		_nap(self.zzz, v, lo, 3)
		_nap(zzz2, v, lo, 4)

		with patch.object(xep_mod, "goi_y_o", wraps=xep_mod.goi_y_o) as gian_diep:
			dong = [d for d in hang_chua_xep(KHO) if d["vat_tu"] == v]

		self.assertEqual(len(dong), 2, "hai ô nguồn khác nhau phải cho ra hai dòng riêng")
		# Kho thật (dữ liệu có sẵn trên site) có thể còn hàng trăm mặt hàng khác
		# đang chờ ở ô chưa xếp, nên KHÔNG đếm `call_count` tổng — phải lọc
		# đúng các lời gọi mang mặt hàng `v` của bài này rồi mới đếm.
		goi_cho_v = [c for c in gian_diep.call_args_list if c.args[0] == v]
		self.assertEqual(
			len(goi_cho_v),
			1,
			"cùng một (mặt hàng, lô) trải trên nhiều dòng chỉ được gọi goi_y_o một lần",
		)

	def test_tem_hong_dung_hang_theo_tung_dong_trong_cung_mot_lan_goi(self):
		"""Chốt của vòng sửa 2 (điều phối, sau Task 4).

		Dựng HAI mặt hàng khác nhau trong CÙNG một lần gọi `hang_chua_xep`: một
		mặt hàng có tem ĐÚNG (ô ghi trên tem còn dùng được) và một mặt hàng có
		tem HỎNG (ô ghi trên tem đã bị mặt hàng khác chiếm). Khẳng định
		`d["tem_hong"]` đúng cho TỪNG dòng.

		Đây là bài bắt đúng cả hai đột biến đã từng làm sai: (1) `tem_hong`
		hằng `True`/`False` bất kể nhánh nào (thấy ngay ở CÙNG một lần gọi vì
		có cả hàng đúng lẫn hàng hỏng); (2) suy `tem_hong` bằng so khớp chuỗi
		con "tem" trong `ly_do_goi_y` — bộ lọc đó gộp NHẦM cả hàng tem ĐÚNG
		(câu "theo ô đã in trên tem của lô…" cũng chứa chữ "tem") vào chung
		một nhóm với hàng tem HỎNG.
		"""
		from erpnext.vi_tri_kho.vitri.xep import hang_chua_xep

		v_dung = _vat_tu("9X-LC-TEMDUNG-VT", co_lo=True)
		v_hong = _vat_tu("9X-LC-TEMHONG-VT", co_lo=True)
		v_khac = _vat_tu("9X-LC-TEMHONG-CHIEM", co_lo=True)  # chiếm ô trên tem hỏng

		a = _o("9X13010101")  # ô tem ĐÚNG sẽ trỏ vào — còn trống
		c = _o("9X13020101")  # ô tem HỎNG sẽ trỏ vào — sẽ bị v_khac chiếm
		_o("9X13020102")  # ô trống cùng nhánh — trước 19/09 gợi ý rơi vào đây

		_gan(v_dung, "9X130101")
		_gan(v_hong, "9X130201")  # nhánh riêng chứa cả c lẫn d

		lo_dung = _lo("9X-LC-TEMDUNG-LO", v_dung)
		lo_hong = _lo("9X-LC-TEMHONG-LO", v_hong)
		frappe.db.set_value("Batch", lo_dung, "custom_o_in_tem", a)
		frappe.db.set_value("Batch", lo_hong, "custom_o_in_tem", c)

		lo_khac = _lo("9X-LC-TEMHONG-LO-CHIEM", v_khac)
		_nap(c, v_khac, lo_khac, 3)  # chiếm CHÍNH ô ghi trên tem của lô hỏng

		_nap(self.zzz, v_dung, lo_dung, 5)
		_nap(self.zzz, v_hong, lo_hong, 5)

		dong = {d_["vat_tu"]: d_ for d_ in hang_chua_xep(KHO) if d_["vat_tu"] in (v_dung, v_hong)}

		self.assertEqual(dong[v_dung]["den_o"], a)
		self.assertFalse(dong[v_dung]["tem_hong"], "tem đúng — KHÔNG được báo là tem hỏng")

		# Luật 19/09/2026: lô chỉ xếp vào đúng ô in trên tem. Tem hỏng thì KHÔNG
		# còn rơi sang ô khác (ô `d` mà `goi_y_o` tính ra) — để trống và nói phải
		# đổi ô trên tem, in lại tem. Cờ `tem_hong` vẫn đúng như trước.
		self.assertIsNone(dong[v_hong]["den_o"], "tem hỏng: không được tự xếp sang ô khác ô trên tem")
		self.assertIn("Đổi ô trên tem", dong[v_hong]["ly_do_goi_y"])
		self.assertTrue(dong[v_hong]["tem_hong"], "tem của lô này đã không dùng được nữa")
