# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tình trạng đối chiếu công nợ theo kỳ (FR-15a): từng biên bản + tóm tắt tỷ lệ xác nhận."""

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from erpnext.debt_reconciliation import constants as C


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(), data, None, get_chart(data), get_summary(data)


def get_columns():
	return [
		{
			"label": _("Biên bản"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": C.DOCTYPE,
			"width": 150,
		},
		{"label": _("Loại"), "fieldname": "party_type", "fieldtype": "Data", "width": 90},
		{"label": _("Đối tác"), "fieldname": "party_name", "fieldtype": "Data", "width": 220},
		{"label": _("Kỳ"), "fieldname": "to_date", "fieldtype": "Date", "width": 95},
		{"label": _("Dư cuối kỳ"), "fieldname": "closing_balance", "fieldtype": "Currency", "width": 140},
		{"label": _("Chiều dư"), "fieldname": "balance_direction", "fieldtype": "Data", "width": 80},
		{"label": _("Trạng thái"), "fieldname": "status", "fieldtype": "Data", "width": 130},
		{"label": _("Phản hồi"), "fieldname": "partner_response", "fieldtype": "Data", "width": 110},
		{"label": _("Hạn phản hồi"), "fieldname": "response_deadline", "fieldtype": "Date", "width": 105},
		{"label": _("Quá hạn"), "fieldname": "overdue", "fieldtype": "Check", "width": 70},
		{"label": _("Số theo đối tác"), "fieldname": "dispute_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Diễn giải chênh lệch"), "fieldname": "dispute_note", "fieldtype": "Data", "width": 200},
	]


def get_data(filters):
	conditions = {"docstatus": ["<", 2]}
	if filters.company:
		conditions["company"] = filters.company
	if filters.from_date:
		conditions["from_date"] = [">=", filters.from_date]
	if filters.to_date:
		conditions["to_date"] = ["<=", filters.to_date]
	if filters.party_type:
		conditions["party_type"] = filters.party_type
	if filters.status:
		conditions["status"] = filters.status

	rows = frappe.get_all(
		C.DOCTYPE,
		filters=conditions,
		fields=[
			"name",
			"party_type",
			"party",
			"party_name",
			"to_date",
			"closing_balance",
			"balance_direction",
			"status",
			"partner_response",
			"response_deadline",
			"dispute_amount",
			"dispute_note",
			"docstatus",
		],
		order_by="to_date desc, party_type, party_name",
	)
	today = getdate(nowdate())
	for r in rows:
		r.overdue = int(
			r.docstatus == 1
			and r.partner_response == C.RESPONSE_NONE
			and bool(r.response_deadline)
			and getdate(r.response_deadline) < today
		)
	return rows


def get_summary(data):
	total = len(data)
	sent = sum(
		1 for r in data if r.docstatus == 1 and r.status not in (C.STATUS_APPROVED, C.STATUS_SEND_FAILED)
	)
	confirmed = sum(1 for r in data if r.status == C.STATUS_CONFIRMED)
	disputed = sum(1 for r in data if r.status == C.STATUS_DISPUTED)
	overdue = sum(r.overdue for r in data)
	rate = round(confirmed * 100.0 / sent, 1) if sent else 0
	return [
		{"label": _("Tổng biên bản"), "value": total, "datatype": "Int"},
		{"label": _("Đã gửi"), "value": sent, "datatype": "Int", "indicator": "Blue"},
		{"label": _("Đã xác nhận"), "value": confirmed, "datatype": "Int", "indicator": "Green"},
		{"label": _("Tỷ lệ xác nhận (%)"), "value": rate, "datatype": "Float", "indicator": "Green"},
		{"label": _("Chênh lệch"), "value": disputed, "datatype": "Int", "indicator": "Orange"},
		{"label": _("Quá hạn"), "value": overdue, "datatype": "Int", "indicator": "Red"},
	]


def get_chart(data):
	counts = {}
	for r in data:
		counts[r.status] = counts.get(r.status, 0) + 1
	if not counts:
		return None
	return {
		"data": {
			"labels": list(counts),
			"datasets": [{"name": _("Số biên bản"), "values": list(counts.values())}],
		},
		"type": "bar",
	}
