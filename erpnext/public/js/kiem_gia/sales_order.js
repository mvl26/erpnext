// Kiểm giá bán (BA12): nút "Áp giá đề xuất" — D06, giá theo hệ số được ưu tiên hơn bảng giá.
// Giá đề xuất được tính khi lưu và khi sửa dòng (tinh_lai.js); nút chép giá đề xuất vào đơn
// giá của các dòng còn lệch. Bảng "Kiểm giá bán" dưới lưới mặt hàng hiện kết quả của mọi
// dòng, không phải mở từng dòng.
// Q10: SO đã Submit còn dòng chờ khách chấp thuận giá thì nhắc ngay đầu form.
frappe.provide("erpnext.kiem_gia");

frappe.ui.form.on("Sales Order", {
	setup: () => erpnext.kiem_gia.to_mau_trang_thai_gia("Sales Order Item"),
	refresh(frm) {
		erpnext.kiem_gia.ve_bang_kiem_gia(frm);
		const cho = (frm.doc.items || []).filter((d) => d.cho_chap_thuan);
		if (frm.doc.docstatus === 1 && cho.length) {
			frm.set_intro(
				__(
					"Dòng {0} chờ khách chấp thuận giá: mở dòng, nhập số văn bản, người đại diện KH, ngày chấp thuận rồi bấm Cập nhật. Chưa nhập thì chưa tạo được Phiếu giao hàng / Hóa đơn bán cho các dòng này.",
					[cho.map((d) => `${d.idx} (${frappe.utils.escape_html(d.item_code)})`).join(", ")]
				),
				"orange"
			);
		}
		const lech = (frm.doc.items || []).filter(
			(d) => d.gia_de_xuat && ["Thấp hơn", "Cao hơn"].includes(d.trang_thai_gia)
		);
		if (frm.doc.docstatus !== 0 || !lech.length) return;
		frm.add_custom_button(__("Áp giá đề xuất"), () => {
			lech.forEach((d) => frappe.model.set_value(d.doctype, d.name, "rate", d.gia_de_xuat));
			frappe.show_alert({
				message: __("Đã áp giá đề xuất cho {0} dòng. Lưu để kiểm lại.", [lech.length]),
				indicator: "blue",
			});
		});
	},
	kiem_gia_tinh_xong: (frm) => erpnext.kiem_gia.ve_bang_kiem_gia(frm),
});

frappe.ui.form.on("Sales Order Item", {
	qty: (frm) => erpnext.kiem_gia.ve_bang_kiem_gia(frm),
	uom: (frm) => erpnext.kiem_gia.ve_bang_kiem_gia(frm),
	items_remove: (frm) => erpnext.kiem_gia.ve_bang_kiem_gia(frm),
});

