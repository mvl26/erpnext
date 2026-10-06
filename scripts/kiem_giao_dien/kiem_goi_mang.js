#!/usr/bin/env node
// Cổng nghiệm thu cho LỚP GỌI MẠNG (`vo.js::goi()`) — chứng minh bằng HÀNH VI
// THẬT, không bằng grep, rằng cùng một bundle gọi đúng địa chỉ ở CẢ HAI NƠI.
//
// VÌ SAO PHẢI CÓ RIÊNG MỘT CỔNG: cổng `kiem_ban_dong_goi.js` THAY HẲN
// `KhoApp.goi` bằng một máy chủ giả trong trang (`a.goi = ...`), nên nó không
// nhìn thấy một dòng nào của lớp gọi mạng — nó xanh 4/4 kể cả khi `goi()` gọi vào
// hư không. Cổng này làm ngược lại: giữ `goi()` THẬT, dựng một MÁY CHỦ HTTP THẬT
// ở `127.0.0.1` và đọc xem lời gọi ĐI TỚI ĐÂU và MANG THEO HEADER GÌ.
//
// HAI MÔI TRƯỜNG, MỘT BUNDLE:
//   APP — mở `file://…/pda_app/www/index.html`, `window.KHO_MAY_CHU` trỏ vào máy
//         chủ giả, `window.KHO_LA_APP === true`. Trang nằm ở `file://` nên một
//         đường dẫn TƯƠNG ĐỐI không thể nào tới được máy chủ giả: mỗi lời gọi ghi
//         nhận được là một bằng chứng địa chỉ TUYỆT ĐỐI đã được dựng đúng.
//   WEB — máy chủ giả tự phục vụ một trang ở `/kho-thu` nạp ĐÚNG ba file của bản
//         đóng gói (jQuery + `shim.js` + `kho_pda.bundle.js`) nhưng KHÔNG khai
//         `KHO_MAY_CHU`/`KHO_LA_APP`. Đó là hình ảnh của đường web: `goc()` rỗng
//         → đường tương đối → cùng nguồn. Cái cần khoá ở đây là KHÔNG ĐỔI HÀNH VI.
//
// KHÔNG BAO GIỜ ĐI RA MÁY CHỦ THẬT: máy chủ giả nghe trên `127.0.0.1` cổng ngẫu
// nhiên, và một đường dẫn `/api/method/...` LẠ làm HỎNG bài (không trả 200 im
// lặng) — cùng khuôn với `kiem_ban_dong_goi.js`.
//
// CHẠY:  node scripts/kiem_giao_dien/kiem_goi_mang.js
// Cần `scripts/pda/dong-goi.sh` chạy trước (www/ phải có bản dựng MỚI NHẤT — cổng
// này đọc bản ĐÃ CHÉP, không đọc mã nguồn).

const fs = require("fs");
const http = require("http");
const path = require("path");

const DUONG_PLAYWRIGHT =
	"/home/hoangvietyeuem/frappe-bench-yhct/apps/supplycore/frontend/node_modules/playwright";

const GOC_APP = path.resolve(__dirname, "..", "..");
const WWW = path.join(GOC_APP, "pda_app", "www");
const TRANG_APP = path.join(WWW, "index.html");

// Đường dẫn hàm máy chủ GIẢ. Không trùng một hàm thật nào — nếu bài này lỡ trỏ
// vào máy chủ thật thì nó 404 ở đó, không âm thầm chạy một hàm nghiệp vụ.
const HAM_OK = "kho.thu.doc_duoc";
const HAM_401 = "kho.thu.can_dang_nhap";
const HAM_CSRF = "kho.thu.doi_csrf";
// TASK 2B — ba ca câu lỗi. Máy chủ THẬT sinh cả ba; trước Task 2B cả ba đều đổ
// nguyên vẹn ra dải báo của thủ kho.
const HAM_LOI_HTML = "kho.thu.loi_html"; // 403 + `_server_messages` là khối HTML tiếng Anh
const HAM_TRANG_500 = "kho.thu.trang_500"; // 500 + thân KHÔNG phải JSON (trang lỗi HTML)
const HAM_401_TRONG = "kho.thu.401_khong_than"; // 401 + thân JSON rỗng (không có câu nào)
// TASK 4 — nút "Đăng xuất" gọi ĐÚNG `logout` của Frappe (`handler.py`, allow_guest).
// Tên thật, không phải tên giả, vì cổng này bấm đúng cái nút đó: đường thật phải nằm
// trong tập đường dẫn BIẾT TRƯỚC, không thì nó rơi vào nhánh "đường dẫn LẠ → 500" ở
// cuối file và cổng đỏ vì một lý do chẳng liên quan.
const HAM_LOGOUT = "logout";

// VÒNG SỬA 1 (soát xét, T5-4) — TÊN THẬT, cùng lý do `HAM_LOGOUT`: đây là mục kiểm
// HÀNH VI của cơ chế "giờ máy chủ" (Task 5), phải để `vo.js::_dong_bo_gio_may_chu()`
// gọi ĐÚNG đường thật của nó, không phải một tên giả.
const HAM_GIO_MAY_CHU = "erpnext.warehouse_operations.vitri.the_pda.gio_may_chu";
const HAM_TRA_CUU = "erpnext.warehouse_operations.vitri.quet.tra_cuu";
// TASK 6 — TÊN THẬT, cùng lý do `HAM_LOGOUT`/`HAM_GIO_MAY_CHU`: màn menu gọi đúng
// đường này để hỏi bản cài mới nhất (spec §10).
const HAM_BAN_CAI = "erpnext.warehouse_operations.vitri.cai_app.ban_cai_moi_nhat";

// TASK 6 — PHIÊN BẢN CỦA CHÍNH BẢN ĐÓNG GÓI ĐANG ĐO, đọc từ `www/cau-hinh.js`
// (bản ĐÃ CHÉP, không phải từ `build.gradle`).
//
// VÌ SAO ĐỌC TỪ BẢN ĐÃ CHÉP: `dong-goi.sh` là thứ sinh ra `KHO_BAN_APP`, nên nếu
// nó quên sinh (hoặc sinh sai khuôn) thì bài này phải ĐỎ — viết cứng "1.0" ở đây
// là tự mình trả lời câu hỏi mình đang hỏi. Không đọc được = cổng đỏ ngay ở hàm
// khởi động phía dưới, vì mọi khẳng định của dải nhắc đều dựng trên con số này.
function ban_app_cua_ban_dong_goi() {
	const tep = path.join(WWW, "cau-hinh.js");
	if (!fs.existsSync(tep)) return "";
	const khop = /window\.KHO_BAN_APP\s*=\s*"([^"]+)"/.exec(fs.readFileSync(tep, "utf-8"));
	return khop ? khop[1] : "";
}
const BAN_APP = ban_app_cua_ban_dong_goi();

// Tên file bản cài mà máy chủ giả trả cho `ban_cai_moi_nhat`. ĐỔI ĐƯỢC giữa các
// kịch bản (xem `do_nhac_ban_moi`).
//
// MẶC ĐỊNH LÀ BẢN NGANG BẰNG, KHÔNG PHẢI MỘT CỜ "BỎ QUA": mọi kịch bản khác của
// cổng này vẽ màn menu, và dải nhắc bật lên ở đó sẽ làm bẩn phép đo của chúng.
// Cách tắt nó phải đi qua ĐÚNG CƠ CHẾ THẬT (máy chủ nói "bản mới nhất chính là
// bản anh đang cầm") — thêm một cờ `KHO_BO_QUA_NHAC_BAN_MOI` là dựng lại đúng cái
// bẫy T5-4 của Task 5: một cổng tự tắt cơ chế nó phải canh thì không phải cổng.
let ten_ban_cai_gia = `miyano-pda-${BAN_APP}-release.apk`;
// Độ trễ (ms) máy chủ giả giữ lại trước khi trả `ban_cai_moi_nhat`. Dùng để dựng
// ca "lời gọi còn đang bay thì người dùng rời màn menu rồi quay lại" — ca duy
// nhất làm lộ được hai dải nhắc chồng nhau (xem `do_hai_dai_nhac`).
let tre_ban_cai_ms = 0;
// Bật lên thì máy chủ giả trả 500 cho `ban_cai_moi_nhat` — hình ảnh một lượt hỏi
// thất bại (mất sóng, máy chủ hỏng riêng đường này). Xem `do_hoi_lai_sau_khi_hong`.
let ban_cai_hong = false;
// Giá trị CỐ ĐỊNH máy chủ giả trả cho `gio_may_chu` — không lấy theo đồng hồ tiến
// trình chạy bài test: nếu `ngay`/`gio` bị ĐẢO chỗ tiêm (F1 của soát xét vòng 1),
// `gio_may_chu()` (đọc "09:30:00" thay vì "2026-09-25") không khớp khuôn ngày của
// `_ngay_con_lai`, `trang_thai_han` rơi về `{muc:"khong"}` — chip biến mất, và
// khẳng định "đúng nội dung chip" bên dưới bắt được ngay không cần suy luận gì thêm.
const NGAY_MAY_CHU_GIA_CO_DINH = "2026-09-25";
const GIO_MAY_CHU_GIA_CO_DINH = "09:30:00";
// Một lô HẾT HẠN NGÀY MAI (theo `NGAY_MAY_CHU_GIA_CO_DINH`) — nếu lớp luồng nhận
// ĐÚNG cả `ngay` lẫn `gio_may_chu()` thật sự chạy (F3: đồng bộ luôn thoát sớm) thì
// chip phải là "Còn 1 ngày"/`muc-can`; sai một trong hai thứ đó, chip hoặc biến
// mất hoặc đổi chữ — cả hai đều bắt được bằng một phép so CHUỖI ĐÚNG.
const HSD_LO_GIA_CO_DINH = "2026-09-26";

// Nguyên văn câu mà Frappe nhét vào `_server_messages` cho lỗi quyền — chép từ
// phép đo của vòng soát Task 2 (mục F), không bịa.
const CAU_HTML_CUA_FRAPPE =
	"<details><summary>You are not permitted to access this resource. Login to access</summary>" +
	"Function erpnext.warehouse_operations.api.tra_cuu is not whitelisted.</details>";
const CAU_CHUA_CAP_QUYEN = "Máy chưa được cấp quyền — báo trưởng kho cấp khoá cho máy này.";
// VÒNG SỬA CUỐI (soát tổng, N2) — CÂU RIÊNG CHO 403 NGHIỆP VỤ.
//
// Trước vòng này, 403 và 401 dùng CHUNG câu `CAU_CHUA_CAP_QUYEN`. Đo trên máy chủ
// thật (25/09/2026): khoá API sai → 401 `AuthenticationError`; lỗi QUYỀN nghiệp vụ
// → 403 `PermissionError`. Mà `the_pda.kiem_khoa_may` — hàng rào mã máy — ném
// `AuthenticationError`, tức 401. Nên 403 trong app KHÔNG phải "khoá máy hỏng", và
// bảo thủ kho "báo trưởng kho cấp khoá cho máy này" là chỉ sai người lẫn sai việc:
// khoá máy của họ vẫn tốt, quét lại thẻ không chữa được gì.
const CAU_KHONG_DU_QUYEN = "Tài khoản không có quyền làm việc này — báo trưởng kho.";
const CAU_CHUNG = "Có lỗi, thử lại.";

// Bản `native-bridge.js` THẬT mà Capacitor tiêm vào WebView trên Android. Cổng
// này nạp ĐÚNG file đó (không viết lại một bản mô phỏng): thứ cần đo là mã CỦA
// CAPACITOR dựng ra đối tượng `Response`, không phải hiểu biết của ta về nó.
const NATIVE_BRIDGE = path.join(
	GOC_APP,
	"pda_app",
	"node_modules",
	"@capacitor",
	"android",
	"capacitor",
	"src",
	"main",
	"assets",
	"native-bridge.js"
);

// Token mà TRANG WEB GIẢ nhúng sẵn — `_doc_lai_csrf_tu_trang()` (vo.js) rút đúng
// chuỗi này ra khi máy chủ trả `CSRFTokenError`.
const TOKEN_TRANG = "TOKEN-MOI-7391";
const TOKEN_CU = "TOKEN-CU-0001";

const KIEU = {
	".js": "application/javascript; charset=utf-8",
	".css": "text/css; charset=utf-8",
	".html": "text/html; charset=utf-8",
};

// Trang WEB giả: cùng ba file của bản đóng gói, KHÔNG `cau-hinh.js`, KHÔNG
// `KHO_LA_APP`. `data-la_khach="0"` để `vo.js` vẽ thẳng màn menu (màn menu là nơi
// in dòng "Máy chủ:", và nó không gọi máy chủ lúc vẽ nên không làm bẩn phép đếm).
//
// Chuỗi `frappe.csrf_token = "…";` nhúng trong HTML là thứ `_doc_lai_csrf_tu_trang`
// TÌM BẰNG REGEX trên phần thân trang — giống hệt cách `base_template_page.py` của
// Frappe nhúng nó cho phiên đang đăng nhập.
function trang_web_gia() {
	return `<!doctype html>
<html lang="vi">
<head><meta charset="utf-8" /><title>Kho — web giả</title>
<link rel="stylesheet" href="/www/kho_pda.bundle.css" /></head>
<body>
	<div id="kho-app" data-la_khach="0" data-nguoi_dung="thukho-gia"></div>
	<script src="/www/vendor/jquery.min.js"></script>
	<script src="/www/shim.js"></script>
	<script>frappe.csrf_token = "${TOKEN_TRANG}";</script>
	<script src="/www/kho_pda.bundle.js"></script>
</body>
</html>`;
}

function dat_cors(res) {
	// `Access-Control-Allow-Origin: *` LÀ HỢP LỆ ở đây đúng vì `goi()` dùng
	// `credentials: "same-origin"` (không gửi cookie khi khác nguồn). Đổi sang
	// `"include"` là phải trả origin ĐÍCH DANH + `Allow-Credentials` — xem chú
	// thích trong `vo.js::goi()`.
	res.setHeader("Access-Control-Allow-Origin", "*");
	res.setHeader("Access-Control-Allow-Methods", "POST, GET, OPTIONS");
	// Thiếu `Authorization` ở đây thì preflight từ chối và bài đỏ vì một lý do
	// KHÔNG LIÊN QUAN tới thứ đang đo. `X-Ma-May` (Task 4) cũng vậy — nó KHÔNG nằm
	// trong danh sách header an toàn của CORS, nên lời gọi của nửa APP (trang
	// `file://` → máy chủ giả, tức KHÁC NGUỒN) bị chặn ngay ở lượt preflight và
	// `goi()` báo "Mất kết nối" — một triệu chứng chẳng liên quan gì tới lỗi thật.
	// Trên máy THẬT không có lượt preflight nào: cầu native đi bằng
	// `HttpURLConnection` ở tầng Java, ngoài luật cùng-nguồn của WebView.
	res.setHeader(
		"Access-Control-Allow-Headers",
		"Content-Type, Authorization, X-Frappe-CSRF-Token, X-Ma-May"
	);
}

