# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nhật ký mọi lời gọi tới Fast — mục C4 và nguyên tắc A3 của đặc tả.

Log là **căn cứ duy nhất** khi đối chiếu tranh chấp với Fast hoặc Cơ quan Thuế,
nên mọi trường đều read-only sau khi ghi và không có đường tắt để tắt ghi log.
"""

import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, now_datetime

# Đặc tả C4: giữ tối thiểu 12 tháng để đối chiếu với CQT, tự dọn sau 24 tháng.
LOG_RETENTION_MONTHS = 24

SUCCESS_STATUS = "Thành công"


class FastEInvoiceLog(Document):
	def before_insert(self):
		self.user = self.user or frappe.session.user
		self.timestamp = self.timestamp or now_datetime()

	def validate(self):
		self.success = 1 if self.status == SUCCESS_STATUS else 0


def delete_old_logs():
	"""Job nền hằng ngày — dọn log quá hạn lưu trữ."""
	cutoff = add_to_date(now_datetime(), months=-LOG_RETENTION_MONTHS)
	frappe.db.delete("Fast EInvoice Log", {"creation": ("<", cutoff)})
