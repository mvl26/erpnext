# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nhắc hạn thanh toán và thu tiền, chạy 08:00 mỗi ngày.

Quét hoá đơn còn nợ có hạn rơi đúng 7 / 3 / 1 ngày phía trước. Nhật ký gửi lo
phần chống trùng nên job chạy lại trong ngày không gửi thêm lần nữa; đổi lại,
job không chạy bù các mốc đã trôi qua.

Tham chiếu: docs/05c_Spec_KyThuat_Plan_Thong_Bao.md muc 10.
"""

import frappe
from frappe.utils import add_days, getdate

from erpnext.supply_notification.constants import DUE_MILESTONES, DUE_REMINDER, POINTS
from erpnext.supply_notification.dispatch import dispatch

POINT_DOCTYPE = "Supply Notification Point"
LOG_DOCTYPE = "Supply Notification Dispatch Log"


def due_documents(doctype: str, due_date) -> list[str]:
	return frappe.get_all(
		doctype,
		filters={
			"docstatus": 1,
			"due_date": due_date,
			"outstanding_amount": (">", 0),
		},
		pluck="name",
	)


def send_due_reminders():
	"""Điểm vào của scheduler."""
	today = getdate()

	for spec in POINTS:
		if spec["trigger_event"] != DUE_REMINDER:
			continue

		code = spec["code"]
		if not frappe.db.get_value(POINT_DOCTYPE, code, "enabled"):
			continue

		doctype = spec["reference_doctype"]
		for days in DUE_MILESTONES:
			for name in due_documents(doctype, add_days(today, days)):
				dispatch(code, doctype, name, milestone=f"d{days}")


def clear_old_dispatch_logs():
	"""Nhật ký gửi chỉ cần cho đối chiếu ngắn hạn — giữ 180 ngày."""
	from erpnext.supply_notification.doctype.supply_notification_dispatch_log.supply_notification_dispatch_log import (
		SupplyNotificationDispatchLog,
	)

	SupplyNotificationDispatchLog.clear_old_logs()
