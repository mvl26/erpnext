"""Trang quét thẻ PDA — màn hình đầu tiên app mở ra.

Là trang WEBSITE chứ không phải Desk page: người chưa đăng nhập không mở được
Desk. Và nó phải nằm TRÊN MÁY CHỦ (không gói trong app) vì phiên Frappe là
cookie: trang gói trong app chạy ở nguồn khác, cookie không đặt và không gửi
kèm được — xem spec §3.
"""

import frappe

no_cache = 1


def get_context(context):
	if frappe.session.user != "Guest":
		frappe.local.flags.redirect_location = "/app/pda-home"
		raise frappe.Redirect
	context.no_header = 1
	context.no_breadcrumbs = 1
	return context
