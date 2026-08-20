# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tầng giao tiếp SOAP với cổng dịch vụ Fast e-Invoice (portal service v2.5).

Đây là **lớp duy nhất được phép gọi mạng**. Mọi tầng trên chỉ thấy
``FastResponse``. Chế độ vận hành: **không mã hóa RSA** — payload chỉ base64,
không ký/mã hóa thêm.

Tên tham số và hình dạng phản hồi lấy từ **WSDL thật** của Fast
(``…/FastEInvoice.PortalService.asmx?WSDL``, đối chiếu 2026-08-10):

- ``GetKey(proxyCode, clientCode, user, hash)`` → ``<GetKeyResult>`` = token
- ``CheckKey(proxyCode, clientCode, user, data)`` → ``<CheckKeyResult>``
- ``ExcuteCommand(action, method, user, proxyCode, clientCode, unitCode, data,
  checkSum)`` → ``<ExcuteCommandResult>``

Mọi phản hồi bọc trong một thẻ ``<…Result>`` chứa chuỗi; rỗng = Fast từ chối
(sai tài khoản / hash / mã). Còn hai điểm **chưa xác nhận được** vì phải có
token thật mới quan sát được một phản hồi thành công:

1. Thuật toán băm mật khẩu cho thẻ ``hash`` — xem ``hash_password``.
2. Định dạng bên trong ``<ExcuteCommandResult>`` khi thành công — xem
   ``_leading_error_code``.
