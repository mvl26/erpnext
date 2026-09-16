"""Móc điền NCC cho lô sinh từ chứng từ mua (spec khối C §4.3).

Vì sao móc này tồn tại: hộp thoại lô sẵn có của ERPNext trên dòng phiếu nhập
vẫn mở được và vẫn tạo lô KHÔNG có NCC. Spec chọn không chặn đường đó (chặn sẽ
vỡ các luồng kho khác dùng chung `Batch`), nên phải bảo đảm dữ liệu không thiếu
bất kể lô sinh bằng đường nào.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.vi_tri_kho.tests.test_hook_nhap import _tao_item

CONG_TY = "Miyano Việt Nam"


def _ncc_thu() -> str:
	ten = "_Test NCC Nhap Lo"
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
		"""Móc chỉ ĐIỀN CHỖ TRỐNG. Ghi đè là lặng lẽ sửa dữ liệu người khác đã khai."""
		ncc_khac = self.ncc
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
