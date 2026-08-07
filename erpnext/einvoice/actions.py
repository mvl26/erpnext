# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Các nút gọi Fast trên chứng từ HĐĐT — Phần D và Phần E của đặc tả.

Mọi hàm ở đây đều đi qua ``gateway.call_fast`` nên tự động tuân thủ nguyên tắc
A1 (ghi log trước và sau lời gọi). Việc xác nhận của người dùng (Phần A2) nằm ở
tầng giao diện; phía server vẫn kiểm tra lại tiền điều kiện — không tin dữ liệu
client gửi lên.
"""

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime, time_diff_in_seconds

from erpnext.einvoice.constants import (
	STATUS_AWAITING_CUSTOMER,
	STATUS_CUSTOMER_APPROVED,
	STATUS_DRAFT,
	STATUS_DRAFT_VIEWED,
	STATUS_SENT,
)
from erpnext.einvoice.errors import describe_error
from erpnext.einvoice.fast_settings import check_enabled
from erpnext.einvoice.fast_client import decode_message
from erpnext.einvoice.gateway import call_fast
from erpnext.einvoice.payload import build_payload
from erpnext.einvoice.setup import DRAFT_TEMPLATE, ISSUED_TEMPLATE
from erpnext.einvoice.validation import validate_before_send

FEI = "Fast EInvoice Document"

# Bảng B2 — các trạng thái còn được phép xem bản nháp.
DRAFT_PREVIEW_STATUSES = frozenset(
	{
		"01 - Nháp",
		"02 - Đã xem nháp",
		"03 - Chờ khách duyệt",
		"04 - Khách đã duyệt",
		"98 - Cần đối soát",
		"99 - Lỗi",
	}
)

# Xem trước: Fast dựng PDF nhưng không ký số, không cấp số, không gửi CQT.
ACTION_PREVIEW = 600
ACTION_EXECUTE = 0
METHOD_INVOICE = 310


@frappe.whitelist()
def preview_draft(fei, client=None):
	"""Nút 3 — lấy bản nháp PDF từ Fast (mục E2).

	Không tiêu số hóa đơn: ``action=600`` chỉ dựng bản in thử. PDF thu được là
	**bản nháp không có giá trị pháp lý** cho tới khi thực sự phát hành.
	"""
	check_enabled()
	doc = frappe.get_doc(FEI, fei)
	_assert_status(doc, DRAFT_PREVIEW_STATUSES, _("xem bản nháp"))

	# Chặn trước khi tốn một lời gọi nào với Fast.
	validate_before_send(doc).throw_if_blocking()

	response = call_fast(
		doc,
		action=ACTION_PREVIEW,
		method=METHOD_INVOICE,
		data=build_payload(doc),
		purpose=_("Xem bản nháp PDF"),
		client=client,
	)

	if not response.success:
		_record_error(doc, response)
		return {"ok": False, "message": _explain(response)}

	file_url = _attach_pdf(doc, response.message, _draft_filename(doc))
	frappe.db.set_value(
		FEI,
		doc.name,
		{
			"draft_pdf": file_url,
			"draft_pdf_time": now_datetime(),
			"status": STATUS_DRAFT_VIEWED,
			"error_code": "",
			"error_message": "",
		},
		update_modified=False,
	)
	_mirror_status(doc.name, STATUS_DRAFT_VIEWED)
	return {"ok": True, "file_url": file_url}


# --- Tiện ích dùng chung cho các nút ----------------------------------------


def _assert_status(doc, allowed, what):
	if doc.status not in allowed:
		frappe.throw(
			_("Hóa đơn đang ở trạng thái {0} nên không {1} được.").format(doc.status, what)
		)


def _explain(response):
	described = describe_error(response.error_code, fallback=response.message)
	return f"{described.message} {described.hint}".strip()


def _record_error(doc, response):
	"""Ghi lỗi lên chứng từ nhưng **giữ nguyên trạng thái** (mục E2)."""
	frappe.db.set_value(
		FEI,
		doc.name,
		{"error_code": response.error_code or "", "error_message": _explain(response)},
		update_modified=False,
	)


def _attach_pdf(doc, base64_message, filename):
	"""Giải base64 rồi đính kèm vào chứng từ. File để riêng tư."""
	from frappe.utils.file_manager import save_file

	content = decode_message(base64_message)
	saved = save_file(filename, content, FEI, doc.name, is_private=1)
	return saved.file_url


def _draft_filename(doc):
	previous = frappe.db.count(
		"File", {"attached_to_doctype": FEI, "attached_to_name": doc.name, "file_name": ("like", "Nhap_%")}
	)
	return f"Nhap_{doc.name}_{previous + 1}.pdf"


def _mirror_status(fei_name, status):
	"""Đồng bộ trạng thái sang phiếu giao (mục C5)."""
	delivery_note = frappe.db.get_value(FEI, fei_name, "delivery_note")
	if delivery_note:
		frappe.db.set_value(
			"Delivery Note", delivery_note, "fast_einvoice_status", status, update_modified=False
		)


# --- Nút 4/5/6 — vòng duyệt bản nháp với khách hàng (mục E3, E4) -------------

# Bảng B2 — gửi bản nháp được phép ở các trạng thái này.
DRAFT_SEND_STATUSES = frozenset({STATUS_DRAFT_VIEWED, STATUS_AWAITING_CUSTOMER, STATUS_CUSTOMER_APPROVED})

MIN_FEEDBACK_LENGTH = 10


@frappe.whitelist()
def send_draft_to_customer(fei, recipients=None, cc=None, subject=None, message=None, mailer=None):
	"""Nút 4 — gửi bản nháp cho khách kiểm tra (mục E3).

	Nội dung email **bắt buộc** nói rõ đây là bản nháp chưa có giá trị pháp lý:
	bản PDF ở trạng thái 01–04 chưa có số hóa đơn, chưa ký số, chưa lên Cơ quan
	Thuế. Gửi mà không nói rõ là để khách hiểu nhầm đã có hóa đơn.
	"""
	check_enabled()
	doc = frappe.get_doc(FEI, fei)
	_assert_status(doc, DRAFT_SEND_STATUSES, _("gửi bản nháp"))

	if not doc.draft_pdf:
		frappe.throw(_("Chưa có bản nháp PDF — bấm “Xem bản nháp” trước khi gửi cho khách."))

	to = _recipient_list(recipients or doc.email_deliver)
	if not to:
		frappe.throw(_("Chưa có email người nhận."))

	rendered = _render_template(DRAFT_TEMPLATE, doc, subject, message)
	log = _open_email_log(doc, _("Gửi bản nháp cho khách hàng"), to)

	(mailer or frappe.sendmail)(
		recipients=to,
		cc=_recipient_list(cc),
		subject=rendered["subject"],
		message=rendered["message"],
		attachments=[{"file_url": doc.draft_pdf}],
		reference_doctype=FEI,
		reference_name=doc.name,
	)

	frappe.db.set_value(
		FEI,
		doc.name,
		{
			"draft_sent_to": ", ".join(to),
			"draft_sent_time": now_datetime(),
			"draft_send_count": (doc.draft_send_count or 0) + 1,
			"status": STATUS_AWAITING_CUSTOMER,
		},
		update_modified=False,
	)
	_close_email_log(log, ok=True)
	_mirror_status(doc.name, STATUS_AWAITING_CUSTOMER)
	doc.add_comment("Comment", _("Đã gửi bản nháp hóa đơn tới {0}.").format(", ".join(to)))
	return {"ok": True, "recipients": to}


@frappe.whitelist()
def record_customer_feedback(fei, feedback):
	"""Nút 5 — khách yêu cầu sửa (mục E4).

	Ghi **nối tiếp** vào lịch sử phản hồi, không ghi đè: đây là bằng chứng nội bộ
	khi có tranh chấp về nội dung hóa đơn.
	"""
	check_enabled()
	doc = frappe.get_doc(FEI, fei)
	_assert_status(doc, {STATUS_AWAITING_CUSTOMER}, _("ghi nhận ý kiến khách"))

	feedback = (feedback or "").strip()
	if len(feedback) < MIN_FEEDBACK_LENGTH:
		frappe.throw(
			_("Ghi rõ khách yêu cầu sửa gì (tối thiểu {0} ký tự) — đây là căn cứ để sửa hóa đơn.").format(
				MIN_FEEDBACK_LENGTH
			)
		)

	stamp = _("[{0} — {1}] {2}").format(
		frappe.utils.format_datetime(now_datetime()), frappe.session.user, feedback
	)
	history = f"{doc.customer_feedback}\n{stamp}" if doc.customer_feedback else stamp

	frappe.db.set_value(
		FEI,
		doc.name,
		{
			"customer_feedback": history,
			"status": STATUS_DRAFT,
			"revision_count": (doc.revision_count or 0) + 1,
		},
		update_modified=False,
	)
	_mirror_status(doc.name, STATUS_DRAFT)
	doc.add_comment("Comment", _("Khách yêu cầu sửa: {0}").format(feedback))
	return {"ok": True}


@frappe.whitelist()
def mark_customer_approved(fei, approved_by, channel="Email"):
	"""Nút 6 — khách đã duyệt bản nháp (mục E4).

	Bắt buộc ghi tên người xác nhận: "khách đã đồng ý" nói miệng không đứng vững
	khi có tranh chấp về nội dung hóa đơn.
	"""
	check_enabled()
	doc = frappe.get_doc(FEI, fei)
	_assert_status(doc, {STATUS_AWAITING_CUSTOMER}, _("ghi nhận khách duyệt"))

	approved_by = (approved_by or "").strip()
	if not approved_by:
		frappe.throw(_("Ghi rõ tên người bên khách hàng đã xác nhận duyệt bản nháp."))

	frappe.db.set_value(
		FEI,
		doc.name,
		{
			"customer_approved_by": approved_by,
			"customer_approved_time": now_datetime(),
			"status": STATUS_CUSTOMER_APPROVED,
		},
		update_modified=False,
	)
	_mirror_status(doc.name, STATUS_CUSTOMER_APPROVED)
	doc.add_comment(
		"Comment",
		_("Khách hàng đã duyệt bản nháp — xác nhận bởi {0} qua {1}.").format(approved_by, channel),
	)
	return {"ok": True}


# --- Tiện ích email ---------------------------------------------------------


def _recipient_list(value):
	if not value:
		return []
	if isinstance(value, list):
		return [v.strip() for v in value if v and v.strip()]
	return [part.strip() for part in str(value).replace(";", ",").split(",") if part.strip()]


def _render_template(template_name, doc, subject=None, message=None):
	"""Dựng nội dung từ Email Template, cho phép người gửi sửa lại."""
	if subject and message:
		return {"subject": subject, "message": message}

	template = frappe.get_doc("Email Template", template_name)
	context = {"doc": doc, "frappe": frappe}
	return {
		"subject": subject or frappe.render_template(template.subject, context),
		"message": message or frappe.render_template(template.response or "", context),
	}


def _open_email_log(doc, purpose, recipients):
	log = frappe.get_doc(
		{
			"doctype": "Fast EInvoice Log",
			"fei_document": doc.name,
			"operation": "Email",
			"purpose": purpose,
			"status": "Đang gửi",
			"request_json": frappe.as_json({"recipients": recipients}),
			"timestamp": now_datetime(),
		}
	)
	log.flags.ignore_permissions = True
	log.insert()
	return log


def _close_email_log(log, ok, error_message=None):
	frappe.db.set_value(
		"Fast EInvoice Log",
		log.name,
		{
			"status": "Thành công" if ok else "Lỗi",
			"success": 1 if ok else 0,
			"error_message": error_message,
		},
		update_modified=False,
	)


# --- Nút 8 & 9 — tải PDF chính thức / PDF chuyển đổi (mục E6) ---------------

METHOD_OFFICIAL_PDF = 380
METHOD_CONVERTED_PDF = 385

# Bảng B2 — hóa đơn đã có số thật thì mới có PDF chính thức để tải.
PDF_STATUSES = frozenset(
	{"06 - Đã phát hành", "07 - Đã gửi khách", "08 - CQT chấp nhận", "09 - CQT từ chối"}
)

# Đặc tả E6: hai lần gọi 380/385 phải cách nhau tối thiểu 5 giây.
PDF_THROTTLE_SECONDS = 5


@frappe.whitelist()
def download_official_pdf(fei, client=None):
	"""Nút 8 — tải bản PDF chính thức của hóa đơn đã phát hành."""
	doc = _pdf_ready_document(fei)
	_assert_pdf_throttle()

	response = call_fast(
		doc,
		action=ACTION_EXECUTE,
		method=METHOD_OFFICIAL_PDF,
		data={"key": doc.fast_key_search},
		purpose=_("Tải PDF chính thức"),
		client=client,
	)
	if not response.success:
		_record_error(doc, response)
		return {"ok": False, "message": _explain(response)}

	filename = f"HD_{doc.fast_serial or 'HD'}_{doc.fast_invoice_no or doc.name}.pdf"
	file_url = _attach_pdf(doc, response.message, filename)
	frappe.db.set_value(FEI, doc.name, "official_pdf", file_url, update_modified=False)

	# Bản PDF cũng đính sang phiếu giao: thủ kho và kế toán kho làm việc ở đó.
	if doc.delivery_note:
		_attach_pdf_to(doc, response.message, filename, "Delivery Note", doc.delivery_note)

	return {"ok": True, "file_url": file_url}


@frappe.whitelist()
def download_converted_pdf(fei, convert_name=None, client=None):
	"""Nút 9 — bản PDF chuyển đổi, dùng làm bản in giấy hợp lệ.

	Bản in giấy phải ghi tên người thực hiện chuyển đổi, nên tên là bắt buộc.
	"""
	doc = _pdf_ready_document(fei)

	convert_name = (convert_name or "").strip()
	if not convert_name:
		frappe.throw(_("Nhập tên người chuyển đổi — bản in giấy bắt buộc ghi tên này."))

	_assert_pdf_throttle()

	response = call_fast(
		doc,
		action=ACTION_EXECUTE,
		method=METHOD_CONVERTED_PDF,
		data={"key": doc.fast_key_search, "convertName": convert_name},
		purpose=_("Tải PDF chuyển đổi"),
		client=client,
	)
	if not response.success:
		_record_error(doc, response)
		return {"ok": False, "message": _explain(response)}

	filename = f"HDCD_{doc.fast_serial or 'HD'}_{doc.fast_invoice_no or doc.name}.pdf"
	file_url = _attach_pdf(doc, response.message, filename)
	frappe.db.set_value(FEI, doc.name, "converted_pdf", file_url, update_modified=False)
	return {"ok": True, "file_url": file_url}


def _pdf_ready_document(fei):
	check_enabled()
	doc = frappe.get_doc(FEI, fei)
	_assert_status(doc, PDF_STATUSES, _("tải PDF"))
	if not doc.fast_key_search:
		frappe.throw(
			_("Chứng từ chưa có mã tra cứu (keySearch) — bấm Truy vấn (370) để lấy về trước.")
		)
	return doc


def _assert_pdf_throttle():
	"""Chặn ở phía ta thay vì để Fast từ chối (đặc tả E6)."""
	last = frappe.db.get_value(
		"Fast EInvoice Log",
		{"method": ("in", [METHOD_OFFICIAL_PDF, METHOD_CONVERTED_PDF])},
		"creation",
		order_by="creation desc",
	)
	if not last:
		return
	elapsed = time_diff_in_seconds(now_datetime(), get_datetime(last))
	if elapsed < PDF_THROTTLE_SECONDS:
		frappe.throw(
			_("Vui lòng đợi {0} giây rồi tải lại — Fast giới hạn khoảng cách giữa hai lần tải PDF.").format(
				int(PDF_THROTTLE_SECONDS - elapsed) + 1
			)
		)


def _attach_pdf_to(doc, base64_message, filename, doctype, name):
	from frappe.utils.file_manager import save_file

	return save_file(filename, decode_message(base64_message), doctype, name, is_private=1).file_url


# --- Nút 10 — gửi hóa đơn chính thức cho khách hàng (mục E7) ----------------

METHOD_FAST_EMAIL = 700

# Bảng B2 — gửi hóa đơn chính thức được phép khi hóa đơn đã có số.
INVOICE_SEND_STATUSES = frozenset(
	{"06 - Đã phát hành", "07 - Đã gửi khách", "08 - CQT chấp nhận"}
)


@frappe.whitelist()
def send_invoice_to_customer(
	fei, recipients=None, cc=None, subject=None, message=None, via="erp", mailer=None, client=None
):
	"""Nút 10 — gửi hóa đơn đã phát hành cho khách (mục E7).

	``via="erp"`` (mặc định, phương án A khuyến nghị): ERP tự gửi, nội dung nằm
	trong Communication của ERP nên tra lại được khi khách nói chưa nhận.
	``via="fast"`` (phương án B): nhờ Fast gửi bằng method 700, dùng khi cần
	đúng mẫu email của portal.
	"""
	check_enabled()
	doc = frappe.get_doc(FEI, fei)
	_assert_status(doc, INVOICE_SEND_STATUSES, _("gửi hóa đơn cho khách"))

	to = _recipient_list(recipients or doc.email_deliver)
	if not to:
		frappe.throw(_("Chưa có email người nhận."))

	if via == "fast":
		return _send_invoice_via_fast(doc, to, client)
	return _send_invoice_via_erp(doc, to, cc, subject, message, mailer)


def _send_invoice_via_erp(doc, to, cc, subject, message, mailer):
	if not doc.official_pdf:
		frappe.throw(
			_("Chưa tải PDF chính thức — bấm “Tải PDF” trước, nếu không khách nhận email không có hóa đơn.")
		)

	rendered = _render_template(ISSUED_TEMPLATE, doc, subject, message)
	log = _open_email_log(doc, _("Gửi hóa đơn chính thức cho khách"), to)

	(mailer or frappe.sendmail)(
		recipients=to,
		cc=_recipient_list(cc),
		subject=rendered["subject"],
		message=rendered["message"],
		attachments=[{"file_url": doc.official_pdf}],
		reference_doctype=FEI,
		reference_name=doc.name,
	)
	_close_email_log(log, ok=True)
	_mark_invoice_sent(doc, to)
	return {"ok": True, "recipients": to}


def _send_invoice_via_fast(doc, to, client):
	if not doc.fast_key_search:
		frappe.throw(_("Chứng từ chưa có mã tra cứu (keySearch)."))

	response = call_fast(
		doc,
		action=ACTION_EXECUTE,
		method=METHOD_FAST_EMAIL,
		data={"key": doc.fast_key_search, "email": ", ".join(to)},
		purpose=_("Nhờ Fast gửi hóa đơn cho khách"),
		client=client,
	)
	if not response.success:
		_record_error(doc, response)
		return {"ok": False, "message": _explain(response)}

	_mark_invoice_sent(doc, to)
	return {"ok": True, "recipients": to}


def _mark_invoice_sent(doc, to):
	frappe.db.set_value(
		FEI,
		doc.name,
		{
			"invoice_sent_to": ", ".join(to),
			"invoice_sent_time": now_datetime(),
			"invoice_send_count": (doc.invoice_send_count or 0) + 1,
			"status": STATUS_SENT,
		},
		update_modified=False,
	)
	_mirror_status(doc.name, STATUS_SENT)
	doc.add_comment("Comment", _("Đã gửi hóa đơn chính thức tới {0}.").format(", ".join(to)))
