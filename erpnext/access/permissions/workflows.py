"""Workflow step of the sync — builds the Workflow docs of spec 9.3 from ``matrix/workflows.json``.

The JSON holds role codes and only the "Điều kiện (ngoài G11)" part of each condition. The builder:
- turns codes into Frappe role names, one transition row per (from, action, to, role);
- substitutes the approval limits ``{H1}`` ``{H2}`` ``{H3}`` (R-1);
- appends G11 (approver ≠ creator, ≠ the employee on HR documents) and ``allow_self_approval = 0`` on every
  transition leaving a "Chờ …" state;
- adds "Mở lại" (Từ chối → Nháp, the creator roles) where Từ chối is a draft state.
"""

import frappe
from frappe.utils import cint

from erpnext.access.permissions.matrix import Matrix
from erpnext.access.permissions.schema import _set_property

LIMIT_EXPR = "float(frappe.db.get_value('MVL Approval Limits', None, '{f}') or 0)"
LIMITS = {"{H1}": "h1", "{H2}": "h2", "{H3}": "h3"}
STATE_FIELD = "workflow_state"
PENDING_PREFIX = "Chờ"
DRAFT = "Nháp"
REJECTED = "Từ chối"
REOPEN = "Mở lại"
# 9.4 — Business Trip keeps the name of the workflow hrms creates, so ``setup_cong_tac_workflow`` finds it.
FIXED_NAMES = {"WF-BT": "Cong Tac Approval"}
FLAGS = ("document_type", "is_active", "override_status", "send_email_alert", "workflow_state_field")


def render_condition(raw: str) -> str:
	for placeholder, field in LIMITS.items():
		raw = raw.replace(placeholder, LIMIT_EXPR.format(f=field))
	return raw


def _has_employee_field(doctype: str) -> bool:
	field = frappe.get_meta(doctype).get_field("employee")
	return bool(field and field.fieldtype == "Link" and field.options == "Employee")


def g11_condition(doctype: str) -> str:
	condition = "doc.owner != frappe.session.user"
	if _has_employee_field(doctype):
		condition += " and frappe.db.get_value('Employee', doc.employee, 'user_id') != frappe.session.user"
	return condition


def workflow_name(code: str, doctype: str) -> str:
	return FIXED_NAMES.get(code) or f"{code} {doctype}"


def _join(parts: list[str]) -> str | None:
	if not parts:
		return None
	if len(parts) == 1:
		return parts[0]
	return " and ".join(f"({p})" for p in parts)


def _state_row(m: Matrix, doctype: str, state: dict) -> dict:
	row = {
		"state": state["state"],
		"doc_status": str(state["doc_status"]),
		"allow_edit": m.role_names(state["allow_edit"])[0],
	}
	targets = state.get("update_doctypes")
	if state.get("update_field") and (not targets or doctype in targets):
		row["update_field"] = state["update_field"]
		row["update_value"] = state.get("update_value")
	return row


def _transition_rows(m: Matrix, doctype: str, t: dict) -> list[dict]:
	if doctype in (t.get("except_doctypes") or ()):
		return []
	raw = (t.get("per_doctype_condition") or {}).get(doctype, t.get("condition"))
	parts = [render_condition(raw)] if raw else []
	pending = t["from"].startswith(PENDING_PREFIX)
	if pending:
		parts.append(g11_condition(doctype))
	condition = _join(parts)
	return [
		{
			"state": t["from"],
			"action": t["action"],
			"next_state": t["to"],
			"allowed": role,
			"allow_self_approval": 0 if pending else 1,
			"condition": condition,
		}
		for code in t["roles"]
		for role in m.role_names(code)
	]


