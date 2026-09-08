# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Diễn giải cấu hình người nhận thành danh sách người thật.

Nguồn phòng ban là hồ sơ Nhân viên (quyết định D1): `Employee.department` gắn với
`Employee.user_id`, chỉ lấy nhân viên đang làm việc. Site không cài `hrms` thì phần
theo phòng ban trả rỗng — cấu hình theo người đích danh vẫn chạy.

Tham chiếu: docs/05c_Spec_KyThuat_Plan_Thong_Bao.md muc 6.
"""

import frappe
from frappe import _

#: Hai tài khoản hệ thống không bao giờ là người nhận nghiệp vụ.
SYSTEM_USERS = ("Administrator", "Guest")

SOURCE_DEPARTMENT = "department"
SOURCE_USER = "user"
SOURCE_OWNER = "owner"


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


def _describe(users_by_source: dict[str, set[str]]) -> dict[str, list[str]]:
	sources: dict[str, list[str]] = {}
	for source, users in users_by_source.items():
		for user in users:
			sources.setdefault(user, []).append(source)
	return sources


def filter_valid(users: set[str]) -> list[frappe._dict]:
	"""Bỏ tài khoản hệ thống, tài khoản khoá, tài khoản không có email; khử trùng."""
	candidates = {u for u in users if u and u not in SYSTEM_USERS}
	if not candidates:
		return []

	rows = frappe.get_all(
		"User",
		filters={"name": ("in", list(candidates)), "enabled": 1},
		fields=["name", "email", "full_name"],
		order_by="full_name asc",
	)
	return [row for row in rows if row.email]


def resolve(point, doc=None) -> list[frappe._dict]:
	"""Danh sách người nhận nội bộ cuối cùng của một điểm thông báo."""
	users = users_in_departments([row.department for row in (point.departments or [])])
	users |= {row.user for row in (point.users or []) if row.user}
	if point.notify_owner and doc is not None:
		users.add(doc.owner)

	return filter_valid(users)


@frappe.whitelist()
def preview(point: str) -> dict:
	"""Xem trước người nhận thực tế của một điểm, kèm cảnh báo cấu hình."""
	doc = frappe.get_doc("Supply Notification Point", point)
	doc.check_permission("read")

	department_names = [row.department for row in (doc.departments or [])]
	from_departments = users_in_departments(department_names)
	from_users = {row.user for row in (doc.users or []) if row.user}

	recipients = filter_valid(from_departments | from_users)
	sources = _describe({SOURCE_DEPARTMENT: from_departments, SOURCE_USER: from_users})

	warnings = []
	if not doc.enabled:
		warnings.append(_("Điểm thông báo đang tắt — sẽ không gửi gì."))
	if not doc.send_email and not doc.send_inapp:
		warnings.append(_("Cả hai kênh email và in-app đều đang tắt."))

	missing = employees_without_user(department_names)
	if missing:
		warnings.append(
			_("{0} nhân viên thuộc phòng ban đã chọn chưa gắn tài khoản nên không nhận được: {1}").format(
				len(missing), ", ".join(sorted(missing)[:10])
			)
		)

	dropped = sorted((from_departments | from_users) - {row.name for row in recipients} - set(SYSTEM_USERS))
	if dropped:
		warnings.append(_("Bỏ qua tài khoản đã khoá hoặc không có email: {0}").format(", ".join(dropped)))

	if department_names and not from_departments:
		warnings.append(_("Không tìm được nhân viên nào đang làm việc trong các phòng ban đã chọn."))

	if not recipients and not doc.notify_owner:
		warnings.append(_("Chưa có người nhận nào — thông báo sẽ không đến ai."))

	return {
		"recipients": [
			{
				"user": row.name,
				"full_name": row.full_name,
				"email": row.email,
				"sources": sources.get(row.name, []),
			}
			for row in recipients
		],
		"notify_owner": bool(doc.notify_owner),
		"warnings": warnings,
	}


def _party_of(doc) -> tuple[str | None, str | None]:
	"""Đối tác ngoài của chứng từ, để tra liên hệ khi trên chứng từ chưa có email."""
	if doc.meta.has_field("party_type") and doc.get("party_type"):
		return doc.get("party_type"), doc.get("party")
	if doc.meta.has_field("supplier") and doc.get("supplier"):
		return "Supplier", doc.get("supplier")
	if doc.meta.has_field("customer") and doc.get("customer"):
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


def external_email(doc) -> str | None:
	"""Email của NCC/khách trên chứng từ, lần lượt theo bốn nguồn ưu tiên.

	Không tìm được thì trả None — bên gọi bỏ qua phần gửi ra ngoài và ghi nhật ký,
	tuyệt đối không làm hỏng việc ghi sổ chứng từ.
	"""
	for fieldname in ("contact_email", "email_to"):
		if doc.meta.has_field(fieldname):
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
