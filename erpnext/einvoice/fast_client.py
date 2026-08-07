# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tầng giao tiếp SOAP với cổng dịch vụ Fast e-Invoice (portal service v2.5).

Đây là **lớp duy nhất được phép gọi mạng**. Mọi tầng trên chỉ thấy
``FastResponse``. Chế độ vận hành: **không mã hóa RSA** — payload chỉ base64,
không ký/mã hóa thêm.

⚠️ CẦN ĐỐI CHIẾU VỚI WSDL THẬT TRƯỚC KHI GO-LIVE ⚠️
Đặc tả v2.0 nêu tên ba lời gọi (``CheckKey``, ``GetKey``, ``ExcuteCommand``) và
bốn tham số của ``ExcuteCommand`` (``action``, ``method``, ``data``,
``checkSum``) nhưng **không kèm WSDL**, và ``fast_client.py`` mà Giai đoạn 2 nói
"đã có sẵn" không tồn tại trên bench. Vì vậy các tên tham số còn lại
(``clientCode``/``proxyCode``/``unitCode``/``userName``/``password``) và
namespace ``http://tempuri.org/`` là **suy ra**, chưa xác nhận với Fast.

Chúng được gom hết vào ``OPERATIONS`` ngay dưới đây: sửa đúng một chỗ đó là
khớp lại được với WSDL thật, không phải sờ vào logic nghiệp vụ.
"""

import base64
import json
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from xml.sax.saxutils import escape, unescape

import frappe
import requests
from frappe import _
from frappe.utils import get_datetime, now_datetime, time_diff_in_hours

from erpnext.einvoice.fast_settings import get_settings

# Namespace của web service ASMX — suy ra, cần xác nhận với WSDL của Fast.
FAST_NAMESPACE = "http://tempuri.org/"

# Token Fast có hiệu lực 24h (mục C1 #10).
TOKEN_TTL_HOURS = 24

# Timeout mạng. Hóa đơn 300 dòng ký HSM có thể lâu, nên để rộng.
REQUEST_TIMEOUT_SECONDS = 120

# Tham số của từng lời gọi, theo đúng thứ tự SOAP mong đợi.
OPERATIONS = {
	"CheckKey": ("clientCode", "userName", "checkSum"),
	"GetKey": ("clientCode", "userName", "password"),
	"ExcuteCommand": (
		"clientCode",
		"proxyCode",
		"unitCode",
		"action",
		"method",
		"data",
		"checkSum",
	),
}

# Fast báo token chết bằng nhiều cách khác nhau; nhận ra để lấy token mới rồi
# thử lại đúng MỘT lần. Không bao giờ thử lại lỗi nghiệp vụ — thử lại một lệnh
# phát hành là nguy cơ hai số hóa đơn cho một lần bán.
TOKEN_EXPIRED_HINTS = ("401", "token", "phiên", "hết hiệu lực", "chưa đăng nhập")


class FastTimeout(frappe.ValidationError):
	"""Đã gửi đi nhưng không nhận được kết quả — bắt buộc truy vấn 370 trước khi thao tác tiếp."""


@dataclass
class FastResponse:
	success: bool = False
	message: str = ""
	error_code: str = ""
	raw: str = ""
	duration_ms: int = 0
	request_summary: dict = field(default_factory=dict)


def encode_payload(payload):
	"""JSON → UTF-8 → base64, đúng quy tắc đóng gói Phần I.

	``ensure_ascii=False``: để mặc định thì tiếng Việt thành ``\\uXXXX`` và Fast
	dựng lại sai tên hàng.
	"""
	raw = json.dumps(payload, ensure_ascii=False, indent=1, default=str)
	return base64.b64encode(raw.encode("utf-8")).decode("ascii")


def decode_message(message):
	"""Giải base64 phần Message — dùng cho PDF trả về từ method 310/380/385."""
	return base64.b64decode(message)


def parse_response(raw):
	"""Bóc ``Success``/``Message`` khỏi SOAP envelope.

	Phản hồi không phải XML (proxy lỗi, trang HTML 502…) được coi là thất bại
	chứ không ném ngoại lệ: tầng trên còn phải ghi log rồi mới báo người dùng.
	"""
	response = FastResponse(raw=raw or "")
	try:
		root = ET.fromstring(raw)
	except ET.ParseError:
		response.message = _("Phản hồi từ Fast không đọc được (không phải XML).")
		return response

	def find(tag):
		for element in root.iter():
			if element.tag.rsplit("}", 1)[-1] == tag:
				return element.text
		return None

	success = (find("Success") or "").strip()
	response.success = success in ("1", "true", "True")
	response.message = unescape(find("Message") or "")
	if not response.success:
		response.error_code = _extract_error_code(response.message)
	return response


def _extract_error_code(message):
	"""Fast trả lỗi dạng ``"835|Hóa đơn đã tồn tại"`` — lấy phần mã dẫn đầu."""
	head = (message or "").split("|", 1)[0].strip()
	return head if head.isdigit() else ""


def _post(url, soap_action, body, timeout=None):
	"""Lời gọi mạng thật. Test thay hàm này bằng transport giả."""
	response = requests.post(
		url,
		data=body.encode("utf-8"),
		headers={
			"Content-Type": "text/xml; charset=utf-8",
			"SOAPAction": soap_action,
		},
		timeout=timeout or REQUEST_TIMEOUT_SECONDS,
	)
	response.raise_for_status()
	return response.text


class FastClient:
	def __init__(self, settings=None, transport=None):
		self.settings = settings or get_settings()
		self.transport = transport or _post
		# Token đã xác minh, dùng lại trong suốt vòng đời client. Một lần phát hành
		# gồm truy vấn 370 rồi mới tới 310; hỏi CheckKey cho từng lệnh là tự nhân
		# đôi số vòng mạng ở đúng lúc không nên chậm.
		self._verified_token = None

	# --- Dựng và gửi envelope ------------------------------------------

	def build_envelope(self, operation, params):
		"""SOAP 1.1 envelope. Mọi giá trị đều escape & < > trước khi nhúng."""
		body = "".join(
			f"<{name}>{escape(str(params.get(name, '')))}</{name}>" for name in OPERATIONS[operation]
		)
		return (
			'<?xml version="1.0" encoding="utf-8"?>'
			'<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
			"<soap:Body>"
			f'<{operation} xmlns="{FAST_NAMESPACE}">{body}</{operation}>'
			"</soap:Body></soap:Envelope>"
		)

	def _call(self, operation, params):
		body = self.build_envelope(operation, params)
		started = time.monotonic()
		try:
			raw = self.transport(
				self.settings.api_url,
				f'"{FAST_NAMESPACE}{operation}"',
				body,
				REQUEST_TIMEOUT_SECONDS,
			)
		except (requests.Timeout, requests.ConnectionError) as exc:
			raise FastTimeout(
				_(
					"Không nhận được phản hồi từ Fast ({0}). Phải truy vấn (370) trước khi thao tác tiếp."
				).format(exc)
			) from exc

		response = parse_response(raw)
		response.duration_ms = int((time.monotonic() - started) * 1000)
		response.request_summary = _mask(operation, params)
		return response

	# --- Token ------------------------------------------------------------

	def token(self, force=False):
		"""Token phiên, lấy lại khi cần. Trình tự CheckKey → GetKey của mục E5."""
		if force:
			self._verified_token = None
		elif self._verified_token:
			return self._verified_token

		if not force and self._stored_token_is_fresh() and self._check_key():
			self._verified_token = self.settings.token
		else:
			self._verified_token = self._get_key()
		return self._verified_token

	def _stored_token_is_fresh(self):
		if not self.settings.token or not self.settings.token_time:
			return False
		return time_diff_in_hours(now_datetime(), get_datetime(self.settings.token_time)) < TOKEN_TTL_HOURS

	def _check_key(self):
		response = self._call(
			"CheckKey",
			{
				"clientCode": self.settings.client_code,
				"userName": self.settings.api_user,
				"checkSum": self.settings.token,
			},
		)
		return response.success

	def _get_key(self):
		response = self._call(
			"GetKey",
			{
				"clientCode": self.settings.client_code,
				"userName": self.settings.api_user,
				"password": self.settings.api_password,
			},
		)
		if not response.success:
			frappe.throw(
				_("Không lấy được token từ Fast: {0}").format(response.message or _("không rõ lý do"))
			)

		token = (response.message or "").strip()
		self.settings.token = token
		self.settings.token_time = now_datetime()
		frappe.db.set_value(
			"Fast EInvoice Settings",
			"Fast EInvoice Settings",
			{"token": token, "token_time": self.settings.token_time},
			update_modified=False,
		)
		frappe.clear_document_cache("Fast EInvoice Settings")
		return token

	# --- Lệnh nghiệp vụ ---------------------------------------------------

	def excute_command(self, action, method, data):
		"""Gửi một lệnh nghiệp vụ. Chỉ thử lại khi token chết, không bao giờ khi lỗi nghiệp vụ."""
		response = self._excute(action, method, data, self.token())
		if not response.success and self._looks_like_dead_token(response):
			response = self._excute(action, method, data, self.token(force=True))
		return response

	def _excute(self, action, method, data, token):
		return self._call(
			"ExcuteCommand",
			{
				"clientCode": self.settings.client_code,
				"proxyCode": self.settings.proxy_code,
				"unitCode": self.settings.unit_code,
				"action": action,
				"method": method,
				"data": encode_payload(data),
				"checkSum": token,
			},
		)

	@staticmethod
	def _looks_like_dead_token(response):
		"""Mã lỗi nghiệp vụ (3 chữ số của bảng G) không bao giờ là lỗi token."""
		if response.error_code and response.error_code not in ("401",):
			return False
		haystack = f"{response.error_code} {response.message}".lower()
		return any(hint in haystack for hint in TOKEN_EXPIRED_HINTS)


def _mask(operation, params):
	"""Bản request để ghi log — che mật khẩu và token (nguyên tắc A3).

	``data`` là base64; log giữ bản đọc được do tầng gọi cung cấp, ở đây chỉ ghi
	độ dài để không phình log.
	"""
	masked = {}
	for name, value in params.items():
		if name in ("password", "checkSum"):
			masked[name] = "***"
		elif name == "data":
			masked[name] = f"<base64 {len(str(value))} ký tự>"
		else:
			masked[name] = value
	return {"operation": operation, "params": masked}
