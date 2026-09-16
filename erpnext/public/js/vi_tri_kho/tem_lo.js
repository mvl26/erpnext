// Bộ VẼ nhãn lô 50×30mm cho Zebra ZD421 (203 dpi) — MỘT bố cục duy nhất.
//
// Dùng chung cho hai chỗ: nút "In nhãn cả phiếu" trên `Batch Entry` và nút
// "In nhãn" trên form `Batch` (Task 9). Một bản vẽ duy nhất cho cả xem trước
// lẫn trang in — xem trước một bố cục KHÁC với cái sẽ in ra thì tệ hơn là
// không xem trước gì.
//
// Nạp bằng `frappe.require("/assets/erpnext/js/vi_tri_kho/tem_lo.js")`. CỐ Ý
// không đưa vào `app_include_js` của `erpnext/hooks.py`, cùng lý do đã ghi ở
// `tem_vi_tri.js`: dòng trong `hooks.py` là "dòng dễ mất nhất" mỗi lần merge
// ERPNext bản mới, và nhãn này chỉ hai màn hình cần.
//
// File này PHỤ THUỘC `tem_vi_tri.js` (dùng `erpnext.vi_tri_kho.tem
// .may_ve_ma_vach`) — nạp nó trước, xem `may_vach()` gần cuối file.
//
// ─────────────────────────────────────────────────────────────────────────────
// VÌ SAO KHÔNG CÒN "BỐ CỤC A" — ĐỌC TRƯỚC KHI ĐỊNH KHÔI PHỤC NÓ
//
// Spec §6.1 và mockup SPD vẽ một bố cục (gọi là A) đặt mã vạch trong CỘT TRÁI
// rộng 29,4mm, cạnh một cột phải 17,0mm chứa số gọi. Bản đầu của file này làm
// đúng thế, và chọn giữa A và B theo số module đo được. ĐÃ BỎ HẲN. Lý do là
// hình học, không phải thẩm mỹ:
//
//   Code 128 cần VÙNG YÊN TĨNH (quiet zone) ≥ 10 module = 2,5mm ở MỖI đầu.
//   Ngưỡng định nghĩa của bố cục A là 112 module = 28,0mm.
//   Vậy A cần   28,0 + 2,5 + 2,5 = 33,0mm.
//   A chỉ có    29,4mm.
//
// Thiếu 3,6mm, và không cách nào bù: nống cột trái thì cột phải hết chỗ cho số
// gọi, mà cột phải đã là ô chật nhất trên tem. Tức là A hỏng ĐÚNG TẠI BIÊN CỦA
// CHÍNH NÓ — ở mã dài nhất mà nó nhận, vùng yên tĩnh đo được chỉ còn 0,7mm ≈
// 2,8 module, chưa tới một phần ba chuẩn.
//
// Đây cùng hạng lỗi với con bug `viewBox` ghi ở `tem_vi_tri.js`: nhãn TRÔNG
// ĐÚNG, mọi phép đo bố cục đều xanh (khối vẫn đúng 28,0mm), chỉ máy quét mới
// biết — và lúc ấy tem đã dán lên thùng hàng. Spec khối C đã chốt nguyên tắc
// cho đúng hạng lỗi này: "không bao giờ được thu module xuống dưới 2 dot để
// nhét vừa". Vùng yên tĩnh thiếu là CÙNG MỘT sự đánh đổi, chỉ khác chỗ.
//
// Bố cục còn lại cho mã vạch trọn 47,0mm, nên 112 module + 5,0mm vùng yên tĩnh
// chỉ hết 33,0mm — dư 14,0mm. Nó cũng là chỗ duy nhất số gọi 5 chữ số in ra
// không bị cắt.
//
// ─────────────────────────────────────────────────────────────────────────────
// HÌNH HỌC MÃ VẠCH — vì sao phải ĐO chứ không ước lượng
//
// Máy in: Zebra ZD421, 203 dpi = 8 dot/mm, 1 dot = 0,125mm. Đầu in nhiệt chỉ
// bật/tắt được NGUYÊN dot. Module phải là 2 dot = 0,25mm: 1 dot dưới ngưỡng
// đọc tin cậy của Code 128, 3 dot làm mã tràn khung. X = 0,25mm là giá trị DUY
// NHẤT dùng được (spec §6.2, giống hệt kết luận của tem vị trí).
//
// `may.ve(ma, k)` đặt bề rộng SVG theo mm KÈM `preserveAspectRatio="none"` —
// tức nó KÉO GIÃN mã cho vừa khung, BẤT KỂ mã dài bao nhiêu. Không có lỗi nào
// báo. Nhồi một mã dài vào khung hẹp ra module dưới 2 dot, và máy quét ĐỌC RA
// SAI KÝ TỰ — không phải đọc hỏng, mà đọc ra một chuỗi khác. Sai lặng lẽ, trên
// một vật thể đã dán lên thùng hàng y tế.
//
// Nên bề rộng mã vạch được TÍNH: số module × 0,25mm, đo từ chính thứ sắp được
// in ra (`ve_tho`) — xem `ke_hoach_vach`. Không tự đếm lại Code 128 ở JS: đã
// có `erpnext/vi_tri_kho/vitri/ma_vach.py` cho phía máy chủ, và hai bản cài
// đặt của cùng một phép tính thì một ngày nào đó `validate` cho qua một số lô
// mà nhãn không vẽ nổi — phát hiện ra lúc tem đã in và đã dán.
//
// ─────────────────────────────────────────────────────────────────────────────
// BA LUẬT CSS CHÉP NGUYÊN TỪ `tem_vi_tri.js` — mỗi luật là một lỗi đã trả giá
//
// 1. `flex: 0 0 auto` trên mọi hàng và trên khối mã vạch. `.tem` là flex cột
//    nên mặc định mọi con đều CO ĐƯỢC. Nếu một ngày khối chữ cao thêm (thêm
//    dòng, đổi cỡ chữ), thứ nhường chỗ sẽ là MÃ VẠCH: nó thấp dần đi mà không
//    có lỗi nào, không có gì tràn, trên màn hình vẫn trông y hệt. Chỉ máy quét
//    ngoài kho mới biết — mà lúc đó tem đã dán rồi. Khoá cứng lại thì một sai
//    sót về chiều cao sẽ TRÀN, và tràn thì phép đo bắt được.
// 2. `min-width: 0` trên mọi cột chữ. Flex item mặc định là `min-width: auto`,
//    nghĩa là KHÔNG co xuống dưới bề rộng nội dung tối thiểu. Một bản ghi dị
//    dạng (tên hàng rất dài, số lô rất dài) sẽ nống cột của nó ra và ăn mất bề
//    rộng của cột bên cạnh — thứ bị cắt là ô KHÁC, không phải ô có dữ liệu
//    xấu. Với `min-width: 0`, chữ dị dạng bị cắt TRONG Ô CỦA NÓ, kèm dấu "…".
//    (Vế DỌC của luật này là `min-height: 0`, xem trong `css()`.)
// 3. `preserveAspectRatio="none"` đi ĐÔI với `displayValue: false`. `none` cho
//    phép ép đúng chiều cao yêu cầu (với `meet` thì chiều cao chỉ là TRẦN, mã
//    thực tế thấp hơn và không ai báo). Kéo méo dọc VÔ HẠI với mã vạch vì
//    thông tin nằm ở bề rộng vạch. Nhưng nếu in chữ dưới vạch thì `none` sẽ
//    BÓP MÉO CHỮ. Hai thiết lập đi kèm nhau, đừng đổi một cái.
//    (Cả hai nằm ở `tem_vi_tri.js`, trong `TUY_CHON_VACH` và `ve()`.)

