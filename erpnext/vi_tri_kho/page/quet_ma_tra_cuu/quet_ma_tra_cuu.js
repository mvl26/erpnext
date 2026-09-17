// Trang "Quét mã tra cứu" — dùng trên PDA cầm tay của thủ kho.
//
// VÌ SAO LÀ MỘT TRANG RIÊNG: chủ đầu tư, 17/09/2026 — "anh muốn quét mã tra cứu
// là chức năng riêng và ở trong workspace vị trí kho … màn đấy sẽ hiển thị cho
// màn hình pda". Trước đó khung quét nằm nhúng trong form `Batch Entry`, tức là
// muốn tra một thùng hàng phải mở một phiếu nhập lô bất kỳ trước.
//
// Máy chủ: `erpnext.vi_tri_kho.vitri.quet.tra_cuu` — quét gì cũng trả một dict
// có khoá `loai` ("lo" / "vat_tu" / "kho" / "o" / null). Rẽ nhánh THEO KHOÁ ĐÓ,
// không dò chữ trong chuỗi hiển thị (xem docstring `quet.py`).
//
// BA ĐIỀU RIÊNG CỦA PDA (chưa thử trên PDA thật — thử trên Chrome giả lập màn
// hình nhỏ; cần chủ đầu tư quét thử bằng máy của kho):
//
// 1. Súng quét của PDA gõ vào ô đang focus như một bàn phím rồi (thường) gửi
//    Enter. Nên ô quét phải LUÔN giữ focus — sau mỗi kết quả, sau mỗi lần chạm
//    vào chỗ trống, sau khi quay lại trang.
// 2. Giữ focus trên màn hình cảm ứng thì bàn phím ảo bật lên che nửa màn hình.
//    `inputmode="none"` giữ focus mà không gọi bàn phím; nút ⌨ chuyển sang gõ
//    tay khi tem mờ không quét được.
// 3. Một số PDA cài súng quét KHÔNG gửi Enter. Ở chế độ quét (bàn phím ảo đang
//    tắt) thì không ai gõ tay được vào ô, nên chữ xuất hiện trong ô chỉ có thể
//    là súng quét — ngừng nhận ký tự `TU_GUI_SAU_MS` là coi như quét xong.

frappe.pages["quet-ma-tra-cuu"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Quét mã tra cứu"),
		single_column: true,
	});
	wrapper.quet_ma = new erpnext.vi_tri_kho.QuetMaTraCuu(page);
};

frappe.pages["quet-ma-tra-cuu"].on_page_show = function (wrapper) {
	wrapper.quet_ma && wrapper.quet_ma.giu_focus();
};

frappe.provide("erpnext.vi_tri_kho");

const TU_GUI_SAU_MS = 250;
const SO_LAN_QUET_NHO = 10;
// Lô còn hạn từ ngần này ngày trở xuống thì tô cam ("cận date"). Đặt 3 tháng
// khi dựng trang — CHƯA hỏi kho ngưỡng thật; kho dùng mốc khác thì đổi ở đây.
const NGAY_CAN_DATE = 90;

