// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam
//
// "Thông báo của tôi": mỗi người tự xem mình đang nhận những thông báo nào và
// tắt bớt những điểm được phép tắt (D18). Thông báo bắt buộc xử lý hiện rõ là
// không tắt được, kèm lý do, thay vì chỉ khoá công tắc mà không nói gì.

frappe.pages["thong_bao_cua_toi"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Thông báo của tôi"),
		single_column: true,
	});

	page.main.html(`<div class="my-notifications"><p class="text-muted">${__("Đang tải...")}</p></div>`);
	page.set_primary_action(__("Tải lại"), () => load(page));

	load(page);
};

function load(page) {
	frappe.call("erpnext.supply_notification.my_notifications.my_points").then((r) => {
		render(page, r.message || []);
	});
}

function render(page, rows) {
	const container = page.main.find(".my-notifications");

	if (!rows.length) {
		container.html(`<p>${__("Bạn chưa nằm trong danh sách nhận của điểm thông báo nào.")}</p>`);
		return;
	}

	const body = rows
		.map((row) => {
			const control = row.allow_opt_out
				? `<input type="checkbox" data-point="${frappe.utils.escape_html(row.point)}" ${
						row.opted_out ? "" : "checked"
				  }>`
				: `<span class="text-muted" title="${__("Thông báo bắt buộc xử lý")}">${__(
						"bắt buộc"
				  )}</span>`;

			const note = row.only_as_owner
				? `<div class="text-muted small">${__("chỉ khi bạn là người tạo chứng từ")}</div>`
				: "";

			return `<tr>
				<td>${frappe.utils.escape_html(row.point)}</td>
				<td>${frappe.utils.escape_html(row.title)}${note}</td>
				<td>${frappe.utils.escape_html(row.doctype_label)}</td>
				<td>${frappe.utils.escape_html(row.trigger)}</td>
				<td class="text-center">${control}</td>
			</tr>`;
		})
		.join("");

	container.html(`
		<table class="table table-bordered">
			<thead>
				<tr>
					<th>${__("Mã")}</th>
					<th>${__("Thông báo")}</th>
					<th>${__("Chứng từ")}</th>
					<th>${__("Khi nào")}</th>
					<th class="text-center">${__("Nhận")}</th>
				</tr>
			</thead>
			<tbody>${body}</tbody>
		</table>`);

	container.find("input[type=checkbox]").on("change", function () {
		const point = $(this).data("point");
		const receive = $(this).is(":checked") ? 1 : 0;

		frappe.call({
			method: "erpnext.supply_notification.my_notifications.set_subscription",
			args: { point: point, receive: receive },
			callback() {
				frappe.show_alert({
					message: receive ? __("Sẽ nhận lại {0}", [point]) : __("Đã tắt {0}", [point]),
					indicator: "blue",
				});
			},
		});
	});
}
