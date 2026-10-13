// Khung của app PDA: định tuyến, khung màn hình, dải báo, và một chỗ DUY NHẤT
// gọi máy chủ.
//
// ĐỊNH TUYẾN BẰNG HASH: nút Back của Android lùi trong lịch sử trình duyệt. Dùng
// hash thì mỗi màn là một mục lịch sử mà KHÔNG tải lại trang — tải lại giữa ca là
// mất trạng thái đang quét dở.
//
// MỌI LỜI GỌI MÁY CHỦ ĐI QUA `goi()`: phiên sống 12 tiếng, hết giữa ca thì máy chủ
// trả 401/403. Gom về một chỗ thì chỉ cần một câu "về màn quét thẻ", thay vì mỗi
// màn tự đoán.
//
// VÌ SAO `goi()` DÙNG `fetch()` THẲNG, KHÔNG `frappe.xcall`: `frappe.xcall` bọc
// `frappe.call`, mà nhánh lỗi 401/403 của nó (`frappe/public/js/frappe/request.js`)
// gọi `frappe.app.handle_session_expired()` trước khi tới tay ta — `frappe.app`
// chỉ được gán trong `desk.js` (`frappe.app = new frappe.Application()`), KHÔNG
// nằm trong `frappe-web.bundle.js` mà trang website này nạp. Lỗi ném ra bị nuốt
// trong khối `try/catch` của `.fail()` trong chính file đó, nên `error_callback`
// (chỗ `xcall` gọi `reject`) KHÔNG BAO GIỜ chạy — promise treo mãi, `.catch()` ở
// đây không bao giờ tới lượt. Nhánh 403 còn tự bật một hộp `msgprint` — hộp thoại
// kiểu Desk trên màn 4 inch, đúng thứ `test_vo_khong_dung_api_cua_desk` cấm (bài
// đó chỉ đọc file của TA nên không bắt được lỗi này, nhưng gọi `xcall` vẫn sai
// tinh thần Task 1). `fetch()` thẳng — cùng cách `erpnext/www/pda.html` đã làm
// cho màn quét thẻ gốc — tránh toàn bộ lớp đó và tự đọc được `_server_messages`
// để hiện đúng câu máy chủ trả về (Bước 6 của brief).

frappe.provide("erpnext.kho_pda");

// ============================================================================
// KHO CẤT BỀN CỦA MÁY (Task 4)
// ============================================================================
//
// Khoá máy và mã máy cất trong `localStorage` CỦA WEBVIEW. Đây là vùng RIÊNG của
// app (sandbox Android — WebView của app đứng tên nguồn `https://localhost` do
// Capacitor phục vụ, không dùng chung kho với Chrome hay bất kỳ app nào khác), và
// nó SỐNG QUA CÁC LẦN MỞ APP. Đó là toàn bộ điều kiện để "chạm icon là vào thẳng
// menu": thủ kho quét thẻ MỘT LẦN lúc nhận máy, không phải mỗi ca.
//
// HỆ QUẢ PHẢI BIẾT, nói thẳng ra để không ai đi tìm lỗi khi nó xảy ra: người dùng
// (hoặc IT) bấm "Xoá dữ liệu ứng dụng" trong Cài đặt Android là MẤT KHOÁ → app mở
// lên ở màn quét thẻ, quét lại là xong. Không mất gì khác: mọi dữ liệu nghiệp vụ
// nằm ở máy chủ, chỗ này chỉ giữ danh tính của chiếc máy.
//
// VÌ SAO KHÔNG THÊM GÓI `@capacitor/preferences`: thêm một gói npm là thêm một thứ
// phải cài được lúc dựng — và ở đây nó còn KHÔNG DÙNG ĐƯỢC. `kho_pda.bundle.js` do
// `bench build` dựng từ `apps/erpnext`, nên một dòng `import ... from
// "@capacitor/preferences"` giải theo `apps/erpnext/node_modules` (thư mục đó hôm
// nay chỉ có `onscan.js`), KHÔNG phải `pda_app/node_modules`. Mà CÙNG MỘT bundle
// còn phục vụ trang `/kho` trên web, nơi không có Capacitor nào cả. `localStorage`
// có sẵn ở cả hai nơi và đã đủ.
//
// MỌI PHÉP ĐỌC/GHI BỌC `try/catch`: WebView có thể bị chặn kho lưu (chế độ riêng
// tư, dữ liệu vừa bị xoá, bản Android nào đó tắt DOM storage). Một ngoại lệ ném ra
// ở `khoi_dong()` là MÀN TRẮNG không lời giải thích; hỏng theo hướng "coi như chưa
// có khoá" thì cùng lắm là phải quét thẻ lại — luôn chọn hướng đó.
const _O_KHOA = "kho_pda.khoa";
const _O_MA_MAY = "kho_pda.ma_may";
const _O_NGUOI_DUNG = "kho_pda.nguoi_dung";
//: TASK 6 — địa chỉ máy chủ do LỐI ẨN khai đè lên địa chỉ đóng gói trong
//: `cau-hinh.js`. Xem `_nap_may_chu_ghi_de()` để biết vì sao lối ẩn tồn tại.
const _O_MAY_CHU = "kho_pda.may_chu";

//: TASK 6 — các máy chủ được phép gọi bằng HTTP KHÔNG mã hoá từ lối ẩn.
//:
//: HỢP ĐỒNG VỚI TẦNG ANDROID, không phải một lựa chọn của JS: từ Android 9, một
//: lời gọi `http://` tới địa chỉ không có trong
//: `pda_app/android/app/src/main/res/xml/network_security_config.xml` bị CHÍNH
//: HỆ ĐIỀU HÀNH chặn, trước khi chạm tới mã của app. Người đi cứu máy gõ một địa
//: chỉ LAN `http://` lạ sẽ thấy triệu chứng y hệt "máy chủ chết" — đúng cái tình
//: huống lối ẩn sinh ra để chấm dứt. Từ chối NGAY LÚC GÕ kèm một câu nói rõ vì
//: sao thì người ta còn biết phải làm gì.
//:
//: KHÔNG nới `base-config` của file XML để khỏi phải kiểm: nới ra là mọi lời gọi
//: của app đi được bằng HTTP trần, kể cả lời gọi mang khoá máy.
//: `test_giao_dien.test_task6_danh_sach_host_http_khop_network_security_config`
//: đối chiếu thẳng danh sách này với file XML, nên hai nơi không trôi khỏi nhau.
const _HOST_HTTP_CHO_PHEP = ["192.168.61.129", "10.0.2.2"];

//: Tên lớp ngoại lệ mà Frappe trả trong `exc_type` khi lời gọi bị từ chối vì
//: DANH TÍNH (khoá API sai, hoặc `the_pda.kiem_khoa_may` từ chối mã máy). ĐÂY LÀ
//: HỢP ĐỒNG VỚI MÁY CHỦ: `frappe/utils/response.py:47` ghi
//: `frappe.response["exc_type"] = exc_type.__name__` cho API v1, và
//: `frappe/exceptions.py` cho `AuthenticationError.http_status_code = 401`,
//: `PermissionError.http_status_code = 403`.
//:
//: Phân biệt này là thứ chặn ca N2: một lỗi QUYỀN nghiệp vụ (403/PermissionError)
//: từng làm app XOÁ khoá máy và đá thủ kho về màn quét thẻ — xem `_la_loi_danh_tinh`.
//: `test_giao_dien.test_task6_kiem_khoa_may_van_nem_dung_lop_ngoai_le` đối chiếu
//: hằng số này với lớp ngoại lệ `the_pda.py` thật sự ném, nên hai nơi không trôi
//: khỏi nhau.
const _EXC_DANH_TINH = "AuthenticationError";

//: Tên header khai "tôi là chiếc máy nào". HỢP ĐỒNG với máy chủ:
//: `the_pda.py::DAU_MA_MAY`. Máy chủ TỪ CHỐI 401 mọi lời gọi mang khoá mà thiếu
//: header này (fail-closed, cố ý) — nên lệch một chữ ở đây là cả kho đứng im, và
//: `test_giao_dien.py` đối chiếu thẳng hai hằng số này với nhau.
const _DAU_MA_MAY = "X-Ma-May";

//: Đường gọi máy chủ để đồng bộ đồng hồ (Task 5, spec §8) — xem `_dong_bo_gio_may_chu()`.
const _DUONG_GIO_MAY_CHU = "erpnext.warehouse_operations.vitri.the_pda.gio_may_chu";
//: Lệch quá ngưỡng này (phút) thì hiện dải cam nhắc IT (`ve_dai_lech_gio`). KHÔNG
//: đổi phán quyết hết hạn — phán quyết đó luôn theo giờ MÁY CHỦ bất kể lệch bao
//: nhiêu; ngưỡng này chỉ quyết định có NÓI hay không, một lời nhắc chứ không phải
//: một cái khoá (brief Task 5, Bước 4: "Không chặn việc, chỉ nói").
const _NGUONG_LECH_GIO_PHUT = 10;
//: Sau chừng này (mili-giây) kể từ lượt đồng bộ TRƯỚC, coi giờ máy chủ đã cất là
//: CŨ và tự đồng bộ lại — xem lý do đầy đủ ở `_dong_bo_gio_may_chu()`: khoá máy
//: không bao giờ hết hạn nên một WebView có thể sống qua nửa đêm mà không tải
//: lại; không có ngưỡng này thì `ngay_may_chu()` kẹt ở NGÀY LÚC MỞ APP suốt phiên
//: — cùng lớp lỗi mà cả Task này sinh ra để vá, chỉ đổi tên từ "đồng hồ máy sai"
//: thành "bộ nhớ đệm cũ". 45 phút: đủ ngắn để không lỡ một phiên qua đêm, đủ dài
//: để không đồng bộ lại ở MỌI lượt quét (chi phí một `fetch()` mỗi 45 phút, không
//: phải mỗi lần bấm).
const _NGUONG_LAM_MOI_GIO_MS = 45 * 60 * 1000;
//: VÒNG SỬA 1 (soát xét, T5-1) — quá chừng này (mili-giây) mà lượt `fetch()` đồng
//: bộ giờ còn chưa xong thì COI NHƯ HỎNG và nhả cờ `_dang_dong_bo_gio` ra, thay vì
//: chờ mãi. Không phải `AbortController`: cầu HTTP native của Capacitor không đọc
//: `signal`, một `AbortController` chỉ có tác dụng trên trình duyệt thường — xem
//: lý do đầy đủ ở `_dong_bo_gio_may_chu()`.
const _THOI_GIAN_CHO_DONG_BO_MS = 8000;
//: VÒNG SỬA 1 (soát xét, mục 4 — "im lặng phải nhìn thấy được") — "chưa có giờ
//: máy chủ dùng được" kéo dài quá chừng này (mili-giây) thì hiện dải riêng
//: (`ve_dai_thieu_gio`). Ngắn hơn khoảng thời gian đồng bộ BÌNH THƯỜNG lúc mở app
//: (thường dưới 1 giây) sẽ nhấp nháy dải này ở MỌI lần mở — dài hơn thế mới đúng
//: là dấu hiệu của một ca THẬT SỰ kẹt (mất mạng lâu, máy chủ hỏng riêng đường này).
const _NGUONG_BAO_THIEU_GIO_MS = 5000;

function _doc_ben(ten) {
	try {
		return window.localStorage.getItem(ten) || "";
	} catch (e) {
		return "";
	}
}

function _ghi_ben(ten, gia_tri) {
	try {
		window.localStorage.setItem(ten, gia_tri);
	} catch (e) {
		// Nuốt có chủ đích — xem khối chú thích trên. Người gỡ lỗi vẫn thấy hậu quả
		// (app hỏi thẻ lại mỗi lần mở), và đó là hậu quả ĐÚNG.
	}
}

function _xoa_ben(ten) {
	try {
		window.localStorage.removeItem(ten);
	} catch (e) {
		// như trên
	}
}

/** Sinh mã máy: một chuỗi NGẪU NHIÊN, cất lại và dùng mãi.
 *
 * QUYẾT ĐỊNH (Task 4, việc 3): KHÔNG thêm `@capacitor/device` để lấy `Device.getId()`.
 * Hai lý do, lý do thứ hai mới là lý do thật:
 *
 * 1. Gói đó không giải được trong bundle này (xem khối chú thích trên), và nó kéo
 *    theo một plugin native phải đăng ký trong project Android.
 * 2. KHÔNG ĐỔI LẤY GÌ CẢ: từ Capacitor 4, `Device.getId()` trên Android trả về một
 *    UUID mà CHÍNH PLUGIN tự sinh rồi cất trong kho tuỳ chọn của app (Android đã
 *    khoá `ANDROID_ID` lại theo từng app từ Android 8). Tức nó cũng chỉ là "một
 *    chuỗi ngẫu nhiên cất trong vùng riêng của app", CÙNG VÒNG ĐỜI với dòng dưới
 *    đây: "Xoá dữ liệu ứng dụng" là mất cả hai.
 *
 * `randomUUID` cần ngữ cảnh an toàn (có ở `https://localhost` của APK); hai bậc rơi
 * phía sau để một WebView đời cũ không làm hàm này ném — mã máy tệ hơn một chút vẫn
 * hơn là app không nhận máy được. */
function _sinh_ma_may() {
	const may = window.crypto;
	if (may && typeof may.randomUUID === "function") return "pda-" + may.randomUUID();
	if (may && typeof may.getRandomValues === "function") {
		const byte = new Uint8Array(16);
		may.getRandomValues(byte);
		return "pda-" + Array.from(byte, (b) => ("0" + b.toString(16)).slice(-2)).join("");
	}
	return "pda-" + Date.now().toString(16) + "-" + Math.random().toString(16).slice(2, 14);
}

