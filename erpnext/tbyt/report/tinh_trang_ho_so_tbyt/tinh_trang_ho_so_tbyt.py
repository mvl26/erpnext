# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tình trạng hồ sơ pháp lý TBYT theo từng mặt hàng.

Đã chốt hệ thống KHÔNG chặn nghiệp vụ khi thiếu chứng từ, nên báo cáo này là cơ
chế kiểm soát duy nhất còn lại — nó phải nói đủ, kể cả phần mà trạng thái trên
Item cố ý bỏ qua (chứng từ cấp lô).
"""

import frappe
from frappe import _

from erpnext.tbyt.constants import (
	DOC_STATUS_EXPIRED,
	ITEM_STATUS_OK,
	LEVEL_BB,
	LEVEL_BB_STAR,
	LEVEL_NC,
)
from erpnext.tbyt.resolver import get_item_documents
from erpnext.tbyt.status import get_item_status

BATCH_REQUIRED = ("cq_chung_nhan_chat_luong", "co_chung_nhan_xuat_xu")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"fieldname": "item_code",
			"label": _("Mặt hàng"),
			"fieldtype": "Link",
			"options": "Item",
			"width": 180,
		},
		{"fieldname": "item_name", "label": _("Tên hàng"), "fieldtype": "Data", "width": 200},
		{
			"fieldname": "item_group",
			"label": _("Nhóm"),
			"fieldtype": "Link",
			"options": "Item Group",
			"width": 140,
		},
		{
			"fieldname": "so_luu_hanh",
			"label": _("Số lưu hành"),
			"fieldtype": "Link",
			"options": "TBYT Marketing Authorization",
			"width": 150,
		},
		{"fieldname": "phan_loai_tbyt", "label": _("Phân loại"), "fieldtype": "Data", "width": 80},
		{"fieldname": "trang_thai_slh", "label": _("Trạng thái SLH"), "fieldtype": "Data", "width": 130},
		{"fieldname": "tinh_trang_ho_so", "label": _("Tình trạng hồ sơ"), "fieldtype": "Data", "width": 170},
		{"fieldname": "bb_thieu", "label": _("BB thiếu"), "fieldtype": "Int", "width": 90},
		{"fieldname": "bb_star_thieu", "label": _("BB* thiếu"), "fieldtype": "Int", "width": 90},
		{"fieldname": "nc_thieu", "label": _("NC thiếu"), "fieldtype": "Int", "width": 90},
		{"fieldname": "chung_tu_het_han", "label": _("Hết hạn"), "fieldtype": "Int", "width": 80},
		{
			"fieldname": "ngay_het_han_gan_nhat",
			"label": _("Hết hạn gần nhất"),
			"fieldtype": "Date",
			"width": 130,
		},
		{"fieldname": "ho_so_lo", "label": _("Hồ sơ cấp lô"), "fieldtype": "Data", "width": 130},
	]


def get_data(filters):
	# `phan_loai_tbyt` trên Item là fetch_from, chỉ đồng bộ lại khi Item được
	# lưu — sửa phân loại trên Authorization không tự đẩy xuống Item. Vì vậy
	# không lọc bằng cột đó: đọc `phan_loai` sống từ Authorization bên dưới,
	# giống hệt cách `chu_so_huu` đã được áp dụng hậu truy vấn.
	item_filters = {"la_thiet_bi_y_te": 1}
	if filters.get("item_group"):
		item_filters["item_group"] = filters.item_group

	items = frappe.get_all(
		"Item",
		filters=item_filters,
		fields=["name", "item_name", "item_group", "so_luu_hanh"],
		order_by="name",
	)

	owner_filter = filters.get("chu_so_huu")
	class_filter = filters.get("phan_loai")
	rows = []
	for item in items:
		auth = (
			frappe.db.get_value(
				"TBYT Marketing Authorization",
				item.so_luu_hanh,
				["chu_so_huu", "trang_thai", "phan_loai"],
				as_dict=True,
			)
			if item.so_luu_hanh
			else None
		)
		if owner_filter and (not auth or auth.chu_so_huu != owner_filter):
			continue
		if class_filter and (not auth or auth.phan_loai != class_filter):
			continue

		documents = get_item_documents(item.name)
		missing = _count_missing(documents)
		expired = [d for d in documents if d["document"] and d["trang_thai"] == DOC_STATUS_EXPIRED]
		horizon = _nearest_expiry(documents)
		# Truyền lại bộ chứng từ vừa phân giải: báo cáo chạy trên cả nghìn mặt
		# hàng, để `get_item_status` tự phân giải lần hai là nhân đôi toàn bộ.
		status = get_item_status(item.name, documents=documents)
		batch_label, batch_complete = _batch_coverage(item.name)

		# Trạng thái Item cố ý bỏ qua chứng từ cấp lô (CQ, CO), nên "đủ hồ sơ
		# mặt hàng" không có nghĩa là đủ hồ sơ thật sự — phải xét cả batch_complete,
		# nếu không bộ lọc mặc định sẽ giấu đúng khoảng trống mà cột này sinh ra
		# để phơi bày.
		if filters.get("chi_hien_thieu") and status == ITEM_STATUS_OK and batch_complete:
			continue

		rows.append(
			{
				"item_code": item.name,
				"item_name": item.item_name,
				"item_group": item.item_group,
				"so_luu_hanh": item.so_luu_hanh,
				"phan_loai_tbyt": auth.phan_loai if auth else None,
				"trang_thai_slh": auth.trang_thai if auth else None,
				"tinh_trang_ho_so": status,
				"bb_thieu": missing[LEVEL_BB],
				"bb_star_thieu": missing[LEVEL_BB_STAR],
				"nc_thieu": missing[LEVEL_NC],
				"chung_tu_het_han": len(expired),
				"ngay_het_han_gan_nhat": horizon,
				"ho_so_lo": batch_label,
			}
		)
	return rows


def _count_missing(documents):
	counts = {LEVEL_BB: 0, LEVEL_BB_STAR: 0, LEVEL_NC: 0}
	for row in documents:
		if row["document"]:
			continue
		if row["level"] == LEVEL_BB_STAR and not row["is_required"]:
			continue
		if row["level"] in counts:
			counts[row["level"]] += 1
	return counts


def _nearest_expiry(documents):
	dates = [
		row["ngay_het_han"]
		for row in documents
		if row["document"] and not row["khong_thoi_han"] and row["ngay_het_han"]
	]
	return min(dates) if dates else None


def _batch_coverage(item_code: str) -> tuple[str, bool]:
	"""CQ và CO theo từng lô — phần mà trạng thái trên Item cố ý không xét.

	Trả về `("3/4 lô", False)` nghĩa là 3 trên 4 lô còn tồn đã đủ cả CQ lẫn CO
	— cờ thứ hai là False vì vẫn còn lô thiếu. Không có lô nào thì coi là đủ
	(`True`): không có gì để thiếu, đúng lý do trạng thái Item bỏ qua cấp lô.
	"""
	batches = frappe.get_all("Batch", filters={"item": item_code, "disabled": 0}, pluck="name")
	if not batches:
		return _("Chưa có lô"), True

	covered = 0
	for batch in batches:
		found = frappe.db.sql(
			"""
			select count(distinct rd.document_type)
			from `tabTBYT Regulatory Document` rd
			inner join `tabTBYT Document Scope` sc on sc.parent = rd.name
			where rd.is_active = 1
				and rd.document_type in %(types)s
				and sc.parenttype = 'TBYT Regulatory Document'
				and sc.scope_doctype = 'Batch'
				and sc.scope_name = %(batch)s
			""",
			{"types": BATCH_REQUIRED, "batch": batch},
		)[0][0]
		if found == len(BATCH_REQUIRED):
			covered += 1

	label = f"{covered}/{len(batches)} " + _("lô")
	return label, covered == len(batches)
