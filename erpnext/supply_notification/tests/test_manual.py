# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nút gửi thủ công trên chứng từ — kịch bản CR_01 AC1…AC6."""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.supply_notification import manual
from erpnext.supply_notification.tests import fixtures
from erpnext.supply_notification.tests.test_resolver import make_user


def make_send_to_supplier_point(**values):
	"""Điểm kiểu NTF-13: Purchase Order · Thủ công · chỉ gửi ra ngoài."""
	values.setdefault("conditions", [("status", "≠", "Closed")])
	return fixtures.make_point(
		reference_doctype="Purchase Order",
		trigger_event="Manual",
		button_label="Gửi cho NCC",
		manual_docstatus="Đã ghi sổ",
		send_email=0,
		send_inapp=0,
		notify_external=1,
		external_party_contact=1,
		party_field="supplier_name",
		main_date_field="transaction_date",
		subject_prefix="[Miyano]",
		subject_template="",
		external_subject_template="Đơn mua hàng {{ doc.name }} – đề nghị xác nhận",
		external_body_template="<p>Kính gửi {{ ten_doi_tac }}</p>{{ bang_mat_hang() }}",
		**values,
	)


class TestButtonVisibility(FrappeTestCase):
	def test_button_shows_on_a_submitted_order(self):
		point = make_send_to_supplier_point()
		order = fixtures.make_purchase_order(supplier=fixtures.make_supplier(email="ncc@example.com"))

		buttons = manual.get_buttons("Purchase Order", order.name)

		self.assertIn(point.name, [row["point"] for row in buttons])
		self.assertEqual([row["label"] for row in buttons if row["point"] == point.name], ["Gửi cho NCC"])

	def test_draft_order_has_no_button(self):
		point = make_send_to_supplier_point()
		order = fixtures.make_purchase_order(submit=False)

		buttons = manual.get_buttons("Purchase Order", order.name)

		self.assertNotIn(point.name, [row["point"] for row in buttons])

	def test_cancelled_order_has_no_button(self):
		point = make_send_to_supplier_point()
		order = fixtures.make_purchase_order()
		order.cancel()

		self.assertNotIn(
			point.name, [row["point"] for row in manual.get_buttons("Purchase Order", order.name)]
		)

	def test_condition_hides_the_button(self):
		"""D29: PO đã đóng (Closed) thì không gửi được nữa."""
		point = make_send_to_supplier_point()
		order = fixtures.make_purchase_order()
		order.db_set("status", "Closed")

		self.assertNotIn(
			point.name, [row["point"] for row in manual.get_buttons("Purchase Order", order.name)]
		)


class TestApiGuards(FrappeTestCase):
	def test_api_refuses_a_draft_order(self):
		"""AC1: gọi thẳng API vẫn bị từ chối, không chỉ ẩn nút."""
		point = make_send_to_supplier_point()
		order = fixtures.make_purchase_order(submit=False)

		with self.assertRaises(frappe.ValidationError):
			manual.send(point.name, "Purchase Order", order.name)

	def test_api_refuses_a_closed_order(self):
		point = make_send_to_supplier_point()
		order = fixtures.make_purchase_order()
		order.db_set("status", "Closed")

		with self.assertRaises(frappe.ValidationError):
			manual.send(point.name, "Purchase Order", order.name)

	def test_api_refuses_a_point_of_another_doctype(self):
		point = fixtures.make_point(users=[make_user()], trigger_event="Manual", button_label="Thử")
		order = fixtures.make_purchase_order()

		with self.assertRaises(frappe.ValidationError):
			manual.send(point.name, "Purchase Order", order.name)

	def test_api_refuses_when_the_supplier_has_no_email(self):
		"""AC6: báo rõ, không gửi thư trống."""
		point = make_send_to_supplier_point()
		order = fixtures.make_purchase_order(supplier=fixtures.make_supplier())

		before = frappe.db.count("Email Queue")
		with self.assertRaises(frappe.ValidationError):
			manual.send(point.name, "Purchase Order", order.name)

		self.assertEqual(frappe.db.count("Email Queue"), before)


