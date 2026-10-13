"""Thêm `Batch.custom_so_goi` và `Batch.custom_o_in_tem` (spec khối C §4.2).

Cả hai READ-ONLY có chủ đích, cùng lý do như `custom_quan_ly_vi_tri`: chúng là
KẾT QUẢ của một thao tác chứ không phải thứ để khai.

`custom_so_goi` là số người ta đọc cho nhau qua kho ("lấy giúp lô ba tám năm
sáu"). Sửa tay được nghĩa là hai lô có thể mang cùng một số gọi, và khi ấy câu
nói trong kho trỏ vào hai thùng hàng khác nhau.

`custom_o_in_tem` ghi lại MỘT SỰ KIỆN LỊCH SỬ: một tờ giấy đã in ra và đang dán
trên thùng hàng. Sửa nó không làm đổi tờ giấy đó — chỉ làm hệ thống nói khác
với vật thể.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def execute():
	create_custom_field(
		"Batch",
		{
			"fieldname": "custom_so_goi",
			"label": "Số gọi",
			"fieldtype": "Data",
			"read_only": 1,
			"insert_after": "reference_name",
			"description": "Số 4 chữ số in to trên nhãn để gọi nhanh. Chỉ 'Batch Entry' đặt.",
		},
	)
	create_custom_field(
		"Batch",
		{
			"fieldname": "custom_o_in_tem",
			"label": "Ô đã in trên tem",
			"fieldtype": "Link",
			"options": "Storage Location",
			"read_only": 1,
			"insert_after": "custom_so_goi",
			"description": "Ô đã in lên nhãn đang dán trên hàng. Gợi ý xếp sẽ ưu tiên ô này.",
		},
	)
