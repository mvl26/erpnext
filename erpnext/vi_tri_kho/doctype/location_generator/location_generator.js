frappe.ui.form.on("Location Generator", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button("Xem trước rồi sinh ô", () => xem_truoc(frm));
	},
});

function tham_so(frm) {
	return {
		kho: frm.doc.kho,
		khu: frm.doc.khu,
		so_day: frm.doc.so_day,
		so_khoang_moi_day: frm.doc.so_khoang_moi_day,
		so_tang_moi_khoang: frm.doc.so_tang_moi_khoang,
		so_o_moi_tang: frm.doc.so_o_moi_tang,
	};
}

function xem_truoc(frm) {
	const args = tham_so(frm);
	frappe.call({
		method: "erpnext.vi_tri_kho.vitri.sinh_ma.xem_truoc_sinh",
		args,
		freeze: true,
		callback: (r) => {
			const k = r.message;
			if (k.trung.length) {
				frappe.msgprint({
					title: "Có mã ô đã tồn tại",
					indicator: "red",
					message: `${k.trung.length} mã đã có: ${k.trung.slice(0, 5).join(", ")}.
					          Đổi khu hoặc kích thước rồi thử lại — hệ sẽ không tạo ô nào cả.`,
				});
				return;
			}
			const mau = k.ma_mau.map((m) => frappe.utils.escape_html(m)).join(", ");
			frappe.confirm(
				`<p>Sẽ tạo <b>${k.so_o}</b> ô.</p><p>Ví dụ: ${mau}${k.so_o > 20 ? " …" : ""}</p>
				 <p><b>Mã ô không sửa được sau khi tạo</b> — tem đã in và người đã quen mã.
				 Kiểm kỹ trước khi tạo.</p>`,
				() => {
					frappe.call({
						method: "erpnext.vi_tri_kho.vitri.sinh_ma.sinh",
						args,
						freeze: true,
						callback: (r2) => {
							frm.set_value("so_o_da_tao", r2.message.so_o_da_tao);
							frm.save();
							frappe.show_alert({ message: `Đã tạo ${r2.message.so_o_da_tao} ô.`, indicator: "green" });
						},
					});
				},
			);
		},
	});
}
