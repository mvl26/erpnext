# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Bộ mã dùng chung của hóa đơn điện tử Fast.

Giá trị ở đây đi thẳng vào payload gửi Fast nên là **mã của Fast**, không phải
nhãn hiển thị. Đổi một dòng ở đây là đổi dữ liệu gửi lên Cơ quan Thuế.
"""

# --- Vòng đời hóa đơn — bảng B2 của đặc tả.
# Mã dẫn đầu để trạng thái sắp xếp đúng thứ tự vòng đời trên list view.
STATUS_DRAFT = "01 - Nháp"
STATUS_DRAFT_VIEWED = "02 - Đã xem nháp"
STATUS_AWAITING_CUSTOMER = "03 - Chờ khách duyệt"
STATUS_CUSTOMER_APPROVED = "04 - Khách đã duyệt"
STATUS_ISSUING = "05 - Đang phát hành"
STATUS_ISSUED = "06 - Đã phát hành"
STATUS_SENT = "07 - Đã gửi khách"
STATUS_TAX_ACCEPTED = "08 - CQT chấp nhận"
STATUS_TAX_REJECTED = "09 - CQT từ chối"
STATUS_ADJUSTED = "10 - Đã điều chỉnh"
STATUS_REPLACED = "11 - Đã thay thế"
STATUS_CANCELLED = "12 - Đã hủy nội bộ"
# Đặc tả E5 nhánh 7c gọi đây là "biến thể của 99"; tách mã riêng để phân biệt
# "gửi đi rồi nhưng chưa biết kết quả" với "chắc chắn lỗi".
STATUS_NEEDS_RECONCILE = "98 - Cần đối soát"
STATUS_ERROR = "99 - Lỗi"

STATUSES = (
	STATUS_DRAFT,
	STATUS_DRAFT_VIEWED,
	STATUS_AWAITING_CUSTOMER,
	STATUS_CUSTOMER_APPROVED,
	STATUS_ISSUING,
	STATUS_ISSUED,
	STATUS_SENT,
	STATUS_TAX_ACCEPTED,
	STATUS_TAX_REJECTED,
	STATUS_ADJUSTED,
	STATUS_REPLACED,
	STATUS_CANCELLED,
	STATUS_NEEDS_RECONCILE,
	STATUS_ERROR,
)
STATUS_OPTIONS = "\n".join(STATUSES)

# Sửa được dữ liệu (cột cuối bảng B2). Mọi trạng thái khác khóa dữ liệu master.
EDITABLE_STATUSES = frozenset(
	{
		STATUS_DRAFT,
		STATUS_DRAFT_VIEWED,
		STATUS_AWAITING_CUSTOMER,
		STATUS_CUSTOMER_APPROVED,
		STATUS_NEEDS_RECONCILE,
		STATUS_ERROR,
	}
)

# Đã tiêu một số hóa đơn thật trên hệ thống Fast — không bao giờ phát hành lại.
ISSUED_STATUSES = frozenset(
	{
		STATUS_ISSUED,
		STATUS_SENT,
		STATUS_TAX_ACCEPTED,
		STATUS_TAX_REJECTED,
		STATUS_ADJUSTED,
		STATUS_REPLACED,
		STATUS_CANCELLED,
	}
)

# Lập được hóa đơn điều chỉnh / thay thế. Điều kiện đầy đủ còn cần Cơ quan Thuế
# đã chấp nhận (``tax_status``) — xem `lineage.can_amend`. Tập này chỉ loại các
# trạng thái không có số hóa đơn, hoặc đã bị điều chỉnh/thay thế/hủy rồi.
ADJUSTABLE_STATUSES = frozenset({STATUS_ISSUED, STATUS_SENT, STATUS_TAX_ACCEPTED})

# Đang giữ chỗ trên Delivery Note: không cho lập bản ghi HĐĐT thứ hai cho cùng DN
# (đặc tả C2.1 #1 — "không cho trùng với bản ghi khác đang ở trạng thái 01—08").
LIVE_STATUSES = frozenset(
	{
		STATUS_DRAFT,
		STATUS_DRAFT_VIEWED,
		STATUS_AWAITING_CUSTOMER,
		STATUS_CUSTOMER_APPROVED,
		STATUS_ISSUING,
		STATUS_ISSUED,
		STATUS_SENT,
		STATUS_TAX_ACCEPTED,
		STATUS_NEEDS_RECONCILE,
	}
)

# --- Loại chứng từ — mục C2.1 #5.
INVOICE_TYPE_ORIGINAL = "Hóa đơn gốc"
INVOICE_TYPE_ADJUSTMENT = "Hóa đơn điều chỉnh"
INVOICE_TYPE_REPLACEMENT = "Hóa đơn thay thế"
INVOICE_TYPES = (INVOICE_TYPE_ORIGINAL, INVOICE_TYPE_ADJUSTMENT, INVOICE_TYPE_REPLACEMENT)
INVOICE_TYPE_OPTIONS = "\n".join(INVOICE_TYPES)

# --- Loại điều chỉnh — mục C2.1 #7. Thay thế thì hệ thống tự gán 4.
ADJUSTMENT_TYPE_OPTIONS = "\n".join(
	("1 - Điều chỉnh giảm", "2 - Điều chỉnh tăng", "3 - Điều chỉnh thông tin")
)
ADJUSTMENT_TYPE_REPLACEMENT = "4"

# --- Trạng thái Cơ quan Thuế — mục C2.4 #69.
TAX_STATUS_PENDING = "Chờ CQT"
TAX_STATUS_ACCEPTED = "3 - Chấp nhận"
TAX_STATUS_REJECTED = "4 - Từ chối"
TAX_STATUS_OPTIONS = "\n".join(("", TAX_STATUS_PENDING, TAX_STATUS_ACCEPTED, TAX_STATUS_REJECTED))

# --- Hình thức thanh toán — mục C2.3 #36.
PAYMENT_METHOD_OPTIONS = "\n".join(("TM", "CK", "TM/CK"))

# --- Thuế suất (thẻ TaxRate, dùng chung cho master và từng dòng) — mục C2.3 #41.
TAX_RATE_CODES = ("0", "5", "8", "10", "-1", "-2", "-8", "-9")
TAX_RATE_LABELS = {
	"0": "0%",
	"5": "5%",
	"8": "8%",
	"10": "10%",
	"-1": "KCT — không chịu thuế",
	"-2": "KKKNT — không kê khai nộp thuế",
	"-8": "KHAC — thuế suất khác",
	"-9": "Không ghi thuế suất (dòng ghi chú / hóa đơn điều chỉnh)",
}
TAX_RATE_OPTIONS = "\n".join(TAX_RATE_CODES)

# Thuế suất có số: dùng để cộng nhóm TaxAmount0/5/10 và kiểm tra số liệu.
NUMERIC_TAX_RATES = {"0": 0.0, "5": 5.0, "8": 8.0, "10": 10.0}

# --- Tính chất dòng hàng (thẻ ProcessType) — mục C3 #1.
PROCESS_TYPE_GOODS = "1"
PROCESS_TYPE_PROMOTION = "2"
PROCESS_TYPE_DISCOUNT = "3"
PROCESS_TYPE_NOTE = "4"
PROCESS_TYPE_SPECIAL = "5"

PROCESS_TYPE_CODES = (
	PROCESS_TYPE_GOODS,
	PROCESS_TYPE_PROMOTION,
	PROCESS_TYPE_DISCOUNT,
	PROCESS_TYPE_NOTE,
	PROCESS_TYPE_SPECIAL,
)
PROCESS_TYPE_LABELS = {
	PROCESS_TYPE_GOODS: "Hàng hóa / dịch vụ",
	PROCESS_TYPE_PROMOTION: "Khuyến mại",
	PROCESS_TYPE_DISCOUNT: "Chiết khấu",
	PROCESS_TYPE_NOTE: "Ghi chú",
	PROCESS_TYPE_SPECIAL: "Hàng đặc trưng",
}

# Dòng chảy vào Tiền hàng và Tiền thuế của hóa đơn.
#
# Khuyến mại có giá trị nhưng không thu tiền, ghi chú thì không phải tiền — cộng
# hai loại này vào tiền hàng là thổi phồng số phải thu và số kê khai. Chiết khấu
# **có** nằm trong đây vì dòng chiết khấu nhập số âm: nó phải trừ được tiền hàng.
BILLABLE_PROCESS_TYPES = frozenset({PROCESS_TYPE_GOODS, PROCESS_TYPE_DISCOUNT, PROCESS_TYPE_SPECIAL})
PROCESS_TYPE_OPTIONS = "\n".join(PROCESS_TYPE_CODES)

# --- Giới hạn của Fast.
MAX_LINES_PER_INVOICE = 300  # lỗi 3000
MAX_LEN = {
	"fast_key": 32,
	"buyer": 100,
	"item_code": 32,
	"item_name": 500,
	"uom": 16,
	"human_name": 128,
	"email_deliver": 256,
	"buyer_unit": 7,
	"passport_no": 20,
	"external": 500,
}
