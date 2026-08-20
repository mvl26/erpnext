# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Test switching an empty company from the Standard chart onto TT99."""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.regional.vietnam.reconfigure import VN_CHART, reconfigure_company_to_vn_chart


class TestReconfigureToVN(FrappeTestCase):
	def test_switch_empty_standard_company_to_tt99(self):
		company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "_Test VN Reconfigure",
				"abbr": "TVRC",
				"default_currency": "VND",
				"country": "Vietnam",
				"chart_of_accounts": "Standard",
				"enable_perpetual_inventory": 1,
			}
		)
		company.flags.ignore_permissions = True
		company.insert()
		cname = company.name

		# Pre-condition: on the English Standard chart.
		self.assertEqual(frappe.db.get_value("Company", cname, "chart_of_accounts"), "Standard")
		self.assertTrue(frappe.db.exists("Account", {"company": cname, "account_name": "Debtors"}))

		backup = reconfigure_company_to_vn_chart(cname)
		self.assertTrue(backup)  # backup file path returned

		# Now on the TT99 chart with defaults wired to TT99 numbers.
		self.assertEqual(frappe.db.get_value("Company", cname, "chart_of_accounts"), VN_CHART)
		comp = frappe.get_doc("Company", cname)

		def num(a):
			return frappe.db.get_value("Account", a, "account_number") if a else None

		self.assertEqual(num(comp.default_receivable_account), "131")
		self.assertEqual(num(comp.default_payable_account), "331")
		self.assertEqual(num(comp.default_inventory_account), "156")
		self.assertEqual(num(comp.default_expense_account), "632")
		self.assertEqual(num(comp.default_income_account), "511")

		# Old English accounts are gone.
		for english in ("Debtors", "Creditors", "Stock In Hand"):
			self.assertFalse(
				frappe.db.exists("Account", {"company": cname, "account_name": english}),
				f"English account {english!r} still present after reconfigure",
			)

		# TT99 accounts + module wiring present.
		self.assertTrue(frappe.db.exists("Account", {"company": cname, "account_number": "131"}))
		self.assertTrue(frappe.db.exists("Asset Category", "Tài sản cố định hữu hình"))

	def test_reconfigure_is_idempotent(self):
		company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "_Test VN Reconfigure Idem",
				"abbr": "TVRI",
				"default_currency": "VND",
				"country": "Vietnam",
				"chart_of_accounts": VN_CHART,
				"enable_perpetual_inventory": 1,
			}
		)
		company.flags.ignore_permissions = True
		company.insert()
		# Already on TT99 -> reconfigure is a no-op.
		self.assertIsNone(reconfigure_company_to_vn_chart(company.name))
