# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Tests for Vietnam regional company defaults.

A Vietnam company should require no manual localization: its default currency
resolves to VND (from the country's currency) and the TT99 chart is the only
one offered, so the setup wizard auto-selects it.
"""

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.accounts.doctype.account.chart_of_accounts import chart_of_accounts

CHART_NAME = "Vietnam - Chart of Accounts (Thông tư 99/2025/TT-BTC)"


class TestVietnamChartAutoSelection(unittest.TestCase):
	def test_only_vn_chart_offered(self):
		# Exactly one chart -> get_charts_for_country returns it without the
		# Standard fallback, so the setup wizard defaults to the TT99 chart.
		self.assertEqual(chart_of_accounts.get_charts_for_country("Vietnam"), [CHART_NAME])


class TestVietnamRegionalDefaults(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "_Test VN Auto Currency",
				"abbr": "TVAC",
				"country": "Vietnam",
				"chart_of_accounts": CHART_NAME,
				# default_currency intentionally omitted — must resolve to VND
			}
		)
		company.flags.ignore_permissions = True
		company.insert()
		cls.company = company.name

	def test_company_defaults_currency_to_vnd(self):
		self.assertEqual(frappe.db.get_value("Company", self.company, "default_currency"), "VND")

	def test_company_wires_unrealized_fx_to_413(self):
		# TT99: đánh giá lại tỷ giá cuối kỳ posts to TK 413 (Chênh lệch tỷ giá hối đoái).
		acc_413 = frappe.db.get_value(
			"Account", {"company": self.company, "account_number": "413", "is_group": 0}, "name"
		)
		self.assertEqual(
			frappe.db.get_value("Company", self.company, "unrealized_exchange_gain_loss_account"),
			acc_413,
		)


if __name__ == "__main__":
	unittest.main()
