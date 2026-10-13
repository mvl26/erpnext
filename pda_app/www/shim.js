// Các toàn cục mà bốn màn mượn của Frappe. Trong app KHÔNG có Frappe, nên vỏ tự
// cấp.
//
// VÌ SAO KHÔNG GÓI CẢ `frappe-web.bundle.js`: nó kéo theo socket.io, `frappe.boot`
// và cơ chế phiên của web — đúng cái "web" mà đợt này sinh ra để bỏ. Tập toàn cục
// thật sự cần đã đếm được bằng grep trên `erpnext/public/js/kho_pda/*.js` +
// `erpnext/public/js/warehouse_operations/luong/*.js` (hai thư mục duy nhất mà
// `kho_pda.bundle.js` `import`), nhỏ và đứng yên:
//
//     __()                          142 lần
//     flt()                          48 lần
//     $() jQuery                     28 lần   (gói riêng ở vendor/jquery.min.js)
//     frappe.provide                 18 lần
//     frappe.utils.escape_html       11 lần
//     frappe.datetime.str_to_user     4 lần
//     frappe.utils.icon               1 lần
//     frappe.csrf_token               4 lần   (đọc/ghi thuộc tính trong `vo.js::goi()`,
//                                              cần `frappe` tồn tại; xem cuối file)
//
// SỐ ĐO LỆCH VỚI BẢNG Ở BRIEF/SPEC §5 — bảng đó đếm cả trang Desk: `format_number`
// KHÔNG xuất hiện lần nào trong bundle; `frappe.utils.flt` chỉ có trong chú thích;
// `frappe.datetime.now_time`/`get_today`/`get_day_diff` chỉ được bốn trang Desk
// (`warehouse_operations/page/*/*.js`) gọi, KHÔNG nằm trong bundle này. Vẫn cấp cả
// ba theo brief (chi phí bằng không, và Task 5 sẽ thay) — nhưng đừng tưởng bundle
// đang dùng chúng.
//
// `__()` trả nguyên chuỗi: hệ thống dùng tiếng Việt, không có bản dịch thứ hai
// đang chờ (xem Ruling 23 của đợt /kho).
//
// GIỮ TRÊN MỘT ĐƯỜNG THẲNG VỚI FRAPPE: mỗi hàm dưới đây phải trả ĐÚNG THỨ bản web
// trả, không chỉ "trả một cái gì đó". Một shim có mặt mà trả sai (icon trả
// `undefined`, `flt` trả chuỗi, `__` bỏ qua `{0}`) KHÔNG ném lỗi nào — nó chỉ in
// chữ "undefined"/số sai/`{0}` ra màn 4 inch. Cổng
// `scripts/kiem_giao_dien/kiem_ban_dong_goi.js` vì thế soi cả ba chuỗi đó.

