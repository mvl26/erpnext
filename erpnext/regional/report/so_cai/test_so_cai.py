# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Tests for Sổ Cái (VN general ledger, per account)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate

from erpnext.regional.report.so_cai.so_cai import execute

CHART_NAME = "Vietnam - Chart of Accounts (Thông tư 99/2025/TT-BTC)"


class TestSoCai(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "_Test VN So Cai",
				"abbr": "TVSC",
				"default_currency": "VND",
				"country": "Vietnam",
				"chart_of_accounts": CHART_NAME,
			}
		)
		company.flags.ignore_permissions = True
		company.insert()
		cls.company = company.name
		cc = frappe.db.get_value("Company", cls.company, "cost_center")
		cls.cash = frappe.db.get_value(
			"Account", {"company": cls.company, "account_number": "111", "is_group": 0}, "name"
		)
		other = frappe.db.get_value(
			"Account", {"company": cls.company, "account_number": "3388", "is_group": 0}, "name"
		)

		def post(debit_acc, credit_acc, amount):
			je = frappe.get_doc(
				{
					"doctype": "Journal Entry",
					"company": cls.company,
					"posting_date": nowdate(),
					"accounts": [
						{"account": debit_acc, "debit_in_account_currency": amount, "cost_center": cc},
						{"account": credit_acc, "credit_in_account_currency": amount, "cost_center": cc},
					],
				}
			)
			je.flags.ignore_permissions = True
			je.insert()
			je.submit()

		post(cls.cash, other, 1_000_000)  # +1,000,000 to cash
		post(other, cls.cash, 300_000)  # -300,000 from cash

	def _run(self):
		filters = frappe._dict(
			company=self.company, account=self.cash, from_date="1900-01-01", to_date=nowdate()
		)
		return execute(filters)

	def test_running_balance_ties_to_gl(self):
		_, data = self._run()
		# closing row balance == GL balance for the account
		closing = next(r for r in data if r.get("is_closing"))
		gl_balance = flt(
			frappe.db.sql(
				"""select sum(debit) - sum(credit) from `tabGL Entry`
				where company=%s and account=%s and is_cancelled=0""",
				(self.company, self.cash),
			)[0][0]
		)
		self.assertEqual(closing["balance"], gl_balance)
		self.assertEqual(closing["balance"], 700_000)

	def test_entry_rows_and_totals(self):
		_, data = self._run()
		entry_rows = [r for r in data if r.get("voucher_no")]
		self.assertEqual(len(entry_rows), 2)
		total = next(r for r in data if r.get("is_total"))
		self.assertEqual(total["debit"], 1_000_000)
		self.assertEqual(total["credit"], 300_000)
