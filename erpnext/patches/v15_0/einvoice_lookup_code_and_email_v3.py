# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""HĐĐT — email dạng tra cứu (phân tích "Tự gửi HĐĐT sau phát hành", bản 2.2).

1. Điền mã tra cứu và trang tra cứu cho các hóa đơn đã có PDF chính thức trước khi
   hệ thống biết đọc chúng từ PDF (mục 4.3). Không gọi Fast: đọc lại file đã lưu.
2. Thay mẫu email hóa đơn chính thức bằng mẫu Miyano (mục 4.2) — **chỉ khi** mẫu
   còn nguyên bản hệ thống tạo; mẫu kế toán đã sửa tay thì giữ nguyên và ghi Error Log.
"""

import frappe

FEI = "Fast EInvoice Document"


def execute():
	frappe.reload_doc("einvoice", "doctype", "fast_einvoice_document")
	frappe.reload_doc("einvoice", "doctype", "fast_einvoice_settings")

	_backfill_lookup_codes()

	from erpnext.einvoice.setup import upgrade_issued_template

	upgrade_issued_template()


def _backfill_lookup_codes():
	from erpnext.einvoice.actions import fill_lookup_from_pdf

	rows = frappe.get_all(
		FEI,
		filters={"official_pdf": ("is", "set"), "fast_lookup_code": ("is", "not set")},
		fields=["name", "official_pdf"],
	)
	unread = []
	for row in rows:
		try:
			content = frappe.get_doc("File", {"file_url": row.official_pdf}).get_content()
			if not fill_lookup_from_pdf(row.name, content):
				unread.append(row.name)
		except Exception:
			frappe.log_error(title=f"HĐĐT: không đọc lại được PDF chính thức của {row.name}")
	if unread:
		frappe.log_error(
			title="HĐĐT: chưa đọc được mã tra cứu từ PDF",
			message=(
				"Các chứng từ sau có PDF chính thức nhưng không đọc được mã tra cứu — chép tay mã "
				f"từ PDF vào trường “Mã tra cứu in trên hóa đơn”: {', '.join(unread)}"
			),
		)
