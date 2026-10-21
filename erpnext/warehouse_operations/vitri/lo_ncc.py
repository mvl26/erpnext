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


def dien_so_lo_neu_trong(doc, method=None):
	"""Lô sinh NGOÀI `Batch Entry` (hộp thoại lô ERPNext, series của mặt hàng,
	import) không có số lô NCC — lấy chính mã lô làm số lô, để mọi màn hình hiện
	số lô luôn có chữ mà hiện và `title_field` không bao giờ trống.

	`validate` chứ không `before_insert` như hàm trên: lô đặt tên theo series sinh
	tên trong `autoname`, chạy SAU `before_insert` — tới đó tên còn rỗng. Chỉ điền
	khi trống nên chạy lại mỗi lần lưu cũng không đè giá trị nào.
	"""
	if not doc.get("custom_so_lo"):
		doc.custom_so_lo = doc.batch_id or doc.name
