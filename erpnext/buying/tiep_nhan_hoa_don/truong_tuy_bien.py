# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Trường tùy biến của Đợt 4: hợp đồng khung, tiếp nhận hóa đơn NCC (FRD-MAP-01, spec 2026-10-23).

Cùng nguyên tắc với BA12 / YC5: không sửa JSON DocType chuẩn. Trường thêm là Custom Field, tạo ở
mỗi lần migrate (`after_migrate`), chạy lại nhiều lần an toàn (`update=True`).
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from erpnext.buying.tiep_nhan_hoa_don.cau_hinh import TRUONG_BAT_BUOC_MAC_DINH, TRUONG_DONG_BAT_BUOC_MAC_DINH
from erpnext.buying.tiep_nhan_hoa_don.chuan_hoa import DONG_NGHIA_MAC_DINH

THUE_SUAT = "\n10%\n8%\n5%\n0%\nKCT"
CAI_DAT = "Supplier Invoice Intake Settings"


def _ro(**field):
	"""Ô do server ghi: chỉ đọc, không chép khi Duplicate/Amend, không in."""
	return {"read_only": 1, "no_copy": 1, "print_hide": 1, **field}


MUA = "eval:doc.blanket_order_type == 'Purchasing'"


def _lien_tiep(truoc, *fields, **chung):
	"""Gắn `insert_after` nối tiếp nhau, bắt đầu sau ô `truoc`."""
	out = []
	for f in fields:
		out.append({**chung, **f, "insert_after": truoc})
		truoc = f["fieldname"]
	return out


