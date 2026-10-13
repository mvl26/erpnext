// Màn "Đặt ô trên tem hàng loạt" — bản gốc Desk (`dat_o_hang_loat.js`, 291 dòng)
// là một BẢNG RỘNG của máy tính (một dòng/lô, cột "Ô trên tem" là một Link
// control full-width). KHÔNG bê nguyên được vào màn 4 inch: brief Task 5 đòi
// THIẾT KẾ LẠI — mỗi lô là một THẺ DỌC (số lô · mặt hàng · tồn · ô trên tem, có
// nút chọn ô), ô lọc + nút "Chọn tất cả dòng có ô" ở trên, nút "Đặt ô cho N dòng"
// ở dưới cùng, và một dòng nhắc "bảng rộng — nên làm trên máy tính".
//
// Phần QUYẾT ĐỊNH ("dòng nào tự chọn sẵn", "dòng nào cho đặt", câu chữ) nằm ở
// `../warehouse_operations/luong/dat_o.js` — CÙNG một file mà trang Desk cũ
// (`warehouse_operations/page/dat_o_hang_loat/dat_o_hang_loat.js`, Bước 6 của
// brief) cũng dùng. File này CHỈ VẼ: không tự suy "dòng nào tick sẵn", không tự
// viết câu báo — mọi thứ đọc thẳng từ `_luong.trang_thai()`.
//
// KHÔNG có ô quét (`OQuet`) trên màn này — khác Tra cứu/Xếp hàng/Lấy hàng: đây là
// một màn CHỌN TỪ DANH SÁCH + GÕ TAY, không phải một màn bắn súng quét. Vì vậy
// KHÔNG có `roi()` dọn `OQuet` (không có gì để dọn) — `vo.js::_ve_that()` gọi
// `roi` là TUỲ CHỌN (`if (... .roi) { ... }`), không có thì bỏ qua, không lỗi.
//
// Nút "Đặt ô cho N dòng" đi qua `erpnext.kho_pda.hoi()` — hộp này không nghe
// phím; cùng lý do `man_xep_hang.js`/`man_lay_hang.js`: một hộp bắt Enter từng
// làm DUYỆT NHẦM một phiếu thật (17/09/2026). Màn này không có súng quét, nhưng
// khuôn CHUNG của app (một cách hỏi DUY NHẤT cho mọi lời GHI) không có ngoại lệ
// theo màn — dùng `hoi()` cho MỌI xác nhận ghi, kể cả trên một màn không quét,
// để không ai phải nhớ "màn nào được phép confirm() kiểu khác".
//
// TRÌNH NGHE UỶ QUYỀN GẮN LÊN `$goc`, KHÔNG LÊN `$than` — bài học đắt của Task 3
// (soát xét vòng 1, P1): `vo.js::_ve_that()` chỉ `.empty()` phần CON của `$than`
// (nay có `.off()` làm lưới an toàn, nhưng đừng ỷ vào đó). `$goc` là phần tử CON
// được `$than.html(...)` dựng LẠI mỗi lượt `ve()`, nên handler cũ tự biến mất
// cùng DOM cũ khi rời màn.

frappe.provide("erpnext.kho_pda");

// Một luồng SỐNG SUỐT phiên app, cùng khuôn `man_xep_hang.js`/`man_lay_hang.js`
// — thủ kho đang sửa ô của vài lô, quay ra kiểm việc khác rồi vào lại "Đặt ô" vẫn
// thấy đúng những ô mình vừa gõ, không phải soát lại từ đầu.
//
// TASK 6, VIỆC THÊM NGOÀI BRIEF 1: dựng LƯỜI ở lần `ve()` ĐẦU TIÊN, KHÔNG ở cấp
// module như bản cũ (`const _luong = _LUONG_NS.tao(...)` chạy NGAY lúc `import`,
// cùng biến `const _LUONG_NS = erpnext.warehouse_operations.luong.dat_o;` chụp
// nhanh namespace ở cấp module — cả hai đã bỏ, xem khuôn đầy đủ ở `man_tra_cuu.js`.
// Bản cũ khoá cứng thứ tự các dòng `import` trong `kho_pda.bundle.js`: đảo nhầm
// một dòng là màn này chết hẳn ngay lúc tải trang, không bài test nào bắt được.
// `_luong` vẫn là biến module-scope (không còn `const`) để giữ ĐÚNG tính
// SINGLETON — `_dung_luong()` chỉ dựng khi còn `null`, các lượt `ve()` sau tái
// dùng để giữ những ô vừa gõ dở.
let _luong = null;

