# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Số lưu hành — thực thể trung tâm, nguồn sự thật cho phân loại A/B/C/D.

Cho phép trạng thái "Đang đăng ký" với số lưu hành để trống: thực tế phải tạo
mã hàng để báo giá hoặc nhập hàng mẫu TRƯỚC khi Cục cấp số. Bắt buộc có số
thật ngay từ đầu sẽ chặn nghiệp vụ có thật.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.tbyt import constants

DOCTYPE = "TBYT Marketing Authorization"


def make_manufacturer(name="_Test TBYT Hang"):
	"""Site có 0 bản ghi Manufacturer nên mọi suite phải tự dựng."""
	if frappe.db.exists("Manufacturer", name):
		return name
	doc = frappe.new_doc("Manufacturer")
	doc.short_name = name
	doc.insert(ignore_permissions=True)
	return doc.name


def make_authorization(**kwargs):
	doc = frappe.new_doc(DOCTYPE)
	doc.so_luu_hanh = kwargs.get("so_luu_hanh", "_TEST-SLH-001")
	doc.loai_hinh = kwargs.get("loai_hinh", "Số công bố tiêu chuẩn")
	doc.phan_loai = kwargs.get("phan_loai", "B")
	doc.chu_so_huu = kwargs.get("chu_so_huu") or make_manufacturer()
	doc.miyano_la_chu_so_huu = kwargs.get("miyano_la_chu_so_huu", 0)
	doc.hang_nhap_khau = kwargs.get("hang_nhap_khau", 1)
	doc.trang_thai = kwargs.get("trang_thai", constants.AUTH_STATUS_VALID)
	doc.khong_thoi_han = kwargs.get("khong_thoi_han", 1)
	doc.ngay_cap = kwargs.get("ngay_cap", "2026-01-01")
	doc.ngay_het_han = kwargs.get("ngay_het_han")
	doc.insert(ignore_permissions=True)
	return doc


class TestTBYTMarketingAuthorization(FrappeTestCase):
	def test_document_name_uses_naming_series_not_the_number(self):
		"""Số lưu hành thật hay chứa dấu `/` sẽ hỏng routing URL nếu làm tên document."""
		doc = make_authorization(so_luu_hanh="220000123/PCBA-HN")
		self.assertTrue(doc.name.startswith("TBYT-LH-"))
		self.assertNotIn("/", doc.name)

	def test_pending_registration_needs_neither_number_nor_dates(self):
		doc = frappe.new_doc(DOCTYPE)
		doc.loai_hinh = "Số đăng ký lưu hành"
		doc.phan_loai = "C"
		doc.chu_so_huu = make_manufacturer()
		doc.trang_thai = constants.AUTH_STATUS_PENDING
		doc.insert(ignore_permissions=True)
		self.assertFalse(doc.so_luu_hanh)
		self.assertFalse(doc.ngay_cap)

	def test_issued_authorization_requires_issue_date(self):
		doc = frappe.new_doc(DOCTYPE)
		doc.so_luu_hanh = "_TEST-SLH-NO-DATE"
		doc.loai_hinh = "Số công bố tiêu chuẩn"
		doc.phan_loai = "A"
		doc.chu_so_huu = make_manufacturer()
		doc.trang_thai = constants.AUTH_STATUS_VALID
		doc.khong_thoi_han = 1
		with self.assertRaises(frappe.MandatoryError):
			doc.insert(ignore_permissions=True)

	def test_dated_authorization_requires_an_expiry_date(self):
		"""Không tích vô thời hạn thì phải có ngày — nếu không, trống mang hai nghĩa."""
		doc = frappe.new_doc(DOCTYPE)
		doc.so_luu_hanh = "_TEST-SLH-DATED"
		doc.loai_hinh = "Số đăng ký lưu hành"
		doc.phan_loai = "D"
		doc.chu_so_huu = make_manufacturer()
		doc.trang_thai = constants.AUTH_STATUS_VALID
		doc.khong_thoi_han = 0
		doc.ngay_cap = "2026-01-01"
		with self.assertRaises(frappe.MandatoryError):
			doc.insert(ignore_permissions=True)

	def test_indefinite_authorization_must_not_carry_an_expiry_date(self):
		doc = frappe.new_doc(DOCTYPE)
		doc.so_luu_hanh = "_TEST-SLH-CONTRADICT"
		doc.loai_hinh = "Số đăng ký lưu hành"
		doc.phan_loai = "C"
		doc.chu_so_huu = make_manufacturer()
		doc.trang_thai = constants.AUTH_STATUS_VALID
		doc.khong_thoi_han = 1
		doc.ngay_cap = "2026-01-01"
		doc.ngay_het_han = "2030-01-01"
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_expiry_date_cannot_precede_issue_date(self):
		doc = frappe.new_doc(DOCTYPE)
		doc.so_luu_hanh = "_TEST-SLH-BACKWARDS"
		doc.loai_hinh = "Số công bố tiêu chuẩn"
		doc.phan_loai = "B"
		doc.chu_so_huu = make_manufacturer()
		doc.trang_thai = constants.AUTH_STATUS_VALID
		doc.khong_thoi_han = 0
		doc.ngay_cap = "2026-06-01"
		doc.ngay_het_han = "2026-01-01"
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_condition_context_exposes_the_two_bb_star_switches(self):
		from erpnext.tbyt.doctype.tbyt_marketing_authorization.tbyt_marketing_authorization import (
			get_condition_context,
		)

		doc = make_authorization(
			so_luu_hanh="_TEST-SLH-CTX",
			miyano_la_chu_so_huu=0,
			hang_nhap_khau=1,
		)
		self.assertEqual(
			get_condition_context(doc.name),
			{"miyano_la_chu_so_huu": 0, "hang_nhap_khau": 1},
		)
