"""Hàng đang nằm ở ô "Chưa xếp vị trí" — danh sách việc của thủ kho.

Báo cáo này biến việc bỏ sót khai vị trí thành HỮU HÌNH thay vì thành lỗi.
Không có nó thì ô CHUA-XEP âm thầm phình ra và không ai biết.
"""

import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	dieu_kien = ["sl.la_o_chua_xep = 1", "lb.so_luong != 0"]
	tham_so = {}

	if filters.get("kho"):
		dieu_kien.append("lb.kho = %(kho)s")
		tham_so["kho"] = filters["kho"]

	dong = frappe.db.sql(
		f"""
		select lb.o, lb.kho, lb.vat_tu, lb.so_lo, b.expiry_date, lb.so_luong
		from `tabLocation Balance` lb
		join `tabStorage Location` sl on sl.name = lb.o
		left join `tabBatch` b on b.name = lb.so_lo
		where {' and '.join(dieu_kien)}
		order by lb.kho asc, lb.vat_tu asc
		""",
		tham_so,
	)
	return _cot(), [list(d) for d in dong]


def _cot():
	return [
		{"label": _("Ô"), "fieldname": "o", "fieldtype": "Link", "options": "Storage Location", "width": 200},
		{"label": _("Kho"), "fieldname": "kho", "fieldtype": "Link", "options": "Warehouse", "width": 160},
		{"label": _("Mặt hàng"), "fieldname": "vat_tu", "fieldtype": "Link", "options": "Item", "width": 220},
		{"label": _("Số lô"), "fieldname": "so_lo", "fieldtype": "Link", "options": "Batch", "width": 170},
		{"label": _("Hạn dùng"), "fieldname": "expiry_date", "fieldtype": "Date", "width": 110},
		{"label": _("Số lượng"), "fieldname": "so_luong", "fieldtype": "Float", "width": 110},
	]
