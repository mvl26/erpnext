// Trang "Lấy hàng" — PDA của thủ kho.
//
// Chủ đầu tư 18/09/2026 chọn bản đầy đủ: quét tem lô + tem ô để XÁC NHẬN đã lấy,
// và sổ vị trí trừ ĐÚNG ô đã quét (qua bảng phân bổ `Location Allocation`), thay
// vì ô do FEFO tự chọn lúc duyệt phiếu giao.
//
// PHẦN QUYẾT ĐỊNH ("quét mã này thì làm gì", "lô hết hạn có lấy được không", "đổi
// lô hay tách dòng", "số lượng/đơn vị/số kiện mặc định", nhãn và câu báo) KHÔNG còn
// nằm ở đây (Task 4, Bước 6 của brief app PDA `/kho`) — đã chuyển sang
// `luong/lay_hang.js`, CÙNG một file mà màn "Lấy hàng" của app PDA
// (`kho_pda/man_lay_hang.js`) dùng, để hai nơi không lệch luật. File này chỉ còn
// giữ TOÀN BỘ phần VẼ + hộp thoại xác nhận riêng của Desk (không nghe phím, cùng lý
// do `kho_pda/hop_thoai.js` — súng quét gửi Enter sau mỗi lần bắn).
//
// Máy chủ: `vitri/lay_hang.py` — lý do ghi ngay từng lượt, cờ "chốt thiếu" và các
// phép kiểm nằm ở đó, xem docstring file đó.
//
// Bọc IIFE và KHÔNG dùng `frappe.confirm` — xem `hoi()` ở cuối file.
(function () {
	const O_QUET = ["/assets/erpnext/js/warehouse_operations/o_quet.js", "/assets/erpnext/js/warehouse_operations/o_quet.css"];
	const LUONG_LAY_HANG = "/assets/erpnext/js/warehouse_operations/luong/lay_hang.js";

	frappe.pages["lay-hang-pda"].on_page_load = function (wrapper) {
		const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Lấy hàng"), single_column: true });
		// Nạp lớp LUỒNG trước — constructor bên dưới gọi
		// `erpnext.warehouse_operations.luong.lay_hang.tao(...)` ngay lập tức, đúng
		// tinh thần `xep_hang_pda.js` (Task 3, Bước 6).
		frappe.require(LUONG_LAY_HANG, () => {
			frappe.require(O_QUET, () => {
				wrapper.lay_hang = new LayHangPda(page);
			});
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
			// Phần QUYẾT ĐỊNH — CÙNG một luồng mà màn "Lấy hàng" của app PDA dùng.
			// `goi: frappe.xcall` — `frappe.xcall` đã tự hiện câu báo máy chủ cho lỗi
			// quyền/mất mạng/ghi bị từ chối, nên trang này không cần tự đọc `.message`
			// của lỗi, chỉ cần biết là ĐÃ hỏng để dừng đúng chỗ (giống hệt cách trang
			// GỐC dùng `frappe.xcall` trước khi tách lớp). `ngay` — định dạng ngày theo
			// thói quen người dùng Desk; xem lý do tiêm ở đầu `luong/lay_hang.js`.
			this._luong = erpnext.warehouse_operations.luong.lay_hang.tao({
				goi: frappe.xcall,
				ngay: (gia_tri) => frappe.datetime.str_to_user(gia_tri),
			});
			// Bản sao ĐỌC của trạng thái luồng — làm mới bằng `_dong_bo()` ngay sau MỌI
			// lời gọi luồng, trước khi `ve()` đọc nó (cùng khuôn `xep_hang_pda.js`).
			this.st = this._luong.trang_thai();
			// Phiếu đã mở theo đường dẫn lần gần nhất — để Back từ form về cùng đường
			// dẫn thì chỉ nạp lại, không kéo thủ kho khỏi phiếu/danh sách đang xem.
			this.phieu_theo_duong_dan = null;
			this.dung();
			this.theo_duong_dan();
		}

		_dong_bo() {
			this.st = this._luong.trang_thai();
		}

		// Nút "Lấy hàng trên PDA" trên form Phiếu giao đưa tới `/app/lay-hang-pda/<phiếu>`
		// (`public/js/warehouse_operations/delivery_note.js`): mở thẳng phiếu đó.
		theo_duong_dan() {
			const ten = frappe.get_route()[1];
			if (!ten || ten === this.phieu_theo_duong_dan) return this.nap_lai();
			this.phieu_theo_duong_dan = ten;
			return this._luong
				.mo(ten)
				.then((st) => {
					this.st = st;
					// `bao` chỉ có khi phiếu đã duyệt/huỷ — CÂU CHỮ của luồng, không phải
					// của trang (bản gốc tự gõ "Phiếu {0} đã {1} …" ở đây).
					if (st.bao) {
						this.bao(st.bao, st.muc);
						return this.nap_lai();
					}
					this.bao();
					this.ve();
					this.o_quet.giu_focus();
				})
				.catch(() => {
					// Máy chủ đã hiện câu báo (không có quyền, phiếu không tồn tại…).
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
			this.$goc.on("click", ".lh-ve-danh-sach", () => this.ve_danh_sach());
			this.$goc.on("click", ".lh-bo-luot", (ev) => this.bo_luot($(ev.currentTarget).attr("data-luot")));
			this.$goc.on("click", ".lh-chot-thieu", (ev) => this.chot_thieu($(ev.currentTarget).attr("data-dong")));
			this.$goc.on("click", ".lh-bo-chot-thieu", (ev) => this.bo_chot_thieu($(ev.currentTarget).attr("data-dong")));
			this.$goc.on("click", ".lh-hoan-tat", () => this.hoan_tat());
			this.$goc.on("click", ".lh-xac-nhan-lo-khac", () => this.xac_nhan_lo_khac());
			this.$goc.on("click", ".lh-bo-lo", () => this.bo_lo());
			this.$goc.on("click", ".lh-cong-tru", (ev) => this.cong_tru(Number($(ev.currentTarget).attr("data-buoc"))));
			this.$goc.on("click", ".lh-chon-don-vi", (ev) => this.chon_don_vi($(ev.currentTarget).attr("data-uom")));
			this.$goc.on("click", ".lh-kien-cong-tru", (ev) =>
				this.kien_cong_tru(Number($(ev.currentTarget).attr("data-buoc")))
			);
			this.$goc.on("input change", ".lh-so-luong", (ev) => {
				// `dat_so_luong` của luồng tự bật cờ "người dùng đã sửa" — từ đó `ghi()`
				// không còn được âm thầm cắt số này theo tồn của ô.
				this._luong.dat_so_luong(ev.currentTarget.value);
				this._dong_bo();
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
			return this._luong
				.lam_moi()
				.then((st) => {
					this.st = st;
					this.ve();
					this.o_quet.giu_focus();
				})
				.catch(() => {
					// `frappe.xcall` đã hiện câu báo của máy chủ; vẫn vẽ lại để màn hình
					// không đứng im ở một trạng thái không còn đúng.
					this._dong_bo();
					this.ve();
				});
		}

		chon_kho(kho) {
			this.bao();
			if (!kho) {
				// Nút "Đổi": về màn chọn kho. KHÔNG nạp lại — không truyền kho thì máy
				// chủ tự chọn lại đúng kho vừa rời khi chỉ có một kho quản lý vị trí.
				this.st = this._luong.doi_kho();
				this.ve();
				return;
			}
			this._luong
				.danh_sach(kho)
				.then((st) => {
					this.st = st;
					this.ve();
					this.o_quet.giu_focus();
				})
				.catch(() => this.nap_lai());
		}

		ve_danh_sach() {
			this.phieu_theo_duong_dan = null;
			const co_ten_tren_duong_dan = !!frappe.get_route()[1];
			this.bao();
			// Rời phiếu Ở LỚP LUỒNG TRƯỚC, đổi đường dẫn SAU. Bản gốc đặt `this.phieu =
			// null` rồi mới `frappe.set_route` — thứ tự đó là bắt buộc và dễ mất khi gộp
			// lớp: `set_route` kích `on_page_show` → `theo_duong_dan()` → `nap_lai()`,
			// mà `nap_lai()` hỏi LUỒNG xem có phiếu nào đang mở không. Đổi đường dẫn
			// trước thì luồng vẫn còn giữ phiếu vừa rời và màn hình quay lại đúng nó —
			// nút "← Danh sách" thành nút không làm gì.
			this._luong
				.ve_danh_sach()
				.then((st) => {
					this.st = st;
					this.ve();
					this.o_quet.giu_focus();
					// Bỏ tên phiếu khỏi đường dẫn — nếu không, F5 hay Back sẽ mở lại đúng
					// phiếu vừa rời.
					if (co_ten_tren_duong_dan) frappe.set_route("lay-hang-pda");
				})
				.catch(() => this.nap_lai());
		}

		mo_phieu(ten) {
			this.bao();
			this._luong
				.mo(ten)
				.then((st) => {
					this.st = st;
					if (st.bao) this.bao(st.bao, st.muc);
					this.ve();
					this.o_quet.giu_focus();
				})
				.catch(() => this.nap_lai());
		}

		quet(ma) {
			this._luong
				.quet(ma)
				.then((kq) => {
					this._dong_bo();
					this.rung_theo(kq);
					if (kq.bao) this.bao(kq.bao, kq.muc);
					else this.bao();
					this.ve();
					if (kq.nap_lai) return this.nap_lai();
				})
				.catch(() => {
					// Máy chủ từ chối ghi (`ghi_da_lay` — ô chỉ còn N, ô ngừng dùng…):
					// `frappe.xcall` đã tự hiện câu báo. Trạng thái của luồng KHÔNG đổi khi
					// lời gọi ghi thất bại (xem `luong/lay_hang.js`), nên không cần đọc lại
					// — chỉ báo rung.
					rung([80, 60, 80]);
				})
				.finally(() => this.o_quet.giu_focus());
		}

		// Nút "Đổi sang lô …": trang CHỈ nói "người dùng đồng ý". `doi_lo` hay
		// `tach_dong_theo_lo` là quyết định của LỚP LUỒNG — luật đắt nhất của màn, và
		// là lý do nó không được nằm ở đây nữa (bản gốc tự chọn tên hàm ngay trong
		// `nhan_lo_khac`, mỗi lớp vẽ một bản).
		xac_nhan_lo_khac() {
			this._luong
				.xac_nhan_doi_lo()
				.then((kq) => {
					this._dong_bo();
					this.rung_theo(kq);
					if (kq.bao) this.bao(kq.bao, kq.muc);
					this.ve();
					if (kq.nap_lai) return this.nap_lai();
				})
				.catch(() => {
					rung([80, 60, 80]);
					return this.nap_lai();
				})
				.finally(() => this.o_quet.giu_focus());
		}

		bo_lo() {
			this.st = this._luong.bo_lo();
			this.bao();
			this.ve();
			this.o_quet.giu_focus();
		}

		chon_don_vi(uom) {
			this.st = this._luong.dat_don_vi(uom);
			this.ve();
			this.o_quet.giu_focus();
		}

		cong_tru(buoc) {
			if (!this.st.cho) return;
			this.st = this._luong.dat_so_luong(flt(this.st.cho.so_luong) + buoc);
			// Cập nhật TẠI CHỖ, không vẽ lại cả thẻ: vẽ lại làm mất focus và nhấp nháy
			// đúng lúc thủ kho đang bấm liên tiếp.
			this.$goc.find(".lh-so-luong").val(this.st.cho ? this.st.cho.so_luong : 0);
			this.$goc.find(".lh-so-kien").text(this.st.cho ? this.st.cho.so_kien : "");
		}

		kien_cong_tru(buoc) {
			if (!this.st.cho) return;
			this.st = this._luong.dat_so_kien(flt(this.st.cho.so_kien) + buoc);
			this.$goc.find(".lh-so-kien").text(this.st.cho ? this.st.cho.so_kien : "");
		}

		/** Một thao tác GHI có hộp xác nhận. `chuan_bi()` tự NẠP LẠI phiếu từ máy chủ
		 * rồi mới trả câu hỏi — màn GHI không được hỏi "bỏ lượt 5 Hộp ở ô 1A01?" dựa
		 * trên một ảnh chụp cũ (ràng buộc riêng của Task 4). */
		hoi_roi_lam(chuan_bi, lam, khi_xong) {
			chuan_bi()
				.then((h) => {
					this._dong_bo();
					this.ve();
					if (!h.ok) {
						this.bao(h.bao, h.muc || "cam");
						this.o_quet.giu_focus();
						return;
					}
					hoi({
						noi_dung: e(h.cau),
						// NHÃN NÚT cũng là câu chữ của LUỒNG (`h.nhan`), cùng lẽ với
						// `lo_khac.nhan_nut` — trang không tự gõ nữa.
						nhan: h.nhan || __("Đồng ý"),
						khi_dong_y: () =>
							lam()
								.then((kq) => {
									this._dong_bo();
									this.rung_theo(kq);
									if (khi_xong) khi_xong(kq);
									else if (kq.bao) this.bao(kq.bao, kq.muc);
									this.ve();
								})
								.catch(() => {
									rung([80, 60, 80]);
									return this.nap_lai();
								})
								.finally(() => this.o_quet.giu_focus()),
						khi_dong: () => this.o_quet.giu_focus(),
					});
				})
				.catch(() => {
					rung([80, 60, 80]);
					this.o_quet.giu_focus();
				});
		}

		bo_luot(ten) {
			this.hoi_roi_lam(
				() => this._luong.hoi_bo_luot(ten),
				() => this._luong.bo_luot(ten)
			);
		}

		chot_thieu(dong_hang) {
			this.hoi_roi_lam(
				() => this._luong.hoi_chot_thieu(dong_hang),
				() => this._luong.chot_thieu(dong_hang)
			);
		}

		bo_chot_thieu(dong_hang) {
			this._luong
				.bo_chot_thieu(dong_hang)
				.then((kq) => {
					this._dong_bo();
					this.bao(kq.bao, kq.muc);
					this.ve();
				})
				.catch(() => this.nap_lai())
				.finally(() => this.o_quet.giu_focus());
		}

		hoan_tat() {
			this.hoi_roi_lam(
				() => this._luong.hoi_hoan_tat(),
				() =>
					this._luong.hoan_tat().then((kq) =>
						// Sau khi duyệt, phiếu không còn — nạp lại danh sách để thủ kho đi
						// tiếp phiếu sau, GIỮ kết quả của luồng cho lượt vẽ này. KHÔNG đụng
						// `phieu_theo_duong_dan`: giữ nguyên hành vi bản gốc (quay lại trang
						// bằng Back chỉ nạp lại, không mở lại phiếu vừa duyệt).
						this._luong.danh_sach().then(() => kq)
					),
				// SOÁT XÉT TASK 3 (mục 4): liên kết "Xem phiếu" của bản Desk phải SỐNG
				// SÓT qua lần gộp lớp này. Không đi qua `bao()` chung (nó escape TOÀN BỘ
				// `chu`, sẽ biến thẻ `<a>` thành chữ): `bao_voi_lien_ket()` tô đậm
				// `kq.bao` theo quy ước `**…**` rồi TỰ ghép một liên kết do CHÍNH TA
				// dựng (href từ `kq.ten` — tên tài liệu do máy chủ sinh, vẫn escape).
				(kq) =>
					this.bao_voi_lien_ket(
						kq.bao,
						kq.muc,
						`/app/delivery-note/${encodeURIComponent(kq.ten)}`,
						__("Xem phiếu")
					)
			);
		}

		// ------------------------------------------------------------------ vẽ

		rung_theo(kq) {
			if (kq.muc === "xanh") return rung([40, 40, 40]);
			if (kq.muc === "do") return rung([120, 80, 120]);
			if (kq.muc === "cam") return rung([80, 60, 80]);
		}

		// `chu` là CHỮ THƯỜNG có quy ước `**…**` (không phải HTML thô) — `bao()` LUÔN
		// escape TRƯỚC, CÙNG hợp đồng với `KhoApp.bao()` của app PDA (`vo.js`), rồi mới
		// đổi `**x**` thành `<b>x</b>` CỦA RIÊNG nó. Máy chủ không có cách nào nhét một
		// thẻ HTML thật qua `chu`.
		bao(chu, muc) {
			const $tb = this.$goc.find(".lh-thong-bao");
			if (!chu) return $tb.empty();
			$tb.html(`<div class="lh-bao muc-${muc || "xam"}">${_dam(chu)}</div>`);
		}

		// Ca DUY NHẤT `bao()` không đủ: banner sau khi duyệt cần thêm một liên kết
		// THẬT tới phiếu vừa duyệt. Bản gốc có nó (`<a href='/app/delivery-note/…'>`);
		// Task 3 từng ĐÁNH RƠI đúng loại liên kết này lúc gộp lớp — gộp lớp không được
		// phép là một lần cắt tính năng đang chạy. `href`/`nhan` do CHÍNH phương thức
		// này dựng (không lấy nguyên văn từ `kq.bao`), vẫn escape phòng hờ.
		bao_voi_lien_ket(chu, muc, href, nhan) {
			const $tb = this.$goc.find(".lh-thong-bao");
			$tb.html(`<div class="lh-bao muc-${muc || "xam"}">${_dam(chu)} <a href="${e(href)}">${e(nhan)}</a></div>`);
		}

		ve() {
			this.ve_dau_trang();
			this.ve_than();
			this.ve_chan_trang();
			const g = this.st.goi_y_o_quet;
			this.o_quet.dat_goi_y(g.chu, g.nhan_manh ? "nhan-manh" : undefined);
		}

		ve_dau_trang() {
			const $d = this.$goc.find(".lh-dau-trang");
			if (this.st.khong_co_kho) {
				$d.html(`<div class="lh-bao muc-cam">${__("Chưa kho nào bật quản lý vị trí.")}</div>`);
				return;
			}
			if (this.st.hien_chon_kho) {
				$d.html(`
					<div class="lh-tieu-de-muc">${__("Chọn kho")}</div>
					<div class="lh-chon-kho-ds">
						${this.st.kho_ds
							.map((k) => `<button type="button" class="lh-chon-kho" data-kho="${e(k)}">${e(k)}</button>`)
							.join("")}
					</div>`);
				return;
			}
			const doi_kho = this.st.hien_doi_kho
				? `<button type="button" class="lh-lien-ket-nho lh-chon-kho" data-kho="">${__("Đổi")}</button>`
				: "";
			const ve_ds = this.st.phieu
				? `<button type="button" class="lh-lien-ket-nho lh-ve-danh-sach">${__("← Danh sách")}</button>`
				: "";
			const phieu = this.st.phieu
				? `<span class="lh-cham">·</span>
					<a class="lh-ma-phieu" href="/app/delivery-note/${encodeURIComponent(this.st.phieu.name)}">${e(
						this.st.phieu.name
				  )}</a>
					<span class="lh-mo">${e(this.st.phieu.khach_hang || "")}</span>`
				: "";
			$d.html(`
				<div class="lh-kho">
					<span class="lh-mo">${__("Kho")}</span> <b>${e(this.st.kho)}</b> ${doi_kho}
					${phieu}
					${ve_ds}
				</div>`);
		}

		ve_than() {
			const $t = this.$goc.find(".lh-than");
			if (!this.st.kho) return $t.empty();
			if (!this.st.phieu) return this.ve_danh_sach_phieu($t);
			$t.html(this.html_lo_dang_cho() + this.html_dong_hang());
		}

		ve_danh_sach_phieu($t) {
			const ds = this.st.ds_phieu || [];
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

		// Thẻ "lô khác lô đang chốt" — mọi kết luận (câu giải thích, có cảnh báo hạn
		// không, nhãn nút) đọc thẳng từ `st.lo_khac`; trang không tự dựng câu nào.
		html_lo_dang_cho() {
			const lk = this.st.lo_khac;
			if (lk) {
				return `
					<div class="lh-o-khac">
						<div>${_dam(lk.cau)}</div>
						${lk.canh_bao ? `<div class="lh-canh-bao-han">${e(lk.canh_bao)}</div>` : ""}
						<div class="lh-mo">${e(lk.nhac)}</div>
						<button type="button" class="lh-xac-nhan-lo-khac">${e(lk.nhan_nut)}</button>
					</div>`;
			}
			const c = this.st.cho;
			if (!c) return "";
			// `so_lo` là `null` cho mặt hàng không quản lý lô — hiện tên hàng thay cho
			// một mã lô không tồn tại, KHÔNG dùng phông đều `.lh-ma-to` cho chữ thường
			// (quy tắc chỉ dành phông đều cho mã ô/mã lô).
			return `
				<div class="lh-the">
					<div class="lh-the-dau">
						<div class="lh-dong-tren">
							<span class="lh-nhan-loai">${c.so_lo ? __("Đang lấy lô") : __("Đang lấy hàng (không lô)")}</span>
							<button type="button" class="lh-lien-ket-nho lh-bo-lo">${__("Bỏ lô này")}</button>
						</div>
						${
							c.so_lo
								? `<div class="lh-ma-to">${e(c.so_lo)}</div>`
								: `<div class="lh-ten-hang">${e(c.ten_hang || c.vat_tu)}</div>`
						}
					</div>
					${this.html_chon_don_vi(c)}
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
							<span class="lh-so-kien">${e(c.so_kien)}</span>
							<button type="button" class="lh-kien-cong-tru" data-buoc="1">+</button>
						</div>
					</div>
				</div>`;
		}

		// Hàng nút đơn vị theo quy đổi khai trên mặt hàng. `hien_chon_don_vi` là kết
		// luận của luồng ("dưới hai lựa chọn thì không có gì để chọn").
		html_chon_don_vi(c) {
			if (!c.hien_chon_don_vi) return "";
			return `
				<div class="lh-muc">
					<div class="lh-tieu-de-muc">${__("Đơn vị")}</div>
					<div class="lh-chon-don-vi-ds">
						${c.don_vi_chon
							.map(
								(x) => `<button type="button" class="lh-chon-don-vi ${x.uom === c.don_vi ? "dang-chon" : ""}"
									data-uom="${e(x.uom)}">${e(x.uom)}${
									flt(x.he_so) !== 1 ? `<small> = ${so(x.he_so)} ${e(c.don_vi_ton)}</small>` : ""
								}</button>`
							)
							.join("")}
					</div>
				</div>`;
		}

		html_dong_hang() {
			const dong = this.st.dong || [];
			return `
				<div class="lh-tieu-de-muc lh-tieu-de-ds">${__("Các dòng hàng · {0}", [dong.length])}</div>
				${dong.map((d) => this.html_mot_dong(d)).join("")}`;
		}

		// MỌI kết luận đã có sẵn trên `d` (`du`, `ly_do_khong_quet`,
		// `hien_nut_chot_thieu`, `banner_chot_thieu`, `cau_thieu_trong_lo`,
		// `cau_lo_nen_lay`, `canh_bao_han`, `khac_don_vi`, `hsd_chu`) — vẽ, không nghĩ.
		// Bản gốc tính tất cả những thứ này ngay trong hàm vẽ, kể cả một câu dự phòng
		// tự gõ khi máy chủ không trả `ly_do_khong_quet`; đúng hình dạng lỗi mà Task 2
		// từng trượt (`kq.du_lieu || {loai: null}`).
		html_mot_dong(d) {
			if (d.ly_do_khong_quet) {
				return `
					<div class="lh-dong lh-dong-mo">
						<div class="lh-dong-dau">
							<div class="lh-dong-ten">${e(d.ten_hang)}</div>
							<div class="lh-dong-sl">${so(d.da_lay)}/${so(d.can_lay)}<small>${e(d.don_vi || "")}</small></div>
						</div>
						<div class="lh-mo">${e(d.vat_tu)}${d.so_lo ? " · lô " + e(d.so_lo) : ""}</div>
						<div class="lh-mo">${e(d.ly_do_khong_quet)}</div>
					</div>`;
			}

			const chot = d.banner_chot_thieu
				? `<div class="lh-chot-banner">
						<div>${_dam(d.banner_chot_thieu)}</div>
						<button type="button" class="lh-bo-chot-thieu" data-dong="${e(d.dong_hang)}">${__("Bỏ chốt thiếu")}</button>
					</div>`
				: "";

			const goi_y = d.o_nen_lay.length
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

			const thieu_lo = d.cau_thieu_trong_lo ? `<div class="lh-thieu-lo">${e(d.cau_thieu_trong_lo)}</div>` : "";

			const da_lay_o = d.da_lay_o.length
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

			const lo_nen = d.cau_lo_nen_lay
				? `<div class="lh-mo">${e(d.cau_lo_nen_lay)}</div>${
						d.canh_bao_han ? `<div class="lh-canh-bao-han">${e(d.canh_bao_han)}</div>` : ""
				  }`
				: "";

			const nut_chot_thieu = d.hien_nut_chot_thieu
				? `<button type="button" class="lh-chot-thieu" data-dong="${e(d.dong_hang)}">${__("Chốt thiếu")}</button>`
				: "";

			return `
				<div class="lh-dong ${d.du ? "lh-dong-du" : ""}">
					<div class="lh-dong-dau">
						<div class="lh-dong-ten">${e(d.ten_hang)}</div>
						<div class="lh-dong-sl">${so(d.da_lay)}/${so(d.can_lay)}<small>${e(d.don_vi || "")}</small>${
				d.khac_don_vi
					? `<div class="lh-mo">${so(d.da_lay_ton)}/${so(d.can_lay_ton)} ${e(d.don_vi_ton)}</div>`
					: ""
			}</div>
					</div>
					<div class="lh-mo">${e(d.vat_tu)}${d.so_lo ? " · lô " + e(d.so_lo) : ""}${
				d.hsd_chu ? " · HSD " + e(d.hsd_chu) : ""
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
			if (!this.st.hien_nut_hoan_tat) return $c.empty();
			// Máy in tem nối với máy tính — PDA chỉ báo trạng thái; thiếu tem thì
			// `hoan_tat` bị chặn (`lay_hang.chan_duyet_chua_lay`) với câu nói rõ.
			const t = this.st.trang_thai_tem;
			const tem = t ? `<div class="lh-trang-thai-tem ${t.thieu ? "thieu" : ""}">${e(t.chu)}</div>` : "";
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
	// (phiếu XVT-2026-00007 trên erptest, đã huỷ). Hộp `frappe.ui.Dialog` thường
	// không có cờ đó nên Enter không chạm được nó.
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

	// Mirror của `vo.js::_dam()` (app PDA) — Desk không dùng `KhoApp`, nên giữ một
	// bản riêng, cùng khuôn: escape TOÀN BỘ trước, RỒI MỚI đổi `**x**` (quy ước lớp
	// luồng tự đánh dấu) thành `<b>x</b>` CỦA RIÊNG hàm này.
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
