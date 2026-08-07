# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Cấu hình kết nối Fast — mục C1 của đặc tả."""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.einvoice.fast_settings import get_environment_banner, get_settings

SETTINGS = "Fast EInvoice Settings"


def _set(**values):
	doc = frappe.get_single(SETTINGS)
	doc.update(values)
	doc.flags.ignore_permissions = True
	doc.save()
	return doc


class TestFastEInvoiceSettings(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()

	def tearDown(self):
		frappe.db.rollback()

	def test_settings_doctype_is_single(self):
		self.assertTrue(frappe.get_meta(SETTINGS).issingle)

	def test_api_password_is_stored_as_password_fieldtype(self):
		"""Mật khẩu phải mã hóa trong DB, không nằm thẳng ở bảng Singles."""
		self.assertEqual(frappe.get_meta(SETTINGS).get_field("api_password").fieldtype, "Password")

	def test_defaults_are_safe_for_a_fresh_site(self):
		"""Site mới phải tắt tích hợp và trỏ vào môi trường TEST."""
		meta = frappe.get_meta(SETTINGS)
		self.assertEqual(meta.get_field("enabled").default, "0")
		self.assertEqual(meta.get_field("is_test_mode").default, "1")

	def test_spec_defaults_for_the_operational_checkboxes(self):
		meta = frappe.get_meta(SETTINGS)
		self.assertEqual(meta.get_field("auto_download_pdf").default, "1")
		self.assertEqual(meta.get_field("auto_poll_tax_status").default, "1")
		self.assertEqual(meta.get_field("require_customer_approval").default, "1")

	def test_credentials_are_optional_while_the_integration_is_off(self):
		"""Site mới chưa xin được tài khoản Fast vẫn phải lưu được cấu hình."""
		doc = _set(enabled=0, api_url="", client_code="", api_user="", api_password="")
		self.assertEqual(doc.enabled, 0)

	def test_enabling_without_credentials_is_blocked(self):
		with self.assertRaises(frappe.MandatoryError):
			_set(enabled=1, api_url="", client_code="", api_user="", api_password="")

	def test_get_settings_trims_codes_before_they_reach_fast(self):
		"""Spec C1: `client_code` và `unit_code` phải trim khoảng trắng khi gửi."""
		_set(
			enabled=0,
			client_code="  008254  ",
			unit_code=" CTY ",
			proxy_code=" 006384 ",
			voucher_book=" 1C26TAA ",
			api_url=" https://tportal.fast.com.vn:9000/x.asmx ",
		)
		settings = get_settings()
		self.assertEqual(settings.client_code, "008254")
		self.assertEqual(settings.unit_code, "CTY")
		self.assertEqual(settings.proxy_code, "006384")
		self.assertEqual(settings.voucher_book, "1C26TAA")
		self.assertEqual(settings.api_url, "https://tportal.fast.com.vn:9000/x.asmx")

	def test_get_settings_exposes_the_decrypted_password(self):
		_set(enabled=0, api_password="s3cret")
		self.assertEqual(get_settings().api_password, "s3cret")

	def test_banner_warns_loudly_when_pointing_at_the_real_system(self):
		"""Nguyên tắc A4: phải biết ngay mình đang bắn vào hệ thống thật."""
		_set(enabled=0, is_test_mode=0)
		banner = get_environment_banner()
		self.assertEqual(banner["indicator"], "red")
		self.assertIn("THẬT", banner["message"])

	def test_banner_is_calm_in_test_mode(self):
		_set(enabled=0, is_test_mode=1)
		banner = get_environment_banner()
		self.assertEqual(banner["indicator"], "yellow")
		self.assertIn("TEST", banner["message"])

	def test_notify_on_error_is_a_user_multiselect(self):
		field = frappe.get_meta(SETTINGS).get_field("notify_on_error")
		self.assertEqual(field.fieldtype, "Table MultiSelect")
		child = frappe.get_meta(field.options)
		self.assertEqual(child.get_field("user").options, "User")
