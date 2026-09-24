# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Trang *Thông báo của tôi*: mỗi người tự xem mình đang nhận gì và tắt bớt.

Quyết định D18: chỉ điểm có cờ *Cho phép người nhận tự tắt* mới tắt được. Thông
báo bắt buộc xử lý (nhắc hạn thanh toán chẳng hạn) không cho tắt — giảm thư thừa
mà không mất thư bắt buộc.

API ở đây chạy dưới quyền người dùng thường, nên chỉ đụng tới bản ghi tắt/bật
của **chính họ**.
"""

import frappe
from frappe import _

from erpnext.supply_notification import constants, registry, resolver

OPT_OUT_DOCTYPE = "Supply Notification Opt Out"
POINT_DOCTYPE = "Supply Notification Point"

TRIGGER_LABELS = {
	constants.NEW: "Khi tạo mới",
	constants.SUBMIT: "Khi ghi sổ",
	constants.CANCEL: "Khi huỷ",
	constants.VALUE_CHANGE: "Khi một trường đổi giá trị",
	constants.WORKFLOW_TRANSITION: "Khi chuyển trạng thái duyệt",
	constants.DATE_REMINDER: "Nhắc theo ngày",
	constants.MANUAL: "Khi có người bấm gửi",
}


def points_for_user(user: str) -> list[dict]:
	"""Điểm mà người này đang nằm trong danh sách nhận."""
	rows = []
	opted_out = set(frappe.get_all(OPT_OUT_DOCTYPE, filters={"user": user}, pluck="point"))

	for doctype in list(registry.point_map()):
		for point in registry.points_for(doctype):
			sources = resolver.internal_sources(point)
			receives = user in set().union(*sources.values()) if sources else False

			if not receives and not point.notify_owner:
				continue

			rows.append(
				{
					"point": point.name,
					"title": point.title,
					"doctype_label": _(point.reference_doctype),
					"trigger": _(TRIGGER_LABELS.get(point.trigger_event, point.trigger_event)),
					"only_as_owner": not receives,
					"allow_opt_out": bool(point.allow_opt_out),
					"opted_out": point.name in opted_out,
				}
			)

	return sorted(rows, key=lambda row: row["point"])


@frappe.whitelist()
def my_points() -> list[dict]:
	return points_for_user(frappe.session.user)


@frappe.whitelist()
def set_subscription(point: str, receive: int | str = 1) -> dict:
	"""Bật/tắt nhận một điểm cho chính người đang đăng nhập."""
	user = frappe.session.user
	receive = int(receive)

	if not frappe.db.exists(POINT_DOCTYPE, point):
		frappe.throw(_("Không có điểm thông báo {0}.").format(point))

	if not frappe.db.get_value(POINT_DOCTYPE, point, "allow_opt_out"):
		frappe.throw(_("Điểm {0} là thông báo bắt buộc, không tắt được.").format(point))

	existing = frappe.get_all(OPT_OUT_DOCTYPE, filters={"user": user, "point": point}, pluck="name")

	if receive:
		for name in existing:
			frappe.delete_doc(OPT_OUT_DOCTYPE, name, ignore_permissions=True, force=True)
	elif not existing:
		frappe.get_doc({"doctype": OPT_OUT_DOCTYPE, "user": user, "point": point}).insert(
			ignore_permissions=True
		)

	return {"point": point, "receive": bool(receive)}
