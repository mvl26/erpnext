// Màn "Xếp hàng vào ô" — MÀN ĐẦU TIÊN CỦA APP PDA CÓ GHI (Task 3, brief). Phần
// QUYẾT ĐỊNH ("hai bước lô→ô", "ô phải khớp ô in trên tem", "số lượng mặc định",
// nhãn và câu báo) nằm ở `../warehouse_operations/luong/xep_hang.js` — CÙNG một
// file mà trang Desk cũ (`quet_ma_tra_cuu... `xep_hang_pda.js`, Bước 6 của brief)
// cũng dùng. File này CHỈ VẼ: không tự suy luật SAI Ô, không tự viết câu báo,
// không tự tính số lượng mặc định — mọi thứ đọc thẳng từ `_luong.trang_thai()`
// hoặc kết quả trả về của `_luong.quet()`.
//
// Nút "Hoàn tất phiếu" đi qua `erpnext.kho_pda.hoi()` (không nghe phím) — một hộp
// xác nhận bắt Enter từng DUYỆT NHẦM một phiếu thật ngày 17/09/2026, xem
// `hop_thoai.js`.
//
// CẢNH BÁO CHO TASK 4–5 (soát xét vòng 1, Task 3, P1 — lỗi NẶNG, đã sửa, đọc kỹ
// trước khi chép file này làm mẫu): `ve($than)` KHÔNG được gắn trình nghe uỷ
// quyền (`.on("click", ".lop-con", …)`) THẲNG lên `$than` — `vo.js::_ve_that()`
// chỉ `.empty()` (nay thêm `.off()` làm lưới an toàn, nhưng đừng ỷ vào đó) phần
// CON của `$than`, không đụng tới handler gắn trên CHÍNH `$than`. Bản đầu của màn
// này mắc đúng lỗi này: ~9 handler gắn lên `$than`, đo được rò 10 → 37 sau 3 vòng
// vào/ra màn, và MỘT cú bấm "Hoàn tất phiếu" bật ra 4 hộp xác nhận chồng nhau —
// đồng ý cả bốn thì `duyet()` (một lời GHI thật) chạy 4 LẦN. Khuôn ĐÚNG (xem biến
// `$goc` trong `ve()` bên dưới, và cách `man_tra_cuu.js` dùng `$lich_su`): luôn
// gắn `.on(...)` lên một phần tử CON được `$than.html(...)` dựng LẠI mỗi lượt
// `ve()` — handler cũ tự biến mất cùng DOM cũ khi màn bị rời, không cần gỡ tay.

frappe.provide("erpnext.kho_pda");

// Một luồng SỐNG SUỐT phiên app, giống `man_tra_cuu.js` — thủ kho quét dở một lô
// (chờ ô), quay ra kiểm việc khác rồi vào lại "Xếp hàng" vẫn thấy đúng chỗ đang
// làm dở, không phải quét lại tem LÔ từ đầu.
//
// TASK 6, VIỆC THÊM NGOÀI BRIEF 1: dựng LƯỜI ở lần `ve()` ĐẦU TIÊN, KHÔNG ở cấp
// module như bản cũ (`const _luong = _LUONG_NS.tao(...)` chạy NGAY lúc `import`,
// và `const _LUONG_NS = erpnext.warehouse_operations.luong.xep_hang;` — một biến
// khác cũng chụp nhanh ở cấp module — đã bỏ hẳn, gọi thẳng namespace bên trong
// `_dung_luong()` để không giữ tham chiếu cũ). Bản cũ khoá cứng thứ tự các dòng
// `import` trong `kho_pda.bundle.js`: đảo nhầm một dòng (namespace luồng nạp SAU
// file màn) khiến `.tao()` gọi trên namespace còn `undefined`, ném `TypeError`
// NGAY LÚC TẢI TRANG — không bài test Python nào ở đây bắt được vì không bài nào
// thực thi JS trong trình duyệt (xem khuôn đầy đủ, cùng lý do, ở `man_tra_cuu.js`).
// `_luong` vẫn là biến module-scope (không còn `const`) để giữ ĐÚNG tính
// SINGLETON: `_dung_luong()` chỉ thật sự dựng khi còn `null`, mọi lượt `ve()` sau
// TÁI DÙNG đúng một luồng đó — không mất lô đang xếp dở giữa các lượt vào/ra màn.
let _luong = null;