erpnext.vi_tri_kho.QuetMaTraCuu = class QuetMaTraCuu {
	constructor(page) {
		this.page = page;
		this.lich_su = [];
		// Số thứ tự lần quét: quét dồn hai mã liền nhau thì câu trả lời của mã
		// TRƯỚC có thể về SAU — không có số này thì màn hình hiện nhầm mã cũ.
		this.lan = 0;
		this.go_tay = false;
		this.dung();
	}

	dung() {
		this.$goc = $(`
			<div class="qmtc">
				<div class="qmtc-thanh-quet">
					<div class="qmtc-o-quet">
						<span class="qmtc-bieu-tuong">${frappe.utils.icon("scan", "md")}</span>
						<input type="text" class="qmtc-nhap" inputmode="none"
							autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false"
							enterkeyhint="search" placeholder="${__("Quét tem lô, tem vị trí…")}" />
						<!-- Hai biểu tượng vẽ tay: \`icon-keyboard\` của Frappe tô cứng màu
							#192734 nên gần như biến mất ở chế độ tối; bộ biểu tượng không có máy ảnh. -->
						<button type="button" class="qmtc-nut qmtc-nut-ban-phim" title="${__("Gõ tay")}">
							<svg class="icon icon-md" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><rect x="2.5" y="6" width="19" height="12" rx="2"/><path d="M6 10h.01M9 10h.01M12 10h.01M15 10h.01M18 10h.01M7.5 14h9"/></svg>
						</button>
						<button type="button" class="qmtc-nut qmtc-nut-camera" title="${__("Quét bằng camera")}">
							<svg class="icon icon-md" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8h3l2-2.5h6L17 8h3v11H4z"/><circle cx="12" cy="13" r="3.5"/></svg>
						</button>
					</div>
					<div class="qmtc-goi-y">${__("Bấm nút quét trên PDA và chiếu vào tem")}</div>
				</div>
				<div class="qmtc-ket-qua"></div>
				<div class="qmtc-lich-su"></div>
			</div>
		`).appendTo(this.page.main);

		this.$nhap = this.$goc.find(".qmtc-nhap");
		this.$ket_qua = this.$goc.find(".qmtc-ket-qua");
		this.$lich_su = this.$goc.find(".qmtc-lich-su");

		this.ve_cho();
		this.gan_su_kien();
		this.giu_focus();
	}

	gan_su_kien() {
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

		this.$goc.find(".qmtc-nut-ban-phim").on("click", () => this.doi_ban_phim());
		this.$goc.find(".qmtc-nut-camera").on("click", () => this.quet_camera());

		// Chạm vào chỗ trống thì trả focus cho ô quét. KHÔNG cướp focus khỏi
		// liên kết, nút, hay chữ người dùng đang bôi đen để chép.
		this.$goc.on("click", (ev) => {
			if ($(ev.target).closest("a, button, input, .qmtc-dong-lich-su").length) return;
			if (window.getSelection && String(window.getSelection())) return;
			this.giu_focus();
		});

		this.$lich_su.on("click", ".qmtc-dong-lich-su", (ev) => {
			this.tra_cuu(String($(ev.currentTarget).attr("data-ma")));
		});
	}

	giu_focus() {
		// Không kéo trang lên đầu mỗi lần focus — người dùng đang đọc giữa thẻ.
		this.$nhap.length && this.$nhap[0].focus({ preventScroll: true });
	}

	doi_ban_phim() {
		this.go_tay = !this.go_tay;
		clearTimeout(this.hen_gui);
		this.$nhap.attr("inputmode", this.go_tay ? "text" : "none");
		this.$goc.find(".qmtc-nut-ban-phim").toggleClass("dang-bat", this.go_tay);
		this.$goc
			.find(".qmtc-goi-y")
			.text(this.go_tay ? __("Gõ mã rồi bấm Enter") : __("Bấm nút quét trên PDA và chiếu vào tem"));
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
				if (ma) this.tra_cuu(ma);
			},
		});
	}

	gui() {
		clearTimeout(this.hen_gui);
		const ma = String(this.$nhap.val() || "").trim();
		this.$nhap.val("");
		if (ma) this.tra_cuu(ma);
	}

	tra_cuu(ma) {
		const lan = ++this.lan;
		this.ve_dang_tra(ma);
		// Đang cuộn xuống cuối danh sách lô của lần quét trước mà bóp cò quét
		// tiếp thì kết quả mới phải hiện ngay trước mắt, không nằm khuất phía trên.
		window.scrollTo({ top: 0 });
		frappe
			.xcall("erpnext.vi_tri_kho.vitri.quet.tra_cuu", { ma: ma })
			.then((d) => {
				if (lan !== this.lan) return;
				d = d || { loai: null };
				this.ve_ket_qua(ma, d);
				this.nho(ma, d);
				rung(d.loai ? [40] : [80, 60, 80]);
			})
			.catch(() => {
				// Lỗi quyền / mất mạng: `frappe.xcall` đã tự hiện câu báo của máy
				// chủ. Chỉ gỡ khung "đang tra" để màn hình không treo mãi.
				if (lan === this.lan) this.ve_cho();
			})
			.finally(() => {
				if (lan === this.lan) this.giu_focus();
			});
	}

	nho(ma, d) {
		this.lich_su = this.lich_su.filter((x) => x.ma !== ma);
		this.lich_su.unshift({ ma: ma, loai: d.loai, ten: tieu_de_ngan(d), luc: frappe.datetime.now_time() });
		this.lich_su = this.lich_su.slice(0, SO_LAN_QUET_NHO);
		this.ve_lich_su();
	}

	// ----------------------------------------------------------------- vẽ

	ve_cho() {
		this.$ket_qua.html(`
			<div class="qmtc-the qmtc-cho">
				<div class="qmtc-cho-hinh">${frappe.utils.icon("scan", "xl")}</div>
				<div class="qmtc-cho-chu">${__("Sẵn sàng quét")}</div>
				<div class="qmtc-mo">${__("Tem lô · tem vị trí · mã vật tư · mã kho")}</div>
			</div>`);
	}

	ve_dang_tra(ma) {
		this.$ket_qua.html(`
			<div class="qmtc-the qmtc-dang-tra">
				<div class="qmtc-ma-to">${e(ma)}</div>
				<div class="qmtc-mo">${__("Đang tra cứu…")}</div>
				<div class="qmtc-thanh-cho"></div>
			</div>`);
	}

	ve_ket_qua(ma, d) {
		const ve = { lo: the_lo, vat_tu: the_vat_tu, o: the_o, kho: the_kho }[d.loai];
		this.$ket_qua.html(ve ? ve(d) : the_khong_thay(ma));
	}

	ve_lich_su() {
		if (!this.lich_su.length) return this.$lich_su.empty();
		this.$lich_su.html(`
			<div class="qmtc-tieu-de-muc">${__("Vừa quét")}</div>
			${this.lich_su
				.map(
					(x) => `
				<div class="qmtc-dong-lich-su ${x.loai ? "" : "khong-thay"}" data-ma="${e(x.ma)}" role="button">
					<span class="qmtc-nhan-loai loai-${x.loai || "khong"}">${nhan_loai(x.loai)}</span>
					<span class="qmtc-lich-su-chu">
						<span class="qmtc-lich-su-ma">${e(x.ma)}</span>
						${x.ten ? `<span class="qmtc-lich-su-ten">${e(x.ten)}</span>` : ""}
					</span>
					<span class="qmtc-lich-su-luc">${e(x.luc.slice(0, 5))}</span>
				</div>`
				)
				.join("")}`);
	}
};