erpnext.kiem_gia.ve_bang_kiem_gia = function (frm) {
	const field = frm.fields_dict.bang_kiem_gia;
	if (!field) return;
	// Khách không có hệ số: dòng không có trạng thái, không hiện bảng (R07).
	const dong = (frm.doc.items || []).filter((d) => d.item_code && d.trang_thai_gia);
	frm.toggle_display("bang_kiem_gia", dong.length > 0);
	if (!dong.length) {
		field.$wrapper.empty();
		return;
	}

	const e = frappe.utils.escape_html;
	const tien = (v) => format_currency(v, frm.doc.currency, 4);
	const hien_thi = (d) => erpnext.kiem_gia.trang_thai_hien_thi(d.trang_thai_gia, d);
	const dem = (ds) => dong.filter((d) => ds.includes(hien_thi(d))).length;
	const lech = dem(["Thấp hơn", "Cao hơn"]);
	const chua_co = dem(["Chưa có giá mua"]);
	const tom_tat =
		lech || chua_co
			? `<span style="color: var(--red-600); font-weight: 600">${[
					lech && __("{0} dòng lệch giá bán đề xuất", [lech]),
					chua_co && __("{0} dòng chưa có giá mua", [chua_co]),
			  ]
					.filter(Boolean)
					.join(", ")}</span>`
			: `<span style="color: var(--green-600); font-weight: 600">${__("Khớp giá cả đơn")}</span>`;
	const ghi_chu =
		frm.doc.docstatus === 0
			? __("giá chưa VAT, theo ĐVT của dòng; chọn NCC dự kiến hoặc đổi đơn giá thì tính lại ngay")
			: __(
					"giá chưa VAT, theo ĐVT của dòng; kết quả lúc lập đơn, đổi NCC dự kiến thì tính lại dòng đó (bấm Cập nhật để lưu)"
			  );

	const hang = dong
		.map((d) => {
			const tt = hien_thi(d);
			const mau = erpnext.kiem_gia.MAU_TRANG_THAI_GIA[tt] || "gray";
			// Chưa có giá mua / Bỏ qua: không có giá để so (đã lưu thì ô tiền trống thành 0).
			const co_gia = !["Chưa có giá mua", "Bỏ qua"].includes(d.trang_thai_gia);
			const cl = flt(d.chenh_lech_gia);
			const chenh = cl ? (cl > 0 ? "+" : "-") + format_number(Math.abs(cl), null, 4) : "0";
			return `<tr>
				<td>
					<a href="#" data-dong="${e(d.name)}">${e(d.item_name || d.item_code)}</a>
					<div class="text-muted small">${e(d.item_code)}</div>
				</td>
				<td data-ncc="${e(d.name)}"></td>
				<td>${e(d.uom || "")}</td>
				<td class="text-right text-nowrap">${co_gia ? tien(d.gia_mua) : ""}</td>
				<td class="text-right text-nowrap">${tien(d.net_rate)}</td>
				<td class="text-right text-nowrap">${co_gia ? tien(d.gia_de_xuat) : ""}</td>
				<td class="text-right text-nowrap">${co_gia ? chenh : ""}</td>
				<td><span class="indicator-pill ${mau}" title="${e(d.ghi_chu_gia || "")}">${e(__(tt))}</span></td>
			</tr>`;
		})
		.join("");

	field.$wrapper.html(`
		<div class="mt-4">
			<div style="font-weight: 600">${__("Kiểm giá bán")}</div>
			<div class="mb-2">${tom_tat} <span class="text-muted">· ${ghi_chu}</span></div>
			<table class="table table-bordered" style="margin-bottom: 0">
				<thead><tr>
					<th style="min-width: 160px">${__("Mặt hàng")}</th>
					<th style="min-width: 190px">${__("NCC dự kiến")}</th>
					<th>${__("ĐVT")}</th>
					<th class="text-right">${__("Giá mua")}</th>
					<th class="text-right" title="${__("Đơn giá trên đơn, sau chiết khấu, chưa VAT")}">${__("Giá bán")}</th>
					<th class="text-right" title="${__("Giá mua x hệ số của khách")}">${__("Giá bán đề xuất")}</th>
					<th class="text-right" title="${__("Giá bán - giá bán đề xuất")}">${__("Chênh lệch")}</th>
					<th>${__("Trạng thái giá")}</th>
				</tr></thead>
				<tbody>${hang}</tbody>
			</table>
		</div>`);
	dong.forEach((d) => erpnext.kiem_gia.o_chon_ncc(frm, d, field.$wrapper.find(`[data-ncc="${d.name}"]`)));
	// Mở dòng để nhập thông tin khách chấp thuận.
	field.$wrapper.find("[data-dong]").on("click", (ev) => {
		ev.preventDefault();
		frm.fields_dict.items.grid.grid_rows_by_docname[$(ev.currentTarget).attr("data-dong")]?.toggle_view(
			true
		);
	});
};

// Ô chọn NCC dự kiến ngay trong bảng: gợi ý NCC đang có giá cho mặt hàng kèm giá mua
// (gia_goc.ncc_co_gia). Chọn xong ghi vào dòng; tinh_lai.js tính lại và vẽ lại bảng.
erpnext.kiem_gia.o_chon_ncc = function (frm, d, $td) {
	// Trường bị ẩn trong chi tiết dòng; quyền sửa xét như khi trường hiện.
	const df = { ...frappe.meta.get_docfield(d.doctype, "ncc_du_kien", frm.doc.name), hidden: 0 };
	if (frappe.perm.get_field_display_status(df, d, frm.perm) !== "Write") {
		$td.text(d.ncc_du_kien || "");
		return;
	}
	const o = frappe.ui.form.make_control({
		parent: $td,
		df: {
			fieldtype: "Link",
			options: "Supplier",
			fieldname: "ncc_du_kien",
			placeholder: __("NCC mặc định của mặt hàng"),
			get_query: () => ({
				query: "erpnext.selling.kiem_gia.gia_goc.ncc_co_gia",
				filters: { item_code: d.item_code, ngay: frm.doc.transaction_date, company: frm.doc.company },
			}),
			change: () => {
				const v = o.get_value() || null;
				if (v !== (d.ncc_du_kien || null))
					frappe.model.set_value(d.doctype, d.name, "ncc_du_kien", v);
			},
		},
		only_input: true,
		render_input: true,
	});
	o.set_input(d.ncc_du_kien || "");
};
