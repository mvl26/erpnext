# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.supply_notification.events import matching_points


def doc_of(doctype, **values):
	doc = frappe.new_doc(doctype)
	doc.update(values)
	return doc


class TestEventRouting(FrappeTestCase):
	def test_sales_order_always_matches(self):
		self.assertEqual(matching_points(doc_of("Sales Order")), ["NTF-01"])

	def test_material_request_only_when_purchase(self):
		self.assertEqual(
			matching_points(doc_of("Material Request", material_request_type="Purchase")), ["NTF-02"]
		)
		for other in ("Material Transfer", "Material Issue", "Manufacture", "Customer Provided"):
			self.assertEqual(matching_points(doc_of("Material Request", material_request_type=other)), [])

	def test_payment_request_splits_by_direction(self):
		self.assertEqual(
			matching_points(doc_of("Payment Request", payment_request_type="Outward")), ["NTF-09"]
		)
		self.assertEqual(
			matching_points(doc_of("Payment Request", payment_request_type="Inward")), ["NTF-11"]
		)

	def test_payment_entry_splits_by_type_and_skips_internal_transfer(self):
		self.assertEqual(matching_points(doc_of("Payment Entry", payment_type="Pay")), ["NTF-10"])
		self.assertEqual(matching_points(doc_of("Payment Entry", payment_type="Receive")), ["NTF-12"])
		self.assertEqual(matching_points(doc_of("Payment Entry", payment_type="Internal Transfer")), [])

	def test_sales_invoice_has_no_submit_point(self):
		self.assertEqual(matching_points(doc_of("Sales Invoice")), [])

	def test_every_submit_doctype_is_wired_in_hooks(self):
		wired = set()
		for key, events in frappe.get_hooks("doc_events").items():
			targets = events.get("on_submit") or []
			if isinstance(targets, str):
				targets = [targets]
			if "erpnext.supply_notification.events.on_submit" in targets:
				wired.update(key if isinstance(key, tuple | list) else [key])

		expected = {
			"Sales Order",
			"Material Request",
			"Purchase Order",
			"Purchase Receipt",
			"Purchase Invoice",
			"Delivery Note",
			"Payment Request",
			"Payment Entry",
		}
		self.assertEqual(expected - wired, set())
