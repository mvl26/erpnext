"""Trang tải bản cài app PDA — địa chỉ ngắn để gõ trên máy quét mới.

VÌ SAO LÀ TRANG WEBSITE CHỨ KHÔNG PHẢI TRANG DESK: máy PDA lúc chưa cài app thì
chưa có phiên đăng nhập nào, mà mọi trang Desk đều đòi đăng nhập. Trang quản trị
(`cai-app-pda`, nơi ĐƯA bản mới lên) mới là trang Desk — ở đây chỉ có đúng một
việc: tải xuống thứ vốn đã công khai.
"""

import frappe

no_cache = 1


def get_context(context):
	from erpnext.warehouse_operations.vitri.cai_app import _ban_moi_nhat

	context.no_header = 1
	context.no_breadcrumbs = 1
	context.ban = _ban_moi_nhat()
	return context
