# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Thông số thông báo bơm vào `frappe.boot` lúc nạp Desk.

Hai việc: (1) âm báo và thời gian toast lấy từ Cài đặt thay vì hằng số trong JS
(AC-13); (2) danh sách chứng từ **có nút Thủ công** để trình duyệt chỉ hỏi máy
chủ khi form đang mở thuộc danh sách đó — mở chứng từ khác không kéo theo lời
gọi thừa nào.
"""

import frappe
from frappe.utils import cint


def bootinfo(bootinfo):
	if frappe.session.user in ("Guest", None):
		return

	try:
		from erpnext.supply_notification import registry
		from erpnext.supply_notification.doctype.supply_notification_settings.supply_notification_settings import (
			get_settings,
		)

		settings = get_settings()
		bootinfo.supply_notification = {
			"enabled": cint(settings.enabled),
			"test_mode": cint(settings.test_mode),
			"sound": settings.sound or "alert",
			"toast_seconds": cint(settings.toast_seconds) or 10,
			"sound_debounce_seconds": cint(settings.sound_debounce_seconds),
			"manual_doctypes": registry.manual_doctypes(),
		}
	except Exception:
		# Site chưa migrate xong thì Desk vẫn phải mở được.
		bootinfo.supply_notification = {"enabled": 0, "manual_doctypes": []}
