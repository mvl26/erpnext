"""Role / Role Profile hygiene — runs on every ``bench migrate``, with or without ``mvl_rbac_enabled``.

    bench --site <site> execute erpnext.access.permissions.cleanup.run              # dry-run: prints only
    bench --site <site> execute erpnext.access.permissions.cleanup.run --kwargs "{'dry_run': 0}"

Removes only what is dead — nothing grants a right through it and no installed app recreates it:

1. ``DEAD_WORKFLOWS`` — test leftovers, while no document carries one of their states;
2. ``DEAD_ROLES`` — roles of apps that are not installed on the site, test leftovers, and the ERPNext
   ``Analytics`` role (created once by ``setup.install.after_install``, used nowhere). Users holding one lose it:
   the role grants nothing, which the link check below proves before anything is deleted;
3. RBAC-owned names the matrix no longer lists — ``MVL *`` roles and ``RP-*`` Role Profiles (combined ones
   included) — and the retired ERPNext / VN department profiles of the old model (``cutover.OLD_ERP_PROFILES``,
   ``VN_ROLE_PROFILES``). Never taken from a user: a profile or role still held is kept;
4. Role Profiles named with the test prefix ``ZZ-AC-`` (assetcore stand-ins of the RBAC tests);
5. test Users — e-mail on a reserved test domain (``TEST_EMAIL_DOMAINS``, RFC 2606 / 6761 or the apps' test
   domains; a real address never ends so) — with the Contact frappe made for each, and the Contacts such Users
   left behind (frappe only unlinks a Contact when its User is deleted). A Contact linked to a party is kept.

Every delete runs frappe's link checks and then ``frappe.delete_doc`` without ``force`` (kept in Deleted Document,
so it can be restored): nothing is removed while any Link field on the site still points at the record (DocPerm, Custom DocPerm, Workflow, Notification, Report / Page / Workspace roles,
Role Profile, User…). Each record has its own savepoint, so a refused delete leaves it exactly as it was and is
reported as ``skip``. Standard roles of installed apps (``retired_roles``) are not deleted here — a DocType import
recreates them — the cutover disables them instead. Matrix roles and profiles are never touched.
"""

import frappe
from frappe.model.delete_doc import get_dynamic_linked_docs, get_linked_docs
from frappe.utils import cint, strip_html

from erpnext.access.permissions.matrix import Matrix, load_matrix

DEAD_WORKFLOWS = ("SO Test Workflow",)  # erpnext test_sales_order, active on Sales Order since 2026-09-08
DEAD_ROLES = (
	# mvl_accounting (parked, not installed)
	"Kế toán trưởng",
	"Kế toán tổng hợp",
	"Kế toán công nợ - ngân hàng",
	"Kế toán kho - ký gửi",
	"Thủ quỹ",
	"Nhân viên mua hàng",
	"Quản lý xem báo cáo",
	# antmed_crm (not installed)
	"NV kinh doanh",
	"Thủ kho",
	"Quản lý",
	# normcore_dmktkt / norm_himedic (not installed)
	"Norm User",
	"Norm Manager",
	"Healthcare Administrator",
	"Laboratory User",
	"Internal Auditor",
	# erpnext test_sales_order (SO Test Workflow)
	"Test Approver",
	"Test Junior Approver",
	# erpnext setup.install.after_install — no permission, report or page uses it
	"Analytics",
)
RBAC_ROLE_PREFIX = "MVL "
RBAC_PROFILE_PREFIX = "RP-"
TEST_PROFILE_PREFIX = "ZZ-AC-"
TEST_EMAIL_DOMAINS = (
	"example.com",
	"example.org",
	"example.net",
	"example.invalid",
	"test.local",
	"assetcore.test",
)
# User.on_trash deletes or unlinks these itself, before frappe checks the links (frappe/core/doctype/user/user.py)
USER_TRASH_HANDLED = frozenset(("Contact", "Notification Settings", "Event"))


