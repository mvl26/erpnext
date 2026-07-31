# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tests for B02-DN Báo cáo kết quả hoạt động kinh doanh (VN income statement)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from erpnext.regional.report.bao_cao_kqhdkd_b02.bao_cao_kqhdkd_b02 import execute

CHART_NAME = "Vietnam - Chart of Accounts (Thông tư 99/2025/TT-BTC)"


class TestBaoCaoKQHDKD(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "_Test VN B02",
				"abbr": "TVB2",
				"default_currency": "VND",
				"country": "Vietnam",
				"chart_of_accounts": CHART_NAME,
			}
		)
		company.flags.ignore_permissions = True
		company.insert()
		cls.company = company.name
		cls.cc = frappe.db.get_value("Company", cls.company, "cost_center")

		def acc(number):
			return frappe.db.get_value(
				"Account", {"company": cls.company, "account_number": number, "is_group": 0}, "name"
			)

		cash = acc("111")
		other = acc("3388")

		def post(dr, cr, amount):
			je = frappe.get_doc(
				{
					"doctype": "Journal Entry",
					"company": cls.company,
					"posting_date": nowdate(),
					"accounts": [
						{"account": dr, "debit_in_account_currency": amount, "cost_center": cls.cc},
						{"account": cr, "credit_in_account_currency": amount, "cost_center": cls.cc},
					],
				}
			)
			je.flags.ignore_permissions = True
			je.insert()
			je.submit()

		post(cash, acc("511"), 10_000_000)  # doanh thu
		post(acc("632"), other, 6_000_000)  # giá vốn
		post(acc("6421"), other, 1_000_000)  # chi phí QLDN
		post(acc("82111"), other, 500_000)  # chi phí thuế TNDN hiện hành

	def _run(self):
		result = execute(
			frappe._dict(company=self.company, from_date="1900-01-01", to_date=nowdate())
		)
		columns, data = result[0], result[1]
		return {r["ma_so"]: r["so_tien"] for r in data}

	def test_line_items_and_subtotals(self):
		v = self._run()
		self.assertEqual(v["01"], 10_000_000)  # doanh thu
		self.assertEqual(v["10"], 10_000_000)  # doanh thu thuần
		self.assertEqual(v["11"], 6_000_000)  # giá vốn
		self.assertEqual(v["20"], 4_000_000)  # lợi nhuận gộp
		self.assertEqual(v["26"], 1_000_000)  # chi phí QLDN
		self.assertEqual(v["30"], 3_000_000)  # lợi nhuận thuần
		self.assertEqual(v["50"], 3_000_000)  # tổng LN trước thuế
		self.assertEqual(v["51"], 500_000)  # thuế TNDN hiện hành
		self.assertEqual(v["60"], 2_500_000)  # lợi nhuận sau thuế

	def test_net_profit_ties_to_income_minus_expense(self):
		v = self._run()
		# 60 = tổng doanh thu/thu nhập − tổng chi phí
		self.assertEqual(v["60"], 10_000_000 - (6_000_000 + 1_000_000 + 500_000))