// Máy chủ giả + nhật ký mọi lời gọi `/api/method/...` nó nhận được.
function dung_may_chu_gia(dia_chi_nghe) {
	const nhat_ky = [];
	//: Nhật ký RIÊNG chỉ ghi phương thức, và ghi TRƯỚC mọi nhánh trả sớm — xem chú
	//: thích trong thân máy chủ. Tách khỏi `nhat_ky` vì `nhat_ky` chỉ được đẩy sau
	//: khi đọc xong thân lời gọi, tức sau vài nhánh `return`.
	const nhat_ky_pt = [];
	const may_chu = http.createServer((req, res) => {
		const u = new URL(req.url, "http://127.0.0.1");
		dat_cors(res);

		// GHI PHƯƠNG THỨC TRƯỚC MỌI NHÁNH TRẢ SỚM (Task 3, ý kiến P2 của vòng soát
		// Task 2B). Nếu chỉ ghi ở nhánh `/api/method/` phía dưới thì một `OPTIONS`
		// hay một lời gọi rẽ sớm sẽ không để lại dấu vết nào, và khẳng định "mọi lời
		// gọi đều POST" ở cuối file sẽ có một điểm mù ngay chỗ nó cần nhìn nhất.
		//
		// BỎ QUA ĐÚNG MỘT THỨ, và nói rõ vì sao: lượt PREFLIGHT do CHÍNH TRÌNH DUYỆT
		// phát ra, không phải `goi()` phát. Nhận diện nó bằng header
		// `Access-Control-Request-Method` (thứ chỉ có ở preflight thật) chứ không
		// bằng `method === "OPTIONS"` trần — nếu một ngày `goi()` tự phát một
		// `OPTIONS` thì lời gọi đó KHÔNG mang header này và vẫn bị bắt. Trên máy
		// thật không có lượt preflight nào cả: cầu native đi bằng `HttpURLConnection`
		// ở tầng Java, ngoài luật cùng-nguồn của WebView.
		const la_preflight = req.method === "OPTIONS" && !!req.headers["access-control-request-method"];
		if (u.pathname.startsWith("/api/method/") && !la_preflight) {
			nhat_ky_pt.push({ pt: req.method, duong_dan: u.pathname });
		}

		if (req.method === "OPTIONS") {
			res.writeHead(204);
			res.end();
			return;
		}

		if (u.pathname === "/kho-thu") {
			res.writeHead(200, { "Content-Type": KIEU[".html"] });
			res.end(trang_web_gia());
			return;
		}

		if (u.pathname.startsWith("/www/")) {
			const tep = path.join(WWW, u.pathname.slice("/www/".length));
			if (!tep.startsWith(WWW) || !fs.existsSync(tep)) {
				res.writeHead(404);
				res.end("khong co");
				return;
			}
			res.writeHead(200, { "Content-Type": KIEU[path.extname(tep)] || "text/plain" });
			res.end(fs.readFileSync(tep));
			return;
		}

		if (!u.pathname.startsWith("/api/method/")) {
			res.writeHead(404);
			res.end("khong co");
			return;
		}

		const ham = u.pathname.slice("/api/method/".length);
		let than = "";
		req.on("data", (m) => (than += m));
		req.on("end", () => {
			nhat_ky.push({
				ham: ham,
				duong_dan: u.pathname,
				dau: req.headers,
				than: than,
				origin: req.headers.origin || "",
			});

			const tra = (ma, doi_tuong) => {
				res.writeHead(ma, { "Content-Type": "application/json" });
				res.end(JSON.stringify(doi_tuong));
			};

			if (ham === HAM_OK) return tra(200, { message: { ok: true, ten: "Găng tay khám bệnh cỡ M" } });
			// `logout` của Frappe trả 200 với thân gần như rỗng.
			if (ham === HAM_LOGOUT) return tra(200, { message: "Logged Out" });
			// VÒNG SỬA 1 (T5-4) — giá trị CỐ ĐỊNH, xem lý do ở khai báo hằng số.
			if (ham === HAM_GIO_MAY_CHU) {
				return tra(200, {
					message: {
						ngay: NGAY_MAY_CHU_GIA_CO_DINH,
						gio: GIO_MAY_CHU_GIA_CO_DINH,
						moc_epoch_ms: Date.now(),
					},
				});
			}
			if (ham === HAM_TRA_CUU) {
				return tra(200, {
					message: {
						loai: "lo",
						so_lo: "LO-T5-VONG-SUA-1",
						vat_tu: "VT-T5-VONG-SUA-1",
						ten_hang: "Hàng giả — vòng sửa 1 T5-4",
						don_vi: "Hộp",
						hsd: HSD_LO_GIA_CO_DINH,
						ton_theo_o: [],
					},
				});
			}
			// TASK 6 — hình dạng THẬT của `cai_app._ban_moi_nhat()`: một đối tượng
			// mang `ten` (tên file), `duong_dan`, `dung_luong_mb`, `tai_len_luc`.
			// `null` khi chưa ai tải bản nào lên — `ten_ban_cai_gia` rỗng dựng lại
			// đúng ca đó.
			if (ham === HAM_BAN_CAI) {
				if (ban_cai_hong) return tra(500, { _server_messages: "[]" });
				if (tre_ban_cai_ms) {
					const ten_luc_do = ten_ban_cai_gia;
					return setTimeout(() => {
						tra(200, {
							message: ten_luc_do
								? { ma: "FILE-GIA-0001", ten: ten_luc_do, dung_luong_mb: 4.2 }
								: null,
						});
					}, tre_ban_cai_ms);
				}
				if (!ten_ban_cai_gia) return tra(200, { message: null });
				return tra(200, {
					message: {
						ma: "FILE-GIA-0001",
						ten: ten_ban_cai_gia,
						duong_dan: "/api/method/erpnext.warehouse_operations.vitri.cai_app.tai_ban_cai",
						duong_dan_file_tinh: "/files/" + ten_ban_cai_gia,
						dung_luong_mb: 4.2,
						tai_len_luc: "2026-09-25 08:00:00",
					},
				});
			}
			if (ham === HAM_401) {
				return tra(401, {
					_server_messages: JSON.stringify([JSON.stringify({ message: "Thẻ không hợp lệ." })]),
				});
			}
			// TASK 2B — ba ca câu lỗi mà máy chủ Frappe THẬT sinh ra.
			if (ham === HAM_LOI_HTML) {
				// Y NGUYÊN hình dạng đã đo trên máy chủ thật: 403, `Content-Type`
				// LÀ `application/json`, và `_server_messages` chứa một khối HTML.
				// Đây KHÔNG phải ca "thân không phải JSON" — chỗ này từng bị chẩn
				// đoán nhầm, nên cổng phải giữ đúng hình dạng thật.
				return tra(403, {
					_server_messages: JSON.stringify([JSON.stringify({ message: CAU_HTML_CUA_FRAPPE })]),
				});
			}
			if (ham === HAM_401_TRONG) {
				return tra(401, {});
			}
			if (ham === HAM_TRANG_500) {
				// Thân KHÔNG phải JSON: một trang lỗi HTML. `res.json()` ném lỗi,
				// `goi()` nuốt bằng `.catch(() => ({}))` → không có câu nào để rút.
				res.writeHead(500, { "Content-Type": "text/html; charset=utf-8" });
				res.end("<!doctype html><html><body><h1>Internal Server Error</h1></body></html>");
				return;
			}
			if (ham === HAM_CSRF) {
				// Y như Frappe: token CŨ → 400 `CSRFTokenError`; token trang → 200.
				if (req.headers["x-frappe-csrf-token"] === TOKEN_TRANG) {
					return tra(200, { message: { ok: true, token_da_dung: TOKEN_TRANG } });
				}
				return tra(400, { exc_type: "CSRFTokenError", _server_messages: "[]" });
			}
			// Đường dẫn LẠ: hỏng LỘ RA, không 200 im lặng.
			return tra(500, {
				_server_messages: JSON.stringify([
					JSON.stringify({ message: "MAY CHU GIA khong biet duong dan: " + ham }),
				]),
			});
		});
	});
	const nghe = dia_chi_nghe || "127.0.0.1";
	return new Promise((ok) => {
		may_chu.listen(0, nghe, () =>
			ok({ may_chu, nhat_ky, nhat_ky_pt, cong: may_chu.address().port, nghe })
		);
	});
}

// Ghi đè `window.KHO_MAY_CHU` / `KHO_LA_APP` / `KHO_BAN_THU` bằng ACCESSOR chứ
// không bằng phép gán: `cau-hinh.js` của bản đóng gói chạy SAU `addInitScript` và
// sẽ đè mất một phép gán thường. Setter rỗng nuốt phép gán đó, getter giữ giá trị
// của bài. (Cách này cũng chính là cách chứng minh `goc()` đọc ĐÚNG biến ấy.)
function script_khai(bien) {
	return `
		(function () {
			var V = ${JSON.stringify(bien)};
			Object.keys(V).forEach(function (ten) {
				Object.defineProperty(window, ten, {
					configurable: true,
					get: function () { return V[ten]; },
					set: function () {},
				});
			});
			window.__loi_async = [];
			window.addEventListener("unhandledrejection", function (e) {
				window.__loi_async.push(String((e.reason && e.reason.stack) || e.reason));
			});
		})();
	`;
}

const sai = [];
function khang_dinh(dieu_kien, cau) {
	if (!dieu_kien) sai.push(cau);
}

// ============================================================================
// HAI RÀO CHẮN TẤT ĐỊNH (vòng sửa cuối — soát tổng, V3)
// ============================================================================
//
// Phần Task 6 của cổng này từng CHẬP CHỜN: người soát chạy 11 lượt → 5 đỏ / 6
// xanh, 5 cụm khẳng định khác nhau, 100% thuộc `ban_cai_moi_nhat`, đỏ dồn về lúc
// máy tải nặng. Nguyên nhân: tôi chờ bằng `waitForTimeout(<số cố định>)` rồi đọc
// DOM. Dưới tải, lượt gọi mạng + một vòng microtask không kịp xong trong khung
// đó, và khẳng định đọc trúng trạng thái DỞ DANG.
//
// Luật từ soát tổng: **một cổng đỏ ngẫu nhiên cũng không phải cổng** — người bảo
// trì sẽ chạy lại tới khi xanh, và từ lúc đó nó không còn canh gì. Cách chữa
// KHÔNG phải nới khẳng định hay tăng số giây (chỉ đẩy xác suất xuống, không xoá
// nó): thay phép chờ THEO THỜI GIAN bằng phép chờ THEO SỰ KIỆN.
//
// Rào 1 — `cho_may_chu_nhan()`: chờ ở phía NODE cho tới khi máy chủ giả THẬT SỰ
// ghi nhận đủ số lời gọi. Không có trình duyệt nào tham gia, nên không có gì để
// đua.
// Rào 1b — `tim_goi()`: lấy lời gọi ĐẦU TIÊN tới `ham` kể từ vị trí `tu_vi_tri`,
// thay cho `nhat_ky[tu_vi_tri]`.
//
// VÌ SAO (V3): đọc theo CHỈ SỐ giả định "lời gọi kế tiếp đúng là lời gọi tôi vừa
// phát". Từ Task 6 giả định đó KHÔNG còn đúng: màn menu tự bắn một lượt
// `ban_cai_moi_nhat`, và dưới tải nó có thể đáp xuống nhật ký CHEN VÀO GIỮA — lúc
// đó mọi khẳng định phía sau đọc nhầm sang lời gọi của cơ chế khác và cổng đỏ vì
// một lý do chẳng liên quan. Tra theo tên hàm thì thứ tự đáp không còn ảnh hưởng.
function tim_goi(nhat_ky, ham, tu_vi_tri) {
	return nhat_ky.slice(tu_vi_tri).find((g) => g.ham === ham);
}

async function cho_may_chu_nhan(nhat_ky, ham, so_luong, tu_vi_tri, han_ms = 15000) {
	const het = Date.now() + han_ms;
	while (Date.now() < het) {
		if (nhat_ky.slice(tu_vi_tri).filter((g) => g.ham === ham).length >= so_luong) return true;
		await new Promise((r) => setTimeout(r, 20));
	}
	return false;
}

// Rào 2 — `cho_nhac_xong()`: chờ trong TRANG cho tới khi lượt hỏi bản cài đã được
// XỬ LÝ XONG, không phải chỉ "đã về tới".
//
// Mẹo ở đây là dùng chính cơ chế của sản phẩm: `hoi_ban_cai_moi()` GHI NHỚ lời
// hứa, nên gọi lại nó trả về ĐÚNG lời hứa mà `man_menu.ve()` đã gắn `.then()` lúc
// vẽ màn. `await` nó trong `page.evaluate` vì thế chỉ trở về SAU khi `.then()` của
// `man_menu` (đăng ký trước) đã chạy xong — tức sau khi dải nhắc đã được vẽ hoặc
// đã quyết định không vẽ. Đó là một BẤT BIẾN của hàng đợi microtask, không phải
// một khoảng thời gian đoán chừng.
//
// KHÔNG DÙNG ĐƯỢC cho ca lượt hỏi HỎNG: ở đó `hoi_ban_cai_moi()` tự quên lời hứa
// (xem `vo.js`), nên gọi lại sẽ BẮN THÊM một lời gọi mới và làm bẩn đúng phép đếm
// mà bài đang đo. Ca đó dùng `cho_quen_hen()` bên dưới.
async function cho_nhac_xong(page) {
	await page.evaluate(() => erpnext.kho_pda.KhoApp.hoi_ban_cai_moi());
}

// Rào 3 — cho ca lượt hỏi HỎNG: chờ tới lúc lời hứa đã bị QUÊN (`_hen_ban_cai`
// trở lại `null`). Đó là bước cuối cùng của chuỗi `.then()` trong
// `hoi_ban_cai_moi()`, nên tới được đó nghĩa là `.then()` của `man_menu` cũng đã
// chạy xong — cùng một bất biến hàng đợi, đọc bằng một trạng thái quan sát được.
async function cho_quen_hen(page, han_ms = 15000) {
	await page.waitForFunction(() => erpnext.kho_pda.KhoApp._hen_ban_cai === null, { timeout: han_ms });
}

