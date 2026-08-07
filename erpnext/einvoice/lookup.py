# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tra số hóa đơn điện tử cho các chứng từ kế toán.

Bảng kê bán ra và tờ khai 01/GTGT dựng từ **Sales Invoice**, nhưng hóa đơn điện
tử phát hành từ **Delivery Note**. Module này bắc cầu giữa hai bên, theo thứ tự
ưu tiên:

1. Chứng từ HĐĐT trỏ thẳng vào Sales Invoice (kế toán tự điền), hoặc
2. Chứng từ HĐĐT của phiếu giao mà các dòng hàng của Sales Invoice tham chiếu tới.

Chỉ lấy hóa đơn **đã thực sự có số** — hóa đơn nháp hoặc đã hủy không được lọt
vào bảng kê.
"""

import frappe

from erpnext.einvoice.constants import ISSUED_STATUSES, STATUS_CANCELLED

FEI = "Fast EInvoice Document"

# Đã có số thật và còn giá trị kê khai. Hóa đơn đã hủy nội bộ (12) bị loại: nó
# bị Cơ quan Thuế từ chối nên không được vào bảng kê bán ra.
DECLARABLE_STATUSES = tuple(sorted(ISSUED_STATUSES - {STATUS_CANCELLED}))


def invoice_numbers_for(sales_invoices):
	"""``{tên Sales Invoice: {number, symbol, pattern, date}}`` cho các SI đã có HĐĐT."""
	names = [name for name in (sales_invoices or []) if name]
	if not names:
		return {}

	found = {}
	_collect_direct(names, found)
	_collect_via_delivery_notes([name for name in names if name not in found], found)
	return found


def _fields():
	return ["sales_invoice", "delivery_note", "fast_invoice_no", "fast_serial", "fast_pattern", "fast_signed_date"]


def _as_entry(row):
	return {
		"number": row.fast_invoice_no or "",
		"symbol": row.fast_serial or "",
		"pattern": row.fast_pattern or "",
		"date": row.fast_signed_date,
	}


def _collect_direct(names, found):
	for row in frappe.get_all(
		FEI,
		filters={
			"sales_invoice": ("in", names),
			"status": ("in", DECLARABLE_STATUSES),
			"fast_invoice_no": ("!=", ""),
		},
		fields=_fields(),
	):
		found[row.sales_invoice] = _as_entry(row)


def _collect_via_delivery_notes(names, found):
	"""Đi vòng qua phiếu giao mà các dòng hàng của hóa đơn bán tham chiếu tới."""
	if not names:
		return

	links = frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": ("in", names), "delivery_note": ("!=", "")},
		fields=["parent", "delivery_note"],
	)
	if not links:
		return

	notes = {link.delivery_note for link in links if link.delivery_note}
	by_note = {
		row.delivery_note: _as_entry(row)
		for row in frappe.get_all(
			FEI,
			filters={
				"delivery_note": ("in", list(notes)),
				"status": ("in", DECLARABLE_STATUSES),
				"fast_invoice_no": ("!=", ""),
			},
			fields=_fields(),
		)
	}
	if not by_note:
		return

	for link in links:
		if link.parent in found:
			continue
		if entry := by_note.get(link.delivery_note):
			found[link.parent] = entry
