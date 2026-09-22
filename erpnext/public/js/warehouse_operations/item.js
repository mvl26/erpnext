// Gán vị trí cố định ngay trên form mặt hàng.
//
// VÌ SAO CÓ FILE NÀY: chủ đầu tư thử luồng thật ngày 17/09/2026 — "trong item
// chưa có phần setup vị trí". Việc gán chỉ làm được trên doctype riêng `Item
// Location Preference` mà không ai biết tìm ở đâu, nên mặt hàng nhập kho rồi vẫn
// chưa từng có vị trí, và tem in ra ô vị trí trống.
//
// KHÔNG thêm trường nào lên Item. Vẫn đúng MỘT nguồn dữ liệu là bản gán, và việc
// lưu đi qua `gan.gan_vi_tri_cho_mat_hang`, tức qua `validate()` của bản gán —
// đủ các phép kiểm chống chồng lấn nhánh của mặt hàng khác. Cây chọn vị trí là
// ĐÚNG cây form bản gán đang dùng (`cay_chon_vi_tri.js`), không phải bản chép.
//
// Hiển thị bằng `frm.dashboard.set_headline_alert`, KHÔNG bằng `frm.set_intro`:
// `stock/doctype/item/item.js` gốc tự gọi `frm.set_intro()` để xoá dòng giới thiệu
// mỗi lần làm mới (và đặt câu riêng cho mặt hàng mẫu / biến thể) — dùng chung chỗ
// đó thì hai bên xoá chữ của nhau tuỳ thứ tự chạy.

const DUONG_CAY_VI_TRI = "/assets/erpnext/js/warehouse_operations/cay_chon_vi_tri.js";

frappe.ui.form.on("Item", {
	refresh(frm) {
		// Luôn xoá trước: `frm` được dùng lại cho mọi mặt hàng trong phiên, nên
		// không xoá thì mở một mặt hàng KHÔNG lưu kho ngay sau một mặt hàng đã
		// gán sẽ còn treo dòng vị trí của mặt hàng trước.
		frm.dashboard.clear_headline();
		if (frm.is_new() || !frm.doc.is_stock_item) return;

		frappe
			.call({
				method: "erpnext.warehouse_operations.vitri.gan.vi_tri_cua_mat_hang",
				args: { vat_tu: frm.doc.name },
			})
			.then((r) => {
				const gan = r.message;
				hien_vi_tri(frm, gan);

				// Bản gán chỉ cho System Manager và Stock Manager tạo / sửa. Không
				// hiện nút cho người không có quyền — bấm vào rồi mới báo lỗi quyền
				// là bắt người dùng đi hết một hộp thoại cho một việc không làm được.
				// Máy chủ vẫn tự kiểm quyền; đây chỉ là không mời người ta vào.
				const duoc_gan =
					frappe.model.can_create("Item Location Preference")
					|| frappe.model.can_write("Item Location Preference");
				if (!duoc_gan) return;

				frm.add_custom_button(__("Gán vị trí"), () => hop_gan(frm, gan), __("Vị trí kho"));
			});
	},
});

function hien_vi_tri(frm, gan) {
	const esc = frappe.utils.escape_html;
	if (!gan || !(gan.dong || []).length) {
		frm.dashboard.set_headline_alert(
			__("Mặt hàng này chưa gán vị trí cố định — tem in ra sẽ trống ô vị trí."),
			"orange"
		);
		return;
	}
	// Nhiều vị trí (22/09/2026): liệt kê đủ, theo thứ tự dòng.
	const ds = gan.dong
		.map(
			(d) =>
				`${esc(d.ma_in_nhan || d.vi_tri)} <span class="text-muted">(${esc(d.cap_do || "")}, ${esc(
					d.kho || ""
				)})</span>`
		)
		.join(" · ");
	const lien_ket = `<a href="/app/item-location-preference/${encodeURIComponent(gan.name)}">${__(
		"xem bản gán"
	)}</a>`;
	frm.dashboard.set_headline_alert(__("Vị trí cố định: {0} · {1}", [ds, lien_ket]), "blue");
}

