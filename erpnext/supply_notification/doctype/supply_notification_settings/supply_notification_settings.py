# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Thông số chung của tính năng thông báo.

Mọi hằng số từng nằm trong `constants.py` — âm báo, mốc giữ nhật ký, giờ nhắc,
trần thư, số dòng bảng mặt hàng — chuyển về đây để nghiệp vụ sửa được trên giao
diện mà không cần deploy (BA mục 5.1).
"""

import frappe
from frappe import _
from frappe.model.document import Document

SETTINGS_DOCTYPE = "Supply Notification Settings"


class SupplyNotificationSettings(Document):
	def validate(self):
		if self.test_mode and not self.test_email:
			frappe.throw(_("Bật chế độ thử thì phải điền địa chỉ email nhận thư thử."))

		if self.reminder_hour is not None and not 0 <= self.reminder_hour <= 23:
			frappe.throw(_("Giờ chạy hằng ngày phải nằm trong khoảng 0 đến 23."))

		for fieldname in ("max_item_rows", "toast_seconds", "sound_debounce_seconds"):
			if self.get(fieldname) is not None and self.get(fieldname) < 0:
				frappe.throw(_("{0} không được âm.").format(_(self.meta.get_label(fieldname))))

	def on_update(self):
		from erpnext.supply_notification import registry

		registry.clear_cache()


def get_settings() -> Document:
	"""Bản ghi cài đặt, đọc qua cache. Site chưa gieo thì trả bản mặc định."""
	return frappe.get_cached_doc(SETTINGS_DOCTYPE)
