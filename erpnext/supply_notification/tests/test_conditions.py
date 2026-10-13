# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Bảng điều kiện: từng toán tử, bảng con, VÀ/HOẶC, và bộ lọc đẩy xuống SQL."""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.supply_notification import conditions
from erpnext.supply_notification.tests import fixtures


def order(**values):
	doc = frappe.new_doc("Sales Order")
	doc.update(values)
	return doc


class TestOperators(FrappeTestCase):
	def test_equality_compares_numbers_as_numbers(self):
		self.assertTrue(conditions.compare(100.0, conditions.EQ, "100", "Currency"))
		self.assertTrue(conditions.compare(100.0, conditions.GT, "99.5", "Currency"))
		self.assertFalse(conditions.compare(100.0, conditions.LT, "99.5", "Currency"))

	def test_text_equality_is_plain_string_comparison(self):
		self.assertTrue(conditions.compare("Purchase", conditions.EQ, "Purchase", "Select"))
		self.assertFalse(conditions.compare("Purchase", conditions.EQ, "purchase", "Select"))

	def test_not_equal(self):
		self.assertTrue(conditions.compare("Closed", conditions.NE, "Draft", "Select"))
		self.assertFalse(conditions.compare("Closed", conditions.NE, "Closed", "Select"))

	def test_in_and_not_in_lists(self):
		self.assertTrue(conditions.compare("Purchase", conditions.IN, "Purchase, Material Transfer"))
		self.assertFalse(conditions.compare("Manufacture", conditions.IN, "Purchase, Material Transfer"))
		self.assertTrue(conditions.compare("Manufacture", conditions.NOT_IN, "Purchase"))

	def test_is_set_and_empty(self):
		self.assertTrue(conditions.compare("x", conditions.IS_SET, ""))
		self.assertFalse(conditions.compare(None, conditions.IS_SET, ""))
		self.assertTrue(conditions.compare("", conditions.IS_NOT_SET, ""))
		self.assertFalse(conditions.compare(0, conditions.IS_NOT_SET, ""))

	def test_contains_ignores_case(self):
		self.assertTrue(conditions.compare("Bông băng y tế", conditions.CONTAINS, "băng"))
		self.assertTrue(conditions.compare("MIYANO", conditions.CONTAINS, "miyano"))
		self.assertFalse(conditions.compare("Miyano", conditions.CONTAINS, "khác"))

	def test_dates_compare_chronologically_not_alphabetically(self):
		self.assertTrue(conditions.compare("2026-09-23", conditions.GT, "2026-09-09", "Date"))

	def test_mismatched_types_never_raise(self):
		self.assertFalse(conditions.compare(None, conditions.GT, "abc", "Currency"))
		self.assertFalse(conditions.compare("chữ", conditions.GT, "2026-01-01", "Date"))


class TestMatch(FrappeTestCase):
	def test_no_conditions_means_every_document_matches(self):
		point = fixtures.make_point(users=[], notify_owner=1)
		self.assertTrue(conditions.match(point, order()))

	def test_single_condition_on_parent_field(self):
		point = fixtures.make_point(
			reference_doctype="Material Request",
			notify_owner=1,
			conditions=[("material_request_type", "=", "Purchase")],
		)

		request = frappe.new_doc("Material Request")
		request.material_request_type = "Purchase"
		self.assertTrue(conditions.match(point, request))

		request.material_request_type = "Material Transfer"
		self.assertFalse(conditions.match(point, request))

	def test_and_needs_every_row(self):
		point = fixtures.make_point(
			notify_owner=1,
			condition_logic="VÀ",
			conditions=[("customer_name", "Có giá trị", ""), ("grand_total", ">", "1000")],
		)

		self.assertTrue(conditions.match(point, order(customer_name="Khách", grand_total=5000)))
		self.assertFalse(conditions.match(point, order(customer_name="Khách", grand_total=10)))

	def test_or_needs_only_one_row(self):
		point = fixtures.make_point(
			notify_owner=1,
			condition_logic="HOẶC",
			conditions=[("customer_name", "=", "Không ai"), ("grand_total", ">", "1000")],
		)

		self.assertTrue(conditions.match(point, order(customer_name="Khách", grand_total=5000)))
		self.assertFalse(conditions.match(point, order(customer_name="Khách", grand_total=10)))

	def test_child_table_matches_when_at_least_one_row_matches(self):
		point = fixtures.make_point(
			notify_owner=1,
			conditions=[("items.item_code", "=", fixtures.ensure_item())],
		)

		doc = fixtures.make_sales_order(submit=False)
		self.assertTrue(conditions.match(point, doc))

		doc.items[0].item_code = "KHONG-CO"
		self.assertFalse(conditions.match(point, doc))

	def test_unknown_field_does_not_match_and_does_not_raise(self):
		point = fixtures.make_point(notify_owner=1)
		point.append("conditions", {"fieldname": "khong_co_truong", "operator": "=", "value": "x"})

		self.assertFalse(conditions.match(point, order()))


class TestFilters(FrappeTestCase):
	def test_simple_conditions_become_sql_filters(self):
		point = fixtures.make_point(
			reference_doctype="Purchase Invoice",
			trigger_event="Date Reminder",
			date_field="due_date",
			reminder_offsets="-7",
			notify_owner=1,
			conditions=[("outstanding_amount", ">", "0")],
		)

		self.assertEqual(conditions.to_filters(point), {"outstanding_amount": (">", 0.0)})

	def test_child_conditions_stay_out_of_sql(self):
		point = fixtures.make_point(
			notify_owner=1,
			conditions=[("items.item_code", "=", "X")],
		)

		self.assertEqual(conditions.to_filters(point), {})

	def test_or_logic_is_not_pushed_down(self):
		point = fixtures.make_point(
			notify_owner=1,
			condition_logic="HOẶC",
			conditions=[("grand_total", ">", "1"), ("customer_name", "Có giá trị", "")],
		)

		self.assertEqual(conditions.to_filters(point), {})
