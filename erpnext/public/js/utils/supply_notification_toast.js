// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam
//
// Chuông thông báo chuỗi cung ứng: âm báo + toast bấm mở được chứng từ.
//
// Sự kiện "notification" sẵn có của Frappe chỉ đủ để cập nhật số trên chuông vì nó
// không mang dữ liệu. Máy chủ phát thêm sự kiện riêng kèm chứng từ để dựng toast.
// Âm báo đi qua frappe.utils.play_sound nên tự tôn trọng cờ "Mute Sounds" của người
// dùng. Trình duyệt chặn phát âm trước lần tương tác đầu tiên của phiên — toast vẫn
// hiện, đó là giới hạn của trình duyệt chứ không phải lỗi.

frappe.provide("erpnext.supply_notification");

// Nhiều chứng từ ghi sổ liên tiếp chỉ kêu một lần trong khoảng này.
const SOUND_DEBOUNCE_MS = 3000;
const TOAST_SECONDS = 10;

erpnext.supply_notification.last_sound_at = 0;

erpnext.supply_notification.play_sound = function () {
	const now = new Date().getTime();
	if (now - erpnext.supply_notification.last_sound_at < SOUND_DEBOUNCE_MS) {
		return;
	}
	erpnext.supply_notification.last_sound_at = now;
	frappe.utils.play_sound("alert");
};

erpnext.supply_notification.show = function (payload) {
	if (!payload || !payload.subject) {
		return;
	}

	const subject = frappe.utils.escape_html(payload.subject);
	const message = payload.url ? `<a href="${payload.url}">${subject}</a>` : subject;

	frappe.show_alert({ message: message, indicator: "blue" }, TOAST_SECONDS);
	erpnext.supply_notification.play_sound();
};

$(document).on("app_ready", function () {
	frappe.realtime.on("supply_notification", (payload) => {
		erpnext.supply_notification.show(payload);
	});
});
