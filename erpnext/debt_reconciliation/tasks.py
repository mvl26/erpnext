# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Các hàm scheduler gọi vào (đăng ký trong hooks.py)."""

import frappe
from frappe.utils import cint, now_datetime

from erpnext.debt_reconciliation.constants import SETTINGS


def hourly():
	"""Job sinh biên bản đầu tháng — chạy trong khung giờ ``generation_hour`` của ``generation_day``.

	Scheduler ``hourly`` không chạy đúng phút :00 nên "10:00" nghĩa là 10:00-10:59;
	sinh biên bản idempotent nên chạy lặp không tạo trùng.
	"""
	settings = frappe.get_cached_doc(SETTINGS)
	now = now_datetime()
	if not cint(settings.auto_generate):
		return
	if now.day != (cint(settings.generation_day) or 1) or now.hour != cint(settings.generation_hour):
		return
	frappe.enqueue(
		"erpnext.debt_reconciliation.generation.auto_generate",
		queue="long",
		timeout=3000,
		enqueue_after_commit=True,
		now=frappe.flags.in_test,
	)


def send_due_reminders():
	from erpnext.debt_reconciliation.reminders import send_due_reminders as _send

	_send()
