# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nhật ký đối soát Phiếu nhập ↔ Hóa đơn mua không sửa, không xóa được (YC5, spec 6.3.4)."""

import frappe
from frappe.tests.utils import FrappeTestCase

NHAT_KY = "Purchase Invoice PR Reconciliation Log"


class TestPurchaseInvoicePRReconciliationLog(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("nhat_ky_doi_soat")
		self.addCleanup(frappe.db.rollback, save_point="nhat_ky_doi_soat")
		self.dong = frappe.get_doc(
			{"doctype": NHAT_KY, "hoa_don": "_NK-HD-1", "su_kien": "Đối soát", "trang_thai": "Lệch"}
		).insert(ignore_permissions=True)

	def test_khong_vai_tro_nao_duoc_tao_sua_xoa(self):
		for p in frappe.get_meta(NHAT_KY).permissions:
			self.assertFalse(p.create or p.write or p.delete or p.get("import"), p.role)

	def test_khong_sua_duoc_ke_ca_khi_bo_qua_quyen(self):
		self.dong.trang_thai = "Khớp"
		self.assertRaisesRegex(
			frappe.ValidationError, "không sửa được", self.dong.save, ignore_permissions=True
		)

	def test_khong_xoa_duoc_ke_ca_administrator(self):
		self.assertRaisesRegex(
			frappe.ValidationError,
			"không xóa được",
			frappe.delete_doc,
			NHAT_KY,
			self.dong.name,
			ignore_permissions=True,
		)
