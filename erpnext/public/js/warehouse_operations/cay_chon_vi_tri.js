// Dialog chọn một nút vị trí bằng cây, dùng chung.
//
// Nạp bằng `frappe.require("/assets/erpnext/js/warehouse_operations/cay_chon_vi_tri.js")`
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
//     `get_label(node)` (gọi từ `get_node_label()`, dòng 254-263) và mọi
//     callback nhận `node` ĐỀU thấy được các trường phụ qua `node.data`.
//   - SAI: brief dùng `node.value` để lấy mã vị trí. Không có thuộc tính
//     `value` rời nào trên `node` — `add_node()` (dòng 135) chỉ gán
//     `label: data.value`, không gán `value` rời. Nên `node.value` LUÔN
//     `undefined`; phải đọc `node.label` hoặc `node.data.value`.
//   - SAI NẶNG HƠN, khiến cả một callback thành mã chết: constructor của
//     `frappe.ui.Tree` (tree.js dòng 6-21) khai tham số `on_click` (CÓ gạch
//     dưới), và `expand_node()` (dòng 201-215) gọi đúng
//     `this.on_click && this.on_click(node)`. Brief truyền khoá `onclick`
//     (KHÔNG gạch dưới). `$.extend(this, arguments[0])` ở dòng 22 chỉ gắn
//     thêm một thuộc tính thừa `this.onclick` lên instance; `this.on_click`
//     vẫn `undefined` nên callback không bao giờ chạy. GHI CHÚ CHO NGƯỜI SAU:
//     `erpnext/accounts/doctype/chart_of_accounts_importer/chart_of_accounts_importer.js:189`
//     (mã upstream, không phải của module này) mắc ĐÚNG hai lỗi trên cùng
//     lúc — viết `onclick` (không phải `on_click`) VÀ đọc `node.value` (không
//     tồn tại) — nên hàm `onclick` của file đó CHƯA TỪNG chạy một lần nào kể
//     từ khi được viết. Đừng dùng file đó làm tiền lệ để copy mà không tự đọc
//     `tree.js` trước — đó chính xác là cách bug này lọt vào bản brief đưa
//     cho Task 7.
//
// VÌ SAO CHỌN QUA NÚT "CHỌN VỊ TRÍ NÀY" TRONG `toolbar`, KHÔNG QUA `on_click`
// CỦA CHÍNH NÚT CÂY (Ruling P, vòng sửa 1 điều phối):
//
// `expand_node()` (tree.js dòng 201-215) gọi `on_click` cho MỌI cú bấm vào
// một nút — kể cả bấm chỉ để MỞ một nhánh (Khu/Dãy/Khoang/Tầng), không phân
// biệt "bấm để duyệt" với "bấm để chọn". Nếu `on_click` vừa chọn vừa
// `d.hide()`, hộp thoại đóng ngay ở LẦN BẤM ĐẦU TIÊN vào Khu gốc — cây không
// bao giờ mở được tới cấp thứ hai. Thu hẹp việc chọn về riêng nút lá (Ô) né
// được lỗi đó nhưng lại phá đúng yêu cầu thật của chủ đầu tư (15/09,
// spec §3.1/§3.4): gán ở cấp TẦNG/KHOANG là CA DÙNG CHÍNH — spec còn nói gán
// vào một Ô lẻ là ca NÊN TRÁNH (luật "ô trống đầu tiên" khiến lần nhập hàng
// thứ hai vào đúng Ô đó luôn báo đầy). Một cây chỉ chọn được lá là làm đúng
// phần dễ và bỏ mất phần thật sự cần dùng.
//
// Lối ra: `frappe.ui.Tree` có sẵn cơ chế `toolbar` tách biệt hẳn với
// `on_click` — mỗi nút cây tự mang một dải nút bấm riêng (`get_toolbar()`,
// tree.js dòng 294-312), ẩn/hiện theo đúng nút đang được chọn
// (`show_toolbar()`, dòng 248-252, gọi từ `on_node_click()` mỗi lần bấm một
// nút bất kỳ). Mỗi mục toolbar nhận `condition(node)` — không thoả thì nút
// KHÔNG được dựng ra, không phải dựng ra rồi vô hiệu hoá. Nhờ vậy:
//
//   - Bấm vào chính một nút cây = hành vi CÂY MẶC ĐỊNH (mở/đóng nhánh). Không
//     gắn `on_click` nào ở đây cả — không cần, vì `toggle_node()` bên trong
//     `expand_node()` tự lo việc mở/đóng, không phụ thuộc `on_click`.
//   - Nút "Chọn vị trí này" trong toolbar của MỘT nút = chọn CHÍNH nút đó rồi
//     đóng hộp thoại. Chạy được cho CẢ nút nhóm lẫn Ô lá — đúng điều cần,
//     không còn giới hạn chỉ-chọn-lá của vòng trước.
//   - `condition(node)` không dựng nút này trên nốt ĐÃ CÓ CHỦ — "không khả
//     dụng" thể hiện bằng việc KHÔNG CÓ NÚT ĐỂ BẤM, còn tốt hơn bấm rồi mới
//     hiện cảnh báo (dù cảnh báo cũng đã có sẵn ở `get_label`, xem dưới).
//
// ĐIỀU DUY NHẤT KHÔNG ĐƯỢC BỎ: nút đã có chủ phải hiện MỜ kèm tên mặt hàng
// đang giữ ở MỌI cấp (group lẫn lá) — nhìn thấy TRƯỚC KHI bấm, và không có
// đường nào để chọn nó (nút "Chọn vị trí này" không được dựng ra). Không
// được để người dùng chọn được rồi mới ăn lỗi từ `validate()` phía máy chủ:
// với 214 ô đó là trò chơi đoán.
//
// GHI CHÚ (vòng sửa 3, điều phối bấm thật thấy cây "chết"): đã đo bằng CDP
// thật trên site chạy (không phải suy luận) và XÁC NHẬN `frappe.ui.Tree`
// hoạt động đúng bên trong `frappe.ui.Dialog` — không có xung đột CSS/cấu
// trúc nào giữa hai thứ này (SCSS của `.tree-children`, xem
// `apps/frappe/frappe/public/scss/desk/tree.scss`, KHÔNG hề đặt
// `display: none` bằng CSS; toàn bộ việc ẩn/hiện là do jQuery
// `.hide()/.toggle()` gọi TRỰC TIẾP trong `tree.js`, không phụ thuộc ngữ
// cảnh Dialog hay bất kỳ class `.opened` nào — khối CSS `&.opened::before`
// ở `tree.scss` thậm chí đang bị COMMENT hết). Triệu chứng "chỉ hiện nốt
// gốc, bấm không ra gì" đo được ở vòng sửa 3 là do CHÍNH kịch bản đo bấm
// vào nốt GỐC — nốt này tự mở sẵn ngay khi hộp thoại vừa hiện ra (ba Khu đã
// hiện sẵn, không cần bấm gì) — rồi bấm nó THÊM MỘT LẦN NỮA: `tree.js`
// coi đó là bấm để ĐÓNG một nhánh đang mở (hành vi toggle bình thường của
// MỌI cây trong `frappe.ui.Tree`, không riêng gì cây này), nên toàn bộ ba
// Khu vừa hiện biến mất, và các nốt bấm sau đó (nằm trong nhánh vừa đóng)
// tải được dữ liệu (có trong DOM) nhưng không ai nhìn thấy vì tổ tiên của
// chúng vừa bị đóng. Không phải lỗi CSS, không phải Dialog không tương
// thích — là bấm trúng đúng cái nốt vừa mở sẵn một lần nữa. Đã kiểm lại
// KHÔNG bấm lại nốt gốc: nhãn đang hiện tăng dần 4 → 8 → 12 → 16 → 18 khi
// mở Khu → Dãy → Khoang → Tầng → Ô, `$toolbar.is(':visible')` đúng `true`
// ở nốt vừa bấm, và bấm "Chọn vị trí này" ở cấp TẦNG (không chỉ lá) điền
// đúng `vi_tri` rồi đóng hộp thoại. Không đổi gì ở cách gắn cây/Dialog vì
// không tìm thấy lỗi nào để sửa — xem `task-7-report.md`, mục "Vòng sửa 3"
// để có đầy đủ số đo và đường dẫn ảnh chụp.

