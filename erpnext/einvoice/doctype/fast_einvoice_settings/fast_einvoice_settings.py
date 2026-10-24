# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import validate_email_address

# Thiếu bất kỳ trường nào trong đây thì không thể gọi Fast, nên không cho bật tích hợp.
REQUIRED_TO_ENABLE = {
	"api_url": "URL dịch vụ",
	"client_code": "Mã doanh nghiệp",
	"proxy_code": "Mã nhóm dịch vụ",
	"unit_code": "Mã đơn vị",
	"voucher_book": "Quyển hóa đơn",
	"api_user": "User API",
	"api_password": "Mật khẩu",
}


class FastEInvoiceSettings(Document):
	def validate(self):
		for fieldname in ("api_url", "client_code", "proxy_code", "unit_code", "voucher_book", "api_user"):
			if value := self.get(fieldname):
				self.set(fieldname, value.strip())

		self._validate_credentials_before_enabling()
		self._validate_invoice_delivery()

	def _validate_credentials_before_enabling(self):
		"""Chặn ở server, không chỉ ở giao diện.

		``mandatory_depends_on`` của Frappe chỉ chạy phía client, nên bật tích hợp
		qua API hay patch vẫn lọt. Đây là cờ mở đường cho các lời gọi phát hành
		thật nên phải khóa ở server.
		"""
		if not self.enabled:
			return
		missing = [label for fieldname, label in REQUIRED_TO_ENABLE.items() if not self.get(fieldname)]
		if missing:
			frappe.throw(
				_("Chưa thể kích hoạt tích hợp Fast — còn thiếu: {0}").format(", ".join(missing)),
				frappe.MandatoryError,
			)

	def _validate_invoice_delivery(self):
		"""Tự gửi cần PDF chính thức có sẵn; email đầu mối và CC phải là email thật.

		Một địa chỉ CC gõ sai thì mọi email hóa đơn đều kèm một người nhận hỏng —
		chặn ngay lúc lưu cấu hình thay vì để hàng đợi email báo lỗi từng lần gửi.
		"""
		if self.get("auto_send_invoice") and not self.auto_download_pdf:
			frappe.throw(
				_("Bật “Tự tải PDF sau phát hành” trước — hệ thống chỉ tự gửi khi đã có PDF chính thức.")
			)
		from erpnext.einvoice.fast_settings import split_emails

		for fieldname in ("invoice_email_cc", "invoice_sender_email"):
			for email in split_emails(self.get(fieldname)):
				validate_email_address(email, throw=True)
