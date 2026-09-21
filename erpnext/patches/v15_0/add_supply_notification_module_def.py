# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tạo Module Def cho module Supply Notification.

`bench migrate` KHÔNG tạo Module Def cho module mới thêm vào `modules.txt` —
`frappe.installer.add_module_defs` chỉ chạy lúc cài app. Thiếu bản ghi này thì
DocType khai `"module": "Supply Notification"` không có gì để trỏ tới.
"""

import frappe


def execute():
	if frappe.db.exists("Module Def", "Supply Notification"):
		return

	doc = frappe.new_doc("Module Def")
	doc.module_name = "Supply Notification"
	doc.app_name = "erpnext"
	doc.insert(ignore_permissions=True)
