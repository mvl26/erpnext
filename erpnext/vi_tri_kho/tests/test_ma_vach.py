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
	MODULE_TOI_DA,
	kiem_tra_do_dai,
	kiem_tra_ky_tu,
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

	def test_tran_module(self):
		self.assertEqual(MODULE_TOI_DA, 188)
		# 47mm / 0,25mm = 188 module. Không phải con số tròn ngẫu nhiên.
		self.assertEqual(MODULE_TOI_DA * 0.25, 47.0)

	def test_khong_con_hang_so_bo_cuc_A(self):
		"""Bố cục A đã bị bỏ (vùng yên tĩnh 2,5mm mỗi đầu không vừa cột 29,4mm).

		Khoá luôn việc hằng số của nó đã biến mất: một hằng số còn nằm đó quảng
		cáo rằng máy chủ "có hỗ trợ bố cục A" chính là thứ khiến người sau khôi
		phục bố cục đó cho giống mockup.
		"""
		from erpnext.vi_tri_kho.vitri import ma_vach

		self.assertFalse(hasattr(ma_vach, "MODULE_BO_CUC_A"))
		self.assertFalse(hasattr(ma_vach, "MODULE_BO_CUC_B"))


class TestKiemTraKyTu(FrappeTestCase):
	"""Code 128 chỉ mã hoá được ASCII.

	Vì sao phải chặn từ máy chủ chứ không để tới lúc in: JsBarcode ném lỗi,
	`frappe/form/controls/barcode.js` nuốt lỗi, và phần tử SVG giữ nguyên nội
	dung lần vẽ TRƯỚC — tem của lô này in ra mã vạch của lô liền trước, không
	một dấu hiệu nào. Đã tái hiện được trên trình duyệt.
	"""

	def test_ascii_thuan_thi_qua(self):
		for lo in ("25L4125", "LOT-2026-A45", "1B01040302", "026090374561", "A/B_C.D"):
			kiem_tra_ky_tu(lo, "lô")  # không throw

	def test_dau_tieng_viet_bi_chan(self):
		for lo in ("LÔ-2026", "25L4125Ộ", "lô25"):
			with self.assertRaises(frappe.ValidationError):
				kiem_tra_ky_tu(lo, "lô")

	def test_en_dash_bi_chan(self):
		"""`–` U+2013 — ký tự hay bị dán từ phiếu đóng gói của nhà cung cấp.

		Nó TRÔNG gần y hệt dấu trừ `-` ASCII, nên không ai soi ra bằng mắt.
		"""
		with self.assertRaises(frappe.ValidationError):
			kiem_tra_ky_tu("7Fr\u20132026", "lô")

	def test_cau_bao_neu_dich_danh_ky_tu_va_vi_tri(self):
		"""Câu báo chung chung khiến thủ kho xoá bừa vài ký tự rồi thử lại — mà
		số lô cắt bớt là số lô SAI dán lên hàng. Phải nêu đúng ký tự, đúng mã
		U+, đúng vị trí.
		"""
		with self.assertRaises(frappe.ValidationError) as ctx:
			kiem_tra_ky_tu("AB\u2013CD", "lô")
		cau = str(ctx.exception)
		self.assertIn("\u2013", cau)
		self.assertIn("U+2013", cau)
		self.assertIn("3", cau)  # vị trí ký tự vi phạm

	def test_chuoi_rong_khong_no(self):
		kiem_tra_ky_tu("", "lô")
		kiem_tra_ky_tu(None, "lô")

	def test_chuoi_rong_khong_no(self):
		"""Guard trong `so_ky_hieu` và `so_module` độc lập — nếu chỉ khoá một trong hai
		thì khi đó được xoá sẽ không ai phát hiện. Hai guard riêng biệt → hai assertion.
		"""
		self.assertEqual(so_ky_hieu(""), 0)
		self.assertEqual(so_module(""), 0)


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

	def test_ba_con_so_gioi_han_26_23_13_khoa_nguon(self):
		"""Ba con số 26/23/13 trong câu throw không được để cứng (không suy ra từ code).

		Nếu sau này `X_MM` hay bề rộng vùng in đổi nhưng quên sửa câu báo, bài này
		sẽ ĐỐ — đó là mục đích. Bài test khẳng định hành vi tính toán thực tế mà
		câu báo dựa vào.
		"""
		# 26 chữ số (chẵn) = 13 ký hiệu = 35 + 11*13 = 178 module < 188 ✓
		kiem_tra_do_dai("0" * 26, "mã")
		# 28 chữ số (chẵn) = 14 ký hiệu = 35 + 11*14 = 189 module > 188 ✗
		with self.assertRaises(frappe.ValidationError):
			kiem_tra_do_dai("0" * 28, "mã")

		# 23 chữ số (lẻ) = 2 + 11 = 13 ký hiệu = 178 module < 188 ✓
		kiem_tra_do_dai("1" * 23, "mã")
		# 25 chữ số (lẻ) = 2 + 12 = 14 ký hiệu = 189 module > 188 ✗
		with self.assertRaises(frappe.ValidationError):
			kiem_tra_do_dai("1" * 25, "mã")

		# 13 ký tự có chữ = 13 ký hiệu = 178 module < 188 ✓
		kiem_tra_do_dai("A" * 13, "mã")
		# 14 ký tự có chữ = 14 ký hiệu = 189 module > 188 ✗
		with self.assertRaises(frappe.ValidationError):
			kiem_tra_do_dai("A" * 14, "mã")
