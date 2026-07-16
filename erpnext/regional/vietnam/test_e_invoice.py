# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Tests for Vietnam hóa đơn điện tử (NĐ 70/2025): log DocType, fields, issuance."""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.regional.vietnam.setup import _acct
from erpnext.regional.vietnam.test_books_and_vouchers import _make_party
from erpnext.regional.vietnam.test_setup import make_vn_company


def _make_service_item(name="_Test VN EInv Service"):
	if not frappe.db.exists("Item", name):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": name,
				"item_name": name,
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 0,
			}
		).insert(ignore_permissions=True)
	return name


def make_draft_sales_invoice(company, rate=10_000_000, customer_name="_Test VN EInv Customer"):
	customer = _make_party("Customer", customer_name)
	si = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"company": company,
			"customer": customer.name,
			"posting_date": frappe.utils.nowdate(),
			"items": [{"item_code": _make_service_item(), "qty": 1, "rate": rate}],
		}
	)
	si.flags.ignore_permissions = True
	si.insert()
	return si


class TestVietnamEInvoiceLog(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = make_vn_company("_Test VN EInvoice", "TVEV")
		cls.si = make_draft_sales_invoice(cls.company)

	def test_doctype_installed(self):
		self.assertTrue(frappe.db.exists("DocType", "Vietnam E Invoice Log"))

	def test_log_crud_and_status(self):
		log = frappe.get_doc(
			{"doctype": "Vietnam E Invoice Log", "sales_invoice": self.si.name, "provider": "mock"}
		).insert(ignore_permissions=True)
		self.assertEqual(log.status, "Draft")
		self.assertEqual(log.company, self.company)

		log.status = "Issued"
		log.invoice_number = "00000042"
		log.save(ignore_permissions=True)
		self.assertEqual(
			frappe.db.get_value("Vietnam E Invoice Log", log.name, "invoice_number"), "00000042"
		)

	def test_self_lineage_blocked(self):
		log = frappe.get_doc(
			{"doctype": "Vietnam E Invoice Log", "sales_invoice": self.si.name}
		).insert(ignore_permissions=True)
		log.adjusts = log.name
		self.assertRaises(frappe.ValidationError, log.save)
