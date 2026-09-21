// Phiếu xếp / chuyển vị trí trên máy tính.
//
// LUẬT 19/09/2026 (chủ đầu tư): lô CHỈ được xếp vào đúng ô in trên tem lô — sai
// là máy chủ chặn (`vitri/o_tem.py`, gọi từ `LocationTransfer.validate`), không
// ai được vượt. Màn hình này chỉ báo SỚM, luật thật ở máy chủ.
//
// - Nút "Lấy hàng chưa xếp": đổ hàng ở ô "Chưa xếp vị trí" thành dòng, ô đến
//   lấy theo tem. Lô chưa có ô / ô trên tem hỏng thì KHÔNG thêm dòng (lưu sẽ bị
//   chặn) mà liệt kê ra để đi in lại tem.
// - Ô "Quét tem": quét tem lô là tự thêm dòng (chủ đầu tư: "quét mã lô thì auto
//   điền item, không phải chọn item xong chọn lô"); quét tem ô là xác nhận ô
//   đến của dòng vừa thêm — sai ô báo đỏ ngay.
// - Nút "Xếp trên PDA": mở trang `xep-hang-pda` (màn hình điện thoại).

const XEP_API = "erpnext.warehouse_operations.vitri.xep.";

frappe.ui.form.on("Location Transfer", {
	refresh(frm) {
		frm.__cho_o = null;
		if (frm.doc.docstatus !== 0) return;
		frm.add_custom_button(__("Xếp trên PDA"), () => frappe.set_route("xep-hang-pda"));
		if (!frm.doc.kho) return;
		frm.add_custom_button(__("Lấy hàng chưa xếp"), () => lay_hang_chua_xep(frm));
	},

	quet_tem(frm) {
		const ma = (frm.doc.quet_tem || "").trim();
		if (!ma) return;
		frm.set_value("quet_tem", "");
		if (!frm.doc.kho) {
			frappe.show_alert({ message: __("Chọn kho trước khi quét."), indicator: "orange" });
			return;
		}
		frappe.xcall(XEP_API + "quet_de_xep", { kho: frm.doc.kho, ma }).then((kq) => nhan_ma(frm, kq, ma));
	},

	kho(frm) {
		// Ô của kho cũ không dùng được cho kho mới — phép kiểm K2 phía máy chủ
		// sẽ chặn lúc lưu. Xoá luôn ở đây để người dùng khỏi phải sửa từng
		// dòng rồi mới biết.
		if (frm.doc.items && frm.doc.items.length) {
			frm.clear_table("items");
			frm.refresh_field("items");
			frappe.show_alert({ message: __("Đã xoá các dòng vì đổi kho."), indicator: "orange" });
		}
	},
});

function lay_hang_chua_xep(frm) {
	frappe.call({
		method: "erpnext.warehouse_operations.vitri.xep.hang_chua_xep",
		args: { kho: frm.doc.kho },
		callback(r) {
			let dong = r.message || [];
			if (!dong.length) {
				frappe.msgprint({
					title: __("Không có hàng chưa xếp"),
					message: __("Kho {0} không còn hàng nào ở ô 'Chưa xếp vị trí'.", [frm.doc.kho]),
					indicator: "green",
				});
				return;
			}
			// Lô bị luật tem chặn: không đưa vào phiếu (lưu sẽ hỏng), liệt kê ra.
			const bi_chan = dong.filter((d) => d.so_lo && !d.den_o);
			dong = dong.filter((d) => !(d.so_lo && !d.den_o));
			if (bi_chan.length) {
				frappe.msgprint({
					title: __("{0} lô chưa xếp được — cần in lại tem", [bi_chan.length]),
					indicator: "red",
					message:
						"<ul>" +
						bi_chan
							.map(
								(d) =>
									`<li><b>${frappe.utils.escape_html(d.so_lo)}</b> (${frappe.utils.escape_html(
										d.vat_tu
									)}): ${frappe.utils.escape_html(d.ly_do_goi_y || "")}</li>`
							)
							.join("") +
						"</ul>",
				});
			}
			if (!dong.length) return;
			frm.clear_table("items");
			dong.forEach((d) => {
				const r = frm.add_child("items");
				r.vat_tu = d.vat_tu;
				r.so_lo = d.so_lo;
				r.tu_o = d.tu_o;
				r.so_luong = d.so_luong;
				// Lô: ô in trên tem (bắt buộc). Hàng không lô: gợi ý theo gán vị trí.
				r.den_o = d.den_o;
			});
			frm.refresh_field("items");
			frappe.show_alert({
				message: __("Đã lấy {0} dòng — ô đến theo tem lô.", [dong.length]),
				indicator: "blue",
			});

			// Dòng còn trống ô đến (hàng KHÔNG lô chưa gán vị trí) — gộp theo lý do
			// thật (Ruling O: "chưa gán" / "vùng đã đầy" / lỗi dữ liệu cần ba việc
			// khác nhau). Lô thì không bao giờ tới đây trống ô: đã bị tách ra ở trên.
			const chua_co_goi_y = dong.filter((d) => !d.den_o);

			const tom_tat_theo_ly_do = (ds) => {
				const theo_ly_do = {};
				ds.forEach((d) => {
					const ly_do = d.ly_do_goi_y || __("không rõ lý do");
					theo_ly_do[ly_do] = (theo_ly_do[ly_do] || 0) + 1;
				});
				return Object.keys(theo_ly_do)
					.map((ly_do) => __("{0} dòng ({1})", [theo_ly_do[ly_do], ly_do]))
					.join(", ");
			};

			if (chua_co_goi_y.length) {
				frappe.show_alert({
					message: __("{0} dòng chưa có gợi ý: {1}.", [
						chua_co_goi_y.length,
						tom_tat_theo_ly_do(chua_co_goi_y),
					]),
					indicator: "orange",
				});
			}
		},
	});
}

