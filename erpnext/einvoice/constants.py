# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Bộ mã dùng chung của hóa đơn điện tử Fast.

Giá trị ở đây đi thẳng vào payload gửi Fast nên là **mã của Fast**, không phải
nhãn hiển thị. Đổi một dòng ở đây là đổi dữ liệu gửi lên Cơ quan Thuế.
"""

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
PROCESS_TYPE_CODES = ("1", "2", "3", "4", "5")
PROCESS_TYPE_LABELS = {
	"1": "Hàng hóa / dịch vụ",
	"2": "Khuyến mại",
	"3": "Chiết khấu",
	"4": "Ghi chú",
	"5": "Hàng đặc trưng",
}
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
