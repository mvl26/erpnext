# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Ba trạng thái hiệu lực phải tách bạch tuyệt đối.

Nếu `ngay_het_han` để trống mang cả hai nghĩa "vô thời hạn" và "chưa nhập" thì
job hết hạn hoặc báo động giả hàng loạt, hoặc im lặng bỏ sót giấy sắp hết hạn.
Cả hai đều phá hỏng mục tiêu chính của cả tính năng.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, today

from erpnext.tbyt import constants
from erpnext.tbyt.expiry import compute_document_status

DOCTYPE = "TBYT Regulatory Document"


def make_regulatory_document(document_type, scope_doctype, scope_name, **kwargs):
	"""File là Attach nên chỉ cần một chuỗi URL — không phải tạo File thật."""
	doc = frappe.new_doc(DOCTYPE)
	doc.document_type = document_type
	doc.append("pham_vi", {"scope_doctype": scope_doctype, "scope_name": scope_name})
	doc.so_hieu = kwargs.get("so_hieu", "_TEST-SH-001")
	doc.ngay_cap = kwargs.get("ngay_cap", "2026-01-01")
	doc.khong_thoi_han = kwargs.get("khong_thoi_han", 1)
	doc.ngay_het_han = kwargs.get("ngay_het_han")
	doc.file = kwargs.get("file", "/private/files/_test_tbyt.pdf")
	doc.is_active = kwargs.get("is_active", 1)
	doc.insert(ignore_permissions=True)
	return doc


class TestComputeDocumentStatus(FrappeTestCase):
	def test_indefinite_document_is_always_valid(self):
		self.assertEqual(
			compute_document_status(is_active=1, khong_thoi_han=1, ngay_het_han=None),
			constants.DOC_STATUS_VALID,
		)

	def test_document_far_from_expiry_is_valid(self):
		far = add_days(today(), constants.EXPIRY_WARNING_DAYS + 10)
		self.assertEqual(
			compute_document_status(is_active=1, khong_thoi_han=0, ngay_het_han=far),
			constants.DOC_STATUS_VALID,
		)

	def test_document_inside_the_warning_window_is_expiring(self):
		near = add_days(today(), constants.EXPIRY_WARNING_DAYS - 1)
		self.assertEqual(
			compute_document_status(is_active=1, khong_thoi_han=0, ngay_het_han=near),
			constants.DOC_STATUS_EXPIRING,
		)

	def test_document_past_its_date_is_expired(self):
		past = add_days(today(), -1)
		self.assertEqual(
			compute_document_status(is_active=1, khong_thoi_han=0, ngay_het_han=past),
			constants.DOC_STATUS_EXPIRED,
		)

	def test_expiring_on_the_boundary_day_still_counts_as_expiring(self):
		"""Đúng ngày hết hạn thì vẫn còn hiệu lực trong ngày đó, chỉ là sắp hết."""
		boundary = today()
		self.assertEqual(
			compute_document_status(is_active=1, khong_thoi_han=0, ngay_het_han=boundary),
			constants.DOC_STATUS_EXPIRING,
		)

	def test_inactive_document_is_superseded_regardless_of_dates(self):
		self.assertEqual(
			compute_document_status(is_active=0, khong_thoi_han=1, ngay_het_han=None),
			constants.DOC_STATUS_SUPERSEDED,
		)


class TestRegulatoryDocumentExpiry(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.tbyt.setup import setup_tbyt_masters

		setup_tbyt_masters()

	def setUp(self):
		from erpnext.tbyt.doctype.tbyt_marketing_authorization.test_tbyt_marketing_authorization import (
			make_authorization,
		)

		self.auth = make_authorization(so_luu_hanh=f"_TEST-SLH-EXP-{frappe.generate_hash(length=6)}")

	def test_dated_document_without_expiry_date_cannot_be_saved(self):
		"""Đây là ràng buộc gỡ bỏ hoàn toàn khoảng mờ giữa vô hạn và chưa nhập."""
		doc = frappe.new_doc(DOCTYPE)
		doc.document_type = "hdsd_tieng_viet"
		doc.append(
			"pham_vi",
			{"scope_doctype": "TBYT Marketing Authorization", "scope_name": self.auth.name},
		)
		doc.ngay_cap = "2026-01-01"
		doc.khong_thoi_han = 0
		doc.file = "/private/files/_test_tbyt.pdf"
		with self.assertRaises(frappe.MandatoryError):
			doc.insert(ignore_permissions=True)

	def test_indefinite_document_must_not_carry_an_expiry_date(self):
		doc = frappe.new_doc(DOCTYPE)
		doc.document_type = "hdsd_tieng_viet"
		doc.append(
			"pham_vi",
			{"scope_doctype": "TBYT Marketing Authorization", "scope_name": self.auth.name},
		)
		doc.ngay_cap = "2026-01-01"
		doc.khong_thoi_han = 1
		doc.ngay_het_han = "2030-01-01"
		doc.file = "/private/files/_test_tbyt.pdf"
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_status_is_computed_on_save(self):
		doc = make_regulatory_document(
			"hdsd_tieng_viet",
			"TBYT Marketing Authorization",
			self.auth.name,
			khong_thoi_han=0,
			ngay_het_han=add_days(today(), -5),
		)
		self.assertEqual(doc.trang_thai, constants.DOC_STATUS_EXPIRED)

	def test_scope_doctype_is_filled_from_the_document_type(self):
		"""Người dùng chỉ chọn đối tượng; cấp phạm vi suy ra từ loại chứng từ."""
		doc = frappe.new_doc(DOCTYPE)
		doc.document_type = "hdsd_tieng_viet"
		doc.append("pham_vi", {"scope_name": self.auth.name})
		doc.ngay_cap = "2026-01-01"
		doc.khong_thoi_han = 1
		doc.file = "/private/files/_test_tbyt.pdf"
		doc.insert(ignore_permissions=True)
		self.assertEqual(doc.pham_vi[0].scope_doctype, "TBYT Marketing Authorization")

	def test_scope_level_is_denormalised_for_filtering(self):
		doc = make_regulatory_document("hdsd_tieng_viet", "TBYT Marketing Authorization", self.auth.name)
		self.assertEqual(doc.scope_level, constants.SCOPE_AUTHORIZATION)

	def test_expiry_date_cannot_precede_issue_date(self):
		doc = frappe.new_doc(DOCTYPE)
		doc.document_type = "hdsd_tieng_viet"
		doc.append(
			"pham_vi",
			{"scope_doctype": "TBYT Marketing Authorization", "scope_name": self.auth.name},
		)
		doc.ngay_cap = "2026-06-01"
		doc.khong_thoi_han = 0
		doc.ngay_het_han = "2026-01-01"
		doc.file = "/private/files/_test_tbyt.pdf"
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)
