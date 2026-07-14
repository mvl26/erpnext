# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Tests for Quyết toán thuế TNDN (VN corporate income tax summary)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from erpnext.regional.report.quyet_toan_tndn.quyet_toan_tndn import execute

CHART_NAME = "Vietnam - Chart of Accounts (Thông tư 99/2025/TT-BTC)"


class TestQuyetToanTNDN(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "_Test VN TNDN",
				"abbr": "TVCI",
				"default_currency": "VND",
				"country": "Vietnam",
				"chart_of_accounts": CHART_NAME,
			}
		)
		company.flags.ignore_permissions = True
		company.insert()
		cls.company = company.name
		cc = frappe.db.get_value("Company", cls.company, "cost_center")

		def acc(number):
			return frappe.db.get_value(
				"Account", {"company": cls.company, "account_number": number, "is_group": 0}, "name"
			)

		accrue = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"company": cls.company,
				"posting_date": nowdate(),
				"accounts": [
					{"account": acc("82111"), "debit_in_account_currency": 2_000_000, "cost_center": cc},
					{"account": acc("3334"), "credit_in_account_currency": 2_000_000},
				],
			}
		)
		accrue.flags.ignore_permissions = True
		accrue.insert()
		accrue.submit()

		pay = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"company": cls.company,
				"posting_date": nowdate(),
				"accounts": [
					{"account": acc("3334"), "debit_in_account_currency": 1_200_000},
					{"account": acc("111"), "credit_in_account_currency": 1_200_000},
				],
			}
		)
		pay.flags.ignore_permissions = True
		pay.insert()
		pay.submit()

	def _run(self):
		result = execute(
			frappe._dict(company=self.company, from_date="1900-01-01", to_date=nowdate())
		)
		return {r["chi_tieu"]: r["so_tien"] for r in result[1] if r.get("so_tien") is not None}

	def test_cit_summary_ties_to_gl(self):
		v = self._run()
		self.assertEqual(v["Chi phí thuế TNDN hiện hành"], 2_000_000)
		self.assertEqual(v["Thuế TNDN phải nộp phát sinh trong kỳ"], 2_000_000)
		self.assertEqual(v["Thuế TNDN đã nộp"], 1_200_000)
		self.assertEqual(v["Thuế TNDN còn phải nộp cuối kỳ"], 800_000)