// ------------------------------------------------------------------- thẻ

function the_lo(d) {
	const han = trang_thai_han(d.hsd);
	const ton = d.ton_theo_o || [];
	const tong = ton.reduce((t, x) => t + flt(x.so_luong), 0);
	return `
		<div class="qmtc-the qmtc-the-lo muc-${han.muc}">
			<div class="qmtc-dau">
				<span class="qmtc-nhan-loai loai-lo">${nhan_loai("lo")}</span>
				<a class="qmtc-ma-to" href="${lien_ket("batch", d.so_lo)}">${e(d.so_lo)}</a>
				<div class="qmtc-ten-hang">${e(d.ten_hang || d.vat_tu)}</div>
				<div class="qmtc-mo">${e(d.vat_tu)}${d.don_vi ? " · " + e(d.don_vi) : ""}</div>
			</div>

			<div class="qmtc-han muc-${han.muc}">
				<div>
					<div class="qmtc-nhan">${__("Hạn dùng")}</div>
					<div class="qmtc-han-ngay">${d.hsd ? e(ngay(d.hsd)) : __("Không có")}</div>
				</div>
				${han.chu ? `<span class="qmtc-han-con">${e(han.chu)}</span>` : ""}
			</div>

			<div class="qmtc-luoi">
				${o_luoi(__("Ngày SX"), d.ngay_san_xuat && ngay(d.ngay_san_xuat))}
				${o_luoi(__("Ngày nhập"), d.ngay_nhap && ngay(d.ngay_nhap))}
				${o_luoi(__("Số gói"), d.so_goi)}
				${o_luoi(
					__("Phiếu nhập"),
					d.so_phieu_nhap &&
						`<a href="${lien_ket("purchase-receipt", d.so_phieu_nhap)}">${e(d.so_phieu_nhap)}</a>`,
					true
				)}
				${o_luoi(__("Nhà cung cấp"), d.nha_cung_cap, false, true)}
			</div>

			<div class="qmtc-muc">
				<div class="qmtc-tieu-de-muc">${__("Vị trí")}</div>
				<div class="qmtc-chip-hang">
					${chip(__("Cố định"), d.vi_tri_co_dinh, "storage-location")}
					${chip(__("Tem in"), d.o_in_tem, "storage-location")}
				</div>
				${
					ton.length
						? `<div class="qmtc-bang">
							${ton
								.map(
									(x) => `
								<div class="qmtc-dong">
									<a class="qmtc-dong-chinh qmtc-ma-o" href="${lien_ket("storage-location", x.o)}">${e(
										x.o
									)}</a>
									<span class="qmtc-so">${so(x.so_luong)}${don_vi(d.don_vi)}</span>
								</div>`
								)
								.join("")}
							${
								ton.length > 1
									? `<div class="qmtc-dong qmtc-tong"><span class="qmtc-dong-chinh">${__(
											"Tổng"
									  )}</span><span class="qmtc-so">${so(tong)}${don_vi(d.don_vi)}</span></div>`
									: ""
							}
						</div>`
						: `<div class="qmtc-trong">${__("Lô này chưa xếp vào ô nào")}</div>`
				}
			</div>
		</div>`;
}

