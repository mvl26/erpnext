# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Móc nối hồ sơ TBYT vào Item.

Để ở module `tbyt` chứ không nhồi vào `item.py`: logic TBYT thay đổi theo thông
tư, còn `item.py` là controller dùng chung — trộn vào nhau thì mỗi lần Bộ Y tế
sửa quy định lại phải mở một file 1000 dòng của core.
"""

import frappe
from frappe import _
from frappe.utils import cint


def require_authorization_for_medical_item(doc, method=None):
	"""Số lưu hành là ràng buộc CỨNG duy nhất của cả tính năng — chặn thật.

	`mandatory_depends_on` trên trường chỉ chặn ở trình duyệt: không chỗ nào trong
	`frappe/model/` đọc nó. ERPNext core cũng không tin nó — `Item.asset_category`
	có `mandatory_depends_on`, nhưng `item.py` vẫn viết riêng một kiểm tra server.
	Thiếu hàm này thì mọi đường ghi không qua form đều lọt.
	"""
	if not cint(doc.get("la_thiet_bi_y_te")):
		return
	if doc.get("so_luu_hanh"):
		return
	frappe.throw(
		_("Mặt hàng là thiết bị y tế thì bắt buộc phải có Số lưu hành."),
		frappe.MandatoryError,
	)


def warn_about_missing_documents(doc, method=None):
	"""Cảnh báo thiếu chứng từ — KHÔNG BAO GIỜ chặn lưu.

	Ràng buộc cứng duy nhất là số lưu hành, và nó đã do
	`mandatory_depends_on` trên chính trường đó lo. Chứng từ thì phụ thuộc nhà
	cung cấp gửi, chặn lưu ở đây sẽ chặn cả việc tạo mã hàng để báo giá.
	"""
	from erpnext.tbyt.constants import (
		AUTH_STATUS_EXPIRED,
		AUTH_STATUS_PENDING,
		AUTH_STATUS_REVOKED,
		DOC_STATUS_EXPIRED,
		LEVEL_BB,
		LEVEL_BB_STAR,
		LEVEL_NC,
	)
	from erpnext.tbyt.resolver import get_item_documents
	from erpnext.tbyt.status import get_item_status

	if not cint(doc.get("la_thiet_bi_y_te")):
		doc.tinh_trang_ho_so = None
		return

	snapshot = {
		"name": doc.name,
		"la_thiet_bi_y_te": doc.la_thiet_bi_y_te,
		"so_luu_hanh": doc.so_luu_hanh,
	}
	doc.tinh_trang_ho_so = get_item_status(doc.name, item=snapshot)

	if not doc.so_luu_hanh:
		return

	auth_status = frappe.db.get_value("TBYT Marketing Authorization", doc.so_luu_hanh, "trang_thai")
	lines = []

	if auth_status in (AUTH_STATUS_EXPIRED, AUTH_STATUS_REVOKED):
		lines.append(f"<b style='color:var(--red-600)'>Số lưu hành đang ở trạng thái “{auth_status}”.</b>")
	elif auth_status == AUTH_STATUS_PENDING:
		# Chưa có phân loại chắc chắn thì liệt kê thiếu gì chỉ gây nhiễu.
		frappe.msgprint(
			"Số lưu hành chưa được cấp (đang đăng ký). Hồ sơ chứng từ sẽ kiểm khi có số chính thức.",
			indicator="orange",
			alert=True,
		)
		return

	rows = get_item_documents(doc.name, item=snapshot)
	expired = [r for r in rows if r["is_required"] and r["trang_thai"] == DOC_STATUS_EXPIRED]
	missing_bb = [r for r in rows if not r["document"] and r["level"] == LEVEL_BB]
	missing_star = [r for r in rows if not r["document"] and r["level"] == LEVEL_BB_STAR and r["is_required"]]
	missing_nc = [r for r in rows if not r["document"] and r["level"] == LEVEL_NC]

	if expired:
		names = ", ".join(r["document_name"] for r in expired)
		lines.append(f"<b style='color:var(--red-600)'>Chứng từ đã hết hạn:</b> {names}")
	if missing_bb:
		names = ", ".join(r["document_name"] for r in missing_bb)
		lines.append(f"<b style='color:var(--red-600)'>Thiếu chứng từ bắt buộc:</b> {names}")
	if missing_star:
		names = ", ".join(r["document_name"] for r in missing_star)
		lines.append(f"<b style='color:var(--orange-600)'>Thiếu chứng từ bắt buộc có điều kiện:</b> {names}")
	if missing_nc:
		names = ", ".join(r["document_name"] for r in missing_nc)
		lines.append(f"<span style='color:var(--blue-600)'>Nên bổ sung:</span> {names}")

	# Gộp một hộp thoại duy nhất — bốn msgprint liên tiếp sẽ dội vào mặt người dùng.
	if lines:
		frappe.msgprint(
			"<br>".join(lines),
			title="Hồ sơ pháp lý TBYT chưa đầy đủ",
			indicator="red" if (expired or missing_bb) else "orange",
		)
