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

from erpnext.tbyt.constants import AUTH_STATUS_PENDING, LOAI_HINH_BY_CLASS
from erpnext.tbyt.refresh import refresh_for_authorization


class TBYTMarketingAuthorization(Document):
	def validate(self):
		self._derive_loai_hinh()
		self._validate_dates_required_unless_pending()
		self._validate_expiry_is_unambiguous()
		self._validate_date_order()

	def on_update(self):
		refresh_for_authorization(self)

	def _derive_loai_hinh(self):
		"""`loai_hinh` không phải lựa chọn độc lập — nó suy trực tiếp từ `phan_loai`
		theo Nghị định 98/2021 (A/B công bố tiêu chuẩn, C/D đăng ký lưu hành).

		`read_only` trong JSON chỉ là trang trí phía trình duyệt — Data Import,
		API hay `bench console` đều với qua được. Ghi đè im lặng ở đây mới là
		ràng buộc thật, và không throw vì giá trị sai chỉ có thể đến từ những
		đường vòng đó, và sửa lại đúng chính là hành vi mong muốn.
		"""
		if self.phan_loai in LOAI_HINH_BY_CLASS:
			self.loai_hinh = LOAI_HINH_BY_CLASS[self.phan_loai]

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


@frappe.whitelist()
def get_authorization_documents(authorization: str) -> list[dict]:
	"""Các chứng từ đang gắn vào số lưu hành này, cho bảng trên form."""
	frappe.has_permission("TBYT Marketing Authorization", doc=authorization, throw=True)
	return frappe.db.sql(
		"""
		select rd.name, rd.document_type, rd.so_hieu, rd.ngay_het_han,
			rd.khong_thoi_han, rd.trang_thai
		from `tabTBYT Regulatory Document` rd
		inner join `tabTBYT Document Scope` sc on sc.parent = rd.name
		where rd.is_active = 1
			and sc.parenttype = 'TBYT Regulatory Document'
			and sc.scope_doctype = 'TBYT Marketing Authorization'
			and sc.scope_name = %(authorization)s
		order by rd.document_type
		""",
		{"authorization": authorization},
		as_dict=True,
	)
