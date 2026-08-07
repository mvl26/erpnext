# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Bảng trạng thái B2 dưới dạng dữ liệu — nút nào hiện ở trạng thái nào.

Logic nằm ở server chứ không nằm trong JS vì hai lý do: giao diện và chốt chặn
phía server không được phép lệch nhau (nút hiện ra mà server từ chối thì kế toán
không hiểu chuyện gì), và bảng B2 chỉ kiểm chứng được bằng test khi nó là dữ
liệu Python.

Ba cấp xác nhận của nguyên tắc A2:
- **1** hộp thoại Có/Không
- **2** hộp thoại nhập/sửa thông tin rồi mới chạy
- **3** bảng tóm tắt toàn màn hình, phải **gõ đúng chữ** mới bật được nút
"""

import frappe
from frappe import _

from erpnext.einvoice.constants import (
	EDITABLE_STATUSES,
	LIVE_STATUSES,
	STATUS_AWAITING_CUSTOMER,
	STATUS_CUSTOMER_APPROVED,
	STATUS_DRAFT,
	STATUS_DRAFT_VIEWED,
	STATUS_ERROR,
	STATUS_ISSUED,
	STATUS_NEEDS_RECONCILE,
	STATUS_SENT,
	STATUS_TAX_ACCEPTED,
	STATUS_TAX_REJECTED,
)
from erpnext.einvoice.fast_settings import get_environment_banner, get_settings
from erpnext.einvoice.setup import is_chief_accountant
from erpnext.einvoice.validation import validate_before_send

FEI = "Fast EInvoice Document"

# Trạng thái còn được phép sửa và gửi lại vòng nháp.
_PREPARING = (STATUS_DRAFT, STATUS_DRAFT_VIEWED, STATUS_AWAITING_CUSTOMER, STATUS_CUSTOMER_APPROVED)
_FIXABLE = (*_PREPARING, STATUS_ERROR, STATUS_NEEDS_RECONCILE)
_HAS_NUMBER = (STATUS_ISSUED, STATUS_SENT, STATUS_TAX_ACCEPTED)

# (tên, nhãn, phương thức, cấp xác nhận, các trạng thái hiện nút, chỉ kế toán trưởng)
BUTTONS = (
	(
		"resync",
		"Đồng bộ lại từ phiếu giao",
		"erpnext.einvoice.builder.resync_from_delivery_note",
		1,
		_FIXABLE,
		False,
	),
	(
		"preview_draft",
		"Xem bản nháp PDF",
		"erpnext.einvoice.actions.preview_draft",
		1,
		_FIXABLE,
		False,
	),
	(
		"send_draft",
		"Gửi bản nháp cho khách",
		"erpnext.einvoice.actions.send_draft_to_customer",
		2,
		(STATUS_DRAFT_VIEWED, STATUS_AWAITING_CUSTOMER, STATUS_CUSTOMER_APPROVED),
		False,
	),
	(
		"record_feedback",
		"Ghi nhận ý kiến khách",
		"erpnext.einvoice.actions.record_customer_feedback",
		2,
		(STATUS_AWAITING_CUSTOMER,),
		False,
	),
	(
		"mark_approved",
		"Khách đã duyệt",
		"erpnext.einvoice.actions.mark_customer_approved",
		2,
		(STATUS_AWAITING_CUSTOMER,),
		False,
	),
	(
		"issue",
		"PHÁT HÀNH HÓA ĐƠN",
		"erpnext.einvoice.issue.issue_invoice",
		3,
		None,  # tính riêng theo cấu hình bắt buộc khách duyệt
		True,
	),
	(
		"download_pdf",
		"Tải PDF chính thức",
		"erpnext.einvoice.actions.download_official_pdf",
		1,
		_HAS_NUMBER,
		False,
	),
	(
		"download_converted_pdf",
		"Tải PDF chuyển đổi",
		"erpnext.einvoice.actions.download_converted_pdf",
		2,
		_HAS_NUMBER,
		False,
	),
	(
		"send_invoice",
		"Gửi hóa đơn cho khách",
		"erpnext.einvoice.actions.send_invoice_to_customer",
		2,
		_HAS_NUMBER,
		False,
	),
	(
		"check_tax",
		"Kiểm tra trạng thái CQT",
		"erpnext.einvoice.tax_status.check_tax_status",
		1,
		(STATUS_ISSUED, STATUS_SENT),
		False,
	),
	(
		"reconcile",
		"Truy vấn đối soát (370)",
		"erpnext.einvoice.reconcile.reconcile_invoice",
		1,
		(*_HAS_NUMBER, STATUS_TAX_REJECTED, STATUS_NEEDS_RECONCILE, STATUS_ERROR),
		False,
	),
	(
		"create_adjustment",
		"Tạo hóa đơn điều chỉnh",
		"erpnext.einvoice.lineage.create_adjustment",
		2,
		(STATUS_TAX_ACCEPTED,),
		True,
	),
	(
		"create_replacement",
		"Tạo hóa đơn thay thế",
		"erpnext.einvoice.lineage.create_replacement",
		2,
		(STATUS_TAX_ACCEPTED,),
		True,
	),
	(
		"cancel",
		"Hủy nội bộ",
		"erpnext.einvoice.cancel.cancel_internally",
		3,
		(STATUS_TAX_REJECTED,),
		True,
	),
)

CONFIRM_WORDS = {"issue": "PHAT HANH", "cancel": "HUY"}


@frappe.whitelist()
def get_form_state(fei):
	"""Mọi thứ giao diện cần để vẽ form: banner, nút khả dụng, kết quả kiểm tra."""
	doc = frappe.get_doc(FEI, fei)
	settings = get_settings()

	return {
		"status": doc.status,
		"banner": get_environment_banner(),
		"enabled": settings.enabled,
		"is_chief": is_chief_accountant(),
		"buttons": _buttons_for(doc, settings),
		"validation": _validation_for(doc),
	}


def _buttons_for(doc, settings):
	chief = is_chief_accountant()
	buttons = []
	for name, label, method, level, statuses, needs_chief in BUTTONS:
		allowed = _issue_statuses(settings) if name == "issue" else statuses
		if doc.status not in allowed:
			continue
		if needs_chief and not chief:
			continue
		buttons.append(
			{
				"name": name,
				"label": _(label),
				"method": method,
				"level": level,
				"confirm_word": CONFIRM_WORDS.get(name),
			}
		)
	return buttons


def _issue_statuses(settings):
	"""Bắt buộc khách duyệt thì chỉ trạng thái 04 mới được phát hành (mục E5)."""
	if settings.require_customer_approval:
		return (STATUS_CUSTOMER_APPROVED,)
	return (STATUS_DRAFT, STATUS_DRAFT_VIEWED, STATUS_CUSTOMER_APPROVED, STATUS_ERROR)


def _validation_for(doc):
	"""Hóa đơn đã khóa thì không chạy kiểm tra — không còn gì để sửa, chỉ gây nhiễu."""
	if doc.status not in EDITABLE_STATUSES:
		return {"ok": True, "issues": []}
	return validate_before_send(doc).as_dict()


# --- Trạng thái HĐĐT nhìn từ phiếu giao hàng (Nút 1, mục E1) ----------------


@frappe.whitelist()
def get_delivery_note_state(delivery_note):
	"""Phiếu giao này có lập được hóa đơn điện tử không, và vì sao không."""
	settings = get_settings()
	source = frappe.db.get_value(
		"Delivery Note",
		delivery_note,
		["docstatus", "is_return", "customer", "customer_name", "grand_total", "currency"],
		as_dict=True,
	)
	if not source:
		return {"can_create": False, "reason": _("Không tìm thấy phiếu giao hàng.")}

	existing = frappe.get_all(
		FEI,
		filters={"delivery_note": delivery_note, "status": ("in", list(LIVE_STATUSES))},
		fields=["name", "status"],
		limit=1,
	)

	state = {
		"can_create": False,
		"reason": "",
		"existing": existing[0] if existing else None,
		"customer_name": source.customer_name or source.customer,
		"grand_total": source.grand_total,
		"currency": source.currency,
	}

	if not settings.enabled:
		state["reason"] = _("Tích hợp hóa đơn điện tử đang tắt.")
	elif source.docstatus != 1:
		state["reason"] = _("Phiếu giao hàng chưa được submit.")
	elif source.is_return:
		state["reason"] = _("Phiếu trả hàng không lập hóa đơn trực tiếp — dùng hóa đơn điều chỉnh giảm.")
	elif existing:
		state["reason"] = _("Phiếu giao này đã có chứng từ HĐĐT {0} ({1}).").format(
			existing[0].name, existing[0].status
		)
	else:
		state["can_create"] = True

	return state
