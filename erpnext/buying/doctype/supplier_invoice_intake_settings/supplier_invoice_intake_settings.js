// Cài đặt tiếp nhận hóa đơn NCC: chọn trường bắt buộc khi Nộp hợp đồng khung (Đơn khung loại mua)
// bằng hộp tích chọn. Ô lưu tên trường, mỗi dòng một trường; server kiểm tên trường và áp khi Nộp.
frappe.provide("erpnext.tiep_nhan_hoa_don");

erpnext.tiep_nhan_hoa_don.TRUONG_BAT_BUOC = [
	{ fieldname: "truong_bat_buoc_hdk", doctype: "Blanket Order", label: __("Đầu hợp đồng") },
	{ fieldname: "truong_bat_buoc_dong_hdk", doctype: "Blanket Order Item", label: __("Dòng hợp đồng") },
];
// Hệ thống luôn bắt buộc hoặc tự điền: không đưa vào danh sách chọn.
erpnext.tiep_nhan_hoa_don.KHONG_CHON = [
	"naming_series",
	"blanket_order_type",
	"customer",
	"supplier",
	"order_no",
	"bang_gia_mua",
	"company",
	"from_date",
	"to_date",
	"hop_dong_goc",
	"so_phu_luc",
	"ma_hop_dong",
	"amended_from",
	"item_code",
	"qty",
	"rate",
	"ma_dong_hdk",
];

frappe.ui.form.on("Supplier Invoice Intake Settings", {
	onload(frm) {
		frappe.model.with_doctype("Blanket Order", () =>
			frappe.model.with_doctype("Blanket Order Item", () => frm.trigger("tom_tat"))
		);
	},
	refresh(frm) {
		frm.trigger("tom_tat");
		if (frappe.user.has_role("System Manager")) {
			frm.add_custom_button(__("Chọn trường bắt buộc khi Nộp hợp đồng khung"), () =>
				frm.trigger("chon_truong_bat_buoc")
			);
		}
	},
	truong_bat_buoc_hdk(frm) {
		frm.trigger("tom_tat");
	},
	truong_bat_buoc_dong_hdk(frm) {
		frm.trigger("tom_tat");
	},
	tom_tat(frm) {
		const wrapper =
			frm.fields_dict.tom_tat_truong_bat_buoc && frm.fields_dict.tom_tat_truong_bat_buoc.$wrapper;
		if (!wrapper) return;
		const html = erpnext.tiep_nhan_hoa_don.TRUONG_BAT_BUOC.map((n) => {
			const nhan = (frm.doc[n.fieldname] || "")
				.split("\n")
				.filter(Boolean)
				.map((f) => {
					const df = frappe.meta.get_docfield(n.doctype, f);
					return frappe.utils.escape_html(df ? __(df.label) : f);
				});
			return `<p><b>${n.label}:</b> ${nhan.length ? nhan.join(", ") : __("(không có)")}</p>`;
		});
		wrapper.html(html.join(""));
	},
	chon_truong_bat_buoc(frm) {
		frappe.model.with_doctype("Blanket Order", () =>
			frappe.model.with_doctype("Blanket Order Item", () => {
				const nhom = erpnext.tiep_nhan_hoa_don.TRUONG_BAT_BUOC.map((n) => {
					const dang_chon = (frm.doc[n.fieldname] || "").split("\n");
					const options = frappe.meta
						.get_docfields(n.doctype)
						.filter(
							(df) =>
								df.label &&
								!frappe.model.no_value_type.includes(df.fieldtype) &&
								!["Table", "Table MultiSelect"].includes(df.fieldtype) &&
								!df.read_only &&
								!df.hidden &&
								!df.reqd &&
								!erpnext.tiep_nhan_hoa_don.KHONG_CHON.includes(df.fieldname)
						)
						.map((df) => ({
							label: __(df.label),
							value: df.fieldname,
							checked: dang_chon.includes(df.fieldname),
						}));
					return {
						fieldname: n.fieldname,
						fieldtype: "MultiCheck",
						label: n.label,
						columns: 2,
						options,
					};
				});
				const d = new frappe.ui.Dialog({
					title: __("Trường bắt buộc khi Nộp hợp đồng khung"),
					size: "large",
					fields: nhom,
					primary_action_label: __("Áp dụng"),
					primary_action(values) {
						erpnext.tiep_nhan_hoa_don.TRUONG_BAT_BUOC.forEach((n) =>
							frm.set_value(n.fieldname, (values[n.fieldname] || []).join("\n"))
						);
						d.hide();
						frappe.show_alert({ message: __("Bấm Lưu để áp dụng."), indicator: "blue" });
					},
				});
				d.show();
			})
		);
	},
});
