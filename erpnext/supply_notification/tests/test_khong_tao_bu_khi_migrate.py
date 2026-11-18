# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""`bench migrate` không được tạo bù dữ liệu nghiệp vụ người dùng đã sửa hay xoá.

Quyết định 10/11/2026: phòng ban, điểm thông báo, mẫu câu và mẫu email HĐĐT chỉ gieo
một lần lúc dựng site. Trước đó mỗi lần migrate gọi lại `setup_supply_notification`
và đẻ phòng `Kho - M` trùng với phòng kho người dùng đã đặt tên riêng.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.einvoice import setup as einvoice_setup
from erpnext.setup import department_catalog
from erpnext.supply_notification import setup as sn_setup

ONE_TIME_SEEDS = (
	"erpnext.supply_notification.setup.setup_supply_notification",
	"erpnext.einvoice.setup.setup_einvoice",
)


class TestKhongTaoBuKhiMigrate(FrappeTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_after_migrate_khong_goi_ham_gieo_du_lieu(self):
		hooks = frappe.get_hooks("after_migrate", app_name="erpnext") or []
		for dotted in ONE_TIME_SEEDS:
			self.assertNotIn(
				dotted, hooks, f"{dotted} gieo dữ liệu nghiệp vụ, không được chạy mỗi lần migrate"
			)

	def test_migrate_khong_tao_lai_phong_ban_va_diem_da_xoa(self):
		# Custom field đã có thì einvoice.after_migrate không chạy DDL, test không commit giữa chừng.
		self.assertTrue(
			frappe.db.exists("Custom Field", {"dt": "Sales Invoice", "fieldname": "fast_invoice_no"})
		)

		# Người dùng "tắt" mọi phòng kho: bản cũ sẽ coi là thiếu và tạo `P. Kho`.
		company = sn_setup.default_company()
		for key in (department_catalog.STOCK, department_catalog.PURCHASE):
			while name := department_catalog.find_department(key, company):
				frappe.db.set_value("Department", name, "disabled", 1)

		# Người dùng xoá một điểm thông báo và một mẫu câu đã gieo.
		point = frappe.get_all(sn_setup.POINT_DOCTYPE, filters={"is_seed": 1}, pluck="name", limit=1)
		snippet = frappe.get_all(sn_setup.SNIPPET_DOCTYPE, pluck="name", limit=1)
		for doctype, names in ((sn_setup.POINT_DOCTYPE, point), (sn_setup.SNIPPET_DOCTYPE, snippet)):
			if names:
				frappe.db.delete(doctype, {"name": names[0]})
		frappe.db.delete("Email Template", {"name": einvoice_setup.DRAFT_TEMPLATE})

		before = self._counts()
		einvoice_setup.after_migrate()
		sn_setup.after_migrate()

		self.assertEqual(self._counts(), before)

	def _counts(self):
		return {
			doctype: frappe.db.count(doctype)
			for doctype in (
				"Department",
				sn_setup.POINT_DOCTYPE,
				sn_setup.SNIPPET_DOCTYPE,
				"Email Template",
			)
		}
