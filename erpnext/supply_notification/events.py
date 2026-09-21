# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nối 10 điểm thông báo theo Ghi sổ vào `doc_events`.

Một hàm duy nhất phục vụ 8 DocType: tra bảng định nghĩa để biết chứng từ vừa ghi
sổ khớp điểm nào, rồi đẩy việc gửi sang job nền. Mọi lỗi ở đây đều bị nuốt —
thông báo hỏng tuyệt đối không được chặn việc ghi sổ chứng từ.

Tham chiếu: docs/05c_Spec_KyThuat_Plan_Thong_Bao.md muc 7.
"""

import frappe

from erpnext.supply_notification.constants import POINTS, SUBMIT
from erpnext.supply_notification.dispatch import MILESTONE_SUBMIT


def matching_points(doc) -> list[str]:
	"""Mã các điểm mà chứng từ này thoả điều kiện bắn."""
	codes = []

	for spec in POINTS:
		if spec["trigger_event"] != SUBMIT or spec["reference_doctype"] != doc.doctype:
			continue

		field = spec["filter_field"]
		if field and doc.get(field) not in spec["filter_values"]:
			continue

		codes.append(spec["code"])

	return codes


def on_submit(doc, method=None):
	try:
		for code in matching_points(doc):
			frappe.enqueue(
				"erpnext.supply_notification.dispatch.dispatch",
				queue="short",
				point_code=code,
				doctype=doc.doctype,
				docname=doc.name,
				milestone=MILESTONE_SUBMIT,
				enqueue_after_commit=True,
				now=frappe.flags.in_test,
			)
	except Exception:
		frappe.log_error(
			title="Supply Notification: không xếp được job thông báo",
			message=f"{doc.doctype} {doc.name}\n\n{frappe.get_traceback()}",
		)