// Hộp thoại gán NHIỀU vị trí (22/09/2026 — chủ đầu tư: "1 item có thể gán nhiều vị
// trí khác nhau… ở ô này và ở tầng bên kia nữa").
//
// Danh sách `ds` sống trong bộ nhớ của hộp thoại tới khi bấm Lưu — thêm/bỏ/đổi thứ
// tự không gọi máy chủ. Lưu gọi `gan_vi_tri_cho_mat_hang` với CẢ danh sách, tức đi
// qua `validate()` của bản gán: mọi luật (chồng mặt hàng khác, tự lồng nhau, nhánh
// đang có hàng khác) do máy chủ nói, câu báo "Dòng N: …" hiện nguyên văn.
//
// Thứ tự dòng chỉ để phân định khi có nhiều ô trống cùng lúc (gợi ý đi "ô trống
// trước, bất kể thuộc vị trí nào") — nên không gọi là vị trí "chính/phụ".
function hop_gan(frm, gan) {
	const esc = frappe.utils.escape_html;
	const ds = ((gan && gan.dong) || []).map((x) => Object.assign({}, x));

	const d = new frappe.ui.Dialog({
		title: __("Vị trí cố định cho {0}", [frm.doc.item_name || frm.doc.name]),
		size: "large",
		fields: [
			{ fieldname: "bang", fieldtype: "HTML" },
			{
				fieldname: "ghi_chu",
				fieldtype: "HTML",
				options: `<p class="text-muted small">${__(
					"Một mặt hàng có thể giữ nhiều vị trí, kể cả ở kho khác. Gợi ý ô khi nhập hàng: ô trống trước (bất kể thuộc vị trí nào), hết ô trống mới dồn vào ô đang có chính mặt hàng này. Thứ tự chỉ dùng khi có nhiều ô trống cùng lúc."
				)}</p>`,
			},
		],
		primary_action_label: __("Lưu"),
		primary_action() {
			if (!ds.length) {
				frappe.msgprint(__("Cần ít nhất một vị trí."));
				return;
			}
			frappe
				.call({
					method: "erpnext.warehouse_operations.vitri.gan.gan_vi_tri_cho_mat_hang",
					args: { vat_tu: frm.doc.name, vi_tri: ds.map((x) => x.vi_tri) },
					freeze: true,
					freeze_message: __("Đang gán vị trí…"),
				})
				.then(() => {
					d.hide();
					frappe.show_alert({ message: __("Đã lưu {0} vị trí.", [ds.length]), indicator: "green" });
					frm.reload_doc();
				});
			// Lỗi do `validate()` của bản gán ném ra và `frappe.call` tự hiện — không
			// viết lại câu báo ở đây: máy chủ đã nêu đích danh dòng nào, đụng ai.
		},
		secondary_action_label: __("Thêm vị trí"),
		secondary_action() {
			them_vi_tri();
		},
	});

	function ve() {
		const $b = d.fields_dict.bang.$wrapper;
		if (!ds.length) {
			$b.html(`<p class="text-muted">${__("Chưa có vị trí nào — bấm Thêm vị trí.")}</p>`);
			return;
		}
		const dong = ds
			.map(
				(x, i) => `<tr>
					<td>${i + 1}</td>
					<td><b>${esc(x.ma_in_nhan || x.vi_tri)}</b></td>
					<td>${esc(x.cap_do || "")}</td>
					<td>${esc(x.kho || "")}</td>
					<td class="text-right">
						<button class="btn btn-xs btn-default gvt-len" data-i="${i}" ${i === 0 ? "disabled" : ""}>↑</button>
						<button class="btn btn-xs btn-default gvt-xuong" data-i="${i}" ${
					i === ds.length - 1 ? "disabled" : ""
				}>↓</button>
						<button class="btn btn-xs btn-danger gvt-bo" data-i="${i}">×</button>
					</td>
				</tr>`
			)
			.join("");
		$b.html(`
			<table class="table table-bordered">
				<thead><tr>
					<th style="width:48px">#</th><th>${__("Vị trí")}</th><th>${__("Cấp")}</th>
					<th>${__("Kho")}</th><th style="width:120px"></th>
				</tr></thead>
				<tbody>${dong}</tbody>
			</table>`);
	}

	d.fields_dict.bang.$wrapper.on("click", "button", (ev) => {
		const $n = $(ev.currentTarget);
		const i = Number($n.attr("data-i"));
		if ($n.hasClass("gvt-bo")) ds.splice(i, 1);
		else if ($n.hasClass("gvt-len") && i > 0) [ds[i - 1], ds[i]] = [ds[i], ds[i - 1]];
		else if ($n.hasClass("gvt-xuong") && i < ds.length - 1) [ds[i + 1], ds[i]] = [ds[i], ds[i + 1]];
		ve();
	});

	function them_vi_tri() {
		const hoi_kho = new frappe.ui.Dialog({
			title: __("Thêm vị trí — chọn kho"),
			fields: [
				{
					fieldname: "kho",
					fieldtype: "Link",
					options: "Warehouse",
					label: __("Kho"),
					reqd: 1,
					default: ds.length ? ds[ds.length - 1].kho : null,
					// Chỉ kho ĐÃ bật quản lý vị trí mới có cây vị trí. Chọn một kho
					// chưa bật thì cây mở ra trống trơn và người dùng không biết vì sao.
					get_query: () => ({ filters: { custom_quan_ly_vi_tri: 1, is_group: 0 } }),
					description: __("Chỉ hiện kho đã bật quản lý vị trí."),
				},
			],
			primary_action_label: __("Chọn trên cây vị trí"),
			primary_action(v) {
				hoi_kho.hide();
				frappe.require(DUONG_CAY_VI_TRI, () => {
					// `tru_ten`: loại MỌI dòng đã lưu của bản gán này khỏi "đã có chủ";
					// `dang_co`: danh sách ĐANG trong hộp thoại — nút giao nó bị khoá.
					// Xem chú thích đầu `cay_chon_vi_tri.js` và `gan.cay_chon_vi_tri`.
					erpnext.warehouse_operations.chon_vi_tri(
						v.kho,
						(o) => {
							frappe.db.get_value("Storage Location", o, ["ma_in_nhan", "kho"]).then((r) => {
								const sl = r.message || {};
								ds.push({ vi_tri: o, ma_in_nhan: sl.ma_in_nhan || o, kho: sl.kho || v.kho, cap_do: ten_cap(o) });
								ve();
							});
						},
						gan ? gan.name : null,
						ds.map((x) => x.vi_tri)
					);
				});
			},
		});
		hoi_kho.show();
	}

	ve();
	d.show();
}

// Chỉ để HIỂN THỊ trong hộp thoại trước khi lưu: mã vị trí mỗi cấp thêm 2 ký tự
// (`ma_vi_tri.TEN_CAP`, `MAU_CAP` — Khu 2 / Dãy 4 / Khoang 6 / Tầng 8 / Ô 10). Lưu
// xong máy chủ tự tính lại `cap_do` từ chính mã, không tin giá trị này.
const TEN_CAP = [__("Khu"), __("Dãy"), __("Khoang"), __("Tầng"), __("Ô")];
function ten_cap(ma) {
	return TEN_CAP[(ma || "").length / 2 - 1] || "";
}
