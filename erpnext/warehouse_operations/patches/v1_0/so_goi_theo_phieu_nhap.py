"""Cập nhật mô tả `Batch.custom_so_goi`: số gọi giờ là phần số cuối của tên
phiếu nhập (chốt 14/10/2026, xem `batch_entry._so_goi_tu_phieu_nhap`), không
còn là "số 4 chữ số" của bộ đếm riêng. Site đã chạy `them_so_goi_va_o_in_tem`
không chạy lại patch đó, nên phải sửa thẳng Custom Field đã cài.
"""

import frappe

MO_TA = "Số phiếu nhập (phần số cuối, VD MAT-PRE-2026-00027 → 00027) in to trên nhãn để gọi nhanh. Chỉ 'Batch Entry' đặt."


def execute():
	if frappe.db.exists("Custom Field", "Batch-custom_so_goi"):
		frappe.db.set_value("Custom Field", "Batch-custom_so_goi", "description", MO_TA)
		frappe.clear_cache(doctype="Batch")
