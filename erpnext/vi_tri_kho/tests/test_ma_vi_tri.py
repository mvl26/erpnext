"""Mã vị trí 12 ký tự theo chuẩn SPD.

Nguồn: SPD_VanHanh_PhanTichMaViTriKho_20260907_v2 §5.2, xác nhận lại ở
SPD_PhanMem_DacTaNhanNhapKho_50x30_20260908_v2 trường F8.

    [Kho 2][Khu 2][Dãy 2][Khoang 2][Tầng 2][Ô 2] = K11B01040302

Lưu trong CSDL 12 ký tự KHÔNG dấu gạch; in lên nhãn dạng K11B0104-0302.

MỘT MÂU THUẪN TRONG TÀI LIỆU, ĐÃ CHỐT: §5.2 mô tả Khu là "chữ cái A–Z + số
tầng nhà" (chữ trước số) nhưng MỌI ví dụ trong cả ba tài liệu đều là SỐ trước
CHỮ (1B, 3B, 4B — kể cả ảnh chụp kho MSC). Chủ dự án chốt theo ví dụ.

Dải giá trị (§5.2): Dãy 01–99 · Khoang 01–99 · Tầng 01–09 · Ô 01–99.
Tầng chỉ tới 09 vì kệ kho không cao hơn 9 tầng — đây là ràng buộc thật, không
phải giới hạn kỹ thuật, nên regex phải cưỡng chế chứ không chỉ kiểm độ dài.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.vi_tri_kho.vitri.ma_vi_tri import dinh_dang_nhan, phan_tich_ma


class TestPhanTichMaHopLe(FrappeTestCase):
	def test_tach_dung_sau_thanh_phan(self):
		self.assertEqual(
			phan_tich_ma("K11B01040302"),
			{"ma_kho": "K1", "khu": "1B", "day": "01", "khoang": "04", "tang": "03", "o": "02"},
		)

	def test_kho_ve_tinh_benh_vien(self):
		# B1…B9 = kho vệ tinh trong bệnh viện (§5.2)
		self.assertEqual(phan_tich_ma("B93A99990901")["ma_kho"], "B9")


class TestDaiGiaTri(FrappeTestCase):
	def test_tang_khong_duoc_qua_09(self):
		with self.assertRaises(frappe.ValidationError):
			phan_tich_ma("K11B01041002")

	def test_tang_khong_duoc_bang_00(self):
		with self.assertRaises(frappe.ValidationError):
			phan_tich_ma("K11B01040002")

	def test_day_khong_duoc_bang_00(self):
		with self.assertRaises(frappe.ValidationError):
			phan_tich_ma("K11B00040302")

	def test_o_khong_duoc_bang_00(self):
		with self.assertRaises(frappe.ValidationError):
			phan_tich_ma("K11B01040300")


class TestDinhDangSai(FrappeTestCase):
	def test_thieu_ky_tu(self):
		with self.assertRaises(frappe.ValidationError):
			phan_tich_ma("K11B010403")

	def test_khu_dat_chu_truoc_so_bi_tu_choi(self):
		# "B1" thay vì "1B" — chốt theo ví dụ trong tài liệu
		with self.assertRaises(frappe.ValidationError):
			phan_tich_ma("K1B101040302")

	def test_chu_thuong_bi_tu_choi(self):
		# §1.1 quy tắc mã hoá: chỉ A–Z in hoa
		with self.assertRaises(frappe.ValidationError):
			phan_tich_ma("k11b01040302")

	def test_co_dau_gach_bi_tu_choi(self):
		# dạng có gạch là để IN, không phải để lưu
		with self.assertRaises(frappe.ValidationError):
			phan_tich_ma("K11B0104-0302")

	def test_thong_bao_loi_tieng_viet_neu_ro_mau_dung(self):
		with self.assertRaises(frappe.ValidationError) as ctx:
			phan_tich_ma("SAI")
		loi = str(ctx.exception)
		self.assertIn("12 ký tự", loi)
		self.assertIn("K11B01040302", loi)
		self.assertNotIn("Traceback", loi)


class TestDangInTrenNhan(FrappeTestCase):
	"""Mã LƯU 12 ký tự liền; mã IN có đúng một dấu gạch.

	Tài liệu có HAI dạng hiển thị cho cùng 12 ký tự: §5.2 viết
	`K1-1B01-04-0302` (ba gạch), còn trường F8 của đặc tả nhãn v2 viết
	`VT K11B0104-0302` (một gạch). Chốt theo NHÃN, vì đó là thứ dán lên kệ và
	là thứ nhân viên đọc — tài liệu nhãn cũng là bản mới hơn.
	"""

	def test_chen_dung_mot_gach_truoc_tang_o(self):
		self.assertEqual(dinh_dang_nhan("K11B01040302"), "K11B0104-0302")

	def test_ma_sai_dinh_dang_thi_tu_choi_chu_khong_in_bua(self):
		with self.assertRaises(frappe.ValidationError):
			dinh_dang_nhan("SAI")