def _dong_hdk():
	"""Thông tin dòng hợp đồng khung (FRD 6.2, đặt ở dòng hợp đồng thay vì thẻ vật tư: D4-1), gồm các
	cột Mã hàng, Tên thương hiệu, Hãng, ĐVT, Đơn giá của hợp đồng nguyên tắc mẫu (Điều 2.1)."""
	return _lien_tiep(
		"party_item_code",
		{
			"fieldname": "ma_hang_ncc",
			"fieldtype": "Data",
			"label": "Mã hàng NCC theo hợp đồng",
			"description": "Trống: lấy mã hàng của NCC trên thẻ mặt hàng. Hóa đơn ghi mã này thì khớp tầng 1.",
		},
		{
			"fieldname": "ma_dong_hdk",
			"fieldtype": "Data",
			"label": "Mã dòng hợp đồng",
			"description": "Tự sinh [NCC]-[Mã hợp đồng]-[Nhóm hàng]-[STT] khi có Số hợp đồng; sửa được trước khi Nộp. Không trùng.",
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
		{
			"fieldname": "dvt_hdk",
			"fieldtype": "Link",
			"options": "UOM",
			"label": "ĐVT theo hợp đồng",
			"description": "Số lượng và đơn giá của dòng tính theo ĐVT này; phải là ĐVT kho của mặt hàng. Trống: ĐVT kho.",
		},
		{"fieldname": "thue_suat", "fieldtype": "Select", "options": THUE_SUAT, "label": "Thuế suất GTGT"},
		{
			"fieldname": "ghi_chu_gia",
			"fieldtype": "Small Text",
			"label": "Ghi chú giá",
			"description": "Ví dụ mức giá khác theo số lượng mỗi đơn (10 - 30 hộp/đơn: 3.812.500). Hệ thống chỉ dùng Đơn giá của dòng: hóa đơn theo giá khác bị cảnh báo lệch giá và cần duyệt.",
		},
		_ro(
			fieldname="da_lap_hoa_don",
			fieldtype="Float",
			label="Đã lập hóa đơn (ĐVT kho)",
			description="Lũy kế số lượng trên Hóa đơn mua đã Nộp của các Đơn mua gắn hợp đồng này.",
		),
	)


def _hop_dong():
	"""Khung chung của hợp đồng nguyên tắc, hợp đồng nào cũng có hoặc hệ thống cần dùng (D4-6, D4-13): mã
	hợp đồng trong mã dòng, phụ lục, tệp đã ký, giá gồm VAT, không cam kết số lượng, các bên ký. Điều
	khoản riêng của từng NCC không thành trường cố định: ghi ở mục Điều khoản và điều kiện chuẩn của
	ERPNext, lấy từ Mẫu điều khoản (Terms and Conditions) người dùng tự tạo. Chỉ hiện với loại mua."""
	return [
		{
			"fieldname": "bang_gia_mua",
			"fieldtype": "Link",
			"options": "Price List",
			"label": "Bảng giá mua",
			"description": "Nộp hợp đồng thì giá từng dòng được ghi vào bảng giá này (giá HĐ nguyên tắc dùng khi kiểm giá bán); hủy hợp đồng thì xóa. Trống: bảng giá mặc định của nhà cung cấp.",
			"depends_on": MUA,
			"insert_after": "supplier_name",
		},
		*_lien_tiep(
			"contract",
			{
				"fieldname": "ma_hop_dong",
				"fieldtype": "Data",
				"label": "Mã hợp đồng trong mã dòng",
				"description": "Phần [Mã hợp đồng] của mã dòng, nên ngắn (ví dụ 001GT). Trống: Số hợp đồng bỏ dấu và ký tự đặc biệt.",
			},
			{
				"fieldname": "hop_dong_goc",
				"fieldtype": "Link",
				"options": "Blanket Order",
				"label": "Phụ lục của hợp đồng",
				"description": "Hợp đồng đã Nộp không sửa được. Bổ sung mặt hàng hoặc đổi giá theo phụ lục: lập Đơn khung mới, chọn hợp đồng gốc ở đây. Giá trong phụ lục áp từ Từ ngày của phụ lục.",
			},
			{
				"fieldname": "so_phu_luc",
				"fieldtype": "Data",
				"label": "Số phụ lục",
				"depends_on": "hop_dong_goc",
			},
			{"fieldname": "tep_hop_dong", "fieldtype": "Attach", "label": "Tệp hợp đồng đã ký"},
			{
				"fieldname": "gia_gom_vat",
				"fieldtype": "Check",
				"label": "Đơn giá đã gồm thuế GTGT",
				"description": "Tích thì hệ thống quy đơn giá về giá chưa VAT theo Thuế suất của dòng (làm tròn đến đồng) khi ghi bảng giá mua, khi gắn Đơn mua và khi so với hóa đơn.",
			},
			{
				"fieldname": "khong_cam_ket_so_luong",
				"fieldtype": "Check",
				"label": "Không cam kết số lượng tối thiểu",
				"description": "Tích: dòng để Số lượng 0 là không giới hạn, không cảnh báo hay chặn hạn mức. Không tích: dòng nào cũng phải có số lượng (hạn mức).",
			},
			{
				"fieldname": "cac_ben_section",
				"fieldtype": "Section Break",
				"label": "Các bên ký hợp đồng",
				"description": "Ô trống được điền khi Lưu: Bên A theo công ty và hợp đồng gần nhất của công ty; Bên B theo thẻ NCC (MST, địa chỉ, tài khoản ngân hàng) và hợp đồng gần nhất của NCC.",
			},
			{"fieldname": "dai_dien_ben_a", "fieldtype": "Data", "label": "Đại diện Bên A (Miyano)"},
			{"fieldname": "chuc_vu_ben_a", "fieldtype": "Data", "label": "Chức vụ đại diện Bên A"},
			{
				"fieldname": "mst_ben_a",
				"fieldtype": "Data",
				"label": "MST Bên A",
				"fetch_from": "company.tax_id",
				"fetch_if_empty": 1,
			},
			{"fieldname": "dia_chi_ben_a", "fieldtype": "Small Text", "label": "Địa chỉ Bên A"},
			{"fieldname": "tai_khoan_ben_a", "fieldtype": "Data", "label": "Số tài khoản Bên A"},
			{"fieldname": "ngan_hang_ben_a", "fieldtype": "Data", "label": "Ngân hàng Bên A (mở tại)"},
			{"fieldname": "cac_ben_cb", "fieldtype": "Column Break"},
			{"fieldname": "dai_dien_ben_b", "fieldtype": "Data", "label": "Đại diện Bên B (NCC)"},
			{"fieldname": "chuc_vu_ben_b", "fieldtype": "Data", "label": "Chức vụ đại diện Bên B"},
			{
				"fieldname": "mst_ben_b",
				"fieldtype": "Data",
				"label": "MST Bên B",
				"fetch_from": "supplier.tax_id",
				"fetch_if_empty": 1,
			},
			{"fieldname": "dien_thoai_ben_b", "fieldtype": "Data", "label": "Điện thoại Bên B"},
			{"fieldname": "fax_ben_b", "fieldtype": "Data", "label": "Fax Bên B"},
			{"fieldname": "dia_chi_ben_b", "fieldtype": "Small Text", "label": "Địa chỉ Bên B"},
			{
				"fieldname": "tai_khoan_ben_b",
				"fieldtype": "Data",
				"label": "Số tài khoản Bên B",
				"description": "Tài khoản nhận thanh toán theo hợp đồng.",
			},
			{"fieldname": "ngan_hang_ben_b", "fieldtype": "Data", "label": "Ngân hàng Bên B (mở tại)"},
			depends_on=MUA,
		),
	]


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
	"Blanket Order": _hop_dong(),
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
		_ro(
			fieldname="hoa_don_dieu_chinh",
			fieldtype="Small Text",
			label="Hóa đơn điều chỉnh đã gộp",
			description="Hóa đơn này lập theo số sau điều chỉnh: hóa đơn gốc (Số hóa đơn NCC) cộng các hóa"
			" đơn điều chỉnh này.",
			depends_on="hoa_don_dieu_chinh",
			insert_after="phieu_tiep_nhan",
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


# Quyền trên Đơn khung: nhân viên mua hàng nhập bản nháp; giám đốc (Sales Manager, như kiểm giá bán
# Đợt 1 - 2) Nộp / Hủy / Sửa đổi / gia hạn Đến ngày (Frappe đòi quyền Nộp để sửa ô sau khi Nộp); kế
# toán và kho chỉ xem (người dùng chọn 24 - 25/10/2026). Chỉ dùng vai trò có sẵn; System Manager giữ
# quyền chuẩn của DocType.
NHAP_NHAP = ("read", "write", "create", "print", "email", "report", "share")
CHI_XEM = ("read", "print", "report")
QUYEN_DON_KHUNG = {
	"Sales Manager": (*NHAP_NHAP, "delete", "submit", "cancel", "amend", "export"),
	"Purchase Manager": NHAP_NHAP,
	"Purchase User": NHAP_NHAP,
	"Accounts Manager": CHI_XEM,
	"Accounts User": CHI_XEM,
	"Stock User": CHI_XEM,
}
VAI_TRO_GIAM_DOC = "Sales Manager"


def phan_quyen_don_khung():
	"""Lần đầu: chép quyền chuẩn của Blanket Order sang Custom DocPerm rồi thêm các dòng trên. Site đã
	tự chỉnh quyền Blanket Order (đã có Custom DocPerm) thì giữ nguyên, không ghi đè."""
	from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype
	from frappe.permissions import setup_custom_perms

	if frappe.db.exists("Custom DocPerm", {"parent": "Blanket Order"}):
		return
	setup_custom_perms("Blanket Order")
	for role, quyen in QUYEN_DON_KHUNG.items():
		if not frappe.db.exists("Role", role):
			continue
		frappe.get_doc(
			{
				"doctype": "Custom DocPerm",
				"parent": "Blanket Order",
				"parenttype": "DocType",
				"parentfield": "permissions",
				"role": role,
				"permlevel": 0,
				**{q: 1 for q in quyen},
			}
		).insert(ignore_permissions=True)
	validate_permissions_for_doctype("Blanket Order")
	frappe.clear_cache(doctype="Blanket Order")


def tao_truong_tuy_bien():
	"""Gọi từ `after_migrate`. Lần đầu (cài đặt chưa lưu) gieo giá trị mặc định và từ đồng nghĩa."""
	create_custom_fields(CUSTOM_FIELDS, update=True)
	phan_quyen_don_khung()
	if frappe.db.exists("DocType", CAI_DAT) and not frappe.db.get_single_value(
		CAI_DAT, "da_khoi_tao_truong_bat_buoc"
	):
		# Một lần: quản trị bỏ bớt / thêm trường ở Cài đặt thì migrate sau không ghi đè (D4-13).
		frappe.db.set_single_value(
			CAI_DAT,
			{
				"truong_bat_buoc_hdk": "\n".join(TRUONG_BAT_BUOC_MAC_DINH),
				"truong_bat_buoc_dong_hdk": "\n".join(TRUONG_DONG_BAT_BUOC_MAC_DINH),
				"da_khoi_tao_truong_bat_buoc": 1,
			},
		)
	if frappe.db.exists("DocType", CAI_DAT) and not frappe.db.get_single_value(CAI_DAT, "nguong_tu_dong"):
		s = frappe.get_single(CAI_DAT)
		s.update(
			{
				"bat_tiep_nhan": 1,
				"nguong_canh_bao_han_muc": 90,
				"vai_tro_duyet_lech_gia": VAI_TRO_GIAM_DOC,
				"vai_tro_duyet_anh_xa": VAI_TRO_GIAM_DOC,
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
