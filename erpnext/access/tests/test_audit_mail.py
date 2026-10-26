"""H4 — audit mail (spec 11.3 H4; plan R-7, T42). sendmail is replaced by a Mailbox: nothing is really sent."""

from collections import Counter
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.access import audit_mail

ENABLED = "erpnext.access.audit_mail.is_enabled"
DIRECTOR = "director@example.com"
REAL_RECIPIENTS = audit_mail.recipients


class Mailbox:
	def __init__(self):
		self.sent = []

	def __call__(self, **kwargs):
		self.sent.append(kwargs)


def make_user(**extra):
	email = f"audit-{frappe.generate_hash(length=8)}@example.com"
	doc = frappe.get_doc(
		{"doctype": "User", "email": email, "first_name": "Audit", "send_welcome_email": 0, **extra}
	)
	doc.insert(ignore_permissions=True)
	return doc


class TestAuditMail(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def setUp(self):
		self.box = Mailbox()
		self.patches = [
			patch.object(frappe, "sendmail", self.box),
			patch(ENABLED, return_value=True),
			patch.object(audit_mail, "recipients", return_value=[DIRECTOR]),
		]
		for p in self.patches:
			p.start()
			self.addCleanup(p.stop)

	def test_user_mail_only_on_roles_profile_or_enabled(self):
		user = make_user()
		self.box.sent.clear()
		user.reload()
		user.first_name = "Renamed"
		user.save(ignore_permissions=True)
		self.assertEqual(self.box.sent, [])
		user.reload()
		user.append("roles", {"role": "Blogger"})
		user.save(ignore_permissions=True)
		self.assertEqual(len(self.box.sent), 1)
		mail = self.box.sent[0]
		self.assertEqual(mail["recipients"], [DIRECTOR])
		self.assertEqual(mail["subject"], f"[Miyano ERP] Thay đổi phân quyền: User {user.name}")
		self.assertIn("Blogger", mail["message"])
		self.assertIn(frappe.session.user, mail["message"])
		self.assertFalse(mail["now"])
		user.reload()
		user.enabled = 0
		user.save(ignore_permissions=True)
		self.assertEqual(len(self.box.sent), 2)

	def test_insert_and_delete_send_one_mail_each(self):
		target = make_user().name
		self.box.sent.clear()
		perm = frappe.get_doc(
			{"doctype": "User Permission", "user": target, "allow": "User", "for_value": "Administrator"}
		)
		perm.insert(ignore_permissions=True)
		self.assertEqual(len(self.box.sent), 1)
		self.assertIn("User Permission", self.box.sent[0]["subject"])
		self.assertIn("tạo", self.box.sent[0]["message"])
		perm.delete(ignore_permissions=True)
		self.assertEqual(len(self.box.sent), 2)
		self.assertIn("xóa", self.box.sent[1]["message"])

	def test_hooks_are_registered_for_every_audited_doctype(self):
		hooks = frappe.get_hooks("doc_events")
		for doctype in (
			"User",
			"Has Role",
			"Role Profile",
			"Custom DocPerm",
			"Custom Role",
			"User Permission",
			"Workflow",
			"MVL Approval Limits",
		):
			handlers = hooks.get(doctype, {})
			flat = [h for v in handlers.values() for h in (v if isinstance(v, list) else [v])]
			self.assertIn("erpnext.access.audit_mail.on_change", flat, doctype)

	def test_silent_during_sync(self):
		doc = frappe.get_doc({"doctype": "Custom Role", "report": "General Ledger"})
		with patch.dict(frappe.flags, {"in_rbac_sync": True}):
			audit_mail.on_change(doc, "on_update")
		self.assertEqual(self.box.sent, [])

	def test_gate_off_sends_nothing(self):
		doc = frappe.get_doc({"doctype": "Custom Role", "report": "General Ledger"})
		with patch(ENABLED, return_value=False):
			audit_mail.on_change(doc, "on_update")
			audit_mail.send_sync_summary(Counter(inserted=3))
		self.assertEqual(self.box.sent, [])

	def test_no_recipient_no_mail_no_error(self):
		doc = frappe.get_doc({"doctype": "Custom Role", "report": "General Ledger"})
		with patch.object(audit_mail, "recipients", return_value=[]):
			audit_mail.on_change(doc, "on_update")
		self.assertEqual(self.box.sent, [])

	def test_sync_summary(self):
		audit_mail.send_sync_summary(Counter(inserted=0, deleted=0, roles=5))
		self.assertEqual(self.box.sent, [])
		audit_mail.send_sync_summary(Counter(inserted=2, deleted=1, roles=5))
		self.assertEqual(len(self.box.sent), 1)
		self.assertIn("roles: 5", self.box.sent[0]["message"])

	def test_recipients_are_enabled_directors(self):
		with patch.object(frappe, "get_all", return_value=["a@x.com"]) as get_all:
			self.assertEqual(REAL_RECIPIENTS(), ["a@x.com"])
		self.assertEqual(
			get_all.call_args.kwargs["filters"], {"enabled": 1, "role_profile_name": "RP-BGD-GDVH"}
		)