def run(dry_run: int = 1) -> list[str]:
	"""Print and return what was (``dry_run=0``) or would be removed."""
	dry = bool(cint(dry_run))
	m = load_matrix()
	lines = [
		*_workflows(dry),
		*_test_users(dry),
		*_dead_roles(dry, m),
		*_stale_rbac_roles(dry, m),
		*_stale_profiles(dry, m),
		*_orphan_test_contacts(dry),
	]
	if not dry and any(line.startswith("done:") for line in lines):
		frappe.clear_cache()
	for line in lines:
		print(f"  Dọn role: {line}")
	return lines


def _say(dry: bool, text: str) -> str:
	return f"{'[dry-run] ' if dry else 'done: '}{text}"


def _links(doc, ignore=frozenset()) -> list[dict]:
	"""frappe's own delete-time link scan (``ignore_links_on_delete`` honoured), minus ``ignore`` DocTypes."""
	found = [*get_linked_docs(doc), *get_dynamic_linked_docs(doc)]
	return [link for link in found if link["reference_doctype"] not in ignore]


def _delete(dry: bool, doctype: str, name: str, before_delete=None, ignore=frozenset()) -> str:
	"""Delete ``name`` unless something still links to it.

	frappe's link scan runs first, so a refusal names the linking record. A dry run stops after it —
	``delete_doc`` queues ``delete_dynamic_links`` for after the commit, which a savepoint rollback would not undo —
	so a record that only becomes free once an earlier step deletes something shows as ``skip`` in the preview.
	``ignore`` lists DocTypes the record's own ``on_trash`` clears before frappe's check.
	"""
	savepoint = f"mvl_cleanup_{frappe.generate_hash(length=8)}"
	frappe.db.savepoint(savepoint)
	try:
		if before_delete:
			before_delete()
		links = _links(frappe.get_doc(doctype, name), ignore)
		if links:
			frappe.db.rollback(save_point=savepoint)
			link = links[0]
			return f"skip: {doctype} '{name}' — còn liên kết với {link['reference_doctype']} {link['reference_docname']}"
		if not dry:
			frappe.delete_doc(doctype, name, ignore_permissions=True)
	except frappe.LinkExistsError as e:
		frappe.db.rollback(save_point=savepoint)
		frappe.clear_messages()
		return f"skip: {doctype} '{name}' — {strip_html(str(e))}"
	if dry:
		frappe.db.rollback(save_point=savepoint)
	return _say(dry, f"xóa {doctype} '{name}'")


# -- workflows ------------------------------------------------------------------------------------


def _workflows(dry: bool) -> list[str]:
	lines = []
	for name in DEAD_WORKFLOWS:
		wf = frappe.db.get_value("Workflow", name, ["document_type", "workflow_state_field"], as_dict=True)
		if not wf:
			continue
		field = wf.workflow_state_field or "workflow_state"
		if frappe.get_meta(wf.document_type).has_field(field) and frappe.db.exists(
			wf.document_type, {field: ("is", "set")}
		):
			lines.append(f"skip: Workflow '{name}' — còn chứng từ {wf.document_type} mang trạng thái của nó")
			continue
		lines.append(_delete(dry, "Workflow", name))
		if not dry and lines[-1].startswith("done:"):
			frappe.cache.hdel("workflow", wf.document_type)
	return lines


# -- roles ----------------------------------------------------------------------------------------


def _matrix_roles(m: Matrix) -> frozenset[str]:
	return frozenset(name for role in m.roles.values() for name in role.names)


def _strip_from_users(role: str):
	return lambda: frappe.db.delete("Has Role", {"parenttype": "User", "role": role})


def _dead_roles(dry: bool, m: Matrix) -> list[str]:
	keep = _matrix_roles(m)
	return [
		_delete(dry, "Role", role, _strip_from_users(role))
		for role in DEAD_ROLES
		if role not in keep and frappe.db.exists("Role", role)
	]