function _dung_luong() {
	if (!_luong) {
		_luong = erpnext.warehouse_operations.luong.dat_o.tao({
			goi: (duong_dan, doi_so) => erpnext.kho_pda.KhoApp.goi(duong_dan, doi_so),
		});
	}
	return _luong;
}

// Đổi ca (cùng lý do ba màn trước): người SAU quét thẻ vào không được thừa hưởng
// danh sách/lựa chọn đang sửa dở của người TRƯỚC. `""` (lỗi mạng lúc đọc
// `nguoi_dung`) coi là "không xác định", LUÔN dọn — thà xoá oan còn hơn lộ dữ
// liệu người khác.
let _nguoi_dung_luc_vao = erpnext.kho_pda.KhoApp.nguoi_dung;

function _e(gia_tri) {
	return frappe.utils.escape_html(String(gia_tri == null ? "" : gia_tri));
}

function _so(gia_tri) {
	return _e(flt(gia_tri).toLocaleString("vi-VN", { maximumFractionDigits: 3 }));
}

function _ngay(gia_tri) {
	return gia_tri ? frappe.datetime.str_to_user(gia_tri) : "";
}

// Tô đậm AN TOÀN — bản dùng tại chỗ của `vo.js::_dam()` (không xuất ra ngoài file
// đó, cùng lý do `man_lay_hang.js` có bản riêng): escape TOÀN BỘ trước, RỒI MỚI
// đổi `**x**` (quy ước do LỚP LUỒNG tự đánh dấu) thành `<b>x</b>` CỦA RIÊNG hàm
// này. Dùng cho những chỗ KHÔNG đi qua `KhoApp.bao()` (câu mở đầu của màn) —
// KhoApp.bao() tự làm việc này cho dải báo, không cần gọi lại ở đây.
function _dam(chu) {
	return frappe.utils.escape_html(String(chu == null ? "" : chu)).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
}