"""

import base64
import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from xml.sax.saxutils import escape, unescape

import frappe
import requests
from frappe import _
from frappe.utils import now_datetime

from erpnext.einvoice.fast_settings import get_settings

# Namespace của web service ASMX — suy ra, cần xác nhận với WSDL của Fast.
FAST_NAMESPACE = "http://tempuri.org/"

# Token Fast có hiệu lực 24h (mục C1 #10) — CheckKey là nơi xác thực còn hạn hay
# không, nên không cần tự tính giờ ở client.
TOKEN_TTL_HOURS = 24

# Timeout mạng. Hóa đơn 300 dòng ký HSM có thể lâu, nên để rộng.
REQUEST_TIMEOUT_SECONDS = 120

# Tham số của từng lời gọi — đúng tên và thứ tự trong WSDL của Fast.
OPERATIONS = {
	"GetKey": ("proxyCode", "clientCode", "user", "hash"),
	"CheckKey": ("proxyCode", "clientCode", "user", "data"),
	"ExcuteCommand": (
		"action",
		"method",
		"user",
		"proxyCode",
		"clientCode",
		"unitCode",
		"data",
		"checkSum",
	),
}

# Che khi ghi log — nguyên tắc A3. `data` của ExcuteCommand là base64 payload nên
# chỉ ghi độ dài; `data` của CheckKey là token; `hash`/`checkSum` là bí mật.
_MASKED_PARAMS = ("hash", "checkSum")

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


# Ký tự ngăn cách trong chuỗi hash — Chrw(254) = þ, theo tài liệu API Fast.
_HASH_SEP = chr(254)


def hash_password(password, salt):
	"""Chuỗi ``hash`` cho GetKey, đúng công thức tài liệu API Fast:

	``hash = md5( md5(password) + salt ) + chr(254) + salt``

	``salt`` (8 ký tự) lấy từ phản hồi ``Ok:<salt>`` của CheckKey. Đã đối chiếu
	khớp ví dụ trong tài liệu (mật khẩu ``123abc456`` + salt ``9dd8e7e4``).
	"""
	inner = hashlib.md5((password or "").encode("utf-8")).hexdigest()
	digest = hashlib.md5((inner + (salt or "")).encode("utf-8")).hexdigest()
	return f"{digest}{_HASH_SEP}{salt}"


def parse_response(raw):
	"""Bóc kết quả khỏi SOAP envelope của Fast.

	Mọi lời gọi trả về ``<…Result>chuỗi</…Result>``. Hai dạng chuỗi:

	- **Lệnh nghiệp vụ** (ExcuteCommand) → JSON ``{"Success":N,"Code":N,
	  "Message":"…"}``. ``Message`` khi thành công là chuỗi JSON dữ liệu hóa đơn.
	- **Token** (CheckKey/GetKey) → chuỗi thường: ``"Ok"`` / ``"Ok:<salt>"`` /
	  ``"token,salt"`` / rỗng (Fast từ chối).

	Phản hồi không phải XML (proxy lỗi, HTML 502…) tính là thất bại chứ không ném
	ngoại lệ — tầng trên còn phải ghi log rồi mới báo người dùng.
	"""
	response = FastResponse(raw=raw or "")
	try:
		root = ET.fromstring(raw)
	except ET.ParseError:
		response.message = _("Phản hồi từ Fast không đọc được (không phải XML): {0}").format(_snippet(raw))
		return response

	result_text, fault = None, None
	for element in root.iter():
		tag = element.tag.rsplit("}", 1)[-1]
		if tag.endswith("Result") and result_text is None:
			result_text = element.text or ""
		elif tag == "faultstring" and fault is None:
			fault = element.text or ""

	if result_text is None:
		# Không có thẻ *Result: hoặc SOAP Fault, hoặc phản hồi lạ. Luôn để lại dấu
		# vết — "không rõ lý do" là câu vô dụng với cả kế toán lẫn người sửa lỗi.
		response.message = (
			unescape(fault)
			if fault
			else _("Phản hồi không đúng cấu trúc của Fast. Nội dung nhận được: {0}").format(_snippet(raw))
		)
		return response

	text = unescape(result_text).strip()
	if _apply_command_envelope(response, text):
		return response

	# Kết quả token: chuỗi thường, rỗng = Fast từ chối.
	response.success = bool(text)
	response.message = text
	return response


def _apply_command_envelope(response, text):
	"""Nếu ``text`` là JSON ``{"Success","Code","Message"}`` thì nạp vào response.

	Trả True khi đúng dạng envelope của ExcuteCommand, False nếu là kết quả token.
	"""
	if not text.startswith("{"):
		return False
	try:
		payload = json.loads(text)
	except ValueError:
		return False
	if not isinstance(payload, dict) or "Success" not in payload:
		return False

	response.success = str(payload.get("Success")).strip() in ("1", "true", "True")
	code = str(payload.get("Code") or "").strip()
	response.error_code = "" if code in ("", "0") else code
	response.message = payload.get("Message") or ""
	return True


def _snippet(raw, limit=300):
	"""Rút gọn phản hồi thô để nhét vừa một thông báo lỗi."""
	text = " ".join((raw or "").split())
	return text[:limit] + ("…" if len(text) > limit else "")


def _http_failure(exc):
	"""Lỗi HTTP → ngoại lệ đúng mức độ nguy hiểm.

	5xx (hoặc không rõ mã) nghĩa là request **đã tới Fast** nhưng không biết bên
	đó xử lý tới đâu — với lệnh phát hành thì đây là ca "cần đối soát", tuyệt đối
	không được coi là thất bại chắc chắn rồi gửi lại.
	4xx (sai tài khoản, sai URL) thì chắc chắn chưa chạm tới nghiệp vụ.
	"""
	status = getattr(getattr(exc, "response", None), "status_code", None)
	body = _snippet(getattr(getattr(exc, "response", None), "text", "") or "", 200)
	detail = f" — {body}" if body else ""

	if status and status < 500:
		return frappe.ValidationError(
			_("Fast từ chối request (HTTP {0}){1}. Kiểm tra URL dịch vụ và tài khoản API.").format(
				status, detail
			)
		)
	return FastTimeout(
		_(
			"Fast trả lỗi máy chủ (HTTP {0}){1}. Nếu lệnh vừa gửi là phát hành, "
			"phải truy vấn (370) trước khi thao tác tiếp."
		).format(status or "?", detail)
	)


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
					"Không kết nối được tới Fast tại {0} ({1}). Nếu lệnh vừa gửi là phát hành, "
					"phải truy vấn (370) trước khi thao tác tiếp."
				).format(self.settings.api_url, exc)
			) from exc
		except requests.HTTPError as exc:
			raise _http_failure(exc) from exc

		response = parse_response(raw)
		response.duration_ms = int((time.monotonic() - started) * 1000)
		response.request_summary = _mask(operation, params)
		return response

	# --- Token ------------------------------------------------------------

	def token(self, force=False):
		"""Token phiên, theo đúng handshake của tài liệu API Fast.

		``CheckKey`` là nguồn sự thật: trả ``"Ok"`` nếu token còn hiệu lực,
		``"Ok:<salt>"`` nếu cần cấp mới (kể cả lần đầu chưa có token), rỗng nếu sai
		thông tin doanh nghiệp / user. Có salt thì ``GetKey`` với hash dựng từ salt
		đó. Token có hiệu lực 24h, lưu lại để lần sau chỉ cần CheckKey.
		"""
		if not force and self._verified_token:
			return self._verified_token

		stored = "" if force else (self.settings.token or "")
		check = self._call(
			"CheckKey",
			{
				"proxyCode": self.settings.proxy_code,
				"clientCode": self.settings.client_code,
				"user": self.settings.api_user,
				"data": stored,
			},
		)
		result = (check.message or "").strip()

		if result == "Ok" and stored:
			self._verified_token = stored
			return stored

		salt = self._extract_salt(result)
		if salt is None:
			self._raise_auth_error(result)

		self._verified_token = self._get_key(salt)
		return self._verified_token

	@staticmethod
	def _extract_salt(check_result):
		"""``"Ok:<salt>"`` → salt (8 ký tự). ``None`` nếu không phải dạng cấp salt."""
		match = re.match(r"Ok\s*:\s*(\S+)", check_result or "")
		return match.group(1) if match else None

	def _get_key(self, salt):
		response = self._call(
			"GetKey",
			{
				"proxyCode": self.settings.proxy_code,
				"clientCode": self.settings.client_code,
				"user": self.settings.api_user,
				"hash": hash_password(self.settings.api_password, salt),
			},
		)
		# GetKey trả "token,salt"; rỗng = sai mật khẩu / user chưa có quyền API.
		token = (response.message or "").split(",", 1)[0].strip()
		if not token:
			self._raise_auth_error(response.message)

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

	def _raise_auth_error(self, fast_reply):
		frappe.throw(
			_(
				"Không đăng nhập được vào Fast bằng user API <b>{0}</b>.<br>Fast trả về: {1}"
				"<br><br>Kiểm tra <b>User API</b>, <b>Mật khẩu</b> và <b>URL dịch vụ</b> "
				"({2}) trong Fast EInvoice Settings. Nếu là user thường, cần được phân "
				"quyền phát hành hóa đơn trên portal Fast."
			).format(
				self.settings.api_user or _("(chưa điền)"),
				(fast_reply or _("(kết quả rỗng)")).strip() or _("(kết quả rỗng)"),
				self.settings.api_url,
			),
			title=_("Không lấy được token"),
		)

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
				"action": action,
				"method": method,
				"user": self.settings.api_user,
				"proxyCode": self.settings.proxy_code,
				"clientCode": self.settings.client_code,
				"unitCode": self.settings.unit_code,
				"data": encode_payload(data),
				"checkSum": token,
			},
		)

	@staticmethod
	def _looks_like_dead_token(response):
		"""Có phải lỗi token chết không — để lấy token mới rồi thử lại đúng một lần.

		Mã lỗi nghiệp vụ đã biết (bảng G) không bao giờ được coi là lỗi token: thử
		lại một lệnh phát hành là nguy cơ hai số hóa đơn.
		"""
		from erpnext.einvoice.errors import ERROR_CATALOGUE

		if response.error_code in ERROR_CATALOGUE:
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
		if name in _MASKED_PARAMS:
			masked[name] = "***"
		elif name == "data" and operation == "ExcuteCommand":
			# ExcuteCommand.data là base64 payload — chỉ ghi độ dài để khỏi phình log.
			masked[name] = f"<base64 {len(str(value))} ký tự>"
		elif name == "data":
			# CheckKey.data là token phiên — che đi.
			masked[name] = "***"
		else:
			masked[name] = value
	return {"operation": operation, "params": masked}
