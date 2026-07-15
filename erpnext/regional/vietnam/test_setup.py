# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Tests for the Vietnam company-setup hook (module/master-data account wiring)."""

import frappe
from frappe.tests.utils import FrappeTestCase

CHART_NAME = "Vietnam - Chart of Accounts (Thông tư 99/2025/TT-BTC)"


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
	parent = frappe.get_doc("Mode of Payment", mode)
	for row in parent.accounts:
		if row.company == company:
			return row.default_account
	return None


class TestVietnamModeOfPayment(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = make_vn_company("_Test VN Setup MoP", "TVSM")

	def test_cash_and_bank_wired_to_tt99(self):
		self.assertEqual(mode_of_payment_account("Cash", self.company), acct(self.company, "111"))
		self.assertEqual(mode_of_payment_account("Bank", self.company), acct(self.company, "112"))
