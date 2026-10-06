# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nhắc hạn phản hồi & nhận bản ký — ngày 06 (FR-14)."""

import frappe
from frappe import _
from frappe.utils import get_url_to_form, getdate, nowdate

from erpnext.debt_reconciliation import constants as C
from erpnext.debt_reconciliation.generation import get_reminder_recipients, make_notification


def get_due_statements(date=None):
	"""(chưa phản hồi đối soát, đã khớp nhưng chưa có bản ký) có hạn đúng ``date``."""
	date = getdate(date or nowdate())
	fields = ["name", "party_type", "party", "party_name", "status", "response_deadline"]
	base = {"docstatus": 1, "response_deadline": date}
	no_response = frappe.get_all(
		C.DOCTYPE,
		filters={
			**base,
			"partner_response": C.RESPONSE_NONE,
			"status": ["in", [C.STATUS_SENT, C.STATUS_SEND_FAILED]],
		},
		fields=fields,
		order_by="party_type, party_name",
	)
	unsigned = frappe.get_all(
		C.DOCTYPE,
		filters={**base, "status": C.STATUS_MATCHED, "signed_copy": ["is", "not set"]},
		fields=fields,
		order_by="party_type, party_name",
	)
	return no_response, unsigned


def send_due_reminders(date=None):
	date = getdate(date or nowdate())
	key = f"{frappe.local.site}:dr:reminded:{date}"
	cache = frappe.cache()
	if cache.get(key):
		return
	no_response, unsigned = get_due_statements(date)
	if not (no_response or unsigned):
		return
	recipients = get_reminder_recipients()
	if not recipients:
		return

	def block(title, rows):
		if not rows:
			return ""
		items = "".join(
			f'<li><a href="{get_url_to_form(C.DOCTYPE, r.name)}">{r.name}</a> — {frappe.utils.escape_html(r.party_name or r.party)} ({r.status})</li>'
			for r in rows
		)
		return f"<p><b>{title} ({len(rows)})</b></p><ul>{items}</ul>"

	subject = _("Nhắc hạn đối chiếu công nợ {0}: {1} chưa phản hồi, {2} chưa có bản ký").format(
		frappe.utils.formatdate(date), len(no_response), len(unsigned)
	)
	message = block(_("Chưa phản hồi đối soát"), no_response) + block(
		_("Đã đối soát khớp nhưng chưa nhận bản ký"), unsigned
	)
	frappe.sendmail(recipients=recipients, subject=subject, message=message)
	make_notification(recipients, subject, message)
	cache.set(key, 1, ex=2 * 24 * 3600)
	return no_response, unsigned
