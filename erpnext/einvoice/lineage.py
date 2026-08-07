# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nút 13a/13b — hóa đơn điều chỉnh (320) và thay thế (350) — mục E9.

Hóa đơn đã được Cơ quan Thuế chấp nhận thì không sửa được nữa. Muốn thay đổi
phải lập một hóa đơn **mới** trỏ về hóa đơn gốc:

- **Điều chỉnh (320)** — sai số lượng / đơn giá / thuế suất, hoặc trả lại hàng:
  chỉ ghi phần chênh lệch, dòng giảm truyền **số âm**.
- **Thay thế (350)** — sai nhiều, sai nghiêm trọng: nhập lại **toàn bộ** nội dung.

Bản ghi mới đi lại đúng vòng đời từ Nháp: xem nháp → gửi khách → duyệt → phát
hành. Chỉ khi nó phát hành xong thì hóa đơn gốc mới chuyển sang trạng thái 10/11.
"""

import frappe
from frappe import _

from erpnext.einvoice.constants import (
	INVOICE_TYPE_ADJUSTMENT,
	INVOICE_TYPE_REPLACEMENT,
	LIVE_STATUSES,
	MAX_LEN,
	STATUS_DRAFT,
	STATUS_TAX_ACCEPTED,
)
from erpnext.einvoice.fast_settings import check_enabled

FEI = "Fast EInvoice Document"

# Các trường kết quả của hóa đơn gốc tuyệt đối không được sao sang bản mới:
# bản mới phải tự xin số của nó.
_RESULT_FIELDS = (
	"fast_key_search",
	"fast_invoice_no",
	"fast_pattern",
	"fast_serial",
	"fast_signed_date",
	"issued_by",
	"issued_time",
	"official_pdf",
	"converted_pdf",
	"draft_pdf",
	"draft_pdf_time",
	"draft_sent_to",
	"draft_sent_time",
	"invoice_sent_to",
	"invoice_sent_time",
	"tax_status",
	"tax_verification_code",
	"tax_feedback",
	"tax_checked_time",
	"error_code",
	"error_message",
	"cancel_reason",
	"cancelled_time",
	"amended_from_fei",
)

_COPIED_FIELDS = (
	"delivery_note",
	"sales_invoice",
	"customer",
	"invoice_date",
	"customer_code",
	"buyer",
	"customer_name",
	"customer_tax_code",
	"customer_type",
	"address",
	"phone_number",
	"fax_number",
	"id_card_no",
	"passport_no",
	"buyer_unit",
	"email_deliver",
	"bank_account",
	"bank_name",
	"payment_method",
	"currency",
	"exchange_rate",
	"amount",
	"total_amount",
	"tax_rate",
	"tax_amount",
	"tax_amount_free",
	"tax_amount_0",
	"tax_amount_5",
	"tax_amount_10",
	"discount_amount",
	"promotion_amount",
	"deduction_amount",
	"deduction_amount_other",
	"amount_in_words",
	"human_name",
	"release_type",
)


@frappe.whitelist()
def create_adjustment(original, adjustment_type, reason, minute_no=None, minute_date=None):
	"""Nút 13a — lập hóa đơn điều chỉnh cho một hóa đơn đã được CQT chấp nhận."""
	return _create_child(
		original,
		INVOICE_TYPE_ADJUSTMENT,
		reason,
		adjustment_type=adjustment_type,
		minute_no=minute_no,
		minute_date=minute_date,
		suffix="DC",
	)


@frappe.whitelist()
def create_replacement(original, reason, minute_no=None, minute_date=None):
	"""Nút 13b — lập hóa đơn thay thế; loại điều chỉnh hệ thống tự gán 4."""
	return _create_child(
		original,
		INVOICE_TYPE_REPLACEMENT,
		reason,
		minute_no=minute_no,
		minute_date=minute_date,
		suffix="TT",
	)


def _create_child(
	original, invoice_type, reason, suffix, adjustment_type=None, minute_no=None, minute_date=None
):
	check_enabled()
	parent = frappe.get_doc(FEI, original)

	if parent.status != STATUS_TAX_ACCEPTED:
		frappe.throw(
			_(
				"Chỉ điều chỉnh hoặc thay thế được hóa đơn đã được Cơ quan Thuế chấp nhận. "
				"Hóa đơn {0} đang ở trạng thái {1}."
			).format(parent.name, parent.status)
		)

	if not (reason or "").strip():
		frappe.throw(_("Nhập lý do điều chỉnh / thay thế — đây là căn cứ giải trình với Cơ quan Thuế."))

	_assert_no_live_child(parent)

	child = frappe.new_doc(FEI)
	for fieldname in _COPIED_FIELDS:
		child.set(fieldname, parent.get(fieldname))
	for fieldname in _RESULT_FIELDS:
		child.set(fieldname, None)

	child.invoice_type = invoice_type
	child.original_document = parent.name
	child.adjustment_type = adjustment_type
	child.adjustment_reason = reason.strip()
	child.minute_no = minute_no
	child.minute_date = minute_date
	child.status = STATUS_DRAFT
	child.revision_count = 0
	child.draft_send_count = 0
	child.invoice_send_count = 0
	child.fast_key = _child_key(parent.fast_key, suffix)

	for line in parent.lines:
		row = child.append("lines", {})
		for field, value in line.as_dict().items():
			if field not in (
				"name",
				"parent",
				"parenttype",
				"parentfield",
				"idx",
				"creation",
				"modified",
				"owner",
				"modified_by",
				"docstatus",
			):
				row.set(field, value)

	child.flags.ignore_permissions = True
	child.insert()

	parent.add_comment(
		"Comment", _("Đã lập {0} {1}: {2}").format(invoice_type.lower(), child.name, reason.strip())
	)
	return child.name


def _assert_no_live_child(parent):
	existing = frappe.get_all(
		FEI,
		filters={"original_document": parent.name, "status": ("in", list(LIVE_STATUSES))},
		fields=["name", "status"],
		limit=1,
	)
	if existing:
		frappe.throw(
			_("Hóa đơn {0} đã có chứng từ điều chỉnh/thay thế đang xử lý: {1} ({2}).").format(
				parent.name, existing[0].name, existing[0].status
			)
		)


def _child_key(parent_key, suffix):
	"""Key riêng cho bản ghi con — dùng lại Key của hóa đơn gốc là lỗi 809 ngay."""
	base = (parent_key or "")[: MAX_LEN["fast_key"] - len(suffix) - 3]
	index = 1
	while True:
		candidate = f"{base}-{suffix}{index}"
		if not frappe.db.exists(FEI, {"fast_key": candidate}):
			return candidate
		index += 1


def mark_original_superseded(child):
	"""Sau khi bản ghi con phát hành xong: khóa hóa đơn gốc và nối hai chiều.

	Chỉ chạy khi con đã thực sự có số — hóa đơn gốc vẫn còn nguyên giá trị chừng
	nào bản điều chỉnh chưa phát hành được.
	"""
	if not child.original_document:
		return

	from erpnext.einvoice.constants import STATUS_ADJUSTED, STATUS_REPLACED

	status = STATUS_REPLACED if child.invoice_type == INVOICE_TYPE_REPLACEMENT else STATUS_ADJUSTED
	frappe.db.set_value(
		FEI,
		child.original_document,
		{"status": status, "amended_from_fei": child.name},
		update_modified=False,
	)
