// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam
//
// Nút "Tạo hóa đơn điện tử" trên hóa đơn bán (Nút 1, mục E1 — đặc tả bản 3.0).
//
// Hóa đơn bán là chứng từ nguồn duy nhất của hóa đơn gốc. Tiền điều kiện do
// server quyết định (`get_sales_invoice_state`) — form chỉ vẽ lại, để giao diện
// không bao giờ mời một hành động mà server sẽ từ chối.

frappe.ui.form.on("Sales Invoice", {
	async refresh(frm) {
		if (frm.is_new() || frm.doc.docstatus !== 1) return;

		const { message: state } = await frappe.call({
			method: "erpnext.einvoice.form_state.get_sales_invoice_state",
			args: { sales_invoice: frm.doc.name },
		});
		if (!state) return;

		if (state.existing) {
			frm.add_custom_button(
				__("Mở chứng từ HĐĐT"),
				() => frappe.set_route("Form", "Fast EInvoice Document", state.existing.name),
				__("Hóa đơn điện tử")
			);
		}

		if (state.can_create) {
			frm.add_custom_button(
				__("Tạo hóa đơn điện tử"),
				() => confirm_create(frm, state),
				__("Hóa đơn điện tử")
			);
		}

		// Không có nút tạo thì phải nói vì sao. Server đã tính sẵn `reason`; giấu
		// nó đi là để người dùng nhìn một hóa đơn trống trơn mà đoán xem hóa đơn
		// điện tử hỏng ở đâu.
		if (!state.can_create && state.reason) {
			frm.dashboard.add_comment(
				__("Chưa lập được hóa đơn điện tử: {0}", [state.reason]),
				"orange",
				true
			);
		}
	},
});

function confirm_create(frm, state) {
	const total = format_currency(state.grand_total, state.currency);

	frappe.confirm(
		`<p>${__("Tạo chứng từ hóa đơn điện tử từ hóa đơn bán <b>{0}</b>?", [frm.doc.name])}</p>
		 <p>${__("Khách hàng")}: <b>${frappe.utils.escape_html(state.customer_name || "")}</b><br>
		    ${__("Tổng tiền")}: <b>${total}</b></p>
		 <p class="text-muted">${__(
				"Hệ thống sẽ sao chép dữ liệu sang chứng từ HĐĐT để rà soát trước khi phát hành. Chưa gửi gì cho Fast ở bước này."
			)}</p>`,
		() => {
			frappe.call({
				method: "erpnext.einvoice.builder.create_from_sales_invoice",
				args: { sales_invoice: frm.doc.name },
				freeze: true,
				freeze_message: __("Đang tạo chứng từ…"),
				callback(response) {
					if (response.message) {
						frappe.set_route("Form", "Fast EInvoice Document", response.message);
					}
				},
			});
		}
	);
}
