# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Trường tùy biến của kiểm giá bán (BA12) và báo trước khi đổi giá (YC4).

BA12 yêu cầu "không sửa core ERPNext": mọi trường thêm trên DocType chuẩn là Custom
Field, logic gắn qua `doc_events` / `doctype_js` trong hooks.py. Hàm `tao_truong_tuy_bien`
chạy ở mỗi lần migrate (`after_migrate`), chạy lại nhiều lần an toàn (`update=True`).
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

TRANG_THAI_GIA = "\nKhớp\nThấp hơn\nCao hơn\nChưa có giá mua\nĐang trong thời hạn báo giá\nBỏ qua"


def _ro(**field):
	"""Ô do server ghi: chỉ đọc, không chép khi Duplicate/Amend, không in."""
	return {"read_only": 1, "no_copy": 1, "print_hide": 1, **field}


def _truong_dong(insert_after, cho_so):
	"""Trường kiểm giá trên dòng Quotation / Sales Order (BA12 R02-R05, D08)."""
	fields = [
		{
			"fieldname": "kiem_gia_ban_section",
			"fieldtype": "Section Break",
			"label": "Kiểm giá bán (BA12)",
			"insert_after": insert_after,
			"collapsible": 1,
			"collapsible_depends_on": "eval:doc.trang_thai_gia && !['Khớp','Bỏ qua'].includes(doc.trang_thai_gia)",
		},
		{
			"fieldname": "ncc_du_kien",
			"fieldtype": "Link",
			"options": "Supplier",
			"label": "NCC dự kiến",
			"description": "D08: để trống thì lấy NCC mặc định của mặt hàng. Đổi NCC thì giá mua tính lại khi lưu.",
			"insert_after": "kiem_gia_ban_section",
			"no_copy": 1,
			"print_hide": 1,
		},
		_ro(
			fieldname="trang_thai_gia",
			fieldtype="Select",
			options=TRANG_THAI_GIA,
			label="Trạng thái giá",
			insert_after="ncc_du_kien",
			in_standard_filter=1,
		),
		_ro(
			fieldname="gia_mua",
			fieldtype="Currency",
			options="currency",
			label="Giá mua",
			description="Theo ĐVT của dòng, tiền tệ chứng từ, chưa VAT.",
			insert_after="trang_thai_gia",
		),
		_ro(
			fieldname="nguon_gia_mua",
			fieldtype="Select",
			options="\nBáo giá đợt\nHĐ nguyên tắc",
			label="Nguồn giá mua",
			insert_after="gia_mua",
		),
		_ro(
			fieldname="chung_tu_gia_mua",
			fieldtype="Data",
			label="Chứng từ giá mua",
			description="Số báo giá NCC hoặc dòng giá của bảng giá Mua - NCC. Data, không Link: Link sẽ chặn hủy/xóa chứng từ nguồn.",
			insert_after="nguon_gia_mua",
		),
		_ro(
			fieldname="ngay_gia_mua", fieldtype="Date", label="Ngày giá mua", insert_after="chung_tu_gia_mua"
		),
		{"fieldname": "column_break_kiem_gia", "fieldtype": "Column Break", "insert_after": "ngay_gia_mua"},
		_ro(
			fieldname="he_so_gia_ban",
			fieldtype="Float",
			precision="4",
			label="Hệ số",
			insert_after="column_break_kiem_gia",
		),
		_ro(
			fieldname="so_hop_dong_he_so", fieldtype="Data", label="Số hợp đồng", insert_after="he_so_gia_ban"
		),
		_ro(
			fieldname="gia_de_xuat",
			fieldtype="Currency",
			options="currency",
			label="Giá đề xuất",
			description="R03: giá mua x hệ số, làm tròn đến đồng.",
			insert_after="so_hop_dong_he_so",
		),
		_ro(
			fieldname="chenh_lech_gia",
			fieldtype="Currency",
			options="currency",
			label="Chênh lệch",
			description="Giá bán (làm tròn đến đồng) - giá đề xuất.",
			insert_after="gia_de_xuat",
		),
		_ro(
			fieldname="gia_bang_gia",
			fieldtype="Currency",
			options="currency",
			label="Giá bảng giá KH",
			description="Theo bảng giá mặc định của khách (Customer → Default Price List), không theo bảng giá chọn trên chứng từ.",
			insert_after="chenh_lech_gia",
		),
		_ro(
			fieldname="ngoai_bang_gia",
			fieldtype="Check",
			label="Chưa có trong bảng giá KH",
			insert_after="gia_bang_gia",
		),
		_ro(
			fieldname="khac_bang_gia",
			fieldtype="Check",
			label="Đề xuất khác bảng giá",
			description="R05: giá đề xuất khác giá bảng giá KH, hoặc mặt hàng chưa có trong bảng giá KH.",
			insert_after="ngoai_bang_gia",
		),
		_ro(
			fieldname="ghi_chu_gia",
			fieldtype="Small Text",
			label="Ghi chú kiểm giá",
			insert_after="khac_bang_gia",
		),
	]
	if cho_so:
		fields += [
			{
				"fieldname": "chap_thuan_gia_section",
				"fieldtype": "Section Break",
				"label": "Khách chấp thuận giá mới (R05)",
				"insert_after": "ghi_chu_gia",
				"depends_on": "khac_bang_gia",
			},
			{
				"fieldname": "so_van_ban_gia",
				"fieldtype": "Data",
				"label": "Số văn bản thông báo / đề nghị điều chỉnh giá",
				"description": "Sau Submit: ô còn trống vẫn điền được (bấm Cập nhật); ô đã điền chỉ Giám đốc sửa.",
				"insert_after": "chap_thuan_gia_section",
				"allow_on_submit": 1,
				"no_copy": 1,
				"print_hide": 1,
			},
			{
				"fieldname": "nguoi_dai_dien_kh",
				"fieldtype": "Data",
				"label": "Người đại diện KH xác nhận",
				"insert_after": "so_van_ban_gia",
				"allow_on_submit": 1,
				"no_copy": 1,
				"print_hide": 1,
			},
			{
				"fieldname": "ngay_chap_thuan_gia",
				"fieldtype": "Date",
				"label": "Ngày chấp thuận",
				"insert_after": "nguoi_dai_dien_kh",
				"allow_on_submit": 1,
				"no_copy": 1,
				"print_hide": 1,
			},
			{
				"fieldname": "tep_van_ban_gia",
				"fieldtype": "Attach",
				"label": "Tệp văn bản chấp thuận",
				"description": 'Bắt buộc khi Selling Settings bật "Bắt buộc đính kèm văn bản chấp thuận".',
				"insert_after": "ngay_chap_thuan_gia",
				"allow_on_submit": 1,
				"no_copy": 1,
				"print_hide": 1,
			},
			{
				"fieldname": "column_break_chap_thuan",
				"fieldtype": "Column Break",
				"insert_after": "tep_van_ban_gia",
			},
			# Q1/Q10: dòng khác bảng giá còn thiếu thông tin chấp thuận. Sau Submit (Update
			# Items) dòng được giữ ở trạng thái này: chưa tạo được Phiếu giao / Hóa đơn bán.
			_ro(
				fieldname="cho_chap_thuan",
				fieldtype="Check",
				label="Chờ khách chấp thuận giá",
				insert_after="column_break_chap_thuan",
			),
			_ro(
				fieldname="nguoi_nhap_chap_thuan",
				fieldtype="Link",
				options="User",
				label="Người nhập chấp thuận",
				insert_after="cho_chap_thuan",
			),
			_ro(
				fieldname="thoi_diem_nhap_chap_thuan",
				fieldtype="Datetime",
				label="Thời điểm nhập chấp thuận",
				insert_after="nguoi_nhap_chap_thuan",
			),
			# Giá bán lúc kiểm lần cuối: "Update Items" sau Submit chỉ kiểm lại dòng mới hoặc
			# dòng đổi giá (D05: dòng không ai đụng giữ nguyên kết quả lúc lập).
			_ro(
				fieldname="gia_da_kiem",
				fieldtype="Currency",
				options="currency",
				label="Giá bán lúc kiểm",
				hidden=1,
				insert_after="thoi_diem_nhap_chap_thuan",
			),
		]
	for f in fields:
		if cho_so and f.get("read_only"):
			f["allow_on_submit"] = 1
	return fields


