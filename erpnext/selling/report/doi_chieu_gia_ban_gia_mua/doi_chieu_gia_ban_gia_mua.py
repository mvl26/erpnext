# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Đối chiếu bảng giá bán với giá mua x hệ số khách hàng (BA12 R02, R03).

Chỉ đọc. Dùng để rà và làm sạch bảng giá của khách (ví dụ "Bảng giá Himedic") trước khi
bật kiểm giá. Mỗi dòng là giá đang hiệu lực tại ngày chọn của một (mặt hàng, ĐVT, khách)
trong bảng giá bán, giống cách ERPNext chọn giá cho chứng từ: dòng có `valid_from` mới
nhất mà không sau ngày đó. Giá mua lấy theo D07 (báo giá đợt, rồi HĐ nguyên tắc) của NCC
mặc định; hệ số của khách chọn ở bộ lọc (mặc định: khách dùng bảng giá này làm bảng giá
mặc định). Theo từng Sales Order: báo cáo "Doi Soat Gia Mua Gia Ban" (A08).
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from erpnext.selling.kiem_gia.cau_hinh import he_so_ap_dung
from erpnext.selling.kiem_gia.gia_goc import (
	CHUA_CO_GIA_MUA,
	KHOP,
	he_so_quy_doi,
	ncc_mac_dinh,
	so_sanh,
	tim_gia_mua_nhieu,
	tinh_gia_de_xuat,
)

KHONG_CO_HE_SO = "Khách không có hệ số"


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
		{"fieldname": "gia_ban", "label": _("Giá bảng giá"), "fieldtype": "Float", "width": 120},
		{"fieldname": "ngay_gia_ban", "label": _("Hiệu lực giá bán"), "fieldtype": "Date", "width": 110},
		{"fieldname": "ncc", "label": _("NCC"), "fieldtype": "Link", "options": "Supplier", "width": 130},
		{"fieldname": "nguon_gia_mua", "label": _("Nguồn giá mua"), "fieldtype": "Data", "width": 110},
		{"fieldname": "chung_tu_gia_mua", "label": _("Chứng từ giá mua"), "fieldtype": "Data", "width": 140},
		{"fieldname": "gia_mua", "label": _("Giá mua (theo ĐVT)"), "fieldtype": "Float", "width": 130},
		{"fieldname": "he_so", "label": _("Hệ số"), "fieldtype": "Float", "precision": 4, "width": 80},
		{"fieldname": "gia_de_xuat", "label": _("Giá đề xuất"), "fieldtype": "Float", "width": 120},
		{"fieldname": "chenh_lech", "label": _("Chênh lệch"), "fieldtype": "Float", "width": 110},
		{"fieldname": "trang_thai", "label": _("Trạng thái"), "fieldtype": "Data", "width": 160},
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
	# Ô hệ số để trống: theo hệ số của khách (R01). Có nhập: áp một hệ số cho mọi dòng (để
	# thử "nếu hệ số là ...").
	he_so_co_dinh = flt(filters.he_so) if filters.get("he_so") not in (None, "", 0) else None
	khach_mac_dinh = filters.get("customer") or frappe.db.get_value(
		"Customer", {"default_price_list": filters.price_list, "disabled": 0}, "name"
	)

	gia_ban = _gia_ban_hieu_luc(filters, ngay)
	if not gia_ban:
		return []

	item_codes = list({r.item_code for r in gia_ban})
	ncc = ncc_mac_dinh(item_codes)
	gia_mua = tim_gia_mua_nhieu([(c, ncc.get(c)) for c in item_codes], ngay, filters.get("company"))
	quy_doi = he_so_quy_doi(item_codes, {r.uom for r in gia_ban})
	he_so_theo_khach = {
		khach: he_so_ap_dung(khach, item_codes, ngay)
		for khach in {r.customer or khach_mac_dinh for r in gia_ban}
	}

	data = []
	for r in gia_ban:
		mua = gia_mua[(r.item_code, ncc.get(r.item_code))]
		khach = r.customer or khach_mac_dinh
		row = frappe._dict(
			item_code=r.item_code,
			item_name=r.item_name,
			uom=r.uom,
			customer=khach,
			gia_ban=flt(r.price_list_rate),
			ngay_gia_ban=r.valid_from,
			item_price=r.name,
			ncc=ncc.get(r.item_code),
			nguon_gia_mua=mua.nguon,
			chung_tu_gia_mua=mua.chung_tu,
			ly_do=mua.ly_do,
		)
		cf = 1 if r.uom == r.stock_uom else quy_doi.get((r.item_code, r.uom))
		hs = he_so_theo_khach[khach].get(r.item_code) if khach else None
		he_so = he_so_co_dinh if he_so_co_dinh is not None else (hs.he_so if hs else None)
		if he_so is None:
			row.trang_thai = KHONG_CO_HE_SO
		elif mua.gia_kho is None or not cf:
			row.trang_thai = CHUA_CO_GIA_MUA
			if mua.gia_kho is not None:
				row.ly_do = _("ĐVT {0} chưa khai hệ số quy đổi trên mặt hàng").format(r.uom)
		else:
			row.gia_mua = flt(mua.gia_kho * cf, 2)
			row.he_so = he_so
			row.gia_de_xuat = tinh_gia_de_xuat(mua.gia_kho * cf, he_so)
			row.chenh_lech, row.trang_thai = so_sanh(row.gia_ban, row.gia_de_xuat)

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
