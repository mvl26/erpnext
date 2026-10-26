"""Go-live cutover (spec 12 Bước 4 and Bước 6, 9.4) — one-time, idempotent, dry-run by default.

    bench --site <site> execute erpnext.access.permissions.cutover.run --kwargs "{'dry_run': 0}"

Order: legacy workflows → ``workflow_state`` remap of existing documents → retire legacy roles, User Type and
Role Profiles. Run it after every user has an ``RP-*`` Role Profile (Bước 6.2): an old profile still held by a
user is kept. Each step returns human-readable lines; ``dry_run=1`` performs no write at all.

Writes are plain SQL / ``set_value`` — never ``doc.save`` — so no guard, email or workflow fires during cutover.
"""

import frappe
from frappe.utils import cint

from erpnext.access.permissions.matrix import Matrix, load_matrix

# 9.4 — "MVL Duyệt thanh toán" is switched off, "SO Test Workflow" deleted; "Cong Tac Approval" is edited in
# place by the sync, so cutover leaves Business Trip alone (WF-BT).
DISABLE_WORKFLOWS = ("MVL Duyệt thanh toán",)
DELETE_WORKFLOWS = ("SO Test Workflow",)
UNMANAGED_CODES = ("WF-BT",)

STATE_FIELD = "workflow_state"
CANCELLED = "Đã hủy"
APPROVED = "Đã duyệt"
# Documents whose own ``status`` decides the state (spec 12 Bước 4.3). Open/Draft keep the workflow default.
STATUS_MAP = {"Approved": APPROVED, "Rejected": "Từ chối"}
STATUS_MAPPED_DOCTYPES = ("Leave Application", "Shift Request")

OLD_ERP_PROFILES = ("Inventory", "Manufacturing", "Accounts", "Sales", "Purchase", "HR")
ESS_USER_TYPE = "Employee Self Service"


def run(dry_run: int = 1, approved_bank_accounts: list[str] | None = None) -> list[str]:
	"""Run every cutover step; returns what was done (or, with ``dry_run``, what would be done)."""
	dry = bool(cint(dry_run))
	lines = [
		*retire_workflows(dry),
		*remap_workflow_states(dry, approved_bank_accounts),
		*retire_legacy(dry),
	]
	if not dry and lines:
		frappe.clear_cache()
	return lines or ["Không có việc cần làm."]


def _say(dry: bool, text: str) -> str:
	return f"{'[dry-run] ' if dry else 'done: '}{text}"


# -- step 1: legacy workflows ---------------------------------------------------------------------


def retire_workflows(dry: bool, disable: tuple = DISABLE_WORKFLOWS, delete: tuple = DELETE_WORKFLOWS):
	lines = []
	for name in disable:
		active = frappe.db.get_value("Workflow", name, ["is_active", "document_type"], as_dict=True)
		if not active or not cint(active.is_active):
			continue
		if not dry:
			frappe.db.set_value("Workflow", name, "is_active", 0)
			_clear_workflow_cache(active.document_type)
		lines.append(_say(dry, f"tắt workflow '{name}' ({active.document_type})"))
	for name in delete:
		doctype = frappe.db.get_value("Workflow", name, "document_type")
		if not doctype:
			continue
		if not dry:
			frappe.delete_doc("Workflow", name, force=1, ignore_permissions=True)
			_clear_workflow_cache(doctype)
		lines.append(_say(dry, f"xóa workflow '{name}' ({doctype})"))
	return lines


def _clear_workflow_cache(doctype: str) -> None:
	frappe.cache.hdel("workflow", doctype)


# -- step 2: workflow_state of existing documents -------------------------------------------------


def default_targets(m: Matrix | None = None) -> dict[str, dict]:
	"""Per managed DocType: the first doc_status-1 state, the cancel state and the status→state map."""
	m = m or load_matrix()
	targets: dict[str, dict] = {}
	for code, wf in m.workflows.items():
		if code in UNMANAGED_CODES:
			continue
		states = wf["states"]
		first = next((s["state"] for s in states if int(s["doc_status"]) == 1), None)
		cancelled = CANCELLED if any(s["state"] == CANCELLED for s in states) else None
		for doctype in wf["doctypes"]:
			mapped = doctype in STATUS_MAPPED_DOCTYPES
			targets[doctype] = {
				"first": first,
				"cancelled": cancelled,
				"status_field": "status" if mapped else None,
				"status_map": dict(STATUS_MAP) if mapped else {},
			}
	return targets


def remap_workflow_states(
	dry: bool, approved_bank_accounts: list[str] | None = None, targets: dict[str, dict] | None = None
):
	lines = []
	for doctype, spec in (default_targets() if targets is None else targets).items():
		if not frappe.db.exists("DocType", doctype) or not frappe.db.table_exists(doctype):
			continue
		if not frappe.db.has_column(doctype, STATE_FIELD):
			lines.append(f"skip: {doctype} chưa có cột {STATE_FIELD}")
			continue
		lines.extend(_remap_doctype(dry, doctype, spec))
	lines.extend(_approve_bank_accounts(dry, approved_bank_accounts))
	return lines