def _stale_rbac_roles(dry: bool, m: Matrix) -> list[str]:
	keep = _matrix_roles(m)
	names = frappe.get_all("Role", filters={"name": ("like", f"{RBAC_ROLE_PREFIX}%")}, pluck="name")
	return [_delete(dry, "Role", role) for role in sorted(names) if role not in keep]


# -- role profiles --------------------------------------------------------------------------------


def wanted_profiles(m: Matrix) -> frozenset[str]:
	"""The ``RP-*`` profiles the sync keeps: matrix profiles plus each combined one (``profiles.py``)."""
	from erpnext.access.permissions.profiles import combined_profile_name

	combined = {combined_profile_name(pair["erp"], pair["assetcore"]) for pair in m.combined_profiles}
	return frozenset(m.role_profiles) | combined


def _stale_profiles(dry: bool, m: Matrix) -> list[str]:
	from erpnext.access.permissions.cutover import OLD_ERP_PROFILES
	from erpnext.regional.vietnam.role_profiles import VN_ROLE_PROFILES

	keep = wanted_profiles(m)
	names = set(frappe.get_all("Role Profile", pluck="name"))
	stale = {
		name
		for name in names
		if (name.startswith(RBAC_PROFILE_PREFIX) and name not in keep) or name.startswith(TEST_PROFILE_PREFIX)
	}
	stale |= names & {*OLD_ERP_PROFILES, *VN_ROLE_PROFILES}
	# combined profiles first: a test stand-in ZZ-AC-x is still named inside RP-…+AC-ZZ-AC-x
	return [_delete(dry, "Role Profile", name) for name in sorted(stale, key=lambda n: ("+AC-" not in n, n))]


# -- test users and their contacts ----------------------------------------------------------------


def is_test_email(email: str | None) -> bool:
	domain = (email or "").rpartition("@")[2].lower()
	return domain in TEST_EMAIL_DOMAINS


def _contact_has_party(contact: str) -> bool:
	return bool(frappe.db.exists("Dynamic Link", {"parenttype": "Contact", "parent": contact}))


def _drop_contact_rows(contact: str) -> None:
	"""Plain deletes of a party-less Contact and its child rows — no ``delete_doc`` (dry runs roll back)."""
	for child in ("Contact Email", "Contact Phone"):
		frappe.db.delete(child, {"parenttype": "Contact", "parent": contact})
	frappe.db.delete("Contact", {"name": contact})


def _drop_own_contacts(user: str):
	def run():
		for contact in frappe.get_all("Contact", filters={"user": user}, pluck="name"):
			if not _contact_has_party(contact):
				_drop_contact_rows(contact)

	return run


def _test_users(dry: bool) -> list[str]:
	users = [u for u in frappe.get_all("User", pluck="name") if is_test_email(u)]
	return [
		_delete(dry, "User", user, _drop_own_contacts(user), ignore=USER_TRASH_HANDLED)
		for user in sorted(users)
	]


def _orphan_test_contacts(dry: bool) -> list[str]:
	"""Contacts of test e-mails whose User is gone, with no party and nothing linking to them — one summary line."""
	rows = frappe.get_all("Contact", fields=["name", "user", "email_id"])
	candidates = [
		row.name
		for row in rows
		if (is_test_email(row.user) or is_test_email(row.email_id))
		and not (row.user and frappe.db.exists("User", row.user))
	]
	removed, kept = 0, []
	for name in candidates:
		if _contact_has_party(name) or _links(frappe.get_doc("Contact", name)):
			kept.append(name)
			continue
		if not dry:
			_drop_contact_rows(name)
		removed += 1
	lines = [_say(dry, f"xóa {removed} Contact của user test đã xóa")] if removed else []
	if kept:
		lines.append(f"skip: {len(kept)} Contact của user test còn liên kết (vd. {kept[0]})")
	return lines
