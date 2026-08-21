# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Phân giải bộ chứng từ pháp lý của một Item.

Nguyên tắc: KHÔNG sao chép. Một tờ giấy nằm ở đúng cấp của nó — công ty, chủ sở
hữu, số lưu hành, hay chính mặt hàng — và Item đi ngược chuỗi để nhặt về. Nhờ
vậy gia hạn một tờ CFS là sửa một bản ghi, không phải sửa từng SKU.
"""

import frappe
from frappe.utils import cint

from erpnext.tbyt.constants import (
	LEVEL_BB,
	LEVEL_BB_STAR,
	LEVEL_NA,
	LEVEL_TH,
	SCOPE_AUTHORIZATION,
	SCOPE_COMPANY,
	SCOPE_DOCTYPE,
	SCOPE_ITEM,
	SCOPE_OWNER,
)
from erpnext.tbyt.doctype.tbyt_marketing_authorization.tbyt_marketing_authorization import (
	get_condition_context,
)

# Bốn cấp mà một Item phân giải được. Cấp Lô kiểm ở Batch (item chưa có lô thì
# không có gì để thiếu); cấp Giao dịch dùng đính kèm sẵn có của chứng từ bán hàng.
ITEM_SCOPES = (SCOPE_COMPANY, SCOPE_OWNER, SCOPE_AUTHORIZATION, SCOPE_ITEM)


def get_item_documents(item_code: str) -> list[dict]:
	"""Trả về bộ chứng từ đã phân giải của một Item.

	Danh sách rỗng nếu mặt hàng không phải TBYT hoặc chưa gắn số lưu hành.
	"""
	item = frappe.db.get_value("Item", item_code, ["name", "la_thiet_bi_y_te", "so_luu_hanh"], as_dict=True)
	if not item or not cint(item.la_thiet_bi_y_te) or not item.so_luu_hanh:
		return []

	auth = frappe.db.get_value(
		"TBYT Marketing Authorization",
		item.so_luu_hanh,
		["name", "phan_loai", "chu_so_huu"],
		as_dict=True,
	)
	if not auth or not auth.phan_loai:
		return []

	context = get_condition_context(auth.name)
	scope_values = get_scope_values(item_code)

	rows = []
	for doc_type in _document_types():
		if doc_type.scope_level not in ITEM_SCOPES:
			continue

		level, condition = _rule_for(doc_type.name, auth.phan_loai)
		if not level or level == LEVEL_NA:
			continue

		record = _find_document(
			doc_type.name,
			SCOPE_DOCTYPE[doc_type.scope_level],
			scope_values.get(doc_type.scope_level),
		)

		# TH không bao giờ tính là thiếu, nhưng đã tải lên thì phải hiện ra và
		# phải được theo dõi hạn — nếu ẩn đi thì tải lên coi như mất.
		if level == LEVEL_TH and not record:
			continue

		rows.append(
			{
				"document_key": doc_type.name,
				"document_name": doc_type.document_name,
				"short_code": doc_type.short_code,
				"scope_level": doc_type.scope_level,
				"level": level,
				"is_required": _is_required(level, condition, context),
				"is_supplementary": level == LEVEL_TH,
				"document": record.name if record else None,
				"so_hieu": record.so_hieu if record else None,
				"ngay_cap": record.ngay_cap if record else None,
				"ngay_het_han": record.ngay_het_han if record else None,
				"khong_thoi_han": cint(record.khong_thoi_han) if record else 0,
				"trang_thai": record.trang_thai if record else None,
				"file": record.file if record else None,
			}
		)
	return rows


def get_scope_values(item_code: str) -> dict:
	"""Đối tượng cụ thể của Item ở từng cấp phạm vi."""
	import erpnext

	item = frappe.db.get_value("Item", item_code, ["name", "so_luu_hanh"], as_dict=True)
	if not item:
		return {}

	owner = None
	if item.so_luu_hanh:
		owner = frappe.db.get_value("TBYT Marketing Authorization", item.so_luu_hanh, "chu_so_huu")

	return {
		SCOPE_COMPANY: erpnext.get_default_company(),
		SCOPE_OWNER: owner,
		SCOPE_AUTHORIZATION: item.so_luu_hanh,
		SCOPE_ITEM: item.name,
	}


def find_items_for_scope(scope_doctype: str, scope_name: str) -> list[str]:
	"""Những Item bị ảnh hưởng khi một chứng từ ở phạm vi này thay đổi.

	Dùng cho việc làm mới trạng thái (Task 11) — một tờ giấy cấp chủ sở hữu có
	thể chạm rất nhiều mặt hàng.
	"""
	if scope_doctype == "Item":
		return [scope_name]

	if scope_doctype == "TBYT Marketing Authorization":
		return frappe.get_all(
			"Item", filters={"so_luu_hanh": scope_name, "la_thiet_bi_y_te": 1}, pluck="name"
		)

	if scope_doctype == "Manufacturer":
		auths = frappe.get_all(
			"TBYT Marketing Authorization", filters={"chu_so_huu": scope_name}, pluck="name"
		)
		if not auths:
			return []
		return frappe.get_all(
			"Item",
			filters={"so_luu_hanh": ("in", auths), "la_thiet_bi_y_te": 1},
			pluck="name",
		)

	if scope_doctype == "Company":
		return frappe.get_all("Item", filters={"la_thiet_bi_y_te": 1}, pluck="name")

	return []


def _document_types():
	return frappe.get_all(
		"TBYT Document Type",
		fields=["name", "document_name", "short_code", "scope_level"],
		order_by="name",
	)


def _rule_for(document_key: str, device_class: str):
	row = frappe.db.get_value(
		"TBYT Document Rule",
		{
			"parent": document_key,
			"parenttype": "TBYT Document Type",
			"device_class": device_class,
		},
		["level", "condition"],
		as_dict=True,
	)
	if not row:
		return None, None
	return row.level, row.condition


def _is_required(level: str, condition: str | None, context: dict) -> bool:
	if level == LEVEL_BB:
		return True
	if level != LEVEL_BB_STAR:
		return False
	if not condition:
		return True
	return bool(frappe.safe_eval(condition, None, dict(context)))


def _find_document(document_key: str, scope_doctype: str, scope_name: str | None):
	"""Bản ghi còn hiệu lực của loại này phủ đúng đối tượng này.

	Chặn trùng ở Task 6 bảo đảm nhiều nhất một bản ghi khớp, nên `limit 1` là
	tất định chứ không phải chọn bừa.
	"""
	if not scope_name:
		return None

	rows = frappe.db.sql(
		"""
		select rd.name, rd.so_hieu, rd.ngay_cap, rd.ngay_het_han,
			rd.khong_thoi_han, rd.trang_thai, rd.file
		from `tabTBYT Regulatory Document` rd
		inner join `tabTBYT Document Scope` sc on sc.parent = rd.name
		where rd.document_type = %(document_type)s
			and rd.is_active = 1
			and sc.parenttype = 'TBYT Regulatory Document'
			and sc.scope_doctype = %(scope_doctype)s
			and sc.scope_name = %(scope_name)s
		limit 1
		""",
		{
			"document_type": document_key,
			"scope_doctype": scope_doctype,
			"scope_name": scope_name,
		},
		as_dict=True,
	)
	return rows[0] if rows else None
