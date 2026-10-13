// Màn quét thẻ — cửa duy nhất vào app khi chưa đăng nhập, và nơi `goi()` (vo.js)
// đẩy người dùng về khi phiên hết hạn (web) hoặc khi khoá máy bị thu hồi (app).
//
// MỘT MÀN, HAI Ý NGHĨA — cùng một file, rẽ nhánh bằng `KHO_LA_APP` (Task 4):
//
//   WEB `/kho`  — QUÉT THẺ MỖI CA. Tấm thẻ mở một PHIÊN (cookie), phiên sống 12
//                 tiếng rồi hết. Đường này KHÔNG ĐỔI MỘT BYTE ở Task 4.
//   APP         — QUÉT THẺ MỘT LẦN LÚC NHẬN MÁY. Tấm thẻ đổi lấy một KHOÁ MÁY cất
//                 trong máy; từ lần mở sau, chạm icon là vào thẳng menu (xem
//                 `khoi_dong` trong `vo.js`). Màn này khi đó không hiện ra nữa cho
//                 tới khi trưởng kho thu hồi.
//
// VÌ SAO KHÔNG TÁCH RA HAI FILE: cùng một `kho_pda.bundle.js` phục vụ cả hai nơi —
// đó là điều kiện để web và app không trôi khỏi nhau (spec §12). Hai bản mã là hai
// câu chữ, hai cách chuẩn hoá mã thẻ, và một ngày nào đó hai hành vi khác nhau mà
// không ai biết.

frappe.provide("erpnext.kho_pda");

/** ĐƯỜNG WEB — quét thẻ mở một phiên cho CA làm việc này. KHÔNG ĐỔI ở Task 4. */
function _dang_nhap_ca(App, ma) {
	return (
		App.goi("erpnext.warehouse_operations.vitri.the_pda.dang_nhap_bang_the", { ma: ma })
			.then(() =>
				// `dang_nhap_bang_the` không trả tên người dùng, chỉ trả `di_toi` (vỏ
				// này bỏ qua — xem index.py/vo.js). Và `KhoApp.nguoi_dung` đọc từ
				// `data-nguoi_dung` lúc TẢI TRANG nên vẫn mang giá trị rỗng của lúc
				// còn là khách — không tải lại trang (đúng tinh thần định tuyến bằng
				// hash), nên phải tự hỏi lại máy chủ SAU KHI đăng nhập mới có tên
				// đúng cho màn menu. Lỗi ở bước này (hiếm, phiên vừa tạo) không được
				// chặn đường vào menu — người dùng đã đăng nhập thật, chỉ thiếu mỗi
				// dòng tên hiển thị.
				App.goi("frappe.auth.get_logged_user").catch(() => "")
			)
			.then((nguoi_dung) => {
				// `la_khach` PHẢI đổi ở đây, không chỉ `nguoi_dung`: chốt chặn khách
				// trong `_theo_hash` (vo.js) đọc đúng cờ này để quyết có ép về "the"
				// hay không — không cập nhật thì vừa đăng nhập xong, `di("menu")` bên
				// dưới lập tức bị chính chốt chặn đó đá ngược lại "the".
				App.la_khach = false;
				App.nguoi_dung = nguoi_dung || "";
			})
	);
}

/** ĐƯỜNG APP — NHẬN MÁY: đổi tấm thẻ lấy một khoá máy dùng lâu dài.
 *
 * KHÔNG gọi `dang_nhap_bang_the`: hàm đó mở một PHIÊN COOKIE, mà lời gọi của app là
 * KHÁC NGUỒN và `goi()` dùng `credentials: "same-origin"` — cái cookie ấy không bao
 * giờ được gửi đi lần nào nữa. Quét thẻ trên app bằng đường web là quét xong rồi
 * không đăng nhập được gì, một kiểu hỏng im lặng.
 *
 * CHỈ MỘT LỜI GỌI, khác đường web: `cap_khoa_may` trả luôn `ho_ten`, nên không cần
 * hỏi lại `get_logged_user` cho dòng tên trên màn menu.
 *
 * Khoá về tới đây là ĐÃ CẤP RỒI ở phía máy chủ — `dat_khoa()` cất nó xuống máy
 * NGAY, trước cả `di("menu")`: máy chủ chỉ trả chuỗi này đúng một lần, mất là phải
 * gọi trưởng kho. */
