# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tra số hóa đơn điện tử cho bảng kê bán ra / tờ khai 01/GTGT (T23, đặc tả bản 3.0).

Hóa đơn điện tử lập từ chính hóa đơn bán, nên số nối thẳng qua `sales_invoice`.
Đường vòng qua phiếu giao chỉ còn cho bản ghi bản 2.0 chưa gắn hóa đơn bán.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.einvoice.builder import create_from_sales_invoice, link_sales_invoice
from erpnext.einvoice.constants import (
	STATUS_CANCELLED,
	STATUS_DRAFT,
	STATUS_REPLACED,
	STATUS_TAX_ACCEPTED,
	TAX_STATUS_ACCEPTED,
)
from erpnext.einvoice.lookup import invoice_numbers_for
from erpnext.einvoice.tests.test_fast_client import configure
from erpnext.einvoice.tests.test_fixtures import (
	COMPANY,
	make_delivery_note,
	make_legacy_fei,
	make_sales_invoice,
	make_sales_invoice_from_delivery_note,
)

FEI = "Fast EInvoice Document"


def _issue(fei, number="2", status=STATUS_TAX_ACCEPTED, **values):
	frappe.db.set_value(
		FEI,
		fei,
		{
			"status": status,
			"fast_invoice_no": number,
			"fast_serial": "1C26TMY",
			"fast_pattern": "1/001",
			"fast_signed_date": "2026-08-07",
			**values,
		},
	)


class TestInvoiceNumberLookup(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure()
		self.si = make_sales_invoice()
		self.fei = create_from_sales_invoice(self.si.name)

	def tearDown(self):
		frappe.db.rollback()

	def test_no_invoices_returns_empty(self):
		self.assertEqual(invoice_numbers_for([]), {})

	def test_the_sales_invoice_finds_its_own_number(self):
		_issue(self.fei)

		found = invoice_numbers_for([self.si.name])
		self.assertEqual(found[self.si.name]["number"], "2")
		self.assertEqual(found[self.si.name]["symbol"], "1C26TMY")

	def test_a_draft_einvoice_never_reaches_the_declaration(self):
		frappe.db.set_value(FEI, self.fei, "status", STATUS_DRAFT)
		self.assertEqual(invoice_numbers_for([self.si.name]), {})

	def test_a_cancelled_einvoice_is_excluded(self):
		"""Hóa đơn bị CQT từ chối rồi hủy không được lọt vào bảng kê bán ra."""
		_issue(self.fei, status=STATUS_CANCELLED)
		self.assertEqual(invoice_numbers_for([self.si.name]), {})

	def test_a_sales_invoice_with_no_einvoice_is_simply_absent(self):
		self.assertEqual(invoice_numbers_for([make_sales_invoice().name]), {})

	def test_a_replaced_invoice_declares_the_replacement_number(self):
		from erpnext.einvoice.lineage import create_replacement

		_issue(self.fei, tax_status=TAX_STATUS_ACCEPTED)
		child = create_replacement(self.fei, reason="Sai tên hàng")
		_issue(child, number="9")
		frappe.db.set_value(FEI, self.fei, "status", STATUS_REPLACED)

		self.assertEqual(invoice_numbers_for([self.si.name])[self.si.name]["number"], "9")

	def test_an_adjustment_does_not_hide_the_original_number(self):
		from erpnext.einvoice.lineage import create_adjustment

		_issue(self.fei, tax_status=TAX_STATUS_ACCEPTED)
		child = create_adjustment(self.fei, adjustment_type="1 - Điều chỉnh giảm", reason="Trả 1 hộp")
		_issue(child, number="9")

		self.assertEqual(invoice_numbers_for([self.si.name])[self.si.name]["number"], "2")


class TestOneSalesInvoiceOverTwoDeliveries(FrappeTestCase):
	"""Kịch bản K6 #15: hóa đơn bán gộp hai phiếu giao — một hóa đơn, bảng kê lấy đúng số."""

	def setUp(self):
		frappe.db.rollback()
		configure()

	def tearDown(self):
		frappe.db.rollback()

	def test_one_invoice_covers_both_deliveries(self):
		first, second = make_delivery_note(qty=10), make_delivery_note(qty=20)
		si = make_sales_invoice_from_delivery_note(first.name, submit=False)
		for row in make_sales_invoice_from_delivery_note(second.name, submit=False).items:
			si.append("items", row.as_dict(no_default_fields=True))
		si.save()
		si.submit()

		fei = frappe.get_doc(FEI, create_from_sales_invoice(si.name))
		self.assertEqual(len(fei.lines), 2)
		self.assertEqual(sum(line.qty for line in fei.lines), 30)

		_issue(fei.name, number="11")
		self.assertEqual(invoice_numbers_for([si.name])[si.name]["number"], "11")


class TestVersionTwoRecords(FrappeTestCase):
	"""Sáu hóa đơn phát hành theo bản 2.0 vẫn lên bảng kê."""

	def setUp(self):
		frappe.db.rollback()
		configure()
		self.dn = make_delivery_note()
		self.legacy = make_legacy_fei(self.dn.name)
		_issue(self.legacy)
		self.si = make_sales_invoice_from_delivery_note(self.dn.name)

	def tearDown(self):
		frappe.db.rollback()

	def test_the_number_is_found_through_the_delivery_note(self):
		self.assertEqual(invoice_numbers_for([self.si.name])[self.si.name]["number"], "2")

	def test_once_linked_the_number_comes_the_direct_way(self):
		link_sales_invoice(self.legacy, self.si.name)
		self.assertEqual(invoice_numbers_for([self.si.name])[self.si.name]["number"], "2")


class TestBangKeBanRaUsesTheFastNumber(FrappeTestCase):
	"""Nghiệm thu T23: bảng kê bán ra phải hiện số hóa đơn Fast, không phải tên SI."""

	def setUp(self):
		frappe.db.rollback()
		configure()

	def tearDown(self):
		frappe.db.rollback()

	def _row(self, si):
		from erpnext.regional.report.to_khai_thue_gtgt_01.to_khai_thue_gtgt_01 import bang_ke_ban_ra

		rows = bang_ke_ban_ra(COMPANY, si.posting_date, si.posting_date)
		return next(r for r in rows if r.get("chung_tu") == si.name)

	def test_the_declared_number_comes_from_the_einvoice(self):
		si = make_sales_invoice()
		_issue(create_from_sales_invoice(si.name))

		row = self._row(si)
		self.assertEqual(row["so_hoa_don"], "2")
		self.assertEqual(row["ky_hieu"], "1C26TMY")

	def test_a_sales_invoice_without_an_einvoice_shows_a_missing_number(self):
		"""Lấy tên chứng từ ERP thế vào là che mất khoản doanh thu chưa xuất hóa đơn."""
		si = make_sales_invoice()
		self.assertEqual(self._row(si)["so_hoa_don"], "")
