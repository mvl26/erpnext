"""Workflow builder (spec 9) — every test here works on in-memory Workflow docs.

WORKFLOW TEST SAFETY: on site miyano no test inserts or activates a Workflow (the Redis "workflow" hash is
shared with production). Only the sync integration tests write Workflows, and they skip unless the site is a
test site (``require_test_site``).
"""

from unittest.mock import patch

import frappe
from frappe.model.workflow import get_transitions, get_workflow_safe_globals
from frappe.tests.utils import FrappeTestCase

from erpnext.access.permissions import workflows
from erpnext.access.permissions.matrix import DocTypeEntry, load_matrix
from erpnext.access.permissions.profiles import sync_roles
from erpnext.access.permissions.site import SiteInfo
from erpnext.access.permissions.validate import validate
from erpnext.access.permissions.workflows import (
	LIMIT_EXPR,
	build_workflow,
	g11_condition,
	render_condition,
	sync_workflows,
	workflow_name,
)
from erpnext.access.tests.helpers import require_test_site, small_matrix

OWNER_CHECK = "doc.owner != frappe.session.user"
EMPLOYEE_CHECK = "frappe.db.get_value('Employee', doc.employee, 'user_id') != frappe.session.user"
LIMITS = "MVL Approval Limits"

# (states, transitions after expanding role codes and the auto "Mở lại") per built Workflow — spec 9.3.
EXPECTED_COUNTS = {
	("WF-PO", "Purchase Order"): (6, 11),
	("WF-SO", "Sales Order"): (5, 7),
	("WF-SI", "Sales Invoice"): (5, 5),
	("WF-PI", "Purchase Invoice"): (5, 5),
	("WF-PE", "Payment Entry"): (6, 7),
	("WF-JE", "Journal Entry"): (5, 4),
	("WF-SE", "Stock Entry"): (5, 8),
	("WF-SR", "Stock Reconciliation"): (6, 9),
	("WF-BA", "Bank Account"): (4, 6),
	("WF-LA", "Leave Application"): (6, 6),
	("WF-LA", "Shift Request"): (6, 5),
	("WF-AR", "Attendance Request"): (6, 6),
	("WF-AR", "Compensatory Leave Request"): (6, 6),
	("WF-EC", "Expense Claim"): (7, 9),
	("WF-EC", "Employee Advance"): (7, 9),
	("WF-PAY", "Payroll Entry"): (5, 4),
	("WF-HR", "Salary Structure Assignment"): (5, 4),
	("WF-HR", "Employee Promotion"): (5, 4),
	("WF-HR", "Employee Transfer"): (5, 4),
	("WF-HR", "Job Offer"): (5, 4),
	("WF-BT", "Business Trip"): (6, 6),
}


def make_user(*roles):
	email = f"wf-{frappe.generate_hash(length=8)}@example.com"
	user = frappe.get_doc({"doctype": "User", "email": email, "first_name": "WF", "send_welcome_email": 0})
	user.insert(ignore_permissions=True)
	user.add_roles(*roles)
	return email


def make_po(total, state="Nháp", owner=None):
	"""An in-memory, not-new Purchase Order — never inserted."""
	po = frappe.get_doc(
		{
			"doctype": "Purchase Order",
			"name": f"PO-WF-{frappe.generate_hash(length=8)}",
			"company": "Miyano",
			"docstatus": 0,
			"workflow_state": state,
			"base_grand_total": total,
			"owner": owner or frappe.session.user,
		}
	)
	po.flags.ignore_permissions = True  # read permission is not what these tests check
	return po


def rows_from(built, state):
	return [t for t in built["transitions"] if t["state"] == state]


