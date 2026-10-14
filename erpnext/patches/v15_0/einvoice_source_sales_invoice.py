# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""HĐĐT bản 3.0: đổi chứng từ nguồn từ Delivery Note sang Sales Invoice (đặc tả Phần K, mục K4).

Patch không gọi Fast và không tạo chứng từ kế toán nào. Các bước:

1. Mọi bản ghi HĐĐT có sẵn là bản ghi bản 2.0: `source_doctype = Delivery Note (v2)`.
   Bản ghi đã có số giữ nguyên, **không đổi `fast_key`** — Key đã nằm trên Fast.
2. Bản nháp bản 2.0 mà phiếu giao có đúng một hóa đơn bán: gắn hóa đơn bán, chuyển
   nguồn sang Sales Invoice và nạp lại dữ liệu từ hóa đơn bán.
3. Bản nháp bản 2.0 mà phiếu giao chưa có hóa đơn bán: xóa nháp — lập lại từ hóa
   đơn bán khi có. Bản nháp chưa tiêu số hóa đơn nào nên xóa không mất gì.
4. Custom field trên Sales Invoice, ẩn bảy field trên Delivery Note, sửa hai mẫu
   email (`einvoice.setup`).
5. Gỡ custom field `vn_einvoice_*` và bảng `Vietnam E Invoice Log` của luồng cũ —
   chỉ khi không còn dữ liệu nghiệp vụ nào.
6. Đổi `modified` của Sales Invoice và Delivery Note để trình duyệt nạp lại form
   script (meta nằm trong localStorage, Ctrl+Shift+R không xóa được).
7. Tự kiểm tra ở cuối và ghi Error Log nếu còn sót: lần dọn luồng cũ ngày
   07/08/2026 đã chạy mà field vẫn còn nguyên, không ai biết.

