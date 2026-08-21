# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Số lưu hành là ràng buộc CỨNG duy nhất của cả tính năng.

Chứng từ thì thiếu tạm thời được — chúng phụ thuộc nhà cung cấp gửi. Nhưng số
lưu hành là điều kiện pháp lý để hàng được phép lưu thông: không có nó thì mã
hàng không có cơ sở tồn tại. Trường hợp chưa được Cục cấp số thì vẫn khai được
qua bản ghi trạng thái "Đang đăng ký".
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.tbyt.doctype.tbyt_marketing_authorization.test_tbyt_marketing_authorization import (
	make_authorization,
)

MEDICAL_GROUP = "_Test Nhom TBYT"


def make_item_group(name=MEDICAL_GROUP, la_tbyt=1):
	if frappe.db.exists("Item Group", name):
		doc = frappe.get_doc("Item Group", name)
		if doc.la_tbyt != la_tbyt:
			doc.la_tbyt = la_tbyt
			doc.save(ignore_permissions=True)
		return name
	doc = frappe.new_doc("Item Group")
	doc.item_group_name = name
	doc.parent_item_group = "All Item Groups"
	doc.is_group = 0
	doc.la_tbyt = la_tbyt
	doc.insert(ignore_permissions=True)
	return doc.name


def make_item(item_code, **kwargs):
	doc = frappe.new_doc("Item")
	doc.item_code = item_code
	doc.item_name = kwargs.get("item_name", item_code)
	doc.item_group = kwargs.get("item_group", make_item_group())
	doc.stock_uom = kwargs.get("stock_uom", "Nos")
	doc.is_stock_item = 0
	if "la_thiet_bi_y_te" in kwargs:
		doc.la_thiet_bi_y_te = kwargs["la_thiet_bi_y_te"]
	if "so_luu_hanh" in kwargs:
		doc.so_luu_hanh = kwargs["so_luu_hanh"]
	doc.insert(ignore_permissions=True)
	return doc


class TestItemTBYTFields(FrappeTestCase):
	def setUp(self):
		self.suffix = frappe.generate_hash(length=6)
		self.auth = make_authorization(so_luu_hanh=f"_TEST-SLH-ITEM-{self.suffix}", phan_loai="C")

	def test_medical_flag_defaults_from_the_item_group(self):
		item = make_item(f"_TEST-TBYT-DEFAULT-{self.suffix}", so_luu_hanh=self.auth.name)
		self.assertEqual(item.la_thiet_bi_y_te, 1)

	def test_non_medical_group_leaves_the_flag_off(self):
		group = make_item_group("_Test Nhom Thuong", la_tbyt=0)
		item = make_item(f"_TEST-TBYT-PLAIN-{self.suffix}", item_group=group)
		self.assertEqual(item.la_thiet_bi_y_te, 0)

	def test_medical_item_without_authorization_cannot_be_saved(self):
		doc = frappe.new_doc("Item")
		doc.item_code = f"_TEST-TBYT-NOAUTH-{self.suffix}"
		doc.item_name = doc.item_code
		doc.item_group = make_item_group()
		doc.stock_uom = "Nos"
		doc.is_stock_item = 0
		with self.assertRaises(frappe.MandatoryError):
			doc.insert(ignore_permissions=True)

	def test_device_class_is_fetched_from_the_authorization(self):
		"""Suy ra, không nhập tay — hai item cùng số lưu hành không thể khai lệch loại."""
		item = make_item(f"_TEST-TBYT-CLASS-{self.suffix}", so_luu_hanh=self.auth.name)
		self.assertEqual(item.phan_loai_tbyt, "C")

	def test_device_class_field_is_read_only(self):
		meta = frappe.get_meta("Item")
		self.assertEqual(meta.get_field("phan_loai_tbyt").read_only, 1)

	def test_authorization_is_only_mandatory_for_medical_items(self):
		group = make_item_group("_Test Nhom Thuong", la_tbyt=0)
		item = make_item(f"_TEST-TBYT-OPTIONAL-{self.suffix}", item_group=group)
		self.assertFalse(item.so_luu_hanh)

	def test_manual_override_of_the_medical_flag_survives_saving(self):
		"""Bỏ tích rồi lưu lại không được bị nhóm hàng ghi đè ngược."""
		group = make_item_group("_Test Nhom Thuong", la_tbyt=0)
		item = make_item(
			f"_TEST-TBYT-OVERRIDE-{self.suffix}",
			item_group=group,
			la_thiet_bi_y_te=1,
			so_luu_hanh=self.auth.name,
		)
		item.reload()
		item.item_name = "Doi ten"
		item.save(ignore_permissions=True)
		self.assertEqual(item.la_thiet_bi_y_te, 1)