function _dung_luong() {
	if (!_luong) {
		_luong = erpnext.warehouse_operations.luong.xep_hang.tao({
			goi: (duong_dan, doi_so) => erpnext.kho_pda.KhoApp.goi(duong_dan, doi_so),
		});
	}
	return _luong;
}

// Đổi ca (cùng lý do `man_tra_cuu.js`, soát xét Task 2 vòng 1 P11/mục 6): người
// SAU quét thẻ vào (không tải lại trang) không được thừa hưởng lô đang xếp dở của
// người TRƯỚC — coi `""` (lỗi mạng lúc đọc `nguoi_dung`) là "không xác định", LUÔN
// dọn khi giá trị hiện tại là `""`, thà xoá oan còn hơn lộ dữ liệu người khác.
let _nguoi_dung_luc_vao = erpnext.kho_pda.KhoApp.nguoi_dung;

function _e(gia_tri) {
	return frappe.utils.escape_html(String(gia_tri == null ? "" : gia_tri));
}

function _so(gia_tri) {
	return _e(flt(gia_tri).toLocaleString("vi-VN", { maximumFractionDigits: 3 }));
}

// KHÔNG escape — dùng riêng cho `noi_dung` của `hoi()`, nơi TỰ escape toàn bộ
// chuỗi truyền vào (`hop_thoai.js`). Escape hai lần sẽ biến `&` thành `&amp;amp;`.
function _so_tho(gia_tri) {
	return flt(gia_tri).toLocaleString("vi-VN", { maximumFractionDigits: 3 });
}

function _ngay(gia_tri) {
	return gia_tri ? frappe.datetime.str_to_user(gia_tri) : "";
}

function _rung(kq) {
	let mau;
	if (kq.buoc === "da_ghi") mau = [40, 40, 40];
	else if (kq.muc === "do") mau = [80, 60, 80];
	else if (kq.muc === "cam") mau = [60];
	else mau = null;
	if (!mau) return;
	try {
		navigator.vibrate && navigator.vibrate(mau);
	} catch (err) {
		// Trình duyệt chặn rung (chưa có thao tác người dùng) — không sao.
	}
}

// --------------------------------------------------------------------- vẽ

function _ve_dau($dau, st) {
	if (!st.kho_ds.length) {
		$dau.html(`<div class="kho-bao-o muc-cam">${_e(__("Chưa kho nào bật quản lý vị trí."))}</div>`);
		return;
	}
	if (!st.kho) {
		$dau.html(`
			<div class="kho-tieu-de-muc">${__("Chọn kho")}</div>
			<div class="xh2-chon-kho-ds">
				${st.kho_ds
					.map((k) => `<button type="button" class="xh2-chon-kho" data-kho="${_e(k)}">${_e(k)}</button>`)
					.join("")}
			</div>`);
		return;
	}
	const doi_kho =
		st.kho_ds.length > 1 && !st.cho
			? `<button type="button" class="xh2-lien-ket-nho xh2-doi-kho">${__("Đổi")}</button>`
			: "";
	const phieu = st.phieu
		? `<span class="xh2-ma-phieu">${_e(st.phieu.name)}</span>`
		: `<span class="xh2-mo">${__("phiếu mới")}</span>`;
	$dau.html(`
		<div class="xh2-kho">
			<span class="xh2-mo">${__("Kho")}</span> <b>${_e(st.kho)}</b> ${doi_kho}
			<span class="xh2-cham">·</span> ${phieu}
		</div>`);
}

function _ve_dat_o($khoi, st) {
	const o = st.o_tren_tem;
	if (!o) return $khoi.empty();
	if (o.dang_cho_quet) {
		$khoi.html(`
			<div class="kho-the xh2-the-dat-o">
				<span class="kho-nhan-loai loai-o">${__("Đang chờ quét ô")}</span>
				<div class="kho-the-ma">${_e(o.so_lo || o.ten_hang)}</div>
				<div class="kho-the-mo">${__("Quét tem Ô muốn đặt lên tem lô này.")}</div>
				<button type="button" class="xh2-lien-ket-nho xh2-huy-dat-o">${__("Huỷ")}</button>
			</div>`);
		return;
	}
	$khoi.html(`
		<div class="kho-the xh2-the-dat-o">
			<span class="kho-nhan-loai loai-o">${__("Chưa có ô trên tem")}</span>
			<div class="kho-the-ma">${_e(o.so_lo || o.ten_hang)}</div>
			<button type="button" class="xh2-nut-chinh xh2-dat-o-tem">${__("Đặt ô trên tem")}</button>
		</div>`);
}

