// Trang "Lấy hàng" — PDA của thủ kho.
//
// Chủ đầu tư 18/09/2026 chọn bản đầy đủ: quét tem lô + tem ô để XÁC NHẬN đã lấy,
// và sổ vị trí trừ ĐÚNG ô đã quét (qua bảng phân bổ `Location Allocation`), thay
// vì ô do FEFO tự chọn lúc duyệt phiếu giao.
//
// Máy chủ: `vitri/lay_hang.py`. Trang KHÔNG tự kiểm ô/lô — gửi lên và để câu báo
// của máy chủ hiện ra, một chỗ duy nhất giữ luật.
//
// Bọc IIFE và KHÔNG dùng `frappe.confirm` — xem `xep_hang_pda.js` để biết vì sao
// (súng quét gửi Enter sau mỗi lần quét, `frappe.confirm` bắt Enter toàn trang
// để bấm "Có" — hộp đang mở mà bóp cò là duyệt/ghi ngoài ý muốn).
(function () {
	const O_QUET = ["/assets/erpnext/js/vi_tri_kho/o_quet.js", "/assets/erpnext/js/vi_tri_kho/o_quet.css"];
	const API = "erpnext.vi_tri_kho.vitri.lay_hang.";

	frappe.pages["lay-hang-pda"].on_page_load = function (wrapper) {
		const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Lấy hàng"), single_column: true });
		frappe.require(O_QUET, () => {
			wrapper.lay_hang = new LayHangPda(page);
		});
	};

	frappe.pages["lay-hang-pda"].on_page_show = function (wrapper) {
		// Quay lại trang (vd. vừa mở phiếu trên form rồi bấm Back): nạp lại — có
		// thể đã bị sửa hay duyệt ở nơi khác.
		if (wrapper.lay_hang) wrapper.lay_hang.nap_lai();
	};

	class LayHangPda {
		constructor(page) {
			this.page = page;
			this.kho = null;
			this.kho_ds = [];
			this.ds = []; // danh sách phiếu đang chờ lấy của kho hiện tại
			this.phieu = null; // kết quả mo_phieu_giao
			// Lô đang chờ quét ô. `null` = đang ở bước ① (chờ quét lô).
			// { dong_hang, so_lo, so_luong, lo_khac } — `lo_khac` khác null khi đang
			// chờ QUÉT LẠI để xác nhận đổi/tách lô (xem `hoi_doi_lo`).
			this.cho = null;
			this.dung();
			this.nap_lai();
		}

		dung() {
			this.$goc = $(`
				<div class="lh">
					<div class="lh-dau-trang"></div>
					<div class="lh-cho-o-quet"></div>
					<div class="lh-thong-bao"></div>
					<div class="lh-than"></div>
					<div class="lh-chan-trang"></div>
				</div>
			`).appendTo(this.page.main);

			this.o_quet = new erpnext.vi_tri_kho.OQuet({
				cha: this.$goc.find(".lh-cho-o-quet"),
				vung: this.$goc,
				placeholder: __("Quét tem…"),
				goi_y: "",
				khi_quet: (ma) => this.quet(ma),
			});

			this.$goc.on("click", ".lh-chon-kho", (ev) => this.chon_kho($(ev.currentTarget).attr("data-kho")));
			this.$goc.on("click", ".lh-mo-phieu", (ev) => this.mo_phieu($(ev.currentTarget).attr("data-phieu")));
			this.$goc.on("click", ".lh-ve-danh-sach", () => {
				this.phieu = null;
				this.cho = null;
				this.nap_lai();
			});
			this.$goc.on("click", ".lh-bo-luot", (ev) => this.bo_luot($(ev.currentTarget).attr("data-luot")));
			this.$goc.on("click", ".lh-chot-thieu", (ev) => this.chot_thieu($(ev.currentTarget).attr("data-dong")));
			this.$goc.on("click", ".lh-bo-chot-thieu", (ev) => this.bo_chot_thieu($(ev.currentTarget).attr("data-dong")));
			this.$goc.on("click", ".lh-hoan-tat", () => this.hoan_tat());
			this.$goc.on("click", ".lh-xac-nhan-lo-khac", () => this.nhan_lo_khac());
			this.$goc.on("click", ".lh-cong-tru", (ev) => this.cong_tru(Number($(ev.currentTarget).attr("data-buoc"))));
			this.$goc.on("input change", ".lh-so-luong", (ev) => {
				if (this.cho) this.cho.so_luong = flt(ev.currentTarget.value);
			});
			// Enter trên ô số lượng: xong sửa số, trả focus cho súng quét.
			this.$goc.on("keydown", ".lh-so-luong", (ev) => {
				if (ev.key !== "Enter") return;
				ev.preventDefault();
				ev.currentTarget.blur();
				this.o_quet.giu_focus();
			});
		}

		// ------------------------------------------------------------ trạng thái

		nap_lai() {
			const goi = this.phieu
				? frappe.xcall(API + "mo_phieu_giao", { phieu: this.phieu.name }).then((p) => {
						this.phieu = p;
				  })
				: frappe.xcall(API + "danh_sach_phieu_giao", { kho: this.kho }).then((r) => {
						this.kho_ds = r.kho_ds || [];
						this.kho = r.kho;
						this.ds = r.phieu || [];
				  });
			return goi.then(() => {
				this.ve();
				this.o_quet.giu_focus();
			});
		}

		chon_kho(kho) {
			this.cho = null;
			this.bao();
			if (!kho) {
				// Nút "Đổi": về màn chọn kho. KHÔNG nạp lại — không truyền kho thì máy
				// chủ tự chọn lại đúng kho vừa rời khi chỉ có một kho quản lý vị trí.
				this.kho = null;
				this.phieu = null;
				this.ve();
				return;
			}
			this.kho = kho;
			this.phieu = null;
			this.nap_lai();
		}

		mo_phieu(ten) {
			this.cho = null;
			frappe.xcall(API + "mo_phieu_giao", { phieu: ten }).then((p) => {
				this.phieu = p;
				this.bao();
				this.ve();
				this.o_quet.giu_focus();
			});
		}

		quet(ma) {
			if (!this.phieu) {
				this.bao(__("Chọn phiếu giao trước khi quét."), "cam");
				return;
			}
			frappe.xcall(API + "quet_de_lay", { phieu: this.phieu.name, ma: ma }).then((d) => {
				d = d || { loai: null };
				if (d.loai === "lo") return this.nhan_lo(d);
				if (d.loai === "lo_khac") return this.hoi_doi_lo(d);
				if (d.loai === "o") return this.nhan_o(d);
				if (d.loai === "can_quet_lo") {
					// Chỉ hiện câu nhắc — KHÔNG đổi `this.cho`/gọi `ve()` lại: giữ nguyên
					// trạng thái đang chờ (nếu có) của lượt trước, cùng khuôn
					// `xep_hang_pda.js`.
					rung([80, 60, 80]);
					return this.bao(
						__("{0} có quản lý lô — quét tem LÔ trên thùng, không quét mã hàng.", [
							e(d.ten_hang || d.vat_tu),
						]),
						"cam"
					);
				}
				rung([80, 60, 80]);
				this.bao(__("Không nhận ra mã <b>{0}</b>, hoặc lô này không nằm trong phiếu.", [e(ma)]), "xam");
			});
		}

		nhan_lo(d) {
			const dong = this.phieu.dong.find((x) => x.dong_hang === d.dong_hang);
			if (!dong) {
				// `quet_de_lay` đọc phiếu MỚI từ CSDL; `this.phieu.dong` là bản đệm từ
				// lần `mo_phieu_giao` trước — lệch nhau khi có người khác (hoặc chính
				// mình ở `nhan_lo_khac`) vừa thêm/tách dòng. Nạp lại thay vì TypeError
				// câm trên `dong.can_lay` (đúng kiểu hỏng im lặng module này phải tránh).
				rung([80, 60, 80]);
				this.bao(__("Phiếu vừa thay đổi — đang nạp lại."), "cam");
				this.nap_lai();
				return;
			}
			const con_can = flt(dong.can_lay) - flt(dong.da_lay);
			if (con_can <= 0) {
				this.bao(__("Dòng này đã lấy đủ."), "xam");
				return;
			}
			rung([40]);
			// Quét lô mới khi đang chờ ô cho lô cũ: THAY lô cũ — chưa có gì được ghi.
			// `so_lo` có thể là `null` (mặt hàng không quản lý lô, xem `quet_de_lay`)
			// — giữ `vat_tu`/`ten_hang` để `html_lo_dang_cho`/gợi ý dưới ô quét có gì
			// để hiện thay cho một mã lô không tồn tại.
			this.cho = {
				dong_hang: d.dong_hang,
				so_lo: d.so_lo,
				vat_tu: d.vat_tu,
				ten_hang: dong.ten_hang,
				so_luong: con_can,
				lo_khac: null,
			};
			this.bao();
			this.ve();
		}

		hoi_doi_lo(d) {
			// Quét lại đúng tem đó để xác nhận — KHÔNG hộp thoại (Enter của súng quét
			// bấm luôn nút "Có" nếu dùng `frappe.confirm`, xem đầu file).
			if (this.cho && this.cho.lo_khac && this.cho.lo_khac.so_lo === d.so_lo) return this.nhan_lo_khac();
			rung([80]);
			this.cho = { dong_hang: d.dong_hang, so_lo: null, so_luong: 0, lo_khac: d };
			this.bao();
			this.ve();
		}

		nhan_lo_khac() {
			const lk = this.cho && this.cho.lo_khac;
			if (!lk) return;
			const dong = this.phieu.dong.find((x) => x.dong_hang === lk.dong_hang);
			if (!dong) {
				// Cùng lý do bảo vệ ở `nhan_lo`: phiếu có thể đã đổi giữa lúc chờ xác nhận.
				rung([80, 60, 80]);
				this.cho = null;
				this.bao(__("Phiếu vừa thay đổi — đang nạp lại."), "cam");
				this.nap_lai();
				return;
			}
			// Đã lấy được một phần của lô cũ → TÁCH dòng; chưa lấy gì → ĐỔI lô.
			const ham = flt(dong.da_lay) > 0 ? "tach_dong_theo_lo" : "doi_lo";
			frappe
				.xcall(API + ham, { phieu: this.phieu.name, dong_hang: lk.dong_hang, so_lo_moi: lk.so_lo })
				.then((p) => {
					rung([40, 40]);
					this.phieu = p;
					this.cho = null;
					this.bao(__("Đã chuyển sang lô <b>{0}</b>. Quét lại tem lô để lấy.", [e(lk.so_lo)]), "xanh");
					this.ve();
				})
				.catch(() => rung([80, 60, 80]))
				.finally(() => this.o_quet.giu_focus());
		}

		nhan_o(o) {
			// Không dùng `!this.cho.so_lo` để kiểm "đã quét lô chưa": mặt hàng KHÔNG
			// quản lý lô hợp lệ mang `so_lo = null` ngay cả khi đã sẵn sàng nhận ô
			// (xem `nhan_lo`) — trạng thái CHƯA sẵn sàng đúng là `!this.cho` (chưa
			// quét gì) hoặc `this.cho.lo_khac` (đang chờ quét lại để xác nhận đổi lô).
			if (!this.cho || this.cho.lo_khac) {
				rung([80, 60, 80]);
				this.bao(__("Quét tem LÔ (hoặc mã hàng, nếu mặt hàng không quản lý lô) trước, rồi mới quét tem ô."), "cam");
				return;
			}
			const c = this.cho;
			if (!(flt(c.so_luong) > 0)) {
				this.bao(__("Số lượng phải lớn hơn 0."), "cam");
				return;
			}
			frappe
				.xcall(API + "ghi_da_lay", {
					phieu: this.phieu.name,
					dong_hang: c.dong_hang,
					so_lo: c.so_lo,
					o: o.ma_o,
					so_luong: c.so_luong,
				})
				.then((p) => {
					rung([40, 40, 40]);
					this.phieu = p;
					this.cho = null;
					this.bao(
						__("Đã lấy <b>{0}</b> {1} ở <b>{2}</b>", [
							so(c.so_luong),
							e(c.so_lo || c.ten_hang || c.vat_tu || ""),
							e(o.ma_in_nhan || o.ma_o),
						]),
						"xanh"
					);
					this.ve();
				})
				.catch(() => rung([80, 60, 80]))
				.finally(() => this.o_quet.giu_focus());
		}

		cong_tru(buoc) {
			if (!this.cho) return;
			this.cho.so_luong = Math.max(0, flt(this.cho.so_luong) + buoc);
			this.$goc.find(".lh-so-luong").val(this.cho.so_luong);
		}

		bo_luot(ten) {
			frappe
				.xcall(API + "bo_dong_da_lay", { phieu: this.phieu.name, ten_dong: ten })
				.then((p) => {
					this.phieu = p;
					this.bao(__("Đã bỏ một lượt lấy."), "xam");
					this.ve();
				})
				.finally(() => this.o_quet.giu_focus());
		}

		chot_thieu(dong_hang) {
			const d = this.phieu.dong.find((x) => x.dong_hang === dong_hang);
			hoi({
				noi_dung: __("Chốt <b>{0}</b> chỉ lấy được <b>{1}</b>/{2}? Phiếu giao sẽ hạ số lượng xuống.", [
					e(d.ten_hang),
					so(d.da_lay),
					so(d.can_lay),
				]),
				nhan: __("Chốt thiếu"),
				khi_dong_y: () =>
					frappe
						.xcall(API + "chot_thieu", { phieu: this.phieu.name, dong_hang: dong_hang })
						.then((p) => {
							this.phieu = p;
							this.ve();
						})
						.finally(() => this.o_quet.giu_focus()),
				khi_dong: () => this.o_quet.giu_focus(),
			});
		}

		bo_chot_thieu(dong_hang) {
			frappe
				.xcall(API + "bo_chot_thieu", { phieu: this.phieu.name, dong_hang: dong_hang })
				.then((p) => {
					this.phieu = p;
					this.bao(__("Đã gỡ cờ chốt thiếu."), "xam");
					this.ve();
				})
				.finally(() => this.o_quet.giu_focus());
		}

		hoan_tat() {
			const ten = this.phieu.name;
			hoi({
				noi_dung: __("Duyệt phiếu giao <b>{0}</b>? Kho sẽ trừ đúng các ô vừa quét.", [e(ten)]),
				nhan: __("Duyệt phiếu"),
				khi_dong_y: () =>
					frappe
						.xcall(API + "hoan_tat", { phieu: ten })
						.then((kq) => {
							rung([40, 40, 40]);
							this.phieu = null;
							this.cho = null;
							const thieu = (kq.lay_thieu || []).length
								? " " + __("Có {0} dòng lấy thiếu — xem ghi chú trên phiếu.", [kq.lay_thieu.length])
								: "";
							this.bao(
								__("Đã duyệt <a href='{0}'>{1}</a>.", [
									`/app/delivery-note/${encodeURIComponent(ten)}`,
									e(ten),
								]) + thieu,
								"xanh"
							);
							return this.nap_lai();
						})
						.catch(() => {
							rung([80, 60, 80]);
							return this.nap_lai();
						})
						.finally(() => this.o_quet.giu_focus()),
				khi_dong: () => this.o_quet.giu_focus(),
			});
		}

		// ------------------------------------------------------------------ vẽ

		bao(html, muc) {
			const $tb = this.$goc.find(".lh-thong-bao");
			if (!html) return $tb.empty();
			$tb.html(`<div class="lh-bao muc-${muc || "xam"}">${html}</div>`);
		}

		ve() {
			this.ve_dau_trang();
			this.ve_than();
			this.ve_chan_trang();
			if (!this.kho_ds.length || !this.kho) {
				this.o_quet.dat_goi_y(__("Chọn kho để bắt đầu"));
			} else if (!this.phieu) {
				this.o_quet.dat_goi_y(__("Chọn phiếu giao để bắt đầu"));
			} else if (this.cho && this.cho.lo_khac) {
				this.o_quet.dat_goi_y(__("Quét LẠI tem {0} để đổi lô", [this.cho.lo_khac.so_lo]), "nhan-manh");
			} else if (this.cho) {
				// `so_lo` có thể là `null` (mặt hàng không quản lý lô) — khi đó nhắc
				// theo tên hàng thay vì in ra "lô null".
				const nhan = this.cho.so_lo
					? __("② Quét tem Ô cho lô {0}", [this.cho.so_lo])
					: __("② Quét tem Ô cho {0}", [this.cho.ten_hang || this.cho.vat_tu || ""]);
				this.o_quet.dat_goi_y(nhan, "nhan-manh");
			} else {
				this.o_quet.dat_goi_y(__("① Quét tem LÔ (hoặc mã hàng, nếu mặt hàng không quản lý lô)"));
			}
		}

		ve_dau_trang() {
			const $d = this.$goc.find(".lh-dau-trang");
			if (!this.kho_ds.length) {
				$d.html(`<div class="lh-bao muc-cam">${__("Chưa kho nào bật quản lý vị trí.")}</div>`);
				return;
			}
			if (!this.kho) {
				$d.html(`
					<div class="lh-tieu-de-muc">${__("Chọn kho")}</div>
					<div class="lh-chon-kho-ds">
						${this.kho_ds
							.map((k) => `<button type="button" class="lh-chon-kho" data-kho="${e(k)}">${e(k)}</button>`)
							.join("")}
					</div>`);
				return;
			}
			const doi_kho =
				this.kho_ds.length > 1 && !this.phieu
					? `<button type="button" class="lh-lien-ket-nho lh-chon-kho" data-kho="">${__("Đổi")}</button>`
					: "";
			const ve_ds = this.phieu
				? `<button type="button" class="lh-lien-ket-nho lh-ve-danh-sach">${__("← Danh sách")}</button>`
				: "";
			const phieu = this.phieu
				? `<span class="lh-cham">·</span>
					<a class="lh-ma-phieu" href="/app/delivery-note/${encodeURIComponent(this.phieu.name)}">${e(
						this.phieu.name
				  )}</a>
					<span class="lh-mo">${e(this.phieu.khach_hang || "")}</span>`
				: "";
			$d.html(`
				<div class="lh-kho">
					<span class="lh-mo">${__("Kho")}</span> <b>${e(this.kho)}</b> ${doi_kho}
					${phieu}
					${ve_ds}
				</div>`);
		}

		ve_than() {
			const $t = this.$goc.find(".lh-than");
			if (!this.kho) return $t.empty();
			if (!this.phieu) return this.ve_danh_sach($t);
			$t.html(this.html_lo_dang_cho() + this.html_dong_hang());
		}

		ve_danh_sach($t) {
			const ds = this.ds || [];
			if (!ds.length) {
				$t.html(`<div class="lh-bao muc-xam">${__("Không có phiếu giao nào đang chờ lấy ở kho này.")}</div>`);
				return;
			}
			$t.html(`
				<div class="lh-tieu-de-muc">${__("Phiếu đang chờ lấy · {0}", [ds.length])}</div>
				<div class="lh-ds-phieu">
					${ds
						.map(
							(p) => `
						<button type="button" class="lh-mo-phieu" data-phieu="${e(p.name)}">
							<div class="lh-mp-dau">
								<span class="lh-ma-phieu">${e(p.name)}</span>
								<span class="lh-mp-sl">${so(p.da_lay)}/${so(p.can_lay)}</span>
							</div>
							<div class="lh-mo">${e(p.khach_hang || "")} · ${so(p.so_dong)} ${__("dòng")}</div>
							${
								(p.nguoi_dang_lay || []).length
									? `<div class="lh-mp-dang-lay">${__("{0} đang lấy", [e(p.nguoi_dang_lay.join(", "))])}</div>`
									: ""
							}
						</button>`
						)
						.join("")}
				</div>`);
		}

		html_lo_dang_cho() {
			const c = this.cho;
			if (!c) return "";
			if (c.lo_khac) {
				const lk = c.lo_khac;
				const hsd_moi = lk.hsd ? frappe.datetime.str_to_user(lk.hsd) : "—";
				const hsd_cu = lk.hsd_dang_chot ? frappe.datetime.str_to_user(lk.hsd_dang_chot) : "—";
				return `
					<div class="lh-o-khac">
						<div>${__("Lô <b>{0}</b> (HSD {1}) KHÁC lô đang chốt <b>{2}</b> (HSD {3}) của cùng mặt hàng.", [
							e(lk.so_lo),
							e(hsd_moi),
							e(lk.so_lo_dang_chot || "—"),
							e(hsd_cu),
						])}</div>
						${
							lk.han_xa_hon
								? `<div class="lh-canh-bao-han">${__(
										"Lô mới có hạn XA HƠN lô đang chốt — kiểm tra kỹ trước khi đổi."
								  )}</div>`
								: ""
						}
						<div class="lh-mo">${__("Quét LẠI tem {0} để xác nhận, hoặc chạm nút bên dưới.", [e(lk.so_lo)])}</div>
						<button type="button" class="lh-xac-nhan-lo-khac">${__("Đổi sang lô {0}", [e(lk.so_lo)])}</button>
					</div>`;
			}
			// `so_lo` là `null` cho mặt hàng không quản lý lô (xem `quet_de_lay`/
			// `nhan_lo`) — hiện tên hàng thay cho một mã lô không tồn tại, KHÔNG
			// dùng phông đều `.lh-ma-to` cho chữ thường (quy tắc chỉ dành phông đều
			// cho mã ô/mã lô).
			return `
				<div class="lh-the">
					<div class="lh-the-dau">
						<span class="lh-nhan-loai">${c.so_lo ? __("Đang lấy lô") : __("Đang lấy hàng (không lô)")}</span>
						${
							c.so_lo
								? `<div class="lh-ma-to">${e(c.so_lo)}</div>`
								: `<div class="lh-ten-hang">${e(c.ten_hang || c.vat_tu)}</div>`
						}
					</div>
					<div class="lh-muc">
						<div class="lh-tieu-de-muc">${__("Số lượng lấy")}</div>
						<div class="lh-so-luong-hang">
							<button type="button" class="lh-cong-tru" data-buoc="-1">−</button>
							<input type="number" class="lh-so-luong" inputmode="decimal" min="0" step="any"
								value="${flt(c.so_luong)}" />
							<button type="button" class="lh-cong-tru" data-buoc="1">+</button>
						</div>
					</div>
				</div>`;
		}

		html_dong_hang() {
			const dong = (this.phieu && this.phieu.dong) || [];
			return `
				<div class="lh-tieu-de-muc lh-tieu-de-ds">${__("Các dòng hàng · {0}", [dong.length])}</div>
				${dong.map((d) => this.html_mot_dong(d)).join("")}`;
		}

		html_mot_dong(d) {
			if (!d.can_quet) {
				return `
					<div class="lh-dong lh-dong-mo">
						<div class="lh-dong-dau">
							<div class="lh-dong-ten">${e(d.ten_hang)}</div>
							<div class="lh-dong-sl">${so(d.da_lay)}/${so(d.can_lay)}<small>${e(d.don_vi || "")}</small></div>
						</div>
						<div class="lh-mo">${e(d.vat_tu)}${d.so_lo ? " · lô " + e(d.so_lo) : ""}</div>
						<div class="lh-mo">${__("Kho không quản lý vị trí — lấy tay, không cần quét.")}</div>
					</div>`;
			}

			const du = flt(d.da_lay) >= flt(d.can_lay) - 1e-9;
			const chot = d.da_chot_thieu
				? `<div class="lh-chot-banner">
						<div>${__("Đã chốt thiếu bởi <b>{0}</b> lúc {1}.", [
							e(d.chot_thieu_boi || "—"),
							d.chot_thieu_luc ? e(frappe.datetime.str_to_user(d.chot_thieu_luc)) : "—",
						])}</div>
						<button type="button" class="lh-bo-chot-thieu" data-dong="${e(d.dong_hang)}">${__("Bỏ chốt thiếu")}</button>
					</div>`
				: "";

			const goi_y = (d.o_nen_lay || []).length
				? `<div class="lh-goi-y-ds">
						<span class="lh-nhan">${__("Nên lấy")}</span>
						${d.o_nen_lay
							.map(
								(g) =>
									`<span class="lh-goi-y-o"><span class="lh-ma">${e(g.ma_in_nhan || g.o)}</span> <b>${so(
										g.so_luong
									)}</b></span>`
							)
							.join("")}
					</div>`
				: "";

			const da_lay_o = (d.da_lay_o || []).length
				? `<div class="lh-da-lay-ds">
						${d.da_lay_o
							.map(
								(p) => `
							<div class="lh-da-lay-dong">
								<span class="lh-ma">${e(p.o)}</span>
								<span class="lh-da-lay-sl">${so(p.so_luong)}</span>
								<button type="button" class="lh-bo-luot" data-luot="${e(p.name)}" title="${__("Bỏ lượt")}">×</button>
							</div>`
							)
							.join("")}
					</div>`
				: "";

			const nut_chot_thieu =
				!d.da_chot_thieu && flt(d.da_lay) > 0 && flt(d.da_lay) < flt(d.can_lay)
					? `<button type="button" class="lh-chot-thieu" data-dong="${e(d.dong_hang)}">${__("Chốt thiếu")}</button>`
					: "";

			return `
				<div class="lh-dong ${du ? "lh-dong-du" : ""}">
					<div class="lh-dong-dau">
						<div class="lh-dong-ten">${e(d.ten_hang)}</div>
						<div class="lh-dong-sl">${so(d.da_lay)}/${so(d.can_lay)}<small>${e(d.don_vi || "")}</small></div>
					</div>
					<div class="lh-mo">${e(d.vat_tu)}${d.so_lo ? " · lô " + e(d.so_lo) : ""}${
				d.hsd ? " · HSD " + e(frappe.datetime.str_to_user(d.hsd)) : ""
			}</div>
					${chot}
					${goi_y}
					${da_lay_o}
					${nut_chot_thieu}
				</div>`;
		}

		ve_chan_trang() {
			const $c = this.$goc.find(".lh-chan-trang");
			const dong = (this.phieu && this.phieu.dong) || [];
			const co_luot = dong.some((d) => flt(d.da_lay) > 0);
			if (!this.phieu || !co_luot) return $c.empty();
			$c.html(`<button type="button" class="btn btn-primary lh-hoan-tat">${__("Hoàn tất phiếu")}</button>`);
		}
	}

	// Hộp hỏi CHỈ nhận thao tác CHẠM.
	//
	// KHÔNG dùng `frappe.confirm`: nó đặt `confirm_dialog = true`, và
	// `frappe/public/js/frappe/ui/keyboard.js` bắt phím Enter TOÀN TRANG để bấm nút
	// "Có" của hộp đó. Súng quét PDA gửi Enter sau mỗi lần quét — hộp "Duyệt phiếu?"
	// đang mở mà bóp cò là phiếu được duyệt ngoài ý muốn. Không phải lo xa: bài kiểm
	// trình duyệt ngày 17/09/2026 đã DUYỆT THẬT một phiếu xếp theo đúng đường này
	// (phiếu XVT-2026-00007 trên erptest, đã huỷ) — xem `xep_hang_pda.js`. Hộp
	// `frappe.ui.Dialog` thường không có cờ đó nên Enter không chạm được nó.
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
		d.$body.append(`<p class="lh-hoi">${noi_dung}</p>`);
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
