# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Giá trị cố định của module Đối chiếu công nợ (status, chiều dư, nguồn tạo)."""

DOCTYPE = "Debt Reconciliation Statement"
SETTINGS = "Debt Reconciliation Settings"

# Trạng thái biên bản — điều khiển bằng code, không dùng Frappe Workflow (D20)
STATUS_DRAFT = "Nháp"
STATUS_APPROVED = "Đã duyệt"
STATUS_SENT = "Đã gửi"
STATUS_SEND_FAILED = "Lỗi gửi"
STATUS_MATCHED = "Đã đối soát khớp"
STATUS_DISPUTED = "Chênh lệch"
STATUS_CONFIRMED = "Đã xác nhận"
STATUS_CANCELLED = "Đã hủy"

# Chiều dư
DIR_DEBIT = "Dư Nợ"
DIR_CREDIT = "Dư Có"
DIR_ZERO = "Bằng 0"

# Nguồn tạo (R-g)
SOURCE_AUTO = "Tự động"
SOURCE_MANUAL = "Thủ công"

# Phản hồi đối soát
RESPONSE_NONE = "Chưa phản hồi"
RESPONSE_MATCH = "Khớp"
RESPONSE_MISMATCH = "Chưa khớp"

CONFIRM_HARD_COPY = "C1 - Bản cứng"
CONFIRM_E_SIGN = "C2 - Ký điện tử"

PRINT_FORMATS = {
	"Supplier": "BB DCCN - NCC 331",
	"Customer": "BB DCCN - KH 131",
}

EMAIL_TEMPLATE = "Biên bản đối chiếu công nợ"

MANAGER_ROLE = "Accounts Manager"
USER_ROLE = "Accounts User"


def require_manager():
	"""``frappe.only_for`` bỏ qua kiểm tra khi chạy test — kiểm role trực tiếp."""
	import frappe

	if MANAGER_ROLE not in frappe.get_roles():
		raise frappe.PermissionError(frappe._("Chỉ Accounts Manager được thực hiện thao tác này."))
