# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tầng giao tiếp SOAP với Fast — Giai đoạn 1 của lộ trình.

Không test nào chạm mạng: transport được tiêm vào client, mọi phản hồi là giả.
"""

import base64
import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from erpnext.einvoice.fast_client import (
	FastClient,
	FastTimeout,
	decode_message,
	encode_payload,
	parse_response,
)

SETTINGS = "Fast EInvoice Settings"


def result_xml(text):
	"""Phản hồi ``<…Result>`` với nội dung nguyên văn (không bị blank như envelope)."""
	return (
		'<?xml version="1.0" encoding="utf-8"?>'
		'<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
		'<soap:Body><ExcuteCommandResponse xmlns="http://tempuri.org/">'
		f"<ExcuteCommandResult>{text}</ExcuteCommandResult>"
		"</ExcuteCommandResponse></soap:Body></soap:Envelope>"
	)


def envelope(success, message):
	"""Phản hồi SOAP giả theo đúng hình dạng WSDL của Fast: ``<…Result>chuỗi</…>``.

	Tham số ``success`` giữ lại cho các test đang có: khi ``success`` là 0 nhưng
	``message`` không mở đầu bằng mã lỗi (ví dụ token bị từ chối), Fast trả kết
	quả **rỗng**, nên helper cũng trả rỗng để phản ánh đúng thực tế.
	"""
	from erpnext.einvoice.errors import ERROR_CATALOGUE

	looks_like_error = message and message.split("|", 1)[0].strip() in ERROR_CATALOGUE
	if not success and not looks_like_error:
		message = ""  # Fast từ chối = <…Result> rỗng
	return (
		'<?xml version="1.0" encoding="utf-8"?>'
		'<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
		'<soap:Body><ExcuteCommandResponse xmlns="http://tempuri.org/">'
		f"<ExcuteCommandResult>{message}</ExcuteCommandResult>"
		"</ExcuteCommandResponse></soap:Body></soap:Envelope>"
	)


class FakeTransport:
	"""Ghi lại lời gọi và trả phản hồi đã dựng sẵn."""

	def __init__(self, *responses):
		self.responses = list(responses)
		self.calls = []

	def __call__(self, url, soap_action, body, timeout=None):
		self.calls.append({"url": url, "soap_action": soap_action, "body": body})
		if not self.responses:
			raise AssertionError("Transport bị gọi nhiều lần hơn số phản hồi đã dựng")
		nxt = self.responses.pop(0)
		if isinstance(nxt, Exception):
			raise nxt
		return nxt

	@property
	def operations(self):
		return [c["soap_action"].rsplit("/", 1)[-1].strip('"') for c in self.calls]


def configure(**values):
	"""Đặt cấu hình về một trạng thái đã biết.

	`Fast EInvoice Settings` là Single DocType — giá trị đang lưu trên site rò
	thẳng vào test. Vì vậy **mọi cờ hành vi đều đặt tường minh ở đây**, kể cả các
	cờ trông như không liên quan; test nào cần khác thì truyền kwarg.
	"""
	doc = frappe.get_single(SETTINGS)
	doc.update(
		{
			"enabled": 1,
			"is_test_mode": 1,
			"require_customer_approval": 1,
			"auto_download_pdf": 1,
			"auto_poll_tax_status": 1,
			"api_url": "https://tportal.fast.com.vn:9000/AppService/FastEInvoice.PortalService.asmx",
			"client_code": "008254",
			"proxy_code": "006384",
			"unit_code": "CTY",
			"voucher_book": "1C26TAA",
			"api_user": "erp.miyano",
			"api_password": "s3cret",
			**values,
		}
	)
	doc.flags.ignore_permissions = True
	doc.save()
	return doc


class TestPayloadEncoding(FrappeTestCase):
	def test_payload_is_utf8_json_in_base64(self):
		encoded = encode_payload({"buyer": "Bệnh viện Đa khoa X"})
		self.assertEqual(
			json.loads(base64.b64decode(encoded).decode("utf-8"))["buyer"], "Bệnh viện Đa khoa X"
		)

	def test_payload_keeps_vietnamese_readable_not_escaped(self):
		"""ensure_ascii sẽ biến tiếng Việt thành \\uXXXX — Fast không đọc được."""
		raw = base64.b64decode(encode_payload({"x": "Bơm kim tiêm"})).decode("utf-8")
		self.assertIn("Bơm kim tiêm", raw)

	def test_numbers_stay_numbers_in_the_payload(self):
		"""Phần I: số gửi dạng number, không phải chuỗi."""
		raw = base64.b64decode(encode_payload({"amount": 10000000, "rate": 1.0})).decode("utf-8")
		self.assertIn('"amount": 10000000', raw)
		self.assertNotIn('"10000000"', raw)

	def test_decode_message_returns_bytes_for_pdf_content(self):
		self.assertEqual(decode_message(base64.b64encode(b"%PDF-1.4 x").decode()), b"%PDF-1.4 x")


class TestResponseParsing(FrappeTestCase):
	def test_success_response_is_parsed(self):
		result = parse_response(envelope(1, "2|1C26TMY|ABCKEY"))
		self.assertTrue(result.success)
		self.assertEqual(result.message, "2|1C26TMY|ABCKEY")

	def test_failure_response_carries_the_error_code(self):
		result = parse_response(envelope(0, "835|Hóa đơn đã tồn tại"))
		self.assertFalse(result.success)
		self.assertEqual(result.error_code, "835")

	def test_xml_entities_in_the_message_are_decoded(self):
		result = parse_response(envelope(0, "812|Tên hàng A &amp; B quá dài"))
		self.assertIn("A & B", result.message)

	def test_unparseable_response_is_a_failure_not_a_crash(self):
		result = parse_response("<html>502 Bad Gateway</html>")
		self.assertFalse(result.success)
		self.assertTrue(result.raw)


class TestEnvelopeBuilding(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure()

	def tearDown(self):
		frappe.db.rollback()

	def test_special_characters_are_escaped_into_the_envelope(self):
		"""Phần I: escape & < > trước khi nhúng vào XML envelope."""
		client = FastClient(transport=FakeTransport(envelope(1, "ok")))
		body = client.build_envelope("ExcuteCommand", {"data": "A & B <tag>"})
		self.assertIn("A &amp; B &lt;tag&gt;", body)
		self.assertNotIn("A & B <tag>", body)

	def test_envelope_is_well_formed_xml(self):
		import xml.etree.ElementTree as ET

		client = FastClient(transport=FakeTransport(envelope(1, "ok")))
		ET.fromstring(client.build_envelope("ExcuteCommand", {"data": "A & B"}))


class TestTokenLifecycle(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure(token="", token_time=None)

	def tearDown(self):
		frappe.db.rollback()

	def test_first_call_fetches_a_token_with_get_key(self):
		transport = FakeTransport(envelope(1, "TOKEN-ABC"))
		client = FastClient(transport=transport)

		self.assertEqual(client.token(), "TOKEN-ABC")
		self.assertEqual(transport.operations, ["GetKey"])

	def test_token_is_persisted_so_it_survives_the_request(self):
		client = FastClient(transport=FakeTransport(envelope(1, "TOKEN-ABC")))
		client.token()

		frappe.clear_document_cache(SETTINGS)
		self.assertEqual(frappe.get_single(SETTINGS).token, "TOKEN-ABC")

	def test_fresh_token_is_verified_with_check_key_then_reused(self):
		configure(token="TOKEN-OLD", token_time=now_datetime())
		transport = FakeTransport(envelope(1, "still valid"))
		client = FastClient(transport=transport)

		self.assertEqual(client.token(), "TOKEN-OLD")
		self.assertEqual(transport.operations, ["CheckKey"])

	def test_expired_token_goes_straight_to_get_key(self):
		"""Token hết hiệu lực 24h — hỏi CheckKey nữa chỉ tốn một vòng mạng."""
		configure(token="TOKEN-OLD", token_time=add_to_date(now_datetime(), hours=-25))
		transport = FakeTransport(envelope(1, "TOKEN-NEW"))
		client = FastClient(transport=transport)

		self.assertEqual(client.token(), "TOKEN-NEW")
		self.assertEqual(transport.operations, ["GetKey"])

	def test_token_rejected_by_check_key_is_replaced(self):
		configure(token="TOKEN-DEAD", token_time=now_datetime())
		transport = FakeTransport(envelope(0, "token không hợp lệ"), envelope(1, "TOKEN-NEW"))
		client = FastClient(transport=transport)

		self.assertEqual(client.token(), "TOKEN-NEW")
		self.assertEqual(transport.operations, ["CheckKey", "GetKey"])

	def test_failed_get_key_raises_with_the_fast_message(self):
		client = FastClient(transport=FakeTransport(envelope(0, "802|Tài khoản không có quyền")))
		with self.assertRaises(frappe.ValidationError):
			client.token()


class TestExcuteCommand(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure(token="TOKEN-ABC", token_time=now_datetime())

	def tearDown(self):
		frappe.db.rollback()

	def test_command_sends_action_method_and_base64_data(self):
		transport = FakeTransport(envelope(1, "still valid"), envelope(1, "2|1C26TMY|KEY"))
		client = FastClient(transport=transport)

		result = client.excute_command(action=600, method=310, data={"voucherBook": "1C26TAA"})

		self.assertTrue(result.success)
		body = transport.calls[-1]["body"]
		self.assertIn("<action>600</action>", body)
		self.assertIn("<method>310</method>", body)
		self.assertIn(encode_payload({"voucherBook": "1C26TAA"}), body)

	def test_command_carries_the_token_as_checksum(self):
		transport = FakeTransport(envelope(1, "still valid"), envelope(1, "ok"))
		client = FastClient(transport=transport)
		client.excute_command(action=0, method=310, data={})

		self.assertIn("<checkSum>TOKEN-ABC</checkSum>", transport.calls[-1]["body"])

	def test_command_identifies_the_company_and_unit(self):
		transport = FakeTransport(envelope(1, "still valid"), envelope(1, "ok"))
		client = FastClient(transport=transport)
		client.excute_command(action=0, method=310, data={})

		body = transport.calls[-1]["body"]
		self.assertIn("<clientCode>008254</clientCode>", body)
		self.assertIn("<proxyCode>006384</proxyCode>", body)
		self.assertIn("<unitCode>CTY</unitCode>", body)

	def test_expired_token_mid_call_is_refreshed_and_the_call_retried_once(self):
		"""Kịch bản 8 của Giai đoạn 6: người dùng không được thấy lỗi token."""
		transport = FakeTransport(
			envelope(1, "still valid"),  # CheckKey
			result_xml("401|Token hết hiệu lực"),  # ExcuteCommand lần 1 — token chết
			envelope(1, "TOKEN-NEW"),  # GetKey
			envelope(1, "2|1C26TMY|KEY"),  # ExcuteCommand lần 2
		)
		client = FastClient(transport=transport)

		result = client.excute_command(action=0, method=310, data={})

		self.assertTrue(result.success)
		self.assertEqual(transport.operations, ["CheckKey", "ExcuteCommand", "GetKey", "ExcuteCommand"])

	def test_a_real_error_is_not_retried(self):
		"""Lỗi nghiệp vụ mà thử lại là nguy cơ phát hành hai lần."""
		transport = FakeTransport(
			envelope(1, "still valid"),
			envelope(0, "836|Thiếu thông tin người mua"),
		)
		client = FastClient(transport=transport)

		result = client.excute_command(action=0, method=310, data={})

		self.assertFalse(result.success)
		self.assertEqual(result.error_code, "836")
		self.assertEqual(transport.operations, ["CheckKey", "ExcuteCommand"])

	def test_network_timeout_surfaces_as_fast_timeout(self):
		"""Nhánh 7c: timeout phải phân biệt được với lỗi nghiệp vụ."""
		import requests

		transport = FakeTransport(envelope(1, "still valid"), requests.Timeout("hết giờ"))
		client = FastClient(transport=transport)

		with self.assertRaises(FastTimeout):
			client.excute_command(action=0, method=310, data={})

	def test_duration_is_measured_for_the_log(self):
		transport = FakeTransport(envelope(1, "still valid"), envelope(1, "ok"))
		client = FastClient(transport=transport)
		result = client.excute_command(action=0, method=310, data={})

		self.assertIsInstance(result.duration_ms, int)
		self.assertGreaterEqual(result.duration_ms, 0)


def soap_fault(faultstring, faultcode="soap:Server"):
	"""Fast trả SOAP Fault khi lỗi ở tầng dịch vụ chứ không phải lỗi nghiệp vụ."""
	return (
		'<?xml version="1.0" encoding="utf-8"?>'
		'<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
		f"<soap:Body><soap:Fault><faultcode>{faultcode}</faultcode>"
		f"<faultstring>{faultstring}</faultstring>"
		"</soap:Fault></soap:Body></soap:Envelope>"
	)


class TestDiagnosableFailures(FrappeTestCase):
	"""Người dùng phải đọc được LÝ DO, không phải "không rõ lý do"."""

	def setUp(self):
		frappe.db.rollback()
		configure(token="", token_time=None)

	def tearDown(self):
		frappe.db.rollback()

	def test_soap_fault_is_surfaced_as_its_faultstring(self):
		result = parse_response(soap_fault("Server was unable to process request. Invalid user."))
		self.assertFalse(result.success)
		self.assertIn("Invalid user", result.message)

	def test_a_response_without_success_or_fault_still_explains_itself(self):
		"""Không hiểu được phản hồi thì ít nhất phải cho thấy Fast đã trả về cái gì."""
		result = parse_response("<root><Something>khac</Something></root>")
		self.assertFalse(result.success)
		self.assertTrue(result.message.strip(), "Phản hồi lạ mà không có lời giải thích nào")

	def test_bad_credentials_report_the_reason_not_a_shrug(self):
		client = FastClient(transport=FakeTransport(soap_fault("Sai tên đăng nhập hoặc mật khẩu")))

		with self.assertRaises(frappe.ValidationError) as caught:
			client.token()

		message = str(caught.exception)
		self.assertIn("Sai tên đăng nhập", message)
		self.assertNotIn("không rõ lý do", message)

	def test_http_error_from_fast_is_not_a_raw_stack_trace(self):
		import requests

		response = requests.Response()
		response.status_code = 500
		response._content = b"<html>Internal Server Error</html>"
		transport = FakeTransport(requests.HTTPError("500 Server Error", response=response))

		with self.assertRaises(FastTimeout) as caught:
			FastClient(transport=transport).token()
		self.assertIn("500", str(caught.exception))

	def test_an_auth_rejection_is_a_definite_failure_not_an_unknown_outcome(self):
		"""401/403 chắc chắn chưa tới nghiệp vụ — không được coi là "cần đối soát"."""
		import requests

		response = requests.Response()
		response.status_code = 401
		transport = FakeTransport(requests.HTTPError("401 Unauthorized", response=response))

		client = FastClient(transport=transport)
		with self.assertRaises(frappe.ValidationError) as caught:
			client.token()
		self.assertNotIsInstance(caught.exception, FastTimeout)
		self.assertIn("401", str(caught.exception))

	def test_unreachable_host_says_so_plainly(self):
		import requests

		transport = FakeTransport(requests.ConnectionError("Name or service not known"))
		with self.assertRaises(FastTimeout) as caught:
			FastClient(transport=transport).token()
		self.assertIn("Fast", str(caught.exception))
