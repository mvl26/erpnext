# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tests for B03-DN Báo cáo lưu chuyển tiền tệ (VN cash flow, indirect)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from erpnext.regional.report.bao_cao_luu_chuyen_tien_te_b03.bao_cao_luu_chuyen_tien_te_b03 import (
	execute,
)

CHART_NAME = "Vietnam - Chart of Accounts (Thông tư 99/2025/TT-BTC)"


class TestBaoCaoLuuChuyenTienTe(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "_Test VN B03",
				"abbr": "TVB3",
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

		post(acc("111"), acc("4118"), 5_000_000)  # góp vốn -> tài chính +5tr
		post(acc("1281"), acc("111"), 2_000_000)  # gửi tiền có kỳ hạn -> đầu tư -2tr
		post(acc("111"), acc("511"), 3_000_000, cc)  # bán hàng -> kinh doanh +3tr

	def _run(self):
		result = execute(
			frappe._dict(company=self.company, from_date="1900-01-01", to_date=nowdate())
		)
		data = result[1]
		return {r["ma_so"]: r["so_tien"] for r in data if r.get("ma_so")}

	def test_net_cash_flow_ties_to_cash_change(self):
		v = self._run()
		self.assertEqual(v["20"], 3_000_000)  # HĐ kinh doanh
		self.assertEqual(v["30"], -2_000_000)  # HĐ đầu tư
		self.assertEqual(v["40"], 5_000_000)  # HĐ tài chính
		self.assertEqual(v["50"], 6_000_000)  # lưu chuyển thuần
		self.assertEqual(v["60"], 0)  # tiền đầu kỳ
		self.assertEqual(v["70"], 6_000_000)  # tiền cuối kỳ
		# 50 = 20 + 30 + 40, and 70 = 50 + 60
		self.assertEqual(v["50"], v["20"] + v["30"] + v["40"])
		self.assertEqual(v["70"], v["50"] + v["60"])
