// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam
//
// Chuông thông báo chuỗi cung ứng: âm báo + toast bấm mở được chứng từ.
//
// Sự kiện "notification" sẵn có của Frappe chỉ đủ để cập nhật số trên chuông vì nó
// không mang dữ liệu. Máy chủ phát thêm sự kiện riêng kèm chứng từ để dựng toast.
// Âm báo đi qua frappe.utils.play_sound nên tự tôn trọng cờ "Mute Sounds" của người
// dùng. Trình duyệt chặn phát âm trước lần tương tác đầu tiên của phiên — toast vẫn
// hiện, đó là giới hạn của trình duyệt chứ không phải lỗi.
//
// Âm báo, thời gian hiện toast và khoảng chống dội lấy từ *Cài đặt thông báo*
// (bơm sẵn vào frappe.boot), nên nghiệp vụ đổi được mà không cần deploy (AC-13).

frappe.provide("erpnext.supply_notification");

const DEFAULTS = { sound: "alert", toast_seconds: 10, sound_debounce_seconds: 3 };

erpnext.supply_notification.last_sound_at = 0;

erpnext.supply_notification.settings = function () {
	const boot = (frappe.boot && frappe.boot.supply_notification) || {};
	return {
		sound: boot.sound || DEFAULTS.sound,
		toast_seconds: boot.toast_seconds || DEFAULTS.toast_seconds,
		sound_debounce_seconds:
			boot.sound_debounce_seconds === undefined
				? DEFAULTS.sound_debounce_seconds
				: boot.sound_debounce_seconds,
	};
};

erpnext.supply_notification.play_sound = function () {
	const settings = erpnext.supply_notification.settings();
	const now = new Date().getTime();

	if (now - erpnext.supply_notification.last_sound_at < settings.sound_debounce_seconds * 1000) {
		return;
	}

	erpnext.supply_notification.last_sound_at = now;
	frappe.utils.play_sound(settings.sound);
};

erpnext.supply_notification.show = function (payload) {
	if (!payload || !payload.subject) {
		return;
	}

	const subject = frappe.utils.escape_html(payload.subject);
	const message = payload.url ? `<a href="${payload.url}">${subject}</a>` : subject;

	frappe.show_alert(
		{ message: message, indicator: "blue" },
		erpnext.supply_notification.settings().toast_seconds
	);
	erpnext.supply_notification.play_sound();
};

$(document).on("app_ready", function () {
	frappe.realtime.on("supply_notification", (payload) => {
		erpnext.supply_notification.show(payload);
	});
});
