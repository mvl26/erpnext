// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

// Loại hình suy trực tiếp từ phân loại — khớp erpnext/tbyt/constants.py::LOAI_HINH_BY_CLASS.
// Server ghi đè lại trong validate() dù người dùng có sửa gì đi nữa; ở đây chỉ để
// người dùng thấy giá trị đúng ngay khi chọn, không cần lưu mới biết.
const LOAI_HINH_BY_CLASS = {
	A: "Số công bố tiêu chuẩn",
	B: "Số công bố tiêu chuẩn",
	C: "Số đăng ký lưu hành",
	D: "Số đăng ký lưu hành",
};

// Loại chứng từ chứng minh chính số lưu hành — khớp
// erpnext/tbyt/constants.py::AUTH_DOCUMENT_BY_CLASS. Dùng để điền sẵn nút tải lên.
const AUTH_DOCUMENT_BY_CLASS = {
	A: "so_cong_bo_tieu_chuan",
	B: "so_cong_bo_tieu_chuan",
	C: "gcn_dang_ky_luu_hanh",
	D: "gcn_dang_ky_luu_hanh",
};

frappe.ui.form.on("TBYT Marketing Authorization", {
	phan_loai(frm) {
		if (LOAI_HINH_BY_CLASS[frm.doc.phan_loai]) {
			frm.set_value("loai_hinh", LOAI_HINH_BY_CLASS[frm.doc.phan_loai]);
		}
	},

	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		frm.add_custom_button(__("Tải chứng từ lên"), () => {
			frappe.route_options = {
				document_type: AUTH_DOCUMENT_BY_CLASS[frm.doc.phan_loai],
			};
			// `frappe.route_options` không sống nổi tới `onload` của form đích: Frappe
			// tự đặt nó về null ngay trong `frappe.model.get_new_doc()` (create_new.js),
			// TRƯỚC khi trang New render và bắn onload — chỉ trường khớp tên field thật
			// (như document_type ở trên) được sao chép ra ngoài kịp lúc, bảng con thì
			// không có cơ chế nào sao chép cả. Dùng một biến toàn cục riêng, tự quản,
			// để mang phạm vi qua được onload.
			frappe.tbyt_pending_scope = {
				scope_doctype: "TBYT Marketing Authorization",
				scope_name: frm.doc.name,
			};
			frappe.new_doc("TBYT Regulatory Document");
		}).addClass("btn-primary");

		frm.trigger("render_chung_tu_html");
	},

	render_chung_tu_html(frm) {
		frappe.call({
			method: "erpnext.tbyt.doctype.tbyt_marketing_authorization.tbyt_marketing_authorization.get_authorization_documents",
			args: { authorization: frm.doc.name },
			callback(r) {
				const rows = r.message || [];
				const wrapper = frm.fields_dict.chung_tu_html.wrapper;

				if (!rows.length) {
					$(wrapper).html(
						`<div class="text-muted">${__("Chưa có chứng từ nào gắn vào số lưu hành này.")}</div>`
					);
					return;
				}

				const body = rows
					.map((row) => {
						const documentType = frappe.utils.escape_html(row.document_type || "");
						const soHieu = frappe.utils.escape_html(row.so_hieu || "");
						const hetHan = row.khong_thoi_han
							? __("Vô thời hạn")
							: frappe.utils.escape_html(frappe.datetime.str_to_user(row.ngay_het_han) || "");
						const trangThai = frappe.utils.escape_html(row.trang_thai || "");
						const route = frappe.utils.escape_html(
							frappe.utils.get_form_link("TBYT Regulatory Document", row.name)
						);

						return `<tr>
							<td><a href="${route}">${documentType}</a></td>
							<td>${soHieu}</td>
							<td>${hetHan}</td>
							<td>${trangThai}</td>
						</tr>`;
					})
					.join("");

				$(wrapper).html(`
					<table class="table table-bordered">
						<thead>
							<tr>
								<th>${__("Loại chứng từ")}</th>
								<th>${__("Số hiệu")}</th>
								<th>${__("Hết hạn")}</th>
								<th>${__("Trạng thái")}</th>
							</tr>
						</thead>
						<tbody>${body}</tbody>
					</table>
				`);
			},
		});
	},
});
