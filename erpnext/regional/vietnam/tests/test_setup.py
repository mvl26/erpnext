# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tests for the Vietnam company-setup hook (module/master-data account wiring)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.controllers.accounts_controller import get_taxes_and_charges

CHART_NAME = "Vietnam - Chart of Accounts (Thông tư 99/2025/TT-BTC)"

HUU_HINH = "Tài sản cố định hữu hình"
VO_HINH = "Tài sản cố định vô hình"


def make_vn_company(name, abbr):
	company = frappe.get_doc(
		{
			"doctype": "Company",
			"company_name": name,
			"abbr": abbr,
			"default_currency": "VND",
			"country": "Vietnam",
			"chart_of_accounts": CHART_NAME,
			"enable_perpetual_inventory": 1,
		}
	)
	company.flags.ignore_permissions = True
	company.insert()
	return company.name


def acct(company, number):
	return frappe.db.get_value(
		"Account", {"company": company, "account_number": number, "is_group": 0}, "name"
	)


def company_account_number(company, field):
	account = frappe.db.get_value("Company", company, field)
	return frappe.db.get_value("Account", account, "account_number") if account else None


def mode_of_payment_account(mode, company):
	if not frappe.db.exists("Mode of Payment", mode):
		return None
	parent = frappe.get_doc("Mode of Payment", mode)
	for row in parent.accounts:
		if row.company == company:
			return row.default_account
	return None


def _ensure_service_item():
	code = "_Test VN Service Item"
	if not frappe.db.exists("Item", code):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 0,
			}
		).insert(ignore_permissions=True)
	return code


def _ensure_customer():
	name = "_Test VN Customer"
	if not frappe.db.exists("Customer", name):
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": name,
				"customer_group": "All Customer Groups",
				"territory": "All Territories",
			}
		).insert(ignore_permissions=True)
	return name


def _ensure_supplier():
	name = "_Test VN Supplier"
	if not frappe.db.exists("Supplier", name):
		frappe.get_doc(
			{"doctype": "Supplier", "supplier_name": name, "supplier_group": "All Supplier Groups"}
		).insert(ignore_permissions=True)
	return name


def asset_category_numbers(category, company):
	if not frappe.db.exists("Asset Category", category):
		return None
	cat = frappe.get_doc("Asset Category", category)
	for row in cat.accounts:
		if row.company_name == company:

			def num(a):
				return frappe.db.get_value("Account", a, "account_number") if a else None

			return {
				"fixed": num(row.fixed_asset_account),
				"accum": num(row.accumulated_depreciation_account),
				"dep": num(row.depreciation_expense_account),
				"cwip": num(row.capital_work_in_progress_account),
			}
	return None


def _inject_orphan_asset_category_row(category, ghost_company):
	"""Write a row for a company that does not exist, bypassing validation.

	Mirrors how the rot appears in real life: a company is created, its Asset
	Category row is written, and the company (with its accounts) later goes away —
	leaving a row that no longer validates.
	"""
	row = frappe.get_doc(
		{
			"doctype": "Asset Category Account",
			"parent": category,
			"parenttype": "Asset Category",
			"parentfield": "accounts",
			"idx": 99,
			"company_name": ghost_company,
			"fixed_asset_account": f"211 - Tài sản cố định hữu hình - {ghost_company}",
			"accumulated_depreciation_account": f"2141 - Hao mòn TSCĐ hữu hình - {ghost_company}",
			"depreciation_expense_account": f"6424 - Chi phí khấu hao TSCĐ - {ghost_company}",
			"capital_work_in_progress_account": f"2411 - Mua sắm TSCĐ - {ghost_company}",
		}
	)
	row.name = f"_test-orphan-{frappe.scrub(category)}"
	row.db_insert()
	return row.name


class TestVietnamAssetCategoryHygiene(FrappeTestCase):
	"""A row left by a deleted company must never block setup for another company.

	``Asset Category`` is global with a per-company child table, so Frappe validates
	the links of EVERY row on save. One stale row (accounts gone with its company)
	therefore fails the save for an unrelated company — and because the VN hook runs
	inside ``install_country_fixtures``, that failure aborts the company creation.
	"""

	GHOST = "_Test VN Ghost Co"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# A first VN company guarantees both Asset Categories exist to be polluted.
		cls.company = make_vn_company("_Test VN Hygiene A", "TVHA")

	def test_company_creation_survives_and_prunes_orphan_rows(self):
		self.assertFalse(frappe.db.exists("Company", self.GHOST))
		for category in (HUU_HINH, VO_HINH):
			_inject_orphan_asset_category_row(category, self.GHOST)

		second = make_vn_company("_Test VN Hygiene B", "TVHB")

		for category in (HUU_HINH, VO_HINH):
			companies = [r.company_name for r in frappe.get_doc("Asset Category", category).accounts]
			self.assertNotIn(self.GHOST, companies, f"orphan row survived on {category}")
			self.assertIn(second, companies)
			self.assertIn(self.company, companies)  # live companies keep their wiring

	def test_deleting_a_company_takes_its_asset_category_rows_with_it(self):
		"""No new orphans: Company.on_trash must clear the rows it left behind."""
		doomed = make_vn_company("_Test VN Hygiene C", "TVHC")
		self.assertTrue(
			any(r.company_name == doomed for r in frappe.get_doc("Asset Category", HUU_HINH).accounts)
		)

		frappe.delete_doc("Company", doomed, ignore_permissions=True)

		for category in (HUU_HINH, VO_HINH):
			companies = [r.company_name for r in frappe.get_doc("Asset Category", category).accounts]
			self.assertNotIn(doomed, companies, f"deleted company left a row on {category}")