// Câu thay thế khi KHÔNG có câu nào của máy chủ dùng được (thân rỗng, không đúng
// khuôn `_server_messages`, hoặc câu rút ra là HTML — xem `_cau_loi_may_chu`).
//
// 401/403 ĐƯỢC NÓI RIÊNG vì nó là ca DUY NHẤT mà người đứng trước máy làm được
// một việc cụ thể: "Có lỗi, thử lại." bảo thủ kho bấm lại một nút sẽ hỏng y như
// vậy lần nữa.
//
// VÒNG SỬA CUỐI — LỜI KHAI CŨ SAI, VÀ NÓ DẪN CẢ BẢN VÁ ĐI HƯỚNG SAI (soát tổng,
// N2). Câu cũ viết: *"trong app, 401/403 nghĩa là máy chủ không nhận danh tính của
// MÁY NÀY"*. Đúng với 401, **SAI với 403**. Đo trên máy chủ thật (25/09/2026):
//
//     khoá API sai        → HTTP 401, exc_type "AuthenticationError"
//     lỗi QUYỀN nghiệp vụ → HTTP 403, exc_type "PermissionError"
//
// `kiem_khoa_may` (the_pda.py) ném `frappe.AuthenticationError`, tức **401**. Nên
// 403 trong app là "tài khoản này không được phép làm VIỆC NÀY" — một câu chuyện
// khác hẳn, và nó ĐÃ XẢY RA THẬT: `selling_controller.py` mang một bản vá ngày
// 24/09 cho đúng `PermissionError` mà thủ kho ăn **mỗi lần lưu phiếu giao** trên
// màn Lấy hàng. Bảo họ "báo trưởng kho cấp khoá cho máy này" là chỉ sai người và
// sai việc.
//
// BA CÂU, không phải hai:
//   web (mọi mã)      — "Có lỗi, thử lại." / câu cũ ở `goi()`; KHÔNG đổi một chữ.
//   app 401           — khoá máy chưa cấp hoặc đã bị thu hồi → trưởng kho cấp khoá.
//   app 403           — quyền của TÀI KHOẢN, khoá máy vẫn tốt → trưởng kho xem quyền.
function _cau_loi_thay_the(ma, la_app) {
	if (la_app && ma === 401)
		return __("Máy chưa được cấp quyền — báo trưởng kho cấp khoá cho máy này.");
	if (la_app && ma === 403)
		return __("Tài khoản không có quyền làm việc này — báo trưởng kho.");
	return __("Có lỗi, thử lại.");
}

// Rút câu báo của máy chủ từ phần thân JSON lỗi (giống `loi_tu` trong
// `erpnext/www/pda.html`) — mọi màn dùng `goi()` cần câu THẬT, không phải một
// câu chung chung che mất lý do (thẻ sai khác thẻ đã thu hồi khác tài khoản khoá).
//
// CHẶN CÂU HTML (Task 2B): Frappe nhét NGUYÊN MỘT KHỐI HTML tiếng Anh vào
// `_server_messages` cho lỗi quyền — đo được ở vòng soát Task 2:
// `"<details><summary>You are not permitted to access this resource. Login to
// access</summary>Function …tra_cuu is not whitelisted.</details>"`. Hàm này rút
// đúng thứ máy chủ đưa (nó KHÔNG hỏng), nhưng `_dam()` escape nên thủ kho đọc
// thấy cả thẻ `<details>` dưới dạng chữ, giữa kho, trên màn 4 inch.
//
// LỌC THEO DẤU VẾT HTML, KHÔNG THEO MÃ LỖI: đây là một LỚP lỗi, không phải một
// ca. Một trang 500 HTML, một câu `<b>…</b>` của hàm nghiệp vụ nào đó, một bản
// Frappe sau đổi câu chữ — tất cả đổ vào cùng dải báo theo cùng một đường. Đo
// "câu này có phải markup không" chặn cả lớp; đo "mã có phải 403 không" chặn
// đúng một ca và sẽ thủng ở ca sau.
//
// `console.warn` NGUYÊN VĂN: người gỡ lỗi vẫn phải đọc được câu thật ("Function X
// is not whitelisted" là chẩn đoán, không phải rác) — chỉ là không cho nó ra màn
// hình của thủ kho. Đây là chỗ DUY NHẤT câu đó biến mất, nên phải có một lối ra
// cho nó ở đây, không phải ở chỗ gọi.
function _cau_loi_may_chu(than, ma, la_app) {
	let cau = "";
	try {
		const ds = JSON.parse((than && than._server_messages) || "[]");
		if (ds.length) cau = JSON.parse(ds[0]).message;
	} catch (e) {
		// Thân lỗi không đúng khuôn `_server_messages` (mất mạng, 500 không kịp
		// định dạng...) — rơi về câu thay thế bên dưới, không để lỗi phân tích JSON
		// đè lên lỗi gốc.
	}
	cau = cau == null ? "" : String(cau);
	if (!cau) return _cau_loi_thay_the(ma, la_app);
	// Một thẻ mở (`<details`, `<b`) hoặc một khai báo (`<!doctype`) — cộng thêm
	// phép đo thẻ ĐÓNG (`</p>`) cho ca câu bị cắt đầu. KHÔNG dùng `indexOf("<")`
	// trần: một câu nghiệp vụ hợp lệ có thể chứa `<` (ví dụ "số lượng < 0"), và
	// câu đó thủ kho PHẢI đọc được.
	if (/<[a-zA-Z!]/.test(cau) || cau.indexOf("</") !== -1) {
		console.warn("kho_pda: câu lỗi máy chủ là HTML, không hiện cho thủ kho:", cau);
		return _cau_loi_thay_the(ma, la_app);
	}
	return cau;
}

// SOÁT XÉT VÒNG 1 (Task 3, mục 3): quy ước tô đậm AN TOÀN cho `bao()` — lớp LUỒNG
// (vd `warehouse_operations/luong/xep_hang.js`) đánh dấu phần muốn nổi bật (số
// lượng, mã ô…) bằng cặp `**…**` NGAY TRONG câu chữ thường nó trả về; hàm này
// ESCAPE TOÀN BỘ chuỗi TRƯỚC (triệt tiêu mọi `<`/`>`/`&` — kể cả những gì đứng
// giữa hai dấu `**`), RỒI MỚI đổi `**x**` thành `<b>x</b>` CỦA RIÊNG NÓ. Thứ tự
// này là điểm mấu chốt: một câu báo LẤY TỪ MÁY CHỦ không có cách nào nhét được
// một thẻ HTML thật vào `$bao` — cùng lắm chỉ chèn được thêm một cặp `**` vô hại
// (tự biến thành `<b>` của CHÍNH TA, không phải thẻ do nó tự ý đưa vào). Task 3
// (soát xét, mục P2) từng phát hiện: bỏ tô đậm hoàn toàn (escape trần, không quy
// ước gì) làm mất đúng chỗ thủ kho cần liếc nhanh nhất trên màn 4 inch — số lượng
// và mã ô đích. Không dùng `**` trong câu thì hàm này là `escape_html` nguyên
// vẹn, không đổi hành vi của mọi lời gọi `bao()` khác trong app.
function _dam(chu) {
	return frappe.utils
		.escape_html(chu)
		.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
}

class _KhoApp {
	constructor() {
		this.man = {};
		this.man_hien_tai = null;
		// Khoá máy (Authorization). Task 3 cấp nó; Task 4 cất nó vào máy và nạp lại
		// lúc khởi động (`khoi_dong` → `_nap_khoa_da_cat`). Trên web ô này LUÔN rỗng
		// — ở đó danh tính đi bằng cookie phiên, không có khoá máy nào.
		this._khoa = "";
		// Bản sao trong bộ nhớ của mã máy: `ma_may()` đọc `localStorage` MỘT LẦN rồi
		// giữ ở đây. Không có bản sao này thì một WebView bị chặn kho lưu sẽ sinh một
		// mã MỚI ở MỖI lời gọi — máy chủ cấp khoá cho mã thứ nhất rồi 401 lời gọi thứ
		// hai, một kiểu hỏng gần như không chẩn đoán được từ trong kho.
		this._ma_may = "";
		// TASK 5 — giờ MÁY CHỦ, đồng bộ MỘT LẦN lúc mở app (`_dong_bo_gio_may_chu()`,
		// gọi từ `khoi_dong()`). `null` = CHƯA đồng bộ xong (mất mạng, hoặc đang giữa
		// lượt gọi đầu) — `ngay_may_chu()`/`gio_may_chu()` trả thẳng `null` trong ca
		// đó, KHÔNG tự suy ra một ngày/giờ nào khác từ đồng hồ máy: lớp luồng
		// (`luong/tra_cuu.js`) đọc `null` là "chưa biết", ẩn chip hạn dùng thay vì
		// dùng liều giờ máy trạm — thà mất một chip trong vài trăm mili-giây đầu còn
		// hơn một phán quyết hết hạn ĐÚNG-NHÌN-SAI-BỤNG dựa trên đồng hồ không đảm bảo.
		this._gio_may_chu = null;
		this._dang_dong_bo_gio = false;
		// VÒNG SỬA 1 — mốc `Date.now()` đầu tiên của đợt "thiếu giờ máy chủ dùng
		// được" đang diễn ra; `null` khi đang có giờ tốt. Chỉ dùng để quyết định
		// hiện `ve_dai_thieu_gio()` hay không — xem `_theo_doi_thieu_gio()`.
		this._luc_dau_tien_thieu_gio = null;
		// TASK 6 — địa chỉ máy chủ do LỐI ẨN khai đè. Rỗng = dùng địa chỉ đóng gói
		// (`window.KHO_MAY_CHU`). Nạp từ kho lưu trong `khoi_dong()`, và CHỈ trong
		// app — xem `_nap_may_chu_ghi_de()`.
		this._may_chu_ghi_de = "";
		// TASK 6 — lời hứa của lượt hỏi "bản cài mới nhất là bản nào" (spec §10).
		// GHI NHỚ MỘT LẦN MỖI LƯỢT MỞ APP: màn menu là màn thủ kho quay lại nhiều
		// nhất trong ca, hỏi lại máy chủ ở mỗi lượt vẽ là hàng chục lời gọi thừa cho
		// một thông tin đổi vài tháng một lần.
		this._hen_ban_cai = null;
	}

	dang_ky_man(ten, dinh_nghia) {
		this.man[ten] = dinh_nghia;
	}

	/** ĐỊA CHỈ GỐC CỦA MÁY CHỦ — CHỖ DUY NHẤT GIỮ NÓ.
	 *
	 * Trên web trả CHUỖI RỖNG: `fetch("/api/method/...")` là đường TƯƠNG ĐỐI,
	 * giải theo `location` → đúng máy chủ đang phục vụ trang `/kho`, y như hành vi
	 * trước Task 2. Trong app, vỏ khai `window.KHO_MAY_CHU` (`www/cau-hinh.js`,
	 * do `scripts/pda/dong-goi.sh` sinh) và hàm này trả địa chỉ TUYỆT ĐỐI.
	 *
	 * VÌ SAO KHÔNG ĐỂ ĐƯỜNG TƯƠNG ĐỐI CHO CẢ HAI NƠI: trong app trang nằm ở
	 * `file://` (APK thật: `https://localhost` — Capacitor `androidScheme`), nên
	 * `/api/method/...` trỏ vào CHÍNH CÁI VỎ, không tới máy chủ. Hỏng kiểu này IM
	 * LẶNG: WebView trả 404 của chính nó, không phải lỗi mạng, nên `goi()` đọc ra
	 * một lỗi HTTP bình thường và mọi màn báo "Có lỗi, thử lại." mãi mãi.
	 *
	 * KHÔNG hằng số hoá địa chỉ vào bundle: CÙNG MỘT `kho_pda.bundle.js` phục vụ
	 * cả hai nơi (đó là điều kiện để web và app không trôi khỏi nhau), nên chỗ
	 * phân biệt phải là một biến toàn cục do vỏ khai, không phải hai bản mã.
	 *
	 * CẮT DẤU `/` THỪA Ở ĐUÔI: `cau-hinh-may-chu.json` là file NGƯỜI PHÁT HÀNH
	 * sửa tay trước khi dựng APK; một địa chỉ ngrok dán vào kèm `/` ở cuối sẽ
	 * thành `https://x.ngrok.app//api/method/...`. Chuẩn hoá Ở ĐÂY, không ở chỗ
	 * gọi — để dòng "Máy chủ:" trên màn và lời gọi mạng luôn đọc cùng MỘT giá trị
	 * đã chuẩn hoá, không phải hai giá trị hơi khác nhau.
	 *
	 * LỐI ẨN GHI ĐÈ ĐỌC Ở ĐÂY, KHÔNG Ở CHỖ KHÁC (Task 6): `this._may_chu_ghi_de`
	 * là địa chỉ mà người đi cứu máy đã gõ tay (`_nap_may_chu_ghi_de()` nạp nó từ
	 * kho lưu lúc `khoi_dong()`). Đặt phép ưu tiên NGAY TRONG hàm này là cách duy
	 * nhất giữ đúng bất biến "một chỗ duy nhất giữ địa chỉ": dòng "Máy chủ:" trên
	 * màn (`dia_chi_may_chu()`) và lời gọi mạng (`goi()`) đều đi qua đây, nên
	 * chúng không thể nói hai câu khác nhau. Ghi thẳng vào `window.KHO_MAY_CHU`
	 * thì HỎNG: `cau-hinh.js` chạy ở mỗi lượt tải trang và đè lại giá trị ấy, và
	 * cổng `kiem_goi_mang.js` còn khai biến đó bằng `defineProperty` có setter
	 * rỗng — một phép gán sẽ bị NUỐT, tức lối ẩn xanh trong bài mà chết trên máy. */
	goc() {
		return (this._may_chu_ghi_de || window.KHO_MAY_CHU || "").replace(/\/+$/, "");
	}

