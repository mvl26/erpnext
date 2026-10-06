"""Kiểm cấu trúc DocType PDA Thiet Bi — tồn tại, schema đúng, permissions đúng.

Bài kiểm logic thực tế (cấp khoá, thu hồi, khoá gắn mã máy) nằm ở
`warehouse_operations/tests/test_khoa_may.py` — cùng chỗ với các bài khác của
module, đúng bảng đường dẫn trong `scripts/file_structure/gate.py`.
"""

import frappe
from frappe.tests.utils import FrappeTestCase


class TestPDAThietBiSchema(FrappeTestCase):
	def test_doctype_ton_tai_va_co_nhung_field_bat_buoc(self):
		meta = frappe.get_meta("PDA Thiet Bi")
		self.assertIsNotNone(meta, "DocType PDA Thiet Bi phải tồn tại")
		co = {f.fieldname for f in meta.fields}
		self.assertTrue(
			{"nguoi_dung", "ten_may", "ma_may", "cap_luc", "lan_dung_cuoi", "con_hieu_luc", "ghi_chu"} <= co,
			f"thiếu field bắt buộc (spec §6): {co}",
		)

	def test_ma_may_unique_va_la_ten_ban_ghi(self):
		"""`ma_may` vừa phải DUY NHẤT vừa phải là tên bản ghi: hook kiểm khoá máy tra
		theo mã này, hai dòng cùng mã là hai câu trả lời cho cùng một câu hỏi."""
		meta = frappe.get_meta("PDA Thiet Bi")
		self.assertEqual(meta.autoname, "field:ma_may")
		self.assertTrue(meta.get_field("ma_may").unique, "ma_may phải unique = 1")

	def test_khong_co_field_nao_giu_BI_MAT(self):
		"""Doctype này giữ ĐỊNH DANH của khoá, KHÔNG giữ BÍ MẬT — và phân biệt ấy là có
		thật, không phải chơi chữ.

		`api_key` là thứ `validate_api_key_secret` dùng để TRA RA người dùng, y như một
		tên đăng nhập; một mình nó không đăng nhập được, vì vẫn phải khớp `api_secret`
		giải mã từ bảng `__Auth`. (Kiểm được ngay trên site này: `bvbm@demo.miyano` có
		một `api_secret` mồ côi trong `__Auth` mà `api_key = None` — và nó vô dụng, đúng
		vì phép tra đi theo `api_key`.) Vì vậy vòng sửa 1 CỐ Ý thêm `api_key_da_cap`: có
		nó thì thu hồi mới xoá đúng chiếc khoá do PDA cấp thay vì giết khoá tích hợp của
		người khác.

		Cái tuyệt đối không được có là **bí mật đọc ngược ra được**. Vòng sửa 2 siết lại
		danh sách cấm cho đúng điều đó: cấm những cái tên chỉ một bí mật **thuận nghịch**
		(`secret`, `token`, `password`, `mat_khau`), và **không** cấm hậu tố `_bam` —
		`bi_mat_bam` là SHA-256 có muối của `api_secret`, cùng đúng kỹ thuật mà
		`PDA Badge.ma_bam` đã dùng cho mã thẻ từ 23/09; cấm nó là cấm chính cách duy
		nhất phân biệt được ca "nhận máy trước, xoay khoá sau" mà không lưu bí mật.

		**BÀI NÀY MỘT MÌNH LÀ HÀNG RÀO GIẢ — người soát đã chứng minh:** cho
		`_ghi_thiet_bi` ghi cả `api_key + ":" + api_secret` vào một trường tên vô hại thì
		bài này vẫn xanh. Hàng rào thật là bài so **GIÁ TRỊ** trên toàn bộ JSON bản ghi
		(`tests/test_khoa_may.py::test_khong_luu_BI_MAT_vao_pda_thiet_bi`). Giữ cả hai;
		đừng bao giờ coi bài tên trường là bằng chứng."""
		meta = frappe.get_meta("PDA Thiet Bi")
		cam = ("secret", "token", "password", "mat_khau")
		xau = [f.fieldname for f in meta.fields if any(t in f.fieldname.lower() for t in cam)]
		self.assertEqual(xau, [], f"PDA Thiet Bi không được có field giữ BÍ MẬT: {xau}")
		# Hai trường băm PHẢI kín: hiện ra hoặc sao chép được là mời người ta đem đi dò.
		for ten in ("bi_mat_bam", "muoi_khoa"):
			f = meta.get_field(ten)
			self.assertIsNotNone(f, f"thiếu {ten} thì thu hồi không phân biệt được khoá xoay-sau")
			self.assertTrue(f.hidden and f.read_only and f.no_copy, f"{ten} phải hidden+read_only+no_copy")

	def test_co_du_field_ghi_xuat_xu_khoa(self):
		"""Thiếu một trong hai thì `thu_hoi` lại xoá khoá vô điều kiện như trước vòng sửa 1."""
		meta = frappe.get_meta("PDA Thiet Bi")
		co = {f.fieldname for f in meta.fields}
		self.assertIn("api_key_da_cap", co)
		self.assertIn("khoa_von_co_truoc", co)
		self.assertTrue(meta.get_field("api_key_da_cap").read_only, "không ai được sửa tay xuất xứ khoá")
		self.assertTrue(meta.get_field("khoa_von_co_truoc").read_only)

	def test_permissions_dung_cho_system_manager_stock_manager(self):
		meta = frappe.get_meta("PDA Thiet Bi")
		co_quyen = {p.role for p in meta.permissions if p.read}
		self.assertEqual(
			co_quyen,
			{"System Manager", "Stock Manager"},
			f"quyền đọc phải đúng tập VAI_TRO_QUAN_LY_THE, thực tế: {co_quyen}",
		)

	def test_permissions_khop_voi_vai_tro_quan_ly_the(self):
		"""Khoá bằng chính hằng số, không bằng hai chuỗi gõ tay: `the_pda` đổi tập vai
		trò mà JSON đứng yên thì trưởng kho mất chỗ bấm thu hồi."""
		from erpnext.warehouse_operations.vitri.the_pda import VAI_TRO_QUAN_LY_THE

		meta = frappe.get_meta("PDA Thiet Bi")
		self.assertEqual({p.role for p in meta.permissions if p.write}, VAI_TRO_QUAN_LY_THE)