function _nhan_may(App, ma) {
	return App.goi("erpnext.warehouse_operations.vitri.the_pda.cap_khoa_may", {
		ma: ma,
		ten_may: _ten_may(),
		ma_may: App.ma_may(),
	}).then((kq) => {
		App.dat_khoa(kq.khoa);
		App.dat_nguoi_dung(kq.ho_ten || kq.nguoi_dung || "");
		App.la_khach = false;
	});
}

/** Một cái TÊN cho trưởng kho đọc trong danh sách máy ("PDA SM-T500"), không phải
 * một danh tính: danh tính là `ma_may`. Rút từ `navigator.userAgent` của WebView
 * (khối trong ngoặc đơn có dạng `Linux; Android 11; SM-T500 Build/...; wv`), nên nó
 * chỉ tốt tới mức nhà sản xuất khai — máy chủ đã phòng sẵn: rỗng thì `_ghi_thiet_bi`
 * lấy `ma_may` làm tên, và cắt còn 140 ký tự. */
function _ten_may() {
	const trong_ngoac = /\(([^)]*)\)/.exec(navigator.userAgent || "");
	const phan = trong_ngoac ? trong_ngoac[1].split(";").map((x) => x.trim()) : [];
	const may = (phan[2] || "").split(" Build/")[0].trim();
	return (may ? "PDA " + may : "PDA Android").slice(0, 140);
}

//: TASK 6 — bấm giữ logo bao lâu thì mở lối ẩn (mili-giây). BA GIÂY là một con số
//: có việc: dài hơn mọi cú chạm/quét vô tình (một cú chạm thường dưới 200ms, một
//: lần bấm giữ để chọn chữ khoảng 500ms), nhưng vẫn ngắn hơn sự kiên nhẫn của
//: người được chỉ cách làm. Không có bước xác thực nào ở đây và đó là CÓ CHỦ ĐÍCH:
//: xem `_mo_loi_an()` để biết vì sao một mật khẩu ở đây không thêm gì.
const _GIU_MO_LOI_AN_MS = 3000;

/** LỐI ẨN KHAI ĐỊA CHỈ MÁY CHỦ — hộp nhập, lưu đè, rồi tải lại trang.
 *
 * VÌ SAO KHÔNG ĐẶT MẬT KHẨU: thứ lối này đổi được là địa chỉ máy chủ mà CHIẾC MÁY
 * NÀY gọi tới. Ai bấm được ba giây trên logo thì đang cầm chiếc máy trong tay —
 * người đó cũng gỡ cài đặt được, cũng cài một APK khác được. Một mật khẩu ở đây
 * chỉ chặn đúng người ta muốn giúp (người đi cứu máy giữa ca) và không chặn ai
 * khác. Thẩm quyền thật nằm ở chỗ khác: khoá máy do máy chủ cấp, và trỏ sang một
 * máy chủ lạ thì khoá cũ vô giá trị ở đó.
 *
 * TẢI LẠI TRANG SAU KHI LƯU: `goc()` được đọc ở rất nhiều chỗ trong một lượt vẽ
 * (dòng "Máy chủ:", mọi lời gọi đang bay, bộ đệm giờ máy chủ của Task 5 vừa lấy từ
 * máy chủ CŨ). Vá từng chỗ là một danh sách phải nhớ; nạp lại trang thì mọi thứ
 * dựng lại từ một địa chỉ duy nhất. */
function _mo_loi_an(App) {
	const dang_dung = App.may_chu_ghi_de();
	erpnext.kho_pda.hoi_chuoi({
		noi_dung: __("Địa chỉ máy chủ. Chỉ dùng khi kỹ thuật yêu cầu."),
		// Ô hiện địa chỉ ĐANG DÙNG (`goc()`), kể cả khi nó là địa chỉ đóng gói —
		// người đi cứu máy cần thấy mình đang sửa từ cái gì, và thường chỉ phải đổi
		// một đoạn của tên miền ngrok.
		gia_tri: App.goc(),
		goi_y: "https://…",
		nhan: __("Lưu và mở lại"),
		// Nút "Bỏ địa chỉ gõ tay" CHỈ hiện khi thật sự có một địa chỉ gõ tay để bỏ —
		// hiện vô điều kiện thì trên máy chưa từng dùng lối ẩn nó là một nút không
		// làm gì, đúng thứ khiến người ta bấm thử.
		nhan_phu: dang_dung ? __("Bỏ địa chỉ gõ tay") : "",
		khi_luu: (chu) => {
			const loi = App.dat_may_chu(chu);
			if (loi) return loi;
			location.reload();
			return "";
		},
		khi_phu: () => {
			App.xoa_may_chu();
			location.reload();
		},
	});
}

