# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Module `einvoice` đã đăng ký, và luồng HĐĐT cũ (SI-driven) đã gỡ sạch.

Luồng cũ (Task 40—44) tự phát hành hóa đơn khi submit Sales Invoice. Nó trái
nguyên tắc A2 của đặc tả Fast v2.0 ("không hành động nào tự chạy ngầm không
hỏi") nên bị thay hẳn bằng luồng Fast chạy trên Delivery Note. Bộ test này là
lưới an toàn: nếu ai đó vô tình dựng lại một mảnh của luồng cũ, nó đỏ ngay.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

OLD_LOG_DOCTYPE = "Vietnam E Invoice Log"


class TestEInvoiceModule(FrappeTestCase):
	def test_einvoice_module_is_registered_in_the_app(self):
		"""DocType HĐĐT sẽ nằm trong module này, nên nó phải được app khai báo."""
		self.assertIn("Einvoice", frappe.get_module_list("erpnext"))

	def test_einvoice_module_path_resolves(self):
		"""frappe phải phân giải được module -> thư mục, nếu không migrate sẽ hỏng."""
		import os

		path = frappe.get_module_path("Einvoice")
		self.assertTrue(os.path.isdir(path), f"Không thấy thư mục module: {path}")

	def test_old_si_driven_flow_module_is_gone(self):
		with self.assertRaises(ImportError):
			import erpnext.regional.vietnam.e_invoice

	def test_old_provider_adapter_package_is_gone(self):
		with self.assertRaises(ImportError):
			import erpnext.regional.vietnam.e_invoice_providers

	def test_old_log_doctype_is_gone(self):
		self.assertFalse(frappe.db.exists("DocType", OLD_LOG_DOCTYPE))

	def test_no_vn_einvoice_custom_fields_remain(self):
		"""Custom field của luồng cũ trên Company và Sales Invoice phải sạch."""
		leftover = frappe.get_all(
			"Custom Field",
			filters={"fieldname": ["like", "vn_einvoice%"]},
			fields=["dt", "fieldname"],
		)
		self.assertEqual(leftover, [], f"Còn sót custom field luồng cũ: {leftover}")

	def test_vn_setup_does_not_recreate_the_old_custom_fields(self):
		"""Chạy lại setup VN không được dựng lại các trường vừa gỡ."""
		from erpnext.regional.vietnam import setup as vn_setup

		self.assertFalse(hasattr(vn_setup, "_make_e_invoice_custom_fields"))

	def test_sales_invoice_submit_no_longer_triggers_issuance(self):
		"""Hook tự phát hành khi submit Sales Invoice phải được gỡ khỏi hooks.py."""
		handlers = frappe.get_hooks("doc_events").get("Sales Invoice", {}).get("on_submit") or []
		self.assertFalse(
			[h for h in handlers if "e_invoice" in h],
			f"Vẫn còn hook phát hành HĐĐT khi submit Sales Invoice: {handlers}",
		)
