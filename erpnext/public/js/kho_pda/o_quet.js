// Ô quét dùng chung cho các màn của app `/kho`.
//
// Chép BA HÀNH VI đã học từ máy thật trong ô quét gốc của module vị trí kho
// (`erpnext/public/js/warehouse_operations/o_quet.js`, chú thích dòng 1–30) — nơi
// đó ghi lại vì sao mỗi điều tồn tại, không lặp lại ở đây. CỐ TÌNH khác bản gốc ở
// bốn chỗ, không chỉ hai: tên namespace (`erpnext.kho_pda` — vỏ này không phải
// Desk); BỎ nút camera (`quet_camera()` bản gốc dùng lớp quét-bằng-máy-ảnh của
// Desk, tên đầy đủ `ui.Scanner` trên namespace `frappe`, chỉ có
// trong `desk.js`, không có trong `frappe-web.bundle.js` mà trang website nạp —
// thêm máy ảnh là việc của spec §9, ngoài phạm vi Task 1); viết cứng mã màu thay
// vì biến CSS của Frappe (`--fg-color`...) và bỏ `:focus-within` mà bản gốc dùng —
// vỏ `/kho` không tải bundle CSS của Desk nơi những biến/luật đó được định nghĩa
// cho khung `.oq` (xem chú thích đầu `kho_pda.bundle.scss`); và thêm cơ chế khoá
// khi có hộp thoại mở (`_ap_dung_khoa`, dưới) mà bản gốc không cần vì Desk có lớp
// hộp thoại chuẩn (`ui.Dialog` trên namespace `frappe`) tự quản lý focus modal,
// còn `hop_thoai.js` ở đây thì không.
// Hai bản SẼ trôi khỏi nhau (bản gốc đã tự cảnh báo điều này ở chú thích của nó) —
// sửa một hành vi súng quét thì nhớ soát cả hai file.
//
// BA ĐIỀU RIÊNG CỦA PDA (thử trên Chrome giả lập màn hình nhỏ; CHƯA thử trên PDA
// thật của kho):
// 1. Súng quét gõ vào ô đang focus như một bàn phím rồi (thường) gửi Enter. Nên
//    ô quét phải LUÔN giữ focus — sau mỗi lần quét, sau mỗi lần chạm vào chỗ
//    trống, sau khi quay lại trang.
// 2. Giữ focus trên màn hình cảm ứng thì bàn phím ảo bật lên che nửa màn hình.
//    `inputmode="none"` giữ focus mà không gọi bàn phím; nút ⌨ chuyển sang gõ
//    tay khi tem mờ không quét được.
// 3. Một số PDA cài súng quét KHÔNG gửi Enter. Ở chế độ quét (bàn phím ảo đang
//    tắt) thì không ai gõ tay được vào ô, nên chữ xuất hiện trong ô chỉ có thể là
//    súng quét — ngừng nhận ký tự `TU_GUI_SAU_MS` là coi như quét xong.

frappe.provide("erpnext.kho_pda");

const TU_GUI_SAU_MS = 250;

// Vẽ tay: bộ biểu tượng Frappe (`icon-keyboard`) tô cứng màu #192734 nên gần như
// biến mất ở chế độ tối — cùng lý do bản gốc đã tự vẽ SVG này thay vì dùng icon set.
const HINH_BAN_PHIM = `<svg class="icon icon-md" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><rect x="2.5" y="6" width="19" height="12" rx="2"/><path d="M6 10h.01M9 10h.01M12 10h.01M15 10h.01M18 10h.01M7.5 14h9"/></svg>`;

// Đếm để mỗi `OQuet` có một namespace sự kiện RIÊNG (`.oqN`) — `huy()` cần gỡ
// đúng handler của CHÍNH NÓ trên `$vung` (một phần tử KHÔNG do `OQuet` sở hữu,
// sống lâu hơn nó qua nhiều lượt chuyển màn) mà không đụng tới listener của
// những `OQuet` khác từng gắn lên cùng phần tử đó trước hoặc sau nó.
let _dem_oq = 0;

