# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Đường nộp chứng từ từ mặt hàng — cửa vào hình dạng mặt hàng cho một mô hình

xoay quanh chủ thể pháp lý.

Người dùng đứng ở mặt hàng, cầm trong tay tập giấy tờ của nó. Mô hình xoay
quanh chủ thể (công ty, chủ sở hữu, số lưu hành) mới là thứ mua được tính
không-trùng-lặp. Bốn hàm ở đây suy chủ thể đích từ một mặt hàng, để nộp *từ*
mặt hàng không bao giờ biến thành gắn *vào* mặt hàng — làm khác đi là dựng lại
chính vấn đề trùng lặp mà cả thiết kế sinh ra để tránh.

Chỉ bốn loại chứng từ được đánh dấu `cho_phep_nhieu_pham_vi` mới "gắn tờ đã có"
có nghĩa (đều ở cấp Số lưu hành). Với 19 loại còn lại, hoặc mặt hàng đã có tờ
đó qua chuỗi phân giải, hoặc nó cần một tờ giấy khác — không phải tờ đang tra.
"""

import frappe
from frappe import _
from frappe.utils import cint

from erpnext.tbyt.constants import (
	SCOPE_AUTHORIZATION,
	SCOPE_BATCH,
	SCOPE_COMPANY,
	SCOPE_DOCTYPE,
	SCOPE_ITEM,
	SCOPE_OWNER,
)
from erpnext.tbyt.resolver import ITEM_SCOPES, get_item_documents
from erpnext.tbyt.status import update_item_status

AUTH_DOCTYPE = "TBYT Marketing Authorization"

# Nhãn tiếng Việt cho `scope_summary` — chỉ bốn cấp mà một Item phân giải được
# cộng cấp Lô xuất hiện thật trong dữ liệu; Transaction không có bản ghi phạm vi.
_SCOPE_COUNT_LABEL = {
	SCOPE_COMPANY: "công ty",
	SCOPE_OWNER: "hãng",
	SCOPE_AUTHORIZATION: "số lưu hành",
	SCOPE_ITEM: "mặt hàng",
	SCOPE_BATCH: "lô",
}


def _load_item_for_intake(item_code: str) -> dict | None:
	"""Mặt hàng phải là TBYT và đã có số lưu hành mới suy được chủ thể đích."""
	item = frappe.db.get_value("Item", item_code, ["name", "la_thiet_bi_y_te", "so_luu_hanh"], as_dict=True)
	if not item or not cint(item.la_thiet_bi_y_te) or not item.so_luu_hanh:
		return None
	return item


def _resolve_intake_target(item: dict, doc_type: dict, document_key: str) -> dict | None:
	"""Suy `(mặt hàng, loại chứng từ) -> chủ thể phải gắn vào`, theo §5.5 đặc tả.

	Trả None khi cấp không suy được từ một mặt hàng (Batch, Transaction) — cấp Lô
	nằm ngoài phạm vi tính năng này vì một mặt hàng có thể có nhiều lô.
	"""
	scope_level = doc_type.scope_level
	if scope_level not in ITEM_SCOPES:
		return None

	scope_doctype = SCOPE_DOCTYPE[scope_level]

	if scope_level == SCOPE_COMPANY:
		import erpnext

		company = erpnext.get_default_company()
		if not company:
			return None
		scope_name = company
		scope_label = f"Công ty {company}"
		explain = f"Tờ này sẽ gắn vào Công ty {company} — mọi mặt hàng TBYT đều dùng chung."
	elif scope_level == SCOPE_OWNER:
		owner = frappe.db.get_value(AUTH_DOCTYPE, item["so_luu_hanh"], "chu_so_huu")
		if not owner:
			return None
		scope_name = owner
		scope_label = f"hãng {owner}"
		explain = f"Tờ này sẽ gắn vào hãng {owner} — mọi mặt hàng của hãng đều dùng chung."
	elif scope_level == SCOPE_AUTHORIZATION:
		auth = frappe.db.get_value(AUTH_DOCTYPE, item["so_luu_hanh"], ["name", "so_luu_hanh"], as_dict=True)
		if not auth:
			return None
		scope_name = auth.name
		so_that = auth.so_luu_hanh or auth.name
		scope_label = f"số lưu hành {so_that}"
		explain = f"Tờ này sẽ gắn vào số lưu hành {so_that} — mọi mặt hàng cùng số này đều dùng chung."
	else:  # SCOPE_ITEM
		ma = item["name"]
		scope_name = ma
		scope_label = f"mặt hàng {ma}"
		explain = f"Tờ này sẽ gắn vào chính mặt hàng {ma} — không mặt hàng nào khác dùng chung được."

	return {
		"document_key": document_key,
		"document_name": doc_type.document_name,
		"scope_level": scope_level,
		"scope_doctype": scope_doctype,
		"scope_name": scope_name,
		"scope_label": scope_label,
		"explain": explain,
		"allows_multi": cint(doc_type.cho_phep_nhieu_pham_vi),
		"mac_dinh_co_thoi_han": cint(doc_type.mac_dinh_co_thoi_han),
	}


def _get_doc_type(document_key: str) -> dict | None:
	return frappe.db.get_value(
		"TBYT Document Type",
		document_key,
		["document_name", "scope_level", "cho_phep_nhieu_pham_vi", "mac_dinh_co_thoi_han"],
		as_dict=True,
	)


@frappe.whitelist()
def get_intake_context(item_code: str, document_key: str) -> dict | None:
	"""Mọi thứ hộp thoại "Nộp chứng từ" cần để tự dựng — kể cả câu dạy mô hình.

	None nếu mặt hàng không phải TBYT, chưa có số lưu hành, hoặc loại chứng từ ở
	cấp Batch/Transaction — không có gì để nộp từ mặt hàng trong các ca đó.
	"""
	frappe.has_permission("Item", doc=item_code, throw=True)

	item = _load_item_for_intake(item_code)
	if not item:
		return None

	doc_type = _get_doc_type(document_key)
	if not doc_type:
		return None

	return _resolve_intake_target(item, doc_type, document_key)


@frappe.whitelist()
def find_documents_by_so_hieu(
	so_hieu: str, item_code: str | None = None, document_key: str | None = None
) -> list[dict]:
	"""Chứng từ ĐANG HIỆU LỰC có số hiệu khớp `so_hieu` — tối đa 10, mới nhất trước.

	Chuỗi ngắn hơn 3 ký tự trả rỗng ngay, không chạm DB: gõ tới đâu tra tới đó
	(§9.3 đặc tả) nên phải rẻ, và một, hai ký tự khớp cả danh mục chẳng nói lên
	điều gì.
	"""
	if item_code:
		frappe.has_permission("Item", doc=item_code, throw=True)

	so_hieu = (so_hieu or "").strip()
	if len(so_hieu) < 3:
		return []

	rows = frappe.db.sql(
		"""
		select rd.name, rd.document_type, rd.so_hieu, rd.trang_thai, rd.scope_level
		from `tabTBYT Regulatory Document` rd
		where rd.is_active = 1
			and rd.so_hieu like %(pattern)s
		order by rd.modified desc
		limit 10
		""",
		{"pattern": f"%{so_hieu}%"},
		as_dict=True,
	)
	if not rows:
		return []

	type_meta = {}
	for doc_type in {row.document_type for row in rows}:
		type_meta[doc_type] = frappe.db.get_value(
			"TBYT Document Type", doc_type, ["document_name", "cho_phep_nhieu_pham_vi"], as_dict=True
		)

	already_by_type = {}
	if item_code:
		already_by_type = {r["document_key"]: r["document"] for r in get_item_documents(item_code)}

	results = []
	for row in rows:
		meta = type_meta.get(row.document_type) or {}
		scope_count = frappe.db.count(
			"TBYT Document Scope",
			{"parent": row.name, "parenttype": "TBYT Regulatory Document"},
		)
		label = _SCOPE_COUNT_LABEL.get(row.scope_level, "phạm vi")
		results.append(
			{
				"name": row.name,
				"document_type": row.document_type,
				"document_name": meta.get("document_name"),
				"so_hieu": row.so_hieu,
				"trang_thai": row.trang_thai,
				"scope_count": scope_count,
				"scope_summary": f"{scope_count} {label}",
				"allows_multi": cint(meta.get("cho_phep_nhieu_pham_vi")),
				"same_type": int(bool(document_key) and row.document_type == document_key),
				"already_covers_item": int(already_by_type.get(row.document_type) == row.name),
			}
		)
	return results


@frappe.whitelist()
def attach_existing_to_item(item_code: str, document_name: str) -> dict:
	"""Thêm một dòng phạm vi vào bản ghi đã có, trỏ đúng chủ thể suy từ mặt hàng.

	Chỉ có nghĩa cho bốn loại `cho_phep_nhieu_pham_vi` — controller vẫn cưỡng
	chế mọi ràng buộc khi `save()`; các kiểm tra ở đây chỉ để nói bằng tiếng
	người trước khi người dùng đâm vào lỗi thô của controller.
	"""
	frappe.has_permission("Item", doc=item_code, throw=True)
	frappe.has_permission("TBYT Regulatory Document", "write", throw=True)

	item = _load_item_for_intake(item_code)
	if not item:
		frappe.throw(_("Mặt hàng này chưa có số lưu hành, không suy được chủ thể để gắn chứng từ."))

	doc = frappe.get_doc("TBYT Regulatory Document", document_name)
	doc_type = _get_doc_type(doc.document_type)
	target = _resolve_intake_target(item, doc_type, doc.document_type) if doc_type else None
	if not target:
		frappe.throw(_("Không suy được chủ thể để gắn chứng từ này cho mặt hàng."))

	already_covered = any(
		row.scope_doctype == target["scope_doctype"] and row.scope_name == target["scope_name"]
		for row in doc.pham_vi
	)
	if already_covered:
		return {"document": doc.name, "tinh_trang_ho_so": update_item_status(item_code)}

	if not target["allows_multi"]:
		frappe.throw(
			_("Loại chứng từ {0} chỉ nhận một phạm vi, không gắn thêm được.").format(target["document_name"])
		)

	existing_owners = {
		frappe.db.get_value(AUTH_DOCTYPE, row.scope_name, "chu_so_huu")
		for row in doc.pham_vi
		if row.scope_doctype == AUTH_DOCTYPE
	}
	existing_owners.discard(None)
	target_owner = frappe.db.get_value(AUTH_DOCTYPE, target["scope_name"], "chu_so_huu")
	if existing_owners and target_owner not in existing_owners:
		frappe.throw(
			_(
				"Tờ này đang gắn cho các số lưu hành của hãng {0}. Mặt hàng này thuộc hãng "
				"{1}, không gắn chung được."
			).format(", ".join(sorted(existing_owners)), target_owner)
		)

	clash = frappe.db.sql(
		"""
		select rd.name
		from `tabTBYT Regulatory Document` rd
		inner join `tabTBYT Document Scope` sc on sc.parent = rd.name
		where rd.document_type = %(document_type)s
			and rd.is_active = 1
			and rd.name != %(name)s
			and sc.parenttype = 'TBYT Regulatory Document'
			and sc.scope_doctype = %(scope_doctype)s
			and sc.scope_name = %(scope_name)s
		limit 1
		""",
		{
			"document_type": doc.document_type,
			"name": doc.name,
			"scope_doctype": target["scope_doctype"],
			"scope_name": target["scope_name"],
		},
	)
	if clash:
		label = target["scope_label"]
		label = label[:1].upper() + label[1:]
		frappe.throw(
			_(
				"{0} đã có {1} đang hiệu lực: {2}. Nếu tờ mới thay thế tờ cũ, dùng biểu mẫu "
				"đầy đủ và khai ô Thay thế cho."
			).format(label, target["document_name"], clash[0][0])
		)

	doc.append("pham_vi", {"scope_doctype": target["scope_doctype"], "scope_name": target["scope_name"]})
	doc.save()

	return {"document": doc.name, "tinh_trang_ho_so": update_item_status(item_code)}


@frappe.whitelist()
def create_document_for_item(
	item_code: str,
	document_key: str,
	so_hieu: str | None,
	ngay_cap,
	khong_thoi_han,
	ngay_het_han=None,
	file_url: str | None = None,
) -> dict:
	"""Tạo bản ghi chứng từ mới cho mặt hàng và lưu ngay (§9.1 đặc tả).

	Suy chủ thể như `get_intake_context`, thêm đúng một dòng phạm vi, rồi để
	controller cưỡng chế mọi ràng buộc — không nhân bản logic của nó ở đây.
	"""
	frappe.has_permission("Item", doc=item_code, throw=True)

	item = _load_item_for_intake(item_code)
	if not item:
		frappe.throw(_("Mặt hàng này chưa có số lưu hành, không suy được chủ thể để gắn chứng từ."))

	doc_type = _get_doc_type(document_key)
	if not doc_type:
		frappe.throw(_("Không tìm thấy loại chứng từ {0}.").format(document_key))

	target = _resolve_intake_target(item, doc_type, document_key)
	if not target:
		frappe.throw(_("Không suy được chủ thể để gắn chứng từ này cho mặt hàng."))

	new_doc = frappe.new_doc("TBYT Regulatory Document")
	new_doc.document_type = document_key
	new_doc.append("pham_vi", {"scope_doctype": target["scope_doctype"], "scope_name": target["scope_name"]})
	new_doc.so_hieu = so_hieu
	new_doc.ngay_cap = ngay_cap
	new_doc.khong_thoi_han = cint(khong_thoi_han)
	new_doc.ngay_het_han = ngay_het_han
	new_doc.file = file_url
	new_doc.insert()

	return {"document": new_doc.name, "tinh_trang_ho_so": update_item_status(item_code)}