Bản chép rác `FEI-2026-00007` (cùng số, cùng Key với 00006) **không** bị đụng tới:
xử lý theo quyết định J11, không tự xóa.
"""

import frappe
from frappe.utils import now

from erpnext.einvoice.constants import (
	EDITABLE_STATUSES,
	INVOICE_TYPE_ORIGINAL,
	SOURCE_DELIVERY_NOTE_V2,
	SOURCE_SALES_INVOICE,
)

FEI = "Fast EInvoice Document"
OLD_LOG_DOCTYPE = "Vietnam E Invoice Log"
SALES_INVOICE_FIELDS = ("fast_invoice_no", "fast_einvoice_status", "fast_key_search", "fast_einvoice_pdf_url")


def execute():
	frappe.reload_doc("einvoice", "doctype", "fast_einvoice_document")
	frappe.reload_doc("einvoice", "doctype", "fast_einvoice_settings")

	from erpnext.einvoice.setup import setup_einvoice

	setup_einvoice()
	_mark_existing_records_as_v2()
	_move_drafts_to_sales_invoice()
	_remove_old_si_flow()
	_bump_form_scripts()
	_self_check()


def _mark_existing_records_as_v2():
	for name in frappe.get_all(FEI, filters={"source_doctype": ("is", "not set")}, pluck="name"):
		frappe.db.set_value(FEI, name, "source_doctype", SOURCE_DELIVERY_NOTE_V2, update_modified=False)


def _move_drafts_to_sales_invoice():
	from erpnext.einvoice.builder import (
		_copy_from_source,
		clear_source_stamp,
		live_invoice_for,
		sales_invoice_refusal,
		stamp_source_documents,
	)
	from erpnext.einvoice.fast_settings import get_settings

	drafts = frappe.get_all(
		FEI,
		filters={
			"source_doctype": SOURCE_DELIVERY_NOTE_V2,
			"invoice_type": INVOICE_TYPE_ORIGINAL,
			"status": ("in", list(EDITABLE_STATUSES)),
			"fast_invoice_no": ("is", "not set"),
			"sales_invoice": ("is", "not set"),
		},
		fields=["name", "delivery_note"],
	)
	for draft in drafts:
		sales_invoices = sorted(
			set(
				frappe.get_all(
					"Sales Invoice Item",
					filters={
						"delivery_note": draft.delivery_note,
						"parenttype": "Sales Invoice",
						"docstatus": 1,
					},
					pluck="parent",
				)
			)
		)
		if not sales_invoices:
			# Chưa có hóa đơn bán thì không có gì để lập hóa đơn — lập lại khi có.
			frappe.delete_doc(FEI, draft.name, ignore_permissions=True, force=True)
			continue
		if len(sales_invoices) > 1:
			frappe.log_error(
				title="HĐĐT 3.0: bản nháp cần kế toán xử lý",
				message=(
					f"{draft.name} (phiếu giao {draft.delivery_note}) ứng với nhiều hóa đơn bán "
					f"{', '.join(sales_invoices)}. Patch không tự chọn — xóa nháp rồi lập lại từ hóa đơn bán."
				),
			)
			continue

		sales_invoice = sales_invoices[0]
		source = frappe.get_doc("Sales Invoice", sales_invoice)
		if sales_invoice_refusal(source) or live_invoice_for(sales_invoice, exclude=draft.name):
			frappe.log_error(
				title="HĐĐT 3.0: bản nháp cần kế toán xử lý",
				message=f"{draft.name}: hóa đơn bán {sales_invoice} không nhận chứng từ này được.",
			)
			continue

		doc = frappe.get_doc(FEI, draft.name)
		doc.source_doctype = SOURCE_SALES_INVOICE
		doc.sales_invoice = sales_invoice
		_copy_from_source(doc, source, get_settings())
		frappe.db.set_value(
			FEI,
			doc.name,
			{"source_doctype": SOURCE_SALES_INVOICE, "sales_invoice": sales_invoice},
			update_modified=False,
		)
		# Lưu bỏ qua chốt đổi nguồn: đây là lần chuyển nguồn duy nhất được phép,
		# và hai trường nguồn đã được ghi thẳng xuống ở trên.
		doc.flags.ignore_permissions = True
		doc.save()

		clear_source_stamp("Delivery Note", draft.delivery_note)
		stamp_source_documents(doc.name)


def _remove_old_si_flow():
	"""Dọn nốt luồng HĐĐT cũ chạy theo Sales Invoice (patch `remove_vn_einvoice_si_flow`).

	Không dọn thì form Sales Invoice có hai mục "Hóa đơn điện tử". Chỉ dọn khi
	không còn dữ liệu nghiệp vụ — dữ liệu hóa đơn là chứng từ pháp lý.
	"""
	if _has_old_flow_data():
		frappe.log_error(
			title="HĐĐT 3.0: giữ lại dữ liệu luồng cũ",
			message=(
				f"Site còn bản ghi {OLD_LOG_DOCTYPE} hoặc Sales Invoice đã đóng dấu số HĐĐT luồng cũ. "
				"Patch không xóa để bảo toàn chứng từ — cần kế toán đối chiếu và dọn thủ công."
			),
		)
		return

	for name in frappe.get_all("Custom Field", filters={"fieldname": ("like", "vn_einvoice%")}, pluck="name"):
		frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)

	if frappe.db.exists("DocType", OLD_LOG_DOCTYPE):
		frappe.delete_doc("DocType", OLD_LOG_DOCTYPE, ignore_permissions=True, force=True)
	if frappe.db.table_exists(OLD_LOG_DOCTYPE):
		frappe.db.sql_ddl(f"drop table `tab{OLD_LOG_DOCTYPE}`")

	frappe.clear_cache(doctype="Sales Invoice")
	frappe.clear_cache(doctype="Company")


def _has_old_flow_data():
	if frappe.db.table_exists(OLD_LOG_DOCTYPE) and frappe.db.count(OLD_LOG_DOCTYPE):
		return True
	if not frappe.db.has_column("Sales Invoice", "vn_einvoice_number"):
		return False
	return bool(
		frappe.db.sql("select 1 from `tabSales Invoice` where ifnull(vn_einvoice_number, '') != '' limit 1")
	)


def _bump_form_scripts():
	for doctype in ("Sales Invoice", "Delivery Note"):
		frappe.db.set_value("DocType", doctype, "modified", now(), update_modified=False)
		frappe.clear_cache(doctype=doctype)


def _self_check():
	problems = []

	meta = frappe.get_meta("Sales Invoice", cached=False)
	missing = [field for field in SALES_INVOICE_FIELDS if not meta.has_field(field)]
	if missing:
		problems.append(f"Sales Invoice thiếu custom field: {', '.join(missing)}")
	shown = frappe.get_all(
		"Custom Field",
		filters={"dt": "Delivery Note", "fieldname": ("like", "fast_%"), "hidden": 0},
		pluck="fieldname",
	)
	if shown:
		problems.append(f"Field HĐĐT trên Delivery Note chưa ẩn: {', '.join(shown)}")

	leftover = frappe.get_all("Custom Field", filters={"fieldname": ("like", "vn_einvoice%")}, pluck="name")
	if leftover and not _has_old_flow_data():
		problems.append(f"Còn custom field luồng cũ: {', '.join(leftover)}")

	unsourced = frappe.get_all(FEI, filters={"source_doctype": ("is", "not set")}, pluck="name")
	if unsourced:
		problems.append(f"Chứng từ HĐĐT chưa có Loại chứng từ nguồn: {', '.join(unsourced)}")
	orphaned = frappe.get_all(
		FEI,
		filters={"source_doctype": SOURCE_SALES_INVOICE, "sales_invoice": ("is", "not set")},
		pluck="name",
	)
	if orphaned:
		problems.append(f"Chứng từ HĐĐT nguồn hóa đơn bán mà chưa gắn hóa đơn bán: {', '.join(orphaned)}")

	for template in frappe.get_all("Email Template", filters={"name": ("like", "Fast HĐĐT%")}, pluck="name"):
		doc = frappe.get_doc("Email Template", template)
		text = " ".join(doc.get(field) or "" for field in ("subject", "response_html", "response"))
		if "doc.delivery_note" in text and "doc.sales_invoice" not in text:
			problems.append(f"Mẫu email {template} còn nêu phiếu giao — đã bị sửa tay, cần sửa tay tiếp.")

	if problems:
		frappe.log_error(title="HĐĐT 3.0: patch chuyển nguồn còn sót", message="\n".join(problems))
