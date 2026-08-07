# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tests for Bảng cân đối số phát sinh (VN trial balance)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from erpnext.regional.report.bang_can_doi_so_phat_sinh.bang_can_doi_so_phat_sinh import execute

CHART_NAME = "Vietnam - Chart of Accounts (Thông tư 99/2025/TT-BTC)"


class TestBangCanDoiSoPhatSinh(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "_Test VN Trial Balance",
				"abbr": "TVTB",
				"default_currency": "VND",
				"country": "Vietnam",
				"chart_of_accounts": CHART_NAME,
			}
		)
		company.flags.ignore_permissions = True
		company.insert()
		cls.company = company.name
		cc = frappe.db.get_value("Company", cls.company, "cost_center")
		cash = frappe.db.get_value(
			"Account", {"company": cls.company, "account_number": "111", "is_group": 0}, "name"
		)
		other_payable = frappe.db.get_value(
			"Account", {"company": cls.company, "account_number": "3388", "is_group": 0}, "name"
		)
		je = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"company": cls.company,
				"posting_date": nowdate(),
				"accounts": [
					{"account": cash, "debit_in_account_currency": 1_000_000, "cost_center": cc},
					{"account": other_payable, "credit_in_account_currency": 1_000_000, "cost_center": cc},
				],
			}
		)
		je.flags.ignore_permissions = True
		je.insert()
		je.submit()

	def _run(self):
		filters = frappe._dict(company=self.company, from_date="1900-01-01", to_date=nowdate())
		return execute(filters)

	def test_columns_present(self):
		columns, _ = self._run()
		fieldnames = {c["fieldname"] for c in columns}
		for f in (
			"account_number",
			"opening_debit",
			"opening_credit",
			"debit",
			"credit",
			"closing_debit",
			"closing_credit",
		):
			self.assertIn(f, fieldnames)

	def test_account_rows_and_balancing(self):
		_, data = self._run()
		by_number = {r.get("account_number"): r for r in data if r.get("account_number")}

		self.assertIn("111", by_number)
		self.assertIn("3388", by_number)
		self.assertEqual(by_number["111"]["debit"], 1_000_000)
		self.assertEqual(by_number["111"]["closing_debit"], 1_000_000)
		self.assertEqual(by_number["3388"]["credit"], 1_000_000)
		self.assertEqual(by_number["3388"]["closing_credit"], 1_000_000)

		# Trial balance must balance on every pair of columns.
		total = next(r for r in data if r.get("is_total"))
		self.assertEqual(total["debit"], total["credit"])
		self.assertEqual(total["opening_debit"], total["opening_credit"])
		self.assertEqual(total["closing_debit"], total["closing_credit"])
		self.assertEqual(total["debit"], 1_000_000)
