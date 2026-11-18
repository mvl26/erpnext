# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Logo Miyano ERP: navbar Desk, trang đăng nhập và nút về ERP trong Raven.

Logo cố định là `app_logo_url` trong erpnext/hooks.py; chỉ thay khi đặt *App Logo*
trong **Website Settings** (quyết định 18/11/2026). Navbar Settings > App Logo
không còn tác dụng.

Không dùng `get_app_logo()` của Frappe (navbar_settings.py): hàm đó chỉ lấy logo
của app thứ hai khi đúng HAI app khai `app_logo_url`. Site cài thêm một app có
logo (Raven) là hàm trả về logo Frappe — navbar và trang đăng nhập mất logo Miyano.
"""

import frappe


def get_erp_logo() -> str:
	return frappe.get_website_settings("app_logo") or frappe.get_hooks("app_logo_url", app_name="erpnext")[0]


def set_desk_logo(bootinfo):
	"""Hook `extend_bootinfo`: chạy SAU `get_bootinfo()`, nơi Frappe gán `app_logo_url`.

	`boot_session` chạy trước dòng gán đó nên đặt ở đó sẽ bị ghi đè.
	"""
	bootinfo.app_logo_url = get_erp_logo()


def set_login_logo(context):
	"""Hook `update_website_context`: chạy sau `get_context` của trang.

	Chỉ trang đăng nhập (frappe/www/login.py) đặt khoá `logo`; trang khác để nguyên.
	"""
	if context.get("logo"):
		context["logo"] = get_erp_logo()
