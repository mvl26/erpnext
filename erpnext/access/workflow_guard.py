"""Server-side workflow guards — spec 9.2 and 11.3 H5, H10, H11, plan review rows R-15 to R-18 and R-23.

Frappe enforces a workflow only half-way: ``allow_edit`` is a client-side lock, ``validate_workflow`` judges a
transition on the *stored* copy, and a submit that keeps the state goes through untouched. The four
``doc_events["*"]`` hooks below close those gaps. Call order inside ``Document._save`` (frappe/model/document.py)
that every guard relies on:

1. ``check_if_latest`` (document.py:859) loads ``_doc_before_save`` from the database;
2. ``run_before_save_methods`` (document.py:1125) runs ``before_validate`` — the controller method first, then
   the ``doc_events`` hooks (``Document.hook``, document.py:1356-1376) — then ``validate``, then ``before_submit``;
3. only then ``_validate`` → ``validate_workflow`` (document.py:636, 687) and ``set_workflow_state_on_action``,
   which moves a submitted doc to the first ``doc_status 1`` state (frappe/model/workflow.py:362-376);
4. ``run_post_save_methods`` ends with ``on_change`` (document.py:1200).
5. A cancel runs only ``before_cancel`` (document.py:1151) and skips ``_validate`` (document.py:416), so frappe never
   moves a cancelled doc to its cancelled state; ``before_cancel`` here does, before ``db_update`` (428).

Only the workflows the RBAC sync builds from ``workflows.json`` are guarded; assetcore's and the legacy ones
are left to frappe.

R-GATE: every hook returns at once while ``mvl_rbac_enabled`` is off — these run on every save of the site.
Saves by Administrator or with ``ignore_permissions`` (system JEs, jobs) skip H5/H10/H11 and write no R-18 marker.
"""

import json
from functools import lru_cache

import frappe
from frappe import _
from frappe.model import child_table_fields, default_fields, no_value_fields
from frappe.model.workflow import get_workflow_name, is_transition_condition_satisfied
from frappe.utils import cint, cstr, flt, get_datetime, get_time, getdate

from erpnext.access.permissions.sync import is_enabled

PENDING_PREFIX = "Chờ"
MARKER_PREFIX = "MVL-DUYET: "
MARKER_ARROW = " → "
NUMERIC_TYPES = frozenset(("Currency", "Float", "Int", "Long Int", "Percent", "Check", "Rating", "Duration"))
SKIP_FIELDS = frozenset(default_fields) | frozenset(child_table_fields) | {"amended_from"}


# -- shared ---------------------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _matrix():
	from erpnext.access.permissions.matrix import load_matrix

	return load_matrix()


@lru_cache(maxsize=1)
def _managed_names() -> frozenset:
	from erpnext.access.permissions.workflows import workflow_name

	return frozenset(
		workflow_name(code, doctype) for code, wf in _matrix().workflows.items() for doctype in wf["doctypes"]
	)


def _active_workflow(doctype: str):
	"""The active Workflow of ``doctype`` if the RBAC sync manages it, else None."""
	name = get_workflow_name(doctype)
	if not name or name not in _managed_names():
		return None
	return frappe.get_cached_doc("Workflow", name)


def _guarded_workflow(doc):
	"""The active Workflow of ``doc`` when a guard applies to this save, else None."""
	if frappe.session.user == "Administrator" or doc.flags.ignore_permissions:
		return None
	return _active_workflow(doc.doctype)


def _first_state(workflow, doc_status: int = 0) -> str | None:
	"""First state with ``doc_status`` — the one frappe assigns (spec 9.2.4); a draft falls back to states[0]."""
	rows = [s for s in workflow.states if cint(s.doc_status) == doc_status]
	if not rows and doc_status == 0:
		rows = workflow.states
	return rows[0].state if rows else None


def _state_row(workflow, state: str):
	return next((s for s in workflow.states if s.state == state), None)


