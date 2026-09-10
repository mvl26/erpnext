# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Gửi thông báo của một điểm cho một chứng từ.

Chạy trong job nền nên không bao giờ chặn việc ghi sổ. Ba kênh độc lập nhau:
email nội bộ, in-app, email ra ngoài — kênh này hỏng không kéo kênh kia theo.
Mỗi bộ ba (điểm, chứng từ, mốc) chỉ gửi một lần, kể cả khi job chạy lại.

Tham chiếu: docs/05c_Spec_KyThuat_Plan_Thong_Bao.md muc 6, 9, 11.
"""

import frappe
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.utils import get_url_to_form, now_datetime

from erpnext.supply_notification import content, resolver
from erpnext.supply_notification.constants import REALTIME_EVENT

POINT_DOCTYPE = "Supply Notification Point"
LOG_DOCTYPE = "Supply Notification Dispatch Log"

MILESTONE_SUBMIT = "submit"


def already_dispatched(point: str, doctype: str, docname: str, milestone: str) -> bool:
	return bool(
		frappe.db.exists(
			LOG_DOCTYPE,
			{
				"point": point,
				"reference_doctype": doctype,
				"reference_name": docname,
				"milestone": milestone,
				"status": ("in", ("Sent", "Skipped")),
			},
		)
	)


def _write_log(point, doc, milestone, **values):
	log = frappe.new_doc(LOG_DOCTYPE)
	log.point = point.name
	log.reference_doctype = doc.doctype
	log.reference_name = doc.name
	log.milestone = milestone
	log.sent_on = now_datetime()
	log.update(values)
	log.insert(ignore_permissions=True)
	return log


def _send_internal_email(point, doc, recipients, subject, body):
	frappe.sendmail(
		recipients=[row.email for row in recipients],
		subject=subject,
		message=body,
		reference_doctype=doc.doctype,
		reference_name=doc.name,
	)


def _notify_in_app(point, doc, recipients, subject):
	users = [row.name for row in recipients]
	if not users:
		return

	enqueue_create_notification(
		users,
		{
			"type": "Alert",
			"document_type": doc.doctype,
			"document_name": doc.name,
			"subject": subject,
			"from_user": frappe.session.user,
		},
	)

	payload = {
		"subject": subject,
		"doctype": doc.doctype,
		"docname": doc.name,
		"url": get_url_to_form(doc.doctype, doc.name),
	}
	for user in users:
		frappe.publish_realtime(REALTIME_EVENT, payload, user=user, after_commit=True)


def _external_attachments(point, doc) -> list[dict]:
	if not point.attach_pdf or not point.print_format:
		return []

	try:
		return [frappe.attach_print(doc.doctype, doc.name, print_format=point.print_format)]
	except Exception:
		frappe.log_error(
			title="Supply Notification: không tạo được PDF đính kèm",
			message=f"{point.name} · {doc.doctype} {doc.name}\n\n{frappe.get_traceback()}",
		)
		return []


def _send_external_email(point, doc, context) -> tuple[str | None, str]:
	"""Trả (email đã gửi, ghi chú). Thiếu email thì bỏ qua chứ không báo lỗi."""
	email = resolver.external_email(doc)
	if not email:
		return None, "Chứng từ và đối tác chưa có email liên hệ."

	frappe.sendmail(
		recipients=[email],
		subject=content.external_subject(point, context),
		message=content.external_body(point, doc, context),
		reference_doctype=doc.doctype,
		reference_name=doc.name,
		attachments=_external_attachments(point, doc),
	)
	return email, ""


def dispatch(point_code: str, doctype: str, docname: str, milestone: str = MILESTONE_SUBMIT):
	"""Điểm vào của job nền. Không bao giờ ném lỗi ra ngoài."""
	try:
		_dispatch(point_code, doctype, docname, milestone)
	except Exception:
		frappe.log_error(
			title="Supply Notification: lỗi khi gửi thông báo",
			message=f"{point_code} · {doctype} {docname} · {milestone}\n\n{frappe.get_traceback()}",
		)
		_log_failure(point_code, doctype, docname, milestone)


def _log_failure(point_code: str, doctype: str, docname: str, milestone: str):
	"""Ghi lại thất bại để còn đối chiếu.

	Cố ý không rollback rồi commit ở đây: job nền tự chốt giao dịch khi kết thúc,
	còn trong test thì rollback sẽ cuốn theo cả chứng từ vừa dựng.
	"""
	try:
		if not frappe.db.exists(POINT_DOCTYPE, point_code) or not frappe.db.exists(doctype, docname):
			return

		_write_log(
			frappe.get_doc(POINT_DOCTYPE, point_code),
			frappe.get_doc(doctype, docname),
			milestone,
			status="Failed",
			remark=frappe.get_traceback()[-500:],
		)
	except Exception:
		frappe.log_error(title="Supply Notification: không ghi được nhật ký lỗi")


def _dispatch(point_code: str, doctype: str, docname: str, milestone: str):
	if not frappe.db.exists(POINT_DOCTYPE, point_code):
		return

	point = frappe.get_doc(POINT_DOCTYPE, point_code)
	if not point.enabled:
		return

	if already_dispatched(point_code, doctype, docname, milestone):
		return

	doc = frappe.get_doc(doctype, docname)
	context = content.build_context(point, doc, None if milestone == MILESTONE_SUBMIT else milestone)
	subject = content.subject(point, context)

	recipients = resolver.resolve(point, doc)
	notes = []

	sent_email = False
	if point.send_email and recipients:
		_send_internal_email(point, doc, recipients, subject, content.internal_body(point, doc, context))
		sent_email = True
	elif point.send_email:
		notes.append("Không có người nhận nội bộ nào.")

	sent_inapp = False
	if point.send_inapp and recipients:
		_notify_in_app(point, doc, recipients, subject)
		sent_inapp = True

	external_email = None
	if point.notify_external:
		external_email, remark = _send_external_email(point, doc, context)
		if remark:
			notes.append(remark)

	status = "Sent" if (sent_email or sent_inapp or external_email) else "Skipped"
	_write_log(
		point,
		doc,
		milestone,
		status=status,
		channel_email=int(sent_email),
		channel_inapp=int(sent_inapp),
		channel_external=int(bool(external_email)),
		recipients=", ".join(row.email for row in recipients),
		external_recipients=external_email or "",
		remark=" ".join(notes),
	)
