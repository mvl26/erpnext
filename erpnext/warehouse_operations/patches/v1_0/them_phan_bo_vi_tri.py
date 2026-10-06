"""Thêm `Delivery Note.custom_phan_bo_vi_tri` — bảng phân bổ vị trí (spec lấy hàng §3.1).

READ-ONLY có chủ đích, cùng lẽ với `custom_so_goi` / `custom_o_in_tem`: bảng này
là KẾT QUẢ của việc thủ kho quét tem ngoài kệ, không phải chỗ để khai tay. Sửa
tay được nghĩa là sổ vị trí nói một đằng, hàng trên kệ một nẻo — mà tổng tồn vẫn
khớp nên không báo cáo nào bắt được.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def execute():
	create_custom_field(
		"Delivery Note",
		{
			"fieldname": "custom_phan_bo_vi_tri",
			"label": "Phân bổ vị trí",
			"fieldtype": "Table",
			"options": "Location Allocation",
			"read_only": 1,
			"insert_after": "items",
			"description": "Ô đã lấy hàng, do trang Lấy hàng (PDA) ghi. Trống = hệ tự chọn ô theo hạn dùng.",
		},
	)