def _states(doc, workflow) -> tuple[str, str]:
	"""(state before the save, state being saved); an empty state means the first draft state, as in frappe."""
	field = workflow.workflow_state_field
	before = getattr(doc, "_doc_before_save", None)
	first = _first_state(workflow)
	return (before.get(field) if before is not None else None) or first, doc.get(field) or first


def _user_transitions(workflow, from_state: str, doc):
	roles = set(frappe.get_roles())
	return [
		t
		for t in workflow.transitions
		if t.state == from_state and t.allowed in roles and is_transition_condition_satisfied(t, doc)
	]


def _h5_skip_tables() -> dict:
	return _matrix().rules.get("h5_skip_tables") or {}


def reload_rules() -> None:
	"""Forget the cached matrix — rules and managed workflow names (tests, or after editing the matrix)."""
	_matrix.cache_clear()
	_managed_names.cache_clear()


# -- H5: no content edits without the state's allow_edit ------------------------------------------


def _normalise(df, value):
	"""Make a value typed by the user and the value read back from the database compare equal."""
	if df.fieldtype in NUMERIC_TYPES:
		return flt(value, 9)
	if value is None or value == "":
		return ""
	try:
		if df.fieldtype == "Date":
			return str(getdate(value))
		if df.fieldtype == "Datetime":
			return str(get_datetime(value))
		if df.fieldtype == "Time":
			return str(get_time(value))
		if df.fieldtype == "JSON":
			return json.dumps(frappe.parse_json(value), sort_keys=True, default=str)
	except Exception:
		pass
	return cstr(value)


def _is_compared(df, skip: set) -> bool:
	"""Fields a user can type: not read-only/hidden/set-only-once, not virtual."""
	return not (
		df.fieldname in skip
		or df.fieldtype in no_value_fields
		or df.read_only
		or df.hidden
		or df.set_only_once
		or df.is_virtual
	)


def _refetched(meta, df, new, old) -> bool:
	"""True when a changed ``fetch_from`` field was refilled from its link by frappe itself — not a user edit.

	``_validate_links`` runs before ``before_validate`` (frappe/model/base_document.py:816-851). It overwrites a
	plain ``fetch_from`` field whenever the link is set, except on a row already at ``docstatus`` 1 (a submit),
	where only ``allow_on_submit`` fields are refilled. It fills a ``fetch_if_empty`` field only when that is empty,
	so such a field counts as refilled only when its old value was empty and the new one is exactly what the link
	holds now — any other value was typed, and is compared like a plain field.
	"""
	link_fieldname, _sep, source = df.fetch_from.partition(".")
	link_df = meta.get_field(link_fieldname)
	link_value = new.get(link_fieldname)
	if not (link_df and link_value and source):
		return False
	if not df.fetch_if_empty:
		return cint(new.get("docstatus")) != 1 or bool(df.allow_on_submit)
	if _normalise(df, old.get(df.fieldname)) != _normalise(df, None):
		return False
	doctype = link_df.options if link_df.fieldtype == "Link" else new.get(link_df.options)
	if not doctype:
		return False
	fetched = frappe.db.get_value(doctype, link_value, source)
	return _normalise(df, new.get(df.fieldname)) == _normalise(df, fetched)


def _changed_fields(meta, new, old, skip: set) -> bool:
	for df in meta.fields:
		if not _is_compared(df, skip):
			continue
		if _normalise(df, new.get(df.fieldname)) == _normalise(df, old.get(df.fieldname)):
			continue
		if df.fetch_from and _refetched(meta, df, new, old):
			continue
		return True
	return False


def _table_changed(df, new_rows, old_rows) -> bool:
	new_by_name = {row.name: row for row in new_rows or []}
	old_by_name = {row.name: row for row in old_rows or []}
	if new_by_name.keys() != old_by_name.keys():
		return True
	child_meta = frappe.get_meta(df.options)
	return any(
		_changed_fields(child_meta, row, old_by_name[name], SKIP_FIELDS) for name, row in new_by_name.items()
	)


