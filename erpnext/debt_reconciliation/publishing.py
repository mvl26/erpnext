# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Phát hành biên bản: PDF + email sau khi Duyệt (FR-09, FR-10).

Email được đưa vào hàng đợi rồi chuyển Đã gửi ngay — đợt này không theo dõi email có
tới được đối tác hay không (D21). Chỉ chặn trước trường hợp thiếu/sai email → Lỗi gửi.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime, validate_email_address
from frappe.utils.file_manager import save_file

from erpnext.debt_reconciliation import constants as C


def send_statement(name):
	doc = frappe.get_doc(C.DOCTYPE, name)
	if doc.docstatus != 1 or doc.status != C.STATUS_APPROVED:
		return

	email = (doc.reconciliation_email or "").strip()
	if not email:
		return mark_failed(doc, _("Đối tác chưa có email nhận đối chiếu."))
	if not validate_email_address(email):
		return mark_failed(doc, _("Email nhận đối chiếu không đúng định dạng: {0}").format(email))

	try:
		# get_print thay vì attach_print: attach_print trả HTML khi Print Settings tắt "gửi dạng PDF"
		frappe.local.flags.ignore_print_permissions = True
		content = frappe.get_print(
			C.DOCTYPE, doc.name, print_format=C.PRINT_FORMATS[doc.party_type], as_pdf=True, no_letterhead=1
		)
		file_doc = save_file(get_pdf_name(doc), content, C.DOCTYPE, doc.name, is_private=1)

		settings = frappe.get_cached_doc(C.SETTINGS)
		subject, message = render_email(doc, settings)
		queue = frappe.sendmail(
			recipients=[email],
			cc=split_emails(settings.cc_emails),
			sender=get_sender(settings),
			subject=subject,
			message=message,
			# đính kèm theo File đã lưu — hàng đợi chỉ giữ tham chiếu, gửi mới đọc nội dung
			attachments=[{"fid": file_doc.name}],
			reference_doctype=C.DOCTYPE,
			reference_name=doc.name,
		)
	except Exception as e:
		frappe.log_error(title=_("Gửi biên bản đối chiếu công nợ lỗi: {0}").format(doc.name))
		return mark_failed(doc, str(e) or e.__class__.__name__)

	doc.db_set(
		{
			"status": C.STATUS_SENT,
			"sent_on": now_datetime(),
			"sent_pdf": file_doc.file_url,
			"email_queue": queue.name if queue else None,
			"send_error": None,
		}
	)
	doc.add_comment("Info", _("Đã gửi biên bản tới {0}").format(email))


def mark_failed(doc, error):
	from erpnext.debt_reconciliation.generation import get_reminder_recipients, make_notification

	doc.db_set({"status": C.STATUS_SEND_FAILED, "send_error": error})
	doc.add_comment("Info", _("Lỗi gửi: {0}").format(error))
	recipients = {doc.owner, frappe.session.user, *get_reminder_recipients()} - {"Administrator", "Guest"}
	make_notification(
		list(recipients),
		_("Biên bản {0} ({1}) lỗi gửi: {2}").format(doc.name, doc.party_name, error),
		document_name=doc.name,
	)


def get_pdf_name(doc):
	period = frappe.utils.getdate(doc.to_date).strftime("%m-%Y")
	return f"BB doi chieu cong no {period} - {doc.party}.pdf"


def render_email(doc, settings):
	template_name = settings.email_template or C.EMAIL_TEMPLATE
	context = {"doc": doc, "settings": settings}
	if frappe.db.exists("Email Template", template_name):
		template = frappe.get_cached_doc("Email Template", template_name)
		body = template.response_html if template.use_html else template.response
		return frappe.render_template(template.subject, context), frappe.render_template(body or "", context)
	subject = _("Biên bản đối chiếu công nợ tháng {0} - {1}").format(
		frappe.utils.getdate(doc.to_date).strftime("%m/%Y"), doc.company
	)
	return subject, _("Kính gửi {0}, vui lòng xem biên bản đính kèm.").format(doc.party_name)


def get_sender(settings):
	if settings.sender_email_account:
		account = frappe.db.get_value(
			"Email Account", settings.sender_email_account, ["email_id", "name"], as_dict=True
		)
		if account:
			return f"{account.name} <{account.email_id}>"
	return None


def split_emails(raw):
	return [e.strip() for e in (raw or "").replace(",", "\n").splitlines() if e.strip()]


@frappe.whitelist()
def bulk_approve(names):
	"""Duyệt & gửi hàng loạt (FR-11): bản lỗi không chặn bản khác (US-03)."""
	C.require_manager()
	names = frappe.parse_json(names) if isinstance(names, str) else names
	result = {"ok": [], "failed": []}
	for name in names or []:
		try:
			frappe.db.savepoint("dr_bulk_approve")
			doc = frappe.get_doc(C.DOCTYPE, name)
			if doc.docstatus != 0:
				raise frappe.ValidationError(_("Không còn ở trạng thái Nháp"))
			doc.submit()
			result["ok"].append(name)
		except Exception as e:
			frappe.db.rollback(save_point="dr_bulk_approve")
			frappe.clear_last_message()
			result["failed"].append({"name": name, "error": str(e) or e.__class__.__name__})
	return result
