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


def get_allowed_companies():
	"""Công ty được dùng Mạng nội bộ: site_config `gameplan_companies`, mặc định là Company mặc định."""
	configured = frappe.conf.get("gameplan_companies")
	if configured:
		return list(configured)
	default = frappe.defaults.get_global_default("company")
	return [default] if default else []


def get_user_company(user):
	"""Công ty của nhân viên đang làm việc gắn với tài khoản (nếu có module HR)."""
	if not user or not doctype_exists("Employee"):
		return None
	return frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "company")


def is_company_user(user):
	"""Tài khoản thuộc nhân viên đang làm việc của công ty được phép dùng Mạng nội bộ."""
	if user == "Administrator" or not doctype_exists("Employee"):
		return True
	company = get_user_company(user)
	if not company:
		return False
	allowed = get_allowed_companies()
	return not allowed or company in allowed


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
