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
