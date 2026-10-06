// Lớp LUỒNG của màn Tra cứu — phần QUYẾT ĐỊNH ("quét mã này ra cái gì", "gọi nó là
// gì", "còn hạn hay không") tách khỏi phần VẼ, dùng chung cho CẢ HAI nơi: màn app
// PDA (`kho_pda/man_tra_cuu.js`) và trang Desk cũ
// (`warehouse_operations/page/quet_ma_tra_cuu/quet_ma_tra_cuu.js`, Bước 6 của brief
// Task 2). Một chỗ quyết định, hai chỗ chỉ khác nhau ở cách vẽ — đây là khuôn Task
// 3–5 sẽ theo lại.
//
// VÒNG SỬA 1 (soát xét `task-2-soat-xet.md`): bản đầu chỉ chuyển được BA quyết định
// (chuẩn hoá mã, tên hàm máy chủ, đổi `null`→`"khong_ro"`) — phần LỚN luật (nhãn
// hiển thị của `loai`, câu báo, chính sách lịch sử, ngưỡng cận date) vẫn nằm ở hai
// lớp vẽ, và Desk còn LẬT NGƯỢC phán quyết `loai`/`bao` của lớp luồng
// (`quet_ma_tra_cuu.js` cũ: `const d = kq.du_lieu || {loai: null}` vứt cả hai).
// Vòng này chuyển thêm BỐN thứ vào đây — xem từng khối bên dưới.
//
// `goi` là hàm gọi máy chủ, TIÊM TỪ NGOÀI (không gọi thẳng `KhoApp.goi` hay
// `frappe.xcall`): `KhoApp.goi` ở app PDA tự lo phiên hết hạn/mất mạng (xem
// `kho_pda/vo.js`), `frappe.xcall` ở Desk. Tiêm từ ngoài là điều kiện DUY NHẤT để
// file này chạy được trong Node lúc `node --test` — ở đó không có `frappe`/`window`.
//
// `loai` TRẢ NGUYÊN VĂN giá trị máy chủ trả về (`"lo" | "vat_tu" | "kho" | "o"`,
// xem docstring `erpnext/warehouse_operations/vitri/quet.py`), CHỈ đổi tên khi máy
// chủ trả rỗng/`null` thành `"khong_ro"`. CỐ Ý không thu hẹp còn ba giá trị như một
// cách đọc hẹp của brief (brief chỉ liệt kê `"lo" | "o" | "khong_ro"` vì bốn bài
// test mẫu chỉ chạm tới ba giá trị đó): Bước 6 đòi trang Desk vẫn vẽ được cả bốn
// loại thẻ y như cũ (`{lo, vat_tu, o, kho}[d.loai]`, nguyên trong
// `quet_ma_tra_cuu.js`) — thu hẹp `loai` ở đây thì quét mã vật tư/mã kho trên
// trang Desk (vốn KHÔNG được đổi) sẽ đổ về "Không nhận ra mã này", một hồi quy
// thật. Xem quyết định này trong báo cáo Task 2.

// `__()` (hàm dịch của Frappe) không tồn tại trong Node lúc `node --test` — bọc qua
// một hàm portable thay vì gọi thẳng `__`, để file này chạy được ở CẢ HAI môi trường
// mà bài test không phải tự dựng một `__` giả toàn cục. `typeof __` an toàn với một
// biến chưa từng khai báo (không ném lỗi như đọc thẳng `__`). Nhận thêm `doi_so`
// (mảng) để khớp chữ ký `__(chu, doi_so)` của Frappe (thay `{0}` bằng phần tử tương
// ứng) — cần cho `trang_thai_han()` bên dưới ("Còn {0} ngày").
function _dich(chu, doi_so) {
	if (typeof __ === "function") return __(chu, doi_so);
	if (!doi_so) return chu;
	return chu.replace(/\{(\d+)\}/g, (_, i) => (doi_so[i] !== undefined ? doi_so[i] : ""));
}

// Nhãn hiển thị của `loai` — HỢP ĐỒNG của lớp luồng (`quet.py`) thì tên hiển thị
// của hợp đồng đó cũng phải là một, không phải mỗi lớp vẽ tự chép một bản (soát xét
// vòng 1, P2: `man_tra_cuu.js` và `quet_ma_tra_cuu.js` từng lặp NGUYÊN VĂN cùng một
// object `{lo, vat_tu, o, kho}` — thêm một `loai` mới ở máy chủ phải nhớ sửa hai
// nơi). Trả chuỗi ĐÃ DỊCH — gọi trực tiếp lúc vẽ, không cần lớp vẽ tự bọc `__()`
// thêm lần nữa (khác `MO_TA_KHONG_RO` bên dưới, xem lý do ở đó).
const _NHAN_LOAI = { lo: "Lô", vat_tu: "Vật tư", o: "Vị trí", kho: "Kho" };
function nhan_loai(loai) {
	return _dich(_NHAN_LOAI[loai] || "Không rõ");
}

