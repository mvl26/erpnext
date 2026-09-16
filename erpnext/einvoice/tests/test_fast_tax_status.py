# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nút 11 & 12 — trạng thái CQT (8200) và truy vấn đối soát (370) — mục E8."""

import json
from datetime import timedelta

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, get_datetime, getdate, now_datetime, nowdate

from erpnext.einvoice.builder import create_from_delivery_note
from erpnext.einvoice.constants import (
	STATUS_DRAFT,
	STATUS_ISSUED,
	STATUS_NEEDS_RECONCILE,
	STATUS_SENT,
	STATUS_TAX_ACCEPTED,
	STATUS_TAX_REJECTED,
	TAX_STATUS_ACCEPTED,
	TAX_STATUS_PENDING,
	TAX_STATUS_REJECTED,
)
from erpnext.einvoice.fast_client import FastClient
from erpnext.einvoice.reconcile import reconcile_invoice
from erpnext.einvoice.tax_status import _is_due, check_tax_status, poll_pending_tax_status
from erpnext.einvoice.tests.test_fast_client import FakeTransport, checkkey_ok, configure, envelope
from erpnext.einvoice.tests.test_fixtures import make_delivery_note

FEI = "Fast EInvoice Document"
LOG = "Fast EInvoice Log"

# Hình dạng thật của kết quả 8200 — tài liệu API Fast mục 17 (tr. 38-39):
# Message là chuỗi JSON ``{"data":[…]}``; mỗi dòng khớp hóa đơn theo ``key`` —
# chính là Key client đã gửi lúc phát hành, không phải keySearch.
TAX_QUERY_FIELDS = {
	"invoiceDateFrom",
	"invoiceDateTo",
	"invoiceNumberFrom",
	"invoiceNumberTo",
	"voucherBook",
	"invoiceType",
}


def tax_result(key, tax_status, verification_code="", feedback=""):
	rows = [
		{
			"key": key,
			"invoiceDate": getdate(nowdate()).strftime("%Y%m%d"),
			"taxStatus": tax_status,
			"verificationCode": verification_code,
			"feedbackContent": feedback,
		}
	]
	return envelope(1, json.dumps({"data": rows}))


