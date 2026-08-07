# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nút 8 & 9 — tải PDF chính thức (380) và PDF chuyển đổi (385) — mục E6."""

import base64

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from erpnext.einvoice.actions import download_converted_pdf, download_official_pdf
from erpnext.einvoice.builder import create_from_delivery_note
from erpnext.einvoice.constants import STATUS_DRAFT, STATUS_ISSUED, STATUS_TAX_ACCEPTED
from erpnext.einvoice.fast_client import FastClient
from erpnext.einvoice.test_fast_client import FakeTransport, configure, envelope
from erpnext.einvoice.test_fixtures import make_delivery_note, minimal_pdf_bytes

FEI = "Fast EInvoice Document"
LOG = "Fast EInvoice Log"


def pdf_envelope(extra=b""):
	return envelope(1, base64.b64encode(minimal_pdf_bytes() + extra).decode())


def sent_payload(body):
	"""Giải base64 tham số `data` để xem thực sự gửi gì lên Fast."""
	import json
	import re

	encoded = re.search(r"<data>(.*?)</data>", body).group(1)
	return json.loads(base64.b64decode(encoded).decode("utf-8"))


class PdfTestBase(FrappeTestCase):
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
				"fast_key_search": "KS-ABC-123",
				"fast_invoice_no": "2",
				"fast_serial": "1C26TMY",
			},
		)
		self.fei.reload()

	def tearDown(self):
		frappe.db.rollback()

	def _client(self, *responses):
		self.transport = FakeTransport(envelope(1, "still valid"), *responses)
		return FastClient(transport=self.transport)

	def _age_pdf_logs(self, seconds=60):
		"""Lùi thời điểm các lời gọi PDF để vượt qua cửa chặn 5 giây."""
		for name in frappe.get_all(LOG, filters={"method": ("in", [380, 385])}, pluck="name"):
			frappe.db.set_value(
				LOG, name, "creation", add_to_date(now_datetime(), seconds=-seconds), update_modified=False
			)


class TestOfficialPdf(PdfTestBase):
	def test_pdf_is_attached_to_the_invoice(self):
		download_official_pdf(self.fei.name, client=self._client(pdf_envelope()))

		self.fei.reload()
		self.assertTrue(self.fei.official_pdf)

	def test_filename_carries_the_serial_and_number(self):
		download_official_pdf(self.fei.name, client=self._client(pdf_envelope()))

		self.fei.reload()
		self.assertIn("HD_1C26TMY_2", self.fei.official_pdf)

	def test_the_lookup_key_is_what_gets_sent(self):
		download_official_pdf(self.fei.name, client=self._client(pdf_envelope()))
		self.assertEqual(sent_payload(self.transport.calls[-1]["body"])["key"], "KS-ABC-123")

	def test_it_uses_method_380(self):
		download_official_pdf(self.fei.name, client=self._client(pdf_envelope()))
		log = frappe.get_doc(LOG, {"fei_document": self.fei.name, "method": 380})
		self.assertEqual(log.action, 0)
		self.assertEqual(log.status, "Thành công")

	def test_the_pdf_also_lands_on_the_delivery_note(self):
		"""Kế toán kho cần bản PDF ngay trên phiếu giao, không phải lần mò sang chứng từ khác."""
		download_official_pdf(self.fei.name, client=self._client(pdf_envelope()))

		attached = frappe.get_all(
			"File",
			filters={"attached_to_doctype": "Delivery Note", "attached_to_name": self.dn.name},
			pluck="file_name",
		)
		self.assertTrue(any("HD_1C26TMY_2" in name for name in attached))

	def test_an_unissued_invoice_has_no_official_pdf(self):
		frappe.db.set_value(FEI, self.fei.name, "status", STATUS_DRAFT)
		with self.assertRaises(frappe.ValidationError):
			download_official_pdf(self.fei.name, client=self._client(pdf_envelope()))

	def test_missing_lookup_key_is_refused_before_calling(self):
		frappe.db.set_value(FEI, self.fei.name, "fast_key_search", "")
		client = self._client(pdf_envelope())

		with self.assertRaises(frappe.ValidationError):
			download_official_pdf(self.fei.name, client=client)
		self.assertEqual(self.transport.calls, [])

	def test_tax_accepted_invoice_can_still_be_downloaded(self):
		frappe.db.set_value(FEI, self.fei.name, "status", STATUS_TAX_ACCEPTED)
		download_official_pdf(self.fei.name, client=self._client(pdf_envelope()))

		self.fei.reload()
		self.assertTrue(self.fei.official_pdf)


