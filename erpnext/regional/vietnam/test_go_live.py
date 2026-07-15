# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Tests for Vietnam go-live: configuration, opening-balance validation, readiness."""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.regional.vietnam.constants import VN_NAMING_SERIES
from erpnext.regional.vietnam.go_live import configure_go_live
from erpnext.regional.vietnam.test_setup import make_vn_company

# Far-future so the fiscal year never collides with real or seed fiscal years.
GO_LIVE_YEAR = 2099


def _series_options(doctype):
	return [o for o in (frappe.get_meta(doctype).get_field("naming_series").options or "").split("\n") if o]


class TestVietnamGoLiveConfig(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = make_vn_company("_Test VN GoLive", "TVGL")
		cls.result = configure_go_live(cls.company, fiscal_year=GO_LIVE_YEAR)

	def test_configure_returns_ok(self):
		self.assertTrue(self.result["ok"])
		self.assertEqual(self.result["fiscal_year"], str(GO_LIVE_YEAR))

	def test_configure_guards_non_vn_company(self):
		# A non-VN company (or missing) must be a no-op, not an error.
		self.assertFalse(configure_go_live(None)["ok"])

	def test_fiscal_year_created(self):
		self.assertTrue(frappe.db.exists("Fiscal Year", str(GO_LIVE_YEAR)))
		fy = frappe.get_doc("Fiscal Year", str(GO_LIVE_YEAR))
		self.assertEqual(str(fy.year_start_date), f"{GO_LIVE_YEAR}-01-01")
		self.assertEqual(str(fy.year_end_date), f"{GO_LIVE_YEAR}-12-31")

	def test_perpetual_inventory_and_valuation(self):
		self.assertTrue(frappe.db.get_value("Company", self.company, "enable_perpetual_inventory"))
		self.assertTrue(frappe.get_single("Stock Settings").valuation_method)

	def test_vn_naming_series_present(self):
		for doctype, series in VN_NAMING_SERIES:
			self.assertIn(series, _series_options(doctype), f"{series} missing from {doctype}")

	def test_naming_series_preserves_existing_options(self):
		# Adding the VN series must not wipe the shipped default options.
		self.assertIn("ACC-SINV-.YYYY.-", _series_options("Sales Invoice"))

	def test_vnd_currency_enabled(self):
		self.assertEqual(frappe.db.get_value("Company", self.company, "default_currency"), "VND")
		self.assertTrue(frappe.db.get_value("Currency", "VND", "enabled"))

	def test_configure_is_idempotent(self):
		# Re-run must not raise, duplicate the fiscal year, or duplicate series options.
		configure_go_live(self.company, fiscal_year=GO_LIVE_YEAR)
		self.assertEqual(frappe.db.count("Fiscal Year", {"year": str(GO_LIVE_YEAR)}), 1)
		for doctype, series in VN_NAMING_SERIES:
			self.assertEqual(_series_options(doctype).count(series), 1, f"{series} duplicated in {doctype}")


class TestVietnamRoleProfiles(FrappeTestCase):
	def test_creates_all_profiles(self):
		from erpnext.regional.vietnam.role_profiles import VN_ROLE_PROFILES, ensure_vn_role_profiles

		ensure_vn_role_profiles()
		for name in VN_ROLE_PROFILES:
			self.assertTrue(frappe.db.exists("Role Profile", name), f"missing Role Profile {name}")

	def test_profiles_have_expected_roles(self):
		from erpnext.regional.vietnam.role_profiles import ensure_vn_role_profiles

		ensure_vn_role_profiles()
		ketoan = [r.role for r in frappe.get_doc("Role Profile", "Kế toán").roles]
		self.assertIn("Accounts User", ketoan)
		truong = [r.role for r in frappe.get_doc("Role Profile", "Kế toán trưởng").roles]
		self.assertIn("Accounts Manager", truong)

	def test_is_idempotent(self):
		from erpnext.regional.vietnam.role_profiles import ensure_vn_role_profiles

		ensure_vn_role_profiles()
		ensure_vn_role_profiles()
		roles = [r.role for r in frappe.get_doc("Role Profile", "Kế toán trưởng").roles]
		self.assertEqual(len(roles), len(set(roles)), "duplicate roles after re-run")


def _make_customer(name, tax_id=None):
	return frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": name,
			"customer_group": "All Customer Groups",
			"territory": "All Territories",
			"tax_id": tax_id,
		}
	).insert(ignore_permissions=True)


class TestVietnamMasterData(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.regional.vietnam.master_data import seed_master_data

		cls.company = make_vn_company("_Test VN MData", "TVMD")
		seed_master_data(cls.company)

	def test_item_group_taxonomy_created(self):
		for group in ("Thiết bị y tế", "Vật tư y tế", "Thiết bị xét nghiệm"):
			self.assertTrue(frappe.db.exists("Item Group", group), f"missing Item Group {group}")

	def test_completeness_flags_customer_missing_mst(self):
		from erpnext.regional.vietnam.master_data import master_data_completeness

		cust = _make_customer("_Test VN NoMST")
		flagged = {(i["doctype"], i["name"]) for i in master_data_completeness(self.company)["issues"]}
		self.assertIn(("Customer", cust.name), flagged)

	def test_completeness_passes_complete_customer(self):
		from erpnext.regional.vietnam.master_data import master_data_completeness

		cust = _make_customer("_Test VN WithMST", tax_id="0312345678")
		flagged = {(i["doctype"], i["name"]) for i in master_data_completeness(self.company)["issues"]}
		self.assertNotIn(("Customer", cust.name), flagged)

	def test_seed_is_idempotent(self):
		from erpnext.regional.vietnam.master_data import seed_master_data

		seed_master_data(self.company)
		self.assertEqual(frappe.db.count("Item Group", {"item_group_name": "Thiết bị y tế"}), 1)
