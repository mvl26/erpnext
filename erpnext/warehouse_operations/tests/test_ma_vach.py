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

from erpnext.warehouse_operations.vitri.ma_vach import (
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
		from erpnext.warehouse_operations.vitri import ma_vach

		self.assertFalse(hasattr(ma_vach, "MODULE_BO_CUC_A"))
		self.assertFalse(hasattr(ma_vach, "MODULE_BO_CUC_B"))

	def test_chuoi_rong_khong_no(self):
		"""Guard trong `so_ky_hieu` và `so_module` độc lập — nếu chỉ khoá một trong hai
		thì khi đó được xoá sẽ không ai phát hiện. Hai guard riêng biệt → hai assertion.
		"""
		self.assertEqual(so_ky_hieu(""), 0)
		self.assertEqual(so_module(""), 0)

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

	def test_chuoi_rong_va_none_khong_no(self):
		"""Tên phải KHÁC `TestSoModule.test_chuoi_rong_khong_no`.

		Hai phương thức trùng tên trong cùng một lớp thì định nghĩa sau GHI ĐÈ
		định nghĩa trước trong class dict — bài trước biến mất mà suite vẫn
		xanh, không gì báo. Đúng cái bẫy "khoá trùng nuốt khoá" mà chú thích
		trong `hooks.py` cảnh báo cho `doc_events`, lần này ở tầng test.
		"""
		kiem_tra_ky_tu("", "lô")
		kiem_tra_ky_tu(None, "lô")

class TestKiemTraDoDai(FrappeTestCase):
	def test_vua_bo_cuc_b_thi_qua(self):
		kiem_tra_do_dai("A" * 13, "lô")  # 178 module

	def test_vuot_bo_cuc_b_thi_throw(self):
		with self.assertRaises(frappe.ValidationError):
			kiem_tra_do_dai("A" * 14, "lô")  # 189 module

	def test_cau_bao_noi_ro_gioi_han(self):
		"""Câu báo phải nói ĐANG bao nhiêu và ĐƯỢC bao nhiêu (ký tự).

		Chốt âm cho lớp lỗi 'màn hình nói sai sự thật' đã dính hai lần trong dự
		án: một câu chung chung kiểu 'số lô quá dài' khiến thủ kho cắt bừa vài ký
		tự rồi thử lại, mà số lô cắt bớt là số lô SAI dán lên hàng.
		"""
		try:
			kiem_tra_do_dai("A" * 20, "lô")
		except frappe.ValidationError as e:
			cau = str(e)
			self.assertIn("20 ký tự", cau)  # đang có
			self.assertIn("13 ký tự", cau)  # được tối đa
			self.assertIn("không in được", cau)
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


class TestKiemSoLoKhiNhap(FrappeTestCase):
	"""`kiem_so_lo` — màn hình Phiếu nhập lô báo NGAY khi gõ xong số lô (22/09/2026).

	Phải nói ĐÚNG như `validate` lúc lưu, và KHÔNG ném lỗi: ném thì `frappe.throw`
	đã đẩy câu vào `message_log` trước, trình duyệt bật hộp lỗi thứ hai chồng lên
	câu báo của màn hình.
	"""

	def test_so_lo_that_17_ky_tu_co_chu_bi_bao(self):
		from erpnext.warehouse_operations.vitri.ma_vach import kiem_so_lo

		kq = kiem_so_lo("240311(9A-12 21G)")
		self.assertEqual(kq["so_ky_tu"], 17)
		self.assertIn("13 ký tự nếu có chữ", kq["loi"])
		self.assertIn("không in được", kq["loi"])

	def test_vua_gioi_han_thi_khong_bao(self):
		from erpnext.warehouse_operations.vitri.ma_vach import kiem_so_lo

		self.assertIsNone(kiem_so_lo("A" * 13)["loi"])
		self.assertIsNone(kiem_so_lo("1" * 26)["loi"])
		self.assertIsNone(kiem_so_lo("")["loi"])

	def test_ky_tu_bao_truoc_do_dai(self):
		"""Cùng thứ tự với `BatchEntry.kiem_tra_so_lo`: số lô vừa có dấu vừa quá dài
		thì việc phải làm là gõ lại không dấu — báo độ dài trước là xui cắt bớt."""
		from erpnext.warehouse_operations.vitri.ma_vach import kiem_so_lo

		kq = kiem_so_lo("LÔ-" + "A" * 20)
		self.assertIn("U+00D4", kq["loi"])

	def test_khong_nem_loi_khong_de_lai_message_log(self):
		from erpnext.warehouse_operations.vitri.ma_vach import kiem_so_lo

		truoc = len(frappe.local.message_log)
		kiem_so_lo("240311(9A-12 21G)")
		self.assertEqual(len(frappe.local.message_log), truoc)

	def test_cau_bao_giong_het_luc_luu(self):
		from erpnext.warehouse_operations.vitri.ma_vach import kiem_so_lo

		cau = kiem_so_lo("240311(9A-12 21G)")["loi"]
		with self.assertRaises(frappe.ValidationError) as ctx:
			kiem_tra_do_dai("240311(9A-12 21G)", "lô")
		self.assertEqual(str(ctx.exception), cau)


class TestTranGoTrenManHinh(FrappeTestCase):
	"""Màn hình Phiếu nhập lô chặn GÕ quá trần (`batch_entry.js`, 22/09/2026) bằng
	một hằng viết cứng. Hằng đó phải khớp trần suy từ `ma_vach.py` — nếu ai đổi
	khổ tem hay bề rộng vạch ở đây mà quên sửa màn hình, màn hình sẽ chặn sai
	(cho gõ một số lô mà lúc Lưu lại bị từ chối, hoặc chặn oan)."""

	def test_hang_tren_man_hinh_khop_tran_ma_vach(self):
		import os
		import re

		import erpnext

		duong = os.path.join(
			os.path.dirname(erpnext.__file__),
			"warehouse_operations",
			"doctype",
			"batch_entry",
			"batch_entry.js",
		)
		with open(duong, encoding="utf-8") as f:
			js = f.read()
		co_chu = int(re.search(r"const TOI_DA_CO_CHU = (\d+);", js).group(1))
		chu_so = int(re.search(r"const TOI_DA_CHU_SO = (\d+);", js).group(1))

		# Có chữ: ký tự thứ `co_chu` còn vừa, thứ `co_chu + 1` thì không.
		self.assertLessEqual(so_module("A" * co_chu), MODULE_TOI_DA)
		self.assertGreater(so_module("A" * (co_chu + 1)), MODULE_TOI_DA)
		# Toàn chữ số: độ dài `chu_so` còn vừa, và là độ dài lớn nhất còn vừa.
		self.assertLessEqual(so_module("1" * chu_so), MODULE_TOI_DA)
		self.assertTrue(all(so_module("1" * n) > MODULE_TOI_DA for n in range(chu_so + 1, chu_so + 6)))
