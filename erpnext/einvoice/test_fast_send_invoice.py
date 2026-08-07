# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nút 10 — gửi hóa đơn chính thức cho khách hàng (mục E7)."""

import base64

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from erpnext.einvoice.actions import download_official_pdf, send_invoice_to_customer
from erpnext.einvoice.builder import create_from_delivery_note
from erpnext.einvoice.constants import STATUS_DRAFT, STATUS_ISSUED, STATUS_SENT
from erpnext.einvoice.fast_client import FastClient
from erpnext.einvoice.test_fast_approval import Mailbox
from erpnext.einvoice.test_fast_client import FakeTransport, configure, envelope
from erpnext.einvoice.test_fast_pdf import pdf_envelope, sent_payload
from erpnext.einvoice.test_fixtures import make_delivery_note

FEI = "Fast EInvoice Document"
LOG = "Fast EInvoice Log"


class SendInvoiceBase(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure(token="TOKEN-ABC", token_time=now_datetime())
		self.dn = make_delivery_note()
		self.fei = frappe.get_doc(FEI, create_from_delivery_note(self.dn.name))
		frappe.db.set_value(
			FEI,
			self.fei.name,
			{
				"status": STATUS_ISSUED,
				"fast_key_search": "KS-ABC-123",
				"fast_invoice_no": "2",
				"fast_serial": "1C26TMY",
				"fast_pattern": "1/001",
				"fast_signed_date": "2026-08-07",
			},
		)
		self.fei.reload()
		self.mailbox = Mailbox()

	def tearDown(self):
		frappe.db.rollback()

	def _client(self, *responses):
		self.transport = FakeTransport(envelope(1, "still valid"), *responses)
		return FastClient(transport=self.transport)

	def _attach_official_pdf(self):
		download_official_pdf(self.fei.name, client=self._client(pdf_envelope()))
		self.fei.reload()


class TestSendViaErp(SendInvoiceBase):
	"""Phương án A — ERP tự gửi (mặc định theo khuyến nghị của đặc tả)."""

	def setUp(self):
		super().setUp()
		self._attach_official_pdf()

	def test_sending_moves_to_sent_status(self):
		send_invoice_to_customer(self.fei.name, mailer=self.mailbox)

		self.fei.reload()
		self.assertEqual(self.fei.status, STATUS_SENT)
		self.assertEqual(self.fei.invoice_send_count, 1)
		self.assertIsNotNone(self.fei.invoice_sent_time)

	def test_email_carries_the_number_serial_and_lookup_code(self):
		"""Khách cần mã tra cứu để tự đối chiếu trên cổng của Fast/CQT."""
		send_invoice_to_customer(self.fei.name, mailer=self.mailbox)

		body = self.mailbox.sent[0]["message"]
		self.assertIn("2", body)
		self.assertIn("1C26TMY", body)
		self.assertIn("KS-ABC-123", body)

	def test_official_pdf_is_attached(self):
		send_invoice_to_customer(self.fei.name, mailer=self.mailbox)
		self.assertIn("HD_1C26TMY_2", str(self.mailbox.sent[0]["attachments"]))

	def test_recipient_defaults_to_the_invoice_email(self):
		send_invoice_to_customer(self.fei.name, mailer=self.mailbox)
		self.assertEqual(self.mailbox.sent[0]["recipients"], [self.fei.email_deliver])

	def test_resending_counts_up(self):
		send_invoice_to_customer(self.fei.name, mailer=self.mailbox)
		send_invoice_to_customer(self.fei.name, recipients="them@bvx.vn", mailer=self.mailbox)

		self.fei.reload()
		self.assertEqual(self.fei.invoice_send_count, 2)
		self.assertEqual(self.fei.invoice_sent_to, "them@bvx.vn")

	def test_sending_is_logged(self):
		send_invoice_to_customer(self.fei.name, mailer=self.mailbox)
		self.assertTrue(
			frappe.db.exists(LOG, {"fei_document": self.fei.name, "operation": "Email", "success": 1})
		)


class TestSendViaFast(SendInvoiceBase):
	"""Phương án B — nhờ Fast gửi bằng method 700."""

	def test_fast_is_asked_to_send_with_key_and_email(self):
		send_invoice_to_customer(
			self.fei.name, via="fast", recipients="kt@bvx.vn", client=self._client(envelope(1, "ok"))
		)

		payload = sent_payload(self.transport.calls[-1]["body"])
		self.assertEqual(payload["key"], "KS-ABC-123")
		self.assertEqual(payload["email"], "kt@bvx.vn")

	def test_method_700_is_used(self):
		send_invoice_to_customer(
			self.fei.name, via="fast", recipients="kt@bvx.vn", client=self._client(envelope(1, "ok"))
		)
		self.assertTrue(frappe.db.exists(LOG, {"fei_document": self.fei.name, "method": 700}))

	def test_status_advances_after_fast_sends(self):
		send_invoice_to_customer(
			self.fei.name, via="fast", recipients="kt@bvx.vn", client=self._client(envelope(1, "ok"))
		)

		self.fei.reload()
		self.assertEqual(self.fei.status, STATUS_SENT)

	def test_a_fast_error_does_not_mark_it_sent(self):
		send_invoice_to_customer(
			self.fei.name, via="fast", recipients="kt@bvx.vn", client=self._client(envelope(0, "802|Khong co quyen"))
		)

		self.fei.reload()
		self.assertEqual(self.fei.status, STATUS_ISSUED)
		self.assertEqual(self.fei.invoice_send_count, 0)

	def test_no_official_pdf_is_needed_when_fast_sends_it(self):
		"""Fast gửi từ bản của Fast — không cần ta tải PDF về trước."""
		self.assertFalse(self.fei.official_pdf)
		send_invoice_to_customer(
			self.fei.name, via="fast", recipients="kt@bvx.vn", client=self._client(envelope(1, "ok"))
		)
		self.fei.reload()
		self.assertEqual(self.fei.status, STATUS_SENT)


class TestSendPreconditions(SendInvoiceBase):
	def test_an_unissued_invoice_cannot_be_sent(self):
		frappe.db.set_value(FEI, self.fei.name, "status", STATUS_DRAFT)
		with self.assertRaises(frappe.ValidationError):
			send_invoice_to_customer(self.fei.name, mailer=self.mailbox)

	def test_erp_sending_needs_the_official_pdf_first(self):
		"""Gửi hóa đơn mà thiếu file đính kèm thì khách nhận được một email rỗng."""
		self.assertFalse(self.fei.official_pdf)
		with self.assertRaises(frappe.ValidationError):
			send_invoice_to_customer(self.fei.name, mailer=self.mailbox)

	def test_missing_recipient_is_refused(self):
		self._attach_official_pdf()
		frappe.db.set_value(FEI, self.fei.name, "email_deliver", "")
		with self.assertRaises(frappe.ValidationError):
			send_invoice_to_customer(self.fei.name, mailer=self.mailbox)
