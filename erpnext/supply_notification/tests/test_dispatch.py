# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Cửa gửi duy nhất: ba kênh, chống trùng, chế độ thử, trần thư, gửi lại."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.supply_notification import dispatch as dispatch_module
from erpnext.supply_notification.dispatch import LOG_DOCTYPE, dispatch
from erpnext.supply_notification.tests import fixtures
from erpnext.supply_notification.tests.test_resolver import make_user

LOG_FIELDS = [
	"name",
	"status",
	"channel_email",
	"channel_inapp",
	"channel_external",
	"recipients",
	"external_recipients",
	"cc",
	"subject",
	"test_mode",
	"is_manual",
	"reason",
	"remark",
]


def logs_for(doc, point=None, milestone="submit"):
	"""Nhật ký của MỘT điểm trên một chứng từ.

	Lọc theo điểm là bắt buộc: `FrappeTestCase` rollback ở phạm vi **class**, nên
	điểm do test trước tạo vẫn còn và cũng bắn trên chứng từ của test sau.
	"""
	filters = {
		"reference_doctype": doc.doctype,
		"reference_name": doc.name,
		"milestone": milestone,
	}
	if point is not None:
		filters["point"] = point.name if hasattr(point, "name") else point

	return frappe.get_all(LOG_DOCTYPE, filters=filters, fields=LOG_FIELDS)


def queued_emails(doc):
	return frappe.db.count("Email Queue", {"reference_doctype": doc.doctype, "reference_name": doc.name})


def queue_rows_to(doc, address) -> set[str]:
	"""Các thư của chứng từ này gửi tới một địa chỉ."""
	names = frappe.get_all(
		"Email Queue", filters={"reference_doctype": doc.doctype, "reference_name": doc.name}, pluck="name"
	)
	if not names:
		return set()
	return set(
		frappe.get_all(
			"Email Queue Recipient",
			filters={"parent": ("in", names), "recipient": address},
			pluck="parent",
		)
	)


def emails_to(doc, address) -> int:
	return len(queue_rows_to(doc, address))


def decoded_subject(row) -> str:
	"""Tiêu đề thật của một thư trong hàng đợi (Email Queue không có cột subject)."""
	import email as email_lib
	from email.header import decode_header, make_header

	message = email_lib.message_from_string(row.message)
	return str(make_header(decode_header(message["Subject"] or "")))


def last_email(doc):
	rows = frappe.get_all(
		"Email Queue",
		filters={"reference_doctype": doc.doctype, "reference_name": doc.name},
		fields=["name", "message"],
		order_by="creation desc",
		limit=1,
	)
	return rows[0] if rows else None


class TestChannels(FrappeTestCase):
	def test_submitting_sends_email_and_in_app_notification(self):
		user = make_user()
		point = fixtures.make_point(users=[user])

		order = fixtures.make_sales_order()

		rows = logs_for(order, point)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0].status, "Sent")
		self.assertEqual(rows[0].channel_email, 1)
		self.assertEqual(rows[0].channel_inapp, 1)
		self.assertEqual(emails_to(order, frappe.db.get_value("User", user, "email")), 1)
		self.assertTrue(
			frappe.db.exists(
				"Notification Log",
				{"document_type": "Sales Order", "document_name": order.name, "for_user": user},
			)
		)

	def test_in_app_notification_is_an_alert_so_frappe_adds_no_second_email(self):
		user = make_user()
		fixtures.make_point(users=[user])

		order = fixtures.make_sales_order()

		self.assertEqual(
			frappe.db.get_value(
				"Notification Log",
				{"document_type": "Sales Order", "document_name": order.name, "for_user": user},
				"type",
			),
			"Alert",
		)
		self.assertEqual(emails_to(order, frappe.db.get_value("User", user, "email")), 1)

	def test_point_without_recipients_is_logged_as_skipped(self):
		# Kiểm V5 không cho LƯU một điểm đang bật mà không có người nhận, nên tình
		# huống này chỉ xảy ra khi người nhận biến mất sau đó (nghỉ việc, khoá tài
		# khoản). Dựng đúng như vậy: tắt lúc lưu, bật lại bằng db_set.
		point = fixtures.make_point(users=[], notify_owner=0, enabled=0)
		point.db_set("enabled", 1)

		order = fixtures.make_sales_order(submit=False)
		log = dispatch_module.send(point, order, "submit")

		row = frappe.get_doc(LOG_DOCTYPE, log.name)
		self.assertEqual(row.status, "Skipped")
		self.assertIn("Không có người nhận", row.reason)

	def test_subject_carries_the_configured_prefix(self):
		point = fixtures.make_point(users=[make_user()], subject_prefix="[SupplyCore]")

		order = fixtures.make_sales_order()

		self.assertTrue(logs_for(order, point)[0].subject.startswith("[SupplyCore]"))


