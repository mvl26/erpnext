import dataclasses
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.access.permissions import settings
from erpnext.access.permissions.settings import sync_module_profiles, sync_settings
from erpnext.access.tests.helpers import small_matrix


def limit(field):
	return frappe.db.get_single_value("MVL Approval Limits", field)


class TestSettings(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def matrix(self, **values):
		m = small_matrix()
		m.settings = {
			"MVL Approval Limits": {"h1": 5000000},
			"Company::Nope-" + frappe.generate_hash(length=6): {"exception_budget_approver_role": "x"},
			"guarded": {"MVL Approval Limits.h2": "no_negative_bins"},
		}
		m.settings["MVL Approval Limits"].update(values)
		return m

	def test_plain_setting_applied_and_second_run_writes_nothing(self):
		m = self.matrix()
		audit = sync_settings(m)
		self.assertEqual(float(limit("h1")), 5000000)
		self.assertTrue(any("not found" in a for a in audit))
		with patch.object(frappe.db, "set_single_value") as w:
			sync_settings(m)
			w.assert_not_called()

	def test_guarded_blocked_keeps_value_and_audits(self):
		m = self.matrix(h2=7)
		before = limit("h2")
		with patch.dict(settings.CHECKS, {"no_negative_bins": lambda: False}):
			audit = sync_settings(m)
		self.assertEqual(limit("h2"), before)
		self.assertTrue(any("MVL Approval Limits.h2" in a and "no_negative_bins" in a for a in audit))

	def test_guarded_passes_when_check_true(self):
		m = self.matrix(h2=7)
		with patch.dict(settings.CHECKS, {"no_negative_bins": lambda: True}):
			sync_settings(m)
		self.assertEqual(float(limit("h2")), 7)

	def test_two_factor_set_on_throwaway_roles(self):
		m = self.matrix()
		for code in settings.TWO_FA_CODES:
			name = f"T8-{code}-{frappe.generate_hash(length=6)}"
			frappe.get_doc({"doctype": "Role", "role_name": name, "two_factor_auth": 0}).insert()
			m.roles[code] = dataclasses.replace(m.roles[code], names=(name,))
		sync_settings(m)
		for code in settings.TWO_FA_CODES:
			self.assertEqual(frappe.db.get_value("Role", m.role_names(code)[0], "two_factor_auth"), 1)
		with patch.object(frappe.db, "set_value") as w:
			sync_settings(m)
			w.assert_not_called()

	def test_guarded_equal_value_needs_no_check(self):
		m = self.matrix(h3=9)
		m.settings["guarded"] = {"MVL Approval Limits.h3": "no_negative_bins"}
		frappe.db.set_single_value("MVL Approval Limits", "h3", 9)

		def boom():
			raise AssertionError("check must not run")

		with patch.dict(settings.CHECKS, {"no_negative_bins": boom}):
			sync_settings(m)

	def test_unknown_check_audited(self):
		m = self.matrix(h3=3)
		m.settings["guarded"] = {"MVL Approval Limits.h3": "nope"}
		audit = sync_settings(m)
		self.assertTrue(any("unknown check nope" in a for a in audit))

	def test_guards_run_against_site_data(self):
		self.assertIsInstance(settings.no_negative_bins(), bool)
		self.assertIsInstance(settings.no_open_orders_with_rate_mismatch(), bool)
		self.assertIsInstance(settings.password_policy_ok(), bool)

	def test_password_policy_logic(self):
		for policy, expected in (
			("", False),
			(None, False),
			("{first_name}", True),
			("{no_such_field}", False),
		):
			with patch.object(frappe.db, "get_single_value", return_value=policy):
				self.assertIs(settings.password_policy_ok(), expected, policy)

	def test_module_profile(self):
		m = small_matrix()
		m.module_profiles = {"MVL PDA": {"allow_modules": ["Stock", "Warehouse Operations"]}}
		sync_module_profiles(m)
		blocked = {r.module for r in frappe.get_doc("Module Profile", "MVL PDA").block_modules}
		self.assertIn("Accounts", blocked)
		self.assertNotIn("Stock", blocked)
		with patch("frappe.model.document.Document.save") as s:
			sync_module_profiles(m)
			s.assert_not_called()
