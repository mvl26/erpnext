# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Tests for Quyết toán thuế TNCN (VN personal income tax summary)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from erpnext.regional.report.quyet_toan_tncn.quyet_toan_tncn import execute

CHART_NAME = "Vietnam - Chart of Accounts (Thông tư 99/2025/TT-BTC)"


class TestQuyetToanTNCN(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "_Test VN TNCN",
				"abbr": "TVPT",
				"default_currency": "VND",
				"country": "Vietnam",
				"chart_of_accounts": CHART_NAME,
			}
		)
		company.flags.ignore_permissions = True
		company.insert()
		cls.company = company.name

		def acc(number):
			return frappe.db.get_value(
				"Account", {"company": cls.company, "account_number": number, "is_group": 0}, "name"
			)

		def post(dr, cr, amount):
			je = frappe.get_doc(
				{
					"doctype": "Journal Entry",
					"company": cls.company,
					"posting_date": nowdate(),
					"accounts": [
						{"account": dr, "debit_in_account_currency": amount},
						{"account": cr, "credit_in_account_currency": amount},
					],
				}
			)
			je.flags.ignore_permissions = True
			je.insert()
			je.submit()

		post(acc("334"), acc("3335"), 800_000)  # khấu trừ TNCN từ lương
		post(acc("3335"), acc("111"), 300_000)  # nộp một phần NSNN

	def _run(self):
		result = execute(
			frappe._dict(company=self.company, from_date="1900-01-01", to_date=nowdate())
		)
		return {r["chi_tieu"]: r["so_tien"] for r in result[1] if r.get("so_tien") is not None}

	def test_pit_summary(self):
		v = self._run()
		self.assertEqual(v["Thuế TNCN đã khấu trừ trong kỳ"], 800_000)
		self.assertEqual(v["Thuế TNCN đã nộp Ngân sách Nhà nước"], 300_000)
		self.assertEqual(v["Thuế TNCN còn phải nộp cuối kỳ"], 500_000)
