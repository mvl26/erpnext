# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Danh mục loại chứng từ — khuôn của bảng rule 23 x 4.

`mac_dinh_co_thoi_han` cố ý CHỈ là gợi ý: có hạn hay không là thuộc tính của
từng tờ giấy chứ không phải của loại (số lưu hành C/D nay nhiều giấy cấp vô
thời hạn, giấy cùng loại cấp trước đó vẫn có hạn). Quyền quyết định nằm ở
`khong_thoi_han` trên từng bản ghi chứng từ — xem Task 5.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.tbyt import constants

DOCTYPE = "TBYT Document Type"


def make_document_type(document_key, **kwargs):
	"""Get-or-create để suite chạy lại được sau khi seed thật đã có mặt."""
	if frappe.db.exists(DOCTYPE, document_key):
		return frappe.get_doc(DOCTYPE, document_key)
	doc = frappe.new_doc(DOCTYPE)
	doc.document_key = document_key
	doc.short_code = kwargs.get("short_code", "XX")
	doc.document_name = kwargs.get("document_name", "Chứng từ thử")
	doc.scope_level = kwargs.get("scope_level", constants.SCOPE_AUTHORIZATION)
	doc.cho_phep_nhieu_pham_vi = kwargs.get("cho_phep_nhieu_pham_vi", 0)
	doc.mac_dinh_co_thoi_han = kwargs.get("mac_dinh_co_thoi_han", 0)
	for device_class in kwargs.get("levels", {}):
		doc.append(
			"rules",
			{"device_class": device_class, "level": kwargs["levels"][device_class]},
		)
	doc.insert()
	return doc


class TestTBYTDocumentType(FrappeTestCase):
	def test_document_key_becomes_the_document_name(self):
		doc = make_document_type("_test_key_autoname")
		self.assertEqual(doc.name, "_test_key_autoname")

	def test_rules_hold_one_level_per_device_class(self):
		doc = make_document_type(
			"_test_key_rules",
			levels={"A": constants.LEVEL_BB, "B": constants.LEVEL_NC},
		)
		levels = {row.device_class: row.level for row in doc.rules}
		self.assertEqual(levels, {"A": constants.LEVEL_BB, "B": constants.LEVEL_NC})

	def test_duplicate_device_class_in_rules_is_rejected(self):
		"""Hai dòng cùng phân loại làm mức áp dụng thành nhập nhằng — chặn tại chỗ."""
		doc = frappe.new_doc(DOCTYPE)
		doc.document_key = "_test_key_dup_rule"
		doc.short_code = "XX"
		doc.document_name = "Chứng từ thử"
		doc.scope_level = constants.SCOPE_AUTHORIZATION
		doc.append("rules", {"device_class": "A", "level": constants.LEVEL_BB})
		doc.append("rules", {"device_class": "A", "level": constants.LEVEL_NC})
		with self.assertRaises(frappe.ValidationError):
			doc.insert()

	def test_condition_only_makes_sense_for_bb_star(self):
		"""Điều kiện gắn vào mức không phải BB* là dấu hiệu nhập sai — chặn."""
		doc = frappe.new_doc(DOCTYPE)
		doc.document_key = "_test_key_bad_condition"
		doc.short_code = "XX"
		doc.document_name = "Chứng từ thử"
		doc.scope_level = constants.SCOPE_AUTHORIZATION
		doc.append(
			"rules",
			{
				"device_class": "A",
				"level": constants.LEVEL_BB,
				"condition": "not miyano_la_chu_so_huu",
			},
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert()