async function do_app(browser, goc_gia, nhat_ky) {
	const ctx = await browser.newContext({ viewport: { width: 360, height: 640 } });
	const page = await ctx.newPage();
	const loi = [];
	page.on("pageerror", (e) => loi.push(String(e)));
	// TASK 5: `KHO_BO_QUA_DONG_BO_GIO` tắt lượt gọi `gio_may_chu` tự bắn ở
	// `khoi_dong()` — máy chủ giả dưới đây chỉ biết một tập đường dẫn liệt kê sẵn
	// (`HAM_OK`, `HAM_401`...), một lời gọi thật tới đường dẫn đó sẽ rơi vào nhánh
	// "đường dẫn LẠ" ở cuối file vì một lý do KHÔNG LIÊN QUAN tới thứ bài này đo.
	await page.addInitScript(
		script_khai({ KHO_MAY_CHU: goc_gia, KHO_LA_APP: true, KHO_BAN_THU: true, KHO_BO_QUA_DONG_BO_GIO: true })
	);
	try {
		await page.goto("file://" + TRANG_APP);
		await page.waitForSelector("#kho-app .kho-than", { timeout: 5000 });

		// 1. Dòng "Máy chủ:" phải nói địa chỉ THẬT, không phải `file://`.
		const chu_man_the = await page.evaluate(() => document.querySelector("#kho-app .kho-than").innerText);
		const trich = JSON.stringify(chu_man_the.slice(0, 160));
		khang_dinh(
			chu_man_the.includes(goc_gia),
			`APP · màn thẻ không in địa chỉ máy chủ thật (${goc_gia}) — đọc được: ${trich}`
		);
		khang_dinh(
			!chu_man_the.includes("file://"),
			"APP · màn thẻ vẫn in `file://` — dòng 'Máy chủ:' nói dối"
		);
		khang_dinh(
			chu_man_the.includes("BẢN THỬ"),
			"APP · KHO_BAN_THU = true mà màn thẻ không hiện dải 'BẢN THỬ'"
		);

		// 2. Lời gọi đi tới ĐỊA CHỈ TUYỆT ĐỐI, chưa có khoá → không header nào.
		//    (Trang ở `file://`: một đường tương đối KHÔNG THỂ tới được máy chủ này.)
		//
		// ĐẶT MỘT TOKEN CSRF KHÁC RỖNG TRƯỚC KHI GỌI — phép thử này đã từng KHÔNG
		// CẮN vì thiếu đúng dòng dưới đây: `shim.js` khai `frappe.csrf_token = ""`,
		// nên gỡ hẳn `!this._la_app() &&` khỏi nhánh gắn header vẫn cho ra một lời
		// gọi KHÔNG có header (chuỗi rỗng là falsy) và cổng vẫn xanh. Thứ cần khoá
		// là "nhánh CSRF bị chặn VÌ đang là app", không phải "token tình cờ rỗng".
		await page.evaluate(() => {
			frappe.csrf_token = "TOKEN-RAC-CUA-APP";
		});
		const truoc = nhat_ky.length;
		const ra = await page.evaluate(
			(ham) => erpnext.kho_pda.KhoApp.goi(ham, { a: 1 }).catch((e) => ({ loi: e.message })),
			HAM_OK
		);
		khang_dinh(
			ra && ra.ok === true,
			`APP · goi() không nhận được kết quả máy chủ: ${JSON.stringify(ra)}`
		);
		const g1 = tim_goi(nhat_ky, HAM_OK, truoc);
		khang_dinh(!!g1, "APP · máy chủ giả KHÔNG nhận được lời gọi nào — địa chỉ tuyệt đối chưa được dựng");
		if (g1) {
			khang_dinh(g1.duong_dan === `/api/method/${HAM_OK}`, `APP · đường dẫn sai: ${g1.duong_dan}`);
			khang_dinh(!g1.dau.authorization, "APP · chưa đặt khoá mà đã gửi Authorization");
			khang_dinh(
				!g1.dau["x-frappe-csrf-token"],
				"APP · gửi X-Frappe-CSRF-Token trong app — nhánh CSRF chưa bị bỏ qua khi KHO_LA_APP"
			);
			khang_dinh(g1.than === JSON.stringify({ a: 1 }), `APP · thân lời gọi sai: ${g1.than}`);
			// `Origin: null` = lời gọi xuất phát từ một trang `file://` và ĐÃ VƯỢT
			// SANG một nguồn khác. Đây là bằng chứng THỨ HAI (ngoài việc máy chủ giả
			// nhận được gì) rằng địa chỉ tuyệt đối đã được dựng: một đường tương đối
			// từ `file://` không bao giờ rời khỏi đĩa.
			khang_dinh(
				g1.origin === "null",
				`APP · Origin không phải "null" (${g1.origin}) — lời gọi không xuất phát từ trang file://`
			);
		}

		// 3. `dat_khoa()` → `Authorization: token <khoá>`; `xoa_khoa()` → không còn.
		const truoc2 = nhat_ky.length;
		await page.evaluate((ham) => {
			erpnext.kho_pda.KhoApp.dat_khoa("KHOAGIA123:BIMATGIA456");
			return erpnext.kho_pda.KhoApp.goi(ham).catch(() => null);
		}, HAM_OK);
		const g2 = tim_goi(nhat_ky, HAM_OK, truoc2);
		khang_dinh(
			g2 && g2.dau.authorization === "token KHOAGIA123:BIMATGIA456",
			`APP · Authorization sai sau dat_khoa(): ${g2 && g2.dau.authorization}`
		);

		const truoc3 = nhat_ky.length;
		await page.evaluate((ham) => {
			erpnext.kho_pda.KhoApp.xoa_khoa();
			return erpnext.kho_pda.KhoApp.goi(ham).catch(() => null);
		}, HAM_OK);
		const g3 = tim_goi(nhat_ky, HAM_OK, truoc3);
		khang_dinh(g3 && !g3.dau.authorization, "APP · xoa_khoa() rồi mà vẫn gửi Authorization");

		// 4. 401 → VỀ MÀN THẺ (không treo), và lời hứa bị TỪ CHỐI với câu máy chủ.
		//
		// Đứng ở màn MENU trước: `goi()` cố ý KHÔNG tự đá về màn thẻ khi đang ở
		// chính màn thẻ (đó là ca "thẻ vừa quét sai", một câu chuyện khác).
		await page.evaluate(() => {
			erpnext.kho_pda.KhoApp.la_khach = false;
			erpnext.kho_pda.KhoApp.di("menu");
		});
		// `di()` đổi `location.hash`; `hashchange` là sự kiện BẤT ĐỒNG BỘ nên phải
		// để trình duyệt chạy hết một nhịp rồi mới đọc `man_hien_tai` — cả trước lẫn
		// sau lời gọi. Không chờ là đo trúng trạng thái dở dang, không phải hồi quy.
		await page.waitForTimeout(200);
		const ket = await page.evaluate(
			(ham) =>
				erpnext.kho_pda.KhoApp.goi(ham).then(
					() => ({ trang_thai: "xong" }),
					(e) => ({ trang_thai: "loi", cau: e.message, ma: e.ma })
				),
			HAM_401
		);
		await page.waitForTimeout(300);
		const man_sau_401 = await page.evaluate(() => erpnext.kho_pda.KhoApp.man_hien_tai);
		khang_dinh(ket.trang_thai === "loi", "APP · 401 mà goi() không từ chối lời hứa (treo)");
		khang_dinh(ket.ma === 401, `APP · mã lỗi không phải 401: ${ket.ma}`);
		khang_dinh(ket.cau === "Thẻ không hợp lệ.", `APP · không đọc được câu máy chủ: ${ket.cau}`);
		khang_dinh(man_sau_401 === "the", `APP · 401 không đưa về màn thẻ (đang ở "${man_sau_401}")`);

		// ====================================================================
		// 5. TASK 4 — NHẬN MÁY MỘT LẦN: khoá cất BỀN, mã máy đi kèm, 401 giết khoá
		// ====================================================================
		//
		// Đây là phép đo chứng minh cả Task 4, và nó phải là phép đo HÀNH VI chứ
		// không phải đọc mã: thứ cần chứng minh là "TẢI LẠI TRANG rồi mà vẫn vào
		// thẳng menu". `pda_app/www/index.html` viết cứng `data-la_khach="1"`, nên
		// trước Task 4 lượt tải lại dưới đây CHẮC CHẮN rơi về màn thẻ — mục (d) là
		// cái cổng không thể xanh oan bằng cách đọc lại chính giá trị vừa ghi.
		const KHOA_THU = "KHOABEN789:BIMATBEN012";

		// (a) Dọn về trạng thái "máy chưa nhận" rồi ĐO LẠI, không tin là đã sạch.
		const sach = await page.evaluate(() => {
			erpnext.kho_pda.KhoApp.xoa_khoa();
			return {
				khoa: erpnext.kho_pda.KhoApp.khoa(),
				luu: localStorage.getItem("kho_pda.khoa"),
			};
		});
		khang_dinh(
			sach.khoa === "" && !sach.luu,
			`APP · xoa_khoa() không dọn sạch cả bộ nhớ lẫn kho lưu: ${JSON.stringify(sach)}`
		);

		// (b)+(c) Đặt khoá → lời gọi phải mang CẢ HAI header, và `X-Ma-May` phải
		//         BẰNG ĐÚNG `KhoApp.ma_may()` (không phải "một chuỗi nào đó").
		const truoc5 = nhat_ky.length;
		const may_truoc = await page.evaluate(
			(x) => {
				erpnext.kho_pda.KhoApp.dat_khoa(x.khoa);
				erpnext.kho_pda.KhoApp.dat_nguoi_dung("Thu kho thu");
				return erpnext.kho_pda.KhoApp.goi(x.ham)
					.catch(() => null)
					.then(() => erpnext.kho_pda.KhoApp.ma_may());
			},
			{ khoa: KHOA_THU, ham: HAM_OK }
		);
		const g5 = tim_goi(nhat_ky, HAM_OK, truoc5);
		khang_dinh(!!may_truoc, "APP · ma_may() trả rỗng — máy không tự khai được mình là ai");
		khang_dinh(
			g5 && g5.dau.authorization === "token " + KHOA_THU,
			`APP · Authorization sai: ${g5 && g5.dau.authorization}`
		);
		khang_dinh(
			g5 && g5.dau["x-ma-may"] === may_truoc,
			`APP · lời gọi MANG KHOÁ mà không mang đúng X-Ma-May (${g5 && g5.dau["x-ma-may"]} ≠ ${may_truoc}) — máy chủ trả 401 cho mọi lời gọi như thế`
		);
		// Đối chứng NGƯỢC: lời gọi KHÔNG mang khoá thì cũng không mang mã máy (lượt
		// 2 ở trên, lúc chưa `dat_khoa`). Không có vế này thì "có gửi X-Ma-May" có
		// thể chỉ là "gửi vô điều kiện", tức không chứng minh được nó đi theo khoá.
		khang_dinh(
			g1 && !g1.dau["x-ma-may"],
			`APP · gửi X-Ma-May cho một lời gọi KHÔNG có khoá: ${g1 && g1.dau["x-ma-may"]}`
		);

		// (d) MỞ LẠI TRANG TỪ ĐẦU — hình ảnh của "đóng app rồi chạm icon mở lại".
		//
		// `goto` chứ không `reload()`, và lý do là một khác biệt THẬT chứ không phải
		// cho tiện: `reload()` giữ nguyên `location.hash` của lượt trước (ở đây là
		// `#/the`, do phép đo 401 phía trên để lại), trong khi WebView của app mở lên
		// luôn nạp `index.html` TRẦN — Capacitor nạp địa chỉ khởi động, không khôi
		// phục URL cũ. Đo bằng `reload()` ở đây là đo một tình huống không tồn tại
		// trên máy thật. (Lượt `reload()` giữa ca — thứ brief Task 4 gọi là "tải lại
		// trang" — được đo trong kịch bản đi–về thật, ở đó màn đang đứng là "menu".)
		await page.goto("file://" + TRANG_APP);
		await page.waitForSelector("#kho-app .kho-than", { timeout: 5000 });
		await page.waitForTimeout(200);
		const sau_tai_lai = await page.evaluate(() => ({
			man: erpnext.kho_pda.KhoApp.man_hien_tai,
			khoa: erpnext.kho_pda.KhoApp.khoa(),
			nguoi_dung: erpnext.kho_pda.KhoApp.nguoi_dung,
			la_khach: erpnext.kho_pda.KhoApp.la_khach,
			ma_may: erpnext.kho_pda.KhoApp.ma_may(),
			co_o_quet: !!document.querySelector("#kho-app .man-the-o"),
			co_menu: !!document.querySelector("#kho-app .kho-menu-luoi"),
		}));
		khang_dinh(
			sau_tai_lai.man === "menu" && sau_tai_lai.co_menu && !sau_tai_lai.co_o_quet,
			`APP · tải lại trang mà KHÔNG vào thẳng menu (màn "${sau_tai_lai.man}", ô quét thẻ hiện: ${sau_tai_lai.co_o_quet}) — mục tiêu "chạm icon vào thẳng menu" chưa đạt`
		);
		khang_dinh(
			sau_tai_lai.khoa === KHOA_THU && sau_tai_lai.la_khach === false,
			`APP · khoá máy không sống qua lượt tải lại: ${JSON.stringify(sau_tai_lai)}`
		);
		khang_dinh(
			sau_tai_lai.nguoi_dung === "Thu kho thu",
			`APP · tên người cầm máy không sống qua lượt tải lại: "${sau_tai_lai.nguoi_dung}"`
		);
		khang_dinh(
			sau_tai_lai.ma_may === may_truoc,
			`APP · mã máy ĐỔI sau khi tải lại (${may_truoc} → ${sau_tai_lai.ma_may}) — mỗi lần mở app sẽ là một chiếc máy mới`
		);

		// (d2) NÚT "ĐĂNG XUẤT" — TỪ TASK 4 ĐÂY LÀ ĐƯỜNG TRẢ MÁY DUY NHẤT.
		//
		// Khi khoá đã cất, app mở lên là vào thẳng menu; nên lúc thủ kho A giao máy cho
		// thủ kho B đổi ca, nút này là chỗ DUY NHẤT đưa được về màn quét thẻ. Nó không
		// phải một nút trang trí, và trước lượt đo này nó chỉ được canh bằng một bài
		// test TĨNH đọc mã — đúng hai chữ ("chỉ tĩnh") đã bị bắt bốn lần trong đợt này.
		//
		// Bấm ĐÚNG CÁI NÚT trong DOM, không gọi hàm nội bộ. `location.reload()` trong
		// trình xử lý sẽ nạp lại trang, nên đọc kho lưu NGAY SAU lượt bấm (trước khi
		// trang kịp thay) không chắc chắn — đo sau khi trang đã ổn định lại, và điều
		// phải đúng ở cả hai thời điểm là như nhau: khoá đã chết trong kho lưu.
		await page.evaluate((x) => {
			erpnext.kho_pda.KhoApp.dat_khoa(x.khoa);
			erpnext.kho_pda.KhoApp.dat_nguoi_dung("Thu kho thu");
			erpnext.kho_pda.KhoApp.la_khach = false;
			erpnext.kho_pda.KhoApp.di("menu");
		}, { khoa: KHOA_THU });
		await page.waitForTimeout(250);
		await page.click("#kho-app .kho-menu-dang-xuat");
		await page.waitForTimeout(800);
		await page.waitForSelector("#kho-app .kho-than", { timeout: 5000 });
		const sau_dang_xuat = await page.evaluate(() => ({
			man: erpnext.kho_pda.KhoApp.man_hien_tai,
			khoa: erpnext.kho_pda.KhoApp.khoa(),
			luu_khoa: localStorage.getItem("kho_pda.khoa"),
			luu_ma_may: localStorage.getItem("kho_pda.ma_may"),
			co_o_quet: !!document.querySelector("#kho-app .man-the-o"),
		}));
		khang_dinh(
			sau_dang_xuat.khoa === "" && !sau_dang_xuat.luu_khoa,
			`APP · bấm "Đăng xuất" mà khoá máy vẫn sống: ${JSON.stringify(sau_dang_xuat)} — nút trả máy không trả gì`
		);
		khang_dinh(
			sau_dang_xuat.man === "the" && sau_dang_xuat.co_o_quet,
			`APP · sau "Đăng xuất" không về màn quét thẻ: ${JSON.stringify(sau_dang_xuat)} — người nhận ca không có đường vào`
		);
		khang_dinh(
			sau_dang_xuat.luu_ma_may === may_truoc,
			`APP · "Đăng xuất" xoá luôn mã máy (${sau_dang_xuat.luu_ma_may}) — đổi ca là chiếc máy đó thành một máy khác trong sổ`
		);

		// Dựng lại trạng thái "đã nhận máy" cho phép đo (e) bên dưới.
		await page.evaluate((x) => {
			erpnext.kho_pda.KhoApp.dat_khoa(x.khoa);
			erpnext.kho_pda.KhoApp.la_khach = false;
			erpnext.kho_pda.KhoApp.di("menu");
		}, { khoa: KHOA_THU });
		await page.waitForTimeout(250);

		// (e) THU HỒI: máy chủ trả 401 → khoá phải chết CẢ TRONG KHO LƯU, không chỉ
		//     trong bộ nhớ. Chỉ xoá trong bộ nhớ thì lượt mở app sau nạp lại đúng
		//     chiếc khoá đã chết và máy kẹt vĩnh viễn ở vòng "vào menu → 401".
		await page.evaluate((ham) => erpnext.kho_pda.KhoApp.goi(ham).catch(() => null), HAM_401);
		await page.waitForTimeout(300);
		const sau_401 = await page.evaluate(() => ({
			man: erpnext.kho_pda.KhoApp.man_hien_tai,
			khoa: erpnext.kho_pda.KhoApp.khoa(),
			la_khach: erpnext.kho_pda.KhoApp.la_khach,
			luu_khoa: localStorage.getItem("kho_pda.khoa"),
			luu_ma_may: localStorage.getItem("kho_pda.ma_may"),
			// Dải báo của `goi()`. `_giu_bao` sinh ra để câu này SỐNG QUA lượt vẽ mà
			// `di("the")` gây ra; nếu nó bị lượt vẽ xoá thì thủ kho bị đá về màn quét
			// thẻ mà KHÔNG MỘT CHỮ giải thích — một cái bật lùi không lời.
			bao: (document.querySelector("#kho-app .kho-bao") || {}).textContent || "",
		}));
		khang_dinh(
			sau_401.khoa === "" && !sau_401.luu_khoa,
			`APP · 401 KHÔNG giết được khoá đã cất: ${JSON.stringify(sau_401)}`
		);
		khang_dinh(sau_401.man === "the", `APP · 401 sau thu hồi không đưa về màn thẻ ("${sau_401.man}")`);
		khang_dinh(
			!!sau_401.bao.trim(),
			"APP · bị đá về màn quét thẻ mà dải báo RỖNG — thủ kho không có một chữ nào giải thích"
		);
		// VÒNG SỬA 1, MỤC F — dải báo phải nói ĐÚNG NGUYÊN NHÂN. Trong app 401 nghĩa là
		// khoá máy bị thu hồi, KHÔNG phải phiên hết hạn; câu "Phiên đã hết — quét thẻ để
		// làm tiếp." đẩy thủ kho đi quét lại đúng tấm thẻ vừa bị thu hồi rồi thất bại
		// lần nữa, mà không biết phải gọi trưởng kho. Máy chủ giả trả `HAM_401` với câu
		// "Thẻ không hợp lệ." nên đây là câu phải tới dải báo — điểm cần đo là dải báo
		// dùng CÂU CỦA MÁY CHỦ, không phải một chuỗi viết cứng.
		khang_dinh(
			sau_401.bao.includes("Thẻ không hợp lệ."),
			`APP · dải báo không nói nguyên nhân máy chủ trả về: ${JSON.stringify(sau_401.bao)}`
		);
		khang_dinh(
			!sau_401.bao.includes("Phiên đã hết"),
			`APP · dải báo vẫn nói "Phiên đã hết" trong app — app không có phiên nào để hết: ${JSON.stringify(sau_401.bao)}`
		);
		khang_dinh(sau_401.la_khach === true, "APP · 401 xoá khoá rồi mà `la_khach` vẫn false — bấm Back là vào lại menu");
		// Mã máy PHẢI SỐNG qua lượt thu hồi: `_ghi_thiet_bi` (the_pda.py) upsert theo
		// `ma_may`, nên một mã mới sau mỗi lần thu hồi là bảng `PDA Thiet Bi` mọc thêm
		// một dòng cho CÙNG một chiếc máy — đúng cái điều bảng đó sinh ra để chặn.
		khang_dinh(
			sau_401.luu_ma_may === may_truoc,
			`APP · thu hồi xoá luôn MÃ MÁY (${sau_401.luu_ma_may}) — chiếc máy này quét thẻ lại sẽ thành một chiếc máy khác trong sổ`
		);

		// (f) Mở lại app sau khi bị thu hồi → màn thẻ, đúng nơi thủ kho quét lại.
		await page.goto("file://" + TRANG_APP);
		await page.waitForSelector("#kho-app .kho-than", { timeout: 5000 });
		await page.waitForTimeout(200);
		const sau_thu_hoi_mo_lai = await page.evaluate(() => ({
			man: erpnext.kho_pda.KhoApp.man_hien_tai,
			co_o_quet: !!document.querySelector("#kho-app .man-the-o"),
		}));
		khang_dinh(
			sau_thu_hoi_mo_lai.man === "the" && sau_thu_hoi_mo_lai.co_o_quet,
			`APP · sau thu hồi, mở lại app KHÔNG ra màn quét thẻ: ${JSON.stringify(sau_thu_hoi_mo_lai)}`
		);

		loi.push(...(await page.evaluate(() => window.__loi_async.slice())));
		if (loi.length) sai.push(`APP · lỗi JS: ${loi.slice(0, 3).join(" | ")}`);
	} finally {
		await ctx.close();
	}
}

