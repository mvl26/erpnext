"""Cờ bật quản lý vị trí ở cấp kho.

Hai điều bài này khoá lại:

1. Cờ là READ-ONLY. Bật quản lý vị trí không phải tích một ô — nó phải tạo
   ô CHUA-XEP, chuyển đổi tồn hiện có tách theo từng lô, rồi đối soát. Ai
   tích tay vào cờ là bỏ qua sạch các bước đó và hệ sai ngay từ giây đầu.
   Chỉ Warehouse Location Setup (Task 11-13) được đặt.

2. Hàm hỏi trạng thái đọc qua CACHE. Hook chạy trên MỌI dòng SLE nên không
   thể truy vấn DB mỗi lần. Hệ quả: bật/tắt phải xoá cache, nếu không thao
   tác bật sẽ không có hiệu lực và người vận hành tưởng chức năng hỏng.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.warehouse_operations.vitri import kho as vk
from erpnext.warehouse_operations.vitri.bat_kho import tao_o_chua_xep

KHO = "Kho Miyano - MYN"


class _CoTienDeKho(FrappeTestCase):
	"""Lớp nền: khẳng định tường minh dữ liệu kho mà file test này dựa vào.

	Cùng khuôn với `_CoTienDeKho` trong `test_storage_location.py` (Task 2):
	không được để bài test xanh vô cớ nhờ dữ liệu tình cờ có sẵn trên site,
	cũng không được đỏ khó hiểu ở một chỗ không liên quan tới cái đang thử.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		if not frappe.db.exists("Warehouse", KHO):
			raise AssertionError(
				f"Tiền đề thiếu: Warehouse '{KHO}' không tồn tại trên site erptest.local. "
				"Bài test cờ quản lý vị trí cần kho lá này có sẵn."
			)
		if frappe.db.get_value("Warehouse", KHO, "is_group"):
			raise AssertionError(
				f"Tiền đề sai: Warehouse '{KHO}' đang là kho NHÓM (is_group=1), nhưng bài "
				"test cần một kho lá."
			)
		if not frappe.db.exists("Warehouse", "Stores - MYN"):
			raise AssertionError(
				"Tiền đề thiếu: Warehouse 'Stores - MYN' không tồn tại trên site erptest.local. "
				"Bài test o_chua_xep() cần kho này để thử trường hợp kho chưa bật quản lý vị trí."
			)


class TestCustomField(FrappeTestCase):
	def test_field_ton_tai(self):
		self.assertTrue(
			frappe.db.exists("Custom Field", {"dt": "Warehouse", "fieldname": "custom_quan_ly_vi_tri"})
		)

	def test_field_la_read_only(self):
		ro = frappe.db.get_value(
			"Custom Field", {"dt": "Warehouse", "fieldname": "custom_quan_ly_vi_tri"}, "read_only"
		)
		self.assertEqual(ro, 1, "Cờ phải read-only — xem docstring đầu file")


