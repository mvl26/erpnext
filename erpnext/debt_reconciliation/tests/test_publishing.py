# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Gửi email + PDF (T5, T6), mẫu in (T3, T16, T21), bulk duyệt, nhắc hạn (T10)."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.debt_reconciliation import constants as C
from erpnext.debt_reconciliation import publishing, reminders
from erpnext.debt_reconciliation.generation import build_statement
from erpnext.debt_reconciliation.tests.utils import get_company, make_party, post

FROM, TO = "2026-03-01", "2026-03-31"


class TestPublishing(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = get_company("_Test DR Gen", "TDRG")

	def make(self, party_type="Supplier", dr=0, cr=0, **party_fields):
		party = make_party(party_type, **party_fields)
		if dr or cr:
			post(self.company, party_type, party, dr, cr, "2026-03-10")
		name, _ = build_statement(self.company, party_type, party, FROM, TO, C.SOURCE_MANUAL)
		return frappe.get_doc(C.DOCTYPE, name)

	def test_valid_email_is_queued_with_pdf_and_marked_sent(self):
		doc = self.make("Supplier", cr=1_500_000, reconciliation_email="ncc.ok@example.com")
		doc.submit()
		doc.reload()
		self.assertEqual(doc.status, C.STATUS_SENT)
		self.assertTrue(doc.sent_on)
		self.assertTrue(doc.sent_pdf)
		self.assertTrue(doc.email_queue)
		recipients = frappe.get_all(
			"Email Queue Recipient", filters={"parent": doc.email_queue}, pluck="recipient"
		)
		self.assertEqual(recipients, ["ncc.ok@example.com"])
		queue = frappe.get_doc("Email Queue", doc.email_queue)
		self.assertEqual((queue.reference_doctype, queue.reference_name), (C.DOCTYPE, doc.name))
		self.assertEqual(
			frappe.parse_json(queue.attachments),
			[{"fid": frappe.db.get_value("File", {"file_url": doc.sent_pdf})}],
		)
		file_doc = frappe.get_doc("File", {"file_url": doc.sent_pdf})
		self.assertTrue(file_doc.is_private)
		self.assertTrue(file_doc.get_content().startswith(b"%PDF"))

	def test_missing_email_marks_send_failed_then_resend(self):
		doc = self.make("Customer", dr=200_000)
		self.assertIn("chưa có email", doc.missing_party_warning)
		doc.submit()
		doc.reload()
		self.assertEqual(doc.status, C.STATUS_SEND_FAILED)
		self.assertTrue(doc.send_error)

		self.assertRaises(frappe.ValidationError, doc.apply_action, "resend", email="khong-hop-le")
		doc.apply_action("resend", email="kh.moi@example.com")
		self.assertEqual(doc.status, C.STATUS_SENT)
		self.assertEqual(doc.reconciliation_email, "kh.moi@example.com")
		self.assertFalse(doc.send_error)

	def test_invalid_email_marks_send_failed(self):
		doc = self.make("Supplier", cr=10_000, reconciliation_email="ok@example.com")
		self.assertRaises(frappe.InvalidEmailAddressError, doc.update({"reconciliation_email": "sai@"}).save)
		doc.reload()
		doc.submit()
		# email sai lọt vào DB bằng đường khác (import, SQL) vẫn phải ra Lỗi gửi, không im lặng
		frappe.db.set_value(
			C.DOCTYPE, doc.name, {"reconciliation_email": "sai-dinh-dang@", "status": C.STATUS_APPROVED}
		)
		publishing.send_statement(doc.name)
		self.assertEqual(frappe.db.get_value(C.DOCTYPE, doc.name, "status"), C.STATUS_SEND_FAILED)

	def test_bulk_approve_isolates_failures(self):
		ok = self.make("Supplier", cr=10_000, reconciliation_email="a@example.com")
		no_figures = self.make("Supplier", cr=20_000, reconciliation_email="b@example.com")
		no_figures.db_set("figures_fetched_on", None)
		result = publishing.bulk_approve([ok.name, no_figures.name])
		self.assertEqual(result["ok"], [ok.name])
		self.assertEqual([f["name"] for f in result["failed"]], [no_figures.name])
		self.assertEqual(frappe.db.get_value(C.DOCTYPE, ok.name, "status"), C.STATUS_SENT)
		self.assertEqual(frappe.db.get_value(C.DOCTYPE, no_figures.name, "docstatus"), 0)

	def test_email_template_renders_deadline(self):
		doc = self.make("Supplier", cr=10_000)
		subject, message = publishing.render_email(doc, frappe.get_cached_doc(C.SETTINGS))
		self.assertIn("03/2026", subject)
		self.assertIn(doc.party_name, message)
		self.assertIn("06/04/2026", message)


class TestPrintFormats(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = get_company("_Test DR Gen", "TDRG")

	def render(self, doc):
		return frappe.get_print(C.DOCTYPE, doc.name, print_format=C.PRINT_FORMATS[doc.party_type], doc=doc)

	def make(self, party_type, dr, cr, **fields):
		party = make_party(party_type, framework_contract_no="HDNT-01/2026", representative_name="Ông Test")
		post(self.company, party_type, party, dr, cr, "2026-03-10")
		name, _ = build_statement(self.company, party_type, party, FROM, TO, C.SOURCE_MANUAL)
		doc = frappe.get_doc(C.DOCTYPE, name)
		doc.update(fields)
		doc.save()
		return doc

	def test_supplier_layout(self):
		doc = self.make("Supplier", 0, 56_001_171_083, interest_in_period=5_000)
		html = self.render(doc)
		legal = frappe.db.get_single_value(C.SETTINGS, "company_legal_name")
		self.assertIn("03.SL MVL-…./2026", html)
		self.assertIn("HDNT-01/2026", html)
		# NCC là Bên A (bán), Miyano là Bên B (mua)
		self.assertLess(html.index(doc.party_name), html.index("II. Bên mua (Bên B)"))
		self.assertGreater(html.index(legal, html.index("II. Bên mua (Bên B)")), 0)
		# PS Có = gốc + lãi, tách ngay dưới dòng PS Có
		self.assertIn("56.001.176.083", html)
		self.assertLess(html.index("1. Phát sinh có"), html.index("(2) Lãi quá hạn", html.index("[ii]")))
		self.assertLess(html.index("(2) Lãi quá hạn", html.index("[ii]")), html.index("2. Phát sinh nợ"))
		self.assertIn(f"{legal} còn nợ tiền mua hàng của {doc.party_name}", html)
		self.assertIn("./.", html)
		self.assertIn("06/04/2026", html)
		self.assertNotIn("ngày 10/", html)

	def test_customer_layout_splits_interest_under_debit(self):
		doc = self.make("Customer", 1_000_000, 0, interest_in_period=10_000)
		html = self.render(doc)
		legal = frappe.db.get_single_value(C.SETTINGS, "company_legal_name")
		# Miyano là Bên A (bán), khách hàng là Bên B (mua)
		self.assertLess(html.index(legal), html.index("II. Bên mua (Bên B)"))
		self.assertGreater(html.index(doc.party_name, html.index("II. Bên mua (Bên B)")), 0)
		ii = html.index("[ii]")
		self.assertLess(html.index("2. Phát sinh nợ", ii), html.index("(1) Giá trị gốc", ii))
		self.assertIn("1.010.000", html)
		self.assertIn(f"{doc.party_name} còn nợ tiền mua hàng của {legal}", html)

	def test_prepaid_prints_no_negative_numbers(self):
		doc = self.make("Supplier", 250_000, 0)
		html = self.render(doc)
		self.assertIn("đã thanh toán trước cho", html)
		self.assertIn("(Dư Nợ)", html)
		self.assertNotIn("-250", html)
		self.assertFalse(doc.amount_in_words.lower().startswith("âm"))


class TestReminders(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = get_company("_Test DR Gen", "TDRG")

	def test_due_lists_and_idempotency(self):
		deadline = "2031-05-06"  # ngày giả lập, không trùng dữ liệu thật
		key = f"{frappe.local.site}:dr:reminded:{deadline}"
		frappe.cache().delete(key)

		docs = []
		for i in range(2):
			party = make_party("Supplier", reconciliation_email=f"r{i}@example.com")
			post(self.company, "Supplier", party, 0, 10_000 * (i + 1), "2026-03-10")
			name, _ = build_statement(self.company, "Supplier", party, FROM, TO, C.SOURCE_MANUAL)
			doc = frappe.get_doc(C.DOCTYPE, name)
			doc.submit()
			doc.db_set("response_deadline", deadline)
			docs.append(doc)
		docs[1].reload()
		docs[1].apply_action("respond_match")

		try:
			with patch.object(reminders, "get_reminder_recipients", return_value=["Administrator"]):
				no_response, unsigned = reminders.send_due_reminders(deadline)
				self.assertIn(docs[0].name, [r.name for r in no_response])
				self.assertIn(docs[1].name, [r.name for r in unsigned])
				self.assertIsNone(reminders.send_due_reminders(deadline))  # đã nhắc trong ngày
		finally:
			frappe.cache().delete(key)
