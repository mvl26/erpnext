# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Quy tắc sinh mã vật tư: `[Mã nhóm]-[Mã thương hiệu]-[Mã hàng NCC]`.

Mã nhóm và mã thương hiệu là trường riêng trên danh mục (`item_group_code`,
`brand_code`), tách khỏi ID của bản ghi: ID là tên, dùng để liên kết chứng từ; mã
chỉ dùng để sinh mã vật tư. Ở chế độ quy tắc, hai mã này bắt buộc, và đã lưu thì khóa.

Mã vật tư CHẠY THEO thông tin ghép nên nó: đổi nhóm hàng, thương hiệu, NCC mặc định
hay mã hàng NCC của vật tư thì vật tư được đổi mã ngay trong lần lưu đó; đổi mã nhóm,
mã thương hiệu ở danh mục thì mọi vật tư mang mã cũ được đổi theo. Đổi mã là đổi tên
bản ghi Item, tức cập nhật mọi chứng từ đang liên kết tới nó.

Mỗi phần có độ dài tối đa (3-6-11). Nhập dài hơn thì hệ thống lấy các ký tự đầu:
mã nhóm và mã thương hiệu cắt ngay ở danh mục, mã hàng NCC cắt lúc ghép mã còn bản
nguyên văn vẫn nằm trong `supplier_part_no`.

Đặc tả: docs/ke-hoach-build-sinh-ma-vat-tu.md.