/** Gắn "bấm giữ 3 giây" lên logo. Trả về hàm tháo (cho `roi()`).
 *
 * DÙNG SỰ KIỆN `pointer*`, KHÔNG `touch*` VÀ KHÔNG `mouse*`: WebView Android phát
 * `pointerdown/up/cancel` cho ngón tay, nên một bộ nghe là đủ cho cả máy thật lẫn
 * cổng nghiệm thu (Playwright bấm bằng chuột, cũng ra `pointer*`). Nghe `touch*`
 * thì cổng KHÔNG ĐO ĐƯỢC GÌ; nghe `mouse*` thì máy thật không chạy.
 *
 * `pointercancel` + `pointerleave` phải huỷ hẹn: kéo ngón tay ra khỏi logo (hoặc
 * hệ điều hành thu sự kiện lại để cuộn trang) là người dùng ĐÃ THÔI, không phải
 * đã giữ đủ ba giây. Thiếu hai nhánh này thì một cú chạm rồi cuộn vẫn bật hộp ra
 * sau ba giây, giữa lúc thủ kho đang quét. */
function _gan_loi_an($logo, App) {
	let hen = null;
	const huy = () => {
		if (hen) clearTimeout(hen);
		hen = null;
	};
	$logo.on("pointerdown", () => {
		huy();
		hen = setTimeout(() => {
			hen = null;
			_mo_loi_an(App);
		}, _GIU_MO_LOI_AN_MS);
	});
	$logo.on("pointerup pointercancel pointerleave", huy);
	// Bấm giữ trên Android bật trình chọn chữ ("copy/paste") che mất logo và ăn mất
	// sự kiện; `contextmenu` là nơi lượt đó lộ ra trên WebView.
	$logo.on("contextmenu", (sk) => sk.preventDefault());
	return huy;
}