def build_workflow(m: Matrix, code: str, doctype: str) -> dict:
	wf = m.workflows[code]
	transitions = [row for t in wf["transitions"] for row in _transition_rows(m, doctype, t)]
	rejected = next((s for s in wf["states"] if s["state"] == REJECTED), None)
	if rejected is not None and int(rejected["doc_status"]) == 0:
		reopen = {"from": REJECTED, "action": REOPEN, "to": DRAFT, "roles": wf.get("creators") or []}
		transitions += _transition_rows(m, doctype, reopen)
	return {
		"doctype": "Workflow",
		"workflow_name": workflow_name(code, doctype),
		"document_type": doctype,
		"is_active": 1,
		"override_status": 1,
		"send_email_alert": 1,
		"workflow_state_field": STATE_FIELD,
		"states": [_state_row(m, doctype, s) for s in wf["states"]],
		"transitions": transitions,
	}


# -- sync ----------------------------------------------------------------------------------------


def _signature(doc: dict) -> tuple:
	"""What the sync owns of a Workflow, normalised so a stored doc and a built dict compare equal."""

	def text(value) -> str:
		return "" if value is None else str(value)

	states = tuple(
		(
			s["state"],
			text(s["doc_status"]),
			s["allow_edit"],
			text(s.get("update_field")),
			text(s.get("update_value")),
		)
		for s in doc["states"]
	)
	transitions = tuple(
		(
			t["state"],
			t["action"],
			t["next_state"],
			t["allowed"],
			cint(t.get("allow_self_approval")),
			text(t.get("condition")),
		)
		for t in doc["transitions"]
	)
	flags = tuple(
		text(doc.get(f)) if f in ("document_type", "workflow_state_field") else cint(doc.get(f))
		for f in FLAGS
	)
	return flags, states, transitions


def _ensure_masters(doctype: str, fieldname: str, names: set[str]) -> None:
	for name in sorted(names):
		if not frappe.db.exists(doctype, name):
			frappe.get_doc({"doctype": doctype, fieldname: name}).insert(ignore_permissions=True)


def _save(wanted: dict) -> None:
	name = wanted["workflow_name"]
	if not frappe.db.exists("Workflow", name):
		frappe.get_doc(wanted).insert(ignore_permissions=True)
		return
	doc = frappe.get_doc("Workflow", name)
	doc.update({f: wanted[f] for f in FLAGS})
	doc.set("states", wanted["states"])
	doc.set("transitions", wanted["transitions"])
	doc.save(ignore_permissions=True)


def _differs(wanted: dict) -> bool:
	name = wanted["workflow_name"]
	if not frappe.db.exists("Workflow", name):
		return True
	stored = frappe.get_doc("Workflow", name).as_dict()
	return _signature(stored) != _signature(wanted)


def _show_in_list_view(doctype: str) -> None:
	"""9.2.3 — the ``workflow_state`` column next to the controller's own status indicator."""
	field = frappe.get_meta(doctype).get_field(STATE_FIELD)
	if field is None or cint(field.in_list_view):
		return
	custom = frappe.db.get_value("Custom Field", {"dt": doctype, "fieldname": STATE_FIELD})
	if custom:
		frappe.db.set_value("Custom Field", custom, "in_list_view", 1)
		frappe.clear_cache(doctype=doctype)
	else:
		_set_property(doctype, STATE_FIELD, "in_list_view", "1", "Check")


def sync_workflows(m: Matrix) -> None:
	wanted = [
		build_workflow(m, code, doctype)
		for code, wf in m.workflows.items()
		for doctype in wf["doctypes"]
		if frappe.db.exists("DocType", doctype)
	]
	_ensure_masters(
		"Workflow State", "workflow_state_name", {s["state"] for w in wanted for s in w["states"]}
	)
	_ensure_masters(
		"Workflow Action Master",
		"workflow_action_name",
		{t["action"] for w in wanted for t in w["transitions"]},
	)
	for workflow in wanted:
		if _differs(workflow):
			_save(workflow)
	for doctype in dict.fromkeys(w["document_type"] for w in wanted):
		_show_in_list_view(doctype)