	/** Địa chỉ máy chủ để HIỆN LÊN MÀN (màn thẻ + màn menu).
	 *
	 * ĐỌC ĐÚNG CÁI HẰNG SỐ MÀ `goi()` DÙNG — đó là toàn bộ lý do hàm này tồn tại
	 * thay vì mỗi màn tự in `location.origin`. Thứ thủ kho cần thấy không phải
	 * "trang này đang nằm ở đâu" mà "bản cài này gọi tới máy chủ NÀO": đây là chốt
	 * chặn bằng mắt duy nhất chống ca cài nhầm bản trỏ máy chủ thử rồi ghi vào dữ
	 * liệu thử mà không ai biết. Trong bản đóng gói `location.origin` là `file://`
	 * (APK: `https://localhost`) — một chốt chặn bằng mắt mà nói dối thì tệ hơn là
	 * không có.
	 *
	 * Rơi về `location.origin` khi `goc()` rỗng là ĐÚNG, không phải một nguồn thứ
	 * hai: `goc()` rỗng nghĩa là `goi()` đang dùng đường TƯƠNG ĐỐI, mà đường tương
	 * đối giải ra đúng `location.origin`. Hai vế của câu vẫn là một. */
	dia_chi_may_chu() {
		return this.goc() || location.origin;
	}

	/** Đang chạy trong bản ĐÓNG GÓI (vỏ khai `window.KHO_LA_APP = true` trong
	 * `pda_app/www/index.html`) hay trên trang `/kho` của web. Dùng để BỎ nhánh
	 * CSRF — xem `goi()`. */
	_la_app() {
		return window.KHO_LA_APP === true;
	}

	/** Lượt gọi bị từ chối này có phải vì MÁY CHỦ KHÔNG NHẬN DANH TÍNH CỦA MÁY NÀY
	 * không — hay chỉ là tài khoản không đủ quyền làm việc vừa bấm?
	 *
	 * ĐÂY LÀ HAI CHUYỆN KHÁC HẲN NHAU, và đánh đồng chúng đã là một lỗi NẶNG (soát
	 * tổng, N2): chỉ ca thứ nhất được phép `xoa_khoa()` + đá về màn quét thẻ. Ca
	 * thứ hai phải để thủ kho đứng yên tại chỗ với một câu nói đúng nguyên nhân —
	 * khoá máy của họ vẫn tốt, quét lại thẻ không chữa được gì.
	 *
	 * ĐO ĐƯỢC TRÊN MÁY CHỦ THẬT (25/09/2026), không suy luận:
	 *     `Authorization: token sai:sai`  → 401 + exc_type "AuthenticationError"
	 *     lỗi quyền nghiệp vụ             → 403 + exc_type "PermissionError"
	 * và `the_pda.kiem_khoa_may` — hàng rào mã máy — ném `frappe.AuthenticationError`,
	 * tức 401. Nên trong app: **401 là danh tính, 403 thì không**.
	 *
	 * VẾ 403 VẪN ĐƯỢC XÉT, không cắt thẳng: nếu một ngày hàng rào mã máy đổi sang
	 * ném ở tầng khác mà vẫn là lỗi danh tính, `exc_type` nói đúng sự thật đó và
	 * app không phải đợi một lượt sửa nữa. Đọc `exc_type` chứ KHÔNG so câu chữ
	 * tiếng Việt: câu chữ là thứ sửa mỗi vòng, tên lớp ngoại lệ thì không.
	 *
	 * WEB GIỮ NGUYÊN HÀNH VI CŨ, cố ý: ở đó 401/403 đều là "phiên hết", `goi()` đã
	 * báo đúng câu đó và đưa về màn thẻ từ trước Task 4. Ràng buộc của cả đợt là
	 * bản web không đổi một hành vi nào. */
	_la_loi_danh_tinh(ma, than) {
		if (!this._la_app()) return ma === 401 || ma === 403;
		if (ma === 401) return true;
		if (ma !== 403) return false;
		return !!(than && than.exc_type === _EXC_DANH_TINH);
	}

	/** Bản đóng gói này trỏ vào máy chủ KHÁC địa chỉ phát hành → dải "BẢN THỬ".
	 * `scripts/pda/dong-goi.sh` sinh `window.KHO_BAN_THU = true` khi `may_chu`
	 * khác `may_chu_phat_hanh` trong `scripts/pda/cau-hinh-may-chu.json`. Trên web
	 * biến này không tồn tại → không hiện gì. */
	ban_thu() {
		return window.KHO_BAN_THU === true;
	}

	/** Chèn dải "BẢN THỬ" vào ĐẦU `$noi`. MỘT CHỖ DUY NHẤT dựng dải này để màn thẻ
	 * và màn menu không bao giờ nói hai câu khác nhau.
	 *
	 * VÌ SAO CẦN DẢI MÀU CHỨ KHÔNG CHỈ DÒNG "Máy chủ:": thủ kho sẽ không đối chiếu
	 * `192.168.61.129:8003` với một URL ngrok họ chưa từng nhớ. Một dải màu nổi thì
	 * không cần đọc chữ cũng thấy, và nó TỰ TẮT ở bản phát hành thật (hai địa chỉ
	 * bằng nhau → script không sinh biến).
	 *
	 * Chèn vào thân MÀN chứ không vào khung chung (`.kho-dau`): khung chung sẽ kéo
	 * dải này lên cả bốn màn nghiệp vụ, chiếm chỗ trên màn 4 inch đúng lúc thủ kho
	 * đang quét. Hai màn ĐỨNG YÊN (thẻ, menu) là đủ để nhìn thấy trước khi làm việc. */
	ve_dai_ban_thu($noi) {
		if (!this.ban_thu()) return;
		const chu = frappe.utils.escape_html(__("BẢN THỬ — KHÔNG phải máy chủ thật"));
		$noi.prepend(`<div class="kho-ban-thu">${chu}</div>`);
	}

	// ========================================================================
	// TASK 6 — LỐI ẨN KHAI ĐỊA CHỈ MÁY CHỦ (spec §9)
	// ========================================================================
	//
	// VÌ SAO CÓ LỐI NÀY: địa chỉ máy chủ được nướng vào từng bản cài lúc đóng gói
	// (`cau-hinh.js`). Hôm nay đường vào kho là một đường hầm ngrok chạy trên MỘT
	// máy; hầm rớt là địa chỉ cũ chết, và nó chết cho MỌI máy quét CÙNG MỘT LÚC.
	// Không có lối này thì cách duy nhất cứu là dựng APK mới rồi đi cài lại từng
	// chiếc — giữa ca, với cả kho đứng chờ.
	//
	// VÌ SAO GIẤU: đây KHÔNG phải một thiết lập của thủ kho. Một ô nhập địa chỉ
	// máy chủ nằm trong luồng thường là một đường để gõ nhầm vào site thử rồi ghi
	// dữ liệu thật vào đó — đúng rủi ro mà dải "BẢN THỬ" sinh ra để chặn. Bấm giữ
	// ba giây trên logo thì không ai chạm nhầm, mà người biết việc vẫn mở được.

	/** Địa chỉ do lối ẩn khai, hoặc chuỗi rỗng. Để màn hình nói được "đang dùng
	 * địa chỉ gõ tay hay địa chỉ đóng gói" — hai thứ đó phải phân biệt được. */
	may_chu_ghi_de() {
		return this._may_chu_ghi_de || "";
	}

	/** Nạp địa chỉ lối ẩn đã cất. CHỈ TRONG APP, cố ý.
	 *
	 * Trên web `goc()` phải trả chuỗi rỗng (đường tương đối — xem `goc()`), và một
	 * giá trị sót trong `localStorage` của trình duyệt sẽ biến trang `/kho` thành
	 * một trang gọi chéo nguồn: ràng buộc của cả đợt là bản web KHÔNG đổi hành vi.
	 *
	 * KIỂM LẠI LÚC NẠP, không chỉ lúc ghi: giá trị nằm trong `localStorage` — một
	 * thứ sửa tay được bằng trình gỡ lỗi, và (đáng kể hơn) một thứ SỐNG SÓT qua
	 * nâng cấp APK. Bản sau siết luật thì bản cũ đã ghi vẫn phải bị luật mới xét. */
	_nap_may_chu_ghi_de() {
		if (!this._la_app()) return;
		const luu = _doc_ben(_O_MAY_CHU);
		this._may_chu_ghi_de = luu && !this.loi_dia_chi_may_chu(luu) ? this.chuan_hoa_dia_chi(luu) : "";
	}

	/** Cắt khoảng trắng và dấu `/` ở đuôi. Người đi cứu máy DÁN địa chỉ từ cửa sổ
	 * ngrok, và bản dán ấy thường kèm một dấu `/` — cùng lý do `goc()` chuẩn hoá. */
	chuan_hoa_dia_chi(dia_chi) {
		return String(dia_chi || "").trim().replace(/\/+$/, "");
	}

	/** Câu lỗi tiếng Việt nếu địa chỉ không dùng được, hoặc chuỗi rỗng nếu dùng được.
	 *
	 * BA LUẬT, mỗi luật chặn một ca đã biết:
	 *
	 * 1. Phải là một URL phân tích được và có `http:`/`https:` — dán thiếu lược đồ
	 *    ("kho.ngrok.app") cho ra một `goc()` mà `fetch` giải thành đường tương đối
	 *    trên `file://`, tức app im lặng gọi vào chính cái vỏ.
	 * 2. KHÔNG có đường dẫn/tham số — `goc()` được nối thẳng với `/api/method/...`,
	 *    nên "https://x.ngrok.app/kho" sinh ra `.../kho/api/method/...` và mọi lời
	 *    gọi 404. Đây là lỗi gõ dễ mắc nhất khi dán từ thanh địa chỉ trình duyệt.
	 * 3. `http://` CHỈ cho các host trong `_HOST_HTTP_CHO_PHEP`. Xem khối chú thích
	 *    ở hằng số đó: luật này là của tầng Android, không phải của ta, và nó chặn
	 *    trước khi mã của app chạy — từ chối ở đây là cách duy nhất nói được vì sao. */
	loi_dia_chi_may_chu(dia_chi) {
		const chu = this.chuan_hoa_dia_chi(dia_chi);
		if (!chu) return __("Chưa nhập địa chỉ.");
		let u;
		try {
			u = new URL(chu);
		} catch (e) {
			return __("Địa chỉ không hợp lệ. Phải có dạng https://… hoặc http://…");
		}
		if (u.protocol !== "https:" && u.protocol !== "http:") {
			return __("Địa chỉ phải bắt đầu bằng https:// hoặc http://");
		}
		if (u.pathname !== "/" || u.search || u.hash) {
			return __("Chỉ nhập tới tên miền và cổng, bỏ phần sau dấu / (ví dụ https://abc.ngrok-free.app)");
		}
		if (u.protocol === "http:" && _HOST_HTTP_CHO_PHEP.indexOf(u.hostname) === -1) {
			return __(
				"Android chặn http:// tới {0}. Dùng địa chỉ https://, hoặc báo kỹ thuật dựng bản cài mới.",
				[u.hostname]
			);
		}
		return "";
	}

	/** Ghi địa chỉ lối ẩn. Trả câu lỗi (chuỗi rỗng = đã ghi).
	 *
	 * GHI XUỐNG KHO LƯU rồi mới đặt vào bộ nhớ: nếu kho lưu bị chặn (`_ghi_ben`
	 * nuốt lỗi) thì lần mở app sau địa chỉ biến mất, và ta muốn ca đó lộ ra ngay ở
	 * lượt kiểm dưới đây chứ không phải sau khi người đi cứu máy đã bỏ đi. */
	dat_may_chu(dia_chi) {
		const loi = this.loi_dia_chi_may_chu(dia_chi);
		if (loi) return loi;
		const chu = this.chuan_hoa_dia_chi(dia_chi);
		_ghi_ben(_O_MAY_CHU, chu);
		if (_doc_ben(_O_MAY_CHU) !== chu) {
			return __("Máy không cho lưu địa chỉ. Địa chỉ sẽ mất khi đóng app.");
		}
		this._may_chu_ghi_de = chu;
		return "";
	}

	/** Bỏ địa chỉ gõ tay, quay về địa chỉ đóng gói trong `cau-hinh.js`.
	 *
	 * CẦN CÓ ĐƯỜNG LÙI: gõ nhầm một địa chỉ chết rồi đóng app thì lượt mở sau vẫn
	 * nạp đúng địa chỉ chết ấy — không có nút này, chiếc máy chỉ còn cách gỡ cài
	 * đặt. Lối ẩn vẫn mở được (nó không cần mạng), nên đường lùi luôn với tới. */
	xoa_may_chu() {
		_xoa_ben(_O_MAY_CHU);
		this._may_chu_ghi_de = "";
	}

	// ========================================================================
	// TASK 6 — NHẮC CÓ BẢN CÀI MỚI (spec §10)
	// ========================================================================
	//
	// KHÔNG TỰ TẢI, KHÔNG TỰ CÀI, cố ý: Android không cho một app tự thay chính
	// nó mà không có người bấm đồng ý, và một lượt tải 30 MB tự khởi động giữa ca
	// trên wifi kho là đúng thứ làm màn quét đứng hình. App chỉ NÓI và mở trang
	// tải; người bấm là người quyết.

	/** Phiên bản của chính bản cài này (`window.KHO_BAN_APP`, do
	 * `scripts/pda/dong-goi.sh` sinh từ `versionName` trong `build.gradle`).
	 * Rỗng trên web và trên một bản đóng gói cũ — và rỗng nghĩa là KHÔNG NHẮC. */
	ban_app() {
		return window.KHO_BAN_APP || "";
	}

