# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Luật chặn email ở ``erpnext.utilities.email_guard``."""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.utilities.email_guard import (
	block_unsubscribed_recipients,
	extract_bounced_addresses,
	handle_bounce,
	is_globally_unsubscribed,
)

BLOCKED = "khach.da.nghi@example.vn"
ACTIVE = "khach.dang.mua@example.vn"


def unsubscribe_globally(email):
	if is_globally_unsubscribed(email):
		return
	frappe.get_doc({"doctype": "Email Unsubscribe", "email": email, "global_unsubscribe": 1}).insert(
		ignore_permissions=True
	)


def email_queue(*recipients):
	doc = frappe.new_doc("Email Queue")
	doc.status = "Not Sent"
	for email in recipients:
		doc.append("recipients", {"recipient": email})
	return doc


def communication(**values):
	return frappe._dict(
		{
			"sent_or_received": "Received",
			"sender": "",
			"subject": "",
			"content": "",
			"reference_doctype": "Sales Invoice",
			"reference_name": "ACC-SINV-0001",
			"in_reply_to": "COMM-0001",
			"unread_notification_sent": 0,
			**values,
		}
	)


class TestBlockUnsubscribedRecipients(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		unsubscribe_globally(BLOCKED)

	def test_removes_only_unsubscribed_recipients(self):
		doc = email_queue(BLOCKED, ACTIVE)
		block_unsubscribed_recipients(doc)
		self.assertEqual([r.recipient for r in doc.recipients], [ACTIVE])
		self.assertEqual(doc.status, "Not Sent")

	def test_matches_regardless_of_case_and_spaces(self):
		doc = email_queue(f"  {BLOCKED.upper()} ", ACTIVE)
		block_unsubscribed_recipients(doc)
		self.assertEqual([r.recipient for r in doc.recipients], [ACTIVE])

	def test_marks_error_when_no_recipient_left(self):
		doc = email_queue(BLOCKED)
		block_unsubscribed_recipients(doc)
		self.assertEqual(doc.status, "Error")
		self.assertIn(BLOCKED, doc.error)

	def test_leaves_queue_untouched_when_nobody_blocked(self):
		doc = email_queue(ACTIVE)
		block_unsubscribed_recipients(doc)
		self.assertEqual([r.recipient for r in doc.recipients], [ACTIVE])
		self.assertEqual(doc.status, "Not Sent")


HARD_BOUNCE_BODY = (
	"Address not found. Your message wasn't delivered to <khach.sai@benhvien.vn> "
	"because the address couldn't be found. 550 5.1.1 The email account that you tried to reach "
	"does not exist. Final-Recipient: rfc822; khach.sai@benhvien.vn"
)


class TestHandleBounce(FrappeTestCase):
	def test_detaches_bounce_from_document(self):
		doc = communication(sender="Mail Delivery Subsystem <mailer-daemon@googlemail.com>")
		handle_bounce(doc)
		self.assertIsNone(doc.reference_doctype)
		self.assertIsNone(doc.reference_name)
		self.assertIsNone(doc.in_reply_to)
		self.assertEqual(doc.unread_notification_sent, 1)

	def test_detects_bounce_by_subject(self):
		doc = communication(subject="Delivery Status Notification (Failure)")
		handle_bounce(doc)
		self.assertIsNone(doc.reference_doctype)

	def test_ignores_normal_customer_reply(self):
		doc = communication(sender="khach@benhvien.vn", subject="Re: Hóa đơn tháng 9")
		handle_bounce(doc)
		self.assertEqual(doc.reference_doctype, "Sales Invoice")

	def test_ignores_sent_mail(self):
		doc = communication(sent_or_received="Sent", sender="mailer-daemon@googlemail.com")
		handle_bounce(doc)
		self.assertEqual(doc.reference_doctype, "Sales Invoice")

	def test_hard_bounce_unsubscribes_address(self):
		doc = communication(sender="mailer-daemon@googlemail.com", content=HARD_BOUNCE_BODY)
		handle_bounce(doc)
		self.assertTrue(is_globally_unsubscribed("khach.sai@benhvien.vn"))

	def test_soft_bounce_does_not_unsubscribe(self):
		doc = communication(
			sender="mailer-daemon@googlemail.com",
			content="Mailbox full, will retry later: <khach.day@benhvien.vn>",
		)
		handle_bounce(doc)
		self.assertFalse(is_globally_unsubscribed("khach.day@benhvien.vn"))


class TestExtractBouncedAddresses(FrappeTestCase):
	def test_skips_internal_and_system_addresses(self):
		body = (
			"address not found: <khach.sai@benhvien.vn> from ketoan@miyano.com.vn "
			"via mailer-daemon@googlemail.com noreply@fast.com.vn"
		)
		self.assertEqual(extract_bounced_addresses(body), ["khach.sai@benhvien.vn"])

	def test_ignores_quoted_original_beyond_head(self):
		body = "address not found." + " " * 2000 + "cc: dong.nghiep@benhvien.vn"
		self.assertEqual(extract_bounced_addresses(body), [])

	def test_reads_final_recipient_even_past_head(self):
		body = "address not found." + " " * 2000 + "final-recipient: rfc822; khach.sai@benhvien.vn"
		self.assertEqual(extract_bounced_addresses(body), ["khach.sai@benhvien.vn"])
