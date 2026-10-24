import frappe
from frappe import _

from gameplan.miyano.utils import get_user_department, is_admin

MIYANO_PROJECT_FIELDS = (
	"miyano_restrict_posting",
	"miyano_posters",
	"miyano_notify_all",
	"miyano_email_new_post",
)


def can_post(project, user=None):
	"""Người dùng có được đăng bài mới vào nhóm (GP Project) này không."""
	user = user or frappe.session.user
	if not project:
		return True
	if is_admin(user):
		return True
	restrict = frappe.db.get_value("GP Project", project, "miyano_restrict_posting")
	if not restrict:
		return True
	posters = frappe.get_all(
		"GP Project Poster",
		filters={"parent": project, "parenttype": "GP Project"},
		fields=["poster_type", "department", "user"],
	)
	department = get_user_department(user)
	for p in posters:
		if p.user and p.user == user:
			return True
		if p.department and department and p.department == department:
			return True
	return False


def validate_new_discussion(doc, method=None):
	"""Hook GP Discussion.before_insert: chặn đăng bài khi không có quyền."""
	if frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.miyano_skip_post_check:
		return
	if not can_post(doc.project, doc.owner or frappe.session.user):
		title = frappe.db.get_value("GP Project", doc.project, "title") or doc.project
		frappe.throw(
			_("Bạn chưa có quyền đăng bài trong nhóm “{0}”. Bạn vẫn có thể đọc và bình luận.").format(title),
			frappe.PermissionError,
		)


def validate_project(doc, method=None):
	"""Hook GP Project.validate: chỉ quản trị viên được đổi cấu hình quyền đăng & thông báo."""
	if doc.is_new() or is_admin():
		return
	before = doc.get_doc_before_save()
	if not before:
		return
	for field in MIYANO_PROJECT_FIELDS:
		if field == "miyano_posters":
			old = [(r.poster_type, r.department, r.user) for r in before.get(field)]
			new = [(r.poster_type, r.department, r.user) for r in doc.get(field)]
			changed = old != new
		else:
			changed = doc.has_value_changed(field)
		if changed:
			frappe.throw(_("Chỉ quản trị viên mới được thay đổi quyền đăng bài và cài đặt thông báo của nhóm."))
