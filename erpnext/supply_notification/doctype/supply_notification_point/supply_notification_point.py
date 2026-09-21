# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

import frappe
from frappe import _
from frappe.model.document import Document


class SupplyNotificationPoint(Document):
	def validate(self):
		self._validate_print_format()
		self._validate_channels()

	def _validate_print_format(self):
		if not self.attach_pdf:
			self.print_format = None
			return

		if not self.print_format:
			frappe.throw(_("Đã bật đính PDF thì phải chọn mẫu in."))

		doc_type = frappe.db.get_value("Print Format", self.print_format, "doc_type")
		if doc_type != self.reference_doctype:
			frappe.throw(
				_("Mẫu in {0} dành cho {1}, không dùng được cho {2}.").format(
					self.print_format, doc_type, self.reference_doctype
				)
			)

	def _validate_channels(self):
		if self.enabled and not (self.send_email or self.send_inapp or self.notify_external):
			frappe.throw(_("Điểm đang bật thì phải mở ít nhất một kênh gửi."))
