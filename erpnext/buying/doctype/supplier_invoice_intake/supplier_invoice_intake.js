// Phiếu tiếp nhận hóa đơn NCC (Đợt 4). Mọi kiểm tra và đối soát nằm ở server
// (erpnext.buying.tiep_nhan_hoa_don); file này chỉ hiển thị và gọi các nút.
frappe.provide("erpnext.tiep_nhan_hoa_don");

erpnext.tiep_nhan_hoa_don.MAU = {
	"Mới tiếp nhận": "gray",
	"Đã trích xuất": "blue",
	"Đã đối soát": "green",
	"Chờ xử lý thủ công": "orange",
	"Đã tạo nháp hóa đơn mua": "blue",
	"Đã ghi sổ": "green",
	"Từ chối": "red",
};

frappe.ui.form.on("Supplier Invoice Intake", {
	refresh(frm) {
		const tt = frm.doc.trang_thai;
		if (!frm.is_new() && tt) {
			frm.page.set_indicator(__(tt), erpnext.tiep_nhan_hoa_don.MAU[tt] || "gray");
		}
		const khoa = ["Đã tạo nháp hóa đơn mua", "Đã ghi sổ"].includes(tt) && frm.doc.purchase_invoice;
		frm.set_df_property("items", "read_only", khoa ? 1 : 0);
		frm.set_df_property("tep_hoa_don", "read_only", khoa ? 1 : 0);

		if (tt === "Từ chối") {
			frm.set_intro(__("Từ chối: {0}", [frm.doc.ly_do_tu_choi || ""]), "red");
		} else if (tt === "Chờ xử lý thủ công") {
			frm.set_intro(
				__(
					"Còn dòng chưa khớp / chờ xác nhận hoặc cảnh báo chưa xử lý. Chọn mặt hàng cho dòng chưa khớp, tích Đã xác nhận cho dòng chờ xác nhận, rồi Lưu."
				),
				"orange"
			);
		}

		if (frm.doc.purchase_invoice) {
			frm.add_custom_button(__("Mở Hóa đơn mua"), () =>
				frappe.set_route("Form", "Purchase Invoice", frm.doc.purchase_invoice)
			);
		}
		if (tt === "Đã đối soát" && !frm.doc.purchase_invoice) {
			frm.add_custom_button(__("Tạo Hóa đơn mua nháp"), () => {
				if (frm.is_dirty()) return frappe.msgprint(__("Lưu phiếu trước."));
				frappe
					.xcall("erpnext.buying.tiep_nhan_hoa_don.tao_hoa_don.tao_hoa_don_mua", {
						phieu: frm.doc.name,
					})
					.then((pi) => {
						frm.reload_doc();
						frappe.show_alert({
							message: __("Đã tạo Hóa đơn mua nháp {0}", [pi]),
							indicator: "green",
						});
					});
			}).addClass("btn-primary");
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
					({ ly_do }) =>
						frappe
							.xcall("erpnext.buying.tiep_nhan_hoa_don.doi_soat.duyet_canh_bao", {
								phieu: frm.doc.name,
								ly_do,
							})
							.then(() => frm.reload_doc()),
					__("Duyệt lệch giá / vượt hạn mức hợp đồng khung"),
					__("Duyệt")
				);
			});
		}
	},
});

frappe.ui.form.on("Supplier Invoice Intake Item", {
	// Sửa mặt hàng là chọn tay (tầng 4): server giữ lựa chọn này khi đối soát lại.
	item_code(frm, cdt, cdn) {
		const d = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "chon_tay", d.item_code ? 1 : 0);
	},
});
