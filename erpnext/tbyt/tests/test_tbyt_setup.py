# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Bộ danh mục 23 loại chứng từ phải khớp ma trận Thông tư, chạy lại không nhân đôi.

`hop_chuan_hop_quy` là bẫy đã được ghi rõ trong đặc tả: NC ở A/B nhưng TH ở C/D.
Copy danh sách A sang C là sai — nên nó có test riêng.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.tbyt import constants
from erpnext.tbyt.setup import CONDITIONS, DOCUMENT_TYPES, setup_tbyt_masters

DOCTYPE = "TBYT Document Type"


class TestTBYTSetup(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_tbyt_masters()

	def test_all_twenty_three_document_types_exist(self):
		self.assertEqual(len(DOCUMENT_TYPES), 23)
		for spec in DOCUMENT_TYPES:
			self.assertTrue(
				frappe.db.exists(DOCTYPE, spec["document_key"]),
				f"Thiếu loại chứng từ: {spec['document_key']}",
			)

	def test_every_type_declares_all_four_device_classes(self):
		"""23 x 4 = 92 dòng quy tắc, không thiếu phân loại nào."""
		total = 0
		for spec in DOCUMENT_TYPES:
			doc = frappe.get_doc(DOCTYPE, spec["document_key"])
			classes = sorted(row.device_class for row in doc.rules)
			self.assertEqual(classes, list(constants.DEVICE_CLASSES), spec["document_key"])
			total += len(doc.rules)
		self.assertEqual(total, 92)

	def test_hop_chuan_hop_quy_flips_level_between_ab_and_cd(self):
		"""Bẫy đã biết: NC ở A/B, TH ở C/D. Copy nhầm danh sách A sang C là sai."""
		doc = frappe.get_doc(DOCTYPE, "hop_chuan_hop_quy")
		levels = {row.device_class: row.level for row in doc.rules}
		self.assertEqual(levels["A"], constants.LEVEL_NC)
		self.assertEqual(levels["B"], constants.LEVEL_NC)
		self.assertEqual(levels["C"], constants.LEVEL_TH)
		self.assertEqual(levels["D"], constants.LEVEL_TH)

	def test_cong_bo_dk_mua_ban_does_not_apply_to_class_a(self):
		doc = frappe.get_doc(DOCTYPE, "cong_bo_dk_mua_ban")
		levels = {row.device_class: row.level for row in doc.rules}
		self.assertEqual(levels["A"], constants.LEVEL_NA)
		self.assertEqual(levels["B"], constants.LEVEL_BB)

	def test_scope_level_distribution_matches_the_spec(self):
		"""1 Công ty + 2 Chủ sở hữu + 14 Số lưu hành + 3 Lô + 2 Item + 1 Giao dịch = 23."""
		counts = {}
		for spec in DOCUMENT_TYPES:
			counts[spec["scope_level"]] = counts.get(spec["scope_level"], 0) + 1
		self.assertEqual(
			counts,
			{
				constants.SCOPE_COMPANY: 1,
				constants.SCOPE_OWNER: 2,
				constants.SCOPE_AUTHORIZATION: 14,
				constants.SCOPE_BATCH: 3,
				constants.SCOPE_ITEM: 2,
				constants.SCOPE_TRANSACTION: 1,
			},
		)

	def test_exactly_four_types_allow_multiple_scopes(self):
		"""Bốn chứng từ do chủ sở hữu cấp nhưng liệt kê theo sản phẩm."""
		multi = {s["document_key"] for s in DOCUMENT_TYPES if s["cho_phep_nhieu_pham_vi"]}
		self.assertEqual(
			multi,
			{
				"cfs_giay_luu_hanh",
				"giay_uy_quyen_csh",
				"giay_xac_nhan_bao_hanh",
				"uy_quyen_nhap_khau",
			},
		)

	def test_conditions_are_attached_only_to_bb_star_rows(self):
		for key in CONDITIONS:
			doc = frappe.get_doc(DOCTYPE, key)
			for row in doc.rules:
				if row.level == constants.LEVEL_BB_STAR:
					self.assertEqual(row.condition, CONDITIONS[key], key)
				else:
					self.assertFalse(row.condition, key)

	def test_running_setup_twice_does_not_duplicate(self):
		setup_tbyt_masters()
		self.assertEqual(frappe.db.count(DOCTYPE), 23)
		self.assertEqual(
			frappe.db.count("TBYT Document Rule", {"parenttype": DOCTYPE}),
			92,
		)
