// Hộp thoại LẤY HÀNG trên form phiếu giao (máy tính ở bàn đóng gói, súng quét USB)
// — chủ đầu tư 22/09/2026: "trong phiếu delivery note chúng ta sẽ làm nút lấy hàng".
//
// Cùng MỘT bộ hàm máy chủ với trang PDA `lay-hang-pda` (`vitri/lay_hang.py`): mọi
// luật — đúng lô, đúng ô, tồn của ô, quy đổi đơn vị, chốt thiếu, chặn lô hết hạn —
// nằm ở máy chủ. File này chỉ vẽ và gọi; KHÔNG thêm luật nào ở đây, nếu không hai
// màn hình sẽ nói hai kiểu về cùng một phiếu.
//
// Khác PDA ở chỗ bước ghi: PDA ghi ngay khi quét ô (tay đang cầm hàng ở kệ); ở bàn
// đóng gói người dùng còn chọn ĐƠN VỊ và SỐ KIỆN, nên quét ô chỉ điền ô, bấm Ghi
// (hoặc Enter ở ô số) mới ghi.
//
// KHÔNG dùng `frappe.confirm`: nó bật `confirm_dialog`, và Enter của súng quét bấm
// luôn nút "Có" (xem `lay_hang_pda.js`, hàm `hoi`). `frappe.ui.Dialog` thường thì
// Enter không chạm được.

frappe.provide("erpnext.warehouse_operations");

