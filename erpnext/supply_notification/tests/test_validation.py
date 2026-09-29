# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Kiểm khi lưu điểm thông báo — V1…V8 của BA mục 6.4.

Giá trị của những kiểm này là chặn sai sót **trước khi** nó thành thư gửi nhầm
hoặc thư không bao giờ gửi, và nói bằng tiếng Việt có gợi ý sửa.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.supply_notification.tests import fixtures
from erpnext.supply_notification.tests.test_resolver import make_user


def error_of(test, **values) -> str:
	with test.assertRaises(frappe.ValidationError) as caught:
		fixtures.make_point(**values)
	return str(caught.exception)


class TestTemplateChecks(FrappeTestCase):
	def test_v1_broken_syntax_is_refused(self):
		message = error_of(self, users=[make_user()], subject_template="{{ doc.name ")

		self.assertIn("lỗi cú pháp", message)

	def test_v2_unknown_variable_is_refused(self):
		message = error_of(self, users=[make_user()], subject_template="{{ khong_co_bien }}")

		self.assertIn("không có biến", message)

	def test_v2_unknown_field_is_refused_with_a_suggestion(self):
		message = error_of(self, users=[make_user()], subject_template="{{ doc.customer_nam }}")

		self.assertIn("customer_nam", message)
		self.assertIn("Có phải ý bạn là customer_name", message)

	def test_v2_accepts_a_real_field(self):
		point = fixtures.make_point(users=[make_user()], subject_template="{{ doc.customer_name }}")

		self.assertTrue(point.name)


class TestConditionChecks(FrappeTestCase):
	def test_v3_unknown_field_in_a_condition_is_refused(self):
		message = error_of(
			self,
			users=[make_user()],
			conditions=[("customer_nam", "=", "X")],
		)

		self.assertIn("không có trên", message)

	def test_v3_value_outside_a_select_list_is_refused(self):
		message = error_of(
			self,
			reference_doctype="Material Request",
			users=[make_user()],
			conditions=[("material_request_type", "=", "Mua")],
		)

		self.assertIn("Chọn một trong", message)
		self.assertIn("Purchase", message)

	def test_v3_child_table_condition_is_accepted(self):
		point = fixtures.make_point(
			users=[make_user()],
			conditions=[("items.item_code", "=", fixtures.ensure_item())],
		)

		self.assertTrue(point.name)

	def test_v3_condition_without_a_value_is_refused(self):
		message = error_of(self, users=[make_user()], conditions=[("customer_name", "=", "")])

		self.assertIn("chưa điền giá trị", message)


class TestExternalContentChecks(FrappeTestCase):
	def test_v4_internal_block_in_external_content_is_refused(self):
		message = error_of(
			self,
			users=[make_user()],
			notify_external=1,
			external_party_contact=1,
			external_subject_template="Thư gửi NCC {{ doc.name }}",
			external_body_template="{{ nut_mo_chung_tu() }}",
		)

		self.assertIn("chỉ dùng cho email nội bộ", message)

	def test_v4_internal_link_in_external_content_is_refused(self):
		message = error_of(
			self,
			users=[make_user()],
			notify_external=1,
			external_party_contact=1,
			external_subject_template="Thư gửi NCC {{ doc.name }}",
			external_body_template='<a href="/app/sales-order">Mở</a>',
		)

		self.assertIn("đường dẫn nội bộ", message)

	def test_v4_internal_snippet_in_external_content_is_refused(self):
		snippet = fixtures.make_snippet(content="<p>Nội bộ</p>", scope="Nội bộ")
		message = error_of(
			self,
			users=[make_user()],
			notify_external=1,
			external_party_contact=1,
			external_subject_template="Thư gửi NCC {{ doc.name }}",
			external_body_template=f'{{{{ mau("{snippet}") }}}}',
		)

		self.assertIn("chỉ dùng cho nội bộ", message)

	def test_v4_unknown_snippet_is_refused(self):
		message = error_of(
			self,
			users=[make_user()],
			notify_external=1,
			external_party_contact=1,
			external_subject_template="Thư gửi NCC {{ doc.name }}",
			external_body_template='{{ mau("Mẫu không tồn tại") }}',
		)

		self.assertIn("Không có mẫu dùng chung", message)


