# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Tests for TT45 khung khấu hao defaults on the VN Asset Categories."""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.regional.vietnam.test_setup import make_vn_company


class TestVietnamTT45(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Creating a VN company dispatches setup(), which applies the TT45 defaults.
		cls.company = make_vn_company("_Test VN TT45", "TVT4")

	def test_categories_carry_tt45_defaults(self):
		from erpnext.regional.vietnam.tt45 import TT45_USEFUL_LIFE_YEARS

		for name, years in TT45_USEFUL_LIFE_YEARS.items():
			category = frappe.get_doc("Asset Category", name)
			self.assertTrue(category.finance_books, f"{name} missing depreciation defaults")
			row = category.finance_books[0]
			self.assertEqual(row.total_number_of_depreciations, years * 12)
			self.assertEqual(row.frequency_of_depreciation, 1)
			self.assertEqual(row.depreciation_method, "Straight Line")

	def test_rerun_creates_no_duplicate_rows(self):
		from erpnext.regional.vietnam.setup import setup

		setup(self.company)
		setup(self.company)
		category = frappe.get_doc("Asset Category", "Tài sản cố định hữu hình")
		self.assertEqual(len(category.finance_books), 1)

	def test_user_tuned_values_are_preserved(self):
		from erpnext.regional.vietnam.tt45 import apply_tt45_useful_life

		category = frappe.get_doc("Asset Category", "Tài sản cố định vô hình")
		category.finance_books[0].total_number_of_depreciations = 120
		category.flags.ignore_permissions = True
		category.save()

		apply_tt45_useful_life()
		category.reload()
		self.assertEqual(category.finance_books[0].total_number_of_depreciations, 120)
