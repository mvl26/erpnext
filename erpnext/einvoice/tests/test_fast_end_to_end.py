# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Kịch bản end-to-end của Giai đoạn 6 — chạy trọn vòng đời trên transport giả.

Các kịch bản còn lại (hóa đơn 250 dòng, khách cá nhân có CCCD, chạy thật trên
sandbox) cần tài khoản Fast thật — xem `docs/fast_miyano/RUNBOOK_HDDT_FAST.md`.
"""

import base64
import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from erpnext.einvoice.actions import (
	download_official_pdf,
	mark_customer_approved,
	preview_draft,
	record_customer_feedback,
	send_draft_to_customer,
	send_invoice_to_customer,
)
from erpnext.einvoice.builder import create_from_delivery_note, resync_from_delivery_note
from erpnext.einvoice.constants import (
	STATUS_ADJUSTED,
	STATUS_AWAITING_CUSTOMER,
	STATUS_CUSTOMER_APPROVED,
	STATUS_DRAFT,
	STATUS_DRAFT_VIEWED,
	STATUS_ISSUED,
	STATUS_NEEDS_RECONCILE,
	STATUS_SENT,
	STATUS_TAX_ACCEPTED,
)
from erpnext.einvoice.fast_client import FastClient
from erpnext.einvoice.issue import issue_invoice
from erpnext.einvoice.lineage import create_adjustment
from erpnext.einvoice.reconcile import reconcile_invoice
from erpnext.einvoice.tax_status import check_tax_status
from erpnext.einvoice.tests.test_fast_approval import Mailbox
from erpnext.einvoice.tests.test_fast_client import FakeTransport, checkkey_ok, configure, envelope
from erpnext.einvoice.tests.test_fixtures import make_delivery_note, minimal_pdf_bytes

FEI = "Fast EInvoice Document"

NOT_FOUND = envelope(0, "888|Khong tim thay")
ISSUE_OK = envelope(
	1, '{"invoiceNo":"2","pattern":"1/001","serial":"1C26TMY","signedDate":"20260807","keySearch":"KS-1"}'
)


def pdf():
	return envelope(1, base64.b64encode(minimal_pdf_bytes()).decode())


class EndToEndBase(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure(token="TOKEN-ABC", token_time=now_datetime(), auto_download_pdf=0)
		self.mailbox = Mailbox()
		self.dn = make_delivery_note()
		self.fei = create_from_delivery_note(self.dn.name)

	def tearDown(self):
		frappe.db.rollback()

	def client(self, *responses):
		self.transport = FakeTransport(checkkey_ok(), *responses)
		return FastClient(transport=self.transport)

	def status(self):
		return frappe.db.get_value(FEI, self.fei, "status")

	def tax_ok(self):
		"""Kết quả 8200 của Fast — khớp hóa đơn theo ``key`` client đã gửi lúc phát hành."""
		row = {
			"key": frappe.db.get_value(FEI, self.fei, "fast_key"),
			"taxStatus": "3",
			"verificationCode": "M1-0099",
			"feedbackContent": "",
		}
		return envelope(1, json.dumps({"data": [row]}))

	def draft_round(self):
		preview_draft(self.fei, client=self.client(pdf()))
		send_draft_to_customer(self.fei, mailer=self.mailbox)


class TestScenario9DraftRevisionCycle(EndToEndBase):
	"""Kịch bản 9: gửi khách → sửa 2 lần → duyệt → phát hành."""

	def test_the_full_revision_cycle_ends_in_an_issued_invoice(self):
		self.draft_round()
		self.assertEqual(self.status(), STATUS_AWAITING_CUSTOMER)

		record_customer_feedback(self.fei, "Khách yêu cầu sửa lại tên đơn vị mua")
		self.assertEqual(self.status(), STATUS_DRAFT)

		self.draft_round()
		record_customer_feedback(self.fei, "Khách yêu cầu sửa lại địa chỉ xuất hóa đơn")
		self.assertEqual(self.status(), STATUS_DRAFT)

		self.draft_round()
		mark_customer_approved(self.fei, approved_by="Chị Lan (BV X)", channel="Email")
		self.assertEqual(self.status(), STATUS_CUSTOMER_APPROVED)

		issue_invoice(self.fei, client=self.client(NOT_FOUND, ISSUE_OK))
		self.assertEqual(self.status(), STATUS_ISSUED)

	def test_two_customer_revisions_are_counted_as_two(self):
		"""revision_count đếm số lần quay về Nháp từ 02/03/04 (mục C2.2 #19)."""
		self.draft_round()
		record_customer_feedback(self.fei, "Sửa tên đơn vị mua giúp anh")
		self.draft_round()
		record_customer_feedback(self.fei, "Sửa nốt địa chỉ xuất hóa đơn")

		self.assertEqual(frappe.db.get_value(FEI, self.fei, "revision_count"), 2)

	def test_resyncing_a_draft_does_not_inflate_the_revision_count(self):
		"""Đồng bộ lại một bản đang là Nháp không phải là một vòng sửa với khách."""
		self.draft_round()
		record_customer_feedback(self.fei, "Sửa tên đơn vị mua giúp anh")

		resync_from_delivery_note(self.fei)
		self.assertEqual(frappe.db.get_value(FEI, self.fei, "revision_count"), 1)

	def test_the_feedback_history_survives_the_whole_cycle(self):
		self.draft_round()
		record_customer_feedback(self.fei, "Sửa tên đơn vị mua giúp anh")
		self.draft_round()
		record_customer_feedback(self.fei, "Sửa nốt địa chỉ xuất hóa đơn")

		history = frappe.db.get_value(FEI, self.fei, "customer_feedback")
		self.assertIn("tên đơn vị mua", history)
		self.assertIn("địa chỉ xuất hóa đơn", history)


class TestScenario1HappyPath(EndToEndBase):
	"""Kịch bản 1: khách doanh nghiệp có MST, VAT 10% — trọn đường tới CQT."""

	def test_from_delivery_note_to_tax_office_acceptance(self):
		self.draft_round()
		mark_customer_approved(self.fei, approved_by="Chị Lan", channel="Email")
		issue_invoice(self.fei, client=self.client(NOT_FOUND, ISSUE_OK))

		download_official_pdf(self.fei, client=self.client(pdf()))
		send_invoice_to_customer(self.fei, mailer=self.mailbox)
		self.assertEqual(self.status(), STATUS_SENT)

		check_tax_status(self.fei, client=self.client(self.tax_ok()))
		self.assertEqual(self.status(), STATUS_TAX_ACCEPTED)

	def test_the_delivery_note_mirrors_the_final_state(self):
		self.draft_round()
		mark_customer_approved(self.fei, approved_by="Chị Lan", channel="Email")
		issue_invoice(self.fei, client=self.client(NOT_FOUND, ISSUE_OK))

		self.dn.reload()
		self.assertEqual(self.dn.fast_invoice_no, "2")
		self.assertEqual(self.dn.fast_einvoice, self.fei)


class TestScenario7NetworkCutMidIssue(EndToEndBase):
	"""Kịch bản 7: ngắt mạng giữa lúc phát hành, rồi đối soát bằng 370."""

	def test_a_timeout_recovers_the_real_invoice_number(self):
		import requests

		self.draft_round()
		mark_customer_approved(self.fei, approved_by="Chị Lan", channel="Email")

		issue_invoice(self.fei, client=self.client(NOT_FOUND, requests.Timeout("đứt mạng")))
		self.assertEqual(self.status(), STATUS_NEEDS_RECONCILE)

		# Hóa đơn thực ra đã ra số ở phía Fast.
		reconcile_invoice(self.fei, apply=True, client=self.client(ISSUE_OK))

		self.assertEqual(self.status(), STATUS_ISSUED)
		self.assertEqual(frappe.db.get_value(FEI, self.fei, "fast_invoice_no"), "2")

	def test_a_timeout_that_never_reached_fast_returns_to_draft(self):
		import requests

		self.draft_round()
		mark_customer_approved(self.fei, approved_by="Chị Lan", channel="Email")
		issue_invoice(self.fei, client=self.client(NOT_FOUND, requests.Timeout("đứt mạng")))

		reconcile_invoice(self.fei, apply=True, client=self.client(NOT_FOUND))
		self.assertEqual(self.status(), STATUS_DRAFT)

	def test_no_second_invoice_number_is_ever_burned(self):
		"""Điều quan trọng nhất của kịch bản 7: một lần bán chỉ một số hóa đơn."""
		import requests

		self.draft_round()
		mark_customer_approved(self.fei, approved_by="Chị Lan", channel="Email")
		issue_invoice(self.fei, client=self.client(NOT_FOUND, requests.Timeout("đứt mạng")))

		# Bấm phát hành lại: truy vấn thấy hóa đơn đã tồn tại nên phải dừng.
		with self.assertRaises(frappe.ValidationError):
			issue_invoice(self.fei, client=self.client(ISSUE_OK))

		issue_commands = [c for c in self.transport.calls if "<method>310</method>" in c["body"]]
		self.assertEqual(issue_commands, [])


class TestScenario10AdjustmentAfterAcceptance(EndToEndBase):
	"""Kịch bản 10: điều chỉnh giảm sau khi CQT chấp nhận."""

	def test_the_original_is_locked_and_linked_both_ways(self):
		self.draft_round()
		mark_customer_approved(self.fei, approved_by="Chị Lan", channel="Email")
		issue_invoice(self.fei, client=self.client(NOT_FOUND, ISSUE_OK))
		check_tax_status(self.fei, client=self.client(self.tax_ok()))

		child = create_adjustment(
			self.fei, adjustment_type="1 - Điều chỉnh giảm", reason="Khách trả lại 10 hộp"
		)
		frappe.db.set_value(FEI, child, "status", STATUS_CUSTOMER_APPROVED)

		child_ok = envelope(1, '{"invoiceNo":"3","serial":"1C26TMY","keySearch":"KS-2"}')
		issue_invoice(child, client=self.client(NOT_FOUND, child_ok))

		self.assertEqual(self.status(), STATUS_ADJUSTED)
		self.assertEqual(frappe.db.get_value(FEI, self.fei, "amended_from_fei"), child)
		self.assertEqual(frappe.db.get_value(FEI, child, "original_document"), self.fei)


class TestScenario6DoubleClick(EndToEndBase):
	"""Kịch bản 6: bấm nút phát hành hai lần liên tiếp."""

	def test_only_one_invoice_is_born(self):
		self.draft_round()
		mark_customer_approved(self.fei, approved_by="Chị Lan", channel="Email")
		issue_invoice(self.fei, client=self.client(NOT_FOUND, ISSUE_OK))

		with self.assertRaises(frappe.ValidationError):
			issue_invoice(self.fei, client=self.client(NOT_FOUND, ISSUE_OK))

		self.assertEqual(frappe.db.get_value(FEI, self.fei, "fast_invoice_no"), "2")


class TestScenario3ValidationStopsBeforeFast(EndToEndBase):
	"""Kịch bản 3: có MST nhưng xóa địa chỉ.

	Chốt chặn chỉ đứng ở nút phát hành. Bản nháp vẫn xem được — đó là cách kế
	toán nhìn ra mình thiếu địa chỉ; khóa nó lại là khóa đúng cái cửa dẫn tới
	chỗ sửa. Bản nháp không tiêu số hóa đơn nên không có gì để mất.
	"""

	def test_the_draft_is_still_viewable_so_the_mistake_can_be_found(self):
		frappe.db.set_value(FEI, self.fei, "address", "")

		result = preview_draft(self.fei, client=self.client(pdf()))

		self.assertTrue(result["ok"])
		self.assertEqual(self.status(), STATUS_DRAFT_VIEWED)

	def test_nothing_is_sent_to_fast_when_issuing_without_an_address(self):
		frappe.db.set_value(FEI, self.fei, "address", "")
		frappe.db.set_value(FEI, self.fei, "status", STATUS_CUSTOMER_APPROVED)
		client = self.client(NOT_FOUND, ISSUE_OK)

		with self.assertRaises(frappe.ValidationError):
			issue_invoice(self.fei, client=client)

		self.assertEqual(self.transport.calls, [])
		self.assertEqual(self.status(), STATUS_CUSTOMER_APPROVED)
