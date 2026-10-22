# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Đối chiếu giá trong một bảng giá bán với giá mua x (1 + % lãi).

Chỉ đọc. Dùng để rà và làm sạch bảng giá (ví dụ "Bảng giá Himedic") trước khi bật
kiểm giá trên Quotation/SO — thiết kế mục 13, bước 1.2. Mỗi dòng là giá đang hiệu lực
tại ngày chọn của một (mặt hàng, ĐVT, khách) trong bảng giá bán, giống cách ERPNext
chọn giá cho chứng từ: dòng có `valid_from` mới nhất mà không sau ngày đó.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from erpnext.selling.kiem_gia.cau_hinh import ty_le_lai_nhieu
from erpnext.selling.kiem_gia.gia_goc import (
	CHUA_XAC_DINH,
	KHOP,
	he_so_quy_doi,
	so_sanh,
	tim_gia_goc_nhieu,
	tinh_gia_chuan,
)
from erpnext.selling.kiem_gia.kiem_chung_tu import BO_QUA


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.get("price_list"):
		frappe.throw(_("Chọn bảng giá bán"))
	company = filters.get("company") or frappe.defaults.get_user_default("Company")
	pl_currency = frappe.get_cached_value("Price List", filters.price_list, "currency")
	company_currency = frappe.get_cached_value("Company", company, "default_currency") if company else None
	if company_currency and pl_currency != company_currency:
		frappe.throw(
			_("Bảng giá {0} dùng {1}; báo cáo chỉ so được bảng giá bằng tiền tệ công ty ({2}).").format(
				filters.price_list, pl_currency, company_currency
			)
		)
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"fieldname": "item_code",
			"label": _("Mã hàng"),
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{"fieldname": "item_name", "label": _("Tên hàng"), "fieldtype": "Data", "width": 220},
		{"fieldname": "uom", "label": _("ĐVT"), "fieldtype": "Link", "options": "UOM", "width": 70},
		{
			"fieldname": "customer",
			"label": _("Khách"),
			"fieldtype": "Link",
			"options": "Customer",
			"width": 120,
		},
		{"fieldname": "gia_ban", "label": _("Giá bán"), "fieldtype": "Float", "width": 120},
		{"fieldname": "ngay_gia_ban", "label": _("Hiệu lực giá bán"), "fieldtype": "Date", "width": 110},
		{"fieldname": "gia_goc", "label": _("Giá gốc (theo ĐVT)"), "fieldtype": "Float", "width": 130},
		{"fieldname": "ty_le_lai", "label": _("% lãi áp dụng"), "fieldtype": "Percent", "width": 90},
		{"fieldname": "gia_chuan", "label": _("Giá chuẩn"), "fieldtype": "Float", "width": 120},
		{"fieldname": "chenh_lech", "label": _("Chênh lệch"), "fieldtype": "Float", "width": 110},
		{"fieldname": "ty_le_lai_thuc", "label": _("% lãi thực"), "fieldtype": "Percent", "width": 90},
		{"fieldname": "trang_thai", "label": _("Trạng thái"), "fieldtype": "Data", "width": 160},
		{
			"fieldname": "nguon_gia_goc",
			"label": _("Dòng giá mua"),
			"fieldtype": "Link",
			"options": "Item Price",
			"width": 110,
		},
		{
			"fieldname": "bang_gia_mua",
			"label": _("Bảng giá mua"),
			"fieldtype": "Link",
			"options": "Price List",
			"width": 150,
		},
		{"fieldname": "ncc", "label": _("NCC"), "fieldtype": "Link", "options": "Supplier", "width": 130},
		{"fieldname": "ngay_gia_mua", "label": _("Hiệu lực giá mua"), "fieldtype": "Date", "width": 110},
		{"fieldname": "ly_do", "label": _("Ghi chú"), "fieldtype": "Data", "width": 300},
		{
			"fieldname": "item_price",
			"label": _("Dòng giá bán"),
			"fieldtype": "Link",
			"options": "Item Price",
			"width": 110,
		},
	]


