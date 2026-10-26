"""H4 — audit e-mail to the Operations Director when permissions change (spec 11.3 H4; plan R-7).

Every change to User roles/profile/enabled, Has Role, Role Profile, Custom DocPerm, Custom Role, User Permission,
Workflow or MVL Approval Limits sends one mail. During ``sync.run`` (``frappe.flags.in_rbac_sync``) nothing is sent
per document: ``send_sync_summary`` sends a single mail at the end instead.

Has Role is a child table, so its ``doc_events`` do NOT fire when a User's roles change (the parent writes the
child rows). Role changes are therefore detected in the User hook by comparing the roles before and after the
save; the Has Role registration only catches a direct Has Role insert (rare).
R-GATE: returns at once while ``mvl_rbac_enabled`` is off.
"""

import frappe
from frappe.utils import escape_html, now_datetime

from erpnext.access.permissions.sync import is_enabled

RECIPIENT_PROFILE = "RP-BGD-GDVH"
SUBJECT_PREFIX = "[Miyano ERP] Thay đổi phân quyền"


def recipients() -> list[str]:
	"""Enabled users holding the Operations Director profile; empty means no mail and no error."""
	return frappe.get_all(
		"User", filters={"enabled": 1, "role_profile_name": RECIPIENT_PROFILE}, pluck="name"
	)


def _roles(doc) -> set[str]:
	return {row.role for row in (doc.get("roles") or [])}


def _user_changes(doc) -> list[str]:
	"""Human-readable list of the audited changes on a User; empty when none of them changed."""
	before = doc.get_doc_before_save()
	old_roles = _roles(before) if before else set()
	old_profile = before.get("role_profile_name") if before else None
	old_enabled = before.get("enabled") if before else None
	changes = []
	added, removed = sorted(_roles(doc) - old_roles), sorted(old_roles - _roles(doc))
	if added:
		changes.append("Vai trò thêm: " + ", ".join(added))
	if removed:
		changes.append("Vai trò bớt: " + ", ".join(removed))
	if (doc.get("role_profile_name") or None) != (old_profile or None):
		changes.append(
			f"Role Profile: {old_profile or '(trống)'} → {doc.get('role_profile_name') or '(trống)'}"
		)
	if before and bool(doc.get("enabled")) != bool(old_enabled):
		changes.append(f"Kích hoạt: {old_enabled} → {doc.get('enabled')}")
	return changes


def _send(subject: str, lines: list[str]) -> None:
	to = recipients()
	if not to:
		return
	body = "<br>".join(escape_html(line) for line in lines)
	frappe.sendmail(recipients=to, subject=subject, message=body, now=False)


def _event_label(doc, method) -> str:
	if method == "on_trash":
		return "xóa"
	return "tạo" if doc.flags.get("in_insert") or not doc.get_doc_before_save() else "sửa"


def on_change(doc, method=None) -> None:
	"""Single hook for every audited DocType; ``method`` is the event name and goes into the mail."""
	if not is_enabled() or frappe.flags.get("in_rbac_sync"):
		return
	lines = [
		f"Người thực hiện: {frappe.session.user}",
		f"Đối tượng: {doc.doctype} {doc.name}",
		f"Sự kiện: {_event_label(doc, method)} ({method or ''})",
		f"Thời điểm: {now_datetime()}",
	]
	if doc.doctype == "User":
		changes = _user_changes(doc)
		if not changes:
			return
		lines += changes
	_send(f"{SUBJECT_PREFIX}: {doc.doctype} {doc.name}", lines)


def send_sync_summary(counter) -> None:
	"""One mail per sync, only when it inserted or deleted something."""
	if not is_enabled():
		return
	if (counter.get("inserted") or 0) + (counter.get("deleted") or 0) <= 0:
		return
	lines = [
		f"Người thực hiện: {frappe.session.user}",
		f"Thời điểm: {now_datetime()}",
		"Kết quả đồng bộ phân quyền:",
	]
	lines += [f"{key}: {value}" for key, value in sorted(counter.items())]
	_send(f"{SUBJECT_PREFIX}: đồng bộ ma trận", lines)
