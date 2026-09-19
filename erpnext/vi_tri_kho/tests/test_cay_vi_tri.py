"""Cây vị trí là HÌNH CHIẾU của mã, không phải dữ liệu độc lập.

Mọi bài ở đây khoá đúng một điều: không tồn tại thao tác nào của người dùng
đặt được cây lệch khỏi mã. Đó là lý do spec 2026-09-09 từng bỏ cây đi, và là
điều kiện để dựng lại nó.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

KHO = "Kho Miyano - MYN"


def _o(ma):
	if not frappe.db.exists("Storage Location", ma):
		frappe.get_doc({"doctype": "Storage Location", "ma_o": ma, "kho": KHO}).insert(
			ignore_permissions=True
		)
	return ma


class TestCaySuyTuMa(FrappeTestCase):
	def test_tu_sinh_du_to_tien(self):
		"""RÀ TOÀN NHÁNH: tiền đề "chưa có nút cha nào" phải TỰ bài này dựng,
		không mượn của bài khác. Bản trước dùng tiền tố "9Z18..." — trùng
		với `test_cha_dung_theo_ma`, chạy TRƯỚC theo thứ tự alphabet
		(`test_cha_...` < `test_tu_sinh_...`) và đã tạo đủ 4 tổ tiên; `_o()`
		có guard `if not exists` nên lần gọi ở đây là no-op — bài chỉ đang
		khẳng định lại thứ BÀI KIA tạo ra, tiền đề "chưa có nút cha nào"
		không bao giờ đúng. Đổi sang tiền tố "9Q18..." — không bài nào khác
		trong file này đụng tới — và khẳng định tường minh tiền đề TRƯỚC khi
		lưu, để một khi ai đó lại vô tình dùng chung tiền tố, bài này tự báo
		đỏ ở đúng chỗ thay vì âm thầm xanh giả.
		"""
		to_tien = ("9Q", "9Q18", "9Q1801", "9Q180101")
		for cha in to_tien:
			self.assertFalse(
				frappe.db.exists("Storage Location", cha),
				f"tiền đề: nút {cha} phải CHƯA tồn tại trước khi lưu ô lá — nếu đỏ ở "
				"đây, một bài khác đã dùng chung tiền tố 9Q18 và làm hỏng tiền đề",
			)
		_o("9Q18010101")
		for cha in to_tien:
			self.assertTrue(frappe.db.exists("Storage Location", cha), f"thiếu nút {cha}")

	def test_cha_dung_theo_ma(self):
		_o("9Z18010101")
		self.assertEqual(
			frappe.db.get_value("Storage Location", "9Z18010101", "parent_storage_location"),
			"9Z180101",
		)

	def test_nut_nhom_la_is_group(self):
		_o("9Z18010101")
		for cha in ("9Z", "9Z18", "9Z1801", "9Z180101"):
			self.assertTrue(frappe.db.get_value("Storage Location", cha, "is_group"), cha)
		self.assertFalse(
			frappe.db.get_value("Storage Location", "9Z18010101", "is_group"),
			"ô lá không được là nút nhóm",
		)

	def test_sua_tay_cha_bi_ghi_de_ve_dung(self):
		"""`parent` là read_only trên form, nhưng API vẫn đặt được — chặn ở validate."""
		_o("9Z18010101")
		_o("9Z18020101")
		d = frappe.get_doc("Storage Location", "9Z18010101")
		d.parent_storage_location = "9Z180201"  # sai: thuộc dãy 02
		d.save(ignore_permissions=True)
		self.assertEqual(
			frappe.db.get_value("Storage Location", "9Z18010101", "parent_storage_location"),
			"9Z180101",
			"cha phải được tính lại từ mã, không nhận giá trị người dùng đặt",
		)

	def test_o_chua_xep_dung_ngoai_cay(self):
		from erpnext.vi_tri_kho.vitri.bat_kho import tao_o_chua_xep

		ma = tao_o_chua_xep(KHO)
		self.assertIsNone(
			frappe.db.get_value("Storage Location", ma, "parent_storage_location"),
			"ô hệ thống không thuộc cây — nó không ứng với chỗ nào ngoài kho",
		)

	def test_nut_nhom_khong_bi_ep_dinh_dang_o_la(self):
		"""Nút nhóm có mã 2/4/6/8 ký tự — không được đòi đủ 10."""
		_o("9Z18010101")
		self.assertEqual(frappe.db.get_value("Storage Location", "9Z18", "ma_o"), "9Z18")

	def test_ma_sai_cap_bi_chan(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({"doctype": "Storage Location", "ma_o": "9Z180", "kho": KHO}).insert(
				ignore_permissions=True
			)

	def test_xoa_o_la_dong_lai_khoang_lft_rgt(self):
		"""ĐIỀU PHỐI F1: `on_trash` phải gọi `super().on_trash()` — không thì xoá một ô
		lá để lại một khoảng `lft/rgt` mồ côi trong cha, không ai báo lỗi.
		"""
		_o("9Z19010101")
		truoc = frappe.db.get_value("Storage Location", "9Z190101", ["lft", "rgt"], as_dict=True)
		frappe.delete_doc("Storage Location", "9Z19010101", ignore_permissions=True)
		sau = frappe.db.get_value("Storage Location", "9Z190101", ["lft", "rgt"], as_dict=True)
		self.assertEqual(
			sau.rgt - sau.lft,
			truoc.rgt - truoc.lft - 2,
			"xoá ô lá phải đóng lại khoảng lft/rgt của cha, không để khoảng mồ côi",
		)

	def test_khong_xoa_duoc_nut_nhom_con_con(self):
		"""ĐIỀU PHỐI F1: `super().on_trash()` tự chặn xoá một nút nhóm còn con —
		không phải logic riêng của `StorageLocation`, nhưng chỉ có khi gọi super.
		"""
		from frappe.utils.nestedset import NestedSetChildExistsError

		_o("9Z19010101")
		with self.assertRaises(NestedSetChildExistsError):
			frappe.delete_doc("Storage Location", "9Z190101", ignore_permissions=True)

	def test_nut_cha_trung_ten_khac_kho_bi_chan(self):
		"""VÒNG SỬA 1 (review điều phối): `ma_o` mất 2 ký tự mã kho (Task 1) nên
		giờ là khoá chính TOÀN HỆ, không phải duy nhất trong một kho. Hai kho
		khác nhau cùng tạo ô lá chung tiền tố sẽ đụng đúng một bản ghi nút
		nhóm ở cấp TỔ TIÊN GẦN NHẤT (ở đây là nút Tầng 8 ký tự "9Y180101" —
		cấp `dam_bao_to_tien()` kiểm TRƯỚC TIÊN vì đó là cha trực tiếp của ô
		lá, không phải nút Khu 2 ký tự) — nếu không kiểm `kho` của nút cha đã
		tồn tại, nhánh của kho B sẽ âm thầm gắn vào nút cha thuộc kho A (hoặc
		ngược lại), không có lỗi nào báo.
		"""
		_o("9Y18010101")  # sinh đủ tổ tiên, trong đó "9Y180101" thuộc KHO
		kho_b = "Stores - MYN"
		with self.assertRaises(frappe.ValidationError) as cm:
			frappe.get_doc({"doctype": "Storage Location", "ma_o": "9Y18010102", "kho": kho_b}).insert(
				ignore_permissions=True
			)
		thong_bao = str(cm.exception)
		self.assertIn(KHO, thong_bao, "thông báo phải nêu tên kho ĐANG giữ nút cha")
		self.assertIn(kho_b, thong_bao, "thông báo phải nêu tên kho đang cố gắn vào")

	def test_thieu_kho_khi_nut_cha_da_ton_tai_khong_lo_chu_none(self):
		"""VÒNG SỬA 2 (review điều phối): bài vòng 1 chỉ kiểm mismatch giữa
		HAI kho hợp lệ — không kiểm trường hợp `kho` để trống trong khi nút
		cha đã tồn tại. `reqd=1` trên field `kho` chỉ chặn ở tầng client;
		qua API/`ignore_permissions` vẫn chèn được bản ghi thiếu kho.

		Trước vòng sửa 2: `dung_cho_trong_cay()` (→ `dam_bao_to_tien()`) chạy
		TRƯỚC `kiem_tra_kho()` trong `validate()`. Khi nút cha đã tồn tại,
		`kho_cha` (một chuỗi tên kho thật) luôn khác `self.kho` (`None`) nên
		ném NHẦM thông báo "đã thuộc kho X, không phải kho None" — sai
		nguyên nhân (không phải trùng kho, mà là CHƯA CHỌN kho) và lộ chuỗi
		Python "None" ra thông báo tiếng Việt gửi người dùng.
		"""
		_o("9X18010101")  # sinh nút cha "9X180101" (8 ký tự) trước
		with self.assertRaises(frappe.ValidationError) as cm:
			frappe.get_doc({"doctype": "Storage Location", "ma_o": "9X18010102"}).insert(
				ignore_permissions=True
			)
		thong_bao = str(cm.exception)
		self.assertIn("kho", thong_bao.lower(), "thông báo phải nói về việc THIẾU kho")
		self.assertNotIn("None", thong_bao, "không được lộ chuỗi Python 'None' ra thông báo")


class TestKhongGhiSoVaoNutNhom(FrappeTestCase):
	def test_ghi_vao_nut_nhom_bi_chan(self):
		"""Nếu lọt, báo cáo gộp theo cấp sẽ đếm HAI LẦN cùng một lượng hàng:
		một lần ở nút nhóm, một lần khi cộng dồn các ô lá bên dưới.
		"""
		from erpnext.vi_tri_kho.vitri import so

		_o("9Z18010101")
		with self.assertRaises(frappe.ValidationError) as ctx:
			so.ghi_dong_so(
				o="9Z1801",
				kho=KHO,
				vat_tu="_Test Item",
				so_lo=None,
				so_luong=5,
				chung_tu_type="Storage Location",
				chung_tu="9Z1801",
				chung_tu_row="r",
				sle=None,
				ngay="2026-09-01",
				thoi_diem="2026-09-01 08:00:00",
				company="Miyano Việt Nam",
			)
		self.assertIn("nhóm", str(ctx.exception).lower())
