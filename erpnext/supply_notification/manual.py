# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Loại thời điểm **Thủ công**: nút gửi ngay trên form chứng từ (BA F5, CR_01).

Khác mọi loại khác ở ba điểm: người dùng chủ động bấm, mỗi lần bấm là một lần
gửi thật (không chống trùng — D17), và lỗi báo thẳng cho người bấm chứ không
chỉ nằm trong nhật ký (BR1).

Quyền được kiểm **ở máy chủ**, không chỉ ở nút: gọi thẳng API trên PO nháp hay
PO đã huỷ phải bị từ chối (CR_01 AC1).

Tham chiếu: docs/superpowers/specs/2026-09-23-thong-bao-tu-thiet-lap-design.md muc 4.9.
"""

import frappe
from frappe import _
from frappe.utils import format_datetime

from erpnext.supply_notification import conditions, constants, content, context, dispatch, registry, resolver
from erpnext.supply_notification.doctype.supply_notification_settings.supply_notification_settings import (
	get_settings,
)

DOCSTATUS_SUBMITTED = "Đã ghi sổ"
DOCSTATUS_DRAFT = "Nháp"
DOCSTATUS_BOTH = "Cả hai"

BUTTON_COLORS = {
	"Mặc định": None,
	"Chính (xanh)": "primary",
	"Cảnh báo (vàng)": "warning",
	"Nguy hiểm (đỏ)": "danger",
}


def docstatus_allowed(point, doc) -> bool:
	setting = point.manual_docstatus or DOCSTATUS_SUBMITTED
	if doc.docstatus == 2:
		return False
	if setting == DOCSTATUS_BOTH:
		return doc.docstatus in (0, 1)
	if setting == DOCSTATUS_DRAFT:
		return doc.docstatus == 0
	return doc.docstatus == 1


def can_press(point, doc, user: str | None = None) -> bool:
	"""Ai được bấm: vai trò cấu hình, nếu bỏ trống thì ai sửa được chứng từ (D27)."""
	user = user or frappe.session.user

	if point.button_role:
		return point.button_role in frappe.get_roles(user)

	return bool(
		frappe.has_permission(doc.doctype, "write", doc=doc, user=user)
		or frappe.has_permission(doc.doctype, "submit", doc=doc, user=user)
	)


def applicable_points(doc, user: str | None = None) -> list:
	points = []
	for point in registry.points_for(doc.doctype, constants.MANUAL):
		if not docstatus_allowed(point, doc):
			continue
		if not conditions.match(point, doc):
			continue
		if not can_press(point, doc, user):
			continue
		points.append(point)
	return points


def sent_history(point_name: str, doctype: str, docname: str) -> dict:
	rows = frappe.get_all(
		dispatch.LOG_DOCTYPE,
		filters={
			"point": point_name,
			"reference_doctype": doctype,
			"reference_name": docname,
			"status": dispatch.STATUS_SENT,
		},
		fields=["sent_on", "triggered_by", "external_recipients"],
		order_by="sent_on desc",
	)

	if not rows:
		return {"count": 0, "summary": ""}

	last = rows[0]
	return {
		"count": len(rows),
		"summary": _("Đã gửi {0} lần – lần cuối {1} bởi {2} tới {3}").format(
			len(rows),
			format_datetime(last.sent_on),
			frappe.get_cached_value("User", last.triggered_by, "full_name")
			if last.triggered_by
			else _("hệ thống"),
			last.external_recipients or _("người nhận nội bộ"),
		),
	}


@frappe.whitelist()
def get_buttons(doctype: str, docname: str) -> list[dict]:
	"""Các nút Thủ công hiện được trên form chứng từ này."""
	if not get_settings().enabled or not frappe.db.exists(doctype, docname):
		return []

	doc = frappe.get_doc(doctype, docname)
	doc.check_permission("read")

	return [
		{
			"point": point.name,
			"label": point.button_label or point.title,
			"color": BUTTON_COLORS.get(point.button_color or "Mặc định"),
			**sent_history(point.name, doctype, docname),
		}
		for point in applicable_points(doc)
	]


@frappe.whitelist()
def get_confirmation(point: str, doctype: str, docname: str) -> dict:
	"""Nội dung hộp xác nhận: gửi cho ai, kèm gì, đã gửi mấy lần, xem trước."""
	point_doc, doc = _load(point, doctype, docname)

	recipients = resolver.resolve(point_doc, doc, frappe.session.user)
	warnings = list(recipients.notes)
	blocked = False

	if point_doc.notify_external and not recipients.external:
		blocked = True
		warnings.append(_("Nhà cung cấp / khách hàng trên chứng từ chưa có email liên hệ nên chưa gửi được."))

	if point_doc.send_email and not recipients.emails:
		warnings.append(_("Không có người nhận nội bộ nào."))

	warnings.extend(_missing_address_warnings(point_doc, doc))

	if get_settings().test_mode:
		warnings.append(
			_("Đang bật Chế độ thử: thư sẽ về {0}, đối tác không nhận gì.").format(get_settings().test_email)
		)

	scope = context.SCOPE_EXTERNAL if point_doc.notify_external else context.SCOPE_INTERNAL
	preview = content.build(point_doc, doc, scope=scope, triggered_by=frappe.session.user)

	attachments = []
	if point_doc.notify_external:
		files, error = dispatch.attachments_for(point_doc, doc)
		if error:
			warnings.append(error)
			blocked = blocked or bool(point_doc.require_pdf)
		attachments = [file.get("fname") or file.get("file_name") or file.get("fid", "") for file in files]

	return {
		"point": point_doc.name,
		"title": point_doc.title,
		"to": recipients.external if point_doc.notify_external else recipients.emails,
		"cc": recipients.cc,
		"bcc": recipients.bcc,
		"reply_to": recipients.reply_to,
		"attachments": attachments,
		"subject": preview.subject,
		"body": preview.body,
		"warnings": warnings,
		"blocked": blocked,
		**sent_history(point_doc.name, doctype, docname),
	}


def _missing_address_warnings(point, doc) -> list[str]:
	"""Cảnh báo dữ liệu thiếu của CR_01: địa chỉ giao chưa có người nhận/điện thoại."""
	if not point.address_field:
		return []

	address = doc.get(point.address_field)
	if not address:
		return [_("Chứng từ chưa chọn địa chỉ giao hàng.")]

	from erpnext.supply_notification import blocks

	rendered = str(blocks.delivery_address(point, doc.as_dict()))
	if _("Người nhận:") in rendered:
		return []

	return [
		_("Địa chỉ giao hàng {0} chưa gắn người nhận — email sẽ không có dòng người nhận.").format(address)
	]


@frappe.whitelist()
def send(point: str, doctype: str, docname: str) -> dict:
	"""Gửi thật. Chạy đồng bộ để lỗi báo thẳng cho người bấm."""
	point_doc, doc = _load(point, doctype, docname)

	if not get_settings().enabled:
		frappe.throw(_("Tính năng thông báo đang tắt trong Cài đặt thông báo."))

	if point_doc.notify_external:
		recipients, note = resolver.external_emails(point_doc, doc)
		if not recipients:
			frappe.throw(note or _("Chưa có email người nhận ngoài."))

	log = dispatch.send(
		point_doc,
		doc,
		dispatch.MILESTONE_MANUAL,
		triggered_by=frappe.session.user,
		force=True,
	)

	if not log:
		frappe.throw(_("Không gửi được: điểm thông báo đang tắt."))

	return {
		"log": log.name,
		"status": log.status,
		"to": log.external_recipients or log.recipients,
		**sent_history(point_doc.name, doctype, docname),
	}


def _load(point: str, doctype: str, docname: str):
	"""Nạp điểm và chứng từ, kiểm mọi điều kiện được phép bấm (AC1)."""
	point_doc = frappe.get_doc("Supply Notification Point", point)

	if point_doc.trigger_event != constants.MANUAL:
		frappe.throw(_("Điểm {0} không phải loại gửi thủ công.").format(point))

	if not point_doc.enabled:
		frappe.throw(_("Điểm {0} đang tắt.").format(point))

	if point_doc.reference_doctype != doctype:
		frappe.throw(_("Điểm {0} không dùng cho {1}.").format(point, _(doctype)))

	doc = frappe.get_doc(doctype, docname)
	doc.check_permission("read")

	if not docstatus_allowed(point_doc, doc):
		frappe.throw(
			_("Chứng từ đang ở trạng thái không được gửi ({0} chỉ gửi khi: {1}).").format(
				point_doc.button_label or point_doc.title, point_doc.manual_docstatus
			)
		)

	if not conditions.match(point_doc, doc):
		frappe.throw(_("Chứng từ không thoả điều kiện của điểm {0}.").format(point))

	if not can_press(point_doc, doc):
		raise frappe.PermissionError(_("Bạn không có quyền bấm gửi trên chứng từ này."))

	return point_doc, doc