erpnext.warehouse_operations.lay_hang_dialog = (function () {
	const API = "erpnext.warehouse_operations.vitri.lay_hang.";
	const NAP = [
		"/assets/erpnext/js/warehouse_operations/o_quet.js",
		"/assets/erpnext/js/warehouse_operations/o_quet.css",
		"/assets/erpnext/js/warehouse_operations/tem_kien.js",
	];

	const CSS = `
		.lhd-bao { padding: 8px 12px; border-radius: var(--border-radius); margin: 8px 0; }
		.lhd-bao.muc-xanh { background: var(--green-highlight-color); }
		.lhd-bao.muc-cam { background: var(--yellow-highlight-color); }
		.lhd-bao.muc-do { background: var(--red-highlight-color); }
		.lhd-bao.muc-xam { background: var(--control-bg); }
		.lhd-cho { border: 1px solid var(--border-color); border-radius: var(--border-radius); padding: 12px; margin: 8px 0; }
		.lhd-cho-hang { display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-end; }
		.lhd-cho-hang label { display: block; font-size: var(--text-xs); color: var(--text-muted); margin-bottom: 2px; }
		.lhd-cho-hang input, .lhd-cho-hang select { width: 110px; }
		.lhd-ma { font-family: var(--font-stack-monospace, monospace); font-weight: 600; }
		.lhd-bang td, .lhd-bang th { vertical-align: top; font-size: var(--text-sm); }
		.lhd-dong-du { background: var(--green-highlight-color); }
		.lhd-luot { white-space: nowrap; }
		.lhd-luot button { padding: 0 6px; line-height: 1.2; }
		.lhd-canh-bao { color: var(--red-600, #c0392b); font-size: var(--text-xs); }
		.lhd-chan { display: flex; gap: 8px; justify-content: flex-end; flex-wrap: wrap; margin-top: 12px; }
	`;

	function mo(phieu, khi_dong) {
		frappe.require(NAP, () => new HopLayHang(phieu, khi_dong));
	}

	class HopLayHang {
		constructor(phieu, khi_dong) {
			this.ten = phieu;
			this.phieu = null; // kết quả `mo_phieu_giao`
			// Lượt đang chuẩn bị: null = chờ quét lô.
			// { dong_hang, so_lo, vat_tu, ten_hang, don_vi, so_luong, so_kien, o, ma_in_nhan, lo_khac }
			this.cho = null;
			this.d = new frappe.ui.Dialog({
				title: __("Lấy hàng · {0}", [phieu]),
				size: "extra-large",
				fields: [{ fieldtype: "HTML", fieldname: "goc" }],
			});
			this.d.onhide = () => khi_dong && khi_dong();
			this.$goc = this.d.fields_dict.goc.$wrapper;
			this.$goc.html(`
				<style>${CSS}</style>
				<div class="lhd-quet"></div>
				<div class="lhd-thong-bao"></div>
				<div class="lhd-cho-o"></div>
				<div class="lhd-than"></div>
				<div class="lhd-chan"></div>
			`);
			this.o_quet = new erpnext.warehouse_operations.OQuet({
				cha: this.$goc.find(".lhd-quet"),
				vung: this.d.$body,
				placeholder: __("Quét tem…"),
				khi_quet: (ma) => this.quet(ma),
			});
			this.gan_su_kien();
			this.d.show();
			this.nap_lai();
		}

		gan_su_kien() {
			const $g = this.$goc;
			$g.on("click", ".lhd-ghi", () => this.ghi());
			$g.on("click", ".lhd-huy-cho", () => {
				this.cho = null;
				this.bao();
				this.ve();
			});
			$g.on("click", ".lhd-doi-lo", () => this.nhan_lo_khac());
			$g.on("click", ".lhd-bo-luot", (ev) => this.goi("bo_dong_da_lay", { ten_dong: $(ev.currentTarget).attr("data-luot") }, __("Đã bỏ một lượt lấy.")));
			$g.on("click", ".lhd-chot-thieu", (ev) => this.chot_thieu($(ev.currentTarget).attr("data-dong")));
			$g.on("click", ".lhd-bo-chot-thieu", (ev) =>
				this.goi("bo_chot_thieu", { dong_hang: $(ev.currentTarget).attr("data-dong") }, __("Đã gỡ cờ chốt thiếu."))
			);
			$g.on("click", ".lhd-in-tem", (ev) => this.in_tem(Number($(ev.currentTarget).attr("data-chua-in"))));
			$g.on("click", ".lhd-hoan-tat", () => this.hoan_tat());
			$g.on("change", ".lhd-don-vi", (ev) => this.doi_don_vi(ev.currentTarget.value));
			$g.on("input change", ".lhd-so-luong", (ev) => {
				if (this.cho) this.cho.so_luong = flt(ev.currentTarget.value);
			});
			$g.on("input change", ".lhd-so-kien", (ev) => {
				if (this.cho) this.cho.so_kien = cint(ev.currentTarget.value);
			});
			$g.on("keydown", ".lhd-so-luong, .lhd-so-kien", (ev) => {
				if (ev.key !== "Enter") return;
				ev.preventDefault();
				this.ghi();
			});
		}

		// ------------------------------------------------------------ gọi máy chủ

		nap_lai() {
			return frappe.xcall(API + "mo_phieu_giao", { phieu: this.ten }).then((p) => {
				this.phieu = p;
				this.ve();
				this.o_quet.giu_focus();
			});
		}

		/** Gọi một hàm trả về phiếu (`mo_phieu_giao`) rồi vẽ lại. */
		goi(ham, doi_so, bao_xong) {
			return frappe
				.xcall(API + ham, Object.assign({ phieu: this.ten }, doi_so))
				.then((p) => {
					this.phieu = p;
					if (bao_xong) this.bao(bao_xong, "xam");
					this.ve();
					return p;
				})
				.finally(() => this.o_quet.giu_focus());
		}

		dong(dong_hang) {
			return ((this.phieu && this.phieu.dong) || []).find((x) => x.dong_hang === dong_hang);
		}

		quet(ma) {
			frappe.xcall(API + "quet_de_lay", { phieu: this.ten, ma }).then((d) => {
				d = d || { loai: null };
				if ((d.loai === "lo" || d.loai === "lo_khac") && d.het_han) {
					const hsd = d.hsd ? frappe.datetime.str_to_user(d.hsd) : "—";
					return this.bao(__("CHẶN: lô <b>{0}</b> đã hết hạn ngày {1}.", [e(d.so_lo), e(hsd)]), "do");
				}
				if (d.loai === "lo") return this.nhan_lo(d);
				if (d.loai === "lo_khac") return this.hoi_doi_lo(d);
				if (d.loai === "o") return this.nhan_o(d);
				if (d.loai === "can_quet_lo") {
					return this.bao(__("{0} có quản lý lô — quét tem LÔ, không quét mã hàng.", [e(d.ten_hang || d.vat_tu)]), "cam");
				}
				this.bao(__("Không nhận ra mã <b>{0}</b>, hoặc lô này không nằm trong phiếu.", [e(ma)]), "xam");
			});
		}

		nhan_lo(d) {
			const dong = this.dong(d.dong_hang);
			if (!dong) return this.nap_lai();
			if (flt(dong.da_lay_ton) >= flt(dong.can_lay_ton) - 1e-9) return this.bao(__("Dòng này đã lấy đủ."), "xam");
			this.cho = {
				dong_hang: d.dong_hang,
				so_lo: d.so_lo,
				vat_tu: d.vat_tu,
				ten_hang: dong.ten_hang,
				o: null,
				ma_in_nhan: null,
				lo_khac: null,
			};
			this.doi_don_vi(dong.don_vi_dong, true);
			// Còn thiếu ít hơn một đơn vị của dòng (vd. 50 Cái trên dòng bán theo Hộp):
			// gợi ý theo đơn vị tồn thay vì số 0.
			if (!(flt(this.cho.so_luong) > 0)) this.doi_don_vi(dong.don_vi_ton, true);
			this.bao();
			this.ve();
		}

		/** Đổi đơn vị lấy: số lượng mặc định = phần còn thiếu quy theo đơn vị mới. */
		doi_don_vi(don_vi, khong_ve) {
			const c = this.cho;
			const dong = c && this.dong(c.dong_hang);
			if (!dong) return;
			const dv = (dong.don_vi_chon || []).find((x) => x.uom === don_vi) || { uom: dong.don_vi_ton, he_so: 1 };
			const con_ton = Math.max(0, flt(dong.can_lay_ton) - flt(dong.da_lay_ton));
			c.don_vi = dv.uom;
			c.he_so = flt(dv.he_so) || 1;
			// Đơn vị lớn (Thùng) có thể không chia tròn phần còn thiếu — lấy phần NGUYÊN,
			// phần lẻ lấy tiếp bằng đơn vị nhỏ hơn. Không bao giờ gợi ý vượt phần còn thiếu.
			c.so_luong = c.he_so === 1 ? flt(con_ton, 6) : Math.floor(con_ton / c.he_so + 1e-9);
			// Cùng mặc định với máy chủ (`ghi_da_lay`): đơn vị đóng gói → mỗi đơn vị một kiện.
			c.so_kien = c.he_so !== 1 ? Math.max(1, Math.round(c.so_luong)) : 1;
			if (!khong_ve) this.ve();
		}

		hoi_doi_lo(d) {
			// Quét LẠI đúng tem đó = xác nhận (không hộp thoại — Enter của súng quét).
			if (this.cho && this.cho.lo_khac && this.cho.lo_khac.so_lo === d.so_lo) return this.nhan_lo_khac();
			this.cho = { dong_hang: d.dong_hang, lo_khac: d };
			this.bao();
			this.ve();
		}

		nhan_lo_khac() {
			const lk = this.cho && this.cho.lo_khac;
			const dong = lk && this.dong(lk.dong_hang);
			if (!dong) return this.nap_lai();
			const ham = flt(dong.da_lay_ton) > 0 ? "tach_dong_theo_lo" : "doi_lo";
			this.cho = null;
			this.goi(ham, { dong_hang: lk.dong_hang, so_lo_moi: lk.so_lo }).then(() =>
				this.bao(__("Đã chuyển sang lô <b>{0}</b>. Quét lại tem lô để lấy.", [e(lk.so_lo)]), "xanh")
			);
		}

		nhan_o(o) {
			if (!this.cho || this.cho.lo_khac) {
				return this.bao(__("Quét tem LÔ trước, rồi mới quét tem ô."), "cam");
			}
			this.cho.o = o.ma_o;
			this.cho.ma_in_nhan = o.ma_in_nhan || o.ma_o;
			this.bao();
			this.ve();
			// Số lượng / số kiện đã sẵn mặc định — con trỏ về ô số để sửa nhanh, Enter là ghi.
			this.$goc.find(".lhd-so-luong").trigger("focus").trigger("select");
		}

		ghi() {
			const c = this.cho;
			if (!c || c.lo_khac) return;
			if (!c.o) return this.bao(__("Quét tem Ô nơi lấy hàng trước khi ghi."), "cam");
			if (!(flt(c.so_luong) > 0)) return this.bao(__("Số lượng phải lớn hơn 0."), "cam");
			if (!(cint(c.so_kien) >= 1)) return this.bao(__("Số kiện phải từ 1 trở lên."), "cam");
			frappe
				.xcall(API + "ghi_da_lay", {
					phieu: this.ten,
					dong_hang: c.dong_hang,
					so_lo: c.so_lo,
					o: c.o,
					so_luong: c.so_luong,
					don_vi: c.don_vi,
					so_kien: c.so_kien,
				})
				.then((p) => {
					this.phieu = p;
					this.cho = null;
					this.bao(
						__("Đã lấy <b>{0} {1}</b> ({2} kiện) lô {3} ở <b>{4}</b>.", [
							so(p.so_luong_da_ghi != null ? p.so_luong_da_ghi : c.so_luong),
							e(p.don_vi_da_ghi || c.don_vi),
							cint(c.so_kien),
							e(c.so_lo || c.vat_tu),
							e(c.ma_in_nhan),
						]),
						"xanh"
					);
					this.ve();
				})
				.finally(() => this.o_quet.giu_focus());
		}

		chot_thieu(dong_hang) {
			const d = this.dong(dong_hang);
			hoi(
				__("Chốt <b>{0}</b> chỉ lấy được <b>{1}</b>/{2} {3}? Phiếu giao sẽ hạ số lượng xuống khi Hoàn tất.", [
					e(d.ten_hang),
					so(d.da_lay),
					so(d.can_lay),
					e(d.don_vi_dong),
				]),
				__("Chốt thiếu"),
				() => this.goi("chot_thieu", { dong_hang }),
				() => this.o_quet.giu_focus()
			);
		}

		in_tem(chi_chua_in) {
			erpnext.warehouse_operations.tem_kien.in_tem(this.ten, chi_chua_in).then((kq) => {
				if (kq) this.nap_lai();
				else this.o_quet.giu_focus();
			});
		}

		hoan_tat() {
			hoi(
				__("Duyệt phiếu giao <b>{0}</b>? Kho sẽ trừ đúng các ô vừa lấy.", [e(this.ten)]),
				__("Duyệt phiếu"),
				() =>
					frappe
						.xcall(API + "hoan_tat", { phieu: this.ten })
						.then(() => {
							frappe.show_alert({ message: __("Đã duyệt {0}", [this.ten]), indicator: "green" });
							this.d.hide();
						})
						.catch(() => this.nap_lai()),
				() => this.o_quet.giu_focus()
			);
		}

		// ------------------------------------------------------------------ vẽ

		bao(html, muc) {
			const $tb = this.$goc.find(".lhd-thong-bao");
			if (!html) return $tb.empty();
			$tb.html(`<div class="lhd-bao muc-${muc || "xam"}">${html}</div>`);
		}

		ve() {
			this.$goc.find(".lhd-cho-o").html(this.html_cho());
			this.$goc.find(".lhd-than").html(this.html_bang());
			this.$goc.find(".lhd-chan").html(this.html_chan());
			const c = this.cho;
			if (!c) this.o_quet.dat_goi_y(__("① Quét tem LÔ trên hàng"));
			else if (c.lo_khac) this.o_quet.dat_goi_y(__("Quét LẠI tem {0} để đổi lô", [c.lo_khac.so_lo]), "nhan-manh");
			else if (!c.o) this.o_quet.dat_goi_y(__("② Quét tem Ô nơi lấy lô {0}", [c.so_lo || c.vat_tu]), "nhan-manh");
			else this.o_quet.dat_goi_y(__("③ Chọn đơn vị, số lượng, số kiện rồi bấm Ghi (hoặc Enter)"), "nhan-manh");
		}

		html_cho() {
			const c = this.cho;
			if (!c) return "";
			if (c.lo_khac) {
				const lk = c.lo_khac;
				return `
					<div class="lhd-cho">
						<div>${__("Lô <b>{0}</b> (HSD {1}) KHÁC lô đang chốt <b>{2}</b> trên dòng này.", [
							e(lk.so_lo),
							lk.hsd ? e(frappe.datetime.str_to_user(lk.hsd)) : "—",
							e(lk.so_lo_dang_chot || "—"),
						])}</div>
						${lk.han_xa_hon ? `<div class="lhd-canh-bao">${__("Lô mới có hạn XA HƠN lô đang chốt — kiểm tra kỹ trước khi đổi.")}</div>` : ""}
						<div class="lhd-chan" style="justify-content:flex-start">
							<button type="button" class="btn btn-sm btn-primary lhd-doi-lo">${__("Đổi sang lô {0}", [e(lk.so_lo)])}</button>
							<button type="button" class="btn btn-sm btn-default lhd-huy-cho">${__("Thôi")}</button>
						</div>
					</div>`;
			}
			const dong = this.dong(c.dong_hang) || {};
			const lua_chon = (dong.don_vi_chon || [])
				.map(
					(x) =>
						`<option value="${e(x.uom)}" ${x.uom === c.don_vi ? "selected" : ""}>${e(x.uom)}${
							flt(x.he_so) !== 1 ? ` (= ${so(x.he_so)} ${e(dong.don_vi_ton)})` : ""
						}</option>`
				)
				.join("");
			const quy_doi =
				flt(c.he_so) !== 1 ? `= ${so(flt(c.so_luong) * flt(c.he_so))} ${e(dong.don_vi_ton)}` : "";
			return `
				<div class="lhd-cho">
					<div style="margin-bottom:8px">
						${__("Đang lấy")} <span class="lhd-ma">${e(c.so_lo || "")}</span> · ${e(c.ten_hang || c.vat_tu)}
						· ${__("Ô")}: ${c.o ? `<span class="lhd-ma">${e(c.ma_in_nhan)}</span>` : `<i class="text-muted">${__("chưa quét")}</i>`}
					</div>
					<div class="lhd-cho-hang">
						<div><label>${__("Đơn vị")}</label><select class="form-control input-sm lhd-don-vi">${lua_chon}</select></div>
						<div><label>${__("Số lượng")}</label><input type="number" min="0" step="any" class="form-control input-sm lhd-so-luong" value="${flt(c.so_luong)}"></div>
						<div><label>${__("Số kiện (số tem)")}</label><input type="number" min="1" step="1" class="form-control input-sm lhd-so-kien" value="${cint(c.so_kien)}"></div>
						<div class="text-muted small" style="padding-bottom:6px">${quy_doi}</div>
						<div>
							<button type="button" class="btn btn-sm btn-primary lhd-ghi" ${c.o ? "" : "disabled"}>${__("Ghi")}</button>
							<button type="button" class="btn btn-sm btn-default lhd-huy-cho">${__("Thôi")}</button>
						</div>
					</div>
				</div>`;
		}

		html_bang() {
			const ds = (this.phieu && this.phieu.dong) || [];
			return `
				<table class="table table-bordered lhd-bang">
					<thead><tr>
						<th>${__("Mặt hàng")}</th><th>${__("Lô")}</th><th>${__("Đã lấy / cần")}</th>
						<th>${__("Nên lấy ở")}</th><th>${__("Các lượt đã lấy")}</th><th></th>
					</tr></thead>
					<tbody>${ds.map((d) => this.html_dong(d)).join("")}</tbody>
				</table>`;
		}

		html_dong(d) {
			const ten = `<div>${e(d.ten_hang)}</div><div class="text-muted small">${e(d.vat_tu)}</div>`;
			if (!d.can_quet) {
				return `<tr><td>${ten}</td><td colspan="5" class="text-muted small">${e(d.ly_do_khong_quet || "")}</td></tr>`;
			}
			const du = flt(d.da_lay_ton) >= flt(d.can_lay_ton) - 1e-9;
			const lo = `
				<div class="lhd-ma">${e(d.so_lo || "—")}</div>
				${d.hsd ? `<div class="text-muted small">HSD ${e(frappe.datetime.str_to_user(d.hsd))}</div>` : ""}
				${
					d.lo_nen_lay && d.lo_nen_lay !== d.so_lo
						? `<div class="small">${__("Nên lấy lô")} <span class="lhd-ma">${e(d.lo_nen_lay)}</span>${
								d.lo_nen_lay_hsd ? ` (HSD ${e(frappe.datetime.str_to_user(d.lo_nen_lay_hsd))})` : ""
						  }</div>`
						: ""
				}
				${
					d.lo_tren_phieu_muon_hon
						? `<div class="lhd-canh-bao">${__("Lô trên phiếu hết hạn muộn hơn lô {0}", [e(d.lo_nen_lay)])}</div>`
						: ""
				}`;
			const khac_dv = d.don_vi_dong !== d.don_vi_ton;
			const sl = `
				<b>${so(d.da_lay)}/${so(d.can_lay)}</b> ${e(d.don_vi_dong)}
				${khac_dv ? `<div class="text-muted small">${so(d.da_lay_ton)}/${so(d.can_lay_ton)} ${e(d.don_vi_ton)}</div>` : ""}
				${d.da_chot_thieu ? `<div class="lhd-canh-bao">${__("Đã chốt thiếu")}</div>` : ""}`;
			const goi_y = (d.o_nen_lay || [])
				.map((g) => `<div><span class="lhd-ma">${e(g.ma_in_nhan || g.o)}</span> ${so(g.so_luong)} ${e(d.don_vi_ton)}</div>`)
				.join("");
			const luot = (d.da_lay_o || [])
				.map(
					(p) => `
					<div class="lhd-luot">
						<span class="lhd-ma">${e(p.ma_in_nhan || p.o)}</span> · ${so(p.so_luong_lay)} ${e(p.don_vi_lay)}
						· ${__("{0} kiện", [p.so_kien])}${p.so_kien_da_in >= p.so_kien ? " ✓" : ""}
						<button type="button" class="btn btn-xs btn-default lhd-bo-luot" data-luot="${e(p.name)}" title="${__("Bỏ lượt")}">×</button>
					</div>`
				)
				.join("");
			let nut = "";
			if (d.da_chot_thieu) {
				nut = `<button type="button" class="btn btn-xs btn-default lhd-bo-chot-thieu" data-dong="${e(d.dong_hang)}">${__("Bỏ chốt thiếu")}</button>`;
			} else if (flt(d.da_lay_ton) > 0 && !du) {
				nut = `<button type="button" class="btn btn-xs btn-default lhd-chot-thieu" data-dong="${e(d.dong_hang)}">${__("Chốt thiếu")}</button>`;
			}
			return `<tr class="${du ? "lhd-dong-du" : ""}"><td>${ten}</td><td>${lo}</td><td>${sl}</td><td>${goi_y}</td><td>${luot}</td><td>${nut}</td></tr>`;
		}

		html_chan() {
			const p = this.phieu;
			if (!p) return "";
			const tong = cint(p.tong_kien);
			const da_in = cint(p.so_kien_da_in);
			const nut_tem = tong
				? `<button type="button" class="btn btn-default lhd-in-tem" data-chua-in="${da_in < tong ? 1 : 0}">${
						da_in < tong ? __("In tem kiện ({0}/{1} đã in)", [da_in, tong]) : __("In lại tem kiện ({0})", [tong])
				  }</button>`
				: "";
			return `${nut_tem}<button type="button" class="btn btn-primary lhd-hoan-tat">${__("Hoàn tất (duyệt)")}</button>`;
		}
	}

	// Hộp hỏi chỉ nhận thao tác CHUỘT — xem đầu file (không `frappe.confirm`).
	function hoi(noi_dung, nhan, khi_dong_y, khi_dong) {
		let dong_y = false;
		const d = new frappe.ui.Dialog({
			title: __("Xác nhận"),
			primary_action_label: nhan,
			primary_action: () => {
				dong_y = true;
				d.hide();
				khi_dong_y();
			},
			secondary_action_label: __("Không"),
			secondary_action: () => d.hide(),
		});
		d.$body.append(`<p>${noi_dung}</p>`);
		d.onhide = () => {
			if (!dong_y && khi_dong) khi_dong();
		};
		d.show();
	}

	function so(x) {
		return e(flt(x).toLocaleString("vi-VN", { maximumFractionDigits: 3 }));
	}

	function e(x) {
		return frappe.utils.escape_html(String(x == null ? "" : x));
	}

	return { mo };
})();
