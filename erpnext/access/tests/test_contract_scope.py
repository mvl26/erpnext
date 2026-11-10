"""H1 — Contract visible only for the ``party_type`` the user's roles allow (spec 11.3 H1; plan R-2).

Contracts used by the list-query case are inserted inside the class transaction against existing Customer /
Employee records (nothing is created outside the rollback); the other cases judge in-memory documents.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.access import contract_scope
from erpnext.access.contract_scope import allowed_party_types, has_permission, query_conditions

ENABLED = "erpnext.access.contract_scope.is_enabled"


def make_user(*roles):
	email = f"cscope-{frappe.generate_hash(length=8)}@example.com"
	user = frappe.get_doc(
		{"doctype": "User", "email": email, "first_name": "CScope", "send_welcome_email": 0}
	)
	user.insert(ignore_permissions=True)
	if roles:
		user.add_roles(*roles)
	frappe.clear_cache(user=email)
	return email


def contract(party_type, owner="Administrator"):
	return frappe.get_doc({"doctype": "Contract", "party_type": party_type, "owner": owner})


class TestContractScope(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.sales = make_user("Sales Manager")
		cls.purchase = make_user("Purchase User")
		cls.hr = make_user("HR User")
		cls.sales_hr = make_user("Sales Manager", "HR Manager")
		cls.admin_role = make_user("System Manager")
		cls.accountant = make_user("Accounts Manager")
		cls.other = make_user("Blogger")

	def setUp(self):
		patcher = patch(ENABLED, return_value=True)
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_allowed_party_types_per_role(self):
		self.assertEqual(allowed_party_types(self.sales), ("Customer",))
		self.assertEqual(allowed_party_types(self.purchase), ("Supplier",))
		self.assertEqual(allowed_party_types(self.hr), ("Employee",))
		self.assertEqual(allowed_party_types(self.other), ())

	def test_union_across_roles(self):
		self.assertEqual(set(allowed_party_types(self.sales_hr)), {"Customer", "Employee"})

	def test_all_party_types_roles(self):
		self.assertIsNone(allowed_party_types(self.admin_role))
		self.assertIsNone(allowed_party_types(self.accountant))
		self.assertIsNone(allowed_party_types("Administrator"))

	def test_has_permission_false_or_none_only(self):
		self.assertIsNone(has_permission(contract("Customer"), "read", self.sales))
		self.assertIs(has_permission(contract("Supplier"), "read", self.sales), False)
		self.assertIs(has_permission(contract("Employee"), "write", self.sales), False)
		self.assertIsNone(has_permission(contract("Employee"), "read", self.sales_hr))
		self.assertIs(has_permission(contract("Customer"), "read", self.other), False)
		self.assertIsNone(has_permission(contract("Supplier"), "read", self.admin_role))
		self.assertIsNone(has_permission(contract("Supplier"), "read", "Administrator"))

	def test_query_conditions(self):
		self.assertEqual(query_conditions("Administrator", "Contract"), "")
		self.assertEqual(query_conditions(self.admin_role, "Contract"), "")
		self.assertEqual(query_conditions(self.accountant, "Contract"), "")
		self.assertEqual(
			query_conditions(self.sales, "Contract"), "`tabContract`.`party_type` in ('Customer')"
		)
		self.assertEqual(query_conditions(self.other, "Contract"), "1=0")
		both = query_conditions(self.sales_hr, "Contract")
		self.assertIn("'Customer'", both)
		self.assertIn("'Employee'", both)
		self.assertNotIn("'Supplier'", both)

	def test_gate_off_returns_nothing(self):
		with patch(ENABLED, return_value=False):
			self.assertEqual(query_conditions(self.other, "Contract"), "")
			self.assertIsNone(has_permission(contract("Supplier"), "read", self.other))

	def test_get_list_filters_by_party_type(self):
		customer = frappe.db.get_value("Customer", {}, "name")
		employee = frappe.db.get_value("Employee", {}, "name")
		if not (customer and employee):
			self.skipTest("site thiếu Customer/Employee")
		names = {}
		for party_type, party in (("Customer", customer), ("Employee", employee)):
			doc = frappe.get_doc(
				{
					"doctype": "Contract",
					"party_type": party_type,
					"party_name": party,
					"contract_terms": "H1 test",
					"is_signed": 0,
				}
			).insert(ignore_permissions=True)
			names[party_type] = doc.name
		visible = set(
			frappe.get_list(
				"Contract", filters={"name": ("in", list(names.values()))}, pluck="name", user=self.sales
			)
		)
		self.assertEqual(visible, {names["Customer"]})
		visible = set(
			frappe.get_list(
				"Contract", filters={"name": ("in", list(names.values()))}, pluck="name", user=self.sales_hr
			)
		)
		self.assertEqual(visible, set(names.values()))
		self.assertTrue(frappe.has_permission("Contract", "read", names["Customer"], user=self.sales))
		self.assertFalse(frappe.has_permission("Contract", "read", names["Employee"], user=self.sales))
