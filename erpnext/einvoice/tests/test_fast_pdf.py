# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nút 8 & 9 — tải PDF chính thức (380) và PDF chuyển đổi (385) — mục E6."""

import base64

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, get_url, now_datetime

from erpnext.einvoice.actions import (
	download_converted_pdf,
	download_official_pdf,
	download_pending_official_pdfs,
)
from erpnext.einvoice.builder import create_from_delivery_note
from erpnext.einvoice.constants import STATUS_DRAFT, STATUS_ISSUED, STATUS_TAX_ACCEPTED
from erpnext.einvoice.fast_client import FastClient
from erpnext.einvoice.tests.test_fast_client import FakeTransport, checkkey_ok, configure, envelope
from erpnext.einvoice.tests.test_fixtures import make_delivery_note, minimal_pdf_bytes

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
		self.transport = FakeTransport(checkkey_ok(), *responses)
		return FastClient(transport=self.transport)

	def _issued_seconds_ago(self, seconds):
		frappe.db.set_value(FEI, self.fei.name, "issued_time", add_to_date(now_datetime(), seconds=-seconds))

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

	def test_empty_response_gives_a_pdf_not_ready_hint(self):
		"""Fast trả rỗng ngay sau phát hành HSM — nói rõ PDF chưa sẵn sàng, đừng "không rõ mã"."""
		from erpnext.einvoice.tests.test_fast_client import auth_empty

		result = download_official_pdf(self.fei.name, client=self._client(auth_empty("ExcuteCommand")))
		self.assertFalse(result["ok"])
		self.assertIn("ký số", result["message"])
		self.assertNotIn("không rõ mã", result["message"])


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


class TestOfficialPdfIsPublic(PdfTestBase):
	"""PDF chính thức công khai — link gửi thẳng cho khách, khỏi giải thích mã tra cứu."""

	def _download(self):
		download_official_pdf(self.fei.name, client=self._client(pdf_envelope()))
		self.fei.reload()

	def test_the_official_pdf_is_public(self):
		self._download()
		self.assertEqual(frappe.db.get_value("File", {"file_url": self.fei.official_pdf}, "is_private"), 0)

	def test_the_delivery_note_copy_is_public_too(self):
		self._download()
		privacy = frappe.get_all(
			"File",
			filters={"attached_to_doctype": "Delivery Note", "attached_to_name": self.dn.name},
			pluck="is_private",
		)
		self.assertTrue(privacy)
		self.assertEqual(set(privacy), {0})

	def test_the_link_cannot_be_guessed_from_serial_and_number(self):
		"""Chỉ có ký hiệu + số thì đổi số trên link là ra hóa đơn của khách khác."""
		self._download()
		self.assertNotIn("/files/HD_1C26TMY_2.pdf", self.fei.official_pdf)
		self.assertRegex(self.fei.official_pdf, r"HD_1C26TMY_2_[0-9a-f]{16}")

	def test_a_full_erp_link_lands_on_the_invoice_and_the_delivery_note(self):
		self._download()
		self.assertEqual(self.fei.public_pdf_url, get_url(self.fei.official_pdf))
		self.assertTrue(self.fei.public_pdf_url.startswith("http"))

		self.dn.reload()
		self.assertEqual(self.dn.fast_einvoice_pdf_url, self.fei.public_pdf_url)

	def test_the_converted_pdf_stays_private(self):
		"""Bản chuyển đổi mang tên người chuyển đổi — không công khai."""
		download_converted_pdf(
			self.fei.name, convert_name="Chu Văn Hiếu", client=self._client(pdf_envelope(b"%%conv\n"))
		)
		self.fei.reload()
		self.assertEqual(frappe.db.get_value("File", {"file_url": self.fei.converted_pdf}, "is_private"), 1)


class TestWaitForSigning(PdfTestBase):
	"""Fast cần khoảng 30 giây – 1 phút ký số xong mới có PDF — gọi sớm chỉ nhận về rỗng."""

	def test_downloading_right_after_issuance_is_refused_without_calling_fast(self):
		self._issued_seconds_ago(10)
		client = self._client(pdf_envelope())

		with self.assertRaises(frappe.ValidationError) as caught:
			download_official_pdf(self.fei.name, client=client)
		self.assertIn("giây", str(caught.exception))
		self.assertEqual(self.transport.calls, [])

	def test_it_downloads_once_a_minute_has_passed(self):
		self._issued_seconds_ago(70)
		download_official_pdf(self.fei.name, client=self._client(pdf_envelope()))

		self.fei.reload()
		self.assertTrue(self.fei.official_pdf)


class TestAutoDownloadJob(PdfTestBase):
	"""Job mỗi phút tự tải PDF khi Fast ký số xong — thay cho tải ngay sau phát hành."""

	def setUp(self):
		super().setUp()
		configure(token="TOKEN-ABC", token_time=now_datetime(), auto_download_pdf=1)

	def _run(self):
		return download_pending_official_pdfs(client=self._client(pdf_envelope()), _sleep=lambda _s: None)

	def _fail_once(self):
		"""Một lần Fast trả rỗng (PDF chưa sẵn sàng) — để lại một dòng nhật ký 380."""
		from erpnext.einvoice.tests.test_fast_client import auth_empty

		download_official_pdf(self.fei.name, client=self._client(auth_empty("ExcuteCommand")))

	def test_a_just_issued_invoice_is_left_alone(self):
		self._issued_seconds_ago(30)
		self.assertNotIn(self.fei.name, self._run())

	def test_it_downloads_once_fast_has_had_a_minute(self):
		self._issued_seconds_ago(90)
		self.assertIn(self.fei.name, self._run())

		self.fei.reload()
		self.assertTrue(self.fei.official_pdf)
		self.assertTrue(self.fei.public_pdf_url)

	def test_a_recent_failed_attempt_is_not_retried_straight_away(self):
		self._issued_seconds_ago(300)
		self._fail_once()
		self._age_pdf_logs(seconds=60)
		self.assertNotIn(self.fei.name, self._run())

	def test_it_retries_once_two_minutes_have_passed(self):
		self._issued_seconds_ago(300)
		self._fail_once()
		self._age_pdf_logs(seconds=150)
		self.assertIn(self.fei.name, self._run())

	def test_it_gives_up_after_five_attempts(self):
		"""Hết lượt thì để kế toán bấm tay — không gọi Fast mãi."""
		self._issued_seconds_ago(3000)
		for _attempt in range(5):
			self._age_pdf_logs(seconds=150)  # vượt cửa chặn 5 giây giữa hai lần gọi PDF
			self._fail_once()
		self._age_pdf_logs(seconds=150)
		self.assertNotIn(self.fei.name, self._run())

	def test_an_invoice_that_already_has_its_pdf_is_skipped(self):
		self._issued_seconds_ago(90)
		frappe.db.set_value(FEI, self.fei.name, "official_pdf", "/files/da_co.pdf")
		self.assertNotIn(self.fei.name, self._run())

	def test_invoices_older_than_a_day_are_left_for_manual_download(self):
		self._issued_seconds_ago(25 * 3600)
		self.assertNotIn(self.fei.name, self._run())

	def test_nothing_happens_when_auto_download_is_off(self):
		configure(auto_download_pdf=0, token="TOKEN-ABC", token_time=now_datetime())
		self._issued_seconds_ago(90)
		self.assertEqual(self._run(), [])

	def test_the_job_runs_every_minute(self):
		cron = frappe.get_hooks("scheduler_events").get("cron") or {}
		self.assertIn("erpnext.einvoice.actions.download_pending_official_pdfs", cron.get("* * * * *", []))