class TestVietnamCompanySetup(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = make_vn_company("_Test VN Setup", "TVSU")

	def test_mode_of_payment_wired_to_tt99(self):
		self.assertEqual(mode_of_payment_account("Cash", self.company), acct(self.company, "111"))
		self.assertEqual(mode_of_payment_account("Bank", self.company), acct(self.company, "112"))

	def test_hr_payroll_accounts_wired_to_tt99(self):
		# tạm ứng -> 141, phải trả người lao động (lương + hoàn ứng chi phí) -> 334
		self.assertEqual(company_account_number(self.company, "default_employee_advance_account"), "141")
		self.assertEqual(company_account_number(self.company, "default_expense_claim_payable_account"), "334")
		self.assertEqual(company_account_number(self.company, "default_payroll_payable_account"), "334")

	def test_setup_is_idempotent(self):
		from erpnext.regional.vietnam.setup import setup

		# The hook already ran on company creation; running it again must not duplicate.
		setup(self.company)
		setup(self.company)

		for mode in ("Cash", "Bank"):
			rows = [r for r in frappe.get_doc("Mode of Payment", mode).accounts if r.company == self.company]
			self.assertEqual(len(rows), 1, f"duplicate {mode} MoP row")
		for category in (HUU_HINH, VO_HINH):
			rows = [
				r
				for r in frappe.get_doc("Asset Category", category).accounts
				if r.company_name == self.company
			]
			self.assertEqual(len(rows), 1, f"duplicate {category} row")

	def _gl_by_number(self, voucher_no):
		result = {}
		for r in frappe.get_all(
			"GL Entry",
			filters={"voucher_no": voucher_no, "is_cancelled": 0, "company": self.company},
			fields=["account", "debit", "credit"],
		):
			num = frappe.db.get_value("Account", r.account, "account_number")
			agg = result.setdefault(num, [0.0, 0.0])
			agg[0] += r.debit
			agg[1] += r.credit
		return result

	def test_sales_invoice_posts_to_tt99(self):
		item = _ensure_service_item()
		customer = _ensure_customer()
		template = frappe.db.get_value(
			"Sales Taxes and Charges Template",
			{"title": "GTGT bán ra 10%", "company": self.company},
			"name",
		)
		si = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": self.company,
				"customer": customer,
				"taxes_and_charges": template,
				"items": [{"item_code": item, "qty": 1, "rate": 10_000_000}],
			}
		)
		for tax in get_taxes_and_charges("Sales Taxes and Charges Template", template):
			si.append("taxes", tax)
		si.flags.ignore_permissions = True
		si.insert()
		si.submit()

		gl = self._gl_by_number(si.name)
		self.assertEqual(gl.get("131"), [11_000_000, 0])  # phải thu khách hàng (Nợ)
		self.assertEqual(gl.get("511"), [0, 10_000_000])  # doanh thu (Có)
		self.assertEqual(gl.get("33311"), [0, 1_000_000])  # GTGT đầu ra (Có)

	def test_purchase_invoice_posts_to_tt99(self):
		item = _ensure_service_item()
		supplier = _ensure_supplier()
		template = frappe.db.get_value(
			"Purchase Taxes and Charges Template",
			{"title": "GTGT mua vào 10%", "company": self.company},
			"name",
		)
		pi = frappe.get_doc(
			{
				"doctype": "Purchase Invoice",
				"company": self.company,
				"supplier": supplier,
				"taxes_and_charges": template,
				"items": [
					{
						"item_code": item,
						"qty": 1,
						"rate": 5_000_000,
						"expense_account": acct(self.company, "632"),
					}
				],
			}
		)
		for tax in get_taxes_and_charges("Purchase Taxes and Charges Template", template):
			pi.append("taxes", tax)
		pi.flags.ignore_permissions = True
		pi.insert()
		pi.submit()

		gl = self._gl_by_number(pi.name)
		self.assertEqual(gl.get("632"), [5_000_000, 0])  # giá vốn / chi phí (Nợ)
		self.assertEqual(gl.get("1331"), [500_000, 0])  # GTGT được khấu trừ (Nợ)
		self.assertEqual(gl.get("331"), [0, 5_500_000])  # phải trả người bán (Có)

	def test_asset_categories_wired_to_tt99(self):
		self.assertEqual(
			asset_category_numbers(HUU_HINH, self.company),
			{"fixed": "211", "accum": "2141", "dep": "6424", "cwip": "2411"},
		)
		self.assertEqual(
			asset_category_numbers(VO_HINH, self.company),
			{"fixed": "213", "accum": "2143", "dep": "6424", "cwip": "2411"},
		)
