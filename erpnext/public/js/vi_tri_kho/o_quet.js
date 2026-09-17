// Ô quét dùng chung cho các trang PDA của module vị trí kho
// (`quet-ma-tra-cuu`, `xep-hang-pda`).
//
// Tách ra từ trang quét mã tra cứu ngày 17/09/2026 khi làm trang xếp hàng: phần
// giữ focus / tắt bàn phím ảo / tự gửi khi súng quét không có Enter là phần tinh
// vi nhất của cả hai trang, và hai bản chép sẽ trôi khỏi nhau ngay lần sửa đầu.
//
// BA ĐIỀU RIÊNG CỦA PDA (thử trên Chrome giả lập màn hình nhỏ; CHƯA thử trên PDA
// thật của kho):
//
// 1. Súng quét gõ vào ô đang focus như một bàn phím rồi (thường) gửi Enter. Nên
//    ô quét phải LUÔN giữ focus — sau mỗi lần quét, sau mỗi lần chạm vào chỗ
//    trống, sau khi quay lại trang.
// 2. Giữ focus trên màn hình cảm ứng thì bàn phím ảo bật lên che nửa màn hình.
//    `inputmode="none"` giữ focus mà không gọi bàn phím; nút ⌨ chuyển sang gõ
//    tay khi tem mờ không quét được.
// 3. Một số PDA cài súng quét KHÔNG gửi Enter. Ở chế độ quét (bàn phím ảo đang
//    tắt) thì không ai gõ tay được vào ô, nên chữ xuất hiện trong ô chỉ có thể là
//    súng quét — ngừng nhận ký tự `TU_GUI_SAU_MS` là coi như quét xong.
//
// Dùng:
//   const o = new erpnext.vi_tri_kho.OQuet({
//     cha: $noi_gan,            // nơi gắn ô quét
//     vung: $ca_trang,          // chạm chỗ trống trong vùng này thì trả focus
//     goi_y: "Quét tem lô…",    // dòng chữ dưới ô
//     placeholder: "…",
//     khi_quet: (ma) => {...},  // nhận chuỗi đã trim, không rỗng
//   });
//   o.giu_focus(); o.dat_goi_y("…", "nhan-manh");

frappe.provide("erpnext.vi_tri_kho");

(function () {
	const TU_GUI_SAU_MS = 250;

	const HINH_BAN_PHIM = `<svg class="icon icon-md" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><rect x="2.5" y="6" width="19" height="12" rx="2"/><path d="M6 10h.01M9 10h.01M12 10h.01M15 10h.01M18 10h.01M7.5 14h9"/></svg>`;
	const HINH_MAY_ANH = `<svg class="icon icon-md" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8h3l2-2.5h6L17 8h3v11H4z"/><circle cx="12" cy="13" r="3.5"/></svg>`;

	erpnext.vi_tri_kho.OQuet = class OQuet {
		constructor({ cha, vung, goi_y, placeholder, khi_quet }) {
			this.khi_quet = khi_quet;
			this.goi_y_mac_dinh = goi_y || "";
			this.go_tay = false;

			// Hai biểu tượng vẽ tay: `icon-keyboard` của Frappe tô cứng màu #192734
			// nên gần như biến mất ở chế độ tối; bộ biểu tượng không có máy ảnh.
			this.$goc = $(`
				<div class="oq">
					<div class="oq-o">
						<span class="oq-bieu-tuong">${frappe.utils.icon("scan", "md")}</span>
						<input type="text" class="oq-nhap" inputmode="none"
							autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false"
							enterkeyhint="search" placeholder="${frappe.utils.escape_html(placeholder || "")}" />
						<button type="button" class="oq-nut oq-nut-ban-phim" title="${__("Gõ tay")}">${HINH_BAN_PHIM}</button>
						<button type="button" class="oq-nut oq-nut-camera" title="${__("Quét bằng camera")}">${HINH_MAY_ANH}</button>
					</div>
					<div class="oq-goi-y"></div>
				</div>
			`).appendTo(cha);

			this.$nhap = this.$goc.find(".oq-nhap");
			this.$goi_y = this.$goc.find(".oq-goi-y");
			this.dat_goi_y(this.goi_y_mac_dinh);
			this.gan_su_kien(vung || cha);
		}

		gan_su_kien($vung) {
			this.$nhap.on("keydown", (ev) => {
				// Tab: vài dòng PDA cài hậu tố Tab thay cho Enter.
				if (ev.key !== "Enter" && ev.key !== "Tab") return;
				ev.preventDefault();
				this.gui();
			});

			this.$nhap.on("input", () => {
				clearTimeout(this.hen_gui);
				if (this.go_tay) return;
				this.hen_gui = setTimeout(() => this.gui(), TU_GUI_SAU_MS);
			});

			this.$goc.find(".oq-nut-ban-phim").on("click", () => this.doi_ban_phim());
			this.$goc.find(".oq-nut-camera").on("click", () => this.quet_camera());

			// Chạm vào chỗ trống thì trả focus cho ô quét. KHÔNG cướp focus khỏi
			// liên kết, nút, ô nhập khác (số lượng), hay chữ đang bôi đen để chép.
			$($vung).on("click", (ev) => {
				if ($(ev.target).closest("a, button, input, select, textarea, label, [role=button]").length) return;
				if (window.getSelection && String(window.getSelection())) return;
				this.giu_focus();
			});
		}

		giu_focus() {
			// Không kéo trang lên đầu mỗi lần focus — người dùng đang đọc giữa thẻ.
			this.$nhap.length && this.$nhap[0].focus({ preventScroll: true });
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

		quet_camera() {
			new frappe.ui.Scanner({
				dialog: true,
				multiple: false,
				on_scan: (data) => {
					const ma = data && data.result && data.result.text;
					if (ma) this.khi_quet(String(ma).trim());
				},
			});
		}

		gui() {
			clearTimeout(this.hen_gui);
			const ma = String(this.$nhap.val() || "").trim();
			this.$nhap.val("");
			if (ma) this.khi_quet(ma);
		}
	};
})();