frappe.provide("erpnext.vi_tri_kho");

erpnext.vi_tri_kho.tem_lo = (function () {
	/** Bề rộng một module mã vạch, mm. 2 dot trên đầu in 203 dpi.
	 *
	 * Bản sao của `ma_vach.X_MM` phía máy chủ. Hai bản sao của một HẰNG SỐ thì
	 * chấp nhận được (một con số, đọc là thấy); hai bản cài đặt của một PHÉP
	 * TÍNH thì không — đó là lý do số module được ĐO chứ không đếm lại ở đây.
	 */
	const X_MM = 0.25;

	/** Vùng yên tĩnh Code 128: 10 module mỗi đầu. Không đánh đổi. */
	const YEN_TINH_MODULE = 10;
	const YEN_TINH_MM = YEN_TINH_MODULE * X_MM; // 2,5mm

	/** Mọi con số dưới đây là MILIMÉT THẬT trên con tem, trừ `co.*` là point.
	 *
	 * Vùng in an toàn 47 × 27mm = (50 − 2×1,5) × (30 − 2×1,5).
	 * `cot_trai + gap + cot_phai` = 27,0 + 0,6 + 19,4 = 47,0 ✓
	 *
	 * ─────────────────────────────────────────────────────────────────────
	 * SÀN CHIỀU CAO HÀNG — đo HỘP CHỮ, không đo chiều cao chữ hoa
	 *
	 * Mỗi hàng cao ít nhất bằng HỘP CHỮ (đỉnh ascender → đáy descender) của
	 * cỡ lớn nhất trong nó, KHÔNG phải bằng chiều cao chữ hoa: một trường
	 * tiếng Việt có dấu đâm xuống (`ạ` `ợ` `ậ` `ộ`) sẽ chạm hàng dưới dù chữ
	 * hoa không chạm. Số đo (Chrome, Arial/Liberation Sans, mm):
	 *
	 *   5pt 1,852 · 5,5pt 2,381 · 6,5/7pt 2,646 · 8pt 3,175 · 9pt 3,704
	 *   11pt 4,234 · 16pt 6,350 · 18pt 7,144 · 19pt 7,409 · 20pt 7,938
	 *
	 *   Hàng  Chứa                                Sàn     Đặt    Biên
	 *   R1    F1 11pt                             4,234   4,32   +0,086
	 *   R2    F2 8pt                              3,175   3,26   +0,085
	 *   R3    F4 5,5pt                            2,381   2,47   +0,089
	 *   R4    F5 8pt                              3,175   3,90   +0,725
	 *   R5    F6 7pt                              2,646   3,58   +0,934
	 *   R4+R5 F9 19pt trải hai hàng               7,409   7,48   +0,071
	 *   R6    F8 7pt · F7 6,5pt                   2,646   2,73   +0,084
	 *   R7    mã vạch 4,8 + F11 5pt 1,852         6,652   6,74   +0,088
	 *
	 * Tổng sàn 26,497 trong ngân sách 27,0 — chỉ dư 0,503mm cho bảy hàng.
	 *
	 * ─────────────────────────────────────────────────────────────────────
	 * VÌ SAO F9 LÀ 19pt — bị chặn bởi CHIỀU CAO, không phải bề ngang
	 *
	 * F9 (số gọi) trải hai hàng R4+R5, nên cỡ của nó bị chặn bởi phần chiều
	 * cao còn lại sau khi trừ sàn của năm hàng kia. Đã hạ F2 9→8pt và F4
	 * 6,5→5,5pt để lấy thêm 0,794mm cho nó (hai ô đó có biên rộng nhất):
	 *
	 *   R4+R5 nhiều nhất có được = 27,0 − (4,234+3,175+2,381+2,646+6,652)
	 *                            = 7,912mm
	 *   F9 19pt cần 7,409 ✓        F9 20pt cần 7,938 ✗ (thiếu 0,026mm)
	 *
	 * Bề ngang thì thoải mái: "38561" @19pt = 18,637mm trong cột 19,4mm,
	 * biên 0,763mm. Muốn 20pt thì phải lấy chiều cao ở chỗ khác — ứng viên
	 * duy nhất còn lại là F11 (chữ dưới mã vạch), mà F11 chính là đường lui
	 * khi máy quét hỏng. Không đánh đổi.
	 */
	const KHO = {
		rong: 50,
		cao: 30,
		le: 1.5,
		hang: [4.32, 3.26, 2.47, 3.9, 3.58, 2.73, 6.74], // = 27,0
		cot_trai: 27.0,
		gap: 0.6,
		cot_phai: 19.4,
		// TRẦN bề rộng mã vạch (= trọn vùng in), KHÔNG phải bề rộng vẽ ra.
		// Bề rộng vẽ = số module × X_MM — xem `ke_hoach_vach`.
		vach_rong: 47.0,
		vach_cao: 4.8,
		co: { f1: 11, f2: 8, f3: 6.5, f4: 5.5, f5: 8, f6: 7, f7: 6.5, f8: 7, f9: 19, f11: 5 },
	};

	/** Chiều cao dùng được = 30 − 2×1,5. Mảng `hang` phải cộng ĐÚNG số này.
	 *
	 * VÌ SAO phải có phép kiểm này thay vì tin vào chú thích "= 27,0": nếu ai
	 * đó chỉnh một con số mà quên chỉnh con số bù lại, nhãn TRÀN ra ngoài vùng
	 * in — và `overflow: hidden` ở `.tem` (luật đỡ cuối, xem `css()`) sẽ NUỐT
	 * phần tràn đó. Không có lỗi nào báo, màn hình xem trước trông vẫn ổn, chỉ
	 * là chữ bị cắt trên giấy, phát hiện ra khi tem đã dán lên hàng.
	 *
	 * So bằng epsilon chứ không bằng `===`: phép kiểm này sống để đỡ những lần
	 * SỬA SAU, và một mảng toàn số lẻ hai chữ số thập phân thì `=== 27` sai
	 * trong khi hình học vẫn đúng. Một phép kiểm báo động giả là một phép kiểm
	 * bị người ta gỡ đi.
	 */
	const CAO_DUNG_DUOC = KHO.cao - 2 * KHO.le;
	(function () {
		const tong = KHO.hang.reduce(function (a, b) {
			return a + b;
		}, 0);
		console.assert(
			Math.abs(tong - CAO_DUNG_DUOC) < 1e-9,
			`tem_lo: tổng chiều cao hàng = ${tong}mm, phải đúng ${CAO_DUNG_DUOC}mm`
		);
	})();

	/** Trần số module — SUY RA từ bề rộng, không gõ tay.
	 *
	 * `TRAN_VE_DUOC` (188): rộng nhất vẽ nổi trong vùng in 47,0mm ở 2 dot mỗi
	 * module. Quá con số này thì KHÔNG cách nào vẽ đúng — `ma_vach.py` đã chặn
	 * từ lúc lưu lô (`int(47.0 / X_MM)`, cùng một phép suy), nên hai phía
	 * không thể lệch nhau mà không ai thấy.
	 *
	 * `TRAN_YEN_TINH` (180): rộng nhất còn giữ được vùng yên tĩnh 2,5mm mỗi
	 * đầu TRÊN CHÍNH CON TEM. Mã vạch căn giữa tem 50mm, nên vùng trắng mỗi
	 * bên là (50 − bề rộng) ÷ 2; muốn ≥ 2,5mm thì bề rộng ≤ 45,0mm = 180
	 * module. Giữa 181 và 188 module thì vẫn vẽ được nhưng vùng yên tĩnh
	 * THIẾU — cảnh báo chứ không chặn, xem `ke_hoach_vach`.
	 */
	const TRAN_VE_DUOC = Math.floor(KHO.vach_rong / X_MM); // 188
	const TRAN_YEN_TINH = Math.floor((KHO.rong - 2 * YEN_TINH_MM) / X_MM); // 180

	function esc(s) {
		return frappe.utils.escape_html(s == null ? "" : String(s));
	}

	/** Số module Code 128 của `ma`, ĐO từ SVG do JsBarcode dựng.
	 *
	 * `width: 2` trong `TUY_CHON_VACH` (`tem_vi_tri.js`) nghĩa là mỗi module
	 * rộng 2 px, `margin: 0` nghĩa là không có lề cộng thêm. Nên
	 *
	 *     số module = bề rộng px của nội dung SVG ÷ 2
	 *
	 * ĐỌC `viewBox`, KHÔNG ĐỌC THUỘC TÍNH `width`. Đây không phải chuyện thẩm
	 * mỹ — đọc `width` cho ra một con số SAI CỐ ĐỊNH:
	 *
	 *     frappe/public/js/frappe/form/controls/barcode.js, get_barcode_html:
	 *         JsBarcode(svg, value, this.get_options(value));
	 *         $(svg).attr("width", "100%");     ← ghi đè bề rộng px
	 *
	 * nên `parseFloat(svg.getAttribute("width"))` luôn ra 100 cho MỌI mã, và
	 * `100 / 2 = 50`. Đo bằng chính JsBarcode frappe đóng gói: 25L4125 →
	 * 202px (101 module), LOT-2026-A45 → 334px (167), 1B01040302 → 224px
	 * (112); đọc `width` thì cả ba đều ra "100%".
	 *
	 * `viewBox` thì do chính `SVGRenderer.setSvgAttributes` của JsBarcode ghi
	 * (`"0 0 <px bề rộng> <px chiều cao>"`) và KHÔNG ai ghi đè.
	 *
	 * Trả `0` khi không đo được. Bên gọi phải hiểu 0 là "ĐO HỎNG" chứ không
	 * phải "mã rất ngắn" — xem `ke_hoach_vach`.
	 */
	function so_module(may, ma) {
		const svg = may.ve_tho(ma);
		if (!svg) return 0;
		const vb = svg.getAttribute("viewBox");
		if (!vb) return 0;
		const rong = parseFloat(vb.trim().split(/[\s,]+/)[2]);
		if (!rong) return 0;
		return Math.round(rong / 2);
	}

	/** Bề rộng mã vạch THẬT cho `ma`, cùng hai lời cảnh báo có thể phát ra.
	 *
	 * Trả `{ so_module, k_ve }` — `k_ve` là bản sao của `KHO` chỉ khác ở
	 * `vach_rong`, dành riêng cho `may.ve()`.
	 *
	 * BỀ RỘNG = SỐ MODULE × 0,25mm, không phải hằng số `vach_rong` (đó là
	 * TRẦN). Ép một mã 101 module cho đầy 47,0mm ra 0,465mm/module = 3,7 dot;
	 * ép cho đầy 28,0mm ra 2,22 dot. Cả hai đều KHÔNG nguyên dot, mà trình
	 * điều khiển máy in phải làm tròn từng vạch về dot gần nhất — nên vạch ra
	 * lúc 2 dot lúc 3 dot, KHÔNG ĐỀU. Đúng dạng hỏng mà commit cd749e16 đã sửa
	 * cho tem vị trí: máy quét lúc đọc được lúc không, tuỳ con tem và tuỳ góc
	 * quét. Không ai gọi nó là lỗi, người ta chỉ "quét lại lần nữa".
	 *
	 * Hai ngưỡng, hai lời cảnh báo KHÁC NHAU, vì hai kiểu hỏng khác nhau:
	 *
	 *   > 180 module → vẽ đúng 2 dot nhưng VÙNG YÊN TĨNH thiếu
	 *   > 188 module → không vẽ nổi trong vùng in, buộc phải bóp module
	 *
	 * Cả hai chỉ cảnh báo, không chặn in: thủ kho vẫn cần con tem, và F11 in
	 * nguyên số lô dưới mã vạch nên vẫn gõ tay được. Nhưng phải NÓI THẲNG —
	 * im lặng ở đây là để người ta dán lên hàng một mã không quét nổi.
	 */
	function ke_hoach_vach(may, ma) {
		const m = so_module(may, ma);

		// ĐO HỎNG (m = 0) — KHÔNG IN MÃ VẠCH NÀO, và nói thẳng ra.
		//
		// Bản trước vẽ trọn 47,0mm ở nhánh này. Đó là MẶT THỨ HAI của cùng lỗi
		// mà `_ve_vao_control` chặn ở `tem_vi_tri.js`: chú thích cũ viết "bên
		// gọi phải hiểu 0 là ĐO HỎNG", nhưng bên gọi không hiểu thế — nó cứ
		// thế kéo giãn một mã ra 47mm. Vá một đầu mà không vá đầu này thì lỗi
		// chỉ đổi dạng, từ "mã vạch của lô khác" thành "mã vạch bị kéo giãn
		// trong im lặng".
		//
		// THÀ KHÔNG CÓ MÃ VẠCH CÒN HƠN CÓ MỘT MÃ SAI: không quét được thì người
		// ta gõ tay theo F11 (số lô in nguyên văn dưới mã vạch); quét ra SAI
		// thì không ai biết để mà gõ lại.
		if (!m) {
			frappe.msgprint({
				title: __("KHÔNG in được mã vạch cho lô này"),
				indicator: "red",
				message: __(
					"Số lô {0} có ký tự mà Code 128 không mã hoá được — Code 128 chỉ nhận " +
						"ký tự ASCII, còn dấu tiếng Việt và dấu gạch ngang dài “–” (hay bị dán " +
						"từ phiếu của nhà cung cấp) thì không. Nhãn vẫn in, nhưng CHỪA TRỐNG " +
						"chỗ mã vạch: số lô vẫn đọc được bằng mắt ở dòng dưới. Sửa số lô thành " +
						"ký tự ASCII rồi in lại.",
					[esc(ma)]
				),
			});
			return { so_module: 0, k_ve: Object.assign({}, KHO) };
		}

		const rong = Math.min(m * X_MM, KHO.vach_rong);

		if (m > TRAN_VE_DUOC) {
			frappe.msgprint({
				title: __("Mã vạch có thể KHÔNG QUÉT ĐƯỢC"),
				indicator: "red",
				message: __(
					"Số lô {0} cần {1} module mã vạch nhưng nhãn 50×30 chỉ chứa được {2}. " +
						"Nhãn vẫn in nhưng mã vạch bị ép hẹp hơn 2 dot — máy quét có thể đọc " +
						"ra SAI KÝ TỰ chứ không phải báo lỗi. Quét thử trước khi dán, hoặc " +
						"đổi sang số lô ngắn hơn.",
					[esc(ma), m, TRAN_VE_DUOC]
				),
			});
		} else if (m > TRAN_YEN_TINH) {
			frappe.msgprint({
				title: __("Vùng yên tĩnh mã vạch bị thiếu"),
				indicator: "orange",
				message: __(
					"Số lô {0} dài {1} module ({2}mm), nên hai bên mã vạch chỉ còn {3}mm " +
						"trắng thay vì {4}mm mà Code 128 cần. Vạch vẫn đúng 2 dot, nhưng máy " +
						"quét có thể không bắt được mã ở góc nghiêng. Quét thử trước khi dán.",
					[esc(ma), m, rong.toFixed(2), ((KHO.rong - rong) / 2).toFixed(2), YEN_TINH_MM.toFixed(2)]
				),
			});
		}

		return { so_module: m, k_ve: Object.assign({}, KHO, { vach_rong: rong }) };
	}

	/** HTML của MỘT con tem. `o` là một dòng `nhap_lo.du_lieu_tem` trả về.
	 *
	 * DỮ LIỆU VÀO LÀ KHOÁ CHỮ HOA `F1`…`F11`, và ĐÃ ĐỊNH DẠNG SẴN: `F5` đã là
	 * `"HSD 2029/01/31"`, `F6` đã là `"Lô 25L4125"`, `F7` đã là `"NHẬP
	 * 2026/09/03"`, `F8` đã qua `ma_vi_tri.dinh_dang_nhan()` hoặc bằng
	 * `"VT —"`. HÀM NÀY KHÔNG ĐỊNH DẠNG LẠI GÌ — nó chỉ đặt chữ vào ô. Trộn
	 * định dạng vào đây là mở đường cho nhãn in và màn hình xem trước nói khác
	 * nhau, mà chỉ một trong hai đi theo thùng hàng.
	 *
	 * `F4` có thể rỗng. Khi đó ô để TRẮNG và hàng GIỮ NGUYÊN chiều cao (hàng
	 * có `height` cố định nên điều này tự đúng — đừng "tối ưu" bằng cách bỏ
	 * hàng đi). Người đứng trước kệ đọc nhãn bằng VỊ TRÍ trước khi đọc bằng
	 * chữ; hai nhãn cạnh nhau đặt cùng một thông tin ở hai độ cao khác nhau là
	 * nhãn khó đọc.
	 *
	 * VỊ TRÍ F7: đi cùng F8 trên hàng R6 (rộng TRỌN 47,0mm), KHÔNG đi cùng F6
	 * trên hàng R5 (rộng 27,0mm). Đo thật, cùng font đang dựng:
	 *   F6 + F7 trên cột trái = 19,62 + 18,42 = 38,04mm  → cắt cả hai
	 *   F5 + F7 trên cột trái = 20,85 + 18,42 = 39,27mm  → còn tệ hơn
	 *   F8 + F7 trên R6       = 18,80 + 18,42 = 37,22mm  → VỪA, dư 9,78mm
	 * R6 trước đây chỉ có mỗi F8 (18,80mm trong 47,0mm), tức bỏ không 28,2mm
	 * ngay cạnh hai ô đang phải cắt chữ.
	 *
	 * `hinh_vach` truyền từ ngoài vào (đã serialize) để một mã vạch vẽ một lần
	 * rồi dùng cho cả N bản in của cùng lô đó. RỖNG nghĩa là không mã hoá được
	 * số lô này (xem `ke_hoach_vach`) — khi đó in một DÒNG CHỮ vào đúng chỗ mã
	 * vạch, không để trống.
	 *
	 * VÌ SAO phải in chữ chứ không để trống: một khoảng trắng trên tem không
	 * nói gì cả — người cầm tem không biết đó là lỗi hay là thiết kế, và cũng
	 * không biết có phải đi tìm mã vạch ở chỗ khác không. Cảnh báo đỏ của
	 * `ke_hoach_vach` chỉ sống trên màn hình lúc bấm in; con tem thì đi theo
	 * thùng hàng suốt vòng đời. Dòng chữ nằm TRONG hàng R7 vốn đã có sẵn nên
	 * KHÔNG tốn thêm milimét nào của ngân sách 27,0mm.
	 *
	 * F11 vẫn in nguyên số lô ngay dưới — đó chính là thứ người ta sẽ gõ tay.
	 */
	function ve_tem(o, hinh_vach) {
		return `<div class="tem">
	<div class="hang h1"><span class="f1">${esc(o.F1)}</span><span class="f3">${esc(o.F3)}</span></div>
	<div class="hang h2"><span class="f2">${esc(o.F2)}</span></div>
	<div class="hang h3"><span class="f4">${esc(o.F4)}</span></div>
	<div class="giua">
		<div class="cot-trai">
			<div class="hang h4"><span class="f5">${esc(o.F5)}</span></div>
			<div class="hang h5"><span class="f6">${esc(o.F6)}</span></div>
		</div>
		<div class="cot-phai o-f9"><span class="f9">${esc(o.F9)}</span></div>
	</div>
	<div class="hang h6"><span class="f8">${esc(o.F8)}</span><span class="f7">${esc(o.F7)}</span></div>
	<div class="hang h7 o-vach">
		${hinh_vach ? `<div class="vach">${hinh_vach}</div>` : `<div class="khong-vach">${esc(__("KHÔNG CÓ MÃ VẠCH — GÕ TAY SỐ LÔ"))}</div>`}
		<div class="f11">${esc(o.F11)}</div>
	</div>
</div>`;
	}

	/** CSS cho con tem. `cho_in = true` thì kèm `@page` và ngắt trang mỗi tem. */
	function css(cho_in) {
		// Chiều cao hàng và cỡ chữ sinh THẲNG từ hằng số — không gõ lại ở CSS.
		// Gõ lại là dựng một bản thứ hai của cùng bộ số, mà `console.assert` ở
		// trên chỉ canh bản thứ nhất.
		const cao_hang = KHO.hang
			.map(function (h, i) {
				return `\t.tem .h${i + 1} { height: ${h}mm; }`;
			})
			.join("\n");
		const co_chu = Object.keys(KHO.co)
			.map(function (f) {
				return `\t.tem .${f} { font-size: ${KHO.co[f]}pt; }`;
			})
			.join("\n");

		const trang = cho_in
			? `@page { size: ${KHO.rong}mm ${KHO.cao}mm; margin: 0; }
	.tem { page-break-after: always; break-after: page; }
	/* Không có dòng này thì máy nhả thêm một con tem TRẮNG ở cuối mỗi xấp. */
	/* :last-of-type chứ KHÔNG phải :last-child — phần tử con CUỐI CÙNG của
	   <body> là thẻ <script> gọi window.print(), nên :last-child không bao giờ
	   khớp một con tem nào và cái lưới đỡ mô tả ở dòng trên CHƯA TỪNG chạy.
	   Hôm nay không lộ ra vì Chrome tự bỏ trang trắng cuối, nhưng đó là may
	   mắn của một engine cụ thể, không phải điều ta đặt ra. */
	.tem:last-of-type { page-break-after: auto; break-after: auto; }`
			: // `outline` chứ KHÔNG `border`: border (với box-sizing: border-box)
			  // ăn 0,2mm mỗi phía vào chính vùng in, nên ô xem trước sẽ có bố cục
			  // LỆCH với tờ giấy sẽ in ra — đo được 0,26mm ở mỗi lề và 0,53mm bề
			  // ngang. Ô xem trước khác tờ in là ô xem trước mất ý nghĩa.
			  // `outline` không chiếm chỗ trong bố cục.
			  `.tem { outline: 0.2mm dashed #b8b8b8; outline-offset: -0.2mm; }`;

		return `
	* { box-sizing: border-box; }
	.tem {
		width: ${KHO.rong}mm; height: ${KHO.cao}mm;
		padding: ${KHO.le}mm;
		min-width: 0;
		display: flex; flex-direction: column;
		background: #fff; color: #000;
		font-family: Arial, Helvetica, sans-serif;
		/* Chữ số cùng bề rộng: HSD, ngày nhập, số gọi và số lô đều là số, mà số
		   rộng bằng nhau thì bề rộng ô đoán trước được — đó là điều kiện để phép
		   đo trên trình duyệt có nghĩa cho MỌI lô chứ không chỉ cho lô vừa đo. */
		font-variant-numeric: tabular-nums;
		/* Lưới đỡ cuối cùng: một con tem TRÀN không chỉ xấu — trên cuộn liên tục
		   nó đẩy lệch MỌI con tem in sau nó. Nhưng đây là lưới ĐỠ, không phải
		   phép kiểm: nó nuốt phần tràn trong im lặng, nên phép đo từng ô bằng
		   Range mới là thứ bắt được lỗi. */
		overflow: hidden;
	}
	/* flex: 0 0 auto trên MỌI hàng — KHÔNG phải thừa. Xem luật 1 đầu file. */
	.tem .hang {
		flex: 0 0 auto;
		min-width: 0;
		/* min-height: 0 là vế DỌC của luật min-width: 0, và nó cần thiết vì cùng
		   một lý do. Flex item mặc định là min-height: auto, tức KHÔNG co xuống
		   dưới chiều cao nội dung. Một cỡ chữ quá to sẽ NỐNG hàng đó ra thay vì
		   bị cắt: các hàng dưới bị đẩy xuống, mã vạch tụt ra khỏi vùng in, và
		   overflow: hidden ở .tem nuốt phần thừa. Với min-height: 0 thì chữ quá
		   to bị CẮT trong ô của nó và phép đo bắt được ngay. */
		min-height: 0;
		/* align-items: center, KHÔNG phải baseline.
		   Với baseline, hộp DÒNG (line-height 1 = 1,0em) bám ĐỈNH hàng, còn hộp
		   CHỮ thật (đỉnh ascender → đáy descender) cao khoảng 1,15em nên nó thò
		   ra 0,18mm PHÍA TRÊN đỉnh hàng — tức đâm vào hàng ở trên. Đã đo được
		   0,18mm giữa F5 và hàng dưới nó. Với center, hộp chữ nằm giữa hàng, nên
		   chỉ cần "hàng ≥ hộp chữ" (luật ở khối hằng số) là chữ nằm TRỌN. */
		display: flex; align-items: center;
		/* KHÔNG đặt overflow: hidden ở HÀNG.
		   Ngân sách 27,0mm chỉ còn dư 0,503mm sau khi trừ sàn chiều cao của bảy
		   hàng, nên năm hàng chỉ còn khoảng 0,08mm biên. Nếu HÀNG tự cắt thì
		   phần đó bị xén — đúng vào chân các dấu tiếng Việt đâm xuống. Cắt chữ
		   là việc của từng Ô (mỗi span đã có overflow: hidden kèm ellipsis, cắt
		   theo chiều NGANG đúng cho nó), còn lưới đỡ cuối cùng vẫn là
		   overflow: hidden ở .tem. Hàng ở giữa không cần cắt gì. */
	}
	/* min-width: 0 trên mọi ô chữ — chặn một lỗi IM LẶNG. Xem luật 2 đầu file.
	   Cắt bằng "…" chứ không cắt trần: một số lô cụt trông y như số lô thật và
	   người ta gõ nhầm nó, còn "25L4…" thì nhìn là biết chưa đọc hết. */
	.tem .f1, .tem .f2, .tem .f3, .tem .f4, .tem .f5,
	.tem .f6, .tem .f7, .tem .f8, .tem .f11 {
		min-width: 0;
		white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
		line-height: 1;
	}
	/* Khối giữa: hai cột. 27,0 + 0,6 + 19,4 = 47,0mm đúng bằng vùng in. */
	.tem .giua {
		height: ${KHO.hang[3] + KHO.hang[4]}mm;
		flex: 0 0 auto; min-height: 0;
		display: flex;
		position: relative;
	}
	.tem .cot-trai {
		flex: 0 0 ${KHO.cot_trai}mm; min-width: 0; min-height: 0;
		display: flex; flex-direction: column;
	}
	.tem .cot-phai {
		flex: 0 0 ${KHO.cot_phai}mm; min-width: 0; min-height: 0;
		margin-left: ${KHO.gap}mm;
		display: flex; flex-direction: column;
		position: relative;
	}
	/* Đường kẻ vẽ bằng LỚP PHỦ TUYỆT ĐỐI, không bằng border.
	   border ăn vào ngân sách 27,0mm / 47,0mm đã cân đúng ở khối hằng số, và
	   thứ bị ăn mất là chiều cao của một hàng chữ — cắt trong im lặng dưới
	   overflow: hidden. Lớp phủ thì tốn 0mm bố cục.
	   0,25mm = 2 dot chẵn trên đầu in 203 dpi: nét rơi đúng lưới dot thay vì
	   lệch nửa dot rồi ra nét mảnh chỗ đậm chỗ nhạt. */
	.tem .giua::before, .tem .h6::before {
		content: ""; position: absolute; left: 0; right: 0; top: 0;
		height: 0.25mm; background: #000;
	}
	.tem .h6 { position: relative; }
	/* Đường kẻ DỌC vẽ từ KHỐI CHA, không vẽ từ .cot-phai.
	   Đo được: đặt nó trên .cot-phai thì nó BIẾN MẤT, vì .cot-phai cũng mang
	   .o-f9 (overflow: hidden) và nét kẻ nằm ngoài hộp — bị chính ô đó cắt mất.
	   Không có lỗi nào báo, chỉ là một đường kẻ có ở nhãn này và không có ở
	   nhãn kia. Vẽ từ khối cha thì nét nằm trong hộp của khối cha. */
	.tem .giua::after {
		content: ""; position: absolute; top: 0; bottom: 0;
		left: ${KHO.cot_trai + KHO.gap / 2 - 0.125}mm;
		width: 0.25mm; background: #000;
	}
	.tem .f1 { flex: 1 1 auto; font-weight: 700; }
	.tem .f2 { flex: 1 1 auto; font-weight: 700; }
	.tem .f3 { flex: 0 1 auto; max-width: 50%; margin-left: 1.5mm; text-align: right; }
	.tem .f4 { flex: 1 1 auto; }
	.tem .f5 { flex: 1 1 auto; font-weight: 700; }
	.tem .f6 { flex: 1 1 auto; }
	.tem .f7 { flex: 0 1 auto; }
	.tem .f8 { flex: 0 1 auto; font-weight: 700; }
	/* F8 và F7 đẩy về hai đầu hàng R6. */
	.tem .h6 { justify-content: space-between; }
	/* Ô F9 (số gọi): căn giữa cả hai chiều, cắt trong ô của nó.
	   .cot-phai đã là flex cột, .o-f9 chỉ thêm căn giữa. */
	.tem .o-f9 {
		display: flex; align-items: center; justify-content: center;
		overflow: hidden;
	}
	.tem .f9 {
		font-weight: 700; line-height: 1;
		white-space: nowrap; min-width: 0;
		overflow: hidden; text-overflow: ellipsis;
	}
	/* Khối mã vạch: vạch trên, F11 dưới, căn giữa theo chiều ngang.
	   F11 nằm DƯỚI chứ không nằm BÊN (khác cách phác trong spec): mã vạch
	   chiếm tới 47,0mm nên không còn bề ngang nào để đặt chữ bên cạnh.
	   align-items: center — vùng trắng chia đều hai bên khi mã vạch hẹp hơn ô,
	   và chia đều chính là điều kiện để vùng yên tĩnh hai đầu bằng nhau. */
	.tem .o-vach {
		display: flex; flex-direction: column; align-items: center;
		overflow: hidden;
	}
	/* flex: 0 0 auto — luật số 1 đầu file, ở chỗ nó QUAN TRỌNG NHẤT.
	   Chiều cao mã vạch là thứ DUY NHẤT trên con tem này mà co lại không gây ra
	   bất kỳ dấu hiệu nào nhìn thấy được. */
	.tem .vach {
		flex: 0 0 auto;
		height: ${KHO.vach_cao}mm; max-width: ${KHO.vach_rong}mm;
		line-height: 0;
	}
	/* Dòng chữ thay chỗ mã vạch khi không mã hoá được số lô.
	   Chiếm đúng phần chiều cao mà mã vạch bỏ lại (height = vach_cao), nên
	   hàng R7 không đổi và ngân sách 27,0mm không bị đụng.
	   Câu chữ và cỡ chữ ĐO RA chứ không chọn: chỗ dùng được là 47,0 − 2×1,0mm
	   padding = 45,0mm, trần có biên 0,5mm là 44,5mm. Câu dài hơn ("KHÔNG IN
	   ĐƯỢC MÃ VẠCH — nhập số lô bằng tay") ở 5,5pt ra 48,78mm, TRÀN 1,78mm và
	   bị chính khối này cắt — một dòng cảnh báo bị cắt cụt thì tệ hơn không có.
	   Câu hiện tại ở 6pt ra 41,62mm, dư 2,88mm, mà lại ĐỌC TO HƠN câu dài.
	   Hộp chữ cao 2,381mm nằm gọn trong 4,8mm và còn cách F11 bên dưới 0,99mm.
	   Chữ hoa, giãn nhẹ và viền nét đứt để nhìn là biết ngay đây KHÔNG phải
	   một mã vạch in mờ. */
	.tem .khong-vach {
		flex: 0 0 auto;
		height: ${KHO.vach_cao}mm; max-width: ${KHO.vach_rong}mm;
		display: flex; align-items: center; justify-content: center;
		font-size: 6pt; font-weight: 700; line-height: 1;
		letter-spacing: 0.02em;
		white-space: nowrap; overflow: hidden;
		border: 0.25mm dashed #000;
		padding: 0 1mm;
	}
	/* line-height dưới 1 cho F11 — có tính toán, không phải tuỳ tiện.
	   Hàng R7 cao 6,74mm, mã vạch ăn 4,8mm, còn 1,94mm. 5pt với line-height 1
	   là 1,76mm nên vừa; nhưng hộp CHỮ thật cao 1,85mm, sát đến mức một lần đổi
	   font là tràn. 0,9 cho hộp dòng 1,59mm, chừa chỗ cho hộp chữ. Chữ số không
	   có nét dưới đường chân (không có g/j/p/q) nên thu hộp dòng không cắt vào
	   nét nào. */
	.tem .f11 {
		flex: 1 1 auto; width: 100%;
		line-height: 0.9;
		text-align: center;
		letter-spacing: 0.02em;
	}
${cao_hang}
${co_chu}
	${trang}
`;
	}

	/** Bảo đảm `tem_vi_tri.js` (nơi có `may_ve_ma_vach`) đã nạp.
	 *
	 * File này chỉ MƯỢN cái máy vẽ mã vạch, không dựng lại: dựng lại là có hai
	 * bộ tuỳ chọn JsBarcode trong cùng một ứng dụng, và phép đo số module ở
	 * đây phụ thuộc vào đúng `width: 2` / `margin: 0` của bộ kia.
	 */
	function may_vach() {
		if (!erpnext.vi_tri_kho.tem || !erpnext.vi_tri_kho.tem.may_ve_ma_vach) {
			frappe.throw(
				__(
					"Chưa nạp tem_vi_tri.js — gọi frappe.require('/assets/erpnext/js/vi_tri_kho/tem_vi_tri.js') trước tem_lo.js."
				)
			);
		}
		return erpnext.vi_tri_kho.tem.may_ve_ma_vach();
	}

	/** Ô xem trước trên màn hình: tem vẽ ĐÚNG mm thật rồi phóng to bằng
	 * `transform`.
	 *
	 * Phóng bằng transform chứ không phải bằng cách nống các con số mm lên:
	 * nống số thì cái nhìn thấy không còn là cái sẽ in ra, và ô xem trước mất
	 * sạch ý nghĩa. Trình duyệt quy 1mm = 96/25.4 px, nên tem 50mm chỉ ra
	 * ~189px — đúng bằng con tem thật, nhỏ đến mức không soi được chữ.
	 */
	function ve_xem_truoc($dich, o, he_so) {
		const may = may_vach();
		const kh = ke_hoach_vach(may, o.F10);
		he_so = he_so || 2.4;
		const html = ve_tem(o, may.ve(o.F10, kh.k_ve));
		may.don();

		$dich.empty();
		$(`<div class="vi-tri-kho-xem-tem-lo" style="
				width:${KHO.rong * he_so}mm; height:${KHO.cao * he_so}mm; overflow:hidden;">
			<style>${css(false)}</style>
			<div style="transform:scale(${he_so}); transform-origin:top left;">${html}</div>
		</div>`).appendTo($dich);
	}

	/** Dựng và mở cửa sổ in cho cả xấp nhãn. Trả `false` nếu bị chặn pop-up.
	 *
	 * `danh_sach` là kết quả `nhap_lo.du_lieu_tem` (mảng dict F1…F11).
	 * `so_ban` mặc định 1 — mỗi lô một nhãn (spec §6.5).
	 */
	function in_xap(danh_sach, so_ban) {
		so_ban = so_ban || 1;
		const may = may_vach();
		const tem = [];

		(danh_sach || []).forEach(function (o) {
			const kh = ke_hoach_vach(may, o.F10);
			// Vẽ MỘT lần cho mỗi lô rồi nhân bản chuỗi: 200 lô × 5 bản mà vẽ
			// lại từng cái là 1000 lượt dựng SVG, cửa sổ in đứng hình trước
			// khi kịp gọi print().
			const mot = ve_tem(o, may.ve(o.F10, kh.k_ve));
			for (let i = 0; i < so_ban; i++) tem.push(mot);
		});
		may.don();

		const trang = `<!doctype html><html><head><meta charset="utf-8">
<title>${esc(__("Nhãn lô"))} ${KHO.rong} × ${KHO.cao} mm</title>
<style>${css(true)}
	body { margin: 0; }
</style></head><body>
${tem.join("\n")}
<script>
	window.onload = function () {
		window.print();
		// Đóng ngay có thể HUỶ lệnh in ở một số engine — chờ một nhịp.
		setTimeout(function () { window.close(); }, 400);
	};
<\/script>
</body></html>`;

		const cua_so = window.open("", "_blank", "width=460,height=600");
		if (!cua_so) return false;
		cua_so.document.write(trang);
		cua_so.document.close();
		return true;
	}

	return {
		KHO,
		X_MM,
		YEN_TINH_MM,
		TRAN_VE_DUOC,
		TRAN_YEN_TINH,
		so_module,
		ke_hoach_vach,
		ve_tem,
		css,
		ve_xem_truoc,
		in_xap,
	};
})();
