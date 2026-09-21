// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam
//
// Chấm màu trạng thái trên danh sách chứng từ HĐĐT.
//
// Bảng màu này là **bản sao** của `STATUS_COLOURS` trong erpnext/einvoice/constants.py.
// Phải sao vì `get_indicator` chạy phía client cho từng dòng, không gọi server được.
// Test `TestStatusColours` trong tests/test_fast_form_state.py đối chiếu hai bên —
// sửa một chỗ mà quên chỗ kia là test đỏ.

const STATUS_COLOURS = {
	"01 - Nháp": "grey",
	"02 - Đã xem nháp": "grey",
	"03 - Chờ khách duyệt": "orange",
	"04 - Khách đã duyệt": "blue",
	"05 - Đang phát hành": "yellow",
	"06 - Đã phát hành": "blue",
	"07 - Đã gửi khách": "blue",
	"08 - CQT chấp nhận": "green",
	"09 - CQT từ chối": "red",
	"10 - Đã điều chỉnh": "darkgrey",
	"11 - Đã thay thế": "darkgrey",
	"12 - Đã hủy nội bộ": "darkgrey",
	"98 - Cần đối soát": "orange",
	"99 - Lỗi": "red",
};

frappe.listview_settings["Fast EInvoice Document"] = {
	add_fields: ["status", "fast_invoice_no", "tax_status"],

	get_indicator(doc) {
		// Phần tử thứ ba làm chấm màu bấm được: bấm là lọc luôn theo trạng thái đó.
		return [__(doc.status), STATUS_COLOURS[doc.status] || "grey", `status,=,${doc.status}`];
	},
};
