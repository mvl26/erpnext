# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Một dòng cho mỗi lần gửi — vết đối chiếu của cả tính năng.

Dọn nhật ký nay theo hai hạn khác nhau và do `reminders.clear_old_dispatch_logs`
lo (quyết định D30: thủ công giữ vĩnh viễn, tự động 180 ngày, chỉnh được trong
Cài đặt thông báo).
"""

from frappe.model.document import Document


class SupplyNotificationDispatchLog(Document):
	pass
