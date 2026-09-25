# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nhắc theo ngày — chạy hằng giờ, tự so với giờ trong Cài đặt.

Cron nối ở `hooks.py` chạy **mỗi giờ**; hàm này mới quyết định có làm gì không,
bằng cách so giờ hiện tại với `Cài đặt thông báo → Giờ chạy hằng ngày` (D31).
Nhờ vậy đổi giờ nhắc là việc của nghiệp vụ trên giao diện, không phải sửa
`hooks.py` rồi deploy.

Mốc âm là trước ngày (`-7` là trước hạn 7 ngày), mốc dương là quá hạn. Nhật ký
lo phần chống trùng nên chạy lại trong ngày không gửi thêm lần nữa; đổi lại,
job không chạy bù các mốc đã trôi qua (F4).

Tham chiếu: docs/superpowers/specs/2026-09-23-thong-bao-tu-thiet-lap-design.md muc 4.11.
"""

import frappe
from frappe.utils import add_days, cint, getdate, now_datetime

from erpnext.supply_notification import conditions, constants, dispatch, registry
from erpnext.supply_notification.doctype.supply_notification_settings.supply_notification_settings import (
	get_settings,
)

LOG_DOCTYPE = "Supply Notification Dispatch Log"


def milestone_for(offset: int) -> str:
	"""`-7` → `d7` (giữ đúng chuỗi mốc của bản cũ), `+1` → `q1` (quá hạn)."""
	if offset > 0:
		return f"q{offset}"
	return f"d{abs(offset)}"


def run_hourly():
	"""Điểm vào của scheduler (cron mỗi giờ)."""
	settings = get_settings()
	if not settings.enabled:
		return

	if now_datetime().hour != cint(settings.reminder_hour):
		return

	send_date_reminders()


def send_date_reminders(today=None):
	"""Quét mọi điểm nhắc theo ngày đang bật."""
	today = getdate(today)

	for doctype in list(registry.point_map()):
		for point in registry.points_for(doctype, constants.DATE_REMINDER):
			try:
				run_point(point, today)
			except Exception:
				frappe.log_error(
					title="Supply Notification: lỗi khi quét nhắc theo ngày",
					message=f"{point.name}\n\n{frappe.get_traceback()}",
				)


def documents_due(point, target_date) -> list[str]:
	"""Chứng từ có ngày rơi đúng mốc, đã lọc sẵn phần điều kiện đẩy được xuống SQL."""
	meta = frappe.get_meta(point.reference_doctype)
	if not point.date_field or not meta.has_field(point.date_field):
		return []

	filters = conditions.to_filters(point)
	filters[point.date_field] = target_date
	if meta.is_submittable:
		filters["docstatus"] = 1

	return frappe.get_all(point.reference_doctype, filters=filters, pluck="name")


def run_point(point, today):
	for offset in point.reminder_offset_list():
		target_date = add_days(today, -offset)
		milestone = milestone_for(offset)

		for name in documents_due(point, target_date):
			doc = frappe.get_doc(point.reference_doctype, name)
			if not conditions.match(point, doc):
				continue
			dispatch.send(point, doc, milestone)


def clear_old_dispatch_logs():
	"""Dọn nhật ký theo hai hạn khác nhau (D30): tự động 180 ngày, thủ công vĩnh viễn."""
	settings = get_settings()

	_delete_older_than(cint(settings.auto_log_retention_days), is_manual=0)
	_delete_older_than(cint(settings.manual_log_retention_days), is_manual=1)


def _delete_older_than(days: int, is_manual: int):
	if not days:
		return

	cutoff = add_days(getdate(), -days)
	names = frappe.get_all(
		LOG_DOCTYPE,
		filters={"creation": ("<", cutoff), "is_manual": is_manual},
		pluck="name",
		limit=5000,
	)
	for name in names:
		frappe.delete_doc(LOG_DOCTYPE, name, ignore_permissions=True, force=True, delete_permanently=True)
