# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nút 11 và job nền — trạng thái Cơ quan Thuế (method 8200) — mục E8.

Đây là **hành động đọc**: không đổi dữ liệu hóa đơn, chỉ ghi nhận CQT đã chấp
nhận hay từ chối. Vì vậy job nền được phép tự chạy mà không hỏi người dùng —
nhưng vẫn ghi log đầy đủ như mọi lời gọi khác (nguyên tắc A3).
"""

import json
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, getdate, now_datetime, nowdate

from erpnext.einvoice.actions import ACTION_EXECUTE, FEI, _explain, _mirror_status
from erpnext.einvoice.constants import (
	STATUS_ISSUED,
	STATUS_SENT,
	STATUS_TAX_ACCEPTED,
	STATUS_TAX_REJECTED,
	TAX_STATUS_ACCEPTED,
	TAX_STATUS_PENDING,
	TAX_STATUS_REJECTED,
)
from erpnext.einvoice.fast_client import FastClient
from erpnext.einvoice.fast_settings import check_enabled, get_notify_recipients, get_settings
from erpnext.einvoice.gateway import call_fast

METHOD_TAX_STATUS = 8200

# Bảng B2 — hóa đơn đã phát hành hoặc đã gửi khách thì mới có trạng thái CQT.
TAX_CHECK_STATUSES = frozenset({STATUS_ISSUED, STATUS_SENT})

# Nhịp hỏi CQT giãn dần theo tuổi hóa đơn: (tuổi tối đa tính bằng giờ, khoảng
# cách tối thiểu giữa hai lần hỏi tính bằng phút). CQT cấp mã thường trong vài
# phút; hóa đơn còn chờ sau đó thì hỏi dồn cũng không nhanh hơn, chỉ đẻ thêm lời
# gọi và dòng nhật ký — hỏi 20 phút/lần suốt 7 ngày là ~500 lời gọi cho một hóa
# đơn kẹt. Quá mốc cuối thì thôi tự hỏi: báo cáo đối soát đã gom hóa đơn chờ CQT
# quá 24 giờ, người xử lý bấm nút 11 hoặc hỏi Fast.
POLL_SCHEDULE = (
	(2, 0),  # 2 giờ đầu: mỗi lượt cron (20 phút)
	(24, 120),  # tới hết ngày đầu: 2 giờ/lần
	(72, 720),  # tới hết ngày thứ ba: 12 giờ/lần
)
# Cron chạy lệch vài giây mỗi lượt — không có dung sai thì nhịp 2 giờ thành 2 giờ 20.
POLL_TOLERANCE = timedelta(minutes=5)
# Lọc thô trong SQL theo ngày ký (chỉ có ngày, không có giờ). Mốc chính xác là
# `POLL_SCHEDULE`; cửa sổ này chỉ cần phủ được mốc cuối.
POLL_WINDOW_DAYS = 3

# Loại chứng từ truy vấn (tài liệu Fast mục 17): 1 - Hóa đơn, 2 - Phiếu xuất kho.
# Module này chỉ phát hành hóa đơn (310/320/350) nên luôn hỏi loại 1.
INVOICE_TYPE_INVOICE = "1"

# Kết quả 8200 (tài liệu Fast mục 17, tr. 38-39):
#   {"data":[{"key":…,"invoiceDate":…,"taxStatus":"3","verificationCode":…,
#             "feedbackContent":…}]}
# `key` là Key client gửi lên lúc phát hành (`fast_key`) — KHÔNG phải keySearch.
_STATUS_MAP = {"3": TAX_STATUS_ACCEPTED, "4": TAX_STATUS_REJECTED}


def parse_tax_status(message, key=None, invoice_no=None):
	"""Tìm bản ghi của hóa đơn này trong kết quả 8200. ``None`` = CQT chưa xử lý."""
	try:
		payload = json.loads(message or "")
	except ValueError:
		return None

	rows = _rows(payload)
	for row in rows:
		if not isinstance(row, dict):
			continue
		# Fast đệm khoảng trắng quanh cả tên thẻ lẫn giá trị (ví dụ ở tài liệu mục 17:
		# `" taxStatus ":"3"`) — so nguyên văn thì không bao giờ khớp, hóa đơn kẹt "Chờ CQT".
		lowered = {str(name).strip().lower(): value for name, value in row.items()}
		if key and _text(lowered.get("key")) == _text(key):
			return _normalise(lowered)
		if invoice_no and _text(lowered.get("invoiceno")) == _text(invoice_no):
			return _normalise(lowered)
	return None


def _text(value):
	return str(value or "").strip()


def _rows(payload):
	"""Danh sách hóa đơn trong Message — bọc trong thẻ ``data`` theo tài liệu."""
	if isinstance(payload, dict):
		inner = payload.get("data")
		if isinstance(inner, list):
			return inner
		return [payload]
	return payload if isinstance(payload, list) else []


def _normalise(row):
	return {
		"tax_status": _STATUS_MAP.get(_text(row.get("taxstatus")), TAX_STATUS_PENDING),
		"tax_verification_code": _text(row.get("verificationcode")),
		"tax_feedback": _text(row.get("feedbackcontent")),
	}


@frappe.whitelist()
def check_tax_status(fei, client=None):
	"""Nút 11 — hỏi Fast xem Cơ quan Thuế đã xử lý hóa đơn này chưa."""
	check_enabled()
	doc = frappe.get_doc(FEI, fei)
	if doc.status not in TAX_CHECK_STATUSES:
		frappe.throw(
			_("Hóa đơn đang ở trạng thái {0} nên chưa có trạng thái CQT để kiểm tra.").format(doc.status)
		)
	return _apply_tax_status(doc, client)


def _apply_tax_status(doc, client=None):
	response = call_fast(
		doc,
		action=ACTION_EXECUTE,
		method=METHOD_TAX_STATUS,
		data=_query_payload(doc),
		purpose=_("Kiểm tra trạng thái Cơ quan Thuế"),
		client=client,
	)

	values = {"tax_checked_time": now_datetime()}
	if not response.success:
		frappe.db.set_value(FEI, doc.name, values, update_modified=False)
		return {"ok": False, "message": _explain(response)}

	found = parse_tax_status(response.message, doc.fast_key, doc.fast_invoice_no)
	if not found:
		# Không có trong kết quả = CQT chưa xử lý xong. Đây KHÔNG phải từ chối.
		frappe.db.set_value(FEI, doc.name, values, update_modified=False)
		return {"ok": True, "tax_status": TAX_STATUS_PENDING, "pending": True}

	values.update(found)
	if found["tax_status"] == TAX_STATUS_ACCEPTED:
		values["status"] = STATUS_TAX_ACCEPTED
	elif found["tax_status"] == TAX_STATUS_REJECTED:
		values["status"] = STATUS_TAX_REJECTED

	frappe.db.set_value(FEI, doc.name, values, update_modified=False)
	if values.get("status"):
		_mirror_status(doc.name, values["status"])
	if found["tax_status"] == TAX_STATUS_REJECTED:
		_notify_rejection(doc, found["tax_feedback"])

	return {"ok": True, "tax_status": found["tax_status"]}


def _query_payload(doc):
	"""Chuỗi data của 8200 — **phải đủ cả 6 thẻ**, thẻ không bắt buộc để rỗng.

	Thiếu một thẻ thì Fast ném ``810 - The given key was not present in the
	dictionary`` (nó đọc thẳng khóa trong dictionary chứ không kiểm tra trước).
	Khoảng số hóa đơn thu hẹp kết quả về đúng hóa đơn này thay vì cả ngày.

	Thẻ ngày lọc theo **ngày hóa đơn** — ``InvoiceDate`` đã gửi lúc phát hành, tức
	ngày phiếu giao — chứ không phải ngày ký. Phát hành sau ngày giao hàng thì hai
	ngày lệch nhau; chỉ hỏi theo ngày ký là Fast trả rỗng và hóa đơn kẹt "Chờ CQT"
	mãi. Lấy khoảng bao cả hai: số hóa đơn đã khóa đúng một hóa đơn nên nới ngày
	không kéo thêm hóa đơn nào khác về.
	"""
	dates = sorted(getdate(value) for value in (doc.invoice_date, doc.fast_signed_date) if value)
	number = str(doc.fast_invoice_no or "")
	return {
		"invoiceDateFrom": _yyyymmdd(dates[0]) if dates else "",
		"invoiceDateTo": _yyyymmdd(dates[-1]) if dates else "",
		"invoiceNumberFrom": number,
		"invoiceNumberTo": number,
		"voucherBook": "",
		"invoiceType": INVOICE_TYPE_INVOICE,
	}


def _yyyymmdd(value):
	return getdate(value).strftime("%Y%m%d") if value else ""


def poll_pending_tax_status(client=None):
	"""Job nền 20 phút — quét các hóa đơn còn chờ Cơ quan Thuế.

	Trả danh sách tên chứng từ đã kiểm tra (phục vụ test và nhật ký vận hành).
	"""
	settings = get_settings()
	if not settings.enabled or not settings.auto_poll_tax_status:
		return []

	candidates = frappe.get_all(
		FEI,
		filters={
			"tax_status": TAX_STATUS_PENDING,
			"status": ("in", list(TAX_CHECK_STATUSES)),
			"fast_signed_date": (">=", add_to_date(nowdate(), days=-POLL_WINDOW_DAYS)),
		},
		fields=["name", "issued_time", "fast_signed_date", "tax_checked_time"],
	)
	now = now_datetime()
	pending = [row.name for row in candidates if _is_due(row, now)]
	if not pending:
		return []

	# Một client cho cả lô: token xác minh một lần thay vì mỗi hóa đơn một vòng.
	client = client or FastClient()
	checked = []
	for name in pending:
		try:
			_apply_tax_status(frappe.get_doc(FEI, name), client)
			checked.append(name)
		except Exception:
			# Một hóa đơn hỏng không được làm chết cả lô.
			frappe.log_error(title=f"HĐĐT: không kiểm tra được trạng thái CQT của {name}")
	return checked


def _is_due(row, now):
	"""Hóa đơn này đã tới lượt hỏi CQT chưa — theo ``POLL_SCHEDULE``.

	``tax_checked_time`` ghi cả khi lời gọi hỏng, nên Fast lỗi cũng bị giãn nhịp
	chứ không bị gọi dồn.
	"""
	issued = get_datetime(row.issued_time or row.fast_signed_date)
	age_hours = (now - issued).total_seconds() / 3600
	for max_age_hours, gap_minutes in POLL_SCHEDULE:
		if age_hours < max_age_hours:
			if not row.tax_checked_time:
				return True
			waited = now - get_datetime(row.tax_checked_time)
			return waited >= timedelta(minutes=gap_minutes) - POLL_TOLERANCE
	return False


def _notify_rejection(doc, reason):
	recipients = get_notify_recipients()
	if not recipients:
		return
	try:
		frappe.sendmail(
			recipients=recipients,
			subject=_("[HĐĐT] Cơ quan Thuế TỪ CHỐI hóa đơn {0}").format(doc.fast_invoice_no or doc.name),
			message=_(
				"<p>Hóa đơn <b>{0}</b> (chứng từ {1}) bị Cơ quan Thuế từ chối.</p><p>Lý do: {2}</p>"
			).format(doc.fast_invoice_no or "?", doc.name, frappe.utils.escape_html(reason or "—")),
			reference_doctype=FEI,
			reference_name=doc.name,
		)
	except Exception:
		frappe.log_error(title=f"HĐĐT: không gửi được cảnh báo CQT từ chối cho {doc.name}")
