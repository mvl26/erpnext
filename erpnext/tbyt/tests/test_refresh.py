# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Chứng từ đổi thì trạng thái Item đổi NGAY, không chờ job nửa đêm."""

import frappe
from frappe.tests.utils import FrappeTestCase

import erpnext
from erpnext.tbyt import constants
from erpnext.tbyt.doctype.tbyt_marketing_authorization.test_tbyt_marketing_authorization import (
	make_authorization,
	make_manufacturer,
)
from erpnext.tbyt.tests.test_expiry import make_regulatory_document
from erpnext.tbyt.tests.test_item_fields import make_item
from erpnext.tbyt.tests.test_status import upload_everything_required

AUTH_DOCTYPE = "TBYT Marketing Authorization"


def _upload_everything_required_except_owner_level(item, auth):
	"""Như `upload_everything_required`, nhưng cố ý bỏ qua cấp Chủ sở hữu.

	Cần cho phép chứng minh riêng một chỗ còn thiếu — tờ giấy cấp chủ sở hữu —
	để phần còn lại của hồ sơ đã đủ từ trước, và cú tải cuối cùng chỉ đóng góp
	đúng một chứng từ nhưng chạm nhiều Item.
	"""
	from erpnext.tbyt.resolver import get_item_documents

	scope_map = {
		constants.SCOPE_COMPANY: ("Company", erpnext.get_default_company()),
		constants.SCOPE_AUTHORIZATION: (AUTH_DOCTYPE, auth.name),
		constants.SCOPE_ITEM: ("Item", item.name),
	}
	for row in get_item_documents(item.name):
		if not row["is_required"] or row["document"] or row["scope_level"] == constants.SCOPE_OWNER:
			continue
		scope_doctype, scope_name = scope_map[row["scope_level"]]
		make_regulatory_document(row["document_key"], scope_doctype, scope_name)


class TestRefresh(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.tbyt.setup import setup_tbyt_masters

		setup_tbyt_masters()

	def setUp(self):
		self.suffix = frappe.generate_hash(length=6)
		# Chủ sở hữu riêng cho từng test: FrappeTestCase KHÔNG rollback giữa các
		# test method trong cùng một class, chỉ rollback một lần ở cuối class.
		# Dùng chung chủ sở hữu mặc định sẽ làm chứng từ cấp chủ sở hữu của một
		# test rò sang test chạy sau, khiến tiền đề "còn thiếu" của test đó sai.
		self.manufacturer = make_manufacturer(f"_Test TBYT Hang RF-{self.suffix}")
		self.auth = make_authorization(
			so_luu_hanh=f"_TEST-SLH-RF-{self.suffix}", phan_loai="A", chu_so_huu=self.manufacturer
		)
		self.item = make_item(f"_TEST-TBYT-RF-{self.suffix}", la_thiet_bi_y_te=1, so_luu_hanh=self.auth.name)

	def _status(self, item=None):
		return frappe.db.get_value("Item", (item or self.item).name, "tinh_trang_ho_so")

	def test_owner_level_upload_refreshes_every_item_of_that_owner(self):
		"""Một tờ giấy cấp chủ sở hữu chạm rất nhiều mặt hàng — phải quét hết, không
		chỉ cái đang được nhìn tới."""
		sibling_auth = make_authorization(
			so_luu_hanh=f"_TEST-SLH-RF2-{self.suffix}",
			phan_loai="A",
			chu_so_huu=self.auth.chu_so_huu,
		)
		sibling = make_item(
			f"_TEST-TBYT-RF2-{self.suffix}", la_thiet_bi_y_te=1, so_luu_hanh=sibling_auth.name
		)

		# Đủ hồ sơ ở mọi cấp khác, chỉ còn thiếu đúng một tờ cấp chủ sở hữu —
		# và cả hai Item cùng thiếu đúng tờ đó vì chung một chủ sở hữu.
		_upload_everything_required_except_owner_level(self.item, self.auth)
		_upload_everything_required_except_owner_level(sibling, sibling_auth)
		for item in (self.item, sibling):
			self.assertEqual(self._status(item), constants.ITEM_STATUS_MISSING)

		make_regulatory_document("thong_tin_bao_hanh", "Manufacturer", self.auth.chu_so_huu)

		# Một lần tải, cả hai Item cùng chuyển sang Đủ — đúng tuyên bố của task.
		for item in (self.item, sibling):
			self.assertEqual(self._status(item), constants.ITEM_STATUS_OK)

	def test_uploading_the_last_missing_document_flips_the_item_to_complete(self):
		from erpnext.tbyt.resolver import get_item_documents

		scope_map = {
			constants.SCOPE_COMPANY: ("Company", erpnext.get_default_company()),
			constants.SCOPE_OWNER: ("Manufacturer", self.auth.chu_so_huu),
			constants.SCOPE_AUTHORIZATION: (AUTH_DOCTYPE, self.auth.name),
			constants.SCOPE_ITEM: ("Item", self.item.name),
		}
		for row in get_item_documents(self.item.name):
			if row["is_required"] and not row["document"]:
				scope_doctype, scope_name = scope_map[row["scope_level"]]
				make_regulatory_document(row["document_key"], scope_doctype, scope_name)

		self.assertEqual(self._status(), constants.ITEM_STATUS_OK)

	def test_deactivating_a_document_flips_the_item_back_to_missing(self):
		upload_everything_required(self.item, self.auth)
		self.assertEqual(self._status(), constants.ITEM_STATUS_OK)

		doc_name = frappe.db.get_value(
			"TBYT Regulatory Document", {"document_type": "hdsd_tieng_viet"}, "name"
		)
		doc = frappe.get_doc("TBYT Regulatory Document", doc_name)
		doc.is_active = 0
		doc.save(ignore_permissions=True)
		self.assertEqual(self._status(), constants.ITEM_STATUS_MISSING)

	def test_revoking_the_authorization_refreshes_its_items(self):
		auth = frappe.get_doc(AUTH_DOCTYPE, self.auth.name)
		auth.trang_thai = constants.AUTH_STATUS_REVOKED
		auth.save(ignore_permissions=True)
		self.assertEqual(self._status(), constants.ITEM_STATUS_AUTH_INVALID)

	def test_deleting_a_document_refreshes_the_items_it_covered(self):
		upload_everything_required(self.item, self.auth)
		self.assertEqual(self._status(), constants.ITEM_STATUS_OK)

		doc_name = frappe.db.get_value(
			"TBYT Regulatory Document", {"document_type": "hdsd_tieng_viet"}, "name"
		)
		frappe.delete_doc("TBYT Regulatory Document", doc_name, force=1, ignore_permissions=True)
		self.assertEqual(self._status(), constants.ITEM_STATUS_MISSING)
