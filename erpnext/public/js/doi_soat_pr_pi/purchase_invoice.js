// Đối soát Phiếu nhập ↔ Hóa đơn mua (YC5): trạng thái ở đầu form, nút Đối soát lại (ghép dòng
// rồi lưu lại để tính từ đầu) và Duyệt ngoại lệ (E8, chỉ hiện với Kế toán trưởng / Ban Điều hành).
// Mọi kiểm tra nằm ở server; file này chỉ hiển thị và gọi `doi_soat_lai` / `duyet_ngoai_le`.
frappe.ui.form.on("Purchase Invoice", {
	refresh(frm) {
		const trang_thai = frm.doc.trang_thai_doi_soat_pr;
		if (!trang_thai) return;

		const mau = { Khớp: "green", Lệch: "red", "Ngoại lệ đã duyệt": "orange" }[trang_thai] || "gray";
		// Nhãn ở dashboard chỉ thấy trong thẻ Liên kết: trạng thái khớp / ngoại lệ hiện thêm ở đầu form.
		frm.dashboard.add_indicator(__("Đối soát Phiếu nhập: {0}", [__(trang_thai)]), mau);
		if (trang_thai === "Khớp") {
			frm.set_intro(__("Đối soát Phiếu nhập: Khớp."), "green");
		} else if (trang_thai === "Ngoại lệ đã duyệt") {
			frm.set_intro(
				__("Đối soát Phiếu nhập: Ngoại lệ đã duyệt ({0}).", [
					frappe.utils.escape_html(frm.doc.ly_do_ngoai_le || ""),
				]),
				"orange"
			);
		}
		frm.add_custom_button(
			__("Nhật ký đối soát"),
			() =>
				frappe.set_route("List", "Purchase Invoice PR Reconciliation Log", {
					hoa_don: frm.doc.name,
				}),
			__("Đối soát Phiếu nhập")
		);
		if (frm.doc.docstatus !== 0) return;

		if (trang_thai === "Lệch") {
			frm.set_intro(
				__(
					"Hóa đơn lệch Phiếu nhập mua ở {0} điểm, chưa Nộp được. Xem Bảng chênh lệch, chọn Nhánh xử lý rồi sửa; lưu lại để đối soát lại.",
					[(frm.doc.chenh_lech_pr || []).length]
				),
				"red"
			);
		} else if (trang_thai === "Chưa đối soát") {
			frm.set_intro(__("Phiếu nhập liên quan vừa thay đổi. Bấm Đối soát lại."), "orange");
		}

		frm.add_custom_button(
			__("Đối soát lại"),
			() => {
				if (frm.is_dirty()) {
					frm.save();
					return;
				}
				frappe
					.call({
						method: "erpnext.accounts.doi_soat_pr_pi.doi_soat.doi_soat_lai",
						args: { hoa_don: frm.doc.name },
						freeze: true,
					})
					.then(() => frm.reload_doc());
			},
			__("Đối soát Phiếu nhập")
		);

		if (trang_thai === "Lệch" && frm.doc.__onload && frm.doc.__onload.co_quyen_duyet_ngoai_le) {
			frm.add_custom_button(
				__("Duyệt ngoại lệ"),
				() => {
					if (frm.is_dirty()) {
						frappe.msgprint(__("Lưu hóa đơn trước khi duyệt ngoại lệ."));
						return;
					}
					frappe.prompt(
						{
							fieldname: "ly_do",
							fieldtype: "Small Text",
							label: __("Lý do cho Nộp khi còn lệch"),
							reqd: 1,
						},
						({ ly_do }) =>
							frappe
								.call({
									method: "erpnext.accounts.doi_soat_pr_pi.doi_soat.duyet_ngoai_le",
									args: { hoa_don: frm.doc.name, ly_do },
									freeze: true,
								})
								.then(() => frm.reload_doc()),
						__("Duyệt ngoại lệ đối soát"),
						__("Duyệt")
					);
				},
				__("Đối soát Phiếu nhập")
			);
		}
	},
});
