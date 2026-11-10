# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Kiểm vai trò kho — một cửa cho mọi hằng `VAI_TRO_*` của `vitri/`.

Mỗi hằng là bộ vai trò SAU go-live (không có `System Manager`: quản trị hệ thống không vận
hành kho). Trước go-live (cờ `mvl_rbac_enabled` tắt) người dùng còn giữ vai trò cũ nên
`System Manager` vẫn được thêm vào, để production không đổi hành vi khi code được nạp.
"""

import frappe

from erpnext.access.permissions.sync import is_enabled


def cho_phep(vai_tro: set[str]) -> set[str]:
	"""Bộ vai trò hiệu lực: `vai_tro` sau go-live, thêm `System Manager` khi cờ RBAC còn tắt."""
	return set(vai_tro) if is_enabled() else set(vai_tro) | {"System Manager"}


def co_quyen(vai_tro: set[str], roles: set[str] | None = None) -> bool:
	"""`True` nếu người dùng hiện tại (hoặc `roles`) có ít nhất một vai trò trong `vai_tro`."""
	return bool(cho_phep(vai_tro) & (set(frappe.get_roles()) if roles is None else roles))
