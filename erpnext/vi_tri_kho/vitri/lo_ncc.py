"""Điền nhà cung cấp cho lô sinh từ chứng từ mua (spec khối C §4.3).

Spec chọn KHÔNG chặn hộp thoại lô sẵn có của ERPNext — chặn sẽ vỡ các luồng kho
khác vốn dùng chung `Batch`. Đổi lại phải bảo đảm dữ liệu không thiếu bất kể lô
sinh bằng đường nào, và đây là chỗ làm việc đó.

`before_insert` chứ không phải `validate`: `validate` chạy lại mỗi lần lưu, nên
một người cố tình xoá NCC đi sẽ bị hệ điền lại ngay — tức là hệ cãi người dùng
mà không nói gì. Điền một lần lúc sinh ra là đủ.
"""

import frappe

# Chỉ hai doctype này. Danh sách mở rộng theo "cái nào có trường supplier" là
# cái bẫy: nhiều doctype có trường tên `supplier` mà không phải nguồn gốc của
# lô hàng (Supplier Quotation, Subscription...). Liệt kê tường minh.
_CHUNG_TU_MUA = ("Purchase Receipt", "Purchase Invoice")


def dien_ncc_tu_chung_tu(doc, method=None):
	if doc.supplier:
		return
	if doc.reference_doctype not in _CHUNG_TU_MUA or not doc.reference_name:
		return

	ncc = frappe.db.get_value(doc.reference_doctype, doc.reference_name, "supplier")
	if ncc:
		doc.supplier = ncc