function _ve_cho($khoi, st) {
	const c = st.cho;
	if (!c) return $khoi.empty();

	const nguon = (c.nguon || [])
		.map(
			(n) => `
			<button type="button" class="xh2-nguon ${n.o === c.tu_o ? "dang-chon" : ""}" data-o="${_e(n.o)}">
				${
					n.la_o_chua_xep
						? `<span>${__("Chưa xếp")}</span>`
						: `<span class="xh2-ma">${_e(n.ma_in_nhan || n.o)}</span>`
				}
				<span class="xh2-nguon-sl">${_so(n.con_xep_duoc)}</span>
			</button>`
		)
		.join("");

	const g = c.goi_y || {};
	const goi_y = g.den_o
		? `<div class="xh2-goi-y">
				<div class="kho-nhan">${g.theo_tem ? __("Xếp vào ô trên tem — bắt buộc") : __("Ô gợi ý")}</div>
				<div class="xh2-goi-y-o">${_e(g.ma_in_nhan || g.den_o)}</div>
			</div>`
		: `<div class="xh2-goi-y trong">
				<div class="kho-nhan">${__("Chưa có ô gợi ý — quét tem ô định xếp")}</div>
			</div>`;

	const n = (c.nguon || []).find((x) => x.o === c.tu_o);

	$khoi.html(`
		<div class="kho-the xh2-the-cho">
			<div class="kho-the-dau">
				<div class="xh2-dong-tren">
					<span class="kho-nhan-loai loai-lo">${c.so_lo ? __("Lô") : __("Hàng không lô")}</span>
					<button type="button" class="xh2-lien-ket-nho xh2-bo-lo">${__("Bỏ lô này")}</button>
				</div>
				${c.so_lo ? `<div class="kho-the-ma">${_e(c.so_lo)}</div>` : ""}
				<div class="kho-the-ten">${_e(c.ten_hang)}</div>
				<div class="kho-the-mo">${_e(c.vat_tu)}${c.hsd ? " · HSD " + _e(_ngay(c.hsd)) : ""}</div>
			</div>

			<div class="xh2-muc">
				<div class="kho-tieu-de-muc">${
					(c.nguon || []).length > 1 ? __("Lấy từ ô — chạm để đổi") : __("Lấy từ ô")
				}</div>
				<div class="xh2-nguon-ds">${nguon}</div>
			</div>

			<div class="xh2-muc">
				<div class="kho-tieu-de-muc">${__("Số lượng xếp")}${
		n ? ` <span class="xh2-mo">· ${__("tối đa {0}", [_so(n.con_xep_duoc)])}</span>` : ""
	}</div>
				<div class="xh2-so-luong-hang">
					<button type="button" class="xh2-cong-tru" data-buoc="-1">−</button>
					<input type="number" class="xh2-so-luong" inputmode="decimal" min="0" step="any"
						value="${flt(c.so_luong)}" />
					<span class="xh2-don-vi">${_e(c.don_vi || "")}</span>
					<button type="button" class="xh2-cong-tru" data-buoc="1">+</button>
				</div>
			</div>

			<div class="xh2-muc">${goi_y}</div>
		</div>`);
}

function _ve_danh_sach($khoi, st) {
	const dong = st.dong || [];
	if (!dong.length) return $khoi.empty();
	$khoi.html(`
		<div class="kho-tieu-de-muc">${__("Trên phiếu · {0} dòng", [dong.length])}</div>
		${dong
			.slice()
			.reverse()
			.map(
				(d) => `
			<div class="xh2-dong">
				<div class="xh2-dong-chinh">
					<div class="xh2-dong-ten">${_e(d.ten_hang || d.vat_tu)}</div>
					${d.so_lo ? `<div class="xh2-dong-lo">${_e(d.so_lo)}</div>` : ""}
					<div class="xh2-dong-duong">
						${
							d.tu_o_chua_xep
								? `<span>${__("Chưa xếp")}</span>`
								: `<span class="xh2-ma">${_e(d.tu_o)}</span>`
						}
						<span class="xh2-mui-ten">→</span>
						<b>${_e(d.den_o)}</b>
					</div>
				</div>
				<div class="xh2-dong-sl">${_so(d.so_luong)}<small>${_e(d.don_vi || "")}</small></div>
				<button type="button" class="xh2-xoa-dong" data-dong="${_e(d.name)}" title="${_e(__("Bỏ dòng"))}">×</button>
			</div>`
			)
			.join("")}`);
}