class TaxStatusBase(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure(token="TOKEN-ABC", token_time=now_datetime())
		self.dn = make_delivery_note()
		self.fei = frappe.get_doc(FEI, create_from_delivery_note(self.dn.name))
		frappe.db.set_value(
			FEI,
			self.fei.name,
			{
				"status": STATUS_ISSUED,
				"tax_status": TAX_STATUS_PENDING,
				"fast_key": "KEY-ABC-123",
				"fast_key_search": "KS-ABC-123",
				"fast_invoice_no": "2",
				"fast_serial": "1C26TMY",
				"fast_signed_date": nowdate(),
			},
		)
		self.fei.reload()

	def tearDown(self):
		frappe.db.rollback()

	def _client(self, *responses):
		self.transport = FakeTransport(checkkey_ok(), *responses)
		return FastClient(transport=self.transport)

	def accepted(self):
		return tax_result(self.fei.fast_key, "3", verification_code="M1-0099")

	def rejected(self):
		return tax_result(self.fei.fast_key, "4", feedback="Sai mã số thuế người mua")

	def not_listed(self):
		return tax_result("KEY-CUA-HOA-DON-KHAC", "3")


class TestCheckTaxStatus(TaxStatusBase):
	def test_acceptance_advances_the_invoice(self):
		check_tax_status(self.fei.name, client=self._client(self.accepted()))

		self.fei.reload()
		self.assertEqual(self.fei.tax_status, TAX_STATUS_ACCEPTED)
		self.assertEqual(self.fei.status, STATUS_TAX_ACCEPTED)
		self.assertEqual(self.fei.tax_verification_code, "M1-0099")
		self.assertIsNotNone(self.fei.tax_checked_time)

	def test_rejection_is_recorded_with_the_reason(self):
		check_tax_status(self.fei.name, client=self._client(self.rejected()))

		self.fei.reload()
		self.assertEqual(self.fei.tax_status, TAX_STATUS_REJECTED)
		self.assertEqual(self.fei.status, STATUS_TAX_REJECTED)
		self.assertIn("Sai mã số thuế", self.fei.tax_feedback)

	def test_an_invoice_not_in_the_result_stays_pending(self):
		"""Đặc tả E8: không có trong kết quả = CQT chưa xử lý xong, không phải là từ chối."""
		check_tax_status(self.fei.name, client=self._client(self.not_listed()))

		self.fei.reload()
		self.assertEqual(self.fei.tax_status, TAX_STATUS_PENDING)
		self.assertEqual(self.fei.status, STATUS_ISSUED)
		self.assertIsNotNone(self.fei.tax_checked_time)

	def test_it_uses_method_8200(self):
		check_tax_status(self.fei.name, client=self._client(self.accepted()))
		log = frappe.get_doc(LOG, {"fei_document": self.fei.name, "method": 8200})
		self.assertEqual(log.status, "Thành công")

	def test_the_query_carries_every_field_fast_requires(self):
		"""Tài liệu Fast mục 17: thiếu một thẻ là Fast ném 810 "The given key was not present"."""
		check_tax_status(self.fei.name, client=self._client(self.accepted()))

		log = frappe.get_doc(LOG, {"fei_document": self.fei.name, "method": 8200})
		payload = json.loads(log.request_json)["payload"]
		self.assertEqual(set(payload), TAX_QUERY_FIELDS)
		today = getdate(nowdate()).strftime("%Y%m%d")
		self.assertEqual(payload["invoiceDateFrom"], today)
		self.assertEqual(payload["invoiceDateTo"], today)
		self.assertEqual(payload["invoiceNumberFrom"], "2")
		self.assertEqual(payload["invoiceNumberTo"], "2")
		self.assertEqual(payload["invoiceType"], "1")

	def test_the_query_covers_the_invoice_date_when_issued_later(self):
		"""8200 lọc theo ngày hóa đơn (= ngày phiếu giao), không phải ngày ký.

		Phát hành sau ngày giao hàng mà chỉ hỏi theo ngày ký thì Fast trả rỗng và
		hóa đơn kẹt "Chờ CQT" mãi dù CQT đã chấp nhận từ lâu.
		"""
		invoice_day = add_to_date(nowdate(), days=-2)
		frappe.db.set_value(FEI, self.fei.name, "invoice_date", invoice_day)
		check_tax_status(self.fei.name, client=self._client(self.accepted()))

		log = frappe.get_doc(LOG, {"fei_document": self.fei.name, "method": 8200})
		payload = json.loads(log.request_json)["payload"]
		self.assertEqual(payload["invoiceDateFrom"], getdate(invoice_day).strftime("%Y%m%d"))
		self.assertEqual(payload["invoiceDateTo"], getdate(nowdate()).strftime("%Y%m%d"))

	def test_padded_fields_in_the_result_still_match(self):
		"""Tài liệu Fast mục 17 có ví dụ đệm khoảng trắng quanh cả tên thẻ lẫn giá trị."""
		row = {
			" key ": f" {self.fei.fast_key} ",
			" taxStatus ": " 3 ",
			" verificationCode ": " M1-0099 ",
			" feedbackContent ": "",
		}
		padded = envelope(1, json.dumps({"data": [row]}))
		check_tax_status(self.fei.name, client=self._client(padded))

		self.fei.reload()
		self.assertEqual(self.fei.status, STATUS_TAX_ACCEPTED)
		self.assertEqual(self.fei.tax_verification_code, "M1-0099")

	def test_a_sent_invoice_can_also_be_checked(self):
		frappe.db.set_value(FEI, self.fei.name, "status", STATUS_SENT)
		check_tax_status(self.fei.name, client=self._client(self.accepted()))

		self.fei.reload()
		self.assertEqual(self.fei.status, STATUS_TAX_ACCEPTED)

	def test_an_unissued_invoice_has_no_tax_status_to_check(self):
		frappe.db.set_value(FEI, self.fei.name, "status", STATUS_DRAFT)
		with self.assertRaises(frappe.ValidationError):
			check_tax_status(self.fei.name, client=self._client(self.accepted()))


class TestPollJob(TaxStatusBase):
	def test_the_job_picks_up_pending_invoices(self):
		checked = poll_pending_tax_status(client=self._client(self.accepted()))

		self.fei.reload()
		self.assertIn(self.fei.name, checked)
		self.assertEqual(self.fei.status, STATUS_TAX_ACCEPTED)

	def test_invoices_older_than_the_window_are_left_alone(self):
		"""Quét 7 ngày gần nhất — hóa đơn cũ hơn thì đối soát tay, không quét mãi."""
		frappe.db.set_value(FEI, self.fei.name, "fast_signed_date", add_to_date(nowdate(), days=-30))
		checked = poll_pending_tax_status(client=self._client(self.accepted()))
		self.assertNotIn(self.fei.name, checked)

	def test_already_settled_invoices_are_not_polled_again(self):
		frappe.db.set_value(FEI, self.fei.name, "tax_status", TAX_STATUS_ACCEPTED)
		checked = poll_pending_tax_status(client=self._client(self.accepted()))
		self.assertNotIn(self.fei.name, checked)

	def test_the_job_does_nothing_when_auto_polling_is_off(self):
		configure(auto_poll_tax_status=0, token="TOKEN-ABC", token_time=now_datetime())
		self.assertEqual(poll_pending_tax_status(client=self._client(self.accepted())), [])

	def _age(self, hours, checked_minutes_ago=None):
		now = now_datetime()
		issued = add_to_date(now, hours=-hours)
		frappe.db.set_value(
			FEI,
			self.fei.name,
			{
				"issued_time": issued,
				"fast_signed_date": getdate(issued),
				"tax_checked_time": (
					add_to_date(now, minutes=-checked_minutes_ago) if checked_minutes_ago is not None else None
				),
			},
		)

	def _polled(self):
		return self.fei.name in poll_pending_tax_status(client=self._client(self.accepted()))

	def test_a_fresh_invoice_is_asked_every_run(self):
		self._age(hours=1, checked_minutes_ago=20)
		self.assertTrue(self._polled())

	def test_an_older_invoice_is_not_asked_again_so_soon(self):
		"""Hóa đơn 5 giờ tuổi vừa hỏi 20 phút trước thì bỏ qua lượt này — không gọi dồn."""
		self._age(hours=5, checked_minutes_ago=20)
		self.assertFalse(self._polled())

	def test_it_asks_again_once_the_gap_has_passed(self):
		self._age(hours=5, checked_minutes_ago=118)
		self.assertTrue(self._polled())

	def test_it_stops_asking_after_three_days(self):
		"""Quá mốc cuối thì thôi tự hỏi — báo cáo đối soát gom lại cho người xử lý."""
		self._age(hours=80)
		self.assertFalse(self._polled())

	def test_a_stuck_invoice_costs_a_bounded_number_of_calls(self):
		"""Hóa đơn kẹt "Chờ CQT" mãi: hỏi 20 phút/lần suốt 7 ngày là ~500 lời gọi."""
		issued = get_datetime("2026-09-01 08:00:00")
		row = frappe._dict(issued_time=issued, fast_signed_date=issued.date(), tax_checked_time=None)
		calls = []
		for step in range(7 * 72):  # cron 20 phút/lượt, 7 ngày
			now = issued + timedelta(minutes=20 * step, seconds=7)
			if _is_due(row, now):
				calls.append(now)
				row.tax_checked_time = now + timedelta(seconds=3)

		self.assertLessEqual(len(calls), 25)
		self.assertLess(calls[-1], issued + timedelta(hours=72))

	def test_the_job_is_registered_on_a_cron_schedule(self):
		cron = frappe.get_hooks("scheduler_events").get("cron") or {}
		registered = [job for jobs in cron.values() for job in jobs]
		self.assertIn("erpnext.einvoice.tax_status.poll_pending_tax_status", registered)


class TestReconcile(TaxStatusBase):
	"""Nút 12 — truy vấn đối soát (370)."""

	def test_matching_data_reports_no_difference(self):
		same = envelope(1, '{"invoiceNo":"2","serial":"1C26TMY","keySearch":"KS-ABC-123"}')
		result = reconcile_invoice(self.fei.name, client=self._client(same))
		self.assertEqual(result["differences"], [])

	def test_differences_are_reported_without_being_written(self):
		"""Ghi đè dữ liệu hóa đơn phải có xác nhận của người dùng (cấp 2)."""
		other = envelope(1, '{"invoiceNo":"77","serial":"1C26TMY","keySearch":"KS-ABC-123"}')
		result = reconcile_invoice(self.fei.name, client=self._client(other))

		self.fei.reload()
		self.assertTrue(result["differences"])
		self.assertEqual(self.fei.fast_invoice_no, "2")

	def test_applying_the_difference_overwrites_from_fast(self):
		other = envelope(1, '{"invoiceNo":"77","serial":"1C26TMY","keySearch":"KS-ABC-123"}')
		reconcile_invoice(self.fei.name, apply=True, client=self._client(other))

		self.fei.reload()
		self.assertEqual(self.fei.fast_invoice_no, "77")

	def test_not_found_on_fast_is_reported_as_never_issued(self):
		result = reconcile_invoice(self.fei.name, client=self._client(envelope(0, "888|Khong tim thay")))
		self.assertFalse(result["found"])

	def test_a_timed_out_invoice_recovers_its_number(self):
		"""Đường thoát của nhánh 7c: 370 cho biết hóa đơn thực ra đã ra số."""
		frappe.db.set_value(
			FEI,
			self.fei.name,
			{
				"status": STATUS_NEEDS_RECONCILE,
				"fast_invoice_no": "",
				"fast_key_search": "",
				"tax_status": "",
			},
		)
		recovered = envelope(1, '{"invoiceNo":"2","serial":"1C26TMY","keySearch":"KS-ABC-123"}')
		reconcile_invoice(self.fei.name, apply=True, client=self._client(recovered))

		self.fei.reload()
		self.assertEqual(self.fei.status, STATUS_ISSUED)
		self.assertEqual(self.fei.fast_invoice_no, "2")
		self.assertEqual(self.fei.fast_key_search, "KS-ABC-123")

	def test_a_timed_out_invoice_confirmed_unissued_returns_to_draft(self):
		"""Không có trên Fast nghĩa là chưa tiêu số nào — cho phát hành lại."""
		frappe.db.set_value(FEI, self.fei.name, {"status": STATUS_NEEDS_RECONCILE, "fast_invoice_no": ""})
		reconcile_invoice(self.fei.name, apply=True, client=self._client(envelope(0, "888|Khong tim thay")))

		self.fei.reload()
		self.assertEqual(self.fei.status, STATUS_DRAFT)

	def test_it_uses_method_370(self):
		same = envelope(1, '{"invoiceNo":"2","keySearch":"KS-ABC-123"}')
		reconcile_invoice(self.fei.name, client=self._client(same))
		self.assertTrue(frappe.db.exists(LOG, {"fei_document": self.fei.name, "method": 370}))
