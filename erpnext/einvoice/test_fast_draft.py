# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nút 3 — xem bản nháp PDF (action=600, method=310) — mục E2."""

import base64

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.einvoice.actions import preview_draft
from erpnext.einvoice.builder import create_from_delivery_note
from erpnext.einvoice.constants import (
	STATUS_DRAFT,
	STATUS_DRAFT_VIEWED,
	STATUS_ISSUED,
	STATUS_TAX_ACCEPTED,
)
from erpnext.einvoice.fast_client import FastClient
from erpnext.einvoice.test_fast_client import checkkey_ok, FakeTransport, configure, envelope
from erpnext.einvoice.test_fixtures import make_delivery_note, minimal_pdf_bytes

FEI = "Fast EInvoice Document"
LOG = "Fast EInvoice Log"
PDF_BYTES = minimal_pdf_bytes()


def pdf_response():
	return envelope(1, base64.b64encode(PDF_BYTES).decode())


class TestPreviewDraft(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure(token="TOKEN-ABC", token_time=frappe.utils.now_datetime())
		self.dn = make_delivery_note()
		self.fei = frappe.get_doc(FEI, create_from_delivery_note(self.dn.name))

	def tearDown(self):
		frappe.db.rollback()

	def _client(self, *responses):
		self.transport = FakeTransport(checkkey_ok(), *responses)
		return FastClient(transport=self.transport)

	def test_draft_pdf_is_attached_and_status_advances(self):
		preview_draft(self.fei.name, client=self._client(pdf_response()))

		self.fei.reload()
		self.assertEqual(self.fei.status, STATUS_DRAFT_VIEWED)
		self.assertTrue(self.fei.draft_pdf)
		self.assertIsNotNone(self.fei.draft_pdf_time)

	def test_attached_file_holds_the_decoded_pdf(self):
		preview_draft(self.fei.name, client=self._client(pdf_response()))
		self.fei.reload()

		file_doc = frappe.get_doc("File", {"file_url": self.fei.draft_pdf})
		content = file_doc.get_content()
		if isinstance(content, str):
			content = content.encode("latin-1")
		self.assertEqual(content, PDF_BYTES)

	def test_draft_file_is_private(self):
		"""Bản nháp hóa đơn là dữ liệu khách hàng — không để công khai."""
		preview_draft(self.fei.name, client=self._client(pdf_response()))
		self.fei.reload()
		self.assertEqual(frappe.get_doc("File", {"file_url": self.fei.draft_pdf}).is_private, 1)

	def test_the_call_uses_action_600_so_no_invoice_number_is_burned(self):
		"""action=600 là xem trước: không ký số, không lên CQT, không tiêu số."""
		preview_draft(self.fei.name, client=self._client(pdf_response()))

		log = frappe.get_doc(LOG, {"fei_document": self.fei.name, "method": 310})
		self.assertEqual(log.action, 600)
		self.assertEqual(log.method, 310)
		self.assertEqual(log.status, "Thành công")

	def test_previewing_twice_stays_in_the_viewed_status(self):
		preview_draft(self.fei.name, client=self._client(pdf_response()))
		self.fei.reload()
		first_time = self.fei.draft_pdf_time

		preview_draft(self.fei.name, client=self._client(pdf_response()))
		self.fei.reload()
		self.assertEqual(self.fei.status, STATUS_DRAFT_VIEWED)
		self.assertGreaterEqual(self.fei.draft_pdf_time, first_time)

	def test_a_changed_draft_produces_a_new_file(self):
		"""Nội dung giống hệt thì Frappe dùng lại file cũ; nội dung khác phải ra file mới."""
		preview_draft(self.fei.name, client=self._client(pdf_response()))
		self.fei.reload()
		first = self.fei.draft_pdf

		revised = base64.b64encode(PDF_BYTES + b"%% ban sua\n").decode()
		preview_draft(self.fei.name, client=self._client(envelope(1, revised)))
		self.fei.reload()
		self.assertNotEqual(self.fei.draft_pdf, first)

	# --- Đường lỗi --------------------------------------------------------

	def test_fast_error_keeps_the_status_and_records_the_reason(self):
		"""Mục E2: lỗi thì giữ nguyên trạng thái, không nhảy sang 02."""
		preview_draft(self.fei.name, client=self._client(envelope(0, "836|Loi so lieu")))

		self.fei.reload()
		self.assertEqual(self.fei.status, STATUS_DRAFT)
		self.assertEqual(self.fei.error_code, "836")
		self.assertIn("Thiếu thông tin bắt buộc", self.fei.error_message)
		self.assertFalse(self.fei.draft_pdf)

	def test_blocking_validation_stops_before_any_network_call(self):
		"""Dữ liệu sai thì không tốn một lời gọi nào với Fast."""
		frappe.db.set_value(FEI, self.fei.name, "amount_in_words", "")
		client = self._client(pdf_response())

		with self.assertRaises(frappe.ValidationError):
			preview_draft(self.fei.name, client=client)

		self.assertEqual(self.transport.calls, [])

	def test_issued_invoice_cannot_be_previewed_as_a_draft(self):
		frappe.db.set_value(FEI, self.fei.name, "status", STATUS_ISSUED)
		with self.assertRaises(frappe.ValidationError):
			preview_draft(self.fei.name, client=self._client(pdf_response()))

	def test_tax_accepted_invoice_cannot_be_previewed_as_a_draft(self):
		frappe.db.set_value(FEI, self.fei.name, "status", STATUS_TAX_ACCEPTED)
		with self.assertRaises(frappe.ValidationError):
			preview_draft(self.fei.name, client=self._client(pdf_response()))

	def test_disabled_integration_refuses(self):
		configure(enabled=0)
		with self.assertRaises(frappe.ValidationError):
			preview_draft(self.fei.name, client=self._client(pdf_response()))
