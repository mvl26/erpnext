# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Tests for the Vietnam default GTGT (VAT) tax setup.

The country entry in ``erpnext/setup/setup_wizard/data/country_wise_tax.json``
must create Sales/Purchase Taxes and Charges Templates, Item Tax Templates and
Tax Categories for the standard GTGT rates, wired to the TT99 accounts
33311 (thuế GTGT đầu ra) and 1331 (thuế GTGT được khấu trừ).
"""

import json
import os
import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

CHART_NAME = "Vietnam - Chart of Accounts (Thông tư 99/2025/TT-BTC)"
OUTPUT_VAT_NUMBER = "33311"  # thuế GTGT đầu ra (Liability) — sales
INPUT_VAT_NUMBER = "1331"  # thuế GTGT được khấu trừ (Asset) — purchase

SALES_TEMPLATES = ["GTGT bán ra 10%", "GTGT bán ra 8%", "GTGT bán ra 5%", "GTGT bán ra 0%"]
PURCHASE_TEMPLATES = ["GTGT mua vào 10%", "GTGT mua vào 8%", "GTGT mua vào 5%", "GTGT mua vào 0%"]
ITEM_TAX_TEMPLATES = ["GTGT 10%", "GTGT 8%", "GTGT 5%", "GTGT 0%"]
TAX_CATEGORIES = ["GTGT 10%", "GTGT 8%", "GTGT 5%", "GTGT 0%", "Không chịu thuế GTGT"]
RATES = {10.0, 8.0, 5.0, 0.0}


def _tax_json():
	path = frappe.get_app_path("erpnext", "setup", "setup_wizard", "data", "country_wise_tax.json")
	with open(path, encoding="utf-8") as f:
		return json.load(f)


class TestVietnamTaxJson(unittest.TestCase):
	"""Fast structural checks on the Vietnam entry (no DB)."""

	@classmethod
	def setUpClass(cls):
		cls.vn = _tax_json()["Vietnam"]

	def test_uses_detailed_format(self):
		self.assertIn("chart_of_accounts", self.vn)

	def _templates(self, key):
		coa = self.vn["chart_of_accounts"]
		block = coa.get(CHART_NAME) or coa.get("*")
		return block[key]

	def test_sales_templates(self):
		sales = self._templates("sales_tax_templates")
		self.assertEqual([t["title"] for t in sales], SALES_TEMPLATES)
		self.assertEqual({t["taxes"][0]["account_head"]["tax_rate"] for t in sales}, RATES)
		for t in sales:
			self.assertEqual(t["taxes"][0]["account_head"]["account_number"], OUTPUT_VAT_NUMBER)
		self.assertEqual(sum(1 for t in sales if t.get("is_default")), 1)

	def test_purchase_templates(self):
		purchase = self._templates("purchase_tax_templates")
		gtgt = [t for t in purchase if t["title"] in PURCHASE_TEMPLATES]
		self.assertEqual([t["title"] for t in gtgt], PURCHASE_TEMPLATES)
		for t in gtgt:
			self.assertEqual(t["taxes"][0]["account_head"]["account_number"], INPUT_VAT_NUMBER)
		self.assertEqual(sum(1 for t in purchase if t.get("is_default")), 1)

	def test_import_purchase_templates(self):
		purchase = self._templates("purchase_tax_templates")
		by_title = {t["title"]: t for t in purchase}
		expected = {
			"Thuế nhập khẩu": "3333",
			"Thuế TTĐB hàng nhập khẩu": "3332",
			"Thuế GTGT hàng nhập khẩu": "33312",
		}
		for title, number in expected.items():
			self.assertIn(title, by_title, f"missing import template {title!r}")
			self.assertEqual(by_title[title]["taxes"][0]["account_head"]["account_number"], number)

	def test_item_tax_templates_cover_both_accounts(self):
		items = self._templates("item_tax_templates")
		self.assertEqual([t["title"] for t in items], ITEM_TAX_TEMPLATES)
		for t in items:
			numbers = {row["tax_type"]["account_number"] for row in t["taxes"]}
			self.assertEqual(numbers, {OUTPUT_VAT_NUMBER, INPUT_VAT_NUMBER})

	def test_tax_categories(self):
		titles = [tc["title"] if isinstance(tc, dict) else tc for tc in self.vn["tax_categories"]]
		self.assertEqual(titles, TAX_CATEGORIES)


class TestVietnamTaxTemplatesCreated(FrappeTestCase):
	"""End-to-end: creating a VN company builds the GTGT templates on TT99 accounts."""

	def test_templates_created_on_company(self):
		company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "_Test VN GTGT",
				"abbr": "TVGT",
				"default_currency": "VND",
				"country": "Vietnam",
				"chart_of_accounts": CHART_NAME,
				"enable_perpetual_inventory": 1,
			}
		)
		company.flags.ignore_permissions = True
		company.insert()

		for title in SALES_TEMPLATES:
			self.assertTrue(
				frappe.db.exists(
					"Sales Taxes and Charges Template", {"title": title, "company": company.name}
				),
				f"missing sales template {title!r}",
			)
		for title in PURCHASE_TEMPLATES:
			self.assertTrue(
				frappe.db.exists(
					"Purchase Taxes and Charges Template", {"title": title, "company": company.name}
				),
				f"missing purchase template {title!r}",
			)
		for title in ITEM_TAX_TEMPLATES:
			self.assertTrue(
				frappe.db.exists("Item Tax Template", {"title": title, "company": company.name}),
				f"missing item tax template {title!r}",
			)
		for title in TAX_CATEGORIES:
			self.assertTrue(frappe.db.exists("Tax Category", title), f"missing tax category {title!r}")

		# The default 10% sales template must post to the TT99 output-VAT account 33311.
		default_sales = frappe.get_doc(
			"Sales Taxes and Charges Template", {"title": "GTGT bán ra 10%", "company": company.name}
		)
		acct_number = frappe.db.get_value("Account", default_sales.taxes[0].account_head, "account_number")
		self.assertEqual(acct_number, OUTPUT_VAT_NUMBER)
		self.assertEqual(default_sales.taxes[0].rate, 10.0)


if __name__ == "__main__":
	unittest.main()
