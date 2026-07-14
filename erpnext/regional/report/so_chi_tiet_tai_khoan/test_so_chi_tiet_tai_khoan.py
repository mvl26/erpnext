# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Tests for Sổ chi tiết tài khoản (VN account detail ledger)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate

from erpnext.regional.report.so_chi_tiet_tai_khoan.so_chi_tiet_tai_khoan import execute

CHART_NAME = "Vietnam - Chart of Accounts (Thông tư 99/2025/TT-BTC)"


class TestSoChiTietTaiKhoan(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "_Test VN So Chi Tiet",
				"abbr": "TVCT",
				"default_currency": "VND",
				"country": "Vietnam",
				"chart_of_accounts": CHART_NAME,
			}
		)
		company.flags.ignore_permissions = True
		company.insert()
		cls.company = company.name
		cc = frappe.db.get_value("Company", cls.company, "cost_center")

		customer = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": "_Test VN SCT Customer",
				"customer_group": "All Customer Groups",
				"territory": "All Territories",
			}
		)
		customer.flags.ignore_permissions = True
		customer.insert()
		cls.customer = customer.name

		cls.receivable = frappe.db.get_value(
			"Account", {"company": cls.company, "account_number": "131", "is_group": 0}, "name"
		)
		revenue = frappe.db.get_value(
			"Account", {"company": cls.company, "account_number": "511", "is_group": 0}, "name"
		)
		je = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"company": cls.company,
				"posting_date": nowdate(),
				"accounts": [
					{
						"account": cls.receivable,
						"party_type": "Customer",
						"party": cls.customer,
						"debit_in_account_currency": 2_000_000,
						"cost_center": cc,
					},
					{"account": revenue, "credit_in_account_currency": 2_000_000, "cost_center": cc},
				],
			}
		)
		je.flags.ignore_permissions = True
		je.insert()
		je.submit()

	def _run(self, party=None):
		filters = frappe._dict(
			company=self.company,
			account=self.receivable,
			from_date="1900-01-01",
			to_date=nowdate(),
		)
		if party:
			filters.party_type = "Customer"
			filters.party = party
		return execute(filters)

	def test_ties_to_gl_and_shows_party(self):
		_, data = self._run()
		closing = next(r for r in data if r.get("is_closing"))
		gl_balance = flt(
			frappe.db.sql(
				"""select sum(debit) - sum(credit) from `tabGL Entry`
				where company=%s and account=%s and is_cancelled=0""",
				(self.company, self.receivable),
			)[0][0]
		)
		self.assertEqual(closing["balance"], gl_balance)
		self.assertEqual(closing["balance"], 2_000_000)
		entry = next(r for r in data if r.get("voucher_no"))
		self.assertEqual(entry["party"], self.customer)

	def test_party_filter(self):
		_, data = self._run(party=self.customer)
		entry_rows = [r for r in data if r.get("voucher_no")]
		self.assertEqual(len(entry_rows), 1)
