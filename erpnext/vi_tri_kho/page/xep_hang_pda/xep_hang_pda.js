// Trang "Xếp hàng vào ô" — PDA của thủ kho.
//
// Chủ đầu tư, 17/09/2026: "giao diện xếp hàng cũng là pda … quét mã lô thì hiển
// thị ra mặt hàng và thực hiện xác nhận xếp, có thể xếp nhiều hàng trên 1 phiếu
// xếp Location Transfer". Chốt cùng ngày: xác nhận bằng QUÉT TEM Ô trên kệ (hệ
// biết thủ kho thật sự đặt hàng ở đâu, không phải bấm "đồng ý" theo gợi ý), số
// lượng mặc định cả phần đang chờ ở ô nguồn và sửa được, và quét lô đã nằm ở ô
// khác thì thành dòng CHUYỂN Ô.
//
// Hai bước lặp lại:  ① quét tem LÔ  →  ② quét tem Ô  →  dòng lưu ngay lên phiếu nháp.
//
// Máy chủ là `vitri/xep.py` (khối "Xếp hàng trên PDA") — lý do dòng lưu ngay, phiếu
// nháp theo từng người, và phép kiểm dòng nằm ở controller đều ghi ở đó. Trang
// này KHÔNG tự kiểm ô nhóm / nhánh ngừng dùng / sai kho: gửi lên và để câu báo của
// máy chủ hiện ra, một chỗ duy nhất giữ luật.
//
// Bọc IIFE: script trang Frappe chạy ở phạm vi toàn cục — xem `quet_ma_tra_cuu.js`.
(function () {
	const O_QUET = ["/assets/erpnext/js/vi_tri_kho/o_quet.js", "/assets/erpnext/js/vi_tri_kho/o_quet.css"];
	const API = "erpnext.vi_tri_kho.vitri.xep.";

	frappe.pages["xep-hang-pda"].on_page_load = function (wrapper) {
		const page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Xếp hàng vào ô"),
			single_column: true,
		});
		frappe.require(O_QUET, () => {
			wrapper.xep = new XepHangPda(page);
		});
	};

	frappe.pages["xep-hang-pda"].on_page_show = function (wrapper) {
		// Quay lại trang (vd. vừa mở phiếu trên form rồi bấm Back): nạp lại phiếu —
		// có thể đã bị sửa hay duyệt ở nơi khác.
		if (wrapper.xep) wrapper.xep.nap_lai();
	};

	class XepHangPda {
		constructor(page) {
			this.page = page;
			this.kho = null;
			this.kho_ds = [];
			this.phieu = null;
			// Lô đang chờ quét tem ô. `null` = đang ở bước ① (chờ quét lô).
			this.cho = null;
			this.dang_gui = false;
			this.dung();
			this.nap_lai();
		}

		dung() {
			this.$goc = $(`
				<div class="xh">
					<div class="xh-dau-trang"></div>
					<div class="xh-cho-o-quet"></div>
					<div class="xh-thong-bao"></div>
					<div class="xh-lo-dang-cho"></div>
					<div class="xh-danh-sach"></div>
					<div class="xh-chan-trang"></div>
				</div>
			`).appendTo(this.page.main);

			this.o_quet = new erpnext.vi_tri_kho.OQuet({
				cha: this.$goc.find(".xh-cho-o-quet"),
				vung: this.$goc,
				placeholder: __("Quét tem…"),
				goi_y: "",
				khi_quet: (ma) => this.quet(ma),
			});

			this.$goc.on("click", ".xh-chon-kho", (ev) => this.chon_kho($(ev.currentTarget).attr("data-kho")));
			this.$goc.on("click", ".xh-nguon", (ev) => this.chon_nguon($(ev.currentTarget).attr("data-o")));
			this.$goc.on("click", ".xh-bo-lo", () => this.bo_lo());
			this.$goc.on("click", ".xh-xac-nhan-o-khac", () => this.xac_nhan_o_khac());
			this.$goc.on("click", ".xh-xoa-dong", (ev) => this.xoa_dong($(ev.currentTarget).attr("data-dong")));
			this.$goc.on("click", ".xh-hoan-tat", () => this.hoan_tat());
			this.$goc.on("click", ".xh-cong-tru", (ev) => this.cong_tru(Number($(ev.currentTarget).attr("data-buoc"))));
			this.$goc.on("input change", ".xh-so-luong", (ev) => {
				if (this.cho) this.cho.so_luong = flt(ev.currentTarget.value);
			});
			// Enter trên ô số lượng: xong sửa số, trả focus cho súng quét.
			this.$goc.on("keydown", ".xh-so-luong", (ev) => {
				if (ev.key !== "Enter") return;
				ev.preventDefault();
				ev.currentTarget.blur();
				this.o_quet.giu_focus();
			});
		}

		// ------------------------------------------------------------ trạng thái

		nap_lai() {
			return frappe.xcall(API + "phieu_xep_dang_lam", { kho: this.kho }).then((r) => {
				this.kho_ds = r.kho_ds || [];
				this.kho = r.kho;
				this.phieu = r.phieu;
				this.ve();
				this.o_quet.giu_focus();
			});
		}

		chon_kho(kho) {
			this.cho = null;
			this.bao();
			if (!kho) {
				// Nút "Đổi": về màn chọn kho. KHÔNG nạp lại — không truyền kho thì máy
				// chủ tự chọn lại đúng kho vừa rời (kho của phiếu nháp gần nhất).
				this.kho = null;
				this.phieu = null;
				this.ve();
				return;
			}
			this.kho = kho;
			this.nap_lai();
		}

		quet(ma) {
			if (!this.kho) {
				this.bao(__("Chọn kho trước khi quét."), "cam");
				return;
			}
			if (this.dang_gui) return;
			frappe.xcall(API + "quet_de_xep", { kho: this.kho, ma: ma }).then((d) => {
				d = d || { loai: null };
				if (d.loai === "lo") return this.nhan_lo(d);
				if (d.loai === "o") return this.nhan_o(d);
				rung([80, 60, 80]);
				if (d.loai === "can_quet_lo") {
					return this.bao(
						__("{0} có quản lý lô — quét tem LÔ trên thùng, không quét mã hàng.", [
							e(d.ten_hang || d.vat_tu),
						]),
						"cam"
					);
				}
				this.bao(__("Không nhận ra mã <b>{0}</b>.", [e(ma)]), "xam");
			});
		}

		nhan_lo(d) {
			if (!d.nguon.length) {
				rung([80, 60, 80]);
				this.bao(
					__("Lô <b>{0}</b> không còn hàng nào để xếp ở kho này (hoặc đã lên hết phiếu).", [
						e(d.so_lo || d.vat_tu),
					]),
					"cam"
				);
				return;
			}
			rung([40]);
			// Quét lô mới khi đang chờ ô cho lô cũ: THAY lô cũ. Chưa có gì được ghi,
			// và đó là điều người cầm súng quét muốn — họ vừa đổi ý cầm thùng khác.
			this.cho = { ...d, tu_o: d.tu_o_mac_dinh, so_luong: 0 };
			this.dat_so_luong_theo_nguon();
			this.bao();
			this.ve();
		}

		nhan_o(o) {
			if (!this.cho) {
				rung([80, 60, 80]);
				this.bao(
					__("Đây là tem vị trí <b>{0}</b>. Quét tem LÔ trước, rồi mới quét tem ô.", [
						e(o.ma_in_nhan || o.ma_o),
					]),
					"cam"
				);
				return;
			}
			if (!this.cho.tu_o) {
				rung([80, 60, 80]);
				this.bao(__("Lô này đang nằm ở nhiều ô — chạm chọn ô LẤY hàng ra trước."), "cam");
				return;
			}
			if (!(flt(this.cho.so_luong) > 0)) {
				this.bao(__("Số lượng phải lớn hơn 0."), "cam");
				return;
			}
			// Ô khác gợi ý: xác nhận bằng QUÉT LẠI đúng tem ô đó (hoặc chạm nút trên
			// thẻ) — KHÔNG bằng hộp thoại. Xem `hoi()` ở cuối file: một hộp
			// `frappe.confirm` đang mở thì phím Enter của lần quét kế tiếp bấm "Có".
			const goi_y = this.cho.goi_y && this.cho.goi_y.den_o;
			const da_xac_nhan = this.cho.o_khac && this.cho.o_khac.ma_o === o.ma_o;
			if (goi_y && o.ma_o !== goi_y && !da_xac_nhan) {
				rung([80]);
				this.cho.o_khac = o;
				this.ve();
				return;
			}
			this.them_dong(o);
		}

		xac_nhan_o_khac() {
			if (this.cho && this.cho.o_khac) this.them_dong(this.cho.o_khac);
		}

		them_dong(o) {
			const c = this.cho;
			this.dang_gui = true;
			frappe
				.xcall(API + "them_dong_xep", {
					kho: this.kho,
					vat_tu: c.vat_tu,
					so_lo: c.so_lo,
					tu_o: c.tu_o,
					den_o: o.ma_o,
					so_luong: c.so_luong,
				})
				.then((phieu) => {
					rung([40, 40, 40]);
					this.phieu = phieu;
					this.cho = null;
					this.bao(
						__("Đã xếp <b>{0}</b> {1} {2} → <b>{3}</b>", [
							so(c.so_luong),
							e(c.don_vi || ""),
							e(c.so_lo || c.ten_hang),
							e(o.ma_in_nhan || o.ma_o),
						]),
						"xanh"
					);
					this.ve();
				})
				.catch(() => {
					// Câu báo của máy chủ (ô nhóm, ngừng dùng, không đủ hàng…) đã hiện
					// qua `frappe.xcall`. Giữ nguyên lô đang chờ để quét lại ô khác.
					rung([80, 60, 80]);
				})
				.finally(() => {
					this.dang_gui = false;
					this.o_quet.giu_focus();
				});
		}

		bo_lo() {
			this.cho = null;
			this.bao();
			this.ve();
			this.o_quet.giu_focus();
		}

		chon_nguon(o) {
			if (!this.cho) return;
			this.cho.tu_o = o;
			this.dat_so_luong_theo_nguon();
			this.ve();
			this.o_quet.giu_focus();
		}

		// Mặc định số lượng = phần còn xếp được ở ĐÚNG ô nguồn đang chọn — không phải
		// tổng của lô: một lô nằm ở hai ô thì chỉ lấy được từ một ô mỗi dòng.
		dat_so_luong_theo_nguon() {
			const n = this.nguon_dang_chon();
			this.cho.so_luong = n ? flt(n.con_xep_duoc) : 0;
		}

		nguon_dang_chon() {
			return this.cho && (this.cho.nguon || []).find((n) => n.o === this.cho.tu_o);
		}

		cong_tru(buoc) {
			if (!this.cho) return;
			const n = this.nguon_dang_chon();
			const toi_da = n ? flt(n.con_xep_duoc) : Infinity;
			this.cho.so_luong = Math.min(toi_da, Math.max(0, flt(this.cho.so_luong) + buoc));
			this.$goc.find(".xh-so-luong").val(this.cho.so_luong);
		}

		xoa_dong(ten_dong) {
			const d = ((this.phieu && this.phieu.dong) || []).find((x) => x.name === ten_dong);
			if (!d) return;
			hoi({
				noi_dung: __("Bỏ dòng <b>{0}</b> · {1} → {2} khỏi phiếu?", [
					e(d.so_lo || d.ten_hang),
					so(d.so_luong),
					e(d.den_o),
				]),
				nhan: __("Bỏ dòng"),
				khi_dong_y: () =>
					frappe
						.xcall(API + "xoa_dong_xep", { phieu: this.phieu.name, dong: ten_dong })
						.then((phieu) => {
							this.phieu = phieu;
							this.bao(__("Đã bỏ một dòng."), "xam");
							this.ve();
						})
						.finally(() => this.o_quet.giu_focus()),
				khi_dong: () => this.o_quet.giu_focus(),
			});
		}

		hoan_tat() {
			if (!this.phieu || !this.phieu.dong.length) return;
			const ten = this.phieu.name;
			const so_dong = this.phieu.dong.length;
			hoi({
				noi_dung: __("Ghi phiếu <b>{0}</b> ({1} dòng) vào sổ vị trí? Sau khi ghi, tồn theo ô đổi ngay.", [
					e(ten),
					so_dong,
				]),
				nhan: __("Ghi phiếu"),
				khi_dong_y: () => {
					this.dang_gui = true;
					frappe
						.xcall(API + "duyet_phieu_xep", { phieu: ten })
						.then(() => {
							rung([40, 40, 40]);
							this.phieu = null;
							this.cho = null;
							this.bao(
								__("Đã ghi phiếu <a href='{0}'>{1}</a> — {2} dòng. Quét tem lô để bắt đầu phiếu mới.", [
									`/app/location-transfer/${encodeURIComponent(ten)}`,
									e(ten),
									so_dong,
								]),
								"xanh"
							);
							this.ve();
						})
						.catch(() => {
							// Máy chủ đã nói dòng/ô nào sai; phiếu nháp còn nguyên
							// (`duyet_phieu_xep` rollback). Nạp lại để thấy đúng trạng thái.
							rung([80, 60, 80]);
							this.nap_lai();
						})
						.finally(() => {
							this.dang_gui = false;
							this.o_quet.giu_focus();
						});
				},
				khi_dong: () => this.o_quet.giu_focus(),
			});
		}

		// ------------------------------------------------------------------ vẽ

		bao(html, muc) {
			const $tb = this.$goc.find(".xh-thong-bao");
			if (!html) return $tb.empty();
			$tb.html(`<div class="xh-bao muc-${muc || "xam"}">${html}</div>`);
		}

		ve() {
			this.ve_dau_trang();
			this.ve_lo_dang_cho();
			this.ve_danh_sach();
			this.ve_chan_trang();
			if (!this.kho) {
				this.o_quet.dat_goi_y(__("Chọn kho để bắt đầu"));
			} else if (this.cho && this.cho.o_khac) {
				this.o_quet.dat_goi_y(
					__("Quét LẠI tem {0} để xác nhận", [this.cho.o_khac.ma_in_nhan || this.cho.o_khac.ma_o]),
					"nhan-manh"
				);
			} else if (this.cho) {
				this.o_quet.dat_goi_y(
					__("② Quét tem Ô trên kệ để xếp {0}", [this.cho.so_lo || this.cho.ten_hang]),
					"nhan-manh"
				);
			} else {
				this.o_quet.dat_goi_y(__("① Quét tem LÔ cần xếp"));
			}
		}

		ve_dau_trang() {
			const $d = this.$goc.find(".xh-dau-trang");
			if (!this.kho_ds.length) {
				$d.html(`<div class="xh-bao muc-cam">${__("Chưa kho nào bật quản lý vị trí.")}</div>`);
				return;
			}
			if (!this.kho) {
				$d.html(`
					<div class="xh-tieu-de-muc">${__("Chọn kho")}</div>
					<div class="xh-chon-kho-ds">
						${this.kho_ds
							.map((k) => `<button type="button" class="xh-chon-kho" data-kho="${e(k)}">${e(k)}</button>`)
							.join("")}
					</div>`);
				return;
			}
			const doi_kho =
				this.kho_ds.length > 1 && !this.cho
					? `<button type="button" class="xh-lien-ket-nho xh-chon-kho" data-kho="">${__("Đổi")}</button>`
					: "";
			const phieu = this.phieu
				? `<a class="xh-ma-phieu" href="/app/location-transfer/${encodeURIComponent(this.phieu.name)}">${e(
						this.phieu.name
				  )}</a>`
				: `<span class="xh-mo">${__("phiếu mới")}</span>`;
			$d.html(`
				<div class="xh-kho">
					<span class="xh-mo">${__("Kho")}</span> <b>${e(this.kho)}</b> ${doi_kho}
					<span class="xh-cham">·</span> ${phieu}
				</div>`);
		}

		ve_lo_dang_cho() {
			const $c = this.$goc.find(".xh-lo-dang-cho");
			const c = this.cho;
			if (!c) return $c.empty();

			const nguon = c.nguon
				.map(
					(n) => `
					<button type="button" class="xh-nguon ${n.o === c.tu_o ? "dang-chon" : ""}" data-o="${e(n.o)}">
						${n.la_o_chua_xep ? `<span>${__("Chưa xếp")}</span>` : `<span class="xh-ma">${e(n.ma_in_nhan || n.o)}</span>`}
						<span class="xh-nguon-sl">${so(n.con_xep_duoc)}</span>
					</button>`
				)
				.join("");

			const g = c.goi_y || {};
			const goi_y = g.den_o
				? `<div class="xh-goi-y">
						<div class="xh-nhan">${__("Ô gợi ý")}</div>
						<div class="xh-goi-y-o">${e(g.ma_in_nhan || g.den_o)}</div>
						${g.ly_do ? `<div class="xh-mo">${e(g.ly_do)}</div>` : ""}
					</div>`
				: `<div class="xh-goi-y trong">
						<div class="xh-nhan">${__("Chưa có ô gợi ý — quét tem ô định xếp")}</div>
						${g.ly_do ? `<div class="xh-mo">${e(g.ly_do)}</div>` : ""}
					</div>`;
			const tem_hong = g.tem_hong
				? `<div class="xh-bao muc-cam">${__(
						"Ô in trên tem của lô này không còn xếp được — ĐỪNG theo tem cũ, dán đè tem mới."
				  )}</div>`
				: "";

			const ok = c.o_khac;
			const o_khac = ok
				? `<div class="xh-o-khac">
						<div>${__("Ô <b>{0}</b> KHÁC ô gợi ý. <b>Quét lại tem {0}</b> để xác nhận xếp vào đó, hoặc quét tem ô gợi ý.", [
							e(ok.ma_in_nhan || ok.ma_o),
						])}</div>
						<button type="button" class="xh-xac-nhan-o-khac">${__("Xếp vào {0}", [e(ok.ma_in_nhan || ok.ma_o)])}</button>
					</div>`
				: "";

			const n = this.nguon_dang_chon();
			$c.html(`
				<div class="xh-the">
					<div class="xh-the-dau">
						<div class="xh-dong-tren">
							<span class="xh-nhan-loai">${c.so_lo ? __("Lô") : __("Hàng không lô")}</span>
							<button type="button" class="xh-lien-ket-nho xh-bo-lo">${__("Bỏ lô này")}</button>
						</div>
						${c.so_lo ? `<div class="xh-ma-to">${e(c.so_lo)}</div>` : ""}
						<div class="xh-ten-hang">${e(c.ten_hang)}</div>
						<div class="xh-mo">${e(c.vat_tu)}${c.hsd ? " · HSD " + e(frappe.datetime.str_to_user(c.hsd)) : ""}</div>
					</div>

					<div class="xh-muc">
						<div class="xh-tieu-de-muc">${
							c.nguon.length > 1 ? __("Lấy từ ô — chạm để đổi") : __("Lấy từ ô")
						}</div>
						<div class="xh-nguon-ds">${nguon}</div>
					</div>

					<div class="xh-muc">
						<div class="xh-tieu-de-muc">${__("Số lượng xếp")}${
				n ? ` <span class="xh-mo">· ${__("tối đa {0}", [so(n.con_xep_duoc)])}</span>` : ""
			}</div>
						<div class="xh-so-luong-hang">
							<button type="button" class="xh-cong-tru" data-buoc="-1">−</button>
							<input type="number" class="xh-so-luong" inputmode="decimal" min="0" step="any"
								value="${flt(c.so_luong)}" />
							<span class="xh-don-vi">${e(c.don_vi || "")}</span>
							<button type="button" class="xh-cong-tru" data-buoc="1">+</button>
						</div>
					</div>

					<div class="xh-muc">${goi_y}${tem_hong}${o_khac}</div>
				</div>`);
		}

		ve_danh_sach() {
			const $ds = this.$goc.find(".xh-danh-sach");
			const dong = (this.phieu && this.phieu.dong) || [];
			if (!dong.length) return $ds.empty();
			$ds.html(`
				<div class="xh-tieu-de-muc xh-tieu-de-ds">${__("Trên phiếu · {0} dòng", [dong.length])}</div>
				${dong
					.slice()
					.reverse()
					.map(
						(d) => `
					<div class="xh-dong">
						<div class="xh-dong-chinh">
							<div class="xh-dong-ten">${e(d.ten_hang || d.vat_tu)}</div>
							${d.so_lo ? `<div class="xh-dong-lo">${e(d.so_lo)}</div>` : ""}
							<div class="xh-dong-duong">
								${d.tu_o_chua_xep ? `<span>${__("Chưa xếp")}</span>` : `<span class="xh-ma">${e(d.tu_o)}</span>`}
								<span class="xh-mui-ten">→</span>
								<b>${e(d.den_o)}</b>
							</div>
						</div>
						<div class="xh-dong-sl">${so(d.so_luong)}<small>${e(d.don_vi || "")}</small></div>
						<button type="button" class="xh-xoa-dong" data-dong="${e(d.name)}" title="${__("Bỏ dòng")}">×</button>
					</div>`
					)
					.join("")}`);
		}

		ve_chan_trang() {
			const $c = this.$goc.find(".xh-chan-trang");
			const so_dong = ((this.phieu && this.phieu.dong) || []).length;
			if (!so_dong) return $c.empty();
			$c.html(`
				<button type="button" class="btn btn-primary xh-hoan-tat">
					${__("Hoàn tất phiếu · {0} dòng", [so_dong])}
				</button>`);
		}
	}

	// Hộp hỏi CHỈ nhận thao tác CHẠM.
	//
	// KHÔNG dùng `frappe.confirm`: nó đặt `confirm_dialog = true`, và
	// `frappe/public/js/frappe/ui/keyboard.js` bắt phím Enter TOÀN TRANG để bấm nút
	// "Có" của hộp đó. Súng quét PDA gửi Enter sau mỗi lần quét — hộp "Ghi phiếu?"
	// đang mở mà bóp cò là phiếu được ghi vào sổ. Không phải lo xa: bài kiểm trình
	// duyệt ngày 17/09/2026 đã DUYỆT THẬT một phiếu xếp theo đúng đường này (phiếu
	// XVT-2026-00007 trên erptest, đã huỷ). Hộp `frappe.ui.Dialog` thường không có
	// cờ đó nên Enter không chạm được nó.
	function hoi({ noi_dung, nhan, khi_dong_y, khi_dong }) {
		let da_dong_y = false;
		const d = new frappe.ui.Dialog({
			title: __("Xác nhận"),
			primary_action_label: nhan,
			primary_action: () => {
				da_dong_y = true;
				d.hide();
				khi_dong_y();
			},
			secondary_action_label: __("Không"),
			secondary_action: () => d.hide(),
		});
		d.$body.append(`<p class="xh-hoi">${noi_dung}</p>`);
		d.onhide = () => {
			if (!da_dong_y && khi_dong) khi_dong();
		};
		d.show();
		return d;
	}

	function so(gia_tri) {
		return e(flt(gia_tri).toLocaleString("vi-VN", { maximumFractionDigits: 3 }));
	}

	function e(gia_tri) {
		return frappe.utils.escape_html(String(gia_tri == null ? "" : gia_tri));
	}

	function rung(mau) {
		try {
			navigator.vibrate && navigator.vibrate(mau);
		} catch (err) {
			// Trình duyệt chặn rung — không sao.
		}
	}
})();