class TestHoiTrangThai(_CoTienDeKho):
	def setUp(self):
		# Lưu giá trị THẬT của cờ. `tearDown` bản trước ghi cứng 0 — từ
		# 10/09/2026 `Kho Miyano - MYN` đã bật thật, nên nếu một lần chạy bị
		# giết sau khi có commit ở giữa, nhóm bài này tắt hộ kho của chủ dự án.
		# Nhóm chỉ lật cờ chứ không xoá dữ liệu nên hậu quả nhẹ hơn hẳn
		# `_don_sach` (xem `kho_thu.py`), nhưng bật lại thì phải `dong_bo_lai`.
		self._co_cu = frappe.db.get_value("Warehouse", KHO, "custom_quan_ly_vi_tri")

	def tearDown(self):
		frappe.db.set_value("Warehouse", KHO, "custom_quan_ly_vi_tri", self._co_cu)
		vk.xoa_cache_kho(KHO)

	def test_kho_chua_bat_tra_false(self):
		frappe.db.set_value("Warehouse", KHO, "custom_quan_ly_vi_tri", 0)
		vk.xoa_cache_kho(KHO)
		self.assertFalse(vk.kho_co_quan_ly_vi_tri(KHO))

	def test_kho_da_bat_tra_true(self):
		frappe.db.set_value("Warehouse", KHO, "custom_quan_ly_vi_tri", 1)
		vk.xoa_cache_kho(KHO)
		self.assertTrue(vk.kho_co_quan_ly_vi_tri(KHO))

	def test_khong_xoa_cache_thi_doc_ra_gia_tri_cu(self):
		# Bài này KHÔNG kiểm tra một tính năng — nó ghi lại cái bẫy.
		#
		# Lưu ý phiên bản: trên Frappe 15.113.4, `frappe.db.set_value` TỰ gọi
		# `frappe.clear_document_cache` (apps/frappe/frappe/database/database.py,
		# trong `set_value`, trước khi chạy câu UPDATE) — nên ghi bằng
		# `frappe.db.set_value` không còn tái hiện được cái bẫy nữa. Đoạn ghi thứ
		# hai dưới đây cố tình dùng SQL thô để mô phỏng đúng hình dạng của các
		# đường ghi KHÔNG tự xoá cache (SQL thô, bulk update, patch) — dạng mà
		# Task 7 / 11-13 vẫn có thể chạm phải. Không đổi thứ tự các dòng: lần đọc
		# assertFalse đầu tiên có tác dụng NẠP cache với giá trị 0, để lần ghi SQL
		# thô sau đó thật sự để lại cache cũ.
		frappe.db.set_value("Warehouse", KHO, "custom_quan_ly_vi_tri", 0)
		vk.xoa_cache_kho(KHO)
		self.assertFalse(vk.kho_co_quan_ly_vi_tri(KHO))  # nạp cache với giá trị 0

		frappe.db.sql("update `tabWarehouse` set custom_quan_ly_vi_tri = 1 where name = %s", KHO)
		# cố tình KHÔNG xoá cache
		self.assertFalse(vk.kho_co_quan_ly_vi_tri(KHO), "get_cached_value vẫn trả giá trị cũ")
		vk.xoa_cache_kho(KHO)
		self.assertTrue(vk.kho_co_quan_ly_vi_tri(KHO))

	def test_kho_khong_ton_tai_tra_false(self):
		self.assertFalse(vk.kho_co_quan_ly_vi_tri("Kho Không Có Thật - XX"))


class TestOChuaXep(_CoTienDeKho):
	def test_kho_chua_co_o_chua_xep_tra_none(self):
		self.assertIsNone(vk.o_chua_xep("Stores - MYN"))


class TestOChuaXepSaiDangBiBao(_CoTienDeKho):
	"""CRITICAL 2 (review điều phối, sau khi 147/147 bài "xong"): trước đây
	`o_chua_xep()` chỉ hỏi `frappe.db.exists` — một bản ghi trùng mã nhưng
	`disabled=1` (hoặc sai kho/không phải cờ la_o_chua_xep/là ô nhóm) vẫn
	được coi là ô CHUA-XEP hợp lệ, khiến FEFO (lọc `disabled=0`) và hook ghi
	sổ (không lọc gì) đọc ra HAI kết luận khác nhau về cùng một ô — đúng cơ
	chế "một checkbox làm đứng cả kho". Dựng bản ghi malformed bằng
	`frappe.db.set_value` (KHÔNG qua `.save()`) — sau khi có validate chặn ở
	`StorageLocation`, không còn cách nào tạo được trạng thái này qua đường
	bình thường; đây chính là lý do phải phòng thủ ở tầng ĐỌC (`o_chua_xep`)
	chứ không chỉ ở tầng GHI (`validate`) — dữ liệu cũ hoặc ghi tay qua Data
	Import vẫn có thể mang hình dạng này.
	"""

	def setUp(self):
		self.kho = "Stores - MYN"
		ma = vk.ma_o_chua_xep(self.kho)
		frappe.db.sql("delete from `tabStorage Location` where name=%s", (ma,))
		# Dựng lại bằng hàm production, không tự `insert()` — xem docstring
		# `bat_kho.tao_o_chua_xep`.
		self.ma = tao_o_chua_xep(self.kho)

	def tearDown(self):
		frappe.db.sql("delete from `tabStorage Location` where name=%s", (self.ma,))

	def test_disabled_bi_bao_khong_tra_ve_lang_le(self):
		frappe.db.set_value("Storage Location", self.ma, "disabled", 1)
		with self.assertRaises(frappe.ValidationError) as ctx:
			vk.o_chua_xep(self.kho)
		self.assertIn(self.ma, str(ctx.exception))

	def test_sai_kho_bi_bao(self):
		frappe.db.set_value("Storage Location", self.ma, "kho", "Kho Miyano - MYN")
		with self.assertRaises(frappe.ValidationError):
			vk.o_chua_xep(self.kho)

	def test_dung_dang_thi_khong_bao(self):
		# Đối chứng: bản ghi ĐÚNG dạng phải trả về bình thường, không throw.
		self.assertEqual(vk.o_chua_xep(self.kho), self.ma)
