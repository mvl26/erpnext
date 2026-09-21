// Bộ VẼ tem vị trí kho — bố cục SPD ba nhóm số, hai khổ giấy (45×25 và 50×30mm).
//
// Dùng chung cho BA chỗ: form `Storage Location`, ô xem trước trong hộp thoại
// "In tem", và trang in thật. Một bản vẽ duy nhất, vì đó chính là điều làm cho
// ô xem trước có giá trị: xem trước một bố cục KHÁC với cái sẽ in ra thì tệ hơn
// là không xem trước gì.
//
// Nạp bằng `frappe.require("/assets/erpnext/js/warehouse_operations/tem_vi_tri.js")` từ
// hai file doctype JS. CỐ Ý không đưa vào bundle và không thêm `app_include_js`
// vào `erpnext/hooks.py`: tài liệu bàn giao của module này gọi dòng trong
// `hooks.py` là "dòng dễ mất nhất" ở mỗi lần merge ERPNext bản mới, nên không
// thêm dòng thứ hai vào đó cho một thứ chỉ hai màn hình cần.
//
// ─────────────────────────────────────────────────────────────────────────────
// BỐ CỤC — đọc ảnh nhãn SPD của kho MSC East Osaka (docs/warehouse_operations/):
//
//   ┌─────┬──────────────────────────┐
//   │ ⬛⇓ │  TẦNG        Ô           │   Mã 10 ký tự `1B01040302` tách ba nhóm
//   ├──┬──┤ ┌──────────────────────┐ │   theo đúng cách người đứng trước kệ
//   │KHU DÃY│KHOANG│     0302      │ │   tìm hàng: tới Khu+Dãy → đếm Khoang →
//   │ 1B01 │ 04 │  └───────────────┘ │   nhìn Tầng+Ô. Nhóm CUỐI to nhất vì khi
//   └──────┴────┴──────────────────┘ │   đã đứng đúng khoang thì chỉ còn nó
//   ▌│▌▌│▌ ▌│▌▌▌ │▌ ▌│▌▌ ▌│▌          │   đáng đọc.
//   Kho Miyano - MYN · Kệ inox tầng 3 │
//
// BA CHỖ CỐ Ý LÀM KHÁC ẢNH CHỤP:
//
// 1. KHÔNG có nền lốm đốm sau nhóm số lớn. Trong ảnh đó là nhiễu của máy ảnh,
//    không phải thiết kế — đầu in nhiệt gặp nền chấm sẽ nhoè và ăn mất tương
//    phản của đúng con số quan trọng nhất. Thay bằng khung viền đậm.
// 2. KHÔNG in chữ dưới mã vạch (`displayValue: false`), khác bản tem 50×30 cũ.
//    Quy tắc "luôn in chữ dưới vạch" có lý do thật — tem bẩn, ribbon mòn, máy
//    quét lỗi thì người còn gõ tay được — nhưng ba nhóm số ở trên đã làm đúng
//    việc đó và làm tốt hơn: `1B01 · 04 · 0302` dễ đọc hơn chuỗi liền. Đọc
//    liền ba nhóm ra đúng chuỗi máy quét trả về (`test_tem.py` khoá điều này).
// 3. Mũi tên ⇓ in CỐ ĐỊNH trên mọi tem, nghĩa "ô của tem này nằm ngay DƯỚI chỗ
//    dán" (tem dán lên thanh xà / mép tầng trên). Không có trường dữ liệu nào
//    cho hướng, nên không có cách nào để nó chỉ sai — một mũi tên đổi chiều
//    được mà không ai bảo trì thì tệ hơn hẳn không có mũi tên.
//
// ─────────────────────────────────────────────────────────────────────────────
// VÌ SAO MÃ VẠCH RỘNG ĐÚNG 28,0mm VÀ KHÔNG ĐƯỢC LÀM TRÒN:
//
// Máy in: Zebra ZD421, 203 dpi = 8 dot/mm, tức 1 dot = 0,125mm. Đầu in nhiệt
// chỉ bật/tắt được NGUYÊN dot — không có nửa dot.
//
// Mã vị trí Miyano luôn dài đúng 112 module Code 128 (đo bằng chính JsBarcode
// mà frappe đóng gói: `[0-9][A-Z]` đi Code B, 8 chữ số sau ghép thành 4 cặp
// Code C, nên mọi mã 10 ký tự đều ra cùng một con số). Vậy:
//
//     112 module × 2 dot = 224 dot = 224 ÷ 8 = 28,0 mm
//
// ĐỪNG làm tròn con số này cho "đẹp". Bản trước đặt 36mm: 36 × 8 ÷ 112 = 2,57
// dot/module. Trình điều khiển máy in phải làm tròn từng vạch về dot gần nhất,
// nên vạch ra lúc 2 dot lúc 3 dot KHÔNG ĐỀU — máy quét lúc đọc được lúc không,
// tuỳ con tem và tuỳ góc quét. Đó là kiểu hỏng tệ nhất: không ai gọi nó là lỗi,
// người ta chỉ "quét lại lần nữa" suốt nhiều tháng.
//
// 2 dot cũng đúng chuẩn nhà: `SPD_Nhan_NhapKho_50x30_Template.zpl` của SPD
// dùng `^BY2` cho nhãn nhập kho.
//
// Hệ quả: vùng trắng còn (45 − 28) ÷ 2 = 8,5mm mỗi bên, thừa xa mức tối thiểu
// 10 module (2,5mm). Tem trông rộng chỗ hơn cần, nhưng bề rộng vạch mới là thứ
// máy quét đọc — không đổi nó để lấp chỗ trống.
//
// `le` của khổ 45×25 là 1,25mm chứ không phải 1,2mm vì CÙNG lý do: 1,25mm = 10
// dot chẵn, nên mép trái mã vạch cũng rơi đúng vào lưới dot thay vì lệch nửa
// dot rồi kéo cả 112 vạch lệch theo.

