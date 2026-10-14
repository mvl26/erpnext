# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tra số hóa đơn điện tử cho các chứng từ kế toán.

Bảng kê bán ra và tờ khai 01/GTGT dựng từ **Sales Invoice**, và từ bản 3.0 hóa
đơn điện tử cũng lập từ chính Sales Invoice — nên số hóa đơn nối thẳng, một — một:

1. Chứng từ HĐĐT trỏ thẳng vào Sales Invoice (`sales_invoice`) — đường chính.
2. Chỉ cho bản ghi lập theo bản 2.0 (nguồn phiếu giao) chưa gắn hóa đơn bán: đi
   vòng qua phiếu giao mà các dòng hàng của Sales Invoice tham chiếu tới.

Chỉ lấy hóa đơn **đã thực sự có số** — hóa đơn nháp hoặc đã hủy không được lọt
vào bảng kê.
"""

import frappe

from erpnext.einvoice.constants import (
	INVOICE_TYPE_ORIGINAL,
	INVOICE_TYPE_REPLACEMENT,
	ISSUED_STATUSES,
	SOURCE_DELIVERY_NOTE_V2,
	STATUS_CANCELLED,
	STATUS_REPLACED,
)

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
	return [
		"name",
		"sales_invoice",
		"delivery_note",
		"invoice_type",
		"status",
		"fast_invoice_no",
		"fast_serial",
		"fast_pattern",
		"fast_signed_date",
	]


def _as_entry(row):
	return {
		"number": row.fast_invoice_no or "",
		"symbol": row.fast_serial or "",
		"pattern": row.fast_pattern or "",
		"date": row.fast_signed_date,
	}


def _collect_direct(names, found):
	"""Số hóa đơn của chứng từ HĐĐT trỏ thẳng vào hóa đơn bán.

	Một hóa đơn bán có thể mang nhiều chứng từ: hóa đơn gốc, và hóa đơn điều chỉnh
	/ thay thế mang theo hóa đơn bán của nó. Số kê khai là của hóa đơn gốc — trừ
	khi hóa đơn gốc đã bị thay thế, khi đó là số của hóa đơn thay thế.
	"""
	by_invoice = {}
	for row in frappe.get_all(
		FEI,
		filters={
			"sales_invoice": ("in", names),
			"status": ("in", DECLARABLE_STATUSES),
			"fast_invoice_no": ("!=", ""),
		},
		fields=_fields(),
		order_by="creation asc",
	):
		by_invoice.setdefault(row.sales_invoice, []).append(row)

	for sales_invoice, rows in by_invoice.items():
		if chosen := _declared_row(rows):
			found[sales_invoice] = _as_entry(chosen)


def _declared_row(rows):
	originals = [row for row in rows if row.invoice_type == INVOICE_TYPE_ORIGINAL]
	replacements = [row for row in rows if row.invoice_type == INVOICE_TYPE_REPLACEMENT]
	if originals and originals[-1].status == STATUS_REPLACED and replacements:
		return replacements[-1]
	if originals:
		return originals[-1]
	return replacements[-1] if replacements else None


def _collect_via_delivery_notes(names, found):
	"""Đi vòng qua phiếu giao — chỉ cho hóa đơn gốc bản 2.0 chưa gắn hóa đơn bán.

	Đường vòng sai khi một hóa đơn bán gộp nhiều phiếu giao hay một phiếu giao tách
	nhiều hóa đơn bán, nên nó chỉ còn phục vụ sáu hóa đơn đã phát hành theo bản 2.0.
	Gắn hóa đơn bán vào chứng từ cũ (`builder.link_sales_invoice`) là chuyển nó sang
	đường thẳng.
	"""
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
				"source_doctype": SOURCE_DELIVERY_NOTE_V2,
				"invoice_type": INVOICE_TYPE_ORIGINAL,
				"sales_invoice": ("is", "not set"),
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
