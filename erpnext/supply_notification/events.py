# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Bộ máy bắt sự kiện chung — bốn móc phục vụ mọi chứng từ.

Bản build 05c nối tay 8 DocType vào `hooks.py`; thêm một điểm trên chứng từ mới
là phải sửa code và deploy. Nay bộ máy nối vào `doc_events["*"]`, còn "chứng từ
này có điểm nào không" là một lần đọc cache (`registry`) — DocType không có điểm
thì thoát ngay, không truy vấn gì thêm (NF1).

**Vì sao `on_change` chứ không phải `on_update`:** ERPNext ghi các trường trạng
thái (`delivery_status`, `per_received`, `status`, trạng thái duyệt) bằng
`Document.db_set`, mà `db_set` chỉ chạy `on_change` chứ không chạy `on_update`
(frappe/model/document.py:1290). Nối sai móc thì loại *Trường thay đổi* và
*Chuyển trạng thái duyệt* im lặng không bao giờ bắn.

Mọi lỗi ở đây đều bị nuốt — thông báo hỏng tuyệt đối không được chặn việc lưu
hay ghi sổ chứng từ (BR1).

Tham chiếu: docs/superpowers/specs/2026-09-23-thong-bao-tu-thiet-lap-design.md muc 4.2.
"""

import frappe
from frappe.model.workflow import get_workflow_name
from frappe.utils import flt

from erpnext.supply_notification import conditions, constants, dispatch, registry

MILESTONE_BY_EVENT = {
	constants.NEW: "new",
	constants.SUBMIT: dispatch.MILESTONE_SUBMIT,
	constants.CANCEL: "cancel",
}


def _skip() -> bool:
	"""Không bắn trong lúc cài đặt, migrate, chạy patch hay nhập dữ liệu."""
	return bool(
		frappe.flags.in_install
		or frappe.flags.in_migrate
		or frappe.flags.in_patch
		or frappe.flags.in_import
		or frappe.flags.in_setup_wizard
	)


def _eligible(doc) -> bool:
	return (
		not _skip()
		and doc.doctype not in constants.BLOCKED_DOCTYPES
		and not doc.meta.istable
		and registry.has_points(doc.doctype)
	)


def _fire(point, doc, milestone: str, triggered_by: str | None = None):
	if not conditions.match(point, doc):
		return
	dispatch.enqueue_dispatch(point.name, doc.doctype, doc.name, milestone, triggered_by)


def _handle(doc, trigger_event: str):
	try:
		if not _eligible(doc):
			return

		milestone = MILESTONE_BY_EVENT[trigger_event]
		for point in registry.points_for(doc.doctype, trigger_event):
			_fire(point, doc, milestone)
	except Exception:
		frappe.log_error(
			title="Supply Notification: không xếp được job thông báo",
			message=f"{doc.doctype} {doc.name} · {trigger_event}\n\n{frappe.get_traceback()}",
		)


# --- Bốn móc của `doc_events["*"]` ---------------------------------------


def after_insert(doc, method=None):
	_handle(doc, constants.NEW)


def on_submit(doc, method=None):
	_handle(doc, constants.SUBMIT)


def on_cancel(doc, method=None):
	_handle(doc, constants.CANCEL)


def on_change(doc, method=None):
	"""Trường thay đổi và chuyển trạng thái duyệt."""
	try:
		if not _eligible(doc) or doc.flags.in_insert:
			return

		before = doc.get_doc_before_save()
		if not before:
			return

		_handle_value_change(doc, before)
		_handle_workflow(doc, before)
	except Exception:
		frappe.log_error(
			title="Supply Notification: không xếp được job thông báo",
			message=f"{doc.doctype} {doc.name} · on_change\n\n{frappe.get_traceback()}",
		)


def value_changed(doc, before, fieldname: str) -> bool:
	"""Trường có **thực sự** đổi giá trị không.

	So sánh thô của Python coi `None` khác `0` và `0` khác `0.0`, nên một chứng
	từ vừa ghi sổ (ERPNext điền 0 vào hàng loạt trường số) sẽ bắn thông báo "giá
	trị đã đổi" cho những trường chưa ai đụng tới. Ở đây trống là trống, và số
	thì so theo số.
	"""
	old_value = before.get(fieldname)
	new_value = doc.get(fieldname)

	if old_value in (None, "") and new_value in (None, ""):
		return False

	df = doc.meta.get_field(fieldname)
	if df and df.fieldtype in conditions.NUMERIC_FIELDTYPES:
		return flt(old_value) != flt(new_value)

	return old_value != new_value


def _handle_value_change(doc, before):
	for point in registry.points_for(doc.doctype, constants.VALUE_CHANGE):
		fieldname = point.watch_field
		if not fieldname:
			continue

		new_value = doc.get(fieldname)
		if not value_changed(doc, before, fieldname):
			continue

		if point.watch_value and str(new_value or "") != str(point.watch_value):
			continue

		_fire(point, doc, f"change:{fieldname}:{new_value}")


def workflow_state_field(doctype: str) -> str | None:
	"""Tên trường giữ trạng thái duyệt của chứng từ, nếu có Workflow đang bật."""
	workflow = get_workflow_name(doctype)
	if not workflow:
		return None
	return frappe.get_cached_value("Workflow", workflow, "workflow_state_field")


def _handle_workflow(doc, before):
	points = registry.points_for(doc.doctype, constants.WORKFLOW_TRANSITION)
	if not points:
		return

	fieldname = workflow_state_field(doc.doctype)
	if not fieldname:
		return

	new_state = doc.get(fieldname)
	if not new_state or before.get(fieldname) == new_state:
		return

	for point in points:
		if point.workflow_state != new_state:
			continue
		_fire(point, doc, f"wf:{new_state}")
