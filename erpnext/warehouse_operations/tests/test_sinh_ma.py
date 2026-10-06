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

from erpnext.warehouse_operations.vitri.ma_vi_tri import phan_tich_ma
from erpnext.warehouse_operations.vitri.sinh_ma import sinh, xem_truoc_sinh

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

	def test_tap_ma_sinh_dung_tich_descartes(self):
		"""Vế đối chiếu dựng TAY, không gọi bất kỳ hàm nào của `sinh_ma`/`ma_vi_tri`.

		Vòng sửa 2 (review điều phối): bản Vòng sửa 1 dùng `phan_tich_ma()["khu"]`
		làm "trọng tài", nhưng đó vẫn là `ma[0:2]` — đúng phép toán mà
		`.startswith()` bản gốc đã làm, chỉ viết khác đi — và `phan_tich_ma`
		không hề độc lập với SUT: `_liet_ke()` trong chính `sinh_ma.py` cũng gọi
		nó để tự soi mã đầu tiên. `khu` đi thẳng từ tham số vào chuỗi, không qua
		phép biến đổi nào đáng kể nên gần như không đáng một bài riêng — thứ
		ĐÁNG khoá là TOÀN BỘ tập mã: cận vòng lặp, đệm số 0, và thứ tự ghép bốn
		chiều dãy→khoang→tầng→ô. Ở đây dựng cả tập `mong_doi` bằng một tích
		Descartes viết tay trong TEST, so thẳng với `kq["ma_mau"]` — không đường
		code sản xuất nào tham gia vế phải.

		Cố ý chọn 4 chiều KHÔNG bằng nhau (2x3x2x1, không phải 2x2x2x2) để một
		đột biến hoán vị khoang<->tầng cũng bị bắt — nếu hai chiều bằng nhau, hoán
		vị chúng cho ra đúng tập mã cũ, bài sẽ không bắt được kiểu lỗi đó.
		"""
		kq = xem_truoc_sinh(
			KHO, khu="8C", so_day=2, so_khoang_moi_day=3, so_tang_moi_khoang=2, so_o_moi_tang=1
		)
		mong_doi = {
			f"8C{d:02d}{k:02d}{t:02d}{o:02d}"
			for d in range(1, 3)
			for k in range(1, 4)
			for t in range(1, 3)
			for o in range(1, 2)
		}
		self.assertEqual(kq["so_o"], 12)
		self.assertEqual(set(kq["ma_mau"]), mong_doi)

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
