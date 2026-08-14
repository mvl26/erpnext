# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Truy cập cấu hình kết nối Fast (mục C1 của đặc tả).

Mọi nơi cần thông số kết nối đều đi qua ``get_settings()`` chứ không đọc thẳng
Single DocType, vì hai lý do: mã doanh nghiệp và mã đơn vị **phải trim khoảng
trắng khi gửi** (C1), và mật khẩu phải lấy qua ``get_password()`` mới ra bản rõ.
"""

import re

import frappe
from frappe import _

SETTINGS_DOCTYPE = "Fast EInvoice Settings"

# Trim khi gửi — khoảng trắng thừa trong các mã này làm Fast từ chối request.
_TRIMMED_FIELDS = (
	"api_url",
	"client_code",
	"proxy_code",
	"unit_code",
	"voucher_book",
	"api_user",
	"default_human_name",
)

# Cổng TEST của Fast là cùng domain nhưng thêm ``:9000`` (tài liệu API mục 1);
# không có cổng này là đang trỏ vào hệ thống thật.
_TEST_PORT = ":9000"


def is_test_endpoint(api_url):
	"""URL đang trỏ vào cổng TEST của Fast hay cổng thật.

	Suy từ chính URL thay vì từ một ô tự khai: một cái tick không đổi được đích
	đến của lời gọi, nên ô tự khai chỉ tạo thêm khả năng nhãn nói một đằng hệ
	thống làm một nẻo — mà nói sai theo đúng hướng nguy hiểm nhất là báo "TEST"
	trong khi đang bắn vào cổng thật.
	"""
	return _TEST_PORT in (api_url or "")


def get_settings():
	"""Cấu hình đã chuẩn hóa, kèm mật khẩu bản rõ. Không gọi mạng."""
	doc = frappe.get_cached_doc(SETTINGS_DOCTYPE)
	settings = frappe._dict({fieldname: (doc.get(fieldname) or "").strip() for fieldname in _TRIMMED_FIELDS})
	settings.api_url = _normalise_url(settings.api_url)
	settings.update(
		{
			"enabled": bool(doc.enabled),
			"is_test_endpoint": is_test_endpoint(settings.api_url),
			"require_customer_approval": bool(doc.require_customer_approval),
			"auto_download_pdf": bool(doc.auto_download_pdf),
			"auto_poll_tax_status": bool(doc.auto_poll_tax_status),
			"draft_email_template": doc.draft_email_template,
			"issued_email_template": doc.issued_email_template,
			"token": doc.token,
			"token_time": doc.token_time,
			"api_password": doc.get_password("api_password", raise_exception=False) or "",
		}
	)
	return settings


def _normalise_url(url):
	"""Gộp dấu ``/`` thừa trong đường dẫn (giữ nguyên ``https://``).

	URL gõ thừa một dấu (``…vn//AppService``) từng làm lời gọi khó chịu; chuẩn hóa
	ở một chỗ để không nơi nào phải lo.
	"""
	return re.sub(r"(?<!:)//+", "/", url or "")


def get_notify_recipients():
	"""Email của những người nhận cảnh báo khi phát hành lỗi / CQT từ chối."""
	doc = frappe.get_cached_doc(SETTINGS_DOCTYPE)
	users = [row.user for row in (doc.notify_on_error or []) if row.user]
	if not users:
		return []
	return [
		email
		for (email,) in frappe.get_all(
			"User", filters={"name": ["in", users], "enabled": 1}, fields=["email"], as_list=True
		)
		if email
	]


@frappe.whitelist()
def get_environment_banner():
	"""Nhắc người dùng đang bắn vào đâu — nguyên tắc A4 của đặc tả.

	Đọc thẳng ``api_url``, không đọc ô cấu hình nào: đổi URL là đổi banner ngay,
	không ai quên tick lại được.
	"""
	if get_settings().is_test_endpoint:
		return {
			"indicator": "yellow",
			"message": _("MÔI TRƯỜNG TEST — hóa đơn phát hành ở đây không có giá trị pháp lý."),
		}
	return {
		"indicator": "red",
		"message": _("HỆ THỐNG THẬT — mỗi lần phát hành tiêu một số hóa đơn và gửi lên Cơ quan Thuế."),
	}


def check_enabled():
	"""Chặn sớm mọi hành động khi tích hợp chưa bật."""
	settings = get_settings()
	if not settings.enabled:
		frappe.throw(_("Tích hợp hóa đơn điện tử Fast chưa được kích hoạt trong Fast EInvoice Settings."))
	return settings
