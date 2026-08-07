# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nút 7 — PHÁT HÀNH HÓA ĐƠN (mục E5). Hành động không thể hoàn tác.

Bộ test này canh đúng những chỗ mà sai một lần là tiêu một số hóa đơn thật hoặc
đẻ ra hai hóa đơn cho một lần bán.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.einvoice.builder import create_from_delivery_note
from erpnext.einvoice.constants import (
	STATUS_CUSTOMER_APPROVED,
	STATUS_DRAFT,
	STATUS_ERROR,
	STATUS_ISSUED,
	STATUS_ISSUING,
	STATUS_NEEDS_RECONCILE,
	TAX_STATUS_PENDING,
)
from erpnext.einvoice.fast_client import FastClient
from erpnext.einvoice.issue import issue_invoice, parse_issue_result
from erpnext.einvoice.test_fast_client import FakeTransport, configure, envelope
from erpnext.einvoice.test_fixtures import make_delivery_note

FEI = "Fast EInvoice Document"
LOG = "Fast EInvoice Log"

# Fast không tìm thấy hóa đơn (mã 888) = chưa phát hành lần nào = an toàn để phát hành.
NOT_FOUND = envelope(0, "888|Khong tim thay")
ISSUE_OK = envelope(1, '{"invoiceNo":"2","pattern":"1/001","serial":"1C26TMY","signedDate":"20260807","keySearch":"KS-ABC-123"}')


class TestParseIssueResult(FrappeTestCase):
	def test_json_response_is_understood(self):
		result = parse_issue_result(
			'{"invoiceNo":"2","pattern":"1/001","serial":"1C26TMY","signedDate":"20260807","keySearch":"KS"}'
		)
		self.assertEqual(result["fast_invoice_no"], "2")
		self.assertEqual(result["fast_serial"], "1C26TMY")
		self.assertEqual(result["fast_pattern"], "1/001")
		self.assertEqual(result["fast_key_search"], "KS")
		self.assertEqual(str(result["fast_signed_date"]), "2026-08-07")

	def test_json_keys_are_matched_case_insensitively(self):
		result = parse_issue_result('{"InvoiceNo":"7","KeySearch":"KS7"}')
		self.assertEqual(result["fast_invoice_no"], "7")
		self.assertEqual(result["fast_key_search"], "KS7")

	def test_pipe_delimited_response_falls_back_to_the_documented_order(self):
		result = parse_issue_result("2|1/001|1C26TMY|20260807|KS-ABC")
		self.assertEqual(result["fast_invoice_no"], "2")
		self.assertEqual(result["fast_key_search"], "KS-ABC")

	def test_unrecognisable_response_keeps_the_raw_text(self):
		"""Không đoán được thì phải giữ nguyên văn để còn đối chiếu với Fast."""
		result = parse_issue_result("hoan toan la gi do")
		self.assertEqual(result["raw"], "hoan toan la gi do")


