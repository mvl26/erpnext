"""Đếm module Code 128 (spec khối C §6.4).

Vì sao phải có module riêng cho một phép tính ba dòng: con số này quyết định
CẢ phép kiểm lúc nhập lô LẪN việc nhãn chọn bố cục nào. Hai bản cài đặt thì
một ngày nào đó `validate` cho qua một số lô mà nhãn không vẽ nổi — và phát
hiện ra lúc tem đã in.

Con số đã được xác nhận bằng tay: `25L4125` (7 ký tự có chữ) ra đúng 112 module
= 28,00 mm, khớp bề rộng cột trái của bố cục A.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.vi_tri_kho.vitri.ma_vach import (
	MODULE_BO_CUC_A,
	MODULE_BO_CUC_B,
	kiem_tra_do_dai,
	so_ky_hieu,
	so_module,
)


class TestSoModule(FrappeTestCase):
	def test_chuoi_co_chu_moi_ky_tu_mot_ky_hieu(self):
		self.assertEqual(so_ky_hieu("25L4125"), 7)
		self.assertEqual(so_module("25L4125"), 112)

	def test_chu_so_do_dai_chan_hai_chu_so_mot_ky_hieu(self):
		self.assertEqual(so_ky_hieu("026090374561"), 6)
		self.assertEqual(so_module("026090374561"), 101)

	def test_chu_so_do_dai_le_ton_them_hai_ky_hieu(self):
		"""Đây là chỗ bản nháp spec đã tính SAI một lần.

		Code 128 không có cách mã hoá một số lẻ chữ số trong bộ C. Chuỗi lẻ phải
		mã hoá chữ số đầu bằng bộ B rồi chèn một ký hiệu chuyển sang bộ C — tốn
		HAI ký hiệu chứ không phải làm tròn lên một. Bỏ qua chỗ này thì 13 chữ số
		lẻ bị tính là vừa 112 module trong khi thực tế là 134.
		"""
		self.assertEqual(so_ky_hieu("1" * 11), 7)
		self.assertEqual(so_module("1" * 11), 112)
		self.assertEqual(so_ky_hieu("1" * 13), 8)
		self.assertEqual(so_module("1" * 13), 123)

	def test_tran_bo_cuc(self):
		self.assertEqual(MODULE_BO_CUC_A, 112)
		self.assertEqual(MODULE_BO_CUC_B, 188)
		# 47mm / 0,25mm = 188 module. Không phải con số tròn ngẫu nhiên.
		self.assertEqual(MODULE_BO_CUC_B * 0.25, 47.0)

	def test_chuoi_rong_khong_no(self):
		self.assertEqual(so_ky_hieu(""), 0)


class TestKiemTraDoDai(FrappeTestCase):
	def test_vua_bo_cuc_b_thi_qua(self):
		kiem_tra_do_dai("A" * 13, "lô")  # 178 module

	def test_vuot_bo_cuc_b_thi_throw(self):
		with self.assertRaises(frappe.ValidationError):
			kiem_tra_do_dai("A" * 14, "lô")  # 189 module

	def test_cau_bao_noi_ro_gioi_han(self):
		"""Câu báo phải nói ĐANG bao nhiêu và ĐƯỢC bao nhiêu.

		Chốt âm cho lớp lỗi 'màn hình nói sai sự thật' đã dính hai lần trong dự
		án: một câu chung chung kiểu 'số lô quá dài' khiến thủ kho cắt bừa vài ký
		tự rồi thử lại, mà số lô cắt bớt là số lô SAI dán lên hàng.
		"""
		try:
			kiem_tra_do_dai("A" * 20, "lô")
		except frappe.ValidationError as e:
			cau = str(e)
			self.assertIn("255", cau)  # module đang có
			self.assertIn("188", cau)  # trần
		else:
			self.fail("phải throw")
