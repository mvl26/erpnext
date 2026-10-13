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
	const O_QUET = ["/assets/erpnext/js/warehouse_operations/o_quet.js", "/assets/erpnext/js/warehouse_operations/o_quet.css"];
	const API = "erpnext.warehouse_operations.vitri.lay_hang.";

	frappe.pages["lay-hang-pda"].on_page_load = function (wrapper) {
		const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Lấy hàng"), single_column: true });
		frappe.require(O_QUET, () => {
			wrapper.lay_hang = new LayHangPda(page);
		});
	};

	frappe.pages["lay-hang-pda"].on_page_show = function (wrapper) {
		// Quay lại trang (vd. vừa mở phiếu trên form rồi bấm Back): nạp lại — có
		// thể đã bị sửa hay duyệt ở nơi khác. Tới từ nút "Lấy hàng trên PDA" của
		// một phiếu KHÁC (`/app/lay-hang-pda/<phiếu>`) thì mở thẳng phiếu đó.
		if (wrapper.lay_hang) wrapper.lay_hang.theo_duong_dan();
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
			// Phiếu đã mở theo đường dẫn lần gần nhất — để Back từ form về cùng đường
			// dẫn thì chỉ nạp lại, không kéo thủ kho khỏi phiếu/danh sách đang xem.
			this.phieu_theo_duong_dan = null;
			this.dung();
			this.theo_duong_dan();
		}

		// Nút "Lấy hàng trên PDA" trên form Phiếu giao đưa tới `/app/lay-hang-pda/<phiếu>`
		// (`public/js/warehouse_operations/delivery_note.js`): mở thẳng phiếu đó, chọn luôn kho.
		theo_duong_dan() {
			const ten = frappe.get_route()[1];
			if (!ten || ten === this.phieu_theo_duong_dan) return this.nap_lai();
			this.phieu_theo_duong_dan = ten;
			this.cho = null;
			return frappe
				.xcall(API + "mo_phieu_giao", { phieu: ten })
				.then((p) => {
					if (p.docstatus !== 0) {
						this.phieu = null;
						this.bao(
							__("Phiếu {0} đã {1} — không lấy hàng được nữa.", [
								e(ten),
								p.docstatus === 1 ? __("duyệt") : __("huỷ"),
							]),
							"cam"
						);
						return this.nap_lai();
					}
					this.phieu = p;
					if (p.kho) this.kho = p.kho;
					this.bao();
					// Danh sách kho cần cho nút "← Danh sách"/"Đổi" — nạp một lần ở
					// nền, không chặn việc vẽ phiếu.
					if (!this.kho_ds.length) {
						// Không truyền `kho`: kho của phiếu có thể không bật quản lý vị
						// trí (máy chủ sẽ từ chối), danh sách chỉ cần để biết các kho.
						frappe.xcall(API + "danh_sach_phieu_giao", {}).then((r) => {
							this.kho_ds = r.kho_ds || [];
							this.ve();
						});
					}
					this.ve();
					this.o_quet.giu_focus();
				})
				.catch(() => {
					// Máy chủ đã hiện câu báo (không có quyền, phiếu không tồn tại…).
					this.phieu = null;
					return this.nap_lai();
				});
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

			this.o_quet = new erpnext.warehouse_operations.OQuet({
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
				// Bỏ tên phiếu khỏi đường dẫn — nếu không, F5 hay Back sẽ mở lại
				// đúng phiếu vừa rời. Đổi đường dẫn tự gọi `on_page_show` → nạp lại.
				this.phieu_theo_duong_dan = null;
				if (frappe.get_route()[1]) frappe.set_route("lay-hang-pda");
				else this.nap_lai();
			});
			this.$goc.on("click", ".lh-bo-luot", (ev) => this.bo_luot($(ev.currentTarget).attr("data-luot")));
			this.$goc.on("click", ".lh-chot-thieu", (ev) => this.chot_thieu($(ev.currentTarget).attr("data-dong")));
			this.$goc.on("click", ".lh-bo-chot-thieu", (ev) => this.bo_chot_thieu($(ev.currentTarget).attr("data-dong")));
			this.$goc.on("click", ".lh-hoan-tat", () => this.hoan_tat());
			this.$goc.on("click", ".lh-xac-nhan-lo-khac", () => this.nhan_lo_khac());
			this.$goc.on("click", ".lh-cong-tru", (ev) => this.cong_tru(Number($(ev.currentTarget).attr("data-buoc"))));
			this.$goc.on("click", ".lh-chon-don-vi", (ev) => this.chon_don_vi($(ev.currentTarget).attr("data-uom")));
			this.$goc.on("click", ".lh-kien-cong-tru", (ev) =>
				this.kien_cong_tru(Number($(ev.currentTarget).attr("data-buoc")))
			);
			this.$goc.on("input change", ".lh-so-luong", (ev) => {
				if (!this.cho) return;
				this.cho.so_luong = flt(ev.currentTarget.value);
				// Người dùng đã TỰ sửa số — từ đây `nhan_o` không còn được âm thầm
				// cắt số này theo tồn của ô (xem `cho.da_sua_so_luong` ở `nhan_o`).
				this.cho.da_sua_so_luong = true;
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
				// VÒNG SỬA CUỐI (review toàn nhánh, Critical): lô hết hạn — CHẶN hẳn,
				// không chuyển `this.cho` sang dòng đó. Không phải "quét lại để xác
				// nhận" như `lo_khac` thường lệ — quét lại tem đó vẫn phải bị chặn.
				if ((d.loai === "lo" || d.loai === "lo_khac") && d.het_han) return this.bao_lo_het_han(d);
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

		// VÒNG SỬA CUỐI (review toàn nhánh, Critical): lô hết hạn — thao tác nguy
		// hiểm nhất (giao lô hết hạn) trước bản vá lại DỄ nhất (`han_xa_hon` chỉ
		// cảnh báo nhẹ khi lô mới gần hạn hơn). CHẶN hẳn ở đây, không phải một
		// bước "quét lại để xác nhận": không đổi `this.cho`, không gọi `ve()` để
		// mở lối sang dòng đó.
		bao_lo_het_han(d) {
			rung([120, 80, 120]);
			const hsd = d.hsd ? frappe.datetime.str_to_user(d.hsd) : "—";
			this.bao(
				__(
					"CHẶN: lô <b>{0}</b> đã hết hạn ngày {1} — không lấy được trên PDA. Muốn xuất lô " +
						"hết hạn thì thao tác trên form Phiếu giao hàng (máy tính).",
					[e(d.so_lo), e(hsd)]
				),
				"do"
			);
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
			if (flt(dong.can_lay_ton) - flt(dong.da_lay_ton) <= 1e-9) {
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
				// `false` = số lượng còn là số MẶC ĐỊNH (toàn bộ phần còn thiếu của
				// dòng) — `nhan_o` được phép âm thầm cắt xuống theo tồn của ô quét
				// được. Bật `true` ngay khi người dùng chạm vào ô số lượng (xem
				// listener "input change"/`cong_tru`) — từ đó KHÔNG được tự ý cắt số
				// người dùng đã tự gõ, đổi ý định của họ.
				da_sua_so_luong: false,
				// Đơn vị lấy (22/09/2026): mặc định đơn vị của dòng; đổi bằng hàng nút
				// `don_vi_chon`. `so_kien` = số tem kiện; người dùng chưa chạm thì để
				// máy chủ tự tính (`ghi_da_lay`) theo số THẬT đã ghi.
				don_vi: dong.don_vi_dong,
				he_so: flt(dong.he_so_dong) || 1,
				so_kien: null,
			};
			// Dòng bán theo đơn vị đóng gói: gợi ý phần NGUYÊN (5,8 Hộp → 5 Hộp), còn
			// thiếu dưới một đơn vị (80 Cái) thì gợi ý theo đơn vị tồn.
			if (flt(this.cho.he_so) !== 1) {
				this.chon_don_vi(dong.don_vi_dong, true);
				if (!(flt(this.cho.so_luong) > 0)) this.chon_don_vi(dong.don_vi_ton, true);
			}
			this.bao();
			this.ve();
		}

		/** Đổi đơn vị lấy: số lượng mặc định = phần còn thiếu quy theo đơn vị mới
		 * (đơn vị đóng gói lấy phần NGUYÊN — phần lẻ lấy tiếp bằng đơn vị nhỏ hơn). */
		chon_don_vi(uom, khong_ve) {
			const c = this.cho;
			const dong = c && this.phieu.dong.find((x) => x.dong_hang === c.dong_hang);
			if (!dong) return;
			const dv = (dong.don_vi_chon || []).find((x) => x.uom === uom);
			if (!dv) return;
			const con_ton = Math.max(0, flt(dong.can_lay_ton) - flt(dong.da_lay_ton));
			c.don_vi = dv.uom;
			c.he_so = flt(dv.he_so) || 1;
			c.so_luong = c.he_so === 1 ? flt(con_ton, 6) : Math.floor(con_ton / c.he_so + 1e-9);
			c.da_sua_so_luong = false;
			c.so_kien = null;
			if (khong_ve) return;
			this.ve();
			this.o_quet.giu_focus();
		}

		/** Số kiện mặc định khi người dùng chưa sửa — CÙNG luật `ghi_da_lay`. */
		so_kien_mac_dinh() {
			const c = this.cho;
			return flt(c.he_so) !== 1 ? Math.max(1, Math.round(flt(c.so_luong))) : 1;
		}

		kien_cong_tru(buoc) {
			if (!this.cho) return;
			const hien = this.cho.so_kien != null ? this.cho.so_kien : this.so_kien_mac_dinh();
			this.cho.so_kien = Math.max(1, hien + buoc);
			this.$goc.find(".lh-so-kien").text(this.cho.so_kien);
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
			// Số lượng còn là MẶC ĐỊNH (người dùng chưa tự sửa): cho máy chủ được
			// cắt xuống theo tồn thật của ô vừa quét (`lay_toi_da_theo_o`) — đúng
			// ca hay gặp nhất, ô gợi ý có ÍT hơn phần còn thiếu của cả dòng. Người
			// dùng ĐÃ TỰ gõ số thì gọi như cũ — không được âm thầm đổi ý định họ.
			const yeu_cau = flt(c.so_luong);
			const theo_ton_o = !c.da_sua_so_luong;
			const doi_so = {
				phieu: this.phieu.name,
				dong_hang: c.dong_hang,
				so_lo: c.so_lo,
				o: o.ma_o,
				so_luong: c.so_luong,
				lay_toi_da_theo_o: theo_ton_o ? 1 : 0,
				don_vi: c.don_vi,
			};
			// Chỉ gửi số kiện khi người dùng ĐÃ sửa: số lượng có thể bị cắt theo tồn
			// của ô, và máy chủ tính số kiện mặc định theo số THẬT đã ghi.
			if (c.so_kien != null) doi_so.so_kien = c.so_kien;
			frappe
				.xcall(API + "ghi_da_lay", doi_so)
				.then((p) => {
					rung([40, 40, 40]);
					this.phieu = p;
					const da_ghi = p.so_luong_da_ghi != null ? flt(p.so_luong_da_ghi) : yeu_cau;
					const bi_cat = theo_ton_o && da_ghi < yeu_cau - 1e-9;
					// Đọc lại phần CÒN THIẾU của dòng từ CHÍNH payload máy chủ vừa trả
					// (không tự trừ tay `yeu_cau - da_ghi`): server là nguồn sự thật duy
					// nhất, và một lượt ghi khác (tab/thiết bị khác) có thể đã đổi
					// `da_lay` của dòng ngay giữa lúc này.
					const dong_moi = (p.dong || []).find((x) => x.dong_hang === c.dong_hang);
					// Theo ĐƠN VỊ ĐANG CHỌN (có thể khác đơn vị của dòng).
					const con_lai_dong = dong_moi
						? (flt(dong_moi.can_lay_ton) - flt(dong_moi.da_lay_ton)) / (flt(c.he_so) || 1)
						: 0;
					const dv_ghi = p.don_vi_da_ghi || c.don_vi || "";
					if (bi_cat && con_lai_dong > 1e-9) {
						// VÒNG SỬA (review độc lập, model mạnh): TRƯỚC bản vá này,
						// `this.cho = null` ở đây bắt thủ kho quét LẠI tem lô trước khi
						// quét ô kế tiếp — trái với chính câu HDSD đã viết ("hệ TỰ lấy
						// đúng số ô còn ... Không cần sửa số tay"), và bước ② biến mất
						// khỏi màn hình đúng lúc thủ kho cần nó nhất. GIỮ nguyên lô/dòng
						// đang chờ (`dong_hang`/`so_lo` không đổi), chỉ cập nhật số lượng
						// = phần còn thiếu MỚI của dòng, và hạ `da_sua_so_luong` về
						// `false` — số này lại là MẶC ĐỊNH, cho phép ô kế tiếp tiếp tục
						// tự cắt theo tồn nếu cần. Gợi ý dưới ô quét (`ve()`) tự đọc
						// `this.cho` và hiện lại đúng bước ② (không phải bước ①).
						this.cho = {
							dong_hang: c.dong_hang,
							so_lo: c.so_lo,
							vat_tu: c.vat_tu,
							ten_hang: c.ten_hang,
							so_luong: flt(c.he_so) === 1 ? flt(con_lai_dong, 6) : Math.floor(con_lai_dong + 1e-9),
							lo_khac: null,
							da_sua_so_luong: false,
							don_vi: c.don_vi,
							he_so: c.he_so,
							so_kien: null,
						};
						this.bao(
							__("Ô <b>{0}</b> chỉ còn <b>{1}</b> {2} — đã lấy {1}, quét ô khác cho phần còn lại.", [
								e(o.ma_in_nhan || o.ma_o),
								so(da_ghi),
								e(dv_ghi),
							]),
							"cam"
						);
					} else {
						this.cho = null;
						this.bao(
							__("Đã lấy <b>{0} {1}</b> {2} ở <b>{3}</b>", [
								so(da_ghi),
								e(dv_ghi),
								e(c.so_lo || c.ten_hang || c.vat_tu || ""),
								e(o.ma_in_nhan || o.ma_o),
							]),
							"xanh"
						);
					}
					this.ve();
				})
				.catch(() => rung([80, 60, 80]))
				.finally(() => this.o_quet.giu_focus());
		}

		cong_tru(buoc) {
			if (!this.cho) return;
			this.cho.so_luong = Math.max(0, flt(this.cho.so_luong) + buoc);
			this.cho.da_sua_so_luong = true;
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
					${this.html_chon_don_vi()}
					<div class="lh-muc">
						<div class="lh-tieu-de-muc">${__("Số lượng lấy")}${c.don_vi ? ` · ${e(c.don_vi)}` : ""}</div>
						<div class="lh-so-luong-hang">
							<button type="button" class="lh-cong-tru" data-buoc="-1">−</button>
							<input type="number" class="lh-so-luong" inputmode="decimal" min="0" step="any"
								value="${flt(c.so_luong)}" />
							<button type="button" class="lh-cong-tru" data-buoc="1">+</button>
						</div>
					</div>
					<div class="lh-muc">
						<div class="lh-tieu-de-muc">${__("Số kiện (số tem)")}</div>
						<div class="lh-so-luong-hang">
							<button type="button" class="lh-kien-cong-tru" data-buoc="-1">−</button>
							<span class="lh-so-kien">${c.so_kien != null ? c.so_kien : this.so_kien_mac_dinh()}</span>
							<button type="button" class="lh-kien-cong-tru" data-buoc="1">+</button>
						</div>
					</div>
				</div>`;
		}

		// Hàng nút đơn vị theo quy đổi khai trên mặt hàng (`Item.uoms`). Chỉ một đơn
		// vị thì không vẽ — không có gì để chọn.
		html_chon_don_vi() {
			const c = this.cho;
			const dong = this.phieu.dong.find((x) => x.dong_hang === c.dong_hang);
			const ds = (dong && dong.don_vi_chon) || [];
			if (ds.length < 2) return "";
			return `
				<div class="lh-muc">
					<div class="lh-tieu-de-muc">${__("Đơn vị")}</div>
					<div class="lh-chon-don-vi-ds">
						${ds
							.map(
								(x) => `<button type="button" class="lh-chon-don-vi ${x.uom === c.don_vi ? "dang-chon" : ""}"
									data-uom="${e(x.uom)}">${e(x.uom)}${
									flt(x.he_so) !== 1 ? `<small> = ${so(x.he_so)} ${e(dong.don_vi_ton)}</small>` : ""
								}</button>`
							)
							.join("")}
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
						<div class="lh-mo">${e(
							// VÒNG SỬA CUỐI (review toàn nhánh): `ly_do_khong_quet` phân biệt
							// BA lý do (kho không quản lý vị trí, mặt hàng không tồn kho, dòng
							// đa đơn vị) — trước bản vá chỉ có đúng một câu chung chung, sai
							// be bét cho hai lý do còn lại. Vẫn giữ câu cũ làm dự phòng cho
							// bản ghi cũ (máy chủ chưa nâng cấp) không mang khoá này.
							d.ly_do_khong_quet || __("Kho không quản lý vị trí — lấy tay, không cần quét.")
						)}</div>
					</div>`;
			}

			const du = flt(d.da_lay_ton) >= flt(d.can_lay_ton) - 1e-9;
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
									)}</b> ${e(d.don_vi_ton)}</span>`
							)
							.join("")}
					</div>`
				: "";

			// Sửa lỗi "mở phiếu bật hộp lỗi": dòng cần nhiều hơn tồn của (mặt
			// hàng, lô) đang chốt — máy chủ (`mo_phieu_giao`) đã tự cắt gợi ý về
			// đúng phần LẤY ĐƯỢC (`o_nen_lay` ở trên) và trả riêng phần CÒN THIẾU
			// (`thieu_trong_lo`) — hiện một DÒNG CHỮ BÌNH THƯỜNG cho phần đó,
			// KHÔNG phải hộp lỗi (spec §6.2: màn mở phiếu phải mở được kể cả khi
			// không đủ hàng).
			const thieu_lo =
				flt(d.thieu_trong_lo) > 1e-9
					? `<div class="lh-thieu-lo">${
							d.so_lo
								? __("Lô {0} chỉ còn {1} — lấy hết rồi quét tem lô khác cho phần còn lại {2}.", [
										e(d.so_lo),
										// `thieu_trong_lo` đo bằng đơn vị TỒN — so với `*_ton`, không với `can_lay`.
										so(flt(d.can_lay_ton) - flt(d.da_lay_ton) - flt(d.thieu_trong_lo)) + " " + e(d.don_vi_ton),
										so(d.thieu_trong_lo) + " " + e(d.don_vi_ton),
								  ])
								: __("Kho chỉ còn {0} — lấy hết rồi báo thủ kho phần còn thiếu {1}.", [
										so(flt(d.can_lay_ton) - flt(d.da_lay_ton) - flt(d.thieu_trong_lo)) + " " + e(d.don_vi_ton),
										so(d.thieu_trong_lo) + " " + e(d.don_vi_ton),
								  ])
					  }</div>`
					: "";

			const da_lay_o = (d.da_lay_o || []).length
				? `<div class="lh-da-lay-ds">
						${d.da_lay_o
							.map(
								(p) => `
							<div class="lh-da-lay-dong">
								<span class="lh-ma">${e(p.ma_in_nhan || p.o)}</span>
								<span class="lh-da-lay-sl">${so(p.so_luong_lay)} ${e(p.don_vi_lay)} · ${__("{0} kiện", [
									p.so_kien,
								])}${p.so_kien_da_in >= p.so_kien ? " ✓" : ""}</span>
								<button type="button" class="lh-bo-luot" data-luot="${e(p.name)}" title="${__("Bỏ lượt")}">×</button>
							</div>`
							)
							.join("")}
					</div>`
				: "";

			// Lô NÊN lấy theo hạn dùng — chỉ gợi ý; lô trên phiếu vẫn là lô sẽ lấy.
			const lo_nen =
				d.lo_nen_lay && d.lo_nen_lay !== d.so_lo
					? `<div class="lh-mo">${__("Nên lấy lô {0}", [e(d.lo_nen_lay)])}${
							d.lo_nen_lay_hsd ? " · HSD " + e(frappe.datetime.str_to_user(d.lo_nen_lay_hsd)) : ""
					  }</div>${
							d.lo_tren_phieu_muon_hon
								? `<div class="lh-canh-bao-han">${__("Lô trên phiếu hết hạn muộn hơn lô {0}", [
										e(d.lo_nen_lay),
								  ])}</div>`
								: ""
					  }`
					: "";
			const khac_dv = d.don_vi_dong && d.don_vi_ton && d.don_vi_dong !== d.don_vi_ton;

			const nut_chot_thieu =
				!d.da_chot_thieu && flt(d.da_lay_ton) > 0 && flt(d.da_lay_ton) < flt(d.can_lay_ton) - 1e-9
					? `<button type="button" class="lh-chot-thieu" data-dong="${e(d.dong_hang)}">${__("Chốt thiếu")}</button>`
					: "";

			return `
				<div class="lh-dong ${du ? "lh-dong-du" : ""}">
					<div class="lh-dong-dau">
						<div class="lh-dong-ten">${e(d.ten_hang)}</div>
						<div class="lh-dong-sl">${so(d.da_lay)}/${so(d.can_lay)}<small>${e(d.don_vi || "")}</small>${
				khac_dv ? `<div class="lh-mo">${so(d.da_lay_ton)}/${so(d.can_lay_ton)} ${e(d.don_vi_ton)}</div>` : ""
			}</div>
					</div>
					<div class="lh-mo">${e(d.vat_tu)}${d.so_lo ? " · lô " + e(d.so_lo) : ""}${
				d.hsd ? " · HSD " + e(frappe.datetime.str_to_user(d.hsd)) : ""
			}</div>
					${lo_nen}
					${chot}
					${goi_y}
					${thieu_lo}
					${da_lay_o}
					${nut_chot_thieu}
				</div>`;
		}

		ve_chan_trang() {
			const $c = this.$goc.find(".lh-chan-trang");
			const dong = (this.phieu && this.phieu.dong) || [];
			const co_luot = dong.some((d) => flt(d.da_lay) > 0);
			if (!this.phieu || !co_luot) return $c.empty();
			// Máy in tem nối với máy tính — PDA chỉ báo trạng thái; thiếu tem thì
			// `hoan_tat` bị chặn (`lay_hang.chan_duyet_chua_lay`) với câu nói rõ.
			const tong = flt(this.phieu.tong_kien);
			const da_in = flt(this.phieu.so_kien_da_in);
			const tem = tong
				? `<div class="lh-trang-thai-tem ${da_in < tong ? "thieu" : ""}">${__("{0}/{1} kiện đã in tem", [
						da_in,
						tong,
				  ])}${da_in < tong ? " — " + __("in ở máy tính (form phiếu giao › In tem kiện)") : ""}</div>`
				: "";
			$c.html(`${tem}<button type="button" class="btn btn-primary lh-hoan-tat">${__("Hoàn tất phiếu")}</button>`);
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
