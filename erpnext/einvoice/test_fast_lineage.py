# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nút 13a/13b — hóa đơn điều chỉnh (320) và thay thế (350) — mục E9."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from erpnext.einvoice.builder import create_from_delivery_note
from erpnext.einvoice.constants import (
	INVOICE_TYPE_ADJUSTMENT,
	INVOICE_TYPE_REPLACEMENT,
	STATUS_ADJUSTED,
	STATUS_CUSTOMER_APPROVED,
	STATUS_DRAFT,
	STATUS_ISSUED,
	STATUS_REPLACED,
	STATUS_TAX_ACCEPTED,
)
from erpnext.einvoice.fast_client import FastClient
from erpnext.einvoice.issue import issue_invoice
from erpnext.einvoice.lineage import create_adjustment, create_replacement
from erpnext.einvoice.test_fast_client import FakeTransport, configure, envelope
from erpnext.einvoice.test_fast_pdf import sent_payload
from erpnext.einvoice.test_fixtures import make_delivery_note

FEI = "Fast EInvoice Document"
LOG = "Fast EInvoice Log"

NOT_FOUND = envelope(0, "888|Khong tim thay")
CHILD_OK = envelope(
	1, '{"invoiceNo":"3","pattern":"1/001","serial":"1C26TMY","signedDate":"20260808","keySearch":"KS-CHILD"}'
)