def get_data(filters):
	ngay = getdate(filters.get("ngay") or nowdate())
	# Ô % lãi để trống: theo cấu hình (mặc định, % của khách, % theo khách - mặt hàng) như
	# khi kiểm trên chứng từ. Có nhập: áp một % cho mọi dòng (để thử "nếu % là ...").
	ty_le_co_dinh = flt(filters.ty_le_lai) if filters.get("ty_le_lai") not in (None, "") else None
	precision = frappe.get_precision("Item Price", "price_list_rate")

	gia_ban = _gia_ban_hieu_luc(filters, ngay)
	if not gia_ban:
		return []

	item_codes = list({r.item_code for r in gia_ban})
	gia_goc = tim_gia_goc_nhieu(item_codes, ngay, filters.get("company"))
	he_so = he_so_quy_doi(item_codes, {r.uom for r in gia_ban})
	ty_le_theo_khach = {
		khach: ty_le_lai_nhieu(khach, item_codes) for khach in {r.customer or None for r in gia_ban}
	}

	data = []
	for r in gia_ban:
		goc = gia_goc[r.item_code]
		row = frappe._dict(
			item_code=r.item_code,
			item_name=r.item_name,
			uom=r.uom,
			customer=r.customer,
			gia_ban=flt(r.price_list_rate),
			ngay_gia_ban=r.valid_from,
			item_price=r.name,
			nguon_gia_goc=goc.item_price,
			bang_gia_mua=goc.price_list,
			ncc=goc.supplier,
			ngay_gia_mua=goc.valid_from,
			ly_do=goc.ly_do,
		)
		cf = 1 if r.uom == r.stock_uom else he_so.get((r.item_code, r.uom))
		ty_le = ty_le_theo_khach[r.customer or None][r.item_code]
		if ty_le_co_dinh is None and not ty_le.kiem:
			row.trang_thai, row.ly_do = BO_QUA, ty_le.nguon
		elif goc.gia_goc is None or not cf:
			row.trang_thai = CHUA_XAC_DINH
			if goc.gia_goc is not None:
				row.ly_do = _("ĐVT {0} chưa khai hệ số quy đổi trên mặt hàng").format(r.uom)
		else:
			row.gia_goc = flt(goc.gia_goc * cf, precision)
			row.ty_le_lai = ty_le.ty_le_lai if ty_le_co_dinh is None else ty_le_co_dinh
			row.gia_chuan = tinh_gia_chuan(goc.gia_goc, cf, row.ty_le_lai, precision)
			row.chenh_lech, row.trang_thai = so_sanh(row.gia_ban, row.gia_chuan, precision)
			if row.gia_goc:
				row.ty_le_lai_thuc = flt((row.gia_ban / row.gia_goc - 1) * 100, 2)

		if filters.get("chi_hien_lech") and row.trang_thai == KHOP:
			continue
		data.append(row)

	return sorted(data, key=lambda d: (d.trang_thai == KHOP, d.item_code, d.uom, d.customer or ""))


def _gia_ban_hieu_luc(filters, ngay):
	"""Giá đang hiệu lực tại `ngay` của mỗi (mặt hàng, ĐVT, khách) trong bảng giá bán."""
	conditions = ["ip.price_list = %(price_list)s", "IFNULL(ip.batch_no, '') = ''"]
	values = {"price_list": filters.price_list, "ngay": ngay}
	if filters.get("item_group"):
		conditions.append("i.item_group = %(item_group)s")
		values["item_group"] = filters.item_group

	rows = frappe.db.sql(
		f"""
		SELECT ip.name, ip.item_code, i.item_name, i.stock_uom, ip.uom, ip.customer,
			ip.price_list_rate, IFNULL(ip.valid_from, '2000-01-01') AS valid_from, ip.modified
		FROM `tabItem Price` ip
		JOIN `tabItem` i ON i.name = ip.item_code
		WHERE {" AND ".join(conditions)}
			AND IFNULL(ip.valid_from, '2000-01-01') <= %(ngay)s
			AND (ip.valid_upto IS NULL OR ip.valid_upto >= %(ngay)s)
		""",
		values,
		as_dict=True,
	)

	hien_hanh = {}
	for r in rows:
		r.valid_from = getdate(r.valid_from)
		key = (r.item_code, r.uom, r.customer or "")
		cur = hien_hanh.get(key)
		if not cur or (r.valid_from, r.modified) > (cur.valid_from, cur.modified):
			hien_hanh[key] = r
	return list(hien_hanh.values())
