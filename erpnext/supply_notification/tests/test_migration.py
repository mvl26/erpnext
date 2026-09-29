# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Chuyển đổi 12 điểm cũ (AC-18) và ranh giới code/cấu hình (AC-20)."""

import pathlib
import re

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.supply_notification import constants, content
from erpnext.supply_notification.setup import build_point
from erpnext.supply_notification.tests import fixtures

MODULE_DIR = pathlib.Path(frappe.get_app_path("erpnext", "supply_notification"))

#: Tên chứng từ nghiệp vụ — sau chuyển đổi không được còn trong mã CHẠY (AC-20).
BUSINESS_DOCTYPES = (
	"Sales Order",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
	"Sales Invoice",
	"Delivery Note",
	"Payment Entry",
	"Payment Request",
	"Material Request",
)

#: Trường nghiệp vụ của từng điểm — cũng phải nằm trong cấu hình, không trong code.
BUSINESS_FIELDS = (
	"grand_total",
	"outstanding_amount",
	"paid_amount",
	"transaction_date",
	"posting_date",
	"schedule_date",
	"customer_name",
	"supplier_name",
	"material_request_type",
	"payment_request_type",
	"payment_type",
)

#: File chỉ chứa dữ liệu hạt giống hoặc không phải mã chạy.
EXEMPT_FILES = ("constants.py",)


def runtime_modules() -> list[pathlib.Path]:
	return [
		path
		for path in MODULE_DIR.glob("*.py")
		if path.name not in EXEMPT_FILES and not path.name.startswith("test_")
	]


class TestCodeBoundary(FrappeTestCase):
	"""AC-20: mã chạy không còn biết tên chứng từ hay trường nghiệp vụ của điểm."""

	def test_no_business_doctype_name_is_left_in_runtime_code(self):
		found = {}
		for path in runtime_modules():
			text = path.read_text()
			hits = [name for name in BUSINESS_DOCTYPES if name in text]
			if hits:
				found[path.name] = hits

		self.assertEqual(found, {})

	def test_no_business_field_name_is_left_in_runtime_code(self):
		found = {}
		for path in runtime_modules():
			text = path.read_text()
			hits = [name for name in BUSINESS_FIELDS if re.search(rf"\b{name}\b", text)]
			if hits:
				found[path.name] = hits

		self.assertEqual(found, {})

	def test_hooks_no_longer_wire_each_document_by_hand(self):
		"""Bộ máy nối vào doc_events["*"], không liệt kê từng chứng từ nữa."""
		wired = set()
		for key, events in frappe.get_hooks("doc_events").items():
			handlers = []
			for value in events.values():
				handlers.extend(value if isinstance(value, list) else [value])
			if any("supply_notification" in handler for handler in handlers):
				wired.update(key if isinstance(key, tuple | list) else [key])

		self.assertEqual(wired, {"*"})


class TestSeedParity(FrappeTestCase):
	"""Điểm đã chuyển đổi trên site phải cho ra đúng nội dung như hạt giống."""

	def assert_same_render(self, code, doc):
		migrated = frappe.get_doc("Supply Notification Point", code)
		seeded = build_point(constants.SEED_POINTS_BY_CODE[code])
		seeded.name = code

		self.assertEqual(
			content.build(migrated, doc).body,
			content.build(seeded, doc).body,
			f"Thân email của {code} khác giữa bản đã chuyển đổi và hạt giống",
		)
		self.assertEqual(content.build(migrated, doc).subject, content.build(seeded, doc).subject)

	def test_sales_order_point_renders_identically(self):
		self.assert_same_render("NTF-01", fixtures.make_sales_order(submit=False))

	def test_material_request_point_renders_identically(self):
		self.assert_same_render("NTF-02", fixtures.make_material_request(submit=False))

	def test_purchase_invoice_reminder_renders_identically(self):
		self.assert_same_render("NTF-06", fixtures.make_purchase_invoice(submit=False))

	def test_every_migrated_point_has_a_body(self):
		for code in constants.SEED_POINTS_BY_CODE:
			self.assertTrue(
				frappe.db.get_value("Supply Notification Point", code, "body_template"),
				f"{code} chưa có thân email sau chuyển đổi",
			)


class TestMigrationOutcome(FrappeTestCase):
	def test_reminder_points_carry_their_date_field_and_milestones(self):
		point = frappe.get_doc("Supply Notification Point", "NTF-06")

		self.assertEqual(point.trigger_event, constants.DATE_REMINDER)
		self.assertEqual(point.date_field, "due_date")
		self.assertEqual(point.reminder_offset_list(), [-7, -3, -1])
		self.assertEqual(
			[(row.fieldname, row.operator, row.value) for row in point.conditions],
			[("outstanding_amount", ">", "0")],
		)

	def test_conditions_replace_the_hardcoded_filters(self):
		point = frappe.get_doc("Supply Notification Point", "NTF-02")

		self.assertEqual(
			[(row.fieldname, row.operator, row.value) for row in point.conditions],
			[("material_request_type", "=", "Purchase")],
		)

	def test_purchase_order_point_no_longer_mails_the_supplier(self):
		"""CR_01 R2/R8/AC7: NTF-03 chỉ còn báo kho; gửi NCC là việc của NTF-13."""
		point = frappe.get_doc("Supply Notification Point", "NTF-03")

		self.assertEqual(point.notify_external, 0)
		self.assertFalse(point.external_body_template)

	def test_the_manual_point_of_cr01_exists_and_is_configured(self):
		point = frappe.get_doc("Supply Notification Point", "NTF-13")

		self.assertEqual(point.trigger_event, constants.MANUAL)
		self.assertEqual(point.reference_doctype, "Purchase Order")
		self.assertEqual(point.button_label, "Gửi cho NCC")
		self.assertEqual(point.notify_external, 1)
		self.assertEqual(point.attach_pdf, 0)
		self.assertEqual(point.send_email, 0)
		self.assertIn("xác nhận đơn", point.external_subject_template)
		self.assertIn("bang_mat_hang", point.external_body_template)
		self.assertIn(constants.SNIPPET_DELIVERY_RULES, point.external_body_template)

	def test_seed_points_are_marked_so_they_cannot_be_deleted(self):
		codes = [*constants.SEED_POINTS_BY_CODE, "NTF-13"]

		for code in codes:
			self.assertEqual(
				frappe.db.get_value("Supply Notification Point", code, "is_seed"),
				1,
				f"{code} chưa được đánh dấu là điểm hạt giống",
			)

	def test_shared_snippets_are_installed(self):
		for name in (
			constants.SNIPPET_FOOTER,
			constants.SNIPPET_DELIVERY_RULES,
			constants.SNIPPET_HOTLINE,
		):
			self.assertTrue(frappe.db.exists("Supply Notification Snippet", name))