function the_vat_tu(d) {
	const lo = d.lo_con_ton || [];
	const tong = lo.reduce((t, x) => t + flt(x.so_luong), 0);
	return `
		<div class="qmtc-the qmtc-the-vat-tu">
			<div class="qmtc-dau">
				<span class="qmtc-nhan-loai loai-vat_tu">${nhan_loai("vat_tu")}</span>
				<div class="qmtc-ten-hang qmtc-ten-to">${e(d.ten_hang || d.vat_tu)}</div>
				<div class="qmtc-mo"><a href="${lien_ket("item", d.vat_tu)}">${e(d.vat_tu)}</a>${
		d.don_vi ? " · " + e(d.don_vi) : ""
	}</div>
			</div>
			<div class="qmtc-muc">
				<div class="qmtc-chip-hang">
					${chip(__("Vị trí cố định"), d.vi_tri_co_dinh, "storage-location", __("Chưa gán"))}
				</div>
			</div>
			<div class="qmtc-muc">
				<div class="qmtc-tieu-de-muc">
					${d.co_lo ? __("Lô còn tồn · hạn gần trước") : __("Tồn theo ô")}
					${lo.length ? `<span class="qmtc-tong-nho">${so(tong)} ${e(d.don_vi || "")}</span>` : ""}
				</div>
				${
					lo.length
						? `<div class="qmtc-bang">${lo
								.map((x) => dong_hang({ ...x, don_vi: d.don_vi }, { hien_lo: d.co_lo }))
								.join("")}</div>`
						: `<div class="qmtc-trong">${__("Không còn tồn ở ô nào")}</div>`
				}
			</div>
		</div>`;
}

