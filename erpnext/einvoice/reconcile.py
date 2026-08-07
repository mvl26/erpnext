# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nút 12 — truy vấn đối soát với Fast (method 370) — mục E8.

Dùng khi nghi phát hành trùng, sau một lần timeout, hoặc để dọn "hóa đơn treo".
Đây là công cụ **thoát hiểm** của nhánh 7c: sau timeout, chỉ có 370 mới cho biết
hóa đơn thực ra đã ra số hay chưa.

Mặc định chỉ **so sánh và báo cáo**. Ghi đè dữ liệu hóa đơn theo Fast là hành
động cần người dùng xác nhận (cấp 2), nên phải truyền ``apply=True``.
"""

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime

from erpnext.einvoice.actions import ACTION_EXECUTE, FEI, _explain, _mirror_status
from erpnext.einvoice.constants import (
	STATUS_DRAFT,
	STATUS_ISSUED,
	STATUS_NEEDS_RECONCILE,
	TAX_STATUS_PENDING,
)
from erpnext.einvoice.fast_settings import check_enabled
from erpnext.einvoice.gateway import call_fast
from erpnext.einvoice.issue import ERROR_NOT_FOUND, METHOD_QUERY, parse_issue_result

# Các trường Fast là nguồn sự thật khi đối soát.
COMPARED_FIELDS = (
	("fast_invoice_no", "Số hóa đơn"),
	("fast_pattern", "Mẫu số"),
	("fast_serial", "Ký hiệu"),
	("fast_key_search", "Mã tra cứu"),
	("fast_signed_date", "Ngày phát hành"),
)


@frappe.whitelist()
def reconcile_invoice(fei, apply=False, client=None):
	"""Hỏi Fast xem hóa đơn này thực sự đang thế nào."""
	check_enabled()
	doc = frappe.get_doc(FEI, fei)

	response = call_fast(
		doc,
		action=ACTION_EXECUTE,
		method=METHOD_QUERY,
		data={"key": doc.fast_key, "period": getdate(doc.invoice_date).strftime("%Y%m")},
		purpose=_("Truy vấn đối soát hóa đơn"),
		client=client,
	)

	if not response.success:
		if response.error_code == ERROR_NOT_FOUND:
			return _handle_not_found(doc, apply)
		return {"ok": False, "found": False, "message": _explain(response)}

	found = parse_issue_result(response.message)
	differences = _differences(doc, found)

	if apply and differences:
		_apply_from_fast(doc, found)

	return {
		"ok": True,
		"found": True,
		"applied": bool(apply and differences),
		"differences": differences,
		"fast": {key: str(found.get(key) or "") for key, _label in COMPARED_FIELDS},
	}


def _differences(doc, found):
	"""So sánh từng trường; chỉ báo lệch khi Fast thực sự trả về giá trị."""
	rows = []
	for fieldname, label in COMPARED_FIELDS:
		theirs = found.get(fieldname)
		if theirs in (None, ""):
			continue
		ours = doc.get(fieldname)
		if str(ours or "") != str(theirs):
			rows.append({"field": fieldname, "label": label, "erp": str(ours or ""), "fast": str(theirs)})
	return rows


def _apply_from_fast(doc, found):
	"""Ghi đè theo Fast — chỉ chạy khi người dùng đã xác nhận."""
	values = {
		fieldname: found.get(fieldname)
		for fieldname, _label in COMPARED_FIELDS
		if found.get(fieldname) not in (None, "")
	}
	# Fast có hóa đơn này nghĩa là nó đã ra số thật.
	values["status"] = STATUS_ISSUED
	values.setdefault("tax_status", doc.tax_status or TAX_STATUS_PENDING)
	values["error_code"] = ""
	values["error_message"] = ""

	frappe.db.set_value(FEI, doc.name, values, update_modified=False)
	_mirror_status(doc.name, STATUS_ISSUED)

	if doc.delivery_note:
		frappe.db.set_value(
			"Delivery Note",
			doc.delivery_note,
			{
				"fast_invoice_no": values.get("fast_invoice_no") or doc.fast_invoice_no or "",
				"fast_key_search": values.get("fast_key_search") or doc.fast_key_search or "",
			},
			update_modified=False,
		)
	doc.add_comment("Comment", _("Đã cập nhật thông tin hóa đơn theo kết quả truy vấn Fast."))


def _handle_not_found(doc, apply):
	"""Fast không có hóa đơn này — chưa tiêu số nào.

	Với chứng từ đang treo ở "Cần đối soát" thì đây là tin tốt: lệnh phát hành
	trước đó không tới nơi, đưa về Nháp để phát hành lại một cách an toàn.
	"""
	message = _("Fast chưa có hóa đơn nào với Key này — chứng từ chưa tiêu số hóa đơn.")

	if apply and doc.status == STATUS_NEEDS_RECONCILE:
		frappe.db.set_value(
			FEI,
			doc.name,
			{
				"status": STATUS_DRAFT,
				"error_code": "",
				"error_message": "",
				"tax_status": "",
			},
			update_modified=False,
		)
		_mirror_status(doc.name, STATUS_DRAFT)
		doc.add_comment(
			"Comment",
			_("Truy vấn Fast xác nhận hóa đơn chưa phát hành — đưa về Nháp, có thể phát hành lại."),
		)
		message = _("Xác nhận chưa phát hành. Chứng từ đã đưa về Nháp, có thể phát hành lại.")

	return {"ok": True, "found": False, "applied": bool(apply), "differences": [], "message": message}
