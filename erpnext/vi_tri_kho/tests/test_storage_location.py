"""Cây vị trí — ràng buộc cấu trúc.

`name` của bản ghi CHÍNH LÀ mã ô (autoname field:ma_o). Nhờ vậy mọi Link
field đọc được ngay và quét mã vạch ra thẳng bản ghi, không phải tra bảng
trung gian. Bài test đầu tiên khoá đúng điều đó lại.
"""

import frappe
from frappe.tests.utils import FrappeTestCase


def _tao_o(ma_o, **kw):
	kw.setdefault("kho", "Kho Miyano - MYN")
	doc = frappe.get_doc({"doctype": "Storage Location", "ma_o": ma_o, **kw})
	doc.insert(ignore_permissions=True)
	return doc


class _CoTienDeKho(FrappeTestCase):
	"""Lớp nền: khẳng định tường minh dữ liệu kho mà cả file test này dựa vào.

	`_tao_o()` hard-code kho "Kho Miyano - MYN", và một số bài test hard-code
	"All Warehouses - MYN" là kho NHÓM. Nếu hai bản ghi đó thiếu hoặc sai hình
	dạng, bài test phải ĐỎ ngay ở đây với thông báo rõ ràng — không được xanh
	vô cớ nhờ dữ liệu tình cờ có sẵn, cũng không được đỏ khó hiểu ở một chỗ
	khác không liên quan tới cái đang thử.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		if not frappe.db.exists("Warehouse", "Kho Miyano - MYN"):
			raise AssertionError(
				"Tiền đề thiếu: Warehouse 'Kho Miyano - MYN' không tồn tại trên site "
				"erptest.local. Bài test cây vị trí cần kho lá này có sẵn để gán vào ô."
			)
		if frappe.db.get_value("Warehouse", "Kho Miyano - MYN", "is_group"):
			raise AssertionError(
				"Tiền đề sai: Warehouse 'Kho Miyano - MYN' đang là kho NHÓM (is_group=1), "
				"nhưng bài test cần một kho lá để gán cho ô."
			)
		if not frappe.db.exists("Warehouse", "All Warehouses - MYN"):
			raise AssertionError(
				"Tiền đề thiếu: Warehouse 'All Warehouses - MYN' không tồn tại trên site "
				"erptest.local. Bài test cần kho NHÓM này để thử ràng buộc chặn ô vào kho tổng."
			)
		if not frappe.db.get_value("Warehouse", "All Warehouses - MYN", "is_group"):
			raise AssertionError(
				"Tiền đề sai: Warehouse 'All Warehouses - MYN' không phải kho NHÓM "
				"(is_group=0), nhưng bài test cần is_group=1 để thử ràng buộc chặn ô vào "
				"kho tổng."
			)


class TestDatTen(_CoTienDeKho):
	def test_name_chinh_la_ma_o(self):
		o = _tao_o("9Z01010101")
		self.assertEqual(o.name, "9Z01010101")

	def test_ma_o_khong_duoc_trung(self):
		_tao_o("9Z01010102")
		with self.assertRaises(frappe.DuplicateEntryError):
			_tao_o("9Z01010102")


class TestRangBuocKho(_CoTienDeKho):
	def test_o_la_bat_buoc_co_kho(self):
		doc = frappe.get_doc({"doctype": "Storage Location", "ma_o": "9Z01010201"})
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_khong_nhan_warehouse_nhom(self):
		with self.assertRaises(frappe.ValidationError) as ctx:
			_tao_o("9Z01010202", kho="All Warehouses - MYN")
		self.assertIn("kho tổng", str(ctx.exception).lower())


class TestKhoaMaO(_CoTienDeKho):
	"""Mã ô đã in lên tem dán kệ — không được đổi âm thầm sau khi tạo.

	`autoname: field:ma_o` chỉ gán `name` lúc insert. Nếu không khoá, sửa
	`ma_o` của bản ghi đã tồn tại làm `name` và `ma_o` lệch nhau âm thầm,
	phá bất biến "name CHÍNH LÀ mã ô" mà toàn hệ thống dựa vào.
	"""

	def test_khong_duoc_sua_ma_o_sau_khi_tao(self):
		o = _tao_o("9Z02010101")
		o.ma_o = "9Z02010102"
		with self.assertRaises(frappe.ValidationError):
			o.save(ignore_permissions=True)


class TestBarcode(_CoTienDeKho):
	"""Barcode phải duy nhất.

	Hai bài về "nút nhóm để trống barcode" đã bỏ cùng cây nested set: mọi bản
	ghi giờ đều là ô lá và luôn được tự điền barcode từ mã ô, nên không còn
	tình huống hai bản ghi cùng để trống.
	"""

	def test_barcode_khong_duoc_trung(self):
		_tao_o("9Z03010101")
		with self.assertRaises(frappe.ValidationError):
			_tao_o("9Z03010102", barcode="9Z03010101")


class TestKhoaOChuaXep(_CoTienDeKho):
	"""CRITICAL 2 (review điều phối, sau khi 147/147 bài "xong"): một
	checkbox (`disabled`) trên ô `la_o_chua_xep=1` làm đứng cả kho — nhập
	vẫn ghi vào ô đã ngừng dùng (vì `o_chua_xep()` trước đây chỉ hỏi
	`frappe.db.exists`), trong khi xuất bị FEFO loại bỏ ô `disabled`
	(`fefo.py:60`) rồi `frappe.throw` giữa `Stock Ledger Entry.on_submit` —
	cuộn ngược MỌI phiếu xuất của MỌI mặt hàng đang ở CHUA-XEP. `disabled`
	không read-only và `Stock Manager` có quyền `write` trên `Storage
	Location` (xem `storage_location.json`), nên đây là một tai nạn vận
	hành có thật, không phải giả thuyết.

	Spec §5.1: "`la_o_chua_xep`: ... mỗi kho đúng 1 ô, không xoá được."
	"""

	def test_khong_duoc_vo_hieu_hoa_o_chua_xep(self):
		o = _tao_o("TEST-CX-DISABLE", la_o_chua_xep=1)
		o.disabled = 1
		with self.assertRaises(frappe.ValidationError) as ctx:
			o.save(ignore_permissions=True)
		self.assertIn("chưa xếp vị trí", str(ctx.exception).lower())

	def test_khong_xoa_duoc_o_chua_xep(self):
		o = _tao_o("TEST-CX-TRASH", la_o_chua_xep=1)
		with self.assertRaises(frappe.ValidationError) as ctx:
			frappe.delete_doc("Storage Location", o.name, ignore_permissions=True)
		self.assertIn("chưa xếp vị trí", str(ctx.exception).lower())
		self.assertTrue(frappe.db.exists("Storage Location", o.name), "phải còn nguyên sau khi bị chặn xoá")

	def test_o_thuong_van_vo_hieu_hoa_duoc(self):
		"""Đối chứng: ràng buộc CHỈ áp dụng cho ô la_o_chua_xep=1, không phải
		mọi ô — nếu không sẽ chặn nhầm thao tác vận hành bình thường."""
		o = _tao_o("9Z04010101")
		o.disabled = 1
		o.save(ignore_permissions=True)  # không được ném lỗi
		o.reload()
		self.assertTrue(o.disabled)


# --- Chuẩn mã 10 ký tự SPD (chốt 10/09/2026, rút gọn Task 1 11/09/2026) ----

MA_HOP_LE = "9Z01040302"


class TestCuongCheDinhDangMa(FrappeTestCase):
	"""Mã ô phải đúng chuẩn 10 ký tự — §5.5 đòi phần mềm kiểm định dạng khi tạo.

	Trước đây `ma_o` là ô chữ tự do, gõ gì cũng nhận. Đó là chỗ mà một mã sai
	lọt vào rồi được IN LÊN TEM dán kệ — sửa sau khi dán tem là thứ §5.3 cảnh
	báo riêng.
	"""

	def test_ma_dung_chuan_thi_nhan(self):
		o = _tao_o(MA_HOP_LE)
		self.assertEqual(o.name, MA_HOP_LE)

	def test_ma_tu_che_bi_tu_choi(self):
		with self.assertRaises(frappe.ValidationError):
			_tao_o("TEST-TU-CHE")

	def test_tach_du_nam_thanh_phan_vao_truong_rieng(self):
		# §5.5: bảng master phải có "mã 10 ký tự VÀ 5 trường thành phần"
		o = _tao_o("9Z07120405")
		self.assertEqual(
			(o.khu, o.day, o.khoang, o.tang, o.o),
			("9Z", "07", "12", "04", "05"),
		)

	def test_luu_san_dang_in_tren_nhan(self):
		o = _tao_o("9Z08010203")
		self.assertEqual(o.ma_in_nhan, "9Z0801-0203")


class TestOChuaXepDuocMienKiemDinhDang(FrappeTestCase):
	"""Ô CHUA-XEP là ô LÔ-GIC, không phải vị trí vật lý.

	Nó không bao giờ được in lên tem và không ứng với chỗ nào ngoài kho. Ép nó
	vào chuẩn 10 ký tự là bịa ra một địa chỉ không tồn tại — nên nó được miễn,
	qua chính cờ `la_o_chua_xep`.
	"""

	def test_o_chua_xep_khong_bi_ep_dinh_dang(self):
		# Tên riêng cho bài này, KHÔNG dùng tên thật `CHUA-XEP-<kho>`: tên thật
		# do `bat()` tạo và các file test khác cũng dựng, dễ đụng nhau; mà xoá
		# đi để dọn thì `on_trash` chặn (đúng thiết kế — ô này không xoá được).
		ten = "CHUA-XEP-TEST-MIEN-DINH-DANG"
		o = frappe.get_doc(
			{
				"doctype": "Storage Location",
				"ma_o": ten,
				"kho": "Kho Miyano - MYN",
				"la_o_chua_xep": 1,
			}
		)
		o.insert(ignore_permissions=True)
		self.assertEqual(o.name, ten)
		self.assertIsNone(o.khu)
