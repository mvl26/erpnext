# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Chữ và màu người dùng thấy trên form kiểm giá bán.

Mã yêu cầu (BA12, R01...R08, D08, YC4) là mã của tài liệu phân tích, người dùng không biết
nghĩa: không được lọt vào nhãn hay chú thích trường.
"""

import os
import re

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.selling.kiem_gia.truong_tuy_bien import CUSTOM_FIELDS

MA_YEU_CAU = re.compile(r"\b(BA\d+|R0\d|D0\d|Q\d+|YC\d+)\b")


class TestGiaoDienKiemGia(FrappeTestCase):
	def test_labels_and_descriptions_carry_no_requirement_codes(self):
		truong = [(dt, f) for dt, fields in CUSTOM_FIELDS.items() for f in fields]
		for dt in ("Customer Price Coefficient", "Customer Item Price Coefficient"):
			truong += [(dt, f.as_dict()) for f in frappe.get_meta(dt).fields]
		for dt, f in truong:
			for key in ("label", "description"):
				with self.subTest(doctype=dt, fieldname=f.get("fieldname"), key=key):
					self.assertNotRegex(f.get(key) or "", MA_YEU_CAU)

	def test_status_colors_are_wired_to_both_forms(self):
		# `doctype_js` trỏ file không tồn tại thì Frappe im lặng bỏ qua: ô Trạng thái giá mất màu.
		for dt in ("Quotation", "Sales Order"):
			gan = frappe.get_hooks("doctype_js", app_name="erpnext").get(dt) or []
			with self.subTest(doctype=dt):
				self.assertIn("public/js/kiem_gia/trang_thai_gia.js", gan)
				for path in gan:
					self.assertTrue(os.path.exists(frappe.get_app_path("erpnext", path)), path)
