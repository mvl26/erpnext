"""Thêm `Item.custom_thong_so_tem` — ô F4 của nhãn lô (spec khối C §4.2).

Đặt trên ITEM chứ không phải Batch, vì thông số phân biệt SKU
("7Fr – Loop 10cm – HD 200cm") là thuộc tính của mặt hàng, không phải của lô.
Đặt trên Batch là bắt thủ kho gõ lại cùng một chuỗi cho từng lô — rồi gõ lệch
nhau giữa các lô, và hai thùng cùng một mặt hàng mang hai nhãn nói khác nhau.

60 ký tự là trần của Ô F4 ở 6,5pt trên vùng in 47mm. Dài hơn thì tràn nhãn, mà
tràn nhãn thì không có lỗi nào báo — chỉ là chữ bị cắt trên giấy.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def execute():
	create_custom_field(
		"Item",
		{
			"fieldname": "custom_thong_so_tem",
			"label": "Thông số in trên tem",
			"fieldtype": "Data",
			"length": 60,
			"insert_after": "description",
			"description": "Ô F4 nhãn lô, ví dụ '7Fr – Loop 10cm – HD 200cm'. Tối đa 60 ký tự.",
		},
	)
