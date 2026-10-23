# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Bảng ánh xạ tên: duyệt / ngừng dùng (FR-22, BR-04; FRD mục 15: Chuỗi cung ứng duyệt)."""

import json

import frappe
from frappe import _

from erpnext.buying.tiep_nhan_hoa_don.cau_hinh import co_quyen_duyet_anh_xa

TRANG_THAI = ("Chờ duyệt", "Đang dùng", "Ngừng dùng")


@frappe.whitelist()
def doi_trang_thai(ten, trang_thai):
	"""Duyệt hàng loạt từ danh sách: `ten` là một tên hoặc danh sách tên (JSON)."""
	if trang_thai not in TRANG_THAI:
		frappe.throw(_("Trạng thái không hợp lệ: {0}").format(trang_thai))
	if not co_quyen_duyet_anh_xa():
		frappe.throw(_("Bạn không có vai trò duyệt Bảng ánh xạ tên."), frappe.PermissionError)
	if isinstance(ten, str):
		ds = json.loads(ten) if ten.startswith("[") else [ten]
	else:
		ds = ten
	for t in ds:
		doc = frappe.get_doc("Supplier Item Alias", t)
		doc.trang_thai = trang_thai
		doc.save()
	return len(ds)