erpnext.kho_pda.KhoApp.dang_ky_man("the", {
	tieu_de: __("Quét thẻ"),

	ve($than) {
		// LOGO CHỈ CÓ TRONG BẢN ĐÓNG GÓI. Nó không phải trang trí — nó là cái nút
		// của lối ẩn (`_gan_loi_an`), mà lối ẩn chỉ có nghĩa ở nơi địa chỉ máy chủ
		// bị nướng vào bản cài. Trên `/kho` của web địa chỉ là chính trang đang mở,
		// không có gì để khai đè; và ràng buộc của cả đợt là bản web KHÔNG đổi hành
		// vi — kể cả không thêm một phần tử nào vào màn.
		const logo = erpnext.kho_pda.KhoApp._la_app()
			? `<div class="man-the-logo" aria-hidden="true">MIYANO</div>`
			: "";
		$than.html(`
			<div class="man-the">
				<div class="man-the-hinh" aria-hidden="true">
					<svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="11" r="2"/><path d="M6 16c.6-1.4 1.7-2 3-2s2.4.6 3 2"/><path d="M15 10h3M15 13h3"/></svg>
				</div>
				${logo}
				<p class="man-the-mo">${__("Bắn mã vạch trên thẻ. Thẻ mờ thì bấm Gõ tay.")}</p>
				<div class="man-the-o"></div>
				<div class="man-the-loi"></div>
				<div class="man-the-may-chu"></div>
			</div>
		`);
		// Không chiếm chỗ của ô quét/nút — chỉ để thủ kho phát hiện ngay nếu app
		// lỡ trỏ vào site thử thay vì site thật (cùng lý do `pda.html` đã làm).
		//
		// `KhoApp.dia_chi_may_chu()`, KHÔNG `location.origin` (Task 2): trong bản
		// đóng gói `location.origin` là nguồn của CHÍNH CÁI VỎ (`file://`, APK:
		// `https://localhost`), không phải máy chủ đang nối — dòng này khi đó nói
		// sai đúng lúc nó cần nhất. Hàm kia đọc CÙNG hằng số mà `goi()` dùng để
		// dựng địa chỉ, nên dòng trên màn và lời gọi mạng không thể trôi khỏi nhau.
		$than.find(".man-the-may-chu").text(__("Máy chủ: {0}", [erpnext.kho_pda.KhoApp.dia_chi_may_chu()]));
		// Dải "BẢN THỬ" khi bản đóng gói này trỏ vào máy chủ khác địa chỉ phát
		// hành — dấu hiệu không cần đọc chữ. Trên web không sinh gì (xem `vo.js`).
		erpnext.kho_pda.KhoApp.ve_dai_ban_thu($than.find(".man-the"));
		// TASK 5 — dải cảnh báo lệch giờ máy (spec §8). Màn thẻ là màn ĐẦU TIÊN thủ
		// kho thấy, và lượt đồng bộ giờ đã bắn đi từ `khoi_dong()` — hiện được ở đây
		// sớm nhất có thể, cùng khuôn với dải "BẢN THỬ". Trên web tự không hiện gì
		// (xem `ve_dai_lech_gio` trong `vo.js`).
		erpnext.kho_pda.KhoApp.ve_dai_lech_gio($than.find(".man-the"));
		// VÒNG SỬA 1 — "im lặng phải nhìn thấy được": nếu lượt đồng bộ giờ máy chủ
		// cứ hỏng, dải này báo rõ thay vì để chip hạn dùng lặng lẽ biến mất suốt ca.
		erpnext.kho_pda.KhoApp.ve_dai_thieu_gio($than.find(".man-the"));
		// TASK 6 — lối ẩn khai địa chỉ máy chủ. `$logo` rỗng trên web (xem trên), và
		// `.on()` trên một tập rỗng của jQuery không gắn gì — không cần rẽ nhánh
		// thêm lần nữa ở đây.
		this._thao_loi_an = _gan_loi_an($than.find(".man-the-logo"), erpnext.kho_pda.KhoApp);

		const $loi = $than.find(".man-the-loi");
		// Chặn bắn hai mã chồng nhau trong lúc lời gọi trước chưa xong: súng quét
		// tự gửi lại sau `TU_GUI_SAU_MS` (o_quet.js) nên tay run/quét trượt dễ tạo
		// hai lượt liền nhau hơn người gõ bàn phím thường.
		let dang_gui = false;

		this._oq = new erpnext.kho_pda.OQuet({
			cha: $than.find(".man-the-o"),
			vung: $than,
			goi_y: __("Quét thẻ nhân viên…"),
			khi_quet: (ma) => {
				if (dang_gui) return;
				dang_gui = true;
				$loi.text("");
				const App = erpnext.kho_pda.KhoApp;
				// RẼ NHÁNH Ở ĐÚNG MỘT CHỖ, và hai nhánh cùng hứa một điều: khi lời hứa
				// xong thì `la_khach` đã là `false` và `nguoi_dung` đã đúng — phần sau
				// (`di("menu")`, báo lỗi) vì thế viết một lần cho cả hai nơi.
				const vao = App._la_app() ? _nhan_may(App, ma) : _dang_nhap_ca(App, ma);
				vao
					.then(() => App.di("menu"))
					.catch((loi) => {
						// Hiện ĐÚNG câu máy chủ trả về (Bước 6 của brief) ở khung riêng của
						// màn này — không dùng dải báo chung `KhoApp.bao()`: dải đó là chỗ
						// `goi()` tự dùng cho ca "phiên hết hạn", một câu chuyện khác với
						// "thẻ vừa quét sai" (xem chú thích trong `goi()`, vo.js).
						dang_gui = false;
						$loi.text(loi && loi.message);
						// `roi()` gán `this._oq = null` khi rời màn — nếu lời gọi này bay xong
						// SAU KHI người dùng đã rời màn thẻ (đường thật: 401 dẫn thẳng lại về
						// chính màn "the", `goi()` bỏ qua nhánh đó khi đang ở "the" nên hôm nay
						// chưa từng chạm tới, nhưng Task 2–5 chép mẫu này ở màn khác dễ dính —
						// soát xét vòng 2, N5) thì gọi thẳng `.giu_focus()` trên `null` ném
						// `TypeError` ngay trong `.catch()`, nuốt luôn câu lỗi vừa hiện ở `$loi`.
						this._oq && this._oq.giu_focus();
					});
			},
		});
	},

	roi() {
		// `roi()` là móc dọn dẹp duy nhất mà `vo.js::_ve()` gọi khi rời màn — không
		// gọi `huy()` ở đây thì listener trên `document` (khoá khi có hộp mở) và
		// trên `$than` (trả focus khi chạm chỗ trống) của `OQuet` này sống mãi, dù
		// DOM của nó đã bị `$than.empty()` xoá sạch (soát xét vòng 1, mục P2).
		this._oq && this._oq.huy();
		this._oq = null;
		// Cùng lý do với `OQuet` ở trên: `$than.empty()` xoá DOM của logo nhưng KHÔNG
		// huỷ cái `setTimeout` đang chạy dở. Rời màn thẻ giữa lúc ngón tay còn đè
		// logo thì ba giây sau hộp lối ẩn bật ra trên một màn khác hẳn.
		this._thao_loi_an && this._thao_loi_an();
		this._thao_loi_an = null;
	},
});
