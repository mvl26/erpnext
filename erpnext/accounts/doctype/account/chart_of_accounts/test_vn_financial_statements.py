# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Regression lock: ERPNext's standard financial statements work on the VN chart.

Miyano uses ERPNext's built-in Balance Sheet and Profit and Loss reports for
Vietnamese financial statements (statutory B01-DN/B02-DN forms are out of scope
until their TT99 templates are provided). Those reports are driven by account
``root_type``/``report_type``; this test guards that the TT99 chart stays
compatible and that both reports render real VN accounts.
"""

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from erpnext.accounts.doctype.account.chart_of_accounts import chart_of_accounts

CHART_NAME = "Vietnam - Chart of Accounts (Thông tư 99/2025/TT-BTC)"

BALANCE_SHEET_ROOT_TYPES = {"Asset", "Liability", "Equity"}
PROFIT_AND_LOSS_ROOT_TYPES = {"Income", "Expense"}


class TestVietnamChartReportTypes(unittest.TestCase):
	"""Fast: the chart covers both statements' root types."""

	def test_chart_covers_both_statements(self):
		tree = chart_of_accounts.get_chart(CHART_NAME)
		root_types = {node["root_type"] for node in tree.values() if isinstance(node, dict)}
		self.assertTrue(BALANCE_SHEET_ROOT_TYPES <= root_types, "Balance Sheet root types missing")
		self.assertTrue(PROFIT_AND_LOSS_ROOT_TYPES <= root_types, "P&L root types missing")


class TestVietnamStandardStatements(FrappeTestCase):
	"""End-to-end: standard Balance Sheet + P&L render VN accounts after a posting."""

	def test_statements_render_vn_accounts(self):
		company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "_Test VN Statements",
				"abbr": "TVST",
				"default_currency": "VND",
				"country": "Vietnam",
				"chart_of_accounts": CHART_NAME,
			}
		)
		company.flags.ignore_permissions = True
		company.insert()

		cost_center = frappe.db.get_value("Company", company.name, "cost_center")
		cash = frappe.db.get_value(
			"Account", {"company": company.name, "account_number": "111", "is_group": 0}, "name"
		)
		revenue = frappe.db.get_value(
			"Account", {"company": company.name, "account_number": "511", "is_group": 0}, "name"
		)

		# Dr 111 Tiền mặt / Cr 511 Doanh thu — gives the Balance Sheet an asset and
		# the P&L income, so both statements have content.
		je = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"company": company.name,
				"posting_date": nowdate(),
				"accounts": [
					{"account": cash, "debit_in_account_currency": 1_000_000, "cost_center": cost_center},
					{
						"account": revenue,
						"credit_in_account_currency": 1_000_000,
						"cost_center": cost_center,
					},
				],
			}
		)
		je.flags.ignore_permissions = True
		je.insert()
		je.submit()

		from erpnext.accounts.report.balance_sheet.balance_sheet import execute as bs_execute
		from erpnext.accounts.report.profit_and_loss_statement.profit_and_loss_statement import (
			execute as pl_execute,
		)
		from erpnext.accounts.utils import get_fiscal_year

		fy_name = get_fiscal_year(nowdate(), company=company.name)[0]
		filters = frappe._dict(
			company=company.name,
			filter_based_on="Fiscal Year",
			from_fiscal_year=fy_name,
			to_fiscal_year=fy_name,
			periodicity="Yearly",
			period_start_date=None,
			period_end_date=None,
			accumulated_values=1,
		)

		bs_data = bs_execute(filters)[1]
		pl_data = pl_execute(filters)[1]

		bs_names = " ".join(r.get("account_name", "") for r in bs_data if r)
		pl_names = " ".join(r.get("account_name", "") for r in pl_data if r)

		self.assertTrue(bs_data, "Balance Sheet returned no rows for the VN company")
		self.assertTrue(pl_data, "Profit and Loss returned no rows for the VN company")
		self.assertIn("111", bs_names, "Tiền mặt (111) missing from the Balance Sheet")
		self.assertIn("511", pl_names, "Doanh thu (511) missing from the Profit and Loss")


if __name__ == "__main__":
	unittest.main()
