# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Đối soát hóa đơn điện tử — ba việc kế toán phải dọn mỗi ngày (mục Giai đoạn 5).

1. **Chưa xuất hóa đơn** — phiếu giao đã submit mà chưa có chứng từ HĐĐT nào.
   Đây là doanh thu đã giao hàng nhưng chưa xuất hóa đơn.
2. **Chờ CQT quá 24 giờ** — đã phát hành nhưng Cơ quan Thuế chưa phản hồi.
   Quá một ngày là bất thường, cần hỏi Fast.
3. **Lỗi / cần đối soát** — phát hành hỏng, hoặc timeout chưa rõ kết quả. Nhóm
   "Cần đối soát" là nguy hiểm nhất: chưa biết đã tiêu số hóa đơn hay chưa.
"""

import frappe
from frappe import _
from frappe.utils import add_to_date, now_datetime

from erpnext.einvoice.constants import (
	LIVE_STATUSES,
	STATUS_ERROR,
	STATUS_ISSUED,
	STATUS_NEEDS_RECONCILE,
	STATUS_SENT,
	TAX_STATUS_PENDING,
)

ISSUE_NOT_INVOICED = "Chưa xuất hóa đơn"
ISSUE_TAX_OVERDUE = "Chờ CQT quá 24 giờ"
ISSUE_ERROR = "Lỗi / cần đối soát"

TAX_OVERDUE_HOURS = 24


def execute(filters=None):
	filters = frappe._dict(filters or {})
	rows = []
	wanted = filters.get("issue_type")

	if not wanted or wanted == ISSUE_NOT_INVOICED:
		rows += _uninvoiced_delivery_notes(filters)
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


def _uninvoiced_delivery_notes(filters):
	window = _date_range(filters)
	conditions = {"docstatus": 1, "is_return": 0}
	if filters.get("company"):
		conditions["company"] = filters.company
	if window["from"] and window["to"]:
		conditions["posting_date"] = ("between", [window["from"], window["to"]])

	notes = frappe.get_all(
		"Delivery Note",
		filters=conditions,
		fields=["name", "customer", "posting_date", "grand_total"],
		order_by="posting_date asc",
	)
	if not notes:
		return []

	live = set(
		frappe.get_all(
			"Fast EInvoice Document",
			filters={
				"delivery_note": ("in", [n.name for n in notes]),
				"status": ("in", list(LIVE_STATUSES)),
			},
			pluck="delivery_note",
		)
	)

	return [
		{
			"issue_type": ISSUE_NOT_INVOICED,
			"fei_document": None,
			"delivery_note": note.name,
			"customer": note.customer,
			"posting_date": note.posting_date,
			"invoice_no": "",
			"status": "",
			"total_amount": note.grand_total,
			"note": _("Đã giao hàng nhưng chưa lập chứng từ hóa đơn điện tử."),
		}
		for note in notes
		if note.name not in live
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
			note = _("Đã gửi lệnh phát hành nhưng chưa rõ kết quả — BẮT BUỘC bấm Truy vấn (370).")
		else:
			note = doc.error_message or _("Phát hành không thành công.")
		rows.append(
			{
				"issue_type": ISSUE_ERROR,
				"fei_document": doc.name,
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
