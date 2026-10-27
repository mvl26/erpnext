"""Workflow guards H5, H10, H11 — ``erpnext.access.workflow_guard`` (Task 17).

WORKFLOW TEST SAFETY: on site miyano no test inserts or activates a Workflow (the Redis "workflow" hash is
shared with production). ``TestWorkflowGuard`` calls the guards directly, in the order frappe calls them, on
in-memory documents: the workflow lookup inside the guard module is patched to in-memory Workflow docs built
from the real ``workflows.json``, ``_doc_before_save`` is set by hand to simulate a save. The end-to-end cases
that need a really active workflow live in ``TestWorkflowGuardOnTestSite`` and skip unless the site is a test
site on which the RBAC sync has activated the workflows (``require_test_site``).
"""

import datetime
from unittest.mock import MagicMock, patch

import frappe
import frappe.client
from frappe.model.workflow import (
	apply_workflow,
	get_workflow_name,
	is_transition_condition_satisfied,
	set_workflow_state_on_action,
)
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from erpnext.access import workflow_guard
from erpnext.access.permissions.matrix import load_matrix
from erpnext.access.permissions.workflows import build_workflow, workflow_name
from erpnext.access.tests.helpers import require_test_site
from erpnext.accounts.deferred_revenue import book_revenue_via_journal_entry
from erpnext.accounts.doctype.journal_entry.journal_entry import JournalEntry
from erpnext.accounts.doctype.payment_reconciliation.payment_reconciliation import reconcile_dr_cr_note
from erpnext.accounts.utils import create_gain_loss_journal

LIMITS = "MVL Approval Limits"
H1, H2, H3 = 50_000_000, 500_000_000, 20_000_000
WORKFLOWS = {
	"Purchase Order": "WF-PO",
	"Sales Invoice": "WF-SI",
	"Payment Entry": "WF-PE",
	"Journal Entry": "WF-JE",
	"Stock Entry": "WF-SE",
	"Leave Application": "WF-LA",
	"Bank Account": "WF-BA",
}
GUARD = "erpnext.access.workflow_guard"


def make_user(*roles):
	email = f"wg-{frappe.generate_hash(length=8)}@example.com"
	user = frappe.get_doc({"doctype": "User", "email": email, "first_name": "WG", "send_welcome_email": 0})
	user.insert(ignore_permissions=True)
	user.add_roles(*roles)
	return email


def row(**values):
	return {"name": f"wg-row-{frappe.generate_hash(length=8)}", **values}


def make_doc(doctype, state, owner, docstatus=0, name=None, **values):
	"""An in-memory, not-new document as it sits in the database — never inserted."""
	doc = frappe.get_doc(
		{
			"doctype": doctype,
			"name": name or f"WG-{frappe.generate_hash(length=8)}",
			"docstatus": docstatus,
			"owner": owner,
			**values,
		}
	)
	doc.workflow_state = state
	return doc


def saving(before, state=None, docstatus=None, **changes):
	"""The copy a save hands to the hooks: same name and rows, ``_doc_before_save`` = ``before``."""
	doc = frappe.get_doc(before.as_dict())
	doc.workflow_state = before.workflow_state if state is None else state
	doc.docstatus = before.docstatus if docstatus is None else docstatus
	doc.update(changes)
	doc._doc_before_save = before
	return doc


def bare_row(doctype):
	"""A bare row in the doctype's table — only so a Comment's Dynamic Link to it validates."""
	doc = frappe.get_doc({"doctype": doctype, "name": f"WG-{frappe.generate_hash(length=8)}"})
	doc.db_insert()
	return doc.name


def markers(doc):
	return frappe.get_all(
		"Comment",
		filters={"reference_doctype": doc.doctype, "reference_name": doc.name, "comment_type": "Info"},
		fields=["owner", "content"],
	)


