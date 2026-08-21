# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Hằng số dùng chung của hồ sơ pháp lý TBYT.

Gom vào một chỗ vì cả resolver, validate, job hết hạn và report đều đọc chúng —
để rải rác thì sửa một chỗ quên chỗ khác.
"""

# --- Cấp phạm vi: tờ giấy nói về chủ thể nào ---
SCOPE_COMPANY = "Company"
SCOPE_OWNER = "Owner"
SCOPE_AUTHORIZATION = "Authorization"
SCOPE_BATCH = "Batch"
SCOPE_ITEM = "Item"
SCOPE_TRANSACTION = "Transaction"

SCOPE_LEVELS = (
	SCOPE_COMPANY,
	SCOPE_OWNER,
	SCOPE_AUTHORIZATION,
	SCOPE_BATCH,
	SCOPE_ITEM,
	SCOPE_TRANSACTION,
)

# Ánh xạ cấp phạm vi sang DocType thật. `Transaction` không có mặt: hồ sơ phân
# phối dùng đính kèm sẵn có của Delivery Note / Sales Invoice, ngoài phạm vi.
SCOPE_DOCTYPE = {
	SCOPE_COMPANY: "Company",
	SCOPE_OWNER: "Manufacturer",
	SCOPE_AUTHORIZATION: "TBYT Marketing Authorization",
	SCOPE_BATCH: "Batch",
	SCOPE_ITEM: "Item",
}

# --- Mức bắt buộc theo ma trận Thông tư ---
LEVEL_BB = "BB"
LEVEL_BB_STAR = "BB*"
LEVEL_NC = "NC"
LEVEL_TH = "TH"
LEVEL_NA = "KHONG_AP_DUNG"

LEVELS = (LEVEL_BB, LEVEL_BB_STAR, LEVEL_NC, LEVEL_TH, LEVEL_NA)

DEVICE_CLASSES = ("A", "B", "C", "D")

# --- Trạng thái số lưu hành ---
AUTH_STATUS_PENDING = "Đang đăng ký"
AUTH_STATUS_VALID = "Còn hiệu lực"
AUTH_STATUS_EXPIRED = "Hết hiệu lực"
AUTH_STATUS_REVOKED = "Bị thu hồi"

AUTH_STATUSES = (
	AUTH_STATUS_PENDING,
	AUTH_STATUS_VALID,
	AUTH_STATUS_EXPIRED,
	AUTH_STATUS_REVOKED,
)

# --- Trạng thái từng chứng từ ---
DOC_STATUS_VALID = "Còn hiệu lực"
DOC_STATUS_EXPIRING = "Sắp hết hạn"
DOC_STATUS_EXPIRED = "Hết hạn"
DOC_STATUS_SUPERSEDED = "Đã thay thế"

DOC_STATUSES = (
	DOC_STATUS_VALID,
	DOC_STATUS_EXPIRING,
	DOC_STATUS_EXPIRED,
	DOC_STATUS_SUPERSEDED,
)

# --- Trạng thái hồ sơ của Item, xếp từ nặng tới nhẹ ---
ITEM_STATUS_AUTH_INVALID = "Số lưu hành hết hiệu lực"
ITEM_STATUS_AUTH_PENDING = "Chưa có số lưu hành"
ITEM_STATUS_EXPIRED = "Có chứng từ hết hạn"
ITEM_STATUS_MISSING = "Thiếu chứng từ bắt buộc"
ITEM_STATUS_EXPIRING = "Sắp hết hạn"
ITEM_STATUS_OK = "Đủ hồ sơ mặt hàng"

# Thứ tự này là hợp đồng: `get_item_status` trả về giá trị đầu tiên khớp.
ITEM_STATUSES = (
	ITEM_STATUS_AUTH_INVALID,
	ITEM_STATUS_AUTH_PENDING,
	ITEM_STATUS_EXPIRED,
	ITEM_STATUS_MISSING,
	ITEM_STATUS_EXPIRING,
	ITEM_STATUS_OK,
)

# Số ngày trước hạn thì bắt đầu cảnh báo.
EXPIRY_WARNING_DAYS = 90

# Thư mục gốc chứa toàn bộ file hồ sơ TBYT.
ROOT_FOLDER = "Home/TBYT"
ARCHIVE_FOLDER_NAME = "_Luu-tru"

# Tiền tố số giữ cây thư mục đúng thứ tự trong giao diện File.
SCOPE_FOLDER_NAME = {
	SCOPE_COMPANY: "01-Cong-ty",
	SCOPE_OWNER: "02-Chu-so-huu",
	SCOPE_AUTHORIZATION: "03-So-luu-hanh",
	SCOPE_BATCH: "04-Lo",
	SCOPE_ITEM: "05-Item",
}
