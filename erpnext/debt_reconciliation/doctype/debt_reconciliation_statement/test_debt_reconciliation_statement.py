# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Controller: lãi quá hạn, chuyển trạng thái, quyền, Hủy/Sửa đổi (T7, T9, T14, T17, T18)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.debt_reconciliation import constants as C
from erpnext.debt_reconciliation.generation import build_statement
from erpnext.debt_reconciliation.tests.utils import get_company, make_party, minimal_pdf_bytes, post

FROM, TO = "2026-03-01", "2026-03-31"


class TestDebtReconciliationStatement(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = get_company("_Test DR Gen", "TDRG")

	def make(self, party_type="Supplier", dr=0, cr=0, email="doi.chieu@example.com"):
		party = make_party(party_type, reconciliation_email=email)
		if dr or cr:
			post(self.company, party_type, party, dr, cr, "2026-03-10")
		name, _ = build_statement(self.company, party_type, party, FROM, TO, C.SOURCE_MANUAL)
		return frappe.get_doc(C.DOCTYPE, name)

	def signed_copy(self, doc):
		return (
			frappe.get_doc(
				{
					"doctype": "File",
					"file_name": f"ban-ky-{frappe.generate_hash(length=6)}.pdf",
					"content": minimal_pdf_bytes(frappe.generate_hash()),
					"is_private": 1,
				}
			)
			.insert(ignore_permissions=True)
			.file_url
		)

	def test_interest_on_owed_side_increases_closing(self):
		doc = self.make("Customer", dr=1_000_000)
		doc.interest_in_period = 20_000
		doc.save()
		self.assertEqual((doc.closing_balance, doc.balance_direction), (1_020_000, C.DIR_DEBIT))
		self.assertIn("Một triệu không trăm hai mươi nghìn", doc.amount_in_words)

	def test_interest_on_prepaid_side_is_blocked(self):
		doc = self.make("Supplier", dr=300_000)  # Miyano trả trước cho NCC → Dư Nợ
		self.assertEqual(doc.balance_direction, C.DIR_DEBIT)
		doc.interest_in_period = 1
		self.assertRaises(frappe.ValidationError, doc.save)
		doc.reload()
		doc.opening_interest = 1
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_submit_requires_figures(self):
		doc = self.make("Supplier", cr=100_000)
		doc.db_set("figures_fetched_on", None)
		doc.reload()
		self.assertRaises(frappe.ValidationError, doc.submit)

	def test_happy_path_match_then_confirm(self):
		doc = self.make("Supplier", cr=500_000)
		doc.submit()
		doc.reload()
		self.assertEqual(doc.status, C.STATUS_SENT)

		doc.apply_action("respond_match")
		self.assertEqual((doc.status, doc.partner_response), (C.STATUS_MATCHED, C.RESPONSE_MATCH))
		self.assertTrue(doc.responded_on)

		self.assertRaises(
			frappe.ValidationError, doc.apply_action, "confirm", confirmation_method=C.CONFIRM_E_SIGN
		)
		file_url = self.signed_copy(doc)
		doc.apply_action("confirm", confirmation_method=C.CONFIRM_E_SIGN, signed_copy=file_url)
		doc.reload()
		self.assertEqual(doc.status, C.STATUS_CONFIRMED)
		self.assertEqual(doc.confirmation_method, C.CONFIRM_E_SIGN)
		self.assertTrue(doc.confirmed_on)
		self.assertEqual(frappe.db.get_value("File", {"file_url": file_url}, "attached_to_name"), doc.name)

	def test_dispute_requires_amount_and_note_then_confirm(self):
		doc = self.make("Customer", dr=800_000)
		doc.submit()
		doc.reload()
		self.assertRaises(
			frappe.ValidationError, doc.apply_action, "respond_mismatch", dispute_amount=750_000
		)
		doc.apply_action("respond_mismatch", dispute_amount=750_000, dispute_note="Thiếu HĐ 0012")
		self.assertEqual((doc.status, doc.partner_response), (C.STATUS_DISPUTED, C.RESPONSE_MISMATCH))
		doc.apply_action(
			"confirm",
			confirmation_method=C.CONFIRM_HARD_COPY,
			signed_copy=self.signed_copy(doc),
			dispute_resolution="Đã bổ sung HĐ",
		)
		self.assertEqual(doc.status, C.STATUS_CONFIRMED)

	def test_confirm_straight_from_sent_marks_match(self):
		doc = self.make("Supplier", cr=90_000)
		doc.submit()
		doc.reload()
		doc.apply_action(
			"confirm", confirmation_method=C.CONFIRM_HARD_COPY, signed_copy=self.signed_copy(doc)
		)
		self.assertEqual((doc.status, doc.partner_response), (C.STATUS_CONFIRMED, C.RESPONSE_MATCH))

	def test_wrong_state_and_unknown_action_rejected(self):
		doc = self.make("Supplier", cr=10_000)
		self.assertRaises(frappe.ValidationError, doc.apply_action, "respond_match")  # còn Nháp
		doc.submit()
		doc.reload()
		self.assertRaises(frappe.ValidationError, doc.apply_action, "resend")  # không ở Lỗi gửi
		self.assertRaises(frappe.ValidationError, doc.apply_action, "bogus")

	def test_accounts_user_cannot_approve_or_change_status(self):
		user = f"dr-user-{frappe.generate_hash(length=6)}@example.com"
		frappe.get_doc(
			{"doctype": "User", "email": user, "first_name": "DR", "roles": [{"role": "Accounts User"}]}
		).insert(ignore_permissions=True)
		doc = self.make("Supplier", cr=10_000)
		frappe.set_user(user)
		try:
			self.assertFalse(frappe.has_permission(C.DOCTYPE, "submit", doc))
			self.assertTrue(frappe.has_permission(C.DOCTYPE, "create"))
			self.assertRaises(frappe.PermissionError, doc.apply_action, "respond_match")
		finally:
			frappe.set_user("Administrator")

	def test_cancel_then_amend_keeps_statement_no(self):
		doc = self.make("Customer", dr=60_000)
		doc.submit()
		doc.reload()
		doc.cancel()
		self.assertEqual(frappe.db.get_value(C.DOCTYPE, doc.name, "status"), C.STATUS_CANCELLED)

		amended = frappe.copy_doc(doc, ignore_no_copy=False)  # như nút Sửa đổi trên giao diện
		amended.docstatus = 0
		amended.amended_from = doc.name
		amended.insert()
		self.assertEqual(amended.statement_no, doc.statement_no)
		self.assertEqual(amended.status, C.STATUS_DRAFT)
		self.assertEqual(amended.partner_response, C.RESPONSE_NONE)
		self.assertFalse(amended.sent_pdf)
