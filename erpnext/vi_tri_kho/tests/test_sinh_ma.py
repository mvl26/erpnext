"""Sinh mã ô hàng loạt theo chuẩn 10 ký tự SPD.

Định dạng do BA chốt (`SPD_VanHanh_PhanTichMaViTriKho_20260907_v2` §5.2), nên
bộ sinh KHÔNG còn ô "mẫu mã tự do": để người dùng tự chế mẫu là mở đường lệch
chuẩn, mà mã ô thì khoá cứng sau khi tạo và đã in lên tem.

MỘT ĐIỀU MẤT ĐI KHI ĐỔI SANG ĐỊNH DẠNG CỐ ĐỊNH, nói thẳng ở đây thay vì giả
vờ còn: bản cũ có bài khoá `thu_tu_lay_hang` được gán theo THỨ TỰ SINH chứ
không theo thứ tự SẮP TÊN, dựng được vì mẫu mã tự do cho phép hai thứ tự lệch
nhau. Với định dạng cố định, mã sinh ra theo dãy→khoang→tầng→ô nên thứ tự sinh
và thứ tự chữ cái LUÔN trùng nhau — không còn cách nào phân biệt hai cài đặt
đó bằng test. Bài dưới chỉ khoá được "tăng dần theo thứ tự sinh".

BỎ TIỀN ĐỀ `custom_ma_kho_spd` (Task 1, 2026-09-11): mã ô bỏ 2 ký tự mã kho
nên bộ sinh không còn đọc trường đó của Warehouse nữa — lớp `_CoTienDe` khoá
tiền đề này ở bản 12 ký tự đã bị gỡ cùng lúc; giữ lại sẽ đỏ vì một lý do sai.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.vi_tri_kho.vitri.ma_vi_tri import phan_tich_ma
from erpnext.vi_tri_kho.vitri.sinh_ma import sinh, xem_truoc_sinh

KHO = "Kho Miyano - MYN"
KHACH = "bvminhduc@demo.miyano"


class TestSinhDungChuan(FrappeTestCase):
	def test_dung_so_o_bang_tich_bon_chieu(self):
		kq = sinh(KHO, khu="8A", so_day=2, so_khoang_moi_day=2, so_tang_moi_khoang=2, so_o_moi_tang=2)
		self.assertEqual(kq["so_o_da_tao"], 16)

	def test_ma_dung_10_ky_tu_va_tach_duoc(self):
		sinh(KHO, khu="8B", so_day=1, so_khoang_moi_day=1, so_tang_moi_khoang=1, so_o_moi_tang=1)
		self.assertTrue(frappe.db.exists("Storage Location", "8B01010101"))
		self.assertEqual(
			phan_tich_ma("8B01010101"),
			{"khu": "8B", "day": "01", "khoang": "01", "tang": "01", "o": "01"},
		)

	def test_khu_sinh_ra_khop_qua_trong_tai_doc_lap(self):
		"""Trọng tài ĐỘC LẬP với công thức dựng chuỗi trong `sinh_ma.py`.

		Bản trước (`kq["ma_mau"][0].startswith("8C")`) so chuỗi kết quả với
		chính chuỗi "8C" đã truyền vào — hai vế cùng đi qua một f-string thuần
		trong `sinh_ma.py`, tức cùng một nguồn, nên bài xanh bất kể logic đúng
		sai (Vòng sửa 1, review điều phối). Ở đây dùng `phan_tich_ma()` — bộ
		regex của `ma_vi_tri.py`, một đường code KHÁC — làm trọng tài: mọi mã
		sinh ra phải qua được nó (đúng định dạng đủ 5 thành phần) VÀ thành
		phần `khu` nó tách ra phải khớp khu đã truyền vào. Sinh 2 ô (so_day=2)
		để trọng tài xét hơn một mã, không chỉ mã đầu.
		"""
		kq = xem_truoc_sinh(
			KHO, khu="8C", so_day=2, so_khoang_moi_day=1, so_tang_moi_khoang=1, so_o_moi_tang=1
		)
		self.assertEqual(kq["so_o"], 2)
		for ma in kq["ma_mau"]:
			self.assertEqual(phan_tich_ma(ma)["khu"], "8C")

	def test_thu_tu_lay_hang_tang_dan_theo_thu_tu_sinh(self):
		sinh(KHO, khu="8D", so_day=1, so_khoang_moi_day=1, so_tang_moi_khoang=1, so_o_moi_tang=3)
		tt = [
			frappe.db.get_value("Storage Location", f"8D010101{i:02d}", "thu_tu_lay_hang") for i in (1, 2, 3)
		]
		self.assertEqual(tt, sorted(tt), "thứ tự lấy hàng phải tăng theo thứ tự sinh")
		self.assertEqual(len(set(tt)), 3, "mỗi ô một số khác nhau")


class TestChanDauVaoSai(FrappeTestCase):
	def test_khu_sai_dinh_dang_bi_bao_ro(self):
		# Khu phải là SỐ rồi CHỮ (1B, 3B, 4B) — xem docstring ma_vi_tri.py
		with self.assertRaises(frappe.ValidationError):
			xem_truoc_sinh(
				KHO, khu="A8", so_day=1, so_khoang_moi_day=1, so_tang_moi_khoang=1, so_o_moi_tang=1
			)

	def test_tang_qua_09_bi_bao_ro(self):
		with self.assertRaises(frappe.ValidationError):
			xem_truoc_sinh(
				KHO, khu="8F", so_day=1, so_khoang_moi_day=1, so_tang_moi_khoang=10, so_o_moi_tang=1
			)


class TestXemTruocKhongGhi(FrappeTestCase):
	def test_khong_ghi_gi(self):
		truoc = frappe.db.count("Storage Location")
		xem_truoc_sinh(KHO, khu="8G", so_day=2, so_khoang_moi_day=2, so_tang_moi_khoang=2, so_o_moi_tang=2)
		self.assertEqual(frappe.db.count("Storage Location"), truoc)


class TestTrungMaThiKhongGhiONao(FrappeTestCase):
	def test_trung_o_giua_batch_khong_ghi_o_nao(self):
		"""Kịch bản "sinh 40 ô rồi vỡ ở ô 41" mà tài liệu §5.3 lấy làm ví dụ.

		Mã trùng đặt ở GIỮA (ô thứ 3/5), không phải đầu — nếu đặt đầu thì
		`insert()` vỡ ngay bản ghi đầu và bài xanh VÌ LÝ DO SAI.
		"""
		giua = "8H01030101"
		frappe.get_doc({"doctype": "Storage Location", "ma_o": giua, "kho": KHO}).insert(
			ignore_permissions=True
		)
		with self.assertRaises(frappe.ValidationError):
			sinh(KHO, khu="8H", so_day=1, so_khoang_moi_day=5, so_tang_moi_khoang=1, so_o_moi_tang=1)
		for i in (1, 2, 4, 5):
			self.assertFalse(
				frappe.db.exists("Storage Location", f"8H01{i:02d}0101"),
				f"khoang {i} không được ghi — kể cả ô đứng SAU vị trí trùng",
			)


class TestKiemQuyen(FrappeTestCase):
	def test_khach_hang_cong_bi_chan_o_ca_hai_ham(self):
		self.assertTrue(frappe.db.exists("User", KHACH), f"tiền đề: cần tài khoản {KHACH}")
		try:
			frappe.set_user(KHACH)
			for fn in (xem_truoc_sinh, sinh):
				with self.assertRaises(frappe.PermissionError):
					fn(KHO, khu="8I", so_day=1, so_khoang_moi_day=1, so_tang_moi_khoang=1, so_o_moi_tang=1)
		finally:
			frappe.set_user("Administrator")
