# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.supply_notification.reminders import send_due_reminders
from erpnext.supply_notification.tests import fixtures
from erpnext.supply_notification.tests.test_dispatch import logs_for, wire_point
from erpnext.supply_notification.tests.test_resolver import make_user


class TestDueReminders(FrappeTestCase):
	def setUp(self):
		self.user = make_user()
		wire_point("NTF-06", users=[self.user], enabled=1)
		wire_point("NTF-08", users=[self.user], enabled=1)

	def test_purchase_invoice_due_in_seven_days_is_reminded(self):
		invoice = fixtures.make_purchase_invoice(due_in_days=7)

		send_due_reminders()

		rows = logs_for(invoice, milestone="d7")
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0].status, "Sent")

	def test_sales_invoice_uses_its_own_point(self):
		invoice = fixtures.make_sales_invoice(due_in_days=3)

		send_due_reminders()

		rows = frappe.get_all(
			"Supply Notification Dispatch Log",
			filters={"reference_name": invoice.name, "milestone": "d3"},
			fields=["point", "status"],
		)
		self.assertEqual([(r.point, r.status) for r in rows], [("NTF-08", "Sent")])

	def test_dates_between_the_milestones_are_left_alone(self):
		invoice = fixtures.make_purchase_invoice(due_in_days=5)

		send_due_reminders()

		self.assertEqual(logs_for(invoice, milestone="d5"), [])
		self.assertEqual(logs_for(invoice, milestone="d7"), [])

	def test_settled_invoice_is_not_reminded(self):
		invoice = fixtures.make_purchase_invoice(due_in_days=3)
		frappe.db.set_value("Purchase Invoice", invoice.name, "outstanding_amount", 0)

		send_due_reminders()

		self.assertEqual(logs_for(invoice, milestone="d3"), [])

	def test_running_twice_in_a_day_does_not_remind_twice(self):
		invoice = fixtures.make_purchase_invoice(due_in_days=1)

		send_due_reminders()
		send_due_reminders()

		self.assertEqual(len(logs_for(invoice, milestone="d1")), 1)

	def test_disabled_point_stops_only_its_own_reminders(self):
		wire_point("NTF-06", users=[self.user], enabled=0)
		purchase = fixtures.make_purchase_invoice(due_in_days=7)
		sales = fixtures.make_sales_invoice(due_in_days=7)

		send_due_reminders()

		self.assertEqual(logs_for(purchase, milestone="d7"), [])
		self.assertEqual(len(logs_for(sales, milestone="d7")), 1)
