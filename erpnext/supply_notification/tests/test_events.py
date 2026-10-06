# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Bộ máy sự kiện chung: 5 loại thời điểm tự động và lối thoát sớm."""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.supply_notification import constants, events, registry
from erpnext.supply_notification.dispatch import LOG_DOCTYPE
from erpnext.supply_notification.tests import fixtures
from erpnext.supply_notification.tests.test_resolver import make_user


def logs_for(doc, point=None):
	filters = {"reference_doctype": doc.doctype, "reference_name": doc.name}
	if point:
		filters["point"] = point
	return frappe.get_all(LOG_DOCTYPE, filters=filters, fields=["point", "status", "milestone"])


class TestDocumentEvents(FrappeTestCase):
	def test_submit_fires_the_point(self):
		point = fixtures.make_point(users=[make_user()])

		order = fixtures.make_sales_order()

		self.assertEqual([row.milestone for row in logs_for(order, point.name)], ["submit"])

	def test_create_fires_a_new_point(self):
		point = fixtures.make_point(users=[make_user()], trigger_event=constants.NEW)

		order = fixtures.make_sales_order(submit=False)

		self.assertEqual([row.milestone for row in logs_for(order, point.name)], ["new"])

	def test_cancel_fires_a_cancel_point(self):
		point = fixtures.make_point(users=[make_user()], trigger_event=constants.CANCEL)

		order = fixtures.make_sales_order()
		order.cancel()

		self.assertEqual([row.milestone for row in logs_for(order, point.name)], ["cancel"])

	def test_conditions_decide_whether_the_point_fires(self):
		point = fixtures.make_point(
			reference_doctype="Material Request",
			users=[make_user()],
			conditions=[("material_request_type", "=", "Purchase")],
		)

		matching = fixtures.make_material_request(request_type="Purchase")
		other = fixtures.make_material_request(request_type="Material Transfer")

		self.assertEqual(len(logs_for(matching, point.name)), 1)
		self.assertEqual(logs_for(other, point.name), [])

	def test_disabled_point_never_fires(self):
		point = fixtures.make_point(users=[make_user()], enabled=0)

		order = fixtures.make_sales_order()

		self.assertEqual(logs_for(order, point.name), [])


class TestValueChange(FrappeTestCase):
	def test_fires_only_when_the_watched_field_really_changes(self):
		point = fixtures.make_point(
			users=[make_user()],
			trigger_event=constants.VALUE_CHANGE,
			watch_field="status",
		)

		# Ghi sổ đã đổi status (Draft → To Deliver and Bill) nên tự nó là một lần bắn
		# đúng nghĩa; phép đo ở đây là phần TĂNG THÊM sau mỗi lần đổi.
		order = fixtures.make_sales_order()
		baseline = len(logs_for(order, point.name))

		order.db_set("status", "On Hold")
		after_change = len(logs_for(order, point.name))

		order.db_set("status", "On Hold")
		after_same_value = len(logs_for(order, point.name))

		self.assertEqual(after_change, baseline + 1)
		self.assertEqual(after_same_value, baseline + 1)

	def test_target_value_narrows_the_trigger(self):
		point = fixtures.make_point(
			users=[make_user()],
			trigger_event=constants.VALUE_CHANGE,
			watch_field="status",
			watch_value="Closed",
		)

		order = fixtures.make_sales_order()
		order.db_set("status", "On Hold")
		self.assertEqual(logs_for(order, point.name), [])

		order.db_set("status", "Closed")
		self.assertEqual(len(logs_for(order, point.name)), 1)

	def test_db_set_is_what_erpnext_uses_so_on_change_is_the_right_hook(self):
		"""Trạng thái chứng từ được ghi bằng db_set — on_update sẽ không bao giờ thấy."""
		point = fixtures.make_point(
			users=[make_user()],
			trigger_event=constants.VALUE_CHANGE,
			watch_field="per_delivered",
		)

		order = fixtures.make_sales_order()
		baseline = len(logs_for(order, point.name))

		order.db_set("per_delivered", 50)

		self.assertEqual(len(logs_for(order, point.name)), baseline + 1)

	def test_filling_an_empty_number_with_zero_is_not_a_change(self):
		"""Ghi sổ điền 0 vào hàng loạt trường số — đó không phải thay đổi nghiệp vụ."""
		point = fixtures.make_point(
			users=[make_user()],
			trigger_event=constants.VALUE_CHANGE,
			watch_field="per_delivered",
		)

		order = fixtures.make_sales_order()

		self.assertEqual(logs_for(order, point.name), [])


class TestWorkflowTransition(FrappeTestCase):
	def test_point_fires_when_the_document_reaches_the_chosen_state(self):
		fieldname = events.workflow_state_field("Sales Order")
		if not fieldname:
			self.skipTest("Site không có Workflow đang bật trên Sales Order")

		states = frappe.get_all(
			"Workflow Document State",
			filters={
				"parent": frappe.db.get_value("Workflow", {"document_type": "Sales Order", "is_active": 1})
			},
			pluck="state",
			order_by="idx desc",
		)
		target = states[0]

		point = fixtures.make_point(
			users=[make_user()],
			trigger_event=constants.WORKFLOW_TRANSITION,
			workflow_state=target,
		)

		order = fixtures.make_sales_order(submit=False)
		order.db_set(fieldname, target)

		rows = logs_for(order, point.name)
		self.assertEqual([row.milestone for row in rows], [f"wf:{target}"])

	def test_other_states_do_not_fire(self):
		fieldname = events.workflow_state_field("Sales Order")
		if not fieldname:
			self.skipTest("Site không có Workflow đang bật trên Sales Order")

		point = fixtures.make_point(
			users=[make_user()],
			trigger_event=constants.WORKFLOW_TRANSITION,
			workflow_state="Trạng thái không có thật",
		)

		order = fixtures.make_sales_order(submit=False)
		order.db_set(fieldname, "Draft")

		self.assertEqual(logs_for(order, point.name), [])


class TestEarlyExit(FrappeTestCase):
	def test_doctype_without_points_is_skipped(self):
		registry.clear_cache()
		self.assertFalse(registry.has_points("ToDo"))

	def test_cache_notices_a_new_point(self):
		registry.clear_cache()
		self.assertFalse(registry.has_points("Journal Entry"))

		fixtures.make_point(reference_doctype="Journal Entry", users=[make_user()])

		self.assertTrue(registry.has_points("Journal Entry"))

	def test_blocked_doctypes_are_refused_at_configuration_time(self):
		with self.assertRaises(frappe.ValidationError):
			fixtures.make_point(reference_doctype="Email Queue", users=[make_user()])

	def test_notification_never_blocks_the_document(self):
		"""Lỗi trong bộ máy chỉ ghi Error Log, chứng từ vẫn ghi sổ được (BR1)."""
		point = fixtures.make_point(users=[make_user()])
		frappe.db.set_value("Supply Notification Point", point.name, "watch_field", "khong_co")

		order = fixtures.make_sales_order()

		self.assertEqual(order.docstatus, 1)
