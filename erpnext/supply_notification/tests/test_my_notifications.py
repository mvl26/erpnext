# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Trang *Thông báo của tôi*: tự xem mình nhận gì, tự tắt điểm được phép tắt."""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.supply_notification import my_notifications, registry, resolver
from erpnext.supply_notification.tests import fixtures
from erpnext.supply_notification.tests.test_resolver import make_user


class TestMyPoints(FrappeTestCase):
	def test_lists_the_points_the_user_receives(self):
		user = make_user()
		point = fixtures.make_point(users=[user], allow_opt_out=1)

		rows = {row["point"]: row for row in my_notifications.points_for_user(user)}

		self.assertIn(point.name, rows)
		self.assertTrue(rows[point.name]["allow_opt_out"])
		self.assertFalse(rows[point.name]["opted_out"])

	def test_points_of_other_people_are_not_listed(self):
		point = fixtures.make_point(users=[make_user()], notify_owner=0)

		rows = [row["point"] for row in my_notifications.points_for_user(make_user())]

		self.assertNotIn(point.name, rows)

	def test_owner_only_points_are_flagged(self):
		point = fixtures.make_point(users=[], notify_owner=1)

		rows = {row["point"]: row for row in my_notifications.points_for_user(make_user())}

		self.assertTrue(rows[point.name]["only_as_owner"])


class TestSubscription(FrappeTestCase):
	def test_turning_a_point_off_stops_the_mail(self):
		"""AC-14: tắt rồi thì không nhận nữa, bật lại thì nhận lại."""
		user = make_user()
		point = fixtures.make_point(users=[user], allow_opt_out=1)

		frappe.set_user(user)
		try:
			my_notifications.set_subscription(point.name, 0)
			registry.clear_cache()
			self.assertEqual(resolver.resolve(point).users, [])

			my_notifications.set_subscription(point.name, 1)
			self.assertEqual([row.name for row in resolver.resolve(point).users], [user])
		finally:
			frappe.set_user("Administrator")

	def test_mandatory_points_cannot_be_turned_off(self):
		user = make_user()
		point = fixtures.make_point(users=[user], allow_opt_out=0)

		frappe.set_user(user)
		try:
			with self.assertRaises(frappe.ValidationError) as caught:
				my_notifications.set_subscription(point.name, 0)
		finally:
			frappe.set_user("Administrator")

		self.assertIn("bắt buộc", str(caught.exception))

	def test_turning_off_twice_does_not_duplicate_rows(self):
		user = make_user()
		point = fixtures.make_point(users=[user], allow_opt_out=1)

		frappe.set_user(user)
		try:
			my_notifications.set_subscription(point.name, 0)
			my_notifications.set_subscription(point.name, 0)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(
			frappe.db.count("Supply Notification Opt Out", {"user": user, "point": point.name}), 1
		)

	def test_unknown_point_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			my_notifications.set_subscription("NTF-KHONG-CO", 0)
