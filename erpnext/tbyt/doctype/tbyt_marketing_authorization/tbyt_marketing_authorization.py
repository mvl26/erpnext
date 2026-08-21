# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Số lưu hành TBYT — thực thể trung tâm của hồ sơ pháp lý.

Ngành TBYT dán hồ sơ vào *số lưu hành*, không dán vào SKU: bơm tiêm
1ml/3ml/5ml/10ml là 4 Item nhưng chung một số công bố, một bản phân loại, một
HDSD. Mô hình hóa số lưu hành là cách duy nhất để một tờ giấy chỉ tồn tại một
lần mà mọi Item dưới nó vẫn tra được.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate

from erpnext.tbyt.constants import AUTH_STATUS_PENDING


class TBYTMarketingAuthorization(Document):
	def validate(self):
		self._validate_dates_required_unless_pending()
		self._validate_expiry_is_unambiguous()
		self._validate_date_order()

	def _validate_dates_required_unless_pending(self):
		"""`mandatory_depends_on` trên JSON chỉ có tác dụng ở trình duyệt (JS) —
		Frappe không tự áp nó khi lưu qua API/import, nên phải khóa lại ở server."""
		if self.trang_thai == AUTH_STATUS_PENDING:
			return
		if not self.ngay_cap:
			frappe.throw(
				_("Ngày cấp là bắt buộc khi Trạng thái không phải Đang đăng ký."), frappe.MandatoryError
			)
		if not cint(self.khong_thoi_han) and not self.ngay_het_han:
			frappe.throw(
				_(
					"Ngày hết hạn là bắt buộc khi Trạng thái không phải Đang đăng ký và chưa tích Vô thời hạn."
				),
				frappe.MandatoryError,
			)

	def _validate_expiry_is_unambiguous(self):
		"""Vô thời hạn và có ngày hết hạn là hai khẳng định trái nhau."""
		if cint(self.khong_thoi_han) and self.ngay_het_han:
			frappe.throw(_("Đã tích Vô thời hạn thì không được điền Ngày hết hạn. Bỏ một trong hai."))

	def _validate_date_order(self):
		if self.ngay_cap and self.ngay_het_han and getdate(self.ngay_het_han) < getdate(self.ngay_cap):
			frappe.throw(_("Ngày hết hạn không được trước Ngày cấp."))

	def is_usable(self) -> bool:
		"""Số lưu hành đang cho phép lưu thông hàng hóa hay không."""
		return self.trang_thai not in (AUTH_STATUS_PENDING,) and not self.is_lapsed()

	def is_lapsed(self) -> bool:
		from erpnext.tbyt.constants import AUTH_STATUS_EXPIRED, AUTH_STATUS_REVOKED

		return self.trang_thai in (AUTH_STATUS_EXPIRED, AUTH_STATUS_REVOKED)


def get_condition_context(authorization: str) -> dict:
	"""Bối cảnh để đánh giá điều kiện của nhóm BB*.

	Trả về đúng hai công tắc mà `TBYT Document Rule.condition` được phép đọc —
	giữ hẹp để biểu thức trong dữ liệu không với tới thứ gì khác.
	"""
	row = frappe.db.get_value(
		"TBYT Marketing Authorization",
		authorization,
		["miyano_la_chu_so_huu", "hang_nhap_khau"],
		as_dict=True,
	)
	if not row:
		return {"miyano_la_chu_so_huu": 0, "hang_nhap_khau": 0}
	return {
		"miyano_la_chu_so_huu": cint(row.miyano_la_chu_so_huu),
		"hang_nhap_khau": cint(row.hang_nhap_khau),
	}
