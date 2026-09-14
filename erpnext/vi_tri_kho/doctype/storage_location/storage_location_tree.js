// Nút "In tem" trên từng nốt của cây vị trí: bấm ở nốt nào thì in tem cho
// mọi ô lá thuộc nhánh dưới nốt đó.
//
// Việc CHỌN ô nào nằm ở `erpnext/vi_tri_kho/vitri/tem.py` (có test + đột
// biến). File này chỉ lo VẼ và ĐẨY RA MÁY IN. Ranh giới đó là cố ý: in thừa
// một xấp tem của nhánh khác rồi dán lên kệ là lỗi im lặng đắt nhất của tính
// năng này, nên phần quyết định phải ở nơi khoá được bằng test.
//
// BA ĐIỀU DƯỚI ĐÂY KHÔNG PHẢI TRANG TRÍ — mỗi cái chặn một kiểu hỏng đã biết
// của việc in tem nhiệt:
//
// 1. `@page { size: 50mm 30mm; margin: 0 }` và mỗi tem là MỘT trang. Thiếu
//    thì máy in nhận khổ A4 và nhả mỗi tem một tờ — hết cuộn. Lề mặc định
//    của trình duyệt còn to hơn cả con tem.
// 2. Mã vạch được VẼ THẲNG vào chuỗi HTML (serialize SVG). Nếu để cửa sổ in
//    đi tải ảnh, `print()` có thể chạy trước khi ảnh về: ra tem TRẮNG, mà
//    lúc phát hiện thì tem đã dán lên kệ.
// 3. Luôn in chữ dưới vạch. Tem bẩn, ribbon mòn, máy quét lỗi — người còn
//    đọc bằng mắt mà gõ tay được. Tem chỉ có vạch là vô dụng đúng lúc cần.

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

const TRAN_SO_BAN = 200;

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
			hop_thoai(goc, danh_sach);
		},
	});
}

function hop_thoai(goc, danh_sach) {
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
				fieldname: "so_ban",
				fieldtype: "Int",
				label: __("Số bản in mỗi ô"),
				default: 1,
				description: __("Tối đa {0}. Tem 50×30mm, mỗi tem một trang.", [TRAN_SO_BAN]),
			},
		],
		primary_action_label: __("In"),
		primary_action(v) {
			// Chặn cả ở đây lẫn ở máy chủ: gõ nhầm số bản in là cuộn tem
			// chạy hết trước khi kịp với tay tắt máy.
			const so_ban = Math.min(TRAN_SO_BAN, Math.max(1, Math.floor(Number(v.so_ban) || 1)));
			d.hide();
			// Hỏi lại máy chủ với đúng `so_ban` — trần tổng số tem do máy
			// chủ giữ, phía JS không được tự quyết (xem tem.py::TRAN_SO_TEM).
			frappe.call({
				method: "erpnext.vi_tri_kho.vitri.tem.danh_sach_tem",
				args: { goc: goc, so_ban: so_ban },
				callback: function (r) {
					if (r.message) in_tem(r.message, so_ban);
				},
			});
		},
	});
	d.show();
}

/** Bọc lấy JsBarcode mà Frappe đã đóng gói sẵn, không thêm phụ thuộc mới.
 *
 * `jsbarcode` bị esbuild gói kín trong `controls.bundle.*.js` của frappe,
 * không lộ biến toàn cục; đường duy nhất chạm tới nó là qua lớp
 * `frappe.ui.form.ControlBarcode`. `get_barcode_html()` của lớp đó vẽ thẳng
 * vào `barcode_area` và KHÔNG bị chặn bởi `this.doc` (khác
 * `set_formatted_input`, xem chú thích ở `storage_location.js`).
 */