class TestWorkflowGuard(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		m = load_matrix()
		cls.workflows = {dt: frappe.get_doc(build_workflow(m, code, dt)) for dt, code in WORKFLOWS.items()}
		cls.pu = make_user("Purchase User")
		cls.pm = make_user("Purchase Manager")
		cls.ap = make_user("MVL Approver")
		cls.pm_ap = make_user("Purchase Manager", "MVL Approver")
		cls.au = make_user("Accounts User")
		cls.am = make_user("Accounts Manager")
		cls.stu = make_user("Stock User")
		cls.stm = make_user("Stock Manager")
		cls.hm = make_user("HR Manager")
		workflow_guard.reload_rules()

	def setUp(self):
		for field, value in (("h1", H1), ("h2", H2), ("h3", H3)):
			frappe.db.set_single_value(LIMITS, field, value)
		enabled = patch.object(workflow_guard, "is_enabled", return_value=True)
		self.enabled = enabled.start()
		self.addCleanup(enabled.stop)
		self.real_active_workflow = workflow_guard._active_workflow
		lookup = patch.object(workflow_guard, "_active_workflow", side_effect=self.workflows.get)
		self.lookup = lookup.start()
		self.addCleanup(lookup.stop)
		self.addCleanup(frappe.set_user, "Administrator")

	def po(self, total, state="Nháp", owner=None, **values):
		values.setdefault("company", "Miyano")
		return make_doc("Purchase Order", state, owner or self.pu, base_grand_total=total, **values)

	def save_hooks(self, doc):
		"""``before_validate`` → (controller) → ``validate`` → ``before_submit`` on a submit, as frappe runs them."""
		workflow_guard.before_validate(doc)
		workflow_guard.validate(doc)
		if doc.docstatus == 1:
			workflow_guard.before_submit(doc)

	# -- gates ---------------------------------------------------------------------------------

	def test_disabled_flag_is_noop(self):
		self.enabled.return_value = False
		doc = saving(self.po(H1 * 10), state="Đã duyệt", docstatus=1)
		doc.flags.mvl_wf_step = ("Chờ TP", "Đã duyệt")
		frappe.set_user(self.pm)
		self.save_hooks(doc)
		workflow_guard.on_change(doc)
		self.lookup.assert_not_called()
		self.assertEqual(markers(doc), [])

	def test_unmanaged_workflow_is_out_of_scope(self):
		"""assetcore's and the legacy workflows are left to frappe — every guard is a no-op on them."""
		self.lookup.side_effect = self.real_active_workflow
		frappe.set_user(self.pm)
		for unmanaged in ("IMM-09 Repair Workflow", "MVL Duyệt thanh toán", "SO Test Workflow"):
			with (
				patch(f"{GUARD}.get_workflow_name", return_value=unmanaged),
				patch.object(frappe, "get_cached_doc") as get_cached_doc,
			):
				doc = saving(self.po(H1 * 10, state="Chờ TP", owner=self.pm), state="Đã duyệt", docstatus=1)
				doc.order_confirmation_no = "SỬA"
				self.save_hooks(doc)
				workflow_guard.on_change(doc)
				cancelled = saving(self.po(H1, state="Đã duyệt", docstatus=1), docstatus=2)
				workflow_guard.before_cancel(cancelled)
				get_cached_doc.assert_not_called()
			self.assertEqual(cancelled.workflow_state, "Đã duyệt")
			self.assertEqual(markers(doc), [])

	def test_workflows_off_manages_nothing(self):
		workflow_guard.reload_rules()
		self.addCleanup(workflow_guard.reload_rules)
		with patch.object(workflow_guard, "workflows_on", return_value=False):
			self.assertEqual(workflow_guard._managed_names(), frozenset())

	def test_managed_workflows_are_found(self):
		workflow_guard.reload_rules()
		self.addCleanup(workflow_guard.reload_rules)
		with patch.object(workflow_guard, "workflows_on", return_value=True):
			managed = workflow_guard._managed_names()
		self.assertIn("WF-PO Purchase Order", managed)
		self.assertIn("Cong Tac Approval", managed)  # WF-BT keeps hrms' name
		self.assertNotIn("SO Test Workflow", managed)
		wf = self.workflows["Purchase Order"]
		with (
			patch(f"{GUARD}.get_workflow_name", return_value="WF-PO Purchase Order"),
			patch.object(frappe, "get_cached_doc", return_value=wf) as get_cached_doc,
		):
			self.assertIs(self.real_active_workflow("Purchase Order"), wf)
		get_cached_doc.assert_called_once_with("Workflow", "WF-PO Purchase Order")

	def test_doctype_without_workflow_passes(self):
		self.lookup.side_effect = lambda doctype: None
		frappe.set_user(self.pm)
		self.save_hooks(saving(self.po(H1 * 10), state="Đã duyệt", docstatus=0))

	def test_administrator_job_passes(self):  # Review Focus 5
		je = make_doc("Journal Entry", "Nháp", self.au)
		self.save_hooks(saving(je, docstatus=1))  # no transition Nháp → Đã ghi sổ at all in WF-JE
		self.save_hooks(saving(je, state="Đã ghi sổ", docstatus=0))
		self.lookup.assert_not_called()

	def test_system_generated_je_passes(self):  # T24
		frappe.set_user(self.au)
		je = make_doc("Journal Entry", "Nháp", self.au)
		with self.assertRaises(frappe.PermissionError):
			workflow_guard.before_submit(saving(je, docstatus=1))
		system = saving(je, docstatus=1, user_remark="khấu hao")
		system.flags.ignore_permissions = True
		self.save_hooks(system)

	# -- system JEs created inside a user's PE/SI/PI submit or reconciliation --------------------

	def submit_through_h11(self):
		"""Patch ``JournalEntry.save``/``submit``: nothing is written, the submit runs H11 as frappe would."""
		submitted = []

		def submit(doc):
			doc.docstatus = 1
			workflow_guard.before_submit(doc)
			submitted.append(doc)

		for method, effect in (("save", None), ("submit", submit)):
			patcher = patch.object(JournalEntry, method, autospec=True, side_effect=effect)
			patcher.start()
			self.addCleanup(patcher.stop)
		return submitted

	def party(self, doctype):
		name = frappe.db.get_value(doctype, {}, "name")
		if not name:
			self.skipTest(f"site has no {doctype}")
		return name

	def test_gain_loss_journal_skips_h11(self):  # accounts/utils.py create_gain_loss_journal
		submitted = self.submit_through_h11()
		company = frappe.get_cached_doc("Company", "Miyano")
		frappe.set_user(self.au)
		create_gain_loss_journal(
			"Miyano",
			None,
			"Customer",
			self.party("Customer"),
			company.default_receivable_account,
			company.exchange_gain_loss_account,
			100,
			"debit",
			"credit",
			"Sales Invoice",
			"WG-SI",
			None,
			"Payment Entry",
			"WG-PE",
			None,
			None,
			None,
		)
		self.assertEqual([je.flags.ignore_permissions for je in submitted], [True])

	def test_credit_note_journal_skips_h11(self):  # payment_reconciliation.py reconcile_dr_cr_note
		submitted = self.submit_through_h11()
		company = frappe.get_cached_doc("Company", "Miyano")
		note = frappe._dict(
			voucher_type="Sales Invoice",
			voucher_no="WG-SI-RET",
			dr_or_cr="credit_in_account_currency",
			account=company.default_receivable_account,
			party_type="Customer",
			party=self.party("Customer"),
			allocated_amount=100,
			unadjusted_amount=100,
			against_voucher_type="Sales Invoice",
			against_voucher="WG-SI",
			cost_center=None,
			exchange_rate=1,
			currency=company.default_currency,
			difference_amount=0,
		)
		frappe.set_user(self.au)
		reconcile_dr_cr_note([note], "Miyano")
		self.assertEqual([je.flags.ignore_permissions for je in submitted], [True])

	def test_advance_reconcile_journal_skips_h11(self):  # accounts_controller.py create_advance_and_reconcile
		submitted = self.submit_through_h11()
		invoice = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"name": f"WG-SI-{frappe.generate_hash(length=6)}",
				"company": "Miyano",
				"customer": self.party("Customer"),
				"posting_date": nowdate(),
				"outstanding_amount": 100,
			}
		)
		link = frappe._dict(primary_role="Supplier", primary_party=self.party("Supplier"))
		frappe.set_user(self.au)
		invoice.create_advance_and_reconcile(link)
		self.assertEqual([je.flags.ignore_permissions for je in submitted], [True])

	def test_deferred_accounting_journal_skips_h11(
		self,
	):  # deferred_revenue.py book_revenue_via_journal_entry
		submitted = self.submit_through_h11()
		company = frappe.get_cached_doc("Company", "Miyano")
		invoice = frappe._dict(
			doctype="Sales Invoice", name="WG-SI-DEF", company="Miyano", log_error=MagicMock()
		)
		item = frappe._dict(name="WG-SII-DEF")
		with patch.object(frappe.db, "commit") as commit, patch.object(frappe.db, "rollback") as rollback:
			frappe.set_user(self.au)
			book_revenue_via_journal_entry(
				invoice,
				company.default_income_account,
				company.default_receivable_account,
				100,
				100,
				nowdate(),
				None,
				company.default_currency,
				company.cost_center,
				item,
				deferred_process=None,
				submit=True,
			)
			frappe.set_user("Administrator")
		invoice.log_error.assert_not_called()
		rollback.assert_not_called()
		commit.assert_called_once()
		self.assertEqual([je.flags.ignore_permissions for je in submitted], [True])

	# -- H11 -----------------------------------------------------------------------------------

	def test_api_submit_po_over_limit_blocked(self):  # T19
		frappe.set_user(self.pu)
		doc = saving(self.po(H1 + 1), docstatus=1)
		workflow_guard.before_validate(doc)
		workflow_guard.validate(doc)
		with self.assertRaisesRegex(frappe.PermissionError, "Phải duyệt qua quy trình"):
			workflow_guard.before_submit(doc)

	def test_api_submit_po_within_limit_passes_and_sets_state(self):
		frappe.set_user(self.pu)
		doc = saving(self.po(H1), docstatus=1)
		self.save_hooks(doc)
		self.assertEqual(doc.workflow_state, "Nháp")  # R-17: the guard never assigns the state
		with patch("frappe.get_doc", return_value=self.workflows["Purchase Order"]):
			set_workflow_state_on_action(doc, "WF-PO Purchase Order", "submit")
		self.assertEqual(doc.workflow_state, "Đã duyệt")  # frappe's first doc_status 1 state

		frappe.set_user(self.pm)  # PM has no transition out of Nháp
		with self.assertRaises(frappe.PermissionError):
			workflow_guard.before_submit(saving(self.po(H1, owner=self.pm), docstatus=1))

	def test_insert_then_submit_receive_payment_entry_passes(self):  # T51 — Bank Reconciliation Tool
		frappe.set_user(self.au)
		values = {"company": "Miyano", "payment_type": "Receive", "base_paid_amount": H3 * 100}
		inserted = make_doc("Payment Entry", None, self.au, **values)
		inserted.set("__islocal", 1)
		self.save_hooks(inserted)  # insert: no _doc_before_save, empty state → first state
		workflow_guard.on_change(inserted)

		stored = make_doc("Payment Entry", "Nháp", self.au, name=inserted.name, **values)
		self.save_hooks(saving(stored, docstatus=1))  # submit: state kept, AU self-approves Receive

		direct = make_doc("Payment Entry", None, self.au, docstatus=1, **values)
		direct.set("__islocal", 1)
		self.save_hooks(direct)  # frappe.client.insert with docstatus 1

		pay = make_doc("Payment Entry", "Nháp", self.au, **{**values, "payment_type": "Pay"})
		with self.assertRaises(frappe.PermissionError):
			workflow_guard.before_submit(saving(pay, docstatus=1))

	def test_direct_submit_from_pending_state_blocked(self):
		frappe.set_user(self.ap)
		doc = saving(self.po(H2 * 2, state="Chờ BGĐ"), docstatus=1)
		with self.assertRaises(frappe.PermissionError):
			workflow_guard.before_submit(doc)  # AP must take the transition, not submit around it

	# -- R-23, R-16 ----------------------------------------------------------------------------

	def test_api_edit_and_approve_in_one_call_rechecks_limit(self):  # R-16
		frappe.set_user(self.pu)
		before = self.po(1)
		doc = saving(before, state="Đã duyệt", docstatus=1, base_grand_total=1_000_000_000)
		wf = self.workflows["Purchase Order"]
		self_approve = next(t for t in wf.transitions if t.state == "Nháp" and t.next_state == "Đã duyệt")
		self.assertTrue(is_transition_condition_satisfied(self_approve, before))  # what frappe looks at
		workflow_guard.before_validate(doc)  # PU may edit a draft
		with self.assertRaisesRegex(
			frappe.PermissionError, "Không có bước duyệt hợp lệ .*bước Duyệt sai trên giá trị hiện tại"
		):
			workflow_guard.validate(doc)
		frappe.set_user(self.pm)  # PM has no Nháp → Đã duyệt transition at all
		with self.assertRaisesRegex(frappe.PermissionError, "vai trò của bạn không có bước duyệt này"):
			workflow_guard.validate(saving(self.po(1), state="Đã duyệt", docstatus=1))
		frappe.set_user(self.pu)

		self.save_hooks(saving(self.po(1), state="Đã duyệt", docstatus=1, base_grand_total=H1))

	def test_submit_with_pending_state_blocked(self):  # R-23
		frappe.set_user(self.pu)
		doc = saving(self.po(H1 * 2), state="Chờ TP", docstatus=1)
		with self.assertRaisesRegex(frappe.PermissionError, "không khớp"):
			workflow_guard.validate(doc)
		self.assertIsNone(doc.flags.mvl_wf_step)

	def test_draft_save_into_submitted_state_blocked(self):  # R-23
		frappe.set_user(self.pu)
		with self.assertRaisesRegex(frappe.PermissionError, "không khớp"):
			workflow_guard.validate(saving(self.po(H1), state="Đã duyệt", docstatus=0))

	def test_send_for_approval_passes_without_marker(self):
		frappe.set_user(self.pu)
		doc = saving(self.po(H1 * 2), state="Chờ TP")
		self.save_hooks(doc)
		self.assertIsNone(doc.flags.mvl_wf_step)  # only steps leaving "Chờ …" are marked

	def test_amend_starts_from_draft(self):  # T34
		frappe.set_user(self.pu)
		amended = self.po(H1, state=None, amended_from=f"WG-OLD-{frappe.generate_hash(length=6)}")
		amended.set("__islocal", 1)
		self.save_hooks(amended)  # workflow_state is no_copy: empty → Nháp, no transition to judge
		stale = self.po(H1, state="Đã hủy", amended_from=amended.amended_from)
		stale.set("__islocal", 1)
		with self.assertRaises(frappe.PermissionError):
			workflow_guard.validate(stale)  # a copied "Đã hủy" state cannot ride along

	def test_cancel_of_pre_workflow_doc_allowed(self):  # Review Focus 3
		frappe.set_user(self.pm)
		before = self.po(H1 * 2, state=None, docstatus=1)  # submitted before the workflow existed
		doc = saving(before, docstatus=2)
		# frappe runs only before_cancel on cancel (document.py:1151, 416): no H5/H10/H11, no marker
		workflow_guard.before_cancel(doc)
		workflow_guard.before_submit(doc)
		workflow_guard.on_change(doc)
		self.assertEqual(markers(doc), [])
		self.assertIsNone(doc.flags.mvl_wf_step)
		self.assertEqual(doc.workflow_state, "Đã hủy")

	def test_cancel_moves_to_cancelled_state(self):
		for user, ignore in ((self.pm, False), ("Administrator", False), (self.pm, True)):  # no bypass
			frappe.set_user(user)
			doc = saving(self.po(H1, state="Đã duyệt", docstatus=1), docstatus=2)
			doc.flags.ignore_permissions = ignore
			workflow_guard.before_cancel(doc)
			self.assertEqual(doc.workflow_state, "Đã hủy", (user, ignore))

		frappe.set_user(self.pm)
		wf = frappe.copy_doc(self.workflows["Purchase Order"])
		wf.append(
			"states", {"state": "Hủy theo transition", "doc_status": "2", "allow_edit": "Purchase Manager"}
		)
		self.lookup.side_effect = lambda doctype: wf
		doc = saving(self.po(H1, state="Đã duyệt", docstatus=1), state="Hủy theo transition", docstatus=2)
		workflow_guard.before_cancel(doc)
		self.assertEqual(doc.workflow_state, "Hủy theo transition")  # an existing cancelled state is kept

		self.lookup.side_effect = self.workflows.get
		account = make_doc("Bank Account", "Đã duyệt", self.au, docstatus=2)
		workflow_guard.before_cancel(account)  # WF-BA has no doc_status 2 state
		self.assertEqual(account.workflow_state, "Đã duyệt")

		self.enabled.return_value = False
		doc = saving(self.po(H1, state="Đã duyệt", docstatus=1), docstatus=2)
		workflow_guard.before_cancel(doc)
		self.assertEqual(doc.workflow_state, "Đã duyệt")

	# -- H5 ------------------------------------------------------------------------------------

	def pending_po(self):
		return self.po(
			H1 * 2,
			state="Chờ TP",
			schedule_date=datetime.date(2026, 10, 30),
			order_confirmation_no=None,
			items=[row(item_code="WG-ITEM", qty=10.0, rate=100.0, schedule_date=datetime.date(2026, 10, 30))],
		)

	def test_edit_while_pending_blocked_even_for_owner(self):  # T26
		frappe.set_user(self.pu)
		before = self.pending_po()
		edits = [
			{"order_confirmation_no": "SỬA"},
			{"schedule_date": "2026-11-30"},
		]
		for change in edits:
			with self.assertRaisesRegex(frappe.ValidationError, "không được sửa nội dung"):
				workflow_guard.before_validate(saving(before, **change))
		doc = saving(before)
		doc.items[0].qty = 11
		with self.assertRaisesRegex(frappe.ValidationError, "không được sửa nội dung"):
			workflow_guard.before_validate(doc)
		doc = saving(before)
		doc.append("items", row(item_code="WG-ITEM", qty=1))
		with self.assertRaises(frappe.ValidationError):
			workflow_guard.before_validate(doc)
		doc = saving(before)
		doc.set("items", [])
		with self.assertRaises(frappe.ValidationError):
			workflow_guard.before_validate(doc)

	def test_approval_without_edits_passes_with_normalised_values(self):
		frappe.set_user(self.pm)
		before = self.pending_po()
		doc = saving(
			before, state="Đã duyệt", docstatus=1, schedule_date="2026-10-30", order_confirmation_no=""
		)
		doc.items[0].qty = 10  # int vs the stored float
		doc.items[0].schedule_date = "2026-10-30"
		self.save_hooks(doc)
		self.assertEqual(doc.flags.mvl_wf_step, ("Chờ TP", "Đã duyệt"))

	def test_fetch_from_field_is_an_edit_unless_frappe_refilled_it(self):
		link = frappe._dict(fieldname="supplier", fieldtype="Link", options="Supplier")
		plain = frappe._dict(fieldname="x", fieldtype="Data", fetch_from="supplier.supplier_name")
		refill = frappe._dict(plain, fetch_if_empty=1)

		def changed(df, new, old, **values):
			fields = {"supplier": link, "x": df}
			meta = frappe._dict(fields=[df], get_field=fields.get)
			new_doc = {"supplier": "NCC-1", "docstatus": 0, "x": new, **values}
			return workflow_guard._changed_fields(meta, new_doc, {"x": old}, set())

		with patch.object(frappe.db, "get_value", return_value="Tên NCC"):
			# plain fetch_from: frappe overwrites it from a set link, except on a submit
			self.assertFalse(changed(plain, "Tên NCC mới", "Tên NCC"))
			self.assertTrue(changed(plain, "Tên NCC mới", "Tên NCC", docstatus=1))
			self.assertFalse(changed(frappe._dict(plain, allow_on_submit=1), "Mới", "Cũ", docstatus=1))
			self.assertTrue(changed(plain, "Gõ tay", "", supplier=None))
			# fetch_if_empty: only an empty field refilled with the link's value is not an edit
			self.assertFalse(changed(refill, "Tên NCC", None))
			self.assertTrue(changed(refill, "Gõ tay", None))
			self.assertTrue(changed(refill, "Gõ tay", "Tên NCC"))

	def test_editor_role_may_edit_draft(self):
		frappe.set_user(self.pu)
		workflow_guard.before_validate(saving(self.po(1), order_confirmation_no="SỬA"))

	def test_update_field_of_target_state_is_not_content(self):
		frappe.set_user(self.hm)
		before = make_doc("Leave Application", "Chờ HCNS", self.pu, status="Open", description="nghỉ")
		self.save_hooks(saving(before, state="Đã duyệt", docstatus=1, status="Approved"))
		with self.assertRaises(frappe.ValidationError):
			workflow_guard.before_validate(
				saving(before, state="Đã duyệt", docstatus=1, status="Approved", description="khác")
			)

	def test_approver_passes_when_controller_resets_posting_time(self):  # R-15
		frappe.set_user(self.am)
		before = make_doc(
			"Sales Invoice",
			"Chờ KTT",
			self.au,
			company="Miyano",
			is_return=1,
			set_posting_time=0,
			posting_date=datetime.date(2026, 10, 1),
			posting_time=datetime.timedelta(hours=9),
		)
		doc = saving(before, state="Đã ghi sổ", docstatus=1)
		workflow_guard.before_validate(doc)  # before the controller: nothing the approver typed changed
		doc.validate_posting_time()  # the controller's validate: set_posting_time = 0 → now
		self.assertNotEqual(str(doc.posting_date), "2026-10-01")
		with self.assertRaises(frappe.ValidationError):
			workflow_guard.before_validate(doc)  # why H5 cannot sit in validate
		workflow_guard.validate(doc)
		workflow_guard.before_submit(doc)
		self.assertEqual(doc.flags.mvl_wf_step, ("Chờ KTT", "Đã ghi sổ"))

	def test_approver_passes_on_putaway_stock_entry(self):  # R-15, putaway
		frappe.set_user(self.stm)
		values = {"company": "Miyano", "stock_entry_type": "Material Receipt", "purpose": "Material Receipt"}
		for putaway, blocked in ((1, False), (0, True)):
			before = make_doc(
				"Stock Entry",
				"Chờ trưởng kho",
				self.stu,
				apply_putaway_rule=putaway,
				items=[row(item_code="WG-ITEM", qty=10.0, t_warehouse="Stores - M")],
				**values,
			)
			doc = saving(before, state="Đã ghi sổ", docstatus=1)
			doc.items[0].qty = 6  # what apply_putaway_rule does in Stock Entry.before_validate
			doc.append("items", row(item_code="WG-ITEM", qty=4.0, t_warehouse="Kho khác - M"))
			if blocked:
				with self.assertRaises(frappe.ValidationError):
					workflow_guard.before_validate(doc)
			else:
				self.save_hooks(doc)

	# -- H10 -----------------------------------------------------------------------------------

	def test_owner_cannot_approve(self):
		frappe.set_user(self.pm)
		doc = saving(self.po(H1 * 2, state="Chờ TP", owner=self.pm), state="Đã duyệt", docstatus=1)
		with self.assertRaisesRegex(frappe.PermissionError, "tự duyệt"):
			workflow_guard.validate(doc)

	def test_employee_cannot_approve_own_hr_document(self):
		frappe.set_user(self.hm)
		before = make_doc("Leave Application", "Chờ HCNS", self.pu, employee="HR-EMP-WG", status="Open")
		doc = saving(before, state="Đã duyệt", docstatus=1, status="Approved")
		with patch(f"{GUARD}._employee_user", return_value=self.hm):
			with self.assertRaisesRegex(frappe.PermissionError, "của chính mình"):
				workflow_guard.validate(doc)

	def stored_po(self, total, state):
		"""A pending PO whose name exists in the table, so marker Comments can reference it."""
		return self.po(total, state=state, name=bare_row("Purchase Order"))

	def add_marker(self, doc, user, text, creation):
		frappe.set_user(user)
		comment = doc.add_comment("Info", text)
		frappe.db.set_value("Comment", comment.name, "creation", creation, update_modified=False)

	def test_same_user_cannot_approve_two_steps(self):  # T30
		before = self.stored_po(H2 * 2, "Chờ BGĐ")
		self.add_marker(before, self.pm_ap, "MVL-DUYET: Chờ TP → Chờ BGĐ", "2026-10-01 09:00:00")
		frappe.set_user(self.pm_ap)
		with self.assertRaisesRegex(frappe.PermissionError, "đã duyệt một bước"):
			workflow_guard.validate(saving(before, state="Đã duyệt", docstatus=1))
		frappe.set_user(self.ap)
		workflow_guard.validate(saving(before, state="Đã duyệt", docstatus=1))

	def test_api_approval_leaves_marker_for_h10(self):  # R-18
		frappe.set_user(self.pm_ap)
		step1 = saving(self.stored_po(H2 * 2, "Chờ TP"), state="Chờ BGĐ")
		self.save_hooks(step1)  # e.g. frappe.client.save with workflow_state = "Chờ BGĐ"
		workflow_guard.on_change(step1)
		workflow_guard.on_change(step1)  # on_change also fires from db_set: one marker only
		self.assertEqual(
			[(m.owner, m.content) for m in markers(step1)], [(self.pm_ap, "MVL-DUYET: Chờ TP → Chờ BGĐ")]
		)

		step2 = saving(self.po(H2 * 2, state="Chờ BGĐ", name=step1.name), state="Đã duyệt", docstatus=1)
		with self.assertRaisesRegex(frappe.PermissionError, "đã duyệt một bước"):
			workflow_guard.validate(step2)  # e.g. apply_workflow "Duyệt"

	def test_rejection_restarts_the_chain(self):
		before = self.stored_po(H2 * 2, "Chờ TP")
		self.add_marker(before, self.pm_ap, "MVL-DUYET: Chờ TP → Chờ BGĐ", "2026-10-01 09:00:00")
		self.add_marker(before, self.ap, "MVL-DUYET: Chờ BGĐ → Từ chối", "2026-10-01 10:00:00")
		frappe.set_user(self.pm_ap)  # resubmitted after the rejection: the same TP judges the new version
		doc = saving(before, state="Chờ BGĐ")
		workflow_guard.validate(doc)
		self.assertEqual(doc.flags.mvl_wf_step, ("Chờ TP", "Chờ BGĐ"))

	# -- registration --------------------------------------------------------------------------

	def test_hooks_registered(self):
		events = frappe.get_hooks("doc_events")["*"]
		self.assertIn(f"{GUARD}.before_validate", events["before_validate"])
		self.assertIn(f"{GUARD}.validate", events["validate"])
		self.assertIn(f"{GUARD}.before_submit", events["before_submit"])
		self.assertIn(f"{GUARD}.before_cancel", events["before_cancel"])
		self.assertIn(f"{GUARD}.on_change", events["on_change"])
		self.assertIn("erpnext.supply_notification.events.on_change", events["on_change"])
		own = frappe.get_hooks("doc_events", app_name="erpnext")["*"]
		self.assertEqual(own["validate"][-1], f"{GUARD}.validate")  # after the other erpnext validate hooks
		self.assertIn(
			"erpnext.support.doctype.service_level_agreement.service_level_agreement.apply", own["validate"]
		)