// Câu báo cho ca "không nhận ra" — MỘT nơi, không phải ba (soát xét vòng 1, P4:
// "Không nhận ra mã này" từng nằm nguyên văn ở `tra_cuu.js`, `man_tra_cuu.js` VÀ
// `quet_ma_tra_cuu.js`). `bao` do `quet()` trả về ĐÃ dịch sẵn (mọi nơi gọi chỉ hiện
// thẳng, không tự dịch lại) — còn `MO_TA_KHONG_RO` là câu mô tả DÀI hơn, chỉ dùng
// làm phụ đề của thẻ "không nhận ra" (không phải một phán quyết, không cần đi qua
// `bao`) nên xuất RAW (chưa dịch): hai lớp vẽ đã có sẵn thói quen tự bọc `__()`
// quanh mọi chuỗi tĩnh khác của chúng, xuất raw để chúng làm y như vậy, không tạo
// thêm một quy ước dịch thứ hai chỉ riêng cho một chuỗi.
const CAU_KHONG_RO = "Không nhận ra mã này.";
const MO_TA_KHONG_RO =
	"Không phải tem lô, tem vị trí, mã vật tư hay mã kho. Có thể vừa quét nhầm mã trên vỏ thùng.";

// Ngưỡng + phân loại "cận date" — CHUYỂN từ lớp vẽ Desk vào đây (soát xét vòng 1,
// P5: trước vòng sửa này chỉ Desk có, app quét CÙNG một lô lại không hiện hạn còn
// bao nhiêu ngày — người soát xếp mức NẶNG dù kế thừa từ trước Task 2, vì "thủ kho
// quét tem giữa kho cần biết lô sắp hết hạn hơn người ngồi máy tính"). THUẦN
// `Date`, KHÔNG `frappe.datetime.get_day_diff`/`get_today()` — hai hàm đó chỉ có
// trong trình duyệt, lớp luồng phải chạy được trong Node.
const NGAY_CAN_DATE = 90;

// Số ngày giữa `hom_nay` và `hsd`, cả hai ở dạng `YYYY-MM-DD`. THUẦN — không đọc
// đồng hồ nào: "hôm nay là ngày nào" là một câu hỏi về MÔI TRƯỜNG, trả lời ở
// `tao()` qua tham số tiêm `ngay` (xem đó).
function _ngay_con_lai(hsd, hom_nay) {
	const a = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(hsd));
	const b = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(hom_nay));
	if (!a || !b) return null;
	const hom_nay_utc = Date.UTC(Number(b[1]), Number(b[2]) - 1, Number(b[3]));
	const hsd_utc = Date.UTC(Number(a[1]), Number(a[2]) - 1, Number(a[3]));
	return Math.round((hsd_utc - hom_nay_utc) / 86400000);
}

/** `{muc, chu}` — `muc` ∈ `"khong" | "het" | "can" | "con"` (dùng làm hậu tố lớp
 * CSS `muc-*` ở cả hai lớp vẽ), `chu` là câu ĐÃ DỊCH ("Còn N ngày"/"Hết hạn N
 * ngày"/"Hết hạn hôm nay"/rỗng). Không có `hsd` (lô không quản lý hạn) thì `muc:
 * "khong"` — không phải lỗi, không phải "hết hạn". THUẦN: `hom_nay` truyền vào. */
function _trang_thai_han(hsd, hom_nay) {
	if (!hsd) return { muc: "khong", chu: "" };
	const con = _ngay_con_lai(hsd, hom_nay);
	if (con === null) return { muc: "khong", chu: "" };
	if (con < 0) return { muc: "het", chu: _dich("Hết hạn {0} ngày", [-con]) };
	if (con === 0) return { muc: "het", chu: _dich("Hết hạn hôm nay") };
	if (con <= NGAY_CAN_DATE) return { muc: "can", chu: _dich("Còn {0} ngày", [con]) };
	return { muc: "con", chu: _dich("Còn {0} ngày", [con]) };
}

// Ngày MÁY TRẠM dạng `YYYY-MM-DD` — mặc định khi không ai tiêm `ngay`, cùng lẽ
// `_gio_may_tram` bên dưới. Dựng từ `getFullYear/getMonth/getDate` chứ KHÔNG
// `toISOString()`: `toISOString` đổi sang UTC trước, nên lúc 23:30 giờ VN nó trả
// NGÀY HÔM SAU — đúng loại lệch một ngày mà hàm này sinh ra để tránh.
function _ngay_may_tram() {
	const d = new Date();
	const hai_so = (n) => String(n).padStart(2, "0");
	return `${d.getFullYear()}-${hai_so(d.getMonth() + 1)}-${hai_so(d.getDate())}`;
}

