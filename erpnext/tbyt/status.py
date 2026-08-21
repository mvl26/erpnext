# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Trạng thái hồ sơ pháp lý của một Item và bảng hiển thị trên form.

Thứ tự ưu tiên là hợp đồng của module này: nặng nhất trước. Số lưu hành hết
hiệu lực đè mọi thứ khác vì đó là sự kiện tuân thủ nặng nhất — hàng không còn
cơ sở pháp lý để lưu thông, dù hồ sơ giấy tờ có đủ tới đâu.
"""

import frappe
from frappe.utils import cint

from erpnext.tbyt.constants import (
	AUTH_STATUS_EXPIRED,
	AUTH_STATUS_PENDING,
	AUTH_STATUS_REVOKED,
	DOC_STATUS_EXPIRED,
	DOC_STATUS_EXPIRING,
	ITEM_STATUS_AUTH_INVALID,
	ITEM_STATUS_AUTH_PENDING,
	ITEM_STATUS_EXPIRED,
	ITEM_STATUS_EXPIRING,
	ITEM_STATUS_MISSING,
	ITEM_STATUS_OK,
)
from erpnext.tbyt.resolver import get_item_documents


def get_item_status(
	item_code: str, item: dict | None = None, documents: list[dict] | None = None
) -> str | None:
	"""Trả về một giá trị ITEM_STATUS_*, hoặc None nếu không phải hàng y tế.

	`documents` cho người gọi đã phân giải sẵn bộ chứng từ truyền lại vào đây thay
	vì bắt phân giải lần hai — mỗi lần phân giải tốn khoảng trăm truy vấn.

	Bộ chứng từ RỖNG của một mặt hàng y tế nghĩa là HỎNG, không phải ĐỦ. Resolver
	chỉ trả rỗng khi có gì đó gãy về cấu trúc: số lưu hành đọc không ra, số lưu
	hành chưa có phân loại, hay danh mục 23 loại chứng từ vắng mặt. Mọi `any(...)`
	trên danh sách rỗng đều False, nên rơi thẳng xuống cuối hàm là mặt hàng báo
	"đủ hồ sơ" đúng lúc không còn gì để đối chiếu — chính là lời nói dối nguy
	hiểm nhất mà cơ chế kiểm soát này có thể mắc.
	"""
	if item is None:
		item = frappe.db.get_value(
			"Item", item_code, ["name", "la_thiet_bi_y_te", "so_luu_hanh"], as_dict=True
		)
	if not item or not cint(item.get("la_thiet_bi_y_te")):
		return None

	if not item.get("so_luu_hanh"):
		return ITEM_STATUS_AUTH_PENDING

	auth = frappe.db.get_value(
		"TBYT Marketing Authorization", item["so_luu_hanh"], ["name", "trang_thai"], as_dict=True
	)
	if not auth:
		# Link treo: số lưu hành đã bị xoá (ignore_links, dọn dữ liệu, Transaction
		# Deletion Record) mà Item vẫn trỏ tới. Không bắt ở đây thì không nhánh nào
		# khớp và mặt hàng trôi xuống cuối hàm thành "đủ hồ sơ mặt hàng".
		return ITEM_STATUS_AUTH_INVALID
	if auth.trang_thai in (AUTH_STATUS_EXPIRED, AUTH_STATUS_REVOKED):
		return ITEM_STATUS_AUTH_INVALID
	if auth.trang_thai == AUTH_STATUS_PENDING:
		return ITEM_STATUS_AUTH_PENDING

	rows = documents if documents is not None else get_item_documents(item_code, item=item)
	if not rows:
		return ITEM_STATUS_AUTH_INVALID

	# Chỉ chứng từ ĐANG bắt buộc mới quyết định trạng thái. BB* không thỏa điều
	# kiện thì không phải nghĩa vụ của Miyano, hết hạn cũng không đổi kết luận.
	if any(r["trang_thai"] == DOC_STATUS_EXPIRED for r in rows if r["is_required"] and r["document"]):
		return ITEM_STATUS_EXPIRED
	if any(r["is_required"] and not r["document"] for r in rows):
		return ITEM_STATUS_MISSING
	if any(r["trang_thai"] == DOC_STATUS_EXPIRING for r in rows if r["is_required"] and r["document"]):
		return ITEM_STATUS_EXPIRING
	return ITEM_STATUS_OK


def update_item_status(item_code: str) -> str | None:
	"""Ghi trạng thái xuống DB mà không đụng `modified`.

	Không dùng `doc.save()`: trạng thái là giá trị suy ra, không phải người dùng
	sửa — làm bẩn `modified` sẽ phá lịch sử sửa đổi thật của mặt hàng.
	"""
	status = get_item_status(item_code)
	frappe.db.set_value("Item", item_code, "tinh_trang_ho_so", status, update_modified=False)
	return status


@frappe.whitelist()
def get_item_dashboard(item_code: str) -> dict:
	"""Dữ liệu cho bảng hồ sơ trên form Item."""
	frappe.has_permission("Item", doc=item_code, throw=True)
	rows = get_item_documents(item_code)
	return {
		"status": get_item_status(item_code),
		"rows": rows,
		"missing": sum(1 for r in rows if r["is_required"] and not r["document"]),
	}
