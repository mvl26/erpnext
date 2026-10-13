# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Cây thư mục file hóa đơn: ``Home/Invoices/{năm}/{tháng}/{ngày}/{số hóa đơn}``."""

import base64
import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, getdate, now_datetime, nowdate
from frappe.utils.file_manager import save_file

from erpnext.einvoice.actions import download_converted_pdf, download_official_pdf, preview_draft
from erpnext.einvoice.builder import create_from_delivery_note
from erpnext.einvoice.constants import STATUS_CUSTOMER_APPROVED, STATUS_ISSUED
from erpnext.einvoice.fast_client import FastClient
from erpnext.einvoice.folders import ROOT
from erpnext.einvoice.issue import issue_invoice
from erpnext.einvoice.tests.test_fast_client import FakeTransport, checkkey_ok, configure, envelope
from erpnext.einvoice.tests.test_fixtures import attach_official_xml, make_delivery_note, minimal_pdf_bytes

FEI = "Fast EInvoice Document"
LOG = "Fast EInvoice Log"
NOT_FOUND = envelope(0, "888|Khong tim thay")


def pdf(extra=b""):
	return envelope(1, base64.b64encode(minimal_pdf_bytes() + extra).decode())


class FolderTestBase(FrappeTestCase):
	def setUp(self):
		frappe.db.rollback()
		configure(token="TOKEN-ABC", token_time=now_datetime(), auto_download_pdf=0)
		self.dn = make_delivery_note()
		self.fei = frappe.get_doc(FEI, create_from_delivery_note(self.dn.name))
		# Số hóa đơn ngẫu nhiên: site thật có thể đã có thư mục cho các số nhỏ.
		self.number = str(int(frappe.generate_hash(length=8), 16))
		self.expected = f"{ROOT}/2026/08/07/{self.number}"

	def tearDown(self):
		frappe.db.rollback()

	def _client(self, *responses):
		self.transport = FakeTransport(checkkey_ok(), *responses)
		return FastClient(transport=self.transport)

	def _issued(self):
		frappe.db.set_value(
			FEI,
			self.fei.name,
			{
				"status": STATUS_ISSUED,
				"fast_key_search": "KS-ABC-123",
				"fast_invoice_no": self.number,
				"fast_serial": "1C26TMY",
				"fast_signed_date": "2026-08-07",
			},
		)
		self.fei.reload()

	def _folder_of(self, file_url, doctype=FEI, name=None):
		return frappe.db.get_value(
			"File",
			{"file_url": file_url, "attached_to_doctype": doctype, "attached_to_name": name or self.fei.name},
			"folder",
		)

	def _age_pdf_logs(self):
		for log in frappe.get_all(LOG, filters={"method": ("in", [380, 385])}, pluck="name"):
			frappe.db.set_value(
				LOG, log, "creation", add_to_date(now_datetime(), seconds=-60), update_modified=False
			)


