# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Dựng vai trò, phòng ban còn thiếu và 12 điểm thông báo mặc định.

Chạy được nhiều lần: gọi lại không nhân đôi bản ghi và **không** ghi đè điểm
thông báo đã tồn tại — nghiệp vụ có thể đã sửa người nhận hoặc câu chữ.

Tham chiếu: docs/05c_Spec_KyThuat_Plan_Thong_Bao.md muc 3.2 va Phu luc C.
"""

import frappe

from erpnext.supply_notification.constants import ADMIN_ROLE, DEPARTMENTS_TO_CREATE, POINTS

POINT_DOCTYPE = "Supply Notification Point"


def setup_supply_notification():
	"""Điểm vào duy nhất, gọi từ patch và từ `after_migrate`."""
	make_admin_role()
	company = default_company()
	if company:
		make_departments(company)
	seed_points(company)


def default_company() -> str | None:
	company = frappe.defaults.get_global_default("company")
	if company and frappe.db.exists("Company", company):
		return company

	companies = frappe.get_all("Company", pluck="name", order_by="creation asc", limit=1)
	return companies[0] if companies else None


def make_admin_role():
	if frappe.db.exists("Role", ADMIN_ROLE):
		return

	frappe.get_doc(
		{
			"doctype": "Role",
			"role_name": ADMIN_ROLE,
			"desk_access": 1,
		}
	).insert(ignore_permissions=True)


def root_department() -> str | None:
	roots = frappe.get_all(
		"Department",
		filters={"is_group": 1, "parent_department": ("in", ("", None))},
		pluck="name",
		limit=1,
	)
	return roots[0] if roots else None


def find_department(department_name: str, company: str | None) -> str | None:
	filters = {"department_name": department_name}
	if company:
		filters["company"] = company

	found = frappe.get_all("Department", filters=filters, pluck="name", limit=1)
	if found:
		return found[0]

	# Site một công ty đôi khi để trống `company`; thử lại không ràng buộc.
	found = frappe.get_all("Department", filters={"department_name": department_name}, pluck="name", limit=1)
	return found[0] if found else None


def make_departments(company: str) -> list[str]:
	"""Tạo bù phòng Kho và Mua hàng nếu site chưa có (quyết định D3)."""
	created = []
	parent = root_department()

	for department_name in DEPARTMENTS_TO_CREATE:
		if find_department(department_name, company):
			continue

		doc = frappe.new_doc("Department")
		doc.department_name = department_name
		doc.company = company
		if parent:
			doc.parent_department = parent
		doc.insert(ignore_permissions=True)
		created.append(doc.name)

	return created


def seed_points(company: str | None = None) -> list[str]:
	"""Gieo các điểm thông báo còn thiếu. Trả về mã các điểm vừa tạo."""
	created = []

	for spec in POINTS:
		if frappe.db.exists(POINT_DOCTYPE, spec["code"]):
			continue

		doc = frappe.new_doc(POINT_DOCTYPE)
		doc.code = spec["code"]
		doc.title = spec["title"]
		doc.enabled = 1
		doc.reference_doctype = spec["reference_doctype"]
		doc.trigger_event = spec["trigger_event"]
		doc.filter_note = spec["filter_note"]
		doc.send_email = 1
		doc.send_inapp = 1
		doc.notify_owner = spec["notify_owner"]
		doc.notify_external = spec["notify_external"]
		doc.attach_pdf = spec["attach_pdf"] if _print_format_ok(spec) else 0
		doc.print_format = spec["print_format"] if doc.attach_pdf else None
		doc.subject_template = spec["subject_template"]
		doc.intro_template = spec["intro_template"]
		doc.action_template = spec["action_template"]
		doc.external_subject_template = spec["external_subject_template"]
		doc.external_intro_template = spec["external_intro_template"]

		for department_name in spec["departments"]:
			resolved = find_department(department_name, company)
			if not resolved:
				continue
			doc.append("departments", {"department": resolved})

		doc.insert(ignore_permissions=True)
		created.append(doc.code)

	return created


def _print_format_ok(spec: dict) -> bool:
	"""Mẫu in phải tồn tại, nếu không thì gieo với cờ đính PDF tắt.

	Site khác chưa có mẫu in tiếng Việt vẫn cài được, chỉ là không đính file.
	"""
	if not spec["attach_pdf"]:
		return False
	return bool(spec["print_format"] and frappe.db.exists("Print Format", spec["print_format"]))
