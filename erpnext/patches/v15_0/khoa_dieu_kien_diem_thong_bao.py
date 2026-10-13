# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Khoá điều kiện cho 6 điểm thông báo đang bắn rộng hơn ý nghiệp vụ.

Nền của đợt sửa này: một chứng từ trong ERPNext có thể mang nhiều nghĩa nghiệp vụ
khác nhau, mà điểm thông báo lại chỉ lọc theo loại chứng từ.

| Điểm | Đang bắn thừa cho | Thêm điều kiện |
| --- | --- | --- |
| NTF-04 | Phiếu **trả hàng** NCC | `is_return = 0` |
| NTF-05 | Hoá đơn mua **trả hàng** | `is_return = 0` |
| NTF-06 | Hoá đơn đang **tạm giữ thanh toán** | `on_hold = 0` |
| NTF-07 | Phiếu **nhận lại hàng trả** — điểm này GỬI THƯ CHO KHÁCH | `is_return = 0` |
| NTF-10 | Phiếu chi cho **nhân viên / cổ đông** | `references.reference_doctype = Purchase Invoice` |
| NTF-12 | Phiếu thu từ **nhân viên / cổ đông** | `references.reference_doctype = Sales Invoice` |

Hai dòng cuối theo quyết định PO 06/10/2026: hoá đơn mua / hoá đơn bán là chứng từ
nguồn **độc quyền** của NCC / khách (ERPNext cưỡng chế ở
`PaymentEntry.get_valid_reference_doctypes`), nên điều kiện đó tự khoá đúng đối
tượng. Phân tích đầy đủ: `docs/BA_ThongBao_PaymentEntry_20261006.md`.

Chạy lại được nhiều lần: dòng điều kiện nào đã có thì bỏ qua, và **không** đụng
tới điều kiện khác mà nghiệp vụ tự thêm.
"""

import frappe

POINT_DOCTYPE = "Supply Notification Point"

#: Giá trị **chắc chắn sai** cho từng điểm: chứng từ đó không bao giờ xuất hiện
#: trên phiếu của loại đối tác mà điểm nhắm tới (ERPNext chặn ở
#: `PaymentEntry.get_valid_reference_doctypes`), nên điểm sẽ im lặng mãi mãi.
#: Patch sửa đúng những giá trị này — gõ nhầm hoá đơn bán vào điểm chi NCC đã
#: xảy ra thật trên site ngày 06/10/2026.
IMPOSSIBLE_VALUES = {
	"NTF-10": {"Sales Invoice", "Sales Order", "Dunning"},
	"NTF-12": {"Purchase Invoice", "Purchase Order"},
}

#: {mã điểm: ((trường, toán tử, giá trị), …)}
GUARDS = {
	"NTF-04": (("is_return", "=", "0"),),
	"NTF-05": (("is_return", "=", "0"),),
	"NTF-06": (("on_hold", "=", "0"),),
	"NTF-07": (("is_return", "=", "0"),),
	"NTF-10": (("references.reference_doctype", "=", "Purchase Invoice"),),
	"NTF-12": (("references.reference_doctype", "=", "Sales Invoice"),),
}


def execute():
	if not frappe.db.exists("DocType", POINT_DOCTYPE):
		return

	changed = []
	for code, guards in GUARDS.items():
		if not frappe.db.exists(POINT_DOCTYPE, code):
			continue
		if add_guards(code, guards):
			changed.append(code)

	if changed:
		from erpnext.supply_notification import registry

		registry.clear_cache()
		frappe.logger().info(f"Supply Notification: đã khoá điều kiện cho {', '.join(changed)}")


def add_guards(code: str, guards) -> bool:
	doc = frappe.get_doc(POINT_DOCTYPE, code)
	meta = frappe.get_meta(doc.reference_doctype)
	existing = {(row.fieldname, row.operator) for row in doc.conditions}

	added = fix_impossible_values(doc, code, guards)
	for fieldname, operator, value in guards:
		if (fieldname, operator) in existing:
			continue
		if not field_exists(meta, fieldname):
			# Site khác có thể thiếu trường (phiên bản ERPNext khác, app gỡ bớt);
			# thiếu thì bỏ qua chứ không làm đứt migrate.
			continue

		doc.append("conditions", {"fieldname": fieldname, "operator": operator, "value": value})
		added = True

	if not added:
		return False

	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)
	return True


def fix_impossible_values(doc, code: str, guards) -> bool:
	"""Sửa giá trị điều kiện không bao giờ thoả được.

	Không phải "ghi đè ý nghiệp vụ": một điều kiện không bao giờ thoả thì điểm im
	lặng vĩnh viễn mà không có lỗi, không có dòng nhật ký — tệ hơn hẳn so với sửa.
	Chỉ sửa đúng danh sách giá trị đã biết là bất khả (`IMPOSSIBLE_VALUES`).
	"""
	impossible = IMPOSSIBLE_VALUES.get(code)
	if not impossible:
		return False

	expected = {fieldname: value for fieldname, _operator, value in guards}
	fixed = False

	for row in doc.conditions:
		if row.fieldname not in expected or row.value not in impossible:
			continue

		frappe.logger().warning(
			f"Supply Notification: {code} có điều kiện {row.fieldname} = {row.value!r}"
			f" không bao giờ thoả, sửa thành {expected[row.fieldname]!r}"
		)
		row.value = expected[row.fieldname]
		fixed = True

	return fixed


def field_exists(meta, fieldname: str) -> bool:
	from erpnext.supply_notification import conditions

	table, child_field = conditions.split_fieldname(fieldname)
	if not table:
		return meta.has_field(child_field)

	parent_df = meta.get_field(table)
	if not parent_df or not parent_df.options:
		return False

	return frappe.get_meta(parent_df.options).has_field(child_field)
