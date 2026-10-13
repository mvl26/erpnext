// Menu của app PDA: bốn việc, nút to, không có gì khác trên màn hình.
//
// Nằm trên MÁY CHỦ chứ không gói trong APK (spec §3): sửa menu không phải cài lại
// app, và mở được cả từ trình duyệt máy tính để đối chiếu khi có sự cố.

frappe.pages["pda-home"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Kho — PDA"), single_column: true });
	const viec = [
		{ route: "xep-hang-pda", nhan: __("Xếp hàng vào ô"), mo: __("Quét tem lô, quét tem ô") },
		{ route: "lay-hang-pda", nhan: __("Lấy hàng"), mo: __("Theo phiếu giao: lô, ô, đơn vị, kiện") },
		{ route: "quet-ma-tra-cuu", nhan: __("Quét mã tra cứu"), mo: __("Tem lô hoặc tem ô ra thông tin") },
		{
			route: "dat-o-hang-loat",
			nhan: __("Đặt ô trên tem"),
			mo: __("Bảng rộng — nên làm trên máy tính"),
		},
	];
	const e = frappe.utils.escape_html;
	$(`
		<div class="ph">
			<div class="ph-nguoi">${e(frappe.session.user_fullname || frappe.session.user)}</div>
			<div class="ph-ds">
				${viec
					.map(
						(v) => `
					<button type="button" class="ph-nut" data-route="${e(v.route)}">
						<span class="ph-nhan">${e(v.nhan)}</span>
						<span class="ph-mo">${e(v.mo)}</span>
					</button>`
					)
					.join("")}
			</div>
			<button type="button" class="ph-thoat">${__("Đăng xuất")}</button>
			<div class="ph-may-chu">${e(__("Máy chủ") + ": " + window.location.host)}</div>
		</div>
	`).appendTo(page.main);

	$(page.main).on("click", ".ph-nut", (ev) => frappe.set_route($(ev.currentTarget).attr("data-route")));
	$(page.main).on("click", ".ph-thoat", () => {
		// `frappe.call` gọi endpoint logout qua AJAX, chờ callback rồi dẫn về
		// `/pda` — màn quét thẻ. Không dùng chuyển hướng trực tiếp vì endpoint
		// `/api/method/logout` chỉ trả JSON, không tự chuyển hướng.
		frappe.call({
			method: "logout",
			callback: () => {
				window.location.href = "/pda";
			}
		});
	});
};