def _content_changed(doc, before, workflow, target_row) -> bool:
	skip = set(SKIP_FIELDS) | {workflow.workflow_state_field}
	if target_row is not None and target_row.update_field:
		skip.add(target_row.update_field)
	if _changed_fields(doc.meta, doc, before, skip):
		return True
	rule = _h5_skip_tables().get(doc.doctype) or {}
	skipped_tables = set(rule.get("tables") or ()) if doc.get(rule.get("flag") or "") else set()
	return any(
		_table_changed(df, doc.get(df.fieldname), before.get(df.fieldname))
		for df in doc.meta.get_table_fields()
		if df.fieldname not in skipped_tables and not (df.read_only or df.hidden)
	)


def before_validate(doc, method=None) -> None:
	"""H5 (R-15): before the controller, so only what the user sent is compared — not the posting time a
	controller resets (erpnext/utilities/transaction_base.py:19-22). Stock Entry's own ``before_validate``
	re-applies putaway rules first (stock_entry.py:183-189), hence ``rules.json["h5_skip_tables"]``."""
	if not is_enabled():
		return
	workflow = _guarded_workflow(doc)
	before = getattr(doc, "_doc_before_save", None)
	if workflow is None or before is None:
		return
	old_state, new_state = _states(doc, workflow)
	old_row = _state_row(workflow, old_state)
	if old_row is None or old_row.allow_edit in frappe.get_roles():
		return
	if _content_changed(doc, before, workflow, _state_row(workflow, new_state)):
		frappe.throw(_("Phiếu đang ở trạng thái {0}, không được sửa nội dung.").format(old_state))


# -- R-23, R-16, H10: a state change must be a real transition on the doc being saved -------------


def _employee_user(doc) -> str | None:
	field = doc.meta.get_field("employee")
	if not (field and field.fieldtype == "Link" and field.options == "Employee" and doc.get("employee")):
		return None
	return frappe.db.get_value("Employee", doc.employee, "user_id")


def _approved_a_step(doc, user: str) -> bool:
	"""R-18: the user left a "Chờ …" state on this doc since the last time an approval chain ended.

	A chain ends on a marker whose target is not a "Chờ …" state (rejected, or approved); after a rejection
	and resubmission the same approvers judge the new version again.
	"""
	markers = frappe.get_all(
		"Comment",
		filters={
			"reference_doctype": doc.doctype,
			"reference_name": doc.name,
			"comment_type": "Info",
			"content": ("like", f"{MARKER_PREFIX}{PENDING_PREFIX}%"),
		},
		fields=["owner", "content"],
		order_by="creation asc",
	)
	since_chain_start = []
	for marker in markers:
		since_chain_start.append(marker.owner)
		target = marker.content.rpartition(MARKER_ARROW)[2]
		if not target.startswith(PENDING_PREFIX):
			since_chain_start = []  # chain ended (rejected/approved): a resubmission is judged afresh
	return user in since_chain_start


def _check_h10(doc, user: str) -> None:
	if doc.owner == user:
		frappe.throw(_("Không được tự duyệt chứng từ do chính mình lập."), frappe.PermissionError)
	if _employee_user(doc) == user:
		frappe.throw(_("Không được tự duyệt chứng từ của chính mình."), frappe.PermissionError)
	if not doc.is_new() and _approved_a_step(doc, user):
		frappe.throw(
			_("Bạn đã duyệt một bước trước trên chứng từ này; bước này phải do người khác duyệt."),
			frappe.PermissionError,
		)


