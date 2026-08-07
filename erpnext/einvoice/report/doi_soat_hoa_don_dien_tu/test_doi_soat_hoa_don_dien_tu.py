# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Report đối soát hóa đơn điện tử."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime, nowdate

from erpnext.einvoice.builder import create_from_delivery_note
from erpnext.einvoice.constants import (
	STATUS_ERROR,
	STATUS_ISSUED,
	STATUS_NEEDS_RECONCILE,
	TAX_STATUS_ACCEPTED,
	TAX_STATUS_PENDING,
)
from erpnext.einvoice.report.doi_soat_hoa_don_dien_tu.doi_soat_hoa_don_dien_tu import (
	ISSUE_ERROR,
	ISSUE_NOT_INVOICED,
	ISSUE_TAX_OVERDUE,
	execute,
)
from erpnext.einvoice.test_fast_client import configure
from erpnext.einvoice.test_fixtures import COMPANY, make_delivery_note

FEI = "Fast EInvoice Document"


def run():
	return execute(
		{
			"company": COMPANY,
			"from_date": add_to_date(nowdate(), months=-1),
			"to_date": add_to_date(nowdate(), days=1),
		}
	)[1]


def rows_of(issue_type, rows=None):
	return [r for r in (rows if rows is not None else run()) if r["issue_type"] == issue_type]


class TestReconciliationReport(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure()

	def tearDown(self):
		frappe.db.rollback()

	def test_report_returns_columns_and_rows(self):
		columns, rows = execute({"company": COMPANY, "from_date": nowdate(), "to_date": nowdate()})
		self.assertTrue(columns)
		self.assertIsInstance(rows, list)

	# --- Chưa xuất hóa đơn -------------------------------------------------

	def test_a_delivery_note_without_an_invoice_is_listed(self):
		dn = make_delivery_note()
		self.assertIn(dn.name, [r["delivery_note"] for r in rows_of(ISSUE_NOT_INVOICED)])

	def test_a_delivery_note_with_a_live_invoice_drops_off(self):
		dn = make_delivery_note()
		create_from_delivery_note(dn.name)
		self.assertNotIn(dn.name, [r["delivery_note"] for r in rows_of(ISSUE_NOT_INVOICED)])

	def test_a_return_note_is_never_flagged_as_uninvoiced(self):
		"""Phiếu trả hàng không lập hóa đơn trực tiếp — không phải việc phải dọn."""
		returned = make_delivery_note(is_return=True)
		self.assertNotIn(returned.name, [r["delivery_note"] for r in rows_of(ISSUE_NOT_INVOICED)])

	# --- Chờ CQT quá 24 giờ ------------------------------------------------

	def test_an_invoice_waiting_over_a_day_is_flagged(self):
		dn = make_delivery_note()
		fei = create_from_delivery_note(dn.name)
		frappe.db.set_value(
			FEI,
			fei,
			{
				"status": STATUS_ISSUED,
				"tax_status": TAX_STATUS_PENDING,
				"issued_time": add_to_date(now_datetime(), hours=-30),
				"fast_invoice_no": "2",
			},
		)
		self.assertIn(fei, [r["fei_document"] for r in rows_of(ISSUE_TAX_OVERDUE)])

	def test_a_freshly_issued_invoice_is_not_flagged_yet(self):
		dn = make_delivery_note()
		fei = create_from_delivery_note(dn.name)
		frappe.db.set_value(
			FEI,
			fei,
			{"status": STATUS_ISSUED, "tax_status": TAX_STATUS_PENDING, "issued_time": now_datetime()},
		)
		self.assertNotIn(fei, [r["fei_document"] for r in rows_of(ISSUE_TAX_OVERDUE)])

	def test_an_accepted_invoice_is_not_flagged(self):
		dn = make_delivery_note()
		fei = create_from_delivery_note(dn.name)
		frappe.db.set_value(
			FEI,
			fei,
			{
				"status": STATUS_ISSUED,
				"tax_status": TAX_STATUS_ACCEPTED,
				"issued_time": add_to_date(now_datetime(), hours=-30),
			},
		)
		self.assertNotIn(fei, [r["fei_document"] for r in rows_of(ISSUE_TAX_OVERDUE)])

	# --- Lỗi / cần đối soát ------------------------------------------------

	def test_a_failed_invoice_is_listed_with_its_reason(self):
		dn = make_delivery_note()
		fei = create_from_delivery_note(dn.name)
		frappe.db.set_value(
			FEI, fei, {"status": STATUS_ERROR, "error_message": "Thiếu mã số thuế người mua"}
		)

		row = next(r for r in rows_of(ISSUE_ERROR) if r["fei_document"] == fei)
		self.assertIn("Thiếu mã số thuế", row["note"])

	def test_a_needs_reconcile_invoice_shouts_about_the_370_query(self):
		"""Nhóm nguy hiểm nhất: chưa biết đã tiêu số hóa đơn hay chưa."""
		dn = make_delivery_note()
		fei = create_from_delivery_note(dn.name)
		frappe.db.set_value(FEI, fei, "status", STATUS_NEEDS_RECONCILE)

		row = next(r for r in rows_of(ISSUE_ERROR) if r["fei_document"] == fei)
		self.assertIn("370", row["note"])

	# --- Lọc ---------------------------------------------------------------

	def test_the_issue_type_filter_narrows_the_result(self):
		make_delivery_note()
		_, rows = execute(
			{
				"company": COMPANY,
				"from_date": add_to_date(nowdate(), months=-1),
				"to_date": nowdate(),
				"issue_type": ISSUE_NOT_INVOICED,
			}
		)
		self.assertTrue(all(r["issue_type"] == ISSUE_NOT_INVOICED for r in rows))
