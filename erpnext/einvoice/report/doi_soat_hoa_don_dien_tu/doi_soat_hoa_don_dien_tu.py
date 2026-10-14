# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Đối soát hóa đơn điện tử — bốn việc kế toán phải dọn mỗi ngày (mục Giai đoạn 5).

1. **Chưa xuất hóa đơn** — hóa đơn bán đã submit mà chưa có chứng từ HĐĐT nào.
   Đây là doanh thu đã ghi sổ nhưng chưa xuất hóa đơn.
2. **Đã giao, chưa lập hóa đơn bán** — phiếu giao đã submit mà chưa có hóa đơn
   bán. Từ bản 3.0 hóa đơn điện tử lập từ hóa đơn bán, nên hóa đơn bán lập muộn
   là hóa đơn điện tử muộn so với ngày giao hàng — rủi ro lớn nhất của việc đổi
   nguồn, và báo cáo này là chỗ bù lại.
3. **Chờ CQT quá 24 giờ** — đã phát hành nhưng Cơ quan Thuế chưa phản hồi.
   Quá một ngày là bất thường, cần hỏi Fast.
4. **Lỗi / cần đối soát** — phát hành hỏng, hoặc timeout chưa rõ kết quả. Nhóm
   "Cần đối soát" là nguy hiểm nhất: chưa biết đã tiêu số hóa đơn hay chưa.
