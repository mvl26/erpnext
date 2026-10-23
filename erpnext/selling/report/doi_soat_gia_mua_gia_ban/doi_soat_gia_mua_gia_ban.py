# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Đối soát giá mua - giá bán theo từng Sales Order (BA12 A08, D05).

Mỗi dòng là một dòng SO đã kiểm giá: SO, mặt hàng, NCC, nguồn giá, giá mua, hệ số, giá bán,
giá bảng giá, chênh lệch, lý do, số văn bản. Các giá trị lấy đúng như đã lưu lúc lập SO —
giá mua đổi sau đó không sửa SO (D05); phần chênh đó hiện ở cột "Giá mua hiện tại" /
"Giá mua đổi".

Q1: thêm người nhập và thời điểm nhập thông tin khách chấp thuận để kế toán hậu kiểm; cột
"Chấp thuận" cho biết dòng khác bảng giá đã đủ thông tin hay còn chờ (Q10).
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate

from erpnext.selling.kiem_gia.gia_goc import tim_gia_mua_nhieu


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	def c(fieldname, label, fieldtype="Data", width=110, options=None):
		col = {"fieldname": fieldname, "label": label, "fieldtype": fieldtype, "width": width}
		if options:
			col["options"] = options
		return col

	return [
		c("sales_order", _("Sales Order"), "Link", 140, "Sales Order"),
		c("transaction_date", _("Ngày SO"), "Date", 95),
		c("customer", _("Khách hàng"), "Link", 140, "Customer"),
		c("item_code", _("Mặt hàng"), "Link", 140, "Item"),
		c("item_name", _("Tên hàng"), "Data", 180),
		c("uom", _("ĐVT"), "Link", 70, "UOM"),
		c("qty", _("Số lượng"), "Float", 80),
		c("ncc", _("NCC"), "Link", 130, "Supplier"),
		c("nguon_gia_mua", _("Nguồn giá"), "Data", 110),
		c("chung_tu_gia_mua", _("Chứng từ giá mua"), "Data", 140),
		c("gia_mua", _("Giá mua"), "Currency", 110, "currency"),
		c("he_so", _("Hệ số"), "Float", 70),
		c("so_hop_dong", _("Số hợp đồng"), "Data", 110),
		c("gia_de_xuat", _("Giá đề xuất"), "Currency", 110, "currency"),
		c("gia_ban", _("Giá bán"), "Currency", 110, "currency"),
		c("chenh_lech", _("Chênh lệch"), "Currency", 100, "currency"),
		c("gia_bang_gia", _("Giá bảng giá"), "Currency", 110, "currency"),
		c("ngoai_bang_gia", _("Chưa có trong bảng giá"), "Check", 90),
		c("trang_thai_gia", _("Trạng thái"), "Data", 130),
		c("ly_do", _("Lý do"), "Data", 200),
		c("so_van_ban", _("Số văn bản"), "Data", 120),
		c("nguoi_dai_dien_kh", _("Người đại diện KH"), "Data", 130),
		c("ngay_chap_thuan", _("Ngày chấp thuận"), "Date", 100),
		c("tep_van_ban", _("Tệp văn bản"), "Data", 120),
		c("chap_thuan", _("Chấp thuận"), "Data", 120),
		c("nguoi_nhap_chap_thuan", _("Người nhập chấp thuận"), "Link", 140, "User"),
		c("thoi_diem_nhap_chap_thuan", _("Thời điểm nhập"), "Datetime", 150),
		c("gia_mua_hien_tai", _("Giá mua hiện tại"), "Currency", 120, "currency"),
		c("gia_mua_doi", _("Giá mua đổi"), "Currency", 100, "currency"),
		c("currency", _("Tiền tệ"), "Link", 60, "Currency"),
	]


def get_data(filters):
	conditions = ["ifnull(soi.trang_thai_gia, '') not in ('', 'Bỏ qua')"]
	conditions.append("so.docstatus = 1" if not cint(filters.get("gom_nhap")) else "so.docstatus < 2")
	values = {}
	for f, cond in (
		("from_date", "so.transaction_date >= %(from_date)s"),
		("to_date", "so.transaction_date <= %(to_date)s"),
		("customer", "so.customer = %(customer)s"),
		("company", "so.company = %(company)s"),
		("supplier", "soi.ncc_du_kien = %(supplier)s"),
		("item_code", "soi.item_code = %(item_code)s"),
	):
		if filters.get(f):
			conditions.append(cond)
			values[f] = filters[f]
	if cint(filters.get("chi_lech")):
		conditions.append(
			"(soi.trang_thai_gia not in ('Khớp', 'Đang trong thời hạn báo giá') or soi.khac_bang_gia = 1)"
		)
	if cint(filters.get("cho_chap_thuan")):
		conditions.append("soi.cho_chap_thuan = 1")

	rows = frappe.db.sql(
		f"""
		select so.name as sales_order, so.transaction_date, so.customer, so.company, so.currency,
			so.conversion_rate, so.ly_do_lech_gia as ly_do, soi.item_code, soi.item_name, soi.uom,
			soi.qty, soi.conversion_factor, soi.ncc_du_kien as ncc, soi.nguon_gia_mua,
			soi.chung_tu_gia_mua, soi.gia_mua, soi.he_so_gia_ban as he_so,
			soi.so_hop_dong_he_so as so_hop_dong, soi.gia_de_xuat, soi.rate as gia_ban,
			soi.chenh_lech_gia as chenh_lech, soi.gia_bang_gia, soi.ngoai_bang_gia,
			soi.khac_bang_gia, soi.cho_chap_thuan, soi.trang_thai_gia,
			soi.so_van_ban_gia as so_van_ban, soi.nguoi_dai_dien_kh,
			soi.ngay_chap_thuan_gia as ngay_chap_thuan, soi.tep_van_ban_gia as tep_van_ban,
			soi.nguoi_nhap_chap_thuan, soi.thoi_diem_nhap_chap_thuan
		from `tabSales Order` so
		join `tabSales Order Item` soi on soi.parent = so.name and soi.parenttype = 'Sales Order'
		where {" and ".join(conditions)}
		order by so.transaction_date desc, so.name, soi.idx
		""",
		values,
		as_dict=True,
	)
	for r in rows:
		if cint(r.ngoai_bang_gia):
			r.gia_bang_gia = None  # không phải giá 0: mặt hàng chưa có trong bảng giá KH (Q2)
		if cint(r.khac_bang_gia):
			r.chap_thuan = _("Chờ chấp thuận") if cint(r.cho_chap_thuan) else _("Đủ")
	_gia_mua_hien_tai(rows)
	return rows


def _gia_mua_hien_tai(rows):
	"""D05: giá mua tại hôm nay của cùng (mặt hàng, NCC), quy về ĐVT và tiền tệ của dòng."""
	theo_cty = {}
	for r in rows:
		if r.ncc:
			theo_cty.setdefault(r.company, set()).add((r.item_code, r.ncc))
	hien_tai = {}
	for company, cap in theo_cty.items():
		for key, kq in tim_gia_mua_nhieu(list(cap), nowdate(), company).items():
			hien_tai[(company, *key)] = kq
	for r in rows:
		kq = hien_tai.get((r.company, r.item_code, r.ncc))
		if not kq or kq.gia_kho is None:
			continue
		r.gia_mua_hien_tai = flt(
			flt(kq.gia_kho) * (flt(r.conversion_factor) or 1) / (flt(r.conversion_rate) or 1), 2
		)
		if r.gia_mua is not None:
			r.gia_mua_doi = flt(r.gia_mua_hien_tai - flt(r.gia_mua), 2)
