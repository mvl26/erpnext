# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Đọc mã tra cứu và trang tra cứu in trên PDF chính thức của Fast (mục 4.3)."""

from frappe.tests.utils import FrappeTestCase

from erpnext.einvoice.pdf_lookup import parse_lookup_text, read_lookup_from_pdf
from erpnext.einvoice.tests.test_fixtures import (
	LOOKUP_CODE,
	LOOKUP_URL,
	lookup_pdf_bytes,
	minimal_pdf_bytes,
)

# Đúng chuỗi pypdf 6.12 tách ra từ PDF thật của FEI-2026-00005: nhãn, dấu hai
# chấm và giá trị nằm trên các dòng khác nhau.
REAL_TEXT = (
	"Mã tra cứu hóa đơn\n \n(Invoice code)\n:\n \n{code}\n"
	"Tra cứu tại\n \n(Search on)\n:\n \nhttps://tinvoice.fast.com.vn:8000/\n"
)
EMPTY = {"code": "", "url": ""}


class TestParseLookupText(FrappeTestCase):
	def test_parses_the_text_pypdf_extracts_from_fast_pdfs(self):
		self.assertEqual(
			parse_lookup_text(REAL_TEXT.format(code="6D A83 217 253 61N 682")),
			{"code": "6D A83 217 253 61N 682", "url": "https://tinvoice.fast.com.vn:8000/"},
		)

	def test_parses_the_codes_of_the_other_real_pdfs(self):
		for code in ("6D AEA D1F 2JB 724 4FG", "6D A23 B1C 253 922 860"):
			self.assertEqual(parse_lookup_text(REAL_TEXT.format(code=code))["code"], code)

	def test_missing_labels_give_empty_values(self):
		self.assertEqual(parse_lookup_text("không có gì"), EMPTY)

	def test_no_text_gives_empty_values(self):
		self.assertEqual(parse_lookup_text(None), EMPTY)


class TestReadLookupFromPdf(FrappeTestCase):
	def test_reads_a_real_pdf(self):
		self.assertEqual(read_lookup_from_pdf(lookup_pdf_bytes()), {"code": LOOKUP_CODE, "url": LOOKUP_URL})

	def test_a_pdf_without_text_is_not_an_error(self):
		self.assertEqual(read_lookup_from_pdf(minimal_pdf_bytes()), EMPTY)

	def test_garbage_bytes_are_not_an_error(self):
		self.assertEqual(read_lookup_from_pdf(b"not a pdf"), EMPTY)

	def test_no_content_is_not_an_error(self):
		self.assertEqual(read_lookup_from_pdf(None), EMPTY)