def validate(doc, method=None) -> None:
	"""After the controller, so totals are recomputed. Runs only when the state changes."""
	if not is_enabled():
		return
	workflow = _guarded_workflow(doc)
	if workflow is None:
		return
	old_state, new_state = _states(doc, workflow)
	if old_state == new_state:
		return

	# R-23 — the action must match the target state: a submit cannot land in "Chờ …" (frappe would lift it
	# to the first doc_status 1 state), a draft save cannot land in a submitted state.
	target = _state_row(workflow, new_state)
	if target is None or cint(target.doc_status) != cint(doc.docstatus):
		frappe.throw(
			_("Trạng thái {0} không khớp với thao tác đang làm trên chứng từ.").format(new_state),
			frappe.PermissionError,
		)

	pending = old_state.startswith(PENDING_PREFIX)
	user = frappe.session.user
	if pending:
		_check_h10(doc, user)  # before R-16: G11 in the condition would hide this behind a generic message

	# R-16 — frappe judges the transition on the stored copy; judge it on the values being saved too.
	roles = set(frappe.get_roles())
	candidates = [
		t
		for t in workflow.transitions
		if t.state == old_state and t.next_state == new_state and t.allowed in roles
	]
	if not any(is_transition_condition_satisfied(t, doc) for t in candidates):
		if candidates:
			reason = _(
				"điều kiện của bước {0} sai trên giá trị hiện tại của chứng từ (đã tính lại khi lưu)"
			).format(", ".join(dict.fromkeys(t.action for t in candidates)))
		else:
			reason = _("vai trò của bạn không có bước duyệt này")
		frappe.throw(
			_("Không có bước duyệt hợp lệ từ {0} sang {1}: {2}.").format(old_state, new_state, reason),
			frappe.PermissionError,
		)

	if pending:
		doc.flags.mvl_wf_step = (old_state, new_state)


def on_change(doc, method=None) -> None:
	"""R-18: mark every step that left a "Chờ …" state, whichever path it took (form, API, apply_workflow)."""
	if not is_enabled():
		return
	step = doc.flags.pop("mvl_wf_step", None)
	if step:
		doc.add_comment("Info", f"{MARKER_PREFIX}{step[0]}{MARKER_ARROW}{step[1]}")


# -- H11: no submit around the workflow -----------------------------------------------------------


def before_submit(doc, method=None) -> None:
	"""H11: a 0→1 submit that keeps the state must match a self-approval transition of the user.

	Never assigns ``workflow_state`` (R-17): frappe moves the doc to the first ``doc_status 1`` state after this
	hook, so only a transition that leads exactly there, from a state that allows self-approval, counts (R-13).
	"""
	if not is_enabled():
		return
	workflow = _guarded_workflow(doc)
	if workflow is None or cint(doc.docstatus) != 1:
		return
	before = getattr(doc, "_doc_before_save", None)
	if before is not None and cint(before.docstatus) != 0:
		return
	old_state, new_state = _states(doc, workflow)
	if old_state != new_state:
		return  # a transition: ``validate`` judged it

	submitted = _first_state(workflow, 1)
	if any(  # self-approval only, and only to the state frappe will assign — not e.g. WF-LA "Từ chối"
		t.next_state == submitted and cint(t.allow_self_approval)
		for t in _user_transitions(workflow, old_state, doc)
	):
		return
	frappe.throw(
		_("Phải duyệt qua quy trình: bạn không có bước duyệt nào để ghi sổ thẳng từ trạng thái {0}.").format(
			old_state
		),
		frappe.PermissionError,
	)


# -- cancel: the state frappe forgets ---------------------------------------------------------------


def before_cancel(doc, method=None) -> None:
	"""Move a cancelled doc to the first ``doc_status 2`` state (spec 9.2.4) — frappe skips this on cancel.

	No Administrator / ``ignore_permissions`` bypass: the state must be right whoever cancels.
	"""
	if not is_enabled():
		return
	workflow = _active_workflow(doc.doctype)
	if workflow is None:
		return
	field = workflow.workflow_state_field
	current = _state_row(workflow, doc.get(field) or "")
	if current is not None and cint(current.doc_status) == 2:
		return  # already a cancelled state (e.g. set by a transition): keep it
	cancelled = _first_state(workflow, 2)
	if cancelled:
		doc.set(field, cancelled)
