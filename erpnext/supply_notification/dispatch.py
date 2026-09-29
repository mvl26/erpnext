# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Gửi thông báo của một điểm cho một chứng từ — **cửa duy nhất** của cả tính năng.

Mọi đường vào (sự kiện chứng từ, nhắc theo ngày, nút Thủ công, gửi lại từ nhật
ký, gửi thử) đều đi qua `send`, nên chống trùng, chế độ thử, trần thư và nhật ký
chỉ viết một lần và không đường nào lách được.

Ba kênh độc lập nhau: email nội bộ, thông báo trong hệ thống, email ra ngoài —
kênh này hỏng không kéo kênh kia theo. Loại tự động chạy trong job nền nên không
bao giờ chặn việc ghi sổ (BR1); loại Thủ công chạy đồng bộ để báo lỗi thẳng cho
người bấm.

Tham chiếu: docs/superpowers/specs/2026-09-23-thong-bao-tu-thiet-lap-design.md muc 4.8.
"""

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.utils import add_to_date, cint, get_url_to_form, now_datetime

from erpnext.supply_notification import constants, content, context, registry, resolver
from erpnext.supply_notification.doctype.supply_notification_settings.supply_notification_settings import (
	get_settings,
)

POINT_DOCTYPE = "Supply Notification Point"
LOG_DOCTYPE = "Supply Notification Dispatch Log"

MILESTONE_SUBMIT = "submit"
MILESTONE_MANUAL = "manual"

STATUS_SENT = "Sent"
STATUS_SKIPPED = "Skipped"
STATUS_FAILED = "Failed"


# --- Điểm vào ------------------------------------------------------------


def enqueue_dispatch(point_code: str, doctype: str, docname: str, milestone: str, triggered_by=None):
	"""Đẩy việc gửi sang job nền, chốt sau khi giao dịch chứng từ commit."""
	frappe.enqueue(
		"erpnext.supply_notification.dispatch.dispatch",
		queue="short",
		point_code=point_code,
		doctype=doctype,
		docname=docname,
		milestone=milestone,
		triggered_by=triggered_by,
		enqueue_after_commit=True,
		now=frappe.flags.in_test,
	)


def dispatch(
	point_code: str,
	doctype: str,
	docname: str,
	milestone: str = MILESTONE_SUBMIT,
	triggered_by: str | None = None,
	force: bool = False,
):
	"""Điểm vào của job nền. Không bao giờ ném lỗi ra ngoài."""
	try:
		if not frappe.db.exists(POINT_DOCTYPE, point_code) or not frappe.db.exists(doctype, docname):
			return

		point = frappe.get_doc(POINT_DOCTYPE, point_code)
		doc = frappe.get_doc(doctype, docname)
		send(point, doc, milestone, triggered_by=triggered_by, force=force)
	except Exception:
		frappe.log_error(
			title="Supply Notification: lỗi khi gửi thông báo",
			message=f"{point_code} · {doctype} {docname} · {milestone}\n\n{frappe.get_traceback()}",
		)
		_log_failure(point_code, doctype, docname, milestone, triggered_by)


def _log_failure(point_code: str, doctype: str, docname: str, milestone: str, triggered_by=None):
	"""Ghi lại thất bại để còn đối chiếu.

	Cố ý không rollback rồi commit ở đây: job nền tự chốt giao dịch khi kết thúc,
	còn trong test thì rollback sẽ cuốn theo cả chứng từ vừa dựng.
	"""
	try:
		if not frappe.db.exists(POINT_DOCTYPE, point_code) or not frappe.db.exists(doctype, docname):
			return

		write_log(
			frappe.get_doc(POINT_DOCTYPE, point_code),
			frappe.get_doc(doctype, docname),
			milestone,
			status=STATUS_FAILED,
			triggered_by=triggered_by,
			reason=_("Lỗi hệ thống khi gửi, xem Error Log."),
			remark=frappe.get_traceback()[-500:],
		)
	except Exception:
		frappe.log_error(title="Supply Notification: không ghi được nhật ký lỗi")


# --- Chống trùng và trần thư ---------------------------------------------


def already_dispatched(point: str, doctype: str, docname: str, milestone: str) -> bool:
	milestone = (milestone or "")[:MILESTONE_MAX_LENGTH]
	return bool(
		frappe.db.exists(
			LOG_DOCTYPE,
			{
				"point": point,
				"reference_doctype": doctype,
				"reference_name": docname,
				"milestone": milestone,
				"status": ("in", (STATUS_SENT, STATUS_SKIPPED)),
			},
		)
	)


def over_hourly_cap(point) -> bool:
	"""Trần thư mỗi điểm mỗi giờ (NF3) — chặn bão thư do cấu hình sai."""
	cap = cint(get_settings().hourly_email_cap)
	if not cap:
		return False

	sent = frappe.db.count(
		LOG_DOCTYPE,
		{
			"point": point.name,
			"status": STATUS_SENT,
			"creation": (">", add_to_date(now_datetime(), hours=-1)),
		},
	)
	return sent >= cap


def pause_point(point, sent_count: int):
	"""Tự tạm dừng điểm vượt trần và báo cho quản trị thông báo."""
	reason = _("Vượt trần {0} thư trong một giờ lúc {1}. Kiểm tra lại điều kiện trước khi bật lại.").format(
		sent_count, frappe.utils.format_datetime(now_datetime())
	)
	frappe.db.set_value(POINT_DOCTYPE, point.name, {"enabled": 0, "paused_reason": reason})
	registry.clear_cache()

	admins = frappe.get_all(
		"Has Role",
		filters={"role": constants.ADMIN_ROLE, "parenttype": "User"},
		pluck="parent",
	)
	admins = [user for user in admins if user not in resolver.SYSTEM_USERS]
	if not admins:
		return

	enqueue_create_notification(
		admins,
		{
			"type": "Alert",
			"document_type": POINT_DOCTYPE,
			"document_name": point.name,
			"subject": _("Điểm thông báo {0} đã tự tạm dừng vì vượt trần thư").format(point.name),
			"from_user": frappe.session.user,
		},
	)


# --- Gửi thư -------------------------------------------------------------


def _test_target() -> str | None:
	settings = get_settings()
	if not settings.test_mode:
		return None
	return settings.test_email or None


def sendmail(*, recipients, subject, message, doc, cc=None, bcc=None, reply_to=None, attachments=None):
	"""Bọc quanh `frappe.sendmail` để chế độ thử không lách được (D16)."""
	test_email = _test_target()
	if test_email:
		original = ", ".join(recipients + (cc or []) + (bcc or []))
		subject = f"[THỬ → {original}] {subject}"
		recipients, cc, bcc = [test_email], [], []

	frappe.sendmail(
		recipients=recipients,
		cc=cc or None,
		bcc=bcc or None,
		subject=subject,
		message=message,
		reference_doctype=doc.doctype,
		reference_name=doc.name,
		reply_to=reply_to,
		attachments=attachments or None,
	)


def attachments_for(point, doc) -> tuple[list[dict], str]:
	"""Tệp đính kèm của email ra ngoài: PDF theo mẫu in và tệp gắn trên chứng từ."""
	files: list[dict] = []

	if point.attach_pdf and point.print_format:
		try:
			files.append(frappe.attach_print(doc.doctype, doc.name, print_format=point.print_format))
		except Exception:
			frappe.log_error(
				title="Supply Notification: không tạo được PDF đính kèm",
				message=f"{point.name} · {doc.doctype} {doc.name}\n\n{frappe.get_traceback()}",
			)
			if point.require_pdf:
				return [], _("Không tạo được PDF theo mẫu in {0}.").format(point.print_format)

	if point.attach_document_files:
		for row in frappe.get_all(
			"File",
			filters={"attached_to_doctype": doc.doctype, "attached_to_name": doc.name},
			fields=["file_name", "name"],
		):
			files.append({"fid": row.name})

	return files, ""


def _notify_in_app(point, doc, users: list[str], subject: str):
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
		frappe.publish_realtime(constants.REALTIME_EVENT, payload, user=user, after_commit=True)


#: Mốc dài hơn mức này bị cắt — `change:<trường>:<giá trị>` có thể rất dài, mà
#: mốc chỉ cần đủ phân biệt để chống gửi trùng.
MILESTONE_MAX_LENGTH = 140


def write_log(point, doc, milestone, **values):
	log = frappe.new_doc(LOG_DOCTYPE)
	log.point = point.name
	log.reference_doctype = doc.doctype
	log.reference_name = doc.name
	log.milestone = (milestone or "")[:MILESTONE_MAX_LENGTH]
	log.trigger_event = point.trigger_event
	log.is_manual = int(point.trigger_event == constants.MANUAL)
	log.test_mode = int(bool(_test_target()))
	log.sent_on = now_datetime()
	log.update(values)
	log.insert(ignore_permissions=True)
	return log


# --- Hàm gửi chính -------------------------------------------------------


def send(point, doc, milestone: str, *, triggered_by: str | None = None, force: bool = False):
	"""Gửi một lần. Trả về bản ghi nhật ký, hoặc None khi không gửi gì."""
	settings = get_settings()
	if not settings.enabled or not point.enabled:
		return None

	if not force and already_dispatched(point.name, doc.doctype, doc.name, milestone):
		return None

	if over_hourly_cap(point):
		pause_point(point, cint(settings.hourly_email_cap))
		return write_log(
			point,
			doc,
			milestone,
			status=STATUS_SKIPPED,
			triggered_by=triggered_by,
			reason=_("Điểm vượt trần thư mỗi giờ nên đã tự tạm dừng."),
		)

	recipients = resolver.resolve(point, doc, triggered_by)
	reasons = list(recipients.notes)

	internal = content.build(
		point, doc, scope=context.SCOPE_INTERNAL, milestone=milestone, triggered_by=triggered_by
	)

	sent_email = False
	if point.send_email and recipients.emails:
		sendmail(
			recipients=list(recipients.emails),
			cc=list(recipients.cc),
			bcc=list(recipients.bcc),
			subject=internal.subject,
			message=internal.body,
			doc=doc,
			reply_to=recipients.reply_to,
		)
		sent_email = True
	elif point.send_email:
		reasons.append(_("Không có người nhận nội bộ nào."))

	sent_inapp = False
	if point.send_inapp and recipients.users:
		_notify_in_app(point, doc, [row.name for row in recipients.users], internal.inapp)
		sent_inapp = True

	external_sent: list[str] = []
	attachments: list[dict] = []
	if point.notify_external and recipients.external:
		attachments, attach_error = attachments_for(point, doc)
		if attach_error:
			reasons.append(attach_error)
		else:
			external = content.build(
				point,
				doc,
				scope=context.SCOPE_EXTERNAL,
				milestone=milestone,
				triggered_by=triggered_by,
			)
			sendmail(
				recipients=list(recipients.external),
				cc=list(recipients.cc),
				bcc=list(recipients.bcc),
				subject=external.subject,
				message=external.body,
				doc=doc,
				reply_to=recipients.reply_to,
				attachments=attachments,
			)
			external_sent = list(recipients.external)

	status = STATUS_SENT if (sent_email or sent_inapp or external_sent) else STATUS_SKIPPED

	return write_log(
		point,
		doc,
		milestone,
		status=status,
		triggered_by=triggered_by,
		subject=internal.subject,
		channel_email=int(sent_email),
		channel_inapp=int(sent_inapp),
		channel_external=int(bool(external_sent)),
		recipients=", ".join(recipients.emails),
		external_recipients=", ".join(external_sent),
		cc=", ".join(recipients.cc),
		bcc=", ".join(recipients.bcc),
		attachments=", ".join(
			file.get("fname") or file.get("file_name") or file.get("fid", "") for file in attachments
		),
		reason=" ".join(reasons),
	)


@frappe.whitelist()
def resend(log: str) -> str:
	"""Nút *Gửi lại* trên dòng nhật ký lỗi (AC-15)."""
	row = frappe.get_doc(LOG_DOCTYPE, log)
	row.check_permission("read")
	frappe.only_for((constants.ADMIN_ROLE, "System Manager"))

	point = frappe.get_doc(POINT_DOCTYPE, row.point)
	doc = frappe.get_doc(row.reference_doctype, row.reference_name)

	new_log = send(point, doc, row.milestone, triggered_by=frappe.session.user, force=True)
	if not new_log:
		frappe.throw(_("Không gửi lại được: điểm đang tắt hoặc tính năng thông báo đang tắt."))

	return new_log.name