// ============================================================================
// TASK 2B — ĐƯỜNG CẦU HTTP NATIVE (`CapacitorHttp`)
// ============================================================================
//
// VÌ SAO PHẢI ĐO RIÊNG ĐƯỜNG NÀY: `capacitor.config.json` bật `CapacitorHttp`, và
// nó VÁ `window.fetch`. Từ lúc đó, `Response` mà `goi()` đọc KHÔNG còn do trình
// duyệt dựng nữa mà do mã của Capacitor dựng bằng `new Response(data, {...})`
// (`native-bridge.js`, nhánh `doPatchHttp`). `goi()` đọc đúng BA thứ của đối
// tượng đó — `res.ok`, `res.status`, `res.json()` — nên "cầu native là trong
// suốt" là một GIẢ THIẾT, và giả thiết đó phải bị đo, không được tin.
//
// CÁCH DỰNG CHO TRUNG THỰC: nạp ĐÚNG file `native-bridge.js` của
// `@capacitor/android` đang cài (cùng file Capacitor tiêm vào WebView thật), khai
// trước ba toàn cục mà nó đọc để tự nhận là đang chạy trên Android với
// `CapacitorHttp` bật, rồi thay ĐÚNG MỘT MẮT XÍCH: lớp Java. Lớp Java được thay
// bằng một hàm Node thực hiện lời gọi HTTP thật rồi trả về đúng hình dạng mà
// `HttpRequestHandler.buildResponse` trả (`{status, headers, url, data}` —
// `HttpRequestHandler.java:214-222`), với `data` đã được phân tích thành đối
// tượng khi máy chủ nói `application/json` (`readData`). Mọi thứ còn lại —
// `convertBody`, `cap.toNative`/`fromNative`, và nhất là khối dựng `Response` —
// là mã THẬT của Capacitor.
//
// BA TOÀN CỤC PHẢI KHAI TRƯỚC (đọc thẳng từ `native-bridge.js`, không theo trí nhớ):
//   `androidBridge`                → `getPlatformId()` trả "android" (dòng ~161)
//   `CapacitorHttpAndroidInterface.isEnabled()` → `doPatchHttp = true` (dòng ~491)
//   `WEBVIEW_SERVER_URL`           → `cap.getServerUrl()` (dòng ~824)
//
// `WEBVIEW_SERVER_URL` PHẢI LÀ `https://localhost` — đúng giá trị của một APK khai
// `androidScheme: "https"` và KHÔNG khai `server.url`. Nhánh ĐẦU của `fetch` đã vá là
//     if (request.url.startsWith(`${cap.getServerUrl()}/`)) return CapacitorWebFetch(...)
// nên một giá trị trùng tiền tố với máy chủ đang gọi làm MỌI lời gọi lặng lẽ rơi
// về `fetch` THƯỜNG, và cả hàm này báo xanh trong khi không đo gì. ĐÃ ĐO: đặt
// `WEBVIEW_SERVER_URL` = địa chỉ máy chủ giả thì bộ đếm đứng ở 0 (xem báo cáo
// Task 2B). Đó đúng hạng lỗi người soát Task 2 đã bắt ở `kiem_ban_dong_goi.js`
// ("xanh 4/4 kể cả khi `goi()` gọi vào hư không").
//
// VÌ VẬY khẳng định NỀN của đường này là một BỘ ĐẾM: số lần lớp native thật sự
// được gọi phải bằng số lời gọi đã phát ra. Không có bộ đếm đó thì mọi khẳng
// định phía sau không chứng minh được gì. (Một giá trị RỖNG thì ngược lại KHÔNG
// gây rơi — `"http://…".startsWith("/")` là sai — nên phép so `=== "https://localhost"`
// bên dưới là để khoá đúng môi trường, còn bộ đếm mới là cái bắt lỗi thật.)
async function do_qua_cau_native(browser, goc_gia, nhat_ky) {
	const ctx = await browser.newContext({ viewport: { width: 360, height: 640 } });
	const page = await ctx.newPage();
	const loi = [];
	const canh_bao = [];
	page.on("pageerror", (e) => loi.push(String(e)));
	page.on("console", (m) => {
		if (m.type() === "warning") canh_bao.push(m.text());
	});

	// Nhật ký của LỚP NATIVE GIẢ: mỗi phần tử là đối số mà `native-bridge.js` giao
	// xuống Java. Đây là chỗ đọc được "cầu native chuyển tiếp CÁI GÌ" — và cũng là
	// chỗ đọc được nó KHÔNG chuyển tiếp cái gì (`credentials`).
	const goi_native = [];

	// Lớp Java giả. Chạy trong Node (ngoài trình duyệt) nên KHÔNG có luật cùng
	// nguồn và KHÔNG có kho cookie của trang — đúng như `HttpURLConnection` trong
	// APK thật.
	await page.exposeFunction("__java_gia_request", async (tuy_chon) => {
		goi_native.push(tuy_chon);
		const u = new URL(tuy_chon.url);
		const than =
			typeof tuy_chon.data === "string" ? tuy_chon.data : tuy_chon.data == null ? "" : JSON.stringify(tuy_chon.data);
		return await new Promise((ok, hong) => {
			const req = http.request(
				{
					hostname: u.hostname,
					port: u.port,
					path: u.pathname + u.search,
					method: tuy_chon.method,
					headers: Object.assign({}, tuy_chon.headers, { "Content-Length": Buffer.byteLength(than) }),
				},
				(res) => {
					let ra = "";
					res.on("data", (m) => (ra += m));
					res.on("end", () => {
						const kieu = res.headers["content-type"] || "";
						// `HttpRequestHandler.readData`: máy chủ nói JSON thì lớp
						// Java PHÂN TÍCH sẵn thành đối tượng; ngược lại trả văn bản
						// thô. Chính bước này là chỗ `res.json()` của `goi()` có thể
						// đổi hành vi, nên phải mô phỏng đúng.
						let du_lieu = ra;
						if (kieu.startsWith("application/json")) {
							try {
								du_lieu = JSON.parse(ra);
							} catch (e) {
								du_lieu = ra;
							}
						}
						ok({ status: res.statusCode, headers: res.headers, url: tuy_chon.url, data: du_lieu });
					});
				}
			);
			req.on("error", (e) => hong(new Error(String(e.message))));
			req.end(than);
		});
	});

	const ma_cau = fs.readFileSync(NATIVE_BRIDGE, "utf-8");
	await page.addInitScript(`
		(function () {
			// TASK 5: cùng lý do đã ghi ở \`do_app\` — máy chủ giả không biết đường dẫn
			// \`gio_may_chu\`, và bộ đếm \`__dem_native\`/\`goi_native\` của bài này phải
			// chỉ đếm những lời gọi CHÍNH BÀI phát ra, không lẫn một lượt tự đồng bộ.
			var V = ${JSON.stringify({ KHO_MAY_CHU: goc_gia, KHO_LA_APP: true, KHO_BO_QUA_DONG_BO_GIO: true })};
			Object.keys(V).forEach(function (ten) {
				Object.defineProperty(window, ten, {
					configurable: true,
					get: function () { return V[ten]; },
					set: function () {},
				});
			});
			window.__loi_async = [];
			window.addEventListener("unhandledrejection", function (e) {
				window.__loi_async.push(String((e.reason && e.reason.stack) || e.reason));
			});

			// Ba toàn cục của môi trường Android — xem chú thích ở hàm gọi.
			window.WEBVIEW_SERVER_URL = "https://localhost";
			window.CapacitorHttpAndroidInterface = { isEnabled: function () { return true; } };
			window.__dem_native = 0;
			window.androidBridge = {
				postMessage: function (chuoi) {
					var tin = JSON.parse(chuoi);
					if (tin.pluginId !== "CapacitorHttp" || tin.methodName !== "request") return;
					window.__dem_native += 1;
					window.__java_gia_request(tin.options).then(
						function (ket) {
							window.Capacitor.fromNative({
								callbackId: tin.callbackId,
								pluginId: tin.pluginId,
								methodName: tin.methodName,
								success: true,
								data: ket,
							});
						},
						function (e) {
							window.Capacitor.fromNative({
								callbackId: tin.callbackId,
								pluginId: tin.pluginId,
								methodName: tin.methodName,
								success: false,
								error: { message: String(e && e.message) },
							});
						}
					);
				},
			};
		})();
		${ma_cau}
	`);

	// TASK 6 — ĐƯỜNG DUY NHẤT APK THẬT ĐI. Đo được (báo cáo §8): từ `file://`,
	// `fetch` THƯỜNG tới máy chủ khác nguồn bị CORS chặn, nên trên máy thật lời gọi
	// `ban_cai_moi_nhat` CHỈ đi qua cầu native. `do_nhac_ban_moi` đo toàn bộ dải
	// nhắc trên đường `fetch` thường — đúng ca mà Ruling 11 sinh ra để chặn
	// ("nghiệm thu trên một đường mà APK phát hành không bao giờ đi"). Đặt tên bản
	// cài MỚI HƠN ngay từ đây để lượt vẽ menu ở mục 4 bật dải nhắc.
	//: Khoá dùng cho phép đo N2 ở mục 5b — đặt riêng để phân biệt với khoá của các
	//: mục khác trong cùng hàm.
	const KHOA_403 = "KHOA403AA:BIMAT403BB";
	const TEN_BAN_CAI_CU = ten_ban_cai_gia;
	ten_ban_cai_gia = "miyano-pda-9.9-release.apk";

	try {
		await page.goto("file://" + TRANG_APP);
		await page.waitForSelector("#kho-app .kho-than", { timeout: 5000 });

		// 0. CẦU ĐÃ VÁ THẬT CHƯA. Không có phép này thì cả hàm có thể đang đo
		//    `fetch` thường.
		const trang_thai_cau = await page.evaluate(() => ({
			nen: window.Capacitor && window.Capacitor.getPlatform(),
			goc_may_chu: window.Capacitor && window.Capacitor.getServerUrl(),
			da_va: typeof window.CapacitorWebFetch === "function" && window.fetch !== window.CapacitorWebFetch,
		}));
		khang_dinh(trang_thai_cau.nen === "android", `NATIVE · Capacitor không nhận là android: ${trang_thai_cau.nen}`);
		khang_dinh(
			trang_thai_cau.goc_may_chu === "https://localhost",
			`NATIVE · getServerUrl() sai (${trang_thai_cau.goc_may_chu}) — tiền tố rỗng sẽ đẩy MỌI lời gọi về fetch thường`
		);
		khang_dinh(trang_thai_cau.da_va, "NATIVE · window.fetch CHƯA bị vá — cả bài này đang đo fetch thường");

		// 1. BA THỨ `goi()` ĐỌC, ĐO TRỰC TIẾP TRÊN `Response` DO CAPACITOR DỰNG.
		//    Gọi bằng ĐÚNG bộ tuỳ chọn của `goi()` (POST + Content-Type JSON +
		//    credentials same-origin + thân JSON.stringify).
		const truoc_dem = await page.evaluate(() => window.__dem_native);
		const hinh_dang = await page.evaluate(
			async (x) => {
				const res = await fetch(`${x.goc}/api/method/${x.ham}`, {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					credentials: "same-origin",
					body: JSON.stringify({ a: 1 }),
				});
				const than = await res.json();
				return {
					la_Response: res instanceof Response,
					ok: res.ok,
					status: res.status,
					co_json: typeof res.json === "function",
					than: than,
					kieu_than: typeof than,
				};
			},
			{ goc: goc_gia, ham: HAM_OK }
		);
		const dem1 = await page.evaluate(() => window.__dem_native);
		khang_dinh(
			dem1 === truoc_dem + 1,
			`NATIVE · lớp native KHÔNG được gọi (đếm ${truoc_dem} → ${dem1}) — lời gọi đã đi bằng fetch thường, mọi phép đo dưới đây vô nghĩa`
		);
		khang_dinh(hinh_dang.la_Response, "NATIVE · thứ fetch trả về KHÔNG phải một Response");
		khang_dinh(hinh_dang.ok === true, `NATIVE · res.ok sai với 200: ${hinh_dang.ok}`);
		khang_dinh(hinh_dang.status === 200, `NATIVE · res.status sai với 200: ${hinh_dang.status}`);
		khang_dinh(hinh_dang.co_json, "NATIVE · Response không có res.json()");
		khang_dinh(
			hinh_dang.kieu_than === "object" && hinh_dang.than && hinh_dang.than.message && hinh_dang.than.message.ok === true,
			`NATIVE · res.json() không trả đúng thân máy chủ: ${JSON.stringify(hinh_dang.than)}`
		);
		const g_native = goi_native[goi_native.length - 1];
		khang_dinh(
			g_native && g_native.method === "POST",
			`NATIVE · lớp native nhận method sai: ${g_native && g_native.method} — GET/HEAD/OPTIONS đi đường proxy, KHÔNG đi native`
		);
		khang_dinh(
			g_native && g_native.url === `${goc_gia}/api/method/${HAM_OK}`,
			`NATIVE · địa chỉ giao xuống native sai: ${g_native && g_native.url}`
		);

		// 2. `credentials` LÀ VÔ HIỆU QUA CẦU NATIVE — đo bằng danh sách đối số mà
		//    `native-bridge.js` thật sự giao xuống Java, không suy luận.
		khang_dinh(
			g_native && !("credentials" in g_native),
			`NATIVE · cầu native có chuyển tiếp "credentials"? khoá nhận được: ${g_native && Object.keys(g_native).join(",")}`
		);

		// 3. CA COOKIE. Đặt một cookie THẬT cho nguồn của máy chủ giả (hình ảnh của
		//    một phiên WebView đời cũ còn sót trong máy), rồi gọi qua cầu native và
		//    xem máy chủ có nhận `Cookie` không.
		//
		//    ĐỐI CHỨNG DƯƠNG nằm ở nửa WEB (`do_web`): ở đó cùng một cookie này
		//    ĐƯỢC gửi. Không có đối chứng thì "không thấy cookie" có thể chỉ nghĩa
		//    là cookie chưa từng được đặt.
		await ctx.addCookies([
			{ name: "sid", value: "PHIEN-WEBVIEW-CU-9988", url: goc_gia },
		]);
		const cookie_da_dat = (await ctx.cookies(goc_gia)).map((c) => c.name);
		khang_dinh(
			cookie_da_dat.includes("sid"),
			`NATIVE · không đặt được cookie "sid" cho ${goc_gia} — ca cookie chưa đo được gì (thấy: ${cookie_da_dat.join(",")})`
		);
		const truoc_ck = nhat_ky.length;
		await page.evaluate((ham) => erpnext.kho_pda.KhoApp.goi(ham, { a: 1 }).catch(() => null), HAM_OK);
		const g_ck = tim_goi(nhat_ky, HAM_OK, truoc_ck);
		khang_dinh(!!g_ck, "NATIVE · máy chủ giả không nhận được lời gọi của ca cookie");
		khang_dinh(
			g_ck && !g_ck.dau.cookie,
			`NATIVE · lời gọi qua cầu native MANG THEO cookie của phiên WebView cũ: ${g_ck && g_ck.dau.cookie}`
		);

		// 3b. TASK 4 — `X-Ma-May` PHẢI XUỐNG TỚI LỚP JAVA. Đây là đường mà APK phát
		//     hành thật sự đi: cầu native tự dựng lấy lời gọi HTTP, nên một header
		//     `goi()` gắn đúng vẫn có thể rơi mất ở khúc `convertBody`/`toNative` —
		//     phải đọc trên danh sách đối số giao xuống Java, không suy luận.
		const truoc_mm = goi_native.length;
		const mm = await page.evaluate((ham) => {
			erpnext.kho_pda.KhoApp.dat_khoa("KHOANATIVE11:BIMATNATIVE22");
			return erpnext.kho_pda.KhoApp.goi(ham)
				.catch(() => null)
				.then(() => erpnext.kho_pda.KhoApp.ma_may());
		}, HAM_OK);
		const g_mm = goi_native[truoc_mm];
		// `native-bridge.js` chuẩn hoá tên header về chữ thường ở khúc dựng
		// `options.headers` — đọc cả hai cách viết để bài này đo NỘI DUNG chứ không
		// đo một chi tiết viết hoa của Capacitor.
		const doc_dau = (g, ten) =>
			(g && g.headers && (g.headers[ten] || g.headers[ten.toLowerCase()])) || "";
		const dau_mm = doc_dau(g_mm, "X-Ma-May");
		khang_dinh(
			!!g_mm && dau_mm === mm && !!mm,
			`NATIVE · cầu native KHÔNG chuyển tiếp X-Ma-May (${dau_mm} ≠ ${mm}) — máy chủ 401 mọi lời gọi của máy thật`
		);
		khang_dinh(
			doc_dau(g_mm, "Authorization") === "token KHOANATIVE11:BIMATNATIVE22",
			`NATIVE · Authorization không xuống tới lớp Java: ${doc_dau(g_mm, "Authorization")} (khoá header: ${g_mm && Object.keys(g_mm.headers || {}).join(",")})`
		);
		// Trả về trạng thái "chưa nhận máy" để phép đo 401 phía dưới vẫn đo đúng
		// thứ nó vẫn đo (401 với máy CHƯA có khoá), không lẫn với đường thu hồi.
		await page.evaluate(() => erpnext.kho_pda.KhoApp.xoa_khoa());

		// 4. `goi()` CHẠY TRỌN VẸN QUA CẦU: 200 trả `message`, 401 ném lỗi mang mã
		//    và ĐƯA VỀ MÀN THẺ. Đây là phép đo "ba thứ kia ghép lại vẫn đúng".
		await page.evaluate(() => {
			erpnext.kho_pda.KhoApp.la_khach = false;
			erpnext.kho_pda.KhoApp.di("menu");
		});
		// TẤT ĐỊNH (V3): chờ lớp native ghi nhận lời gọi, rồi chờ trang xử lý xong.
		{
			const het = Date.now() + 15000;
			while (
				Date.now() < het &&
				!goi_native.some((g) => String(g.url || "").endsWith(HAM_BAN_CAI))
			) {
				await new Promise((r) => setTimeout(r, 20));
			}
		}
		await cho_nhac_xong(page);

		// 4b. TASK 6 — DẢI NHẮC BẢN MỚI, ĐO TRÊN CẦU NATIVE.
		//
		// Hai khẳng định đo hai thứ khác nhau: lời gọi có XUỐNG TỚI lớp Java không
		// (đọc trên danh sách đối số giao xuống, theo TÊN đường dẫn — bộ đếm tổng ở
		// mục 8 không phân biệt được lời gọi nào), và dải có VẼ RA không (một
		// `Response` do Capacitor dựng đi thêm một vòng phân tích JSON; `ten` tới
		// nơi méo là dải im mà không ai biết).
		const g_ban_cai = goi_native.filter((g) => String(g.url || "").endsWith(HAM_BAN_CAI));
		khang_dinh(
			g_ban_cai.length === 1,
			`NATIVE · ${HAM_BAN_CAI} xuống lớp Java ${g_ban_cai.length} lần (phải đúng 1) — dải nhắc bản mới đang đi một đường mà APK thật KHÔNG đi`
		);
		const dai_native = await page.evaluate(() => {
			const el = document.querySelector(".kho-ban-moi");
			const nut = document.querySelector(".kho-ban-moi-nut");
			return { co: !!el, chu: el ? el.textContent : "", href: nut ? nut.getAttribute("href") : null };
		});
		khang_dinh(
			dai_native.co && dai_native.chu.includes("9.9") && dai_native.href === `${goc_gia}/tai-app`,
			`NATIVE · dải nhắc bản mới KHÔNG vẽ đúng qua cầu native: ${JSON.stringify(dai_native)}`
		);

		const ket401 = await page.evaluate(
			(ham) =>
				erpnext.kho_pda.KhoApp.goi(ham).then(
					() => ({ trang_thai: "xong" }),
					(e) => ({ trang_thai: "loi", cau: e.message, ma: e.ma })
				),
			HAM_401
		);
		await page.waitForTimeout(300);
		const man_sau_401 = await page.evaluate(() => erpnext.kho_pda.KhoApp.man_hien_tai);
		khang_dinh(ket401.trang_thai === "loi", "NATIVE · 401 mà goi() không từ chối lời hứa (treo)");
		khang_dinh(ket401.ma === 401, `NATIVE · mã lỗi không phải 401 qua cầu native: ${ket401.ma}`);
		// `_server_messages` là một chuỗi JSON NẰM TRONG một JSON. Qua cầu native nó
		// đi thêm một vòng: Java phân tích → `JSON.stringify` → `res.json()` phân
		// tích lại. Câu này tới nơi nguyên vẹn là bằng chứng vòng đó không làm hỏng
		// gì.
		khang_dinh(
			ket401.cau === "Thẻ không hợp lệ.",
			`NATIVE · câu máy chủ không sống sót qua vòng phân tích của cầu native: ${ket401.cau}`
		);
		khang_dinh(man_sau_401 === "the", `NATIVE · 401 không đưa về màn thẻ (đang ở "${man_sau_401}")`);

		// 5. TASK 2B — CÂU LỖI HTML KHÔNG ĐƯỢC RA MÀN HÌNH.
		//
		// Dựng lại trạng thái "máy ĐÃ NHẬN, đang đứng ở menu" trước lượt 403: mục 5b
		// bên dưới đo xem lượt 403 có giết chiếc khoá này không, nên phải có một
		// chiếc khoá THẬT để giết (lượt 401 ở mục 4 vừa dọn sạch).
		await page.evaluate((x) => {
			erpnext.kho_pda.KhoApp.dat_khoa(x);
			erpnext.kho_pda.KhoApp.la_khach = false;
			erpnext.kho_pda.KhoApp.di("menu");
		}, KHOA_403);
		await page.waitForTimeout(250);
		const truoc_warn = canh_bao.length;
		const ket_html = await page.evaluate(
			(ham) => erpnext.kho_pda.KhoApp.goi(ham).then(() => null, (e) => ({ cau: e.message, ma: e.ma })),
			HAM_LOI_HTML
		);
		await page.waitForTimeout(200);
		khang_dinh(
			ket_html && ket_html.cau === CAU_KHONG_DU_QUYEN,
			`NATIVE · 403 HTML không ra câu tiếng Việt nói được việc phải làm: ${JSON.stringify(ket_html && ket_html.cau)}`
		);
		khang_dinh(
			ket_html && !/<[a-zA-Z!]/.test(ket_html.cau),
			"NATIVE · vẫn để lọt thẻ HTML ra tay người dùng"
		);
		khang_dinh(
			canh_bao.slice(truoc_warn).some((c) => c.includes("not whitelisted")),
			`NATIVE · câu HTML bị nuốt MẤT HẲN — người gỡ lỗi không còn chẩn đoán thật (console.warn thấy: ${JSON.stringify(canh_bao.slice(truoc_warn))})`
		);

		// 5b. VÒNG SỬA CUỐI (soát tổng, N2) — 403 NGHIỆP VỤ KHÔNG ĐƯỢC GIẾT KHOÁ MÁY.
		//
		// KHẲNG ĐỊNH QUYẾT ĐỊNH của cả mục N2, và nó phải nằm ở nửa NATIVE vì đó là
		// đường APK thật đi. Lượt 403 ngay trên (`HAM_LOI_HTML`) mang đúng hình dạng
		// máy chủ thật trả cho một lỗi QUYỀN: 403 + `exc_type: "PermissionError"`.
		//
		// TRƯỚC BẢN VÁ: `goi()` xoá khoá với MỌI 401/403 → chiếc khoá biến khỏi
		// `localStorage` và máy về màn quét thẻ. Hậu quả thật, không giả định: bản vá
		// 24/09 trong `selling_controller.py` là để chữa đúng một `PermissionError`
		// mà thủ kho ăn MỖI LẦN lưu phiếu giao trên màn Lấy hàng. Một lỗi quyền kiểu
		// đó quay lại là CẢ KHO mất khoá cùng lúc, phải đi lấy lại thẻ giấy — mà
		// chính đợt này khuyến khích cất thẻ đi sau khi nhận máy.
		//
		// Ba vế, đo ba thứ khác nhau: khoá còn trong bộ nhớ, khoá còn trong KHO LƯU
		// (thứ quyết định lượt mở app sau), và màn hình KHÔNG bị đá về "the".
		const sau_403 = await page.evaluate(() => ({
			khoa: erpnext.kho_pda.KhoApp.khoa(),
			luu: localStorage.getItem("kho_pda.khoa"),
			man: erpnext.kho_pda.KhoApp.man_hien_tai,
			la_khach: erpnext.kho_pda.KhoApp.la_khach,
		}));
		khang_dinh(
			sau_403.khoa === KHOA_403 && sau_403.luu === KHOA_403,
			`NATIVE · 403 NGHIỆP VỤ đã GIẾT khoá máy: ${JSON.stringify(sau_403)} — một lỗi quyền của máy chủ làm cả kho mất khoá cùng lúc (N2)`
		);
		khang_dinh(
			sau_403.man === "menu" && sau_403.la_khach === false,
			`NATIVE · 403 NGHIỆP VỤ đá thủ kho về màn quét thẻ: ${JSON.stringify(sau_403)} — bỏ dở phiếu đang làm để quét một tấm thẻ chẳng chữa được gì`
		);
		// ĐỐI CHỨNG DƯƠNG (nằm ở mục 7 bên dưới): cùng chiếc khoá ấy, một lượt **401**
		// PHẢI giết nó. Không có vế này thì "403 không giết khoá" có thể chỉ nghĩa là
		// đường giết khoá đã hỏng hẳn.

		// 6. Một trang 500 HTML (thân KHÔNG phải JSON) — cùng một LỚP lỗi.
		const ket500 = await page.evaluate(
			(ham) => erpnext.kho_pda.KhoApp.goi(ham).then(() => null, (e) => ({ cau: e.message, ma: e.ma })),
			HAM_TRANG_500
		);
		khang_dinh(ket500 && ket500.ma === 500, `NATIVE · 500 không giữ được mã: ${ket500 && ket500.ma}`);
		khang_dinh(
			ket500 && ket500.cau === CAU_CHUNG,
			`NATIVE · trang 500 HTML không ra câu chung: ${JSON.stringify(ket500 && ket500.cau)}`
		);

		// 7. 401 mà máy chủ KHÔNG đưa câu nào — ca app gặp hằng ngày trước Task 3.
		const ket_trong = await page.evaluate(
			(ham) => erpnext.kho_pda.KhoApp.goi(ham).then(() => null, (e) => ({ cau: e.message, ma: e.ma })),
			HAM_401_TRONG
		);
		khang_dinh(
			ket_trong && ket_trong.cau === CAU_CHUA_CAP_QUYEN,
			`NATIVE · 401 thân rỗng vẫn ra "Có lỗi, thử lại." thay vì câu chỉ được việc: ${JSON.stringify(ket_trong && ket_trong.cau)}`
		);
		// ĐỐI CHỨNG DƯƠNG của mục 5b: CÙNG chiếc khoá vừa sống sót qua lượt 403 phải
		// CHẾT ở lượt 401 này. Thiếu vế này thì "403 không giết khoá" có thể chỉ nghĩa
		// là đường giết khoá đã hỏng hẳn — và lúc đó một chiếc máy bị thu hồi sẽ kẹt
		// vĩnh viễn ở vòng "vào menu → 401", đúng thứ Task 4 sinh ra để chặn.
		await page.waitForTimeout(250);
		const sau_401_doi_chung = await page.evaluate(() => ({
			khoa: erpnext.kho_pda.KhoApp.khoa(),
			luu: localStorage.getItem("kho_pda.khoa"),
			man: erpnext.kho_pda.KhoApp.man_hien_tai,
		}));
		khang_dinh(
			sau_401_doi_chung.khoa === "" && !sau_401_doi_chung.luu && sau_401_doi_chung.man === "the",
			`NATIVE · 401 KHÔNG giết được khoá máy: ${JSON.stringify(sau_401_doi_chung)} — đường thu hồi đã hỏng, và mục 5b vì thế không chứng minh được gì`
		);

		// 8. Bộ đếm tổng: MỌI lời gọi ở trên phải đi qua lớp native, không sót cái nào.
		const dem_cuoi = await page.evaluate(() => window.__dem_native);
		khang_dinh(
			dem_cuoi === goi_native.length && dem_cuoi >= 6,
			`NATIVE · số lời gọi qua cầu native (${dem_cuoi}) không khớp nhật ký native (${goi_native.length}) hoặc quá ít`
		);

		loi.push(...(await page.evaluate(() => window.__loi_async.slice())));
		if (loi.length) sai.push(`NATIVE · lỗi JS: ${loi.slice(0, 3).join(" | ")}`);
	} finally {
		ten_ban_cai_gia = TEN_BAN_CAI_CU;
		await ctx.close();
	}
}

