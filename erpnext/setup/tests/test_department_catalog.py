# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.setup import department_catalog as catalog

COMPANY = "_Test Company"


def make_department(department_name, company=COMPANY) -> str:
	doc = frappe.new_doc("Department")
	doc.department_name = department_name
	doc.company = company
	doc.insert(ignore_permissions=True)
	return doc.name


class TestDepartmentMatching(FrappeTestCase):
	def test_site_names_match_their_keys(self):
		cases = {
			"P. Mua hàng": catalog.PURCHASE,
			"Mua hàng": catalog.PURCHASE,
			"P. Kinh doanh- M": catalog.SALES,
			"Kế toán": catalog.ACCOUNTS,
			"P. Kế toán tài chính": catalog.ACCOUNTS,
			"Accounts": catalog.ACCOUNTS,
			"Phòng Kho": catalog.STOCK,
			"P. HCNS - pháp chế": catalog.HR_LEGAL,
			"Hành chính - Nhân sự": catalog.HR_LEGAL,
			"Ban Giám đốc": catalog.MANAGEMENT,
		}
		for name, key in cases.items():
			with self.subTest(name=name):
				self.assertGreaterEqual(catalog.match_rank(key, name, "M"), 0)

	def test_prefix_match_respects_word_boundary(self):
		self.assertEqual(catalog.match_rank(catalog.STOCK, "Khoa học"), -1)
		self.assertEqual(catalog.match_rank(catalog.ACCOUNTS, "P. Kế toán quản trị"), 1)

	def test_keys_do_not_overlap(self):
		for row in catalog.CATALOG:
			for other in catalog.CATALOG:
				if other["key"] == row["key"]:
					continue
				with self.subTest(name=row["name"], other=other["key"]):
					self.assertEqual(catalog.match_rank(other["key"], row["name"]), -1)


class TestEnsureDepartments(FrappeTestCase):
	def test_reuses_renamed_department_instead_of_creating(self):
		existing = make_department(f"P. Mua hàng {frappe.generate_hash(length=4)}")
		for name in frappe.get_all(
			"Department", filters={"company": COMPANY, "name": ("!=", existing)}, pluck="name"
		):
			if (
				catalog.match_rank(
					catalog.PURCHASE, frappe.db.get_value("Department", name, "department_name")
				)
				>= 0
			):
				frappe.db.set_value("Department", name, "disabled", 1)

		resolved = catalog.ensure_departments(COMPANY, [catalog.PURCHASE])

		self.assertEqual(resolved[catalog.PURCHASE], existing)

	def test_creates_missing_department_once(self):
		for name in frappe.get_all("Department", filters={"company": COMPANY}, pluck="name"):
			if (
				catalog.match_rank(catalog.STOCK, frappe.db.get_value("Department", name, "department_name"))
				>= 0
			):
				frappe.db.set_value("Department", name, "disabled", 1)

		first = catalog.ensure_departments(COMPANY, [catalog.STOCK])
		second = catalog.ensure_departments(COMPANY, [catalog.STOCK])

		self.assertEqual(first, second)
		self.assertEqual(frappe.db.get_value("Department", first[catalog.STOCK], "department_name"), "P. Kho")
