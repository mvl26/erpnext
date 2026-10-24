import frappe

ADMIN_ROLES = {"System Manager", "Gameplan Admin"}


def is_admin(user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return bool(ADMIN_ROLES.intersection(frappe.get_roles(user)))


def doctype_exists(doctype):
	return bool(frappe.db.exists("DocType", doctype))


def get_user_department(user):
	"""Phòng ban của nhân viên đang làm việc gắn với tài khoản (nếu có module HR)."""
	if not user or not doctype_exists("Employee"):
		return None
	return frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "department")


def get_active_member_users():
	"""Danh sách tài khoản đang có quyền dùng Mạng nội bộ (thành viên/quản trị)."""
	HasRole = frappe.qb.DocType("Has Role")
	User = frappe.qb.DocType("User")
	rows = (
		frappe.qb.from_(HasRole)
		.join(User)
		.on(User.name == HasRole.parent)
		.select(HasRole.parent)
		.distinct()
		.where(HasRole.parenttype == "User")
		.where(HasRole.role.isin(["Gameplan Member", "Gameplan Admin"]))
		.where(User.enabled == 1)
		.where(User.name.notin(["Administrator", "Guest"]))
		.run(pluck=True)
	)
	return list(rows)