// Giờ MÁY TRẠM (múi giờ trình duyệt) — dùng làm MẶC ĐỊNH khi không ai tiêm `gio`
// (ca `node --test`, và ca app PDA — máy quét đứng NGAY tại kho, giờ máy trạm với
// giờ site LUÔN là một). Thuần `Date`, KHÔNG `frappe.datetime.now_time()` (chỉ có
// trong trình duyệt, mà lớp luồng còn phải chạy trong Node).
function _gio_may_tram() {
	const d = new Date();
	const hai_so = (n) => String(n).padStart(2, "0");
	return `${hai_so(d.getHours())}:${hai_so(d.getMinutes())}:${hai_so(d.getSeconds())}`;
}

/** `gio` — hàm lấy giờ ghi vào lịch sử, TIÊM TỪ NGOÀI, CÙNG KHUÔN với `goi` (soát
 * xét vòng 2, M4). VÌ SAO CẦN TIÊM: trước vòng này lớp luồng tự gọi `new Date()`
 * (giờ máy trạm) ở MỌI nơi — đúng cho app (chạy ngay trên máy quét trong kho) NHƯNG
 * SAI cho Desk, nơi vốn ghi giờ bằng `frappe.datetime.now_time()` (giờ SITE, đo
 * được trước khi gộp lớp) — không tiêm mà tự gọi `new Date()` cho cả hai thì một
 * máy tính văn phòng lệch múi giờ với server sẽ thấy dấu giờ trong lịch sử ĐỔI
 * NGHĨA âm thầm, không ai biết vì trước đó không hề lệch (đo cùng múi giờ thì
 * "19:37" cả hai, im lặng che mất khác biệt). Mặc định `_gio_may_tram` (giờ máy
 * trạm) khi không truyền `gio` — đúng cho app VÀ cho Node lúc `node --test` (không
 * có `frappe.datetime` ở đó); Desk truyền `gio: () => frappe.datetime.now_time()`
 * để giữ đúng ý nghĩa CŨ của nó.
 *
 * `ngay` — hàm trả NGÀY HÔM NAY dạng `"YYYY-MM-DD"`, CÙNG KHUÔN với `gio` (soát
 * xét tổng, M2). VÌ SAO CẦN TIÊM, và vì sao nó ĐẮT HƠN `gio` nhiều: `gio` chỉ là
 * dấu giờ trang trí trong lịch sử quét, còn `ngay` là thứ quyết định một lô vật tư
 * y tế HẾT HẠN hay CÒN HẠN (`trang_thai_han` bên dưới). Trước khi gộp lớp, trang
 * Desk tính bằng `frappe.datetime.get_day_diff(hsd, frappe.datetime.get_today())`,
 * mà `get_today` đi qua `moment.tz(frappe.boot.time_zone.user || .system)` — MÚI
 * GIỜ CỦA SITE. Bản gộp lớp đầu tiên gọi thẳng `new Date()` — MÚI GIỜ CỦA MÁY: một
 * máy tính văn phòng đặt sai múi giờ so với site đổi nghĩa ngày hết hạn, âm thầm,
 * trong khi trước đó thì không. Mặc định `_ngay_may_tram` (đúng cho app — máy quét
 * đứng ngay tại kho — và cho Node lúc `node --test`); Desk truyền
 * `ngay: () => frappe.datetime.get_today()`.
 *
 * `trang_thai_han` VÌ THẾ LÀ MỘT PHƯƠNG THỨC CỦA THỂ HIỆN, không còn là hàm cấp
 * module: một hàm cấp module không có cách nào biết ai tiêm ngày gì, nên giữ nó ở
 * đó là giữ nguyên cái bẫy. Cả hai lớp vẽ gọi qua thể hiện (`_luong.trang_thai_han`
 * / `this._luong.trang_thai_han`). `nhan_loai` thì vẫn ở cấp module — nó thuần,
 * không đụng đồng hồ nào. */