class IssueTestBase(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure(token="TOKEN-ABC", token_time=frappe.utils.now_datetime(), auto_download_pdf=0)
		self.dn = make_delivery_note()
		self.fei = frappe.get_doc(FEI, create_from_delivery_note(self.dn.name))
		self._approve()

	def tearDown(self):
		frappe.db.rollback()

	def _approve(self):
		frappe.db.set_value(FEI, self.fei.name, "status", STATUS_CUSTOMER_APPROVED)
		self.fei.reload()

	def _client(self, *responses):
		self.transport = FakeTransport(envelope(1, "still valid"), *responses)
		return FastClient(transport=self.transport)


class TestSuccessfulIssuance(IssueTestBase):
	def test_invoice_details_are_stored(self):
		issue_invoice(self.fei.name, client=self._client(NOT_FOUND, ISSUE_OK))

		self.fei.reload()
		self.assertEqual(self.fei.status, STATUS_ISSUED)
		self.assertEqual(self.fei.fast_invoice_no, "2")
		self.assertEqual(self.fei.fast_serial, "1C26TMY")
		self.assertEqual(self.fei.fast_pattern, "1/001")
		self.assertEqual(self.fei.fast_key_search, "KS-ABC-123")
		self.assertEqual(str(self.fei.fast_signed_date), "2026-08-07")

	def test_issuer_and_time_are_recorded(self):
		issue_invoice(self.fei.name, client=self._client(NOT_FOUND, ISSUE_OK))

		self.fei.reload()
		self.assertEqual(self.fei.issued_by, frappe.session.user)
		self.assertIsNotNone(self.fei.issued_time)

	def test_tax_status_starts_pending(self):
		issue_invoice(self.fei.name, client=self._client(NOT_FOUND, ISSUE_OK))
		self.fei.reload()
		self.assertEqual(self.fei.tax_status, TAX_STATUS_PENDING)

	def test_delivery_note_is_stamped_with_the_invoice_number(self):
		issue_invoice(self.fei.name, client=self._client(NOT_FOUND, ISSUE_OK))

		self.dn.reload()
		self.assertEqual(self.dn.fast_invoice_no, "2")
		self.assertEqual(self.dn.fast_key_search, "KS-ABC-123")
		self.assertEqual(self.dn.fast_einvoice_status, STATUS_ISSUED)

	def test_the_decisive_call_is_action_zero_method_310(self):
		issue_invoice(self.fei.name, client=self._client(NOT_FOUND, ISSUE_OK))

		log = frappe.get_doc(LOG, {"fei_document": self.fei.name, "method": 310, "action": 0})
		self.assertEqual(log.status, "Thành công")

	def test_a_370_precheck_runs_before_the_issue_call(self):
		"""Nguyên tắc A4: luôn truy vấn trước khi phát hành."""
		issue_invoice(self.fei.name, client=self._client(NOT_FOUND, ISSUE_OK))

		methods = [
			frappe.db.get_value(LOG, name, "method")
			for name in frappe.get_all(
				LOG, filters={"fei_document": self.fei.name}, order_by="creation asc", pluck="name"
			)
		]
		self.assertEqual(methods[:2], [370, 310])


class TestDuplicateProtection(IssueTestBase):
	def test_an_invoice_already_on_fast_is_never_issued_again(self):
		"""Lá chắn cho lỗi 835 — phát hành lặp là hai số hóa đơn cho một lần bán."""
		already = envelope(1, '{"invoiceNo":"9","serial":"1C26TMY","keySearch":"KS-CU"}')
		client = self._client(already)

		with self.assertRaises(frappe.ValidationError):
			issue_invoice(self.fei.name, client=client)

		# Chỉ có CheckKey + 370. Lệnh 310 không bao giờ được gửi.
		self.assertEqual(self.transport.operations, ["CheckKey", "ExcuteCommand"])

	def test_the_existing_invoice_details_are_pulled_back_in(self):
		already = envelope(1, '{"invoiceNo":"9","serial":"1C26TMY","keySearch":"KS-CU"}')
		with self.assertRaises(frappe.ValidationError):
			issue_invoice(self.fei.name, client=self._client(already))

		self.fei.reload()
		self.assertEqual(self.fei.fast_invoice_no, "9")
		self.assertEqual(self.fei.status, STATUS_ISSUED)

	def test_an_already_issued_record_is_refused_outright(self):
		frappe.db.set_value(FEI, self.fei.name, "status", STATUS_ISSUED)
		with self.assertRaises(frappe.ValidationError):
			issue_invoice(self.fei.name, client=self._client(NOT_FOUND, ISSUE_OK))

	def test_double_click_is_blocked_while_issuing(self):
		"""Nguyên tắc A4 quy tắc 4 — khóa chống bấm đúp."""
		frappe.db.set_value(FEI, self.fei.name, "status", STATUS_ISSUING)
		with self.assertRaises(frappe.ValidationError):
			issue_invoice(self.fei.name, client=self._client(NOT_FOUND, ISSUE_OK))


class TestFailurePaths(IssueTestBase):
	def test_business_error_lands_in_the_error_state(self):
		issue_invoice(self.fei.name, client=self._client(NOT_FOUND, envelope(0, "836|Thieu thong tin")))

		self.fei.reload()
		self.assertEqual(self.fei.status, STATUS_ERROR)
		self.assertEqual(self.fei.error_code, "836")
		self.assertIn("Thiếu thông tin bắt buộc", self.fei.error_message)
		self.assertFalse(self.fei.fast_invoice_no)

	def test_timeout_lands_in_needs_reconciliation_not_error(self):
		"""Nhánh 7c — đã gửi nhưng chưa biết kết quả, tuyệt đối không phát hành lại."""
		import requests

		client = self._client(NOT_FOUND, requests.Timeout("hết giờ"))
		issue_invoice(self.fei.name, client=client)

		self.fei.reload()
		self.assertEqual(self.fei.status, STATUS_NEEDS_RECONCILE)
		self.assertIn("370", self.fei.error_message)

	def test_timeout_never_retries_the_issue_command(self):
		import requests

		client = self._client(NOT_FOUND, requests.Timeout("hết giờ"))
		issue_invoice(self.fei.name, client=client)

		issue_calls = [c for c in self.transport.calls if "<method>310</method>" in c["body"]]
		self.assertEqual(len(issue_calls), 1)

	def test_a_failed_issue_is_still_fully_logged(self):
		issue_invoice(self.fei.name, client=self._client(NOT_FOUND, envelope(0, "836|Thieu thong tin")))

		log = frappe.get_doc(LOG, {"fei_document": self.fei.name, "method": 310, "action": 0})
		self.assertEqual(log.status, "Lỗi")
		self.assertEqual(log.error_code, "836")


class TestPreconditions(IssueTestBase):
	def test_customer_approval_is_required_when_configured(self):
		configure(require_customer_approval=1)
		frappe.db.set_value(FEI, self.fei.name, "status", STATUS_DRAFT)

		with self.assertRaises(frappe.ValidationError):
			issue_invoice(self.fei.name, client=self._client(NOT_FOUND, ISSUE_OK))

	def test_draft_may_be_issued_when_approval_is_not_required(self):
		configure(require_customer_approval=0, token="TOKEN-ABC", token_time=frappe.utils.now_datetime())
		frappe.db.set_value(FEI, self.fei.name, "status", STATUS_DRAFT)

		issue_invoice(self.fei.name, client=self._client(NOT_FOUND, ISSUE_OK))
		self.fei.reload()
		self.assertEqual(self.fei.status, STATUS_ISSUED)

	def test_blocking_validation_prevents_any_call(self):
		frappe.db.set_value(FEI, self.fei.name, "amount_in_words", "")
		client = self._client(NOT_FOUND, ISSUE_OK)

		with self.assertRaises(frappe.ValidationError):
			issue_invoice(self.fei.name, client=client)

		self.assertEqual(self.transport.calls, [])

	def test_only_the_chief_accountant_may_issue(self):
		"""Nút cấp 3 dành riêng cho kế toán trưởng."""
		from erpnext.einvoice.setup import ROLE_STAFF
		from erpnext.einvoice.test_einvoice_setup import _as, _ensure_user

		staff = _ensure_user("fei-staff-issue@example.com", ROLE_STAFF)
		client = self._client(NOT_FOUND, ISSUE_OK)

		with _as(staff), self.assertRaises(frappe.PermissionError):
			issue_invoice(self.fei.name, client=client)

	def test_disabled_integration_refuses(self):
		configure(enabled=0)
		with self.assertRaises(frappe.ValidationError):
			issue_invoice(self.fei.name, client=self._client(NOT_FOUND, ISSUE_OK))


class TestIssuanceLock(IssueTestBase):
	def test_lock_is_released_after_a_successful_issue(self):
		"""Khóa không nhả là hóa đơn thứ hai trở đi không phát hành được nữa."""
		from erpnext.einvoice.issue import _issuance_lock

		issue_invoice(self.fei.name, client=self._client(NOT_FOUND, ISSUE_OK))

		lock = _issuance_lock(self.fei.name)
		with lock:
			self.assertTrue(lock.acquired)

	def test_lock_is_released_even_when_issuing_fails(self):
		from erpnext.einvoice.issue import _issuance_lock

		issue_invoice(self.fei.name, client=self._client(NOT_FOUND, envelope(0, "836|Thieu")))

		lock = _issuance_lock(self.fei.name)
		with lock:
			self.assertTrue(lock.acquired)

	def test_lock_is_released_when_the_duplicate_check_aborts(self):
		from erpnext.einvoice.issue import _issuance_lock

		already = envelope(1, '{"invoiceNo":"9","keySearch":"KS-CU"}')
		with self.assertRaises(frappe.ValidationError):
			issue_invoice(self.fei.name, client=self._client(already))

		lock = _issuance_lock(self.fei.name)
		with lock:
			self.assertTrue(lock.acquired)
