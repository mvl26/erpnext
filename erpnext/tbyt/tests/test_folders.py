# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Cây thư mục theo NƠI CẤP GIẤY, phân giải theo NƠI GIẤY PHỦ.

Một file chỉ nằm được ở một thư mục, nên chứng từ đa phạm vi (CFS, ủy quyền…)
về thư mục chủ sở hữu. Thư mục chỉ phục vụ người duyệt tay — việc xác định item
nào có chứng từ nào hoàn toàn do resolver quyết định, không đọc thư mục.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.einvoice.tests.test_fixtures import minimal_pdf_bytes
from erpnext.tbyt import constants
from erpnext.tbyt.doctype.tbyt_marketing_authorization.test_tbyt_marketing_authorization import (
	make_authorization,
)
from erpnext.tbyt.folders import build_file_name, ensure_folder, slugify

AUTH_DOCTYPE = "TBYT Marketing Authorization"


def attach_pdf(file_name="_test_tbyt.pdf"):
	"""Frappe parse PDF để dò JS nhúng, nên byte giả sẽ bị từ chối.

	Thêm một dòng chú thích PDF (bắt đầu bằng `%`, nằm sau `%%EOF` nên không đụng
	tới bảng xref) mang một mã ngẫu nhiên riêng cho mỗi lần gọi: nội dung PDF tối
	giản giống hệt nhau ở mọi lần gọi sẽ khiến `File.save_file` gộp theo
	`content_hash` và dùng chung một `file_url` — nhiều bản ghi kiểm thử tưởng
	khác tệp hoá ra trỏ vào cùng một đường dẫn vật lý.
	"""
	suffix = frappe.generate_hash(length=6)
	content = minimal_pdf_bytes() + f"%{suffix}\n".encode()
	doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"{suffix}_{file_name}",
			"content": content,
			"is_private": 1,
			"folder": "Home/Attachments",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc


class TestFolderNaming(FrappeTestCase):
	def test_slugify_strips_accents_and_slashes(self):
		self.assertEqual(slugify("220000123/PCBA-HN"), "220000123-PCBA-HN")
		self.assertEqual(slugify("Số hiệu lạ"), "So-hieu-la")

	def test_missing_number_becomes_khong_so(self):
		self.assertEqual(build_file_name("HDSD", None, "2026-02-03", "pdf"), "HDSD__khong-so__2026-02-03.pdf")

	def test_file_name_carries_code_number_and_date(self):
		self.assertEqual(
			build_file_name("CBTC", "220000123/PCBA-HN", "2026-02-03", "pdf"),
			"CBTC__220000123-PCBA-HN__2026-02-03.pdf",
		)


class TestFolderTree(FrappeTestCase):
	def test_root_folder_is_created_once(self):
		first = ensure_folder(constants.SCOPE_OWNER, "_Test TBYT Hang")
		second = ensure_folder(constants.SCOPE_OWNER, "_Test TBYT Hang")
		self.assertEqual(first, second)
		self.assertTrue(first.startswith("Home/TBYT/02-Chu-so-huu/"))

	def test_each_scope_level_has_its_own_numbered_branch(self):
		self.assertTrue(
			ensure_folder(constants.SCOPE_AUTHORIZATION, "_TEST-SLH-FOLDER").startswith(
				"Home/TBYT/03-So-luu-hanh/"
			)
		)
		self.assertTrue(
			ensure_folder(constants.SCOPE_ITEM, "_TEST-ITEM-FOLDER").startswith("Home/TBYT/05-Item/")
		)


class TestFilePlacement(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.tbyt.setup import setup_tbyt_masters

		setup_tbyt_masters()

	def setUp(self):
		self.suffix = frappe.generate_hash(length=6)
		self.auth = make_authorization(so_luu_hanh=f"_TEST-SLH-FLD-{self.suffix}")

	def _make_document(self, document_type, scope_names, **kwargs):
		attachment = attach_pdf()
		doc = frappe.new_doc("TBYT Regulatory Document")
		doc.document_type = document_type
		for scope_name in scope_names:
			doc.append("pham_vi", {"scope_name": scope_name})
		doc.so_hieu = kwargs.get("so_hieu", "SH-001")
		doc.ngay_cap = kwargs.get("ngay_cap", "2026-02-03")
		doc.khong_thoi_han = 1
		doc.file = attachment.file_url
		doc.insert(ignore_permissions=True)
		return doc

	def test_single_scope_file_lands_in_its_own_scope_folder(self):
		doc = self._make_document("hdsd_tieng_viet", [self.auth.name])
		folder = frappe.db.get_value("File", {"file_url": doc.file}, "folder")
		self.assertEqual(folder, f"Home/TBYT/03-So-luu-hanh/{slugify(self.auth.so_luu_hanh)}")

	def test_file_is_renamed_to_the_convention(self):
		doc = self._make_document("hdsd_tieng_viet", [self.auth.name], so_hieu="SH-XYZ")
		name = frappe.db.get_value("File", {"file_url": doc.file}, "file_name")
		self.assertEqual(name, "HDSD__SH-XYZ__2026-02-03.pdf")

	def test_multi_scope_file_lands_in_the_owner_folder(self):
		sibling = make_authorization(
			so_luu_hanh=f"_TEST-SLH-FLD2-{self.suffix}", chu_so_huu=self.auth.chu_so_huu
		)
		doc = self._make_document("cfs_giay_luu_hanh", [self.auth.name, sibling.name])
		folder = frappe.db.get_value("File", {"file_url": doc.file}, "folder")
		self.assertEqual(folder, f"Home/TBYT/02-Chu-so-huu/{slugify(self.auth.chu_so_huu)}")

	def test_superseded_file_moves_to_the_archive_subfolder(self):
		doc = self._make_document("hdsd_tieng_viet", [self.auth.name])
		doc.is_active = 0
		doc.save(ignore_permissions=True)
		folder = frappe.db.get_value("File", {"file_url": doc.file}, "folder")
		self.assertTrue(folder.endswith(f"/{constants.ARCHIVE_FOLDER_NAME}"), folder)

	def test_attachment_is_always_private(self):
		doc = self._make_document("hdsd_tieng_viet", [self.auth.name])
		self.assertEqual(frappe.db.get_value("File", {"file_url": doc.file}, "is_private"), 1)