class TestConfirmation(FrappeTestCase):
	def test_confirmation_lists_recipients_and_preview(self):
		point = make_send_to_supplier_point()
		supplier = fixtures.make_supplier(email="ncc@example.com")
		order = fixtures.make_purchase_order(supplier=supplier)

		box = manual.get_confirmation(point.name, "Purchase Order", order.name)

		self.assertEqual(box["to"], ["ncc@example.com"])
		self.assertIn("Đơn mua hàng", box["subject"])
		self.assertIn("Kính gửi", box["body"])
		self.assertFalse(box["blocked"])
		self.assertEqual(box["count"], 0)

	def test_confirmation_blocks_and_explains_when_there_is_no_email(self):
		point = make_send_to_supplier_point()
		order = fixtures.make_purchase_order(supplier=fixtures.make_supplier())

		box = manual.get_confirmation(point.name, "Purchase Order", order.name)

		self.assertTrue(box["blocked"])
		self.assertTrue(any("chưa có email" in warning for warning in box["warnings"]))

	def test_confirmation_warns_about_an_address_without_a_receiver(self):
		point = make_send_to_supplier_point(address_field="shipping_address")
		address = fixtures.ensure_address(title="Kho khong nguoi nhan", phone="")
		order = fixtures.make_purchase_order(
			supplier=fixtures.make_supplier(email="ncc@example.com"), shipping_address=address
		)

		box = manual.get_confirmation(point.name, "Purchase Order", order.name)

		self.assertTrue(any("người nhận" in warning for warning in box["warnings"]))


class TestSending(FrappeTestCase):
	def test_each_press_sends_again_and_history_counts(self):
		"""AC5: gửi hai lần thì có hai dòng nhật ký và chỉ báo đúng số lần."""
		point = make_send_to_supplier_point()
		order = fixtures.make_purchase_order(supplier=fixtures.make_supplier(email="ncc@example.com"))

		first = manual.send(point.name, "Purchase Order", order.name)
		second = manual.send(point.name, "Purchase Order", order.name)

		self.assertEqual(first["count"], 1)
		self.assertEqual(second["count"], 2)
		self.assertIn("Đã gửi 2 lần", second["summary"])

		logs = frappe.get_all(
			"Supply Notification Dispatch Log",
			filters={"point": point.name, "reference_name": order.name},
			fields=["status", "is_manual", "triggered_by", "external_recipients"],
		)
		self.assertEqual(len(logs), 2)
		self.assertTrue(all(row.is_manual for row in logs))
		self.assertTrue(all(row.triggered_by == frappe.session.user for row in logs))
		self.assertTrue(all(row.external_recipients == "ncc@example.com" for row in logs))

	def test_the_supplier_mail_carries_the_item_table_and_no_internal_link(self):
		"""AC2: đủ nội dung, không có đường dẫn nội bộ, không đính kèm (D23)."""
		point = make_send_to_supplier_point()
		order = fixtures.make_purchase_order(supplier=fixtures.make_supplier(email="ncc@example.com"))

		manual.send(point.name, "Purchase Order", order.name)

		queue = frappe.get_all(
			"Email Queue",
			filters={"reference_doctype": "Purchase Order", "reference_name": order.name},
			fields=["name", "message", "attachments"],
			order_by="creation desc",
			limit=1,
		)[0]

		self.assertIn(fixtures.ITEM_CODE, queue.message)
		self.assertNotIn("/app/", queue.message)
		self.assertIn(queue.attachments or "[]", ("[]", "", None))

	def test_reply_to_goes_back_to_the_creator(self):
		"""AC4: NCC bấm Trả lời thì thư về người tạo PO."""
		point = make_send_to_supplier_point(reply_to_mode="Người tạo chứng từ", cc_owner=1)
		order = fixtures.make_purchase_order(supplier=fixtures.make_supplier(email="ncc@example.com"))
		# Người tạo trong test là Administrator — tài khoản hệ thống không bao giờ là
		# người nhận nghiệp vụ, nên đặt người tạo là một nhân sự thật.
		creator = make_user()
		frappe.db.set_value("Purchase Order", order.name, "owner", creator)

		manual.send(point.name, "Purchase Order", order.name)

		owner_email = frappe.db.get_value("User", creator, "email")
		log = frappe.get_all(
			"Supply Notification Dispatch Log",
			filters={"point": point.name, "reference_name": order.name},
			fields=["cc"],
		)[0]

		self.assertEqual(log.cc, owner_email)

	def test_manual_send_is_blocked_by_the_global_switch(self):
		point = make_send_to_supplier_point()
		order = fixtures.make_purchase_order(supplier=fixtures.make_supplier(email="ncc@example.com"))
		fixtures.set_settings(enabled=0)

		try:
			with self.assertRaises(frappe.ValidationError):
				manual.send(point.name, "Purchase Order", order.name)
		finally:
			fixtures.set_settings(enabled=1)
