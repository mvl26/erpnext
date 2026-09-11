"""Dọn `Storage Location.loai_vi_tri` còn giá trị không hợp lệ.

"Cách ly" và "Trả hàng" bị bỏ khỏi danh sách lựa chọn: không chỗ nào trong
`vi_tri_kho/vitri/` đọc trường này, nên hàng ở một ô đánh dấu "Cách ly" vẫn
bị FEFO chọn ra để xuất bán — đúng nghĩa một nhãn an toàn giả. Cách ly thật
là ranh giới TỒN KHO, nên nó phải là một `Warehouse` (xem spec
2026-09-11 §3). Để giá trị cũ nằm lại là tiếp tục quảng cáo điều không có.

Nhân patch dọn dữ liệu, gỡ luôn `Warehouse.custom_ma_kho_spd`: Task 1
(2026-09-11) đã bỏ mọi chỗ đọc trường này trong `sinh_ma.py`, nên trường
tồn tại chỉ còn là dữ liệu chết trên form Warehouse.
"""

import frappe


def execute():
	frappe.db.sql(
		"""update `tabStorage Location` set loai_vi_tri = null
		   where ifnull(loai_vi_tri, '') not in ('', 'Lưu trữ', 'Soạn hàng')"""
	)
	frappe.db.delete("Custom Field", {"dt": "Warehouse", "fieldname": "custom_ma_kho_spd"})
	# `frappe.db.delete` là DML thẳng, không chạy `CustomField.on_trash()` nên
	# không tự clear cache như xoá qua UI/API bình thường vẫn làm. `bench
	# migrate` tự clear cache ở cuối nên patch chạy qua migrate không sao,
	# nhưng gọi patch tay ngoài migrate (console, test) sẽ để lại meta
	# `Warehouse` còn field cũ trong cache Redis — clear tay cho chắc.
	frappe.clear_cache(doctype="Warehouse")