def _remap_doctype(dry: bool, doctype: str, spec: dict) -> list[str]:
	field = spec.get("status_field")
	steps = []  # (description, where, params, state)
	mapped = {}
	if field and frappe.db.has_column(doctype, field):
		mapped = spec.get("status_map") or {}
		for value, state in mapped.items():
			steps.append(
				(
					f"{field} = {value}",
					f"`docstatus` = 1 and `{field}` = %s and ifnull(`{STATE_FIELD}`, '') != %s",
					[value, state],
					state,
				)
			)
	if spec.get("cancelled"):
		state = spec["cancelled"]
		steps.append(
			("docstatus 2", f"`docstatus` = 2 and ifnull(`{STATE_FIELD}`, '') != %s", [state], state)
		)
	if spec.get("first"):
		where = f"`docstatus` = 1 and ifnull(`{STATE_FIELD}`, '') = ''"
		params = []
		if mapped:
			where += f" and ifnull(`{field}`, '') not in ({', '.join(['%s'] * len(mapped))})"
			params = list(mapped)
		steps.append(("docstatus 1 chưa có state", where, params, spec["first"]))

	lines = []
	for description, where, params, state in steps:
		count = frappe.db.sql(f"select count(*) from `tab{doctype}` where {where}", params)[0][0]
		if not count:
			continue
		if not dry:
			frappe.db.sql(f"update `tab{doctype}` set `{STATE_FIELD}` = %s where {where}", [state, *params])
		lines.append(_say(dry, f"{doctype}: {count} chứng từ ({description}) → '{state}'"))
	return lines


def _approve_bank_accounts(dry: bool, names: list[str] | None) -> list[str]:
	if not frappe.db.exists("DocType", "Bank Account") or not frappe.db.has_column(
		"Bank Account", STATE_FIELD
	):
		return []
	if not names:
		pending = frappe.db.count("Bank Account", {STATE_FIELD: ("!=", APPROVED)})
		return (
			[f"note: {pending} Bank Account chưa duyệt, chưa truyền approved_bank_accounts"]
			if pending
			else []
		)
	lines = []
	for name in dict.fromkeys(names):
		state = frappe.db.get_value("Bank Account", name, STATE_FIELD)
		if not frappe.db.exists("Bank Account", name):
			lines.append(f"skip: Bank Account {name} không tồn tại")
		elif state != APPROVED:
			if not dry:
				frappe.db.set_value("Bank Account", name, STATE_FIELD, APPROVED, update_modified=False)
			lines.append(_say(dry, f"Bank Account {name} → '{APPROVED}'"))
	return lines


# -- step 3: retire roles, User Type, Role Profiles -----------------------------------------------


def retire_legacy(
	dry: bool,
	roles: list[str] | None = None,
	profiles: list[str] | None = None,
	user_type: str | None = ESS_USER_TYPE,
):
	if roles is None:
		roles = list(load_matrix().rules.get("retired_roles", ()))
	if profiles is None:
		from erpnext.regional.vietnam.role_profiles import VN_ROLE_PROFILES

		profiles = [*OLD_ERP_PROFILES, *VN_ROLE_PROFILES]
	return [*_drop_user_type(dry, user_type), *_retire_roles(dry, roles), *_drop_profiles(dry, profiles)]


def _drop_user_type(dry: bool, user_type: str | None) -> list[str]:
	if not user_type or not frappe.db.exists("User Type", user_type):
		return []
	holders = frappe.db.count("User", {"user_type": user_type})
	if holders:
		return [f"skip: User Type {user_type} còn {holders} user"]
	if not dry:
		frappe.delete_doc("User Type", user_type, force=1, ignore_permissions=True)
	return [_say(dry, f"xóa User Type '{user_type}'")]


def _retire_roles(dry: bool, roles: list[str]) -> list[str]:
	lines = []
	for role in roles:
		disabled = frappe.db.get_value("Role", role, "disabled")
		if disabled is None:
			continue
		users = frappe.db.sql(
			"select count(distinct parent) from `tabHas Role` where parenttype = 'User' and role = %s", role
		)[0][0]
		if users:
			if not dry:
				frappe.db.delete("Has Role", {"parenttype": "User", "role": role})
			lines.append(_say(dry, f"gỡ role '{role}' khỏi {users} user"))
		if not cint(disabled):
			if not dry:
				frappe.db.set_value("Role", role, "disabled", 1)
			lines.append(_say(dry, f"tắt role '{role}'"))
	return lines


def _drop_profiles(dry: bool, profiles: list[str]) -> list[str]:
	lines = []
	for profile in profiles:
		if not frappe.db.exists("Role Profile", profile):
			continue
		holders = frappe.db.count("User", {"role_profile_name": profile})
		if holders:
			lines.append(f"skip: {profile} còn user")
			continue
		if not dry:
			frappe.delete_doc("Role Profile", profile, force=1, ignore_permissions=True)
		lines.append(_say(dry, f"xóa Role Profile '{profile}'"))
	return lines