class TestWorkflowBuilder(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.m = load_matrix()
		cls.purchase_user = make_user("Purchase User")
		cls.purchase_manager = make_user("Purchase Manager")
		cls.po_workflow = frappe.get_doc(build_workflow(cls.m, "WF-PO", "Purchase Order"))

	def tearDown(self):
		frappe.set_user("Administrator")

	def transitions_for(self, user, po):
		frappe.set_user(user)
		return [(t.action, t.next_state) for t in get_transitions(po, workflow=self.po_workflow)]

	# -- conditions ----------------------------------------------------------------------------

	def test_render_condition_substitutes_limits(self):
		out = render_condition("doc.a <= {H1} and doc.b > {H2} or doc.c <= {H3}")
		for field in ("h1", "h2", "h3"):
			self.assertIn(LIMIT_EXPR.format(f=field), out)
		self.assertNotIn("{H", out)
		self.assertEqual(render_condition("doc.is_return == 0"), "doc.is_return == 0")

	def test_limits_unset_does_not_raise(self):  # Review Focus 4
		frappe.db.set_single_value(LIMITS, "h1", None)
		po = make_po(total=1)
		self.assertEqual([a for a, _ in self.transitions_for(self.purchase_user, po)], ["Gửi duyệt"])

	def test_condition_compares_numbers(self):
		frappe.db.set_single_value(LIMITS, "h1", 100)
		self.assertEqual(self.transitions_for(self.purchase_user, make_po(50)), [("Duyệt", "Đã duyệt")])
		self.assertEqual(self.transitions_for(self.purchase_user, make_po(150)), [("Gửi duyệt", "Chờ TP")])

	def test_g11_appended_on_pending_states(self):
		built = build_workflow(self.m, "WF-PO", "Purchase Order")
		for t in built["transitions"]:
			pending = t["state"].startswith("Chờ")
			self.assertEqual(OWNER_CHECK in (t["condition"] or ""), pending, t)
			self.assertEqual(t["allow_self_approval"], 0 if pending else 1, t)
		self.assertNotIn(EMPLOYEE_CHECK, g11_condition("Purchase Order"))

		frappe.db.set_single_value(LIMITS, "h2", 100)
		own = make_po(50, state="Chờ TP", owner=self.purchase_manager)
		self.assertEqual(self.transitions_for(self.purchase_manager, own), [])
		other = make_po(50, state="Chờ TP", owner=self.purchase_user)
		self.assertEqual(
			self.transitions_for(self.purchase_manager, other),
			[("Duyệt", "Đã duyệt"), ("Từ chối", "Từ chối")],
		)

	def test_hr_g11_checks_employee_user(self):
		self.assertIn(EMPLOYEE_CHECK, g11_condition("Leave Application"))
		self.assertIn(OWNER_CHECK, g11_condition("Leave Application"))
		self.assertNotIn(EMPLOYEE_CHECK, g11_condition("Business Trip"))  # no employee field

		leave = build_workflow(self.m, "WF-LA", "Leave Application")
		for t in rows_from(leave, "Chờ TBP"):
			self.assertIn("doc.leave_approver == frappe.session.user", t["condition"])
			self.assertIn(EMPLOYEE_CHECK, t["condition"])
		shift = build_workflow(self.m, "WF-LA", "Shift Request")
		for t in rows_from(shift, "Chờ TBP"):
			self.assertIn("doc.approver == frappe.session.user", t["condition"])
			self.assertNotIn("leave_approver", t["condition"])

		# the approver files a leave for himself: leave_approver matches, the employee check must still stop him
		approver = self.purchase_manager
		condition = rows_from(leave, "Chờ TBP")[0]["condition"]
		doc = {"employee": "HR-EMP-WF", "leave_approver": approver, "owner": "someone-else@example.com"}

		def holds(employee_user):
			env = get_workflow_safe_globals()
			env["frappe"]["db"]["get_value"] = lambda *args: employee_user
			return frappe.safe_eval(condition, env, {"doc": frappe._dict(doc)})

		frappe.set_user(approver)
		self.assertFalse(holds(approver))
		self.assertTrue(holds("employee@example.com"))

	def test_per_doctype_condition_and_update_field(self):
		claim = build_workflow(self.m, "WF-EC", "Expense Claim")
		advance = build_workflow(self.m, "WF-EC", "Employee Advance")
		self.assertTrue(all("advance_amount" not in (t["condition"] or "") for t in claim["transitions"]))
		ktt = [t["condition"] for t in rows_from(advance, "Chờ KTT") if t["action"] == "Duyệt"]
		self.assertEqual(len(ktt), 2)
		self.assertTrue(all("doc.advance_amount" in c and LIMIT_EXPR.format(f="h3") in c for c in ktt))

		def approved(built):
			return next(s for s in built["states"] if s["state"] == "Đã duyệt")

		self.assertEqual(
			(approved(claim)["update_field"], approved(claim)["update_value"]),
			("approval_status", "Approved"),
		)
		self.assertFalse(approved(advance).get("update_field"))

	def test_except_doctypes_drops_hu_submit_row_on_shift_request(self):
		def hu_rows(doctype):
			built = build_workflow(self.m, "WF-LA", doctype)
			return [
				t
				for t in rows_from(built, "Nháp")
				if t["action"] == "Gửi duyệt" and t["allowed"] in self.m.role_names("HU")
			]

		self.assertEqual(hu_rows("Shift Request"), [])
		self.assertTrue(hu_rows("Leave Application"))

	# -- structure -----------------------------------------------------------------------------

	def test_list_indicator_not_overridden(self):
		for code, doctype in EXPECTED_COUNTS:
			built = build_workflow(self.m, code, doctype)
			self.assertEqual(built["override_status"], 1, code)
			self.assertEqual(built["send_email_alert"], 1, code)
			self.assertEqual(built["is_active"], 1, code)
			self.assertEqual(built["workflow_state_field"], "workflow_state", code)
			self.assertEqual(built["document_type"], doctype)

	def test_first_states_obey_rules(self):
		problems = validate(self.m, SiteInfo.from_db())
		wf_errors = [e for e in problems.errors if e.split(" — ")[0] in self.m.workflows or "workflow" in e]
		self.assertEqual(wf_errors, [])

	def test_frappe_accepts_every_workflow(self):
		"""Workflow.validate_docstatus is pure — run it on every in-memory doc (nothing is inserted)."""
		self.assertEqual(
			sorted(EXPECTED_COUNTS),
			sorted((code, dt) for code, wf in self.m.workflows.items() for dt in wf["doctypes"]),
		)
		for (code, doctype), (n_states, n_transitions) in EXPECTED_COUNTS.items():
			built = build_workflow(self.m, code, doctype)
			self.assertEqual(
				(len(built["states"]), len(built["transitions"])), (n_states, n_transitions), code
			)
			frappe.get_doc(built).validate_docstatus()

	def test_workflow_name(self):
		self.assertEqual(workflow_name("WF-PO", "Purchase Order"), "WF-PO Purchase Order")
		self.assertEqual(workflow_name("WF-LA", "Shift Request"), "WF-LA Shift Request")
		self.assertEqual(workflow_name("WF-BT", "Business Trip"), "Cong Tac Approval")
		self.assertEqual(
			build_workflow(self.m, "WF-BT", "Business Trip")["workflow_name"], "Cong Tac Approval"
		)

	def test_allow_edit_by_state_type(self):
		edit = {
			s["state"]: s["allow_edit"] for s in build_workflow(self.m, "WF-PO", "Purchase Order")["states"]
		}
		self.assertEqual(
			edit,
			{
				"Nháp": "Purchase User",
				"Chờ TP": "MVL Khóa sửa",
				"Chờ BGĐ": "MVL Khóa sửa",
				"Đã duyệt": "Purchase Manager",
				"Từ chối": "Purchase User",
				"Đã hủy": "MVL Khóa sửa",
			},
		)
		edit = {s["state"]: s["allow_edit"] for s in build_workflow(self.m, "WF-SE", "Stock Entry")["states"]}
		self.assertEqual((edit["Nháp"], edit["Đã ghi sổ"]), ("Stock User", "Stock Manager"))

	def test_role_codes_expand_to_one_row_per_role(self):
		built = build_workflow(self.m, "WF-PO", "Purchase Order")
		reject = sorted(t["allowed"] for t in rows_from(built, "Chờ TP") if t["action"] == "Từ chối")
		self.assertEqual(reject, ["Purchase Manager", "Purchase Master Manager"])
		se = build_workflow(self.m, "WF-SE", "Stock Entry")
		post = sorted(t["allowed"] for t in rows_from(se, "Nháp") if t["action"] == "Ghi sổ")
		self.assertEqual(post, ["MVL Kho PDA", "Stock User"])

	def test_reopen_only_when_rejected_is_draft(self):
		def reopen(code, doctype):
			built = build_workflow(self.m, code, doctype)
			return sorted(
				t["allowed"]
				for t in built["transitions"]
				if (t["state"], t["action"]) == ("Từ chối", "Mở lại")
			)

		self.assertEqual(reopen("WF-PO", "Purchase Order"), ["Purchase User"])
		self.assertEqual(reopen("WF-SE", "Stock Entry"), ["MVL Kho PDA", "Stock User"])
		self.assertEqual(reopen("WF-BT", "Business Trip"), ["HR User"])
		self.assertEqual(reopen("WF-LA", "Leave Application"), [])  # Từ chối is doc_status 1 there

	def test_business_trip_keeps_existing_states_and_drops_outside_roles(self):
		built = build_workflow(self.m, "WF-BT", "Business Trip")
		self.assertEqual(
			[s["state"] for s in built["states"]],
			["Nháp", "Chờ COO duyệt", "COO đã duyệt", "Đã ra QĐ", "Hoàn tất", "Từ chối"],
		)
		allowed = {t["allowed"] for t in built["transitions"]}
		self.assertEqual(allowed, {"HR User", "MVL Approver", "HR Manager"})
		for t in rows_from(built, "Chờ COO duyệt"):
			self.assertIn("doc.approver_coo == frappe.session.user", t["condition"])


class TestSyncWorkflows(FrappeTestCase):
	"""Writes real Workflows — runs only on a test site."""

	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def setUp(self):
		require_test_site(self)
		sync_roles(load_matrix())  # allow_edit / allowed link to MVL roles such as "MVL Khóa sửa"

	def matrix(self):
		real = load_matrix()
		return small_matrix(
			doctypes={"Purchase Order": DocTypeEntry(state="matrix", perms={"PU": "CRW"}, workflow="WF-PO")},
			workflows={"WF-PO": real.workflows["WF-PO"]},
		)

	def test_creates_workflow_states_actions_and_list_column(self):
		m = self.matrix()
		sync_workflows(m)
		name = workflow_name("WF-PO", "Purchase Order")
		doc = frappe.get_doc("Workflow", name)
		self.assertEqual(doc.is_active, 1)
		self.assertEqual(len(doc.transitions), EXPECTED_COUNTS[("WF-PO", "Purchase Order")][1])
		for state in ("Chờ TP", "Chờ BGĐ", "Đã hủy"):
			self.assertTrue(frappe.db.exists("Workflow State", state))
		self.assertTrue(frappe.db.exists("Workflow Action Master", "Mở lại"))
		frappe.clear_cache(doctype="Purchase Order")
		self.assertEqual(frappe.get_meta("Purchase Order").get_field("workflow_state").in_list_view, 1)

	def test_second_run_writes_nothing(self):
		m = self.matrix()
		sync_workflows(m)
		name = workflow_name("WF-PO", "Purchase Order")
		before = frappe.db.get_value("Workflow", name, "modified")
		with patch.object(workflows, "_save") as save:
			sync_workflows(m)
		save.assert_not_called()
		self.assertEqual(frappe.db.get_value("Workflow", name, "modified"), before)
