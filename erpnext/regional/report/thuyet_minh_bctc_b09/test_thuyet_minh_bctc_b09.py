# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tests for B09-DN Thuyết minh báo cáo tài chính (VN notes)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from erpnext.regional.report.thuyet_minh_bctc_b09.thuyet_minh_bctc_b09 import execute

CHART_NAME = "Vietnam - Chart of Accounts (Thông tư 99/2025/TT-BTC)"


class TestThuyetMinhBCTC(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "_Test VN B09",
				"abbr": "TVB9",
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

		post(acc("111"), acc("511"), 10_000_000, cc)  # doanh thu + tiền
		post(acc("632"), acc("3388"), 6_000_000, cc)  # giá vốn
		post(acc("152"), acc("3388"), 3_000_000)  # hàng tồn kho

	def _run(self):
		result = execute(
			frappe._dict(company=self.company, from_date="1900-01-01", to_date=nowdate())
		)
		return result[1]

	def test_notes_and_key_figures(self):
		data = self._run()
		all_text = " ".join(r.get("noi_dung", "") for r in data)
		self.assertIn("99/2025/TT-BTC", all_text)  # chế độ kế toán áp dụng
		self.assertIn("VND", all_text)  # đơn vị tiền tệ

		figures = {r["chi_tieu"]: r.get("gia_tri") for r in data if r.get("gia_tri") is not None}
		self.assertEqual(figures["Doanh thu bán hàng và cung cấp dịch vụ"], 10_000_000)
		self.assertEqual(figures["Giá vốn hàng bán"], 6_000_000)
		self.assertEqual(figures["Tiền và các khoản tương đương tiền"], 10_000_000)
		self.assertEqual(figures["Hàng tồn kho"], 3_000_000)
