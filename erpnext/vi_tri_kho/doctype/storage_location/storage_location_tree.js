// Nút "In tem" trên từng nốt của cây vị trí: bấm ở nốt nào thì in tem cho
// mọi ô lá thuộc nhánh dưới nốt đó.
//
// BA TẦNG, RANH GIỚI CỐ Ý:
//
//   `vitri/tem.py`                 — CHỌN in những ô nào   (Python, có test)
//   `public/js/vi_tri_kho/tem_vi_tri.js` — VẼ con tem      (dùng chung 3 chỗ)
//   file này                        — hộp thoại: chọn khổ, số bản, xem trước
//
// Phần CHỌN nằm ở Python vì đó là chỗ hỏng đắt và im lặng: in THIẾU thì thấy
// ngay (kệ trống tem), in THỪA thì ra một xấp tem của nhánh khác, dán lên kệ,
// và mọi lần quét sau đó đều trỏ sai chỗ mà không có gì báo lỗi.
//
// Phần VẼ tách ra file dùng chung vì form `Storage Location` và ô xem trước ở
// đây phải vẽ ĐÚNG cái sẽ in ra. Xem trước một bố cục khác với cái in ra thì
// tệ hơn là không xem trước gì.

const DUONG_TEM = "/assets/erpnext/js/vi_tri_kho/tem_vi_tri.js";
const TRAN_SO_BAN = 200;

frappe.treeview_settings["Storage Location"] = {
	extend_toolbar: true,
	toolbar: [
		{
			label: __("In tem"),
			condition: function (node) {
				return !node.is_root;
			},
			click: function (node) {
				mo_hop_in_tem(node.label);
			},
			btnClass: "hidden-xs",
		},
	],
};

function mo_hop_in_tem(goc) {
	frappe.call({
		method: "erpnext.vi_tri_kho.vitri.tem.danh_sach_tem",
		args: { goc: goc, so_ban: 1 },
		callback: function (r) {
			const danh_sach = r.message || [];
			if (!danh_sach.length) {
				frappe.msgprint({
					title: __("Không có tem để in"),
					message: __(
						"Nhánh {0} không có ô lá nào. Nút nhóm và ô 'Chưa xếp vị trí' không có kệ thật để dán tem.",
						[goc]
					),
					indicator: "orange",
				});
				return;
			}
			// Nạp bộ vẽ TRƯỚC khi mở hộp thoại: hộp thoại có ô xem trước, mở ra
			// mà bộ vẽ chưa về thì người dùng thấy một khoảng trống và không
			// biết đó là "đang tải" hay "tem rỗng".
			frappe.require(DUONG_TEM, () => hop_thoai(goc, danh_sach));
		},
	});
}

function hop_thoai(goc, danh_sach) {
	const tem = erpnext.vi_tri_kho.tem;
	const vai_mau = danh_sach
		.slice(0, 5)
		.map((d) => d.ma_in_nhan)
		.join(", ");
	const con_lai = danh_sach.length > 5 ? __(" … và {0} ô nữa", [danh_sach.length - 5]) : "";

	const d = new frappe.ui.Dialog({
		title: __("In tem vị trí"),
		fields: [
			{
				fieldtype: "HTML",
				options: `<p>${__("Nhánh")} <b>${frappe.utils.escape_html(goc)}</b> ${__("có")}
					<b>${danh_sach.length}</b> ${__("ô")}.</p>
					<p class="text-muted small">${frappe.utils.escape_html(vai_mau)}${con_lai}</p>`,
			},
			{
				fieldname: "kho_giay",
				fieldtype: "Select",
				label: __("Khổ tem"),
				options: Object.keys(tem.KHO_GIAY).map((ma) => ({ value: ma, label: tem.KHO_GIAY[ma].ten })),
				default: tem.KHO_MAC_DINH,
				reqd: 1,
				onchange: () => ve_xem_truoc(),
			},
			{
				fieldname: "so_ban",
				fieldtype: "Int",
				label: __("Số bản in mỗi ô"),
				default: 1,
				description: __("Tối đa {0}. Mỗi tem một trang.", [TRAN_SO_BAN]),
			},
			{ fieldtype: "Section Break", label: __("Xem trước") },
			{ fieldname: "xem_truoc", fieldtype: "HTML" },
			{
				fieldtype: "HTML",
				options: `<p class="text-muted small">${__(
					"Khi in, đặt tỉ lệ <b>100%</b> — KHÔNG dùng 'Fit to page'. " +
						"Lệch 10% trên tem 45mm là mã vạch chạy ra khỏi mép."
				)}</p>`,
			},
		],
		primary_action_label: __("In"),
		primary_action(v) {
			// Chặn cả ở đây lẫn ở máy chủ: gõ nhầm số bản in là cuộn tem chạy
			// hết trước khi kịp với tay tắt máy.
			const so_ban = Math.min(TRAN_SO_BAN, Math.max(1, Math.floor(Number(v.so_ban) || 1)));
			const ma_kho = v.kho_giay || tem.KHO_MAC_DINH;
			d.hide();
			// Hỏi lại máy chủ với đúng `so_ban` — trần TỔNG số tem do máy chủ
			// giữ, phía JS không được tự quyết (xem tem.py::TRAN_SO_TEM).
			frappe.call({
				method: "erpnext.vi_tri_kho.vitri.tem.danh_sach_tem",
				args: { goc: goc, so_ban: so_ban },
				callback: function (r) {
					if (!r.message) return;
					if (!tem.in_xap(r.message, so_ban, ma_kho)) {
						frappe.msgprint({
							title: __("Trình duyệt chặn cửa sổ in"),
							message: __("Cho phép cửa sổ bật lên (pop-up) cho trang này rồi bấm In lại."),
							indicator: "red",
						});
					}
				},
			});
		},
	});

	// Xem trước bằng ô ĐẦU TIÊN của nhánh, đúng thứ tự lấy hàng — một ô có
	// thật, không phải mã bịa: nhìn thấy đúng mã mình sắp dán là cách rẻ nhất
	// để phát hiện bấm nhầm nhánh TRƯỚC khi cả xấp tem chạy ra máy in.
	function ve_xem_truoc() {
		tem.ve_xem_truoc(d.fields_dict.xem_truoc.$wrapper, danh_sach[0], d.get_value("kho_giay"));
	}

	d.show();
	ve_xem_truoc();
}
