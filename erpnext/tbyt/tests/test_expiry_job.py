# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Job hằng ngày — và điều quan trọng nhất là những gì nó KHÔNG đụng tới.

Chứng từ vô thời hạn phải bị loại khỏi truy vấn ngay từ đầu. Nếu không, mỗi sáng
người dùng nhận một danh sách cảnh báo giả và sẽ nhanh chóng thôi đọc nó — lúc
đó giấy thật sắp hết hạn cũng chìm theo.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from erpnext.tbyt import constants
from erpnext.tbyt.doctype.tbyt_marketing_authorization.test_tbyt_marketing_authorization import (
	make_authorization,
)
from erpnext.tbyt.expiry import get_expiring_documents, update_document_status
from erpnext.tbyt.tests.test_expiry import make_regulatory_document
from erpnext.tbyt.tests.test_item_fields import make_item

AUTH_DOCTYPE = "TBYT Marketing Authorization"


class TestExpiryJob(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.tbyt.setup import setup_tbyt_masters

		setup_tbyt_masters()

	def setUp(self):
		self.suffix = frappe.generate_hash(length=6)
		self.auth = make_authorization(so_luu_hanh=f"_TEST-SLH-JOB-{self.suffix}")
		self.item = make_item(f"_TEST-TBYT-JOB-{self.suffix}", la_thiet_bi_y_te=1, so_luu_hanh=self.auth.name)

	def test_job_marks_a_lapsed_document_as_expired(self):
		doc = make_regulatory_document(
			"hdsd_tieng_viet",
			AUTH_DOCTYPE,
			self.auth.name,
			khong_thoi_han=0,
			ngay_het_han=add_days(today(), 5),
		)
		# Đẩy ngày về quá khứ mà không qua validate, mô phỏng thời gian trôi.
		frappe.db.set_value("TBYT Regulatory Document", doc.name, "ngay_het_han", add_days(today(), -1))
		update_document_status()
		self.assertEqual(
			frappe.db.get_value("TBYT Regulatory Document", doc.name, "trang_thai"),
			constants.DOC_STATUS_EXPIRED,
		)

	def test_job_never_touches_an_indefinite_document(self):
		doc = make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, self.auth.name)
		update_document_status()
		self.assertEqual(
			frappe.db.get_value("TBYT Regulatory Document", doc.name, "trang_thai"),
			constants.DOC_STATUS_VALID,
		)

	def test_indefinite_document_never_appears_in_the_warning_list(self):
		"""Giấy vô thời hạn không bao giờ lọt vào danh sách cảnh báo.

		Khẳng định trên `name` của chính bản ghi vừa tạo, không phải trên
		`document_type`: loại chứng từ là giá trị dùng chung, mà
		`get_expiring_documents()` truy vấn TOÀN CỤC. Kiểm theo loại thì rác của
		test khác — hoặc dữ liệu thật trên site — cũng làm khẳng định này đúng
		hoặc sai vì lý do chẳng liên quan gì tới điều nó tuyên bố.
		"""
		doc = make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, self.auth.name)
		names = {row["name"] for row in get_expiring_documents()}
		self.assertNotIn(doc.name, names)

	def test_document_inside_the_window_appears_in_the_warning_list(self):
		doc = make_regulatory_document(
			"tai_lieu_ky_thuat_bao_duong",
			AUTH_DOCTYPE,
			self.auth.name,
			khong_thoi_han=0,
			ngay_het_han=add_days(today(), 10),
		)
		names = {row["name"] for row in get_expiring_documents()}
		self.assertIn(doc.name, names)

	def test_job_lapses_an_authorization_whose_date_has_passed(self):
		auth = make_authorization(
			so_luu_hanh=f"_TEST-SLH-JOBEXP-{self.suffix}",
			khong_thoi_han=0,
			ngay_het_han=add_days(today(), 5),
		)
		frappe.db.set_value(AUTH_DOCTYPE, auth.name, "ngay_het_han", add_days(today(), -1))
		update_document_status()
		self.assertEqual(
			frappe.db.get_value(AUTH_DOCTYPE, auth.name, "trang_thai"),
			constants.AUTH_STATUS_EXPIRED,
		)

	def test_job_never_lapses_an_indefinite_authorization(self):
		update_document_status()
		self.assertEqual(
			frappe.db.get_value(AUTH_DOCTYPE, self.auth.name, "trang_thai"),
			constants.AUTH_STATUS_VALID,
		)

	def test_job_refreshes_item_status_as_a_safety_net(self):
		frappe.db.set_value("Item", self.item.name, "tinh_trang_ho_so", None)
		update_document_status()
		self.assertIsNotNone(frappe.db.get_value("Item", self.item.name, "tinh_trang_ho_so"))