# -- end to end: needs the RBAC workflows active (test site only) -----------------------------------


def _company():
	return frappe.db.get_single_value("Global Defaults", "default_company") or frappe.db.get_value(
		"Company", {}, "name"
	)


def _leaf(doctype, **filters):
	return frappe.db.get_value(doctype, {"is_group": 0, **filters}, "name")


def _ensure(doctype, filters, values):
	name = frappe.db.get_value(doctype, filters, "name")
	if name:
		return name
	doc = frappe.get_doc({"doctype": doctype, **values})
	doc.insert(ignore_permissions=True)
	return doc.name


class TestWorkflowGuardOnTestSite(FrappeTestCase):
	"""Real documents through ``frappe.client`` and ``apply_workflow``. Precondition: the RBAC sync has run on
	the test site (``mvl_rbac_test_site`` set), so the Workflows and their ``workflow_state`` columns exist —
	these tests never create a Workflow themselves."""

	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def setUp(self):
		require_test_site(self)
		enabled = patch.object(workflow_guard, "is_enabled", return_value=True)
		enabled.start()
		self.addCleanup(enabled.stop)
		self.addCleanup(frappe.set_user, "Administrator")
		for field, value in (("h1", H1), ("h2", H2), ("h3", H3)):
			frappe.db.set_single_value(LIMITS, field, value)
		self.company = _company()
		self.warehouse = _leaf("Warehouse", company=self.company)

	def require_workflow(self, doctype):
		if get_workflow_name(doctype) != workflow_name(WORKFLOWS[doctype], doctype):
			self.skipTest(f"cần workflow RBAC đang bật cho {doctype}")

	# -- fixtures --------------------------------------------------------------------------------

	def supplier(self):
		return _ensure(
			"Supplier",
			{"supplier_name": "_Test WG Supplier"},
			{"supplier_name": "_Test WG Supplier", "supplier_group": _leaf("Supplier Group")},
		)

	def item(self):
		return _ensure(
			"Item",
			{"item_code": "_TEST-WG-ITEM"},
			{
				"item_code": "_TEST-WG-ITEM",
				"item_name": "_Test WG Item",
				"item_group": _leaf("Item Group"),
				"stock_uom": frappe.db.get_value("UOM", {}, "name"),
				"is_stock_item": 1,
			},
		)

	def purchase_order(self, rate, user):
		frappe.set_user(user)
		po = frappe.get_doc(
			{
				"doctype": "Purchase Order",
				"company": self.company,
				"supplier": self.supplier(),
				"transaction_date": nowdate(),
				"schedule_date": add_days(nowdate(), 7),
				"set_warehouse": self.warehouse,
				"items": [
					{
						"item_code": self.item(),
						"qty": 1,
						"rate": rate,
						"schedule_date": add_days(nowdate(), 7),
						"warehouse": self.warehouse,
					}
				],
			}
		)
		po.insert()
		return po

	def journal_entry(self, user, **flags):
		frappe.set_user(user)
		cash = _leaf("Account", company=self.company, account_type="Cash")
		expense = _leaf("Account", company=self.company, root_type="Expense", account_type="")
		je = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"company": self.company,
				"posting_date": nowdate(),
				"accounts": [
					{"account": expense, "debit_in_account_currency": 100},
					{"account": cash, "credit_in_account_currency": 100},
				],
			}
		)
		je.flags.update(flags)
		je.insert()
		return je

	def state(self, doc):
		return frappe.db.get_value(doc.doctype, doc.name, ["docstatus", "workflow_state"])

	# -- cases -----------------------------------------------------------------------------------

	def test_api_submit_po_over_limit_blocked(self):  # T19
		self.require_workflow("Purchase Order")
		pu = make_user("Purchase User")
		po = self.purchase_order(H1 + 1, pu)
		with self.assertRaises(frappe.PermissionError):
			frappe.client.submit(po.as_dict())
		self.assertEqual(self.state(po), (0, "Nháp"))

	def test_api_submit_po_within_limit_passes_and_sets_state(self):
		self.require_workflow("Purchase Order")
		pu = make_user("Purchase User")
		po = self.purchase_order(1000, pu)
		frappe.client.submit(po.as_dict())
		self.assertEqual(self.state(po), (1, "Đã duyệt"))

	def test_insert_then_submit_receive_payment_entry_passes(self):  # T51
		self.require_workflow("Payment Entry")
		au = make_user("Accounts User")
		customer = _ensure(
			"Customer",
			{"customer_name": "_Test WG Customer"},
			{"customer_name": "_Test WG Customer", "customer_group": _leaf("Customer Group")},
		)
		frappe.set_user(au)
		company = frappe.get_cached_doc("Company", self.company)
		pe = frappe.get_doc(
			{
				"doctype": "Payment Entry",
				"payment_type": "Receive",
				"company": self.company,
				"posting_date": nowdate(),
				"party_type": "Customer",
				"party": customer,
				"paid_from": company.default_receivable_account,
				"paid_to": company.default_cash_account,
				"paid_amount": H3 * 10,
				"received_amount": H3 * 10,
				"source_exchange_rate": 1,
				"target_exchange_rate": 1,
			}
		)
		pe.insert()
		pe.submit()
		self.assertEqual(self.state(pe), (1, "Đã ghi sổ"))

	def test_api_edit_and_approve_in_one_call_rechecks_limit(self):  # R-16
		self.require_workflow("Purchase Order")
		pu = make_user("Purchase User")
		po = self.purchase_order(1, pu)
		doc = po.as_dict()
		doc["items"][0]["rate"] = 1_000_000_000
		doc["workflow_state"] = "Đã duyệt"
		with self.assertRaises(frappe.PermissionError):
			frappe.client.submit(doc)
		self.assertEqual(self.state(po), (0, "Nháp"))

	def test_submit_with_pending_state_blocked(self):  # R-23
		self.require_workflow("Purchase Order")
		pu = make_user("Purchase User")
		po = self.purchase_order(H1 + 1, pu)
		doc = po.as_dict()
		doc["workflow_state"] = "Chờ TP"
		with self.assertRaises(frappe.PermissionError):
			frappe.client.submit(doc)
		self.assertEqual(self.state(po), (0, "Nháp"))

	def test_draft_save_into_submitted_state_blocked(self):  # R-23
		self.require_workflow("Purchase Order")
		pu = make_user("Purchase User")
		po = self.purchase_order(1000, pu)
		doc = po.as_dict()
		doc["workflow_state"] = "Đã duyệt"
		with self.assertRaises(frappe.PermissionError):
			frappe.client.save(doc)

	def test_edit_while_pending_blocked_even_for_owner(self):  # T26
		self.require_workflow("Purchase Order")
		pu = make_user("Purchase User")
		po = self.purchase_order(H1 + 1, pu)
		apply_workflow(po.as_dict(), "Gửi duyệt")
		doc = frappe.get_doc("Purchase Order", po.name).as_dict()
		doc["items"][0]["qty"] = 2
		with self.assertRaises(frappe.ValidationError):
			frappe.client.save(doc)

	def test_same_user_cannot_approve_two_steps(self):  # T30
		self.require_workflow("Purchase Order")
		pu = make_user("Purchase User")
		pm_ap = make_user("Purchase Manager", "MVL Approver")
		po = self.purchase_order(H2 + 1, pu)
		apply_workflow(po.as_dict(), "Gửi duyệt")
		frappe.set_user(pm_ap)
		apply_workflow(frappe.get_doc("Purchase Order", po.name).as_dict(), "Duyệt")
		self.assertEqual(self.state(po), (0, "Chờ BGĐ"))
		with self.assertRaises(frappe.PermissionError):
			apply_workflow(frappe.get_doc("Purchase Order", po.name).as_dict(), "Duyệt")

	def test_api_approval_leaves_marker_for_h10(self):  # R-18
		self.require_workflow("Purchase Order")
		pu = make_user("Purchase User")
		pm_ap = make_user("Purchase Manager", "MVL Approver")
		po = self.purchase_order(H2 + 1, pu)
		apply_workflow(po.as_dict(), "Gửi duyệt")
		frappe.set_user(pm_ap)
		doc = frappe.get_doc("Purchase Order", po.name).as_dict()
		doc["workflow_state"] = "Chờ BGĐ"
		frappe.client.save(doc)  # step 1 by API: frappe writes no Workflow comment
		self.assertTrue(
			frappe.db.exists(
				"Comment",
				{"reference_name": po.name, "comment_type": "Info", "content": "MVL-DUYET: Chờ TP → Chờ BGĐ"},
			)
		)
		with self.assertRaises(frappe.PermissionError):
			apply_workflow(frappe.get_doc("Purchase Order", po.name).as_dict(), "Duyệt")

	def test_system_generated_je_passes(self):  # T24
		self.require_workflow("Journal Entry")
		au = make_user("Accounts User")
		je = self.journal_entry(au, ignore_permissions=True)
		je.submit()
		self.assertEqual(self.state(je), (1, "Đã ghi sổ"))

	def test_administrator_job_passes(self):  # Review Focus 5
		self.require_workflow("Journal Entry")
		je = self.journal_entry("Administrator")
		je.submit()
		self.assertEqual(self.state(je), (1, "Đã ghi sổ"))

	def test_amend_starts_from_draft(self):  # T34
		self.require_workflow("Journal Entry")
		au = make_user("Accounts User")
		am = make_user("Accounts Manager")
		je = self.journal_entry(au)
		apply_workflow(je.as_dict(), "Gửi duyệt")
		frappe.set_user(am)
		apply_workflow(frappe.get_doc("Journal Entry", je.name).as_dict(), "Duyệt")
		frappe.client.cancel("Journal Entry", je.name)
		self.assertEqual(self.state(je), (2, "Đã hủy"))
		frappe.set_user(au)
		amended = frappe.copy_doc(frappe.get_doc("Journal Entry", je.name))
		amended.amended_from = je.name
		amended.docstatus = 0
		amended.insert()
		self.assertEqual(self.state(amended), (0, "Nháp"))

	def test_cancel_of_pre_workflow_doc_allowed(self):  # Review Focus 3
		self.require_workflow("Journal Entry")
		am = make_user("Accounts Manager")
		je = self.journal_entry("Administrator")
		je.submit()
		je.db_set("workflow_state", None)  # as if submitted before the workflow existed
		frappe.set_user(am)
		frappe.client.cancel("Journal Entry", je.name)
		self.assertEqual(self.state(je), (2, "Đã hủy"))  # set by before_cancel: frappe skips it on cancel

	def test_standard_cancel_sets_cancelled_state(self):
		self.require_workflow("Purchase Order")
		pu = make_user("Purchase User")
		pm = make_user("Purchase Manager")
		po = self.purchase_order(1000, pu)
		frappe.client.submit(po.as_dict())
		self.assertEqual(self.state(po), (1, "Đã duyệt"))
		frappe.set_user(pm)
		frappe.client.cancel("Purchase Order", po.name)
		self.assertEqual(self.state(po), (2, "Đã hủy"))
