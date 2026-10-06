frappe.ui.form.on("Warehouse Location Setup", {
	refresh(frm) {
		if (frm.is_new()) return;

		if (frm.doc.trang_thai === "Chưa bật") {
			frm.add_custom_button("Xem trước chuyển đổi", () => xem_truoc(frm));
		}
		if (frm.doc.trang_thai === "Đang bật") {
			frm.add_custom_button("Tắt quản lý vị trí", () => goi(frm, "tat", "Đã tắt quản lý vị trí."));
			frm.add_custom_button("Đồng bộ lại", () => goi(frm, "dong_bo_lai", "Đã đồng bộ lại."));
		}
		if (["Đã tắt", "Cần đồng bộ lại"].includes(frm.doc.trang_thai)) {
			frm.add_custom_button("Đồng bộ lại", () => goi(frm, "dong_bo_lai", "Đã đồng bộ lại."));
		}
	},
});

function xem_truoc(frm) {
	frappe.call({
		method: "erpnext.warehouse_operations.vitri.bat_kho.xem_truoc",
		args: { kho: frm.doc.kho },
		freeze: true,
		callback: (r) => {
			const k = r.message;
			const canh_bao = (k.canh_bao || []).map((c) => `<li>${frappe.utils.escape_html(c)}</li>`).join("");
			frappe.confirm(
				`<p>Sẽ ghi <b>${k.so_dong}</b> dòng sổ cho <b>${k.so_mat_hang}</b> mặt hàng,
				 <b>${k.so_lo}</b> lô — tất cả vào ô "Chưa xếp vị trí".</p>
				 ${canh_bao ? `<ul>${canh_bao}</ul>` : ""}
				 <p>Bật quản lý vị trí cho kho này?</p>`,
				() => goi(frm, "bat", "Đã bật quản lý vị trí."),
			);
		},
	});
}

function goi(frm, phuong_thuc, thong_bao) {
	frappe.call({
		method: `erpnext.warehouse_operations.vitri.bat_kho.${phuong_thuc}`,
		args: { kho: frm.doc.kho },
		freeze: true,
		callback: () => {
			frappe.show_alert({ message: thong_bao, indicator: "green" });
			frm.reload_doc();
		},
	});
}
