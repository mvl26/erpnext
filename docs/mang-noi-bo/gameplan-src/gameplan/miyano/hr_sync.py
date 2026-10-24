"""Đồng bộ nhân sự từ module HR (Employee) sang Mạng nội bộ.

- Nhân viên Active có tài khoản ERP (user_id) -> được cấp vai trò "Gameplan Member",
  có hồ sơ GP User Profile và là thành viên Không gian mặc định.
- Nhân viên nghỉ việc (Left/Inactive) -> bị gỡ vai trò Gameplan Member và khỏi Không gian mặc định.
"""

import frappe

from gameplan.miyano.utils import doctype_exists, is_company_user

MEMBER_ROLE = "Gameplan Member"
DEFAULT_TEAM_KEY = "miyano_default_team"


def get_default_team():
	team = frappe.db.get_default(DEFAULT_TEAM_KEY)
	if team and frappe.db.exists("GP Team", team):
		return team
	return None


def set_default_team(team):
	frappe.db.set_default(DEFAULT_TEAM_KEY, team)


def ensure_member(user):
	if not user or user in ("Administrator", "Guest") or not frappe.db.exists("User", user):
		return False
	changed = False
	user_doc = frappe.get_doc("User", user)
	if not user_doc.enabled:
		return False
	if not is_company_user(user):
		# Nhân viên công ty khác (hoặc không phải nhân viên đang làm việc): không cho vào Mạng nội bộ
		remove_member(user)
		return False
	roles = {r.role for r in user_doc.roles}
	if MEMBER_ROLE not in roles and "Gameplan Admin" not in roles:
		user_doc.add_roles(MEMBER_ROLE)
		changed = True

	from gameplan.gameplan.doctype.gp_user_profile.gp_user_profile import create_user_profile

	create_user_profile(user_doc)

	team = get_default_team()
	if team:
		team_doc = frappe.get_doc("GP Team", team)
		if user not in [m.user for m in team_doc.members]:
			team_doc.append("members", {"user": user})
			team_doc.flags.ignore_permissions = True
			team_doc.save()
			changed = True
	return changed


def remove_member(user):
	if not user or not frappe.db.exists("User", user):
		return False
	changed = False
	user_doc = frappe.get_doc("User", user)
	if MEMBER_ROLE in {r.role for r in user_doc.roles}:
		user_doc.remove_roles(MEMBER_ROLE)
		changed = True
	team = get_default_team()
	if team:
		team_doc = frappe.get_doc("GP Team", team)
		rows = [m for m in team_doc.members if m.user == user]
		for row in rows:
			team_doc.remove(row)
		if rows:
			team_doc.flags.ignore_permissions = True
			team_doc.save()
			changed = True
	return changed


def on_employee_update(doc, method=None):
	"""Hook Employee.on_update / after_insert."""
	try:
		before = doc.get_doc_before_save()
		if before and before.user_id and before.user_id != doc.user_id:
			remove_member(before.user_id)
		if doc.status == "Active" and doc.user_id:
			ensure_member(doc.user_id)
		elif doc.user_id:
			remove_member(doc.user_id)
	except Exception:
		# Không để lỗi đồng bộ chặn việc lưu hồ sơ nhân viên
		frappe.log_error(title="Miyano: lỗi đồng bộ nhân viên sang Mạng nội bộ")


def sync_all():
	"""Chạy hằng ngày (scheduler) hoặc thủ công:
	bench --site <site> execute gameplan.miyano.hr_sync.sync_all
	"""
	if not doctype_exists("Employee"):
		return {"added": 0, "removed": 0, "note": "Không có module HR (Employee)"}
	added, removed = 0, 0
	for e in frappe.get_all(
		"Employee", filters={"user_id": ("is", "set")}, fields=["user_id", "status"]
	):
		if e.status == "Active":
			added += 1 if ensure_member(e.user_id) else 0
		else:
			removed += 1 if remove_member(e.user_id) else 0
	frappe.db.commit()
	return {"added": added, "removed": removed}
