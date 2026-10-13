# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

from frappe.tests.utils import FrappeTestCase

from erpnext.supply_notification.report.doi_tac_thieu_email_lien_he.doi_tac_thieu_email_lien_he import execute
from erpnext.supply_notification.tests import fixtures


class TestDoiTacThieuEmailLienHe(FrappeTestCase):
	def test_supplier_without_any_email_is_listed(self):
		supplier = fixtures.make_supplier()

		rows = {row["party"] for row in execute({"party_type": "Supplier"})[1]}

		self.assertIn(supplier, rows)

	def test_supplier_with_an_email_is_not_listed(self):
		supplier = fixtures.make_supplier(email="ncc@example.com")

		rows = {row["party"] for row in execute({"party_type": "Supplier"})[1]}

		self.assertNotIn(supplier, rows)
