// Dialog chọn một nút vị trí bằng cây, dùng chung.
//
// Nạp bằng `frappe.require("/assets/erpnext/js/vi_tri_kho/cay_chon_vi_tri.js")`
// — cùng lối với `tem_vi_tri.js`, không thêm dòng nào vào `hooks.py`: dòng đó
// bị chính module này gọi là "dòng dễ mất nhất" ở mỗi lần merge ERPNext bản
// mới (xem đầu `tem_vi_tri.js`), nên không thêm dòng thứ hai cho một thứ chỉ
// một màn hình cần.
//
// ĐƯỜNG DỮ LIỆU CỦA `frappe.ui.Tree` — brief bàn giao Task 7 dùng `node.data`
// trong `get_label`/`onclick` mà CHƯA AI KIỂM đường đó có thật không. Đã đọc
// trực tiếp `apps/frappe/frappe/public/js/frappe/ui/tree.js` (bản trên máy
// này) trước khi viết file này, kết luận:
//
//   - ĐÚNG một nửa: `add_node(node, data)` (tree.js dòng 129-140) dựng
//     `TreeNode` với `data: data` — NGUYÊN dòng máy chủ trả về (kể cả
//     `da_gan_cho`, `so_o_trong`, `so_mat_hang_dang_co`) nằm trên `node.data`.
//     `get_label(node)` (gọi từ `get_node_label()`, dòng 254-263) và callback
//     bấm nút ĐỀU thấy được các trường phụ qua `node.data`.
//   - SAI: brief dùng `node.value` để lấy mã vị trí. Không có thuộc tính
//     `value` rời nào trên `node` — `add_node()` chỉ gán `label: data.value`
//     (dòng 135), nên `node.value` luôn `undefined`. Phải đọc `node.label`
//     hoặc `node.data.value`. Tiền lệ `chart_of_accounts_importer.js:189`
//     cũng viết `node.value` — SAI giống hệt, nhưng lỗi đó không lộ ra vì lỗi
//     thứ hai dưới đây khiến callback của file đó chưa từng chạy lần nào.
//   - SAI NẶNG HƠN: constructor của `frappe.ui.Tree` (tree.js dòng 6-21) nhận
//     tham số tên `on_click` (CÓ gạch dưới), và `expand_node()` (dòng
//     201-215) gọi đúng `this.on_click(node)`. Brief (và
//     `chart_of_accounts_importer.js:189`, tiền lệ mà bàn giao Task 7 trỏ
//     tới) truyền khoá `onclick` — KHÔNG gạch dưới. `$.extend(this,
//     arguments[0])` ở đầu constructor chỉ gắn thêm một thuộc tính thừa
//     `this.onclick` lên instance; `this.on_click` vẫn `undefined` nên
//     `this.on_click && this.on_click(node)` không bao giờ gọi hàm. Nghĩa là
//     callback bấm nút của CẢ brief lẫn tiền lệ nó trỏ tới đều là mã chết —
//     sao chép "tiền lệ" mà không tự đọc `tree.js` là sao chép nguyên một
//     callback không bao giờ chạy. Sửa: dùng khoá `on_click`.
//   - MỘT ĐIỀU NỮA brief không tính tới: `expand_node()` gọi `on_click` cho
//     MỌI cú bấm — kể cả bấm để MỞ một nút nhóm (Khu/Dãy/Khoang/Tầng), không
//     chỉ bấm chọn lá. Nếu chọn-và-đóng-hộp-thoại chạy trên MỌI cú bấm (đúng
//     như code mẫu của brief một khi đã sửa `onclick` → `on_click`), hộp
//     thoại sẽ đóng ngay ở LẦN BẤM ĐẦU TIÊN vào một Khu gốc — cây không bao
//     giờ mở được tới cấp thứ hai, hỏng đúng điều Step 7 của brief đòi kiểm
//     bằng mắt ("cây mở được từng cấp"). Vì vậy `on_click` dưới đây CHỈ coi
//     một cú bấm là "chọn" khi nút đó là LÁ thật (`node.expandable` falsy,
//     tức một Ô 10 ký tự); bấm vào nút nhóm chỉ mở/đóng nhánh như tree mặc
//     định vẫn làm, không chọn gì cả. Gán ở cấp Tầng trở lên vẫn làm được —
//     `Item Location Preference.vi_tri` cho phép "nút bất kỳ cấp nào" — chỉ
//     là qua gõ tay vào ô Link như trước (xem chú thích ở
//     `item_location_preference.js`), không qua cây. Đây là điểm LỆCH brief
//     duy nhất có chủ đích, không phải chỗ dịch sai brief.
//
// ĐIỀU DUY NHẤT KHÔNG ĐƯỢC BỎ: nút đã có chủ phải hiện MỜ kèm tên mặt hàng
// đang giữ ở MỌI cấp (group lẫn lá) — nhìn thấy TRƯỚC KHI bấm. Với lá đã có
// chủ, bấm còn phải bị chặn kèm thông báo, không được lặng lẽ chọn rồi để
// `validate()` phía máy chủ mới ném lỗi: với 214 ô đó là trò chơi đoán.

