// Phiếu tiếp nhận hóa đơn NCC (Đợt 4). Mọi kiểm tra và đối soát nằm ở server
// (erpnext.buying.tiep_nhan_hoa_don); file này chỉ hiển thị và gọi các nút.
frappe.provide("erpnext.tiep_nhan_hoa_don");

erpnext.tiep_nhan_hoa_don.MAU = {
	"Mới tiếp nhận": "gray",
	"Đã trích xuất": "blue",
	"Đã đối soát": "green",
	"Chờ xử lý thủ công": "orange",
	"Đã tạo nháp hóa đơn mua": "blue",
	"Lệch PR-PI": "red",
	"Đã ghi sổ": "green",
	"Từ chối": "red",
};

erpnext.tiep_nhan_hoa_don.goi = (frm, method, args, sau) =>
	frappe
		.xcall(`erpnext.buying.tiep_nhan_hoa_don.${method}`, { phieu: frm.doc.name, ...args })
		.then((kq) => {
			frm.reload_doc();
			if (sau) sau(kq);
		});

frappe.ui.form.on("Supplier Invoice Intake", {
	refresh(frm) {
		const tt = frm.doc.trang_thai;
		const goi = erpnext.tiep_nhan_hoa_don.goi;
		const dieu_chinh = frm.doc.tinh_chat_hoa_don === "Điều chỉnh";
		const goc_co_nhap = frm.doc.__onload && frm.doc.__onload.goc_co_hoa_don_nhap;
		// Kế toán chỉ xem phiếu (FRD): không hiện các nút làm thay đổi phiếu.
		const ghi = frm.has_perm("write");
		if (!frm.is_new() && tt) {
			frm.page.set_indicator(__(tt), erpnext.tiep_nhan_hoa_don.MAU[tt] || "gray");
		}
		const khoa =
			(["Đã tạo nháp hóa đơn mua", "Lệch PR-PI", "Đã ghi sổ"].includes(tt) &&
				frm.doc.purchase_invoice) ||
			frm.doc.tu_choi_tay;
		frm.set_df_property("items", "read_only", khoa ? 1 : 0);
		frm.set_df_property("tep_hoa_don", "read_only", khoa ? 1 : 0);
		// Dòng hóa đơn điều chỉnh lấy mặt hàng theo dòng hóa đơn gốc: chỉ chọn STT dòng gốc.
		frm.fields_dict.items.grid.update_docfield_property("item_code", "read_only", dieu_chinh ? 1 : 0);

		if (tt === "Từ chối") {
			frm.set_intro(
				frm.doc.tu_choi_tay
					? __("Từ chối tay bởi {0}: {1}", [
							frappe.user.full_name(frm.doc.nguoi_tu_choi),
							frm.doc.ly_do_tu_choi || "",
					  ])
					: __("Từ chối: {0}", [frm.doc.ly_do_tu_choi || ""]),
				"red"
			);
		} else if (tt === "Lệch PR-PI") {
			frm.set_intro(
				__(
					"Hóa đơn mua {0} lệch Phiếu nhập mua. Mở Hóa đơn mua, xem Bảng chênh lệch và xử lý theo nhánh; khớp lại thì phiếu tự về Đã tạo nháp hóa đơn mua.",
					[frm.doc.purchase_invoice]
				),
				"red"
			);
		} else if (tt === "Chờ xử lý thủ công") {
			frm.set_intro(
				__(
					"Còn dòng chưa khớp / chờ xác nhận hoặc cảnh báo chưa xử lý. Chọn mặt hàng cho dòng chưa khớp, tích Đã xác nhận cho dòng chờ xác nhận, rồi Lưu."
				),
				"orange"
			);
		} else if (dieu_chinh && tt === "Đã đối soát" && frm.doc.phieu_lien_quan) {
			frm.set_intro(
				__(
					"Hóa đơn điều chỉnh của phiếu {0}: bấm nút để lập Hóa đơn mua nháp theo số sau điều chỉnh (một hóa đơn cho cả hóa đơn gốc và hóa đơn điều chỉnh).",
					[frm.doc.phieu_lien_quan]
				),
				"blue"
			);
		}

		if (frm.doc.purchase_invoice) {
			frm.add_custom_button(__("Mở Hóa đơn mua"), () =>
				frappe.set_route("Form", "Purchase Invoice", frm.doc.purchase_invoice)
			);
		}
		if (frm.doc.phieu_lien_quan) {
			frm.add_custom_button(__("Mở phiếu hóa đơn gốc"), () =>
				frappe.set_route("Form", "Supplier Invoice Intake", frm.doc.phieu_lien_quan)
			);
		}
		if (ghi && tt === "Đã đối soát" && !frm.doc.purchase_invoice) {
			const nhan = !dieu_chinh
				? __("Tạo Hóa đơn mua nháp")
				: goc_co_nhap
				? __("Lập lại Hóa đơn mua nháp (gốc + điều chỉnh)")
				: __("Lập Hóa đơn mua nháp (gốc + điều chỉnh)");
			frm.add_custom_button(nhan, () => {
				if (frm.is_dirty()) return frappe.msgprint(__("Lưu phiếu trước."));
				const lap = () =>
					goi(frm, "tao_hoa_don.tao_hoa_don_mua", {}, (pi) =>
						frappe.show_alert({
							message: __("Đã tạo Hóa đơn mua nháp {0}", [pi]),
							indicator: "green",
						})
					);
				if (dieu_chinh && goc_co_nhap) {
					frappe.confirm(
						__(
							"Hóa đơn mua nháp hiện có của hóa đơn gốc sẽ bị xóa và lập lại theo số sau điều chỉnh. Tiếp tục?"
						),
						lap
					);
				} else {
					lap();
				}
			}).addClass("btn-primary");
		}
		if (ghi && frm.doc.tinh_chat_hoa_don === "Thay thế" && tt === "Chờ xử lý thủ công" && goc_co_nhap) {
			frm.add_custom_button(__("Bỏ hóa đơn bị thay thế"), () =>
				frappe.confirm(
					__("Xóa Hóa đơn mua nháp của hóa đơn bị thay thế; phiếu {0} chuyển Từ chối. Tiếp tục?", [
						frm.doc.phieu_lien_quan,
					]),
					() => goi(frm, "hoa_don_lien_quan.bo_hoa_don_bi_thay_the", {})
				)
			);
		}
		const co_canh_bao_chan = (frm.doc.items || []).some((d) => d.canh_bao_chan);
		if (
			tt === "Chờ xử lý thủ công" &&
			co_canh_bao_chan &&
			frm.doc.__onload &&
			frm.doc.__onload.co_quyen_duyet
		) {
			frm.add_custom_button(__("Duyệt cảnh báo"), () => {
				if (frm.is_dirty()) return frappe.msgprint(__("Lưu phiếu trước."));
				frappe.prompt(
					{ fieldname: "ly_do", fieldtype: "Small Text", label: __("Lý do duyệt"), reqd: 1 },
					({ ly_do }) => goi(frm, "doi_soat.duyet_canh_bao", { ly_do }),
					__("Duyệt lệch giá / vượt hạn mức hợp đồng khung"),
					__("Duyệt")
				);
			});
		}

		if (ghi && !frm.is_new() && !["Đã ghi sổ", "Từ chối"].includes(tt)) {
			frm.add_custom_button(__("Từ chối"), () => {
				if (frm.is_dirty()) return frappe.msgprint(__("Lưu phiếu trước."));
				frappe.prompt(
					[
						{
							fieldname: "ghi_chu",
							fieldtype: "HTML",
							options: frm.doc.purchase_invoice
								? `<p class="text-danger">${__("Hóa đơn mua nháp {0} của phiếu sẽ bị xóa.", [
										frm.doc.purchase_invoice,
								  ])}</p>`
								: "",
						},
						{ fieldname: "ly_do", fieldtype: "Small Text", label: __("Lý do từ chối"), reqd: 1 },
					],
					({ ly_do }) => goi(frm, "doi_soat.tu_choi", { ly_do }),
					__("Từ chối phiếu tiếp nhận"),
					__("Từ chối")
				);
			});
		}
		if (ghi && tt === "Từ chối" && frm.doc.tu_choi_tay) {
			frm.add_custom_button(__("Mở lại"), () => goi(frm, "doi_soat.mo_lai", {}));
		}
	},
});

frappe.ui.form.on("Supplier Invoice Intake Item", {
	// Sửa mặt hàng là chọn tay (tầng 4): server giữ lựa chọn này khi đối soát lại.
	item_code(frm, cdt, cdn) {
		const d = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "chon_tay", d.item_code ? 1 : 0);
	},
	// Hóa đơn điều chỉnh: chọn dòng gốc / kiểu điều chỉnh bằng tay thì server giữ lựa chọn.
	dong_goc(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "chon_tay", locals[cdt][cdn].dong_goc ? 1 : 0);
	},
	kieu_dieu_chinh(frm, cdt, cdn) {
		if (locals[cdt][cdn].dong_goc) frappe.model.set_value(cdt, cdn, "chon_tay", 1);
	},
});
