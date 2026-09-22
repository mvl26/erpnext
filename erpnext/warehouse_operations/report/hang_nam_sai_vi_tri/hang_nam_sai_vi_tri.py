"""Ô đang chứa hàng KHÁC với mặt hàng đã gán cho nhánh của nó.

Báo cáo RỖNG = trạng thái đúng.

Vì sao phải có: `ItemLocationPreference.kiem_tra_ton_mat_hang_khac` chỉ chặn
LÚC GÁN. Sau đó hàng vẫn vào sai ô được — phiếu xếp khai tay, đường huỷ chứng
từ (`hook_sle.dao_theo_o_goc`), kiểm kê. Một bất biến chỉ kiểm ở một thời điểm
rồi không ai soi lại là bất biến sẽ mục trong im lặng, và đối soát §3
(`doi_soat.py`) KHÔNG thay thế được: nó chỉ so TỔNG tồn vị trí với tồn kho
ERPNext, nên một ô chứa nhầm mặt hàng vẫn khớp tuyệt đối.
"""

import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	# NHIỀU VỊ TRÍ (22/09/2026): bản gán giữ nhiều dòng (`Item Location Preference
	# Row`), `r.parent` là mã mặt hàng. Một ô chỉ nằm trong nhánh của TỐI ĐA một
	# mặt hàng (luật chồng lấn lúc gán), nên "ô chứa hàng khác với chủ nhánh" vẫn
	# là định nghĩa đủ — hàng của A nằm ở nhánh thứ hai của chính A không bao giờ bị
	# báo, vì chủ nhánh đó cũng là A.
	dieu_kien = ["lb.so_luong != 0", "r.parent != lb.vat_tu"]
	tham_so = {}
	if filters.get("kho"):
		dieu_kien.append("lb.kho = %(kho)s")
		tham_so["kho"] = filters["kho"]

	dong = frappe.db.sql(
		f"""
		select lb.o, ifnull(sl.ma_in_nhan, sl.name) as ma_in_nhan,
		       lb.vat_tu as vat_tu_dang_co, nullif(lb.so_lo, '') as so_lo,
		       lb.so_luong, r.parent as vat_tu_da_gan, r.vi_tri as nut_gan
		from `tabLocation Balance` lb
		join `tabStorage Location` sl on sl.name = lb.o
		join `tabStorage Location` s2 on s2.lft <= sl.lft and s2.rgt >= sl.rgt
		join `tabItem Location Preference Row` r
		  on r.vi_tri = s2.name and r.parenttype = 'Item Location Preference'
		where {' and '.join(dieu_kien)}
		  and sl.lft > 0
		order by sl.lft asc, lb.vat_tu asc
		""",
		tham_so,
	)
	return _cot(), [list(d) for d in dong]


def _cot():
	return [
		{"label": _("Ô"), "fieldname": "o", "fieldtype": "Link",
		 "options": "Storage Location", "width": 160},
		{"label": _("Mã trên nhãn"), "fieldname": "ma_in_nhan", "fieldtype": "Data", "width": 130},
		{"label": _("Mặt hàng đang nằm"), "fieldname": "vat_tu_dang_co", "fieldtype": "Link",
		 "options": "Item", "width": 200},
		{"label": _("Số lô"), "fieldname": "so_lo", "fieldtype": "Link",
		 "options": "Batch", "width": 150},
		{"label": _("Số lượng"), "fieldname": "so_luong", "fieldtype": "Float", "width": 100},
		{"label": _("Đã gán cho"), "fieldname": "vat_tu_da_gan", "fieldtype": "Link",
		 "options": "Item", "width": 200},
		{"label": _("Nút gán"), "fieldname": "nut_gan", "fieldtype": "Link",
		 "options": "Storage Location", "width": 130},
	]
