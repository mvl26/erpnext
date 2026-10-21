"""Số lô NCC tách khỏi mã lô (spec `2026-10-19-so-lo-tach-khoi-ma-lo-design.md`).

Mã lô (tên bản ghi `Batch`) là khoá, mã vạch in nó. Số lô (`custom_so_lo`) là
chữ in trên bao bì NCC — được trùng giữa các mặt hàng — và là thứ mọi màn hình
cho người đọc.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.warehouse_operations.tests.test_hook_nhap import _tao_item

ITEM_LO = "_Test WMS So Lo A"


def _tao_lo(ten, item=ITEM_LO, **kw):
	if frappe.db.exists("Batch", ten):
		frappe.delete_doc("Batch", ten, force=True)
	return frappe.get_doc({"doctype": "Batch", "batch_id": ten, "item": item, **kw}).insert(
		ignore_permissions=True
	)


class TestTruongSoLo(FrappeTestCase):
	def setUp(self):
		_tao_item(ITEM_LO, co_lo=1)

	def test_lo_tao_tay_tu_dien_so_lo_bang_ma(self):
		lo = _tao_lo("SOLO-TAY-1")
		self.assertEqual(lo.custom_so_lo, "SOLO-TAY-1")

	def test_lo_sinh_theo_series_cua_mat_hang_cung_co_so_lo(self):
		# Không truyền batch_id: tên sinh trong `autoname`, SAU `before_insert`.
		lo = frappe.get_doc({"doctype": "Batch", "item": ITEM_LO}).insert(ignore_permissions=True)
		self.assertEqual(lo.custom_so_lo, lo.name)

	def test_title_field_la_so_lo(self):
		meta = frappe.get_meta("Batch")
		self.assertEqual(meta.title_field, "custom_so_lo")
		self.assertEqual(meta.show_title_field_in_link, 1)

	def test_patch_dien_lo_cu(self):
		from erpnext.warehouse_operations.patches.v1_0 import them_so_lo_ncc

		lo = _tao_lo("SOLO-CU-1")
		frappe.db.set_value("Batch", lo.name, "custom_so_lo", None)
		them_so_lo_ncc.execute()
		self.assertEqual(frappe.db.get_value("Batch", lo.name, "custom_so_lo"), "SOLO-CU-1")
		them_so_lo_ncc.execute()
		self.assertEqual(frappe.db.get_value("Batch", lo.name, "custom_so_lo"), "SOLO-CU-1")
