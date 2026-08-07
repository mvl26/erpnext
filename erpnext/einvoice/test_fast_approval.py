# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nút 4/5/6 — vòng duyệt bản nháp với khách hàng (mục E3, E4)."""

import base64

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.einvoice.actions import (
	mark_customer_approved,
	preview_draft,
	record_customer_feedback,
	send_draft_to_customer,
)
from erpnext.einvoice.builder import create_from_delivery_note
from erpnext.einvoice.constants import (
	STATUS_AWAITING_CUSTOMER,
	STATUS_CUSTOMER_APPROVED,
	STATUS_DRAFT,
	STATUS_DRAFT_VIEWED,
	STATUS_ISSUED,
)
from erpnext.einvoice.fast_client import FastClient
from erpnext.einvoice.setup import DRAFT_TEMPLATE, ISSUED_TEMPLATE
from erpnext.einvoice.test_fast_client import FakeTransport, configure, envelope
from erpnext.einvoice.test_fixtures import make_delivery_note, minimal_pdf_bytes

FEI = "Fast EInvoice Document"
LOG = "Fast EInvoice Log"


class Mailbox:
	"""Hộp thư giả — giữ nguyên nội dung để kiểm tra."""

	def __init__(self):
		self.sent = []

	def __call__(self, **kwargs):
		self.sent.append(kwargs)


class TestEmailTemplates(FrappeTestCase):
	def test_both_templates_are_installed(self):
		self.assertTrue(frappe.db.exists("Email Template", DRAFT_TEMPLATE))
		self.assertTrue(frappe.db.exists("Email Template", ISSUED_TEMPLATE))

	def test_draft_template_states_it_has_no_legal_force(self):
		"""Mục E3 bắt buộc: bản nháp phải nói rõ CHƯA CÓ GIÁ TRỊ PHÁP LÝ."""
		body = frappe.db.get_value("Email Template", DRAFT_TEMPLATE, "response")
		self.assertIn("CHƯA CÓ GIÁ TRỊ PHÁP LÝ", body)
		self.assertIn("BẢN NHÁP", body)

	def test_issued_template_carries_the_lookup_code(self):
		body = frappe.db.get_value("Email Template", ISSUED_TEMPLATE, "response")
		self.assertIn("fast_key_search", body)


