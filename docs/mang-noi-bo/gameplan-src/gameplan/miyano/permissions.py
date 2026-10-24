import frappe
from frappe import _

from gameplan.miyano import utils
from gameplan.miyano.utils import get_user_department, is_admin

# Phòng ban được tạo nhóm: HCNS và Ban lãnh đạo. Người khác do quản trị viên cấp vai trò CREATOR_ROLE.
GROUP_CREATOR_DEPARTMENTS = ("P. HCNS - pháp chế - M", "Ban lãnh đạo - M")
CREATOR_ROLE = "Gameplan Group Creator"

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


def can_create_group(user=None):
	"""Người dùng có được tạo nhóm / không gian mới không: quản trị, HCNS, Ban lãnh đạo hoặc
	người được quản trị viên cấp vai trò Gameplan Group Creator."""
	user = user or frappe.session.user
	if utils.is_admin(user):
		return True
	if CREATOR_ROLE in frappe.get_roles(user):
		return True
	department = utils.get_user_department(user)
	return bool(department and department in GROUP_CREATOR_DEPARTMENTS)


def validate_new_group(doc, method=None):
	"""Hook GP Project / GP Team.before_insert: chỉ người có quyền mới được tạo nhóm, không gian."""
	if frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_import:
		return
	if not can_create_group(doc.owner or frappe.session.user):
		frappe.throw(
			_(
				"Bạn chưa có quyền tạo nhóm. Chỉ quản trị viên, phòng HCNS, Ban lãnh đạo hoặc người được "
				"quản trị viên cấp quyền mới tạo được nhóm."
			),
			frappe.PermissionError,
		)


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
