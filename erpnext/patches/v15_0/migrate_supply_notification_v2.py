# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Chuyển 12 điểm thông báo sang mô hình tự thiết lập (BA_NTF_V4, mục 6.6).

Nguyên tắc: **không ghi đè câu chữ của nghiệp vụ**. Patch lấy đúng nội dung đang
nằm trong bản ghi (ba ô mở đầu · việc cần làm · nội dung ngoài) rồi ghép thành
thân email theo đúng thứ tự mà bản build 05c hiển thị; phần trước đây nằm cứng
trong `constants.py` (chứng từ, điều kiện, trường tiền/ngày/đối tác, mốc nhắc)
mới lấy từ hạt giống.

Cột cũ vẫn còn trong bảng sau khi gỡ khỏi DocType JSON (Frappe không xoá cột),
nên patch đọc bằng SQL thô — chạy lại lần nữa cũng không hỏng gì vì điểm đã có
`body_template` thì bỏ qua.

Chạy sau model sync để các trường mới đã tồn tại.
"""

import re

import frappe

from erpnext.supply_notification import constants, content
from erpnext.supply_notification.setup import setup_supply_notification

POINT_DOCTYPE = "Supply Notification Point"
#: Ô câu chữ của bản cũ, nay gộp vào thân email.
LEGACY_COLUMNS = (
	"intro_template",
	"action_template",
	"external_intro_template",
	"external_closing",
	"filter_note",
)

#: Đổi tên biến sang bộ tiếng Việt mới; bí danh cũ vẫn chạy, đổi tên chỉ để
#: người dùng mở form ra thấy đúng tên đang có trong bảng "Có thể chèn".
VARIABLE_RENAMES = {
	"party_name": "ten_doi_tac",
	"owner_name": "ten_nguoi_tao",
	"amount": "so_tien",
	"outstanding": "so_tien",
	"date": "ngay",
	"due": "han_thanh_toan",
	"days_left": "so_ngay_con_lai",
}

_JINJA_TAG = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.DOTALL)


def execute():
	if not frappe.db.exists("DocType", POINT_DOCTYPE):
		return

	existing_columns = set(frappe.db.get_table_columns(POINT_DOCTYPE))

	for spec in constants.SEED_POINTS:
		if not frappe.db.exists(POINT_DOCTYPE, spec["code"]):
			continue
		migrate_point(spec, existing_columns)

	disable_external_channel_on_purchase_order()

	# Điểm còn thiếu (NTF-13 của CR_01), cài đặt, mẫu dùng chung, vai trò.
	setup_supply_notification()

	# Form script và nút Thủ công chỉ tới được trình duyệt khi `modified` đổi.
	frappe.db.set_value("DocType", POINT_DOCTYPE, "modified", frappe.utils.now(), update_modified=False)
	frappe.clear_cache()


def legacy_values(code: str, columns: set[str]) -> dict:
	fields = [column for column in LEGACY_COLUMNS if column in columns]
	if not fields:
		return {}
	return frappe.db.get_value(POINT_DOCTYPE, code, fields, as_dict=True) or {}


def rename_variables(template: str) -> str:
	"""Đổi tên biến **chỉ bên trong** thẻ Jinja, không đụng tới câu chữ."""
	if not template:
		return ""

	def _rename(match: re.Match) -> str:
		tag = match.group(0)
		for old, new in VARIABLE_RENAMES.items():
			tag = re.sub(rf"\b{old}\b", new, tag)
		return tag

	return _JINJA_TAG.sub(_rename, template)


def strip_prefix_variable(subject: str) -> str:
	"""`{{ prefix }} Tiêu đề` → `Tiêu đề`; tiền tố nay là một ô riêng."""
	return re.sub(r"^\s*\{\{\s*(prefix|tien_to)\s*\}\}\s*", "", subject or "").strip()


def migrate_point(spec: dict, columns: set[str]):
	doc = frappe.get_doc(POINT_DOCTYPE, spec["code"])
	if doc.body_template:
		return

	legacy = legacy_values(spec["code"], columns)

	doc.is_seed = 1
	doc.function_group = doc.function_group or spec.get("function_group")
	doc.notes = doc.notes or legacy.get("filter_note") or spec.get("notes")
	doc.subject_prefix = doc.subject_prefix or constants.DEFAULT_PREFIX
	doc.subject_template = rename_variables(strip_prefix_variable(doc.subject_template))
	doc.external_subject_template = rename_variables(strip_prefix_variable(doc.external_subject_template))

	doc.body_template = content.compose_body(
		rename_variables(legacy.get("intro_template") or ""),
		rename_variables(legacy.get("action_template") or ""),
		show_stock_report=spec.get("show_stock_report", 0),
	)

	external_intro = rename_variables(legacy.get("external_intro_template") or "")
	if external_intro:
		doc.external_body_template = content.compose_body(
			external_intro,
			rename_variables(legacy.get("external_closing") or ""),
			external=True,
		)

	doc.party_field = doc.party_field or spec.get("party_field")
	doc.amount_field = doc.amount_field or spec.get("amount_field")
	doc.main_date_field = doc.main_date_field or spec.get("main_date_field")
	doc.item_table_field = doc.item_table_field or "items"

	if doc.trigger_event in (constants.LEGACY_DUE_REMINDER, constants.DATE_REMINDER):
		doc.trigger_event = constants.DATE_REMINDER
		doc.date_field = doc.date_field or spec.get("date_field")
		doc.reminder_offsets = doc.reminder_offsets or spec.get("reminder_offsets")

	if not doc.conditions:
		for fieldname, operator, value in spec.get("conditions", ()):
			doc.append("conditions", {"fieldname": fieldname, "operator": operator, "value": value})

	if not doc.fact_rows:
		for fieldname, label, only_if_previous_empty in constants.default_fact_rows(
			spec.get("amount_label", "Giá trị")
		):
			doc.append(
				"fact_rows",
				{
					"fieldname": fieldname,
					"label": label,
					"only_if_previous_empty": only_if_previous_empty,
				},
			)

	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)


def disable_external_channel_on_purchase_order():
	"""CR_01 R2/R8/AC7: NTF-03 giữ phần báo kho, thôi tự gửi NCC khi ghi sổ.

	Việc gửi NCC chuyển sang điểm NTF-13 với nút bấm tay.
	"""
	if not frappe.db.exists(POINT_DOCTYPE, "NTF-03"):
		return

	frappe.db.set_value(
		POINT_DOCTYPE,
		"NTF-03",
		{
			"notify_external": 0,
			"external_subject_template": "",
			"external_body_template": "",
		},
	)
