"""Scaffolding shared by the mandatory acceptance scenarios T01-T57 (spec section 13, plan Task 26).

The scenario modules (``test_kich_ban_*.py``) judge the REAL synced matrix — Custom DocPerms, Custom Roles,
active workflows, Role Profiles — as throwaway users that carry the real ``RP-*`` Role Profiles. They only make
sense on a test site where ``sync.run()`` has run (``mvl_rbac_test_site`` + ``mvl_rbac_enabled``); on site
miyano every scenario class skips in ``setUp`` (``require_test_site``).

Documents that a scenario only needs to be *judged* (a permission check, a workflow transition list, a guard
hook) are built in memory and never inserted; the few scenarios that need real documents reuse the builders of
``TestWorkflowGuardOnTestSite`` (``workflow_fixtures``).
"""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import frappe
from frappe.model.workflow import get_transitions, get_workflow
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from erpnext.access import scope, workflow_guard
from erpnext.access.tests.fixtures import make_employee_for, make_profile_user
from erpnext.access.tests.test_scope import make_department
from erpnext.access.tests.test_workflow_guard import (
	TestWorkflowGuardOnTestSite,
	_company,
	_ensure,
	_leaf,
	make_doc,
)

LIMITS = "MVL Approval Limits"
H1, H2, H3 = 50_000_000, 500_000_000, 20_000_000

# Spec role code (section 13 wording) → the real Role Profile a throwaway user is created on.
PROFILES = {
	"NV": "RP-NV",  # a plain employee (Employee role only)
	"DH": "RP-KHO-TP",  # holds MVL Department Head via the TBP pack; no HR/finance roles to muddy the cell
	"HU": "RP-NS-NV",
	"HM": "RP-NS-TP",
	"CUS": "RP-NG-KH",
	"SUP": "RP-NG-NCC",
	"SYS": "RP-IT-QT",
	"VW": "RP-BGD-GD",
	"GDVH": "RP-BGD-GDVH",
	"SU": "RP-KD-NV",
	"SM": "RP-KD-TP",
	"MK": "RP-MKT-NV",
	"PDA": "RP-KHO-PDA",
	"STU": "RP-KHO-TK",
	"STM": "RP-KHO-TP",
	"AU": "RP-KT-NV",
	"AM": "RP-KT-KTT",
	"PU": "RP-MH-NV",
	"PM": "RP-MH-TP",
}


class ScenarioCase(FrappeTestCase):
	"""Base of the four scenario modules — each module's class calls ``require_test_site`` then ``prepare``."""

	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._users = {}

	def prepare(self):
		"""Second half of ``setUp`` (after ``require_test_site``): gate, limits, silent mail, cleanup."""
		if not frappe.conf.get("mvl_rbac_enabled"):
			self.skipTest("cần mvl_rbac_enabled — hook RBAC đang tắt")
		if not frappe.db.exists("Role Profile", "RP-KD-NV"):
			self.skipTest("ma trận chưa được đồng bộ trên site này (thiếu Role Profile RP-*)")
		mail = patch.object(frappe, "sendmail", MagicMock())  # H4 mails the Operations Director on user edits
		mail.start()
		self.addCleanup(mail.stop)
		self.addCleanup(frappe.set_user, "Administrator")
		scope.clear_request_cache()
		self.addCleanup(scope.clear_request_cache)
		for field, value in (("h1", H1), ("h2", H2), ("h3", H3)):
			frappe.db.set_single_value(LIMITS, field, value)

	def user(self, code: str) -> str:
		"""The class-wide throwaway user for spec role code ``code`` (see PROFILES)."""
		users = type(self)._users
		if code not in users:
			users[code] = make_profile_user(PROFILES[code])
		return users[code]

	def require_workflow(self, doctype: str) -> None:
		if not frappe.db.get_value("Workflow", {"document_type": doctype, "is_active": 1}):
			self.skipTest(f"cần workflow RBAC đang bật cho {doctype}")


# -- permission probes ----------------------------------------------------------------------------


@contextmanager
def as_user(user: str):
	frappe.set_user(user)
	try:
		yield
	finally:
		frappe.set_user("Administrator")


def memdoc(doctype: str, **fields):
	"""An in-memory, not-new document — never inserted."""
	doc = frappe.get_doc({"doctype": doctype, "owner": "Administrator", **fields})
	doc.name = fields.get("name") or f"ZZ-KB-{frappe.generate_hash(length=8)}"
	return doc


def can(user: str, doctype: str, ptype: str, doc=None) -> bool:
	"""``frappe.has_permission`` as ``user`` — the Custom DocPerms plus every ``has_permission`` hook."""
	return bool(frappe.has_permission(doctype, ptype, doc=doc, user=user))


def fields_with_access(user: str, doctype: str, ptype: str = "read") -> set[str]:
	"""Fieldnames ``user`` holds ``ptype`` on — the same call the report view uses (Custom DocPerm aware)."""
	meta = frappe.get_meta(doctype)
	return set(meta.get_permitted_fieldnames(user=user, permission_type=ptype))


def employee_of(user: str) -> str:
	return frappe.db.get_value("Employee", {"user_id": user}, "name")


def new_employee(department: str | None = None, **fields) -> str:
	"""An Employee without a user — somebody else's record."""
	return make_employee_for(None, department, **fields)


