"""Gán vị trí cố định cho mặt hàng: một mặt hàng một nút, một ô một chủ.

Bất biến đắt nhất ở đây KHÔNG phải "lưu được": nó là **một ô chỉ thuộc về
một mặt hàng**. Hỏng bất biến đó thì hai mặt hàng cùng được gợi ý vào một ô,
thủ kho xếp chồng lên nhau, và không có gì báo — đối soát §3 chỉ so TỔNG nên
vẫn khớp tuyệt đối.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.warehouse_operations.vitri import kho as vk

KHO = "Kho Miyano - MYN"


def _o(ma_o, **kw):
	"""Nút vị trí (mọi cấp). Nút cha tự sinh theo tiền tố của mã."""
	if not frappe.db.exists("Storage Location", ma_o):
		frappe.get_doc({"doctype": "Storage Location", "ma_o": ma_o, "kho": KHO, **kw}).insert(
			ignore_permissions=True
		)
	return ma_o


def _mat_hang(ma):
	if not frappe.db.exists("Item", ma):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": ma,
				"item_name": ma,
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 1,
			}
		).insert(ignore_permissions=True)
	return ma


def _gan(vat_tu, vi_tri, kho=KHO):
	return frappe.get_doc(
		{"doctype": "Item Location Preference", "vat_tu": vat_tu, "kho": kho, "vi_tri": vi_tri}
	).insert(ignore_permissions=True)


class _Nen(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.o1 = _o("7A01010101")  # tạo luôn cả nhánh cha 7A / 7A01 / 7A0101 / 7A010101
		cls.tang = "7A010101"
		cls.o2 = _o("7A01010102")
		cls.vt_a = _mat_hang("_Test Gan VT A")
		cls.vt_b = _mat_hang("_Test Gan VT B")


class TestLuocDo(_Nen):
	def tearDown(self):
		# `FrappeTestCase` chỉ rollback ở tearDownClass (xem `_rollback_db` trong
		# `frappe/tests/utils.py`), KHÔNG rollback sau từng bài — ba bài trong lớp
		# này cùng gán `vt_a`/`vt_b` (khoá chính là `vat_tu`) nên nếu không dọn ở
		# đây, bài chạy sau đụng đúng khoá chính bài trước vừa tạo và văng
		# `DuplicateEntryError` ngay ở lệnh gán bình thường — không phải ở chỗ bài
		# đang cố kiểm.
		frappe.db.delete("Item Location Preference", {"vat_tu": ("in", [self.vt_a, self.vt_b])})

	def test_ten_ban_ghi_chinh_la_ma_mat_hang(self):
		"""`autoname: field:vat_tu` là thứ giữ bất biến "một mặt hàng một nút".

		Nếu ai đó đổi sang `hash` hay `naming_series`, phép kiểm trùng lặp tụt
		xuống thành một dòng trong `validate()` — mà Data Import và REST đi
		vòng được. Khoá ở đây để đổi lược đồ là đỏ ngay.
		"""
		d = _gan(self.vt_a, self.o1)
		self.assertEqual(d.name, self.vt_a)

	def test_mot_mat_hang_khong_gan_duoc_hai_lan(self):
		_gan(self.vt_a, self.o1)
		with self.assertRaises(frappe.DuplicateEntryError):
			_gan(self.vt_a, self.o2)

	def test_cap_do_tu_dien_theo_ma(self):
		"""VÒNG SỬA (điều phối, Task 2): trước đây `vt_b` gán vào `7A010101` —
		đúng là TỔ TIÊN của `self.o1` (`7A01010101`) mà `vt_a` đang giữ trong
		bài này. Từ Task 2, `kiem_tra_chong_lan()` chặn mọi cặp gán chồng
		nhánh, nên bài sẽ tự đỏ ngay khi mã Task 2 vào — không phải vì Task 1
		có khiếm khuyết, mà vì bài đang tình cờ dựng đúng hình dạng chồng lấn
		mà Task 2 sinh ra để chặn. Đổi `vt_b` sang một nhánh RỜI HẲN
		(`8C010101`, một Khu khác toàn bộ, không chung tổ tiên với `self.o1`)
		để ca thử chỉ còn khoá đúng điều nó khai — cấp độ suy từ mã — chứ
		không tình cờ đụng bất biến "một ô một chủ" của một bài kiểm khác.
		"""
		self.assertEqual(_gan(self.vt_a, self.o1).cap_do, "Ô")
		_o("8C010101")
		self.assertEqual(_gan(self.vt_b, "8C010101").cap_do, "Tầng")


class TestChanNutKhongHopLe(_Nen):
	def test_chan_o_chua_xep(self):
		"""`ZZZ-CHUA-XEP` là ô ẢO. Gán vào đó thì gợi ý sẽ trỏ về đúng chỗ mà
		phiếu xếp đang cố đưa hàng RA — vòng tròn không lối thoát."""
		zzz = frappe.db.get_value("Storage Location", {"la_o_chua_xep": 1, "kho": KHO}, "name")
		self.assertIsNotNone(zzz)
		with self.assertRaises(frappe.ValidationError):
			_gan(self.vt_a, zzz)

	def test_chan_nut_thuoc_kho_khac(self):
		kho_khac = frappe.db.get_value("Warehouse", {"name": ("!=", KHO), "is_group": 0}, "name")
		self.assertIsNotNone(kho_khac)
		with self.assertRaises(frappe.ValidationError) as e:
			_gan(self.vt_a, self.o1, kho=kho_khac)
		# Khẳng định nó nổ vì LỆCH KHO, không phải vì kho kia chưa bật quản lý vị trí.
		self.assertIn(KHO, str(e.exception))

	def test_chan_kho_chua_bat_quan_ly_vi_tri(self):
		"""Nút thuộc ĐÚNG kho đang khai, nhưng kho đó chưa bật quản lý vị trí.

		VÒNG SỬA 1 (review điều phối, sau khi đảo thứ tự Ruling F): trước khi
		đảo, `test_chan_nut_thuoc_kho_khac` tình cờ đi qua nhánh
		`kho_co_quan_ly_vi_tri()` — vì kho lệch nó chọn ngẫu nhiên vốn chưa bật
		quản lý vị trí. Đảo xong, kho lệch bị chặn ngay ở phép kiểm lệch kho
		(đúng ý), nhưng nhánh cờ không còn bài nào chạm tới đúng tình huống nó
		sinh ra để chặn: nút thuộc ĐÚNG kho đang khai, chỉ là kho đó chưa bật.
		Xoá hẳn `if not kho_co_quan_ly_vi_tri(...)` thì cả 8 bài (lúc chưa có
		bài này) vẫn xanh tuyệt đối — lỗ này do chính việc đảo Ruling F tạo ra,
		vá tại đây bằng một bài kiểm thẳng nhánh đó.
		"""
		# `kho_co_quan_ly_vi_tri()` đọc `frappe.get_cached_value`, không đọc
		# thẳng CSDL (đường nóng của hook SLE). Đã kiểm thực nghiệm: bản Frappe
		# trên máy này tự gọi `clear_document_cache` bên trong `db.set_value`
		# khi `dn` là một tên chuỗi, nên riêng ở đây `xoa_cache_kho()` không
		# phải điều kiện đủ để bài xanh — nhưng vẫn gọi tường minh, đúng quy
		# ước mọi nơi đổi cờ trong module này đều gọi (`storage_location.py`,
		# `test_fefo.py`), để không lệ thuộc vào chi tiết cài đặt nội bộ đó của
		# `db.set_value` (một bản Frappe khác, hoặc gọi qua đường không phải
		# chuỗi tên, có thể không tự dọn).
		co_cu = frappe.db.get_value("Warehouse", KHO, "custom_quan_ly_vi_tri")
		frappe.db.set_value("Warehouse", KHO, "custom_quan_ly_vi_tri", 0)
		vk.xoa_cache_kho(KHO)
		try:
			with self.assertRaises(frappe.ValidationError) as e:
				_gan(self.vt_a, self.o1)
			# Phân biệt với ba nhánh ValidationError khác trong cùng hàm.
			self.assertIn("chưa bật quản lý vị trí", str(e.exception))
		finally:
			# BẮT BUỘC, kể cả khi bài đỏ: `Kho Miyano - MYN` là kho THẬT của
			# chủ dự án trên site dùng chung này. Trả về giá trị THẬT đã đọc
			# được (không ghi cứng 1) — cùng lý do `test_fefo.py` đã né bẫy
			# này: ghi cứng có thể tắt nhầm kho của người ta nếu giá trị gốc
			# từng khác. Một lần chạy bị giết giữa chừng (ReadTimeout do ba
			# bench chung máy hết RAM) mà không có `finally` sẽ để kho thật ở
			# trạng thái đã tắt quản lý vị trí.
			frappe.db.set_value("Warehouse", KHO, "custom_quan_ly_vi_tri", co_cu)
			vk.xoa_cache_kho(KHO)

	def test_chan_nut_dang_ngung_dung(self):
		frappe.db.set_value("Storage Location", self.o1, "disabled", 1)
		try:
			with self.assertRaises(frappe.ValidationError):
				_gan(self.vt_a, self.o1)
		finally:
			frappe.db.set_value("Storage Location", self.o1, "disabled", 0)

	def test_chan_nut_co_to_tien_ngung_dung(self):
		"""Tắt cả một Tầng để sửa kệ, rồi gán vào Ô bên dưới nó.

		Chốt âm của bài trên: một bản chỉ kiểm `sl.disabled` của CHÍNH nút vẫn
		làm bài trên xanh, nhưng để lọt ca này — và gợi ý sẽ trỏ vào chỗ không
		ai được đụng tới.
		"""
		frappe.db.set_value("Storage Location", "7A010101", "disabled", 1)
		try:
			with self.assertRaises(frappe.ValidationError):
				_gan(self.vt_a, self.o1)
		finally:
			frappe.db.set_value("Storage Location", "7A010101", "disabled", 0)


class TestBayToaDoRong(_Nen):
	def test_nut_ngoai_cay_bi_tu_choi(self):
		"""Cùng hình dạng bẫy đã trả giá ở `fefo.py` và `tem.py`.

		Bản ghi chưa hội tụ mang `lft = rgt = 0`. Cho qua thì vị từ giao nhau ở
		Task 2 thành `0 … 0` và khớp MỌI bản ghi 0/0 khác toàn hệ — gán tưởng
		của Tầng này lại bị chặn bởi nút của kho khác.
		"""
		frappe.db.set_value("Storage Location", self.o1, {"lft": 0, "rgt": 0}, update_modified=False)
		with self.assertRaises(frappe.ValidationError):
			_gan(self.vt_a, self.o1)


class TestChongLan(_Nen):
	"""Ma trận này phải có CẢ chốt âm.

	Một đột biến đổi vị từ giao nhau thành `s.name = %(vi_tri)s` vẫn làm ca
	"trùng đúng nút" xanh, trong khi để lọt hai ca nguy hiểm hơn (gán vào con
	cháu, gán vào tổ tiên). Ngược lại một vị từ chặt quá tay sẽ chặn oan nút
	anh em — và không bài nào bắt được nếu thiếu chốt âm.

	Ba bài "phải chặn" dưới đây còn phải kiểm CÂU CHỮ của thông báo, không chỉ
	loại ngoại lệ: `kiem_tra_chong_lan()` ném cùng một `frappe.ValidationError`
	ở cả ba nhánh quan hệ (trùng nút / con cháu / tổ tiên), và `validate()` có
	nhiều nhánh khác cũng ném đúng loại đó — nên `assertRaises` trơn không
	phân biệt được một đột biến hoán nhầm câu "đã được gán cho" (trùng nút)
	với câu "bao trùm ... đã được gán cho" (tổ tiên): cả 16 bài vẫn xanh dù
	thông báo sai hoàn toàn, vì không bài nào đọc nội dung ngoại lệ.
	"""

	def tearDown(self):
		# Cùng bẫy đã trả giá ở `TestLuocDo`: `FrappeTestCase` chỉ rollback ở
		# `tearDownClass`, không rollback theo từng phương thức — bảy bài
		# trong lớp này cùng gán `vt_a`/`vt_b` (khoá chính là `vat_tu`), nên
		# nếu không dọn ở đây, bài chạy sau đụng đúng khoá chính bài trước vừa
		# tạo và văng `DuplicateEntryError` ngay ở lệnh gán bình thường —
		# không phải ở chỗ bài đang cố kiểm.
		frappe.db.delete("Item Location Preference", {"vat_tu": ("in", [self.vt_a, self.vt_b])})

	def test_trung_dung_nut_bi_chan(self):
		"""Khẳng định phủ định là phần quan trọng nhất của bài này: nếu ai đó
		hoán nhầm nhánh "trùng nút" và nhánh "tổ tiên" trong `quan_he` của
		`kiem_tra_chong_lan()`, thông báo sẽ mang chữ "bao trùm" thay vì "đã
		được gán cho" — vẫn là `ValidationError`, vẫn làm bài xanh nếu chỉ
		`assertRaises` trơn. Kiểm cả hai chiều mới bắt được cú hoán đó."""
		_gan(self.vt_a, "7A010101")
		with self.assertRaises(frappe.ValidationError) as ngoai_le:
			_gan(self.vt_b, "7A010101")
		thong_diep = str(ngoai_le.exception)
		self.assertIn("đã được gán cho", thong_diep)
		self.assertNotIn("nằm trong", thong_diep)
		self.assertNotIn("bao trùm", thong_diep)

	def test_gan_vao_con_chau_bi_chan(self):
		"""A giữ Tầng 7A010101; B gán Ô 7A01010102 nằm trong đó."""
		_gan(self.vt_a, "7A010101")
		with self.assertRaises(frappe.ValidationError) as ngoai_le:
			_gan(self.vt_b, self.o2)
		self.assertIn("nằm trong", str(ngoai_le.exception))

	def test_gan_vao_to_tien_bi_chan(self):
		"""A giữ Ô 7A01010101; B gán Khoang 7A0101 bao trùm nó."""
		_gan(self.vt_a, self.o1)
		with self.assertRaises(frappe.ValidationError) as ngoai_le:
			_gan(self.vt_b, "7A0101")
		self.assertIn("bao trùm", str(ngoai_le.exception))

	def test_nut_anh_em_van_gan_duoc(self):
		"""CHỐT ÂM. Thiếu bài này thì một vị từ chặt quá tay (ví dụ so theo
		Khoang thay vì theo lft/rgt) vẫn xanh hết các bài trên, trong khi thực
		tế nó chặn oan mọi ô cạnh nhau — tức không ai gán được gì."""
		_gan(self.vt_a, self.o1)
		d = _gan(self.vt_b, self.o2)
		self.assertEqual(d.vi_tri, self.o2)

	def test_nhanh_khu_khac_van_gan_duoc(self):
		"""CHỐT ÂM thứ hai: đột biến bỏ hẳn mệnh đề giao nhau thì bài này vẫn
		xanh, nhưng `test_trung_dung_nut_bi_chan` sẽ đỏ — cặp đôi khoá chặt."""
		_o("8C01010101")
		_gan(self.vt_a, self.o1)
		d = _gan(self.vt_b, "8C01010101")
		self.assertEqual(d.vi_tri, "8C01010101")

	def test_sua_chinh_ban_ghi_cua_minh_van_duoc(self):
		"""Loại trừ `p.name != self.name`. Thiếu nó thì mọi lần lưu lại bản ghi
		đã có đều tự báo 'đụng chính mình' — gán tạo được một lần rồi vĩnh viễn
		không sửa nổi ghi chú."""
		d = _gan(self.vt_a, self.o1)
		d.ghi_chu = "đổi chỗ để kiểm"
		d.save(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("Item Location Preference", self.vt_a, "vi_tri"), self.o1)

	def test_thong_bao_neu_ten_mat_hang_dang_giu(self):
		"""'Không hợp lệ' trần thì người dùng không biết đi sửa ở đâu."""
		_gan(self.vt_a, "7A010101")
		with self.assertRaises(frappe.ValidationError) as ngoai_le:
			_gan(self.vt_b, self.o2)
		self.assertIn(self.vt_a, str(ngoai_le.exception))
		self.assertIn("7A010101", str(ngoai_le.exception))


def _ton(o, vat_tu, so_luong, kho=KHO):
	"""Đặt thẳng tồn vị trí. KHÔNG đi qua sổ — bài này chỉ kiểm phép chặn lúc
	gán, không kiểm bất biến sổ/tồn (đã có `test_doi_soat.py` lo)."""
	ten = frappe.db.get_value("Location Balance", {"o": o, "vat_tu": vat_tu, "so_lo": ""}, "name")
	if ten:
		frappe.db.set_value("Location Balance", ten, "so_luong", so_luong)
		return ten
	return frappe.get_doc(
		{"doctype": "Location Balance", "o": o, "kho": kho, "vat_tu": vat_tu,
		 "so_lo": "", "so_luong": so_luong}
	).insert(ignore_permissions=True).name


class TestChanTheoTon(_Nen):
	def tearDown(self):
		# Cùng bẫy đã trả giá ở `TestLuocDo`/`TestChongLan`: `FrappeTestCase` chỉ
		# rollback ở `tearDownClass`, không rollback theo từng phương thức — bốn
		# bài trong lớp này cùng gán `vt_a`/`vt_b` (khoá chính là `vat_tu`), nên
		# nếu không dọn ở đây, bài chạy sau đụng đúng khoá chính bài trước vừa
		# tạo và văng `DuplicateEntryError` ngay ở lệnh gán bình thường. Dọn
		# thêm `Location Balance` mà `_ton()` tạo ra — nếu không, tồn sót lại sẽ
		# làm bài của task sau (gợi ý ô) thấy hàng ở chỗ nó không ngờ.
		frappe.db.delete("Item Location Preference", {"vat_tu": ("in", [self.vt_a, self.vt_b])})
		frappe.db.delete("Location Balance", {"vat_tu": ("in", [self.vt_a, self.vt_b])})

	def test_chan_khi_trong_nhanh_co_hang_mat_hang_khac(self):
		"""VÒNG SỬA 1 (review điều phối): `validate()` có ít nhất 6 nhánh cùng
		ném `ValidationError` (xem `kiem_tra_chong_lan()` và các nhánh khác) —
		`assertRaises` trơn vẫn xanh dù lỗi bật ra từ một nhánh HOÀN TOÀN
		khác. Khoá thêm cụm đặc trưng của đúng nhánh `kiem_tra_ton_mat_hang_khac()`
		để phân biệt với "kiểm có chặn không" (bài này) khỏi "thông báo có đủ
		thông tin để đi dọn không" (`test_thong_bao_neu_ro_o_mat_hang_so_luong`
		ngay dưới) — hai bài khoá hai điều khác nhau, không gộp."""
		_ton(self.o1, self.vt_b, 15)
		with self.assertRaises(frappe.ValidationError) as e:
			_gan(self.vt_a, "7A010101")
		self.assertIn("hàng của mặt hàng khác", str(e.exception))

	def test_thong_bao_neu_ro_o_mat_hang_so_luong(self):
		"""Việc tiếp theo của người dùng là đi dọn ĐÚNG những ô đó bằng phiếu
		chuyển vị trí — thông báo phải đủ để làm việc đó ngay."""
		_ton(self.o1, self.vt_b, 15)
		with self.assertRaises(frappe.ValidationError) as e:
			_gan(self.vt_a, "7A010101")
		self.assertIn(self.o1, str(e.exception))
		self.assertIn(self.vt_b, str(e.exception))
		self.assertIn("15", str(e.exception))

	def test_hang_cua_chinh_no_thi_duoc(self):
		"""CHỐT ÂM. Một đột biến bỏ mệnh đề `vat_tu != ...` sẽ chặn luôn cả
		hàng của chính mặt hàng đang gán — tức không ai gán lại được vị trí cho
		món đã nằm sẵn đúng chỗ."""
		_ton(self.o1, self.vt_a, 15)
		d = _gan(self.vt_a, "7A010101")
		self.assertEqual(d.vi_tri, "7A010101")

	def test_ton_bang_0_khong_chan(self):
		"""Ô từng có hàng rồi hết vẫn còn dòng `so_luong = 0`. Coi đó là 'đang
		có hàng' thì mọi ô từng dùng qua đều vĩnh viễn không gán được."""
		_ton(self.o1, self.vt_b, 0)
		d = _gan(self.vt_a, "7A010101")
		self.assertEqual(d.vi_tri, "7A010101")

	def test_thong_bao_dem_dung_so_o_con_lai(self):
		"""VÒNG SỬA 1 (review điều phối). `ton_khac_trong_nhanh()` bị `limit`
		chặn cứng ở `GIOI_HAN + 1` dòng — đếm trên `len(...)` của kết quả đó
		luôn ra N = 1 bất kể nhánh có bao nhiêu ô thật. Dựng 5 ô có tồn của
		mặt hàng khác trong cùng nhánh (nhiều hơn `GIOI_HAN` = 3) để khoá đúng
		con số CÒN LẠI thật (5 - 3 = 2 ô nữa), không phải 1 ô nữa."""
		o3 = _o("7A01010103")
		o4 = _o("7A01010104")
		o5 = _o("7A01010105")
		for o in (self.o1, self.o2, o3, o4, o5):
			_ton(o, self.vt_b, 15)
		with self.assertRaises(frappe.ValidationError) as e:
			_gan(self.vt_a, self.tang)
		self.assertIn("2 ô nữa", str(e.exception))
		self.assertNotIn("1 ô nữa", str(e.exception))


