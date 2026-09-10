# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tính trạng thái hiệu lực của một chứng từ.

Hàm thuần, không chạm DB — để test được mọi mốc thời gian mà không phải dựng
bản ghi. Job hằng ngày (Task 12) dùng lại chính hàm này, nên trạng thái lúc lưu
và trạng thái do job đặt không bao giờ lệch nhau.
"""

import frappe
from frappe.utils import add_days, cint, getdate

from erpnext.tbyt.constants import (
	DOC_STATUS_EXPIRED,
	DOC_STATUS_EXPIRING,
	DOC_STATUS_SUPERSEDED,
	DOC_STATUS_VALID,
	EXPIRY_WARNING_DAYS,
)


def compute_document_status(is_active, khong_thoi_han, ngay_het_han, today=None) -> str:
	"""Trả về một trong bốn giá trị DOC_STATUS_*.

	`today` để test bơm ngày cố định; bỏ trống thì lấy ngày hệ thống.
	"""
	if not cint(is_active):
		return DOC_STATUS_SUPERSEDED

	# Vô thời hạn: thoát sớm, không bao giờ so ngày. Đây là nhánh giữ cho giấy
	# cấp vô thời hạn khỏi bị job réo hằng ngày.
	if cint(khong_thoi_han):
		return DOC_STATUS_VALID

	if not ngay_het_han:
		# Không lưu được trạng thái này qua form, nhưng dữ liệu cũ có thể lọt.
		return DOC_STATUS_VALID

	reference = getdate(today)
	expiry = getdate(ngay_het_han)

	if expiry < reference:
		return DOC_STATUS_EXPIRED
	if expiry <= getdate(add_days(reference, EXPIRY_WARNING_DAYS - 1)):
		return DOC_STATUS_EXPIRING
	return DOC_STATUS_VALID


def update_document_status() -> dict:
	"""Job hằng ngày: đồng bộ trạng thái hiệu lực và trạng thái hồ sơ Item.

	Bản ghi vô thời hạn bị loại khỏi truy vấn NGAY TỪ ĐẦU — không đọc lên rồi
	mới bỏ qua. Đây là lý do cảnh báo hằng ngày giữ được uy tín.
	"""
	from erpnext.tbyt.constants import AUTH_STATUS_EXPIRED, AUTH_STATUS_VALID
	from erpnext.tbyt.refresh import refresh_items

	documents = 0
	for row in frappe.get_all(
		"TBYT Regulatory Document",
		filters={"is_active": 1, "khong_thoi_han": 0, "ngay_het_han": ("is", "set")},
		fields=["name", "is_active", "khong_thoi_han", "ngay_het_han", "trang_thai"],
	):
		wanted = compute_document_status(
			is_active=row.is_active,
			khong_thoi_han=row.khong_thoi_han,
			ngay_het_han=row.ngay_het_han,
		)
		if wanted != row.trang_thai:
			frappe.db.set_value(
				"TBYT Regulatory Document", row.name, "trang_thai", wanted, update_modified=False
			)
			documents += 1

	authorizations = 0
	lapsed = frappe.get_all(
		"TBYT Marketing Authorization",
		filters={
			"trang_thai": AUTH_STATUS_VALID,
			"khong_thoi_han": 0,
			"ngay_het_han": ("<", getdate()),
		},
		pluck="name",
	)
	for name in lapsed:
		frappe.db.set_value(
			"TBYT Marketing Authorization",
			name,
			"trang_thai",
			AUTH_STATUS_EXPIRED,
			update_modified=False,
		)
		authorizations += 1

	# Lưới an toàn cho việc làm mới tức thời (Task 11): nếu một job nền chết
	# giữa chừng thì đêm nay hệ thống tự sửa lại.
	items = frappe.get_all("Item", filters={"la_thiet_bi_y_te": 1}, pluck="name")
	refresh_items(items)

	return {"documents": documents, "authorizations": authorizations, "items": len(items)}


def get_expiring_documents(days=None) -> list[dict]:
	"""Chứng từ sắp hết hạn trong `days` ngày tới. Vô thời hạn không bao giờ lọt vào."""
	window = EXPIRY_WARNING_DAYS if days is None else days
	return frappe.get_all(
		"TBYT Regulatory Document",
		filters={
			"is_active": 1,
			"khong_thoi_han": 0,
			"ngay_het_han": ("between", [getdate(), add_days(getdate(), window)]),
		},
		fields=["name", "document_type", "so_hieu", "ngay_het_han", "trang_thai"],
		order_by="ngay_het_han asc",
	)