// Ô LỌC KHÔNG CÒN Ở ĐÂY (soát xét tổng, M5): việc "đang hiện dòng nào" quyết định
// luôn việc "Chọn tất cả dòng có ô tác động lên dòng nào" — hai mặt của MỘT quyết
// định, nên cả hai nằm ở lớp luồng (`luong/dat_o.js::dat_bo_loc`). Màn này chỉ đọc
// `st.dong_hien`/`st.bo_loc`/`st.cau_loc_trong` và bắn chữ người dùng gõ vào luồng.

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
					.map((k) => `<button type="button" class="xh2-chon-kho do2-chon-kho" data-kho="${_e(k)}">${_e(k)}</button>`)
					.join("")}
			</div>`);
		return;
	}
	const doi_kho =
		st.kho_ds.length > 1
			? `<button type="button" class="xh2-lien-ket-nho do2-doi-kho">${__("Đổi")}</button>`
			: "";
	const cong_cu = st.dong.length
		? `<div class="do2-cong-cu">
				<input type="text" class="do2-loc" inputmode="search"
					placeholder="${_e(__("Lọc theo số lô / tên hàng…"))}" value="${_e(st.bo_loc)}">
				<button type="button" class="xh2-lien-ket-nho do2-chon-co-o">${__("Chọn tất cả dòng có ô")}</button>
			</div>`
		: "";
	$dau.html(`
		<div class="xh2-kho">
			<span class="xh2-mo">${__("Kho")}</span> <b>${_e(st.kho)}</b> ${doi_kho}
		</div>
		<div class="do2-mo-dau">${_dam(st.cau_dau)}</div>
		${cong_cu}
	`);
}

function _html_mot_dong(d) {
	const goi_y_khac =
		d.o_goi_y && d.o !== d.o_goi_y
			? `<button type="button" class="xh2-lien-ket-nho do2-dung-goi-y" data-o="${_e(d.o_goi_y)}">
					${__("Dùng ô gợi ý {0}", [_e(d.ma_in_nhan_goi_y || d.o_goi_y)])}
				</button>`
			: "";
	const thieu_o = !d.o
		? `<div class="do2-thieu-o">${_e(d.ly_do || __("Chưa có ô gợi ý — tự gõ một ô"))}</div>`
		: "";
	const loi = d.loi_dat ? `<div class="do2-loi">${_e(d.loi_dat)}</div>` : "";
	return `
		<div class="kho-the do2-dong" data-lo="${_e(d.so_lo)}">
			<label class="do2-dau">
				<input type="checkbox" class="do2-tick" ${d.chon ? "checked" : ""}>
				<span class="kho-the-ma">${_e(d.so_lo)}</span>
			</label>
			<div class="kho-the-ten">${_e(d.ten_hang || d.vat_tu)}</div>
			<div class="kho-the-mo">${_e(d.vat_tu)}${d.hsd ? " · HSD " + _e(_ngay(d.hsd)) : ""}</div>
			<div class="do2-hang">
				<span class="xh2-mo">${__("Tồn")}</span> <b>${_so(d.ton)}</b>
				${d.dang_o ? `<span class="xh2-cham">·</span><span class="xh2-mo">${__("Đang ở")} ${_e(d.dang_o)}</span>` : ""}
			</div>
			<div class="do2-o-muc">
				<div class="kho-tieu-de-muc">${__("Ô trên tem")}</div>
				<input type="text" class="do2-o-nhap" value="${_e(d.o)}" placeholder="${_e(d.ly_do || __("Chọn ô"))}">
				${goi_y_khac}
				${thieu_o}
				${loi}
			</div>
		</div>`;
}

function _ve_ds($ds, st) {
	if (!st.dong.length) return $ds.empty();
	// `dong_hien` + `cau_loc_trong` là kết luận CỦA LUỒNG (rule 2) — màn không tự
	// lọc lại và không tự gõ câu "không khớp bộ lọc" nữa.
	if (!st.dong_hien.length) {
		$ds.html(`<div class="kho-trong">${_e(st.cau_loc_trong)}</div>`);
		return;
	}
	$ds.html(st.dong_hien.map(_html_mot_dong).join(""));
}

function _ve_chan($chan, st) {
	if (!st.kho || st.trong) return $chan.empty();
	// `nhan_nut_dat`/`canh_bao_thieu_o` là câu CỦA LUỒNG (rule 2) — màn chỉ ghép
	// vào khung, không tự đếm lại `so_dong_chon`/`so_dong_thieu_o` để lắp câu.
	const canh_bao = st.canh_bao_thieu_o
		? `<div class="do2-thieu-o-canh-bao">${_e(st.canh_bao_thieu_o)}</div>`
		: "";
	$chan.html(`
		${canh_bao}
		<button type="button" class="xh2-nut-chinh do2-dat" ${st.dat_duoc ? "" : "disabled"}>${_e(st.nhan_nut_dat)}</button>
		<div class="do2-nhac-may-tinh">${_e(st.nhac_may_tinh)}</div>
	`);
}

// --------------------------------------------------------------------- màn

erpnext.kho_pda.KhoApp.dang_ky_man("dat-o", {
	tieu_de: __("Đặt ô"),

	// `tham_so` — phần sau dấu `/` trong hash (`vo.js::_theo_hash` cắt ra,
	// `vo.js::_ve_that` truyền vào). Màn này KHÔNG có tuyến sâu nào trong spec §5
	// (không có "mở thẳng một kho" — kho chọn bằng nút, và `mo(kho)` cần biết kho
	// đó có đang quản lý vị trí không). NHẬN ĐÚNG CHỮ KÝ rồi bỏ qua là CỐ Ý: soát
	// xét tổng (N3) đo được `vo.js` đã truyền tham số từ Task 1 mà KHÔNG màn nào
	// khai, nên `#/lay-hang/<phiếu>` im lặng không chạy. Khai đủ ở cả bốn màn để
	// chữ ký là MỘT, không ai phải nhớ màn nào nhận màn nào không.
	ve($than, tham_so) {
		// PHẢI là câu lệnh ĐẦU TIÊN: đoạn đổi ca ngay dưới đọc `_luong.doi_kho()` —
		// gọi sau đoạn đó, ở lượt `ve()` đầu tiên `_luong` vẫn còn `null`.
		_dung_luong();
		const _nguoi_dung_hien_tai = erpnext.kho_pda.KhoApp.nguoi_dung;
		if (!_nguoi_dung_hien_tai || _nguoi_dung_hien_tai !== _nguoi_dung_luc_vao) {
			_luong.doi_kho();
			_nguoi_dung_luc_vao = _nguoi_dung_hien_tai;
		}
		// Ô lọc reset mỗi lượt VÀO màn — giữ nguyên hành vi cũ (nó từng là một biến
		// cục bộ của `ve()`); nay nó sống ở luồng nên phải dọn tường minh.
		_luong.dat_bo_loc("");

		$than.html(`
			<div class="man-dat-o">
				<div class="do2-dau"></div>
				<div class="do2-ds"></div>
				<div class="do2-chan"></div>
			</div>
		`);

		// MỌI `.on(...)` của màn gắn lên `$goc` — phần tử CON vừa dựng LẠI ở trên,
		// KHÔNG lên `$than` (xem cảnh báo đầu file).
		const $goc = $than.find(".man-dat-o");

		const $dau = $than.find(".do2-dau");
		const $ds = $than.find(".do2-ds");
		const $chan = $than.find(".do2-chan");

		const ve_dau = () => _ve_dau($dau, _luong.trang_thai());
		const ve_ds = () => _ve_ds($ds, _luong.trang_thai());
		const ve_chan = () => _ve_chan($chan, _luong.trang_thai());

		// Vẽ lại TOÀN BỘ ba khối — dùng sau một hành động có thể đổi SỐ DÒNG hay
		// đổi KHO (chọn kho, nạp lại, đặt xong).
		const ve_tat_ca = () => {
			ve_dau();
			ve_ds();
			ve_chan();
		};

		// Vẽ lại CHỈ danh sách + chân màn — dùng sau tick/gõ ô: KHÔNG đụng `$dau`
		// (giữ nguyên ô lọc đang gõ dở, cùng lẽ `xh2-so-luong` ở các màn khác
		// không vẽ lại khi đang gõ để khỏi mất vị trí con trỏ).
		const ve_ds_va_chan = () => {
			ve_ds();
			ve_chan();
		};

		const bao_loi = (loi) => erpnext.kho_pda.KhoApp.bao((loi && loi.message) || __("Có lỗi, thử lại."), "do");

		// `mo()`/`nap()` bao API Task 1 (`goi`) đã tự lo phiên hết hạn/mất mạng —
		// chỉ còn lỗi nghiệp vụ thật sự bất ngờ (kho không còn quản lý vị trí…) tới
		// tay `bao_loi`.
		const nap = () => {
			const kho_hien_tai = _luong.trang_thai().kho;
			return (kho_hien_tai ? _luong.nap(kho_hien_tai) : _luong.mo()).then(ve_tat_ca).catch(bao_loi);
		};

		$goc.on("click", ".do2-chon-kho", (ev) => {
			const kho = $(ev.currentTarget).attr("data-kho");
			erpnext.kho_pda.KhoApp.bao();
			_luong.mo(kho).then(ve_tat_ca).catch(bao_loi);
		});

		$goc.on("click", ".do2-doi-kho", () => {
			_luong.doi_kho();
			erpnext.kho_pda.KhoApp.bao();
			ve_tat_ca();
		});

		$goc.on("input", ".do2-loc", (ev) => {
			// `ve_ds_va_chan()` (không `ve_dau()`): vẽ lại `$dau` là dựng lại CHÍNH ô
			// đang gõ — mất con trỏ giữa chừng.
			_luong.dat_bo_loc(ev.currentTarget.value || "");
			ve_ds_va_chan();
		});

		$goc.on("click", ".do2-chon-co-o", () => {
			_luong.chon_tat_ca(true);
			ve_ds_va_chan();
		});

		$goc.on("change", ".do2-tick", (ev) => {
			const so_lo = $(ev.currentTarget).closest(".do2-dong").attr("data-lo");
			_luong.chon(so_lo, ev.currentTarget.checked);
			ve_ds_va_chan();
		});

		// `input`: chỉ cập nhật trạng thái, KHÔNG vẽ lại (mất vị trí con trỏ nếu vẽ
		// lại giữa lúc đang gõ — cùng khuôn ô số lượng của `man_xep_hang.js`).
		// `change` (rời ô/Enter-blur): vẽ lại để hiện đúng tick tự động, gợi ý
		// "khác" (hay không), và trạng thái nút chân màn.
		$goc.on("input", ".do2-o-nhap", (ev) => {
			const so_lo = $(ev.currentTarget).closest(".do2-dong").attr("data-lo");
			_luong.dat_o_cho_dong(so_lo, ev.currentTarget.value);
		});
		$goc.on("change", ".do2-o-nhap", (ev) => {
			const so_lo = $(ev.currentTarget).closest(".do2-dong").attr("data-lo");
			_luong.dat_o_cho_dong(so_lo, ev.currentTarget.value);
			ve_ds_va_chan();
		});

		$goc.on("click", ".do2-dung-goi-y", (ev) => {
			const $the = $(ev.currentTarget).closest(".do2-dong");
			const so_lo = $the.attr("data-lo");
			const o = $(ev.currentTarget).attr("data-o");
			_luong.dat_o_cho_dong(so_lo, o);
			ve_ds_va_chan();
		});

		// "Đặt ô cho N dòng" — lời GHI của màn này. Đi qua `erpnext.kho_pda.hoi()`
		// (không nghe phím, xem đầu file). `hoi_dat()` TỰ nạp lại từ máy chủ trước
		// khi dựng câu hỏi (ràng buộc riêng Task 5: màn có GHI, không hỏi trên số
		// liệu cũ) — `ve_tat_ca()` ngay sau đó để thấy đúng danh sách VỪA nạp lại,
		// kể cả khi người dùng bấm "Không" trên hộp hỏi.
		$goc.on("click", ".do2-dat", () => {
			erpnext.kho_pda.KhoApp.bao();
			_luong
				.hoi_dat()
				.then((h) => {
					ve_tat_ca();
					if (!h.ok) {
						if (h.bao) erpnext.kho_pda.KhoApp.bao(h.bao, h.muc || "cam");
						return;
					}
					erpnext.kho_pda.hoi({
						noi_dung: h.cau,
						nhan: h.nhan || __("Đồng ý"),
						khi_dong_y: () => {
							// `kq.bao`/`kq.muc` là câu CỦA LUỒNG (rule 2) — `dat()` tự trả sẵn,
							// màn không tự lắp lại câu "Đã đặt ô cho N lô" nữa.
							_luong
								.dat()
								.then((kq) => {
									erpnext.kho_pda.KhoApp.bao(kq.bao, kq.muc);
									ve_tat_ca();
								})
								.catch(bao_loi);
						},
					});
				})
				.catch(bao_loi);
		});

		nap();
	},

	// KHÔNG có `roi()` — màn này không dựng `OQuet` nào (không có ô quét, xem đầu
	// file), nên không có gì cần `huy()`. `vo.js::_ve_that()` gọi `roi` là TUỲ
	// CHỌN, thiếu thì bỏ qua — không phải một lỗ hổng dọn dẹp.
});
