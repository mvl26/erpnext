# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Sổ đăng ký chứng từ pháp lý — một bản ghi là một tờ giấy có thật.

Chứng từ KHÔNG gắn vào Item. Nó gắn vào chủ thể mà nó nói về (công ty, chủ sở
hữu, số lưu hành, lô), và Item phân giải ngược chuỗi để dựng bộ hồ sơ của mình.
Nhờ vậy gia hạn một tờ CFS là sửa một bản ghi, không phải sửa 300 dòng.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate

from erpnext.tbyt.constants import SCOPE_DOCTYPE
from erpnext.tbyt.expiry import compute_document_status


class TBYTRegulatoryDocument(Document):
	def validate(self):
		self._fill_scope_doctype()
		self._validate_expiry_is_declared()
		self._validate_expiry_is_unambiguous()
		self._validate_date_order()
		self._set_status()

	def _validate_links(self):
		"""Frappe tự kiểm tra Dynamic Link ngay trong `insert()`/`_save()`, TRƯỚC khi
		gọi `validate()` — sớm hơn cả `before_insert`. Nếu chỉ điền `scope_doctype`
		trong `validate()` như bình thường thì bước kiểm tra sẵn có của khung sườn
		chạy trước, thấy `scope_doctype` còn trống ứng với `scope_name` đã có giá
		trị, và chặn lại với lỗi chung chung. Đón đầu ở đây để điền trước khi khung
		sườn tự kiểm tra.
		"""
		self._fill_scope_doctype()
		super()._validate_links()

	def _fill_scope_doctype(self):
		"""Người dùng chỉ chọn đối tượng; cấp phạm vi suy từ loại chứng từ."""
		scope_level = frappe.db.get_value("TBYT Document Type", self.document_type, "scope_level")
		expected = SCOPE_DOCTYPE.get(scope_level)
		if not expected:
			frappe.throw(
				_("Loại chứng từ {0} ở cấp {1} không gắn được vào bản ghi nào.").format(
					self.document_type, scope_level
				)
			)
		for row in self.pham_vi:
			row.scope_doctype = expected

	def _validate_expiry_is_declared(self):
		"""Nửa server của tri-state. `mandatory_depends_on` chỉ chặn ở trình duyệt.

		Không có hàm này thì tổ hợp "chưa tích Vô thời hạn mà bỏ trống ngày" vẫn lưu
		được qua import, API hay test — và đúng khoảng mờ mà tri-state sinh ra để xoá
		sẽ mở lại.
		"""
		if not cint(self.khong_thoi_han) and not self.ngay_het_han:
			frappe.throw(
				_("Chưa tích Vô thời hạn thì bắt buộc phải điền Ngày hết hạn."),
				frappe.MandatoryError,
			)

	def _validate_expiry_is_unambiguous(self):
		if cint(self.khong_thoi_han) and self.ngay_het_han:
			frappe.throw(_("Đã tích Vô thời hạn thì không được điền Ngày hết hạn. Bỏ một trong hai."))

	def _validate_date_order(self):
		if self.ngay_cap and self.ngay_het_han and getdate(self.ngay_het_han) < getdate(self.ngay_cap):
			frappe.throw(_("Ngày hết hạn không được trước Ngày cấp."))

	def _set_status(self):
		self.trang_thai = compute_document_status(
			is_active=self.is_active,
			khong_thoi_han=self.khong_thoi_han,
			ngay_het_han=self.ngay_het_han,
		)
