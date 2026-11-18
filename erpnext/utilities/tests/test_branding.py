# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Logo Miyano ERP cố định trong code, chỉ Website Settings > App Logo thay được.

Không dựa vào `get_app_logo()` của Frappe: có từ ba app khai `app_logo_url` (cài thêm
Raven là đủ) thì hàm đó trả về logo Frappe.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_html_for_route

from erpnext.utilities import branding

MIYANO_LOGO = "/assets/erpnext/images/miyano-logo.png"


class TestBranding(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.request = None

	def test_logo_mac_dinh_la_logo_miyano(self):
		with patch.object(branding.frappe, "get_website_settings", return_value=None):
			self.assertEqual(branding.get_erp_logo(), MIYANO_LOGO)

	def test_website_settings_thay_duoc_logo(self):
		with patch.object(branding.frappe, "get_website_settings", return_value="/files/logo-moi.png"):
			self.assertEqual(branding.get_erp_logo(), "/files/logo-moi.png")

	def test_navbar_settings_khong_thay_duoc_logo(self):
		with (
			patch.object(branding.frappe, "get_website_settings", return_value=None),
			patch.object(frappe.db, "get_single_value", return_value="/files/logo-navbar.png"),
		):
			self.assertEqual(branding.get_erp_logo(), MIYANO_LOGO)

	def test_khong_theo_get_app_logo_cua_frappe_khi_nhieu_app_khai_logo(self):
		logos = ["/assets/frappe/frappe.svg", MIYANO_LOGO, "/assets/raven/raven.svg"]
		real_get_hooks = frappe.get_hooks

		def get_hooks(hook=None, *args, **kwargs):
			if hook == "app_logo_url" and not kwargs.get("app_name"):
				return logos
			return real_get_hooks(hook, *args, **kwargs)

		with (
			patch.object(branding.frappe, "get_website_settings", return_value=None),
			patch.object(frappe, "get_hooks", side_effect=get_hooks),
		):
			self.assertEqual(branding.get_erp_logo(), MIYANO_LOGO)

	def test_navbar_desk_dung_logo_miyano(self):
		bootinfo = frappe._dict(app_logo_url="/assets/frappe/images/frappe-framework-logo.svg")
		with patch.object(branding.frappe, "get_website_settings", return_value=None):
			branding.set_desk_logo(bootinfo)
		self.assertEqual(bootinfo.app_logo_url, MIYANO_LOGO)

	def test_bootinfo_that_cua_desk_co_logo_miyano(self):
		# Chạy cả luồng boot (get_bootinfo rồi extend_bootinfo); không đọc/ghi cache bootinfo
		# trong Redis, vì Redis dùng chung với site đang chạy.
		from frappe import sessions

		frappe.local.request = None  # ngoài web request; sessions.get() có đọc thuộc tính này
		cache = frappe.cache
		real_hget, real_hset = cache.hget, cache.hset

		def hget(name, *args, **kwargs):
			return None if name == "bootinfo" else real_hget(name, *args, **kwargs)

		def hset(name, *args, **kwargs):
			if name != "bootinfo":
				return real_hset(name, *args, **kwargs)

		with (
			patch.object(branding.frappe, "get_website_settings", return_value=None),
			patch.object(cache, "hget", side_effect=hget),
			patch.object(cache, "hset", side_effect=hset),
		):
			bootinfo = sessions.get()
		self.assertEqual(bootinfo.app_logo_url, MIYANO_LOGO)

	def test_chi_doi_logo_khi_trang_co_khoa_logo(self):
		context = frappe._dict(title="Trang khác")
		branding.set_login_logo(context)
		self.assertNotIn("logo", context)

	def test_hook_duoc_dang_ky(self):
		self.assertIn("erpnext.utilities.branding.set_desk_logo", frappe.get_hooks("extend_bootinfo"))
		self.assertIn("erpnext.utilities.branding.set_login_logo", frappe.get_hooks("update_website_context"))

	def test_trang_dang_nhap_hien_logo_miyano(self):
		frappe.set_user("Guest")
		with patch.object(frappe, "get_website_settings", return_value=None):
			html = get_html_for_route("login")
		self.assertIn(f'src="{MIYANO_LOGO}"', html)
		self.assertNotIn("frappe-framework-logo", html)
