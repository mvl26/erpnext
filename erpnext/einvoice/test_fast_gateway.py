# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Trình tự A1 (ghi log trước+sau khi gọi) và ánh xạ mã lỗi Phần G."""

import base64

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.einvoice.errors import (
	describe_error,
	is_certificate_error,
	is_duplicate_invoice_error,
	is_retryable_error,
)
from erpnext.einvoice.fast_client import FastClient, FastTimeout
from erpnext.einvoice.gateway import call_fast
from erpnext.einvoice.test_fast_client import FakeTransport, configure, envelope
from erpnext.einvoice.test_fast_document import make_fei

LOG = "Fast EInvoice Log"


class TestErrorCatalogue(FrappeTestCase):
	def test_known_code_is_explained_in_vietnamese(self):
		described = describe_error("835")
		self.assertIn("đã được phát hành trước đó", described.message)
		self.assertTrue(described.hint)

	def test_codes_sharing_a_row_share_an_explanation(self):
		"""500/501/502 cùng là chứng thư số HSM chưa sẵn sàng."""
		for code in ("500", "501", "502"):
			self.assertIn("HSM", describe_error(code).message)

	def test_unknown_code_still_reports_something_actionable(self):
		described = describe_error("4242")
		self.assertIn("4242", described.message)

	def test_certificate_errors_are_recognised_as_system_wide_blockers(self):
		self.assertTrue(is_certificate_error("501"))
		self.assertFalse(is_certificate_error("836"))

	def test_duplicate_invoice_errors_are_recognised(self):
		"""809/835 nghĩa là đã phát hành rồi — tuyệt đối không phát hành lại."""
		self.assertTrue(is_duplicate_invoice_error("809"))
		self.assertTrue(is_duplicate_invoice_error("835"))
		self.assertFalse(is_duplicate_invoice_error("152"))

	def test_only_concurrency_clash_is_retryable(self):
		self.assertTrue(is_retryable_error("1002"))
		self.assertFalse(is_retryable_error("836"))
		self.assertFalse(is_retryable_error("835"))

	def test_line_length_errors_point_at_the_data(self):
		self.assertIn("quá dài", describe_error("812").message)


class TestGatewayLogging(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure(token="TOKEN-ABC", token_time=frappe.utils.now_datetime())
		self.fei = make_fei()
		self.fei.insert()

	def tearDown(self):
		frappe.db.rollback()

	def _client(self, *responses):
		"""Token đang tươi nên client luôn hỏi CheckKey trước — dựng sẵn phản hồi đó."""
		return FastClient(transport=FakeTransport(envelope(1, "still valid"), *responses))

	def test_log_exists_before_the_api_call_is_made(self):
		"""Nguyên tắc A1 bước ①③: nếu server sập giữa chừng vẫn còn bằng chứng đã gửi."""
		seen = {}

		def spy(url, soap_action, body, timeout=None):
			seen["status"] = frappe.db.get_value(
				LOG, {"fei_document": self.fei.name, "method": 310}, "status"
			)
			return envelope(1, "2|1C26TMY|KEY")

		client = FastClient(transport=spy)
		call_fast(self.fei, action=0, method=310, data={}, purpose="Phát hành hóa đơn", client=client)

		self.assertEqual(seen["status"], "Đang gửi")

	def test_successful_call_closes_the_log(self):
		client = self._client(envelope(1, "2|1C26TMY|KEY"))
		response = call_fast(
			self.fei, action=0, method=310, data={}, purpose="Phát hành hóa đơn", client=client
		)

		log = frappe.get_doc(LOG, {"fei_document": self.fei.name})
		self.assertTrue(response.success)
		self.assertEqual(log.status, "Thành công")
		self.assertEqual(log.success, 1)
		self.assertIn("1C26TMY", log.response_raw)

	def test_business_error_is_logged_with_the_vietnamese_message(self):
		client = self._client(envelope(0, "836|Loi so lieu"))
		response = call_fast(
			self.fei, action=0, method=310, data={}, purpose="Phát hành hóa đơn", client=client
		)

		log = frappe.get_doc(LOG, {"fei_document": self.fei.name})
		self.assertFalse(response.success)
		self.assertEqual(log.status, "Lỗi")
		self.assertEqual(log.error_code, "836")
		self.assertIn("Thiếu thông tin bắt buộc", log.error_message)

	def test_timeout_is_logged_before_the_exception_escapes(self):
		"""Kể cả khi timeout vẫn phải có dấu vết — đây là ca nguy hiểm nhất."""
		import requests

		client = self._client(requests.Timeout("hết giờ"))

		with self.assertRaises(FastTimeout):
			call_fast(
				self.fei, action=0, method=310, data={}, purpose="Phát hành hóa đơn", client=client
			)

		log = frappe.get_doc(LOG, {"fei_document": self.fei.name})
		self.assertEqual(log.status, "Timeout")
		self.assertIn("370", log.error_message)

	def test_request_log_hides_the_password_and_token(self):
		client = self._client(envelope(1, "ok"))
		call_fast(self.fei, action=0, method=310, data={"x": 1}, purpose="Phát hành", client=client)

		log = frappe.get_doc(LOG, {"fei_document": self.fei.name})
		self.assertNotIn("TOKEN-ABC", log.request_json)
		self.assertNotIn("s3cret", log.request_json)
		self.assertIn("***", log.request_json)

	def test_request_log_keeps_the_payload_readable_not_base64(self):
		"""Đặc tả C4: JSON dạng đọc được, không phải base64."""
		client = self._client(envelope(1, "ok"))
		call_fast(
			self.fei,
			action=0,
			method=310,
			data={"voucherBook": "1C26TAA"},
			purpose="Phát hành",
			client=client,
		)

		log = frappe.get_doc(LOG, {"fei_document": self.fei.name})
		self.assertIn("1C26TAA", log.request_json)

	def test_pdf_response_records_only_its_size(self):
		"""Nhồi cả chuỗi base64 PDF vào log làm phình bảng vô ích."""
		pdf = base64.b64encode(b"%PDF-1.4" + b"x" * 5000).decode()
		client = self._client(envelope(1, pdf))

		call_fast(self.fei, action=0, method=380, data={}, purpose="Tải PDF", client=client)

		log = frappe.get_doc(LOG, {"fei_document": self.fei.name})
		self.assertNotIn(pdf, log.response_raw)
		self.assertIn(str(len(pdf)), log.response_raw)

	def test_log_records_the_call_envelope_and_purpose(self):
		client = self._client(envelope(1, "ok"))
		call_fast(self.fei, action=600, method=310, data={}, purpose="Xem PDF nháp", client=client)

		log = frappe.get_doc(LOG, {"fei_document": self.fei.name})
		self.assertEqual(log.action, 600)
		self.assertEqual(log.method, 310)
		self.assertEqual(log.purpose, "Xem PDF nháp")
		self.assertEqual(log.operation, "ExcuteCommand")
		self.assertGreaterEqual(log.duration_ms, 0)

	def test_processing_status_is_set_before_the_call(self):
		"""Bước ② của A1: chứng từ phải mang trạng thái đang xử lý trước khi bắn đi."""
		seen = {}

		def spy(url, soap_action, body, timeout=None):
			seen["status"] = frappe.db.get_value("Fast EInvoice Document", self.fei.name, "status")
			return envelope(1, "ok")

		call_fast(
			self.fei,
			action=0,
			method=310,
			data={},
			purpose="Phát hành hóa đơn",
			processing_status="05 - Đang phát hành",
			client=FastClient(transport=spy),
		)

		self.assertEqual(seen["status"], "05 - Đang phát hành")
