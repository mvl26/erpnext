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

const DUONG_CAY_VI_TRI = "/assets/erpnext/js/vi_tri_kho/cay_chon_vi_tri.js";

frappe.ui.form.on("Item", {
	refresh(frm) {
		// Luôn xoá trước: `frm` được dùng lại cho mọi mặt hàng trong phiên, nên
		// không xoá thì mở một mặt hàng KHÔNG lưu kho ngay sau một mặt hàng đã
		// gán sẽ còn treo dòng vị trí của mặt hàng trước.
		frm.dashboard.clear_headline();
		if (frm.is_new() || !frm.doc.is_stock_item) return;

		frappe
			.call({
				method: "erpnext.vi_tri_kho.vitri.gan.vi_tri_cua_mat_hang",
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

				frm.add_custom_button(
					gan ? __("Đổi vị trí") : __("Gán vị trí"),
					() => chon_vi_tri(frm, gan),
					__("Vị trí kho")
				);
			});
	},
});

function hien_vi_tri(frm, gan) {
	const esc = frappe.utils.escape_html;
	if (!gan) {
		frm.dashboard.set_headline_alert(
			__("Mặt hàng này chưa gán vị trí cố định — tem in ra sẽ trống ô vị trí."),
			"orange"
		);
		return;
	}
	const lien_ket = `<a href="/app/item-location-preference/${encodeURIComponent(gan.name)}">${esc(
		gan.vi_tri
	)}</a>`;
	frm.dashboard.set_headline_alert(
		__("Vị trí cố định: {0} · {1}{2}", [
			lien_ket,
			esc(gan.kho),
			gan.cap_do ? " · " + esc(__("cấp {0}", [gan.cap_do])) : "",
		]),
		"blue"
	);
}

function chon_vi_tri(frm, gan) {
	const d = new frappe.ui.Dialog({
		title: __("Vị trí cố định cho {0}", [frm.doc.item_name || frm.doc.name]),
		fields: [
			{
				fieldname: "kho",
				fieldtype: "Link",
				options: "Warehouse",
				label: __("Kho"),
				reqd: 1,
				default: gan ? gan.kho : null,
				// Chỉ kho ĐÃ bật quản lý vị trí mới có cây vị trí. Chọn một kho
				// chưa bật thì cây mở ra trống trơn và người dùng không biết vì sao.
				get_query: () => ({ filters: { custom_quan_ly_vi_tri: 1, is_group: 0 } }),
				description: __("Chỉ hiện kho đã bật quản lý vị trí."),
			},
		],
		primary_action_label: __("Chọn trên cây vị trí"),
		primary_action(v) {
			d.hide();
			frappe.require(DUONG_CAY_VI_TRI, () => {
				// `tru_ten`: khi ĐỔI một gán đã có, loại chính gán đó ra khỏi phép
				// đếm "nhánh này đã có mặt hàng khác giữ" của cây — nếu không, dời
				// gán lên nút cha của chính nó (thao tác hợp lệ, máy chủ cũng loại
				// trừ y hệt) sẽ bị khoá oan. Xem chú thích đầu `cay_chon_vi_tri.js`.
				erpnext.vi_tri_kho.chon_vi_tri(v.kho, (o) => luu(frm, v.kho, o), gan ? gan.name : null);
			});
		},
	});
	d.show();
}

function luu(frm, kho, vi_tri) {
	frappe
		.call({
			method: "erpnext.vi_tri_kho.vitri.gan.gan_vi_tri_cho_mat_hang",
			args: { vat_tu: frm.doc.name, kho: kho, vi_tri: vi_tri },
			freeze: true,
			freeze_message: __("Đang gán vị trí…"),
		})
		.then((r) => {
			frappe.show_alert({
				message: __("Đã gán vị trí {0} cho mặt hàng này.", [r.message.vi_tri]),
				indicator: "green",
			});
			frm.reload_doc();
		});
	// Lỗi (chồng lấn nhánh, sai kho, thiếu quyền…) do `validate()` của bản gán ném
	// ra và `frappe.call` tự hiện — không nuốt, không viết lại câu báo ở đây, vì
	// câu báo của máy chủ đã nêu đích danh mặt hàng nào đang giữ nhánh đó.
}
