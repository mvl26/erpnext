"""Thêm `Delivery Note Item.custom_vi_tri_lay` — ô đã lấy của từng dòng hàng (19/09/2026).

Chỉ để ĐỌC và IN: nội dung do `lay_hang.dien_cot_vi_tri_tu_phan_bo` (lúc lưu nháp)
và `lay_hang.ghi_cot_vi_tri_khi_duyet` (lúc duyệt, từ sổ vị trí thật) viết ra.
Nguồn sự thật vẫn là bảng `custom_phan_bo_vi_tri` và `Location Ledger Entry`.
`allow_on_submit` vì bản ghi cuối cùng được viết SAU khi phiếu đã duyệt.

CHỖ TRÊN LƯỚI: lưới dòng hàng chỉ có 10 đơn vị cột, và năm cột sẵn có (mã hàng,
số lượng, đơn vị, đơn giá, thành tiền — mỗi cột mặc định 2) đã dùng hết; cột thứ
sáu `warehouse` vốn đã bị đẩy khỏi lưới từ trước (`grid.js` dừng khi vượt 10).
Không chỉnh gì thì cột mới cũng không bao giờ hiện. Thu số lượng và đơn vị về 1
(giá trị ngắn: "5", "Chai"), bỏ `warehouse` khỏi lưới (không đổi gì thấy được —
nó vốn không hiện), để dành 2 đơn vị cho "Vị trí lấy".
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	create_custom_field(
		"Delivery Note Item",
		{
			"fieldname": "custom_vi_tri_lay",
			"label": "Vị trí lấy",
			"fieldtype": "Small Text",
			"read_only": 1,
			"allow_on_submit": 1,
			"no_copy": 1,
			"in_list_view": 1,
			"columns": 2,
			"insert_after": "warehouse",
			"description": "Ô đã lấy hàng (mã in trên tem ô × số lượng theo đơn vị tồn kho).",
		},
	)
	for ten, thuoc_tinh, gia_tri, kieu in (
		("qty", "columns", "1", "Int"),
		("uom", "columns", "1", "Int"),
		("warehouse", "in_list_view", "0", "Check"),
	):
		make_property_setter(
			"Delivery Note Item", ten, thuoc_tinh, gia_tri, kieu, validate_fields_for_doctype=False
		)
