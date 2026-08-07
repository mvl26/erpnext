# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

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


class TestQuyetToanTNCNPerEmployee(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.regional.vietnam.test_setup import make_vn_company

		cls.company = make_vn_company("_Test VN TNCN NV", "TVTN")

		employee = frappe.get_doc(
			{
				"doctype": "Employee",
				"first_name": "_Test NV TNCN",
				"company": cls.company,
				"gender": "Female",
				"date_of_birth": "1990-01-01",
				"date_of_joining": "2026-01-01",
				"status": "Active",
			}
		).insert(ignore_permissions=True)
		cls.employee = employee.name

		if not frappe.db.exists("Salary Component", "Thuế TNCN"):
			frappe.get_doc(
				{
					"doctype": "Salary Component",
					"salary_component": "Thuế TNCN",
					"type": "Deduction",
					"is_income_tax_component": 1,
				}
			).insert(ignore_permissions=True)

		# Minimal submitted Salary Slip via db_insert (payroll mechanics are hrms's
		# concern — this report only READS the slip + its income-tax deduction row).
		slip = frappe.new_doc("Salary Slip")
		slip.update(
			{
				"name": frappe.generate_hash(length=10),
				"employee": cls.employee,
				"employee_name": employee.employee_name,
				"company": cls.company,
				"start_date": "2026-06-01",
				"end_date": "2026-06-30",
				"posting_date": "2026-06-30",
				"gross_pay": 30_000_000,
				"docstatus": 1,
			}
		)
		slip.db_insert()
		detail = frappe.new_doc("Salary Detail")
		detail.update(
			{
				"name": frappe.generate_hash(length=10),
				"parent": slip.name,
				"parenttype": "Salary Slip",
				"parentfield": "deductions",
				"salary_component": "Thuế TNCN",
				"amount": 1_500_000,
				"docstatus": 1,
			}
		)
		detail.db_insert()

	def _execute(self):
		return execute(
			frappe._dict(company=self.company, from_date="2026-06-01", to_date="2026-06-30")
		)

	def test_per_employee_rows_from_payroll(self):
		_cols, rows, _note = self._execute()
		employee_rows = [r for r in rows if r.get("employee")]
		self.assertEqual(len(employee_rows), 1)
		row = employee_rows[0]
		self.assertEqual(row["employee"], self.employee)
		self.assertEqual(row["thu_nhap"], 30_000_000)
		self.assertEqual(row["tncn"], 1_500_000)

	def test_degrades_gracefully_without_hrms(self):
		from unittest.mock import patch

		with patch(
			"erpnext.regional.report.quyet_toan_tncn.quyet_toan_tncn._has_hrms", return_value=False
		):
			_cols, rows, _note = self._execute()
		self.assertFalse([r for r in rows if r.get("employee")])
		# The GL summary section is still produced.
		self.assertTrue([r for r in rows if r.get("chi_tieu")])
