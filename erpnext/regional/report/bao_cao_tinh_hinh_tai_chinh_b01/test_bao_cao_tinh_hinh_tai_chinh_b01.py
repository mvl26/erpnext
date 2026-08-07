# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tests for B01-DN Báo cáo tình hình tài chính (VN balance sheet)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from erpnext.regional.report.bao_cao_tinh_hinh_tai_chinh_b01.bao_cao_tinh_hinh_tai_chinh_b01 import (
	execute,
)

CHART_NAME = "Vietnam - Chart of Accounts (Thông tư 99/2025/TT-BTC)"


class TestBaoCaoTinhHinhTaiChinh(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "_Test VN B01",
				"abbr": "TVB1",
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

		def post(dr, cr, amount, cost_center=None):
			je = frappe.get_doc(
				{
					"doctype": "Journal Entry",
					"company": cls.company,
					"posting_date": nowdate(),
					"accounts": [
						{"account": dr, "debit_in_account_currency": amount, "cost_center": cost_center},
						{"account": cr, "credit_in_account_currency": amount, "cost_center": cost_center},
					],
				}
			)
			je.flags.ignore_permissions = True
			je.insert()
			je.submit()

		post(acc("111"), acc("4118"), 5_000_000)  # góp vốn bằng tiền
		post(acc("152"), acc("3388"), 3_000_000)  # mua hàng nợ nhà cung cấp
		post(acc("111"), acc("511"), 2_000_000, cc)  # bán hàng thu tiền -> lãi

	def _run(self):
		result = execute(
			frappe._dict(company=self.company, from_date="1900-01-01", to_date=nowdate())
		)
		data = result[1]
		return {r["ma_so"]: r["so_tien"] for r in data if r.get("ma_so")}

	def test_balance_sheet_balances(self):
		v = self._run()
		self.assertEqual(v["270"], 10_000_000)  # tổng tài sản
		self.assertEqual(v["440"], 10_000_000)  # tổng nguồn vốn
		self.assertEqual(v["270"], v["440"])  # phải cân

	def test_key_lines(self):
		v = self._run()
		self.assertEqual(v["110"], 7_000_000)  # tiền (5tr góp + 2tr bán hàng)
		self.assertEqual(v["300"], 3_000_000)  # nợ phải trả
		self.assertEqual(v["421"], 2_000_000)  # LNST chưa phân phối = lãi trong kỳ
