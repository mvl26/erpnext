"""Mã vị trí 10 ký tự theo chuẩn SPD của Miyano Việt Nam.

    [Khu 2][Dãy 2][Khoang 2][Tầng 2][Ô 2]  →  1B01040302

Nguồn: `SPD_VanHanh_PhanTichMaViTriKho_20260907_v2` §5.2, xác nhận lại ở
`SPD_PhanMem_DacTaNhanNhapKho_50x30_20260908_v2` trường F8.

Khu viết SỐ trước CHỮ (1B, 3B, 4B). §5.2 mô tả bằng lời là "chữ cái A-Z + số
tầng nhà" nhưng mọi ví dụ trong cả ba tài liệu — kể cả ảnh chụp kho MSC — đều
ngược lại. Chủ dự án chốt theo ví dụ (10/09/2026).

Bỏ 2 ký tự mã kho (Task 1, 2026-09-11): bản ghi `Storage Location` đã có
trường `kho` trỏ `Warehouse`; lưu thêm mã kho trong CHÍNH mã ô là hai nguồn
sự thật cho cùng một thông tin, dễ lệch. `cap_do()` và `ma_cha()` là nền cho
cây vị trí ở Task 2: mỗi cấp là tiền tố của cấp sau nên mã cha luôn là
`ma[:-2]`, không cần bảng tra nào.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.vi_tri_kho.vitri.ma_vi_tri import cap_do, dinh_dang_nhan, ma_cha, phan_tich_ma


class TestPhanTichMa(FrappeTestCase):
	def test_tach_du_nam_thanh_phan(self):
		self.assertEqual(
			phan_tich_ma("1B01040302"),
			{"khu": "1B", "day": "01", "khoang": "04", "tang": "03", "o": "02"},
		)

	def test_dung_10_ky_tu(self):
		# 12 ký tự là chuẩn CŨ — phải bị từ chối, không được "vẫn nhận cho lành"
		with self.assertRaises(frappe.ValidationError):
			phan_tich_ma("K11B01040302")

	def test_chan_so_khong(self):
		for sai in ("1B00040302", "1B01000302", "1B01040002", "1B01040300"):
			with self.assertRaises(frappe.ValidationError):
				phan_tich_ma(sai)

	def test_tang_toi_da_09(self):
		phan_tich_ma("1B01040902")
		with self.assertRaises(frappe.ValidationError):
			phan_tich_ma("1B01041002")

	def test_khu_so_truoc_chu(self):
		phan_tich_ma("1B01040302")
		with self.assertRaises(frappe.ValidationError):
			phan_tich_ma("B101040302")

	def test_in_nhan(self):
		self.assertEqual(dinh_dang_nhan("1B01040302"), "1B0104-0302")

	def test_in_nhan_vua_gioi_han_nhan(self):
		# Trường F8 của đặc tả nhãn 50x30 v2 giới hạn 16 ký tự kể cả tiền tố
		self.assertLessEqual(len("VT " + dinh_dang_nhan("1B01040302")), 16)

	def test_cap_do(self):
		self.assertEqual(cap_do("1B"), 1)
		self.assertEqual(cap_do("1B01"), 2)
		self.assertEqual(cap_do("1B0104"), 3)
		self.assertEqual(cap_do("1B010403"), 4)
		self.assertEqual(cap_do("1B01040302"), 5)

	def test_cap_do_chan_ma_sai(self):
		for sai in ("1B0", "1B0104030222", "XX"):
			with self.assertRaises(frappe.ValidationError):
				cap_do(sai)

	def test_ma_cha(self):
		self.assertEqual(ma_cha("1B01040302"), "1B010403")
		self.assertEqual(ma_cha("1B01"), "1B")
		self.assertIsNone(ma_cha("1B"), "Khu là gốc, không có cha")

	def test_thong_bao_loi_tieng_viet_neu_ro_mau_dung(self):
		with self.assertRaises(frappe.ValidationError) as ctx:
			phan_tich_ma("SAI")
		loi = str(ctx.exception)
		self.assertIn("10 ký tự", loi)
		self.assertIn("1B01040302", loi)
		self.assertNotIn("Traceback", loi)