erpnext.kho_pda.OQuet = class OQuet {
	constructor({ cha, vung, goi_y, placeholder, khi_quet }) {
		this.khi_quet = khi_quet;
		this.goi_y_mac_dinh = goi_y || "";
		this.go_tay = false;
		this.khoa = false;
		this._ns = ".oq" + ++_dem_oq;

		this.$goc = $(`
			<div class="oq">
				<div class="oq-o">
					<span class="oq-bieu-tuong">${frappe.utils.icon("scan", "md")}</span>
					<input type="text" class="oq-nhap" inputmode="none"
						autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false"
						enterkeyhint="search" placeholder="${frappe.utils.escape_html(placeholder || "")}" />
					<button type="button" class="oq-nut oq-nut-ban-phim" title="${__("Gõ tay")}">${HINH_BAN_PHIM}</button>
				</div>
				<div class="oq-goi-y"></div>
			</div>
		`).appendTo(cha);

		this.$nhap = this.$goc.find(".oq-nhap");
		this.$goi_y = this.$goc.find(".oq-goi-y");
		this.dat_goi_y(this.goi_y_mac_dinh);
		this.gan_su_kien(vung || cha);

		// `hop_thoai.js` giữ MỘT biến đếm dùng chung (`so_hop_dang_mo`) và phát một
		// sự kiện toàn cục mỗi lần biến đó đổi — nghe qua `document` (không qua tham
		// chiếu trực tiếp tới hộp) vì hộp có thể mở từ một nút KHÔNG giữ tham chiếu
		// tới `OQuet` đang sống trên màn. Súng quét gửi ký tự tới PHẦN TỬ ĐANG FOCUS
		// bất kể hộp che nó về mặt hình ảnh hay không — lớp phủ CSS không chặn được
		// sự kiện bàn phím — nên phải chủ động khoá + bỏ focus, không thể trông chờ
		// z-index (đúng họ sự cố 17/09/2026: một hộp xác nhận DUYỆT NHẦM phiếu vì
		// súng quét vẫn "nói chuyện" được với màn phía sau nó).
		//
		// MỘT sự kiện, TỰ TÍNH LẠI trạng thái từ biến đếm mỗi lần nhận — không phải
		// một cặp sự kiện "mở"/"đóng" mà mỗi `OQuet` tự nhớ thành true/false (đúng lỗ
		// hổng N1, soát xét vòng 2: cờ nhớ riêng lệch nhau khi có HAI hộp lồng nhau —
		// đóng hộp trong cùng thì cờ báo "đã đóng" dù hộp ngoài vẫn còn). Và GỌI NGAY
		// một lần lúc dựng — sửa N2: một `OQuet` có thể ra đời SAU khi hộp đã mở
		// (`goi()` nền trả 401 giữa lúc một hộp đang mở → `di("the")` dựng `OQuet`
		// mới cho màn thẻ), lúc đó không có sự kiện TƯƠNG LAI nào báo cho nó biết.
		this._khi_so_hop_doi = () => this._ap_dung_khoa();
		document.addEventListener("kho-hop-doi", this._khi_so_hop_doi);
		this._ap_dung_khoa();
	}

	gan_su_kien($vung) {
		this.$vung = $($vung);
		// Ô quét NẰM NGOÀI luật "không nghe phím" của `hop_thoai.js`: chính súng
		// quét cần sự kiện này để biết lúc nào một lượt bắn kết thúc (điều 1 ở
		// trên). `test_hop_thoai_khong_bat_phim_nao` chỉ đọc `hop_thoai.js`, không
		// đọc file này — không phải một khe hở, mà đúng phạm vi bài test đó.
		this.$nhap.on("keydown" + this._ns, (ev) => {
			// Tab: vài dòng PDA cài hậu tố Tab thay cho Enter.
			if (ev.key !== "Enter" && ev.key !== "Tab") return;
			ev.preventDefault();
			this.gui();
		});

		this.$nhap.on("input" + this._ns, () => {
			clearTimeout(this.hen_gui);
			if (this.go_tay) return;
			this.hen_gui = setTimeout(() => this.gui(), TU_GUI_SAU_MS);
		});

		this.$goc.find(".oq-nut-ban-phim").on("click" + this._ns, () => this.doi_ban_phim());

		// Chạm vào chỗ trống thì trả focus cho ô quét. KHÔNG cướp focus khỏi
		// liên kết, nút, ô nhập khác (số lượng), hay chữ đang bôi đen để chép.
		// Gắn có namespace (`this._ns`) vì `$vung` (thường là `$than` của vo.js)
		// KHÔNG bị gỡ khỏi DOM khi rời màn — `vo.js` chỉ `.empty()` nó, mà `.empty()`
		// gỡ handler của CON chứ không gỡ handler gắn trên CHÍNH `$vung` — `huy()`
		// bên dưới phải tự `.off(this._ns)` mới sạch.
		this.$vung.on("click" + this._ns, (ev) => {
			if ($(ev.target).closest("a, button, input, select, textarea, label, [role=button]").length) return;
			if (window.getSelection && String(window.getSelection())) return;
			this.giu_focus();
		});
	}

	/** Tính lại khoá từ `erpnext.kho_pda.so_hop_dang_mo` — KHOÁ khi số đó > 0 (còn
	 * ít nhất một hộp sống, kể cả khi có nhiều hộp lồng nhau), MỞ khi về đúng 0.
	 * Ô quét mất focus và KHÔNG được tự lấy lại trong lúc khoá, kể cả khi
	 * `giu_focus()` bị gọi (chạm chỗ trống vẫn bắn `click`, dù lớp phủ của hộp che
	 * gần hết màn). Trả `disabled` thật lên DOM (không chỉ cờ nội bộ) để súng quét
	 * không thể gõ ký tự vào ngay cả khi có cách nào đó giành lại được focus ngoài
	 * `giu_focus()`. */
	_ap_dung_khoa() {
		const khoa_moi = erpnext.kho_pda.so_hop_dang_mo > 0;
		// Chỉ tự lấy lại focus ĐÚNG LÚC vừa chuyển từ khoá sang mở — không phải mỗi
		// lần "không khoá" (kể cả lúc DỰNG, khi `this.khoa` còn `false` mặc định và
		// chưa hộp nào từng mở). Gọi `giu_focus()` vô điều kiện mỗi lần "mở khoá"
		// từng là một phần của lỗ hổng N1: nó chạy cả khi thật ra vẫn còn hộp khác
		// (cờ boolean cũ không phân biệt được "vừa mở khoá thật" với "vốn dĩ chưa
		// từng khoá"), và có thể kéo focus lên một `OQuet` không phải ô người dùng
		// đang thao tác khi nhiều `OQuet` cùng sống một lúc.
		const vua_mo_khoa = this.khoa && !khoa_moi;
		this.khoa = khoa_moi;
		this.$nhap.prop("disabled", khoa_moi);
		if (khoa_moi) {
			this.$nhap.blur();
		} else if (vua_mo_khoa) {
			this.giu_focus();
		}
	}

	giu_focus() {
		if (this.khoa) return;
		// Không kéo trang lên đầu mỗi lần focus — người dùng đang đọc giữa thẻ.
		this.$nhap.length && this.$nhap[0].focus({ preventScroll: true });
	}

	/** Gỡ mọi thứ `OQuet` đã gắn RA NGOÀI chính DOM của nó — phần `$goc.remove()`
	 * (gọi ở cuối) tự dọn handler trên `$goc` và con cháu, nhưng KHÔNG chạm tới:
	 * listener trên `document` (sống mãi nếu không tự gỡ — mở/đóng hộp ở màn KHÁC
	 * sau này vẫn gọi vào một `OQuet` đã rời màn từ lâu), handler trên `$vung`
	 * (không phải con của `$goc`), và hẹn giờ tự gửi đang chờ (nổ sau khi rời màn
	 * thì đọc một ô đã tách khỏi DOM, gọi `khi_quet` của màn đã rời — một lệnh gửi
	 * lên máy chủ từ màn người dùng không còn đứng đó nữa). Màn nào dựng `OQuet`
	 * phải gọi hàm này trong `roi()` — không có bước này thì `roi()` không dọn
	 * được gì cả, dù viết đúng cách brief mô tả. */
	huy() {
		clearTimeout(this.hen_gui);
		document.removeEventListener("kho-hop-doi", this._khi_so_hop_doi);
		this.$vung && this.$vung.off(this._ns);
		this.$goc.remove();
	}

	dat_goi_y(chu, kieu) {
		this.$goi_y.text(this.go_tay ? __("Gõ mã rồi bấm Enter") : chu || this.goi_y_mac_dinh);
		this.$goc.toggleClass("nhan-manh", kieu === "nhan-manh");
		this.chu_goi_y = chu;
		this.kieu_goi_y = kieu;
	}

	doi_ban_phim() {
		this.go_tay = !this.go_tay;
		clearTimeout(this.hen_gui);
		this.$nhap.attr("inputmode", this.go_tay ? "text" : "none");
		this.$goc.find(".oq-nut-ban-phim").toggleClass("dang-bat", this.go_tay);
		this.dat_goi_y(this.chu_goi_y, this.kieu_goi_y);
		// Đổi `inputmode` trên một ô ĐANG focus thì Android không mở bàn phím —
		// phải bỏ focus rồi focus lại.
		this.$nhap.blur();
		setTimeout(() => this.giu_focus(), 50);
	}

	gui() {
		clearTimeout(this.hen_gui);
		// Phòng thủ thêm lớp thứ hai: về lý thuyết `disabled` (trong `_ap_dung_khoa`) đã
		// chặn `input`/`keydown` không bao giờ tới tay ta lúc khoá (trình duyệt
		// không phát sự kiện bàn phím cho phần tử `disabled`), nhưng `gui()` là API
		// nội bộ — không dựa hẳn vào việc không ai gọi thẳng nó trong lúc khoá.
		if (this.khoa) return;
		const ma = String(this.$nhap.val() || "").trim();
		this.$nhap.val("");
		if (ma) this.khi_quet(ma);
	}
};
