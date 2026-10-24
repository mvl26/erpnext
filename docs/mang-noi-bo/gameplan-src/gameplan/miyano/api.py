import frappe

from gameplan.miyano.permissions import can_create_group, can_post
from gameplan.miyano.utils import is_admin


@frappe.whitelist()
def get_post_permissions():
	"""Quyền đăng bài của người dùng hiện tại: {is_admin, projects: {project: True/False}}."""
	projects = frappe.get_list("GP Project", pluck="name", limit_page_length=0)
	return {
		"is_admin": is_admin(),
		"can_create_group": can_create_group(),
		"projects": {str(p): can_post(p) for p in projects},
	}
