# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Đánh giá bảng điều kiện của một điểm thông báo (quyết định D11).

Điều kiện là **dữ liệu**: mỗi dòng gồm *Trường — Toán tử — Giá trị*, cả bảng nối
bằng VÀ hoặc HOẶC. Không có ô viết mã, nên nghiệp vụ tự đặt được điều kiện và
hệ thống kiểm được ngay lúc lưu (kiểm V3).

Trường trong bảng con ghi dạng `items.item_group` và thoả khi **ít nhất một
dòng** thoả (F6).

Tham chiếu: docs/superpowers/specs/2026-09-23-thong-bao-tu-thiet-lap-design.md muc 4.3.
"""

import frappe
from frappe.utils import flt, getdate

EQ = "="
NE = "≠"
GT = ">"
GE = "≥"
LT = "<"
LE = "≤"
IN = "Trong danh sách"
NOT_IN = "Không trong danh sách"
IS_SET = "Có giá trị"
IS_NOT_SET = "Trống"
CONTAINS = "Chứa"

OPERATORS = (EQ, NE, GT, GE, LT, LE, IN, NOT_IN, IS_SET, IS_NOT_SET, CONTAINS)

#: Toán tử không cần ô giá trị.
VALUELESS_OPERATORS = (IS_SET, IS_NOT_SET)

#: Ánh xạ sang bộ lọc của Frappe, dùng khi đẩy điều kiện xuống SQL.
FILTER_OPERATORS = {
	EQ: "=",
	NE: "!=",
	GT: ">",
	GE: ">=",
	LT: "<",
	LE: "<=",
	IN: "in",
	NOT_IN: "not in",
	CONTAINS: "like",
}

NUMERIC_FIELDTYPES = ("Currency", "Float", "Int", "Percent")
DATE_FIELDTYPES = ("Date", "Datetime")

LOGIC_AND = "VÀ"
LOGIC_OR = "HOẶC"


def split_values(raw: str) -> list[str]:
	return [part.strip() for part in (raw or "").split(",") if part.strip()]


def _coerce(value, raw: str, fieldtype: str | None):
	"""Ép hai vế về cùng kiểu để so sánh cho đúng nghĩa.

	Trả `None` khi không ép được — bên gọi coi như **không thoả**. So chuỗi thay
	cho ngày là cái bẫy im lặng: `"chữ" > "2026-01-01"` ra True theo thứ tự ký
	tự, và điều kiện ngày hỏng biến thành thông báo bắn nhầm.
	"""
	if fieldtype in NUMERIC_FIELDTYPES:
		return flt(value), flt(raw)

	if fieldtype in DATE_FIELDTYPES:
		try:
			return getdate(value), getdate(raw)
		except Exception:
			return None

	return str(value if value is not None else ""), str(raw or "")


def compare(value, operator: str, raw: str, fieldtype: str | None = None) -> bool:
	"""So một giá trị với một vế phải. Không bao giờ ném lỗi ra ngoài."""
	if operator == IS_SET:
		return value not in (None, "")
	if operator == IS_NOT_SET:
		return value in (None, "")

	if operator in (IN, NOT_IN):
		options = [str(option) for option in split_values(raw)]
		found = str(value if value is not None else "") in options
		return found if operator == IN else not found

	if operator == CONTAINS:
		return str(raw or "").casefold() in str(value if value is not None else "").casefold()

	coerced = _coerce(value, raw, fieldtype)
	if coerced is None:
		return False

	left, right = coerced

	try:
		if operator == EQ:
			return left == right
		if operator == NE:
			return left != right
		if operator == GT:
			return left > right
		if operator == GE:
			return left >= right
		if operator == LT:
			return left < right
		if operator == LE:
			return left <= right
	except TypeError:
		return False

	return False


def split_fieldname(fieldname: str) -> tuple[str | None, str]:
	"""`items.item_group` → (`items`, `item_group`); trường thường → (None, tên)."""
	if fieldname and "." in fieldname:
		table, _, child_field = fieldname.partition(".")
		return table, child_field
	return None, fieldname


def _fieldtype(meta, fieldname: str) -> str | None:
	table, child_field = split_fieldname(fieldname)
	if not table:
		df = meta.get_field(child_field)
		return df.fieldtype if df else None

	parent_df = meta.get_field(table)
	if not parent_df or not parent_df.options:
		return None

	child_df = frappe.get_meta(parent_df.options).get_field(child_field)
	return child_df.fieldtype if child_df else None


def match_condition(doc, row, meta=None) -> bool:
	"""Một dòng điều kiện đúng với chứng từ này không."""
	meta = meta or frappe.get_meta(doc.get("doctype"))
	fieldtype = _fieldtype(meta, row.fieldname)
	table, child_field = split_fieldname(row.fieldname)

	if not table:
		return compare(doc.get(child_field), row.operator, row.value, fieldtype)

	rows = doc.get(table) or []
	return any(
		compare(
			(child if isinstance(child, dict) else child.as_dict()).get(child_field),
			row.operator,
			row.value,
			fieldtype,
		)
		for child in rows
	)


def match(point, doc) -> bool:
	"""Chứng từ có thoả bảng điều kiện của điểm không."""
	rows = point.get("conditions") or []
	if not rows:
		return True

	data = doc if isinstance(doc, dict) else doc.as_dict()
	meta = frappe.get_meta(data.get("doctype"))

	results = []
	for row in rows:
		try:
			results.append(match_condition(data, row, meta))
		except Exception:
			frappe.log_error(
				title="Supply Notification: điều kiện không đánh giá được",
				message=f"{point.get('name')} · {row.fieldname} {row.operator} {row.value}\n\n"
				f"{frappe.get_traceback()}",
			)
			results.append(False)

	if (point.get("condition_logic") or LOGIC_AND) == LOGIC_OR:
		return any(results)
	return all(results)


def to_filters(point) -> dict:
	"""Phần điều kiện đẩy được xuống SQL — chỉ khi nối VÀ và không ở bảng con.

	Bộ nhắc theo ngày quét cả DocType nên lọc sẵn trong truy vấn là đáng; phần
	còn lại (bảng con, nối HOẶC) vẫn do `match` lo sau khi nạp chứng từ.
	"""
	if (point.get("condition_logic") or LOGIC_AND) == LOGIC_OR:
		return {}

	meta = frappe.get_meta(point.reference_doctype)
	filters = {}

	for row in point.get("conditions") or []:
		table, fieldname = split_fieldname(row.fieldname)
		if table or not meta.has_field(fieldname):
			continue

		fieldtype = _fieldtype(meta, fieldname)

		if row.operator == IS_SET:
			filters[fieldname] = ("is", "set")
		elif row.operator == IS_NOT_SET:
			filters[fieldname] = ("is", "not set")
		elif row.operator in (IN, NOT_IN):
			filters[fieldname] = (FILTER_OPERATORS[row.operator], split_values(row.value))
		elif row.operator == CONTAINS:
			filters[fieldname] = ("like", f"%{row.value or ''}%")
		elif row.operator in FILTER_OPERATORS:
			value = flt(row.value) if fieldtype in NUMERIC_FIELDTYPES else row.value
			filters[fieldname] = (FILTER_OPERATORS[row.operator], value)

	return filters