CUSTOM_FIELDS = {
	"Selling Settings": [
		{
			"fieldname": "kiem_gia_ban_section",
			"fieldtype": "Section Break",
			"label": "Kiểm giá bán theo hệ số khách hàng (BA12)",
			"insert_after": "allow_zero_qty_in_sales_order",
		},
		{
			"fieldname": "bat_kiem_gia_ban",
			"fieldtype": "Check",
			"default": "0",
			"label": "Bật kiểm giá bán",
			"description": "Giá đề xuất = giá mua x hệ số của khách. Khách không có hệ số thì không kiểm (R07).",
			"insert_after": "kiem_gia_ban_section",
		},
		{
			"fieldname": "bat_buoc_dinh_kem_van_ban_gia",
			"fieldtype": "Check",
			"default": "0",
			"label": "Bắt buộc đính kèm văn bản chấp thuận",
			"description": "Bật: dòng khác bảng giá phải có tệp văn bản khách chấp thuận, ngoài 3 thông tin R05. Áp cho thông tin nhập từ lúc bật.",
			"insert_after": "bat_kiem_gia_ban",
		},
		{
			"fieldname": "column_break_kiem_gia",
			"fieldtype": "Column Break",
			"insert_after": "bat_buoc_dinh_kem_van_ban_gia",
		},
		{
			"fieldname": "vai_tro_sua_ty_le_lai",
			"fieldtype": "Link",
			"options": "Role",
			"label": "Vai trò được sửa hệ số giá bán",
			"description": "Chỉ vai trò này (Giám đốc) được sửa hệ số trên Khách hàng, các cài đặt của mục này, gửi thông báo đổi giá và sửa thông tin khách chấp thuận (R05) đã điền trên SO đã Submit. Để trống: chỉ System Manager.",
			"insert_after": "column_break_kiem_gia",
		},
	],
	"Customer": [
		{
			"fieldname": "he_so_gia_ban_section",
			"fieldtype": "Section Break",
			"label": "Hệ số giá bán (BA12)",
			"insert_after": "disabled",
			"collapsible": 1,
		},
		{
			"fieldname": "he_so_gia_ban",
			"fieldtype": "Table",
			"options": "Customer Price Coefficient",
			"label": "Hệ số theo khách hàng",
			"description": "R01: mỗi thời điểm tối đa một hệ số hiệu lực, kèm số hợp đồng. Không có hệ số: không kiểm giá (R07).",
			"insert_after": "he_so_gia_ban_section",
		},
		{
			"fieldname": "he_so_theo_mat_hang",
			"fieldtype": "Table",
			"options": "Customer Item Price Coefficient",
			"label": "Hệ số theo mặt hàng",
			"description": "Chỉ dùng khi khách KHÔNG có hệ số theo khách hàng; có hệ số chung thì bảng này bị khóa và không áp.",
			"insert_after": "he_so_gia_ban",
		},
	],
	"Quotation Item": _truong_dong("page_break", cho_so=False),
	"Sales Order Item": _truong_dong("project", cho_so=True),
	"Sales Order": [
		{
			"fieldname": "kiem_gia_ban_section",
			"fieldtype": "Section Break",
			"label": "Kiểm giá bán",
			"insert_after": "items",
			"depends_on": "eval:(doc.items || []).some(d => d.trang_thai_gia && !['Khớp','Bỏ qua','Đang trong thời hạn báo giá'].includes(d.trang_thai_gia)) || doc.ly_do_lech_gia || doc.thong_bao_gia_moi",
		},
		{
			"fieldname": "ly_do_lech_gia",
			"fieldtype": "Small Text",
			"label": "Lý do lệch giá",
			"description": "R04/R08: bắt buộc khi Submit nếu còn dòng lệch giá đề xuất hoặc chưa có giá mua.",
			"insert_after": "kiem_gia_ban_section",
			"allow_on_submit": 1,
			"no_copy": 1,
			"print_hide": 1,
		},
		{"fieldname": "column_break_kiem_gia", "fieldtype": "Column Break", "insert_after": "ly_do_lech_gia"},
		_ro(
			fieldname="thong_bao_gia_moi",
			fieldtype="Link",
			options="Communication",
			label="Thông báo giá mới (R06)",
			insert_after="column_break_kiem_gia",
			allow_on_submit=1,
		),
	],
	"Price List": [
		{
			"fieldname": "bao_truoc_section",
			"fieldtype": "Section Break",
			"label": "Báo trước khi đổi giá",
			"insert_after": "countries",
			"collapsible": 1,
			"collapsible_depends_on": "bao_truoc_khi_doi_gia",
			"depends_on": "selling",
		},
		{
			"fieldname": "bao_truoc_khi_doi_gia",
			"fieldtype": "Check",
			"default": "0",
			"label": "Báo trước khi đổi giá",
			"description": "Giá mới phải vào Bảng giá chờ, rồi Giám đốc Gửi thông báo đổi giá cho khách mới được áp. Giá cũ không sửa, không xóa.",
			"insert_after": "bao_truoc_section",
		},
		{
			"fieldname": "so_ngay_bao_truoc",
			"fieldtype": "Int",
			"default": "7",
			"non_negative": 1,
			"label": "Số ngày báo trước",
			"depends_on": "bao_truoc_khi_doi_gia",
			"insert_after": "bao_truoc_khi_doi_gia",
		},
		{
			"fieldname": "column_break_bao_truoc",
			"fieldtype": "Column Break",
			"insert_after": "so_ngay_bao_truoc",
		},
		{
			"fieldname": "bang_gia_cho",
			"fieldtype": "Link",
			"options": "Price List",
			"label": "Bảng giá chờ",
			"description": "Bảng giá bán chứa giá chưa gửi thông báo. Chứng từ bán không được dùng bảng giá này.",
			"depends_on": "bao_truoc_khi_doi_gia",
			"insert_after": "column_break_bao_truoc",
		},
		{
			"fieldname": "email_nhan_thong_bao",
			"fieldtype": "Small Text",
			"label": "Email nhận thông báo đổi giá",
			"description": "Nhiều email cách nhau bằng dấu phẩy.",
			"depends_on": "bao_truoc_khi_doi_gia",
			"insert_after": "bang_gia_cho",
		},
	],
	"Item Price": [
		{
			"fieldname": "thong_bao_doi_gia_section",
			"fieldtype": "Section Break",
			"label": "Thông báo đổi giá",
			"insert_after": "reference",
			"collapsible": 1,
			"depends_on": "trang_thai_thong_bao",
		},
		_ro(
			fieldname="trang_thai_thong_bao",
			fieldtype="Select",
			options="\nChờ gửi\nĐã gửi\nĐã xác nhận",
			label="Trạng thái thông báo",
			in_standard_filter=1,
			insert_after="thong_bao_doi_gia_section",
			print_hide=0,
		),
		_ro(
			fieldname="ngay_gui_thong_bao",
			fieldtype="Date",
			label="Ngày gửi thông báo",
			insert_after="trang_thai_thong_bao",
		),
		_ro(
			fieldname="so_ngay_bao_truoc",
			fieldtype="Int",
			label="Số ngày báo trước",
			insert_after="ngay_gui_thong_bao",
		),
		_ro(
			fieldname="bao_gap",
			fieldtype="Check",
			default="0",
			label="Báo gấp",
			in_standard_filter=1,
			insert_after="so_ngay_bao_truoc",
		),
		_ro(
			fieldname="thong_bao",
			fieldtype="Link",
			options="Communication",
			label="Email thông báo",
			insert_after="bao_gap",
		),
		_ro(
			fieldname="nguoi_gui_thong_bao",
			fieldtype="Link",
			options="User",
			label="Người gửi thông báo",
			insert_after="thong_bao",
		),
		{
			"fieldname": "column_break_thong_bao",
			"fieldtype": "Column Break",
			"insert_after": "nguoi_gui_thong_bao",
		},
		{
			"fieldname": "ly_do_bao_gap",
			"fieldtype": "Small Text",
			"label": "Lý do báo gấp",
			"depends_on": "bao_gap",
			"no_copy": 1,
			"insert_after": "column_break_thong_bao",
		},
		{
			"fieldname": "ngay_xac_nhan",
			"fieldtype": "Date",
			"label": "Ngày khách xác nhận",
			"description": "Ngày khách đồng ý (qua email). Bằng chứng bổ sung, không phải điều kiện để giá có hiệu lực.",
			"depends_on": "eval:['Đã gửi','Đã xác nhận'].includes(doc.trang_thai_thong_bao)",
			"no_copy": 1,
			"insert_after": "ly_do_bao_gap",
		},
		{
			"fieldname": "bang_chung_xac_nhan",
			"fieldtype": "Attach",
			"label": "Bằng chứng xác nhận",
			"depends_on": "eval:['Đã gửi','Đã xác nhận'].includes(doc.trang_thai_thong_bao)",
			"no_copy": 1,
			"insert_after": "ngay_xac_nhan",
		},
	],
}


def tao_truong_tuy_bien():
	"""Gọi từ `after_migrate`."""
	create_custom_fields(CUSTOM_FIELDS, update=True)
	# YC4: lịch sử sửa cài đặt báo trước của bảng giá.
	frappe.make_property_setter(
		{
			"doctype": "Price List",
			"doctype_or_field": "DocType",
			"property": "track_changes",
			"value": "1",
			"property_type": "Check",
		},
		validate_fields_for_doctype=False,
	)