// ============================================================================
// TASK 6 — LỐI ẨN KHAI ĐỊA CHỈ MÁY CHỦ (spec §9)
// ============================================================================
//
// THỨ PHẢI ĐO, và vì sao dòng chữ trên màn KHÔNG đủ: Ruling 9 của sổ thi công
// nói đúng cái ca hỏng ở đây — `dia_chi_may_chu()` (dòng "Máy chủ:") đọc địa chỉ
// mới trong khi `goi()` vẫn dựng địa chỉ cũ. Một bài chỉ đọc chữ trên màn sẽ XANH
// với đúng ca đó, và thủ kho được một chốt chặn bằng mắt NÓI DỐI. Vì vậy khẳng
// định quyết định là **lời gọi có tới máy chủ THỨ HAI hay không** — hai máy chủ
// giả, hai nhật ký riêng, và phép đo là "gói tin nằm ở nhật ký nào".
//
// `KHO_MAY_CHU` được khai bằng `defineProperty` CÓ SETTER RỖNG (xem `script_khai`)
// — đó cũng chính là hình dạng của bản đóng gói thật, nơi `cau-hinh.js` chạy lại
// ở MỖI lượt tải trang và đè lại giá trị. Một bản vá ghi thẳng `window.KHO_MAY_CHU
// = …` vì thế phải ĐỎ ở đây, không được xanh.
async function do_loi_an(browser, goc_a, goc_b, nhat_ky_a, nhat_ky_b) {
	const ctx = await browser.newContext({ viewport: { width: 360, height: 640 } });
	const page = await ctx.newPage();
	const loi = [];
	page.on("pageerror", (e) => loi.push(String(e)));
	await page.addInitScript(
		script_khai({ KHO_MAY_CHU: goc_a, KHO_LA_APP: true, KHO_BO_QUA_DONG_BO_GIO: true })
	);

	// Bấm giữ ĐÚNG như một ngón tay: `pointerdown` → chờ → `pointerup`, qua chuột
	// của Playwright (chuột sinh ra sự kiện `pointer*`, ngón tay cũng vậy — đó là
	// lý do `man_the.js` nghe `pointer*` chứ không `touch*`/`mouse*`).
	const giu_logo = async (ms) => {
		const o = await page.locator(".man-the-logo").boundingBox();
		if (!o) return false;
		await page.mouse.move(o.x + o.width / 2, o.y + o.height / 2);
		await page.mouse.down();
		await page.waitForTimeout(ms);
		await page.mouse.up();
		await page.waitForTimeout(150);
		return true;
	};
	const co_hop = () => page.evaluate(() => !!document.querySelector(".kho-hop-nhap"));

	try {
		await page.goto("file://" + TRANG_APP);
		await page.waitForSelector("#kho-app .kho-than", { timeout: 20000 });

		// 0. Logo PHẢI CÓ trong bản đóng gói — không có logo thì không có lối ẩn, và
		//    mọi khẳng định dưới đây sẽ "xanh" vì chẳng đo được gì.
		const co_logo = await page.evaluate(() => !!document.querySelector(".man-the-logo"));
		khang_dinh(co_logo, "LOI_AN · màn thẻ của bản đóng gói KHÔNG có logo — lối ẩn không có nút nào để bấm");

		// 1. KHẲNG ĐỊNH NGƯỢC — nhả tay ở 1 giây thì KHÔNG mở. Không có vế này thì
		//    một cái hẹn 0ms (hoặc một `click` thường) cũng cho cổng xanh, tức "bấm
		//    GIỮ ba giây" không được canh bởi bất cứ thứ gì.
		await giu_logo(1000);
		khang_dinh(
			(await co_hop()) === false,
			"LOI_AN · nhả tay sau 1 giây mà lối ẩn ĐÃ MỞ — ngưỡng giữ 3 giây không có tác dụng"
		);
		// ...VÀ KHÔNG MỞ RA MUỘN. Đây là nửa thứ hai của cùng một khẳng định, và nó
		// bắt một ca mà nửa trên BỎ LỌT — đo được: bỏ dòng huỷ hẹn khi nhả tay
		// (`pointerup/cancel/leave` trong `man_the.js`) thì cả cổng vẫn XANH, vì lúc
		// đọc ở trên cái hẹn 3 giây còn chưa tới giờ. Hậu quả thật: chạm logo rồi
		// cuộn màn hình đi làm việc khác, ba giây sau hộp địa chỉ máy chủ bật ra
		// giữa lúc đang quét.
		await page.waitForTimeout(2600);
		khang_dinh(
			(await co_hop()) === false,
			"LOI_AN · nhả tay ở 1 giây rồi mà lối ẩn VẪN bật ra sau đó — cái hẹn không bị huỷ khi nhả tay"
		);

		// 2. Giữ đủ 3 giây thì mở, và ô nhập mang sẵn địa chỉ ĐANG DÙNG.
		await giu_logo(3300);
		khang_dinh((await co_hop()) === true, "LOI_AN · giữ logo 3,3 giây mà lối ẩn KHÔNG mở");
		const o_nhap = await page.evaluate(() => {
			const el = document.querySelector(".kho-hop-nhap");
			return { gia_tri: el ? el.value : null, so_hop: erpnext.kho_pda.so_hop_dang_mo };
		});
		khang_dinh(
			o_nhap.gia_tri === goc_a,
			`LOI_AN · ô nhập không mang địa chỉ đang dùng (${JSON.stringify(o_nhap.gia_tri)} ≠ ${goc_a})`
		);
		// Hộp phải KHOÁ ô quét — nửa sau của sự cố 17/09/2026 (xem `hop_thoai.js`):
		// súng quét bắn xuyên qua hộp vào ô quét phía sau là một lượt quét thẻ không
		// ai định làm, ngay giữa lúc đang gõ địa chỉ máy chủ.
		khang_dinh(
			o_nhap.so_hop === 1,
			`LOI_AN · so_hop_dang_mo = ${o_nhap.so_hop} khi lối ẩn mở — ô quét phía sau KHÔNG bị khoá`
		);

		// 3. ENTER KHÔNG LƯU. Súng quét gửi Enter sau mỗi lần bắn; một cú bắn lạc
		//    vào ô địa chỉ mà Enter tự lưu là chiếc máy đổi địa chỉ giữa ca.
		await page.fill(".kho-hop-nhap", goc_b);
		await page.press(".kho-hop-nhap", "Enter");
		await page.waitForTimeout(250);
		const sau_enter = await page.evaluate(() => ({
			con_hop: !!document.querySelector(".kho-hop-nhap"),
			da_luu: localStorage.getItem("kho_pda.may_chu"),
			goc: erpnext.kho_pda.KhoApp.goc(),
		}));
		khang_dinh(
			sau_enter.con_hop === true && !sau_enter.da_luu,
			`LOI_AN · Enter trong ô địa chỉ đã LƯU/đóng hộp: ${JSON.stringify(sau_enter)} — súng quét đổi được máy chủ`
		);

		// 4. HAI ĐỊA CHỈ BỊ TỪ CHỐI, mỗi cái một lý do thật:
		//    (a) có đường dẫn phía sau tên miền → `goc()` nối thành `.../kho/api/...`;
		//    (b) `http://` tới host không nằm trong `network_security_config.xml` →
		//        Android chặn ở tầng dưới mã của app, triệu chứng giống hệt "máy chủ
		//        chết" — đúng cái tình huống lối ẩn sinh ra để chấm dứt.
		for (const ca of [
			{ dia_chi: "https://abc.ngrok-free.app/kho", vi_sao: "địa chỉ có đường dẫn phía sau" },
			{ dia_chi: "http://10.9.9.9:8000", vi_sao: "http:// tới host ngoài network_security_config" },
		]) {
			await page.fill(".kho-hop-nhap", ca.dia_chi);
			await page.click(".kho-hop-dong-y");
			await page.waitForTimeout(200);
			const tu_choi = await page.evaluate(() => ({
				con_hop: !!document.querySelector(".kho-hop-nhap"),
				cau: (document.querySelector(".kho-hop-loi") || {}).textContent || "",
				da_luu: localStorage.getItem("kho_pda.may_chu"),
			}));
			khang_dinh(
				tu_choi.con_hop && !!tu_choi.cau.trim() && !tu_choi.da_luu,
				`LOI_AN · "${ca.dia_chi}" (${ca.vi_sao}) ĐƯỢC NHẬN hoặc bị từ chối không một chữ: ${JSON.stringify(tu_choi)}`
			);
		}

		// 4b. CA THẬT SỰ LÀM LỐI NÀY TỒN TẠI — một địa chỉ ngrok `https://` phải
		//     ĐƯỢC NHẬN. Không có vế này thì bốn khẳng định "bị từ chối" ở trên đều
		//     xanh với một hàm kiểm từ chối TẤT CẢ, tức lối ẩn vô dụng đúng lúc cần.
		//     Đo trên hàm kiểm chứ không lưu thật: máy này không có đường hầm ngrok
		//     nào để lời gọi đi tới.
		const ngrok_ok = await page.evaluate(() =>
			erpnext.kho_pda.KhoApp.loi_dia_chi_may_chu("https://abc-123.ngrok-free.app/")
		);
		khang_dinh(
			ngrok_ok === "",
			`LOI_AN · địa chỉ ngrok https BỊ TỪ CHỐI (${JSON.stringify(ngrok_ok)}) — đúng ca mà lối ẩn sinh ra để cứu`
		);

		// 5. LƯU ĐỊA CHỈ B rồi tải lại. Đây là phép đo chính.
		await page.fill(".kho-hop-nhap", goc_b);
		await page.click(".kho-hop-dong-y");
		await page.waitForTimeout(900);
		await page.waitForSelector("#kho-app .kho-than", { timeout: 20000 });

		const sau_luu = await page.evaluate(() => ({
			goc: erpnext.kho_pda.KhoApp.goc(),
			hien: erpnext.kho_pda.KhoApp.dia_chi_may_chu(),
			than: document.querySelector("#kho-app .kho-than").innerText,
			ghi_de: erpnext.kho_pda.KhoApp.may_chu_ghi_de(),
		}));
		khang_dinh(sau_luu.goc === goc_b, `LOI_AN · goc() vẫn là ${sau_luu.goc}, phải là ${goc_b}`);
		khang_dinh(sau_luu.ghi_de === goc_b, `LOI_AN · may_chu_ghi_de() = ${sau_luu.ghi_de}`);
		// Dòng "Máy chủ:" phải đổi THEO — và nó phải đọc CÙNG nguồn, nên nó không
		// thể đúng nếu `goc()` sai, và ngược lại (Ruling 9).
		khang_dinh(
			sau_luu.than.includes(goc_b) && !sau_luu.than.includes(goc_a),
			`LOI_AN · dòng "Máy chủ:" chưa đổi sang địa chỉ gõ tay: ${JSON.stringify(sau_luu.than.slice(0, 160))}`
		);

		// 5b. KHẲNG ĐỊNH QUYẾT ĐỊNH — LỜI GỌI THẬT tới máy chủ NÀO.
		const truoc_a = nhat_ky_a.length;
		const truoc_b = nhat_ky_b.length;
		const ra = await page.evaluate(
			(ham) => erpnext.kho_pda.KhoApp.goi(ham, { loi_an: 1 }).catch((e) => ({ loi: e.message })),
			HAM_OK
		);
		khang_dinh(ra && ra.ok === true, `LOI_AN · lời gọi sau khi đổi địa chỉ không thành: ${JSON.stringify(ra)}`);
		khang_dinh(
			nhat_ky_b.length === truoc_b + 1,
			`LOI_AN · máy chủ MỚI (${goc_b}) KHÔNG nhận được lời gọi nào — dòng "Máy chủ:" đổi mà lớp gọi mạng thì không (Ruling 9)`
		);
		khang_dinh(
			nhat_ky_a.length === truoc_a,
			`LOI_AN · lời gọi vẫn tới máy chủ CŨ (${goc_a}) sau khi đã khai địa chỉ mới`
		);

		// 6. ĐƯỜNG LÙI — "Bỏ địa chỉ gõ tay" phải trả về địa chỉ đóng gói. Không có
		//    đường này thì gõ nhầm một địa chỉ chết là chiếc máy chỉ còn cách gỡ cài.
		await giu_logo(3300);
		khang_dinh((await co_hop()) === true, "LOI_AN · không mở lại được lối ẩn sau khi đã khai địa chỉ");
		const co_nut_phu = await page.evaluate(() => !!document.querySelector(".kho-hop-phu"));
		khang_dinh(co_nut_phu, "LOI_AN · đang có địa chỉ gõ tay mà KHÔNG có nút bỏ nó đi");
		await page.click(".kho-hop-phu");
		await page.waitForTimeout(900);
		await page.waitForSelector("#kho-app .kho-than", { timeout: 20000 });
		const sau_bo = await page.evaluate(() => ({
			goc: erpnext.kho_pda.KhoApp.goc(),
			luu: localStorage.getItem("kho_pda.may_chu"),
		}));
		khang_dinh(
			sau_bo.goc === goc_a && !sau_bo.luu,
			`LOI_AN · "Bỏ địa chỉ gõ tay" không trả về địa chỉ đóng gói: ${JSON.stringify(sau_bo)}`
		);
		const truoc_a2 = nhat_ky_a.length;
		await page.evaluate((ham) => erpnext.kho_pda.KhoApp.goi(ham).catch(() => null), HAM_OK);
		khang_dinh(
			nhat_ky_a.length === truoc_a2 + 1,
			`LOI_AN · sau khi bỏ địa chỉ gõ tay, lời gọi KHÔNG quay về máy chủ đóng gói (${goc_a})`
		);

		loi.push(...(await page.evaluate(() => window.__loi_async.slice())));
		if (loi.length) sai.push(`LOI_AN · lỗi JS: ${loi.slice(0, 3).join(" | ")}`);
	} finally {
		await ctx.close();
	}
}

