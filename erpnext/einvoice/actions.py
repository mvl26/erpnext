# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Các nút gọi Fast trên chứng từ HĐĐT — Phần D và Phần E của đặc tả.

Mọi hàm ở đây đều đi qua ``gateway.call_fast`` nên tự động tuân thủ nguyên tắc
A1 (ghi log trước và sau lời gọi). Việc xác nhận của người dùng (Phần A2) nằm ở
tầng giao diện; phía server vẫn kiểm tra lại tiền điều kiện — không tin dữ liệu
client gửi lên.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

from erpnext.einvoice.constants import STATUS_DRAFT_VIEWED
from erpnext.einvoice.errors import describe_error
from erpnext.einvoice.fast_settings import check_enabled
from erpnext.einvoice.fast_client import decode_message
from erpnext.einvoice.gateway import call_fast
from erpnext.einvoice.payload import build_payload
from erpnext.einvoice.validation import validate_before_send

FEI = "Fast EInvoice Document"

# Bảng B2 — các trạng thái còn được phép xem bản nháp.
DRAFT_PREVIEW_STATUSES = frozenset(
	{
		"01 - Nháp",
		"02 - Đã xem nháp",
		"03 - Chờ khách duyệt",
		"04 - Khách đã duyệt",
		"98 - Cần đối soát",
		"99 - Lỗi",
	}
)

# Xem trước: Fast dựng PDF nhưng không ký số, không cấp số, không gửi CQT.
ACTION_PREVIEW = 600
ACTION_EXECUTE = 0
METHOD_INVOICE = 310


@frappe.whitelist()
def preview_draft(fei, client=None):
	"""Nút 3 — lấy bản nháp PDF từ Fast (mục E2).

	Không tiêu số hóa đơn: ``action=600`` chỉ dựng bản in thử. PDF thu được là
	**bản nháp không có giá trị pháp lý** cho tới khi thực sự phát hành.
	"""
	check_enabled()
	doc = frappe.get_doc(FEI, fei)
	_assert_status(doc, DRAFT_PREVIEW_STATUSES, _("xem bản nháp"))

	# Chặn trước khi tốn một lời gọi nào với Fast.
	validate_before_send(doc).throw_if_blocking()

	response = call_fast(
		doc,
		action=ACTION_PREVIEW,
		method=METHOD_INVOICE,
		data=build_payload(doc),
		purpose=_("Xem bản nháp PDF"),
		client=client,
	)

	if not response.success:
		_record_error(doc, response)
		return {"ok": False, "message": _explain(response)}

	file_url = _attach_pdf(doc, response.message, _draft_filename(doc))
	frappe.db.set_value(
		FEI,
		doc.name,
		{
			"draft_pdf": file_url,
			"draft_pdf_time": now_datetime(),
			"status": STATUS_DRAFT_VIEWED,
			"error_code": "",
			"error_message": "",
		},
		update_modified=False,
	)
	_mirror_status(doc.name, STATUS_DRAFT_VIEWED)
	return {"ok": True, "file_url": file_url}


# --- Tiện ích dùng chung cho các nút ----------------------------------------


def _assert_status(doc, allowed, what):
	if doc.status not in allowed:
		frappe.throw(
			_("Hóa đơn đang ở trạng thái {0} nên không {1} được.").format(doc.status, what)
		)


def _explain(response):
	described = describe_error(response.error_code, fallback=response.message)
	return f"{described.message} {described.hint}".strip()


def _record_error(doc, response):
	"""Ghi lỗi lên chứng từ nhưng **giữ nguyên trạng thái** (mục E2)."""
	frappe.db.set_value(
		FEI,
		doc.name,
		{"error_code": response.error_code or "", "error_message": _explain(response)},
		update_modified=False,
	)


def _attach_pdf(doc, base64_message, filename):
	"""Giải base64 rồi đính kèm vào chứng từ. File để riêng tư."""
	from frappe.utils.file_manager import save_file

	content = decode_message(base64_message)
	saved = save_file(filename, content, FEI, doc.name, is_private=1)
	return saved.file_url


def _draft_filename(doc):
	previous = frappe.db.count(
		"File", {"attached_to_doctype": FEI, "attached_to_name": doc.name, "file_name": ("like", "Nhap_%")}
	)
	return f"Nhap_{doc.name}_{previous + 1}.pdf"


def _mirror_status(fei_name, status):
	"""Đồng bộ trạng thái sang phiếu giao (mục C5)."""
	delivery_note = frappe.db.get_value(FEI, fei_name, "delivery_note")
	if delivery_note:
		frappe.db.set_value(
			"Delivery Note", delivery_note, "fast_einvoice_status", status, update_modified=False
		)
