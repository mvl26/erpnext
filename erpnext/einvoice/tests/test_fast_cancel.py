# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nút 13c — hủy nội bộ (method 330) — mục E10."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from erpnext.einvoice.builder import create_from_delivery_note
from erpnext.einvoice.cancel import cancel_internally
from erpnext.einvoice.constants import (
	STATUS_CANCELLED,
	STATUS_ISSUED,
	STATUS_TAX_ACCEPTED,
	STATUS_TAX_REJECTED,
)
from erpnext.einvoice.fast_client import FastClient
from erpnext.einvoice.tests.test_fast_client import FakeTransport, checkkey_ok, configure, envelope
from erpnext.einvoice.tests.test_fast_pdf import sent_payload
from erpnext.einvoice.tests.test_fixtures import make_delivery_note

FEI = "Fast EInvoice Document"
LOG = "Fast EInvoice Log"
REASON = "Cơ quan Thuế từ chối do sai mã số thuế người mua"


class CancelBase(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure(token="TOKEN-ABC", token_time=now_datetime())
		self.dn = make_delivery_note()
		self.fei = frappe.get_doc(FEI, create_from_delivery_note(self.dn.name))
		frappe.db.set_value(
			FEI,
			self.fei.name,
			{
				"status": STATUS_TAX_REJECTED,
				"fast_key_search": "KS-ABC-123",
				"fast_invoice_no": "2",
				"fast_serial": "1C26TMY",
				"tax_feedback": "Sai mã số thuế người mua",
			},
		)
		frappe.db.set_value("Delivery Note", self.dn.name, "fast_invoice_no", "2")
		self.fei.reload()

	def tearDown(self):
		frappe.db.rollback()

	def _client(self, *responses):
		self.transport = FakeTransport(checkkey_ok(), *responses)
		return FastClient(transport=self.transport)


class TestCancelInternally(CancelBase):
	def test_a_rejected_invoice_can_be_cancelled(self):
		cancel_internally(self.fei.name, reason=REASON, client=self._client(envelope(1, "ok")))

		self.fei.reload()
		self.assertEqual(self.fei.status, STATUS_CANCELLED)
		self.assertEqual(self.fei.cancel_reason, REASON)
		self.assertIsNotNone(self.fei.cancelled_time)

	def test_it_uses_method_330_with_the_lookup_key(self):
		cancel_internally(
			self.fei.name,
			reason=REASON,
			minute_no="BB-09",
			minute_date="2026-08-08",
			client=self._client(envelope(1, "ok")),
		)

		payload = sent_payload(self.transport.calls[-1]["body"])
		self.assertEqual(payload["key"], "KS-ABC-123")
		self.assertEqual(payload["reason"], REASON)
		self.assertEqual(payload["minuteNo"], "BB-09")
		self.assertEqual(payload["minuteDate"], "20260808")
		self.assertTrue(frappe.db.exists(LOG, {"fei_document": self.fei.name, "method": 330}))

	def test_the_delivery_note_is_unlocked_for_a_fresh_invoice(self):
		"""Mục E10: xóa số HĐĐT trên phiếu giao nhưng GIỮ liên kết lịch sử."""
		cancel_internally(self.fei.name, reason=REASON, client=self._client(envelope(1, "ok")))

		self.dn.reload()
		self.assertFalse(self.dn.fast_invoice_no)
		self.assertEqual(self.dn.fast_einvoice, self.fei.name)
		self.assertEqual(self.dn.fast_einvoice_status, STATUS_CANCELLED)

	def test_a_new_invoice_can_be_raised_from_the_same_delivery_note(self):
		cancel_internally(self.fei.name, reason=REASON, client=self._client(envelope(1, "ok")))

		replacement = frappe.get_doc(FEI, create_from_delivery_note(self.dn.name))
		self.assertNotEqual(replacement.name, self.fei.name)

	def test_a_fast_error_leaves_the_invoice_as_rejected(self):
		cancel_internally(
			self.fei.name, reason=REASON, client=self._client(envelope(0, "78016|Da duoc chap nhan"))
		)

		self.fei.reload()
		self.assertEqual(self.fei.status, STATUS_TAX_REJECTED)
		self.assertFalse(self.fei.cancelled_time)


class TestCancelPreconditions(CancelBase):
	def test_a_tax_accepted_invoice_can_never_be_cancelled(self):
		"""NĐ 70/2025 bãi bỏ thủ tục hủy thông thường — chỉ điều chỉnh/thay thế."""
		frappe.db.set_value(FEI, self.fei.name, "status", STATUS_TAX_ACCEPTED)
		client = self._client(envelope(1, "ok"))

		with self.assertRaises(frappe.ValidationError):
			cancel_internally(self.fei.name, reason=REASON, client=client)
		self.assertEqual(self.transport.calls, [])

	def test_a_merely_issued_invoice_cannot_be_cancelled(self):
		frappe.db.set_value(FEI, self.fei.name, "status", STATUS_ISSUED)
		with self.assertRaises(frappe.ValidationError):
			cancel_internally(self.fei.name, reason=REASON, client=self._client(envelope(1, "ok")))

	def test_reason_is_mandatory(self):
		client = self._client(envelope(1, "ok"))
		with self.assertRaises(frappe.ValidationError):
			cancel_internally(self.fei.name, reason="", client=client)
		self.assertEqual(self.transport.calls, [])

	def test_only_the_chief_accountant_may_cancel(self):
		from erpnext.einvoice.setup import ROLE_STAFF
		from erpnext.einvoice.tests.test_einvoice_setup import _as, _ensure_user

		staff = _ensure_user("fei-staff-cancel@example.com", ROLE_STAFF)
		client = self._client(envelope(1, "ok"))

		with _as(staff), self.assertRaises(frappe.PermissionError):
			cancel_internally(self.fei.name, reason=REASON, client=client)
