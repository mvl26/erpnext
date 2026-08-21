# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tính trạng thái hiệu lực của một chứng từ.

Hàm thuần, không chạm DB — để test được mọi mốc thời gian mà không phải dựng
bản ghi. Job hằng ngày (Task 12) dùng lại chính hàm này, nên trạng thái lúc lưu
và trạng thái do job đặt không bao giờ lệch nhau.
"""

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