frappe.provide("erpnext.vi_tri_kho");

erpnext.vi_tri_kho.chon_vi_tri = function (kho, khi_chon) {
	const d = new frappe.ui.Dialog({
		title: __("Chọn vị trí cố định"),
		size: "large",
		fields: [{ fieldname: "cay", fieldtype: "HTML" }],
	});
	d.show();

	new frappe.ui.Tree({
		parent: d.fields_dict.cay.$wrapper,
		label: kho,
		expandable: true,
		method: "erpnext.vi_tri_kho.vitri.gan.cay_chon_vi_tri",
		args: { kho: kho },

		// `node.data` là nguyên dòng máy chủ trả về cho nút này (xem chú
		// thích đầu file) — `n.title`/`n.label` KHÔNG cần escape lại vì
		// `node.title`/`node.label` đã đi qua `frappe.utils.escape_html` ở
		// đây; `n.da_gan_cho` là mã mặt hàng NGƯỜI DÙNG gõ tay lúc tạo Item
		// nên PHẢI escape trước khi nhét vào HTML.
		get_label: function (node) {
			const n = node.data || {};
			const nhan = frappe.utils.escape_html(node.title || node.label);

			if (n.da_gan_cho) {
				const ten = frappe.utils.escape_html(n.da_gan_cho);
				return `<span class="text-muted">${nhan} — ${__("đã gán")}: ${ten}</span>`;
			}

			// Chỉ hai gợi ý phụ, không phải cảnh báo: số trống để biết nhánh
			// còn chỗ, số "mặt hàng đang nằm" (tồn của các mặt hàng KHÁC
			// đang tạm ở nhánh này, chưa có gán cố định) để biết nhánh không
			// hề trống dù chưa ai "đứng tên" nó trên cây. Cả hai đều là số
			// nguyên từ COUNT() phía máy chủ, không phải dữ liệu người dùng
			// gõ tay — không cần escape.
			const trong = n.so_o_trong ? ` · ${n.so_o_trong} ${__("ô trống")}` : "";
			const khac = n.so_mat_hang_dang_co
				? ` · <span class="text-warning">${n.so_mat_hang_dang_co} ${__("mặt hàng đang nằm")}</span>`
				: "";
			return `${nhan}<span class="small">${trong}${khac}</span>`;
		},

		// Khoá `on_click` (KHÔNG phải `onclick`) — xem chú thích đầu file vì
		// sao đây là điểm brief sai, không phải lỗi đánh máy được phép sửa
		// tuỳ tiện.
		on_click: function (node) {
			// Nút nhóm (Khu/Dãy/Khoang/Tầng): chỉ mở/đóng nhánh, không chọn.
			// `expand_node()` của tree.js gọi `on_click` cho MỌI cú bấm kể cả
			// bấm để mở nhánh — coi mọi cú bấm là "chọn rồi đóng hộp thoại"
			// sẽ khiến cây không bao giờ mở được quá cấp một.
			if (node.expandable) return;

			const n = node.data || {};
			// `node.data.value` là mã vị trí thật do máy chủ trả về;
			// `node.label` luôn bằng đúng giá trị đó (xem chú thích đầu
			// file) nên dùng làm phương án dự phòng, không phải vì hai
			// đường có thể khác nhau.
			const gia_tri = n.value || node.label;

			if (n.da_gan_cho) {
				frappe.show_alert({
					message: __("{0} đã thuộc mặt hàng {1}.", [
						frappe.utils.escape_html(gia_tri),
						frappe.utils.escape_html(n.da_gan_cho),
					]),
					indicator: "orange",
				});
				return;
			}

			khi_chon(gia_tri);
			d.hide();
		},
	});
};
