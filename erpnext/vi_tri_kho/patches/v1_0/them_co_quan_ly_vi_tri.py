"""Thêm `Warehouse.custom_quan_ly_vi_tri` (spec §5.9).

READ-ONLY có chủ đích. Bật quản lý vị trí là một quy trình chuyển đổi dữ
liệu (tạo ô CHUA-XEP, đọc tồn hiện có tách theo lô, ghi sổ, đối soát), không
phải một cái công tắc. Để field sửa được là mở đường tắt bỏ qua toàn bộ quy
trình đó — và hệ sẽ sai từ giây đầu tiên mà không ai biết. Chỉ doctype
`Warehouse Location Setup` được đặt giá trị này.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def execute():
	create_custom_field(
		"Warehouse",
		{
			"fieldname": "custom_quan_ly_vi_tri",
			"label": "Quản lý theo vị trí",
			"fieldtype": "Check",
			"default": "0",
			"read_only": 1,
			"search_index": 1,
			"insert_after": "warehouse_type",
			"description": "Chỉ đặt qua 'Warehouse Location Setup'. Không sửa tay.",
		},
	)
