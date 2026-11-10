from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.access.permissions.matrix import DocTypeEntry
from erpnext.access.permissions.schema import ensure_schema
from erpnext.access.tests.helpers import small_matrix

# Rarely used DocType: its Property Setters never matter to production users, and the class rollback removes them.
PERIOD = "Supplier Scorecard Period"


def ps_count():
	return frappe.db.count("Property Setter")


def ps_value(doctype, fieldname, prop):
	return frappe.db.get_value(
		"Property Setter", {"doc_type": doctype, "field_name": fieldname, "property": prop}, "value"
	)


class TestSchemaDDL(FrappeTestCase):
	"""Creates real Custom Fields — DDL commits by design (both are hidden and harmless)."""

	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def test_custom_field_and_workflow_state(self):
		m = small_matrix(
			doctypes={},
			custom_fields={
				"fields": {
					"Sales Order": [
						{
							"fieldname": "mvl_dung_gia_hd",
							"fieldtype": "Check",
							"label": "Đúng giá HĐ",
							"insert_after": "per_billed",
							"read_only": 1,
							"hidden": 1,
							"no_copy": 1,
							"default": "0",
						}
					]
				}
			},
			workflows={
				"WF-T": {"doctypes": ["Bank Account", "Sales Order"], "states": [], "transitions": []}
			},
		)
		ensure_schema(m)
		frappe.clear_cache()
		field = frappe.get_meta("Sales Order").get_field("mvl_dung_gia_hd")
		self.assertEqual((field.fieldtype, field.read_only, field.hidden, field.no_copy), ("Check", 1, 1, 1))
		state = frappe.get_meta("Bank Account").get_field("workflow_state")
		self.assertEqual((state.fieldtype, state.options), ("Link", "Workflow State"))
		self.assertEqual((state.hidden, state.allow_on_submit, state.no_copy), (1, 1, 1))

		# Second run: nothing to write, so no DDL is attempted and the rows stay untouched.
		names = ("Sales Order-mvl_dung_gia_hd", "Bank Account-workflow_state")
		stamps = [frappe.db.get_value("Custom Field", n, "modified") for n in names]
		before = frappe.db.count("Custom Field")
		with patch("erpnext.access.permissions.schema.create_custom_fields") as cc:
			ensure_schema(m)
		cc.assert_not_called()
		self.assertEqual(frappe.db.count("Custom Field"), before)
		self.assertEqual([frappe.db.get_value("Custom Field", n, "modified") for n in names], stamps)

	def test_existing_workflow_state_untouched(self):
		if not frappe.db.exists("Custom Field", "Sales Order-workflow_state"):
			self.skipTest("Sales Order-workflow_state Custom Field is absent on this site")
		before = frappe.db.get_value("Custom Field", "Sales Order-workflow_state", "modified")
		ensure_schema(small_matrix(doctypes={}, workflows={"WF-T": {"doctypes": ["Sales Order"]}}))
		self.assertEqual(
			frappe.db.get_value("Custom Field", "Sales Order-workflow_state", "modified"), before
		)


class TestSchemaPropertySetters(FrappeTestCase):
	"""No custom_fields and no workflows here, so no DDL: the class rollback removes every row."""

	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def matrix(self, **kwargs):
		return small_matrix(
			doctypes={
				PERIOD: DocTypeEntry(
					state="matrix",
					perms={"AM": "R R1"},
					permlevel={1: {"fields": ["total_score"], "read": ["AM"], "write": []}},
				)
			},
			**kwargs,
		)

	def test_permlevel_idempotent(self):
		m = self.matrix()
		ensure_schema(m)
		self.assertEqual(ps_value(PERIOD, "total_score", "permlevel"), "1")
		self.assertEqual(frappe.get_meta(PERIOD).get_field("total_score").permlevel, 1)
		count = ps_count()
		modified = frappe.db.get_value("Property Setter", f"{PERIOD}-total_score-permlevel", "modified")
		ensure_schema(m)
		self.assertEqual(ps_count(), count)
		self.assertEqual(
			frappe.db.get_value("Property Setter", f"{PERIOD}-total_score-permlevel", "modified"), modified
		)

	def test_permlevel_skips_field_already_at_level(self):
		count = ps_count()
		m = small_matrix(
			doctypes={
				PERIOD: DocTypeEntry(
					state="matrix", perms={"AM": "R"}, permlevel={0: {"fields": ["total_score"]}}
				)
			}
		)
		ensure_schema(m)
		self.assertEqual(ps_count(), count)

	def test_permlevel_child_doctype(self):
		m = small_matrix(
			doctypes={
				"Supplier Scorecard": DocTypeEntry(
					state="matrix",
					perms={"AM": "R"},
					permlevel={
						2: {"fields": ["Supplier Scorecard Criteria.weight"], "read": [], "write": []}
					},
				)
			}
		)
		ensure_schema(m)
		self.assertEqual(ps_value("Supplier Scorecard Criteria", "weight", "permlevel"), "2")

	def test_reqd_and_default_updates(self):
		cf = {
			"property_setters": [
				{
					"doc_type": PERIOD,
					"field_name": "start_date",
					"property": "reqd",
					"value": "0",
					"property_type": "Check",
				},
				{
					"doc_type": PERIOD,
					"field_name": "naming_series",
					"property": "default",
					"value": "ZZ-.#",
					"property_type": "Text",
				},
			]
		}
		m = self.matrix(custom_fields=cf)
		ensure_schema(m)
		self.assertEqual(ps_value(PERIOD, "naming_series", "default"), "ZZ-.#")
		self.assertEqual(ps_value(PERIOD, "start_date", "reqd"), "0")
		self.assertEqual(frappe.get_meta(PERIOD).get_field("start_date").reqd, 0)
		count = ps_count()
		ensure_schema(m)
		self.assertEqual(ps_count(), count)
		# A changed value updates the existing row instead of adding another.
		cf["property_setters"][1]["value"] = "ZY-.#"
		ensure_schema(m)
		self.assertEqual(ps_value(PERIOD, "naming_series", "default"), "ZY-.#")
		self.assertEqual(ps_count(), count)
