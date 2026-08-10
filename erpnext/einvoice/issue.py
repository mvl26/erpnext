# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nút 7 — PHÁT HÀNH HÓA ĐƠN (mục E5). **Hành động không thể hoàn tác.**

Phát hành thành công là tiêu một số hóa đơn thật và đẩy dữ liệu lên Cơ quan
Thuế. Không xóa được, không sửa được — muốn thay đổi phải lập hóa đơn điều
chỉnh hoặc thay thế. Vì vậy trình tự dưới đây bám sát mục E5 và **không được
rút gọn**:

```
1. Chiếm khóa theo tên chứng từ            (chống bấm đúp — A4 quy tắc 4)
2. Chạy lại toàn bộ validate               (không tin dữ liệu từ client)
3. Truy vấn 370 với fast_key               (chống phát hành lặp — lỗi 835)
4. Ghi log + đặt trạng thái 05 + COMMIT    (còn bằng chứng nếu server sập)
5. Lấy token
6. ExcuteCommand(action=0, method=310)     ← lời gọi quyết định
7a/7b/7c. Thành công / lỗi / timeout
8. Nhả khóa
```
"""

import json
import re

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime

from erpnext.einvoice.actions import (
	ACTION_EXECUTE,
	FEI,
	METHOD_INVOICE,
	_explain,
	_mirror_status,
)
from erpnext.einvoice.constants import (
	INVOICE_TYPE_ADJUSTMENT,
	INVOICE_TYPE_REPLACEMENT,
	ISSUED_STATUSES,
	STATUS_CUSTOMER_APPROVED,
	STATUS_DRAFT,
	STATUS_DRAFT_VIEWED,
	STATUS_ERROR,
	STATUS_ISSUED,
	STATUS_ISSUING,
	STATUS_NEEDS_RECONCILE,
	TAX_STATUS_PENDING,
)
from erpnext.einvoice.errors import is_duplicate_invoice_error
from erpnext.einvoice.fast_client import FastClient, FastTimeout
from erpnext.einvoice.fast_settings import check_enabled, get_notify_recipients
from erpnext.einvoice.gateway import call_fast
from erpnext.einvoice.payload import build_payload
from erpnext.einvoice.setup import is_chief_accountant
from erpnext.einvoice.validation import validate_before_send

METHOD_QUERY = 370

# Mỗi loại chứng từ đi bằng một method riêng (bảng action/method Phần I).
METHOD_ADJUSTMENT = 320
METHOD_REPLACEMENT = 350

# Fast trả 888 khi không tìm thấy hóa đơn = chưa phát hành lần nào = an toàn.
ERROR_NOT_FOUND = "888"

# Khóa giữ tối đa 5 phút — dài hơn timeout mạng để lệnh đang bay không bị lệnh
# thứ hai chen vào, nhưng vẫn tự nhả nếu tiến trình chết.
LOCK_TTL_SECONDS = 300

# Trạng thái được phép phát hành, tùy cấu hình bắt buộc khách duyệt (mục E5).
ISSUABLE_WITH_APPROVAL = frozenset({STATUS_CUSTOMER_APPROVED})
ISSUABLE_WITHOUT_APPROVAL = frozenset(
	{STATUS_DRAFT, STATUS_DRAFT_VIEWED, STATUS_CUSTOMER_APPROVED, STATUS_ERROR}
)

# ⚠️ SUY RA, CHƯA XÁC NHẬN VỚI FAST ⚠️
# Đặc tả nói "parse Message → lưu invoiceNo, keySearch, pattern, serial,
# signedDate" nhưng không cho ví dụ chuỗi trả về. Bộ đọc dưới đây thử JSON
# trước, rồi tới chuỗi ngăn bằng dấu | theo thứ tự này. Response thô luôn được
# giữ trong nhật ký để đối chiếu khi khớp lại với Fast thật.
PIPE_ORDER = ("fast_invoice_no", "fast_pattern", "fast_serial", "fast_signed_date", "fast_key_search")

_JSON_KEYS = {
	"invoiceno": "fast_invoice_no",
	"pattern": "fast_pattern",
	"serial": "fast_serial",
	"signeddate": "fast_signed_date",
	"keysearch": "fast_key_search",
}


def parse_issue_result(message):
	"""Bóc số hóa đơn / ký hiệu / mã tra cứu khỏi Message của Fast."""
	message = (message or "").strip()
	result = {"raw": message}

	parsed = _parse_json(message) or _parse_pipe(message)
	result.update(parsed or {})

	if signed := result.get("fast_signed_date"):
		result["fast_signed_date"] = _parse_signed_date(signed)
	return result


def _parse_json(message):
	if message[:1] not in ("{", "["):
		return None
	try:
		raw = json.loads(message)
	except ValueError:
		return None
	# Phát hành HSM trả Message là **mảng** các hóa đơn: [{"invoiceNo":…}]. Mỗi lần
	# ta chỉ phát hành một hóa đơn nên lấy phần tử đầu.
	if isinstance(raw, list):
		raw = raw[0] if raw else {}
	if not isinstance(raw, dict):
		return None
	return {
		_JSON_KEYS[key.lower()]: str(value)
		for key, value in raw.items()
		if key.lower() in _JSON_KEYS and value not in (None, "")
	}


def _parse_pipe(message):
	if "|" not in message:
		return None
	parts = [part.strip() for part in message.split("|")]
	return {
		field: parts[index] for index, field in enumerate(PIPE_ORDER) if index < len(parts) and parts[index]
	}


def _parse_signed_date(value):
	"""Fast trả ngày dạng yyyyMMdd (mục C2.4 #64)."""
	text = str(value).strip()
	if re.fullmatch(r"\d{8}", text):
		return getdate(f"{text[:4]}-{text[4:6]}-{text[6:]}")
	try:
		return getdate(text)
	except Exception:
		return None


@frappe.whitelist()
def issue_invoice(fei, client=None):
	"""Phát hành hóa đơn điện tử chính thức. Không thể hoàn tác."""
	check_enabled()
	if not is_chief_accountant():
		raise frappe.PermissionError(
			_("Chỉ Kế toán trưởng HĐĐT được phát hành hóa đơn — đây là hành động không thể hoàn tác.")
		)

	doc = frappe.get_doc(FEI, fei)
	_assert_issuable(doc)

	client = client or FastClient()
	with _issuance_lock(doc.name):
		# Đọc lại sau khi có khóa: giữa lúc bấm nút và lúc chiếm được khóa, một
		# tiến trình khác có thể đã phát hành xong.
		doc.reload()
		_assert_issuable(doc)

		# Bước 2 — không tin dữ liệu client gửi lên.
		validate_before_send(doc).throw_if_blocking()

		# Bước 3 — chống phát hành lặp.
		_precheck_not_already_issued(doc, client)

		# Bước 4—6.
		try:
			response = call_fast(
				doc,
				action=ACTION_EXECUTE,
				method=_method_for(doc),
				data=build_payload(doc),
				purpose=_("Phát hành hóa đơn"),
				processing_status=STATUS_ISSUING,
				client=client,
			)
		except FastTimeout as exc:
			return _handle_timeout(doc, exc)

		if not response.success:
			return _handle_failure(doc, response)
		return _handle_success(doc, response)


def _method_for(doc):
	"""Hóa đơn gốc đi 310, điều chỉnh đi 320, thay thế đi 350."""
	if doc.invoice_type == INVOICE_TYPE_ADJUSTMENT:
		return METHOD_ADJUSTMENT
	if doc.invoice_type == INVOICE_TYPE_REPLACEMENT:
		return METHOD_REPLACEMENT
	return METHOD_INVOICE


def _assert_issuable(doc):
	if doc.status in ISSUED_STATUSES:
		frappe.throw(
			_("Hóa đơn {0} đã phát hành (trạng thái {1}) — không phát hành lại.").format(doc.name, doc.status)
		)
	if doc.status == STATUS_ISSUING:
		frappe.throw(_("Hóa đơn đang được phát hành, vui lòng đợi."))

	settings = check_enabled()
	allowed = ISSUABLE_WITH_APPROVAL if settings.require_customer_approval else ISSUABLE_WITHOUT_APPROVAL
	if doc.status not in allowed:
		frappe.throw(
			_("Hóa đơn đang ở trạng thái {0} nên chưa phát hành được. Cần: {1}.").format(
				doc.status, ", ".join(sorted(allowed))
			)
		)


class _issuance_lock:
	"""Khóa chống bấm đúp theo tên chứng từ (nguyên tắc A4 quy tắc 4)."""

	def __init__(self, name):
		# Khóa đặt và xóa bằng cùng một API raw của Redis. `set_value`/`delete_value`
		# của Frappe tự thêm tiền tố site nên trộn hai lối là khóa không bao giờ
		# được nhả. Tiền tố site tự gắn ở đây để nhiều site dùng chung Redis vẫn tách nhau.
		self.key = f"{frappe.local.site}|fast-einvoice-issue|{name}"
		self.acquired = False

	def __enter__(self):
		try:
			self.acquired = bool(frappe.cache().set(self.key, "1", ex=LOCK_TTL_SECONDS, nx=True))
		except Exception:
			# Redis hỏng không được phép chặn việc phát hành: trạng thái 05 trong
			# cơ sở dữ liệu vẫn là chốt chống bấm đúp thứ hai.
			self.acquired = True
			return self
		if not self.acquired:
			frappe.throw(_("Hóa đơn này đang được phát hành ở một phiên khác, vui lòng đợi."))
		return self

	def __exit__(self, *exc):
		if self.acquired:
			try:
				frappe.cache().delete(self.key)
			except Exception:
				pass


def _precheck_not_already_issued(doc, client):
	"""Bước 3 — truy vấn 370 trước khi phát hành (nguyên tắc A4 quy tắc 1).

	Fast trả Success=1 nghĩa là **đã có** hóa đơn với Key này: dừng lại, kéo
	thông tin về, không phát hành nữa. Mã 888 nghĩa là chưa có, đi tiếp.
	"""
	response = call_fast(
		doc,
		action=ACTION_EXECUTE,
		method=METHOD_QUERY,
		data={"key": doc.fast_key, "period": _period(doc)},
		purpose=_("Truy vấn trước khi phát hành"),
		client=client,
	)

	if response.success:
		found = parse_issue_result(response.message)
		_store_issue_result(doc, found, issued_now=False)
		frappe.throw(
			_("Hóa đơn này đã được phát hành trước đó (số {0}, mã tra cứu {1}). Không phát hành lại.").format(
				found.get("fast_invoice_no") or "?", found.get("fast_key_search") or "?"
			)
		)

	if response.error_code == ERROR_NOT_FOUND:
		return

	if is_duplicate_invoice_error(response.error_code):
		frappe.throw(_explain(response))

	# 370 hỏng vì lý do khác. Nếu chứng từ này từng được gửi đi thì không đoán
	# nữa — bắt đối soát tay, vì đoán sai là hai số hóa đơn.
	if _has_prior_issue_attempt(doc):
		frappe.throw(
			_(
				"Không truy vấn được tình trạng hóa đơn trên Fast ({0}), mà chứng từ này đã từng gửi đi. "
				"Phải đối soát thủ công trước khi phát hành."
			).format(_explain(response))
		)


def _period(doc):
	"""Kỳ truy vấn dạng yyyyMM (mục E8)."""
	return getdate(doc.invoice_date).strftime("%Y%m")


def _has_prior_issue_attempt(doc):
	return bool(
		frappe.db.exists(
			"Fast EInvoice Log",
			{"fei_document": doc.name, "method": _method_for(doc), "action": ACTION_EXECUTE},
		)
	)


# --- Nhánh 7a / 7b / 7c ------------------------------------------------------


def _handle_success(doc, response):
	"""7a — hóa đơn đã có số thật."""
	result = parse_issue_result(response.message)
	_store_issue_result(doc, result, issued_now=True)

	# Hóa đơn gốc chỉ bị khóa khi bản điều chỉnh/thay thế đã thực sự có số.
	from erpnext.einvoice.lineage import mark_original_superseded

	mark_original_superseded(doc)

	try:
		_queue_pdf_download(doc)
	except Exception:
		# Hóa đơn đã ra số thật rồi — không được để việc tải PDF làm hỏng kết quả.
		frappe.log_error(title=f"HĐĐT: không hẹn được việc tải PDF cho {doc.name}")

	return {
		"ok": True,
		"invoice_no": result.get("fast_invoice_no"),
		"serial": result.get("fast_serial"),
		"key_search": result.get("fast_key_search"),
		"message": _("Phát hành thành công — hóa đơn số {0}, ký hiệu {1}.").format(
			result.get("fast_invoice_no") or "?", result.get("fast_serial") or "?"
		),
	}


def _store_issue_result(doc, result, issued_now):
	values = {
		"fast_invoice_no": result.get("fast_invoice_no") or "",
		"fast_pattern": result.get("fast_pattern") or "",
		"fast_serial": result.get("fast_serial") or "",
		"fast_key_search": result.get("fast_key_search") or "",
		"fast_signed_date": result.get("fast_signed_date"),
		"status": STATUS_ISSUED,
		"tax_status": TAX_STATUS_PENDING,
		"error_code": "",
		"error_message": "",
	}
	if issued_now:
		values["issued_by"] = frappe.session.user
		values["issued_time"] = now_datetime()

	frappe.db.set_value(FEI, doc.name, values, update_modified=False)
	_stamp_delivery_note(doc, result)
	_mirror_status(doc.name, STATUS_ISSUED)


def _stamp_delivery_note(doc, result):
	if not doc.delivery_note:
		return
	frappe.db.set_value(
		"Delivery Note",
		doc.delivery_note,
		{
			"fast_invoice_no": result.get("fast_invoice_no") or "",
			"fast_key_search": result.get("fast_key_search") or "",
		},
		update_modified=False,
	)


def _handle_failure(doc, response):
	"""7b — Fast từ chối. Dữ liệu còn sửa được, phát hành lại được."""
	message = _explain(response)
	frappe.db.set_value(
		FEI,
		doc.name,
		{"status": STATUS_ERROR, "error_code": response.error_code or "", "error_message": message},
		update_modified=False,
	)
	_mirror_status(doc.name, STATUS_ERROR)
	_notify_failure(doc, message)
	return {"ok": False, "message": message}


def _handle_timeout(doc, exc):
	"""7c — đã gửi nhưng chưa biết kết quả. Tuyệt đối không tự phát hành lại."""
	message = _(
		"Đã gửi lệnh phát hành nhưng chưa nhận được kết quả từ Fast ({0}). "
		"BẮT BUỘC bấm Truy vấn (370) để biết hóa đơn đã ra số hay chưa, "
		"trước khi thao tác tiếp. Không phát hành lại."
	).format(exc)

	frappe.db.set_value(
		FEI,
		doc.name,
		{"status": STATUS_NEEDS_RECONCILE, "error_code": "", "error_message": message},
		update_modified=False,
	)
	_mirror_status(doc.name, STATUS_NEEDS_RECONCILE)
	_notify_failure(doc, message)
	return {"ok": False, "needs_reconcile": True, "message": message}


def _notify_failure(doc, message):
	recipients = get_notify_recipients()
	if not recipients:
		return
	try:
		frappe.sendmail(
			recipients=recipients,
			subject=_("[HĐĐT] Phát hành hóa đơn {0} không thành công").format(doc.name),
			message=f"<p>{frappe.utils.escape_html(message)}</p>",
			reference_doctype=FEI,
			reference_name=doc.name,
		)
	except Exception:
		# Không gửi được cảnh báo thì cũng không được che mất kết quả phát hành.
		frappe.log_error(title=f"HĐĐT: không gửi được cảnh báo cho {doc.name}")


def _queue_pdf_download(doc, enqueue=None):
	"""Nhánh 7a — hẹn tải PDF chính thức sau khi phát hành xong.

	Đợi vài giây rồi mới tải: Fast cần thời gian ký số xong mới có bản PDF, và
	mục E6 chặn hai lời gọi PDF cách nhau dưới 5 giây.
	"""
	settings = check_enabled()
	if not settings.auto_download_pdf:
		return

	(enqueue or frappe.enqueue)(
		method="erpnext.einvoice.actions.download_official_pdf",
		queue="long",
		enqueue_after_commit=True,
		fei=doc.name,
	)
