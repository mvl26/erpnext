# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tự kiểm trước khi bật: xem trước, gửi thử, danh sách trường để chèn."""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.supply_notification import preview
from erpnext.supply_notification.tests import fixtures
from erpnext.supply_notification.tests.test_resolver import make_user


class TestPreviewEmail(FrappeTestCase):
	def test_preview_uses_a_real_document_and_does_not_send(self):
		point = fixtures.make_point(
			users=[make_user()],
			party_field="customer_name",
			body_template="<p>Khách {{ ten_doi_tac }}</p>{{ bang_mat_hang() }}",
		)
		order = fixtures.make_sales_order(submit=False)
		before = frappe.db.count("Email Queue")

		result = preview.preview_email(name=point.name, reference=order.name)

		self.assertEqual(result["reference"], order.name)
		self.assertIn(fixtures.CUSTOMER, result["internal"]["body"])
		self.assertIn(fixtures.ITEM_CODE, result["internal"]["body"])
		self.assertEqual(frappe.db.count("Email Queue"), before)

	def test_preview_works_on_a_form_that_has_not_been_saved(self):
		"""Người dùng thấy đúng cái mình vừa gõ, không phải lưu rồi mới biết sai."""
		point = fixtures.make_point(users=[make_user()])
		order = fixtures.make_sales_order(submit=False)

		draft = point.as_dict()
		draft["subject_template"] = "Bản nháp {{ doc.name }}"

		result = preview.preview_email(point_json=json.dumps(draft, default=str), reference=order.name)

		self.assertIn("Bản nháp", result["internal"]["subject"])

	def test_preview_of_a_reminder_point_fills_the_days_left_variable(self):
		point = fixtures.make_point(
			reference_doctype="Purchase Invoice",
			users=[make_user()],
			trigger_event="Date Reminder",
			date_field="due_date",
			reminder_offsets="-7",
			subject_template="Còn {{ so_ngay_con_lai }} ngày",
			conditions=[("outstanding_amount", ">", "0")],
		)
		invoice = fixtures.make_purchase_invoice()

		result = preview.preview_email(name=point.name, reference=invoice.name)

		self.assertIn("Còn 7 ngày", result["internal"]["subject"])

	def test_preview_reports_when_there_is_nothing_to_preview_with(self):
		point = fixtures.make_point(reference_doctype="Journal Entry", users=[make_user()])

		result = preview.preview_email(name=point.name, reference="KHONG-CO")

		self.assertTrue(result.get("error") or result.get("reference"))


class TestSendTestToMe(FrappeTestCase):
	def test_test_mail_goes_only_to_the_person_pressing_it(self):
		"""AC-11: tiêu đề [THỬ], không có dòng nhật ký nghiệp vụ."""
		point = fixtures.make_point(users=[make_user()])
		order = fixtures.make_sales_order(submit=False)
		logs_before = frappe.db.count("Supply Notification Dispatch Log", {"point": point.name})

		result = preview.send_test_to_me(name=point.name, reference=order.name)

		self.assertEqual(result["email"], frappe.db.get_value("User", frappe.session.user, "email"))
		self.assertEqual(
			frappe.db.count("Supply Notification Dispatch Log", {"point": point.name}), logs_before
		)


class TestFieldOptions(FrappeTestCase):
	def test_options_list_parent_and_child_fields_with_labels(self):
		options = preview.field_options("Sales Order")
		values = [row["value"] for row in options]

		self.assertIn("customer_name", values)
		self.assertIn("items.item_code", values)

	def test_options_can_be_narrowed_by_fieldtype(self):
		options = preview.field_options("Purchase Invoice", only_types="Date")
		values = [row["value"] for row in options]

		self.assertIn("due_date", values)
		self.assertNotIn("supplier_name", values)

	def test_builtin_variables_are_offered_too(self):
		values = [row["value"] for row in preview.field_options("Sales Order")]

		self.assertIn("ten_doi_tac", values)
		self.assertIn("so_tien", values)

	def test_unknown_doctype_returns_nothing(self):
		self.assertEqual(preview.field_options("Không Có DocType"), [])


class TestHelpers(FrappeTestCase):
	def test_suggested_code_follows_the_existing_series(self):
		code = preview.suggest_code()

		self.assertRegex(code, r"^NTF-\d{2,}$")
		self.assertFalse(frappe.db.exists("Supply Notification Point", code))

	def test_statistics_count_sent_and_failed(self):
		point = fixtures.make_point(users=[make_user()])
		fixtures.make_sales_order()

		stats = preview.point_stats(point.name)

		self.assertEqual(stats["total"], 1)
		self.assertEqual(stats["sent"], 1)
		self.assertEqual(stats["failure_rate"], 0)

	def test_workflow_states_are_listed_for_documents_that_have_a_workflow(self):
		states = preview.workflow_states("Sales Order")
		if not states:
			self.skipTest("Site không có Workflow đang bật trên Sales Order")

		self.assertTrue(all(isinstance(state, str) for state in states))
		self.assertEqual(preview.workflow_states("Item"), [])
