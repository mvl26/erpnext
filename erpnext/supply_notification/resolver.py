# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Diễn giải cấu hình người nhận thành danh sách người thật.

Nguồn phòng ban là hồ sơ Nhân viên (quyết định D1): `Employee.department` gắn với
`Employee.user_id`, chỉ lấy nhân viên đang làm việc. Site không cài `hrms` thì phần
theo phòng ban trả rỗng — cấu hình theo người đích danh vẫn chạy (NF5).

Từ bản BA_NTF_V4, nguồn người nhận mở rộng thêm: nhóm người nhận, trường Người
dùng trên chứng từ, người bấm gửi, CC/BCC, trả lời về, và bộ lọc "người đã tự
tắt điểm này" (D18).

Tham chiếu: docs/superpowers/specs/2026-09-23-thong-bao-tu-thiet-lap-design.md muc 4.7.
"""

import frappe
from frappe import _
from frappe.utils import split_emails, validate_email_address

#: Hai tài khoản hệ thống không bao giờ là người nhận nghiệp vụ.
SYSTEM_USERS = ("Administrator", "Guest")

SOURCE_DEPARTMENT = "department"
SOURCE_USER = "user"
SOURCE_GROUP = "group"
SOURCE_OWNER = "owner"
SOURCE_DOC_FIELD = "doc_field"
SOURCE_TRIGGER = "trigger"

SOURCE_LABELS = {
	SOURCE_DEPARTMENT: "phòng ban",
	SOURCE_USER: "đích danh",
	SOURCE_GROUP: "nhóm",
	SOURCE_OWNER: "người tạo chứng từ",
	SOURCE_DOC_FIELD: "trường trên chứng từ",
	SOURCE_TRIGGER: "người bấm gửi",
}

OPT_OUT_DOCTYPE = "Supply Notification Opt Out"


# --- Phòng ban -----------------------------------------------------------


def expand_departments(names: list[str]) -> set[str]:
	"""Trả phòng ban đã chọn cộng mọi phòng con, bỏ phòng đang tắt.

	`Department` là DocType dạng cây; chọn một phòng nhóm phải bao được cả nhánh
	dưới, nếu không thì gán nhân viên vào phòng con là thông báo im lặng biến mất.
	"""
	names = [n for n in (names or []) if n]
	if not names:
		return set()

	rows = frappe.get_all(
		"Department",
		filters={"name": ("in", names)},
		fields=["name", "lft", "rgt", "is_group"],
	)

	resolved: set[str] = set()
	for row in rows:
		if row.is_group and row.lft is not None and row.rgt is not None:
			resolved.update(
				frappe.get_all(
					"Department",
					filters={"lft": (">=", row.lft), "rgt": ("<=", row.rgt)},
					pluck="name",
				)
			)
		else:
			resolved.add(row.name)

	if not resolved:
		return set()

	return set(
		frappe.get_all(
			"Department",
			filters={"name": ("in", list(resolved)), "disabled": 0},
			pluck="name",
		)
	)


def users_in_departments(names: list[str]) -> set[str]:
	"""Trả tài khoản của nhân viên đang làm việc thuộc các phòng ban đã cho."""
	departments = expand_departments(names)
	if not departments or not frappe.db.exists("DocType", "Employee"):
		return set()

	rows = frappe.get_all(
		"Employee",
		filters={
			"department": ("in", list(departments)),
			"status": "Active",
			"user_id": ("is", "set"),
		},
		pluck="user_id",
	)
	return {u for u in rows if u}


def employees_without_user(names: list[str]) -> list[str]:
	"""Nhân viên đang làm việc thuộc phòng ban nhưng chưa gắn tài khoản.

	Dùng cho cảnh báo khi xem trước: đây là lý do phổ biến nhất khiến một phòng
	ban "có người" nhưng không ai nhận được thông báo.
	"""
	departments = expand_departments(names)
	if not departments or not frappe.db.exists("DocType", "Employee"):
		return []

	return frappe.get_all(
		"Employee",
		filters={
			"department": ("in", list(departments)),
			"status": "Active",
			"user_id": ("is", "not set"),
		},
		pluck="employee_name",
	)


# --- Nhóm người nhận ------------------------------------------------------


def group_names(rows) -> list[str]:
	return [row.group for row in (rows or []) if row.group]


def users_in_groups(names: list[str]) -> set[str]:
	users: set[str] = set()
	for name in names:
		if not frappe.db.exists("Supply Notification Recipient Group", name):
			continue
		group = frappe.get_cached_doc("Supply Notification Recipient Group", name)
		if group.disabled:
			continue
		users |= users_in_departments([row.department for row in (group.departments or [])])
		users |= {row.user for row in (group.users or []) if row.user}
	return users


def emails_in_groups(names: list[str]) -> list[str]:
	emails: list[str] = []
	for name in names:
		if not frappe.db.exists("Supply Notification Recipient Group", name):
			continue
		group = frappe.get_cached_doc("Supply Notification Recipient Group", name)
		if group.disabled:
			continue
		emails.extend(split_emails(group.fixed_emails or ""))
	return emails


def describe_group(group) -> dict:
	"""Thành viên thực tế của một nhóm — cho nút *Xem thành viên thực tế*."""
	users = users_in_departments([row.department for row in (group.departments or [])])
	users |= {row.user for row in (group.users or []) if row.user}

	return {
		"recipients": [dict(row) for row in filter_valid(users)],
		"fixed_emails": split_emails(group.fixed_emails or ""),
		"warnings": [
			_("{0} nhân viên chưa gắn tài khoản nên không nhận được: {1}").format(
				len(missing), ", ".join(missing[:10])
			)
			for missing in [employees_without_user([row.department for row in (group.departments or [])])]
			if missing
		],
	}


# --- Lọc -----------------------------------------------------------------


def opted_out_users(point: str) -> set[str]:
	if not point:
		return set()
	return set(frappe.get_all(OPT_OUT_DOCTYPE, filters={"point": point}, pluck="user"))


def filter_valid(users: set[str], exclude: set[str] | None = None) -> list[frappe._dict]:
	"""Bỏ tài khoản hệ thống, tài khoản khoá, tài khoản không có email; khử trùng."""
	candidates = {u for u in users if u and u not in SYSTEM_USERS} - (exclude or set())
	if not candidates:
		return []

	rows = frappe.get_all(
		"User",
		filters={"name": ("in", list(candidates)), "enabled": 1},
		fields=["name", "email", "full_name"],
		order_by="full_name asc",
	)
	return [row for row in rows if row.email]


def _describe(users_by_source: dict[str, set[str]]) -> dict[str, list[str]]:
	sources: dict[str, list[str]] = {}
	for source, users in users_by_source.items():
		for user in users:
			sources.setdefault(user, []).append(source)
	return sources


# --- Người nhận nội bộ ----------------------------------------------------


def internal_sources(point, doc=None, triggered_by: str | None = None) -> dict[str, set[str]]:
	"""Từng nguồn người nhận nội bộ, giữ riêng để xem trước giải thích được."""
	sources = {
		SOURCE_DEPARTMENT: users_in_departments([row.department for row in (point.get("departments") or [])]),
		SOURCE_USER: {row.user for row in (point.get("users") or []) if row.user},
		SOURCE_GROUP: users_in_groups(group_names(point.get("recipient_groups"))),
		SOURCE_OWNER: set(),
		SOURCE_DOC_FIELD: set(),
		SOURCE_TRIGGER: set(),
	}

	if doc is not None:
		data = doc if isinstance(doc, dict) else doc.as_dict()

		if point.get("notify_owner") and data.get("owner"):
			sources[SOURCE_OWNER].add(data.get("owner"))

		for row in point.get("user_fields") or []:
			value = data.get(row.fieldname)
			if value and frappe.db.exists("User", value):
				sources[SOURCE_DOC_FIELD].add(value)

	if point.get("notify_triggering_user") and triggered_by:
		sources[SOURCE_TRIGGER].add(triggered_by)

	return sources


def resolve(point, doc=None, triggered_by: str | None = None) -> frappe._dict:
	"""Toàn bộ người nhận của một lần gửi: nội bộ, ngoài, CC, BCC, trả lời về."""
	sources = internal_sources(point, doc, triggered_by)
	all_users: set[str] = set().union(*sources.values()) if sources else set()

	recipients = filter_valid(all_users, exclude=opted_out_users(point.get("name")))

	notes = []
	external, external_note = external_emails(point, doc)
	if external_note:
		notes.append(external_note)

	return frappe._dict(
		users=recipients,
		emails=[row.email for row in recipients]
		+ emails_in_groups(group_names(point.get("recipient_groups"))),
		external=external,
		cc=cc_emails(point, doc, triggered_by),
		bcc=split_emails(point.get("bcc_emails") or ""),
		reply_to=reply_to(point, doc, triggered_by),
		sources=_describe(sources),
		notes=notes,
	)


# --- Người nhận ngoài -----------------------------------------------------


def _party_of(doc) -> tuple[str | None, str | None]:
	"""Đối tác ngoài của chứng từ, để tra liên hệ khi trên chứng từ chưa có email."""
	meta = frappe.get_meta(doc.get("doctype"))

	if meta.has_field("party_type") and doc.get("party_type"):
		return doc.get("party_type"), doc.get("party")
	if meta.has_field("supplier") and doc.get("supplier"):
		return "Supplier", doc.get("supplier")
	if meta.has_field("customer") and doc.get("customer"):
		return "Customer", doc.get("customer")
	return None, None


def _contact_email(party_type: str, party: str) -> str | None:
	names = frappe.get_all(
		"Dynamic Link",
		filters={"link_doctype": party_type, "link_name": party, "parenttype": "Contact"},
		pluck="parent",
	)
	if not names:
		return None

	rows = frappe.get_all(
		"Contact",
		filters={"name": ("in", names)},
		fields=["email_id", "is_primary_contact"],
		order_by="is_primary_contact desc, modified desc",
	)
	for row in rows:
		if row.email_id:
			return row.email_id
	return None


def party_email(doc) -> str | None:
	"""Email của NCC/khách trên chứng từ, lần lượt theo các nguồn ưu tiên (F9)."""
	meta = frappe.get_meta(doc.get("doctype"))

	for fieldname in ("contact_email", "email_to"):
		if meta.has_field(fieldname):
			value = (doc.get(fieldname) or "").strip()
			if value:
				return value

	party_type, party = _party_of(doc)
	if not party_type or not party:
		return None

	email = _contact_email(party_type, party)
	if email:
		return email

	if party_type in ("Supplier", "Customer"):
		return frappe.db.get_value(party_type, party, "email_id") or None

	return None


def external_emails(point, doc=None) -> tuple[list[str], str]:
	"""Danh sách email gửi ra ngoài và ghi chú khi không tìm được ai."""
	if not point.get("notify_external"):
		return [], ""

	emails: list[str] = []
	data = None
	if doc is not None:
		data = doc if isinstance(doc, dict) else doc.as_dict()

	if data is not None:
		for row in point.get("external_email_fields") or []:
			value = (data.get(row.fieldname) or "").strip()
			if value:
				emails.extend(split_emails(value))

		if point.get("external_party_contact") and not emails:
			found = party_email(data)
			if found:
				emails.append(found)

	emails.extend(split_emails(point.get("external_fixed_emails") or ""))
	emails.extend(emails_in_groups(group_names(point.get("external_groups"))))

	emails = _unique_emails(emails)
	if not emails:
		return [], _("Chứng từ và đối tác chưa có email liên hệ.")

	return emails, ""


def cc_emails(point, doc=None, triggered_by: str | None = None) -> list[str]:
	emails = split_emails(point.get("cc_emails") or "")

	if point.get("cc_owner") and doc is not None:
		data = doc if isinstance(doc, dict) else doc.as_dict()
		emails.append(_email_of(data.get("owner")))

	if point.get("cc_triggering_user") and triggered_by:
		emails.append(_email_of(triggered_by))

	return _unique_emails(emails)


def reply_to(point, doc=None, triggered_by: str | None = None) -> str | None:
	mode = point.get("reply_to_mode") or "Không đặt"

	if mode == "Người tạo chứng từ" and doc is not None:
		data = doc if isinstance(doc, dict) else doc.as_dict()
		return _email_of(data.get("owner")) or None
	if mode == "Người bấm gửi":
		return _email_of(triggered_by) or None
	if mode == "Email cố định":
		return point.get("reply_to_email") or None
	return None


def _email_of(user: str | None) -> str:
	if not user or user in SYSTEM_USERS:
		return ""
	return frappe.db.get_value("User", user, "email") or ""


def _unique_emails(emails: list[str]) -> list[str]:
	seen: list[str] = []
	for email in emails:
		email = (email or "").strip()
		if not email or email in seen:
			continue
		try:
			validate_email_address(email, throw=True)
		except Exception:
			continue
		seen.append(email)
	return seen


# --- Xem trước ------------------------------------------------------------


def preview_for(point, doc=None, triggered_by: str | None = None) -> dict:
	"""Người nhận thực tế của một điểm, kèm cảnh báo cấu hình (thẻ 3 của form)."""
	resolved = resolve(point, doc, triggered_by)
	sources = internal_sources(point, doc, triggered_by)
	all_users: set[str] = set().union(*sources.values()) if sources else set()

	warnings = []
	if not point.get("enabled"):
		warnings.append(_("Điểm thông báo đang tắt — sẽ không gửi gì."))

	if not (point.get("send_email") or point.get("send_inapp") or point.get("notify_external")):
		warnings.append(_("Chưa bật kênh gửi nào."))

	department_names = [row.department for row in (point.get("departments") or [])]
	missing = employees_without_user(department_names)
	if missing:
		warnings.append(
			_("{0} nhân viên thuộc phòng ban đã chọn chưa gắn tài khoản nên không nhận được: {1}").format(
				len(missing), ", ".join(sorted(missing)[:10])
			)
		)

	dropped = sorted(all_users - {row.name for row in resolved.users} - set(SYSTEM_USERS))
	if dropped:
		warnings.append(
			_("Bỏ qua tài khoản đã khoá, không có email, hoặc đã tự tắt điểm này: {0}").format(
				", ".join(dropped)
			)
		)

	if department_names and not sources[SOURCE_DEPARTMENT]:
		warnings.append(_("Không tìm được nhân viên nào đang làm việc trong các phòng ban đã chọn."))

	if not resolved.users and not resolved.emails and not resolved.external:
		warnings.append(_("Chưa có người nhận nào — thông báo sẽ không đến ai."))

	warnings.extend(resolved.notes)

	return {
		"recipients": [
			{
				"user": row.name,
				"full_name": row.full_name,
				"email": row.email,
				"sources": [SOURCE_LABELS.get(s, s) for s in resolved.sources.get(row.name, [])],
			}
			for row in resolved.users
		],
		"group_emails": emails_in_groups(group_names(point.get("recipient_groups"))),
		"external": resolved.external,
		"cc": resolved.cc,
		"bcc": resolved.bcc,
		"reply_to": resolved.reply_to,
		"warnings": warnings,
	}


@frappe.whitelist()
def preview(point: str, reference: str | None = None) -> dict:
	"""API của nút *Xem trước người nhận*."""
	doc = frappe.get_doc("Supply Notification Point", point)
	doc.check_permission("read")

	sample = None
	if reference and frappe.db.exists(doc.reference_doctype, reference):
		sample = frappe.get_doc(doc.reference_doctype, reference)
		sample.check_permission("read")

	return preview_for(doc, sample, frappe.session.user)
