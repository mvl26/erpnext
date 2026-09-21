# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Bỏ cờ "Chế độ TEST" của Fast EInvoice Settings.

Ô này chưa bao giờ định tuyến gì: đích đến của mọi lời gọi do ``api_url`` quyết
định, còn cái tick chỉ đổi màu banner. Hai nguồn sự thật cho cùng một câu hỏi
sớm muộn cũng lệch nhau, và lệch theo đúng hướng nguy hiểm nhất — banner báo
"MÔI TRƯỜNG TEST" trong khi hệ thống đang bắn vào cổng thật. Banner nay suy
thẳng từ ``api_url`` (cổng test của Fast là cùng domain, thêm ``:9000``).

Xóa dòng cũ trong ``tabSingles``: gỡ trường khỏi DocType không tự dọn giá trị đã
lưu, để lại thì nó nằm đó gây nhiễu khi ai đó đọc thẳng bảng.
"""

import frappe


def execute():
	frappe.db.delete("Singles", {"doctype": "Fast EInvoice Settings", "field": "is_test_mode"})
	frappe.clear_cache(doctype="Fast EInvoice Settings")
