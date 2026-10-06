# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""DocType `Fast EInvoice Log` — mục C4, và chính sách lưu trữ log."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from erpnext.einvoice.doctype.fast_einvoice_log.fast_einvoice_log import (
	LOG_RETENTION_MONTHS,
	delete_old_logs,
)

LOG = "Fast EInvoice Log"


def make_log(**values):
	doc = frappe.get_doc(
		{
			"doctype": LOG,
			"operation": "ExcuteCommand",
			"action": 0,
			"method": 310,
			"purpose": "Phát hành hóa đơn",
			"status": "Đang gửi",
			**values,
		}
	)
	doc.flags.ignore_permissions = True
	doc.flags.ignore_links = True
	doc.insert()
	return doc


def age_log(name, months):
	old = add_to_date(now_datetime(), months=-months)
	frappe.db.set_value(LOG, name, "creation", old, update_modified=False)


class TestFastEInvoiceLog(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()

	def tearDown(self):
		frappe.db.rollback()

	def test_log_records_the_call_envelope(self):
		meta = frappe.get_meta(LOG)
		self.assertEqual(meta.get_field("action").fieldtype, "Int")
		self.assertEqual(meta.get_field("method").fieldtype, "Int")
		self.assertEqual(meta.get_field("duration_ms").fieldtype, "Int")
		self.assertEqual(meta.get_field("user").options, "User")

	def test_request_and_response_are_long_text(self):
		"""Payload hóa đơn 300 dòng không nhét vừa Small Text."""
		meta = frappe.get_meta(LOG)
		self.assertEqual(meta.get_field("request_json").fieldtype, "Long Text")
		self.assertEqual(meta.get_field("response_raw").fieldtype, "Long Text")

	def test_document_link_is_optional_for_token_calls(self):
		"""CheckKey/GetKey chưa gắn với hóa đơn nào."""
		self.assertFalse(frappe.get_meta(LOG).get_field("fei_document").reqd)
		log = make_log(operation="GetKey", purpose="Lấy token phiên")
		self.assertIsNone(log.fei_document)

	def test_operation_covers_every_call_the_integration_makes(self):
		options = frappe.get_meta(LOG).get_field("operation").options.split("\n")
		for operation in ("CheckKey", "GetKey", "ExcuteCommand", "Email"):
			self.assertIn(operation, options)

	def test_stamps_user_and_timestamp_on_insert(self):
		"""Log là căn cứ đối chiếu với Fast/CQT — phải biết ai bấm, lúc nào."""
		log = make_log()
		self.assertEqual(log.user, frappe.session.user)
		self.assertIsNotNone(log.timestamp)

	def test_success_flag_follows_the_status(self):
		self.assertEqual(make_log(status="Thành công").success, 1)
		self.assertEqual(make_log(status="Lỗi").success, 0)
		self.assertEqual(make_log(status="Đang gửi").success, 0)

	def test_logs_are_never_editable_after_the_fact(self):
		"""Sửa được log thì log hết là bằng chứng."""
		meta = frappe.get_meta(LOG)
		for fieldname in ("request_json", "response_raw", "action", "method", "user", "timestamp"):
			self.assertEqual(meta.get_field(fieldname).read_only, 1, fieldname)

	# --- Chính sách lưu trữ ------------------------------------------------

	def test_retention_window_is_two_years(self):
		self.assertEqual(LOG_RETENTION_MONTHS, 24)

	def test_cleanup_removes_logs_past_the_retention_window(self):
		stale = make_log(purpose="Rất cũ")
		age_log(stale.name, 25)

		delete_old_logs()
		self.assertFalse(frappe.db.exists(LOG, stale.name))

	def test_cleanup_keeps_logs_inside_the_window(self):
		"""Giữ tối thiểu 12 tháng để còn đối chiếu với Cơ quan Thuế."""
		recent = make_log(purpose="Còn trong hạn")
		age_log(recent.name, 13)

		delete_old_logs()
		self.assertTrue(frappe.db.exists(LOG, recent.name))

	def test_cleanup_is_registered_as_a_scheduled_job(self):
		daily = frappe.get_hooks("scheduler_events").get("daily") or []
		self.assertIn("erpnext.einvoice.doctype.fast_einvoice_log.fast_einvoice_log.delete_old_logs", daily)