(function () {
	window.frappe = window.frappe || {};

	// Nguyên văn `frappe.provide` của `frappe/public/js/frappe/provide.js`: đi dần
	// theo chuỗi tên, CHỈ tạo nhánh còn THIẾU. Không phá nhánh đã có là điều kiện
	// bắt buộc — `kho_pda.bundle.js` gọi `frappe.provide("erpnext.kho_pda")` 18 lần
	// (đầu mỗi file); tạo mới mỗi lần sẽ vứt `erpnext.kho_pda.KhoApp` mà file trước
	// vừa gán.
	frappe.provide = function (duong) {
		var phan = duong.split(".");
		var cha = window;
		for (var i = 0; i < phan.length; i++) {
			if (!cha[phan[i]]) cha[phan[i]] = {};
			cha = cha[phan[i]];
		}
		return cha;
	};

	// `$.format` của Frappe (`frappe/public/js/frappe/format.js`) — thay `{0}`,
	// `{1}`… bằng phần tử tương ứng của mảng, và `{}` bằng phần tử kế tiếp.
	//
	// MỘT KHÁC BIỆT CÓ CHỦ Ý so với bản gốc: khoá KHÔNG phải số (`{ten}`) thì bản
	// gốc để hàm thay thế trả `undefined`, tức in ra chữ "undefined" giữa câu. Ở
	// đây giữ nguyên `{ten}` — không file nào trong bundle dùng khoá chữ, và in
	// nguyên chỗ trống thì người đọc còn biết là câu chưa được ghép, còn "undefined"
	// thì không.
	function _thay_cho_trong(chu, doi_so) {
		var stt = 0;
		return chu.replace(/\{(\w*)\}/g, function (khop, khoa) {
			if (khoa === "") khoa = stt++;
			if (khoa == +khoa) return doi_so[khoa] !== undefined ? doi_so[khoa] : khop;
			return khop;
		});
	}

	// `__(chu, doi_so)` — KHÔNG phải `(s) => s`. `man_the.js` gọi
	// `__("Máy chủ: {0}", [location.origin])` và `luong/tra_cuu.js::_dich` chuyển
	// tiếp `doi_so` cho `"Còn {0} ngày"`: bỏ qua tham số thứ hai là in nguyên `{0}`
	// ra màn hình, không lỗi, không ai biết cho tới khi thủ kho nhìn thấy.
	//
	// Không có bảng dịch: trả nguyên chuỗi nguồn (tiếng Việt) sau khi ghép chỗ trống.
	window.__ = function (chu, doi_so) {
		if (!chu) return chu;
		if (typeof chu !== "string") return chu;
		if (doi_so && typeof doi_so === "object") return _thay_cho_trong(chu, doi_so);
		return chu;
	};
	frappe._ = window.__;

	// `flt` PHẢI trả một SỐ. Trả chuỗi thì `flt(x).toLocaleString("vi-VN", …)` —
	// khuôn dùng ở cả bốn màn — vẫn chạy (String cũng có `toLocaleString`) nhưng in
	// ra con số KHÔNG nhóm hàng nghìn và không cắt phần thập phân: sai lặng lẽ, đúng
	// hạng lỗi nguy hiểm nhất của cả file này.
	//
	// XỬ LÝ CHUỖI PHẢI THEO ĐÚNG `number_format` CỦA SITE, không phải "bỏ dấu phẩy".
	// System Settings của erptest.local/miyano đặt `number_format = "#.###,##"` (đọc
	// thật bằng `bench … execute frappe.db.get_single_value`), tức dấu NHÓM NGHÌN là
	// `.` và dấu THẬP PHÂN là `,` — đúng kiểu Việt Nam, và cũng là lý do bốn màn hiện
	// số qua `toLocaleString("vi-VN", …)`.
	//
	// ĐO ĐƯỢC, không suy đoán: chạy cùng một bộ giá trị qua `flt` của trang `/kho`
	// THẬT và qua hàm này rồi so từng cặp (kịch bản dùng một lần, Task 1). Bản đầu
	// của hàm này chỉ `.replace(/,/g, "")` — chép theo `_flt` của `luong/xep_hang.js`
	// — và LỆCH ngay ở `flt("1,234.5")`: web ra `1.2345`, app ra `1234.5`. Bản dưới
	// đây khớp web ở cả sáu giá trị đã đo.
	//
	// (`_flt` trong `luong/xep_hang.js`/`luong/lay_hang.js` giữ nguyên luật bỏ dấu
	// phẩy của nó — nó chỉ đọc `.value` của `<input type="number">`, mà HTML quy định
	// giá trị đó luôn dùng `.` làm dấu thập phân bất kể ngôn ngữ máy. Đừng "thống
	// nhất" hai hàm: chúng nhận hai loại đầu vào khác nhau.)
	//
	// KHÔNG CHÉP NHÁNH BỎ KÝ HIỆU TIỀN TỆ của `flt` gốc — đây là chỗ DUY NHẤT hàm
	// này lệch với Frappe, cố ý, và đã đo cả hai chiều (soát xét Task 1 P2 →
	// soát xét Task 2 mục B3 → QUYẾT Ở TASK 2B).
	//
	// NHÁNH ĐÓ LÀ GÌ (`frappe/public/js/frappe/utils/number_format.js:14-19`): thấy
	// chuỗi CÓ DẤU CÁCH thì `v.split(" ")`; nếu `parseFloat` của mẩu ĐẦU ra `NaN`
	// thì lấy MẨU CUỐI. Luật này sinh ra cho `"VND 42"` / `"1.200 ₫"`.
	//
	// NGUYÊN NHÂN KHÔNG PHẢI MỘT `trim()`. Hàm này KHÔNG hề gọi `trim` — chính
	// `parseFloat` tự bỏ khoảng trắng hai đầu. Chẩn đoán "shim trim() trước" của
	// vòng soát Task 1 là SAI, và người soát đã tự đính chính ở vòng Task 2; ghi
	// lại ở đây để không ai đi lại đường đó.
	//
	// LỆCH CẢ HAI CHIỀU — mỗi chiều một bên thắng, không phải "shim luôn rộng hơn":
	//     flt("  42  ")  → web **0**   / ở đây **42**   (mẩu cuối là chuỗi rỗng)
	//     flt("VND 42")  → web **42**  / ở đây **0**    (mẩu đầu "VND" không phải
	//                                                    số → web lấy "42"; ở đây
	//                                                    `parseFloat("VND 42")` = NaN)
	// Đúng ra là: sai khác nằm ở MỌI chuỗi có dấu cách, không riêng chuỗi có khoảng
	// trắng thừa. Các chuỗi có dấu cách mà hai bên VẪN khớp (đã đo): "42 VND"→42,
	// "350 Bộ"→350, "1.234,5 Bộ"→1234.5, "1 234,5"→1, "12 34"→12, "a b"→0.
	//
	// GIỮ NGUYÊN, không chép nhánh đó về cho "khớp" — quyết theo một phép ĐẾM CHỖ
	// GỌI, không theo cảm giác. `window.flt` của shim chỉ phục vụ `kho_pda/man_*.js`
	// (bốn màn); liệt kê đủ 12 chỗ gọi `flt(` trong bốn file đó thì đối số luôn là
	// một trong ba thứ: (a) trường SỐ của máy chủ (`x.so_luong`, `x.he_so`,
	// `c.so_luong`), (b) số do lớp luồng giữ (`st.cho.so_luong`, `st.cho.so_kien` —
	// `luong/*.js` đã ép qua `_flt` của chính nó nên luôn là `number`), (c) kết quả
	// của một phép cộng. KHÔNG chỗ nào nhận chuỗi tiền tệ, và bốn màn không hiện
	// tiền — chỉ số lượng, tồn kho, hệ số quy đổi.
	// (`_flt` trong `luong/xep_hang.js`/`luong/lay_hang.js` là hàm KHÁC, đọc
	// `.value` của `<input type="number">` — xem đoạn trên.)
	//
	// Chép nhánh đó về là dựng một nhánh chưa bao giờ chạy CHỈ ĐỂ tái lập `0` cho
	// `"  42  "` — một con số đọc được rõ ràng — trong khi chính nhánh ấy lại làm
	// HỎNG `"VND 42"` theo chiều ngược. Đổi một lệch lý thuyết lấy một lệch lý
	// thuyết khác, cộng thêm một nhánh chết. Ghi ra đây để không ai đọc "shim khớp
	// Frappe" thành "khớp 18/18": nó khớp ở mọi đầu vào mà bốn màn thật sự đưa vào,
	// và CỐ Ý lệch ở lớp chuỗi tiền tệ mà không màn nào sinh ra.
	window.flt = function (gia_tri, so_le) {
		var n;
		if (gia_tri == null || gia_tri === "") {
			n = 0;
		} else if (typeof gia_tri === "number") {
			n = isNaN(gia_tri) ? 0 : gia_tri;
		} else {
			// Bỏ dấu nhóm nghìn `.` TRƯỚC, rồi mới đổi dấu thập phân `,` thành `.` —
			// đảo thứ tự hai bước này là "1.234,5" ra 1.2345 thay vì 1234,5.
			n = parseFloat(String(gia_tri).replace(/\./g, "").replace(/,/g, "."));
			if (isNaN(n)) n = 0;
		}
		// `so_le` KHÔNG được file nào trong bundle truyền (đo bằng grep: mọi lời gọi
		// đều là `flt(x)` một tham số). Nhận nó ở đây chỉ để một lời gọi hai tham số
		// không âm thầm bị bỏ qua. Làm tròn bằng `toFixed` — có thể lệch với chế độ
		// làm tròn cấu hình được của Frappe ở chữ số cuối; chưa có chỗ nào phụ thuộc.
		if (so_le === undefined || so_le === null) return n;
		return Number(n.toFixed(so_le));
	};

	// KHÔNG file nào trong bundle gọi `format_number` (grep: 0 lần) — có mặt vì brief
	// Task 1 liệt kê, để một màn thêm sau không chết vì thiếu. Dùng `vi-VN` cho khớp
	// với `toLocaleString("vi-VN", …)` mà bốn màn đang tự gọi.
	window.format_number = function (gia_tri, _khuon, so_le) {
		return window.flt(gia_tri).toLocaleString("vi-VN", {
			minimumFractionDigits: so_le || 0,
			maximumFractionDigits: so_le === undefined || so_le === null ? 3 : so_le,
		});
	};

	frappe.utils = frappe.utils || {};

	// Nguyên văn bảng thay thế của `frappe/public/js/frappe/utils/utils.js` — KHÔNG
	// được rút gọn. `vo.js::_dam()` và `man_*.js::_e()` dựa vào hàm này để một tên
	// hàng hay một câu báo LẤY TỪ MÁY CHỦ không nhét được thẻ HTML vào màn; một bản
	// "thoát tạm" bỏ sót `"`/`'`/`` ` ``/`=` là một hồi quy an ninh thật, và cổng
	// nào cũng xanh.
	frappe.utils.escape_html = function (chu) {
		if (!chu) return "";
		var bang = {
			"&": "&amp;",
			"<": "&lt;",
			">": "&gt;",
			'"': "&quot;",
			"'": "&#39;",
			"`": "&#x60;",
			"=": "&#x3D;",
		};
		return String(chu).replace(/[&<>"'`=]/g, function (ky_tu) {
			return bang[ky_tu] || ky_tu;
		});
	};

	// `o_quet.js` nội suy giá trị này THẲNG vào chuỗi HTML của ô quét. Bản web trả
	// một thẻ `<svg><use xlink:href="#icon-scan"></use></svg>` trỏ vào tập sprite
	// icon của Desk — tập đó KHÔNG được gói vào app, nên một thẻ `<use>` treo sẽ chỉ
	// là một ô trống.
	//
	// Trả `""`, KHÔNG để hàm rơi về `undefined`: `undefined` nội suy vào template
	// string in ra ĐÚNG CHỮ "undefined" cạnh ô quét — không lỗi, không cổng nào thấy,
	// chỉ thủ kho thấy.
	frappe.utils.icon = function () {
		return "";
	};

	// Bí danh — chỉ xuất hiện trong chú thích của lớp luồng, không lời gọi thật nào
	// trong bundle (grep). Giữ cùng một hàm để hai đường không bao giờ lệch nhau.
	frappe.utils.flt = window.flt;

	frappe.datetime = frappe.datetime || {};

	// Khuôn hiển thị của site erptest.local/miyano: System Settings `date_format` =
	// "dd-mm-yyyy", `time_format` = "HH:mm:ss" (đọc thật bằng
	// `bench --site erptest.local execute frappe.db.get_single_value`). Viết cứng ở
	// đây vì app không có `frappe.boot` để hỏi; đổi khuôn trên site mà quên file này
	// thì app và web hiển thị ngày khác nhau.
	//
	// KHÔNG dùng `moment` (bản web đi qua `moment`/`moment-timezone`): gói thêm hai
	// thư viện đó vào APK chỉ để định dạng lại một chuỗi `"YYYY-MM-DD"` là đắt hơn
	// hẳn việc cắt chuỗi.
	frappe.datetime.str_to_user = function (gia_tri) {
		if (!gia_tri) return "";
		var chu = String(gia_tri).trim();
		// Máy chủ trả `"YYYY-MM-DD"` (Date) hoặc `"YYYY-MM-DD HH:MM:SS"` (Datetime) —
		// `man_lay_hang.js` đưa vào cả hai dạng. Tách phần ngày ra, phần còn lại (giờ)
		// giữ nguyên rồi ghép lại sau.
		var phan = chu.split(" ");
		var ngay = phan[0];
		var gio = phan.length > 1 ? phan.slice(1).join(" ") : "";
		var o = /^(\d{4})-(\d{2})-(\d{2})$/.exec(ngay);
		// LỆCH CÓ CHỦ Ý VỚI BẢN WEB, đã đo: với một chuỗi không phải ngày ("rác"),
		// `moment` của bản web trả đúng chữ "Invalid date"; ở đây trả NGUYÊN chuỗi
		// vào. Máy chủ không gửi ngày rác cho bốn màn này (các trường `hsd`/
		// `ngay_nhap`/`ngay_san_xuat` đều là Date của Frappe), nên cả hai nhánh đều
		// là nhánh chết — chọn nhánh mà nếu có ngày xảy ra thì thủ kho còn đọc được
		// dữ liệu, thay vì một câu tiếng Anh không nói lên điều gì.
		if (!o) return chu;
		var ra = o[3] + "-" + o[2] + "-" + o[1];
		return gio ? ra + " " + gio : ra;
	};

	// TASK 5 — `get_today`/`now_time`/`get_day_diff` ĐÃ BỊ XOÁ, KHÔNG PHẢI QUÊN.
	//
	// Ba hàm này (bản trước Task 5) đọc ĐỒNG HỒ CỦA MÁY ANDROID, mà máy quét trong
	// kho không đảm bảo đúng giờ (spec §8) — một đợt trước, lớp luồng lẳng lặng đổi
	// từ giờ SITE sang giờ MÁY TRẠM qua đúng cửa này, làm phán quyết HẾT HẠN của
	// một lô vật tư y tế đổi nghĩa mà không ai biết. Trước khi xoá, brief Task 5 tự
	// đo lại số lần gọi ba hàm này TRONG PHẠM VI BUNDLE (`kho_pda/*.js` +
	// `warehouse_operations/luong/*.js`, hai thư mục duy nhất `kho_pda.bundle.js`
	// `import`): 0 — lớp luồng tự dùng `Date` qua `gio`/`ngay` TIÊM TỪ NGOÀI
	// (`tao({goi, gio, ngay})`), không hề gọi `frappe.datetime.*`. Bốn trang Desk
	// gọi ba hàm này, nhưng Desk không nạp `shim.js` (chỉ nạp trong
	// `pda_app/www/`) — Desk có `frappe-web.bundle.js` thật, không đụng tới bản
	// giả này bao giờ.
	//
	// XOÁ, KHÔNG SỬA LẠI CHO "ĐÚNG HƠN": giữ ba hàm này (dù có vá cho đọc giờ máy
	// chủ) là giữ một API "trông như frappe.datetime thật" mà bất kỳ ai viết thêm
	// một màn sau này CÓ THỂ lỡ gọi tới, tưởng nó an toàn — đúng cái bẫy mà Task 5
	// sinh ra để dứt điểm. Giờ máy chủ nay sống ở ĐÚNG MỘT NGUỒN
	// (`KhoApp._dong_bo_gio_may_chu()`, `kho_pda/vo.js`), tiêm thẳng vào lớp luồng
	// qua `man_tra_cuu.js::_dung_luong()` — không đi qua `frappe.datetime` nữa.
	//
	// KHẲNG ĐỊNH NGƯỢC (cùng tinh thần Ruling 16 của đợt /kho):
	// `scripts/kiem_giao_dien/kiem_goi_mang.js` grep NGƯỢC ba tên này trong
	// `kho_pda.bundle.js` ĐÃ ĐÓNG GÓI — ai đó sau này lỡ gọi lại một trong ba (trực
	// tiếp hoặc qua một shim mới) sẽ bị bắt ngay, không phải chờ tới lúc một máy
	// lệch giờ làm sai một phán quyết hết hạn thật. Đo trên BUNDLE, không trên các
	// file nguồn `kho_pda/*.js`/`luong/*.js`: chính các file đó CHÉP LẠI ba tên này
	// trong CHÚ THÍCH để giải thích vì sao chúng không được gọi — một phép grep mù
	// trên nguồn sẽ đỏ oan vì chính lời giải thích của nó; esbuild cắt hết chú thích
	// khi đóng gói nên bundle không còn dấu vết nào ngoài mã CHẠY THẬT.

	// `vo.js::goi()` ĐỌC và GHI `frappe.csrf_token`. Trong app không có cookie phiên
	// nên cũng không có CSRF — khai một chuỗi rỗng để chốt `if (frappe.csrf_token &&
	// …)` ở đó tự bỏ qua, thay vì để thuộc tính vắng mặt và người đọc file này phải
	// đoán xem có phải quên không.
	//
	// TASK 2 ĐÃ bỏ hẳn CẢ HAI nhánh CSRF khi `KHO_LA_APP` (`!this._la_app() && …` ở
	// đầu `goi()` và ở nhánh `CSRFTokenError`), nên thuộc tính này trong app nay là
	// cái chốt cửa THỨ HAI chứ không còn là cái duy nhất. Vẫn giữ: nó vẫn bị ĐỌC/GHI
	// nếu ai đó gỡ cờ `KHO_LA_APP` để thử một bản đóng gói trên web, và vắng mặt thì
	// đó là một `TypeError` chứ không phải một nhánh bị bỏ qua.
	frappe.csrf_token = "";
})();