class TestChannelChecks(FrappeTestCase):
	def test_v5_enabled_point_without_a_channel_is_refused(self):
		message = error_of(self, users=[make_user()], send_email=0, send_inapp=0)

		self.assertIn("ít nhất một kênh", message)

	def test_v5_internal_channel_without_recipients_is_refused(self):
		message = error_of(self, users=[], notify_owner=0)

		self.assertIn("chưa chọn người nhận", message)

	def test_v5_external_channel_without_a_source_is_refused(self):
		message = error_of(
			self,
			users=[make_user()],
			notify_external=1,
			external_party_contact=0,
			external_subject_template="Thư {{ doc.name }}",
		)

		self.assertIn("chưa chọn nguồn người nhận ngoài", message)


class TestTriggerChecks(FrappeTestCase):
	def test_v7_reminder_without_a_date_field_is_refused(self):
		message = error_of(
			self,
			reference_doctype="Purchase Invoice",
			users=[make_user()],
			trigger_event="Date Reminder",
			reminder_offsets="-7",
		)

		self.assertIn("Chọn trường ngày", message)

	def test_v7_reminder_with_a_bad_milestone_is_refused(self):
		message = error_of(
			self,
			reference_doctype="Purchase Invoice",
			users=[make_user()],
			trigger_event="Date Reminder",
			date_field="due_date",
			reminder_offsets="bảy ngày",
		)

		self.assertIn("không phải số", message)

	def test_v7_manual_point_needs_a_button_label(self):
		message = error_of(
			self,
			reference_doctype="Purchase Order",
			users=[make_user()],
			trigger_event="Manual",
		)

		self.assertIn("nhãn cho nút", message)

	def test_v7_value_change_needs_an_existing_field(self):
		message = error_of(
			self,
			users=[make_user()],
			trigger_event="Value Change",
			watch_field="khong_co_truong",
		)

		self.assertIn("không có trên", message)

	def test_submit_point_on_a_non_submittable_doctype_is_refused(self):
		message = error_of(self, reference_doctype="Item", users=[make_user()])

		self.assertIn("không phải chứng từ ghi sổ", message)


class TestDoctypeChecks(FrappeTestCase):
	def test_v8_blocked_doctype_is_refused(self):
		message = error_of(self, reference_doctype="Notification Log", users=[make_user()])

		self.assertIn("chứng từ hệ thống", message)

	def test_v8_child_table_is_refused(self):
		message = error_of(self, reference_doctype="Sales Order Item", users=[make_user()])

		self.assertIn("bảng con", message)

	def test_v8_single_doctype_is_refused(self):
		message = error_of(self, reference_doctype="Stock Settings", users=[make_user()])

		self.assertIn("bản ghi cài đặt", message)


class TestPrintFormatCheck(FrappeTestCase):
	def test_v6_print_format_must_belong_to_the_document(self):
		other = frappe.get_all("Print Format", filters={"doc_type": "Sales Invoice"}, pluck="name", limit=1)
		if not other:
			self.skipTest("Site không có mẫu in của Sales Invoice để thử")

		message = error_of(
			self,
			reference_doctype="Purchase Order",
			users=[make_user()],
			notify_external=1,
			external_party_contact=1,
			external_subject_template="Thư {{ doc.name }}",
			attach_pdf=1,
			print_format=other[0],
		)

		self.assertIn("không dùng được cho", message)


class TestDeletionRules(FrappeTestCase):
	def test_seed_point_cannot_be_deleted(self):
		"""D20: điểm hạt giống chỉ tắt được, không xoá được."""
		with self.assertRaises(frappe.ValidationError) as caught:
			frappe.delete_doc("Supply Notification Point", "NTF-01")

		self.assertIn("Hãy tắt điểm thay vì xoá", str(caught.exception))

	def test_point_with_history_cannot_be_deleted(self):
		point = fixtures.make_point(users=[make_user()])
		fixtures.make_sales_order()

		with self.assertRaises(frappe.ValidationError) as caught:
			frappe.delete_doc("Supply Notification Point", point.name)

		self.assertIn("đã có lịch sử gửi", str(caught.exception))

	def test_a_fresh_point_can_still_be_deleted(self):
		point = fixtures.make_point(users=[make_user()])

		frappe.delete_doc("Supply Notification Point", point.name)

		self.assertFalse(frappe.db.exists("Supply Notification Point", point.name))