function the_o(d) {
	const hang = d.hang_trong_o || [];
	const nhan = [
		d.la_nhom ? `<span class="qmtc-co">${__("Nhóm ô")}</span>` : "",
		d.ngung_dung ? `<span class="qmtc-co co-do">${__("Ngừng dùng")}</span>` : "",
		d.loai_vi_tri ? `<span class="qmtc-co">${e(d.loai_vi_tri)}</span>` : "",
	].join("");
	const mh = d.mat_hang_co_dinh;
	return `
		<div class="qmtc-the qmtc-the-o">
			<div class="qmtc-dau">
				<span class="qmtc-nhan-loai loai-o">${nhan_loai("o")}</span>
				<a class="qmtc-ma-to" href="${lien_ket("storage-location", d.ma_o)}">${e(d.ma_in_nhan || d.ma_o)}</a>
				<div class="qmtc-mo">${e(d.kho)}${d.ten_o ? " · " + e(d.ten_o) : ""}</div>
				${nhan ? `<div class="qmtc-co-hang">${nhan}</div>` : ""}
			</div>
			<div class="qmtc-muc">
				<div class="qmtc-tieu-de-muc">${__("Mặt hàng cố định")}</div>
				${
					mh
						? `<a class="qmtc-hop-hang" href="${lien_ket("item", mh.vat_tu)}">
							<span class="qmtc-ten-hang">${e(mh.ten_hang || mh.vat_tu)}</span>
							<span class="qmtc-mo">${e(mh.vat_tu)} · ${__("gán ở {0}", [e(mh.vi_tri)])}</span>
						</a>`
						: `<div class="qmtc-trong">${__("Chưa mặt hàng nào giữ vị trí này")}</div>`
				}
			</div>
			<div class="qmtc-muc">
				<div class="qmtc-tieu-de-muc">${__("Đang chứa")}</div>
				${
					hang.length
						? `<div class="qmtc-bang">${hang
								.map((x) => dong_hang(x, { hien_ten: true, hien_lo: !!x.so_lo, hien_o: d.la_nhom }))
								.join("")}</div>
						${
							d.so_dong_hang > hang.length
								? `<div class="qmtc-trong">${__("… và {0} dòng nữa — xem báo cáo Tồn kho theo vị trí", [
										d.so_dong_hang - hang.length,
								  ])}</div>`
								: ""
						}`
						: `<div class="qmtc-trong">${__("Ô trống")}</div>`
				}
			</div>
		</div>`;
}

function the_kho(d) {
	return `
		<div class="qmtc-the qmtc-the-kho">
			<div class="qmtc-dau">
				<span class="qmtc-nhan-loai loai-kho">${nhan_loai("kho")}</span>
				<a class="qmtc-ten-hang qmtc-ten-to" href="${lien_ket("warehouse", d.kho)}">${e(d.ten_kho || d.kho)}</a>
				${d.ten_kho && d.ten_kho !== d.kho ? `<div class="qmtc-mo">${e(d.kho)}</div>` : ""}
				<div class="qmtc-co-hang">
					${
						d.quan_ly_vi_tri
							? `<span class="qmtc-co co-xanh">${__("Đang quản lý vị trí")}</span>`
							: `<span class="qmtc-co">${__("Chưa bật quản lý vị trí")}</span>`
					}
				</div>
			</div>
			${
				d.quan_ly_vi_tri
					? `<div class="qmtc-thong-ke">
						<div><div class="qmtc-so-to">${so(d.so_o)}</div><div class="qmtc-nhan">${__("ô đang dùng")}</div></div>
						<div><div class="qmtc-so-to">${so(d.so_o_co_hang)}</div><div class="qmtc-nhan">${__(
							"ô có hàng"
					  )}</div></div>
					</div>`
					: ""
			}
		</div>`;
}

function the_khong_thay(ma) {
	return `
		<div class="qmtc-the qmtc-khong-thay">
			<div class="qmtc-cho-hinh">${frappe.utils.icon("search", "xl")}</div>
			<div class="qmtc-cho-chu">${__("Không nhận ra mã này")}</div>
			<div class="qmtc-ma-to">${e(ma)}</div>
			<div class="qmtc-mo">${__(
				"Không phải tem lô, tem vị trí, mã vật tư hay mã kho. Có thể vừa quét nhầm mã trên vỏ thùng."
			)}</div>
		</div>`;
}

