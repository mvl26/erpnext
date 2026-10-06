# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Gỡ luồng HĐĐT cũ chạy theo Sales Invoice, dọn chỗ cho luồng Fast trên Delivery Note.

Luồng cũ tự phát hành hóa đơn khi submit Sales Invoice. Đặc tả Fast v2.0 (nguyên
tắc A2) yêu cầu mọi hành động phải có xác nhận của người dùng, và chứng từ nguồn
đổi sang Delivery Note, nên luồng cũ được thay hẳn chứ không giữ song song — hai
đường phát hành cùng sống là nguy cơ một lần bán ra hai số hóa đơn.

Patch chỉ xóa khi **chưa có dữ liệu nghiệp vụ**. Nếu site nào đó đã lỡ phát hành
qua luồng cũ, patch giữ nguyên bản ghi và chỉ ghi log — dữ liệu hóa đơn là chứng
từ pháp lý, không được dọn tự động.
"""

import frappe

OLD_LOG_DOCTYPE = "Vietnam E Invoice Log"


def execute():
	if _has_legacy_data():
		frappe.log_error(
			title="HĐĐT: giữ lại dữ liệu luồng cũ",
			message=(
				f"Site còn bản ghi {OLD_LOG_DOCTYPE} hoặc Sales Invoice đã đóng dấu số HĐĐT. "
				"Patch không xóa để bảo toàn chứng từ — cần kế toán đối chiếu và dọn thủ công."
			),
		)
		return

	for dt, fieldname in frappe.get_all(
		"Custom Field",
		filters={"fieldname": ["like", "vn_einvoice%"]},
		fields=["dt", "fieldname"],
		as_list=True,
	):
		frappe.delete_doc("Custom Field", f"{dt}-{fieldname}", force=True, ignore_missing=True)

	if frappe.db.exists("DocType", OLD_LOG_DOCTYPE):
		frappe.delete_doc("DocType", OLD_LOG_DOCTYPE, force=True, ignore_missing=True)


def _has_legacy_data():
	"""Có hóa đơn nào từng phát hành qua luồng cũ không?"""
	if frappe.db.table_exists(OLD_LOG_DOCTYPE) and frappe.db.count(OLD_LOG_DOCTYPE):
		return True
	if not frappe.db.has_column("Sales Invoice", "vn_einvoice_number"):
		return False
	return bool(
		frappe.db.sql(
			"select 1 from `tabSales Invoice` where ifnull(vn_einvoice_number, '') != '' limit 1"
		)
	)