frappe.provide("erpnext.warehouse_operations");

erpnext.warehouse_operations.tem = (function () {
	/** Mọi con số dưới đây là MILIMÉT THẬT trên con tem, trừ `co_*` là point.
	 *
	 * Một bố cục, hai khổ giấy — không phải hai bản vẽ. Nuôi hai bản vẽ thì
	 * chúng trôi khỏi nhau, và cái trôi sẽ là cái ít người in hơn, tức là cái
	 * không ai kịp phát hiện.
	 */
	const KHO_GIAY = {
		"45x25": {
			ten: "45 × 25 mm",
			rong: 45,
			cao: 25,
			le: 1.25,
			khoi_cao: 12,
			mui_ten: 5,
			cot_khu: 11.5,
			cot_khoang: 8.5,
			co_tieu_de: 5,
			co_nhom: 11,
			co_lon: 20,
			co_chan: 4,
			vach_rong: 28,
			vach_cao: 7.25,
			// 1,2 + 12 + 0,6 + 7,2 + 1,8 + 1,2 = 24,0mm — chừa 1mm cho sai số
			// bước giấy của máy in nhiệt. Tràn 1mm trên cuộn là mọi tem SAU đó
			// lệch dần, không phải mỗi tem này xấu.
			gap: 0.6,
		},
		"50x30": {
			ten: "50 × 30 mm",
			rong: 50,
			cao: 30,
			le: 1.5,
			khoi_cao: 14,
			mui_ten: 5.5,
			cot_khu: 11.5,
			cot_khoang: 9.5,
			co_tieu_de: 5.5,
			co_nhom: 12,
			co_lon: 23,
			co_chan: 4.5,
			vach_rong: 28,
			vach_cao: 9,
			gap: 0.8,
		},
	};

	const KHO_MAC_DINH = "45x25";

	function kho_giay(ma) {
		return KHO_GIAY[ma] || KHO_GIAY[KHO_MAC_DINH];
	}

	/** Bọc lấy JsBarcode mà Frappe đã đóng gói sẵn, không thêm phụ thuộc mới.
	 *
	 * `jsbarcode` bị esbuild gói kín trong `controls.bundle.*.js` của frappe,
	 * không lộ biến toàn cục; đường duy nhất chạm tới nó là qua lớp
	 * `frappe.ui.form.ControlBarcode`. `get_barcode_html()` của lớp đó vẽ thẳng
	 * vào `barcode_area` và KHÔNG bị chặn bởi `this.doc` (khác
	 * `set_formatted_input` — xem chú thích dài ở `storage_location.js`).
	 *
	 * Trả về một "máy" dùng lại được cho cả xấp tem: dựng control một lần rồi
	 * vẽ nhiều mã, thay vì dựng lại 200 control cho 200 ô.
	 */
	/** Tuỳ chọn JsBarcode — MỘT bản cho cả VẼ (`ve`) lẫn ĐO (`ve_tho`).
	 *
	 * Tách ra thành hằng số chứ không viết lặp hai chỗ, vì hai con số ở đây là
	 * giả thiết của phép đo số module ở `tem_lo.js`:
	 *
	 *     số module = bề rộng px của SVG ÷ 2
	 *
	 * đúng CHỈ KHI `width: 2` (mỗi module 2 px) và `margin: 0` (không có lề
	 * cộng thêm vào bề rộng). Nếu một ngày ai đó sửa `width` ở chỗ vẽ mà quên
	 * chỗ đo, `tem_lo.js` sẽ tính SAI số module — nghĩa là bề rộng mã vạch vẽ
	 * ra không còn bằng số module × 0,25mm, module lệch khỏi 2 dot chẵn, và
	 * máy quét đọc ra SAI KÝ TỰ. Một bản duy nhất thì không có "quên chỗ kia".
	 *
	 * (Câu cũ ở đây nói `tem_lo.js` "chọn sai BỐ CỤC" và nhắc khung 28mm. Đã
	 * lỗi thời: nhãn lô bỏ bố cục hai cột từ 16/09, nay chỉ còn một bố cục và
	 * mã vạch chiếm trọn chiều ngang — xem khối đầu `tem_lo.js`.)
	 */
	const TUY_CHON_VACH = JSON.stringify({
		format: "CODE128",
		// Ba nhóm số ở khối trên ĐÃ là phần cho mắt người đọc (xem chú thích
		// số 2 đầu file). In thêm chữ ở đây là lấy mất chiều cao của chính các
		// vạch. (Và nó đi ĐÔI với `preserveAspectRatio="none"` dưới kia —
		// đổi một cái là méo chữ.)
		displayValue: false,
		width: 2,
		height: 60,
		margin: 0,
	});

	/** Vẽ `ma` vào control rồi trả SVG — hoặc `null` nếu JsBarcode KHÔNG mã
	 * hoá được `ma`.
	 *
	 * ĐÂY LÀ CHỖ CHẶN MỘT LỖI HẠNG NẶNG, đã tái hiện được bằng phép đo:
	 *
	 *   lô 1: "25L4125"  → vẽ được, 101 module
	 *   lô 2: "LÔ-2026"  → JsBarcode NÉM LỖI, `barcode.js` NUỐT lỗi đó, và
	 *                      phần tử SVG trong `barcode_area` GIỮ NGUYÊN nội
	 *                      dung của lô 1. Lấy `find("svg")[0]` ra thì được
	 *                      một mã vạch hoàn chỉnh, đúng 101 module, không một
	 *                      dấu hiệu nào — của LÔ TRƯỚC.
	 *
	 * Trên giấy: tem của lô `LÔ-2026` in chữ `LÔ-2026` dưới mã vạch, còn mã
	 * vạch quét ra `25L4125`. Trong `in_xap` (một `may` dùng cho cả xấp) thì
	 * lô hỏng thứ k nhận mã vạch của lô thứ k−1 — một lô KHÁC của CÙNG chuyến
	 * hàng, tức trường hợp dễ nhầm nhất có thể. 200 con tem chạy ra khỏi cuộn
	 * và không có gì để thủ kho nhìn thấy.
	 *
	 * Vì sao `CODE128` từ chối: `CODE128.valid()` là `/^[\x00-\x7F\xC8-\xD3]+$/`
	 * — CHỈ ASCII. Dấu tiếng Việt và en-dash `–` (U+2013, hay bị dán từ phiếu
	 * đóng gói của nhà cung cấp) đều nằm ngoài.
	 *
	 * Cách nhận biết thành công: `barcode.js` đặt `data-barcode-value` BÊN
	 * TRONG khối `try`, NGAY SAU khi `JsBarcode()` trả về. Nên thuộc tính đó
	 * bằng đúng `ma` là tín hiệu tin cậy rằng SVG này vừa được vẽ cho `ma`,
	 * chứ không phải tàn dư của lần trước.
	 *
	 * (Tem vị trí hôm nay chưa với tới lỗi này vì mã SPD là 10 ký tự ASCII do
	 * máy sinh — một sự MAY MẮN, không phải một thiết kế. Chặn ở đây thì đóng
	 * cho cả tem vị trí lẫn tem lô.)
	 */
	function _ve_vao_control(control, ma) {
		control.df.options = TUY_CHON_VACH;
		control.get_barcode_html(ma);
		const svg = control.barcode_area.find("svg")[0];
		if (!svg) return null;
		if (svg.getAttribute("data-barcode-value") !== String(ma)) return null;
		return svg;
	}

	function may_ve_ma_vach() {
		const khung = $('<div style="display:none"></div>').appendTo(document.body);
		const control = frappe.ui.form.make_control({
			parent: khung,
			render_input: true,
			df: { fieldtype: "Barcode", fieldname: "tem", label: "" },
		});

		return {
			/** Chuỗi SVG đã đổi sang mm, nhúng thẳng được vào trang in.
			 *
			 * Vẽ vào SVG rồi SERIALIZE — không bao giờ để cửa sổ in đi tải ảnh.
			 * `print()` có thể chạy trước khi ảnh về: ra tem TRẮNG, mà lúc phát
			 * hiện thì tem đã dán lên kệ rồi.
			 */
			ve(ma, k) {
				// Trả chuỗi RỖNG khi không mã hoá được — KHÔNG BAO GIỜ trả mã
				// vạch của lần vẽ trước. Xem `_ve_vao_control`.
				const svg = _ve_vao_control(control, ma);
				if (!svg) return "";

				const ban_sao = svg.cloneNode(true);

				// viewBox phải phủ ĐÚNG bề rộng px thật của nội dung. Đổi sang
				// mm mà viewBox hẹp hơn nội dung thì phần thừa bị CẮT chứ
				// không co lại — và mã vạch cụt vẫn trông như một mã vạch.
				//
				// SỬA 2026-09-16 (Task 8). Bản trước dựng viewBox từ thuộc
				// tính `width` của SVG, dựa trên nhận định "JsBarcode đặt
				// width/height theo px và KHÔNG kèm viewBox". ĐO RA LÀ SAI ở
				// cả hai vế:
				//
				//   (a) JsBarcode CÓ đặt viewBox — `SVGRenderer.setSvgAttributes`
				//       ghi `viewBox="0 0 <px> <px>"`, đúng bề rộng nội dung.
				//   (b) `svg.getAttribute("width")` KHÔNG phải số px: ngay sau
				//       khi vẽ, `frappe/form/controls/barcode.js` chạy
				//       `$(svg).attr("width", "100%")`. Nên `parseFloat` ra
				//       đúng 100, cho MỌI mã, và viewBox dựng ra luôn là
				//       `0 0 100 60`.
				//
				// Hệ quả của bản trước, đo bằng chính JsBarcode mà frappe đóng
				// gói (bề rộng nội dung so với viewBox 100 đơn vị):
				//
				//   1B01040302 (mã vị trí) → 224px → hiện 44,6% số vạch
				//   25L4125    (số lô)     → 202px → hiện 49,5%
				//   LOT-2026-A45           → 334px → hiện 29,9%
				//
				// Tem in ra vẫn rộng đúng 28,0mm và vẫn trông như một mã vạch
				// bình thường — chỉ là hơn một nửa số vạch không có mặt. Không
				// màn hình nào báo, không phép đo bố cục nào bắt được (khối vẫn
				// đúng 28,0 × 7,25mm). Chỉ máy quét mới biết.
				//
				// Giữ viewBox của JsBarcode; chỉ tự dựng khi KHÔNG có sẵn (một
				// bản JsBarcode khác, hoặc renderer khác) — an toàn dưới cả
				// hai giả thiết.
				if (!ban_sao.getAttribute("viewBox")) {
					const w = parseFloat(svg.getAttribute("width")) || 0;
					const h = parseFloat(svg.getAttribute("height")) || 0;
					if (w && h) ban_sao.setAttribute("viewBox", `0 0 ${w} ${h}`);
				}
				if (ban_sao.getAttribute("viewBox")) {
					// `none` chứ không phải `meet`: `meet` giữ tỉ lệ gốc nên
					// chiều cao yêu cầu chỉ là TRẦN, thực tế ra thấp hơn và
					// phần thừa thành khoảng trắng — không có lỗi nào báo, chỉ
					// là vạch thấp hơn tính toán trên một con tem vốn đã chật.
					// Kéo méo không đều VÔ HẠI với mã vạch vì thông tin nằm ở
					// bề rộng vạch, mà bề rộng thì `none` vẫn scale đúng tỉ lệ
					// ngang. (Điều này chỉ đúng khi KHÔNG in chữ dưới vạch —
					// có chữ thì `none` sẽ bóp méo chữ. Hai thiết lập đi kèm
					// nhau, đừng đổi một cái.)
					ban_sao.setAttribute("preserveAspectRatio", "none");
				}
				ban_sao.setAttribute("width", `${k.vach_rong}mm`);
				ban_sao.setAttribute("height", `${k.vach_cao}mm`);
				return new XMLSerializer().serializeToString(ban_sao);
			},
			/** SVG GỐC của JsBarcode, chưa đổi đơn vị — để ĐO, không để in.
			 *
			 * TEM VỊ TRÍ KHÔNG DÙNG HÀM NÀY. Mã vị trí Miyano luôn dài đúng
			 * 112 module (10 ký tự, xem khối chú thích đầu file), nên tem vị
			 * trí không có gì để đo: bố cục của nó là hằng số.
			 *
			 * Hàm này có mặt cho `tem_lo.js`. Số lô thì DÀI NGẮN TUỲ LÔ, nên
			 * nhãn lô phải đo số module TRƯỚC khi chọn bố cục: `ve()` đặt bề
			 * rộng SVG theo mm kèm `preserveAspectRatio="none"`, tức nó KÉO
			 * GIÃN mã cho vừa khung bất kể mã dài bao nhiêu. Nhồi một mã 13 ký
			 * tự vào 28mm ra module hẹp hơn 2 dot, và máy quét đọc ra SAI KÝ
			 * TỰ — không phải đọc hỏng. Sai lặng lẽ, trên tem đã dán lên hàng.
			 *
			 * Trả BẢN SAO rời: lần gọi `ve()`/`ve_tho()` kế tiếp thay phần tử
			 * trong `barcode_area`, nên giữ tham chiếu sống là giữ một thứ sẽ
			 * đổi dưới chân mình.
			 *
			 * (Không tự cài đặt lại phép đếm Code 128 ở JS. `vitri/ma_vach.py`
			 * đã có một bản cho phía máy chủ; hai bản cài đặt của cùng một
			 * phép tính thì một ngày nào đó `validate` cho qua một số lô mà
			 * nhãn không vẽ nổi — phát hiện ra lúc tem đã in. Đo từ chính thứ
			 * SẼ ĐƯỢC IN RA là nguồn sự thật duy nhất.)
			 */
			ve_tho(ma) {
				// `null` khi không mã hoá được — bên đo phải thấy "đo hỏng",
				// chứ không phải số module của mã TRƯỚC ĐÓ. Xem
				// `_ve_vao_control`.
				const svg = _ve_vao_control(control, ma);
				return svg ? svg.cloneNode(true) : null;
			},
			don() {
				khung.remove();
			},
		};
	}

	function esc(s) {
		return frappe.utils.escape_html(s == null ? "" : String(s));
	}

	/** Mũi tên ⇩ vẽ bằng SVG, KHÔNG bằng ký tự Unicode.
	 *
	 * `⇩` (U+21E9) không có trong Arial/Helvetica. Font thiếu glyph thì trình
	 * duyệt in ra ô tofu — mà trên nền đen của ô này, một ô tofu trắng trông
	 * gần giống một mũi tên đủ để không ai soi lại, cho tới khi cả cuộn tem đã
	 * dán lên kệ. Hình vẽ thì không phụ thuộc vào font nào có mặt ở máy in.
	 */
	const MUI_TEN_SVG = `<svg viewBox="0 0 20 20" width="100%" height="100%" preserveAspectRatio="none">
			<rect x="0" y="0" width="20" height="20" fill="#000"/>
			<path d="M8.5 3 h3 v8 h3.5 L10 17.5 L5 11 h3.5 z" fill="#fff"/>
		</svg>`;

	/** HTML của MỘT con tem. `o` là một dòng do `tem.py::danh_sach_tem` trả về.
	 *
	 * `hinh_vach` truyền từ ngoài vào (đã serialize) để một mã vạch vẽ một lần
	 * rồi dùng cho cả N bản in của cùng ô đó.
	 */
	function ve_tem(o, hinh_vach) {
		const chan = [o.kho, o.ten_o].filter(Boolean).join(" · ");
		return `<div class="tem">
	<div class="khoi">
		<div class="trai">
			<div class="dai-tren"><div class="mui-ten">${MUI_TEN_SVG}</div></div>
			<div class="dai-duoi">
				<div class="o-nho o-khu">
					<div class="tieu-de-doi"><span>KHU</span><span>DÃY</span></div>
					<div class="so-nhom">${esc(o.khu)}${esc(o.day)}</div>
				</div>
				<div class="o-nho o-khoang">
					<div class="tieu-de">KHOANG</div>
					<div class="so-nhom">${esc(o.khoang)}</div>
				</div>
			</div>
		</div>
		<div class="phai">
			<div class="tieu-de-doi"><span>TẦNG</span><span>Ô</span></div>
			<div class="hop-lon"><span class="so-lon">${esc(o.tang)}${esc(o.o)}</span></div>
		</div>
	</div>
	<div class="vach">${hinh_vach}</div>
	<div class="chan">${esc(chan)}</div>
</div>`;
	}

	/** CSS cho con tem. `cho_in = true` thì kèm `@page` và ngắt trang mỗi tem. */
	function css(k, cho_in) {
		const trang = cho_in
			? `@page { size: ${k.rong}mm ${k.cao}mm; margin: 0; }
	.tem { page-break-after: always; break-after: page; }
	/* Không có dòng này thì máy nhả thêm một con tem TRẮNG ở cuối mỗi xấp. */
	/* :last-of-type chứ KHÔNG phải :last-child — phần tử con CUỐI CÙNG của
	   <body> là thẻ <script> gọi window.print(), nên :last-child không bao giờ
	   khớp một con tem nào và cái lưới đỡ mô tả ở dòng trên CHƯA TỪNG chạy.
	   Hôm nay không lộ ra vì Chrome tự bỏ trang trắng cuối, nhưng đó là may
	   mắn của một engine cụ thể, không phải điều ta đặt ra. */
	.tem:last-of-type { page-break-after: auto; break-after: auto; }`
			: `.tem { border: 0.2mm dashed #b8b8b8; }`;

		return `
	* { box-sizing: border-box; }
	.tem {
		width: ${k.rong}mm; height: ${k.cao}mm;
		padding: ${k.le}mm;
		min-width: 0;
		display: flex; flex-direction: column;
		background: #fff; color: #000;
		font-family: Arial, Helvetica, sans-serif;
		font-variant-numeric: tabular-nums;
		/* Lưới đỡ cuối: một con tem TRÀN không chỉ xấu — trên cuộn liên tục
		   nó đẩy lệch MỌI con tem in sau nó. */
		overflow: hidden;
	}
	/* flex-shrink:0 trên .khoi và .vach — KHÔNG phải thừa.
	   .tem là flex cột, nên mặc định mọi con đều co được. Nếu một ngày khối dữ
	   liệu cao thêm (thêm dòng, đổi cỡ chữ), thứ nhường chỗ sẽ là MÃ VẠCH: nó
	   thấp dần đi mà không có lỗi nào, không có gì tràn, và trên màn hình vẫn
	   trông y hệt. Chỉ máy quét ngoài kho mới biết — mà lúc đó tem đã dán rồi.
	   Khoá cứng hai khối này lại thì một sai sót về chiều cao sẽ TRÀN, và tràn
	   thì phép đo bắt được. */
	.tem .khoi {
		height: ${k.khoi_cao}mm;
		flex: 0 0 auto;
		display: flex;
		border: 0.25mm solid #000;
	}
	/* min-width:0 ở .trai và .o-nho — chặn một lỗi IM LẶNG đã đo được.
	   Flex item mặc định là min-width:auto, nghĩa là KHÔNG co xuống dưới bề
	   rộng nội dung tối thiểu. Một bản ghi lệch chuẩn có Khoang dài hơn 2 ký
	   tự sẽ nống cột trái ra, cột phải (flex:1) co lại theo, và thứ bị cắt là
	   NHÓM SỐ LỚN — đúng con số quan trọng nhất trên tem, cắt trong im lặng vì
	   .hop-lon có overflow:hidden. Với min-width:0, chữ lệch chuẩn bị cắt
	   TRONG Ô CỦA NÓ (kèm dấu ...), không đụng tới phần còn lại. */
	.tem .trai {
		flex: 0 0 ${k.cot_khu + k.cot_khoang}mm;
		min-width: 0;
		display: flex; flex-direction: column;
	}
	.tem .dai-tren { height: ${k.mui_ten}mm; }
	.tem .mui-ten {
		width: ${k.mui_ten}mm; height: ${k.mui_ten}mm;
		line-height: 0;
	}
	.tem .dai-duoi { flex: 1; display: flex; border-top: 0.2mm solid #000; }
	.tem .o-khu { flex: 0 0 ${k.cot_khu}mm; }
	.tem .o-khoang { flex: 1; border-left: 0.2mm solid #000; }
	.tem .o-nho { min-width: 0; display: flex; flex-direction: column; justify-content: flex-end; }
	/* flex:1 chứ không phải bề ngang tính sẵn: khối có viền 0,25mm mỗi bên, nên
	   bề ngang dùng được nhỏ hơn (rong - 2*le) đúng 0,5mm. Ghi số cứng thì tràn
	   nửa milimét — đủ để cột phải bị đẩy ra ngoài mép tem.
	   (Không dùng dấu huyền trong chú thích CSS: cả khối này nằm trong một
	   template literal, một dấu huyền lạc là cắt đứt chuỗi.) */
	.tem .phai {
		flex: 1; min-width: 0;
		display: flex; flex-direction: column;
		border-left: 0.25mm solid #000;
		padding: 0.3mm;
	}
	.tem .tieu-de, .tem .tieu-de-doi {
		font-size: ${k.co_tieu_de}pt; line-height: 1.15;
		letter-spacing: 0.02em;
	}
	.tem .tieu-de { text-align: center; }
	.tem .tieu-de-doi { display: flex; justify-content: space-around; }
	.tem .so-nhom {
		font-size: ${k.co_nhom}pt; font-weight: 700; line-height: 1.05;
		text-align: center;
		/* Mã lệch chuẩn (bản ghi cũ) có thể dài hơn 2 ký tự. Cắt chứ không
		   xuống dòng: xuống dòng thì khối cao thêm và đẩy mã vạch ra khỏi tem.
		   Cắt bằng ellipsis chứ không cắt trần: "1B0" trông y như một mã thật
		   và người ta gõ nhầm nó, còn "1B…" thì nhìn là biết chưa đọc hết. */
		white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
	}
	.tem .hop-lon {
		flex: 1;
		border: 0.45mm solid #000;
		display: flex; align-items: center; justify-content: center;
		overflow: hidden;
	}
	.tem .so-lon {
		font-size: ${k.co_lon}pt; font-weight: 700; line-height: 1;
		white-space: nowrap;
	}
	.tem .vach {
		margin-top: ${k.gap}mm;
		height: ${k.vach_cao}mm;
		flex: 0 0 auto;
		line-height: 0;
		text-align: center;      /* vùng trắng chia đều hai bên — xem đầu file */
	}
	.tem .chan {
		flex: 1;
		font-size: ${k.co_chan}pt; line-height: 1.2;
		text-align: center;
		white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
	}
	${trang}
`;
	}

	/** Ô xem trước trên màn hình: tem vẽ ĐÚNG mm thật rồi phóng to bằng
	 * `transform`.
	 *
	 * Phóng bằng transform chứ không phải bằng cách nống các con số mm lên:
	 * nống số thì cái nhìn thấy không còn là cái sẽ in ra, và ô xem trước mất
	 * sạch ý nghĩa. Trình duyệt quy 1mm = 96/25.4 px, nên tem 45mm chỉ ra ~170px
	 * — đúng bằng con tem thật, và nhỏ đến mức không soi được chữ.
	 */
	function ve_xem_truoc($dich, o, ma_kho, he_so) {
		const k = kho_giay(ma_kho);
		he_so = he_so || 2.4;
		const may = may_ve_ma_vach();
		const html = ve_tem(o, may.ve(o.ma_o, k));
		may.don();

		$dich.empty();
		$(`<div class="vi-tri-kho-xem-tem" style="
				width:${k.rong * he_so}mm; height:${k.cao * he_so}mm; overflow:hidden;">
			<style>${css(k, false)}</style>
			<div style="transform:scale(${he_so}); transform-origin:top left;">${html}</div>
		</div>`).appendTo($dich);
	}

	/** Dựng và mở cửa sổ in cho cả xấp tem. Trả `false` nếu bị chặn pop-up. */
	function in_xap(danh_sach, so_ban, ma_kho) {
		const k = kho_giay(ma_kho);
		const may = may_ve_ma_vach();
		const tem = [];

		danh_sach.forEach(function (o) {
			// Vẽ MỘT lần cho mỗi ô rồi nhân bản chuỗi: 200 ô × 5 bản mà vẽ lại
			// từng cái là 1000 lượt dựng SVG, cửa sổ in đứng hình trước khi kịp
			// gọi print().
			const hinh = may.ve(o.ma_o, k);
			const mot = ve_tem(o, hinh);
			for (let i = 0; i < so_ban; i++) tem.push(mot);
		});
		may.don();

		const trang = `<!doctype html><html><head><meta charset="utf-8">
<title>${esc(__("Tem vị trí"))} ${esc(k.ten)}</title>
<style>${css(k, true)}
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

		const cua_so = window.open("", "_blank", "width=420,height=560");
		if (!cua_so) return false;
		cua_so.document.write(trang);
		cua_so.document.close();
		return true;
	}

	return { KHO_GIAY, KHO_MAC_DINH, kho_giay, may_ve_ma_vach, ve_tem, css, ve_xem_truoc, in_xap };
})();