"""

import frappe
from frappe import _
from frappe.utils import add_to_date, now_datetime

from erpnext.einvoice.constants import (
	INVOICE_TYPE_ORIGINAL,
	LIVE_STATUSES,
	SOURCE_DELIVERY_NOTE_V2,
	STATUS_ERROR,
	STATUS_ISSUED,
	STATUS_NEEDS_RECONCILE,
	STATUS_SENT,
	TAX_STATUS_PENDING,
)

ISSUE_NOT_INVOICED = "Chưa xuất hóa đơn"
ISSUE_NOT_BILLED = "Đã giao, chưa lập hóa đơn bán"
ISSUE_TAX_OVERDUE = "Chờ CQT quá 24 giờ"
ISSUE_ERROR = "Lỗi / cần đối soát"

TAX_OVERDUE_HOURS = 24


def execute(filters=None):
	filters = frappe._dict(filters or {})
	rows = []
	wanted = filters.get("issue_type")

	if not wanted or wanted == ISSUE_NOT_INVOICED:
		rows += _uninvoiced_sales_invoices(filters)
	if not wanted or wanted == ISSUE_NOT_BILLED:
		rows += _unbilled_delivery_notes(filters)
	if not wanted or wanted == ISSUE_TAX_OVERDUE:
		rows += _tax_overdue(filters)
	if not wanted or wanted == ISSUE_ERROR:
		rows += _errored(filters)

	return _columns(), rows


def _columns():
	return [
		{"label": _("Loại vấn đề"), "fieldname": "issue_type", "fieldtype": "Data", "width": 170},
		{
			"label": _("Chứng từ HĐĐT"),
			"fieldname": "fei_document",
			"fieldtype": "Link",
			"options": "Fast EInvoice Document",
			"width": 150,
		},
		{
			"label": _("Hóa đơn bán"),
			"fieldname": "sales_invoice",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 170,
		},
		{
			"label": _("Phiếu giao hàng"),
			"fieldname": "delivery_note",
			"fieldtype": "Link",
			"options": "Delivery Note",
			"width": 160,
		},
		{
			"label": _("Khách hàng"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 200,
		},
		{"label": _("Ngày"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Số hóa đơn"), "fieldname": "invoice_no", "fieldtype": "Data", "width": 100},
		{"label": _("Trạng thái"), "fieldname": "status", "fieldtype": "Data", "width": 160},
		{"label": _("Tổng tiền"), "fieldname": "total_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Ghi chú"), "fieldname": "note", "fieldtype": "Small Text", "width": 320},
	]


def _date_range(filters):
	return {"from": filters.get("from_date"), "to": filters.get("to_date")}


def _source_conditions(filters):
	window = _date_range(filters)
	conditions = {"docstatus": 1, "is_return": 0}
	if filters.get("company"):
		conditions["company"] = filters.company
	if window["from"] and window["to"]:
		conditions["posting_date"] = ("between", [window["from"], window["to"]])
	return conditions


def _uninvoiced_sales_invoices(filters):
	"""Hóa đơn bán là doanh thu cần xuất hóa đơn mà chưa có chứng từ HĐĐT nào.

	Loại trừ đúng những hóa đơn bán mà nút tạo cũng từ chối (ghi nợ, số dư đầu kỳ,
	gộp POS) — báo "chưa xuất" cho thứ không được xuất là nhiễu. Hóa đơn bán của
	phiếu giao đã xuất theo bản 2.0 cũng không tính: lần bán đó đã có hóa đơn.
	"""
	conditions = {**_source_conditions(filters), "is_debit_note": 0, "is_opening": "No", "is_consolidated": 0}
	invoices = frappe.get_all(
		"Sales Invoice",
		filters=conditions,
		fields=["name", "customer", "posting_date", "grand_total"],
		order_by="posting_date asc",
	)
	if not invoices:
		return []
	names = [inv.name for inv in invoices]

	covered = set(
		frappe.get_all(
			"Fast EInvoice Document",
			filters={
				"sales_invoice": ("in", names),
				"invoice_type": INVOICE_TYPE_ORIGINAL,
				"status": ("in", list(LIVE_STATUSES)),
			},
			pluck="sales_invoice",
		)
	)
	covered |= _covered_through_legacy_delivery_notes([n for n in names if n not in covered])

	return [
		{
			"issue_type": ISSUE_NOT_INVOICED,
			"fei_document": None,
			"sales_invoice": inv.name,
			"delivery_note": None,
			"customer": inv.customer,
			"posting_date": inv.posting_date,
			"invoice_no": "",
			"status": "",
			"total_amount": inv.grand_total,
			"note": _("Đã ghi doanh thu nhưng chưa lập chứng từ hóa đơn điện tử."),
		}
		for inv in invoices
		if inv.name not in covered
	]


def _covered_through_legacy_delivery_notes(names):
	if not names:
		return set()
	links = frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": ("in", names), "parenttype": "Sales Invoice", "delivery_note": ("is", "set")},
		fields=["parent", "delivery_note"],
	)
	notes = {link.delivery_note for link in links}
	if not notes:
		return set()
	invoiced = set(
		frappe.get_all(
			"Fast EInvoice Document",
			filters={
				"delivery_note": ("in", list(notes)),
				"source_doctype": SOURCE_DELIVERY_NOTE_V2,
				"invoice_type": INVOICE_TYPE_ORIGINAL,
				"status": ("in", list(LIVE_STATUSES)),
			},
			pluck="delivery_note",
		)
	)
	return {link.parent for link in links if link.delivery_note in invoiced}


def _unbilled_delivery_notes(filters):
	"""Phiếu giao đã submit mà chưa có hóa đơn bán (đã submit) nào lập từ nó.

	Phiếu giao đã xuất hóa đơn theo bản 2.0 thì không tính — lần giao đó đã có hóa
	đơn điện tử.
	"""
	notes = frappe.get_all(
		"Delivery Note",
		filters=_source_conditions(filters),
		fields=["name", "customer", "posting_date", "grand_total"],
		order_by="posting_date asc",
	)
	if not notes:
		return []
	names = [n.name for n in notes]

	billed = set(
		frappe.get_all(
			"Sales Invoice Item",
			filters={"delivery_note": ("in", names), "parenttype": "Sales Invoice", "docstatus": 1},
			pluck="delivery_note",
		)
	)
	legacy = set(
		frappe.get_all(
			"Fast EInvoice Document",
			filters={
				"delivery_note": ("in", names),
				"source_doctype": SOURCE_DELIVERY_NOTE_V2,
				"invoice_type": INVOICE_TYPE_ORIGINAL,
				"status": ("in", list(LIVE_STATUSES)),
			},
			pluck="delivery_note",
		)
	)

	return [
		{
			"issue_type": ISSUE_NOT_BILLED,
			"fei_document": None,
			"sales_invoice": None,
			"delivery_note": note.name,
			"customer": note.customer,
			"posting_date": note.posting_date,
			"invoice_no": "",
			"status": "",
			"total_amount": note.grand_total,
			"note": _(
				"Đã giao hàng nhưng chưa lập hóa đơn bán — hóa đơn điện tử lập từ hóa đơn bán, "
				"nên cần lập hóa đơn bán trong ngày giao hàng."
			),
		}
		for note in notes
		if note.name not in billed and note.name not in legacy
	]


def _tax_overdue(filters):
	cutoff = add_to_date(now_datetime(), hours=-TAX_OVERDUE_HOURS)
	conditions = {
		"tax_status": TAX_STATUS_PENDING,
		"status": ("in", [STATUS_ISSUED, STATUS_SENT]),
		"issued_time": ("<", cutoff),
	}
	_apply_common_filters(conditions, filters)

	return [
		{
			"issue_type": ISSUE_TAX_OVERDUE,
			"fei_document": doc.name,
			"sales_invoice": doc.sales_invoice,
			"delivery_note": doc.delivery_note,
			"customer": doc.customer,
			"posting_date": doc.invoice_date,
			"invoice_no": doc.fast_invoice_no,
			"status": doc.status,
			"total_amount": doc.total_amount,
			"note": _("Phát hành lúc {0} mà Cơ quan Thuế chưa phản hồi — liên hệ Fast.").format(
				doc.issued_time
			),
		}
		for doc in _fei_rows(conditions)
	]


def _errored(filters):
	conditions = {"status": ("in", [STATUS_ERROR, STATUS_NEEDS_RECONCILE])}
	_apply_common_filters(conditions, filters)

	rows = []
	for doc in _fei_rows(conditions):
		if doc.status == STATUS_NEEDS_RECONCILE:
			note = _("Đã gửi lệnh phát hành nhưng chưa rõ kết quả — BẮT BUỘC bấm Lấy dữ liệu từ Fast (370).")
		else:
			note = doc.error_message or _("Phát hành không thành công.")
		rows.append(
			{
				"issue_type": ISSUE_ERROR,
				"fei_document": doc.name,
				"sales_invoice": doc.sales_invoice,
				"delivery_note": doc.delivery_note,
				"customer": doc.customer,
				"posting_date": doc.invoice_date,
				"invoice_no": doc.fast_invoice_no,
				"status": doc.status,
				"total_amount": doc.total_amount,
				"note": note,
			}
		)
	return rows


def _apply_common_filters(conditions, filters):
	window = _date_range(filters)
	if window["from"] and window["to"]:
		conditions["invoice_date"] = ("between", [window["from"], window["to"]])


def _fei_rows(conditions):
	return frappe.get_all(
		"Fast EInvoice Document",
		filters=conditions,
		fields=[
			"name",
			"sales_invoice",
			"delivery_note",
			"customer",
			"invoice_date",
			"fast_invoice_no",
			"status",
			"total_amount",
			"issued_time",
			"error_message",
		],
		order_by="invoice_date asc",
	)
