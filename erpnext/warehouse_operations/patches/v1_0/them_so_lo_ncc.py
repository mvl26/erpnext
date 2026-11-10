"""Thêm `Batch.custom_so_lo` — số lô in trên bao bì NCC (spec 19/10/2026).

VÌ SAO: trước đây số lô NCC LÀ tên bản ghi `Batch`, mà tên là khoá nên không
trùng được — trong khi hai mặt hàng khác nhau chung một số lô là chuyện xảy ra
thường xuyên. Từ nay tên `Batch` là mã lô hệ thống tự sinh (`L26-000123`, mã
vạch in nó), còn số lô NCC nằm ở trường này và được trùng.

`title_field` + `show_title_field_in_link`: ô Link "Batch" ở mọi form ERPNext
hiện số lô thay cho mã. `search_fields` có mặt hàng và HSD vì số lô trùng nhau
thì người chọn cần thấy thêm thứ để phân biệt.

READ-ONLY: số lô là một phần của khoá nhận diện lô (mặt hàng, số lô, HSD) mà
`Batch Entry` dùng để quyết định dùng lại hay tạo lô mới. Sửa tay trên form lô
làm hai lô thật khác nhau trùng khoá, hoặc tách một lô thật làm hai.

Lô cũ: tên cũ CHÍNH LÀ số lô NCC, nên gán `custom_so_lo = name`. Không đổi tên
lô nào — tem cũ đang dán trên thùng mã hoá đúng tên đó.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	create_custom_field(
		"Batch",
		{
			"fieldname": "custom_so_lo",
			"label": "Số lô",
			"fieldtype": "Data",
			"length": 140,
			"read_only": 1,
			"bold": 1,
			"in_list_view": 1,
			"in_standard_filter": 1,
			"search_index": 1,
			"insert_after": "batch_id",
			"description": "Số lô in trên bao bì nhà cung cấp. Có thể trùng giữa các mặt hàng — "
			"mã lô (tên bản ghi) mới là khoá.",
		},
	)
	for prop, value, kieu in (
		("title_field", "custom_so_lo", "Data"),
		("show_title_field_in_link", "1", "Check"),
		("search_fields", "custom_so_lo,item,expiry_date", "Data"),
	):
		make_property_setter("Batch", None, prop, value, kieu, for_doctype=True)

	frappe.db.sql("update `tabBatch` set custom_so_lo = name where ifnull(custom_so_lo, '') = ''")
	frappe.clear_cache(doctype="Batch")
