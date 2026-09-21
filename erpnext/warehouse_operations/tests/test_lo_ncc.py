"""Móc điền NCC cho lô sinh từ chứng từ mua (spec khối C §4.3).

Vì sao móc này tồn tại: hộp thoại lô sẵn có của ERPNext trên dòng phiếu nhập
vẫn mở được và vẫn tạo lô KHÔNG có NCC. Spec chọn không chặn đường đó (chặn sẽ
vỡ các luồng kho khác dùng chung `Batch`), nên phải bảo đảm dữ liệu không thiếu
bất kể lô sinh bằng đường nào.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.warehouse_operations.tests.test_hook_nhap import _tao_item

CONG_TY = "Miyano Việt Nam"


def _ncc_thu() -> str:
	ten = "_Test NCC Nhap Lo"
	if not frappe.db.exists("Supplier", ten):
		frappe.get_doc(
			{"doctype": "Supplier", "supplier_name": ten, "supplier_group": "All Supplier Groups"}
		).insert(ignore_permissions=True)
	return ten


def _ncc_thu_2() -> str:
	"""NCC thứ hai, KHÁC hẳn `_ncc_thu()` — dùng riêng cho bài kiểm tra "không ghi
	đè". Vòng sửa 1 (review): bản trước dùng CÙNG một NCC cho cả lô lẫn phiếu
	nhập, nên xoá hẳn guard `if doc.supplier: return` trong `lo_ncc.py` thì móc
	vẫn ghi lại đúng giá trị cũ (NCC của phiếu nhập trùng NCC đã khai trên lô) —
	`assertEqual` không phân biệt được "giữ nguyên" với "ghi đè bằng đúng giá trị
	cũ", nên bài không bắt được chính đột biến nó tuyên bố phải bắt.
	"""
	ten = "_Test NCC Nhap Lo 2"
	if not frappe.db.exists("Supplier", ten):
		frappe.get_doc(
			{"doctype": "Supplier", "supplier_name": ten, "supplier_group": "All Supplier Groups"}
		).insert(ignore_permissions=True)
	return ten


def _phieu_nhap_nhap(item: str, kho: str, ncc: str, qty=10):
	"""Phiếu nhập CÒN NHÁP — không submit."""
	pr = frappe.get_doc(
		{
			"doctype": "Purchase Receipt",
			"company": CONG_TY,
			"supplier": ncc,
			"items": [{"item_code": item, "qty": qty, "warehouse": kho, "rate": 1000}],
		}
	)
	pr.insert(ignore_permissions=True)
	return pr


class TestDienNccTuChungTu(FrappeTestCase):
	def setUp(self):
		self.ncc = _ncc_thu()
		self.item = _tao_item("_Test LoNcc Co Lo", co_lo=1)
		self.kho = frappe.db.get_value("Warehouse", {"company": CONG_TY, "is_group": 0}, "name")
		self.pr = _phieu_nhap_nhap(self.item, self.kho, self.ncc)

	def test_lo_tu_phieu_nhap_duoc_dien_ncc(self):
		lo = frappe.get_doc(
			{
				"doctype": "Batch",
				"batch_id": "_TEST-LONCC-001",
				"item": self.item,
				"reference_doctype": "Purchase Receipt",
				"reference_name": self.pr.name,
			}
		).insert(ignore_permissions=True)
		self.assertEqual(lo.supplier, self.ncc)

	def test_khong_ghi_de_ncc_da_co(self):
		"""Móc chỉ ĐIỀN CHỖ TRỐNG. Ghi đè là lặng lẽ sửa dữ liệu người khác đã khai.

		Vòng sửa 1 (review): `ncc_khac` PHẢI khác NCC của `self.pr` (`self.ncc`).
		Bản trước gán `ncc_khac = self.ncc` — cùng giá trị — nên xoá hẳn guard
		`if doc.supplier: return` trong `lo_ncc.py` thì móc vẫn lấy `supplier` từ
		`self.pr` (= `self.ncc`) và ghi đè `doc.supplier` thành đúng `ncc_khac`:
		`assertEqual` vẫn xanh dù cơ chế "không ghi đè" đã bị xoá sạch. Dùng NCC
		thứ hai để "giữ nguyên" và "ghi đè bằng giá trị của phiếu nhập" cho ra hai
		kết quả khác nhau — chỉ khi đó `assertEqual` mới thật sự phân biệt được.
		"""
		ncc_khac = _ncc_thu_2()
		lo = frappe.get_doc(
			{
				"doctype": "Batch",
				"batch_id": "_TEST-LONCC-002",
				"item": self.item,
				"supplier": ncc_khac,
				"reference_doctype": "Purchase Receipt",
				"reference_name": self.pr.name,
			}
		).insert(ignore_permissions=True)
		self.assertEqual(lo.supplier, ncc_khac)

	def test_lo_khong_tu_chung_tu_mua_thi_khong_dong_gi(self):
		"""Chốt âm: một đột biến bỏ hết điều kiện `reference_doctype` phải làm bài này đỏ.

		Không có bài này thì móc có thể đi lấy `supplier` của một Stock Entry
		(không có trường đó → None) hoặc tệ hơn, của một doctype tình cờ CÓ
		trường `supplier` nhưng không liên quan gì.
		"""
		lo = frappe.get_doc(
			{"doctype": "Batch", "batch_id": "_TEST-LONCC-003", "item": self.item}
		).insert(ignore_permissions=True)
		self.assertFalse(lo.supplier)


class TestChanKyTuLo(FrappeTestCase):
	"""Móc `doc_events["Batch"]["validate"]` — chặn ký tự Code 128 không mã hoá
	được ở MỌI đường tạo lô, không riêng `Batch Entry`.

	Vì sao phải có cả móc này lẫn phép kiểm trong `BatchEntry.validate`: lô còn
	sinh bằng hộp thoại lô sẵn có của ERPNext trên dòng phiếu nhập, bằng nhập
	tay trên doctype `Batch`, bằng Data Import. Bịt một đường mà bỏ các đường
	kia thì tới lúc in, JsBarcode ném lỗi, `barcode.js` nuốt lỗi, và tem của lô
	này in ra mã vạch của lô LIỀN TRƯỚC trong cùng xấp.
	"""

	def setUp(self):
		self.item = _tao_item("_Test LoNCC KyTu", co_lo=1)

	def test_tao_batch_truc_tiep_co_dau_tieng_viet_bi_chan(self):
		"""KHÔNG đi qua `Batch Entry` — tạo thẳng doctype `Batch`."""
		with self.assertRaises(frappe.ValidationError) as ctx:
			frappe.get_doc(
				{"doctype": "Batch", "batch_id": "_TEST-LÔ-KYTU", "item": self.item}
			).insert(ignore_permissions=True)
		self.assertIn("U+", str(ctx.exception))

	def test_tao_batch_truc_tiep_co_en_dash_bi_chan(self):
		with self.assertRaises(frappe.ValidationError) as ctx:
			frappe.get_doc(
				{"doctype": "Batch", "batch_id": "_TEST\u2013KYTU", "item": self.item}
			).insert(ignore_permissions=True)
		self.assertIn("U+2013", str(ctx.exception))

	def test_batch_ascii_thuan_van_tao_duoc(self):
		"""Vế còn lại: móc KHÔNG được chặn nhầm lô hợp lệ."""
		lo = frappe.get_doc(
			{"doctype": "Batch", "batch_id": "_TEST-LONCC-KYTU-OK", "item": self.item}
		).insert(ignore_permissions=True)
		self.assertEqual(lo.batch_id, "_TEST-LONCC-KYTU-OK")

	def test_lo_cu_luu_lai_duoc_du_khong_sua_duoc_ten(self):
		"""`validate` chạy MỌI lần lưu, nên móc phải chỉ kiểm lúc TẠO MỚI.

		`batch_id` là tên bản ghi: một lô cũ lỡ có ký tự xấu thì không sửa được
		nữa. Nếu móc kiểm cả lúc cập nhật thì bản ghi đó thành một thứ KHÔNG AI
		LƯU LẠI ĐƯỢC — ai mở form `Batch` sửa hạn dùng hay nhà cung cấp rồi bấm
		Save là nổ, trong khi thứ làm nó nổ lại không sửa được.

		(KHÔNG phải mọi đường cập nhật: `recalculate_batch_qty` của ERPNext
		dùng `db_set`, mà `db_set` không kích `validate` — xem
		`frappe/model/document.py:1240`.)
		"""
		lo = frappe.get_doc(
			{"doctype": "Batch", "batch_id": "_TEST-LONCC-KYTU-CU", "item": self.item}
		).insert(ignore_permissions=True)
		# Giả lập một bản ghi cũ mang ký tự xấu, đúng cách nó tồn tại trong CSDL
		# (ghi thẳng, không qua validate), rồi lưu lại như ERPNext vẫn làm khi
		# cập nhật `batch_qty`.
		frappe.db.set_value("Batch", lo.name, "batch_id", "_TEST-LÔ-CU", update_modified=False)
		lo.reload()
		self.assertEqual(lo.batch_id, "_TEST-LÔ-CU")  # bản ghi ĐANG mang ký tự xấu

		# Khẳng định DUY NHẤT của bài này: lưu lại KHÔNG nổ. (Không khẳng định
		# `batch_id` giữ nguyên sau khi lưu — `Batch` của ERPNext tự đặt lại
		# trường đó bằng tên bản ghi, đó là hành vi của nó chứ không phải của
		# móc này.)
		lo.save(ignore_permissions=True)


class TestCustomFieldDaCai(FrappeTestCase):
	"""Patch chạy rồi thì field phải có. Không có bài này thì Task 2-9 hỏng vì
	một lý do (patch chưa chạy) mà thông báo lỗi không hề nhắc tới."""

	def test_ba_field_ton_tai(self):
		for dt, fn in (
			("Batch", "custom_so_goi"),
			("Batch", "custom_o_in_tem"),
			("Item", "custom_thong_so_tem"),
		):
			self.assertTrue(
				frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fn}),
				f"thiếu {dt}.{fn} — chạy `bench --site erptest.local migrate`",
			)
