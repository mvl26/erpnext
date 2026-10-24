"""Thông báo bài mới và gửi email cho Mạng nội bộ."""

import frappe
from frappe.core.utils import html2text
from frappe.utils import escape_html, get_fullname, get_url

from gameplan.miyano.utils import get_active_member_users


def discussion_url(discussion):
	d = frappe.db.get_value("GP Discussion", discussion, ["team", "project", "name"], as_dict=True)
	if not d:
		return get_url("/g")
	return get_url(f"/g/{d.team}/projects/{d.project}/discussion/{d.name}")


def on_new_discussion(doc, method=None):
	"""Hook GP Discussion.after_insert: báo chuông (và email nếu bật) khi có bài mới."""
	if frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_import:
		return
	project = frappe.db.get_value(
		"GP Project",
		doc.project,
		["title", "miyano_notify_all", "miyano_email_new_post"],
		as_dict=True,
	)
	if not project:
		return
	if project.miyano_notify_all:
		recipients = get_active_member_users()
	else:
		recipients = frappe.get_all("GP Followed Project", filters={"project": doc.project}, pluck="user")

	author = doc.owner or frappe.session.user
	author_name = get_fullname(author)
	message = f"{author_name} đã đăng bài mới trong nhóm {project.title}: “{doc.title}”"
	for user in set(recipients):
		if not user or user == author:
			continue
		n = frappe.get_doc(
			doctype="GP Notification",
			type="New Post",
			from_user=author,
			to_user=user,
			discussion=doc.name,
			project=doc.project,
			team=doc.team,
			message=message,
		)
		n.flags.miyano_send_email = bool(project.miyano_email_new_post)
		n.insert(ignore_permissions=True)


def send_notification_email(doc, method=None):
	"""Hook GP Notification.after_insert: gửi email khi được nhắc tên hoặc có bài mới (nếu nhóm bật)."""
	if frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_import:
		return
	if doc.type == "Mention":
		pass
	elif doc.type == "New Post" and doc.flags.get("miyano_send_email"):
		pass
	else:
		return
	if not doc.to_user or not frappe.db.get_value("User", doc.to_user, "enabled"):
		return

	from_name = get_fullname(doc.from_user) if doc.from_user else "Mạng nội bộ"
	link = discussion_url(doc.discussion) if doc.discussion else get_url("/g/notifications")

	excerpt = ""
	if doc.comment:
		excerpt = frappe.db.get_value("GP Comment", doc.comment, "content") or ""
	elif doc.discussion:
		excerpt = frappe.db.get_value("GP Discussion", doc.discussion, "content") or ""
	excerpt = html2text(excerpt or "").strip()
	if len(excerpt) > 400:
		excerpt = excerpt[:400].rsplit(" ", 1)[0] + "…"

	if doc.type == "Mention":
		subject = f"[Mạng nội bộ] {from_name} đã nhắc đến bạn"
		heading = f"{escape_html(from_name)} đã nhắc đến bạn"
	else:
		title = frappe.db.get_value("GP Discussion", doc.discussion, "title") if doc.discussion else ""
		project_title = frappe.db.get_value("GP Project", doc.project, "title") if doc.project else ""
		subject = f"[Mạng nội bộ] Bài mới trong nhóm {project_title}: {title}"
		heading = escape_html(doc.message or subject)

	body = f"""
<div style="font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:0 auto;border:1px solid #e3e6ea;border-radius:6px;overflow:hidden">
  <div style="background:#1f4e79;color:#fff;padding:12px 20px;font-size:13px">MẠNG NỘI BỘ MIYANO</div>
  <div style="padding:20px">
    <h3 style="margin:0 0 12px;font-size:17px;color:#1d2125">{heading}</h3>
    <div style="font-size:14px;line-height:1.6;color:#374151;white-space:pre-line;border-left:3px solid #e3e6ea;padding-left:12px">{escape_html(excerpt)}</div>
    <div style="margin-top:20px"><a href="{link}" style="background:#1f4e79;color:#fff;text-decoration:none;padding:9px 16px;border-radius:4px;font-size:13px">Xem và trả lời</a></div>
  </div>
  <div style="background:#f6f7f9;color:#8a9099;font-size:11px;padding:10px 20px">Email tự động từ Mạng nội bộ Miyano.</div>
</div>"""
	try:
		_send(doc, subject, body)
	except Exception:
		# Không để lỗi email (chưa cấu hình hộp thư gửi...) chặn việc đăng bài/bình luận
		frappe.log_error(title="Miyano: lỗi gửi email Mạng nội bộ")


def _send(doc, subject, body):
	frappe.sendmail(
		recipients=[doc.to_user],
		subject=subject,
		message=body,
		reference_doctype="GP Notification",
		reference_name=doc.name,
		add_unsubscribe_link=0,
	)
