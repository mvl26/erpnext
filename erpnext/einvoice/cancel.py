# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nút 13c — hủy nội bộ (method 330) — mục E10. **Không thể hoàn tác.**

Bối cảnh pháp lý: NĐ 70/2025 đã **bãi bỏ** thủ tục hủy hóa đơn thông thường.
Hàm 330 chỉ còn dùng cho đúng một tình huống: **hóa đơn bị Cơ quan Thuế từ
chối** — hủy trên hệ thống Fast để dữ liệu không lọt vào bảng kê bán ra.

Hóa đơn đã được CQT chấp nhận thì tuyệt đối không hủy: muốn thay đổi phải lập
hóa đơn điều chỉnh hoặc thay thế. Fast cũng chặn (78016, 900, 901) nhưng chặn ở
đây thì kế toán nhận được câu tiếng Việt đúng nghiệp vụ thay vì một mã lỗi.
"""

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime

from erpnext.einvoice.actions import ACTION_EXECUTE, FEI, _explain, _mirror_status, _record_error
from erpnext.einvoice.constants import STATUS_CANCELLED, STATUS_TAX_REJECTED
from erpnext.einvoice.fast_settings import check_enabled
from erpnext.einvoice.gateway import call_fast
from erpnext.einvoice.setup import is_chief_accountant

METHOD_CANCEL = 330


@frappe.whitelist()
def cancel_internally(fei, reason, minute_no=None, minute_date=None, client=None):
	"""Hủy hóa đơn bị Cơ quan Thuế từ chối, trên hệ thống Fast."""
	check_enabled()
	if not is_chief_accountant():
		raise frappe.PermissionError(
			_("Chỉ Kế toán trưởng HĐĐT được hủy hóa đơn — đây là hành động không thể hoàn tác.")
		)

	doc = frappe.get_doc(FEI, fei)
	if doc.status != STATUS_TAX_REJECTED:
		frappe.throw(
			_(
				"Chỉ hủy được hóa đơn bị Cơ quan Thuế từ chối. Hóa đơn {0} đang ở trạng thái {1} — "
				"nếu cần thay đổi thì lập hóa đơn điều chỉnh hoặc thay thế."
			).format(doc.name, doc.status)
		)

	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("Nhập lý do hủy — đây là căn cứ giải trình khi đối chiếu với Cơ quan Thuế."))

	if not doc.fast_key_search:
		frappe.throw(_("Chứng từ chưa có mã tra cứu (keySearch) nên không hủy được trên Fast."))

	response = call_fast(
		doc,
		action=ACTION_EXECUTE,
		method=METHOD_CANCEL,
		data={
			"key": doc.fast_key_search,
			"reason": reason,
			"minuteNo": minute_no or "",
			"minuteDate": getdate(minute_date).strftime("%Y%m%d") if minute_date else "",
		},
		purpose=_("Hủy nội bộ hóa đơn bị CQT từ chối"),
		client=client,
	)

	if not response.success:
		_record_error(doc, response)
		return {"ok": False, "message": _explain(response)}

	frappe.db.set_value(
		FEI,
		doc.name,
		{
			"status": STATUS_CANCELLED,
			"cancel_reason": reason,
			"cancelled_time": now_datetime(),
			"error_code": "",
			"error_message": "",
		},
		update_modified=False,
	)
	_unlock_delivery_note(doc)
	doc.add_comment("Comment", _("Đã hủy nội bộ trên Fast. Lý do: {0}").format(reason))
	return {"ok": True}


def _unlock_delivery_note(doc):
	"""Mở khóa phiếu giao để lập được hóa đơn mới.

	Xóa số hóa đơn nhưng **giữ** liên kết tới chứng từ đã hủy: cần lần lại được
	lịch sử khi đối chiếu, chỉ là không được để số hóa đơn đã hủy trôi vào bảng
	kê bán ra.
	"""
	if not doc.delivery_note:
		return
	frappe.db.set_value(
		"Delivery Note",
		doc.delivery_note,
		{"fast_invoice_no": "", "fast_key_search": "", "fast_einvoice_status": STATUS_CANCELLED},
		update_modified=False,
	)
