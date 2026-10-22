# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Theo dõi thông báo đổi giá (YC4; spec mục 6.2.6, 14 — tình huống T7, T12).

Mỗi dòng là một giá đã gửi thông báo trên bảng giá có báo trước: số ngày báo trước, thiếu
bao nhiêu ngày so với quy định, khách đã xác nhận chưa, và bao nhiêu Sales Order đã bán
theo giá đó. Mặc định chỉ hiện dòng Báo gấp — dòng cần xin khách xác nhận.
"""

import frappe
from frappe import _
from frappe.utils import cint


def execute(filters=None):
	return get_columns(), get_data(frappe._dict(filters or {}))


def get_columns():
	return [
		{
			"fieldname": "price_list",
			"label": _("Bảng giá"),
			"fieldtype": "Link",
			"options": "Price List",
			"width": 150,
		},
		{
			"fieldname": "item_code",
			"label": _("Mã hàng"),
			"fieldtype": "Link",
			"options": "Item",
			"width": 140,
		},
		{"fieldname": "item_name", "label": _("Tên hàng"), "fieldtype": "Data", "width": 200},
		{"fieldname": "uom", "label": _("ĐVT"), "fieldtype": "Link", "options": "UOM", "width": 70},
		{"fieldname": "price_list_rate", "label": _("Giá mới"), "fieldtype": "Float", "width": 110},
		{"fieldname": "valid_from", "label": _("Áp dụng từ"), "fieldtype": "Date", "width": 100},
		{"fieldname": "ngay_gui_thong_bao", "label": _("Ngày gửi"), "fieldtype": "Date", "width": 100},
		{"fieldname": "so_ngay_bao_truoc", "label": _("Báo trước (ngày)"), "fieldtype": "Int", "width": 90},
		{"fieldname": "thieu", "label": _("Thiếu (ngày)"), "fieldtype": "Int", "width": 80},
		{"fieldname": "bao_gap", "label": _("Báo gấp"), "fieldtype": "Check", "width": 70},
		{"fieldname": "trang_thai_thong_bao", "label": _("Trạng thái"), "fieldtype": "Data", "width": 100},
		{"fieldname": "ngay_xac_nhan", "label": _("Khách xác nhận"), "fieldtype": "Date", "width": 100},
		{"fieldname": "so_don", "label": _("Số SO đã bán theo giá"), "fieldtype": "Int", "width": 110},
		{"fieldname": "ly_do_bao_gap", "label": _("Lý do báo gấp"), "fieldtype": "Data", "width": 200},
		{
			"fieldname": "nguoi_gui_thong_bao",
			"label": _("Người gửi"),
			"fieldtype": "Link",
			"options": "User",
			"width": 150,
		},
		{
			"fieldname": "thong_bao",
			"label": _("Email"),
			"fieldtype": "Link",
			"options": "Communication",
			"width": 110,
		},
		{
			"fieldname": "name",
			"label": _("Dòng giá"),
			"fieldtype": "Link",
			"options": "Item Price",
			"width": 100,
		},
	]


def get_data(filters):
	conditions = ["pl.bao_truoc_khi_doi_gia = 1", "ip.trang_thai_thong_bao in ('Đã gửi', 'Đã xác nhận')"]
	values = {}
	if filters.get("price_list"):
		conditions.append("ip.price_list = %(price_list)s")
		values["price_list"] = filters.price_list
	if cint(filters.get("chi_bao_gap", 1)):
		conditions.append("ip.bao_gap = 1")
	if cint(filters.get("chua_xac_nhan")):
		conditions.append("ip.ngay_xac_nhan is null")
	if filters.get("tu_ngay"):
		conditions.append("ip.ngay_gui_thong_bao >= %(tu_ngay)s")
		values["tu_ngay"] = filters.tu_ngay
	if filters.get("den_ngay"):
		conditions.append("ip.ngay_gui_thong_bao <= %(den_ngay)s")
		values["den_ngay"] = filters.den_ngay

	rows = frappe.db.sql(
		f"""
		select ip.name, ip.price_list, ip.item_code, ip.item_name, ip.uom, ip.customer,
			ip.price_list_rate, ip.valid_from, ip.ngay_gui_thong_bao, ip.so_ngay_bao_truoc, ip.bao_gap,
			ip.trang_thai_thong_bao, ip.ngay_xac_nhan, ip.ly_do_bao_gap, ip.nguoi_gui_thong_bao,
			ip.thong_bao, pl.so_ngay_bao_truoc as so_ngay_quy_dinh
		from `tabItem Price` ip
		join `tabPrice List` pl on pl.name = ip.price_list
		where {" and ".join(conditions)}
		order by ip.ngay_gui_thong_bao desc, ip.item_code
		""",
		values,
		as_dict=True,
	)
	for r in rows:
		r.thieu = max(cint(r.so_ngay_quy_dinh) - cint(r.so_ngay_bao_truoc), 0)
		r.so_don = _so_don(r)
	return rows


def _so_don(r):
	"""SO đã Submit theo bảng giá này, mặt hàng này, ngày SO trong thời gian giá có hiệu lực
	(từ ngày áp dụng tới trước ngày áp dụng của giá kế tiếp)."""
	ke_tiep = frappe.db.sql(
		"""select min(valid_from) from `tabItem Price`
		where price_list = %s and item_code = %s and uom = %s and ifnull(customer, '') = %s
			and valid_from > %s""",
		(r.price_list, r.item_code, r.uom, r.customer or "", r.valid_from),
	)[0][0]
	return frappe.db.sql(
		f"""select count(distinct so.name) from `tabSales Order` so
		join `tabSales Order Item` soi on soi.parent = so.name
		where so.docstatus = 1 and so.selling_price_list = %s and soi.item_code = %s
			and so.transaction_date >= %s {"and so.transaction_date < %s" if ke_tiep else ""}""",
		(r.price_list, r.item_code, r.valid_from, *([ke_tiep] if ke_tiep else [])),
	)[0][0]