// ------------------------------------------------------------- ô quét tem

function nhan_ma(frm, kq, ma) {
	const e = frappe.utils.escape_html;
	if (!kq || !kq.loai) {
		frappe.show_alert({ message: __("Không nhận ra mã {0}.", [e(ma)]), indicator: "red" });
		return;
	}
	if (kq.loai === "can_quet_lo") {
		frappe.show_alert({
			message: __("{0} có quản lý lô — quét tem LÔ, không phải mã hàng.", [e(kq.vat_tu)]),
			indicator: "orange",
		});
		return;
	}
	if (kq.loai === "o") return nhan_o(frm, kq);
	return nhan_lo(frm, kq);
}

function nhan_lo(frm, kq) {
	const e = frappe.utils.escape_html;
	const t = kq.o_tem || {};
	if (t.kiem && t.loi) {
		frappe.msgprint({ title: __("Không xếp được lô {0}", [e(kq.so_lo)]), indicator: "red", message: e(t.loi) });
		return;
	}
	if (!(kq.nguon || []).length) {
		frappe.show_alert({
			message: __("{0}{1}: không còn hàng nào để xếp ở kho này (hoặc đã lên hết phiếu xếp PDA của bạn).", [
				e(kq.vat_tu),
				kq.so_lo ? " · " + e(kq.so_lo) : "",
			]),
			indicator: "orange",
		});
		return;
	}
	const tu_o = kq.tu_o_mac_dinh;
	const nguon = (kq.nguon || []).find((n) => n.o === tu_o);
	// `con_xep_duoc` của máy chủ chỉ trừ phiếu PDA nháp của người dùng, không
	// biết các dòng CHƯA LƯU trên form này — tự trừ tiếp ở đây.
	const da_len = (frm.doc.items || [])
		.filter((r) => r.vat_tu === kq.vat_tu && (r.so_lo || null) === (kq.so_lo || null) && r.tu_o === tu_o)
		.reduce((a, r) => a + flt(r.so_luong), 0);
	const con = nguon ? flt(nguon.con_xep_duoc) - da_len : 0;
	if (tu_o && con <= 0) {
		frappe.show_alert({
			message: __("{0}{1} đã lên phiếu hết số đang có ở ô {2}.", [
				e(kq.vat_tu),
				kq.so_lo ? " · " + e(kq.so_lo) : "",
				e(tu_o),
			]),
			indicator: "orange",
		});
		return;
	}
	const r = frm.add_child("items");
	r.vat_tu = kq.vat_tu;
	r.so_lo = kq.so_lo;
	r.tu_o = tu_o || null;
	r.so_luong = tu_o ? con : 0;
	r.den_o = t.kiem ? t.o : (kq.goi_y && kq.goi_y.den_o) || null;
	frm.refresh_field("items");
	frm.dirty();
	frm.__cho_o = { dong: r.name, den_o: r.den_o, ma_in_nhan: t.ma_in_nhan, kiem: !!t.kiem };
	frappe.show_alert({
		message: tu_o
			? t.kiem
				? __("Đã thêm {0} · lô {1}. Quét tem ô {2} để xác nhận.", [
						e(kq.ten_hang),
						e(kq.so_lo),
						e(t.ma_in_nhan || t.o),
				  ])
				: __("Đã thêm {0}. Quét tem ô đến.", [e(kq.ten_hang)])
			: __("Đã thêm {0} — lô đang ở nhiều ô, chọn 'Từ ô' và số lượng trên dòng.", [e(kq.ten_hang)]),
		indicator: "blue",
	});
}

function nhan_o(frm, kq) {
	const e = frappe.utils.escape_html;
	const cho = frm.__cho_o;
	const r = cho && (frm.doc.items || []).find((x) => x.name === cho.dong);
	if (!r) {
		frappe.show_alert({ message: __("Quét tem LÔ trước, rồi mới quét tem ô."), indicator: "orange" });
		return;
	}
	if (cho.kiem) {
		if (kq.ma_o !== cho.den_o) {
			frappe.msgprint({
				title: __("Sai ô"),
				indicator: "red",
				message: __("Ô {0} không phải ô in trên tem lô {1}. Tem ghi ô <b>{2}</b> — xếp đúng ô đó.", [
					e(kq.ma_in_nhan || kq.ma_o),
					e(r.so_lo),
					e(cho.ma_in_nhan || cho.den_o),
				]),
			});
			return;
		}
		frappe.show_alert({ message: __("Đúng ô {0}.", [e(kq.ma_in_nhan || kq.ma_o)]), indicator: "green" });
	} else {
		frappe.model.set_value(r.doctype, r.name, "den_o", kq.ma_o);
		frappe.show_alert({ message: __("Đến ô {0}.", [e(kq.ma_in_nhan || kq.ma_o)]), indicator: "green" });
	}
	frm.__cho_o = null;
}
