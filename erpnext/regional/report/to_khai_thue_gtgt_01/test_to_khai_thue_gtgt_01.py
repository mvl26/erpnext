# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Tests for Tờ khai thuế GTGT (mẫu 01/GTGT)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from erpnext.regional.report.to_khai_thue_gtgt_01.to_khai_thue_gtgt_01 import execute

CHART_NAME = "Vietnam - Chart of Accounts (Thông tư 99/2025/TT-BTC)"


class TestToKhaiThueGTGT(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "_Test VN GTGT Return",
				"abbr": "TVGR",
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

		# Bán hàng có thuế GTGT đầu ra 10%
		sale = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"company": cls.company,
				"posting_date": nowdate(),
				"accounts": [
					{"account": acc("111"), "debit_in_account_currency": 11_000_000},
					{"account": acc("511"), "credit_in_account_currency": 10_000_000, "cost_center": cc},
					{"account": acc("33311"), "credit_in_account_currency": 1_000_000},
				],
			}
		)
		sale.flags.ignore_permissions = True
		sale.insert()
		sale.submit()

		# Mua hàng có thuế GTGT đầu vào được khấu trừ
		purchase = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"company": cls.company,
				"posting_date": nowdate(),
				"accounts": [
					{"account": acc("152"), "debit_in_account_currency": 5_000_000},
					{"account": acc("1331"), "debit_in_account_currency": 500_000},
					{"account": acc("3388"), "credit_in_account_currency": 5_500_000},
				],
			}
		)
		purchase.flags.ignore_permissions = True
		purchase.insert()
		purchase.submit()

	def _run(self):
		result = execute(
			frappe._dict(company=self.company, from_date="1900-01-01", to_date=nowdate())
		)
		return {r["chi_tieu_code"]: r["so_tien"] for r in result[1] if r.get("chi_tieu_code")}

	def test_vat_return_totals(self):
		v = self._run()
		self.assertEqual(v["33"], 1_000_000)  # thuế GTGT đầu ra
		self.assertEqual(v["25"], 500_000)  # thuế GTGT được khấu trừ kỳ này
		self.assertEqual(v["40"], 500_000)  # thuế GTGT phải nộp = đầu ra - khấu trừ
		self.assertEqual(v["41"], 0)  # chưa khấu trừ hết
