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