class TestConvertedPdf(PdfTestBase):
	def test_converted_pdf_is_attached(self):
		download_converted_pdf(
			self.fei.name, convert_name="Chu Văn Hiếu", client=self._client(pdf_envelope(b"%%conv\n"))
		)

		self.fei.reload()
		self.assertTrue(self.fei.converted_pdf)

	def test_the_converter_name_is_sent_to_fast(self):
		"""Bản in giấy hợp lệ phải có tên người chuyển đổi."""
		download_converted_pdf(
			self.fei.name, convert_name="Chu Văn Hiếu", client=self._client(pdf_envelope(b"%%conv\n"))
		)
		self.assertEqual(sent_payload(self.transport.calls[-1]["body"])["convertName"], "Chu Văn Hiếu")

	def test_it_uses_method_385(self):
		download_converted_pdf(
			self.fei.name, convert_name="Chu Văn Hiếu", client=self._client(pdf_envelope(b"%%conv\n"))
		)
		self.assertTrue(frappe.db.exists(LOG, {"fei_document": self.fei.name, "method": 385}))

	def test_converter_name_is_required(self):
		client = self._client(pdf_envelope(b"%%conv\n"))
		with self.assertRaises(frappe.ValidationError):
			download_converted_pdf(self.fei.name, convert_name="", client=client)
		self.assertEqual(self.transport.calls, [])


class TestPdfThrottle(PdfTestBase):
	def test_two_pdf_calls_in_a_row_are_throttled(self):
		"""Đặc tả E6: hai lần gọi 380/385 phải cách nhau tối thiểu 5 giây."""
		download_official_pdf(self.fei.name, client=self._client(pdf_envelope()))

		with self.assertRaises(frappe.ValidationError) as caught:
			download_official_pdf(self.fei.name, client=self._client(pdf_envelope()))
		self.assertIn("giây", str(caught.exception))

	def test_the_throttle_lifts_once_enough_time_has_passed(self):
		download_official_pdf(self.fei.name, client=self._client(pdf_envelope()))
		self._age_pdf_logs(seconds=60)

		download_official_pdf(self.fei.name, client=self._client(pdf_envelope(b"%%v2\n")))
		self.fei.reload()
		self.assertTrue(self.fei.official_pdf)

	def test_the_throttle_spans_both_380_and_385(self):
		download_official_pdf(self.fei.name, client=self._client(pdf_envelope()))

		with self.assertRaises(frappe.ValidationError):
			download_converted_pdf(
				self.fei.name, convert_name="Chu Văn Hiếu", client=self._client(pdf_envelope())
			)


class TestAutoDownloadAfterIssue(PdfTestBase):
	def test_issuance_queues_the_pdf_download_when_configured(self):
		"""Mục E5 nhánh 7a: tự tải PDF sau khi phát hành, nếu cấu hình bật."""
		from erpnext.einvoice.issue import _queue_pdf_download

		queued = []
		_queue_pdf_download(self.fei, enqueue=lambda **kwargs: queued.append(kwargs))
		self.assertTrue(queued)
		self.assertEqual(queued[0]["fei"], self.fei.name)

	def test_nothing_is_queued_when_auto_download_is_off(self):
		configure(auto_download_pdf=0, token="TOKEN-ABC", token_time=now_datetime())
		from erpnext.einvoice.issue import _queue_pdf_download

		queued = []
		_queue_pdf_download(self.fei, enqueue=lambda **kwargs: queued.append(kwargs))
		self.assertEqual(queued, [])
