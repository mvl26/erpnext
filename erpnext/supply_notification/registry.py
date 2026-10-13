# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tra nhanh "chứng từ này có điểm thông báo nào không".

Bộ máy nối vào `doc_events["*"]` nên hàm này chạy ở **mọi** lần lưu của **mọi**
DocType. Vì vậy câu trả lời phải lấy từ cache chứ không phải từ một truy vấn
(yêu cầu NF1: ≤ 5 ms, DocType không có điểm thì không truy vấn gì thêm).

Cache tự dựng lại khi ai đó sửa điểm, nhóm người nhận, mẫu dùng chung hay cài
đặt — nên đổi cấu hình có hiệu lực ngay ở lần bắn kế tiếp, không cần deploy (F7).
"""

import frappe

POINT_DOCTYPE = "Supply Notification Point"

#: Khoá cache: {tên chứng từ: [tóm tắt điểm đang bật]}
CACHE_KEY = "supply_notification_point_map"

#: Các trường đủ để định tuyến sự kiện và dựng nút Thủ công, không phải nạp cả điểm.
SUMMARY_FIELDS = (
	"name",
	"reference_doctype",
	"trigger_event",
	"watch_field",
	"workflow_state",
	"button_label",
	"button_color",
	"manual_docstatus",
)


def build_point_map() -> dict[str, list[dict]]:
	rows = frappe.get_all(
		POINT_DOCTYPE,
		filters={"enabled": 1},
		fields=list(SUMMARY_FIELDS),
		order_by="name asc",
	)

	mapping: dict[str, list[dict]] = {}
	for row in rows:
		if not row.reference_doctype:
			continue
		mapping.setdefault(row.reference_doctype, []).append(dict(row))
	return mapping


def point_map() -> dict[str, list[dict]]:
	return frappe.cache().get_value(CACHE_KEY, build_point_map) or {}


def clear_cache():
	"""Gọi từ `on_update`/`on_trash` của mọi DocType cấu hình."""
	frappe.cache().delete_value(CACHE_KEY)


def has_points(doctype: str) -> bool:
	"""Lối thoát sớm của bộ máy sự kiện."""
	return doctype in point_map()


def summaries_for(doctype: str, trigger_event: str | None = None) -> list[dict]:
	rows = point_map().get(doctype, [])
	if trigger_event is None:
		return rows
	return [row for row in rows if row["trigger_event"] == trigger_event]


def points_for(doctype: str, trigger_event: str | None = None) -> list["frappe.Document"]:
	"""Bản ghi đầy đủ của các điểm đang bật, đọc qua cache tài liệu của Frappe."""
	points = []
	for row in summaries_for(doctype, trigger_event):
		try:
			points.append(frappe.get_cached_doc(POINT_DOCTYPE, row["name"]))
		except frappe.DoesNotExistError:
			clear_cache()
	return points


def manual_doctypes() -> list[str]:
	"""Chứng từ có ít nhất một điểm Thủ công đang bật — bơm vào bootinfo.

	Trình duyệt chỉ hỏi máy chủ về nút Thủ công khi form đang mở thuộc danh sách
	này, nên mở một chứng từ bất kỳ không kéo theo lời gọi thừa nào.
	"""
	from erpnext.supply_notification.constants import MANUAL

	return sorted(
		doctype
		for doctype, rows in point_map().items()
		if any(row["trigger_event"] == MANUAL for row in rows)
	)
