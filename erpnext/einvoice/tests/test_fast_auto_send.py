# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tự gửi hóa đơn cho khách sau phát hành (phân tích "Tự gửi HĐĐT", mục 6 và Q1, Q3, Q4)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from erpnext.einvoice.actions import download_official_pdf, download_pending_official_pdfs
from erpnext.einvoice.auto_send import AUTO_SEND_PURPOSE, send_pending_invoices
from erpnext.einvoice.builder import create_from_sales_invoice
from erpnext.einvoice.constants import (
	STATUS_ISSUED,
	STATUS_SENT,
	STATUS_TAX_ACCEPTED,
	STATUS_TAX_REJECTED,
	TAX_STATUS_PENDING,
)
from erpnext.einvoice.fast_client import FastClient
from erpnext.einvoice.tests.test_fast_approval import Mailbox
from erpnext.einvoice.tests.test_fast_client import FakeTransport, checkkey_ok, configure
from erpnext.einvoice.tests.test_fast_invoice_email import use_miyano_template
from erpnext.einvoice.tests.test_fast_pdf import lookup_envelope
from erpnext.einvoice.tests.test_fast_tax_status import tax_result
from erpnext.einvoice.tests.test_fixtures import LOOKUP_CODE, make_sales_invoice

FEI = "Fast EInvoice Document"
LOG = "Fast EInvoice Log"
NOTICE = "[HĐĐT] Cần gửi tay"


class BrokenMailer:
	def __init__(self):
		self.calls = 0

	def __call__(self, **kwargs):
		if kwargs.get("subject", "").startswith(NOTICE):
			return
		self.calls += 1
		raise Exception("SMTP từ chối")