// ---------------------------------------------------------------- mẩu nhỏ

function dong_hang(x, { hien_ten = false, hien_lo = false, hien_o = true } = {}) {
	const han = trang_thai_han(x.hsd);
	return `
		<div class="qmtc-dong qmtc-dong-hang">
			<div class="qmtc-dong-chinh">
				${hien_ten ? `<div class="qmtc-dong-ten">${e(x.ten_hang || x.vat_tu)}</div>` : ""}
				${hien_lo ? `<div class="qmtc-dong-lo">${e(x.so_lo)}</div>` : ""}
				<div class="qmtc-dong-phu">
					${hien_o ? `<span class="qmtc-ma-o">${e(x.o)}</span>` : ""}
					${x.hsd ? `<span class="qmtc-han-nho muc-${han.muc}">HSD ${e(ngay(x.hsd))}</span>` : ""}
				</div>
			</div>
			<span class="qmtc-so">${so(x.so_luong)}${don_vi(x.don_vi)}</span>
		</div>`;
}

function don_vi(dvt) {
	return dvt ? ` <small>${e(dvt)}</small>` : "";
}

function o_luoi(nhan, gia_tri, la_html = false, rong = false) {
	if (gia_tri === undefined || gia_tri === null || gia_tri === "") return "";
	return `<div class="qmtc-o-luoi ${rong ? "rong" : ""}">
		<div class="qmtc-nhan">${e(nhan)}</div>
		<div class="qmtc-gia-tri">${la_html ? gia_tri : e(gia_tri)}</div>
	</div>`;
}

function chip(nhan, gia_tri, duong, khi_trong) {
	if (!gia_tri && !khi_trong) return "";
	const than = gia_tri
		? `<a href="${lien_ket(duong, gia_tri)}" class="qmtc-chip-gia-tri">${e(gia_tri)}</a>`
		: `<span class="qmtc-chip-gia-tri trong">${e(khi_trong)}</span>`;
	return `<div class="qmtc-chip"><span class="qmtc-chip-nhan">${e(nhan)}</span>${than}</div>`;
}

function trang_thai_han(hsd) {
	if (!hsd) return { muc: "khong", chu: "" };
	const con = frappe.datetime.get_day_diff(hsd, frappe.datetime.get_today());
	if (con < 0) return { muc: "het", chu: __("Hết hạn {0} ngày", [-con]) };
	if (con === 0) return { muc: "het", chu: __("Hết hạn hôm nay") };
	if (con <= NGAY_CAN_DATE) return { muc: "can", chu: __("Còn {0} ngày", [con]) };
	return { muc: "con", chu: __("Còn {0} ngày", [con]) };
}

function nhan_loai(loai) {
	return (
		{ lo: __("Lô"), vat_tu: __("Vật tư"), o: __("Vị trí"), kho: __("Kho") }[loai] || __("Không rõ")
	);
}

function tieu_de_ngan(d) {
	if (d.loai === "lo" || d.loai === "vat_tu") return d.ten_hang || d.vat_tu;
	if (d.loai === "o") return d.kho;
	if (d.loai === "kho") return d.ten_kho !== d.kho ? d.ten_kho : "";
	return "";
}

function lien_ket(duong, ten) {
	return `/app/${duong}/${encodeURIComponent(ten)}`;
}

function ngay(gia_tri) {
	return frappe.datetime.str_to_user(gia_tri);
}

function so(gia_tri) {
	return e(flt(gia_tri).toLocaleString("vi-VN", { maximumFractionDigits: 3 }));
}

function e(gia_tri) {
	return frappe.utils.escape_html(String(gia_tri));
}

function rung(mau) {
	try {
		navigator.vibrate && navigator.vibrate(mau);
	} catch (err) {
		// Trình duyệt chặn rung (chưa có thao tác người dùng) — không sao.
	}
}