class TestDeduplication(FrappeTestCase):
	def test_repeated_dispatch_does_not_send_twice(self):
		point = fixtures.make_point(users=[make_user()])
		order = fixtures.make_sales_order()

		dispatch(point.name, "Sales Order", order.name)
		dispatch(point.name, "Sales Order", order.name)

		self.assertEqual(len(logs_for(order, point)), 1)

	def test_force_bypasses_deduplication(self):
		point = fixtures.make_point(users=[make_user()])
		order = fixtures.make_sales_order()

		dispatch(point.name, "Sales Order", order.name, force=True)

		self.assertEqual(len(logs_for(order, point)), 2)


class TestExternal(FrappeTestCase):
	def test_party_email_gets_its_own_message(self):
		supplier = fixtures.make_supplier(email="ncc@example.com")
		point = fixtures.make_point(
			reference_doctype="Purchase Invoice",
			users=[make_user()],
			notify_external=1,
			external_party_contact=1,
			external_subject_template="Hoá đơn {{ doc.name }}",
			external_body_template="<p>Kính gửi {{ ten_doi_tac }}</p>",
			party_field="supplier_name",
		)

		invoice = fixtures.make_purchase_invoice(supplier=supplier)

		rows = logs_for(invoice, point)
		self.assertEqual(rows[0].channel_external, 1)
		self.assertEqual(rows[0].external_recipients, "ncc@example.com")

		# F10: thư ra ngoài là một thư RIÊNG, NCC không nằm chung thư với nội bộ.
		staff_email = rows[0].recipients.split(",")[0].strip()
		to_supplier = queue_rows_to(invoice, "ncc@example.com")
		to_staff = queue_rows_to(invoice, staff_email)

		self.assertTrue(to_supplier)
		self.assertTrue(to_staff)
		self.assertFalse(to_supplier & to_staff)

	def test_external_mail_never_carries_an_internal_link(self):
		supplier = fixtures.make_supplier(email="ncc2@example.com")
		fixtures.make_point(
			reference_doctype="Purchase Invoice",
			users=[make_user()],
			send_email=0,
			send_inapp=0,
			notify_external=1,
			external_subject_template="Hoá đơn {{ doc.name }}",
			external_body_template="<p>Kính gửi {{ ten_doi_tac }}</p>{{ bang_mat_hang() }}",
		)

		invoice = fixtures.make_purchase_invoice(supplier=supplier)

		self.assertNotIn("/app/", last_email(invoice).message)

	def test_missing_party_email_is_skipped_without_breaking_the_document(self):
		supplier = fixtures.make_supplier()
		point = fixtures.make_point(
			reference_doctype="Purchase Invoice",
			users=[make_user()],
			notify_external=1,
			external_subject_template="Hoá đơn {{ doc.name }}",
			external_body_template="<p>x</p>",
		)

		invoice = fixtures.make_purchase_invoice(supplier=supplier)

		rows = logs_for(invoice, point)
		self.assertEqual(invoice.docstatus, 1)
		self.assertEqual(rows[0].status, "Sent")
		self.assertEqual(rows[0].channel_external, 0)
		self.assertIn("chưa có email", rows[0].reason)