// ============================================================================
// TASK 6 — DẢI NHẮC CÓ BẢN CÀI MỚI (spec §10)
// ============================================================================
//
// BỐN CA, và ba trong bốn ca là KHẲNG ĐỊNH NGƯỢC. Lý do: một bản vá "luôn hiện
// dải" đi qua ca thứ nhất dễ như đi qua một cánh cửa mở. Thứ khó là im lặng đúng
// lúc — bản ngang bằng, bản CŨ HƠN (đúng trạng thái của một máy vừa được cài bản
// mới nhất trong khi máy chủ còn giữ bản cũ hơn trong danh sách), và một tên file
// không rút ra được phiên bản (ai đó tải lên "ban-cai-thang-9.apk").
async function do_nhac_ban_moi(browser, goc_gia, nhat_ky) {
	const CA = [
		{
			ten_tep: "miyano-pda-9.9-release.apk",
			phai_hien: true,
			vi_sao: "máy chủ có bản mới hơn hẳn",
		},
		{
			ten_tep: `miyano-pda-${BAN_APP}-release.apk`,
			phai_hien: false,
			vi_sao: "máy đang cầm đúng bản mới nhất",
		},
		{
			ten_tep: "miyano-pda-0.9-release.apk",
			phai_hien: false,
			vi_sao: "bản trên máy chủ CŨ HƠN bản đang chạy",
		},
		{
			ten_tep: "ban-cai-thang-chin.apk",
			phai_hien: false,
			vi_sao: "tên file không rút ra được phiên bản — không chắc thì KHÔNG nhắc",
		},
		// HAI CA LẤY TỪ TÊN FILE THẬT ĐANG NẰM TRÊN MÁY CHỦ THỬ
		// (`miyano-pda-1.0-kho-2026-09-24.apk`, đo bằng curl 25/09/2026): người phát
		// hành dán NGÀY vào tên file. Bản vá đầu tiên lấy "cụm số đầu tiên thấy
		// được" và tình cờ đúng với khuôn này — nhưng chỉ cần đảo thứ tự một lần là
		// nó đọc ra "2026" và mọi máy nhắc vĩnh viễn. Hai ca dưới khoá cả hai chiều.
		{
			ten_tep: `miyano-pda-${BAN_APP}-kho-2026-09-24.apk`,
			phai_hien: false,
			vi_sao: "tên THẬT có ngày ở đuôi, phiên bản ngang bằng — phải im",
		},
		{
			ten_tep: "miyano-pda-2026-09-24-ban-thang-9.apk",
			phai_hien: false,
			vi_sao: "NGÀY đứng ở chỗ của phiên bản — 2026 KHÔNG phải một bản mới hơn",
		},
		// VÒNG SỬA CUỐI (soát tổng, T6-1) — NGÀY VIẾT BẰNG DẤU CHẤM.
		//
		// Bốn ca này bắt đúng lỗ mà bản vá trước BỎ LỌT: lập luận ngầm "ngày tháng
		// không mang dấu chấm" sai với cách viết của người Việt. Người soát chạy hàm
		// thật trên 14 tên file và tìm ra hai ca đầu; ca `24.09.26` (dd.mm.yy) là ca
		// thứ ba cùng họ, tìm thêm khi vá. Cả ba đều > 1.0 nếu lọt → dải nhắc bật
		// VĨNH VIỄN trên mọi máy cho một bản cài chẳng mới hơn gì.
		//
		// Ca thứ tư đi NGƯỢC LẠI và bắt buộc phải có: nó khoá phần "`.apk` ngay sau
		// số hiệu vẫn phải đọc được". Thiếu nó thì một bản vá siết quá tay (đòi phải
		// có `-` phía sau) sẽ từ chối oan một tên hợp lệ, và ba ca trên vẫn xanh hết.
		{
			ten_tep: "miyano-pda-2026.09.24.apk",
			phai_hien: false,
			vi_sao: "yyyy.mm.dd — ngày viết bằng DẤU CHẤM, đúng ca người soát tìm ra",
		},
		{
			ten_tep: "miyano-pda-25.09.2026-ban-moi.apk",
			phai_hien: false,
			vi_sao: "dd.mm.yyyy — ngày viết bằng DẤU CHẤM, chiều ngược lại",
		},
		{
			ten_tep: "miyano-pda-24.09.26.apk",
			phai_hien: false,
			vi_sao: "dd.mm.yy — ba đoạn hai chữ số, KHÔNG phân biệt được với số hiệu ba đoạn",
		},
		{
			ten_tep: "miyano-pda-9.9.apk",
			phai_hien: true,
			vi_sao: "số hiệu đứng ngay trước `.apk`, không có đuôi `-release` — vẫn phải đọc được",
		},
		{
			ten_tep: "",
			phai_hien: false,
			vi_sao: "chưa ai tải bản cài nào lên (máy chủ trả null)",
		},
		// HAI CA "ĐOẠN THỨ MƯỜI" — chỗ duy nhất phân biệt được phép so BẰNG SỐ với
		// phép so BẰNG CHUỖI. Đo được: thay thân `_so_sanh_ban` bằng `a > b` trên
		// chuỗi thì bốn ca trên VẪN XANH HẾT (bản đóng gói đang là 1.0, và "9.9",
		// "1.0", "0.9" tình cờ xếp đúng thứ tự cả theo chữ cái). Hai ca này phải
		// khai `ban_app` giả — bản đóng gói chỉ có một phiên bản, mà cái bẫy chỉ lộ
		// ra ở lượt nâng cấp thứ mười, tức nhiều tháng sau khi ai đó đọc dòng này.
		{
			ten_tep: "miyano-pda-1.10-release.apk",
			ban_app: "1.9",
			phai_hien: true,
			ban_moi_tren_dai: "1.10",
			vi_sao: "1.10 MỚI HƠN 1.9 — theo thứ tự chữ cái thì ngược lại",
		},
		{
			ten_tep: "miyano-pda-1.9-release.apk",
			ban_app: "1.10",
			phai_hien: false,
			vi_sao: "1.9 CŨ HƠN 1.10 — theo thứ tự chữ cái thì ngược lại",
		},
	];

	for (const ca of CA) {
		ten_ban_cai_gia = ca.ten_tep;
		const ctx = await browser.newContext({ viewport: { width: 360, height: 640 } });
		const page = await ctx.newPage();
		const loi = [];
		page.on("pageerror", (e) => loi.push(String(e)));
		const ban_cua_may = ca.ban_app || BAN_APP;
		await page.addInitScript(
			script_khai(
				Object.assign(
					{ KHO_MAY_CHU: goc_gia, KHO_LA_APP: true, KHO_BO_QUA_DONG_BO_GIO: true },
					// Chỉ hai ca "đoạn thứ mười" mới khai đè phiên bản của app; các ca
					// còn lại đọc ĐÚNG giá trị `dong-goi.sh` vừa sinh ra.
					ca.ban_app ? { KHO_BAN_APP: ca.ban_app } : {}
				)
			)
		);
		try {
			// Máy ĐÃ NHẬN (có khoá cất sẵn) — hình ảnh thật của chiếc máy sẽ thấy dải
			// này: chạm icon là vào thẳng menu, không qua màn thẻ.
			await page.addInitScript(`
				try { localStorage.setItem("kho_pda.khoa", "KHOANHAC11:BIMATNHAC22"); } catch (e) {}
			`);
			const truoc = nhat_ky.length;
			await page.goto("file://" + TRANG_APP);
			await page.waitForSelector("#kho-app .kho-menu-luoi", { timeout: 20000 });
			// TẤT ĐỊNH, không `waitForTimeout` (V3): chờ máy chủ giả ghi nhận lời gọi,
			// rồi chờ chính lời hứa đó được xử lý xong trong trang.
			const da_nhan = await cho_may_chu_nhan(nhat_ky, HAM_BAN_CAI, 1, truoc);
			khang_dinh(
				da_nhan,
				`NHAC_BAN · máy chủ giả KHÔNG nhận được lời gọi ${HAM_BAN_CAI} trong 15 giây — ca "${ca.vi_sao}"`
			);
			await cho_nhac_xong(page);

			// Màn menu PHẢI hỏi máy chủ, đúng một lần cho một lượt mở app. Không có
			// khẳng định này thì các ca "không hiện dải" ở trên đều xanh với một bản
			// vá không hề gọi máy chủ.
			//
			// `cho_nhac_xong()` gọi `hoi_ban_cai_moi()` lần nữa — nó trả về lời hứa ĐÃ
			// GHI NHỚ nên KHÔNG bắn thêm lời gọi nào, và phép đếm "đúng 1" dưới đây
			// chính là thứ canh điều đó.
			const goi_ban_cai = nhat_ky.slice(truoc).filter((g) => g.ham === HAM_BAN_CAI);
			khang_dinh(
				goi_ban_cai.length === 1,
				`NHAC_BAN · màn menu gọi ${HAM_BAN_CAI} ${goi_ban_cai.length} lần (phải đúng 1) — ca "${ca.vi_sao}"`
			);

			const dai = await page.evaluate(() => {
				const el = document.querySelector(".kho-ban-moi");
				const nut = document.querySelector(".kho-ban-moi-nut");
				return {
					co: !!el,
					chu: el ? el.textContent : "",
					href: nut ? nut.getAttribute("href") : null,
					target: nut ? nut.getAttribute("target") : null,
				};
			});
			khang_dinh(
				dai.co === ca.phai_hien,
				`NHAC_BAN · "${ca.ten_tep || "(không có bản cài)"}" — dải nhắc ${dai.co ? "HIỆN" : "KHÔNG hiện"} ` +
					`trong khi phải ${ca.phai_hien ? "hiện" : "im"}: ${ca.vi_sao}`
			);
			if (ca.phai_hien) {
				// NỘI DUNG, không chỉ "có phần tử": dải phải nói CẢ HAI con số, vì
				// "có bản mới" mà không nói bản nào thì trưởng kho không biết máy nào
				// đã nâng, máy nào chưa.
				const ban_moi = ca.ban_moi_tren_dai || "9.9";
				khang_dinh(
					dai.chu.includes(ban_moi) && dai.chu.includes(ban_cua_may),
					`NHAC_BAN · dải nhắc không nói đủ hai phiên bản (mới ${ban_moi} / đang dùng ${ban_cua_may}): ${JSON.stringify(dai.chu)}`
				);
				// Nút phải trỏ tới trang tải CỦA ĐÚNG MÁY CHỦ ĐANG NỐI (`goc()`),
				// không phải một địa chỉ viết cứng — máy đổi địa chỉ bằng lối ẩn thì
				// nút này phải đi theo.
				khang_dinh(
					dai.href === `${goc_gia}/tai-app`,
					`NHAC_BAN · nút mở trang tải trỏ sai: ${JSON.stringify(dai.href)} (phải là ${goc_gia}/tai-app)`
				);
				// `target="_blank"` — trong APK, Capacitor giao địa chỉ ngoài cho
				// trình duyệt hệ thống; một lượt điều hướng ngay trong WebView sẽ kéo
				// app rời khỏi `index.html`.
				khang_dinh(
					dai.target === "_blank",
					`NHAC_BAN · nút mở trang tải thiếu target="_blank": ${JSON.stringify(dai.target)}`
				);
			}

			loi.push(...(await page.evaluate(() => window.__loi_async.slice())));
			if (loi.length) sai.push(`NHAC_BAN · lỗi JS (ca "${ca.vi_sao}"): ${loi.slice(0, 3).join(" | ")}`);
		} finally {
			await ctx.close();
		}
	}

	// Trả máy chủ giả về mặc định "ngang bằng" cho mọi kịch bản chạy sau.
	ten_ban_cai_gia = `miyano-pda-${BAN_APP}-release.apk`;
}

// ============================================================================
// TASK 6 — HAI DẢI NHẮC CHỒNG NHAU (ca bất đồng bộ)
// ============================================================================
//
// `KhoApp.$than` là MỘT nút DOM dùng lại: `khoi_dong()` cất nó một lần, `_ve()`
// chỉ gọi `.empty()` chứ không dựng nút mới. Lời hỏi bản cài thì BẤT ĐỒNG BỘ và
// được ghi nhớ, nên hai lượt vẽ menu cùng gắn `.then()` vào MỘT lời hứa — khi nó
// về, cả hai cùng tìm thấy `.kho-menu` HIỆN TẠI và cùng chèn một dải.
//
// VÌ SAO `do_nhac_ban_moi` KHÔNG THẤY CA NÀY: ở đó mỗi ca là một lượt tải trang,
// MỘT lượt vẽ menu, và máy chủ giả trả tức thì. Phải đủ ba thứ mới dựng lại được:
// phản hồi CHẬM, hai lượt vẽ menu, và lượt thứ hai xảy ra TRƯỚC khi phản hồi về.
// Dùng lại đúng mẹo làm chậm mà soát xét Task 5 đã dùng để lộ lỗ nửa đêm.
async function do_hai_dai_nhac(browser, goc_gia, nhat_ky_chung) {
	const truoc_ten = ten_ban_cai_gia;
	ten_ban_cai_gia = "miyano-pda-9.9-release.apk";
	tre_ban_cai_ms = 1200;
	const ctx = await browser.newContext({ viewport: { width: 360, height: 640 } });
	const page = await ctx.newPage();
	const loi = [];
	page.on("pageerror", (e) => loi.push(String(e)));
	await page.addInitScript(
		script_khai({ KHO_MAY_CHU: goc_gia, KHO_LA_APP: true, KHO_BO_QUA_DONG_BO_GIO: true })
	);
	await page.addInitScript(
		'try { localStorage.setItem("kho_pda.khoa", "KHOACHONG11:BIMATCHONG22"); } catch (e) {}'
	);
	const truoc_log = nhat_ky_chung.length;
	try {
		await page.goto("file://" + TRANG_APP);
		await page.waitForSelector("#kho-app .kho-menu-luoi", { timeout: 20000 });
		// Rời menu rồi quay lại NGAY, trong lúc lời gọi còn đang bay (1,2 giây).
		await page.evaluate(() => erpnext.kho_pda.KhoApp.di("tra-cuu"));
		await page.waitForTimeout(150);
		await page.evaluate(() => erpnext.kho_pda.KhoApp.di("menu"));
		// TẤT ĐỊNH (V3): máy chủ giả giữ phản hồi 1,2 giây — chờ đúng lúc nó trả và
		// trang xử lý xong, không đoán một con số giây.
		await cho_may_chu_nhan(nhat_ky_chung, HAM_BAN_CAI, 1, truoc_log);
		await cho_nhac_xong(page);
		const dem = await page.evaluate(() => ({
			so_dai: document.querySelectorAll(".kho-ban-moi").length,
			man: erpnext.kho_pda.KhoApp.man_hien_tai,
		}));
		khang_dinh(dem.man === "menu", `HAI_DAI · không quay lại được màn menu ("${dem.man}") — ca chưa dựng được`);
		khang_dinh(
			dem.so_dai === 1,
			`HAI_DAI · màn menu mang ${dem.so_dai} dải nhắc bản mới (phải đúng 1) — lời hứa được ghi nhớ nên MỌI lượt vẽ menu cùng chèn một dải`
		);
		loi.push(...(await page.evaluate(() => window.__loi_async.slice())));
		if (loi.length) sai.push(`HAI_DAI · lỗi JS: ${loi.slice(0, 3).join(" | ")}`);
	} finally {
		tre_ban_cai_ms = 0;
		ten_ban_cai_gia = truoc_ten;
		await ctx.close();
	}
}

// ============================================================================
// TASK 6 — MỘT LƯỢT HỎI HỎNG KHÔNG ĐƯỢC KHOÁ CƠ CHẾ VĨNH VIỄN
// ============================================================================
//
// `_hen_ban_cai` ghi nhớ lời hứa. Nhớ luôn cả một lượt HỎNG thì mở app ở góc kho
// mất sóng là chiếc máy đó KHÔNG BAO GIỜ nhắc nữa, kể cả khi đã ra chỗ có wifi —
// mà Task 5 đã đo được rằng một WebView ở đây sống qua cả nửa đêm không tải lại.
// Đúng hình dạng T5-1 ("fetch treo thì khoá cờ VĨNH VIỄN", vá bằng thử lại).
async function do_hoi_lai_sau_khi_hong(browser, goc_gia, nhat_ky) {
	const truoc_ten = ten_ban_cai_gia;
	ban_cai_hong = true;
	const ctx = await browser.newContext({ viewport: { width: 360, height: 640 } });
	const page = await ctx.newPage();
	const loi = [];
	page.on("pageerror", (e) => loi.push(String(e)));
	await page.addInitScript(
		script_khai({ KHO_MAY_CHU: goc_gia, KHO_LA_APP: true, KHO_BO_QUA_DONG_BO_GIO: true })
	);
	await page.addInitScript(
		'try { localStorage.setItem("kho_pda.khoa", "KHOATHULAI11:BIMATTHULAI22"); } catch (e) {}'
	);
	try {
		await page.goto("file://" + TRANG_APP);
		await page.waitForSelector("#kho-app .kho-menu-luoi", { timeout: 20000 });
		// TẤT ĐỊNH (V3), và KHÔNG dùng `cho_nhac_xong()` ở đây: lượt này HỎNG nên
		// `hoi_ban_cai_moi()` tự quên lời hứa, gọi lại sẽ bắn thêm một lời gọi và
		// làm bẩn đúng phép đếm bài này đang đo. Chờ bằng chính trạng thái "đã quên".
		await cho_quen_hen(page);
		const lan_dau = await page.evaluate(() => document.querySelectorAll(".kho-ban-moi").length);
		khang_dinh(lan_dau === 0, `HOI_LAI · lượt hỏi HỎNG mà vẫn vẽ dải nhắc (${lan_dau}) — nhắc dựa trên cái gì?`);

		// "Có sóng lại": máy chủ trả bình thường, và có một bản MỚI HƠN.
		ban_cai_hong = false;
		ten_ban_cai_gia = "miyano-pda-9.9-release.apk";
		const truoc = nhat_ky.length;
		await page.evaluate(() => erpnext.kho_pda.KhoApp.di("tra-cuu"));
		await page.waitForTimeout(200);
		await page.evaluate(() => erpnext.kho_pda.KhoApp.di("menu"));
		await cho_may_chu_nhan(nhat_ky, HAM_BAN_CAI, 1, truoc);
		await cho_nhac_xong(page);
		const sau = await page.evaluate(() => document.querySelectorAll(".kho-ban-moi").length);
		const da_hoi_lai = nhat_ky.slice(truoc).filter((g) => g.ham === HAM_BAN_CAI).length;
		khang_dinh(
			da_hoi_lai >= 1,
			"HOI_LAI · sau một lượt hỏng, màn menu KHÔNG hỏi lại — cơ chế nhắc chết suốt đời WebView đó (T5-1)"
		);
		khang_dinh(
			sau === 1,
			`HOI_LAI · hỏi lại thành công mà dải nhắc ${sau === 0 ? "không hiện" : "hiện " + sau + " lần"}`
		);
		loi.push(...(await page.evaluate(() => window.__loi_async.slice())));
		if (loi.length) sai.push(`HOI_LAI · lỗi JS: ${loi.slice(0, 3).join(" | ")}`);
	} finally {
		ban_cai_hong = false;
		ten_ban_cai_gia = truoc_ten;
		await ctx.close();
	}
}