class TestDoiMaMatHang(_Nen):
	"""`autoname: field:vat_tu` mua được một khoá chính, và phải trả bằng đây.

	`_sync_autoname_field()` (frappe/model/base_document.py:1027) ép
	`vat_tu = name` MỖI LẦN LƯU khi hai giá trị lệch nhau — `name` luôn thắng.
	`rename_doc` của Item cập nhật GIÁ TRỊ `vat_tu` bằng SQL nhưng không đụng
	`name` của bản ghi gán. Không có móc, lần lưu kế tiếp kéo `vat_tu` ngược về
	mã CŨ, âm thầm: gán trỏ vào một mặt hàng không còn tồn tại, và gợi ý cho mã
	mới lặng lẽ biến mất.

	Cùng hình dạng bẫy mà `storage_location.py::kiem_tra_ma_o_khong_doi` đã
	phải chặn tường minh cho `ma_o`.
	"""

	def test_doi_ma_mat_hang_keo_theo_ten_ban_ghi_gan(self):
		cu = _mat_hang("_Test Gan VT Doi Ten")
		_gan(cu, self.o1)
		moi = "_Test Gan VT Doi Ten MOI"
		frappe.rename_doc("Item", cu, moi, force=True)

		self.assertFalse(frappe.db.exists("Item Location Preference", cu))
		self.assertTrue(frappe.db.exists("Item Location Preference", moi))

	def test_luu_lai_sau_khi_doi_ten_khong_keo_vat_tu_ve_ma_cu(self):
		"""CHỐT ÂM — bài trên vẫn xanh nếu ai đó chỉ `db.set_value` trường
		`vat_tu` mà không rename. Bài này bắt đúng cú revert im lặng."""
		cu = _mat_hang("_Test Gan VT Revert")
		_gan(cu, self.o2)
		moi = "_Test Gan VT Revert MOI"
		frappe.rename_doc("Item", cu, moi, force=True)

		d = frappe.get_doc("Item Location Preference", moi)
		d.ghi_chu = "lưu lại sau khi đổi mã"
		d.save(ignore_permissions=True)
		self.assertEqual(d.vat_tu, moi)

	def test_gop_mat_hang_ma_dich_chua_co_gan_thi_giu_lai_gan(self):
		"""Vòng sửa 1 (review điều phối, Ruling L): trước bản vá này,
		`doi_ten_theo_mat_hang()` xoá VÔ ĐIỀU KIỆN bản ghi gán của mã cũ ở
		nhánh `merge=True` — kể cả khi mã đích chưa hề có gán riêng, tức
		rename bình thường là an toàn tuyệt đối. Ca đó xoá là vứt mất vị trí
		cố định của một mặt hàng vẫn còn sống sau khi gộp, mà không ai báo:
		gộp là thao tác hiếm nên khoản mất có thể nằm im rất lâu trước khi ai
		phát hiện. Bài này khoá đúng ca phải GIỮ.

		`o_nguon` là một nhánh RIÊNG, chưa từng dùng trong lớp này — `self.o1`
		và `self.o2` đã bị hai bài phía trên chiếm vĩnh viễn trong lớp (lớp
		này không có `tearDown`, xem báo cáo Task 4), nên tái dùng một trong
		hai sẽ tự đỏ vì đụng `kiem_tra_chong_lan()`, không phải vì mã đang
		kiểm sai."""
		nguon = _mat_hang("_Test Gan VT Gop Nguon A")
		dich = _mat_hang("_Test Gan VT Gop Dich A")
		o_nguon = _o("9A01010101")
		_gan(nguon, o_nguon)
		frappe.rename_doc("Item", nguon, dich, merge=True)

		d = frappe.get_doc("Item Location Preference", dich)
		self.assertEqual(d.vi_tri, o_nguon)

	def test_gop_mat_hang_ma_dich_da_co_gan_thi_giu_gan_cua_dich(self):
		"""Nửa còn lại của Ruling L, gỡ BLOCKED ở Ruling M (vòng sửa 2, review
		điều phối): trước Ruling M, trường `vat_tu` mang thêm một UNIQUE INDEX
		ở cấp DB tách biệt với khoá chính `name` — thừa, vì `autoname:
		field:vat_tu` khiến `name` CHÍNH LÀ `vat_tu`, nên PRIMARY KEY đã giữ
		đủ bất biến "một mặt hàng một gán" rồi. Chỉ mục thừa đó không thêm bảo
		đảm nào, nó chỉ chặn bước chung `update_link_field_values()` của
		`rename_doc()` đặt tạm hai dòng cùng `vat_tu` giữa chừng một thao tác
		gộp — sập ở tầng MySQL, TRƯỚC KHI `after_rename` (và do đó trước khi
		`doi_ten_theo_mat_hang()`) có cơ hội chạy. Bỏ chỉ mục thừa, ca này giờ
		gộp được thật.

		Đúng nỗi lo ban đầu của brief: mã đích ĐÃ có gán riêng thì rename
		thẳng sẽ đụng khoá chính (`name` = `dich` đã tồn tại), nên
		`doi_ten_theo_mat_hang()` phải xoá gán của mã NGUỒN (mặt hàng sắp biến
		mất, gán của nó vô nghĩa) và giữ nguyên gán của mã ĐÍCH (mặt hàng còn
		sống) — không được để mã nguồn ghi đè lên nút của mã đích.

		`o_nguon`/`o_dich` là hai nhánh "Khu" (2 ký tự đầu) tách hẳn nhau —
		"9B" khác "9C" — nên không giao nhau ở `chu_cua_nhanh()`. Không dùng
		`self.o1`/`self.o2`, cùng lý do đã nêu ở bài trên."""
		nguon = _mat_hang("_Test Gan VT Gop Nguon B")
		dich = _mat_hang("_Test Gan VT Gop Dich B")
		o_nguon = _o("9B01010101")
		o_dich = _o("9C01010101")
		_gan(nguon, o_nguon)
		_gan(dich, o_dich)

		frappe.rename_doc("Item", nguon, dich, merge=True)

		self.assertFalse(frappe.db.exists("Item Location Preference", nguon))
		d = frappe.get_doc("Item Location Preference", dich)
		self.assertEqual(d.vi_tri, o_dich)