class AutoSendBase(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure(token="TOKEN-ABC", token_time=now_datetime(), auto_send_invoice=1, auto_download_pdf=1)
		use_miyano_template()
		self.si = make_sales_invoice()
		self.fei = frappe.get_doc(FEI, create_from_sales_invoice(self.si.name))
		frappe.db.set_value(
			FEI,
			self.fei.name,
			{
				"status": STATUS_ISSUED,
				"fast_key": "KEY-AUTO-1",
				"fast_key_search": "KS-ABC-123",
				"fast_invoice_no": "7",
				"fast_pattern": "1",
				"fast_serial": "C26TAA",
				"fast_signed_date": now_datetime().date(),
				"issued_time": add_to_date(now_datetime(), minutes=-3),
				"tax_status": TAX_STATUS_PENDING,
				"tax_verification_code": "TEST-MA-CQT",
				"email_deliver": "kh@bvx.vn",
			},
		)
		self.mailbox = Mailbox()

	def tearDown(self):
		frappe.db.rollback()

	def _client(self, *responses):
		self.transport = FakeTransport(checkkey_ok(), *responses)
		return FastClient(transport=self.transport)

	def _with_pdf(self):
		download_official_pdf(self.fei.name, client=self._client(lookup_envelope()))
		self.fei.reload()

	def _set(self, **values):
		frappe.db.set_value(FEI, self.fei.name, values)

	def _invoice_emails(self, mailbox=None):
		return [m for m in (mailbox or self.mailbox).sent if not m["subject"].startswith(NOTICE)]

	def _notices(self, mailbox=None):
		return [m for m in (mailbox or self.mailbox).sent if m["subject"].startswith(NOTICE)]

	def _run(self, client=None, mailer=None):
		from unittest.mock import patch

		with patch("erpnext.einvoice.auto_send.get_notify_recipients", return_value=["kt@miyano.vn"]):
			return send_pending_invoices(client=client, mailer=mailer or self.mailbox)

	def _value(self, fieldname):
		return frappe.db.get_value(FEI, self.fei.name, fieldname)


class TestAutoSendHappyPath(AutoSendBase):
	def setUp(self):
		super().setUp()
		self._with_pdf()

	def test_disabled_sends_nothing(self):
		configure(auto_send_invoice=0)
		self.assertEqual(self._run(), [])
		self.assertEqual(self.mailbox.sent, [])

	def test_sends_exactly_once(self):
		self.assertEqual(self._run(), [self.fei.name])
		self.assertEqual(self._run(), [])
		self.assertEqual(len(self._invoice_emails()), 1)
		self.assertEqual(self._invoice_emails()[0]["recipients"], ["kh@bvx.vn"])
		self.assertIn(LOOKUP_CODE, self._invoice_emails()[0]["message"])

	def test_issued_moves_to_sent(self):
		self._run()
		self.assertEqual(self._value("status"), STATUS_SENT)
		self.assertEqual(self._value("invoice_send_count"), 1)

	def test_tax_accepted_stays_tax_accepted(self):
		self._set(status=STATUS_TAX_ACCEPTED)
		self._run()
		self.assertEqual(self._value("status"), STATUS_TAX_ACCEPTED)
		self.assertEqual(self._value("invoice_send_count"), 1)

	def test_the_sender_is_the_settings_contact(self):
		configure(
			auto_send_invoice=1, invoice_sender_name="Nguyễn Văn A", invoice_sender_email="hd@miyano.vn"
		)
		self._run()
		email = self._invoice_emails()[0]
		self.assertEqual(email["reply_to"], "hd@miyano.vn")
		self.assertIn("Nguyễn Văn A", email["message"])

	def test_settings_cc_goes_out_with_the_automatic_email(self):
		configure(auto_send_invoice=1, invoice_email_cc="kt@miyano.vn")
		self._run()
		self.assertEqual(self._invoice_emails()[0]["cc"], ["kt@miyano.vn"])

	def test_the_comment_says_the_system_sent_it(self):
		self._run()
		comments = frappe.get_all(
			"Comment", filters={"reference_doctype": FEI, "reference_name": self.fei.name}, pluck="content"
		)
		self.assertTrue(any("Hệ thống đã tự gửi" in (c or "") for c in comments))

	def test_skips_without_email(self):
		self._set(email_deliver="")
		self.assertEqual(self._run(), [])
		self.assertEqual(self._value("auto_send_stopped"), 0)

	def test_skips_when_issued_over_24h_ago(self):
		self._set(issued_time=add_to_date(now_datetime(), hours=-25))
		self.assertEqual(self._run(), [])

	def test_skips_when_already_sent_by_hand(self):
		self._set(invoice_send_count=1)
		self.assertEqual(self._run(), [])

	def test_a_rejected_invoice_is_not_sent(self):
		self._set(status=STATUS_TAX_REJECTED)
		self.assertEqual(self._run(), [])


class TestAutoSendGuards(AutoSendBase):
	def test_skips_without_pdf(self):
		self._set(fast_lookup_code=LOOKUP_CODE)
		self.assertEqual(self._run(), [])
		self.assertEqual(self.mailbox.sent, [])

	def test_missing_lookup_code_stops_and_notifies_once(self):
		self._with_pdf()
		self._set(fast_lookup_code="")

		self._run()
		self._run()

		self.assertEqual(self._value("auto_send_stopped"), 1)
		self.assertEqual(self._invoice_emails(), [])
		self.assertEqual(len(self._notices()), 1)
		comments = frappe.get_all(
			"Comment", filters={"reference_doctype": FEI, "reference_name": self.fei.name}, pluck="content"
		)
		self.assertEqual(sum("Không đọc được mã tra cứu từ PDF —" in (c or "") for c in comments), 1)

	def test_waits_for_the_tax_code(self):
		self._with_pdf()
		self._set(tax_verification_code="")

		sent = self._run(client=self._client(tax_result("KEY-CUA-HOA-DON-KHAC", "3")))

		self.assertEqual(sent, [])
		self.assertEqual(self._value("auto_send_stopped"), 0)
		self.assertTrue(frappe.db.exists(LOG, {"fei_document": self.fei.name, "method": 8200}))

	def test_sends_once_the_tax_office_accepts(self):
		self._with_pdf()
		self._set(tax_verification_code="")

		sent = self._run(client=self._client(tax_result("KEY-AUTO-1", "3", verification_code="M-CQT-77")))

		self.assertEqual(sent, [self.fei.name])
		self.assertEqual(self._value("status"), STATUS_TAX_ACCEPTED)
		self.assertIn("M-CQT-77", self._invoice_emails()[0]["message"])

	def test_rejected_by_tax_office_is_not_sent(self):
		self._with_pdf()
		self._set(tax_verification_code="")

		sent = self._run(client=self._client(tax_result("KEY-AUTO-1", "4", feedback="Sai MST")))

		self.assertEqual(sent, [])
		self.assertEqual(self._invoice_emails(), [])
		self.assertEqual(self._value("status"), STATUS_TAX_REJECTED)

	def test_the_tax_office_is_not_asked_every_run(self):
		self._with_pdf()
		self._set(tax_verification_code="", tax_checked_time=now_datetime())

		self._run(client=self._client())

		self.assertFalse(frappe.db.exists(LOG, {"fei_document": self.fei.name, "method": 8200}))

	def test_gives_up_after_30_minutes_without_tax_code(self):
		self._with_pdf()
		self._set(tax_verification_code="", issued_time=add_to_date(now_datetime(), minutes=-31))

		self._run(client=self._client(tax_result("KEY-CUA-HOA-DON-KHAC", "3")))

		self.assertEqual(self._value("auto_send_stopped"), 1)
		self.assertEqual(len(self._notices()), 1)

	def test_three_mailer_failures_stop_auto_send(self):
		self._with_pdf()
		mailer = BrokenMailer()

		for _ in range(3):
			self._run(mailer=mailer)
		self._run(mailer=mailer)

		self.assertEqual(mailer.calls, 3)
		self.assertEqual(self._value("auto_send_stopped"), 1)
		self.assertEqual(self._value("invoice_send_count"), 0)
		self.assertEqual(
			frappe.db.count(LOG, {"fei_document": self.fei.name, "purpose": AUTO_SEND_PURPOSE, "success": 0}),
			3,
		)

	def test_one_broken_invoice_does_not_stop_the_batch(self):
		self._with_pdf()
		other_si = make_sales_invoice()
		other = create_from_sales_invoice(other_si.name)
		frappe.db.set_value(
			FEI,
			other,
			{
				"status": STATUS_ISSUED,
				"official_pdf": self.fei.official_pdf,
				"fast_lookup_code": LOOKUP_CODE,
				"tax_verification_code": "X",
				"email_deliver": "khac@bvx.vn",
				"fast_invoice_no": "8",
				"issued_time": add_to_date(now_datetime(), minutes=-2),
			},
		)
		calls = []

		def picky_mailer(**kwargs):
			calls.append(kwargs["recipients"])
			if kwargs["recipients"] == ["kh@bvx.vn"]:
				raise Exception("hỏng")

		self.assertEqual(self._run(mailer=picky_mailer), [other])
		self.assertEqual(len(calls), 2)


class TestPdfJobTriggersTheSend(AutoSendBase):
	def test_the_pdf_job_triggers_the_send(self):
		self._set(issued_time=add_to_date(now_datetime(), minutes=-2))

		download_pending_official_pdfs(
			client=self._client(lookup_envelope()), _sleep=lambda seconds: None, _mailer=self.mailbox
		)

		self.assertEqual(self._value("fast_lookup_code"), LOOKUP_CODE)
		self.assertEqual(len(self._invoice_emails()), 1)
		self.assertEqual(self._value("status"), STATUS_SENT)

	def test_the_send_runs_even_when_no_pdf_is_pending(self):
		self._with_pdf()
		download_pending_official_pdfs(
			client=self._client(), _sleep=lambda seconds: None, _mailer=self.mailbox
		)
		self.assertEqual(len(self._invoice_emails()), 1)


class TestAutoSendFailuresBeforeTheMailer(AutoSendBase):
	"""Mục 6.2: lỗi dựng email cũng là lỗi; Fast mất kết nối cũng phải báo sau 30 phút."""

	def test_a_broken_template_counts_as_a_failed_attempt(self):
		from unittest.mock import patch

		self._with_pdf()
		with patch("erpnext.einvoice.actions._render_template", side_effect=Exception("mẫu hỏng")):
			for _ in range(3):
				self._run()

		self.assertEqual(self._value("auto_send_stopped"), 1)
		self.assertEqual(len(self._notices()), 1)
		self.assertEqual(
			frappe.db.count(LOG, {"fei_document": self.fei.name, "purpose": AUTO_SEND_PURPOSE, "success": 0}),
			3,
		)

	def test_a_fast_outage_still_stops_after_30_minutes(self):
		from unittest.mock import patch

		self._with_pdf()
		self._set(tax_verification_code="", issued_time=add_to_date(now_datetime(), minutes=-31))
		with patch("erpnext.einvoice.tax_status._apply_tax_status", side_effect=Exception("Fast timeout")):
			self._run()

		self.assertEqual(self._value("auto_send_stopped"), 1)
		self.assertEqual(len(self._notices()), 1)

	def test_a_fast_outage_before_30_minutes_just_waits(self):
		from unittest.mock import patch

		self._with_pdf()
		self._set(tax_verification_code="")
		with patch("erpnext.einvoice.tax_status._apply_tax_status", side_effect=Exception("Fast timeout")):
			self.assertEqual(self._run(), [])

		self.assertEqual(self._value("auto_send_stopped"), 0)
