# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

import frappe
from frappe import _
from frappe.model.document import Document

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