class LineageBase(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure(token="TOKEN-ABC", token_time=now_datetime(), auto_download_pdf=0)
		self.dn = make_delivery_note()
		self.original = frappe.get_doc(FEI, create_from_delivery_note(self.dn.name))
		frappe.db.set_value(
			FEI,
			self.original.name,
			{
				"status": STATUS_TAX_ACCEPTED,
				"fast_key_search": "KS-GOC",
				"fast_invoice_no": "2",
				"fast_serial": "1C26TMY",
				"fast_signed_date": "2026-08-07",
			},
		)
		self.original.reload()

	def tearDown(self):
		frappe.db.rollback()

	def _client(self, *responses):
		self.transport = FakeTransport(envelope(1, "still valid"), *responses)
		return FastClient(transport=self.transport)

	def _make_adjustment(self, **kwargs):
		kwargs.setdefault("adjustment_type", "1 - Điều chỉnh giảm")
		kwargs.setdefault("reason", "Khách trả lại 10 hộp do sai quy cách")
		return frappe.get_doc(FEI, create_adjustment(self.original.name, **kwargs))


class TestCreateAdjustment(LineageBase):
	def test_adjustment_starts_a_fresh_lifecycle(self):
		"""Bản ghi mới đi lại đúng vòng đời từ Nháp (mục E9)."""
		child = self._make_adjustment()

		self.assertEqual(child.status, STATUS_DRAFT)
		self.assertEqual(child.invoice_type, INVOICE_TYPE_ADJUSTMENT)
		self.assertEqual(child.original_document, self.original.name)

	def test_reason_and_minute_are_carried(self):
		child = self._make_adjustment(minute_no="BB-01", minute_date="2026-08-08")

		self.assertIn("sai quy cách", child.adjustment_reason)
		self.assertEqual(child.minute_no, "BB-01")

	def test_lines_are_copied_from_the_original(self):
		child = self._make_adjustment()
		self.assertEqual(len(child.lines), len(self.original.lines))
		self.assertEqual(child.lines[0].item_code, self.original.lines[0].item_code)

	def test_the_child_gets_its_own_key(self):
		"""Dùng lại Key của hóa đơn gốc là lỗi 809 ngay lập tức."""
		child = self._make_adjustment()

		self.assertNotEqual(child.fast_key, self.original.fast_key)
		self.assertLessEqual(len(child.fast_key), 32)

	def test_the_child_carries_no_result_fields_from_the_original(self):
		child = self._make_adjustment()
		self.assertFalse(child.fast_invoice_no)
		self.assertFalse(child.fast_key_search)

	def test_reason_is_mandatory(self):
		with self.assertRaises(frappe.ValidationError):
			create_adjustment(self.original.name, adjustment_type="1 - Điều chỉnh giảm", reason="")

	def test_only_a_tax_accepted_invoice_may_be_adjusted(self):
		frappe.db.set_value(FEI, self.original.name, "status", STATUS_ISSUED)
		with self.assertRaises(frappe.ValidationError):
			self._make_adjustment()

	def test_an_already_adjusted_invoice_cannot_be_adjusted_again(self):
		"""Fast trả lỗi 901 — chặn ở ERP để khỏi tốn lời gọi."""
		frappe.db.set_value(FEI, self.original.name, "status", STATUS_ADJUSTED)
		with self.assertRaises(frappe.ValidationError):
			self._make_adjustment()

	def test_a_second_live_child_is_refused(self):
		self._make_adjustment()
		with self.assertRaises(frappe.ValidationError):
			self._make_adjustment()


class TestCreateReplacement(LineageBase):
	def test_replacement_is_typed_correctly(self):
		child = frappe.get_doc(
			FEI, create_replacement(self.original.name, reason="Sai nghiêm trọng, lập lại toàn bộ")
		)
		self.assertEqual(child.invoice_type, INVOICE_TYPE_REPLACEMENT)
		self.assertEqual(child.status, STATUS_DRAFT)


class TestIssuingChildren(LineageBase):
	def _issue(self, child):
		frappe.db.set_value(FEI, child.name, "status", STATUS_CUSTOMER_APPROVED)
		return issue_invoice(child.name, client=self._client(NOT_FOUND, CHILD_OK))

	def test_adjustment_is_sent_with_method_320(self):
		child = self._make_adjustment()
		self._issue(child)
		self.assertTrue(frappe.db.exists(LOG, {"fei_document": child.name, "method": 320}))

	def test_replacement_is_sent_with_method_350(self):
		child = frappe.get_doc(FEI, create_replacement(self.original.name, reason="Lập lại toàn bộ"))
		self._issue(child)
		self.assertTrue(frappe.db.exists(LOG, {"fei_document": child.name, "method": 350}))

	def test_payload_points_at_the_original_lookup_key(self):
		child = self._make_adjustment()
		self._issue(child)

		payload = sent_payload(self.transport.calls[-1]["body"])
		self.assertEqual(payload["originalInvoice"], "KS-GOC")
		self.assertEqual(payload["adjustmentType"], "1")

	def test_replacement_payload_uses_adjustment_type_four(self):
		child = frappe.get_doc(FEI, create_replacement(self.original.name, reason="Lập lại toàn bộ"))
		self._issue(child)
		self.assertEqual(sent_payload(self.transport.calls[-1]["body"])["adjustmentType"], "4")

	def test_the_original_is_marked_adjusted_once_the_child_is_issued(self):
		child = self._make_adjustment()
		self._issue(child)

		self.original.reload()
		self.assertEqual(self.original.status, STATUS_ADJUSTED)
		self.assertEqual(self.original.amended_from_fei, child.name)

	def test_the_original_is_marked_replaced_for_a_replacement(self):
		child = frappe.get_doc(FEI, create_replacement(self.original.name, reason="Lập lại toàn bộ"))
		self._issue(child)

		self.original.reload()
		self.assertEqual(self.original.status, STATUS_REPLACED)
		self.assertEqual(self.original.amended_from_fei, child.name)

	def test_the_original_is_untouched_when_the_child_fails(self):
		child = self._make_adjustment()
		frappe.db.set_value(FEI, child.name, "status", STATUS_CUSTOMER_APPROVED)
		issue_invoice(child.name, client=self._client(NOT_FOUND, envelope(0, "901|Da dieu chinh")))

		self.original.reload()
		self.assertEqual(self.original.status, STATUS_TAX_ACCEPTED)
		self.assertIsNone(self.original.amended_from_fei)

	def test_the_child_keeps_its_own_issued_details(self):
		child = self._make_adjustment()
		self._issue(child)

		child.reload()
		self.assertEqual(child.status, STATUS_ISSUED)
		self.assertEqual(child.fast_invoice_no, "3")
		self.assertEqual(child.fast_key_search, "KS-CHILD")


class TestAdjustmentValidation(LineageBase):
	def test_an_adjustment_may_carry_negative_lines(self):
		"""Điều chỉnh giảm truyền số âm (mục C3) — kiểm tra dữ liệu không được chặn."""
		from erpnext.einvoice.validation import validate_before_send

		child = self._make_adjustment()
		child.lines[0].qty = -10
		child.lines[0].amount = -1_000_000
		child.lines[0].tax_amount = -100_000
		child.amount = -1_000_000
		child.tax_amount = -100_000
		child.tax_amount_10 = -100_000
		child.total_amount = -1_100_000
		child.amount_in_words = "Âm một triệu một trăm nghìn đồng"

		result = validate_before_send(child)
		self.assertTrue(result.ok, [i.message for i in result.blocking])

	def test_sharing_the_delivery_note_with_the_original_is_allowed(self):
		"""Hóa đơn điều chỉnh cố ý dùng chung phiếu giao với hóa đơn gốc."""
		from erpnext.einvoice.validation import validate_before_send

		child = self._make_adjustment()
		blocked = [i.rule for i in validate_before_send(child).blocking]
		self.assertNotIn(15, blocked)
