# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Tests for the Vietnam accounting-report shared helpers."""

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from erpnext.regional.vietnam.utils import (
	get_account_balances,
	so_thanh_chu,
	sum_closing_by_prefix,
	sum_movement_by_prefix,
)

CHART_NAME = "Vietnam - Chart of Accounts (Thông tư 99/2025/TT-BTC)"


class TestSoThanhChu(unittest.TestCase):
	"""Vietnamese amount-in-words (số thành chữ)."""

	def test_known_values(self):
		cases = {
			0: "Không đồng",
			5: "Năm đồng",
			10: "Mười đồng",
			15: "Mười lăm đồng",
			21: "Hai mươi mốt đồng",
			100: "Một trăm đồng",
			101: "Một trăm lẻ một đồng",
			1_000: "Một nghìn đồng",
			1_000_000: "Một triệu đồng",
			1_001_000: "Một triệu không trăm lẻ một nghìn đồng",
			1_234_567: "Một triệu hai trăm ba mươi bốn nghìn năm trăm sáu mươi bảy đồng",
			1_000_000_000: "Một tỷ đồng",
		}
		for amount, expected in cases.items():
			self.assertEqual(so_thanh_chu(amount), expected, f"số thành chữ of {amount}")

	def test_rounds_and_capitalizes(self):
		self.assertEqual(so_thanh_chu(4999.6), "Năm nghìn đồng")
		self.assertTrue(so_thanh_chu(123).startswith("M"))


class TestAccountBalances(FrappeTestCase):
	def test_balances_and_prefix_sums(self):
		company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "_Test VN Utils",
				"abbr": "TVUT",
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

		balances = get_account_balances(company.name, "1900-01-01", nowdate())

		self.assertEqual(balances[cash].closing, 1_000_000)  # asset: debit nature
		self.assertEqual(balances[revenue].closing, -1_000_000)  # income: credit nature
		# Cash (111*) closing balance and revenue (511*) period movement.
		self.assertEqual(sum_closing_by_prefix(balances, ["111"]), 1_000_000)
		self.assertEqual(sum_movement_by_prefix(balances, ["511"]), -1_000_000)


if __name__ == "__main__":
	unittest.main()
