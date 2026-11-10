"""H8 — HR record scope ``[e]`` / ``[d]`` (spec 11.3 H8, section 10; plan R-2 and Review Focus 2; T01, T10, T11, T13).

Fixtures are throwaway Departments, Users and Employees inside the class transaction. Every Employee has
``create_user_permission = 0`` (spec 11.7), so no User Permission row muddies the list queries. The documents the
hooks judge (Expense Claim, Leave Application, Salary Slip…) are in-memory only — never inserted.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.access import scope
from erpnext.access.scope import has_permission, query_conditions, unscoped_roles, visible_employees

COMPANY = "Miyano"


def make_user(*roles):
	email = f"scope-{frappe.generate_hash(length=8)}@example.com"
	user = frappe.get_doc({"doctype": "User", "email": email, "first_name": "Scope", "send_welcome_email": 0})
	user.insert(ignore_permissions=True)
	if roles:
		user.add_roles(*roles)
	frappe.clear_cache(user=email)
	return email


def make_department(label, parent="All Departments", approver=None):
	doc = frappe.get_doc(
		{
			"doctype": "Department",
			"department_name": f"ZZ Scope {label} {frappe.generate_hash(length=6)}",
			"company": COMPANY,
			"parent_department": parent,
			"is_group": 1,
		}
	)
	if approver:
		doc.append("leave_approvers", {"approver": approver})
	return doc.insert(ignore_permissions=True).name


def make_employee(label, department, **fields):
	doc = frappe.get_doc(
		{
			"doctype": "Employee",
			"first_name": f"Scope {label}",
			"gender": "Male",
			"date_of_birth": "1990-01-01",
			"date_of_joining": "2020-01-01",
			"company": COMPANY,
			"status": "Active",
			"department": department,
			"create_user_permission": 0,
			**fields,
		}
	)
	return doc.insert(ignore_permissions=True).name


def memdoc(doctype, **fields):
	"""An in-memory, not-new document — never inserted."""
	doc = frappe.get_doc({"doctype": doctype, **fields})
	doc.name = fields.get("name") or f"ZZ-SCOPE-{frappe.generate_hash(length=8)}"
	doc.owner = fields.get("owner") or "Administrator"
	return doc


class TestScope(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.emp_user = make_user()
		cls.dh_user = make_user("MVL Department Head")
		cls.ktnv_user = make_user("Accounts User")
		cls.hunv_user = make_user("HR User")
		cls.pj_user = make_user("Projects User", "MVL Department Head")

		cls.dept_p = make_department("P", approver=cls.dh_user)
		cls.dept_pc = make_department("PC", parent=cls.dept_p)
		cls.dept_o = make_department("O")

		cls.emp_d = make_employee("D", cls.dept_o, user_id=cls.dh_user)
		cls.emp_a = make_employee("A", cls.dept_pc)
		cls.emp_b = make_employee("B", cls.dept_o)
		cls.emp_r = make_employee("R", cls.dept_o, reports_to=cls.emp_d)
		cls.emp_l = make_employee("L", cls.dept_o, leave_approver=cls.dh_user)
		cls.emp_x = make_employee("X", cls.dept_o, expense_approver=cls.dh_user)
		cls.emp_c = make_employee("C", cls.dept_o, user_id=cls.emp_user)
		cls.emp_k = make_employee("K", cls.dept_o, user_id=cls.ktnv_user)
		cls.emp_h = make_employee("H", cls.dept_o, user_id=cls.hunv_user)
		for user in (cls.emp_user, cls.dh_user, cls.ktnv_user, cls.hunv_user, cls.pj_user):
			frappe.clear_cache(user=user)

	def setUp(self):
		enabled = patch.object(scope, "is_enabled", return_value=True)
		self.enabled = enabled.start()
		self.addCleanup(enabled.stop)
		self.addCleanup(frappe.set_user, "Administrator")
		scope.clear_request_cache()
		self.addCleanup(scope.clear_request_cache)

	def get_list_as(self, user, doctype):
		frappe.set_user(user)
		try:
			return set(frappe.get_list(doctype, pluck="name"))
		finally:
			frappe.set_user("Administrator")

	# -- gate and basics ------------------------------------------------------------------------

	def test_gate_off_returns_none(self):
		self.enabled.return_value = False
		other = memdoc("Expense Claim", employee=self.emp_b)
		self.assertIsNone(has_permission(other, "read", self.emp_user))
		self.assertEqual(query_conditions(self.emp_user, "Employee"), "")

	def test_administrator_is_unlimited(self):
		self.assertIsNone(
			has_permission(memdoc("Expense Claim", employee=self.emp_b), "read", "Administrator")
		)
		self.assertEqual(query_conditions("Administrator", "Expense Claim"), "")

	def test_unscoped_roles_are_per_ptype(self):
		self.assertIn("Accounts User", unscoped_roles("Expense Claim", "read"))
		self.assertNotIn("Accounts User", unscoped_roles("Expense Claim", "create"))
		self.assertNotIn("Employee", unscoped_roles("Expense Claim", "read"))
		self.assertNotIn("MVL Department Head", unscoped_roles("Expense Claim", "read"))
		self.assertIn("HR User", unscoped_roles("Leave Application", "create"))
		self.assertNotIn("Projects User", unscoped_roles("Timesheet", "read"))  # ·o row, not unscoped

	# -- (c) own records ------------------------------------------------------------------------

	def test_emp_sees_only_self(self):
		self.assertEqual(
			query_conditions(self.emp_user, "Employee"),
			f"`tabEmployee`.`name` in ({frappe.db.escape(self.emp_c, percent=False)})",
		)
		self.assertEqual(self.get_list_as(self.emp_user, "Employee"), {self.emp_c})
		self.assertIsNone(has_permission(memdoc("Employee", name=self.emp_c), "read", self.emp_user))
		self.assertIs(has_permission(memdoc("Employee", name=self.emp_b), "read", self.emp_user), False)
		self.assertIs(
			has_permission(memdoc("Leave Application", employee=self.emp_b), "create", self.emp_user), False
		)

	# -- (b) department head --------------------------------------------------------------------

	def test_dh_sees_department_and_reportees(self):
		expected = {self.emp_d, self.emp_a, self.emp_r, self.emp_l, self.emp_x}
		self.assertEqual(set(visible_employees(self.dh_user)), expected)
		self.assertEqual(self.get_list_as(self.dh_user, "Employee"), expected)
		self.assertIsNone(
			has_permission(memdoc("Leave Application", employee=self.emp_a), "read", self.dh_user)
		)
		self.assertIsNone(
			has_permission(memdoc("Leave Application", employee=self.emp_r), "submit", self.dh_user)
		)
		self.assertIs(
			has_permission(memdoc("Leave Application", employee=self.emp_b), "read", self.dh_user), False
		)
		self.assertIs(has_permission(memdoc("Employee", name=self.emp_b), "read", self.dh_user), False)

	def test_dh_cannot_open_salary_slip_of_department(self):  # T01
		slip = memdoc("Salary Slip", employee=self.emp_a)
		self.assertIs(has_permission(slip, "read", self.dh_user), False)
		self.assertIsNone(has_permission(memdoc("Salary Slip", employee=self.emp_d), "read", self.dh_user))

	def test_department_mode_doctype(self):
		self.assertEqual(scope.ref_field("Staffing Plan"), scope.RefField("department", scope.DEPARTMENT))
		self.assertIsNone(
			has_permission(memdoc("Staffing Plan", department=self.dept_pc), "read", self.dh_user)
		)
		self.assertIs(
			has_permission(memdoc("Staffing Plan", department=self.dept_o), "read", self.dh_user), False
		)
		condition = query_conditions(self.dh_user, "Staffing Plan")
		self.assertTrue(condition.startswith("`tabStaffing Plan`.`department` in ("), condition)
		self.assertIn(frappe.db.escape(self.dept_pc, percent=False), condition)
		self.assertNotIn(frappe.db.escape(self.dept_o, percent=False), condition)

	# -- Review Focus 2, T10, T11 ---------------------------------------------------------------

	def test_ktnv_reads_all_expense_claims_but_creates_only_own(self):  # T10 + RF2
		other = memdoc("Expense Claim", employee=self.emp_b)
		self.assertEqual(query_conditions(self.ktnv_user, "Expense Claim"), "")
		self.assertIsNone(has_permission(other, "read", self.ktnv_user))
		self.assertIs(has_permission(other, "create", self.ktnv_user), False)
		self.assertIs(has_permission(other, "write", self.ktnv_user), False)
		self.assertIsNone(
			has_permission(memdoc("Expense Claim", employee=self.emp_k), "create", self.ktnv_user)
		)
		self.assertIs(
			has_permission(memdoc("Leave Application", employee=self.emp_b), "create", self.ktnv_user), False
		)

	def test_hu_cannot_read_others_expense_claim(self):  # T11
		self.assertIs(
			has_permission(memdoc("Expense Claim", employee=self.emp_b), "read", self.hunv_user), False
		)
		self.assertIsNone(
			has_permission(memdoc("Expense Claim", employee=self.emp_h), "read", self.hunv_user)
		)
		# HU's own Leave Application cells carry no scope (D6 — HU enters leave on behalf of others)
		self.assertIsNone(
			has_permission(memdoc("Leave Application", employee=self.emp_b), "read", self.hunv_user)
		)

	# -- T13, ·o, empty sets ------------------------------------------------------------------

	def test_reference_masters_are_not_scoped(self):  # T13
		from erpnext import hooks

		for doctype in ("Company", "Warehouse", "Currency", "Cost Center"):
			self.assertNotIn(doctype, hooks.has_permission)
			self.assertNotIn(doctype, hooks.permission_query_conditions)
			self.assertIsNone(has_permission(memdoc(doctype), "read", self.emp_user))
		self.assertIsNone(has_permission(memdoc("Expense Claim", employee=self.emp_c), "read", self.emp_user))

	def test_owner_scope_keeps_own_records(self):
		# Timesheet: PJU ·o + DH [d]; pj_user approves no Department and has no Employee
		self.assertEqual(visible_employees(self.pj_user), ())
		mine = memdoc("Timesheet", employee=self.emp_b, owner=self.pj_user)
		theirs = memdoc("Timesheet", employee=self.emp_b, owner=self.dh_user)
		self.assertIsNone(has_permission(mine, "read", self.pj_user))
		self.assertIs(has_permission(theirs, "read", self.pj_user), False)
		self.assertEqual(
			query_conditions(self.pj_user, "Timesheet"),
			f"(1=0 or `tabTimesheet`.`owner` = {frappe.db.escape(self.pj_user, percent=False)})",
		)

	def test_projects_user_alone_is_left_to_frappe(self):
		user = make_user("Projects User")
		self.assertEqual(query_conditions(user, "Timesheet"), "")
		self.assertIsNone(has_permission(memdoc("Timesheet", employee=self.emp_b), "read", user))

	def test_user_without_employee_matches_nothing(self):
		# erpnext strips the Employee role from a user with no Employee, so use a lone DH (approves nothing)
		user = make_user("MVL Department Head")
		self.assertEqual(query_conditions(user, "Expense Claim"), "1=0")
		self.assertIs(has_permission(memdoc("Expense Claim", employee=self.emp_b), "read", user), False)
		self.assertIs(has_permission(memdoc("Expense Claim"), "read", user), False)

	def test_hook_never_returns_true(self):  # R-2
		own_doc = memdoc("Expense Claim", employee=self.emp_c)
		self.assertIsNone(has_permission(own_doc, "read", self.emp_user))
		users = (self.emp_user, self.dh_user, self.ktnv_user, self.hunv_user, self.pj_user, "Administrator")
		employees = (self.emp_a, self.emp_b, self.emp_c, self.emp_d, None)
		for doctype in sorted(scope.scoped_doctypes()):
			field = scope.ref_field(doctype)
			for user in users:
				for value in (*employees, self.dept_pc, self.dept_o):
					doc = memdoc(doctype, **{field.fieldname: value} if field.fieldname != "name" else {})
					if field.fieldname == "name" and value:
						doc.name = value
					for ptype in ("read", "write", "create", "submit", "cancel", "delete", None):
						result = has_permission(doc, ptype, user)
						self.assertIn(result, (None, False), (doctype, user, value, ptype))
						self.assertIsNot(result, True)

	# -- field resolution -------------------------------------------------------------------------

	def test_every_scoped_doctype_resolves_a_field(self):
		fields = scope.ref_fields()
		self.assertEqual(set(fields), set(scope.scoped_doctypes()))
		self.assertEqual([dt for dt, f in fields.items() if f is None], [])
		self.assertEqual(fields["Employee"], scope.RefField("name", scope.EMPLOYEE))
		self.assertEqual(fields["Business Trip"], scope.RefField("registered_by", scope.EMPLOYEE))
		self.assertEqual(fields["Expense Claim"], scope.RefField("employee", scope.EMPLOYEE))
		self.assertEqual(fields["Job Requisition"], scope.RefField("department", scope.DEPARTMENT))
		self.assertEqual(len(fields), 35)
