# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tự kiểm trước khi bật: xem trước email, gửi thử, danh sách trường để chèn.

Nguyên tắc 5 của BA: *cái gì cấu hình được thì xem trước được và thử được*. Các
API ở đây nhận **giá trị đang có trên form** (kể cả chưa lưu) nên người dùng
thấy đúng cái mình vừa gõ, không phải lưu rồi mới biết sai.

Tham chiếu: docs/superpowers/specs/2026-09-23-thong-bao-tu-thiet-lap-design.md muc 4.10.
"""

import json

import frappe
from frappe import _
from frappe.model.workflow import get_workflow_name
from frappe.utils import add_days, getdate

from erpnext.supply_notification import constants, content, context, dispatch, resolver

POINT_DOCTYPE = "Supply Notification Point"

#: Kiểu trường không đáng liệt kê trong hộp *Chèn trường*.
LAYOUT_FIELDTYPES = (
	"Section Break",
	"Column Break",
	"Tab Break",
	"HTML",
	"Button",
	"Fold",
	"Heading",
	"Image",
)


def point_from(point_json: str | dict | None, name: str | None = None):
	"""Dựng bản ghi điểm từ dữ liệu form (chưa lưu) hoặc từ tên đã lưu."""
	if point_json:
		data = json.loads(point_json) if isinstance(point_json, str) else point_json
		doc = frappe.get_doc(data)
		doc.name = data.get("name") or name or "new-point"
		return doc

	doc = frappe.get_doc(POINT_DOCTYPE, name)
	doc.check_permission("read")
	return doc


def _sample(doctype: str, reference: str | None):
	if reference and frappe.db.exists(doctype, reference):
		return frappe.get_doc(doctype, reference)

	name = context.sample_document(doctype)
	return frappe.get_doc(doctype, name) if name else None


@frappe.whitelist()
def field_options(doctype: str, only_types: str | None = None) -> list[dict]:
	"""Trường của chứng từ (và bảng con) kèm nhãn tiếng Việt, cho hộp Chèn trường."""
	if not doctype or not frappe.db.exists("DocType", doctype):
		return []

	wanted = [t.strip() for t in (only_types or "").split(",") if t.strip()]
	meta = frappe.get_meta(doctype)
	options = []

	for df in meta.fields:
		if df.fieldtype in LAYOUT_FIELDTYPES:
			continue
		if wanted and df.fieldtype not in wanted:
			continue
		options.append(
			{
				"value": df.fieldname,
				"label": f"{_(df.label or df.fieldname)} ({df.fieldname})",
				"description": df.fieldtype,
			}
		)

		if df.fieldtype in ("Table", "Table MultiSelect") and not wanted:
			child = frappe.get_meta(df.options)
			for child_df in child.fields:
				if child_df.fieldtype in LAYOUT_FIELDTYPES:
					continue
				options.append(
					{
						"value": f"{df.fieldname}.{child_df.fieldname}",
						"label": f"{_(df.label or df.fieldname)} → {_(child_df.label or child_df.fieldname)}",
						"description": child_df.fieldtype,
					}
				)

	if not wanted:
		options.extend(
			{"value": name, "label": name, "description": _("biến dựng sẵn")}
			for name in constants_builtin_names()
		)

	return options


def constants_builtin_names() -> list[str]:
	return [name for name in context.BUILTIN_VARIABLES if name not in context.ALIASES and name != "doc"]


@frappe.whitelist()
def workflow_states(doctype: str) -> list[str]:
	"""Trạng thái của Workflow đang bật trên chứng từ — cho ô Trạng thái duyệt đích."""
	workflow = get_workflow_name(doctype) if doctype else None
	if not workflow:
		return []

	return frappe.get_all(
		"Workflow Document State",
		filters={"parent": workflow},
		pluck="state",
		order_by="idx asc",
		distinct=True,
	)


@frappe.whitelist()
def suggest_code() -> str:
	"""Mã kế tiếp theo nếp NTF-nn."""
	codes = frappe.get_all(POINT_DOCTYPE, pluck="name")
	numbers = [int(code.split("-")[-1]) for code in codes if code.split("-")[-1].isdigit()]
	return f"NTF-{max(numbers, default=0) + 1:02d}"


@frappe.whitelist()
def preview_email(
	point_json: str | None = None, name: str | None = None, reference: str | None = None
) -> dict:
	"""Xem trước email với một chứng từ thật — **không gửi** (thẻ 7)."""
	point = point_from(point_json, name)
	doc = _sample(point.reference_doctype, reference)

	if not doc:
		return {"error": _("Chưa có chứng từ {0} nào để xem trước.").format(_(point.reference_doctype))}

	doc.check_permission("read")
	milestone = _preview_milestone(point)
	recipients = resolver.resolve(point, doc, frappe.session.user)

	result = {
		"reference": doc.name,
		"recipients": recipients.emails,
		"external": recipients.external,
		"cc": recipients.cc,
		"bcc": recipients.bcc,
		"reply_to": recipients.reply_to,
		"warnings": list(recipients.notes),
	}

	if point.send_email or point.send_inapp:
		internal = content.build(
			point, doc, scope=context.SCOPE_INTERNAL, milestone=milestone, triggered_by=frappe.session.user
		)
		result["internal"] = {"subject": internal.subject, "body": internal.body, "inapp": internal.inapp}

	if point.notify_external:
		external = content.build(
			point, doc, scope=context.SCOPE_EXTERNAL, milestone=milestone, triggered_by=frappe.session.user
		)
		result["external_mail"] = {"subject": external.subject, "body": external.body}

		files, error = dispatch.attachments_for(point, doc)
		result["attachments"] = [
			file.get("fname") or file.get("file_name") or file.get("fid", "") for file in files
		]
		if error:
			result["warnings"].append(error)

	return result


def _preview_milestone(point) -> str | None:
	"""Mốc giả lập để biến `so_ngay_con_lai` có giá trị khi xem trước điểm nhắc hạn."""
	if point.trigger_event != constants.DATE_REMINDER:
		return None

	offsets = point.reminder_offset_list()
	if not offsets:
		return None

	from erpnext.supply_notification.reminders import milestone_for

	return milestone_for(offsets[0])


@frappe.whitelist()
def send_test_to_me(
	point_json: str | None = None, name: str | None = None, reference: str | None = None
) -> dict:
	"""Gửi thử **chỉ cho người đang thao tác**, không ghi nhật ký nghiệp vụ (AC-11)."""
	point = point_from(point_json, name)
	doc = _sample(point.reference_doctype, reference)

	if not doc:
		frappe.throw(_("Chưa có chứng từ {0} nào để gửi thử.").format(_(point.reference_doctype)))

	doc.check_permission("read")
	email = frappe.db.get_value("User", frappe.session.user, "email")
	if not email:
		frappe.throw(_("Tài khoản của bạn chưa có địa chỉ email."))

	scope = context.SCOPE_EXTERNAL if point.notify_external else context.SCOPE_INTERNAL
	built = content.build(
		point,
		doc,
		scope=scope,
		milestone=_preview_milestone(point),
		triggered_by=frappe.session.user,
	)

	frappe.sendmail(
		recipients=[email],
		subject=f"[THỬ] {built.subject}",
		message=built.body,
	)

	return {"email": email, "subject": built.subject, "reference": doc.name}


@frappe.whitelist()
def point_stats(name: str, days: int = 30) -> dict:
	"""Số lần gửi và tỉ lệ lỗi 30 ngày qua — thẻ 7 của form."""
	frappe.has_permission(POINT_DOCTYPE, "read", throw=True)

	since = add_days(getdate(), -int(days))
	rows = frappe.get_all(
		dispatch.LOG_DOCTYPE,
		filters={"point": name, "creation": (">=", since)},
		fields=["status", "count(name) as total"],
		group_by="status",
	)

	totals = {row.status: row.total for row in rows}
	total = sum(totals.values())

	return {
		"days": int(days),
		"total": total,
		"sent": totals.get(dispatch.STATUS_SENT, 0),
		"skipped": totals.get(dispatch.STATUS_SKIPPED, 0),
		"failed": totals.get(dispatch.STATUS_FAILED, 0),
		"failure_rate": round(totals.get(dispatch.STATUS_FAILED, 0) * 100.0 / total, 1) if total else 0,
	}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def doctype_query(doctype, txt, searchfield, start, page_len, filters):
	"""Danh sách chứng từ chọn được cho ô *Chứng từ nguồn* (kiểm V8 ngay khi chọn).

	Lọc sẵn DocType hệ thống, bảng con và bản ghi cài đặt để người dùng không phải
	thử rồi mới biết là không đặt được thông báo lên đó.
	"""
	from erpnext.supply_notification.constants import BLOCKED_DOCTYPES

	rows = frappe.get_all(
		"DocType",
		filters=[
			["name", "not in", BLOCKED_DOCTYPES],
			["name", "like", f"%{txt}%"],
			["istable", "=", 0],
			["issingle", "=", 0],
			["is_virtual", "=", 0],
		],
		fields=["name", "module"],
		order_by="name asc",
		limit_start=start,
		limit_page_length=page_len,
	)
	return [(row.name, row.module) for row in rows]
