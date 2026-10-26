"""H9 — share a record with the user it is assigned to — spec 11.3 H9, plan R-6.

frappe's Assign To shares *read* only, and only when the assignee lacks access. For a Task the assignee must also
write, so H9 adds the share itself. Removing an assignment in the UI sets the ToDo to ``Cancelled`` (it does not
delete), so unsharing runs on ``on_update`` as well as ``on_trash``.

frappe shares carry no origin marker. H9 therefore unshares only a share that looks exactly like its own (read, plus
write for a Task, never submit/share/everyone), never from the record's owner, and never while another Open ToDo
of the same user on the same record remains. A share added by hand with those same flags is indistinguishable and
is also removed when the assignment ends — accepted.
A share is added only when the ToDo's ``owner`` (set by frappe, unlike the client-settable ``assigned_by``) may
write the Task / read the other records — frappe's ToDo permission lets anyone insert a ToDo allocated to
themselves, which must not become a share of a record they cannot see. When ``on_update`` repoints the ToDo
(reference or assignee changed) or reopens it (Cancelled / Closed → Open), the user making that change must hold
the same right as well: the assignee may edit their own ToDo and would otherwise borrow the assigner's access for
any other record, or win back a share that ended with the assignment.
R-GATE: returns at once while ``mvl_rbac_enabled`` is off.
"""

import frappe

from erpnext.access.permissions.sync import is_enabled

SHARE_WRITE = {"Task"}
SHARE_READ = {"Job Applicant", "Interview", "Training Program", "Training Event"}


def _share(doctype: str, name: str, user: str) -> dict | None:
	return frappe.db.get_value(
		"DocShare",
		{"share_doctype": doctype, "share_name": name, "user": user},
		["read", "write", "submit", "share", "everyone"],
		as_dict=True,
	)


def _add(doctype: str, name: str, user: str) -> None:
	write = int(doctype in SHARE_WRITE)
	if not frappe.db.exists(doctype, name) or not frappe.db.exists("User", user):
		return
	current = _share(doctype, name, user)
	if current and current.read and current.write >= write:
		return  # never downgrade a wider share
	frappe.share.add_docshare(
		doctype, name, user, read=1, write=write, notify=0, flags={"ignore_share_permission": True}
	)


def _remove(doctype: str, name: str, user: str, exclude_todo: str | None) -> None:
	if frappe.db.exists(
		"ToDo",
		{
			"reference_type": doctype,
			"reference_name": name,
			"allocated_to": user,
			"status": "Open",
			"name": ("!=", exclude_todo or ""),
		},
	):
		return
	current = _share(doctype, name, user)
	if not current or current.submit or current.share or current.everyone:
		return
	if current.write != int(doctype in SHARE_WRITE):
		return
	if frappe.db.get_value(doctype, name, "owner") == user:
		return
	frappe.share.remove(
		doctype, name, user, flags={"ignore_permissions": True, "ignore_share_permission": True}
	)


def _shareable(reference_type, reference_name, allocated_to) -> bool:
	return bool(reference_type in SHARE_WRITE | SHARE_READ and reference_name and allocated_to)


def _may_grant(doctype: str, name: str, user: str | None) -> bool:
	"""True when ``user`` holds the right H9 would hand out (write for a Task, read otherwise)."""
	if not user or not frappe.db.exists(doctype, name):
		return False
	ptype = "write" if doctype in SHARE_WRITE else "read"
	return bool(frappe.has_permission(doctype, ptype, doc=name, user=user))


def on_todo_change(doc, method=None) -> None:
	"""``ToDo`` ``after_insert`` / ``on_update`` / ``on_trash``: share while Open, unshare when it ends.

	When ``on_update`` changes the reference or the assignee of a ToDo that was Open, the previous assignee's share
	goes first (same rules), otherwise it would outlive the assignment.
	"""
	if not is_enabled():
		return
	repointed = reopened = False
	if method == "on_update":
		before = doc.get_doc_before_save()
		if before:
			old = (before.reference_type, before.reference_name, before.allocated_to)
			repointed = old != (doc.reference_type, doc.reference_name, doc.allocated_to)
			reopened = before.status != "Open"
			if before.status == "Open" and repointed and _shareable(*old):
				_remove(*old, doc.name)
	if not _shareable(doc.reference_type, doc.reference_name, doc.allocated_to):
		return
	if method != "on_trash" and doc.status == "Open":
		if not _may_grant(doc.reference_type, doc.reference_name, doc.owner):
			return
		if (repointed or reopened) and not _may_grant(
			doc.reference_type, doc.reference_name, frappe.session.user
		):
			return
		_add(doc.reference_type, doc.reference_name, doc.allocated_to)
	else:
		_remove(doc.reference_type, doc.reference_name, doc.allocated_to, doc.name)
