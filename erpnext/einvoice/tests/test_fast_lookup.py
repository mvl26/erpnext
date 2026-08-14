# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tra số hóa đơn điện tử cho bảng kê bán ra / tờ khai 01/GTGT (T23)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.einvoice.builder import create_from_delivery_note
from erpnext.einvoice.constants import STATUS_CANCELLED, STATUS_DRAFT, STATUS_TAX_ACCEPTED
from erpnext.einvoice.lookup import invoice_numbers_for
from erpnext.einvoice.tests.test_fast_client import configure
from erpnext.einvoice.tests.test_fixtures import make_delivery_note

FEI = "Fast EInvoice Document"


class TestInvoiceNumberLookup(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure()
		self.dn = make_delivery_note()
		self.fei = create_from_delivery_note(self.dn.name)

	def tearDown(self):
		frappe.db.rollback()

	def _issue(self, status=STATUS_TAX_ACCEPTED, **values):
		frappe.db.set_value(
			FEI,
			self.fei,
			{
				"status": status,
				"fast_invoice_no": "2",
				"fast_serial": "1C26TMY",
				"fast_pattern": "1/001",
				"fast_signed_date": "2026-08-07",
				**values,
			},
		)

	def _sales_invoice_from_delivery_note(self):
		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice

		si = make_sales_invoice(self.dn.name)
		si.flags.ignore_permissions = True
		si.insert()
		si.submit()
		return si

	def test_no_invoices_returns_empty(self):
		self.assertEqual(invoice_numbers_for([]), {})

	def test_a_directly_linked_sales_invoice_finds_its_number(self):
		si = self._sales_invoice_from_delivery_note()
		self._issue(sales_invoice=si.name)

		found = invoice_numbers_for([si.name])
		self.assertEqual(found[si.name]["number"], "2")
		self.assertEqual(found[si.name]["symbol"], "1C26TMY")

	def test_the_number_is_found_through_the_delivery_note(self):
		"""Hóa đơn phát hành trên phiếu giao, còn bảng kê dựng từ hóa đơn bán."""
		si = self._sales_invoice_from_delivery_note()
		self._issue()

		found = invoice_numbers_for([si.name])
		self.assertEqual(found[si.name]["number"], "2")

	def test_a_draft_einvoice_never_reaches_the_declaration(self):
		si = self._sales_invoice_from_delivery_note()
		frappe.db.set_value(FEI, self.fei, "status", STATUS_DRAFT)

		self.assertEqual(invoice_numbers_for([si.name]), {})

	def test_a_cancelled_einvoice_is_excluded(self):
		"""Hóa đơn bị CQT từ chối rồi hủy không được lọt vào bảng kê bán ra."""
		si = self._sales_invoice_from_delivery_note()
		self._issue(status=STATUS_CANCELLED)

		self.assertEqual(invoice_numbers_for([si.name]), {})

	def test_a_sales_invoice_with_no_einvoice_is_simply_absent(self):
		si = self._sales_invoice_from_delivery_note()
		self.assertEqual(invoice_numbers_for([si.name]), {})


class TestBangKeBanRaUsesTheFastNumber(FrappeTestCase):
	"""Nghiệm thu T23: bảng kê bán ra phải hiện số hóa đơn Fast, không phải tên SI."""

	def setUp(self):
		frappe.db.rollback()
		configure()

	def tearDown(self):
		frappe.db.rollback()

	def test_the_declared_number_comes_from_the_einvoice(self):
		from erpnext.einvoice.tests.test_fixtures import COMPANY
		from erpnext.regional.report.to_khai_thue_gtgt_01.to_khai_thue_gtgt_01 import bang_ke_ban_ra
		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice

		dn = make_delivery_note()
		fei = create_from_delivery_note(dn.name)
		frappe.db.set_value(
			FEI,
			fei,
			{
				"status": STATUS_TAX_ACCEPTED,
				"fast_invoice_no": "2",
				"fast_serial": "1C26TMY",
			},
		)

		si = make_sales_invoice(dn.name)
		si.flags.ignore_permissions = True
		si.insert()
		si.submit()

		rows = bang_ke_ban_ra(COMPANY, si.posting_date, si.posting_date)
		row = next(r for r in rows if r["doanh_so"])

		self.assertEqual(row["so_hoa_don"], "2")
		self.assertEqual(row["ky_hieu"], "1C26TMY")
