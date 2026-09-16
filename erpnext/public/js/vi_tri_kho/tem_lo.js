// Bộ VẼ nhãn lô 50×30mm — hai bố cục A/B, chọn bằng SỐ MODULE ĐO ĐƯỢC.
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
// VÌ SAO CÓ HAI BỐ CỤC — và vì sao phải ĐO chứ không ước lượng
//
// Máy in: Zebra ZD421, 203 dpi = 8 dot/mm, 1 dot = 0,125mm. Đầu in nhiệt chỉ
// bật/tắt được NGUYÊN dot. Module mã vạch phải là 2 dot = 0,25mm: 1 dot dưới
// ngưỡng đọc tin cậy của Code 128, 3 dot làm mã tràn khung. X = 0,25mm là giá
// trị DUY NHẤT dùng được (spec §6.2, giống hệt kết luận của tem vị trí).
//
// Mã vị trí luôn dài đúng 112 module nên tem vị trí chỉ cần MỘT bố cục, và bề
// rộng mã vạch của nó là một hằng số. SỐ LÔ thì không cố định — đo bằng chính
// JsBarcode mà frappe đóng gói: `25L4125` ra 101 module, `LOT-2026-A45` ra 167.
// Nên nhãn lô cần hai bố cục, và bề rộng mã vạch phải TÍNH chứ không phải hằng:
//
//   ≤ 112 module → bố cục A, mã vạch ở cột trái  (trần 28,0mm = 112 × 0,25)
//   ≤ 188 module → bố cục B, mã vạch hết chiều ngang (trần 47,0mm = 188 × 0,25)
//   > 188 module → không xảy ra: `ma_vach.kiem_tra_do_dai` đã chặn lúc lưu lô
//
// Bề rộng VẼ RA = số module × 0,25mm, KHÔNG phải trần — xem `ke_hoach_vach`.
//
// `may.ve(ma, k)` đặt bề rộng SVG theo mm KÈM `preserveAspectRatio="none"` —
// tức nó KÉO GIÃN mã cho vừa khung, BẤT KỂ mã dài bao nhiêu. Không có lỗi nào
// báo. Nhồi một mã 13 ký tự vào 28mm ra module hẹp hơn 2 dot, và máy quét
// ĐỌC RA SAI KÝ TỰ — không phải đọc hỏng, mà đọc ra một chuỗi khác. Sai lặng
// lẽ, trên một vật thể đã dán lên thùng hàng y tế.
//
// Nên phải đo TRƯỚC khi vẽ, và đo từ chính thứ sắp được in ra (`ve_tho`), chứ
// không đếm lại Code 128 ở JS. Đã có `erpnext/vi_tri_kho/vitri/ma_vach.py` cho
// phía máy chủ; hai bản cài đặt của cùng một phép tính thì một ngày nào đó
// `validate` cho qua một số lô mà nhãn không vẽ nổi — phát hiện ra lúc tem đã
// in ra và đã dán.
//
// ─────────────────────────────────────────────────────────────────────────────
// BA LUẬT CSS CHÉP NGUYÊN TỪ `tem_vi_tri.js` — mỗi luật là một lỗi đã trả giá
//
// 1. `flex: 0 0 auto` trên khối mã vạch. `.tem` là flex cột nên mặc định mọi
//    con đều CO ĐƯỢC. Nếu một ngày khối chữ cao thêm (thêm dòng, đổi cỡ chữ),
//    thứ nhường chỗ sẽ là MÃ VẠCH: nó thấp dần đi mà không có lỗi nào, không
//    có gì tràn, trên màn hình vẫn trông y hệt. Chỉ máy quét ngoài kho mới
//    biết — lúc đó tem đã dán rồi. Khoá cứng lại thì sai sót về chiều cao sẽ
//    TRÀN, và tràn thì phép đo bắt được.
// 2. `min-width: 0` trên mọi cột chữ. Flex item mặc định là `min-width: auto`,
//    nghĩa là KHÔNG co xuống dưới bề rộng nội dung tối thiểu. Một bản ghi dị
//    dạng (tên hàng rất dài, số lô rất dài) sẽ nống cột của nó ra và ăn mất bề
//    rộng của cột bên cạnh — thứ bị cắt là ô KHÁC, không phải ô có dữ liệu
//    xấu. Với `min-width: 0`, chữ dị dạng bị cắt TRONG Ô CỦA NÓ, kèm dấu "…".
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

	/** Mọi con số dưới đây là MILIMÉT THẬT trên con tem, trừ `co.*` là point.
	 *
	 * Vùng in an toàn 47 × 27mm = (50 − 2×1,5) × (30 − 2×1,5).
	 * `cot_trai + gap + cot_phai` = 29,4 + 0,6 + 17,0 = 47,0 ✓ cho cả hai.
	 *
	 * ─────────────────────────────────────────────────────────────────────
	 * SÀN CHIỀU CAO HÀNG — vì sao đo HỘP CHỮ chứ không đo chiều cao chữ hoa
	 *
	 * Mỗi hàng phải cao ít nhất bằng HỘP CHỮ (đỉnh ascender → đáy descender)
	 * của cỡ chữ lớn nhất trong nó, chứ không phải bằng chiều cao chữ hoa.
	 * Một trường tiếng Việt có dấu đâm xuống (`ạ` `ợ` `ậ` `ộ`) sẽ chạm hàng
	 * dưới dù chữ hoa không chạm. Số đo (Chrome, Arial/Liberation Sans):
	 *
	 *   5pt → 1,85   6pt → 2,38   6,5/7pt → 2,65   8pt → 3,18   9pt → 3,70
	 *   11pt → 4,23  16pt → 6,35  18pt → 7,14      22pt → 8,73   (mm)
	 *
	 * Bản trước của bố cục B có hàng R4 cao 3,0mm chứa F5 8pt (hộp chữ
	 * 3,18mm) — đo được va chạm 0,18mm xuống hàng dưới.
	 *
	 * ─────────────────────────────────────────────────────────────────────
	 * CỠ CHỮ: TÌM RA BẰNG PHÉP ĐO, KHÔNG PHẢI CHỌN
	 *
	 * Luật: cỡ NGUYÊN lớn nhất sao cho hộp chữ của chuỗi DÀI NHẤT THỰC TẾ
	 * vừa ô, chừa biên ≥ 0,5mm. Cột phải 17,0mm → trần 16,5mm.
	 *
	 *   F7 "NHẬP 2026/09/03"  6pt = 17,02 ✗  →  5pt = 14,17 ✓   (A: 6,5 → 5)
	 *   F8 "VT 3B1205-0401"   7pt = 18,80 ✗  →  6pt = 16,12 ✓   (A: 7 → 6)
	 *
	 * ─────────────────────────────────────────────────────────────────────
	 * F9 — RÀNG BUỘC KHÔNG THOẢ ĐƯỢC, CHỜ CHỦ ĐẦU TƯ QUYẾT
	 *
	 * Hai yêu cầu loại trừ nhau trong cột 17,0mm, và đây là phép chứng minh
	 * bằng số chứ không phải ý kiến:
	 *
	 *   (a) F9 không được nhỏ hơn 18pt (đọc từ giữa lối đi)
	 *   (b) §4.4: số gọi vượt 9999 thành 5 chữ số thì phải CO CHỮ, không
	 *       được CẮT SỐ
	 *
	 *   "38561" @ 18pt = 17,66mm  >  17,0mm cột  →  BỊ CẮT, phạm (b)
	 *   "38561" @ 17pt = 17,00mm  =  17,0mm cột  →  vừa khít, biên 0
	 *   "38561" @ 16pt = 15,69mm  ✓  vừa, biên 1,31mm  →  phạm (a)
	 *   "3856"  @ 21pt = 16,47mm  ✓  (bốn chữ số thì rộng rãi)
	 *
	 * Bố cục A giữ SÀN 18pt theo đúng chỉ thị ("18pt không vừa thì đừng hạ
	 * tiếp, báo lại") — nên số gọi 5 chữ số Ở BỐ CỤC A VẪN BỊ CẮT.
	 *
	 * Bố cục B KHÔNG nâng lên 18pt được, và lý do là CHIỀU CAO chứ không
	 * phải bề ngang: F9 trải hai hàng R4+R5, 18pt cần 7,14mm, mà tổng sàn
	 * của bảy hàng khi đó là 4,23 + 3,70 + 2,65 + 7,14 + 2,65 + 6,65 =
	 * 27,02mm > 27,0mm ngân sách. Thiếu 0,02mm. Nên B giữ 16pt — và B là
	 * chỗ DUY NHẤT trên cả hai bố cục mà số gọi 5 chữ số in ra KHÔNG bị cắt.
	 *
	 * Muốn thoả cả (a) và (b) thì phải nới cột phải lên ≥ 18,16mm
	 * (17,66 + 0,5). Cột trái còn 47,0 − 0,6 − 18,16 = 28,24mm. Mã vạch bố
	 * cục A dài nhất là 112 module = 28,0mm, cộng vùng yên tĩnh tối thiểu
	 * 10 module = 2,5mm mỗi bên thì cần 33,0mm. 28,24 < 33,0 → KHÔNG đủ
	 * chỗ. Tức là: mã vạch và số gọi 5 chữ số 18pt không cùng đứng một hàng
	 * ngang được. Lối ra là đổi bố cục (cho F9 một hàng riêng), và đó là
	 * quyết định của chủ đầu tư.
	 *
	 * ─────────────────────────────────────────────────────────────────────
	 * VÙNG YÊN TĨNH CỦA MÃ VẠCH BỐ CỤC A — một điểm cần biết
	 *
	 * Code 128 cần vùng trắng ≥ 10 module = 2,5mm mỗi đầu. Bố cục A đặt mã
	 * vạch trong cột trái 29,4mm, và ngay bên phải cột đó có một NÉT KẺ ĐEN.
	 * Với mã 101 module (25,25mm) căn giữa: 2,08mm bên trái, 2,25mm từ đuôi
	 * mã tới nét kẻ. Cả hai dưới 2,5mm. Với mã dài 112 module (28,0mm) thì
	 * chỉ còn 0,7mm mỗi bên. Bố cục B không bị (mã vạch chiếm trọn chiều
	 * ngang, hai bên là nền trắng của tem). Không tự sửa vì sửa là đổi
	 * `cot_trai`/`cot_phai` — cùng một quyết định bố cục ở trên.
	 */
	const KHO = {
		rong: 50,
		cao: 30,
		le: 1.5,
		A: {
			ma: "A",
			ten: "A (mã vạch cột trái, trần 28,0mm)",
			// Chiều cao hàng: mỗi hàng cao ÍT NHẤT bằng hộp chữ cao nhất trong
			// nó (đo thật, xem khối "SÀN CHIỀU CAO HÀNG" dưới đây), tổng đúng
			// 27,0. Mọi con số là bội của 0,125mm = 1 dot chẵn.
			//   R1 ≥ 4,23 (F1 11pt) · R2 ≥ 3,70 (F2 9pt) · R3 ≥ 2,65 (F4 6,5pt)
			//   R4 ≥ 3,18 (F5 8pt)  · R5 ≥ 2,65 (F6 7pt) · R6 ≥ 7,14 (F9 18pt)
			hang: [5.0, 4.5, 3.5, 3.5, 3.0, 7.5], // = 27,0
			cot_trai: 29.4,
			gap: 0.6,
			cot_phai: 17.0,
			vach_rong: 28.0,
			vach_cao: 5.0,
			co: { f1: 11, f2: 9, f3: 6.5, f4: 6.5, f5: 8, f6: 7, f7: 5, f8: 6, f9: 18, f11: 5 },
		},
		B: {
			ma: "B",
			ten: "B (mã vạch hết ngang, trần 47,0mm)",
			// Sàn từng hàng (đo thật), tổng đúng 27,0, mọi số là bội 0,125mm:
			//   R1 ≥ 4,23 (F1 11pt)   · R2 ≥ 3,70 (F2 9pt) · R3 ≥ 2,65 (F4 6,5pt)
			//   R4 ≥ 3,18 (F5 8pt)    · R5 ≥ 2,65 (F6 7pt)
			//   R4+R5 ≥ 6,35 (F9 16pt trải hai hàng)
			//   R6 ≥ 2,65 (F8 7pt · F7 6,5pt)
			//   R7 ≥ 6,65 (mã vạch 4,8 + F11 5pt 1,85)
			// Tổng sàn = 26,23; dư 0,77 chia cho các hàng chữ. Chật đến mức
			// này là lý do B KHÔNG nâng F9 lên 18pt được — xem khối dưới.
			hang: [4.375, 3.875, 2.75, 3.375, 3.125, 2.75, 6.75], // = 27,0
			cot_trai: 29.4,
			gap: 0.6,
			cot_phai: 17.0,
			vach_rong: 47.0,
			vach_cao: 4.8,
			co: { f1: 11, f2: 9, f3: 6.5, f4: 6.5, f5: 8, f6: 7, f7: 6.5, f8: 7, f9: 16, f11: 5 },
		},
	};

	/** Chiều cao dùng được = 30 − 2×1,5. Mỗi mảng `hang` phải cộng ĐÚNG số này.
	 *
	 * VÌ SAO phải có phép kiểm này thay vì tin vào chú thích "= 27,0": nếu ai
	 * đó chỉnh một con số mà quên chỉnh con số bù lại, nhãn TRÀN ra ngoài vùng
	 * in — và `overflow: hidden` ở `.tem` (luật đỡ cuối, xem `css()`) sẽ NUỐT
	 * phần tràn đó. Không có lỗi nào báo, màn hình xem trước trông vẫn ổn, chỉ
	 * là chữ bị cắt trên giấy, phát hiện ra khi tem đã dán lên hàng.
	 *
	 * So bằng epsilon chứ không bằng `===`: hôm nay cả hai mảng đều cộng chẵn
	 * trong dấu phẩy động, nhưng phép kiểm này sống để đỡ những lần SỬA SAU —
	 * và lần sửa đầu tiên đụng vào một số lẻ (3,1 / 4,2 …) sẽ làm `=== 27` sai
	 * trong khi hình học vẫn đúng. Một phép kiểm báo động giả là một phép kiểm
	 * bị người ta gỡ đi.
	 */
	const CAO_DUNG_DUOC = KHO.cao - 2 * KHO.le;
	["A", "B"].forEach(function (bc) {
		const tong = KHO[bc].hang.reduce(function (a, b) {
			return a + b;
		}, 0);
		console.assert(
			Math.abs(tong - CAO_DUNG_DUOC) < 1e-9,
			`tem_lo: bố cục ${bc} có tổng chiều cao hàng = ${tong}mm, phải đúng ${CAO_DUNG_DUOC}mm`
		);
	});

	/** Trần số module của mỗi bố cục — SUY RA từ `vach_rong`, không gõ tay.
	 *
	 * Quan hệ ở đây KHÔNG phải trùng hợp: `vach_rong` là bề rộng LỚN NHẤT mà
	 * mã vạch được chiếm, mà mỗi module lại phải rộng đúng `X_MM`, nên số
	 * module lớn nhất vẽ nổi CHÍNH LÀ `vach_rong / X_MM`. Sửa `vach_rong` thì
	 * trần đi theo, đúng như phải thế.
	 *
	 * Gõ tay "112" và "188" thì hai con số đó rời khỏi `vach_rong` ngay lần
	 * đầu ai đó sửa bề rộng mã vạch, và hệ quả của việc rời nhau là chọn bố
	 * cục A cho một mã không vừa cột trái — đúng cái lỗi "đọc ra sai ký tự".
	 * `ma_vach.py` suy ra y hệt (`int(28.0 / X_MM)`), nên hai phía không thể
	 * lệch nhau mà không ai thấy.
	 *
	 * (Đừng nhầm `vach_rong` với bề rộng VẼ RA: 112 × 0,25 = 28,0mm chỉ là
	 * bề rộng của một mã DÀI ĐÚNG 112 module. Mã ngắn hơn vẽ hẹp hơn — xem
	 * `ke_hoach_vach`.)
	 */
	const MODULE_TOI_DA = {
		A: Math.floor(KHO.A.vach_rong / X_MM), // 112
		B: Math.floor(KHO.B.vach_rong / X_MM), // 188
	};

	function esc(s) {
		return frappe.utils.escape_html(s == null ? "" : String(s));
	}

	/** Số module Code 128 của `ma`, ĐO từ SVG do JsBarcode dựng.
	 *
	 * `width: 2` trong `TUY_CHON_VACH` (`tem_vi_tri.js`) nghĩa là mỗi module
	 * rộng 2 px, `margin: 0` nghĩa là không có lề cộng thêm. Nên:
	 *
	 *     số module = bề rộng px của nội dung SVG ÷ 2
	 *
	 * Không tự cài đặt lại phép đếm Code 128 ở đây — xem khối chú thích đầu
	 * file. Đo từ chính thứ sẽ được in ra là nguồn sự thật duy nhất.
	 *
	 * ĐỌC `viewBox`, KHÔNG ĐỌC THUỘC TÍNH `width`. Đây không phải chuyện thẩm
	 * mỹ — đọc `width` cho ra một con số SAI CỐ ĐỊNH:
	 *
	 *     frappe/public/js/frappe/form/controls/barcode.js, get_barcode_html:
	 *         JsBarcode(svg, value, this.get_options(value));
	 *         $(svg).attr("width", "100%");     ← ghi đè bề rộng px
	 *
	 * nên `parseFloat(svg.getAttribute("width"))` luôn ra 100, cho MỌI mã, và
	 * `100 / 2 = 50 ≤ 112` — tức là MỌI số lô, dài đến đâu, cũng được xếp vào
	 * bố cục A và bị ép vào 28mm. Đúng cái hỏng mà file này sinh ra để chặn:
	 * module hẹp hơn 2 dot, máy quét đọc ra SAI KÝ TỰ, không ai thấy.
	 * (Đo bằng chính JsBarcode frappe đóng gói: 25L4125 → 202px, LOT-2026-A45
	 * → 334px, 1B01040302 → 224px; đọc `width` thì cả ba đều ra "100%".)
	 *
	 * `viewBox` thì do chính `SVGRenderer.setSvgAttributes` của JsBarcode ghi
	 * (`"0 0 <px bề rộng> <px chiều cao>"`) và KHÔNG ai ghi đè.
	 *
	 * Trả `0` khi không đo được. Bên gọi phải hiểu 0 là "ĐO HỎNG" chứ không
	 * phải "mã rất ngắn" — xem `chon_bo_cuc`.
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

	/** Chọn bố cục cho mã `ma`. Trả `"A"` hoặc `"B"`.
	 *
	 * Vượt 188 module thì LẼ RA không tới được đây: `ma_vach.kiem_tra_do_dai`
	 * chặn từ lúc lưu lô. Nhưng in LẠI một lô cũ — tạo trước khi khối C có
	 * phép kiểm đó — thì tới được. Khi ấy vẫn vẽ (không chặn in: thủ kho cần
	 * con tem, và một nhãn không quét được vẫn đọc tay được nhờ F11), nhưng
	 * PHẢI nói thẳng ra rằng mã có thể không quét được. Im lặng ở đây là để
	 * người ta dán lên hàng một mã mà máy quét đọc ra chuỗi khác.
	 */
	function chon_bo_cuc(may, ma) {
		return ke_hoach_vach(may, ma).bo_cuc;
	}

	/** Bố cục + bề rộng mã vạch THẬT cho `ma`, đo một lần, dùng cho cả hai.
	 *
	 * Trả `{ bo_cuc, so_module, k, k_ve }` — `k` là hằng số bố cục nguyên bản,
	 * `k_ve` là bản sao chỉ khác ở `vach_rong`, dành riêng cho `may.ve()`.
	 *
	 * ─────────────────────────────────────────────────────────────────────
	 * VÌ SAO BỀ RỘNG MÃ VẠCH KHÔNG PHẢI HẰNG SỐ `vach_rong`
	 *
	 * `vach_rong` (28,0 / 47,0mm) là TRẦN — chỗ rộng nhất mà mã vạch được
	 * chiếm — chứ không phải bề rộng để vẽ. Bề rộng để vẽ phải là
	 *
	 *     số module × 0,25mm   (= số module × 2 dot)
	 *
	 * Tem VỊ TRÍ không phân biệt hai thứ này vì mã vị trí LUÔN dài đúng 112
	 * module, nên 112 × 0,25 = 28,0 = `vach_rong`. Số lô thì KHÔNG cố định:
	 * đo bằng chính JsBarcode frappe đóng gói, `25L4125` ra 101 module.
	 * Kéo 101 module cho đầy 28,0mm là
	 *
	 *     28,0 ÷ 101 = 0,2772mm/module = 2,22 dot
	 *
	 * — KHÔNG phải số dot nguyên. Trình điều khiển máy in phải làm tròn từng
	 * vạch về dot gần nhất, nên vạch ra lúc 2 dot lúc 3 dot, KHÔNG ĐỀU. Đó
	 * đúng là hỏng mà commit cd749e16 đã sửa cho tem vị trí (bản trước để
	 * 2,57 dot/module): máy quét lúc đọc được lúc không, tuỳ con tem và tuỳ
	 * góc quét. Không ai gọi nó là lỗi, người ta chỉ "quét lại lần nữa".
	 *
	 * Với 101 × 0,25 = 25,25mm thì mọi vạch đúng 2 dot chẵn, và 25,25mm vẫn
	 * nằm gọn trong cột trái 29,4mm (căn giữa, vùng trắng 2,08mm mỗi bên —
	 * trên mức tối thiểu 10 module = 2,5mm thì hơi thiếu, nhưng nền tem hai
	 * bên vẫn trắng nên vùng yên tĩnh thực tế rộng hơn thế).
	 *
	 * `Math.min` với `vach_rong` chỉ để chặn ca vượt trần (in lại lô cũ tạo
	 * trước khi `ma_vach.kiem_tra_do_dai` có mặt) — ca đó đã kèm cảnh báo.
	 */
	function ke_hoach_vach(may, ma) {
		const m = so_module(may, ma);
		const bo_cuc = _bo_cuc_theo_module(m, ma);
		const k = KHO[bo_cuc];
		const rong = m ? Math.min(m * X_MM, k.vach_rong) : k.vach_rong;
		return { bo_cuc, so_module: m, k, k_ve: Object.assign({}, k, { vach_rong: rong }) };
	}

	function _bo_cuc_theo_module(m, ma) {
		// ĐO HỎNG (m = 0) thì ngả về B, KHÔNG về A. Hai bố cục không đối xứng
		// về hậu quả: B rộng 47mm nên mọi mã hợp lệ đều quét được trong đó,
		// còn A là hướng BÓP NHỎ — chọn nhầm A là chọn cái sai lặng lẽ. Một
		// nhãn B hơi rộng tay thì xấu; một nhãn A quá chật thì máy quét đọc ra
		// chuỗi khác. "Không đo được" không bao giờ được rơi về phía chật.
		if (!m) return "B";
		if (m <= MODULE_TOI_DA.A) return "A";
		if (m <= MODULE_TOI_DA.B) return "B";

		frappe.msgprint({
			title: __("Mã vạch có thể KHÔNG QUÉT ĐƯỢC"),
			indicator: "red",
			message: __(
				"Số lô {0} cần {1} module mã vạch nhưng nhãn 50×30 chỉ chứa được {2}. " +
					"Nhãn vẫn in (bố cục B) nhưng mã vạch bị ép hẹp hơn 2 dot — máy quét " +
					"có thể đọc ra SAI KÝ TỰ chứ không phải báo lỗi. Quét thử trước khi " +
					"dán, hoặc đổi sang số lô ngắn hơn.",
				[esc(ma), m, MODULE_TOI_DA.B]
			),
		});
		return "B";
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
	 * `hinh_vach` truyền từ ngoài vào (đã serialize) để một mã vạch vẽ một lần
	 * rồi dùng cho cả N bản in của cùng lô đó.
	 */
	function ve_tem(o, hinh_vach, bo_cuc) {
		const k = KHO[bo_cuc] || KHO.A;
		// Khối mã vạch giống nhau ở cả hai bố cục: vạch ở trên, F11 ngay dưới.
		// F11 nằm DƯỚI chứ không nằm BÊN mã vạch (khác cách phác trong spec):
		// mã vạch rộng 28,0mm trong cột 29,4mm (bố cục A) và rộng trọn 47,0mm
		// (bố cục B) — không còn bề ngang nào để đặt chữ bên cạnh.
		const khoi_vach = `<div class="vach">${hinh_vach}</div>
		<div class="f11">${esc(o.F11)}</div>`;

		if (k.ma === "B") {
			return `<div class="tem bo-cuc-B">
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
	<div class="hang h7 o-vach">${khoi_vach}</div>
</div>`;
		}

		return `<div class="tem bo-cuc-A">
	<div class="hang h1"><span class="f1">${esc(o.F1)}</span><span class="f3">${esc(o.F3)}</span></div>
	<div class="hang h2"><span class="f2">${esc(o.F2)}</span></div>
	<div class="hang h3"><span class="f4">${esc(o.F4)}</span></div>
	<div class="duoi">
		<div class="cot-trai">
			<div class="hang h4"><span class="f5">${esc(o.F5)}</span></div>
			<div class="hang h5"><span class="f6">${esc(o.F6)}</span></div>
			<div class="hang h6 o-vach">${khoi_vach}</div>
		</div>
		<div class="cot-phai">
			<div class="hang h4"><span class="f7">${esc(o.F7)}</span></div>
			<div class="hang h5"><span class="f8">${esc(o.F8)}</span></div>
			<div class="hang h6 o-f9"><span class="f9">${esc(o.F9)}</span></div>
		</div>
	</div>
</div>`;
	}

	/** CSS cho MỘT bố cục. `cho_in = true` thì kèm `@page` và ngắt trang.
	 *
	 * MỌI luật đều mang tiền tố `.tem.bo-cuc-X`. VÌ SAO không dùng `.tem` trơn
	 * như `tem_vi_tri.js`: ở đó chỉ có một bố cục trên một trang, ở đây MỘT
	 * XẤP CÓ THỂ TRỘN CẢ HAI (một phiếu nhập có lô `25L4125` ra bố cục A và lô
	 * `LOT-2026-A45` ra bố cục B). Đặt hai bộ luật không tiền tố lên cùng một
	 * trang thì bộ SAU đè bộ TRƯỚC: chiều cao hàng của B áp lên nhãn A, tổng
	 * vẫn 27,0mm nên KHÔNG có gì tràn, không có lỗi nào báo — chỉ là mã vạch
	 * bố cục A bị vẽ ở kích thước của B. Đây là lỗi đã mắc một lần.
	 */
	function css(k, cho_in) {
		const goc = `.tem.bo-cuc-${k.ma}`;

		// Chiều cao hàng sinh THẲNG từ `k.hang` — không gõ lại ở CSS. Gõ lại
		// là dựng một bản thứ hai của cùng bộ số, và `console.assert` ở trên
		// chỉ canh bản thứ nhất.
		const cao_hang = k.hang
			.map(function (h, i) {
				return `\t${goc} .h${i + 1} { height: ${h}mm; }`;
			})
			.join("\n");

		// Cỡ chữ cũng sinh thẳng từ `k.co`, cùng lý do.
		const co_chu = Object.keys(k.co)
			.map(function (f) {
				return `\t${goc} .${f} { font-size: ${k.co[f]}pt; }`;
			})
			.join("\n");

		const trang = cho_in
			? `@page { size: ${KHO.rong}mm ${KHO.cao}mm; margin: 0; }
	${goc} { page-break-after: always; break-after: page; }
	/* Không có dòng này thì máy nhả thêm một con tem TRẮNG ở cuối mỗi xấp. */
	${goc}:last-child { page-break-after: auto; break-after: auto; }`
			: // `outline` chu KHONG `border`: border (voi box-sizing: border-box)
			  // an 0,2mm moi phia vao chinh vung in, nen o xem truoc se co bo
			  // cuc LECH voi to giay se in ra - do duoc 0,26mm o moi le va
			  // 0,53mm be ngang. O xem truoc khac to in la o xem truoc mat y
			  // nghia. outline khong chiem cho trong bo cuc.
			  `${goc} { outline: 0.2mm dashed #b8b8b8; outline-offset: -0.2mm; }`;

		// Khối riêng của từng bố cục: A chia đôi cột cho BA hàng cuối (F10/F11
		// bên trái, F7/F8/F9 bên phải); B chia đôi cột cho HAI hàng giữa (F9
		// trải hết chiều cao cột phải) rồi trả lại nguyên chiều ngang cho F8
		// và mã vạch.
		const rieng =
			k.ma === "B"
				? `
	${goc} .giua {
		height: ${k.hang[3] + k.hang[4]}mm;
		flex: 0 0 auto; min-height: 0;
		display: flex;
		position: relative;
	}
	/* F9 trải trọn hai hàng R4-R5 của cot-phai (cot-phai da la flex cot,
	   o-f9 chi them can giua) - mot con so doc qua loi di thi cang to cang
	   tot, va hai hang chu ben trai von da kin.
	   (KHONG dung dau huyen va dau nguoc trong chu thich CSS: ca khoi nay nam
	   trong mot template literal, mot dau nguoc lac la cat dut chuoi.) */
	/* F7 đi cùng F8 trên hàng R6 (rộng TRỌN 47,0mm), KHÔNG đi cùng F6 trên
	   hàng R5 (rộng 29,4mm).
	   Đo thật, cùng font đang dựng:
	     F6 + F7 trên 29,4mm = 19,62 + 18,42 = 38,04mm  -> cả hai bị cắt
	     F5 + F7 trên 29,4mm = 20,85 + 18,42 = 39,27mm  -> còn TỆ HƠN
	     F8 + F7 trên 47,0mm = 18,80 + 18,42 = 37,22mm  -> VỪA, dư 9,78mm
	   Hàng R6 trước đây chỉ có mỗi F8 (18,80mm trong 47,0mm), tức bỏ không
	   28,2mm ngay cạnh hai ô đang phải cắt chữ. Đây là chỗ duy nhất trên con
	   tem còn đủ bề ngang cho F7. */
	${goc} .h6 { justify-content: space-between; }
	/* F8 không được nuốt hết hàng R6 nữa (luật chung cho nó là flex: 1 1 auto)
	   — có space-between thì nó phải nhường chỗ cho F7. */
	${goc} .h6 .f8 { flex: 0 1 auto; }
	/* Duong ke tren hang F8, doi xung voi duong ke tren .giua. Van la lop phu
	   tuyet doi, khong phai border - xem ly do o khoi chung. */
	${goc} .h6 { position: relative; }
	${goc} .h6::before {
		content: ""; position: absolute; left: 0; right: 0; top: 0;
		height: 0.25mm; background: #000;
	}`
				: `
	${goc} .duoi {
		height: ${k.hang[3] + k.hang[4] + k.hang[5]}mm;
		flex: 0 0 auto; min-height: 0;
		display: flex;
		position: relative;
	}`;

		return `
	* { box-sizing: border-box; }
	${goc} {
		width: ${KHO.rong}mm; height: ${KHO.cao}mm;
		padding: ${KHO.le}mm;
		min-width: 0;
		display: flex; flex-direction: column;
		background: #fff; color: #000;
		font-family: Arial, Helvetica, sans-serif;
		/* Chữ số cùng bề rộng: HSD, ngày nhập, số gọi và số lô đều là số, và
		   số rộng bằng nhau thì bề rộng ô đoán trước được — đó là điều kiện để
		   phép đo trên trình duyệt có ý nghĩa cho MỌI lô chứ không chỉ cho lô
		   vừa đo. */
		font-variant-numeric: tabular-nums;
		/* Lưới đỡ cuối: một con tem TRÀN không chỉ xấu — trên cuộn liên tục
		   nó đẩy lệch MỌI con tem in sau nó. Nhưng đây là lưới ĐỠ, không phải
		   phép kiểm: nó nuốt phần tràn trong im lặng, nên phép đo từng ô bằng
		   Range mới là thứ bắt được lỗi. */
		overflow: hidden;
	}
	/* flex: 0 0 auto trên MỌI hàng — KHÔNG phải thừa.
	   .tem là flex cột, nên mặc định mọi con đều co được. Nếu một ngày một
	   khối chữ cao thêm, thứ nhường chỗ sẽ là hàng có mã vạch: nó thấp dần đi
	   mà không có lỗi nào, không có gì tràn, và trên màn hình vẫn trông y hệt.
	   Chỉ máy quét ngoài kho mới biết — mà lúc đó tem đã dán rồi. Khoá cứng
	   lại thì một sai sót về chiều cao sẽ TRÀN, và tràn thì phép đo bắt được. */
	${goc} .hang {
		flex: 0 0 auto;
		min-width: 0;
		/* min-height: 0 la ve DOC cua luat min-width: 0, va no can thiet vi
		   cung mot ly do. Flex item mac dinh min-height: auto, tuc KHONG co
		   xuong duoi chieu cao noi dung. Mot co chu qua to (hop dong cao hon
		   o) se NONG hang do ra thay vi bi cat: cac hang duoi bi day xuong,
		   ma vach tut ra khoi vung in, va overflow: hidden o .tem nuot phan
		   thua. Do duoc: F9 22pt trong hang 7,0mm lam o do cao 7,76mm va day
		   ca khoi duoi xuong 0,76mm. Voi min-height: 0 thi chu qua to bi CAT
		   trong o cua no va phep do bat duoc ngay. */
		min-height: 0;
		/* align-items: center, KHONG phai baseline.
		   Voi baseline, hop dong (line-height 1 = 1,0em) bam DINH hang, con
		   hop CHU that (dinh ascender -> day descender) cao khoang 1,15em nen
		   no tho ra 0,18mm PHIA TREN dinh hang - tuc dam vao hang o tren.
		   Do duoc: 0,18mm giua F5 va hang duoi no o bo cuc B.
		   Voi center, hop chu nam giua hang, nen chi can hang cao it nhat bang
		   hop chu (dung luat o khoi hang so) la chu nam TRON trong hang. */
		display: flex; align-items: center;
		/* KHONG dat overflow: hidden o HANG.
		   Ngan sach 27,0mm cua bo cuc B chi con 0,768mm du sau khi tru san
		   chieu cao cua bay hang, nen ba hang cua no chi con 0,10mm bien va
		   hop chu con tho ra toi 0,12mm. Neu HANG tu cat thi 0,12mm do bi
		   xen mat - dung vao chan cac dau tieng Viet dam xuong.
		   Cat chu la viec cua tung O (moi span da co overflow: hidden kem
		   ellipsis, cat theo chieu NGANG dung cho no), con luoi do cuoi cung
		   van la overflow: hidden o .tem. Hang o giua khong can cat gi. */
	}
	/* min-width: 0 trên mọi ô chữ — chặn một lỗi IM LẶNG.
	   Flex item mặc định là min-width: auto, tức KHÔNG co xuống dưới bề rộng
	   nội dung tối thiểu. Một tên hàng rất dài sẽ nống ô của nó ra và ăn mất
	   bề rộng ô bên cạnh: thứ bị cắt là ô KHÁC, không phải ô có dữ liệu xấu.
	   Cắt bằng "…" chứ không cắt trần: một số lô cụt trông y như số lô thật và
	   người ta gõ nhầm nó, còn "25L4…" thì nhìn là biết chưa đọc hết. */
	${goc} .f1, ${goc} .f2, ${goc} .f3, ${goc} .f4, ${goc} .f5,
	${goc} .f6, ${goc} .f7, ${goc} .f8, ${goc} .f11 {
		min-width: 0;
		white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
		line-height: 1;
	}
	/* Cột trái / cột phải: 29,4 + 0,6 + 17,0 = 47,0mm đúng bằng vùng in. */
	${goc} .cot-trai {
		flex: 0 0 ${k.cot_trai}mm; min-width: 0; min-height: 0;
		display: flex; flex-direction: column;
	}
	${goc} .cot-phai {
		flex: 0 0 ${k.cot_phai}mm; min-width: 0; min-height: 0;
		margin-left: ${k.gap}mm;
		display: flex; flex-direction: column;
		position: relative;
	}
	/* Hai đường kẻ vẽ bằng LỚP PHỦ TUYỆT ĐỐI, không bằng border.
	   border ăn vào ngân sách 27,0mm / 47,0mm đã cân đúng ở khối hằng số, và
	   thứ bị ăn mất là chiều cao của một hàng chữ — cắt trong im lặng dưới
	   overflow: hidden. Lớp phủ thì tốn 0 mm bố cục.
	   0,25mm = 2 dot chẵn trên đầu in 203 dpi: nét rơi đúng lưới dot thay vì
	   lệch nửa dot rồi ra nét mảnh chỗ đậm chỗ nhạt. */
	${goc} .duoi::before, ${goc} .giua::before {
		content: ""; position: absolute; left: 0; right: 0; top: 0;
		height: 0.25mm; background: #000;
	}
	/* Duong ke DOC ve tu KHOI CHA, khong ve tu .cot-phai.
	   Do duoc: dat no tren .cot-phai thi o bo cuc B no BIEN MAT, vi o do
	   .cot-phai cung mang .o-f9 (overflow: hidden) va net ke nam ngoai hop -
	   bi chinh o do cat mat. Khong co loi nao bao, chi la mot duong ke co o
	   nhan nay va khong co o nhan kia. Ve tu khoi cha thi net nam trong hop
	   cua khoi cha, khong phu thuoc vao thuoc tinh cua cot. */
	${goc} .duoi::after, ${goc} .giua::after {
		content: ""; position: absolute; top: 0; bottom: 0;
		left: ${k.cot_trai + k.gap / 2 - 0.125}mm;
		width: 0.25mm; background: #000;
	}
	${goc} .f1 { flex: 1 1 auto; font-weight: 700; }
	${goc} .f2 { flex: 1 1 auto; font-weight: 700; }
	${goc} .f3 { flex: 0 1 auto; max-width: 50%; margin-left: 1.5mm; text-align: right; }
	${goc} .f4 { flex: 1 1 auto; }
	${goc} .f5 { flex: 1 1 auto; font-weight: 700; }
	${goc} .f6 { flex: 0 1 auto; }
	${goc} .f7 { flex: 0 1 auto; }
	${goc} .f8 { flex: 1 1 auto; font-weight: 700; }
	/* O F9 (so goi): can giua ca hai chieu, cat trong o cua no.
	   align-items center chu khong baseline nhu cac hang khac - F9 dung mot
	   minh trong o nen khong co gi de no canh duong chan chu cung. */
	${goc} .o-f9 {
		display: flex; align-items: center; justify-content: center;
		overflow: hidden;
	}
	${goc} .f9 {
		font-weight: 700; line-height: 1;
		white-space: nowrap; min-width: 0;
		overflow: hidden; text-overflow: ellipsis;
	}
	/* Khối mã vạch: vạch trên, F11 dưới, căn giữa theo chiều ngang.
	   flex-direction: column + align-items: center — vùng trắng chia đều hai
	   bên khi mã vạch hẹp hơn ô (bố cục A: 28,0mm trong 29,4mm). */
	${goc} .o-vach {
		display: flex; flex-direction: column; align-items: center;
		overflow: hidden;
	}
	/* flex: 0 0 auto — luật số 1 ở đầu file, chỗ nó QUAN TRỌNG NHẤT.
	   Chiều cao mã vạch là thứ DUY NHẤT trên con tem này mà co lại không gây
	   ra bất kỳ dấu hiệu nào nhìn thấy được. */
	${goc} .vach {
		flex: 0 0 auto;
		height: ${k.vach_cao}mm; max-width: ${k.vach_rong}mm;
		line-height: 0;
	}
	/* line-height dưới 1 cho F11 — có tính toán, không phải tuỳ tiện.
	   Bố cục B: hàng cuối cao 6,5mm, mã vạch ăn 4,8mm, còn 1,7mm. 5pt với
	   line-height 1 là 1,76mm — TRÀN 0,06mm, và tràn đó bị overflow: hidden
	   nuốt mất. 0,9 cho hộp dòng 1,59mm, vừa; chữ số không có nét dưới đường
	   chân (không có g/j/p/q) nên thu hộp dòng không cắt vào nét nào. */
	${goc} .f11 {
		flex: 1 1 auto; width: 100%;
		line-height: 0.9;
		text-align: center;
		letter-spacing: 0.02em;
	}
${cao_hang}
${co_chu}
${rieng}
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
	 *
	 * Bố cục CHỌN Ở ĐÂY, bằng đúng phép đo mà `in_xap` dùng — nếu xem trước
	 * đoán bố cục theo cách khác thì nó thôi là bản xem trước.
	 */
	function ve_xem_truoc($dich, o, he_so) {
		const may = may_vach();
		const kh = ke_hoach_vach(may, o.F10);
		he_so = he_so || 2.4;
		const html = ve_tem(o, may.ve(o.F10, kh.k_ve), kh.bo_cuc);
		may.don();
		const k = kh.k;

		$dich.empty();
		$(`<div class="vi-tri-kho-xem-tem-lo" style="
				width:${KHO.rong * he_so}mm; height:${KHO.cao * he_so}mm; overflow:hidden;">
			<style>${css(k, false)}</style>
			<div style="transform:scale(${he_so}); transform-origin:top left;">${html}</div>
		</div>`).appendTo($dich);
	}

	/** Dựng và mở cửa sổ in cho cả xấp nhãn. Trả `false` nếu bị chặn pop-up.
	 *
	 * `danh_sach` là kết quả `nhap_lo.du_lieu_tem` (mảng dict F1…F11).
	 * `so_ban` mặc định 1 — mỗi lô một nhãn (spec §6.5).
	 *
	 * Mỗi lô tự chọn bố cục của nó, nên một xấp CÓ THỂ trộn A và B. Chỉ phát
	 * ra `<style>` của những bố cục THỰC SỰ dùng, và cả hai bộ đều có tiền tố
	 * lớp riêng (xem `css()`) nên đặt cạnh nhau không bộ nào đè bộ nào.
	 */
	function in_xap(danh_sach, so_ban) {
		so_ban = so_ban || 1;
		const may = may_vach();
		const tem = [];
		const da_dung = {};

		(danh_sach || []).forEach(function (o) {
			const kh = ke_hoach_vach(may, o.F10);
			da_dung[kh.bo_cuc] = true;
			// Vẽ MỘT lần cho mỗi lô rồi nhân bản chuỗi: 200 lô × 5 bản mà vẽ
			// lại từng cái là 1000 lượt dựng SVG, cửa sổ in đứng hình trước
			// khi kịp gọi print().
			const mot = ve_tem(o, may.ve(o.F10, kh.k_ve), kh.bo_cuc);
			for (let i = 0; i < so_ban; i++) tem.push(mot);
		});
		may.don();

		const bo_css = Object.keys(da_dung)
			.map(function (bc) {
				return css(KHO[bc], true);
			})
			.join("\n");

		const trang = `<!doctype html><html><head><meta charset="utf-8">
<title>${esc(__("Nhãn lô"))} ${KHO.rong} × ${KHO.cao} mm</title>
<style>${bo_css}
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
		MODULE_TOI_DA,
		so_module,
		chon_bo_cuc,
		ke_hoach_vach,
		ve_tem,
		css,
		ve_xem_truoc,
		in_xap,
	};
})();
