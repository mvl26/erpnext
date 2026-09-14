"""Phiếu xếp / chuyển vị trí — spec 2026-09-14.

Bài học đắt nhất của module này: một phép kiểm sai làm lệch tồn theo Ô mà
TỔNG vẫn đúng, nên `doi_soat` vẫn báo khớp và không gì bật lên. Vì vậy gần
như mọi bài ở đây có CHỐT ÂM đi kèm — khẳng định cả cái phải đổi lẫn cái
phải còn nguyên.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

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


def _phieu(dong, kho=KHO, **kw):
	"""Dựng phiếu CHƯA lưu. `dong` là list dict(vat_tu, so_lo, tu_o, den_o, so_luong)."""
	return frappe.get_doc({"doctype": "Location Transfer", "kho": kho, "items": dong, **kw})


class TestPhepKiemCoBan(FrappeTestCase):
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
		"""Đối chứng: mọi phép kiểm trên CHỈ chặn cái sai."""
		p = _phieu(self._dong())
		p.insert(ignore_permissions=True)
		p.submit()
		self.assertEqual(p.docstatus, 1)
