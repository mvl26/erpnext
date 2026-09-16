"""Gợi ý ô khi xếp hàng: ô trống đầu tiên theo THỨ TỰ CÂY.

Bài quan trọng nhất ở đây là `test_theo_thu_tu_cay_chu_khong_phai_thu_tu_ten`.
Trong dữ liệu mẫu, thứ tự `lft` trùng thứ tự chữ cái của mã, nên một bản sắp
theo `order by name` vẫn xanh mọi bài khác mà không chứng minh được gì. Ca đó
dựng riêng một nhánh mà hai thứ tự KHÁC nhau.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.vi_tri_kho.vitri.goi_y import goi_y_o

KHO = "Kho Miyano - MYN"

# Dùng lại helper của bài gán — cùng cách dựng dữ liệu, một chỗ sửa.
from erpnext.vi_tri_kho.tests.test_gan_vi_tri import _gan, _mat_hang, _o, _ton


class _NenGoiY(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Tầng 6B010201 có 3 ô
		for o in ("6B01020101", "6B01020102", "6B01020103"):
			_o(o)
		cls.tang = "6B010201"
		cls.vt = _mat_hang("_Test GoiY VT")
		cls.vt_khac = _mat_hang("_Test GoiY VT Khac")


class TestGoiY(_NenGoiY):
	def tearDown(self):
		# `FrappeTestCase` chỉ rollback ở `tearDownClass`, không rollback theo
		# từng phương thức (cùng bẫy đã trả giá ở `test_gan_vi_tri.py`:
		# `TestLuocDo`, `TestChongLan`, `TestChanTheoTon`). `cls.vt` được TÁI
		# DÙNG ở hai bài trong lớp này (`test_o_trong_dau_tien` và
		# `test_o_chua_xep_khong_bao_gio_la_ket_qua`, cả hai đều `_gan` nó vào
		# CÙNG một nút `cls.tang`) — không dọn thì bài chạy SAU (thứ tự mặc
		# định của `unittest` là theo BẢNG CHỮ CÁI tên phương thức: "..._o_chua_"
		# < "..._o_trong_", nên `test_o_chua_xep...` chạy trước) đụng đúng khoá
		# chính (`name` = `vat_tu`, xem `autoname: field:vat_tu`) mà bài trước
		# vừa tạo, và văng lỗi ngay ở lệnh `_gan` bình thường — không phải ở
		# chỗ bài đang cố kiểm. Các bài còn lại trong lớp tự tạo `_mat_hang()`
		# riêng mỗi bài nên không đụng gì; xoá `vat_tu = cls.vt` là no-op vô
		# hại ở những bài đó. Dọn cả `Location Balance` mà `_ton()` tạo cho
		# `cls.vt` (`test_o_trong_dau_tien`) để tồn không rò sang bài khác.
		frappe.db.delete("Item Location Preference", {"vat_tu": self.vt})
		frappe.db.delete("Location Balance", {"vat_tu": self.vt})

	def test_chua_gan_thi_khong_goi_y_va_KHONG_nem_loi(self):
		"""Phần lớn mặt hàng sẽ chưa gán trong nhiều tháng tới. Ném lỗi ở đây
		là phiếu xếp không mở nổi."""
		o, ly_do = goi_y_o(_mat_hang("_Test GoiY Chua Gan"), KHO)
		self.assertIsNone(o)
		self.assertIn("chưa gán", ly_do)

	def test_o_trong_dau_tien(self):
		_gan(self.vt, self.tang)
		_ton("6B01020101", self.vt, 5)
		o, ly_do = goi_y_o(self.vt, KHO)
		self.assertEqual(o, "6B01020102")
		self.assertIn("trống", ly_do)

	def test_theo_thu_tu_cay_chu_khong_phai_thu_tu_ten(self):
		"""Dựng nhánh mà thứ tự `lft` KHÁC thứ tự chữ cái.

		`Storage Location` là nested set: `lft` do thứ tự chèn quyết định, còn
		mã thì không. Tạo ô `...03` TRƯỚC `...02` rồi kiểm rằng gợi ý vẫn đi
		theo cây. Thiếu ca này, `order by name` và `order by lft` không phân
		biệt được — và bài test không khoá cái nó tưởng là đang khoá.
		"""
		_o("6C01020103")
		_o("6C01020102")
		v = _mat_hang("_Test GoiY ThuTu")
		_gan(v, "6C010201")
		lft = {
			n: frappe.db.get_value("Storage Location", n, "lft")
			for n in ("6C01020102", "6C01020103")
		}
		dau_theo_cay = min(lft, key=lft.get)
		o, _ = goi_y_o(v, KHO)
		self.assertEqual(o, dau_theo_cay)

	def test_het_o_trong_thi_don_vao_o_dang_co_hang_cua_chinh_no(self):
		"""Phương án (b) chủ đầu tư chốt 15/09.

		Không có nhánh này thì gán một mặt hàng vào MỘT Ô lẻ khiến lần nhập thứ
		hai trở đi luôn báo đầy — dù hàng trong ô chính là hàng của nó và kệ
		còn thừa chỗ.
		"""
		v = _mat_hang("_Test GoiY O Le")
		_o("6D01020101")
		_gan(v, "6D01020101")
		_ton("6D01020101", v, 7)
		o, ly_do = goi_y_o(v, KHO)
		self.assertEqual(o, "6D01020101")
		self.assertIn("dồn", ly_do)

	def test_day_thi_bao_day(self):
		"""LỆCH BRIEF, có đo: brief đặt `_ton(o, self.vt_khac, 3)` TRƯỚC
		`_gan(v, "6E010201")`. Chạy đúng thứ tự đó văng `ValidationError` từ
		`kiem_tra_ton_mat_hang_khac()` (Task 2-3): gán vào một nhánh ĐANG có
		hàng của mặt hàng khác bị chặn ngay lúc gán — hợp lý, và đúng ý nghĩa
		của phép kiểm đó. Ca "đầy vì hàng của mặt hàng khác" trong đời thật chỉ
		xảy ra SAU khi gán (nhánh sạch lúc gán), rồi hàng của mặt hàng khác lọt
		vào bằng một luồng nhập/chuyển kho bình thường (đi qua sổ, không đi qua
		`validate()` của gán). Đảo thứ tự: gán trước lúc nhánh còn sạch, rồi mới
		đặt tồn mặt hàng khác — đúng trình tự nghiệp vụ thật.
		"""
		v = _mat_hang("_Test GoiY Day")
		for o in ("6E01020101", "6E01020102"):
			_o(o)
		_gan(v, "6E010201")
		for o in ("6E01020101", "6E01020102"):
			_ton(o, self.vt_khac, 3)
		o, ly_do = goi_y_o(v, KHO)
		self.assertIsNone(o)
		self.assertIn("đầy", ly_do)

	def test_o_trong_nhanh_ngung_dung_khong_bao_gio_duoc_goi_y(self):
		"""Tắt cả một Khoang để sửa kệ. Ô bên dưới vẫn `disabled = 0` của
		riêng nó — chỉ tổ tiên bị tắt. Gợi ý trỏ vào đó thì `fefo` lại từ chối
		lấy hàng ra: hai nửa của hệ nói ngược nhau."""
		v = _mat_hang("_Test GoiY Tat")
		for o in ("6F01020101", "6F01020102"):
			_o(o)
		_gan(v, "6F010201")
		frappe.db.set_value("Storage Location", "6F0102", "disabled", 1)
		try:
			o, ly_do = goi_y_o(v, KHO)
			self.assertIsNone(o)
		finally:
			frappe.db.set_value("Storage Location", "6F0102", "disabled", 0)

	def test_o_chua_xep_khong_bao_gio_la_ket_qua(self):
		zzz = frappe.db.get_value("Storage Location", {"la_o_chua_xep": 1, "kho": KHO}, "name")
		_gan(self.vt, self.tang)
		o, _ = goi_y_o(self.vt, KHO)
		self.assertNotEqual(o, zzz)

	def test_gan_toa_do_rong_bi_chan_ngay_khi_goi_y(self):
		"""Mục 4 (review tổng). Nhánh `frappe.throw` khi nút gán mang
		`lft`/`rgt` = 0 CHƯA có bài nào phủ trước bản vá này — đây là bẫy đã
		trả giá BA LẦN trong module (`fefo.py`, `tem.py`,
		`item_location_preference.py`). Một nhánh throw không ai giữ là thứ
		ĐẦU TIÊN bị xoá trong một lượt "dọn mã chết", và khi xoá thì
		`between 0 and 0` khớp MỌI bản ghi 0/0 toàn hệ, gợi ý một ô của KHO
		KHÁC — im lặng, không lỗi nào báo.

		Khuôn chép từ
		`test_gan_vi_tri.py::TestBayToaDoRong.test_nut_ngoai_cay_bi_tu_choi`:
		phải GÁN TRƯỚC rồi mới phá toạ độ — `validate()` của
		`ItemLocationPreference` đã chặn gán thẳng vào một nút 0/0 (§5.1),
		nên không thể dựng ca này bằng cách gán vào nút đã hỏng sẵn.
		"""
		v = _mat_hang("_Test GoiY ToaDoRong")
		_o("6G01020101")
		nut = "6G010201"
		_gan(v, nut)
		lft_cu, rgt_cu = frappe.db.get_value("Storage Location", nut, ["lft", "rgt"])
		frappe.db.set_value("Storage Location", nut, {"lft": 0, "rgt": 0}, update_modified=False)
		try:
			with self.assertRaises(frappe.ValidationError):
				goi_y_o(v, KHO)
		finally:
			# BẮT BUỘC dù bài đỏ: khôi phục toạ độ để các bài khác trong lớp
			# (rollback theo LỚP, không theo từng bài) không đụng một nút
			# vĩnh viễn hỏng toạ độ.
			frappe.db.set_value("Storage Location", nut, {"lft": lft_cu, "rgt": rgt_cu}, update_modified=False)


class TestPhieuXepDuocDienSan(_NenGoiY):
	"""Task 6: `xep.py::hang_chua_xep` giờ gọi `goi_y_o` một lần cho mỗi MẶT HÀNG
	và điền `den_o`/`ly_do_goi_y` vào từng dòng trả về. Bài ở đây khoá đúng chỗ
	nối đó (hàm có gọi, có gán đúng trường không) — không lặp lại các ca của
	`goi_y_o` chính nó, đã có ở `TestGoiY` trên.

	KHÔNG cần `tearDown` như `TestGoiY`/`TestLuocDo` ở trên dù `FrappeTestCase`
	rollback theo LỚP chứ không theo từng bài: hai bài dưới đây dùng hai
	`vat_tu` RIÊNG (`_Test Xep Da Gan` / `_Test Xep Chua Gan`), không bài nào
	tái dùng mã của bài kia hay của `cls.vt`/`cls.vt_khac` thừa hưởng từ
	`_NenGoiY`. Bẫy `DuplicateEntryError` (khoá chính là `vat_tu`, xem
	`test_gan_vi_tri.py::TestLuocDo`) chỉ nổ khi HAI bài CÙNG lớp gán CÙNG một
	mã — không phải tình huống ở đây.
	"""

	def test_mat_hang_da_gan_thi_den_o_duoc_dien(self):
		from erpnext.vi_tri_kho.vitri.xep import hang_chua_xep

		zzz = frappe.db.get_value("Storage Location", {"la_o_chua_xep": 1, "kho": KHO}, "name")
		v = _mat_hang("_Test Xep Da Gan")
		_o("7B01020101")
		_gan(v, "7B010201")
		_ton(zzz, v, 9)

		dong = [d for d in hang_chua_xep(KHO) if d["vat_tu"] == v]
		self.assertEqual(len(dong), 1)
		self.assertEqual(dong[0]["den_o"], "7B01020101")
		self.assertIn("trống", dong[0]["ly_do_goi_y"])

	def test_mat_hang_chua_gan_thi_den_o_van_trong(self):
		"""CHỐT ÂM và là ca thật: phần lớn mặt hàng chưa gán. Một bản điền bừa
		(ví dụ lấy ô trống đầu tiên của cả kho) sẽ làm bài trên xanh mà vẫn dẫn
		thủ kho xếp nhầm."""
		from erpnext.vi_tri_kho.vitri.xep import hang_chua_xep

		zzz = frappe.db.get_value("Storage Location", {"la_o_chua_xep": 1, "kho": KHO}, "name")
		v = _mat_hang("_Test Xep Chua Gan")
		_ton(zzz, v, 4)

		dong = [d for d in hang_chua_xep(KHO) if d["vat_tu"] == v]
		self.assertEqual(len(dong), 1)
		self.assertFalse(dong[0]["den_o"])
		self.assertIn("chưa gán", dong[0]["ly_do_goi_y"])

	def test_mot_mat_hang_loi_du_lieu_khong_lam_sap_ca_kho(self):
		"""Ruling N (vòng sửa 1, review điều phối).

		Một bản gán hỏng toạ độ (`lft`/`rgt` = 0 trên CHÍNH nút đã gán — mô
		phỏng ca cây chưa hội tụ, cùng hình dạng bẫy đã khoá ở
		`test_gan_vi_tri.py::TestBayToaDoRong`) làm `goi_y_o()` NÉM LỖI cho
		ĐÚNG mặt hàng đó. Trước bản vá này, `hang_chua_xep()` gọi `goi_y_o`
		trong vòng lặp không có `try/except`, nên lỗi của MỘT mặt hàng văng
		thẳng ra khỏi RPC và sập luôn danh sách của mặt hàng LÀNH đứng cạnh
		nó — dựng CẢ HAI trong cùng một lần gọi `hang_chua_xep()` mới khoá
		đúng ca đó; một bài chỉ dựng riêng mặt hàng hỏng không phân biệt được
		"trả lỗi cho đúng dòng đó" với "sập cả hàm".

		Khẳng định thêm `ly_do_goi_y` của dòng hỏng phân biệt rõ với "chưa
		gán" — hai việc cần hai hành động khác nhau của thủ kho (Ruling O ở
		phần JS xử lý đúng sự phân biệt này). Mục 5 (review tổng, vòng sửa
		cuối): câu chữ KHÔNG còn khẳng định chắc đây là "lỗi dữ liệu" nữa —
		`except Exception` ở `hang_chua_xep()` bắt MỌI ngoại lệ, kể cả một
		lỗi LẬP TRÌNH trong `goi_y_o`, nên khẳng định nguyên nhân là sai; câu
		mới chỉ nói "không gợi ý được", không đoán vì sao.
		"""
		from erpnext.vi_tri_kho.vitri.xep import hang_chua_xep

		zzz = frappe.db.get_value("Storage Location", {"la_o_chua_xep": 1, "kho": KHO}, "name")
		lanh = _mat_hang("_Test Xep Lanh")
		hong = _mat_hang("_Test Xep Hong")
		_o("7C01020101")
		_o("7D01020101")
		_gan(lanh, "7C010201")
		_gan(hong, "7D010201")  # gán TRƯỚC khi phá toạ độ — validate() chặn gán
		# thẳng vào một nút 0/0 (xem TestBayToaDoRong), nên phải phá SAU.
		_ton(zzz, lanh, 3)
		_ton(zzz, hong, 5)

		nut_hong = "7D010201"
		lft_cu, rgt_cu = frappe.db.get_value("Storage Location", nut_hong, ["lft", "rgt"])
		frappe.db.set_value("Storage Location", nut_hong, {"lft": 0, "rgt": 0}, update_modified=False)
		try:
			dong = hang_chua_xep(KHO)  # KHÔNG được ném lỗi
		finally:
			# BẮT BUỘC dù bài đỏ: trả cây về trạng thái hội tụ cho các bài khác
			# chạy sau trong cùng lớp (rollback theo LỚP, không theo từng bài).
			frappe.db.set_value(
				"Storage Location", nut_hong, {"lft": lft_cu, "rgt": rgt_cu}, update_modified=False
			)

		d_lanh = next(d for d in dong if d["vat_tu"] == lanh)
		d_hong = next(d for d in dong if d["vat_tu"] == hong)
		self.assertEqual(d_lanh["den_o"], "7C01020101")
		self.assertIn("trống", d_lanh["ly_do_goi_y"])
		self.assertFalse(d_hong["den_o"])
		# Mục 5 (review tổng): câu chữ đổi từ "lỗi dữ liệu vị trí cho ..."
		# (khẳng định SAI nguyên nhân — `except Exception` bắt cả lỗi lập
		# trình, không riêng toạ độ hỏng) sang "không gợi ý được", nhưng vẫn
		# phải giữ phần phân biệt rõ với "chưa gán" — hai việc cần hai hành
		# động khác nhau của thủ kho (Ruling O).
		self.assertIn("không gợi ý được", d_hong["ly_do_goi_y"])
		# CHỐT bằng "đừng gán lại", KHÔNG phải "chưa gán": câu mới chứa cả
		# cụm "KHÔNG PHẢI mặt hàng chưa gán" nên `assertIn("chưa gán", ...)`
		# sẽ xanh dù ai đó lỡ xoá mất phần phân biệt — "đừng gán lại" chỉ
		# xuất hiện ở nhánh lỗi dữ liệu/lỗi mã, khoá đúng thứ cần khoá.
		self.assertIn("đừng gán lại", d_hong["ly_do_goi_y"])
