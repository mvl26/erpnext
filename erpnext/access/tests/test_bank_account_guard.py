"""H3 — Payment Entry may only use Bank Accounts approved through WF-BA (spec 11.3 H3, T22).

The Bank and Bank Accounts are throwaway rows inside the class transaction; their ``workflow_state`` is written
with ``db.set_value`` (no Workflow is activated). The Payment Entry is built in memory and handed to the guard.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.access import bank_account_guard
from erpnext.access.tests.helpers import make_user

ENABLED = "erpnext.access.bank_account_guard.is_enabled"


def bank_account(bank, state=None):
	account = frappe.get_doc(
		{
			"doctype": "Bank Account",
			"account_name": f"BAG {frappe.generate_hash(length=8)}",
			"bank": bank,
			"is_company_account": 0,
		}
	).insert(ignore_permissions=True)
	if state:
		frappe.db.set_value("Bank Account", account.name, "workflow_state", state)
	return account.name


def payment_entry(**fields):
	return frappe.get_doc({"doctype": "Payment Entry", "payment_type": "Pay", "company": "Miyano", **fields})


class TestBankAccountGuard(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		bank = frappe.get_doc({"doctype": "Bank", "bank_name": f"BAG Bank {frappe.generate_hash(length=8)}"})
		bank.insert(ignore_permissions=True)
		cls.approved = bank_account(bank.name, bank_account_guard.APPROVED)
		cls.pending = bank_account(bank.name, "Chờ KT-KTT")
		cls.fresh = bank_account(bank.name)
		cls.au = make_user("Accounts User")

	def setUp(self):
		patcher = patch(ENABLED, return_value=True)
		patcher.start()
		self.addCleanup(patcher.stop)
		self.addCleanup(frappe.set_user, "Administrator")

	def run_as(self, user, doc):
		frappe.set_user(user)
		try:
			bank_account_guard.validate(doc)
		finally:
			frappe.set_user("Administrator")

	def test_t22_unapproved_bank_account_is_blocked(self):
		for account in (self.pending, self.fresh):
			with self.subTest(account), self.assertRaises(frappe.ValidationError) as ctx:
				self.run_as(self.au, payment_entry(bank_account=account))
			self.assertIn(account, str(ctx.exception))

	def test_unapproved_party_bank_account_is_blocked(self):
		with self.assertRaises(frappe.ValidationError) as ctx:
			self.run_as(self.au, payment_entry(bank_account=self.approved, party_bank_account=self.pending))
		self.assertIn(self.pending, str(ctx.exception))
		self.assertNotIn(self.approved, str(ctx.exception))

	def test_approved_accounts_pass(self):
		self.run_as(self.au, payment_entry(bank_account=self.approved, party_bank_account=self.approved))
		self.run_as(self.au, payment_entry())  # no bank account at all

	def test_gate_off_is_a_no_op(self):
		with patch(ENABLED, return_value=False):
			self.run_as(self.au, payment_entry(bank_account=self.pending))

	def test_administrator_and_ignore_permissions_skip(self):
		bank_account_guard.validate(payment_entry(bank_account=self.pending))  # Administrator
		doc = payment_entry(bank_account=self.pending)
		doc.flags.ignore_permissions = True
		self.run_as(self.au, doc)

	def test_site_without_the_state_column_is_skipped(self):
		with patch.object(bank_account_guard, "_has_state_column", return_value=False):
			self.run_as(self.au, payment_entry(bank_account=self.pending))

	def test_validate_is_registered_for_payment_entry(self):
		from erpnext import hooks

		handlers = hooks.doc_events.get("Payment Entry", {}).get("validate", [])
		handlers = [handlers] if isinstance(handlers, str) else handlers
		self.assertIn("erpnext.access.bank_account_guard.validate", handlers)
