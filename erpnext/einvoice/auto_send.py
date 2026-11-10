# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tự gửi hóa đơn cho khách sau phát hành (phân tích "Tự gửi HĐĐT", mục 6.2; Q1, Q3, Q4).

Chạy ở cuối mỗi lượt của job tải PDF chính thức (mỗi phút), nên hóa đơn vừa có
PDF được gửi ngay trong cùng lượt — tách cron riêng thì hai job chạy song song trên
hai worker và lệch nhau một phút.

ERP là kênh gửi duy nhất (Q1: Fast không tự gửi mail), người nhận luôn là ``Email
nhận hóa đơn`` (Q3), và bật/tắt chỉ bằng ô ``auto_send_invoice`` (Q4). Mẫu Miyano
yêu cầu chỉ gửi khi đã có mã của Cơ quan Thuế, nên hóa đơn chưa có mã thì hỏi CQT
(8200) riêng cho nó trước khi gửi.
"""

import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime, time_diff_in_seconds

from erpnext.einvoice.actions import FEI, _recipient_list, _send_invoice_via_erp
from erpnext.einvoice.constants import STATUS_ISSUED, STATUS_TAX_ACCEPTED, STATUS_TAX_REJECTED
from erpnext.einvoice.fast_settings import get_notify_recipients, get_settings

# 06 lên 07 sau khi gửi; 08 giữ nguyên 08 — cùng quy tắc với gửi tay (nút 10).
AUTO_SEND_STATUSES = (STATUS_ISSUED, STATUS_TAX_ACCEPTED)
# Bật tính năng lên không gửi bù hóa đơn cũ.
AUTO_SEND_WINDOW_HOURS = 24
# CQT thường cấp mã trong vài phút; quá mốc này thì chuyển sang gửi tay.
AUTO_SEND_TAX_WAIT_MINUTES = 30
AUTO_SEND_MAX_FAILURES = 3
# Mục đích ghi trên nhật ký email — cũng là khóa để đếm số lần tự gửi lỗi.
AUTO_SEND_PURPOSE = "Tự gửi hóa đơn cho khách"
# Job chạy mỗi phút; hỏi CQT dày hơn thế không nhanh hơn, chỉ thêm lời gọi.
TAX_RECHECK_SECONDS = 60


def send_pending_invoices(client=None, mailer=None):
	"""Gửi các hóa đơn vừa phát hành đã đủ điều kiện. Trả tên các chứng từ **đã gửi** trong lượt."""
	settings = get_settings()
	if not settings.enabled or not settings.auto_send_invoice:
		return []

	now = now_datetime()
	candidates = frappe.get_all(
		FEI,
		filters=[
			[FEI, "status", "in", list(AUTO_SEND_STATUSES)],
			[FEI, "official_pdf", "is", "set"],
			[FEI, "invoice_send_count", "=", 0],
			[FEI, "auto_send_stopped", "=", 0],
			[FEI, "issued_time", ">=", add_to_date(now, hours=-AUTO_SEND_WINDOW_HOURS)],
		],
		order_by="issued_time asc",
		pluck="name",
	)

	sent = []
	for name in candidates:
		try:
			if _send_one(name, settings, client, mailer, now):
				sent.append(name)
		except Exception:
			# Một hóa đơn hỏng không được làm chết cả lô.
			frappe.log_error(title=f"HĐĐT: tự gửi hóa đơn lỗi cho {name}")
	return sent


def _send_one(name, settings, client, mailer, now):
	doc = frappe.get_doc(FEI, name)
	to = _recipient_list(doc.email_deliver)
	if not to:
		# Thiếu người nhận không phải lỗi: kế toán điền email rồi gửi tay.
		return False

	if not doc.fast_lookup_code:
		_stop(
			doc,
			_(
				"Không đọc được mã tra cứu từ PDF — chép mã vào chứng từ rồi bấm "
				"Gửi hóa đơn cho khách để gửi tay."
			),
			mailer,
		)
		return False

	if not doc.tax_verification_code and not _has_tax_code(doc, client, now, mailer):
		return False

	# Chống gửi trùng: kế toán có thể vừa bấm nút 10, hoặc một worker khác đang chạy
	# cùng lượt. Khóa dòng tới hết giao dịch của job rồi mới quyết định.
	locked = frappe.db.sql(
		f"select invoice_send_count from `tab{FEI}` where name=%s for update", name, as_dict=True
	)
	if not locked or locked[0].invoice_send_count:
		return False

	from erpnext.einvoice.invoice_email import sender_for

	try:
		_send_invoice_via_erp(
			doc,
			to,
			None,
			None,
			None,
			mailer,
			sender=sender_for(settings, None),
			purpose=AUTO_SEND_PURPOSE,
			auto=True,
		)
	except Exception:
		frappe.log_error(title=f"HĐĐT: tự gửi hóa đơn lỗi cho {name}")
		failures = frappe.db.count(
			"Fast EInvoice Log",
			{"fei_document": name, "operation": "Email", "purpose": AUTO_SEND_PURPOSE, "success": 0},
		)
		if failures >= AUTO_SEND_MAX_FAILURES:
			_stop(
				doc,
				_("Tự gửi lỗi {0} lần — bấm Gửi hóa đơn cho khách để gửi tay.").format(failures),
				mailer,
			)
		return False
	return True


def _has_tax_code(doc, client, now, mailer):
	"""Hỏi CQT cho riêng hóa đơn này nếu tới lượt. ``True`` = đã có mã, gửi được."""
	from erpnext.einvoice.tax_status import _apply_tax_status

	checked = doc.tax_checked_time
	if not checked or time_diff_in_seconds(now, get_datetime(checked)) >= TAX_RECHECK_SECONDS:
		try:
			_apply_tax_status(doc, client)
		except Exception:
			# Fast mất kết nối không được chặn mốc 30 phút: quá mốc là phải báo gửi tay.
			frappe.log_error(title=f"HĐĐT: tự gửi không hỏi được CQT cho {doc.name}")
		doc.reload()

	if doc.status == STATUS_TAX_REJECTED:
		# Cảnh báo CQT từ chối đã gửi ở `tax_status`; hóa đơn này không được gửi khách.
		return False
	if doc.tax_verification_code:
		return True

	waited = time_diff_in_seconds(now, get_datetime(doc.issued_time)) if doc.issued_time else 0
	if waited > AUTO_SEND_TAX_WAIT_MINUTES * 60:
		_stop(
			doc,
			_("Quá {0} phút chưa có mã của Cơ quan Thuế — bấm Gửi hóa đơn cho khách khi đã có mã.").format(
				AUTO_SEND_TAX_WAIT_MINUTES
			),
			mailer,
		)
	return False


def _stop(doc, reason, mailer=None):
	"""Thôi tự gửi hóa đơn này: đánh dấu, ghi comment, báo người nhận cảnh báo — đúng một lần."""
	frappe.db.set_value(FEI, doc.name, "auto_send_stopped", 1, update_modified=False)
	doc.add_comment("Comment", reason)

	recipients = get_notify_recipients()
	if not recipients:
		return
	try:
		(mailer or frappe.sendmail)(
			recipients=recipients,
			subject=_("[HĐĐT] Cần gửi tay hóa đơn {0}").format(doc.fast_invoice_no or doc.name),
			message=_("<p>Hóa đơn <b>{0}</b> (chứng từ {1}) chưa được gửi cho khách.</p><p>{2}</p>").format(
				doc.fast_invoice_no or "?", doc.name, frappe.utils.escape_html(reason)
			),
			reference_doctype=FEI,
			reference_name=doc.name,
		)
	except Exception:
		frappe.log_error(title=f"HĐĐT: không gửi được cảnh báo tự gửi cho {doc.name}")
