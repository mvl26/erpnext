// Danh sách "máy đang cầm thẻ" và nút thu hồi cho ca MẤT ĐÚNG MỘT MÁY.
//
// Nút này phải giết được khoá thật, không chỉ hạ một cái cờ: app đang mở ra
// internet qua ngrok, nên kẻ nhặt được máy dùng nó từ bất cứ đâu. Việc giết khoá
// nằm ở máy chủ (`the_pda.thu_hoi_may`) — ở đây chỉ hỏi cho chắc rồi gọi, và câu
// hỏi phải nói đúng hậu quả để trưởng kho không bấm nhầm.
//
// Thu hồi CẢ NGƯỜI (mọi máy + thẻ) thì bấm "Thu hồi thẻ" trên `PDA Badge`.

frappe.ui.form.on("PDA Thiet Bi", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.con_hieu_luc) {
			frm.add_custom_button(__("Thu hồi máy"), () => thu_hoi_may(frm));
		} else {
			frm.dashboard.set_headline(
				__("Máy này đã bị thu hồi — mọi lời gọi từ nó đều bị từ chối.")
			);
		}
	},
});

function thu_hoi_may(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Thu hồi máy {0}", [frm.doc.ten_may || frm.doc.ma_may]),
		primary_action_label: __("Thu hồi"),
		primary_action: () => {
			d.hide();
			frappe
				.xcall("erpnext.warehouse_operations.vitri.the_pda.thu_hoi_may", {
					ma_may: frm.doc.ma_may,
				})
				.then((kq) => {
					frappe.show_alert({
						message: kq && kq.con_may_khac
							? __("Đã thu hồi máy này. {0} vẫn còn máy khác đang dùng.", [kq.nguoi_dung])
							: kq && kq.khoa_da_xoa
								? __("Đã thu hồi máy và xoá khoá của {0}.", [kq.nguoi_dung])
								: __("Đã thu hồi máy {0}.", [(kq && kq.nguoi_dung) || ""]),
						indicator: "orange",
					});
					// Ca khoá KHÔNG do PDA cấp: `show_alert` tự tắt sau vài giây, mà đây là
					// thứ trưởng kho phải ĐỌC và quyết định — nên dùng msgprint, không dùng
					// dải báo thoáng qua.
					if (kq && kq.ly_do_giu_khoa) {
						frappe.msgprint({
							title: __("Khoá API vẫn còn"),
							message: kq.ly_do_giu_khoa,
							indicator: "orange",
						});
					}
					frm.reload_doc();
				});
		},
		secondary_action_label: __("Không"),
		secondary_action: () => d.hide(),
	});
	d.$body.append(
		`<p>${__(
			"Máy này sẽ ngừng gọi được máy chủ ngay. Nếu đây là chiếc máy cuối cùng của "
				+ "{0} thì khoá của người đó cũng bị xoá — lần sau nhận máy phải quét thẻ lại.",
			[frm.doc.ho_ten || frm.doc.nguoi_dung]
		)}</p>`
	);
	d.show();
}