function tao({ goi, gio, ngay }) {
	const lay_gio = gio || _gio_may_tram;
	const lay_ngay = ngay || _ngay_may_tram;

	function trang_thai_han(hsd) {
		return _trang_thai_han(hsd, lay_ngay());
	}
	// MỘT chính sách lịch sử DÙNG CHUNG cho cả app lẫn Desk (soát xét vòng 1, P3:
	// trước vòng sửa này hai bên lệch nhau BỐN điểm — trần 20/10, không gộp trùng/
	// có gộp, bỏ/giữ mã lạ, không giờ/có giờ — đo được sau đúng hai lần quét: app 1
	// dòng, Desk 2 dòng). Chốt lấy bản GIÀU HƠN: gộp trùng theo mã (của Desk), có
	// giờ quét (của Desk), GIỮ CẢ mã không nhận ra (của Desk — thủ kho cần thấy cả
	// những lần bắn trượt, không chỉ những lần trúng), trần 20 dòng (của app, rộng
	// hơn 10 của Desk cũ). Không chọn bản NGHÈO hơn để gộp cho gọn — gộp lớp luồng
	// mà cắt một tính năng đang chạy (Desk từng giữ mã lạ, từng dedup) là cắt giảm
	// LÉN LÚT, không ai thấy cho tới khi thủ kho hỏi "sao lịch sử ngắn thế".
	const TRAN_LICH_SU = 20;
	let lich_su = [];

	async function quet(ma) {
		const ma_sach = String(ma == null ? "" : ma).trim();
		// Mã rỗng (kể cả toàn khoảng trắng) không phải một lượt quét thật — súng
		// quét gửi ký tự trắng khi bấm nhầm cò lúc chưa chiếu vào tem. Không gọi
		// máy chủ, và KHÔNG vào lịch sử — khác ca "máy chủ đã thử và không nhận ra"
		// (nhánh dưới, có vào lịch sử từ vòng sửa 1): đây chưa từng là một lượt
		// quét, không có gì để "vừa bắn trượt" mà nhớ lại.
		if (!ma_sach) return { loai: "khong_ro", du_lieu: null, bao: "" };

		const d = (await goi("erpnext.warehouse_operations.vitri.quet.tra_cuu", { ma: ma_sach })) || {};
		const loai = d.loai || "khong_ro";
		const du_lieu = loai === "khong_ro" ? null : d;
		const bao = loai === "khong_ro" ? _dich(CAU_KHONG_RO) : "";

		lich_su = lich_su.filter((x) => x.ma !== ma_sach);
		lich_su.unshift({ ma: ma_sach, loai, du_lieu, luc: lay_gio() });
		if (lich_su.length > TRAN_LICH_SU) lich_su.length = TRAN_LICH_SU;

		return { loai, du_lieu, bao };
	}

	function lay_lich_su() {
		return lich_su;
	}

	function xoa_lich_su() {
		lich_su = [];
	}

	return { quet, lich_su: lay_lich_su, xoa_lich_su, trang_thai_han };
}

// ------------------------------------------------------------- hai môi trường
// HAI CÂU `if` ĐỘC LẬP — CỐ Ý không viết `if/else`. Đọc thẳng bundle đang phục vụ
// xác nhận cơ chế: `kho_pda.bundle.js` (Task 2, Bước 5) `import` file này, esbuild
// (bộ đóng gói của Frappe) thấy cú pháp `module.exports` mà KHÔNG có `import`/
// `export` nào khác thì xếp cả file vào diện CommonJS và bọc trong một hàm
// `__commonJS(...)` tự cấp một đối tượng `module` GIẢ — `typeof module !==
// "undefined"` vẫn ĐÚNG ngay trong trình duyệt.
//
// (Sửa lại một câu nói quá ở vòng trước — soát xét vòng 1, P7: với ĐÚNG thứ tự viết
// dưới đây, nhánh `frappe` đứng TRƯỚC nhánh `module`, nên MỘT `if/else` ở đây vẫn sẽ
// chạy đúng nhánh `frappe.provide` trong bundle — không phải "if/else thì nhánh đó
// không bao giờ chạy" như chú thích cũ khẳng định. Lý do THẬT để dùng hai `if` rời
// không phải "if/else sai", mà là: hai `if` độc lập không PHỤ THUỘC thứ tự viết —
// ai đó sau này đảo hai nhánh cho gọn mắt (hoặc chép sang một file khác rồi lỡ đảo)
// thì `if/else` sẽ ÂM THẦM đổi hành vi theo thứ tự mới, còn hai `if` rời thì không,
// dù viết theo thứ tự nào.) Ba màn sau chép nguyên khối đuôi này — chép ĐÚNG lý do
// này, không chép lại câu đã sửa.
if (typeof frappe !== "undefined" && frappe.provide) {
	frappe.provide("erpnext.warehouse_operations.luong");
	// `trang_thai_han` KHÔNG còn ở đây (soát xét tổng, M2): nó là phán quyết HẾT
	// HẠN, phải đọc ngày TIÊM VÀO `tao()`. Xuất một bản cấp module bên cạnh là để
	// nguyên cái bẫy cũ cho người sau vô tình gọi lại — lấy qua thể hiện.
	erpnext.warehouse_operations.luong.tra_cuu = {
		tao,
		nhan_loai,
		NGAY_CAN_DATE,
		CAU_KHONG_RO,
		MO_TA_KHONG_RO,
	};
}
if (typeof module !== "undefined" && module.exports) {
	module.exports = { tao, nhan_loai, NGAY_CAN_DATE, CAU_KHONG_RO, MO_TA_KHONG_RO };
}
