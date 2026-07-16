# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Tests for Vietnam hóa đơn điện tử (NĐ 70/2025): log DocType, fields, issuance."""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.regional.vietnam.setup import _acct
from erpnext.regional.vietnam.test_books_and_vouchers import _make_party
from erpnext.regional.vietnam.test_setup import make_vn_company


def _ensure_vn_company(name, abbr):
	"""Get-or-create: the custom-field DDL in setup() implicitly commits the test
	transaction once per site, so this class's company can outlive a test run."""
	return frappe.db.get_value("Company", name, "name") or make_vn_company(name, abbr)


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
		cls.company = _ensure_vn_company("_Test VN EInvoice", "TVEV")
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


COMPANY_EINVOICE_FIELDS = ("vn_einvoice_enabled", "vn_einvoice_provider", "vn_einvoice_symbol")
SI_EINVOICE_FIELDS = (
	"vn_einvoice_number",
	"vn_einvoice_symbol",
	"vn_einvoice_cqt_code",
	"vn_einvoice_status",
	"vn_einvoice_log",
)


class TestVietnamEInvoiceFields(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Creating a VN company dispatches the regional setup() hook.
		cls.company = _ensure_vn_company("_Test VN EInv Fields", "TVEF")

	def test_company_fields_created(self):
		for field in COMPANY_EINVOICE_FIELDS:
			self.assertTrue(
				frappe.db.exists("Custom Field", {"dt": "Company", "fieldname": field}),
				f"missing Company custom field {field}",
			)

	def test_sales_invoice_fields_created(self):
		for field in SI_EINVOICE_FIELDS:
			self.assertTrue(
				frappe.db.exists("Custom Field", {"dt": "Sales Invoice", "fieldname": field}),
				f"missing Sales Invoice custom field {field}",
			)

	def test_setup_rerun_creates_no_duplicates(self):
		from erpnext.regional.vietnam.setup import setup

		setup(self.company)
		setup(self.company)
		self.assertEqual(
			frappe.db.count("Custom Field", {"dt": "Sales Invoice", "fieldname": "vn_einvoice_status"}), 1
		)


class TestVietnamEInvoicePayload(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = _ensure_vn_company("_Test VN EInv Payload", "TVEP")
		cls.si = make_draft_sales_invoice(cls.company)

	def test_payload_totals_match_invoice(self):
		from erpnext.regional.vietnam.e_invoice import build_invoice_payload

		payload = build_invoice_payload(self.si)
		self.assertEqual(payload["seller"]["name"], self.company)
		self.assertEqual(payload["invoice"]["erp_reference"], self.si.name)
		self.assertEqual(payload["invoice"]["grand_total"], 10_000_000)
		self.assertEqual(payload["invoice"]["lines"][0]["qty"], 1)
		self.assertIn("Mười triệu đồng", payload["invoice"]["in_words"])

	def test_unknown_provider_raises(self):
		from erpnext.regional.vietnam.e_invoice_providers import get_provider

		self.assertRaises(frappe.ValidationError, get_provider, "nope")

	def test_mock_provider_issues_deterministically(self):
		from erpnext.regional.vietnam.e_invoice import build_invoice_payload
		from erpnext.regional.vietnam.e_invoice_providers import get_provider

		provider = get_provider("mock")
		payload = build_invoice_payload(self.si)
		first, second = provider.issue(payload), provider.issue(payload)
		self.assertTrue(first["ok"])
		self.assertEqual(first["invoice_number"], second["invoice_number"])
		self.assertTrue(first["invoice_number"].isdigit())
		self.assertIn(first["invoice_number"], first["xml"])


class TestVietnamEInvoiceIssuance(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = _ensure_vn_company("_Test VN EInv Issue", "TVIS")
		frappe.db.set_value(
			"Company",
			cls.company,
			{"vn_einvoice_enabled": 1, "vn_einvoice_provider": "mock", "vn_einvoice_symbol": "1C26TAA"},
		)

	def test_submit_issues_and_stamps_the_invoice(self):
		si = make_draft_sales_invoice(self.company, customer_name="_Test VN EInv Issue Cust")
		si.submit()
		si.reload()
		self.assertEqual(si.vn_einvoice_status, "Issued")
		self.assertTrue(si.vn_einvoice_number)
		self.assertEqual(si.vn_einvoice_symbol, "1C26TAA")
		log = frappe.get_doc("Vietnam E Invoice Log", si.vn_einvoice_log)
		self.assertEqual(log.status, "Issued")
		self.assertEqual(log.invoice_number, si.vn_einvoice_number)
		self.assertIn(si.name, log.xml)

	def test_disabled_company_is_untouched(self):
		company = _ensure_vn_company("_Test VN EInv Off", "TVIO")
		si = make_draft_sales_invoice(company, customer_name="_Test VN EInv Off Cust")
		si.submit()
		si.reload()
		self.assertFalse(si.vn_einvoice_status)
		self.assertFalse(frappe.db.exists("Vietnam E Invoice Log", {"sales_invoice": si.name}))

	def test_provider_error_never_blocks_submit_then_retry_succeeds(self):
		from unittest.mock import patch

		from erpnext.regional.vietnam.e_invoice import issue_e_invoice

		si = make_draft_sales_invoice(self.company, customer_name="_Test VN EInv Err Cust")
		with patch(
			"erpnext.regional.vietnam.e_invoice_providers.mock.MockProvider.issue",
			side_effect=Exception("provider down"),
		):
			si.submit()
		si.reload()
		self.assertEqual(si.docstatus, 1)  # accounting never blocked
		self.assertEqual(si.vn_einvoice_status, "Error")
		error_log = frappe.get_doc("Vietnam E Invoice Log", si.vn_einvoice_log)
		self.assertIn("provider down", error_log.error_message)

		issue_e_invoice(si.name)  # whitelisted retry path
		si.reload()
		self.assertEqual(si.vn_einvoice_status, "Issued")
		self.assertTrue(si.vn_einvoice_number)


class TestVietnamEInvoiceLineage(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = _ensure_vn_company("_Test VN EInv Line", "TVIL")
		frappe.db.set_value(
			"Company",
			cls.company,
			{"vn_einvoice_enabled": 1, "vn_einvoice_provider": "mock", "vn_einvoice_symbol": "1C26TAA"},
		)

	def _submit_invoice(self, customer_name):
		si = make_draft_sales_invoice(self.company, customer_name=customer_name)
		si.submit()
		si.reload()
		return si

	def test_return_invoice_issues_dieu_chinh(self):
		original = self._submit_invoice("_Test VN EInv Adj Cust")
		ret = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": self.company,
				"customer": original.customer,
				"posting_date": frappe.utils.nowdate(),
				"is_return": 1,
				"return_against": original.name,
				"items": [{"item_code": "_Test VN EInv Service", "qty": -1, "rate": 10_000_000}],
			}
		)
		ret.flags.ignore_permissions = True
		ret.insert()
		ret.submit()
		ret.reload()

		self.assertEqual(ret.vn_einvoice_status, "Issued")
		adj_log = frappe.get_doc("Vietnam E Invoice Log", ret.vn_einvoice_log)
		self.assertEqual(adj_log.adjusts, original.vn_einvoice_log)
		self.assertNotEqual(adj_log.invoice_number, original.vn_einvoice_number)
		self.assertEqual(
			frappe.db.get_value("Vietnam E Invoice Log", original.vn_einvoice_log, "status"), "Adjusted"
		)

	def test_replacement_links_and_marks_original(self):
		from erpnext.regional.vietnam.e_invoice import issue_replacement

		original = self._submit_invoice("_Test VN EInv Rep Cust 1")
		replacement = self._submit_invoice("_Test VN EInv Rep Cust 2")

		log_name = issue_replacement(replacement.name, replaces_invoice=original.name)
		replacement.reload()

		self.assertEqual(replacement.vn_einvoice_log, log_name)
		rep_log = frappe.get_doc("Vietnam E Invoice Log", log_name)
		self.assertEqual(rep_log.status, "Issued")
		self.assertEqual(rep_log.replaces, original.vn_einvoice_log)
		self.assertEqual(
			frappe.db.get_value("Vietnam E Invoice Log", original.vn_einvoice_log, "status"), "Replaced"
		)
