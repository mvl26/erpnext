# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.supply_notification import dispatch as dispatch_module
from erpnext.supply_notification.dispatch import LOG_DOCTYPE, dispatch
from erpnext.supply_notification.tests import fixtures
from erpnext.supply_notification.tests.test_resolver import make_user


def wire_point(code, users=(), **values):
	point = frappe.get_doc("Supply Notification Point", code)
	point.set("departments", [])
	point.set("users", [])
	for user in users:
		point.append("users", {"user": user})
	point.update(values)
	point.save(ignore_permissions=True)
	return point


def logs_for(doc, milestone="submit"):
	return frappe.get_all(
		LOG_DOCTYPE,
		filters={
			"reference_doctype": doc.doctype,
			"reference_name": doc.name,
			"milestone": milestone,
		},
		fields=[
			"name",
			"status",
			"channel_email",
			"channel_inapp",
			"channel_external",
			"recipients",
			"external_recipients",
			"remark",
		],
	)


def queued_emails(doc):
	return frappe.db.count("Email Queue", {"reference_doctype": doc.doctype, "reference_name": doc.name})


class TestDispatchOnSubmit(FrappeTestCase):
	def test_submitting_sends_email_and_in_app_notification(self):
		user = make_user()
		wire_point("NTF-01", users=[user], notify_owner=0)

		order = fixtures.make_sales_order()

		rows = logs_for(order)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0].status, "Sent")
		self.assertEqual(rows[0].channel_email, 1)
		self.assertEqual(rows[0].channel_inapp, 1)
		self.assertEqual(queued_emails(order), 1)
		self.assertTrue(
			frappe.db.exists(
				"Notification Log",
				{"document_type": "Sales Order", "document_name": order.name, "for_user": user},
			)
		)

	def test_in_app_notification_is_an_alert_so_frappe_adds_no_second_email(self):
		user = make_user()
		wire_point("NTF-01", users=[user], notify_owner=0)

		order = fixtures.make_sales_order()

		self.assertEqual(
			frappe.db.get_value(
				"Notification Log",
				{"document_type": "Sales Order", "document_name": order.name, "for_user": user},
				"type",
			),
			"Alert",
		)
		self.assertEqual(queued_emails(order), 1)

	def test_repeated_dispatch_does_not_send_twice(self):
		wire_point("NTF-01", users=[make_user()], notify_owner=0)
		order = fixtures.make_sales_order()

		dispatch("NTF-01", "Sales Order", order.name)
		dispatch("NTF-01", "Sales Order", order.name)

		self.assertEqual(len(logs_for(order)), 1)
		self.assertEqual(queued_emails(order), 1)

	def test_disabled_point_sends_nothing(self):
		wire_point("NTF-02", users=[make_user()], enabled=0)

		request = fixtures.make_material_request()

		self.assertEqual(logs_for(request), [])
		self.assertEqual(queued_emails(request), 0)

	def test_transfer_request_never_reaches_the_purchase_point(self):
		wire_point("NTF-02", users=[make_user()], enabled=1)

		request = fixtures.make_material_request(request_type="Material Transfer")

		self.assertEqual(logs_for(request), [])

	def test_point_without_recipients_is_logged_as_skipped(self):
		wire_point("NTF-01", users=[], notify_owner=0)

		order = fixtures.make_sales_order()

		rows = logs_for(order)
		self.assertEqual(rows[0].status, "Skipped")
		self.assertIn("Không có người nhận", rows[0].remark)


class TestDispatchExternal(FrappeTestCase):
	def test_missing_party_email_is_skipped_without_breaking_the_document(self):
		fixtures.ensure_supplier(email="")
		wire_point("NTF-05", users=[make_user()], notify_external=1)

		invoice = fixtures.make_purchase_invoice()

		rows = logs_for(invoice)
		self.assertEqual(invoice.docstatus, 1)
		self.assertEqual(rows[0].status, "Sent")
		self.assertEqual(rows[0].channel_external, 0)
		self.assertIn("chưa có email", rows[0].remark)

	def test_party_email_gets_its_own_message(self):
		fixtures.ensure_supplier(email="ncc@example.com")
		wire_point("NTF-05", users=[make_user()], notify_external=1)

		invoice = fixtures.make_purchase_invoice()

		rows = logs_for(invoice)
		self.assertEqual(rows[0].channel_external, 1)
		self.assertEqual(rows[0].external_recipients, "ncc@example.com")
		self.assertEqual(queued_emails(invoice), 2)

	def tearDown(self):
		fixtures.ensure_supplier(email="")


class TestDispatchNeverBreaksSubmit(FrappeTestCase):
	def test_queueing_failure_does_not_block_submit(self):
		wire_point("NTF-01", users=[make_user()])

		with patch.object(dispatch_module.frappe, "sendmail", side_effect=RuntimeError("smtp down")):
			order = fixtures.make_sales_order()

		self.assertEqual(order.docstatus, 1)
		self.assertEqual(logs_for(order)[0].status, "Failed")

	def test_unknown_point_is_ignored(self):
		order = fixtures.make_sales_order(submit=False)
		order.name = "SO-KHONG-CO"

		dispatch("NTF-KHONG-CO", "Sales Order", order.name)

		self.assertEqual(logs_for(order), [])
