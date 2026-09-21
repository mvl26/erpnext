# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Phân giải ngược chuỗi Item → Số lưu hành → Chủ sở hữu → Công ty.

Không sao chép dòng nào: một tờ giấy nằm ở đúng cấp của nó, và mọi Item dưới
cấp đó tự thừa hưởng. Ca then chốt là `test_second_item_inherits_...`: thêm
mặt hàng thứ hai vào cùng số lưu hành thì số bản ghi chứng từ KHÔNG tăng.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.tbyt import constants
from erpnext.tbyt.doctype.tbyt_marketing_authorization.test_tbyt_marketing_authorization import (
	make_authorization,
)
from erpnext.tbyt.resolver import find_items_for_scope, get_item_documents
from erpnext.tbyt.tests.test_expiry import make_regulatory_document
from erpnext.tbyt.tests.test_item_fields import make_item

AUTH_DOCTYPE = "TBYT Marketing Authorization"


def levels_by_key(rows):
	return {row["document_key"]: row["level"] for row in rows}


def required_missing(rows):
	return {row["document_key"] for row in rows if row["is_required"] and not row["document"]}


class TestResolver(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.tbyt.setup import setup_tbyt_masters

		setup_tbyt_masters()

	def setUp(self):
		self.suffix = frappe.generate_hash(length=6)

	def _item_of_class(self, device_class, **auth_kwargs):
		auth = make_authorization(
			so_luu_hanh=f"_TEST-SLH-RES-{device_class}-{self.suffix}",
			phan_loai=device_class,
			**auth_kwargs,
		)
		item = make_item(
			f"_TEST-TBYT-RES-{device_class}-{self.suffix}",
			la_thiet_bi_y_te=1,
			so_luu_hanh=auth.name,
		)
		return item, auth

	def test_class_a_excludes_registration_certificate(self):
		"""Loại A dùng số công bố, không có giấy đăng ký lưu hành."""
		item, _ = self._item_of_class("A")
		keys = levels_by_key(get_item_documents(item.name))
		self.assertIn("so_cong_bo_tieu_chuan", keys)
		self.assertNotIn("gcn_dang_ky_luu_hanh", keys)

	def test_class_c_excludes_standard_declaration(self):
		item, _ = self._item_of_class("C")
		keys = levels_by_key(get_item_documents(item.name))
		self.assertIn("gcn_dang_ky_luu_hanh", keys)
		self.assertNotIn("so_cong_bo_tieu_chuan", keys)

	def test_class_a_excludes_the_trading_eligibility_notice(self):
		item, _ = self._item_of_class("A")
		self.assertNotIn("cong_bo_dk_mua_ban", levels_by_key(get_item_documents(item.name)))

	def test_class_b_includes_the_trading_eligibility_notice(self):
		item, _ = self._item_of_class("B")
		self.assertIn("cong_bo_dk_mua_ban", levels_by_key(get_item_documents(item.name)))

	def test_hop_chuan_hop_quy_flips_level_between_ab_and_cd(self):
		"""Bẫy lật mức: `hop_chuan_hop_quy` là NC ở A/B nhưng TH ở C/D.

		Đây là loại chứng từ DUY NHẤT trong 23 loại có mức đổi giữa các phân loại.
		Nếu ai đó chép danh sách của A sang C khi sửa danh mục thì mọi loại khác vẫn
		đúng, chỉ dòng này sai — nên nó đáng có một test riêng.

		Khẳng định trên chính giá trị mức, không phải trên việc dòng có hiện hay
		không. Bản cũ suy mức từ sự hiện diện, mà cách suy đó chỉ đúng khi dòng TH
		chưa có giấy bị ẩn đi. Giờ TH luôn hiện để người dùng có chỗ nộp, nên phép
		suy gián tiếp ấy không còn phân biệt được NC với TH nữa.
		"""
		item_b, _ = self._item_of_class("B")
		item_d, _ = self._item_of_class("D")
		self.assertEqual(levels_by_key(get_item_documents(item_b.name))["hop_chuan_hop_quy"], "NC")
		self.assertEqual(levels_by_key(get_item_documents(item_d.name))["hop_chuan_hop_quy"], "TH")

	def test_batch_level_documents_are_not_resolved_at_item_level(self):
		item, _ = self._item_of_class("B")
		keys = levels_by_key(get_item_documents(item.name))
		for key in ("cq_chung_nhan_chat_luong", "co_chung_nhan_xuat_xu"):
			self.assertNotIn(key, keys)

	def test_transaction_level_documents_are_out_of_scope(self):
		item, _ = self._item_of_class("B")
		self.assertNotIn("ho_so_phan_phoi", levels_by_key(get_item_documents(item.name)))

	def test_bb_star_is_required_when_miyano_is_not_the_owner(self):
		item, _ = self._item_of_class("B", miyano_la_chu_so_huu=0, hang_nhap_khau=1)
		self.assertIn("giay_uy_quyen_csh", required_missing(get_item_documents(item.name)))

	def test_bb_star_is_not_required_when_miyano_owns_the_authorization(self):
		item, _ = self._item_of_class("B", miyano_la_chu_so_huu=1, hang_nhap_khau=0)
		self.assertNotIn("giay_uy_quyen_csh", required_missing(get_item_documents(item.name)))

	def test_cfs_needs_both_switches(self):
		"""Hàng sản xuất trong nước không có CFS, dù Miyano không phải chủ sở hữu."""
		domestic, _ = self._item_of_class("A", miyano_la_chu_so_huu=0, hang_nhap_khau=0)
		self.assertNotIn("cfs_giay_luu_hanh", required_missing(get_item_documents(domestic.name)))

	def test_th_document_shows_up_even_when_absent(self):
		"""TH hiện ra kể cả khi chưa có giấy — để người dùng có chỗ nộp khi phát sinh.

		Trước đây resolver bỏ hẳn dòng TH chưa có giấy. Hệ quả là không có đường nào
		nộp chứng từ theo trường hợp từ mặt hàng. Giờ dòng vẫn hiện, nhưng
		`is_required` vẫn False nên nó KHÔNG được tính là thiếu ở bất cứ đâu.
		"""
		item, _ = self._item_of_class("B")
		rows = {r["document_key"]: r for r in get_item_documents(item.name)}
		self.assertIn("ke_khai_gia", rows)
		self.assertFalse(rows["ke_khai_gia"]["document"])
		self.assertFalse(rows["ke_khai_gia"]["is_required"])
		self.assertTrue(rows["ke_khai_gia"]["is_supplementary"])

	def test_th_document_shows_up_once_uploaded(self):
		"""Tải lên rồi thì phải thấy và phải theo dõi hạn — không được nuốt mất."""
		item, _ = self._item_of_class("B")
		make_regulatory_document("ke_khai_gia", "Item", item.name)
		rows = {r["document_key"]: r for r in get_item_documents(item.name)}
		self.assertIn("ke_khai_gia", rows)
		self.assertTrue(rows["ke_khai_gia"]["is_supplementary"])
		self.assertFalse(rows["ke_khai_gia"]["is_required"])

	def test_authorization_level_document_is_found(self):
		item, auth = self._item_of_class("B")
		doc = make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, auth.name)
		rows = {r["document_key"]: r for r in get_item_documents(item.name)}
		self.assertEqual(rows["hdsd_tieng_viet"]["document"], doc.name)

	def test_owner_level_document_is_found(self):
		item, auth = self._item_of_class("B")
		doc = make_regulatory_document("thong_tin_bao_hanh", "Manufacturer", auth.chu_so_huu)
		rows = {r["document_key"]: r for r in get_item_documents(item.name)}
		self.assertEqual(rows["thong_tin_bao_hanh"]["document"], doc.name)

	def test_inactive_document_does_not_count(self):
		item, auth = self._item_of_class("B")
		doc = make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, auth.name)
		doc.is_active = 0
		doc.save(ignore_permissions=True)
		self.assertIn("hdsd_tieng_viet", required_missing(get_item_documents(item.name)))

	def test_second_item_inherits_without_creating_any_new_record(self):
		"""Ca then chốt của toàn bộ thiết kế: thừa hưởng chứ không nhân bản."""
		item, auth = self._item_of_class("C")
		make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, auth.name)
		before = frappe.db.count("TBYT Regulatory Document")

		sibling = make_item(f"_TEST-TBYT-SIBLING-{self.suffix}", la_thiet_bi_y_te=1, so_luu_hanh=auth.name)
		rows = {r["document_key"]: r for r in get_item_documents(sibling.name)}

		self.assertTrue(rows["hdsd_tieng_viet"]["document"])
		self.assertEqual(frappe.db.count("TBYT Regulatory Document"), before)

	def test_one_cfs_covers_every_authorization_it_lists(self):
		item_a, auth_a = self._item_of_class("C", miyano_la_chu_so_huu=0, hang_nhap_khau=1)
		auth_b = make_authorization(
			so_luu_hanh=f"_TEST-SLH-RES-COVER-{self.suffix}",
			phan_loai="C",
			chu_so_huu=auth_a.chu_so_huu,
			miyano_la_chu_so_huu=0,
			hang_nhap_khau=1,
		)
		item_b = make_item(f"_TEST-TBYT-COVER-{self.suffix}", la_thiet_bi_y_te=1, so_luu_hanh=auth_b.name)

		cfs = frappe.new_doc("TBYT Regulatory Document")
		cfs.document_type = "cfs_giay_luu_hanh"
		cfs.append("pham_vi", {"scope_name": auth_a.name})
		cfs.append("pham_vi", {"scope_name": auth_b.name})
		cfs.so_hieu = "_TEST-CFS-COVER"
		cfs.ngay_cap = "2026-01-01"
		cfs.khong_thoi_han = 1
		cfs.file = "/private/files/_test_tbyt.pdf"
		cfs.insert(ignore_permissions=True)

		for item in (item_a, item_b):
			rows = {r["document_key"]: r for r in get_item_documents(item.name)}
			self.assertEqual(rows["cfs_giay_luu_hanh"]["document"], cfs.name, item.name)

	def test_non_medical_item_resolves_to_nothing(self):
		from erpnext.tbyt.tests.test_item_fields import make_item_group

		group = make_item_group("_Test Nhom Thuong", la_tbyt=0)
		item = make_item(f"_TEST-TBYT-NONMED-{self.suffix}", item_group=group)
		self.assertEqual(get_item_documents(item.name), [])

	def test_find_items_for_scope_walks_back_from_an_authorization(self):
		item, auth = self._item_of_class("B")
		self.assertIn(item.name, find_items_for_scope(AUTH_DOCTYPE, auth.name))

	def test_find_items_for_scope_walks_back_from_an_owner(self):
		item, auth = self._item_of_class("B")
		self.assertIn(item.name, find_items_for_scope("Manufacturer", auth.chu_so_huu))
