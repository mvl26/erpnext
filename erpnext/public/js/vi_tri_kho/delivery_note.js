// Phiếu giao ↔ Lấy hàng (19/09/2026).
//
// Chủ đầu tư: "luồng tạo delivery note xong tạo lấy hàng rõ ràng hơn và có
// connection". Trước file này, form phiếu giao không có lối nào sang trang PDA —
// thủ kho phải vào workspace rồi dò phiếu trong danh sách — và không nói gì về
// việc lấy hàng đã tới đâu.
//
// Hai thứ ở đây: dòng tiến độ ở đầu form (đọc `lay_hang.tien_do_lay_hang`, đếm
// bằng CÙNG luật với trang PDA), và nút "Lấy hàng trên PDA" mở thẳng phiếu này.
// Ô đã lấy của từng dòng nằm ở cột "Vị trí lấy" (máy chủ ghi); sổ vị trí nằm ở
// tab Connections › Vị trí kho (`delivery_note_dashboard.py`).
//
// Bọc IIFE: `doctype_js` của Delivery Note ghép file này CHUNG một đoạn script
// với `einvoice/delivery_note.js` — hằng số cấp đỉnh trùng tên là vỡ cả hai.
(function () {
	const TIEN_DO = "erpnext.vi_tri_kho.vitri.lay_hang.tien_do_lay_hang";

	frappe.ui.form.on("Delivery Note", {
		refresh(frm) {
			xoa_tien_do(frm);
			if (frm.is_new() || frm.doc.is_return) return;
			frappe.xcall(TIEN_DO, { phieu: frm.doc.name }).then((t) => {
				// Người dùng có thể đã chuyển sang phiếu khác trong lúc chờ.
				if (!t || frm.doc.name !== frm.docname || frm.is_new()) return;
				hien_tien_do(frm, t);
				if (t.lay_duoc) {
					frm.add_custom_button(__("Lấy hàng trên PDA"), () => mo_pda(frm));
				}
			});
		},
	});

	function mo_pda(frm) {
		const di = () => frappe.set_route("lay-hang-pda", frm.doc.name);
		// Sửa chưa lưu (vd. vừa đổi số lượng) mà sang PDA thì trang lấy hàng thấy
		// bản CŨ trên máy chủ — lưu trước rồi mới đi.
		if (frm.is_dirty()) frm.save().then(di);
		else di();
	}

	// Khối tiến độ vẽ NGAY TRÊN BẢNG DÒNG HÀNG (tab Details). Không dùng:
	// - `set_headline_alert`/`set_intro`: form chỉ có MỘT ô thông báo đầu trang,
	//   Frappe dùng nó cho "Submit this document to confirm" và
	//   `einvoice/delivery_note.js` cũng dùng — câu nào về sau thắng, câu kia mất;
	// - `frm.dashboard.add_progress`: ở v15 dashboard nằm trong tab Connections,
	//   người mở phiếu ở tab Details không bao giờ thấy (đo trên erptest 19/09).
	function xoa_tien_do(frm) {
		$(frm.wrapper).find(".vtk-tien-do-lay-hang").remove();
	}

	function ve_khoi(frm, phan_tram, chu, mau) {
		xoa_tien_do(frm);
		const f = frm.fields_dict.items;
		if (!f || !f.$wrapper) return;
		const pt = Math.max(0, Math.min(100, phan_tram));
		$(`
			<div class="vtk-tien-do-lay-hang" style="margin-bottom: var(--margin-md);">
				<div class="d-flex align-items-center justify-content-between" style="gap: 8px;">
					<span class="indicator-pill ${mau}">${__("Lấy hàng")}</span>
					<span class="text-muted small">${Math.round(pt)}%</span>
				</div>
				<div class="progress" style="height: 6px; margin: 6px 0;">
					<div class="progress-bar ${pt >= 100 ? "progress-bar-success" : ""}" style="width: ${pt}%"></div>
				</div>
				<div class="small">${chu}</div>
			</div>
		`).insertBefore(f.$wrapper);
	}

	function hien_tien_do(frm, t) {
		const e = frappe.utils.escape_html;
		const xong = t.so_dong_du + t.so_dong_chot_thieu;
		const phu = [];
		if (t.so_dong_chot_thieu) phu.push(__("{0} dòng chốt thiếu", [t.so_dong_chot_thieu]));
		if (t.so_dong_khong_quet) phu.push(__("{0} dòng lấy tay (không quét)", [t.so_dong_khong_quet]));
		if (t.nguoi_lay && t.nguoi_lay.length) phu.push(__("người lấy: {0}", [t.nguoi_lay.map(e).join(", ")]));
		const them = phu.length ? " · " + phu.join(" · ") : "";

		let chu = null;
		let mau = "blue";
		// Theo SỐ LƯỢNG, không theo số dòng: phiếu một dòng lấy 3/5 phải hiện 60%, không 0%.
		// Dòng chốt thiếu tính là xong trọn dòng (đúng như `hoan_tat` sẽ hạ số lượng).
		const lay = t.tong_da_lay;
		let phan_tram = t.tong_can ? (100 * lay) / t.tong_can : 0;
		if (t.trang_thai === "du") phan_tram = 100;
		switch (t.trang_thai) {
			case "chua_lay":
				chu =
					__("Chưa quét dòng nào. Duyệt ngay thì hệ thống tự chọn ô theo hạn dùng (FEFO).") + them;
				break;
			case "dang_lay":
				chu =
					__("Đã lấy {0}/{1} · {2}/{3} dòng xong", [
						flt(lay, 3),
						flt(t.tong_can, 3),
						xong,
						t.so_dong_quet,
					]) + them;
				mau = "orange";
				break;
			case "du":
				chu =
					__("Đã lấy xong {0}/{1} dòng — sẵn sàng duyệt (bấm Hoàn tất trên PDA).", [
						xong,
						t.so_dong_quet,
					]) + them;
				mau = "green";
				break;
			case "da_duyet_quet":
				chu = __("Đã trừ sổ vị trí theo đúng ô thủ kho quét — xem cột Vị trí lấy.") + them;
				phan_tram = 100;
				mau = "green";
				break;
			case "da_duyet_fefo":
				chu = __(
					"Đã trừ sổ vị trí theo ô hệ thống tự chọn (FEFO, không quét trên PDA) — xem cột Vị trí lấy."
				);
				phan_tram = 100;
				mau = "green";
				break;
		}
		if (chu) ve_khoi(frm, phan_tram, chu, mau);
	}
})();