class TestDraftApprovalCycle(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure(token="TOKEN-ABC", token_time=frappe.utils.now_datetime())
		self.dn = make_delivery_note()
		self.fei = frappe.get_doc(FEI, create_from_delivery_note(self.dn.name))
		self.mailbox = Mailbox()
		self._make_draft_pdf()

	def tearDown(self):
		frappe.db.rollback()

	def _make_draft_pdf(self):
		transport = FakeTransport(
			envelope(1, "still valid"), envelope(1, base64.b64encode(minimal_pdf_bytes()).decode())
		)
		preview_draft(self.fei.name, client=FastClient(transport=transport))
		self.fei.reload()

	# --- Nút 4: gửi nháp cho khách ---------------------------------------

	def test_sending_the_draft_moves_to_awaiting_customer(self):
		send_draft_to_customer(self.fei.name, mailer=self.mailbox)

		self.fei.reload()
		self.assertEqual(self.fei.status, STATUS_AWAITING_CUSTOMER)
		self.assertEqual(self.fei.draft_send_count, 1)
		self.assertIsNotNone(self.fei.draft_sent_time)

	def test_default_recipient_is_the_invoice_email(self):
		send_draft_to_customer(self.fei.name, mailer=self.mailbox)
		self.assertEqual(self.mailbox.sent[0]["recipients"], [self.fei.email_deliver])

	def test_recipient_can_be_overridden(self):
		send_draft_to_customer(self.fei.name, recipients="ai.do@bvx.vn", mailer=self.mailbox)

		self.fei.reload()
		self.assertEqual(self.mailbox.sent[0]["recipients"], ["ai.do@bvx.vn"])
		self.assertEqual(self.fei.draft_sent_to, "ai.do@bvx.vn")

	def test_email_body_warns_that_the_draft_has_no_legal_force(self):
		send_draft_to_customer(self.fei.name, mailer=self.mailbox)
		self.assertIn("CHƯA CÓ GIÁ TRỊ PHÁP LÝ", self.mailbox.sent[0]["message"])

	def test_draft_pdf_is_attached(self):
		send_draft_to_customer(self.fei.name, mailer=self.mailbox)
		attachments = self.mailbox.sent[0]["attachments"]
		self.assertTrue(attachments)
		self.assertIn("Nhap_", str(attachments))

	def test_resending_counts_the_rounds(self):
		"""draft_send_count theo dõi số vòng qua lại với khách."""
		send_draft_to_customer(self.fei.name, mailer=self.mailbox)
		send_draft_to_customer(self.fei.name, mailer=self.mailbox)

		self.fei.reload()
		self.assertEqual(self.fei.draft_send_count, 2)

	def test_sending_is_logged(self):
		send_draft_to_customer(self.fei.name, mailer=self.mailbox)
		log = frappe.get_doc(LOG, {"fei_document": self.fei.name, "operation": "Email"})
		self.assertEqual(log.status, "Thành công")

	def test_cannot_send_a_draft_that_was_never_generated(self):
		frappe.db.set_value(FEI, self.fei.name, {"draft_pdf": "", "status": STATUS_DRAFT})
		with self.assertRaises(frappe.ValidationError):
			send_draft_to_customer(self.fei.name, mailer=self.mailbox)

	def test_cannot_send_a_draft_of_an_issued_invoice(self):
		frappe.db.set_value(FEI, self.fei.name, "status", STATUS_ISSUED)
		with self.assertRaises(frappe.ValidationError):
			send_draft_to_customer(self.fei.name, mailer=self.mailbox)

	# --- Nút 5: ghi nhận ý kiến khách ------------------------------------

	def test_feedback_sends_the_invoice_back_to_draft(self):
		send_draft_to_customer(self.fei.name, mailer=self.mailbox)
		record_customer_feedback(self.fei.name, "Khách yêu cầu sửa lại tên đơn vị mua")

		self.fei.reload()
		self.assertEqual(self.fei.status, STATUS_DRAFT)
		self.assertEqual(self.fei.revision_count, 1)

	def test_feedback_history_is_appended_never_overwritten(self):
		"""Lịch sử phản hồi là bằng chứng khi tranh chấp nội dung hóa đơn."""
		send_draft_to_customer(self.fei.name, mailer=self.mailbox)
		record_customer_feedback(self.fei.name, "Sai tên đơn vị mua")

		self._make_draft_pdf()
		send_draft_to_customer(self.fei.name, mailer=self.mailbox)
		record_customer_feedback(self.fei.name, "Sai thêm địa chỉ nữa")

		self.fei.reload()
		self.assertIn("Sai tên đơn vị mua", self.fei.customer_feedback)
		self.assertIn("Sai thêm địa chỉ nữa", self.fei.customer_feedback)

	def test_feedback_records_who_and_when(self):
		send_draft_to_customer(self.fei.name, mailer=self.mailbox)
		record_customer_feedback(self.fei.name, "Sai tên đơn vị mua")

		self.fei.reload()
		self.assertIn(frappe.session.user, self.fei.customer_feedback)

	def test_trivial_feedback_is_refused(self):
		"""Đặc tả E4: tối thiểu 10 ký tự — "sai" không đủ để sửa lại hóa đơn."""
		send_draft_to_customer(self.fei.name, mailer=self.mailbox)
		with self.assertRaises(frappe.ValidationError):
			record_customer_feedback(self.fei.name, "sai")

	# --- Nút 6: khách đã duyệt -------------------------------------------

	def test_approval_moves_to_ready_to_issue(self):
		send_draft_to_customer(self.fei.name, mailer=self.mailbox)
		mark_customer_approved(self.fei.name, approved_by="Chị Lan (BV X)", channel="Email")

		self.fei.reload()
		self.assertEqual(self.fei.status, STATUS_CUSTOMER_APPROVED)
		self.assertEqual(self.fei.customer_approved_by, "Chị Lan (BV X)")
		self.assertIsNotNone(self.fei.customer_approved_time)

	def test_approval_needs_a_named_person(self):
		"""Bằng chứng nội bộ khi tranh chấp — không chấp nhận duyệt vô danh."""
		send_draft_to_customer(self.fei.name, mailer=self.mailbox)
		with self.assertRaises(frappe.ValidationError):
			mark_customer_approved(self.fei.name, approved_by="", channel="Email")

	def test_approval_is_written_into_the_timeline(self):
		send_draft_to_customer(self.fei.name, mailer=self.mailbox)
		mark_customer_approved(self.fei.name, approved_by="Chị Lan", channel="Điện thoại")

		comments = frappe.get_all(
			"Comment",
			filters={"reference_doctype": FEI, "reference_name": self.fei.name},
			pluck="content",
		)
		self.assertTrue(any("Chị Lan" in (c or "") and "Điện thoại" in (c or "") for c in comments))

	def test_cannot_approve_a_draft_never_sent_to_the_customer(self):
		self.fei.reload()
		self.assertEqual(self.fei.status, STATUS_DRAFT_VIEWED)
		with self.assertRaises(frappe.ValidationError):
			mark_customer_approved(self.fei.name, approved_by="Chị Lan", channel="Email")
