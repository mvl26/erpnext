# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Tests for the Vietnam company-setup hook (module/master-data account wiring)."""

import frappe
from frappe.tests.utils import FrappeTestCase

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


def mode_of_payment_account(mode, company):
	if not frappe.db.exists("Mode of Payment", mode):
		return None
	parent = frappe.get_doc("Mode of Payment", mode)
	for row in parent.accounts:
		if row.company == company:
			return row.default_account
	return None


def asset_category_numbers(category, company):
	if not frappe.db.exists("Asset Category", category):
		return None
	cat = frappe.get_doc("Asset Category", category)
	for row in cat.accounts:
		if row.company_name == company:
			num = lambda a: frappe.db.get_value("Account", a, "account_number") if a else None
			return {
				"fixed": num(row.fixed_asset_account),
				"accum": num(row.accumulated_depreciation_account),
				"dep": num(row.depreciation_expense_account),
				"cwip": num(row.capital_work_in_progress_account),
			}
	return None


class TestVietnamCompanySetup(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = make_vn_company("_Test VN Setup", "TVSU")

	def test_mode_of_payment_wired_to_tt99(self):
		self.assertEqual(mode_of_payment_account("Cash", self.company), acct(self.company, "111"))
		self.assertEqual(mode_of_payment_account("Bank", self.company), acct(self.company, "112"))

	def test_asset_categories_wired_to_tt99(self):
		self.assertEqual(
			asset_category_numbers(HUU_HINH, self.company),
			{"fixed": "211", "accum": "2141", "dep": "6424", "cwip": "2411"},
		)
		self.assertEqual(
			asset_category_numbers(VO_HINH, self.company),
			{"fixed": "213", "accum": "2143", "dep": "6424", "cwip": "2411"},
		)
