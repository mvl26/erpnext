# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""`setup_einvoice()` chạy mỗi lần migrate không được tự cấp quyền — chỉ đồng bộ RBAC được ghi Custom DocPerm."""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.einvoice.setup import ROLE_STAFF, setup_einvoice

FEI = "Fast EInvoice Document"


class TestEInvoiceRoles(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def tearDown(self):
		frappe.db.rollback()

	def test_after_migrate_does_not_grant_permissions(self):
		# Custom field đã có thì setup_einvoice không chạy DDL, test không commit giữa chừng.
		self.assertTrue(
			frappe.db.exists("Custom Field", {"dt": "Sales Invoice", "fieldname": "fast_invoice_no"})
		)
		self.assertTrue(frappe.db.exists("Custom DocPerm", {"parent": FEI, "role": ROLE_STAFF}))

		frappe.db.delete("Custom DocPerm", {"parent": FEI, "role": ROLE_STAFF})
		setup_einvoice()

		self.assertFalse(frappe.db.exists("Custom DocPerm", {"parent": FEI, "role": ROLE_STAFF}))


class TestChiefAccountantOnly(FrappeTestCase):
	"""T44 — C4: chỉ Kế toán trưởng HĐĐT tiêu số hóa đơn thật."""

	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def _roles(self, roles, enabled):
		from unittest.mock import patch

		from erpnext.einvoice.setup import is_chief_accountant

		with (
			patch("erpnext.einvoice.setup.is_enabled", return_value=enabled),
			patch.object(frappe, "get_roles", return_value=roles),
		):
			return is_chief_accountant()

	def test_system_manager_only_is_not_chief_once_enabled(self):
		self.assertFalse(self._roles(["Guest", "System Manager"], True))

	def test_chief_role_is_chief(self):
		from erpnext.einvoice.setup import ROLE_CHIEF

		self.assertTrue(self._roles(["Guest", ROLE_CHIEF], True))
		self.assertTrue(self._roles(["Guest", ROLE_CHIEF], False))

	def test_system_manager_keeps_working_while_flag_is_off(self):
		self.assertTrue(self._roles(["Guest", "System Manager"], False))
