// Trang "Xếp hàng vào ô" — PDA của thủ kho.
//
// Chủ đầu tư, 17/09/2026: "giao diện xếp hàng cũng là pda … quét mã lô thì hiển
// thị ra mặt hàng và thực hiện xác nhận xếp, có thể xếp nhiều hàng trên 1 phiếu
// xếp Location Transfer". Chốt thêm cùng ngày: xác nhận bằng QUÉT TEM Ô trên kệ,
// số lượng mặc định cả phần đang chờ ở ô nguồn và sửa được. Luật 19/09/2026: lô
// CHỈ xếp được vào đúng ô in trên tem — tem chưa có ô thì đòi đặt ô trước
// (20/09/2026, thủ kho tự đặt ngay tại kệ).
//
// PHẦN QUYẾT ĐỊNH ("hai bước lô→ô", "ô có khớp ô trên tem không", "số lượng mặc
// định", nhãn và câu báo) KHÔNG còn nằm ở đây (Task 3, Bước 6 của brief app PDA
// `/kho`) — đã chuyển sang `luong/xep_hang.js`, CÙNG một file mà màn "Xếp hàng"
// của app PDA (`kho_pda/man_xep_hang.js`) dùng, để hai nơi không lệch luật. File
// này chỉ còn giữ TOÀN BỘ phần VẼ + hộp thoại xác nhận riêng của Desk (không nghe
// phím, cùng lý do `kho_pda/hop_thoai.js` — súng quét gửi Enter sau mỗi lần bắn).
//
// Máy chủ: `vitri/xep.py` + `vitri/o_tem.py` — lý do dòng lưu ngay, phiếu nháp
// theo từng người, và phép kiểm dòng nằm ở đó, xem docstring hai file.
//
// Ô quét dùng chung `public/js/warehouse_operations/o_quet.js`.
//
// Bọc IIFE: script trang Frappe chạy ở phạm vi toàn cục — xem `quet_ma_tra_cuu.js`.
(function () {
	const O_QUET = ["/assets/erpnext/js/warehouse_operations/o_quet.js", "/assets/erpnext/js/warehouse_operations/o_quet.css"];
	const LUONG_XEP_HANG = "/assets/erpnext/js/warehouse_operations/luong/xep_hang.js";

	frappe.pages["xep-hang-pda"].on_page_load = function (wrapper) {
		const page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Xếp hàng vào ô"),
			single_column: true,
		});
		// Nạp lớp LUỒNG trước — constructor bên dưới gọi
		// `erpnext.warehouse_operations.luong.xep_hang.tao(...)` ngay lập tức, đúng
		// tinh thần `quet_ma_tra_cuu.js` (Task 2, Bước 6).
		frappe.require(LUONG_XEP_HANG, () => {
			frappe.require(O_QUET, () => {
				wrapper.xep = new XepHangPda(page);
			});
		});
	};

	frappe.pages["xep-hang-pda"].on_page_show = function (wrapper) {
		// Quay lại trang (vd. vừa mở phiếu trên form rồi bấm Back): nạp lại phiếu —
		// có thể đã bị sửa hay duyệt ở nơi khác. `nap_lai()` KHÔNG đụng lô đang chờ
		// (`_luong.lam_moi()` chỉ đọc lại phiếu của đúng kho hiện tại).
		if (wrapper.xep) wrapper.xep.nap_lai();
	};

	class XepHangPda {
		constructor(page) {
			this.page = page;
			this.dang_gui = false;
			// Phần QUYẾT ĐỊNH — CÙNG một luồng mà màn "Xếp hàng" của app PDA dùng
			// (xem đầu file). `goi: frappe.xcall`: đúng nguyên văn Bước 6 của brief —
			// `frappe.xcall` đã tự hiện câu báo máy chủ cho lỗi quyền/mất mạng/ghi bị
			// từ chối, nên trang này không cần tự đọc `.message` của lỗi bị từ chối,
			// chỉ cần biết là ĐÃ hỏng để dừng đúng chỗ (giống hệt cách trang GỐC dùng
			// `frappe.xcall` trước khi tách lớp).
			this._luong = erpnext.warehouse_operations.luong.xep_hang.tao({ goi: frappe.xcall });
			// Bản sao ĐỌC của trạng thái luồng — làm mới bằng `_dong_bo()` ngay sau
			// MỌI lời gọi luồng, trước khi `ve()` đọc nó. Không đọc thẳng
			// `this._luong.trang_thai()` rải rác trong từng hàm vẽ vì `ve()` được gọi
			// nhiều lần trong một lượt xử lý (vd. sau khi cập nhật số lượng) — một bản
			// chụp duy nhất tránh vẽ hai lần với hai trạng thái khác nhau giữa chừng.
			this.st = this._luong.trang_thai();
			this.dung();
			this.nap_lai();
		}

		_dong_bo() {
			this.st = this._luong.trang_thai();
		}

		dung() {
			this.$goc = $(`
				<div class="xh">
					<div class="xh-dau-trang"></div>
					<div class="xh-cho-o-quet"></div>
					<div class="xh-thong-bao"></div>
					<div class="xh-dat-o"></div>
					<div class="xh-lo-dang-cho"></div>
					<div class="xh-danh-sach"></div>
					<div class="xh-chan-trang"></div>
				</div>
			`).appendTo(this.page.main);

			this.o_quet = new erpnext.warehouse_operations.OQuet({
				cha: this.$goc.find(".xh-cho-o-quet"),
				vung: this.$goc,
				placeholder: __("Quét tem…"),
				goi_y: "",
				khi_quet: (ma) => this.quet(ma),
			});

			this.$goc.on("click", ".xh-chon-kho", (ev) => this.chon_kho($(ev.currentTarget).attr("data-kho")));
			this.$goc.on("click", ".xh-nguon", (ev) => this.chon_nguon($(ev.currentTarget).attr("data-o")));
			this.$goc.on("click", ".xh-bo-lo", () => this.bo_lo());
			this.$goc.on("click", ".xh-dat-o-tem", () => this.bat_dau_dat_o());
			this.$goc.on("click", ".xh-huy-dat-o", () => this.huy_dat_o());
			this.$goc.on("click", ".xh-xoa-dong", (ev) => this.xoa_dong($(ev.currentTarget).attr("data-dong")));
			this.$goc.on("click", ".xh-hoan-tat", () => this.hoan_tat());
			this.$goc.on("click", ".xh-cong-tru", (ev) => this.cong_tru(Number($(ev.currentTarget).attr("data-buoc"))));
			this.$goc.on("input", ".xh-so-luong", (ev) => {
				// KHÔNG vẽ lại khi đang gõ (mất vị trí con trỏ) — chỉ cập nhật trạng
				// thái; `change` bên dưới vẽ lại lúc gõ xong để hiện giá trị đã kẹp.
				this._luong.dat_so_luong(ev.currentTarget.value);
				this._dong_bo();
			});
			this.$goc.on("change", ".xh-so-luong", (ev) => {
				this._luong.dat_so_luong(ev.currentTarget.value);
				this._dong_bo();
				this.ve();
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
			// Kho ĐÃ chọn: chỉ đọc lại phiếu của kho đó (`lam_moi()`, không đụng lô
			// đang chờ — đúng hành vi GỐC của `nap_lai()`, xem đầu file). Chưa chọn
			// kho (lần mở trang đầu tiên): để máy chủ tự chọn (`mo()`).
			const p = this.st.kho ? this._luong.lam_moi() : this._luong.mo(this.st.kho);
			return p.then((st) => {
				this.st = st;
				this.ve();
				this.o_quet.giu_focus();
			});
		}

		chon_kho(kho) {
			this.bao();
			if (!kho) {
				// Nút "Đổi": về màn chọn kho. KHÔNG nạp lại — không truyền kho thì máy
				// chủ tự chọn lại đúng kho vừa rời (kho của phiếu nháp gần nhất).
				this.st = this._luong.doi_kho();
				this.ve();
				return;
			}
			this._luong.mo(kho).then((st) => {
				this.st = st;
				this.ve();
				this.o_quet.giu_focus();
			});
		}

		quet(ma) {
			if (this.dang_gui) return;
			this.dang_gui = true;
			this._luong
				.quet(ma)
				.then((kq) => {
					this._dong_bo();
					rung(kq.buoc === "da_ghi" ? [40, 40, 40] : kq.muc === "do" ? [80, 60, 80, 60, 80] : [80, 60, 80]);
					if (kq.bao) this.bao(kq.bao, kq.muc);
					else this.bao();
					this.ve();
				})
				.catch(() => {
					// Máy chủ từ chối ghi (`them_dong_xep`/`doi_o_tren_tem` — ô nhóm,
					// ngừng dùng, không đủ hàng…): `frappe.xcall` đã tự hiện câu báo.
					// Trạng thái của luồng KHÔNG đổi khi lời gọi ghi thất bại (xem
					// `luong/xep_hang.js`), nên không cần đọc lại — chỉ báo rung.
					rung([80, 60, 80]);
				})
				.finally(() => {
					this.dang_gui = false;
					this.o_quet.giu_focus();
				});
		}

		bo_lo() {
			this.st = this._luong.bo_lo();
			this.bao();
			this.ve();
			this.o_quet.giu_focus();
		}

		chon_nguon(o) {
			this.st = this._luong.chon_nguon(o);
			this.ve();
			this.o_quet.giu_focus();
		}

		cong_tru(buoc) {
			if (!this.st.cho) return;
			this.st = this._luong.dat_so_luong(flt(this.st.cho.so_luong) + buoc);
			this.$goc.find(".xh-so-luong").val(this.st.cho.so_luong);
		}

		bat_dau_dat_o() {
			this.st = this._luong.bat_dau_dat_o();
			this.ve();
			this.o_quet.giu_focus();
		}

		huy_dat_o() {
			this.st = this._luong.huy_dat_o();
			this.bao();
			this.ve();
			this.o_quet.giu_focus();
		}

		xoa_dong(ten_dong) {
			const d = (this.st.dong || []).find((x) => x.name === ten_dong);
			if (!d) return;
			hoi({
				noi_dung: __("Bỏ dòng <b>{0}</b> · {1} → {2} khỏi phiếu?", [
					e(d.so_lo || d.ten_hang),
					so(d.so_luong),
					e(d.den_o),
				]),
				nhan: __("Bỏ dòng"),
				khi_dong_y: () =>
					this._luong
						.xoa_dong(ten_dong)
						.then((st) => {
							this.st = st;
							// Soát xét vòng 1, mục 5: câu + mức màu là quyết định CỦA LUỒNG
							// (`st.bao`/`st.muc`), không phải lớp vẽ tự gõ riêng nữa.
							this.bao(st.bao, st.muc);
							this.ve();
						})
						.catch(() => {
							// `frappe.xcall` đã hiện lỗi của máy chủ — nạp lại để chắc chắn
							// đúng trạng thái (Desk gốc KHÔNG có `.catch()` ở đây, một lỗ hổng
							// nhỏ đã sửa: không bắt thì promise bị từ chối không ai xử lý).
							this.nap_lai();
						})
						.finally(() => this.o_quet.giu_focus()),
				khi_dong: () => this.o_quet.giu_focus(),
			});
		}

		hoan_tat() {
			if (!this.st.phieu || !this.st.phieu.dong.length) return;
			const ten = this.st.phieu.name;
			const so_dong = this.st.phieu.dong.length;
			hoi({
				noi_dung: __("Ghi phiếu <b>{0}</b> ({1} dòng) vào sổ vị trí? Sau khi ghi, tồn theo ô đổi ngay.", [
					e(ten),
					so_dong,
				]),
				nhan: __("Ghi phiếu"),
				khi_dong_y: () => {
					this.dang_gui = true;
					this._luong
						.duyet()
						.then((kq) => {
							rung([40, 40, 40]);
							this._dong_bo();
							// SOÁT XÉT VÒNG 1 (Task 3, mục 4): liên kết "Xem phiếu" TRẢ LẠI —
							// bỏ nó ở vòng trước là một lần cắt giảm lén một tính năng đang
							// chạy trên Desk, không phải hệ quả bắt buộc của việc gộp lớp.
							// KHÔNG đi qua `bao()` chung (nó escape TOÀN BỘ `chu`, sẽ biến thẻ
							// `<a>` thành chữ): `_bao_voi_lien_ket()` tự tô đậm `kq.bao` (quy
							// ước `**…**`, xem `_dam()`) rồi TỰ ghép thêm một liên kết do
							// CHÍNH TA dựng (href từ `kq.ten` — tên tài liệu do máy chủ sinh,
							// vẫn escape phòng hờ) — không phải nhét thẳng HTML của `kq.bao`.
							this._bao_voi_lien_ket(
								kq.bao,
								kq.muc,
								`/app/location-transfer/${encodeURIComponent(kq.ten)}`,
								__("Xem phiếu")
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

		giu_focus() {
			this.o_quet && this.o_quet.giu_focus();
		}

		// ------------------------------------------------------------------ vẽ

		// `chu` là CHỮ THƯỜNG có quy ước `**…**` (không phải HTML thô) — kể từ Task 3,
		// `bao()` LUÔN escape TRƯỚC, CÙNG hợp đồng với `KhoApp.bao()` của app PDA
		// (`vo.js`). SOÁT XÉT VÒNG 1 (mục 3): trả lại tô đậm bằng `_dam()` — escape
		// toàn bộ `chu` RỒI MỚI đổi `**x**` (do lớp luồng tự đánh dấu) thành
		// `<b>x</b>` CỦA RIÊNG hàm này; máy chủ không có cách nào nhét được một thẻ
		// HTML thật qua `chu` (mọi `<`/`>` trong dữ liệu đã bị escape trước khi ta
		// tự thêm `<b>` của mình).
		bao(chu, muc) {
			const $tb = this.$goc.find(".xh-thong-bao");
			if (!chu) return $tb.empty();
			$tb.html(`<div class="xh-bao muc-${muc || "xam"}">${_dam(chu)}</div>`);
		}

		// Ca DUY NHẤT `bao()` không đủ: banner thành công sau `duyet()` cần thêm một
		// liên kết THẬT (`<a>`) — không phải chữ tô đậm. `href`/`nhan` do CHÍNH
		// PHƯƠNG THỨC NÀY dựng (không lấy nguyên văn từ `kq.bao`), vẫn escape phòng
		// hờ trước khi ghép.
		_bao_voi_lien_ket(chu, muc, href, nhan) {
			const $tb = this.$goc.find(".xh-thong-bao");
			$tb.html(
				`<div class="xh-bao muc-${muc || "xam"}">${_dam(chu)} <a href="${e(href)}">${e(nhan)}</a></div>`
			);
		}

		ve() {
			this.ve_dau_trang();
			this.ve_dat_o();
			this.ve_lo_dang_cho();
			this.ve_danh_sach();
			this.ve_chan_trang();
			const g = this.st.goi_y_o_quet;
			this.o_quet.dat_goi_y(g.chu, g.nhan_manh ? "nhan-manh" : undefined);
		}

		ve_dau_trang() {
			const $d = this.$goc.find(".xh-dau-trang");
			if (!this.st.kho_ds.length) {
				$d.html(`<div class="xh-bao muc-cam">${__("Chưa kho nào bật quản lý vị trí.")}</div>`);
				return;
			}
			if (!this.st.kho) {
				$d.html(`
					<div class="xh-tieu-de-muc">${__("Chọn kho")}</div>
					<div class="xh-chon-kho-ds">
						${this.st.kho_ds
							.map((k) => `<button type="button" class="xh-chon-kho" data-kho="${e(k)}">${e(k)}</button>`)
							.join("")}
					</div>`);
				return;
			}
			const doi_kho =
				this.st.kho_ds.length > 1 && !this.st.cho
					? `<button type="button" class="xh-lien-ket-nho xh-chon-kho" data-kho="">${__("Đổi")}</button>`
					: "";
			const phieu = this.st.phieu
				? `<a class="xh-ma-phieu" href="/app/location-transfer/${encodeURIComponent(
						this.st.phieu.name
				  )}">${e(this.st.phieu.name)}</a>`
				: `<span class="xh-mo">${__("phiếu mới")}</span>`;
			$d.html(`
				<div class="xh-kho">
					<span class="xh-mo">${__("Kho")}</span> <b>${e(this.st.kho)}</b> ${doi_kho}
					<span class="xh-cham">·</span> ${phieu}
				</div>`);
		}

		// Thẻ RIÊNG cho "chờ đặt ô trên tem" — TÁCH khỏi `bao()` (soát xét Task 3):
		// nút "Đặt ô trên tem" từng ghép thẳng vào chuỗi `bao()` (`t.loi + nut`) khi
		// lớp vẽ tự quyết cả câu lẫn nút cùng lúc; nay lớp luồng chỉ trả CHỮ THƯỜNG
		// (`kq.bao`) và một cờ RIÊNG (`can_xac_nhan`/`trang_thai().o_tren_tem`) —
		// ghép chúng lại thành một chuỗi HTML là việc của lớp vẽ, không phải luồng.
		ve_dat_o() {
			const $k = this.$goc.find(".xh-dat-o");
			const o = this.st.o_tren_tem;
			if (!o) return $k.empty();
			if (o.dang_cho_quet) {
				$k.html(`
					<div class="xh-the xh-the-dat-o">
						<span class="xh-nhan-loai loai-o">${__("Đang chờ quét ô")}</span>
						<div class="xh-ma-to">${e(o.so_lo || o.ten_hang)}</div>
						<div class="xh-mo">${__("Quét tem Ô muốn đặt lên tem lô này.")}</div>
						<button type="button" class="xh-lien-ket-nho xh-huy-dat-o">${__("Huỷ")}</button>
					</div>`);
				return;
			}
			$k.html(`
				<div class="xh-the xh-the-dat-o">
					<span class="xh-nhan-loai loai-o">${__("Chưa có ô trên tem")}</span>
					<div class="xh-ma-to">${e(o.so_lo || o.ten_hang)}</div>
					<button type="button" class="xh-nut-trong-bao xh-dat-o-tem">${__("Đặt ô trên tem")}</button>
				</div>`);
		}

		ve_lo_dang_cho() {
			const $c = this.$goc.find(".xh-lo-dang-cho");
			const c = this.st.cho;
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
						<div class="xh-nhan">${g.theo_tem ? __("Xếp vào ô trên tem — bắt buộc") : __("Ô gợi ý")}</div>
						<div class="xh-goi-y-o">${e(g.ma_in_nhan || g.den_o)}</div>
						${g.ly_do ? `<div class="xh-mo">${e(g.ly_do)}</div>` : ""}
					</div>`
				: `<div class="xh-goi-y trong">
						<div class="xh-nhan">${__("Chưa có ô gợi ý — quét tem ô định xếp")}</div>
						${g.ly_do ? `<div class="xh-mo">${e(g.ly_do)}</div>` : ""}
					</div>`;
			const n = (c.nguon || []).find((x) => x.o === c.tu_o);
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

					<div class="xh-muc">${goi_y}</div>
				</div>`);
		}

		ve_danh_sach() {
			const $ds = this.$goc.find(".xh-danh-sach");
			const dong = this.st.dong || [];
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
			const so_dong = (this.st.dong || []).length;
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

	// Mirror của `vo.js::_dam()` (app PDA) — Desk không dùng `KhoApp`, nên giữ một
	// bản riêng, cùng khuôn: escape TOÀN BỘ trước, RỒI MỚI đổi `**x**` (quy ước lớp
	// luồng tự đánh dấu) thành `<b>x</b>` CỦA RIÊNG hàm này. Xem lý do đầy đủ ở
	// `vo.js`.
	function _dam(chu) {
		return e(chu).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
	}

	function rung(mau) {
		try {
			navigator.vibrate && navigator.vibrate(mau);
		} catch (err) {
			// Trình duyệt chặn rung — không sao.
		}
	}
})();
