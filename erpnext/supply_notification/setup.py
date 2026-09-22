# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Dựng vai trò, phòng ban còn thiếu và 12 điểm thông báo mặc định.

Phòng ban tra theo danh mục chuẩn `erpnext.setup.department_catalog` (khớp bí danh),
nên phòng đã có dưới tên khác được dùng lại thay vì tạo trùng.

Chạy được nhiều lần: gọi lại không nhân đôi bản ghi và **không** ghi đè điểm
thông báo đã tồn tại — nghiệp vụ có thể đã sửa người nhận hoặc câu chữ.

Tham chiếu: docs/05c_Spec_KyThuat_Plan_Thong_Bao.md muc 3.2 va Phu luc C.
"""

import frappe

from erpnext.setup.department_catalog import ensure_departments
from erpnext.supply_notification.constants import ADMIN_ROLE, POINTS

POINT_DOCTYPE = "Supply Notification Point"


def setup_supply_notification():
	"""Điểm vào duy nhất, gọi từ patch và từ `after_migrate`."""
	make_admin_role()
	company = default_company()
	departments = ensure_departments(company, needed_departments()) if company else {}
	seed_points(departments)


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
	"""Gốc cây phòng ban, chỉ trả về khi cây nested set còn lành.

	`rgt = 0` nghĩa là cây chưa dựng: ERPNext chèn phòng ban hàng loạt với
	`ignore_update_nsm` rồi mới `rebuild_tree` ở cuối (xem `Company.create_default_departments`),
	nên một lần tạo công ty đứt giữa chừng để lại toàn bộ `lft`/`rgt` bằng 0.
	Gán một nút như vậy làm cha thì `validate_loop` của Frappe thấy bản ghi vừa
	chèn (cũng lft=0, rgt=0) nằm trong khoảng `lft <= 0 and rgt >= 0` và ném
	`NestedSetRecursionError` — báo đệ quy dù không hề có vòng lặp.
	"""
	roots = frappe.get_all(
		"Department",
		filters={"is_group": 1, "parent_department": ("in", ("", None)), "rgt": (">", 0)},
		pluck="name",
		limit=1,
	)
	return roots[0] if roots else None


def needed_departments() -> list[str]:
	"""Mã phòng ban mà 12 điểm mặc định dùng, giữ thứ tự xuất hiện."""
	return list(dict.fromkeys(key for spec in POINTS for key in spec["departments"]))


def seed_points(departments: dict[str, str] | None = None) -> list[str]:
	"""Gieo các điểm thông báo còn thiếu. Trả về mã các điểm vừa tạo.

	`departments` là {mã danh mục: tên Department} do `ensure_departments` trả về;
	mã không có trong đó thì bỏ dòng khỏi bảng con, không nổ.
	"""
	departments = departments or {}
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

		for key in spec["departments"]:
			if departments.get(key):
				doc.append("departments", {"department": departments[key]})

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