function may_ve_ma_vach() {
	const khung = $('<div style="display:none"></div>').appendTo(document.body);
	const control = frappe.ui.form.make_control({
		parent: khung,
		render_input: true,
		df: { fieldtype: "Barcode", fieldname: "tem", label: "" },
	});
	return {
		/** Trả chuỗi SVG đã scale sang mm, sẵn sàng nhúng vào trang in. */
		ve(ma, nhan) {
			control.df.options = JSON.stringify({
				format: "CODE128",
				displayValue: true,
				text: nhan, // mắt người đọc dạng có gạch nối…
				fontSize: 14,
				width: 1.6,
				height: 40,
				margin: 0,
			});
			control.get_barcode_html(ma); // …còn MÁY QUÉT trả ra `ma` 10 ký tự
			const svg = control.barcode_area.find("svg")[0];
			if (!svg) return "";
			const ban_sao = svg.cloneNode(true);
			// JsBarcode đặt width/height theo px và KHÔNG kèm viewBox. Đổi
			// thẳng sang mm mà không có viewBox thì nội dung bị cắt chứ không
			// co lại — thêm viewBox từ đúng kích thước px rồi mới đặt mm.
			const w = parseFloat(svg.getAttribute("width")) || 0;
			const h = parseFloat(svg.getAttribute("height")) || 0;
			if (w && h) {
				ban_sao.setAttribute("viewBox", `0 0 ${w} ${h}`);
				ban_sao.setAttribute("preserveAspectRatio", "xMidYMid meet");
			}
			ban_sao.setAttribute("width", "44mm");
			ban_sao.setAttribute("height", "16mm");
			return new XMLSerializer().serializeToString(ban_sao);
		},
		don() {
			khung.remove();
		},
	};
}

function in_tem(danh_sach, so_ban) {
	const esc = frappe.utils.escape_html;
	const may = may_ve_ma_vach();
	const tem = [];

	danh_sach.forEach(function (d) {
		const hinh = may.ve(d.ma_o, d.ma_in_nhan || d.ma_o);
		for (let i = 0; i < so_ban; i++) {
			tem.push(`<div class="tem">
				<div class="kho">${esc(d.kho)}</div>
				<div class="vach">${hinh}</div>
				${d.ten_o ? `<div class="ten">${esc(d.ten_o)}</div>` : ""}
			</div>`);
		}
	});
	may.don();

	const trang = `<!doctype html><html><head><meta charset="utf-8">
<title>${esc(__("Tem vị trí"))}</title>
<style>
	@page { size: 50mm 30mm; margin: 0; }
	* { box-sizing: border-box; }
	body { margin: 0; font-family: Arial, Helvetica, sans-serif; }
	.tem {
		width: 50mm; height: 30mm;
		padding: 1mm 2mm;
		display: flex; flex-direction: column;
		align-items: center; justify-content: center;
		overflow: hidden;              /* tem tràn là in lệch thật, không chỉ xấu */
		page-break-after: always;      /* mỗi tem = một trang = một con tem trên cuộn */
		break-after: page;             /* hai thuộc tính vì các engine in phủ khác nhau */
	}
	.tem:last-child { page-break-after: auto; break-after: auto; }  /* khỏi thừa tem trắng cuối */
	.kho {
		font-size: 6pt; color: #000;
		max-width: 46mm;
		white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
	}
	.vach { line-height: 0; }
	.ten {
		font-size: 6pt; max-width: 46mm;
		white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
	}
</style></head><body>
${tem.join("\n")}
<script>
	window.onload = function () {
		window.print();
		// Đóng ngay có thể huỷ lệnh in ở một số engine — chờ một nhịp.
		setTimeout(function () { window.close(); }, 400);
	};
<\/script>
</body></html>`;

	const cua_so = window.open("", "_blank", "width=420,height=560");
	if (!cua_so) {
		frappe.msgprint({
			title: __("Trình duyệt chặn cửa sổ in"),
			message: __("Cho phép cửa sổ bật lên (pop-up) cho trang này rồi bấm In lại."),
			indicator: "red",
		});
		return;
	}
	cua_so.document.write(trang);
	cua_so.document.close();
}