async function do_app_mat_mang(browser) {
	// Máy chủ không tồn tại (cổng đóng trên chính máy này) — `fetch` reject bằng
	// `TypeError: Failed to fetch`. Người dùng PHẢI đọc được câu tiếng Việt.
	const ctx = await browser.newContext({ viewport: { width: 360, height: 640 } });
	const page = await ctx.newPage();
	// TASK 5: xem chú thích ở `do_app` cho lý do cần `KHO_BO_QUA_DONG_BO_GIO` —
	// đây còn cấp bách hơn: `KHO_MAY_CHU` trỏ vào một cổng KHÔNG AI NGHE, và không
	// tắt cờ này thì mỗi lượt `page.goto` bên dưới lại bắn thêm một lời gọi thất
	// bại vô ích, không liên quan gì tới ca "mất mạng" mà bài này đang đo.
	await page.addInitScript(
		script_khai({ KHO_MAY_CHU: "http://127.0.0.1:1", KHO_LA_APP: true, KHO_BO_QUA_DONG_BO_GIO: true })
	);
	try {
		await page.goto("file://" + TRANG_APP);
		await page.waitForSelector("#kho-app .kho-than", { timeout: 5000 });
		const cau = await page.evaluate(
			(ham) =>
				erpnext.kho_pda.KhoApp.goi(ham).then(
					() => "KHONG LOI",
					(e) => e.message
				),
			HAM_OK
		);
		khang_dinh(
			cau === "Mất kết nối. Kiểm tra wifi rồi thử lại.",
			`APP · mất mạng không ra câu tiếng Việt: ${JSON.stringify(cau)}`
		);
		khang_dinh(!/Failed to fetch/i.test(cau), "APP · để lọt 'Failed to fetch' ra tay người dùng");
	} finally {
		await ctx.close();
	}
}

async function do_web(browser, goc_gia, nhat_ky) {
	const ctx = await browser.newContext({ viewport: { width: 360, height: 640 } });
	const page = await ctx.newPage();
	const loi = [];
	page.on("pageerror", (e) => loi.push(String(e)));
	await page.addInitScript(`
		window.__loi_async = [];
		window.addEventListener("unhandledrejection", function (e) {
			window.__loi_async.push(String((e.reason && e.reason.stack) || e.reason));
		});
	`);
	await ctx.addCookies([{ name: "sid", value: "PHIEN-WEB-1234", url: goc_gia }]);
	const truoc_ca_web = nhat_ky.length;
	try {
		await page.goto(goc_gia + "/kho-thu");
		await page.waitForSelector("#kho-app .kho-than", { timeout: 5000 });

		// 0. Không có KHO_MAY_CHU/KHO_LA_APP → `goc()` rỗng, không dải BẢN THỬ.
		const do_duoc = await page.evaluate(() => ({
			goc: erpnext.kho_pda.KhoApp.goc(),
			hien: erpnext.kho_pda.KhoApp.dia_chi_may_chu(),
			than: document.querySelector("#kho-app .kho-than").innerText,
			origin: location.origin,
		}));
		khang_dinh(
			do_duoc.goc === "",
			`WEB · goc() phải RỖNG trên web (đường tương đối), đang là "${do_duoc.goc}"`
		);
		khang_dinh(
			do_duoc.hien === do_duoc.origin,
			`WEB · dòng "Máy chủ:" phải là ${do_duoc.origin}, đang là "${do_duoc.hien}"`
		);
		khang_dinh(do_duoc.than.includes(do_duoc.origin), "WEB · màn menu không in địa chỉ máy chủ");
		khang_dinh(!do_duoc.than.includes("BẢN THỬ"), "WEB · web KHÔNG được hiện dải 'BẢN THỬ'");

		// 1. Đường TƯƠNG ĐỐI, cùng nguồn, CÓ header CSRF — y như trước Task 2.
		const truoc = nhat_ky.length;
		const ra = await page.evaluate(
			(ham) => erpnext.kho_pda.KhoApp.goi(ham, { a: 1 }).catch((e) => ({ loi: e.message })),
			HAM_OK
		);
		khang_dinh(ra && ra.ok === true, `WEB · goi() không nhận được kết quả: ${JSON.stringify(ra)}`);
		const g1 = tim_goi(nhat_ky, HAM_OK, truoc);
		khang_dinh(!!g1, "WEB · máy chủ giả không nhận được lời gọi nào");
		if (g1) {
			khang_dinh(g1.duong_dan === `/api/method/${HAM_OK}`, `WEB · đường dẫn sai: ${g1.duong_dan}`);
			khang_dinh(
				g1.dau["x-frappe-csrf-token"] === TOKEN_TRANG,
				`WEB · MẤT header CSRF trên đường web: ${g1.dau["x-frappe-csrf-token"]}`
			);
			// Chrome gắn `Origin` cho MỌI lời gọi POST, kể cả cùng nguồn — nên phép
			// đọc ở đây không phải "có Origin hay không" mà là Origin BẰNG GÌ: bằng
			// chính nguồn của trang nghĩa là lời gọi CÙNG NGUỒN, tức đường dẫn vẫn
			// tương đối. (Ở phía APP, cùng phép đọc này ra `null` — xem `do_app`.)
			khang_dinh(
				g1.origin === goc_gia,
				`WEB · lời gọi không còn CÙNG NGUỒN (Origin: ${g1.origin}) — đường tương đối đã bị phá`
			);
			// ĐỐI CHỨNG DƯƠNG cho ca cookie của đường native (`do_qua_cau_native`
			// mục 3): CÙNG một cookie `sid`, ở đây `credentials: "same-origin"` trên
			// một lời gọi cùng nguồn thì cookie ĐI. Không có vế này thì "đường
			// native không thấy cookie" có thể chỉ là "cookie chưa từng tồn tại".
			khang_dinh(
				(g1.dau.cookie || "").includes("PHIEN-WEB-1234"),
				`WEB · cookie phiên KHÔNG đi kèm lời gọi cùng nguồn (${g1.dau.cookie}) — đối chứng hỏng, ca cookie bên native mất nghĩa`
			);
		}

		// 2. CƠ CHẾ LÀM MỚI CSRF vẫn sống trên web: token CŨ → 400 CSRFTokenError →
		//    `goi()` tự GET lại trang, rút token mới, GỌI LẠI và thành công.
		const truoc2 = nhat_ky.length;
		const ra2 = await page.evaluate(
			(x) => {
				frappe.csrf_token = x.cu;
				return erpnext.kho_pda.KhoApp.goi(x.ham).then(
					(m) => ({ ok: true, m: m }),
					(e) => ({ ok: false, cau: e.message })
				);
			},
			{ ham: HAM_CSRF, cu: TOKEN_CU }
		);
		khang_dinh(
			ra2.ok && ra2.m && ra2.m.token_da_dung === TOKEN_TRANG,
			`WEB · cơ chế làm mới CSRF đã hỏng: ${JSON.stringify(ra2)}`
		);
		const hai_lan = nhat_ky.slice(truoc2).filter((g) => g.ham === HAM_CSRF);
		const token_da_gui = JSON.stringify(hai_lan.map((g) => g.dau["x-frappe-csrf-token"]));
		khang_dinh(
			hai_lan.length === 2 &&
				hai_lan[0].dau["x-frappe-csrf-token"] === TOKEN_CU &&
				hai_lan[1].dau["x-frappe-csrf-token"] === TOKEN_TRANG,
			`WEB · không thấy đúng hai lượt gọi (cũ rồi mới): ${token_da_gui}`
		);

		// 3. TASK 2B — CÂU LỖI TRÊN ĐƯỜNG WEB KHÔNG ĐƯỢC ĐỔI CÂU CHỮ.
		//
		// Ràng buộc cứng của cả đợt: bản web `/kho` không đổi hành vi. Việc 3 sửa
		// `_cau_loi_may_chu` — một hàm DÙNG CHUNG cho cả hai nơi — nên chỗ này phải
		// khoá lại bằng phép đo, không bằng lời hứa:
		//   · câu HTML: đường web CŨNG chặn (đó là điểm của việc giết cả một LỚP
		//     lỗi — hôm nay trên web nó hiện ra nguyên các thẻ dưới dạng chữ), và
		//     câu thay thế phải là câu CŨ "Có lỗi, thử lại." — KHÔNG phải câu nói
		//     về khoá máy: trên web không có khoá máy nào, nói thế là chỉ sai người
		//     dùng đi làm một việc không tồn tại.
		//   · 401 thân rỗng: đường web giữ NGUYÊN VĂN câu cũ.
		const ket_html_web = await page.evaluate(
			(ham) => erpnext.kho_pda.KhoApp.goi(ham).then(() => null, (e) => ({ cau: e.message, ma: e.ma })),
			HAM_LOI_HTML
		);
		khang_dinh(
			ket_html_web && ket_html_web.cau === CAU_CHUNG,
			`WEB · câu lỗi HTML trên web phải là "${CAU_CHUNG}", đang là ${JSON.stringify(ket_html_web && ket_html_web.cau)}`
		);
		const ket_trong_web = await page.evaluate(
			(ham) => erpnext.kho_pda.KhoApp.goi(ham).then(() => null, (e) => ({ cau: e.message })),
			HAM_401_TRONG
		);
		khang_dinh(
			ket_trong_web && ket_trong_web.cau === CAU_CHUNG,
			`WEB · 401 thân rỗng trên web đã ĐỔI CÂU (${JSON.stringify(ket_trong_web && ket_trong_web.cau)}) — đường web phải giữ nguyên "${CAU_CHUNG}"`
		);

		// 4. TASK 4 — ĐƯỜNG WEB KHÔNG BIẾT GÌ VỀ KHOÁ MÁY. Hai vế, đo chứ không hứa:
		//    không lời gọi nào mang `X-Ma-May` (trên web danh tính đi bằng cookie
		//    phiên), và kho lưu của trình duyệt KHÔNG bị đụng tới một byte nào — tức
		//    Task 4 không lén thêm một cơ chế phiên thứ hai vào trang `/kho`.
		const web_gui_ma_may = nhat_ky.slice(truoc).filter((g) => g.dau["x-ma-may"]);
		khang_dinh(
			web_gui_ma_may.length === 0,
			`WEB · lời gọi trên web MANG X-Ma-May (${web_gui_ma_may.map((g) => g.ham).join(", ")}) — web không có khoá máy nào để khai`
		);
		const kho_luu_web = await page.evaluate(() =>
			Object.keys(localStorage).filter((k) => k.indexOf("kho_pda.") === 0)
		);
		khang_dinh(
			kho_luu_web.length === 0,
			`WEB · trang /kho đã ghi vào localStorage: ${kho_luu_web.join(", ")} — bản web phải không đổi hành vi`
		);

		// 5. VÒNG SỬA 1, MỤC F — ĐƯỜNG WEB KHÔNG ĐƯỢC ĐỔI MỘT CHỮ CỦA DẢI BÁO.
		//
		// Vế app của mục F đổi câu theo `_la_app()`, nên chỗ này là hàng rào giữ vế web:
		// trên web 401/403 THẬT LÀ phiên hết hạn (12 tiếng), và câu cũ phải tới nguyên
		// văn. Không có phép đo này thì một lượt "dọn dẹp" sau đó sẽ gộp hai câu lại và
		// không ai biết.
		await page.evaluate(() => {
			erpnext.kho_pda.KhoApp.la_khach = false;
			erpnext.kho_pda.KhoApp.di("menu");
		});
		await page.waitForTimeout(200);
		await page.evaluate((ham) => erpnext.kho_pda.KhoApp.goi(ham).catch(() => null), HAM_401);
		await page.waitForTimeout(300);
		const bao_web = await page.evaluate(() => ({
			man: erpnext.kho_pda.KhoApp.man_hien_tai,
			bao: (document.querySelector("#kho-app .kho-bao") || {}).textContent || "",
			// TASK 6 — màn thẻ của WEB không được có logo. Logo chỉ là cái nút của
			// lối ẩn; trên `/kho` không có địa chỉ nào để khai đè (trang tự biết máy
			// chủ của nó), nên một logo ở đây vừa là thay đổi giao diện của bản web
			// vừa là một cái nút bấm ba giây ra hộp sửa địa chỉ máy chủ trên MÁY
			// TÍNH VĂN PHÒNG. Đo được: bỏ phép rẽ nhánh `_la_app()` ở `man_the.js`
			// thì mọi khẳng định khác của cổng vẫn XANH.
			co_logo: !!document.querySelector(".man-the-logo"),
		}));
		khang_dinh(
			bao_web.man === "the",
			`WEB · 401 không đưa về màn thẻ trên web ("${bao_web.man}") — đường web đã đổi hành vi`
		);
		khang_dinh(
			bao_web.bao.includes("Phiên đã hết — quét thẻ để làm tiếp."),
			`WEB · dải báo 401 trên web đã ĐỔI CHỮ: ${JSON.stringify(bao_web.bao)}`
		);
		khang_dinh(
			bao_web.co_logo === false,
			"WEB · màn thẻ trên web có logo — lối ẩn (bấm giữ 3 giây ra ô sửa địa chỉ máy chủ) lọt ra bản web"
		);

		// TASK 6 — WEB KHÔNG ĐƯỢC HỎI BẢN CÀI. Trang `/kho` chạy trên máy tính của
		// văn phòng; ở đó không có APK nào để cài, nên một lời gọi ở đây vừa vô ích
		// vừa là một thay đổi hành vi của bản web — thứ ràng buộc của cả đợt cấm.
		// Đây cũng là khẳng định NGƯỢC của `do_nhac_ban_moi`: ở đó đòi đúng 1 lời
		// gọi, ở đây đòi 0 — một bản vá gọi vô điều kiện không qua được cả hai.
		const web_hoi_ban_cai = nhat_ky.slice(truoc_ca_web).filter((g) => g.ham === HAM_BAN_CAI);
		khang_dinh(
			web_hoi_ban_cai.length === 0,
			`WEB · trang /kho gọi ${HAM_BAN_CAI} ${web_hoi_ban_cai.length} lần — bản web đã đổi hành vi`
		);

		loi.push(...(await page.evaluate(() => window.__loi_async.slice())));
		if (loi.length) sai.push(`WEB · lỗi JS: ${loi.slice(0, 3).join(" | ")}`);
	} finally {
		await ctx.close();
	}
}

