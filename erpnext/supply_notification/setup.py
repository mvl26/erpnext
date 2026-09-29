# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Dựng vai trò, cài đặt, mẫu dùng chung, phòng ban còn thiếu và 13 điểm mặc định.

Phòng ban tra theo danh mục chuẩn `erpnext.setup.department_catalog` (khớp bí danh),
nên phòng đã có dưới tên khác được dùng lại thay vì tạo trùng.

Chạy được nhiều lần: gọi lại không nhân đôi bản ghi và **không** ghi đè điểm
thông báo, mẫu hay cài đặt đã tồn tại — nghiệp vụ có thể đã sửa người nhận hoặc
câu chữ (NF6).

Quyết định 23/09/2026: hàm này **không** tạo Custom Field trên `Address` và
**không** gán vai trò *Quản trị thông báo* cho tài khoản nào — việc gán quyền do
PO tự làm trên Desk.

Tham chiếu: docs/superpowers/specs/2026-09-23-thong-bao-tu-thiet-lap-design.md muc 4.12.
"""

import frappe

from erpnext.setup.department_catalog import ensure_departments
from erpnext.supply_notification import constants, content, registry

POINT_DOCTYPE = "Supply Notification Point"
SNIPPET_DOCTYPE = "Supply Notification Snippet"
SETTINGS_DOCTYPE = "Supply Notification Settings"


def setup_supply_notification():
	"""Điểm vào duy nhất, gọi từ patch và từ `after_migrate`."""
	make_admin_role()
	ensure_settings()
	seed_snippets()

	company = default_company()
	departments = ensure_departments(company, needed_departments()) if company else {}
	seed_points(departments)

	registry.clear_cache()


def default_company() -> str | None:
	company = frappe.defaults.get_global_default("company")
	if company and frappe.db.exists("Company", company):
		return company

	companies = frappe.get_all("Company", pluck="name", order_by="creation asc", limit=1)
	return companies[0] if companies else None


def make_admin_role():
	if frappe.db.exists("Role", constants.ADMIN_ROLE):
		return

	frappe.get_doc(
		{
			"doctype": "Role",
			"role_name": constants.ADMIN_ROLE,
			"desk_access": 1,
		}
	).insert(ignore_permissions=True)


def ensure_settings():
	"""Điền mặc định cho bản ghi cài đặt, chỉ khi ô còn trống."""
	settings = frappe.get_single(SETTINGS_DOCTYPE)
	defaults = {
		"enabled": 1,
		"default_subject_prefix": constants.DEFAULT_PREFIX,
		"max_item_rows": 50,
		"sound": "alert",
		"toast_seconds": 10,
		"sound_debounce_seconds": 3,
		"reminder_hour": 8,
		"hourly_email_cap": 200,
		"auto_log_retention_days": 180,
		"manual_log_retention_days": 0,
	}

	changed = False
	for fieldname, value in defaults.items():
		if settings.get(fieldname) in (None, ""):
			settings.set(fieldname, value)
			changed = True

	if changed:
		settings.flags.ignore_permissions = True
		settings.save(ignore_permissions=True)


def seed_snippets() -> list[str]:
	created = []
	for spec in constants.SEED_SNIPPETS:
		if frappe.db.exists(SNIPPET_DOCTYPE, spec["snippet_name"]):
			continue

		doc = frappe.new_doc(SNIPPET_DOCTYPE)
		doc.update(spec)
		doc.insert(ignore_permissions=True)
		created.append(doc.name)
	return created


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
	"""Mã phòng ban mà các điểm mặc định dùng, giữ thứ tự xuất hiện."""
	return list(dict.fromkeys(key for spec in constants.SEED_POINTS for key in spec.get("departments", ())))


def all_seed_specs() -> tuple[dict, ...]:
	return constants.SEED_POINTS + constants.SEED_MANUAL_POINTS


def seed_points(departments: dict[str, str] | None = None) -> list[str]:
	"""Gieo các điểm còn thiếu. Trả về mã các điểm vừa tạo.

	`departments` là {mã danh mục: tên Department} do `ensure_departments` trả về;
	mã không có trong đó thì bỏ dòng khỏi bảng con, không nổ.
	"""
	departments = departments or {}
	created = []

	for spec in all_seed_specs():
		if frappe.db.exists(POINT_DOCTYPE, spec["code"]):
			continue

		doc = build_point(spec, departments)
		doc.insert(ignore_permissions=True)
		created.append(doc.code)

	return created


def build_point(spec: dict, departments: dict[str, str] | None = None) -> "frappe.Document":
	"""Dựng (chưa lưu) một điểm từ dữ liệu hạt giống."""
	departments = departments or {}

	doc = frappe.new_doc(POINT_DOCTYPE)
	doc.code = spec["code"]
	doc.title = spec["title"]
	doc.is_seed = 1
	doc.enabled = 1
	doc.function_group = spec.get("function_group")
	doc.reference_doctype = spec["reference_doctype"]
	doc.trigger_event = spec["trigger_event"]
	doc.notes = spec.get("notes")
	doc.subject_prefix = spec.get("subject_prefix", constants.DEFAULT_PREFIX)

	doc.send_email = spec.get("send_email", 1)
	doc.send_inapp = spec.get("send_inapp", 1)
	doc.notify_owner = spec.get("notify_owner", 0)
	doc.notify_external = spec.get("notify_external", 0)
	doc.external_party_contact = spec.get("external_party_contact", 1 if spec.get("notify_external") else 0)
	doc.cc_owner = spec.get("cc_owner", 0)
	doc.reply_to_mode = spec.get("reply_to_mode", "Không đặt")
	doc.allow_opt_out = spec.get("allow_opt_out", 0)

	doc.attach_pdf = spec.get("attach_pdf", 0) if _print_format_ok(spec) else 0
	doc.print_format = spec.get("print_format") if doc.attach_pdf else None

	doc.party_field = spec.get("party_field")
	doc.amount_field = spec.get("amount_field")
	doc.main_date_field = spec.get("main_date_field")
	doc.item_table_field = spec.get("item_table_field", "items")
	doc.address_field = spec.get("address_field")
	doc.contact_field = spec.get("contact_field")
	doc.signature_person = spec.get("signature_person", "Người tạo")

	doc.date_field = spec.get("date_field")
	doc.reminder_offsets = spec.get("reminder_offsets", "")
	doc.button_label = spec.get("button_label")
	doc.button_color = spec.get("button_color", "Mặc định")
	doc.manual_docstatus = spec.get("manual_docstatus", "Đã ghi sổ")

	doc.subject_template = spec.get("subject_template", "")
	doc.body_template = spec.get("body_template") or (
		content.compose_body(
			spec.get("intro", ""),
			spec.get("action", ""),
			show_stock_report=spec.get("show_stock_report", 0),
		)
		if spec.get("intro")
		else ""
	)
	doc.external_subject_template = spec.get("external_subject_template", "")
	doc.external_body_template = spec.get("external_body_template") or (
		content.compose_body(spec.get("external_intro", ""), external=True)
		if spec.get("external_intro")
		else ""
	)

	for key in spec.get("departments", ()):
		if departments.get(key):
			doc.append("departments", {"department": departments[key]})

	for fieldname, operator, value in spec.get("conditions", ()):
		doc.append("conditions", {"fieldname": fieldname, "operator": operator, "value": value})

	for fieldname, label in spec.get("item_columns", ()):
		doc.append("item_columns", {"fieldname": fieldname, "label": label})

	for fieldname, label, only_if_previous_empty in spec.get(
		"fact_rows", constants.default_fact_rows(spec.get("amount_label", "Giá trị"))
	):
		doc.append(
			"fact_rows",
			{
				"fieldname": fieldname,
				"label": label,
				"only_if_previous_empty": only_if_previous_empty,
			},
		)

	return doc


def _print_format_ok(spec: dict) -> bool:
	"""Mẫu in phải tồn tại, nếu không thì gieo với cờ đính PDF tắt.

	Site khác chưa có mẫu in tiếng Việt vẫn cài được, chỉ là không đính file.
	"""
	if not spec.get("attach_pdf"):
		return False
	return bool(spec.get("print_format") and frappe.db.exists("Print Format", spec["print_format"]))
