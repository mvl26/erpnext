# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tầng giao tiếp SOAP với Fast — Giai đoạn 1 của lộ trình.

Không test nào chạm mạng: transport được tiêm vào client, mọi phản hồi là giả.
"""

import base64
import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from erpnext.einvoice.fast_client import (
	FastClient,
	FastTimeout,
	decode_message,
	encode_payload,
	parse_response,
)

SETTINGS = "Fast EInvoice Settings"


def _soap(op, inner):
	return (
		'<?xml version="1.0" encoding="utf-8"?>'
		'<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
		f'<soap:Body><{op}Response xmlns="http://tempuri.org/">'
		f"<{op}Result>{inner}</{op}Result>"
		f"</{op}Response></soap:Body></soap:Envelope>"
	)


def command_result(inner):
	"""Phản hồi ExcuteCommand nguyên văn (đã là chuỗi JSON envelope hoặc bất kỳ).

	Chỉ escape ``&<>`` — đúng những gì ``parse_response`` sẽ unescape lại; escape
	cả dấu nháy sẽ làm hỏng chuỗi JSON bên trong.
	"""
	from xml.sax.saxutils import escape as xml_escape

	return _soap("ExcuteCommand", xml_escape(inner or ""))


def envelope(success, message):
	"""Phản hồi ExcuteCommand giả theo đúng hình dạng Fast: JSON ``{Success,Code,Message}``.

	``message`` mở đầu bằng mã lỗi (``"835|…"``) thì lấy làm ``Code``; nếu không
	thì Code = 0. Đây là dạng phản hồi của mọi lệnh nghiệp vụ (phát hành, PDF…).
	"""
	from erpnext.einvoice.errors import ERROR_CATALOGUE

	code = 0
	if not success:
		head = (message or "").split("|", 1)[0].strip()
		code = int(head) if head in ERROR_CATALOGUE or head.isdigit() else 1
	payload = json.dumps({"Success": 1 if success else 0, "Code": code, "Message": message or ""})
	return command_result(payload)


def checkkey_ok():
	"""CheckKey xác nhận token còn hiệu lực."""
	return _soap("CheckKey", "Ok")


def checkkey_salt(salt="9dd8e7e4"):
	"""CheckKey báo cần cấp token mới, kèm salt."""
	return _soap("CheckKey", f"Ok:{salt}")


def getkey_token(token, salt="9dd8e7e4"):
	"""GetKey trả ``token,salt``."""
	return _soap("GetKey", f"{token},{salt}")


def auth_empty(op="GetKey"):
	"""Fast từ chối xác thực = ``<…Result>`` rỗng."""
	return _soap(op, "")


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
			# Giá trị giả, cố ý. Test không bao giờ chạm mạng — transport được tiêm
			# vào `FastClient` — nên không cần thông tin đăng nhập thật, và một mật
			# khẩu thật nằm ở đây là một mật khẩu thật nằm trong lịch sử git.
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
	def test_command_success_carries_the_message(self):
		result = parse_response(envelope(1, "2|1C26TMY|ABCKEY"))
		self.assertTrue(result.success)
		self.assertEqual(result.message, "2|1C26TMY|ABCKEY")

	def test_command_failure_carries_the_code_from_the_envelope(self):
		result = parse_response(envelope(0, "835|Hóa đơn đã tồn tại"))
		self.assertFalse(result.success)
		self.assertEqual(result.error_code, "835")

	def test_success_message_can_be_a_json_array_of_invoices(self):
		"""Phát hành HSM trả Message là mảng JSON các hóa đơn."""
		result = parse_response(envelope(1, '[{"invoiceNo":"2","keySearch":"KS"}]'))
		self.assertTrue(result.success)
		self.assertIn('"invoiceNo"', result.message)

	def test_special_characters_in_the_message_survive(self):
		result = parse_response(envelope(0, "812|Tên hàng A & B <x> quá dài"))
		self.assertIn("A & B <x>", result.message)

	def test_token_result_is_a_plain_string(self):
		result = parse_response(getkey_token("TOKENABC", "9dd8e7e4"))
		self.assertTrue(result.success)
		self.assertEqual(result.message, "TOKENABC,9dd8e7e4")

	def test_empty_result_is_a_rejection(self):
		result = parse_response(auth_empty("GetKey"))
		self.assertFalse(result.success)

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
	"""Handshake CheckKey → (salt) → GetKey đúng tài liệu API Fast."""

	def setUp(self):
		frappe.db.rollback()
		configure(token="", token_time=None)

	def tearDown(self):
		frappe.db.rollback()

	def test_first_call_does_checkkey_then_getkey(self):
		"""Lần đầu chưa có token: CheckKey trả salt, rồi GetKey cấp token."""
		transport = FakeTransport(checkkey_salt(), getkey_token("TOKENABC"))
		client = FastClient(transport=transport)

		self.assertEqual(client.token(), "TOKENABC")
		self.assertEqual(transport.operations, ["CheckKey", "GetKey"])

	def test_token_is_persisted_so_it_survives_the_request(self):
		client = FastClient(transport=FakeTransport(checkkey_salt(), getkey_token("TOKENABC")))
		client.token()

		frappe.clear_document_cache(SETTINGS)
		self.assertEqual(frappe.get_single(SETTINGS).token, "TOKENABC")

	def test_getkey_hash_is_built_from_the_salt(self):
		"""hash = md5(md5(password)+salt) + chr(254) + salt."""
		import hashlib

		configure(api_password="123abc456")
		transport = FakeTransport(checkkey_salt("9dd8e7e4"), getkey_token("TOKENABC"))
		FastClient(transport=transport).token()

		inner = hashlib.md5(b"123abc456").hexdigest()
		expected = hashlib.md5((inner + "9dd8e7e4").encode()).hexdigest() + chr(254) + "9dd8e7e4"
		self.assertIn(f"<hash>{expected}</hash>", transport.calls[-1]["body"])

	def test_valid_stored_token_is_reused_after_checkkey(self):
		configure(token="TOKEN-OLD", token_time=now_datetime())
		transport = FakeTransport(checkkey_ok())
		client = FastClient(transport=transport)

		self.assertEqual(client.token(), "TOKEN-OLD")
		self.assertEqual(transport.operations, ["CheckKey"])

	def test_expired_token_is_replaced_via_the_salt(self):
		configure(token="TOKEN-DEAD", token_time=now_datetime())
		transport = FakeTransport(checkkey_salt(), getkey_token("TOKEN-NEW"))
		client = FastClient(transport=transport)

		self.assertEqual(client.token(), "TOKEN-NEW")
		self.assertEqual(transport.operations, ["CheckKey", "GetKey"])

	def test_wrong_company_params_raise_a_clear_error(self):
		"""CheckKey trả rỗng = sai thông tin doanh nghiệp/user."""
		client = FastClient(transport=FakeTransport(auth_empty("CheckKey")))
		with self.assertRaises(frappe.ValidationError):
			client.token()

	def test_rejected_getkey_raises_with_the_account_hint(self):
		transport = FakeTransport(checkkey_salt(), auth_empty("GetKey"))
		client = FastClient(transport=transport)
		with self.assertRaises(frappe.ValidationError) as caught:
			client.token()
		self.assertIn("phân quyền phát hành", str(caught.exception))


class TestExcuteCommand(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure(token="TOKEN-ABC", token_time=now_datetime())

	def tearDown(self):
		frappe.db.rollback()

	def test_command_sends_action_method_and_base64_data(self):
		transport = FakeTransport(checkkey_ok(), envelope(1, "2|1C26TMY|KEY"))
		client = FastClient(transport=transport)

		result = client.excute_command(action=600, method=310, data={"voucherBook": "1C26TAA"})

		self.assertTrue(result.success)
		body = transport.calls[-1]["body"]
		self.assertIn("<action>600</action>", body)
		self.assertIn("<method>310</method>", body)
		self.assertIn(encode_payload({"voucherBook": "1C26TAA"}), body)

	def test_command_carries_the_token_as_checksum(self):
		transport = FakeTransport(checkkey_ok(), envelope(1, "ok"))
		client = FastClient(transport=transport)
		client.excute_command(action=0, method=310, data={})

		self.assertIn("<checkSum>TOKEN-ABC</checkSum>", transport.calls[-1]["body"])

	def test_command_identifies_the_company_and_unit(self):
		transport = FakeTransport(checkkey_ok(), envelope(1, "ok"))
		client = FastClient(transport=transport)
		client.excute_command(action=0, method=310, data={})

		body = transport.calls[-1]["body"]
		self.assertIn("<clientCode>008254</clientCode>", body)
		self.assertIn("<proxyCode>006384</proxyCode>", body)
		self.assertIn("<unitCode>CTY</unitCode>", body)

	def test_expired_token_mid_call_is_refreshed_and_the_call_retried_once(self):
		"""Kịch bản 8 của Giai đoạn 6: người dùng không được thấy lỗi token.

		Token chết giữa lệnh → lấy token mới (CheckKey lấy salt rồi GetKey) rồi thử
		lại đúng một lần.
		"""
		transport = FakeTransport(
			checkkey_ok(),  # CheckKey — token đang dùng còn "hiệu lực"
			envelope(0, "Token hết hiệu lực, vui lòng đăng nhập lại"),  # ExcuteCommand lần 1
			checkkey_salt(),  # CheckKey khi làm mới → salt
			getkey_token("TOKEN-NEW"),  # GetKey
			envelope(1, "2|1C26TMY|KEY"),  # ExcuteCommand lần 2
		)
		client = FastClient(transport=transport)

		result = client.excute_command(action=0, method=310, data={})

		self.assertTrue(result.success)
		self.assertEqual(
			transport.operations,
			["CheckKey", "ExcuteCommand", "CheckKey", "GetKey", "ExcuteCommand"],
		)

	def test_a_real_error_is_not_retried(self):
		"""Lỗi nghiệp vụ mà thử lại là nguy cơ phát hành hai lần."""
		transport = FakeTransport(
			checkkey_ok(),
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

		transport = FakeTransport(checkkey_ok(), requests.Timeout("hết giờ"))
		client = FastClient(transport=transport)

		with self.assertRaises(FastTimeout):
			client.excute_command(action=0, method=310, data={})

	def test_duration_is_measured_for_the_log(self):
		transport = FakeTransport(checkkey_ok(), envelope(1, "ok"))
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