class TestOfficialFiles(FolderTestBase):
	def test_no_folder_exists_before_a_file_is_saved(self):
		"""Không dựng thư mục trước — có file mới kiểm tra và tạo."""
		self._issued()
		self.assertFalse(frappe.db.exists("File", self.expected))

	def test_the_official_pdf_lands_in_year_month_day_number(self):
		self._issued()
		download_official_pdf(self.fei.name, client=self._client(pdf()))

		self.fei.reload()
		self.assertEqual(self._folder_of(self.fei.official_pdf), self.expected)

	def test_every_level_is_a_real_folder(self):
		self._issued()
		download_official_pdf(self.fei.name, client=self._client(pdf()))

		for path in (f"{ROOT}/2026", f"{ROOT}/2026/08", f"{ROOT}/2026/08/07", self.expected):
			self.assertEqual(frappe.db.get_value("File", path, "is_folder"), 1, path)

	def test_the_delivery_note_copy_sits_in_the_same_folder(self):
		self._issued()
		download_official_pdf(self.fei.name, client=self._client(pdf()))

		folders = frappe.get_all(
			"File",
			filters={"attached_to_doctype": "Delivery Note", "attached_to_name": self.dn.name},
			pluck="folder",
		)
		self.assertEqual(set(folders), {self.expected})

	def test_downloading_again_pulls_an_older_identical_file_into_the_folder(self):
		"""File cùng nội dung đã đính từ trước — Frappe trả lại bản ghi cũ, vẫn phải về đúng thư mục."""
		self._issued()
		old = save_file("cu.pdf", minimal_pdf_bytes(), FEI, self.fei.name, is_private=0)
		self.assertNotEqual(old.folder, self.expected)

		download_official_pdf(self.fei.name, client=self._client(pdf()))

		self.assertEqual(frappe.db.get_value("File", old.name, "folder"), self.expected)

	def test_older_drafts_are_gathered_when_the_official_pdf_arrives(self):
		"""Hóa đơn phát hành trước khi có cây thư mục: bản nháp cũ ở Home/Attachments gom về cùng chỗ."""
		self._issued()
		draft = save_file("Nhap_cu.pdf", minimal_pdf_bytes() + b"%%nhap\n", FEI, self.fei.name, is_private=1)

		download_official_pdf(self.fei.name, client=self._client(pdf()))

		self.assertEqual(frappe.db.get_value("File", draft.name, "folder"), self.expected)

	def test_a_second_file_reuses_the_folder_instead_of_making_another(self):
		self._issued()
		download_official_pdf(self.fei.name, client=self._client(pdf()))
		self._age_pdf_logs()
		download_converted_pdf(self.fei.name, convert_name="Chu Văn Hiếu", client=self._client(pdf(b"%%c\n")))

		self.fei.reload()
		self.assertEqual(self._folder_of(self.fei.converted_pdf), self.expected)
		self.assertEqual(frappe.db.count("File", {"name": self.expected, "is_folder": 1}), 1)


class TestDraftFiles(FolderTestBase):
	def _draft_folder(self):
		day = getdate(nowdate())
		return f"{ROOT}/{day.year:04d}/{day.month:02d}/{day.day:02d}/{self.fei.name}"

	def test_a_draft_waits_in_a_folder_named_after_the_document(self):
		"""Nháp chưa có số hóa đơn — tạm lưu dưới tên chứng từ HĐĐT."""
		preview_draft(self.fei.name, client=self._client(pdf()))

		self.fei.reload()
		self.assertEqual(self._folder_of(self.fei.draft_pdf), self._draft_folder())

	def test_issuing_moves_the_draft_into_the_number_folder_and_clears_the_temporary_one(self):
		preview_draft(self.fei.name, client=self._client(pdf()))
		self.fei.reload()
		draft_url, temporary = self.fei.draft_pdf, self._draft_folder()

		frappe.db.set_value(FEI, self.fei.name, "status", STATUS_CUSTOMER_APPROVED)
		issued = envelope(
			1,
			json.dumps(
				{
					"invoiceNo": self.number,
					"pattern": "1/001",
					"serial": "1C26TMY",
					"signedDate": "20260807",
					"keySearch": "KS-ABC-123",
				}
			),
		)
		issue_invoice(self.fei.name, client=self._client(NOT_FOUND, issued))

		self.assertEqual(self._folder_of(draft_url), self.expected)
		self.assertFalse(frappe.db.exists("File", temporary))


class TestXmlFile(FolderTestBase):
	def test_the_uploaded_xml_is_filed_with_the_invoice(self):
		self._issued()
		url = attach_official_xml(self.fei.name)
		self.assertEqual(self._folder_of(url), self.expected)

	def test_xml_cannot_be_attached_before_the_invoice_has_a_number(self):
		with self.assertRaises(frappe.ValidationError):
			attach_official_xml(self.fei.name)

	def test_only_an_xml_file_is_accepted(self):
		self._issued()
		saved = save_file("nham.pdf", minimal_pdf_bytes(), FEI, self.fei.name, is_private=1)

		self.fei.official_xml = saved.file_url
		self.fei.flags.ignore_links = True
		with self.assertRaises(frappe.ValidationError):
			self.fei.save(ignore_permissions=True)
