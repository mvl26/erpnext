// Màn menu — bốn nút việc chính, cửa vào cho tất cả các màn nghiệp vụ.
//
// Task 2–5 mới ĐĂNG KÝ "tra-cuu" / "xep-hang" / "lay-hang" / "dat-o" vào
// `KhoApp.man`; ở Task 1 bốn màn đó chưa tồn tại nên `_theo_hash` (vo.js) tự rơi
// về "menu" khi bấm — vỏ tự lo, không cần xử lý gì thêm ở tệp này.

frappe.provide("erpnext.kho_pda");

// Nút cao ≥ 72px (spec §PDA — ngón tay đeo găng, không phải chuột): kích thước
// đặt trong `kho_pda.bundle.scss`, ở đây chỉ liệt kê bốn việc và đường đi của
// chúng để không rải rác tên màn ở nhiều nơi.
//
// Biểu tượng là SVG viết thẳng ở đây, không qua `frappe.utils.icon`: trong app
// không có tập sprite icon của Desk (xem `shim.js`), và không được tải gì từ mạng.
// `currentColor` để màu đi theo CSS (`.kho-menu-hinh`).
const _SVG = (d) =>
	`<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;

const _VIEC = [
	{
		ten: "tra-cuu",
		nhan: __("Tra cứu"),
		mo: __("Quét lô, ô, mặt hàng"),
		hinh: _SVG('<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>'),
	},
	{
		ten: "xep-hang",
		nhan: __("Xếp hàng"),
		mo: __("Đưa lô lên kệ"),
		hinh: _SVG('<path d="M3 21h18"/><path d="M5 21V8l7-5 7 5v13"/><path d="M12 17V9"/><path d="m9 12 3-3 3 3"/>'),
	},
	{
		ten: "lay-hang",
		nhan: __("Lấy hàng"),
		mo: __("Theo phiếu giao"),
		hinh: _SVG('<path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><path d="M3 6h18"/><path d="M16 10a4 4 0 0 1-8 0"/>'),
	},
	{
		ten: "dat-o",
		nhan: __("Đặt ô"),
		mo: __("Gán ô cho tem lô"),
		hinh: _SVG('<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 17.5h7M17.5 14v7"/>'),
	},
];

erpnext.kho_pda.KhoApp.dang_ky_man("menu", {
	tieu_de: __("Kho — PDA"),

	ve($than) {
		const $luoi = $('<div class="kho-menu-luoi"></div>');
		for (const viec of _VIEC) {
			$(`<button type="button" class="kho-menu-nut">
				<span class="kho-menu-hinh">${viec.hinh}</span>
				<span class="kho-menu-ten">${frappe.utils.escape_html(viec.nhan)}</span>
				<span class="kho-menu-mo">${frappe.utils.escape_html(viec.mo)}</span>
			</button>`)
				.on("click", () => erpnext.kho_pda.KhoApp.di(viec.ten))
				.appendTo($luoi);
		}

		$than.html(`
			<div class="kho-menu">
				<div class="kho-menu-chan">
					<div class="kho-menu-ai-khung">
						<div class="kho-menu-ai"></div>
						<div class="kho-menu-may-chu"></div>
					</div>
					<button type="button" class="kho-menu-dang-xuat">${__("Đăng xuất")}</button>
				</div>
			</div>
		`);
		$than.find(".kho-menu").prepend($luoi);
		$than.find(".kho-menu-ai").text(erpnext.kho_pda.KhoApp.nguoi_dung || "");
		// `dia_chi_may_chu()` đọc CÙNG hằng số mà `goi()` dựng địa chỉ từ đó — xem
		// `vo.js`. `location.origin` ở đây (bản trước Task 2) hiện `file://` trong
		// bản đóng gói, tức chốt chặn bằng mắt chống "cài nhầm bản trỏ máy chủ thử"
		// nói dối.
		$than.find(".kho-menu-may-chu").text(erpnext.kho_pda.KhoApp.dia_chi_may_chu());
		erpnext.kho_pda.KhoApp.ve_dai_ban_thu($than.find(".kho-menu"));
		// TASK 5 — dải cảnh báo lệch giờ máy (spec §8), cùng khuôn với "BẢN THỬ" ở
		// trên: đây là màn thủ kho quay lại nhiều nhất trong ca, nên nếu chưa thấy ở
		// màn thẻ (đã cấp khoá từ trước, chạm icon vào thẳng menu — không qua màn
		// thẻ nữa) thì đây là chỗ hiện được sớm nhất. Trên web tự không hiện gì.
		erpnext.kho_pda.KhoApp.ve_dai_lech_gio($than.find(".kho-menu"));
		// VÒNG SỬA 1 — cùng lý do ở `man_the.js`: "im lặng phải nhìn thấy được".
		erpnext.kho_pda.KhoApp.ve_dai_thieu_gio($than.find(".kho-menu"));

		// TASK 6 — NHẮC CÓ BẢN CÀI MỚI (spec §10). Hỏi máy chủ xem bản cài mới nhất
		// là bản nào, so với phiên bản của chính bản cài này, rồi hiện dải nhắc kèm
		// nút mở trang tải. KHÔNG tự tải, KHÔNG tự cài — xem `ve_dai_ban_moi`.
		//
		// ĐẶT Ở MÀN MENU, không ở màn thẻ: máy đã nhận thì màn thẻ không hiện ra
		// nữa (Task 4), nên nhắc ở đó là nhắc cho một màn không ai thấy.
		//
		// VẼ BẤT ĐỒNG BỘ, KHÔNG CHỜ: lời gọi này không được chặn bốn nút việc. Khi
		// nó về, màn menu có thể đã bị rời — `$than.find(".kho-menu")` khi đó là một
		// tập RỖNG và `prepend` không làm gì, nên không cần cờ "còn ở màn này không".
		// `hoi_ban_cai_moi()` không bao giờ từ chối lời hứa (xem `vo.js`), nên không
		// có `unhandledrejection` nào lọt ra.
		erpnext.kho_pda.KhoApp.hoi_ban_cai_moi().then((ban) => {
			erpnext.kho_pda.KhoApp.ve_dai_ban_moi($than.find(".kho-menu"), ban);
		});

		$than.find(".kho-menu-dang-xuat").on("click", () => {
			// TRONG APP, "ĐĂNG XUẤT" PHẢI GIẾT KHOÁ MÁY — nếu không nó thành một nút
			// KHÔNG LÀM GÌ (Task 4): `logout` chỉ đóng phiên COOKIE, mà app không đăng
			// nhập bằng cookie; khoá máy trong `localStorage` vẫn sống, nên
			// `location.reload()` ngay dưới lại nạp đúng chiếc khoá đó và vào thẳng
			// menu. Người bấm nút tưởng mình đã trả máy trong khi chưa trả gì cả.
			//
			// XOÁ TRƯỚC KHI GỌI, không xoá trong `.then()`: việc trả máy không được
			// phụ thuộc vào một lời gọi mạng có tới nơi hay không. Wifi kho chập chờn
			// thì trang không tải lại, nhưng khoá đã chết trong máy và thao tác kế
			// tiếp rơi về màn thẻ — hỏng theo hướng an toàn.
			//
			// `_la_app()` bọc đúng một dòng: trên web `xoa_khoa()` sẽ đụng vào kho lưu
			// của trình duyệt cho một chiếc khoá chưa từng tồn tại ở đó, và ràng buộc
			// của cả đợt là bản web không đổi hành vi.
			if (erpnext.kho_pda.KhoApp._la_app()) erpnext.kho_pda.KhoApp.xoa_khoa();
			// `handler.py::logout` cho phép Guest gọi (`allow_guest=True`) nên
			// `goi()` không rơi vào nhánh 401/403 ở đây — gọi xong là chắc chắn
			// phiên đã đóng, không cần bọc thêm `catch`.
			erpnext.kho_pda.KhoApp.goi("logout").then(() => location.reload());
		});
	},
});