	/** So hai chuỗi phiên bản kiểu "1.2.10". Trả >0 nếu `a` mới hơn `b`.
	 *
	 * SO TỪNG ĐOẠN BẰNG SỐ, không so chuỗi: `"1.10" > "1.9"` là SAI theo thứ tự
	 * chữ cái (`"1" < "9"`), và đó chính là lượt nâng cấp thứ mười — lúc dải nhắc
	 * lặng lẽ thôi hiện mà không ai để ý. Đoạn thiếu coi như 0 ("1.2" == "1.2.0"). */
	_so_sanh_ban(a, b) {
		const pa = String(a).split(".");
		const pb = String(b).split(".");
		for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
			const x = parseInt(pa[i], 10) || 0;
			const y = parseInt(pb[i], 10) || 0;
			if (x !== y) return x - y;
		}
		return 0;
	}

	/** Phiên bản rút từ TÊN FILE bản cài trên máy chủ, hoặc rỗng nếu không rút được.
	 *
	 * Khuôn tên do `build.gradle` đặt: `miyano-pda-<phiên bản>-release.apk`
	 * (`outputFileName`). Máy chủ KHÔNG có ô "phiên bản" nào khác —
	 * `cai_app.ban_cai_moi_nhat` trả về một bản ghi `File`.
	 *
	 * KHÔNG RÚT ĐƯỢC THÌ KHÔNG NHẮC (trả rỗng): ai đó tải lên một file tên lạ sẽ
	 * làm dải nhắc bật vĩnh viễn trên mọi máy nếu ta đoán bừa là "mới hơn", và một
	 * dải nhắc không bao giờ tắt dạy thủ kho bỏ qua mọi dải nhắc về sau.
	 *
	 * BA RÀNG BUỘC, cả ba đều có số đo đứng sau, không phải phòng xa:
	 *
	 * 1. NEO VÀO TIỀN TỐ `miyano-pda-`. Không neo thì bất cứ cụm số nào trong tên
	 *    cũng thành "phiên bản".
	 * 2. PHẢI CÓ DẤU CHẤM, ít nhất hai đoạn. Bản cài đang nằm trên máy chủ thử tên
	 *    là `miyano-pda-1.0-kho-2026-09-24.apk` (đo bằng curl 25/09/2026) — người
	 *    phát hành có thói quen dán NGÀY vào tên file. Chỉ cần một lần đảo thứ tự
	 *    (`miyano-pda-2026-09-24-ban-thang-9.apk`) là phép neo-tiền-tố đọc ra
	 *    "2026", so 2026 > 1.0, và MỌI máy hiện dải nhắc vĩnh viễn.
	 * 3. ĐÚNG HAI ĐOẠN, mỗi đoạn tối đa 3 CHỮ SỐ, và ngay sau đó phải là `-`, `_`,
	 *    `.apk`, hoặc hết chuỗi. Đây là vòng sửa cuối (soát tổng, T6-1): lập luận
	 *    ngầm của vế 2 — *"ngày tháng không mang dấu chấm"* — **SAI VỚI THỰC TẾ
	 *    VN**. Người soát chạy hàm thật trên 14 cách đặt tên và tìm ra hai ca lọt:
	 *        `miyano-pda-2026.09.24.apk`         → "2026.09.24" > 1.0 → nhắc vĩnh viễn
	 *        `miyano-pda-25.09.2026-ban-moi.apk` → "25.09.2026" > 1.0 → nhắc vĩnh viễn
	 *    và tôi tìm thêm ca thứ ba cùng họ: `miyano-pda-24.09.26.apk` (dd.mm.yy).
	 *
	 *    KHÔNG có cách nào phân biệt `24.09.26` với một số hiệu ba đoạn bằng HÌNH
	 *    DẠNG. Nên ràng buộc là ĐÚNG HAI ĐOẠN — đúng thứ `build.gradle` sinh ra, và
	 *    `scripts/pda/dong-goi.sh` TỪ CHỐI DỰNG một `versionName` khác khuôn đó, nên
	 *    một bản cài ba đoạn không thể ra đời từ đường phát hành chính thức. Phần
	 *    "ngay sau đó phải là `-`/`_`/`.apk`/hết" là phần bắt buộc: thiếu nó thì
	 *    `25.09.2026` vẫn khớp một phần thành `25.09`, và `1.0.apk` (tên hợp lệ,
	 *    không có đuôi `-release`) lại bị từ chối oan.
	 *
	 * Tên lệch khuôn cho ra chuỗi rỗng, tức IM — hỏng theo hướng an toàn. App cố ý
	 * KHÔNG đoán bừa; việc NÓI CHO NGƯỜI PHÁT HÀNH BIẾT họ đặt tên sai là của MÁY
	 * CHỦ, nơi có người đang nhìn màn hình: `cai_app.py` chặn ngay lúc tải lên, và
	 * `ban_cai_moi_nhat` trả `ly_do` kèm một dòng `log_error`. */
	_ban_tu_ten_tep(ten) {
		const khop = /miyano-pda-(\d{1,3}\.\d{1,3})(?=[-_]|\.apk|$)/i.exec(String(ten || ""));
		return khop ? khop[1] : "";
	}

	/** Bản cài trên máy chủ có MỚI HƠN bản đang chạy không. Trả phiên bản mới
	 * (chuỗi) hoặc rỗng. Rỗng ở mọi ca không chắc chắn — xem `_ban_tu_ten_tep`. */
	ban_moi_hon(ban_may_chu) {
		const cua_toi = this.ban_app();
		if (!cua_toi || !ban_may_chu) return "";
		const cua_may_chu = this._ban_tu_ten_tep(ban_may_chu.ten);
		if (!cua_may_chu) return "";
		return this._so_sanh_ban(cua_may_chu, cua_toi) > 0 ? cua_may_chu : "";
	}

	/** Hỏi máy chủ bản cài mới nhất. MỘT LẦN mỗi lượt mở app (xem `_hen_ban_cai`).
	 *
	 * KHÔNG BAO GIỜ TỪ CHỐI LỜI HỨA: mất mạng hay máy chủ hỏng riêng đường này
	 * KHÔNG được biến thành một dải báo đỏ trên màn menu — thủ kho chẳng làm gì
	 * được với nó, và một `unhandledrejection` ở đây là đúng thứ cổng đóng gói bắt.
	 * Hỏng thì trả `null` = "không biết" = không nhắc. */
	hoi_ban_cai_moi() {
		if (!this._la_app()) return Promise.resolve(null);
		if (!this._hen_ban_cai) {
			// NHỚ MỘT CÂU TRẢ LỜI, QUÊN MỘT LƯỢT HỎI HỎNG — và phân biệt hai thứ đó
			// bằng `.catch`, KHÔNG bằng "giá trị có rỗng không".
			//
			// Vế QUÊN: ghi nhớ một lượt HỎNG là khoá cơ chế nhắc suốt đời chiếc
			// WebView đó — mở app ở góc kho mất sóng là máy không bao giờ nhắc nữa,
			// kể cả khi đã ra chỗ có wifi, mà Task 5 đo được rằng một WebView ở đây
			// sống qua cả nửa đêm không tải lại. Đúng hình dạng T5-1.
			//
			// Vế NHỚ: máy chủ trả `null` là một CÂU TRẢ LỜI THẬT ("chưa ai tải bản
			// cài nào lên"), không phải một lượt hỏi hỏng. Bản đầu của vòng sửa này
			// quên cả ca đó, và hậu quả lộ ra ngay ở cổng: mỗi lượt vẽ menu lại bắn
			// một lời gọi mới, mãi mãi, trên mọi site chưa từng phát hành bản nào.
			this._hen_ban_cai = this.goi(
				"erpnext.warehouse_operations.vitri.cai_app.ban_cai_moi_nhat"
			).catch(() => {
				this._hen_ban_cai = null;
				return null;
			});
		}
		return this._hen_ban_cai;
	}

	/** Chèn dải nhắc bản mới vào ĐẦU `$noi`, kèm nút mở trang tải. Không có bản
	 * mới thì không chèn gì.
	 *
	 * NÚT LÀ MỘT THẺ `<a target="_blank">`, KHÔNG phải `location.href = …`: trong
	 * APK, một địa chỉ ngoài `index.html` được `BridgeWebViewClient
	 * .shouldOverrideUrlLoading` giao cho `Bridge.launchIntent()` — trình duyệt hệ
	 * thống mở, app đứng nguyên. Nếu vì lý do nào đó lượt giao ấy KHÔNG xảy ra thì
	 * `location.href` sẽ kéo chính WebView rời khỏi `index.html` và app coi như
	 * mất; một thẻ neo hỏng thì cùng lắm là không mở được gì. (Đường `launchIntent`
	 * CHƯA ĐO ĐƯỢC trên máy thật — không có thiết bị; đã ghi vào bảng kiểm tay.) */
	ve_dai_ban_moi($noi, ban) {
		const moi = this.ban_moi_hon(ban);
		if (!moi) return;
		// CHỈ MỘT DẢI, dù được gọi mấy lần. Lời gọi hỏi bản cài là BẤT ĐỒNG BỘ và
		// `this.$than` là MỘT nút DOM dùng lại (`_ve()` gọi `.empty()` chứ không
		// dựng nút mới), nên `.then()` của lượt vẽ menu TRƯỚC có thể bay về sau khi
		// menu đã được vẽ lại — và nó tìm thấy `.kho-menu` MỚI rồi chèn thêm một dải
		// y hệt. Đường đi có thật: mở app → menu (lời gọi còn bay) → chạm Tra cứu →
		// quay lại menu → lời hứa về, hai `.then()` cùng chèn.
		if ($noi.find(".kho-ban-moi").length) return;
		const e = frappe.utils.escape_html;
		const chu = e(__("Đã có bản cài mới {0} (máy đang dùng {1}).", [moi, this.ban_app()]));
		const nhan = e(__("Mở trang tải"));
		const dia_chi = e(`${this.goc()}/tai-app`);
		$noi.prepend(
			`<div class="kho-ban-moi"><span class="kho-ban-moi-chu">${chu}</span>` +
				`<a class="kho-ban-moi-nut" href="${dia_chi}" target="_blank" rel="noopener">${nhan}</a></div>`
		);
	}

	// ========================================================================
	// TASK 5 — GIỜ MÁY CHỦ (spec §8)
	// ========================================================================
	//
	// Máy Android trong kho KHÔNG đảm bảo đúng giờ (không SIM, không NTP, pin yếu
	// là trôi) — mà một đợt trước, lớp luồng lẳng lặng đổi từ giờ SITE sang giờ
	// MÁY TRẠM, làm phán quyết HẾT HẠN của một lô vật tư y tế đổi nghĩa mà không
	// ai biết cho tới khi thủ kho lấy nhầm lô. Bốn hàm dưới đây đồng bộ đồng hồ
	// MỘT LẦN lúc mở app rồi cất kết quả ở ĐÚNG MỘT CHỖ (`this._gio_may_chu`) —
	// `man_tra_cuu.js` tiêm `ngay_may_chu()`/`gio_may_chu()` vào `tao({ngay, gio})`
	// của lớp luồng, KHÔNG BAO GIỜ để lớp luồng tự đọc đồng hồ máy trong app.

	/** Đồng bộ ngày/giờ với máy chủ. Gọi từ `khoi_dong()` (lúc mở app) VÀ từ đầu
	 * `goi()` (tự chữa — xem lý do ở khối dưới); tự bảo vệ khỏi gọi chồng và gọi
	 * lại vô ích nên MỌI nơi gọi hàm này không cần tự kiểm điều kiện gì cả.
	 *
	 * BA QUYẾT ĐỊNH THIẾT KẾ, mỗi cái né một bẫy cụ thể:
	 *
	 * 1. `fetch()` THẲNG, KHÔNG QUA `goi()`, và KHÔNG GẮN `Authorization`/`X-Ma-May`.
	 *    `_nap_khoa_da_cat()` đã ghi rõ quyết định của Task 4: "KHÔNG hỏi máy chủ
	 *    lúc khởi động, cố ý... đường thu hồi đi qua ĐÚNG MỘT CHỖ, không hai." Gọi
	 *    qua `goi()` với khoá đính kèm sẽ mở một đường THỨ HAI: một khoá vừa bị
	 *    trưởng kho thu hồi sẽ khiến LƯỢT MỞ APP (không phải lượt quét đầu tiên)
	 *    ăn 401 và bật `xoa_khoa()`/`di("the")` — đúng lúc app còn chưa vẽ xong màn
	 *    đầu. Hàm này vì thế KHÔNG mang danh tính nào cả: `gio_may_chu()` phía máy
	 *    chủ cũng `allow_guest=True` đúng để phục vụ ca này.
	 * 2. KHÔNG đọc header HTTP `Date` để suy `ngay`/`gio`: header đó luôn là giờ
	 *    UTC, và múi giờ VN lệch UTC+7 — suy ngày từ đó là dựng lại đúng cái bẫy
	 *    `toISOString()` mà `_ngay_may_tram()` (`luong/tra_cuu.js`) đã né, chỉ đổi
	 *    hướng lệch. Máy chủ tự trả THẲNG hai chuỗi `ngay`/`gio` đã quy múi giờ
	 *    site (xem docstring `the_pda.py::gio_may_chu`) — không có phép quy đổi
	 *    nào ở phía JS để mà sai. Cũng KHÔNG đọc `res.headers` vì một lý do khác:
	 *    Task 2B đo được cầu HTTP native chỉ chuyển tiếp ĐÚNG BA THỨ đáng tin
	 *    (`res.ok`, `res.status`, `res.json()`) — `res.headers` là một trong
	 *    những thứ CHƯA ĐO được qua cầu đó, nên mọi thứ cần thiết phải nằm trong
	 *    THÂN JSON, không nằm ở header.
	 * 3. TỰ CHỮA (self-heal) VÀ TỰ LÀM MỚI (refresh), KHÔNG CHỈ "một lần" theo
	 *    nghĩa đen: wifi kho chập chờn là một điều kiện THƯỜNG TRỰC (xem chú
	 *    thích `goi()`), nên nếu lượt gọi lúc `khoi_dong()` hỏng thì app không
	 *    được kẹt ở giờ máy trạm suốt cả vòng đời (khoá máy không bao giờ hết
	 *    hạn — có thể là NHIỀU NGÀY không mở lại app, và MỘT WebView đã mở có
	 *    thể sống qua NỬA ĐÊM mà không ai tải lại trang). Thiếu vế "làm mới" thì
	 *    một app mở lúc 23:00 và còn sống lúc 00:30 vẫn trả `ngay_may_chu() =
	 *    "hôm qua"` — ĐÚNG CÙNG LỚP LỖI mà cả Task này sinh ra để vá, chỉ đổi
	 *    tên từ "đồng hồ máy sai" sang "bộ nhớ đệm cũ", và NGUY HIỂM HƠN: dải
	 *    cảnh báo lệch giờ sẽ KHÔNG hiện (độ lệch đo lúc đồng bộ là 0, giờ MÁY
	 *    CHỦ đúng, chỉ là bộ nhớ đệm phía app đã cũ) — hỏng ÂM THẦM giống hệt
	 *    lỗi gốc. `goi()` gọi lại hàm này ở đầu MỌI lời gọi nghiệp vụ; hàm tự
	 *    thoát ngay nếu đã có kết quả CÒN MỚI (`_NGUONG_LAM_MOI_GIO_MS`) hoặc
	 *    đang có một lượt đang bay, nên chi phí của việc gọi "thừa" này là một
	 *    phép so sánh, không phải một lời gọi mạng thừa ở đường nóng.
	 *
	 *    DÙNG ĐỒNG HỒ THIẾT BỊ ĐỂ ĐO "BAO LÂU RỒI", KHÔNG PHẢI ĐỂ SUY NGÀY — hai
	 *    việc khác hẳn nhau. Một ĐỘ LỆCH giữa hai mốc `Date.now()` của CÙNG một
	 *    đồng hồ (lúc đồng bộ và lúc kiểm lại) triệt tiêu mọi LỆCH HẰNG SỐ (một
	 *    đồng hồ sai cố định 25 giờ vẫn đếm đúng "đã trôi qua 45 phút") — chỉ sai
	 *    nếu đồng hồ đổi TỐC ĐỘ giữa hai lần đọc, một sai số không đáng kể trong
	 *    45 phút. Đây KHÔNG phải một ngoại lệ của "không đọc đồng hồ máy cho
	 *    phán quyết": phán quyết hết hạn vẫn không bao giờ chạm `Date.now()` của
	 *    thiết bị, chỉ ĐỘ CŨ của bộ nhớ đệm mới chạm.
	 *
	 * `window.KHO_BO_QUA_DONG_BO_GIO` — CỜ CHỈ DÀNH CHO CÁC CỔNG PLAYWRIGHT
	 * (`kiem_goi_mang.js`, `kiem_ban_dong_goi.js`): hai cổng đó dựng một máy chủ
	 * giả biết ĐÚNG một tập đường dẫn đã liệt kê sẵn — một lời gọi thật tới
	 * `gio_may_chu` (đường dẫn không có trong bảng đó) sẽ làm khẳng định "máy chủ
	 * giả nhận đường dẫn LẠ" đỏ oan, vì lý do KHÔNG LIÊN QUAN tới thứ cổng đó đang
	 * đo. `index.html`/`cau-hinh.js` của bản đóng gói THẬT không bao giờ khai cờ
	 * này — nó chỉ tồn tại trong các trang giả mà hai cổng đó tự dựng. */
	/** CÒN MỚI = có dữ liệu VÀ chưa quá `_NGUONG_LAM_MOI_GIO_MS` kể từ lượt đồng bộ
	 * trước. VÒNG SỬA 1 (soát xét, T5-2 — MỨC VỪA–NẶNG, lỗi HÀNH VI đo được):
	 * bản đầu chỉ dùng điều kiện này để quyết định có ĐI GỌI LẠI hay không, còn
	 * `ngay_may_chu()`/`gio_may_chu()` thì trả đệm VÔ ĐIỀU KIỆN — tạo một cuộc
	 * đua: `goi()` gọi `_dong_bo_gio_may_chu()` KHÔNG `await` (cố ý, xem điểm 3 ở
	 * dưới — không được chặn màn hình chờ mạng), nên NẾU lượt quét đi trước lượt
	 * làm mới về tới, `trang_thai_han()` đọc trúng đệm CŨ và ra một PHÁN QUYẾT SAI
	 * ("Còn 1 ngày" cho một lô đã HẾT HẠN HÔM NAY, ngay sau khi ngày lật sang mới
	 * mà lượt làm mới cho ca trước còn chưa kịp về) — người soát dựng lại được
	 * bằng cách ép phản hồi chậm 1,2 giây, một độ trễ KHÔNG lạ trên wifi kho.
	 * Sửa ĐÚNG DOCTRINE của chính hàm này (fail-safe-to-blank): giờ đây
	 * `ngay_may_chu()`/`gio_may_chu()` TỰ GỌI hàm này và trả `null` khi đệm đã CŨ
	 * — ẩn chip còn hơn một phán quyết y tế phụ thuộc vào việc hai lời gọi mạng
	 * song song cái nào về trước. */
	_gio_may_chu_con_moi() {
		return !!(this._gio_may_chu && Date.now() - this._gio_may_chu.luc_dong_bo_ms < _NGUONG_LAM_MOI_GIO_MS);
	}

	/** Ghi lại MỐC ĐẦU TIÊN của một đợt "không có giờ máy chủ dùng được" (mới toanh
	 * hoặc vừa hoá cũ), và xoá mốc đó ngay khi có dữ liệu mới — dùng bởi
	 * `ve_dai_thieu_gio()` để phân biệt "vài trăm mili-giây đầu lúc mở app" (bình
	 * thường, không đáng báo) với "kẹt cả phiên vì lượt đồng bộ cứ hỏng" (đáng báo
	 * — điểm 4 của soát xét vòng 1: "im lặng phải nhìn thấy được"). Gọi Ở MỌI nơi
	 * đọc giờ máy chủ (hai getter dưới đây) để mốc này luôn phản ánh đúng hiện tại,
	 * không phụ thuộc màn nào vừa được vẽ. */
	_theo_doi_thieu_gio() {
		if (this._gio_may_chu_con_moi()) {
			this._luc_dau_tien_thieu_gio = null;
		} else if (this._luc_dau_tien_thieu_gio == null) {
			this._luc_dau_tien_thieu_gio = Date.now();
		}
	}

	_dong_bo_gio_may_chu() {
		if (!this._la_app() || window.KHO_BO_QUA_DONG_BO_GIO) return;
		if (this._dang_dong_bo_gio) return;
		if (this._gio_may_chu_con_moi()) return;
		this._dang_dong_bo_gio = true;
		// VÒNG SỬA 1 (soát xét, T5-1 — MỨC VỪA): `fetch()` KHÔNG có timeout trước
		// đây — một lượt TREO (máy chủ nhận kết nối rồi im, khác hẳn ca "từ chối
		// ngay" mà `.catch()` vốn đã lo) không bao giờ settle, nên `.finally()`
		// không bao giờ chạy, `_dang_dong_bo_gio` kẹt `true` VĨNH VIỄN — không chip,
		// không dải cảnh báo, và KHÔNG một lượt thử lại nào nữa (đo được:
		// `dem_goi_gio` đứng yên ở 1). Vá bằng ĐUA VỚI MỘT ĐỒNG HỒ ĐẾM GIỜ
		// (`Promise.race`), KHÔNG bằng `AbortController`/`signal`: cầu HTTP native
		// của Capacitor (`native-bridge.js`) vá `window.fetch` bằng bản của riêng
		// nó và KHÔNG đọc thuộc tính `signal` của `options` — một `AbortController`
		// sẽ là chỗ dựa CHỈ ĐÚNG trên trình duyệt thường (Playwright, hoặc bản web),
		// TRỞ THÀNH VÔ TÁC DỤNG đúng trên chính con đường APK thật đi qua. `Promise.race`
		// không cần cầu bên dưới hợp tác gì cả — nó chỉ quyết định TA có còn CHỜ
		// tiếp hay không, và ta luôn có thể ngừng chờ.
		//
		// `loi_hen_fetch` KHÔNG BAO GIỜ bị TỪ CHỐI (luôn `.catch()` về `null`) — nếu
		// để nó có thể reject rồi thua cuộc đua, phần còn lại của promise đó (bên
		// thua) vẫn tiếp tục chạy nền và một khi settle bằng reject mà không ai
		// gắn `.catch()` nữa thì trình duyệt báo `unhandledrejection` — đúng thứ
		// `test_giao_dien`/cổng Playwright của kho đang lắng nghe và sẽ đỏ vì một
		// lý do KHÔNG liên quan tới thứ đang đo.
		const loi_hen_fetch = fetch(`${this.goc()}/api/method/${_DUONG_GIO_MAY_CHU}`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: "{}",
		})
			.then((res) => (res.ok ? res.json() : null))
			.catch(() => null);
		const het_gio = new Promise((giai) => setTimeout(() => giai(null), _THOI_GIAN_CHO_DONG_BO_MS));
		Promise.race([loi_hen_fetch, het_gio])
			.then((than) => {
				const kq = than && than.message;
				if (!kq || !kq.ngay || !kq.gio) return;
				// Độ lệch tính bằng SỐ NGUYÊN mili-giây giữa "máy chủ nói lúc nó xử lý
				// xong" và "máy trạm nói lúc nó đọc xong phản hồi" — bỏ qua độ trễ
				// mạng một chiều (vài chục mili-giây trên wifi kho, không đáng kể so
				// với ngưỡng CẢNH BÁO là 10 PHÚT).
				this._gio_may_chu = {
					ngay: kq.ngay,
					gio: kq.gio,
					lech_phut: Math.round(Math.abs(Date.now() - Number(kq.moc_epoch_ms || Date.now())) / 60000),
					// Mốc THIẾT BỊ lúc lượt đồng bộ NÀY hoàn tất — CHỈ dùng để đo "đã bao
					// lâu rồi" ở lượt gọi kế tiếp (một phép TRỪ hai mốc của CÙNG một đồng
					// hồ, xem điểm 3), KHÔNG dùng để suy ngày/giờ hiển thị.
					luc_dong_bo_ms: Date.now(),
				};
				// Mất mạng/CORS/máy chủ lạ/quá giờ chờ — `than` rơi về `null` ở trên,
				// nhánh này không chạy gì cả. KHÔNG xoá `this._gio_may_chu` cũ ở đây dù
				// lượt này hỏng: một lượt làm mới hỏng giữa ca không được biến một giá
				// trị VỪA CŨ (nhưng qua `_gio_may_chu_con_moi()` đã tự ẩn nếu thật sự
				// cũ) thành mất luôn khả năng thử lại — `_dang_dong_bo_gio` vẫn được nhả
				// ở `finally` bên dưới nên lượt `goi()` kế tiếp tự thử lại.
			})
			.finally(() => {
				this._dang_dong_bo_gio = false;
			});
	}

	/** Ngày (`YYYY-MM-DD`) do MÁY CHỦ báo — `null` nếu chưa đồng bộ xong HOẶC đệm
	 * đã CŨ (xem `_gio_may_chu_con_moi()`, vá T5-2). Đây là hàm TIÊM vào
	 * `tao({ngay: () => KhoApp.ngay_may_chu()})` của `luong/tra_cuu.js` (chỉ trong
	 * app — xem `man_tra_cuu.js`); lớp luồng đọc `null` là "chưa biết" và tự ẩn
	 * chip hạn dùng, KHÔNG rơi về đồng hồ máy trạm — mặc định `_ngay_may_tram()`
	 * của lớp luồng chỉ áp dụng khi KHÔNG hề tiêm gì (đúng ca web `/kho`), còn ở
	 * đây ta CÓ tiêm một hàm, chỉ là hàm đó chưa/không còn có dữ liệu ĐÁNG TIN. */
	ngay_may_chu() {
		this._theo_doi_thieu_gio();
		return this._gio_may_chu_con_moi() ? this._gio_may_chu.ngay : null;
	}

	/** Giờ (`HH:MM:SS`) do MÁY CHỦ báo — cùng lẽ `ngay_may_chu()`. */
	gio_may_chu() {
		this._theo_doi_thieu_gio();
		return this._gio_may_chu_con_moi() ? this._gio_may_chu.gio : null;
	}

	/** Số phút lệch giữa đồng hồ máy Android và máy chủ — `null` nếu chưa đo được
	 * HOẶC đệm đã cũ. CỐ Ý gác bởi CÙNG điều kiện `_gio_may_chu_con_moi()`: một
	 * dải cảnh báo lệch giờ dựa trên số đo TỪ LẦN ĐỒNG BỘ CUỐI (có thể đã xảy ra
	 * quá lâu) sẽ nói dối đúng lúc bộ nhớ đệm đã hoá cũ — hai việc "cảnh báo lệch"
	 * và "phán quyết đúng" phải cùng đứng hoặc cùng đổ (nhận xét của người soát,
	 * vòng sửa 1: "dải báo và tính đúng là hai việc khác nhau" — ở đây làm cho
	 * chúng bám vào NHAU thay vì trôi khỏi nhau). */
	lech_phut_gio() {
		return this._gio_may_chu_con_moi() ? this._gio_may_chu.lech_phut : null;
	}

	/** Lệch có VƯỢT NGƯỠNG cảnh báo không (`_NGUONG_LECH_GIO_PHUT` phút). `false`
	 * khi chưa đồng bộ xong — KHÔNG báo oan trong lúc chưa có số đo. */
	lech_gio_qua_nguong() {
		return this._gio_may_chu_con_moi() && this._gio_may_chu.lech_phut > _NGUONG_LECH_GIO_PHUT;
	}

	/** Chèn dải cảnh báo lệch giờ vào ĐẦU `$noi` — CÙNG KHUÔN với `ve_dai_ban_thu()`
	 * (một chỗ dựng, hai màn ĐỨNG YÊN gọi: `man_the.js`/`man_menu.js`, xem lý do ở
	 * đó). CHỈ hiện trong APP: web `/kho` không tiêm giờ máy chủ (giữ nguyên hành
	 * vi cũ), nên `_gio_may_chu` luôn `null` ở đó và hàm này tự thoát — gọi tường
	 * minh `_la_app()` ở đây, không chỉ dựa vào `_gio_may_chu` rỗng, để đọc mã còn
	 * biết ngay đây là một chỉ báo CHỈ CỦA APP.
	 *
	 * KHÔNG CHẶN VIỆC — chỉ NÓI (brief Task 5, Bước 4): thủ kho vẫn làm việc bình
	 * thường, và phán quyết hết hạn ĐÃ đúng theo giờ máy chủ dù dải này có hiện
	 * hay không (xem `ngay_may_chu()`) — dải này chỉ để trưởng kho/IT biết máy cần
	 * chỉnh giờ, không phải một điều kiện cho phép làm việc. */
	ve_dai_lech_gio($noi) {
		if (!this._la_app() || !this.lech_gio_qua_nguong()) return;
		const chu = frappe.utils.escape_html(
			__("Giờ máy sai {0} phút so với hệ thống — báo kỹ thuật.", [this._gio_may_chu.lech_phut])
		);
		$noi.prepend(`<div class="kho-lech-gio">${chu}</div>`);
	}

	/** VÒNG SỬA 1 (soát xét, mục 4) — dải RIÊNG cho ca "chưa/không còn giờ máy chủ
	 * dùng được KÉO DÀI", khác hẳn `ve_dai_lech_gio()` (cần CÓ số đo mới hiện được).
	 * Hai dải này KHÔNG BAO GIỜ cùng hiện — `lech_gio_qua_nguong()` đòi
	 * `_gio_may_chu_con_moi()` đúng, còn dải này đòi hàm đó SAI kéo dài — loại trừ
	 * lẫn nhau theo đúng cấu trúc, không phải một quy ước phải nhớ giữ.
	 *
	 * VÌ SAO CẦN: thủ kho quen "chip đỏ = hết hạn"; KHÔNG CÓ CHIP đọc như "không có
	 * gì bất thường" — nếu lượt đồng bộ cứ hỏng (mạng chết lâu, hoặc một sự cố
	 * riêng của endpoint `gio_may_chu`), toàn app mất chip hạn dùng SUỐT MỘT PHIÊN
	 * mà không một dấu hiệu nào phân biệt nó với "lô này không quản lý hạn dùng"
	 * (ca `muc: "khong"` bình thường, không hsd). Ngắn dưới `_NGUONG_BAO_THIEU_GIO_MS`
	 * (đúng khung lúc mở app bình thường) thì KHÔNG hiện — tránh nhấp nháy vô ích. */
	ve_dai_thieu_gio($noi) {
		if (!this._la_app()) return;
		this._theo_doi_thieu_gio();
		if (this._luc_dau_tien_thieu_gio == null) return;
		if (Date.now() - this._luc_dau_tien_thieu_gio < _NGUONG_BAO_THIEU_GIO_MS) return;
		const chu = frappe.utils.escape_html(
			__("Chưa lấy được giờ hệ thống — tạm ẩn cảnh báo hạn dùng. Báo kỹ thuật nếu kéo dài.")
		);
		$noi.prepend(`<div class="kho-thieu-gio">${chu}</div>`);
	}

	/** Khoá máy cho `Authorization` — API CÔNG BỐ cho Task 3 (cấp khoá) và Task 4
	 * (cất/nạp khoá). Giữ trong bộ nhớ thôi: nơi CẤT khoá (và luật xoá khi thu hồi
	 * máy) là việc của Task 4, không phải của lớp gọi mạng.
	 *
	 * Giá trị được chuyển tiếp NGUYÊN VẸN: khuôn khoá của Frappe là
	 * `api_key:api_secret`, nhưng lớp này không tách, không kiểm, không đoán — Task
	 * 3 sở hữu khuôn đó. */
	dat_khoa(khoa) {
		this._khoa = khoa || "";
		// CẤT LUÔN XUỐNG MÁY, không đợi ai gọi thêm một hàm thứ hai: chiếc khoá này
		// chỉ được máy chủ trả về ĐÚNG MỘT LẦN (`cap_khoa_may` — `api_secret` sau đó
		// nằm mã hoá trong `__Auth`, không đường nào đọc lại). Một nhánh mã quên cất
		// nghĩa là thủ kho phải quét thẻ lại ở lần mở app kế tiếp và không ai hiểu vì
		// sao. Hai vế của `if` là MỘT sự thật: ô nhớ và kho cất luôn nói cùng một câu.
		if (this._khoa) _ghi_ben(_O_KHOA, this._khoa);
		else _xoa_ben(_O_KHOA);
	}

	/** Tên hiển thị của người đang cầm máy, cất cùng chỗ với khoá.
	 *
	 * KHÔNG MANG THẨM QUYỀN GÌ. Danh tính do chiếc KHOÁ quyết định, máy chủ tự đọc
	 * ra từ `Authorization`; dòng chữ này chỉ để thủ kho liếc màn menu là biết máy
	 * đang đứng tên ai. Sửa tay nó trong kho lưu không cho ai thêm một quyền nào. */
	dat_nguoi_dung(ten) {
		this.nguoi_dung = ten || "";
		_ghi_ben(_O_NGUOI_DUNG, this.nguoi_dung);
	}

	xoa_khoa() {
		this._khoa = "";
		// S2 (vòng sửa 1): đặt lại luôn TÊN trong bộ nhớ, không chỉ trong kho lưu. Bỏ
		// dòng này thì sau một lượt 401 màn menu (nếu có ai vẽ lại nó trước khi trang
		// tải lại) còn mang tên người vừa bị thu hồi — một dòng chữ nói sai về ai đang
		// cầm máy, đúng hạng lỗi mà dòng "Máy chủ:" đã phải sửa ở Task 2.
		this.nguoi_dung = "";
		_xoa_ben(_O_KHOA);
		_xoa_ben(_O_NGUOI_DUNG);
		// CỐ Ý KHÔNG XOÁ `_O_MA_MAY`. "Cất cùng chỗ với khoá" là cùng một KHO, không
		// phải cùng một VÒNG ĐỜI: `_ghi_thiet_bi` (the_pda.py) nhận diện máy theo
		// `ma_may` và upsert theo đúng khoá đó. Xoá mã máy mỗi lần thu hồi thì CHÍNH
		// chiếc máy ấy quét thẻ lại sẽ mang một mã mới → bảng `PDA Thiet Bi` mọc thêm
		// một dòng cho một chiếc máy, và bảng đó nói dối đúng cái điều nó sinh ra để
		// trả lời ("ai đang cầm máy nào"). Mã máy chỉ chết khi cả app bị xoá dữ liệu.
	}

	khoa() {
		return this._khoa || "";
	}

	/** MÃ MÁY — chiếc máy này tự khai mình là ai, đi kèm MỌI lời gọi mang khoá.
	 *
	 * Sinh MỘT LẦN rồi dùng mãi (xem `_sinh_ma_may` để biết vì sao tự sinh chứ không
	 * thêm gói lấy id của Android). Nói thẳng giới hạn, đúng như spec §7 đã khai: mã
	 * máy KHÔNG phải bí mật — ai bê được nguyên chiếc máy thì cũng có nó. Thứ nó chặn
	 * là chiếc khoá RÒ RA NGOÀI chiếc máy (bản sao lưu, ảnh chụp màn hình, nhật ký). */
	ma_may() {
		if (this._ma_may) return this._ma_may;
		let ma = _doc_ben(_O_MA_MAY);
		if (!ma) {
			ma = _sinh_ma_may();
			_ghi_ben(_O_MA_MAY, ma);
		}
		this._ma_may = ma;
		return ma;
	}

	/** Nạp lại khoá máy đã cất từ lần mở app trước. `true` nếu có khoá dùng được.
	 *
	 * KHÔNG hỏi máy chủ ở đây, cố ý: một lời gọi kiểm tra lúc khởi động làm app đứng
	 * chờ mạng trước khi vẽ được gì, và nó KHÔNG thêm gì — khoá bị thu hồi thì lời
	 * gọi NGHIỆP VỤ kế tiếp sẽ 401 và `goi()` xoá khoá, về màn thẻ. Đường thu hồi đi
	 * qua đúng một chỗ, không hai. */
	_nap_khoa_da_cat() {
		const khoa = _doc_ben(_O_KHOA);
		if (!khoa) return false;
		this._khoa = khoa;
		this.nguoi_dung = _doc_ben(_O_NGUOI_DUNG);
		return true;
	}

	khoi_dong(goc) {
		this.$goc = $(goc);
		// Đẩy từ máy chủ (index.py) — xem chú thích ở đó vì sao không đọc được
		// từ `frappe.session.user` trên trang website. `la_khach` cập nhật lại
		// ngay khi đăng nhập thành công (`man_the.js`) — nếu không, chốt chặn
		// khách trong `_theo_hash` bên dưới sẽ đứng chắn luôn cả lối vào "menu"
		// sau khi quét thẻ xong.
		this.la_khach = goc.dataset.la_khach === "1";
		this.nguoi_dung = goc.dataset.nguoi_dung || "";
		// TASK 4 — TRONG APP, `data-la_khach` CỦA VỎ KHÔNG PHẢI CÂU TRẢ LỜI CUỐI.
		// `pda_app/www/index.html` viết cứng `data-la_khach="1"` vì bản đóng gói không
		// có phiên nào để máy chủ tính hộ; giữ nguyên nó thì app LUÔN mở ra ở màn quét
		// thẻ, tức mục tiêu "chạm icon vào thẳng menu" không bao giờ đạt được dù khoá
		// máy nằm sẵn trong máy. Hằng số đó vẫn đúng ở vai trò MẶC ĐỊNH — chưa nhận
		// máy thì đúng là khách — nên chỗ này chỉ ghi đè khi thật sự có khoá đã cất.
		//
		// Trên web không đọc kho lưu: ở đó `la_khach` do `www/kho/index.py` tính từ
		// phiên thật, và đường đó không đổi một byte nào.
		if (this._la_app() && this._nap_khoa_da_cat()) this.la_khach = false;
		// TASK 6 — NẠP ĐỊA CHỈ LỐI ẨN TRƯỚC LỜI GỌI MẠNG ĐẦU TIÊN. Dòng ngay dưới
		// (`_dong_bo_gio_may_chu()`) là lời gọi đầu tiên của app và nó dựng địa chỉ
		// bằng `goc()`; nạp sau nó thì lượt đầu mỗi lần mở app vẫn đi tới máy chủ
		// CŨ — đúng cái máy chủ đã chết mà lối ẩn sinh ra để thoát khỏi.
		this._nap_may_chu_ghi_de();
		// TASK 5 — bắn đi NGAY, KHÔNG CHỜ (`_dong_bo_gio_may_chu()` không blocking):
		// một lượt gọi mạng lúc khởi động chặn cả màn hình vẽ là đúng cái bẫy
		// `_nap_khoa_da_cat()` đã né ở trên; hàm tự bảo vệ khỏi mọi môi trường không
		// cần nó (web, cổng Playwright — xem docstring của hàm).
		this._dong_bo_gio_may_chu();
		this._giu_bao = false;
		this.$goc.html(`
			<div class="kho-vo">
				<div class="kho-dau"></div>
				<div class="kho-bao"></div>
				<div class="kho-than"></div>
			</div>
		`);
		this.$dau = this.$goc.find(".kho-dau");
		this.$bao = this.$goc.find(".kho-bao");
		this.$than = this.$goc.find(".kho-than");
		$(window).on("hashchange", () => this._theo_hash());
		// Khách: ép hash về màn thẻ TRƯỚC lần vẽ đầu tiên bằng `replaceState`, KHÔNG
		// gán `location.hash =`. Gán trực tiếp rồi gọi `_theo_hash()` ngay khiến màn
		// thẻ bị vẽ HAI LẦN: `hashchange` là sự kiện BẤT ĐỒNG BỘ nên nổ ở lượt sau bất
		// kể lúc nào ta gắn listener, gọi `_theo_hash()` thêm một lần nữa — đo được:
		// một lần tải trang đã dựng thừa một `OQuet`, không màn nào rời để `roi()` dọn
		// nó (bài soát xét vòng 1, mục P5/P2). `replaceState` đổi `location.hash`
		// nhưng KHÔNG bắn `hashchange` (theo đặc tả History API), nên gọi `_theo_hash()`
		// ngay sau đó chỉ vẽ ĐÚNG MỘT LẦN.
		if (this.la_khach && location.hash !== "#/the") {
			history.replaceState ? history.replaceState(null, "", "#/the") : (location.hash = "#/the");
		}
		this._theo_hash();
	}

	_theo_hash() {
		const phan = (location.hash || "#/menu").replace(/^#\//, "").split("/");
		let ten = phan[0] || "menu";
		if (this.la_khach && ten !== "the") {
			// Chốt chặn khách: bấm Back của Android (hoặc gõ tay một hash khác) từ
			// màn thẻ có thể đổi `location.hash` sang bất cứ đâu — `hashchange` không
			// phân biệt nguồn gốc. Không chặn ở đây thì màn menu (tĩnh, không cần
			// đăng nhập để VẼ) hiện ra trọn vẹn cho khách; nếu Task 2–5 cho màn đó gọi
			// máy chủ ngay lúc mở, khách sẽ ăn 401/403 và rơi vào `goi()` — muộn hơn,
			// sau khi màn đã kịp vẽ ra một nhịp.
			//
			// Chốt chặn này phá bất biến "hash ↔ màn là một-một" theo chiều NGƯỢC với
			// `di()` ở dưới: với khách, `location.hash` có thể là `#/menu` (gõ tay, hoặc
			// Back) trong khi màn THẬT SỰ vẽ ra vẫn là `"the"` — đọc `location.hash` để
			// suy màn đang hiện là sai với khách. Dùng `this.man_hien_tai` (vo.js đã cập
			// nhật đúng), không dùng `location.hash`, để biết màn nào đang thật sự hiện.
			ten = "the";
		}
		this._ve(this.man[ten] ? ten : "menu", phan.slice(1));
	}

	/** BẤT BIẾN mà `_giu_bao` (và bất kỳ ai gọi `di()` rồi trông đợi một lượt `_ve()`
	 * chạy ngay sau) dựa vào: mỗi lần `di()` được gọi, `_ve()` chạy ĐÚNG MỘT LẦN sau
	 * đó — CÓ THỂ đồng bộ (hash không đổi giá trị, tự gọi thẳng `_theo_hash()` ở
	 * dưới) hoặc bất đồng bộ (hash đổi, `hashchange` gọi hộ) — nhưng luôn đúng một
	 * lần. Không có vế "hash không đổi thì tự vẽ" thì soát xét vòng 2 (N4) dựng
	 * được ca: `di("the")` gọi lúc hash ĐÃ SẴN LÀ `"#/the"` (ví dụ nội bộ đang nghĩ
	 * là màn khác) không bắn `hashchange`, không có `_ve()` nào chạy, `_giu_bao`
	 * kẹt `true` mãi — câu báo của lượt điều hướng ĐÓ dính sang tận lượt kế tiếp.
	 * Task 2–5 thêm màn cứ tin vào bất biến này: gọi `di()` xong, `_ve()` LUÔN chạy.
	 *
	 * ĐỘ SÂU LỊCH SỬ ĐI KÈM TỪNG MỤC, KHÔNG PHẢI MỘT BIẾN CỦA MODULE (soát xét tổng,
	 * M6): `di()` gắn `{kho_sau: n}` vào mục lịch sử VỪA ĐẨY bằng `replaceState`
	 * ngay sau khi gán hash — gán `location.hash` cập nhật lịch sử ĐỒNG BỘ (chỉ SỰ
	 * KIỆN `hashchange` mới là bất đồng bộ), nên `replaceState` ngay dòng sau chạm
	 * đúng mục MỚI. Vì con số sống trong chính mục lịch sử, nút Back CỨNG của Android
	 * không thể làm nó lệch: bấm Back là trình duyệt tự đưa ta về một mục có sẵn con
	 * số đúng của nó. Đó là chỗ khác biệt với bộ đếm cấp module của vòng sửa 1 — bộ
	 * đếm ấy không giảm khi người dùng bấm Back cứng (đường đó không đi qua mã của
	 * ta), nên lệch dần; `history.state` thì không. */
	di(ten, tham_so) {
		const duoi = tham_so && tham_so.length ? "/" + tham_so.join("/") : "";
		const hash_moi = `#/${ten}${duoi}`;
		if (hash_moi === location.hash) {
			this._theo_hash();
			return;
		}
		const sau = this._kho_sau();
		location.hash = hash_moi;
		// Mục vừa đẩy có `state === null` — gắn độ sâu của NÓ vào. `replaceState`
		// không bắn `hashchange`, nên bất biến "đúng một `_ve()` mỗi `di()`" (lượt
		// vẽ do `hashchange` của dòng trên lo) không bị đụng.
		if (history.replaceState) history.replaceState({ kho_sau: sau + 1 }, "");
	}

	/** Số mục lịch sử mà CHÍNH APP NÀY đã đẩy để tới được màn đang đứng. `0` = đang
	 * ở đáy ngăn xếp của app (mục đầu tiên khi mở `/kho`, hoặc một hash người dùng
	 * gõ tay — mục đó `state` rỗng). */
	_kho_sau() {
		return (history.state && history.state.kho_sau) || 0;
	}

	/** Lùi một màn. DÙNG `history.back()` KHI CÒN LÙI ĐƯỢC (soát xét tổng, M6).
	 *
	 * Bản trước gọi thẳng `di(man_cha)`, tức ĐẨY THÊM một mục lịch sử kể cả khi đang
	 * đi LÙI — lịch sử chỉ dài ra, không bao giờ ngắn lại. Đo được trên trình duyệt
	 * thật: `menu → tra-cuu → bấm "‹" → menu → Back của Android → TRA-CUU` (đi TỚI
	 * màn vừa rời), và bấm Back mãi cũng không thoát được app. `history.back()` gỡ
	 * đúng mục mà `di()` vừa đẩy, nên sau khi "‹" đưa về menu (đáy, `kho_sau === 0`)
	 * thì Back của Android THOÁT app — đúng thứ thủ kho trông đợi.
	 *
	 * Đang ở ĐÁY (`kho_sau === 0`: mở thẳng `/kho`, hoặc gõ tay một hash) thì không
	 * có gì để lùi — đi thẳng tới `man_cha` (mặc định "menu"), giữ nguyên hành vi
	 * TẤT ĐỊNH mà Task 2–5 trông cậy. `history.back()` bắn `hashchange` (hai mục
	 * khác hash), nên vẫn ĐÚNG MỘT `_ve()` cho một lượt lùi — không thêm trình nghe
	 * `popstate` nào, thêm là mỗi lượt lùi chạy hai lượt vẽ. */
	quay_lai(man_cha) {
		if (this._kho_sau() > 0) {
			history.back();
			return;
		}
		this.di(man_cha || "menu");
	}

	/** CHỐT CHỐNG TÁI NHẬP (Task 2, rào trước theo Ruling 12/M1 của soát xét Task 1):
	 * trước vòng sửa cuối của Task 1, `di()` tới ĐÚNG màn đang đứng là KHÔNG LÀM GÌ;
	 * giờ nó VẼ LẠI màn đó (bất biến ghi ở `di()` bên trên). Một màn lỡ gọi
	 * `di(chính nó)` NGAY TRONG `ve()` của nó (ví dụ dùng `di()` như cách "vẽ lại"/
	 * "làm mới") thì `di()` thấy hash không đổi, gọi THẲNG `_theo_hash()` ĐỒNG BỘ
	 * (không qua `hashchange`, không có nhịp bất đồng bộ nào chen vào), mà hàm đó
	 * lại gọi `_ve()` — tức gọi lại đúng lượt `_ve()` ĐANG CHẠY DỞ. Không có chốt
	 * thì đây là đệ quy ĐỒNG BỘ vô hạn, treo cứng trình duyệt — không phải lỗi ném
	 * ra được để `try/catch` bắt.
	 *
	 * Lượt vẽ đang chạy KHÔNG được khởi động thêm lượt vẽ nào khác: lời gọi tái
	 * nhập bị BỎ QUA hẳn (không xếp hàng chờ chạy tiếp) — brief chỉ cấm "màn tự gọi
	 * `di()` tới chính nó trong `ve()`", một cách dùng SAI, không phải một luồng
	 * hợp lệ cần phục vụ tới nơi tới chốn. */
	_ve(ten, tham_so) {
		if (this._dang_ve) return;
		this._dang_ve = true;
		try {
			this._ve_that(ten, tham_so);
		} finally {
			// `finally`, không phải cuối thân `_ve_that`: một `ve()` của màn ném lỗi
			// giữa chừng vẫn phải mở lại chốt — không thì `_dang_ve` kẹt `true` MÃI
			// MÃI và KHÔNG MÀN NÀO vẽ được nữa, một hỏng nặng hơn cả đệ quy đang vá.
			this._dang_ve = false;
		}
	}

	_ve_that(ten, tham_so) {
		// Một hộp `hoi()` thuộc về màn đã mở nó — sống sót sang màn khác vừa sai
		// nghĩa (nút của nó gọi callback của màn đã rời) vừa để lại một `OQuet` MỚI
		// (của màn mới) đứng dưới một hộp MỒ CÔI mà không ai biết (soát xét vòng 2,
		// N3). Đóng hết TRƯỚC khi dọn màn cũ — `roi()` của màn có thể tự dựng thêm
		// hộp khác, nên thứ tự này (đóng hộp cũ trước, gọi `roi()` sau) mới đúng.
		//
		// Chi tiết đã biết, vô hại: `dong_het_hop()` phát `kho-hop-doi` trong khi
		// `OQuet` của màn CŨ vẫn còn sống (chưa tới lượt `roi()`/`huy()` bên dưới) —
		// nó nhận sự kiện, thấy khoá vừa gỡ, tự `giu_focus()` lên một ô nhập sắp bị
		// `$than.empty()` xoá vài dòng sau. Không gây lỗi (focus trên một phần tử sắp
		// lìa DOM là vô hại), chỉ là `document.activeElement` có một nhịp ngắn trỏ
		// vào ô sắp mất — nêu ra để không ai tưởng đó là một lỗi mới khi bắt gặp.
		erpnext.kho_pda.dong_het_hop();
		if (this.man_hien_tai && this.man[this.man_hien_tai].roi) {
			this.man[this.man_hien_tai].roi();
		}
		this.man_hien_tai = ten;
		if (this._giu_bao) {
			// `goi()` vừa đặt dải báo NGAY TRƯỚC khi gọi `di()` để giải thích vì sao
			// màn nhảy về đây — giữ nguyên qua ĐÚNG một lượt vẽ này rồi thôi (không thì
			// nó đứng mãi, đè lên câu báo của lượt điều hướng kế tiếp).
			this._giu_bao = false;
		} else {
			this.bao();
		}
		// SOÁT XÉT VÒNG 1 (Task 3, P1 — lỗi NẶNG): `.empty()` một mình chỉ gỡ handler
		// gắn trên CON của `$than`, không gỡ handler gắn TRỰC TIẾP lên CHÍNH `$than`
		// (`$than.on("click", ".lop-con", ...)` — cách uỷ quyền hợp lệ mà một màn có
		// thể lỡ dùng nếu quên khuôn "gắn lên phần tử con dựng lại mỗi `ve()`" của
		// `man_tra_cuu.js`). `man_xep_hang.js` (Task 3) mắc đúng lỗi này: ~9 handler
		// gắn thẳng lên `$than`, đo được TĂNG DẦN qua mỗi lượt vào/ra màn — 10 → 37
		// sau 3 vòng menu↔xep-hang (soát xét). Hậu quả không phải chỉ chậm máy: bấm
		// "Hoàn tất phiếu" MỘT lần bật ra 4 hộp xác nhận chồng nhau, và đồng ý cả bốn
		// thì `duyet()` — một lời GHI thật — chạy ĐÚNG 4 LẦN (`xoa_dong()` cũng vậy).
		// `.off()` KHÔNG tham số gỡ SẠCH mọi handler (mọi namespace) đang gắn thẳng
		// trên `$than` TRƯỚC khi xoá nội dung — chốt chặn ở TẦNG KHUNG này bảo vệ
		// MỌI màn hiện tại lẫn tương lai khỏi đúng lớp lỗi này, không chỉ vá riêng
		// `man_xep_hang.js`. An toàn tuyệt đối: không màn nào trong app (`man_the.js`,
		// `man_menu.js`, `man_tra_cuu.js`) cố tình gắn một handler lên CHÍNH `$than`
		// cần SỐNG QUA một lượt vẽ — `OQuet` (dùng `vung: $than`) tự gỡ đúng phần của
		// nó qua `huy()` (namespace `.oqN`) TRƯỚC dòng này (trong `roi()` ở trên), nên
		// `.off()` ở đây không cắt nhầm một cái gì còn cần.
		this.$than.off();
		this.$than.empty();
		const m = this.man[ten];
		// Ẩn nút "‹" cho khách: `_theo_hash` đã ép khách về đúng màn "the", bấm "‹"
		// (gọi thẳng `di("menu")`, không qua chốt chặn) sẽ vẽ được màn menu tĩnh dù
		// chưa đăng nhập — không sai dữ liệu, nhưng đúng cửa mà "vỏ tự lo đăng nhập,
		// không đá sang trang khác" (đầu `index.py`) muốn khoá.
		const an_nut_ve = ten === "menu" || this.la_khach;
		this.$dau.html(`
			<button type="button" class="kho-ve" ${an_nut_ve ? 'hidden=""' : ""}>‹</button>
			<span class="kho-tieu-de">${frappe.utils.escape_html(m.tieu_de)}</span>
		`);
		// `quay_lai()`, KHÔNG `di("menu")` (soát xét tổng, M6): `di()` ĐẨY THÊM một
		// mục lịch sử kể cả khi đang đi lùi, nên Back của Android sau đó đi TỚI màn
		// vừa rời và không bao giờ thoát được app. `quay_lai()` gỡ mục vừa đẩy.
		this.$dau.find(".kho-ve").on("click", () => this.quay_lai());
		m.ve(this.$than, tham_so || []);
	}

	bao(chu, muc) {
		if (!chu) return this.$bao.empty();
		// API công bố cho Task 2–5 nhét câu MÁY CHỦ trả về (tên hàng, lý do lỗi) —
		// `_dam()` escape TRƯỚC (một tên hàng chứa `<` không vỡ khung, dữ liệu người
		// dùng nhập không thành XSS lưu trữ hiện lại trên màn PDA của người khác),
		// RỒI MỚI cho phép đúng một quy ước tô đậm `**…**` do lớp luồng tự đánh dấu
		// (xem `_dam()` ở đầu file).
		this.$bao.html(`<div class="kho-bao-o muc-${muc || "xam"}">${_dam(chu)}</div>`);
	}

	/** Gọi máy chủ. Phiên hết hạn (401/403) thì đưa về màn quét thẻ thay vì để
	 * người dùng bấm mãi một nút không phản hồi. Không tự đưa về màn thẻ nếu ĐANG
	 * ở màn thẻ: đó là ca "thẻ vừa quét sai" (chính `dang_nhap_bang_the` trả 401),
	 * không phải "phiên hết hạn" — hai câu báo khác hẳn nhau. Dải báo đặt ở đây
	 * SỐNG QUA lượt vẽ do `di()` gây ra nhờ cờ `_giu_bao` (xem `_ve()`) — không có
	 * nó thì `hashchange` (bất đồng bộ) kéo theo một lượt `_ve()` gọi `bao()` rỗng,
	 * xoá câu "Phiên đã hết…" trước khi thủ kho kịp đọc (đo được: dải báo còn sống
	 * ngay sau `goi()`, nhưng biến mất sau ~500ms — bài soát xét vòng 1, mục P3).
	 *
	 * `_da_thu_lam_moi_csrf` (thêm ở Task 3, ngoài brief gốc — xem lý do đầy đủ ở
	 * `task-3-report.md`): tham số NỘI BỘ, không phải một phần API công bố cho Task
	 * 4–6 — chỉ `goi()` tự gọi lại chính nó một lần khi cần làm mới CSRF. */
	async goi(duong_dan, doi_so, _da_thu_lam_moi_csrf) {
		// TASK 5 — TỰ CHỮA: nếu lượt đồng bộ giờ lúc `khoi_dong()` chưa xong hoặc đã
		// hỏng (wifi kho chập chờn), mọi lời gọi nghiệp vụ sau đó đều thử lại — hàm
		// tự thoát ngay nếu đã có kết quả hoặc đang có một lượt đang bay (xem
		// docstring `_dong_bo_gio_may_chu()`), nên dòng này không thêm một lời gọi
		// mạng nào ở đường đã đồng bộ xong.
		this._dong_bo_gio_may_chu();
		const dau = { "Content-Type": "application/json" };
		// KHOÁ MÁY: máy chủ không thấy cookie phiên nào từ app (lời gọi là KHÁC
		// NGUỒN — xem `goc()`), nên danh tính đi trong header này. Chưa có khoá là
		// trạng thái BÌNH THƯỜNG hôm nay (Task 3 mới cấp): khi đó không gửi header
		// rỗng — máy chủ đọc `"token "` không có gì phía sau là một lỗi xác thực
		// khó hiểu hơn hẳn "không gửi gì cả" (Guest).
		const khoa = this.khoa();
		if (khoa) {
			dau["Authorization"] = "token " + khoa;
			// MÃ MÁY ĐI CÙNG KHOÁ, KHÔNG BAO GIỜ TÁCH RA (Task 3 → Task 4). Máy chủ
			// (`the_pda.py::kiem_khoa_may`) từ chối 401 mọi lời gọi mang khoá mà thiếu
			// header này — cố ý fail-closed: một hàng rào chỉ chặn khi kẻ cầm khoá tự
			// nguyện khai mã máy thì không phải hàng rào. Gắn ngay TRONG khối `if (khoa)`
			// để hai header không thể rời nhau: gửi khoá mà quên mã máy là 401 toàn bộ
			// kho, gửi mã máy mà không có khoá là gửi rác cho một lời gọi khách.
			dau[_DAU_MA_MAY] = this.ma_may();
		}
		// CSRF CHỈ CÓ NGHĨA TRÊN WEB. Máy chủ chỉ kiểm CSRF cho lời gọi mang COOKIE
		// phiên (`frappe/app.py::validate_csrf_token` — phiên dựng từ cookie `sid`);
		// app xác thực bằng khoá máy ở header trên, không có cookie nào để giả mạo,
		// nên không có CSRF. Gửi header đó từ app là gửi rác: `frappe.csrf_token`
		// trong app là chuỗi rỗng của `shim.js`, và nhánh làm mới bên dưới còn GET
		// `location.pathname` — trong app là một đường `file://`, tức một lời gọi
		// chắc chắn vô nghĩa. BỎ QUA khi là app, KHÔNG XOÁ khỏi đường web.
		//
		// `frappe.csrf_token` là chuỗi VĂN BẢN `"None"` (không phải giá trị JS
		// falsy) khi phiên khách chưa có token thật (`base_template_page.py`) —
		// `if (frappe.csrf_token)` một mình không lọc được ca này, gửi lên một
		// header rác vô hại HÔM NAY nhưng ăn `400 Invalid Request` ở phiên nào đã
		// có token thật (mở thêm `/app` ở tab khác cùng trình duyệt).
		if (!this._la_app() && frappe.csrf_token && frappe.csrf_token !== "None")
			dau["X-Frappe-CSRF-Token"] = frappe.csrf_token;

		let res;
		try {
			// `${this.goc()}` — CHỖ DUY NHẤT nối địa chỉ máy chủ vào lời gọi. Trên
			// web `goc()` rỗng nên chuỗi này là `/api/method/...` y như trước, không
			// đổi một byte nào của hành vi web.
			//
			// `credentials: "same-origin"` GIỮ NGUYÊN, KHÔNG đổi sang `"include"`
			// (lệch đoạn mẫu của brief — lý do ở `task-2-report.md`): trên web lời
			// gọi là CÙNG NGUỒN nên cookie phiên vẫn đi như cũ; trong app lời gọi là
			// KHÁC NGUỒN nên `"same-origin"` tự không gửi cookie — đúng thứ ta muốn
			// (danh tính đi bằng khoá máy). `"include"` sẽ bắt MỌI máy chủ mà APK
			// từng trỏ tới phải trả `Access-Control-Allow-Credentials: true` kèm
			// `Access-Control-Allow-Origin` ĐÍCH DANH (không được `*`), đổi một bài
			// toán CORS đơn giản thành một bài toán khó hơn mà không đổi lấy gì.
			res = await fetch(`${this.goc()}/api/method/${duong_dan}`, {
				method: "POST",
				headers: dau,
				credentials: "same-origin",
				body: JSON.stringify(doi_so || {}),
			});
		} catch (e) {
			// Mất mạng giữa chừng (wifi kho chập chờn) thì `fetch` tự reject bằng một
			// `TypeError` mang câu tiếng Anh của trình duyệt ("Failed to fetch") —
			// không phải phản hồi HTTP nên `_cau_loi_may_chu` không có thân JSON để
			// đọc. Đổi câu ở ĐÚNG MỘT CHỖ này để mọi màn gọi `goi()` không phải tự
			// phân biệt "máy chủ từ chối" với "không tới được máy chủ".
			throw new Error(__("Mất kết nối. Kiểm tra wifi rồi thử lại."));
		}

		const than = await res.json().catch(() => ({}));
		if (res.ok) return than.message;

		// CA CÒN LẠI CỦA LỖI CSRF (thêm ở Task 3): không gửi header rác (đoạn trên)
		// mới chỉ chặn được NỬA sự cố 23/09/2026 — nửa kia là phiên NÀY đã có
		// `csrf_token` THẬT ở phía máy chủ (site sinh nó cho phiên này khi render
		// một trang khác, vd. `/app` mở ở tab khác CÙNG trình duyệt — cookie phiên
		// dùng chung), trong khi biến `frappe.csrf_token` ở đây vẫn mang giá trị lúc
		// TẢI TRANG `/kho` (rỗng nếu tải lúc còn Khách, hoặc token CŨ của phiên
		// trước nếu vừa đăng nhập bằng thẻ mà không tải lại trang — định tuyến bằng
		// hash cố tình không tải lại, xem đầu file). Máy chủ trả đúng `400 "Invalid
		// Request"` kèm `exc_type: "CSRFTokenError"` cho ca này
		// (`frappe/exceptions.py::CSRFTokenError`, `frappe/utils/response.py`:
		// `exc_type` LUÔN được gán cho API v1, không phụ thuộc chế độ traceback) —
		// tín hiệu đủ RIÊNG để không nhầm với một `400` nghiệp vụ khác.
		//
		// Sửa bằng cách ĐỌC LẠI token thật: GET một trang bất kỳ (không bị kiểm CSRF
		// — `validate_csrf_token` chỉ xét phương thức KHÔNG AN TOÀN) rồi rút
		// `frappe.csrf_token = "...";` mà `add_csrf_token()` (`base_template_page.py`)
		// đã nhúng sẵn cho phiên đang đăng nhập, cập nhật biến, rồi GỌI LẠI
		// ĐÚNG MỘT LẦN (`_da_thu_lam_moi_csrf` chặn vòng lặp nếu máy chủ vẫn từ chối
		// vì một lý do khác đội lốt cùng `exc_type`). KHÔNG đổi hàm máy chủ nào —
		// toàn bộ vá nằm ở phía trình duyệt, đúng ràng buộc toàn cục của Task 3.
		//
		// `!this._la_app()` (Task 2): trong app không có cookie phiên nên máy chủ
		// không bao giờ trả `CSRFTokenError` — nhưng nếu một máy chủ nào đó lỡ trả,
		// nhánh này sẽ GET `location.pathname` của một trang `file://` và nuốt mất
		// lỗi thật. Chặn ở điều kiện, không xoá nhánh: đường web vẫn cần nguyên nó.
		if (!this._la_app() && than.exc_type === "CSRFTokenError" && !_da_thu_lam_moi_csrf) {
			const token_moi = await _doc_lai_csrf_tu_trang();
			if (token_moi) {
				frappe.csrf_token = token_moi;
				return this.goi(duong_dan, doi_so, true);
			}
		}

		// THU HỒI, NHÌN THẤY ĐƯỢC TỪ PHÍA MÁY (Task 4, việc 4). Trưởng kho bấm "Thu
		// hồi thẻ"/"Thu hồi máy" trên Desk là chiếc khoá chết thật ở máy chủ (Task 3);
		// từ đây trở đi mọi lời gọi của máy này trả 401. Không XOÁ chiếc khoá đã chết
		// đó khỏi kho lưu thì app kẹt vĩnh viễn: mở lên là `_nap_khoa_da_cat` đọc lại
		// đúng chiếc khoá hỏng, `la_khach = false`, vào thẳng menu, chạm cái gì cũng
		// 401 — thủ kho không có đường nào tới được màn quét thẻ để nhận máy lại.
		//
		// ĐIỀU KIỆN LÀ `khoa`, KHÔNG PHẢI `man_hien_tai`, và nằm NGOÀI khối dưới: một
		// khoá vừa bị thu hồi phải chết kể cả khi 401 xảy ra lúc đang đứng ở màn thẻ.
		// Trên web `khoa` luôn rỗng nên nhánh này không tồn tại ở đó.
		//
		// VÒNG SỬA CUỐI (soát tổng, N2) — ĐIỀU KIỆN KHÔNG CÒN LÀ "401 HOẶC 403".
		// 403 trong app là lỗi QUYỀN NGHIỆP VỤ (`PermissionError`), không phải
		// "khoá máy hỏng"; xoá khoá ở đó là **cả kho mất khoá cùng lúc** vì một
		// lỗi quyền của máy chủ, rồi phải đi lấy lại thẻ giấy — mà chính đợt này
		// khuyến khích cất thẻ đi sau khi nhận máy. Đã xảy ra một lần thật: bản vá
		// 24/09 trong `selling_controller.py` là để chữa đúng một `PermissionError`
		// mà thủ kho ăn mỗi lần lưu phiếu giao trên màn Lấy hàng.
		const la_danh_tinh = this._la_loi_danh_tinh(res.status, than);
		if (la_danh_tinh && khoa) {
			this.xoa_khoa();
			this.la_khach = true;
		}

		// Dựng câu lỗi TRƯỚC khối dải báo, không phải sau (vòng sửa 1, mục F). Câu này
		// vốn đã được tính ra ở đây rồi bị NÉM ĐI khỏi dải báo: cùng một lượt 401 sau
		// khi trưởng kho thu hồi, `loi.message` là "Máy chưa được cấp quyền — báo trưởng
		// kho cấp khoá cho máy này." (đúng nguyên nhân, đúng việc phải làm — Task 2B rút
		// ra được từ `_server_messages`), trong khi dải báo lại nói "Phiên đã hết — quét
		// thẻ để làm tiếp.".
		const cau = _cau_loi_may_chu(than, res.status, this._la_app());

		// CÙNG ĐIỀU KIỆN với khối xoá khoá ở trên, và phải cùng: đá thủ kho về màn
		// quét thẻ vì một lỗi QUYỀN là bắt họ bỏ dở phiếu đang làm để đi quét một
		// tấm thẻ chẳng chữa được gì.
		if (la_danh_tinh && this.man_hien_tai !== "the") {
			// HAI CÂU, RẼ BẰNG `_la_app()` — cùng tiền lệ `_cau_loi_thay_the` của Task 2B,
			// và vì cùng một lý do: trên web 401/403 THẬT LÀ phiên hết hạn (12 tiếng), còn
			// trong app không có phiên nào để hết — nó nghĩa là khoá máy đã bị thu hồi
			// hoặc chưa cấp.
			//
			// HẬU QUẢ CỤ THỂ NẾU DÙNG CHUNG MỘT CÂU: thủ kho đọc "quét thẻ để làm tiếp"
			// nên quét lại ĐÚNG TẤM THẺ VỪA BỊ THU HỒI, thất bại lần nữa, và không biết
			// phải gọi trưởng kho. Task 4 biến đường này từ hiếm (phiên hết giữa ca) thành
			// thường xuyên (mỗi lần thu hồi), nên câu sai ở đây tốn người thật.
			//
			// VẾ WEB GIỮ NGUYÊN VĂN, không một chữ nào đổi — `test_giao_dien` và nửa WEB
			// của `kiem_goi_mang` đều canh đúng chuỗi đó.
			this.bao(this._la_app() ? cau : __("Phiên đã hết — quét thẻ để làm tiếp."), "cam");
			this._giu_bao = true;
			this.di("the");
		}
		const loi = new Error(cau);
		loi.ma = res.status;
		throw loi;
	}
}

/** GET trang HIỆN TẠI (phương thức AN TOÀN, không đi qua `validate_csrf_token`) để
 * đọc `frappe.csrf_token` THẬT mà máy chủ vừa nhúng cho phiên đang đăng nhập —
 * xem lý do đầy đủ ở `goi()`. `null` nếu không đọc được (mất mạng, hoặc phiên vẫn
 * chưa có token thật — ca BÌNH THƯỜNG khi chưa ai render một trang khác trong
 * phiên này; `goi()` khi đó cứ để lỗi 400 gốc nổi lên, không lặp mãi). */
async function _doc_lai_csrf_tu_trang() {
	try {
		const res = await fetch(location.pathname, { method: "GET", credentials: "same-origin" });
		const html = await res.text();
		const khop = /frappe\.csrf_token\s*=\s*"([^"]*)"/.exec(html);
		return khop && khop[1] && khop[1] !== "None" ? khop[1] : null;
	} catch (e) {
		return null;
	}
}

erpnext.kho_pda.KhoApp = new _KhoApp();

$(document).ready(() => {
	const goc = document.getElementById("kho-app");
	if (!goc) return;
	erpnext.kho_pda.KhoApp.khoi_dong(goc);
});
