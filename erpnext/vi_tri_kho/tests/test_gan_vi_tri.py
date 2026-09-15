"""Gán vị trí cố định cho mặt hàng: một mặt hàng một nút, một ô một chủ.

Bất biến đắt nhất ở đây KHÔNG phải "lưu được": nó là **một ô chỉ thuộc về
một mặt hàng**. Hỏng bất biến đó thì hai mặt hàng cùng được gợi ý vào một ô,
thủ kho xếp chồng lên nhau, và không có gì báo — đối soát §3 chỉ so TỔNG nên
vẫn khớp tuyệt đối.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

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
		self.assertEqual(_gan(self.vt_a, self.o1).cap_do, "Ô")
		self.assertEqual(_gan(self.vt_b, "7A010101").cap_do, "Tầng")


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
