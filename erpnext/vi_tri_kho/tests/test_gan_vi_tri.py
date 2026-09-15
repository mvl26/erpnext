"""Gán vị trí cố định cho mặt hàng: một mặt hàng một nút, một ô một chủ.

Bất biến đắt nhất ở đây KHÔNG phải "lưu được": nó là **một ô chỉ thuộc về
một mặt hàng**. Hỏng bất biến đó thì hai mặt hàng cùng được gợi ý vào một ô,
thủ kho xếp chồng lên nhau, và không có gì báo — đối soát §3 chỉ so TỔNG nên
vẫn khớp tuyệt đối.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.vi_tri_kho.vitri import kho as vk

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
		_ton(self.o1, self.vt_b, 15)
		with self.assertRaises(frappe.ValidationError):
			_gan(self.vt_a, "7A010101")

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