class TestCayChonViTri(_Nen):
	"""Chỉ kiểm phần MÁY CHỦ. Việc vẽ cây nằm ở JS và không bài Python nào ở
	đây chứng minh nó vẽ đúng — đừng đọc bộ test này như thể nó chứng minh.

	VÒNG SỬA 2 (điều phối, tự bấm trên trình duyệt bắt được lỗi mà cả lớp
	này lẫn brief đều không thấy): các bài DƯỚI những dòng này phải gọi
	`cay_chon_vi_tri()` đúng CÁCH `frappe.ui.Tree` GỌI THẬT, không phải theo
	chữ ký Python mà ta tự nghĩ ra. Căn cứ là `get_nodes()`
	(`frappe/public/js/frappe/ui/tree.js:41-56`):

		get_nodes(value, is_root) {
			var args = Object.assign({}, this.args);
			args.parent = value;        // LUÔN gửi, kể cả ở gốc
			args.is_root = is_root;     // LUÔN gửi, dạng chuỗi qua HTTP
			frappe.call({ method: this.method, args, ... });
		}

	Ở CẤP GỐC, `value` truyền vào là `root_value` — mà constructor
	(tree.js dòng 22-24) mặc định `root_value = label`, và
	`cay_chon_vi_tri.js` truyền `label: kho`. Nghĩa là widget gọi
	`cay_chon_vi_tri(kho=..., parent=<TÊN KHO>, is_root=true)` ở gốc, KHÔNG
	PHẢI `cay_chon_vi_tri(kho)` suông như các bài phía trên trong lớp này
	(`test_tra_ve_khu_khi_khong_co_parent` và các bài khác gọi không
	`parent` — đó là chữ ký Python gọn, không phải cách widget thật sự gọi
	ở gốc, nên không bắt được lỗi này). Bài kiểm nào chỉ gọi theo chữ ký mà
	không mô phỏng đúng bộ tham số widget gửi thì không chứng minh được gì
	về màn hình thật — đây chính là lỗ mà vòng nộp trước lọt qua.
	"""

	def tearDown(self):
		# Cùng bẫy đã trả giá ở `TestLuocDo`/`TestChongLan`/`TestChanTheoTon`:
		# `FrappeTestCase` chỉ rollback ở `tearDownClass`, không rollback theo
		# từng phương thức — hai bài dưới đây cùng gán `vt_a` (khoá chính là
		# `vat_tu`), nên nếu không dọn ở đây, bài chạy sau đụng đúng khoá
		# chính bài trước vừa tạo và văng `DuplicateEntryError` ngay ở lệnh
		# gán bình thường — không phải ở chỗ bài đang cố kiểm.
		frappe.db.delete("Item Location Preference", {"vat_tu": ("in", [self.vt_a, self.vt_b])})

	def test_tra_ve_khu_khi_khong_co_parent(self):
		from erpnext.warehouse_operations.vitri.gan import cay_chon_vi_tri

		nut = cay_chon_vi_tri(KHO)
		self.assertTrue(nut)
		self.assertTrue(all(len(n["value"]) == 2 for n in nut), "cấp gốc phải là Khu (2 ký tự)")

	def test_nut_da_co_chu_mang_ten_mat_hang(self):
		from erpnext.warehouse_operations.vitri.gan import cay_chon_vi_tri

		_gan(self.vt_a, "7A010101")
		nut = {n["value"]: n for n in cay_chon_vi_tri(KHO, parent="7A0101")}
		self.assertEqual(nut["7A010101"]["da_gan_cho"], self.vt_a)

	def test_con_chau_cua_nut_da_co_chu_cung_bao_co_chu(self):
		"""CHỐT ÂM quan trọng nhất của cây. Một bản chỉ tra gán ĐÚNG nút sẽ
		hiện Tầng là 'đã có chủ' nhưng các Ô bên dưới vẫn trông trống — người
		dùng bấm vào Ô đó rồi mới ăn lỗi. 'Không khả dụng' phải NHÌN THẤY
		TRƯỚC KHI BẤM, nếu không thì với 214 ô đây là trò chơi đoán."""
		from erpnext.warehouse_operations.vitri.gan import cay_chon_vi_tri

		_gan(self.vt_a, "7A010101")
		nut = {n["value"]: n for n in cay_chon_vi_tri(KHO, parent="7A010101")}
		self.assertEqual(nut[self.o1]["da_gan_cho"], self.vt_a)

	def test_gan_o_tang_khien_khoang_cha_bi_khoa_qua_co_gan_ben_trong(self):
		"""Mục 1 (review tổng — khe hở CON CHÁU). Bài trên
		(`test_con_chau_cua_nut_da_co_chu_cung_bao_co_chu`) khoá chiều ĐANG
		chạy được (Ô con hiện 'đã gán' khi Tầng cha nó được gán) — giữ
		nguyên nó. Bài này khoá CHIỀU NGƯỢC LẠI, thứ `da_gan_cho` (tra tổ
		tiên-hoặc-chính-nó) không thấy được: gán ở Tầng `self.tang`
		(`7A010101`), rồi mở cây tới KHOANG CHA của nó (`7A0101`, qua
		`parent="7A01"` — cấp Dãy). Khoang cha CHƯA thuộc về ai (nó không
		phải nút được gán, chỉ BAO TRÙM một nút đã gán) nên `da_gan_cho`
		đúng ra phải là None — nhưng nó vẫn phải hiện KHÔNG CHỌN ĐƯỢC qua
		`co_gan_ben_trong`, nếu không thì `condition()` phía JS vẫn dựng nút
		"Chọn vị trí này", bấm vào ăn đúng lỗi 'bao trùm ... đã được gán
		cho' từ `kiem_tra_chong_lan()` — với 214 ô đó là trò chơi đoán."""
		from erpnext.warehouse_operations.vitri.gan import cay_chon_vi_tri

		_gan(self.vt_a, self.tang)
		nut = {n["value"]: n for n in cay_chon_vi_tri(KHO, parent="7A01")}
		khoang = nut["7A0101"]
		self.assertIsNone(khoang["da_gan_cho"], "Khoang chưa thuộc về ai — nhãn 'đã gán' sẽ nói sai")
		self.assertTrue(khoang["co_gan_ben_trong"], "phải báo có gán bên trong để JS chặn nút chọn")

	def test_tru_ten_loai_tru_chinh_gan_dang_sua_khoi_co_gan_ben_trong(self):
		"""Bắt được ở vòng soát lại SAU khi vá `co_gan_ben_trong` (advisor,
		trước khi bàn giao) — hệ quả trực tiếp của cột đó nếu bỏ sót, không
		phải một mục review riêng.

		`item_location_preference.js` gắn nút "Chọn trên cây vị trí" vào
		`refresh`, nên nó hiện ra CẢ KHI đang SỬA một bản ghi đã lưu. Người
		dùng đang giữ gán ở Tầng `self.tang`, mở cây định DỜI LÊN Khoang
		cha của CHÍNH nó — thao tác này HỢP LỆ: `kiem_tra_chong_lan()` phía
		`validate()` loại trừ đúng bản ghi đang sửa qua `tru_ten=self.name`.
		Không loại trừ tương tự ở `cay_chon_vi_tri()` thì Khoang cha sẽ báo
		`co_gan_ben_trong` = 1 vì đếm nhầm CHÍNH gán đang sửa, khoá nút
		"Chọn vị trí này" cho một thao tác lẽ ra phải làm được.

		Đối chứng với bài trên (không truyền `tru_ten`, `co_gan_ben_trong`
		phải khác 0): bài này CHỨNG MINH truyền đúng `tru_ten` gỡ được khoá
		đó, chứ không phải một tham số vô tác dụng."""
		from erpnext.warehouse_operations.vitri.gan import cay_chon_vi_tri

		_gan(self.vt_a, self.tang)
		nut = {n["value"]: n for n in cay_chon_vi_tri(KHO, parent="7A01", tru_ten=self.vt_a)}
		khoang = nut["7A0101"]
		self.assertFalse(
			khoang["co_gan_ben_trong"], "gán của CHÍNH bản ghi đang sửa phải được loại trừ"
		)

		# Đối xứng cho `da_gan_cho`: mở cây ngay tại CẤP CỦA `self.tang` (liệt
		# kê con của Khoang `7A0101`) với cùng `tru_ten`. Không loại trừ ở đây
		# thì mở cây để sửa ĐÚNG bản ghi đang xem sẽ hiện "đã gán: chính-mình"
		# — không sai logic (không khoá gì) nhưng là nhãn thừa, gây khó chịu
		# khi người dùng chỉ định xem/sửa lại vị trí đang giữ. Khoá tường minh
		# để đây là quyết định có chủ đích, không phải hệ quả tình cờ.
		nut_tang = {n["value"]: n for n in cay_chon_vi_tri(KHO, parent="7A0101", tru_ten=self.vt_a)}
		self.assertIsNone(
			nut_tang[self.tang]["da_gan_cho"],
			"gán của CHÍNH bản ghi đang sửa cũng phải được loại trừ khỏi da_gan_cho",
		)

	def test_so_o_trong_loai_nhanh_ngung_dung(self):
		"""Mục 2 (review tổng). `so_o_trong` từng dùng một vị từ RIÊNG,
		KHÔNG loại nhánh ngừng dùng như `goi_y._UNG_VIEN` — cây khoe "N ô
		trống" ở một nhánh mà `goi_y_o()` đã coi là đầy, hai màn hình của
		cùng một tính năng nói ngược nhau, không gì báo. Tắt cả một Khoang
		để sửa kệ (chỉ TỔ TIÊN `disabled`, hai Ô lá bên dưới vẫn
		`disabled = 0` của riêng chúng — đúng hình dạng kịch bản spec §5.2
		nêu tên) rồi kiểm `so_o_trong` của CHÍNH Khoang đó phải ra 0, không
		phải đếm hai ô lá trống như thể chúng còn dùng được."""
		from erpnext.warehouse_operations.vitri.gan import cay_chon_vi_tri

		for o in ("8D01020101", "8D01020102"):
			_o(o)
		frappe.db.set_value("Storage Location", "8D0102", "disabled", 1)
		try:
			nut = {n["value"]: n for n in cay_chon_vi_tri(KHO, parent="8D01")}
			self.assertEqual(nut["8D0102"]["so_o_trong"], 0)
		finally:
			# BẮT BUỘC dù bài đỏ: nút `8D0102` KHÔNG riêng của bài này (mọi
			# nút vị trí sống hết vòng đời lớp, `FrappeTestCase` chỉ
			# rollback ở `tearDownClass`) — để `disabled = 1` sót lại sẽ làm
			# lệch mọi bài khác trong lớp lỡ đụng nhánh `8D`.
			frappe.db.set_value("Storage Location", "8D0102", "disabled", 0)

	def test_nhanh_ngung_dung_bao_truoc_khi_chinh_day_dang_tat(self):
		"""Mối lo #1 để lại từ lượt sửa trước (xem 'Mối lo' cuối report review
		tổng): cây từng báo trước hai trong ba lý do `kiem_tra_nut_hop_le()`
		từ chối gán (`da_gan_cho`, `co_gan_ben_trong`) nhưng KHÔNG báo lý do
		thứ ba — nút `disabled` hoặc có tổ tiên `disabled`. Tắt một Dãy rồi
		hỏi cây ở ĐÚNG cấp đó (liệt kê con của Khu cha): chính nút Dãy phải tự
		báo `nhanh_ngung_dung`."""
		from erpnext.warehouse_operations.vitri.gan import cay_chon_vi_tri

		khu, day = "9D", "9D01"
		_o("9D01010101")  # sinh cả nhánh cha 9D / 9D01 / 9D0101 / 9D010101
		frappe.db.set_value("Storage Location", day, "disabled", 1)
		try:
			nut = {n["value"]: n for n in cay_chon_vi_tri(KHO, parent=khu)}
			self.assertTrue(nut[day]["nhanh_ngung_dung"], "chính nút Dãy đang tắt phải báo ngừng dùng")
		finally:
			# BẮT BUỘC dù bài đỏ: nút `9D01` sống hết vòng đời lớp
			# (`FrappeTestCase` chỉ rollback ở `tearDownClass`) — để
			# `disabled = 1` sót lại sẽ làm lệch hai bài dưới cùng đụng nhánh
			# `9D`.
			frappe.db.set_value("Storage Location", day, "disabled", 0)

	def test_nhanh_ngung_dung_bao_ca_o_la_con_ben_duoi_day_da_tat(self):
		"""CHỐT ÂM quan trọng nhất của Mục 1 lượt vá này. Ô LÁ bên dưới Dãy đã
		tắt vẫn phải báo `nhanh_ngung_dung`, DÙ cờ `disabled` của CHÍNH ô lá
		đó vẫn = 0 — chỉ tổ tiên (Dãy) của nó bị tắt. Một bản vá chỉ đọc cờ
		của CHÍNH nút (không tính tổ tiên) sẽ làm bài trên
		(`test_nhanh_ngung_dung_bao_truoc_khi_chinh_day_dang_tat`) xanh —
		Dãy tự đọc đúng cờ của chính nó — nhưng để lọt đúng bài này."""
		from erpnext.warehouse_operations.vitri.gan import cay_chon_vi_tri

		day, tang, o = "9D01", "9D010101", "9D01010101"
		_o(o)
		self.assertEqual(
			frappe.db.get_value("Storage Location", o, "disabled"), 0, "tiền đề: cờ của chính Ô lá = 0"
		)
		frappe.db.set_value("Storage Location", day, "disabled", 1)
		try:
			nut = {n["value"]: n for n in cay_chon_vi_tri(KHO, parent=tang)}
			self.assertTrue(
				nut[o]["nhanh_ngung_dung"],
				"Ô lá phải báo ngừng dùng do TỔ TIÊN (Dãy) tắt, dù cờ của chính nó vẫn = 0",
			)
		finally:
			frappe.db.set_value("Storage Location", day, "disabled", 0)

	def test_nhanh_ngung_dung_khong_khoa_nham_nhanh_khong_lien_quan(self):
		"""Chốt âm CHIỀU NGƯỢC LẠI, chặn một bản vá quá tay khoá cả cây: một
		nhánh KHÔNG LIÊN QUAN (Dãy anh em của Dãy đang tắt, cùng Khu cha)
		phải vẫn chọn được bình thường — `nhanh_ngung_dung` falsy."""
		from erpnext.warehouse_operations.vitri.gan import cay_chon_vi_tri

		khu, day, day_khac = "9D", "9D01", "9D02"
		_o("9D01010101")
		_o("9D02010101")
		frappe.db.set_value("Storage Location", day, "disabled", 1)
		try:
			nut = {n["value"]: n for n in cay_chon_vi_tri(KHO, parent=khu)}
			self.assertFalse(
				nut[day_khac]["nhanh_ngung_dung"], "nhánh không liên quan không được khoá lây"
			)
		finally:
			frappe.db.set_value("Storage Location", day, "disabled", 0)

	def test_o_chua_xep_khong_xuat_hien_trong_cay(self):
		from erpnext.warehouse_operations.vitri.gan import cay_chon_vi_tri

		zzz = frappe.db.get_value("Storage Location", {"la_o_chua_xep": 1, "kho": KHO}, "name")
		gia_tri = {n["value"] for n in cay_chon_vi_tri(KHO)}
		self.assertNotIn(zzz, gia_tri)

	def test_widget_goi_dung_o_cap_goc_van_ra_khu(self):
		"""VÒNG SỬA 2 (điều phối, bắt được bằng cách bấm thật trên trình
		duyệt — không bài Python nào trước đó bắt được). Đây là bài mô
		phỏng ĐÚNG cách `frappe.ui.Tree.get_nodes()` gọi ở CẤP GỐC
		(`tree.js:41-56`): `args.parent = value` LUÔN được gán (ở gốc,
		`value` là `root_value`, mặc định bằng `label` — mà
		`cay_chon_vi_tri.js` truyền `label: kho` — nên `parent` mang TÊN
		KHO, không rỗng), và `args.is_root = is_root` LUÔN được gửi. Các
		bài PHÍA TRÊN trong lớp này gọi `cay_chon_vi_tri(KHO)` — không
		`parent`, không `is_root` — đó là chữ ký Python gọn ta tự nghĩ ra,
		KHÔNG PHẢI cách widget thật sự gọi ở gốc, nên không bắt được lỗi
		khiến cây chết trên màn hình (mọi lệnh gọi gốc đều rơi vào nhánh
		`sl.parent_storage_location = %(parent)s` với `parent` = tên kho —
		không khớp `Storage Location` nào, luôn ra rỗng)."""
		from erpnext.warehouse_operations.vitri.gan import cay_chon_vi_tri

		nut = cay_chon_vi_tri(KHO, parent=KHO, is_root="true")
		self.assertTrue(nut, "gọi đúng như widget ở CẤP GỐC phải ra các Khu, không rỗng")
		self.assertTrue(all(len(n["value"]) == 2 for n in nut), "cấp gốc phải là Khu (2 ký tự)")
		self.assertIn("7A", {n["value"] for n in nut})

	def test_is_root_chuoi_false_khong_bi_hieu_nham_la_goc(self):
		"""CHỐT ÂM của bài trên. `is_root` tới dưới dạng CHUỖI `"false"` khi
		gọi qua HTTP (`frappe.call` gửi mọi tham số dạng chuỗi) — một
		`if is_root:` trần sẽ coi `"false"` (chuỗi khác rỗng) là ĐÚNG, tức
		MỌI lệnh gọi xuống nhánh cũng bị hiểu nhầm thành gốc và trả về các
		Khu thay vì con thật của `parent`. Gọi xuống nhánh của Khu `7A`
		(chính lớp `_Nen` dựng sẵn) với `is_root="false"` phải ra con của nó
		(`7A01`, cấp Dãy), TUYỆT ĐỐI không được lẫn Khu (2 ký tự) nào vào."""
		from erpnext.warehouse_operations.vitri.gan import cay_chon_vi_tri

		nut = {n["value"] for n in cay_chon_vi_tri(KHO, parent="7A", is_root="false")}
		self.assertIn("7A01", nut)
		self.assertTrue(all(len(v) > 2 for v in nut), "không được lẫn Khu (2 ký tự) vào nhánh")
