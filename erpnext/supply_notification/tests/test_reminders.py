# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nhắc theo ngày: mốc trước hạn và quá hạn, giờ chạy theo Cài đặt, chống trùng."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate

from erpnext.supply_notification import reminders
from erpnext.supply_notification.dispatch import LOG_DOCTYPE
from erpnext.supply_notification.tests import fixtures
from erpnext.supply_notification.tests.test_resolver import make_user


def logs_for(doc, point, milestone):
	return frappe.get_all(
		LOG_DOCTYPE,
		filters={
			"point": point.name,
			"reference_doctype": doc.doctype,
			"reference_name": doc.name,
			"milestone": milestone,
		},
		fields=["status"],
	)


def make_reminder_point(offsets="-7, -3, -1", **values):
	values.setdefault("reference_doctype", "Purchase Invoice")
	values.setdefault("users", [make_user()])
	values.setdefault("conditions", [("outstanding_amount", ">", "0")])
	return fixtures.make_point(
		trigger_event="Date Reminder",
		date_field="due_date",
		reminder_offsets=offsets,
		subject_template="Hoá đơn {{ doc.name }} đến hạn",
		**values,
	)


class TestMilestones(FrappeTestCase):
	def test_negative_offset_is_before_the_date(self):
		point = make_reminder_point()
		invoice = fixtures.make_purchase_invoice(due_in_days=7)

		reminders.send_date_reminders()

		self.assertEqual(len(logs_for(invoice, point, "d7")), 1)

	def test_positive_offset_is_overdue(self):
		point = make_reminder_point(offsets="+1")
		invoice = fixtures.make_purchase_invoice(due_in_days=1)
		# ERPNext không cho lập hoá đơn có hạn trước ngày ghi sổ, nên hoá đơn quá
		# hạn phải dựng bằng cách lùi hạn sau khi ghi sổ — đúng như ngoài đời.
		frappe.db.set_value("Purchase Invoice", invoice.name, "due_date", add_days(getdate(), -1))

		reminders.send_date_reminders()

		self.assertEqual(len(logs_for(invoice, point, "q1")), 1)

	def test_dates_between_the_milestones_are_left_alone(self):
		point = make_reminder_point()
		invoice = fixtures.make_purchase_invoice(due_in_days=5)

		reminders.send_date_reminders()

		self.assertEqual(logs_for(invoice, point, "d5"), [])
		self.assertEqual(logs_for(invoice, point, "d7"), [])

	def test_running_twice_in_a_day_does_not_remind_twice(self):
		point = make_reminder_point()
		invoice = fixtures.make_purchase_invoice(due_in_days=1)

		reminders.send_date_reminders()
		reminders.send_date_reminders()

		self.assertEqual(len(logs_for(invoice, point, "d1")), 1)

	def test_milestone_names_stay_compatible_with_the_old_build(self):
		self.assertEqual(reminders.milestone_for(-7), "d7")
		self.assertEqual(reminders.milestone_for(-1), "d1")
		self.assertEqual(reminders.milestone_for(2), "q2")


class TestConditions(FrappeTestCase):
	def test_settled_invoice_is_not_reminded(self):
		point = make_reminder_point()
		invoice = fixtures.make_purchase_invoice(due_in_days=3)
		frappe.db.set_value("Purchase Invoice", invoice.name, "outstanding_amount", 0)

		reminders.send_date_reminders()

		self.assertEqual(logs_for(invoice, point, "d3"), [])

	def test_disabled_point_stops_only_its_own_reminders(self):
		off = make_reminder_point()
		on = make_reminder_point()
		off.db_set("enabled", 0)

		invoice = fixtures.make_purchase_invoice(due_in_days=7)
		reminders.send_date_reminders()

		self.assertEqual(logs_for(invoice, off, "d7"), [])
		self.assertEqual(len(logs_for(invoice, on, "d7")), 1)

	def test_draft_documents_are_not_reminded(self):
		point = make_reminder_point()
		invoice = fixtures.make_purchase_invoice(due_in_days=7, submit=False)

		reminders.send_date_reminders()

		self.assertEqual(logs_for(invoice, point, "d7"), [])


class TestSchedule(FrappeTestCase):
	def tearDown(self):
		fixtures.set_settings(reminder_hour=8, enabled=1)

	def test_hourly_job_only_runs_at_the_configured_hour(self):
		import datetime

		fixtures.set_settings(reminder_hour=8)

		with patch.object(reminders, "send_date_reminders") as sender:
			with patch.object(reminders, "now_datetime", return_value=datetime.datetime(2026, 9, 23, 14, 5)):
				reminders.run_hourly()

		self.assertEqual(sender.call_count, 0)

	def test_changing_the_hour_needs_no_deploy(self):
		import datetime

		fixtures.set_settings(reminder_hour=15)

		with patch.object(reminders, "send_date_reminders") as sender:
			with patch.object(reminders, "now_datetime", return_value=datetime.datetime(2026, 9, 23, 15, 5)):
				reminders.run_hourly()

		self.assertEqual(sender.call_count, 1)

	def test_feature_switch_stops_the_scan(self):
		import datetime

		fixtures.set_settings(reminder_hour=15, enabled=0)

		with patch.object(reminders, "send_date_reminders") as sender:
			with patch.object(reminders, "now_datetime", return_value=datetime.datetime(2026, 9, 23, 15, 5)):
				reminders.run_hourly()

		self.assertEqual(sender.call_count, 0)


class TestLogRetention(FrappeTestCase):
	def test_automatic_logs_expire_but_manual_ones_stay(self):
		point = make_reminder_point()
		invoice = fixtures.make_purchase_invoice(due_in_days=1)
		reminders.send_date_reminders()

		log = frappe.get_all(LOG_DOCTYPE, filters={"point": point.name}, pluck="name")[0]
		frappe.db.set_value(LOG_DOCTYPE, log, "creation", add_days(getdate(), -400), update_modified=False)

		manual = frappe.get_doc(
			{
				"doctype": LOG_DOCTYPE,
				"point": point.name,
				"reference_doctype": "Purchase Invoice",
				"reference_name": invoice.name,
				"milestone": "manual",
				"is_manual": 1,
				"status": "Sent",
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value(
			LOG_DOCTYPE, manual.name, "creation", add_days(getdate(), -400), update_modified=False
		)

		fixtures.set_settings(auto_log_retention_days=180, manual_log_retention_days=0)
		reminders.clear_old_dispatch_logs()

		self.assertFalse(frappe.db.exists(LOG_DOCTYPE, log))
		self.assertTrue(frappe.db.exists(LOG_DOCTYPE, manual.name))
