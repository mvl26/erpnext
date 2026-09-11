"""Thêm `Warehouse.custom_ma_kho_spd` — mã kho 2 ký tự trong mã vị trí SPD.

Mã vị trí 12 ký tự mở đầu bằng 2 ký tự định danh KHO (`K1` = kho trung tâm,
`B1`…`B9` = kho vệ tinh trong bệnh viện) — xem
`SPD_VanHanh_PhanTichMaViTriKho_20260907_v2` §5.2.

Vì sao để trên `Warehouse` chứ không gõ tay mỗi lần sinh ô: mã này phải giống
nhau cho MỌI ô của cùng một kho. Để người dùng gõ lại ở từng lần sinh là mời
gọi hai lô ô của cùng kho mang hai mã khác nhau — mà mã ô thì khoá cứng sau
khi tạo và đã in lên tem.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def execute():
	create_custom_field("Warehouse", {
		"fieldname": "custom_ma_kho_spd",
		"label": "Mã kho SPD (2 ký tự)",
		"fieldtype": "Data",
		"length": 2,
		"insert_after": "custom_quan_ly_vi_tri",
		"description": (
			"Hai ký tự mở đầu mã vị trí: chữ + số, ví dụ K1 (kho trung tâm), "
			"B1–B9 (kho vệ tinh bệnh viện)."
		),
	})
