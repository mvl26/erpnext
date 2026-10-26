# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""R-10 — `dispatch.resend` chỉ cho vai trò quản trị thông báo sau go-live.

`frappe.only_for` bỏ qua kiểm tra khi chạy test, nên test bắt đúng tập vai trò mà `resend` truyền vào.
"""

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.supply_notification import constants, dispatch


class TestResendRoles(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def _vai_tro_duoc_phep(self, enabled):
		goi = MagicMock(side_effect=RuntimeError("dừng sau only_for"))
		with (
			patch("erpnext.supply_notification.dispatch.is_enabled", return_value=enabled),
			patch.object(frappe, "get_doc", return_value=MagicMock()),
			patch.object(frappe, "only_for", goi),
			self.assertRaises(RuntimeError),
		):
			dispatch.resend("x")
		return set(goi.call_args.args[0])

	def test_only_admin_role_once_enabled(self):
		self.assertEqual(self._vai_tro_duoc_phep(True), {constants.ADMIN_ROLE})

	def test_system_manager_still_allowed_while_flag_is_off(self):
		self.assertEqual(self._vai_tro_duoc_phep(False), {constants.ADMIN_ROLE, "System Manager"})