Để ở module riêng chứ không nhồi vào `item.py`: quy tắc này chỉ chạy khi Stock
Settings chọn chế độ đặt tên `RULE_MODE`, còn `item.py` là controller dùng chung
cho mọi chế độ. Bộ test core tạo Item không có thương hiệu lẫn NCC, nên mọi ràng buộc ở
đây phải đứng sau công tắc đó — bật mặc định là gãy cả bộ test.
"""

import re
import unicodedata

import frappe
from frappe import _
from frappe.model.naming import getseries
from frappe.utils import cint, cstr, get_link_to_form

RULE_MODE = "Quy tắc mã vật tư"

#: NCC không có mã hàng thì phần thứ ba là số thứ tự. Tiền tố để không lẫn với
#: mã hàng thật của NCC (quyết định D9).
SEQUENCE_PREFIX = "X"
SEQUENCE_DIGITS = 4

#: Số ký tự tối đa của mã nhóm, mã thương hiệu và phần mã hàng NCC trong mã vật tư.
GROUP_CODE_LENGTH = 3
BRAND_CODE_LENGTH = 6
PART_CODE_LENGTH = 11

#: Vị trí của mã nhóm và mã thương hiệu trong mã vật tư.
GROUP_SEGMENT = 0
BRAND_SEGMENT = 1

#: `frappe.flags` mang cờ này khi chính quy tắc đổi mã vật tư, để `guard_rename` cho qua.
SYNC_FLAG = "item_code_rule_sync"

#: Đổi mã một vật tư là cập nhật mọi bảng có liên kết tới Item — khoảng một giây ngay
#: cả trên site gần như trống. Nhiều hơn số này thì đổi ở tiến trình nền.
INLINE_RENAME_LIMIT = 20


class ItemCodeRuleError(frappe.ValidationError):
	pass


class DuplicateItemError(ItemCodeRuleError):
	pass


# --- Phạm vi ---------------------------------------------------------------


def is_rule_mode():
	return frappe.db.get_default("item_naming_by") == RULE_MODE


def in_scope(doc):
	"""Vật tư có quản lý tồn kho; không phải tài sản, mẫu hay biến thể (D4).

	Không dùng `is_purchase_item`: trường đó mặc định bật cho mọi Item, kể cả
	dịch vụ, nên không phân biệt được gì.
	"""
	return bool(
		cint(doc.get("is_stock_item"))
		and not cint(doc.get("is_fixed_asset"))
		and not cint(doc.get("has_variants"))
		and not doc.get("variant_of")
	)


def applies_to(doc):
	return is_rule_mode() and in_scope(doc)


# --- Chuẩn hóa -------------------------------------------------------------


def _alnum(value):
	"""Chỉ chữ không dấu và số, GIỮ NGUYÊN hoa/thường."""
	text = cstr(value).replace("đ", "d").replace("Đ", "D")
	text = unicodedata.normalize("NFKD", text)
	return re.sub(r"[^A-Za-z0-9]", "", text)


def code_part(value):
	"""Phần ghép vào mã: bỏ dấu và ký tự phân cách, rồi lấy tối đa `PART_CODE_LENGTH` ký tự đầu."""
	return _alnum(value)[:PART_CODE_LENGTH]


def match_key(value):
	"""Khóa so trùng: không phân biệt hoa/thường, và KHÔNG cắt.

	Hai mã hàng NCC dài chỉ giống nhau ở những ký tự đầu là hai mặt hàng khác nhau;
	so theo bản đã cắt thì chúng thành "trùng vật tư".
	"""
	return _alnum(value).upper()


def is_truncated(value):
	return len(_alnum(value)) > PART_CODE_LENGTH


def is_code(value):
	"""Chỉ chữ không dấu và số, để `-` luôn là dấu phân cách của mã vật tư."""
	return bool(re.fullmatch(r"[A-Za-z0-9]+", cstr(value)))


def _fit(value, max_length, label):
	"""Mã dài quá thì lấy các ký tự đầu, và nói cho người nhập biết mã đã bị cắt."""
	if len(value) <= max_length:
		return value
	cut = value[:max_length]
	frappe.msgprint(
		_("{0} tối đa {1} ký tự nên hệ thống lấy {1} ký tự đầu: {2} thành {3}.").format(
			label, max_length, value, frappe.bold(cut)
		),
		title=_("Mã đã được cắt ngắn"),
		indicator="orange",
	)
	return cut


def validate_component_code(doc, fieldname, label, max_length):
	value = cstr(doc.get(fieldname)).strip()
	if value and not is_code(value):
		frappe.throw(_("{0} chỉ được gồm chữ không dấu và số: {1}").format(label, value))
	doc.set(fieldname, _fit(value, max_length, label) or None)


def require_component_code(doc, fieldname, label):
	"""Ở chế độ quy tắc, nhóm hàng và thương hiệu phải có mã — lúc tạo lẫn lúc sửa.

	Không đặt `reqd` ở mức trường: nhóm hàng và thương hiệu do trình cài đặt, dữ liệu
	mẫu và bộ test core tạo ra đều không có mã. `ignore_mandatory` dành cho code tự tạo
	danh mục khung.
	"""
	if doc.get(fieldname) or doc.flags.ignore_mandatory or not is_rule_mode():
		return
	frappe.throw(
		_("{0} là bắt buộc: mã này dùng để sinh mã vật tư.").format(label),
		ItemCodeRuleError,
		title=_("Thiếu mã"),
	)


# --- Sinh mã ---------------------------------------------------------------


def set_item_code(doc):
	"""Gọi từ `Item.autoname` — lúc này các dòng `supplier_items` đã nằm trong doc."""
	group_code, brand_code = validate_on_create(doc)
	# So trùng theo thương hiệu là so chuỗi, mà DB so khớp không phân biệt hoa/thường:
	# đưa về đúng ID đã lưu trước khi so.
	doc.brand = frappe.db.get_value("Brand", doc.brand, "name")
	supplier_part_no = get_default_supplier_row(doc).supplier_part_no
	part = code_part(supplier_part_no)

	if part:
		code = _compose(group_code, brand_code, part)
		check_duplicate_item(doc, match_key(supplier_part_no))
		if frappe.db.exists("Item", code):
			_throw_code_taken(code, supplier_part_no)
		if is_truncated(supplier_part_no):
			frappe.msgprint(
				_(
					"Mã hàng NCC {0} dài hơn {1} ký tự nên mã vật tư chỉ lấy {1} ký tự đầu: {2}. Mã hàng NCC nguyên văn vẫn được giữ ở bảng Supplier Items."
				).format(supplier_part_no, PART_CODE_LENGTH, frappe.bold(code)),
				title=_("Mã đã được cắt ngắn"),
				indicator="orange",
			)
	else:
		code = _next_sequence_code(group_code, brand_code)

	doc.item_code = code
	doc.name = code
	doc.flags.item_code_from_rule = True


def _throw_code_taken(code, supplier_part_no):
	if not is_truncated(supplier_part_no):
		frappe.throw(_("Mã vật tư {0} đã tồn tại.").format(code), ItemCodeRuleError)
	frappe.throw(
		_(
			"Mã vật tư {0} đã tồn tại. Mã hàng NCC {1} dài hơn {2} ký tự nên chỉ lấy {2} ký tự đầu, và phần này trùng với vật tư đã có. Liên hệ người quản trị danh mục."
		).format(get_link_to_form("Item", code), supplier_part_no, PART_CODE_LENGTH),
		ItemCodeRuleError,
		title=_("Trùng mã vật tư"),
	)


def validate_on_create(doc):
	"""Mục 5.2, lúc tạo mới. Trả về (mã nhóm, mã thương hiệu)."""
	group_code, brand_code, missing = _component_codes(doc.item_group, doc.brand)
	if not doc.get("supplier_items"):
		missing.append(_("Chưa khai nhà cung cấp ở bảng Supplier Items"))
	if missing:
		frappe.throw(
			_("Chưa đủ thông tin để sinh mã vật tư:") + "<br>" + "<br>".join(missing),
			ItemCodeRuleError,
		)

	validate_supplier_rows(doc)
	return group_code, brand_code


def validate_supplier_rows(doc):
	"""Không trùng NCC, đúng một dòng mặc định. Dòng duy nhất thì tự đánh dấu."""
	rows = doc.get("supplier_items") or []

	seen = set()
	for row in rows:
		if row.supplier in seen:
			frappe.throw(
				_("Nhà cung cấp {0} xuất hiện ở hai dòng của bảng Supplier Items.").format(row.supplier),
				ItemCodeRuleError,
			)
		seen.add(row.supplier)

	defaults = [row for row in rows if cint(row.is_default)]
	if len(rows) == 1 and not defaults:
		rows[0].is_default = 1
		return
	if len(defaults) != 1:
		frappe.throw(
			_("Phải có đúng một dòng được đánh dấu NCC mặc định, đang có {0} dòng.").format(len(defaults)),
			ItemCodeRuleError,
		)


def get_default_supplier_row(doc):
	for row in doc.get("supplier_items") or []:
		if cint(row.is_default):
			return row
	return None


def _component_codes(item_group, brand):
	missing = []
	group_code = brand_code = None

	if not item_group:
		missing.append(_("Chưa chọn Nhóm hàng (Item Group)"))
	else:
		group_code = frappe.db.get_value("Item Group", item_group, "item_group_code")
		if not group_code:
			missing.append(
				_("Nhóm hàng (Item Group) {0} chưa có Mã nhóm (Item Group Code)").format(item_group)
			)
		elif len(group_code) > GROUP_CODE_LENGTH:
			missing.append(
				_(
					"Mã nhóm (Item Group Code) {0} của Nhóm hàng (Item Group) {1} dài hơn {2} ký tự — sửa lại Mã nhóm"
				).format(group_code, item_group, GROUP_CODE_LENGTH)
			)
			group_code = None

	if not brand:
		missing.append(_("Chưa chọn Thương hiệu (Brand)"))
	else:
		brand_code = frappe.db.get_value("Brand", brand, "brand_code")
		if not brand_code:
			missing.append(_("Thương hiệu (Brand) {0} chưa có Mã thương hiệu (Brand Code)").format(brand))
		elif len(brand_code) > BRAND_CODE_LENGTH:
			missing.append(
				_(
					"Mã thương hiệu (Brand Code) {0} của Thương hiệu (Brand) {1} dài hơn {2} ký tự — sửa lại Mã thương hiệu"
				).format(brand_code, brand, BRAND_CODE_LENGTH)
			)
			brand_code = None

	return group_code, brand_code, missing


def _compose(group_code, brand_code, part):
	return f"{group_code}-{brand_code}-{part}"


def _sequence_key(group_code, brand_code):
	return _compose(group_code, brand_code, SEQUENCE_PREFIX)


def _next_sequence_code(group_code, brand_code):
	key = _sequence_key(group_code, brand_code)
	while True:
		code = key + getseries(key, SEQUENCE_DIGITS)
		# NCC có thể đặt mã hàng thật trùng dạng X0001 — bỏ qua số đã có chủ.
		if not frappe.db.exists("Item", code):
			return code


def _peek_sequence_code(group_code, brand_code):
	"""Số thứ tự kế tiếp, KHÔNG tiêu số — dùng cho "Mã dự kiến" trên form."""
	key = _sequence_key(group_code, brand_code)
	series = frappe.qb.DocType("Series")
	current = frappe.qb.from_(series).where(series.name == key).select(series.current).run()
	number = cint(current[0][0]) if current else 0
	while True:
		number += 1
		code = f"{key}{number:0{SEQUENCE_DIGITS}d}"
		if not frappe.db.exists("Item", code):
			return code


# --- Sau khi đã có mã: mã chạy theo thông tin của vật tư -------------------


def validate_item(doc):
	"""Gọi từ `Item.validate`, sau khi Item Defaults đã được điền."""
	set_supplier_part_no_keys(doc)
	set_by_rule_mark(doc)
	doc.flags.item_code_target = None
	if not applies_to(doc):
		return

	if doc.get("supplier_items"):
		validate_supplier_rows(doc)
	if not doc.is_new():
		plan_code_change(doc)


def set_by_rule_mark(doc):
	"""`item_code_by_rule` đánh dấu mã do quy tắc sinh; chỉ những mã này mới chạy theo thông tin.

	Nhìn hình dạng mã thì không đủ: mã đặt tay kiểu `TB-001-A` cũng có ba phần.
	Người dùng không tự bật, tắt dấu này được.
	"""
	if doc.is_new():
		doc.item_code_by_rule = 1 if doc.flags.get("item_code_from_rule") else 0
	else:
		doc.item_code_by_rule = cint(frappe.db.get_value("Item", doc.name, "item_code_by_rule"))


def plan_code_change(doc):
	"""Tính mã theo thông tin hiện tại và kiểm tra; `apply_code_change` mới đổi thật.

	Tách hai bước vì đổi mã là đổi tên bản ghi: phải làm sau khi lần lưu này đã ghi
	xong, còn mọi lý do từ chối thì phải báo trước khi ghi. Tính lại ở mọi lần lưu
	chứ không chỉ khi thông tin vừa đổi, để vật tư đang lệch tự về đúng mã.
	"""
	if not cint(doc.item_code_by_rule):
		before = doc.get_doc_before_save()
		if before and _code_inputs(before) != _code_inputs(doc):
			# Mã đặt tay (có từ trước quy tắc, hoặc đã được đổi tay): không đụng tới.
			frappe.msgprint(
				_("Mã vật tư {0} là mã đặt tay, không do quy tắc sinh, nên giữ nguyên.").format(
					frappe.bold(doc.name)
				),
				title=_("Mã vật tư giữ nguyên"),
				indicator="orange",
			)
		return

	group_code, brand_code = validate_on_create(doc)
	doc.brand = frappe.db.get_value("Brand", doc.brand, "name")
	supplier_part_no = get_default_supplier_row(doc).supplier_part_no
	target = _target_code(doc.name, group_code, brand_code, supplier_part_no)
	if target == doc.name:
		return

	if code_part(supplier_part_no):
		check_duplicate_item(doc, match_key(supplier_part_no))
		if _taken_by_another(target, doc.name):
			_throw_code_taken(target, supplier_part_no)
	doc.flags.item_code_target = target


def apply_code_change(doc):
	"""Gọi ở cuối `Item.on_update`: đổi mã vật tư sang mã đã tính ở `plan_code_change`."""
	target = doc.flags.pop("item_code_target", None)
	if not target or target == doc.name:
		return

	old = doc.name
	rename_item(old, target)

	saving = frappe.flags.currently_saving or []
	if (doc.doctype, old) in saving:
		saving.remove((doc.doctype, old))
	doc.name = target
	doc.reload()
	# Form nhận `localname` y như lúc bản ghi mới được cấp tên: bỏ bản cũ, chuyển sang mã mới.
	doc.localname = old

	message = _("Mã vật tư đã đổi từ {0} thành {1} theo thông tin mới.").format(
		frappe.bold(old), frappe.bold(target)
	)
	supplier_part_no = get_default_supplier_row(doc).supplier_part_no
	if is_truncated(supplier_part_no):
		message += " " + _("Mã hàng NCC dài hơn {0} ký tự nên chỉ lấy {0} ký tự đầu.").format(
			PART_CODE_LENGTH
		)
	frappe.msgprint(message, title=_("Mã vật tư đã đổi"), indicator="blue")


def rename_item(old, new, rebuild_search=True):
	"""Đổi mã một vật tư thay mặt quy tắc, bất kể người đang thao tác có quyền đổi tên hay không."""
	# Bản rút gọn `frappe.rename_doc` không nhận `ignore_permissions`.
	from frappe.model.rename_doc import rename_doc

	frappe.flags[SYNC_FLAG] = True
	try:
		rename_doc(
			"Item",
			old,
			new,
			force=True,
			ignore_permissions=True,
			show_alert=False,
			rebuild_search=rebuild_search,
		)
	finally:
		frappe.flags[SYNC_FLAG] = False


def after_item_rename(new, merge):
	"""Gọi từ `Item.after_rename`. Mã do người dùng đổi tay thì thôi không chạy theo thông tin nữa.

	Đây là lối thoát cho ca quy tắc không cho ra mã dùng được (ví dụ hai mã hàng NCC
	dài trùng nhau ở những ký tự đầu). Không có nó thì lần lưu sau sẽ đổi mã ngược lại.
	"""
	if not merge and not frappe.flags.get(SYNC_FLAG):
		frappe.db.set_value("Item", new, "item_code_by_rule", 0, update_modified=False)


def _target_code(current, group_code, brand_code, supplier_part_no, peek=False):
	part = code_part(supplier_part_no)
	if part:
		return _compose(group_code, brand_code, part)
	# NCC không có mã hàng: vẫn cùng nhóm, cùng thương hiệu thì giữ số thứ tự đang có.
	if re.fullmatch(re.escape(_sequence_key(group_code, brand_code)) + rf"\d{{{SEQUENCE_DIGITS}}}", current):
		return current
	return (_peek_sequence_code if peek else _next_sequence_code)(group_code, brand_code)


def _taken_by_another(code, item_code):
	"""`code` đang là mã của một vật tư khác. DB so khớp không phân biệt hoa/thường."""
	holder = frappe.db.get_value("Item", code, "name")
	return bool(holder) and holder != item_code


def set_supplier_part_no_keys(doc):
	"""Điền ở mọi chế độ: bật quy tắc sau này thì dòng cũ đã có sẵn khóa để so trùng."""
	for row in doc.get("supplier_items") or []:
		row.supplier_part_no_key = match_key(row.supplier_part_no) or None


def _code_inputs(doc):
	row = get_default_supplier_row(doc)
	return (
		doc.item_group,
		doc.brand,
		row.supplier if row else None,
		code_part(row.supplier_part_no) if row else "",
	)


def guard_rename(doc):
	"""Gọi từ `Item.before_rename` — hàm đó xử lý cả đổi tên lẫn gộp mã."""
	if frappe.flags.get(SYNC_FLAG) or not applies_to(doc) or _may_rename():
		return
	frappe.throw(
		_(
			"Bạn không có quyền đổi mã hoặc gộp mã vật tư {0}. Mã vật tư do hệ thống sinh và tự đổi theo nhóm hàng, thương hiệu, mã hàng NCC; liên hệ người quản trị danh mục."
		).format(frappe.bold(doc.name)),
		ItemCodeRuleError,
	)


@frappe.whitelist()
def may_change_codes():
	"""Form Nhóm hàng, Thương hiệu hỏi: người này có được mở khóa ô mã không."""
	return _may_rename()


def _may_rename():
	"""Người được đổi mã vật tư — cũng là người được đổi các thành phần đã ghép vào mã."""
	if frappe.session.user == "Administrator":
		return True
	roles = frappe.get_roles()
	if "System Manager" in roles:
		return True
	role = frappe.db.get_single_value("Stock Settings", "item_rename_role")
	return bool(role and role in roles)


# --- Mã nhóm, mã thương hiệu đổi thì vật tư đổi mã theo ----------------------
#
# Mã ở danh mục đã lưu thì khóa: sửa nó là đổi mã hàng loạt vật tư, nên chỉ người
# được đổi mã vật tư mới làm được. Khi họ sửa, hoặc gộp hai bản ghi mang mã khác
# nhau, mọi vật tư đang mang mã cũ được đổi mã theo. Vật tư mà mã không theo dạng
# ba phần của quy tắc thì không bị đụng tới.


def guard_item_group_code(doc):
	"""Gọi từ `ItemGroup.validate`."""
	_guard_code_change(doc, "item_group_code", "item_group", GROUP_SEGMENT, _("Mã nhóm (Item Group Code)"))


def guard_brand_code(doc):
	"""Gọi từ `Brand.validate`."""
	_guard_code_change(doc, "brand_code", "brand", BRAND_SEGMENT, _("Mã thương hiệu (Brand Code)"))


def guard_item_group_merge(old, new, merge):
	"""Gọi từ `ItemGroup.before_rename`."""
	_guard_merge(
		"Item Group",
		"item_group_code",
		"item_group",
		GROUP_SEGMENT,
		_("Nhóm hàng (Item Group)"),
		old,
		new,
		merge,
	)


def guard_brand_merge(old, new, merge):
	"""Gọi từ `Brand.before_rename`."""
	_guard_merge("Brand", "brand_code", "brand", BRAND_SEGMENT, _("Thương hiệu (Brand)"), old, new, merge)


def apply_cascade(doc):
	"""Gọi từ `on_update` của Item Group, Brand: đổi mã các vật tư đã lên kế hoạch lúc validate."""
	_run_cascade(doc.flags.pop("item_code_cascade", None))


def apply_merge_cascade(merge):
	"""Gọi từ `after_rename` của Item Group, Brand."""
	plan = frappe.flags.pop("item_code_merge_plan", None)
	if merge:
		_run_cascade(plan)


def _guard_code_change(doc, fieldname, item_field, segment, label):
	"""Mã đã lưu thì khóa, kể cả khi chưa vật tư nào dùng.

	Chờ tới lúc có vật tư mới khóa thì mã vẫn đổi được đúng vào quãng người ta đang
	in bảng mã, soạn file nhập. Người được đổi mã vật tư thì sửa được, và vật tư đổi theo.
	"""
	doc.flags.item_code_cascade = None
	if doc.is_new() or not is_rule_mode():
		return
	old = frappe.db.get_value(doc.doctype, doc.name, fieldname)
	new = doc.get(fieldname)
	if not old or old == new:
		return

	items = _items_carrying(item_field, doc.name, segment, old)
	if not _may_rename():
		in_use = " " + _("{0} vật tư đang mang mã này trong mã vật tư.").format(len(items)) if items else ""
		frappe.throw(
			_("{0} {1} không sửa được sau khi đã lưu.").format(label, frappe.bold(old))
			+ in_use
			+ " "
			+ _("Liên hệ người quản trị danh mục."),
			ItemCodeRuleError,
			title=_("Mã đã khóa"),
		)
	doc.flags.item_code_cascade = _plan_cascade(items, segment, new)


def _guard_merge(doctype, fieldname, item_field, segment, label, old, new, merge):
	"""Đổi tên danh mục thì mã vẫn vậy; gộp vào bản ghi mang mã khác thì vật tư phải đổi mã."""
	frappe.flags.item_code_merge_plan = None
	if not merge or not is_rule_mode():
		return
	old_code = frappe.db.get_value(doctype, old, fieldname)
	new_code = frappe.db.get_value(doctype, new, fieldname)
	if not old_code or old_code == new_code:
		return
	items = _items_carrying(item_field, old, segment, old_code)
	if not items:
		return

	examples = ", ".join(get_link_to_form("Item", name) for name in items[:3])
	if not _may_rename():
		frappe.throw(
			_(
				"Không gộp được {0} {1}: {2} vật tư đang mang mã này trong mã vật tư, ví dụ {3}. Liên hệ người quản trị danh mục."
			).format(label, frappe.bold(old), len(items), examples),
			ItemCodeRuleError,
			title=_("Mã đang được dùng"),
		)
	if not new_code:
		frappe.throw(
			_("Không gộp được {0} {1} vào {2}: bản ghi đích chưa có mã để đổi mã {3} vật tư theo.").format(
				label, frappe.bold(old), frappe.bold(new), len(items)
			),
			ItemCodeRuleError,
		)
	frappe.flags.item_code_merge_plan = _plan_cascade(items, segment, new_code)


def _plan_cascade(items, segment, new_code):
	"""{mã cũ: mã mới} cho các vật tư phải đổi mã. Từ chối cả lượt nếu có mã mới đụng mã đã có.

	Kiểm trước, đổi sau: đổi được nửa chừng rồi vấp một mã trùng thì danh mục và
	vật tư lệch nhau đúng kiểu mà việc đổi theo này sinh ra để tránh.
	"""
	plan = {}
	planned = set()
	blocked = []
	for name in items:
		parts = name.split("-")
		parts[segment] = new_code
		target = "-".join(parts)
		if _taken_by_another(target, name) or target.lower() in planned:
			if not re.fullmatch(rf"{SEQUENCE_PREFIX}\d{{{SEQUENCE_DIGITS}}}", parts[2]):
				blocked.append((name, target))
				continue
			# Số thứ tự thì không mang nghĩa gì: đụng nhau thì cấp số kế tiếp ở cặp mới.
			target = _next_sequence_code(parts[0], parts[1])
			while target.lower() in planned:
				target = _next_sequence_code(parts[0], parts[1])
		plan[name] = target
		planned.add(target.lower())

	if blocked:
		examples = ", ".join(f"{old} → {get_link_to_form('Item', new)}" for old, new in blocked[:3])
		frappe.throw(
			_("Không đổi được mã: {0} vật tư sẽ trùng với mã vật tư đã có, ví dụ {1}.").format(
				len(blocked), examples
			),
			ItemCodeRuleError,
			title=_("Trùng mã vật tư"),
		)
	return plan


def _run_cascade(plan):
	if not plan:
		return
	old, new = next(iter(plan.items()))
	example = _("ví dụ {0} thành {1}").format(frappe.bold(old), frappe.bold(new))
	if len(plan) <= INLINE_RENAME_LIMIT:
		rename_items(plan)
		frappe.msgprint(
			_("Đã đổi mã {0} vật tư theo mã mới, {1}.").format(len(plan), example),
			title=_("Mã vật tư đã đổi"),
			indicator="blue",
		)
		return

	frappe.enqueue(
		"erpnext.stock.item_code_rule.rename_items",
		queue="long",
		timeout=600 + 15 * len(plan),
		enqueue_after_commit=True,
		plan=plan,
		in_background=True,
	)
	frappe.msgprint(
		_(
			"{0} vật tư đang được đổi mã ở chế độ nền, {1}. Việc này có thể mất nhiều phút; trong lúc đó một số vật tư còn mang mã cũ."
		).format(len(plan), example),
		title=_("Đang đổi mã vật tư"),
		indicator="orange",
	)


def rename_items(plan, in_background=False):
	"""Đổi mã lần lượt theo `plan`.

	Trong lần lưu của người dùng thì lỗi nào cũng làm hỏng cả lần lưu (rollback
	hết). Ở tiến trình nền thì chốt từng vật tư một, vật tư lỗi được ghi lại và bỏ qua.
	"""
	failed = []
	for old, new in plan.items():
		try:
			rename_item(old, new, rebuild_search=False)
		except Exception:
			if not in_background:
				raise
			frappe.db.rollback()
			failed.append(old)
			frappe.log_error(title=_("Đổi mã vật tư {0} thành {1} thất bại").format(old, new))
		if in_background:
			frappe.db.commit()

	frappe.enqueue(
		"frappe.utils.global_search.rebuild_for_doctype", doctype="Item", enqueue_after_commit=True
	)
	if in_background:
		summary = _("Đã đổi mã {0} vật tư theo mã mới.").format(len(plan) - len(failed))
		if failed:
			summary += " " + _("{0} vật tư chưa đổi được, xem Error Log: {1}.").format(
				len(failed), ", ".join(failed[:10])
			)
		frappe.publish_realtime("msgprint", summary, user=frappe.session.user)
	return failed


def _items_carrying(fieldname, value, segment, code):
	names = frappe.get_all(
		"Item", filters={fieldname: value, "item_code_by_rule": 1}, pluck="name", order_by="name"
	)
	return [name for name in names if _segment(name, segment) == code]


def _segment(item_code, index):
	"""Một phần của mã vật tư, hoặc None nếu mã không theo dạng ba phần của quy tắc."""
	parts = cstr(item_code).split("-")
	return parts[index] if len(parts) == 3 else None


# --- Phát hiện vật tư đã có -------------------------------------------------


def check_duplicate_item(doc, key):
	"""Cùng thương hiệu + cùng mã hàng NCC thì chặn; khác thương hiệu thì chỉ cảnh báo.

	Cảnh báo không chặn và không hỏi lại, nên form, Data Import và API cho cùng
	một kết quả.
	"""
	# Lúc sửa, chính vật tư này cũng đang giữ mã hàng NCC đó.
	rows = [row for row in _items_with_supplier_key(key) if row.item_code != doc.name]
	exact, similar = _split_by_brand(rows, doc.brand)

	if exact:
		frappe.throw(
			_("Vật tư đã có trong hệ thống: {0}. Cùng thương hiệu (Brand) và cùng mã hàng NCC.").format(
				_links(exact)
			),
			DuplicateItemError,
			title=_("Trùng vật tư"),
		)
	if similar:
		frappe.msgprint(
			_(
				"Mã hàng NCC này đã có ở vật tư thuộc thương hiệu (Brand) khác: {0}. Kiểm tra xem có trùng vật tư không."
			).format(_links(similar)),
			title=_("Có thể trùng vật tư"),
			indicator="orange",
		)


@frappe.whitelist()
def preview_item_code(item_group=None, brand=None, supplier_part_no=None, item_code=None):
	"""Mã dự kiến cho form, kèm các vật tư đang dùng cùng mã hàng NCC.

	`item_code` là mã hiện tại khi đang sửa vật tư đã có: form hỏi mã sẽ đổi thành gì.
	Không tiêu số thứ tự. `similar` có cả khi chưa đủ thông tin để ghép mã:
	người dùng nên biết về vật tư trùng ngay từ lúc gõ mã hàng NCC.
	"""
	frappe.has_permission("Item", "read", throw=True)

	part = code_part(supplier_part_no)
	similar = [
		row for row in _items_with_supplier_key(match_key(supplier_part_no)) if row.item_code != item_code
	]
	for row in similar:
		row.same_brand = bool(brand) and row.brand == brand
	preview = {
		"code": None,
		"missing": [],
		"from_sequence": False,
		"similar": similar,
		# Mã hàng NCC dài quá: form nói rõ mã chỉ lấy `part_length` ký tự đầu.
		"truncated": is_truncated(supplier_part_no),
		"part_length": PART_CODE_LENGTH,
		# Mã sau khi cắt đã có vật tư khác dùng: lưu sẽ bị chặn.
		"taken": False,
	}

	group_code, brand_code, preview["missing"] = _component_codes(item_group, brand)
	if preview["missing"]:
		return preview

	preview["from_sequence"] = not part
	if item_code:
		preview["code"] = _target_code(item_code, group_code, brand_code, supplier_part_no, peek=True)
	elif part:
		preview["code"] = _compose(group_code, brand_code, part)
	else:
		preview["code"] = _peek_sequence_code(group_code, brand_code)
	if part:
		preview["taken"] = _taken_by_another(preview["code"], item_code)
	return preview


def warn_duplicate_manufacturer_part_no(doc):
	"""Gọi từ `ItemManufacturer.validate`.

	Mã hàng của nhà sản xuất chỉ khai được sau khi Item đã có, nên phép so này không
	chạy được lúc tạo Item — chỉ cảnh báo ở đây và ở màn hình tra cứu.
	"""
	if not is_rule_mode():
		return
	others = [
		row
		for row in _items_with_manufacturer_key(match_key(doc.manufacturer_part_no))
		if row.item_code != doc.item_code
	]
	if others:
		frappe.msgprint(
			_(
				"Mã hàng của nhà sản xuất (Manufacturer Part Number) {0} đã khai cho vật tư khác: {1}. Kiểm tra xem có trùng vật tư không."
			).format(frappe.bold(doc.manufacturer_part_no), _links(others)),
			title=_("Có thể trùng vật tư"),
			indicator="orange",
		)


def _items_with_supplier_key(key):
	if not key:
		return []
	supplier_row = frappe.qb.DocType("Item Supplier")
	item = frappe.qb.DocType("Item")
	return (
		frappe.qb.from_(supplier_row)
		.inner_join(item)
		.on(item.name == supplier_row.parent)
		.where((supplier_row.parenttype == "Item") & (supplier_row.supplier_part_no_key == key))
		.select(item.name.as_("item_code"), item.item_name, item.brand)
		.distinct()
		.run(as_dict=True)
	)


def _items_with_manufacturer_key(key):
	if not key:
		return []
	matches = {}
	for row in frappe.get_all(
		"Item Manufacturer", fields=["item_code", "item_name", "manufacturer_part_no"], order_by="creation"
	):
		if match_key(row.manufacturer_part_no) == key:
			matches.setdefault(row.item_code, row)
	for row in matches.values():
		row.brand = frappe.db.get_value("Item", row.item_code, "brand")
		row.pop("manufacturer_part_no")
	return list(matches.values())


def _split_by_brand(rows, brand):
	exact = [row for row in rows if row.brand == brand]
	other = [row for row in rows if row.brand != brand]
	return exact, other


def _links(rows):
	return ", ".join(get_link_to_form("Item", row.item_code) for row in rows)


# --- Dữ liệu cũ ------------------------------------------------------------


def backfill_default_supplier_rows():
	"""Đánh dấu NCC mặc định cho Item có từ trước, điền khóa so khớp còn thiếu.

	Trả về mã các Item không tự xác định được — nhiều dòng NCC mà
	`default_supplier` không chỉ ra đúng một dòng. Báo cáo "Vat Tu Chua Co NCC
	Mac Dinh" liệt kê lại chúng bất cứ lúc nào.
	"""
	rows_by_item = {}
	for row in frappe.get_all(
		"Item Supplier",
		filters={"parenttype": "Item"},
		fields=["name", "parent", "supplier", "supplier_part_no", "supplier_part_no_key", "is_default"],
		order_by="parent, idx",
	):
		key = match_key(row.supplier_part_no) or None
		if (row.supplier_part_no_key or None) != key:
			frappe.db.set_value("Item Supplier", row.name, "supplier_part_no_key", key, update_modified=False)
		rows_by_item.setdefault(row.parent, []).append(row)

	unresolved = []
	for item_code, rows in rows_by_item.items():
		if any(cint(row.is_default) for row in rows):
			continue
		target = _row_to_mark_default(item_code, rows)
		if target:
			frappe.db.set_value("Item Supplier", target.name, "is_default", 1, update_modified=False)
		else:
			unresolved.append(item_code)
	return unresolved


def _row_to_mark_default(item_code, rows):
	if len(rows) == 1:
		return rows[0]
	default_suppliers = set(
		frappe.get_all(
			"Item Default",
			filters={"parent": item_code, "parenttype": "Item", "default_supplier": ("is", "set")},
			pluck="default_supplier",
		)
	)
	matches = [row for row in rows if row.supplier in default_suppliers]
	return matches[0] if len(matches) == 1 else None
