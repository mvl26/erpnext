# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Trường tùy biến của Đợt 4: hợp đồng khung, tiếp nhận hóa đơn NCC (FRD-MAP-01, spec 2026-10-23).

Cùng nguyên tắc với BA12 / YC5: không sửa JSON DocType chuẩn. Trường thêm là Custom Field, tạo ở
mỗi lần migrate (`after_migrate`), chạy lại nhiều lần an toàn (`update=True`).
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from erpnext.buying.tiep_nhan_hoa_don.chuan_hoa import DONG_NGHIA_MAC_DINH

THUE_SUAT = "\n10%\n8%\n5%\n0%\nKCT"
CAI_DAT = "Supplier Invoice Intake Settings"


def _ro(**field):
	"""Ô do server ghi: chỉ đọc, không chép khi Duplicate/Amend, không in."""
	return {"read_only": 1, "no_copy": 1, "print_hide": 1, **field}


def _dong_hdk():
	"""Thông tin dòng hợp đồng khung (FRD 6.2, đặt ở dòng hợp đồng thay vì thẻ vật tư: D4-1)."""
	truoc = "party_item_code"
	fields = []
	for f in (
		{
			"fieldname": "ma_dong_hdk",
			"fieldtype": "Data",
			"label": "Mã dòng hợp đồng",
			"description": "Tự sinh [NCC]-[Số hợp đồng]-[Nhóm hàng]-[STT] khi có Số hợp đồng; sửa được trước khi Nộp. Không trùng.",
			"no_copy": 1,
			"in_list_view": 1,
			"columns": 2,
		},
		{"fieldname": "ten_hdk", "fieldtype": "Small Text", "label": "Tên theo hợp đồng"},
		{"fieldname": "quy_cach", "fieldtype": "Data", "label": "Quy cách"},
		{"fieldname": "chat_lieu", "fieldtype": "Data", "label": "Chất liệu"},
		{"fieldname": "hang_sx", "fieldtype": "Data", "label": "Hãng sản xuất"},
		{"fieldname": "nuoc_sx", "fieldtype": "Data", "label": "Nước sản xuất"},
		{"fieldname": "so_luu_hanh", "fieldtype": "Data", "label": "Số lưu hành / công bố"},
		{"fieldname": "thue_suat", "fieldtype": "Select", "options": THUE_SUAT, "label": "Thuế suất GTGT"},
		_ro(
			fieldname="da_lap_hoa_don",
			fieldtype="Float",
			label="Đã lập hóa đơn (ĐVT kho)",
			description="Lũy kế số lượng trên Hóa đơn mua đã Nộp của các Đơn mua gắn hợp đồng này.",
		),
	):
		fields.append({**f, "insert_after": truoc})
		truoc = f["fieldname"]
	return fields


CUSTOM_FIELDS = {
	"Supplier": [
		{
			"fieldname": "ma_viet_tat",
			"fieldtype": "Data",
			"label": "Mã viết tắt",
			"description": "Phần [NCC] của mã dòng hợp đồng khung. Trống: chữ cái đầu của tên.",
			"insert_after": "supplier_name",
		},
	],
	"Item Group": [
		{
			"fieldname": "ma_viet_tat",
			"fieldtype": "Data",
			"label": "Mã viết tắt",
			"description": "Phần [Nhóm] của mã dòng hợp đồng khung. Trống: chữ cái đầu của tên nhóm.",
			"insert_after": "item_group_name",
		},
	],
	"Blanket Order": [
		{
			"fieldname": "bang_gia_mua",
			"fieldtype": "Link",
			"options": "Price List",
			"label": "Bảng giá mua",
			"description": "Nộp hợp đồng thì giá từng dòng được ghi vào bảng giá này (giá HĐ nguyên tắc dùng khi kiểm giá bán); hủy hợp đồng thì xóa. Trống: bảng giá mặc định của nhà cung cấp.",
			"depends_on": "eval:doc.blanket_order_type == 'Purchasing'",
			"insert_after": "supplier_name",
		},
	],
	"Blanket Order Item": _dong_hdk(),
	"Item Price": [
		_ro(
			fieldname="hop_dong_khung",
			fieldtype="Link",
			options="Blanket Order",
			label="Hợp đồng khung",
			description="Giá do hợp đồng khung ghi: sửa ở hợp đồng (Hủy rồi Sửa đổi), không sửa ở đây.",
			depends_on="hop_dong_khung",
			insert_after="supplier",
		),
	],
	"Purchase Invoice": [
		_ro(
			fieldname="phieu_tiep_nhan",
			fieldtype="Link",
			options="Supplier Invoice Intake",
			label="Phiếu tiếp nhận hóa đơn",
			depends_on="phieu_tiep_nhan",
			insert_after="bill_date",
		),
	],
	"Purchase Invoice Item": [
		_ro(
			fieldname="ten_tren_hoa_don",
			fieldtype="Small Text",
			label="Tên trên hóa đơn NCC",
			depends_on="ten_tren_hoa_don",
			insert_after="description",
			no_copy=0,
		),
		_ro(
			fieldname="hop_dong_khung",
			fieldtype="Link",
			options="Blanket Order",
			label="Hợp đồng khung",
			depends_on="hop_dong_khung",
			insert_after="ten_tren_hoa_don",
			no_copy=0,
		),
		_ro(
			fieldname="ma_dong_hdk",
			fieldtype="Data",
			label="Mã dòng hợp đồng",
			depends_on="ma_dong_hdk",
			insert_after="hop_dong_khung",
			no_copy=0,
		),
		_ro(
			fieldname="cach_khop",
			fieldtype="Data",
			label="Cách khớp",
			depends_on="cach_khop",
			insert_after="ma_dong_hdk",
		),
		_ro(
			fieldname="diem_khop",
			fieldtype="Float",
			precision="2",
			label="Điểm khớp",
			depends_on="cach_khop",
			insert_after="cach_khop",
		),
	],
}


def tao_truong_tuy_bien():
	"""Gọi từ `after_migrate`. Lần đầu (cài đặt chưa lưu) gieo giá trị mặc định và từ đồng nghĩa."""
	create_custom_fields(CUSTOM_FIELDS, update=True)
	if frappe.db.exists("DocType", CAI_DAT) and not frappe.db.get_single_value(CAI_DAT, "nguong_tu_dong"):
		s = frappe.get_single(CAI_DAT)
		s.update(
			{
				"bat_tiep_nhan": 1,
				"nguong_canh_bao_han_muc": 90,
				"nguong_tu_dong": 0.75,
				"nguong_xac_nhan": 0.55,
				"trong_so_jaccard": 0.6,
				"trong_so_chuoi": 0.4,
				"tu_bo_qua": "size, cỡ, loại, cái",
			}
		)
		if not s.tu_dong_nghia:
			for a, b in DONG_NGHIA_MAC_DINH:
				s.append("tu_dong_nghia", {"tu_1": a, "tu_2": b})
		s.flags.ignore_permissions = True
		s.save()