class TestTestMode(FrappeTestCase):
	def tearDown(self):
		fixtures.set_settings(test_mode=0, test_email="")

	def test_every_mail_goes_to_the_test_address(self):
		"""AC-12: bật chế độ thử thì NCC không nhận gì."""
		supplier = fixtures.make_supplier(email="ncc-that@example.com")
		fixtures.set_settings(test_mode=1, test_email="thu@miyano.com.vn")
		point = fixtures.make_point(
			reference_doctype="Purchase Invoice",
			users=[make_user()],
			notify_external=1,
			external_subject_template="Hoá đơn {{ doc.name }}",
			external_body_template="<p>x</p>",
		)

		invoice = fixtures.make_purchase_invoice(supplier=supplier)

		recipients = frappe.get_all(
			"Email Queue Recipient",
			filters={
				"parent": (
					"in",
					frappe.get_all("Email Queue", filters={"reference_name": invoice.name}, pluck="name"),
				)
			},
			pluck="recipient",
		)

		self.assertTrue(recipients)
		self.assertEqual(set(recipients), {"thu@miyano.com.vn"})
		self.assertEqual(logs_for(invoice, point)[0].test_mode, 1)

	def test_subject_says_where_the_mail_would_have_gone(self):
		fixtures.set_settings(test_mode=1, test_email="thu@miyano.com.vn")
		user = make_user()
		fixtures.make_point(users=[user])

		order = fixtures.make_sales_order()
		subject = decoded_subject(last_email(order))

		self.assertIn("[THỬ →", subject)
		self.assertIn(frappe.db.get_value("User", user, "email"), subject)


class TestHourlyCap(FrappeTestCase):
	def tearDown(self):
		fixtures.set_settings(hourly_email_cap=200)

	def test_point_over_the_cap_pauses_itself(self):
		"""AC-16: cấu hình sai không được biến thành bão thư."""
		fixtures.set_settings(hourly_email_cap=1)
		point = fixtures.make_point(users=[make_user()])

		first = fixtures.make_sales_order()
		second = fixtures.make_sales_order()

		self.assertEqual(logs_for(first, point)[0].status, "Sent")
		self.assertEqual(logs_for(second, point)[0].status, "Skipped")
		self.assertIn("vượt trần", logs_for(second, point)[0].reason)
		self.assertEqual(frappe.db.get_value("Supply Notification Point", point.name, "enabled"), 0)


class TestFailureHandling(FrappeTestCase):
	def test_smtp_failure_does_not_block_submit(self):
		point = fixtures.make_point(users=[make_user()])

		with patch.object(dispatch_module.frappe, "sendmail", side_effect=RuntimeError("smtp down")):
			order = fixtures.make_sales_order()

		self.assertEqual(order.docstatus, 1)
		self.assertEqual(logs_for(order, point)[0].status, "Failed")

	def test_unknown_point_is_ignored(self):
		order = fixtures.make_sales_order(submit=False)

		dispatch("NTF-KHONG-CO", "Sales Order", order.name)

		self.assertEqual(logs_for(order), [])

	def test_failed_log_can_be_resent(self):
		"""AC-15: sửa xong thì gửi lại được ngay từ nhật ký."""
		point = fixtures.make_point(users=[make_user()])

		with patch.object(dispatch_module.frappe, "sendmail", side_effect=RuntimeError("smtp down")):
			order = fixtures.make_sales_order()

		failed = logs_for(order, point)[0]
		new_log = dispatch_module.resend(failed.name)

		rows = logs_for(order, point)
		self.assertEqual(len(rows), 2)
		self.assertEqual(frappe.db.get_value(LOG_DOCTYPE, new_log, "status"), "Sent")


class TestGlobalSwitch(FrappeTestCase):
	def tearDown(self):
		fixtures.set_settings(enabled=1)

	def test_turning_the_feature_off_stops_everything(self):
		fixtures.set_settings(enabled=0)
		point = fixtures.make_point(users=[make_user()])

		order = fixtures.make_sales_order()

		self.assertEqual(logs_for(order, point), [])
		self.assertEqual(queued_emails(order), 0)