frappe.provide("erpnext.warehouse_operations");

// `tru_ten` (tuỳ chọn): tên bản ghi `Item Location Preference` ĐANG SỬA — khớp
// đúng tham số `tru_ten` mới của `gan.py::cay_chon_vi_tri()`. Thiếu nó thì mở
// cây để SỬA một gán đã lưu (nút "Chọn trên cây vị trí" ở
// `item_location_preference.js` hiện ra cả khi đang sửa, không chỉ lúc tạo
// mới) và định dời lên một nút TỔ TIÊN của chính gán đang sửa sẽ bị `cột
// co_gan_ben_trong` đếm nhầm CHÍNH gán đó rồi khoá nút "Chọn vị trí này" —
// trong khi `kiem_tra_chong_lan()` phía máy chủ đã loại trừ đúng bản ghi này
// (`tru_ten=self.name`) nên thao tác đó vốn HỢP LỆ. Xem docstring
// `cay_chon_vi_tri()` để biết vì sao không tự suy `tru_ten` được ở đây — nơi
// gọi (form) mới biết mình đang sửa bản ghi nào.
// `dang_co` (22/09/2026 — gán nhiều vị trí): danh sách nút ĐANG nằm trong hộp thoại
// gán, kể cả dòng vừa thêm mà chưa lưu. Nút giao một nút trong đó hiện "đã có trong
// danh sách" và không chọn được — máy chủ (`kiem_tra_tu_long_nhau`) sẽ từ chối nó.
erpnext.warehouse_operations.chon_vi_tri = function (kho, khi_chon, tru_ten, dang_co) {
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
		method: "erpnext.warehouse_operations.vitri.gan.cay_chon_vi_tri",
		args: { kho: kho, tru_ten: tru_ten, dang_co: JSON.stringify(dang_co || []) },

		// CỐ Ý không truyền `root_value` riêng (ví dụ chuỗi rỗng) để né việc
		// gốc gửi `parent = kho` — vòng sửa 2 điều phối (bấm thật trên trình
		// duyệt bắt được cây chết ở gốc: xem `gan.py::cay_chon_vi_tri()` và
		// bài test mô phỏng đúng cách widget gọi). Không đổi ở đây vì
		// `root_value` mặc định BẰNG `label` (tree.js dòng 22-24), và
		// `label` ở trên chính là TÊN KHO hiện trên đầu cây — nếu ép
		// `root_value: ""` để né vấn đề, nhãn gốc của cây sẽ mất tên kho
		// (đổi hẳn UI). Sửa đúng chỗ là ở máy chủ: `cay_chon_vi_tri()` giờ
		// nhận thêm `is_root` và coi `parent == kho` cũng LÀ cấp gốc, nên
		// JS không cần đổi gì ở đây.

		// `node.data` là nguyên dòng máy chủ trả về cho nút này (xem chú
		// thích đầu file) — tên trường KHỚP đúng các cột `as` của
		// `gan.py::cay_chon_vi_tri()`: `value`, `title`, `expandable`,
		// `da_gan_cho`, `co_gan_ben_trong`, `nhanh_ngung_dung`, `so_o_trong`,
		// `so_mat_hang_dang_co`.
		// LƯU Ý TÊN THẬT: phần "Interfaces" của brief Task 7 ghi khoá
		// `co_hang_khac`, nhưng cả câu SQL mẫu lẫn bài test
		// (`test_gan_vi_tri.py`) chỉ dùng `so_mat_hang_dang_co` — hai chỗ của
		// brief tự mâu thuẫn nhau, và `so_mat_hang_dang_co` mới là tên cột
		// THẬT sự tồn tại trên CSDL.
		get_label: function (node) {
			const n = node.data || {};
			// `node.title`/`node.label` là `ma_in_nhan`/`name` của
			// `Storage Location` — dữ liệu nhập tay (đặc biệt `ma_in_nhan`,
			// một trường mô tả tự do), nên escape trước khi ghép HTML.
			const nhan = frappe.utils.escape_html(node.title || node.label);

			if (n.cua_chinh_minh) {
				return `<span class="text-muted">${nhan} — ${__("đã có trong danh sách")}</span>`;
			}
			if (n.da_gan_cho) {
				// `da_gan_cho` là mã mặt hàng (Item Code) — cũng là dữ liệu
				// người dùng gõ tay lúc tạo Item, PHẢI escape.
				const ten = frappe.utils.escape_html(n.da_gan_cho);
				return `<span class="text-muted">${nhan} — ${__("đã gán")}: ${ten}</span>`;
			}

			// VÒNG SỬA CUỐI (Mục 1, review tổng): `co_gan_ben_trong` báo nhánh
			// CHỨA một gán (ở một nút con, không phải chính nút này) — nút này
			// CHƯA thuộc về ai (không được nói "đã gán: X", câu đó sai), nhưng
			// cũng không chọn được vì bấm sẽ ăn lỗi "bao trùm ... đã được gán
			// cho" từ `kiem_tra_chong_lan()`. Phải hiện TRƯỚC KHI bấm, không
			// phải trần trụi trả về nhãn bình thường rồi để `condition()` của
			// toolbar âm thầm ẩn nút — người dùng cần biết VÌ SAO.
			if (n.co_gan_ben_trong) {
				return (
					`<span class="text-muted">${nhan} — ` +
					`${__("có")} ${n.co_gan_ben_trong} ${__("gán bên trong")}</span>`
				);
			}

			// VÒNG VÁ TIẾP THEO (mối lo #1, report review tổng trước):
			// `kiem_tra_nut_hop_le()` phía máy chủ từ chối gán vào một nút
			// `disabled` HOẶC có tổ tiên `disabled` — lý do thứ BA trong ba lý
			// do `validate()` có thể từ chối; cây từng chỉ báo trước hai lý do
			// kia. Phải hiện TRƯỚC KHI bấm, và phải là NHÃN RIÊNG, không gộp
			// vào "đã gán"/"có gán bên trong": với người vận hành đây là việc
			// KHÁC hẳn (bật lại nhánh hoặc chờ sửa kệ xong, không phải đi tìm
			// chỗ khác hay gỡ gán con trước).
			if (n.nhanh_ngung_dung) {
				return (
					`<span class="text-muted">${nhan} — ${__("đang ngừng dùng")}` +
					` (${__("do chính nó hoặc do một nút cha")})</span>`
				);
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

		// Cố ý KHÔNG có `on_click`. Chọn nút vị trí là việc của toolbar dưới
		// đây, không phải của cú bấm vào chính nốt cây — xem khối chú thích
		// dài ở đầu file vì sao gắn chọn vào `on_click` sẽ phá luôn khả năng
		// duyệt cây (đóng hộp thoại ở lần bấm đầu tiên).
		toolbar: {
			chon: {
				label: __("Chọn vị trí này"),
				// Nốt gốc (chính là `kho`, một Warehouse) không phải
				// Storage Location — không cho chọn. Nốt đã có chủ
				// (`da_gan_cho`) cũng không dựng nút này: "không khả dụng"
				// hiện ra bằng việc KHÔNG CÓ nút để bấm, người dùng không
				// cần bấm thử rồi mới biết.
				//
				// VÒNG SỬA CUỐI (Mục 1, review tổng): `!n.da_gan_cho` một
				// mình không đủ — nó chỉ loại nút BỊ một TỔ TIÊN gán chiếm.
				// Chiều NGƯỢC LẠI (một nút CON của nút này đã được gán) rơi
				// vào khe hở: `da_gan_cho` ra NULL (nút này chưa có tổ tiên
				// nào gán nó), nút "Chọn vị trí này" vẫn dựng ra, bấm vào rồi
				// mới ăn lỗi "bao trùm ... đã được gán cho" từ máy chủ — với
				// 214 ô đó là trò chơi đoán mà spec §6 cấm bằng chữ in đậm.
				// `co_gan_ben_trong` khoá đúng chiều này.
				//
				// VÒNG VÁ TIẾP THEO (mối lo #1, report review tổng trước):
				// `!n.da_gan_cho && !n.co_gan_ben_trong` một mình không đủ —
				// một nút `disabled` (hoặc có tổ tiên `disabled`) có thể CHƯA
				// ai gán (cả hai cờ trên đều falsy), nút "Chọn vị trí này" vẫn
				// dựng ra, bấm vào rồi mới ăn lỗi "đang ngừng dùng" từ
				// `kiem_tra_nut_hop_le()` phía máy chủ — với 214 ô đó vẫn là
				// trò chơi đoán, chỉ khác lý do. `n.nhanh_ngung_dung` loại
				// đúng lý do thứ ba này.
				condition: function (node) {
					const n = node.data || {};
					return (
						!node.is_root &&
						!n.da_gan_cho &&
						!n.co_gan_ben_trong &&
						!n.nhanh_ngung_dung &&
						!n.cua_chinh_minh
					);
				},
				click: function (node) {
					const n = node.data || {};
					// `node.data.value` là mã vị trí thật do máy chủ trả
					// về; `node.label` luôn bằng đúng giá trị đó (xem khối
					// chú thích đầu file) nên chỉ dùng làm phương án dự
					// phòng.
					khi_chon(n.value || node.label);
					d.hide();
				},
			},
		},
	});
};