function _ve_chan($khoi, st) {
	const so_dong = (st.dong || []).length;
	if (!so_dong) return $khoi.empty();
	$khoi.html(`
		<button type="button" class="xh2-nut-chinh xh2-hoan-tat">
			${__("Hoàn tất phiếu · {0} dòng", [so_dong])}
		</button>`);
}

// --------------------------------------------------------------------- màn

erpnext.kho_pda.KhoApp.dang_ky_man("xep-hang", {
	tieu_de: __("Xếp hàng"),

	// `tham_so` — phần sau dấu `/` trong hash (`vo.js::_theo_hash` cắt ra,
	// `vo.js::_ve_that` truyền vào). Màn này KHÔNG có tuyến sâu nào trong spec §5;
	// NHẬN ĐÚNG CHỮ KÝ rồi bỏ qua là CỐ Ý. Soát xét tổng (N3): `vo.js` đã truyền
	// tham số từ Task 1 mà KHÔNG màn nào khai tham số thứ hai, nên tuyến
	// `#/lay-hang/<phiếu>` im lặng không chạy suốt sáu Task. Khai đủ ở cả bốn màn
	// để chữ ký là MỘT — không ai phải nhớ màn nào nhận, màn nào không.
	ve($than, tham_so) {
		// PHẢI là câu lệnh ĐẦU TIÊN: đoạn đổi ca ngay dưới đọc `_luong.doi_kho()` —
		// gọi sau đoạn đó, ở lượt `ve()` đầu tiên `_luong` vẫn còn `null`.
		_dung_luong();
		const _nguoi_dung_hien_tai = erpnext.kho_pda.KhoApp.nguoi_dung;
		if (!_nguoi_dung_hien_tai || _nguoi_dung_hien_tai !== _nguoi_dung_luc_vao) {
			_luong.doi_kho();
			_nguoi_dung_luc_vao = _nguoi_dung_hien_tai;
		}

		$than.html(`
			<div class="man-xep-hang">
				<div class="xh2-dau"></div>
				<div class="xh2-o-quet"></div>
				<div class="xh2-dat-o"></div>
				<div class="xh2-cho"></div>
				<div class="xh2-danh-sach"></div>
				<div class="xh2-chan"></div>
			</div>
		`);

		// SOÁT XÉT VÒNG 1 (Task 3, P1): MỌI trình nghe uỷ quyền của màn này gắn lên
		// `$goc` — phần tử CON vừa dựng LẠI bởi `$than.html(...)` ở trên, KHÔNG gắn
		// thẳng lên `$than` (bài học đắt: bản trước gắn ~9 handler lên `$than`, đo
		// được rò 10 → 37 sau 3 vòng vào/ra màn, khiến MỘT cú bấm "Hoàn tất phiếu"
		// bật 4 hộp xác nhận chồng nhau và `duyet()` — một lời GHI thật — chạy 4
		// LẦN). `vo.js::_ve_that()` nay có `$than.off()` làm lưới an toàn tầng khung,
		// nhưng đừng ỷ vào đó — đúng khuôn `man_tra_cuu.js` (`$lich_su`, một phần tử
		// CON được dựng lại mỗi lượt `ve()`) mới là lý do gốc màn đó KHÔNG rò: gắn
		// trên một phần tử BỊ HUỶ VÀ THAY MỚI mỗi lượt vẽ thì handler cũ tự biến mất
		// cùng DOM cũ, không cần gỡ tay. Task 4–5 CHÉP file này làm mẫu: luôn khai
		// `$goc` (hoặc tương đương) NGAY sau khi dựng khung `$than.html(...)`, và
		// gắn MỌI `.on(...)` lên đó — không lên `$than`.
		const $goc = $than.find(".man-xep-hang");

		const $dau = $than.find(".xh2-dau");
		const $dat_o = $than.find(".xh2-dat-o");
		const $cho = $than.find(".xh2-cho");
		const $ds = $than.find(".xh2-danh-sach");
		const $chan = $than.find(".xh2-chan");

		// Số thứ tự lượt quét — cùng lẽ `man_tra_cuu.js`/`quet_ma_tra_cuu.js`: bắn
		// hai mã liền nhau thì câu trả lời của mã TRƯỚC có thể bay về SAU câu trả
		// lời của mã sau; không có số này màn hình dừng ở kết quả CŨ dù đã quét mới.
		let lan = 0;

		const ve_tat_ca = () => {
			const st = _luong.trang_thai();
			_ve_dau($dau, st);
			_ve_dat_o($dat_o, st);
			_ve_cho($cho, st);
			_ve_danh_sach($ds, st);
			_ve_chan($chan, st);
			this._oq &&
				this._oq.dat_goi_y(st.goi_y_o_quet.chu, st.goi_y_o_quet.nhan_manh ? "nhan-manh" : undefined);
		};

		// `loi.message` là câu THẬT của máy chủ (`KhoApp.goi()` đã rút từ
		// `_server_messages`) — chỉ còn lỗi nghiệp vụ ghi thật sự bất ngờ tới đây,
		// `goi()` đã tự lo 401/403/mất mạng (xem đầu `vo.js`).
		const bao_loi = (loi) => erpnext.kho_pda.KhoApp.bao((loi && loi.message) || __("Có lỗi, thử lại."), "do");

		const nap = () => {
			const co_kho = !!_luong.trang_thai().kho;
			return (co_kho ? _luong.lam_moi() : _luong.mo()).then(ve_tat_ca).catch(bao_loi);
		};

		const quet = (ma) => {
			const lan_nay = ++lan;
			erpnext.kho_pda.KhoApp.bao();
			_luong
				.quet(ma)
				.then((kq) => {
					if (lan_nay !== lan) return;
					if (kq.bao) erpnext.kho_pda.KhoApp.bao(kq.bao, kq.muc || "xam");
					_rung(kq);
					ve_tat_ca();
				})
				.catch((loi) => {
					// Máy chủ từ chối ghi (`them_dong_xep`/`doi_o_tren_tem`) — luồng CỐ Ý
					// không nuốt lỗi này (xem đầu `luong/xep_hang.js`), màn tự bắt ở đây.
					if (lan_nay !== lan) return;
					bao_loi(loi);
				})
				.finally(() => {
					if (lan_nay === lan) this._oq && this._oq.giu_focus();
				});
		};

		this._oq = new erpnext.kho_pda.OQuet({
			cha: $than.find(".xh2-o-quet"),
			vung: $than,
			placeholder: __("Quét tem…"),
			goi_y: "",
			khi_quet: (ma) => quet(ma),
		});

		$goc.on("click", ".xh2-chon-kho", (ev) => {
			const kho = $(ev.currentTarget).attr("data-kho");
			erpnext.kho_pda.KhoApp.bao();
			_luong
				.mo(kho)
				.then(ve_tat_ca)
				.catch(bao_loi)
				.finally(() => this._oq && this._oq.giu_focus());
		});

		$goc.on("click", ".xh2-doi-kho", () => {
			_luong.doi_kho();
			erpnext.kho_pda.KhoApp.bao();
			ve_tat_ca();
			this._oq && this._oq.giu_focus();
		});

		$goc.on("click", ".xh2-nguon", (ev) => {
			_luong.chon_nguon($(ev.currentTarget).attr("data-o"));
			ve_tat_ca();
			this._oq && this._oq.giu_focus();
		});

		$goc.on("input", ".xh2-so-luong", (ev) => {
			// KHÔNG vẽ lại khi đang gõ (mất vị trí con trỏ) — chỉ cập nhật trạng thái;
			// `change` bên dưới vẽ lại khi gõ xong (blur/Enter) để hiện giá trị đã kẹp.
			_luong.dat_so_luong(ev.currentTarget.value);
		});
		$goc.on("change", ".xh2-so-luong", (ev) => {
			_luong.dat_so_luong(ev.currentTarget.value);
			ve_tat_ca();
		});
		// Enter trên ô số lượng: xong sửa số, trả focus cho súng quét — cùng lẽ
		// Desk (`xep_hang_pda.js` gốc).
		$goc.on("keydown", ".xh2-so-luong", (ev) => {
			if (ev.key !== "Enter") return;
			ev.preventDefault();
			ev.currentTarget.blur();
			this._oq && this._oq.giu_focus();
		});

		$goc.on("click", ".xh2-cong-tru", (ev) => {
			const buoc = Number($(ev.currentTarget).attr("data-buoc"));
			const st = _luong.trang_thai();
			if (!st.cho) return;
			_luong.dat_so_luong(flt(st.cho.so_luong) + buoc);
			ve_tat_ca();
		});

		$goc.on("click", ".xh2-bo-lo", () => {
			_luong.bo_lo();
			erpnext.kho_pda.KhoApp.bao();
			ve_tat_ca();
			this._oq && this._oq.giu_focus();
		});

		$goc.on("click", ".xh2-dat-o-tem", () => {
			_luong.bat_dau_dat_o();
			ve_tat_ca();
			this._oq && this._oq.giu_focus();
		});

		$goc.on("click", ".xh2-huy-dat-o", () => {
			_luong.huy_dat_o();
			erpnext.kho_pda.KhoApp.bao();
			ve_tat_ca();
			this._oq && this._oq.giu_focus();
		});

		$goc.on("click", ".xh2-xoa-dong", (ev) => {
			const ten_dong = $(ev.currentTarget).attr("data-dong");
			const st = _luong.trang_thai();
			const d = (st.dong || []).find((x) => x.name === ten_dong);
			if (!d) return;
			erpnext.kho_pda.hoi({
				noi_dung: __("Bỏ dòng {0} · {1} → {2} khỏi phiếu?", [
					d.so_lo || d.ten_hang,
					_so_tho(d.so_luong),
					d.den_o,
				]),
				nhan: __("Bỏ dòng"),
				khi_dong_y: () => {
					_luong
						.xoa_dong(ten_dong)
						.then((st2) => {
							ve_tat_ca();
							// Soát xét vòng 1, mục 5: câu + mức màu là quyết định CỦA LUỒNG
							// (`st2.bao`/`st2.muc`, xem `xoa_dong()` trong `luong/xep_hang.js`),
							// không phải lớp vẽ tự gõ riêng "Đã bỏ một dòng." nữa.
							erpnext.kho_pda.KhoApp.bao(st2.bao, st2.muc);
							return st2;
						})
						.catch(bao_loi)
						.finally(() => this._oq && this._oq.giu_focus());
				},
				khi_dong: () => this._oq && this._oq.giu_focus(),
			});
		});

		$goc.on("click", ".xh2-hoan-tat", () => {
			const st = _luong.trang_thai();
			if (!st.phieu || !st.phieu.dong.length) return;
			erpnext.kho_pda.hoi({
				noi_dung: __("Ghi phiếu {0} ({1} dòng) vào sổ vị trí? Sau khi ghi, tồn theo ô đổi ngay.", [
					st.phieu.name,
					st.phieu.dong.length,
				]),
				nhan: __("Ghi phiếu"),
				khi_dong_y: () => {
					_luong
						.duyet()
						.then((kq) => {
							// Soát xét vòng 1, mục 5: `kq.muc` (mức màu) do LUỒNG quyết
							// (`duyet()` trong `luong/xep_hang.js`), không hardcode "xanh" ở
							// đây nữa.
							erpnext.kho_pda.KhoApp.bao(kq.bao, kq.muc);
							ve_tat_ca();
						})
						.catch((loi) => {
							// Máy chủ từ chối (dòng/ô lệch sau khi đã lên phiếu) — phiếu nháp
							// và các dòng còn NGUYÊN (`duyet_phieu_xep` rollback); nạp lại để
							// thấy đúng trạng thái, không tự đoán.
							bao_loi(loi);
							return nap();
						})
						.finally(() => this._oq && this._oq.giu_focus());
				},
				khi_dong: () => this._oq && this._oq.giu_focus(),
			});
		});

		nap().finally(() => this._oq && this._oq.giu_focus());
	},

	roi() {
		// `roi()` là móc dọn dẹp DUY NHẤT mà `vo.js::_ve_that()` gọi khi rời màn —
		// không gọi `huy()` thì `OQuet` này rò dần qua mỗi lượt vào/ra màn (đúng lỗi
		// Task 1 đã trả giá, xem `man_the.js`). Chịu được gọi khi CHƯA dựng gì
		// (`this._oq` còn `undefined`) — brief Task 3 đòi rõ điều này.
		this._oq && this._oq.huy();
		this._oq = null;
	},
});