// ============================================================================
// VÒNG SỬA 1 — T5-4: HÀNG RÀO HÀNH VI CHO CƠ CHẾ "GIỜ MÁY CHỦ" (Task 5)
// ============================================================================
//
// Ba bài tĩnh trong `test_giao_dien.py` chỉ đóng được ca "ai đó XOÁ phần dây
// nối" (`ngay_may_chu()`/`gio_may_chu()` biến mất khỏi `_dung_luong()`). Người
// soát dựng được BỐN phép đảo ngược mà KHÔNG cổng nào trong kho từng bắt
// (F1–F4 của `task-5-soat-xet.md`) — nặng nhất là F1: đảo `ngay` ↔ `gio` ngay
// tại chỗ tiêm giữ nguyên cả ba cái tên lẫn hình dạng object rỗng ở nhánh web,
// nên ba bài tĩnh vẫn xanh 83/83, còn TRONG APP THÌ MẤT SẠCH CHIP HẠN DÙNG mà
// không một cổng nào biết. Lý do hai cổng CŨ không bắt được: cả `do_app` lẫn
// `do_qua_cau_native` đều tự đặt `KHO_BO_QUA_DONG_BO_GIO = true` (đúng, vì máy
// chủ giả CHUNG của chúng không biết đường dẫn `gio_may_chu` — một lời gọi thật
// tới đó sẽ rơi vào nhánh "đường dẫn LẠ" và đỏ vì một lý do không liên quan).
// Mục này KHÔNG đặt cờ đó, cho máy chủ giả trả một ngày/lô CỐ ĐỊNH, và khẳng
// định NỘI DUNG chip — đúng kỹ thuật đã đo bằng tay ở `/tmp/claude-1000/do_lech_gio.js`
// (Task 5, vòng đầu), nay đưa Ở LẠI TRONG KHO.
async function do_gio_may_chu_noi_dung(browser, goc_gia, nhat_ky) {
	const ctx = await browser.newContext({ viewport: { width: 360, height: 640 } });
	const page = await ctx.newPage();
	const loi = [];
	page.on("pageerror", (e) => loi.push(String(e)));
	// CỐ Ý KHÔNG đặt `KHO_BO_QUA_DONG_BO_GIO` — đây chính là điểm khác `do_app`.
	await page.addInitScript(script_khai({ KHO_MAY_CHU: goc_gia, KHO_LA_APP: true }));
	try {
		await page.goto("file://" + TRANG_APP);
		await page.waitForSelector("#kho-app .kho-than", { timeout: 5000 });
		await page.evaluate(() => {
			erpnext.kho_pda.KhoApp.la_khach = false;
			erpnext.kho_pda.KhoApp.nguoi_dung = "gio-may-chu-hanh-vi";
		});

		// F3 (đồng bộ luôn thoát sớm, không bao giờ gọi máy chủ) bị bắt NGAY ở đây:
		// nếu `_dong_bo_gio_may_chu()` không bao giờ gọi thật, điều kiện dưới đây
		// không bao giờ đúng và `waitForFunction` hết giờ → cổng đỏ với lý do RÕ.
		await page
			.waitForFunction(() => erpnext.kho_pda.KhoApp.ngay_may_chu() !== null, { timeout: 5000 })
			.catch(() => {
				sai.push(
					"GIO_MAY_CHU · ngay_may_chu() không bao giờ có giá trị — đồng bộ không chạy " +
						"(F3 của soát xét vòng 1: _dong_bo_gio_may_chu() có thể đang luôn thoát sớm)"
				);
			});

		const gio = await page.evaluate(() => ({
			ngay: erpnext.kho_pda.KhoApp.ngay_may_chu(),
			gio: erpnext.kho_pda.KhoApp.gio_may_chu(),
		}));
		// F1 (đảo `ngay` ↔ `gio` ở chỗ tiêm) lộ ra NGAY Ở ĐÂY: hai giá trị đọc từ
		// `KhoApp` (nguồn thật, không phụ thuộc lớp luồng) phải khớp đúng máy chủ
		// giả trả — nếu `man_tra_cuu.js` tiêm sai, HAI GIÁ TRỊ NÀY vẫn đúng (lỗi
		// nằm ở CHỖ TIÊM VÀO LỚP LUỒNG, không phải ở KhoApp) nên khẳng định quyết
		// định của F1 phải nằm ở CHIP dưới đây, không phải ở đây — nhưng vẫn khoá
		// luôn để một lỗi RÚT GIÁ TRỊ TỪ MÁY CHỦ (khác hẳn F1) không lẫn vào nhau.
		khang_dinh(
			gio.ngay === NGAY_MAY_CHU_GIA_CO_DINH,
			`GIO_MAY_CHU · KhoApp.ngay_may_chu() = ${JSON.stringify(gio.ngay)}, phải là ${NGAY_MAY_CHU_GIA_CO_DINH}`
		);
		khang_dinh(
			gio.gio === GIO_MAY_CHU_GIA_CO_DINH,
			`GIO_MAY_CHU · KhoApp.gio_may_chu() = ${JSON.stringify(gio.gio)}, phải là ${GIO_MAY_CHU_GIA_CO_DINH}`
		);
		// F2 (đảo dấu so sánh `>` → `<` ở `lech_gio_qua_nguong()`) — máy chủ giả trả
		// `moc_epoch_ms = Date.now()` nên lệch đo được ≈ 0, LUÔN dưới ngưỡng 10 phút:
		// đảo dấu sẽ làm hàm này trả `true` ở lệch KHÔNG ĐÁNG KỂ, báo oan thủ kho.
		const qua_nguong_khi_khong_lech = await page.evaluate(() => erpnext.kho_pda.KhoApp.lech_gio_qua_nguong());
		khang_dinh(
			qua_nguong_khi_khong_lech === false,
			"GIO_MAY_CHU · lech_gio_qua_nguong() = true khi lệch ≈ 0 — dấu so sánh ngưỡng có thể đã bị đảo (F2)"
		);

		// Quét lô CỐ ĐỊNH (HSD = ngày mai theo `NGAY_MAY_CHU_GIA_CO_DINH`) — đây là
		// khẳng định QUYẾT ĐỊNH cho cả F1 lẫn F3: nếu `man_tra_cuu.js` tiêm SAI
		// (F1: `ngay` nhận `gio_may_chu()`, một chuỗi giờ không khớp khuôn ngày)
		// hoặc lớp luồng không hề nhận được `ngay` (F3), `_ngay_con_lai` không suy
		// ra được số ngày còn lại và `trang_thai_han` rơi về `{muc:"khong"}` —
		// CHIP BIẾN MẤT. Khẳng định NỘI DUNG chip, không chỉ "có phần tử".
		await page.evaluate(() => erpnext.kho_pda.KhoApp.di("tra-cuu"));
		await page.waitForTimeout(200);
		await page.fill(".oq-nhap", "LO-T5-VONG-SUA-1");
		await page.press(".oq-nhap", "Enter");
		await page.waitForTimeout(400);
		const the = await page.evaluate(() => {
			const el = document.querySelector(".kho-han-chip");
			return {
				co_chip: !!el,
				muc: el ? Array.from(el.classList).find((c) => c.startsWith("muc-")) : null,
				chu: el ? el.textContent : null,
				than: document.querySelector("#kho-app .kho-than").innerText,
			};
		});
		khang_dinh(
			the.co_chip && the.muc === "muc-can" && (the.chu || "").includes("Còn 1 ngày"),
			`GIO_MAY_CHU · chip hạn dùng SAI hoặc MẤT: co_chip=${the.co_chip} muc=${the.muc} chu=${JSON.stringify(
				the.chu
			)} — phải là muc-can/"Còn 1 ngày" (thân màn: ${JSON.stringify(the.than.slice(0, 120))})`
		);

		loi.push(...(await page.evaluate(() => window.__loi_async.slice())));
		if (loi.length) sai.push(`GIO_MAY_CHU · lỗi JS: ${loi.slice(0, 3).join(" | ")}`);
	} finally {
		await ctx.close();
	}
}

// F4 (bỏ cơ chế tự làm mới sau `_NGUONG_LAM_MOI_GIO_MS`) cần MỘT máy chủ RIÊNG
// (đếm số lần CHÍNH XÁC `gio_may_chu` bị gọi, và một "hôm nay" có thể đổi giữa
// chừng) — dùng chung máy chủ ở trên sẽ lẫn số đếm với các khẳng định khác.
function dung_may_chu_gia_gio(hsd_tra_cuu) {
	const dem = { gio_may_chu: 0 };
	const may_chu = http.createServer((req, res) => {
		const u = new URL(req.url, "http://127.0.0.1");
		dat_cors(res);
		if (req.method === "OPTIONS") return res.writeHead(204).end();
		if (!u.pathname.startsWith("/api/method/")) return res.writeHead(404).end("khong co");
		const ham = u.pathname.slice("/api/method/".length);
		let than = "";
		req.on("data", (m) => (than += m));
		req.on("end", () => {
			const tra = (obj) => {
				res.writeHead(200, { "Content-Type": "application/json" });
				res.end(JSON.stringify({ message: obj }));
			};
			if (ham === HAM_GIO_MAY_CHU) {
				dem.gio_may_chu += 1;
				return tra({ ngay: NGAY_MAY_CHU_GIA_CO_DINH, gio: GIO_MAY_CHU_GIA_CO_DINH, moc_epoch_ms: Date.now() });
			}
			if (ham === HAM_TRA_CUU) {
				return tra({
					loai: "lo",
					so_lo: "LO-T5-F4",
					vat_tu: "VT-T5-F4",
					ten_hang: "Hàng giả — F4 tự làm mới",
					don_vi: "Hộp",
					hsd: hsd_tra_cuu,
					ton_theo_o: [],
				});
			}
			res.writeHead(500, { "Content-Type": "application/json" }).end("{}");
		});
	});
	return new Promise((ok) => may_chu.listen(0, "127.0.0.1", () => ok({ may_chu, cong: may_chu.address().port, dem })));
}

// Vá `Date` của TRANG (không phải của máy chủ) để nhảy đồng hồ thiết bị TỚI giữa
// phiên — kỹ thuật CHỈ DÙNG CHO BÀI TEST, không phải một phần app thật.
function script_ep_dong_ho_test() {
	return `
		(function () {
			var THAT = Date;
			var LECH = 0;
			function Gia(...args) {
				if (args.length === 0) return new THAT(THAT.now() + LECH);
				return new THAT(...args);
			}
			Gia.now = function () { return THAT.now() + LECH; };
			Gia.prototype = THAT.prototype;
			Gia.parse = THAT.parse;
			Gia.UTC = THAT.UTC;
			window.Date = Gia;
			window.__dat_lech_dong_ho = function (ms) { LECH = ms; };
		})();
	`;
}

async function do_gio_may_chu_tu_lam_moi(browser) {
	const { may_chu, cong, dem } = await dung_may_chu_gia_gio("2099-01-01");
	const goc_gia = `http://127.0.0.1:${cong}`;
	const ctx = await browser.newContext({ viewport: { width: 360, height: 640 } });
	const page = await ctx.newPage();
	await page.addInitScript(script_khai({ KHO_MAY_CHU: goc_gia, KHO_LA_APP: true }));
	await page.addInitScript(script_ep_dong_ho_test());
	try {
		await page.goto("file://" + TRANG_APP);
		await page.waitForSelector("#kho-app .kho-than", { timeout: 5000 });
		await page.evaluate(() => {
			erpnext.kho_pda.KhoApp.la_khach = false;
			erpnext.kho_pda.KhoApp.nguoi_dung = "gio-may-chu-tu-lam-moi";
		});
		const dong_bo_xong = await page
			.waitForFunction(() => erpnext.kho_pda.KhoApp.ngay_may_chu() !== null, { timeout: 5000 })
			.then(() => true)
			.catch(() => false);
		if (!dong_bo_xong) {
			sai.push("GIO_MAY_CHU_F4 · đồng bộ lúc mở không chạy được — bỏ qua phần còn lại của mục này");
			return;
		}
		const dem_luc_mo = dem.gio_may_chu;

		// CHƯA quá ngưỡng (+10 phút) — một lượt gọi mạng khác KHÔNG được kéo theo
		// một lượt `gio_may_chu` mới.
		await page.evaluate(() => window.__dat_lech_dong_ho(10 * 60 * 1000));
		await page.evaluate((ham) => erpnext.kho_pda.KhoApp.goi(ham, {}).catch(() => null), HAM_TRA_CUU);
		await page.waitForTimeout(300);
		const dem_truoc_nguong = dem.gio_may_chu;
		khang_dinh(
			dem_truoc_nguong === dem_luc_mo,
			`GIO_MAY_CHU_F4 · gọi lại gio_may_chu dù CHƯA quá ngưỡng làm mới (dem ${dem_luc_mo} → ${dem_truoc_nguong}) — spam mạng mỗi lượt quét`
		);

		// ĐÃ quá ngưỡng (+46 phút kể từ lúc mở) — lượt `goi()` kế tiếp PHẢI tự làm
		// mới. Đây là khẳng định quyết định của F4: bỏ cơ chế 45 phút thì con số
		// này đứng yên mãi ở `dem_luc_mo`.
		await page.evaluate(() => window.__dat_lech_dong_ho(46 * 60 * 1000));
		await page.evaluate((ham) => erpnext.kho_pda.KhoApp.goi(ham, {}).catch(() => null), HAM_TRA_CUU);
		await page.waitForTimeout(300);
		const dem_sau_nguong = dem.gio_may_chu;
		khang_dinh(
			dem_sau_nguong > dem_truoc_nguong,
			`GIO_MAY_CHU_F4 · KHÔNG tự làm mới sau khi quá ngưỡng 45 phút (dem đứng yên ở ${dem_sau_nguong}) — ` +
				"bộ nhớ đệm sẽ kẹt qua nửa đêm (F4 của soát xét vòng 1, cùng lớp lỗi T5-2)"
		);
	} finally {
		await ctx.close();
		may_chu.close();
	}
}

(async () => {
	const CAN_CO = [
		"index.html",
		"shim.js",
		"kho_pda.bundle.js",
		"kho_pda.bundle.css",
		"vendor/jquery.min.js",
	];
	for (const ten of CAN_CO) {
		if (!fs.existsSync(path.join(WWW, ten))) {
			console.error(`Thiếu ${ten} trong pda_app/www — chạy scripts/pda/dong-goi.sh trước.`);
			process.exit(1);
		}
	}

	if (!BAN_APP) {
		console.error(
			"Không đọc được `window.KHO_BAN_APP` trong pda_app/www/cau-hinh.js — chạy scripts/pda/dong-goi.sh trước.\n" +
				"(Dải nhắc bản mới của Task 6 dựng trên giá trị này; thiếu nó thì mọi khẳng định về nó vô nghĩa.)"
		);
		process.exit(1);
	}

	const { may_chu, nhat_ky, nhat_ky_pt, cong } = await dung_may_chu_gia();
	const goc_gia = `http://127.0.0.1:${cong}`;
	// TASK 6 — MÁY CHỦ THỨ HAI, chỉ cho lối ẩn. Cần một nhật ký RIÊNG: phép đo
	// quyết định là "lời gọi nằm ở nhật ký nào", mà dùng chung một nhật ký thì
	// không phân biệt được máy chủ cũ với máy chủ mới.
	//
	// NGHE TRÊN `192.168.61.129`, KHÔNG `127.0.0.1`, và đó KHÔNG phải chuyện tiện
	// tay: địa chỉ này được GÕ TAY vào lối ẩn, nên nó phải đi qua `loi_dia_chi_may
	// _chu()` — hàm chỉ cho `http://` tới các host có trong
	// `res/xml/network_security_config.xml` (Android chặn phần còn lại ở tầng dưới
	// mã của app). `127.0.0.1` không nằm trong danh sách đó, nên đo bằng nó là tự
	// ép mình phải NỚI luật ra cho bài test chạy được — đúng kiểu sửa làm hỏng thứ
	// đang canh. Cổng ngẫu nhiên (`listen(0)`) và mọi đường dẫn lạ trả 500, nên bài
	// vẫn không thể lẫn sang site thật đang chạy ở `192.168.61.129:8003`.
	const HOST_LOI_AN = "192.168.61.129";
	const may_chu_b = await dung_may_chu_gia(HOST_LOI_AN);
	const goc_gia_b = `http://${HOST_LOI_AN}:${may_chu_b.cong}`;
	console.log(`Cổng LỚP GỌI MẠNG — máy chủ giả ${goc_gia} (lối ẩn: ${goc_gia_b})\n`);

	const { chromium } = require(DUONG_PLAYWRIGHT);
	const browser = await chromium.launch();
	try {
		await do_app(browser, goc_gia, nhat_ky);
		await do_app_mat_mang(browser);
		// TASK 2B: cùng bản đóng gói, cùng máy chủ giả, nhưng lời gọi đi qua CẦU
		// HTTP NATIVE — đường mà APK phát hành thật sự đi.
		await do_qua_cau_native(browser, goc_gia, nhat_ky);
		await do_web(browser, goc_gia, nhat_ky);
		// VÒNG SỬA 1 — T5-4: hàng rào hành vi cho cơ chế "giờ máy chủ" (Task 5).
		await do_gio_may_chu_noi_dung(browser, goc_gia, nhat_ky);
		await do_gio_may_chu_tu_lam_moi(browser);
		// TASK 6 — hai hàng rào hành vi mới.
		await do_loi_an(browser, goc_gia, goc_gia_b, nhat_ky, may_chu_b.nhat_ky);
		await do_nhac_ban_moi(browser, goc_gia, nhat_ky);
		await do_hai_dai_nhac(browser, goc_gia, nhat_ky);
		await do_hoi_lai_sau_khi_hong(browser, goc_gia, nhat_ky);
	} catch (e) {
		sai.push(`ngoại lệ: ${(e && e.stack) || e}`);
	} finally {
		await browser.close();
		may_chu.close();
		may_chu_b.may_chu.close();
	}

	const la = nhat_ky.concat(may_chu_b.nhat_ky).filter(
		(g) =>
			![
				HAM_OK,
				HAM_401,
				HAM_CSRF,
				HAM_LOI_HTML,
				HAM_TRANG_500,
				HAM_401_TRONG,
				HAM_LOGOUT,
				HAM_GIO_MAY_CHU,
				HAM_TRA_CUU,
				HAM_BAN_CAI,
			].includes(g.ham)
	);
	if (la.length) sai.push(`máy chủ giả nhận đường dẫn LẠ: ${la.map((g) => g.ham).join(", ")}`);

	// KHẲNG ĐỊNH NGƯỢC (Task 3, ý kiến P2 của vòng soát Task 2B). Khẳng định
	// `method === "POST"` ở nửa NATIVE chỉ canh ĐÚNG MỘT lời gọi mẫu; nó không nói
	// gì về một lời gọi MỚI mà ai đó thêm vào sau. Mà `GET`/`HEAD`/`OPTIONS`/`TRACE`
	// KHÔNG đi qua cầu HTTP native: `native-bridge.js` đẩy chúng sang một URL proxy
	// `https://localhost/_capacitor_http_interceptor_?u=…` do `WebViewLocalServer`
	// chặn — một đường CHƯA AI ĐO, và trong bản đóng gói một đường tương đối còn
	// giải ra `file://`. Khẳng định dưới đây quét TOÀN BỘ nhật ký, nên lần đầu ai
	// thêm một `GET` là cổng đỏ ngay thay vì im lặng đi đường chưa đo.
	const khac_post = nhat_ky_pt.filter((g) => g.pt !== "POST");
	if (khac_post.length) {
		sai.push(
			`goi() phát lời gọi KHÁC POST: ${khac_post
				.map((g) => `${g.pt} ${g.duong_dan}`)
				.join(", ")} — GET/HEAD/OPTIONS không đi qua cầu native (Task 2B §3.3)`
		);
	}
	if (!nhat_ky_pt.length) {
		sai.push("nhật ký phương thức RỖNG — khẳng định 'chỉ POST' đang canh một cái không có gì");
	}

	// KHẲNG ĐỊNH NGƯỢC (Task 5) — BA HÀM ĐỒNG HỒ ĐÃ XOÁ KHỎI `shim.js` KHÔNG ĐƯỢC
	// QUAY LẠI. Đọc trên BUNDLE ĐÃ ĐÓNG GÓI (`pda_app/www/kho_pda.bundle.js`), không
	// trên các file nguồn `kho_pda/*.js`/`luong/*.js`: chính các file đó NHẮC LẠI ba
	// tên này trong CHÚ THÍCH để giải thích vì sao chúng không được gọi — một phép
	// grep mù trên nguồn sẽ đỏ oan vì chính lời giải thích của nó. esbuild cắt hết
	// chú thích khi đóng gói, nên nếu ba tên này còn xuất hiện trong bundle thì đó
	// LÀ một lời gọi thật — cùng lớp lỗi mà một máy lệch giờ đã đổi nghĩa hạn dùng
	// một lần (xem `shim.js`).
	const BUNDLE_APP = path.join(WWW, "kho_pda.bundle.js");
	if (fs.existsSync(BUNDLE_APP)) {
		const ma_bundle = fs.readFileSync(BUNDLE_APP, "utf-8");
		for (const ten of ["get_today", "now_time", "get_day_diff"]) {
			if (ma_bundle.includes(ten)) {
				sai.push(
					`bundle đã đóng gói còn nhắc "${ten}" — Task 5 xoá ba hàm đọc đồng hồ MÁY ` +
						"khỏi shim.js đúng vì chúng KHÔNG được gọi; một lời gọi mới là dựng lại " +
						"đúng cái bẫy đó (chạy `bench build --app erpnext` rồi `dong-goi.sh` lại " +
						"nếu bundle này là bản CŨ)."
				);
			}
		}
	} else {
		sai.push(`không thấy ${BUNDLE_APP} — chạy scripts/pda/dong-goi.sh trước`);
	}

	if (sai.length) {
		console.log(`FAIL — ${sai.length} phép khẳng định sai:`);
		for (const s of sai) console.log(`   · ${s}`);
	} else {
		console.log(`PASS — lớp gọi mạng đúng ở cả hai nơi (${nhat_ky.length} lời gọi ghi nhận).`);
		if (process.env.KHO_DEM_THEO_HAM) {
			const dem = {};
			for (const g of nhat_ky.concat(may_chu_b.nhat_ky)) dem[g.ham] = (dem[g.ham] || 0) + 1;
			console.log("   đếm theo hàm:", JSON.stringify(dem, null, 1));
		}
	}
	process.exit(sai.length ? 1 : 0);
})();