def report_opens(user: str, report: str) -> bool:
	"""True when ``user`` may run ``report``: its Custom Role and the 'report' right on its doctype."""
	from frappe.desk.query_report import get_report_doc

	with as_user(user):
		try:
			get_report_doc(report)
		except frappe.PermissionError:
			return False
	return True


# -- workflow probes ------------------------------------------------------------------------------


def transitions(user: str, doctype: str, state: str, docstatus: int = 0, owner: str | None = None, **values):
	"""``{(action, next_state)}`` the REAL active workflow offers ``user`` on an in-memory doc in ``state``.

	``frappe.model.workflow.get_transitions`` itself judges roles and conditions (G11, limits, flags); only its
	read-permission check is waived (``ignore_permissions``), so record scope does not need fixtures.
	"""
	doc = make_doc(doctype, state, owner or "Administrator", docstatus=docstatus, **values)
	doc.flags.ignore_permissions = True
	with as_user(user):
		return {(t.action, t.next_state) for t in get_transitions(doc, get_workflow(doctype))}


def run_guards(doc) -> None:
	"""``before_validate`` → ``validate`` → ``before_submit`` of the H5/H10/H11 guards, in frappe's order."""
	workflow_guard.before_validate(doc)
	workflow_guard.validate(doc)
	if doc.docstatus == 1:
		workflow_guard.before_submit(doc)


def workflow_fixtures() -> TestWorkflowGuardOnTestSite:
	"""Real-document builders (``purchase_order``, ``journal_entry``, ``state``) of the earlier workflow-guard
	end-to-end suite. Only its builder methods are used — ``setUp`` is not run, so nothing stays patched."""
	helper = TestWorkflowGuardOnTestSite("test_api_submit_po_over_limit_blocked")
	helper.company = _company()
	helper.warehouse = _leaf("Warehouse", company=helper.company)
	return helper


def ensure_customer(**fields) -> str:
	name = f"_Test KB Customer {frappe.generate_hash(length=6)}"
	return _ensure(
		"Customer",
		{"customer_name": name},
		{"customer_name": name, "customer_group": _leaf("Customer Group"), **fields},
	)


# -- real documents for the approval flows (T27, T28, T36) -------------------------------------------


def place_in_department(user: str, approver: str) -> str:
	"""Put ``user``'s Employee in a new department headed by ``approver`` and make him leave/expense approver."""
	employee = employee_of(user)
	department = make_department("KB", approver=approver)
	frappe.db.set_value(
		"Employee",
		employee,
		{"department": department, "leave_approver": approver, "expense_approver": approver},
	)
	return employee


def insert_leave_application(user: str, employee: str, approver: str):
	"""A real draft Leave Application of ``employee`` inserted by ``user`` (LWP type: no allocation needed)."""
	leave_type = _ensure(
		"Leave Type",
		{"leave_type_name": "_Test KB LWP"},
		{"leave_type_name": "_Test KB LWP", "is_lwp": 1, "include_holiday": 1, "max_leaves_allowed": 30},
	)
	day = add_days(nowdate(), 60)
	frappe.set_user(user)
	doc = frappe.get_doc(
		{
			"doctype": "Leave Application",
			"employee": employee,
			"leave_type": leave_type,
			"from_date": day,
			"to_date": day,
			"company": _company(),
			"leave_approver": approver,
			"posting_date": nowdate(),
		}
	)
	doc.insert()
	return doc


def insert_expense_claim(user: str, employee: str, amount: float):
	"""A real draft Expense Claim of ``employee`` inserted by ``user``."""
	company = frappe.get_cached_doc("Company", _company())
	account = _leaf("Account", company=company.name, root_type="Expense", account_type="")
	expense_type = _ensure(
		"Expense Claim Type",
		{"expense_type": "_Test KB Expense"},
		{
			"expense_type": "_Test KB Expense",
			"accounts": [{"company": company.name, "default_account": account}],
		},
	)
	frappe.set_user(user)
	doc = frappe.get_doc(
		{
			"doctype": "Expense Claim",
			"employee": employee,
			"company": company.name,
			"posting_date": nowdate(),
			"payable_account": company.default_payable_account,
			"cost_center": company.cost_center,
			"expenses": [
				{
					"expense_date": nowdate(),
					"expense_type": expense_type,
					"amount": amount,
					"sanctioned_amount": amount,
				}
			],
		}
	)
	doc.insert()
	return doc


def warehouse_pair(user: str) -> tuple[str, str]:
	"""(assigned, unassigned) Warehouses: ``user`` gets a User Permission on the first only (matrix 'w' scope)."""
	company = _company()
	names = []
	for label in ("KB Gan", "KB Khong Gan"):
		doc = frappe.get_doc(
			{
				"doctype": "Warehouse",
				"warehouse_name": f"{label} {frappe.generate_hash(length=6)}",
				"company": company,
			}
		)
		names.append(doc.insert(ignore_permissions=True).name)
	frappe.get_doc(
		{
			"doctype": "User Permission",
			"user": user,
			"allow": "Warehouse",
			"for_value": names[0],
			"apply_to_all_doctypes": 1,
		}
	).insert(ignore_permissions=True)
	frappe.clear_cache(user=user)
	return names[0], names[1]
