# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Làm mới `tinh_trang_ho_so` của những Item bị một thay đổi chạm tới.

Chạy nền vì một chứng từ cấp chủ sở hữu có thể chạm hàng trăm mặt hàng — để
đồng bộ thì người dùng ngồi chờ mỗi lần bấm Lưu.
"""

import frappe

# CỐ Ý không import `resolver` và `status` ở cấp module. Controller
# `tbyt_marketing_authorization` import file này, mà `resolver` lại import
# `get_condition_context` từ chính controller đó — thành vòng lặp
# `authorization -> refresh -> resolver -> authorization`. Python sẽ nổ
# ImportError ngay khi Frappe nạp controller, và nổ từ cả hai đầu vào. Hoãn
# import vào trong thân hàm cắt vòng tại đúng một điểm.


def refresh_items(item_codes: list[str]) -> None:
	from erpnext.tbyt.status import update_item_status

	for item_code in item_codes:
		update_item_status(item_code)


def refresh_for_document(doc, method=None) -> None:
	"""Chứng từ đổi → làm mới mọi Item mà bảng phạm vi của nó phủ."""
	from erpnext.tbyt.resolver import find_items_for_scope

	affected = []
	for row in doc.pham_vi:
		affected.extend(find_items_for_scope(row.scope_doctype, row.scope_name))
	_enqueue(sorted(set(affected)))


def refresh_for_authorization(doc, method=None) -> None:
	"""Số lưu hành đổi trạng thái → làm mới mọi Item trỏ tới nó."""
	from erpnext.tbyt.resolver import find_items_for_scope

	_enqueue(find_items_for_scope("TBYT Marketing Authorization", doc.name))


def _enqueue(item_codes: list[str]) -> None:
	if not item_codes:
		return
	# `now=in_test` vì enqueue mặc định KHÔNG chạy inline trong test — nó đẩy
	# vào Redis thật và assert ngay sau đó sẽ đọc phải giá trị cũ.
	frappe.enqueue(
		"erpnext.tbyt.refresh.refresh_items",
		queue="short",
		item_codes=item_codes,
		now=bool(frappe.flags.in_test),
	)
