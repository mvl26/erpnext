# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tests for Sổ Nhật ký chung (VN general journal)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from erpnext.regional.report.so_nhat_ky_chung.so_nhat_ky_chung import execute

CHART_NAME = "Vietnam - Chart of Accounts (Thông tư 99/2025/TT-BTC)"


class TestSoNhatKyChung(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "_Test VN Nhat Ky",
				"abbr": "TVNK",
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
		other = frappe.db.get_value(
			"Account", {"company": cls.company, "account_number": "3388", "is_group": 0}, "name"
		)
		for amount in (1_000_000, 500_000):
			je = frappe.get_doc(
				{
					"doctype": "Journal Entry",
					"company": cls.company,
					"posting_date": nowdate(),
					"accounts": [
						{"account": cash, "debit_in_account_currency": amount, "cost_center": cc},
						{"account": other, "credit_in_account_currency": amount, "cost_center": cc},
					],
				}
			)
			je.flags.ignore_permissions = True
			je.insert()
			je.submit()

	def _run(self):
		return execute(
			frappe._dict(company=self.company, from_date="1900-01-01", to_date=nowdate())
		)

	def test_lines_and_balancing(self):
		_, data = self._run()
		entry_rows = [r for r in data if r.get("account_number")]
		self.assertEqual(len(entry_rows), 4)  # 2 JEs x 2 lines
		total = next(r for r in data if r.get("is_total"))
		self.assertEqual(total["debit"], total["credit"])
		self.assertEqual(total["debit"], 1_500_000)
