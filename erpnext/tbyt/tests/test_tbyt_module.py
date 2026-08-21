# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Module `tbyt` phải được app khai báo và phân giải được đường dẫn.

Nếu hai điều này sai thì `bench migrate` không tìm thấy DocType của module và
mọi task sau đều hỏng theo — nên đây là lưới an toàn đặt trước tất cả.
"""

import os

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.tbyt import constants


class TestTBYTModule(FrappeTestCase):
	def test_module_is_registered_in_the_app(self):
		self.assertIn("TBYT", frappe.get_module_list("erpnext"))

	def test_module_path_resolves_to_a_real_directory(self):
		path = frappe.get_module_path("TBYT")
		self.assertTrue(os.path.isdir(path), f"Không thấy thư mục module: {path}")

	def test_scope_doctype_map_covers_every_resolvable_scope(self):
		"""Bốn cấp mà resolver phân giải ở Item đều phải ánh xạ được sang DocType."""
		for scope in (
			constants.SCOPE_COMPANY,
			constants.SCOPE_OWNER,
			constants.SCOPE_AUTHORIZATION,
			constants.SCOPE_ITEM,
		):
			self.assertIn(scope, constants.SCOPE_DOCTYPE)

	def test_expiry_warning_threshold_is_ninety_days(self):
		self.assertEqual(constants.EXPIRY_WARNING_DAYS, 90)
