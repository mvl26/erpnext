# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tắt hai Server Script email đã chuyển thành code ở ``erpnext.utilities.email_guard``.

Để nguyên thì luật chạy hai lần; tệ hơn, khi bench tắt Server Script thì script
vẫn chặn mọi thao tác gửi mail. Chỉ tắt, không xóa: còn bản gốc để đối chiếu.
"""

import frappe

MIGRATED_SCRIPTS = (
	"Khong gui toi dia chi da ngung gui",
	"Chan vong lap thu tra ve (bounce)",
)


def execute():
	for name in MIGRATED_SCRIPTS:
		if frappe.db.exists("Server Script", name):
			frappe.db.set_value("Server Script", name, "disabled", 1, update_modified=False)
	frappe.cache.delete_value("server_script_map")
