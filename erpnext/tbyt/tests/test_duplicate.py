# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Một tờ giấy tồn tại đúng một lần — ràng buộc cứng, không phải kỷ luật người dùng.

Không có lớp chặn này thì hai bản ghi CFS cùng hiệu lực cho một chủ sở hữu vẫn
lưu được, và resolver trở thành KHÔNG TẤT ĐỊNH: hai lần mở cùng một Item có thể
ra hai ngày hết hạn khác nhau tùy thứ tự DB trả về.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.tbyt.doctype.tbyt_marketing_authorization.test_tbyt_marketing_authorization import (
	make_authorization,
	make_manufacturer,
)
from erpnext.tbyt.tests.test_expiry import make_regulatory_document

AUTH_DOCTYPE = "TBYT Marketing Authorization"


class TestRegulatoryDocumentDuplicates(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.tbyt.setup import setup_tbyt_masters

		setup_tbyt_masters()

	def setUp(self):
		suffix = frappe.generate_hash(length=6)
		self.auth = make_authorization(so_luu_hanh=f"_TEST-SLH-DUP-{suffix}")
		self.other = make_authorization(so_luu_hanh=f"_TEST-SLH-DUP2-{suffix}")

	def test_second_active_document_for_the_same_scope_is_blocked(self):
		make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, self.auth.name)
		with self.assertRaises(frappe.ValidationError):
			make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, self.auth.name)

	def test_same_type_on_a_different_scope_is_fine(self):
		make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, self.auth.name)
		doc = make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, self.other.name)
		self.assertTrue(doc.name)

	def test_inactive_predecessor_does_not_block_a_renewal(self):
		old = make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, self.auth.name)
		old.is_active = 0
		old.save(ignore_permissions=True)
		new = make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, self.auth.name)
		self.assertTrue(new.name)

	def test_renewal_via_thay_the_cho_deactivates_the_predecessor(self):
		"""Gia hạn không cần thao tác tay hai bước — khai thay thế là đủ."""
		old = make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, self.auth.name)
		new = frappe.new_doc("TBYT Regulatory Document")
		new.document_type = "hdsd_tieng_viet"
		new.append("pham_vi", {"scope_name": self.auth.name})
		new.so_hieu = "_TEST-SH-RENEWED"
		new.ngay_cap = "2026-06-01"
		new.khong_thoi_han = 1
		new.file = "/private/files/_test_tbyt.pdf"
		new.thay_the_cho = old.name
		new.insert(ignore_permissions=True)

		old.reload()
		self.assertEqual(old.is_active, 0)
		self.assertEqual(old.trang_thai, "Đã thay thế")

	def test_one_document_may_cover_several_authorizations(self):
		"""Một CFS phủ nhiều số lưu hành = MỘT bản ghi, không nhân bản."""
		before = frappe.db.count("TBYT Regulatory Document")
		doc = frappe.new_doc("TBYT Regulatory Document")
		doc.document_type = "cfs_giay_luu_hanh"
		doc.append("pham_vi", {"scope_name": self.auth.name})
		doc.append("pham_vi", {"scope_name": self.other.name})
		doc.so_hieu = "_TEST-CFS-MULTI"
		doc.ngay_cap = "2026-01-01"
		doc.khong_thoi_han = 1
		doc.file = "/private/files/_test_tbyt.pdf"
		doc.insert(ignore_permissions=True)

		self.assertEqual(len(doc.pham_vi), 2)
		self.assertEqual(frappe.db.count("TBYT Regulatory Document"), before + 1)

	def test_single_scope_type_rejects_a_second_scope_row(self):
		doc = frappe.new_doc("TBYT Regulatory Document")
		doc.document_type = "hdsd_tieng_viet"
		doc.append("pham_vi", {"scope_name": self.auth.name})
		doc.append("pham_vi", {"scope_name": self.other.name})
		doc.so_hieu = "_TEST-SH-TOOMANY"
		doc.ngay_cap = "2026-01-01"
		doc.khong_thoi_han = 1
		doc.file = "/private/files/_test_tbyt.pdf"
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_the_same_scope_row_twice_is_rejected(self):
		doc = frappe.new_doc("TBYT Regulatory Document")
		doc.document_type = "cfs_giay_luu_hanh"
		doc.append("pham_vi", {"scope_name": self.auth.name})
		doc.append("pham_vi", {"scope_name": self.auth.name})
		doc.so_hieu = "_TEST-CFS-SELFDUP"
		doc.ngay_cap = "2026-01-01"
		doc.khong_thoi_han = 1
		doc.file = "/private/files/_test_tbyt.pdf"
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)

	def test_multi_scope_document_must_stay_within_one_owner(self):
		"""File chỉ nằm được một thư mục, nên phạm vi không được trải hai hãng."""
		foreign_owner = make_manufacturer("_Test TBYT Hang Khac")
		stranger = make_authorization(
			so_luu_hanh=f"_TEST-SLH-OTHEROWNER-{frappe.generate_hash(length=6)}",
			chu_so_huu=foreign_owner,
		)
		doc = frappe.new_doc("TBYT Regulatory Document")
		doc.document_type = "cfs_giay_luu_hanh"
		doc.append("pham_vi", {"scope_name": self.auth.name})
		doc.append("pham_vi", {"scope_name": stranger.name})
		doc.so_hieu = "_TEST-CFS-CROSSOWNER"
		doc.ngay_cap = "2026-01-01"
		doc.khong_thoi_han = 1
		doc.file = "/private/files/_test_tbyt.pdf"
		with self.assertRaises(frappe.ValidationError):
			doc.insert(ignore_permissions=True)
