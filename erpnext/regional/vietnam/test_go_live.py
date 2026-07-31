# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

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


def _acct(company, number):
	return frappe.db.get_value(
		"Account", {"company": company, "account_number": number, "is_group": 0}, "name"
	)


def _make_numberless_account(company):
	parent = frappe.db.get_value(
		"Account", {"company": company, "is_group": 1, "root_type": "Equity"}, "name"
	)
	return frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": "_Test Numberless Equity",
			"company": company,
			"parent_account": parent,
			"root_type": "Equity",
			"is_group": 0,
		}
	).insert(ignore_permissions=True).name


def _make_misnumbered_account(company, number):
	# A Balance-Sheet account carrying a P&L-range TT99 number: core's report_type
	# gate lets its opening entries through, only the number-prefix gate catches it.
	parent = frappe.db.get_value(
		"Account", {"company": company, "is_group": 1, "root_type": "Equity"}, "name"
	)
	return frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": f"_Test Misnumbered {number}",
			"account_number": number,
			"company": company,
			"parent_account": parent,
			"root_type": "Equity",
			"is_group": 0,
		}
	).insert(ignore_permissions=True).name


def _post_opening_je_by_account(company, lines, posting_date=None):
	je = frappe.new_doc("Journal Entry")
	je.company = company
	je.voucher_type = "Opening Entry"
	je.is_opening = "Yes"
	je.posting_date = posting_date or frappe.utils.nowdate()
	for account, dr, cr in lines:
		je.append("accounts", {"account": account, "debit_in_account_currency": dr, "credit_in_account_currency": cr})
	je.flags.ignore_permissions = True
	je.insert()
	je.submit()
	return je.name


class TestVietnamOpeningBalances(FrappeTestCase):
	# A fresh company per test: submitting an Opening JE releases the test savepoint,
	# so opening entries stay visible across methods within a run — isolate by company.

	def test_balanced_tt99_opening_with_receivable_passes(self):
		from erpnext.regional.vietnam.go_live import post_opening_journal_entry, validate_opening_balances

		company = make_vn_company("_Test VN Open Bal", "TOB1")
		customer = _make_customer("_Test VN Open Cust", tax_id="0311111111")
		post_opening_journal_entry(company, [("111", 1_000_000, 0), ("4211", 0, 1_000_000)])
		post_opening_journal_entry(
			company, [("131", 500_000, 0, "Customer", customer.name), ("4211", 0, 500_000)]
		)
		result = validate_opening_balances(company)
		self.assertTrue(result["ok"], result["checks"])
		self.assertEqual(result["totals"]["receivable_131"], 500_000)

	def test_non_tt99_account_fails(self):
		from erpnext.regional.vietnam.go_live import validate_opening_balances

		company = make_vn_company("_Test VN Open Num", "TON2")
		numberless = _make_numberless_account(company)
		_post_opening_je_by_account(company, [(_acct(company, "111"), 100, 0), (numberless, 0, 100)])
		result = validate_opening_balances(company)
		self.assertFalse(result["ok"])
		self.assertFalse(next(c for c in result["checks"] if c["name"] == "all_tt99")["ok"])

	def test_empty_opening_is_trivially_balanced(self):
		from erpnext.regional.vietnam.go_live import validate_opening_balances

		# No opening entries: nets to zero, nothing non-TT99, no orphan parties.
		company = make_vn_company("_Test VN Open Emp", "TOE3")
		self.assertTrue(validate_opening_balances(company)["ok"])

	def test_midyear_balanced_bs_only_on_date_passes(self):
		from erpnext.regional.vietnam.go_live import (
			go_live_readiness,
			post_opening_journal_entry,
			validate_opening_balances,
		)

		company = make_vn_company("_Test VN Open Mid", "TOM4")
		as_of = "2026-06-30"
		# Mid-year cutover: BS-only TB, the H1 result sits in equity (4212).
		post_opening_journal_entry(company, [("111", 800_000, 0), ("4212", 0, 800_000)], posting_date=as_of)
		result = validate_opening_balances(company, as_of=as_of)
		self.assertTrue(result["ok"], result["checks"])
		# go_live_readiness threads as_of through to the opening check.
		ready = go_live_readiness(company, as_of=as_of)
		self.assertTrue(_check_named(ready, "opening_balanced")["ok"])

	def test_midyear_pnl_numbered_account_fails(self):
		from erpnext.regional.vietnam.go_live import validate_opening_balances

		company = make_vn_company("_Test VN Open Mis", "TOM5")
		as_of = "2026-06-30"
		mis = _make_misnumbered_account(company, "5999")
		_post_opening_je_by_account(
			company, [(_acct(company, "111"), 100, 0), (mis, 0, 100)], posting_date=as_of
		)
		result = validate_opening_balances(company, as_of=as_of)
		self.assertFalse(result["ok"])
		self.assertFalse(_check_named(result, "bs_only")["ok"])
		# FY-start mode (no as_of) does not apply the mid-year gates.
		self.assertNotIn("bs_only", [c["name"] for c in validate_opening_balances(company)["checks"]])

	def test_midyear_off_date_opening_fails(self):
		from erpnext.regional.vietnam.go_live import post_opening_journal_entry, validate_opening_balances

		company = make_vn_company("_Test VN Open Dat", "TOM6")
		post_opening_journal_entry(company, [("112", 300, 0), ("4211", 0, 300)], posting_date="2026-01-01")
		result = validate_opening_balances(company, as_of="2026-06-30")
		self.assertFalse(result["ok"])
		self.assertFalse(_check_named(result, "on_cutover_date")["ok"])
		# The same data is a valid FY-start opening when no as_of is given.
		self.assertTrue(validate_opening_balances(company)["ok"])


def _check_named(result, name):
	return next(c for c in result["checks"] if c["name"] == name)


class TestVietnamGoLiveReadiness(FrappeTestCase):
	def test_fully_configured_is_all_green(self):
		from erpnext.regional.vietnam.go_live import (
			configure_go_live,
			go_live_readiness,
			mark_backup_verified,
		)
		from erpnext.regional.vietnam.role_profiles import ensure_vn_role_profiles

		company = make_vn_company("_Test VN Ready", "TVRD")
		configure_go_live(company, fiscal_year=GO_LIVE_YEAR)
		ensure_vn_role_profiles()
		mark_backup_verified(company)

		result = go_live_readiness(company)
		self.assertTrue(result["ok"], [c for c in result["checks"] if not c["ok"]])

	def test_missing_backup_marker_flips_that_check(self):
		from erpnext.regional.vietnam.go_live import configure_go_live, go_live_readiness
		from erpnext.regional.vietnam.role_profiles import ensure_vn_role_profiles

		company = make_vn_company("_Test VN Ready NB", "TVN2")
		configure_go_live(company, fiscal_year=GO_LIVE_YEAR)
		ensure_vn_role_profiles()
		# Deliberately no backup marker.
		result = go_live_readiness(company)
		self.assertFalse(result["ok"])
		self.assertFalse(_check_named(result, "backup_verified")["ok"])

	def test_cleared_default_flips_company_defaults(self):
		from erpnext.regional.vietnam.go_live import go_live_readiness, mark_backup_verified

		company = make_vn_company("_Test VN Ready CD", "TVN3")
		mark_backup_verified(company)
		frappe.db.set_value("Company", company, "default_income_account", None)
		result = go_live_readiness(company)
		self.assertFalse(_check_named(result, "company_defaults")["ok"])

	def test_non_vn_company_not_ready(self):
		from erpnext.regional.vietnam.go_live import go_live_readiness

		self.assertFalse(go_live_readiness("_Nonexistent Co")["ok"])
