// Màn "Lấy hàng theo phiếu giao" — MÀN NẶNG NHẤT của app PDA (Task 4). Phần
// QUYẾT ĐỊNH ("quét mã này thì làm gì", "lô hết hạn có lấy được không", "đổi lô hay
// tách dòng", "số lượng/đơn vị/số kiện mặc định", nhãn và câu báo) nằm ở
// `../warehouse_operations/luong/lay_hang.js` — CÙNG một file mà trang Desk cũ
// (`warehouse_operations/page/lay_hang_pda/lay_hang_pda.js`, Bước 6 của brief) cũng
// dùng. File này CHỈ VẼ: không tự suy luật lô hết hạn, không tự chọn gọi `doi_lo`
// hay `tach_dong_theo_lo`, không tự viết câu báo, không tự tính số lượng/số kiện
// mặc định — mọi thứ đọc thẳng từ `_luong.trang_thai()` hoặc kết quả trả về của
// `_luong.quet()`/`_luong.hoi_*()`.
//
// Nút "Hoàn tất" (và mọi hộp xác nhận khác của màn) đi qua `erpnext.kho_pda.hoi()`
// — hộp này KHÔNG nghe phím. Súng quét gửi Enter sau mỗi lần bắn, và một hộp bắt
// Enter từng DUYỆT NHẦM một phiếu thật ngày 17/09/2026, xem `hop_thoai.js`.
//
// TRÌNH NGHE UỶ QUYỀN GẮN LÊN `$goc`, KHÔNG LÊN `$than` (bài học đắt của Task 3,
// soát xét vòng 1 P1): `vo.js::_ve_that()` chỉ `.empty()` phần CON của `$than` (nay
// thêm `.off()` làm lưới an toàn, nhưng đừng ỷ vào đó). Bản đầu của `man_xep_hang.js`
// gắn ~9 handler thẳng lên `$than`, đo được rò 10 → 37 sau 3 vòng vào/ra màn, và
// MỘT cú bấm "Hoàn tất phiếu" bật ra 4 hộp xác nhận chồng nhau — đồng ý cả bốn thì
// lệnh duyệt (một lời GHI thật) chạy 4 LẦN. `$goc` là phần tử CON được
// `$than.html(...)` dựng LẠI mỗi lượt `ve()`, nên handler cũ tự biến mất cùng DOM cũ.
//
// HỎI LẠI MÁY CHỦ TRƯỚC KHI HỎI NGƯỜI DÙNG: mọi hộp xác nhận của màn này (bỏ một
// lượt đã lấy, chốt thiếu, hoàn tất) dựng câu hỏi từ `_luong.hoi_*()` — hàm đó tự
// nạp lại phiếu từ máy chủ trước. Đây là màn GHI; hỏi "bỏ lượt 5 Hộp ở ô 1A01?" dựa
// trên một ảnh chụp cũ là hỏi về một thứ có thể không còn ở đó nữa (màn Tra cứu
// chạm dòng lịch sử với 0 lời gọi máy chủ là chuyện khác — màn đó CHỈ ĐỌC).

frappe.provide("erpnext.kho_pda");

// Một luồng SỐNG SUỐT phiên app, giống `man_tra_cuu.js`/`man_xep_hang.js` — thủ kho
// đang lấy dở một phiếu, quay ra kiểm việc khác rồi vào lại "Lấy hàng" vẫn thấy đúng
// phiếu và đúng lô đang chờ, không phải mở lại phiếu từ danh sách.
//
// TASK 6, VIỆC THÊM NGOÀI BRIEF 1: dựng LƯỜI ở lần `ve()` ĐẦU TIÊN, KHÔNG ở cấp
// module như bản cũ (`const _luong = _LUONG_NS.tao(...)` chạy NGAY lúc `import`,
// cùng biến `const _LUONG_NS = erpnext.warehouse_operations.luong.lay_hang;` chụp
// nhanh namespace ở cấp module — cả hai đã bỏ, xem khuôn đầy đủ ở `man_tra_cuu.js`
// và `man_xep_hang.js`, cùng đợt sửa). Bản cũ khoá cứng thứ tự các dòng `import`
// trong `kho_pda.bundle.js`: đảo nhầm một dòng là màn này chết hẳn ngay lúc tải
// trang, không bài test nào bắt được. `_luong` vẫn là biến module-scope (không
// còn `const`) để giữ ĐÚNG tính SINGLETON — `_dung_luong()` chỉ dựng khi còn
// `null`, các lượt `ve()` sau tái dùng để giữ phiếu đang lấy dở.
let _luong = null;

// Tên phiếu đã mở theo TUYẾN SÂU `#/lay-hang/<phiếu>` — cấp module, cùng vòng đời
// với `_luong` (singleton sống suốt phiên). Xem chỗ dùng ở cuối `ve()`.
let _phieu_theo_duong_dan = null;

// Tên phiếu lấy từ hash: gỡ mã hoá URL (dấu cách, ký tự lạ) và bỏ khoảng trắng
// thừa; rỗng thì trả `null` để `ve()` đi đường danh sách như thường.
function _ten_phieu_tu_hash(tho) {
	let ten = String(tho || "");
	try {
		ten = decodeURIComponent(ten);
	} catch (e) {
		// Hash hỏng (dấu `%` lẻ do gõ tay) — dùng nguyên văn, để máy chủ trả lời
		// "không tìm thấy phiếu" thay vì ném `URIError` câm ngay lúc mở màn.
	}
	return ten.trim() || null;
}

function _dung_luong() {
	if (!_luong) {
		_luong = erpnext.warehouse_operations.luong.lay_hang.tao({
			goi: (duong_dan, doi_so) => erpnext.kho_pda.KhoApp.goi(duong_dan, doi_so),
			// Định dạng ngày cho NGƯỜI ĐỌC — thứ DUY NHẤT phụ thuộc môi trường mà lớp
			// luồng cần cho màn này (xem đầu `luong/lay_hang.js`).
			ngay: (gia_tri) => frappe.datetime.str_to_user(gia_tri),
		});
	}
	return _luong;
}

// Đổi ca (cùng lý do `man_tra_cuu.js`/`man_xep_hang.js`): người SAU quét thẻ vào
// (không tải lại trang) không được thừa hưởng phiếu đang lấy dở của người TRƯỚC.
// Coi `""` (lỗi mạng lúc đọc `nguoi_dung`) là "không xác định" và LUÔN dọn.
let _nguoi_dung_luc_vao = erpnext.kho_pda.KhoApp.nguoi_dung;

function _e(gia_tri) {
	return frappe.utils.escape_html(String(gia_tri == null ? "" : gia_tri));
}

function _so(gia_tri) {
	return _e(flt(gia_tri).toLocaleString("vi-VN", { maximumFractionDigits: 3 }));
}

// Tô đậm AN TOÀN — bản dùng tại chỗ của `vo.js::_dam()` (không xuất ra ngoài file
// đó): escape TOÀN BỘ trước, RỒI MỚI đổi `**x**` (quy ước do LỚP LUỒNG tự đánh dấu)
// thành `<b>x</b>` CỦA RIÊNG hàm này. Thứ tự đó là điểm mấu chốt — một câu lấy từ
// máy chủ không có cách nào nhét được một thẻ HTML thật vào màn hình. Dùng cho hai
// chỗ KHÔNG đi qua `KhoApp.bao()` (thẻ "lô khác", banner chốt thiếu), nơi câu chữ
// vẫn là của luồng và vẫn mang dấu `**`.
function _dam(chu) {
	return frappe.utils.escape_html(String(chu == null ? "" : chu)).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
}

function _rung(kq) {
	let mau;
	// "xanh" = một lượt GHI vừa thành công (ghi lượt lấy, đổi/tách lô, duyệt phiếu)
	// — ba nhịp ngắn, nhịp mà thủ kho nhận ra qua găng tay mà không cần nhìn màn.
	if (kq.muc === "xanh") mau = [40, 40, 40];
	else if (kq.muc === "do") mau = [120, 80, 120];
	else if (kq.muc === "cam") mau = [80, 60, 80];
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
	if (st.khong_co_kho) {
		$dau.html(`<div class="kho-bao-o muc-cam">${_e(__("Chưa kho nào bật quản lý vị trí."))}</div>`);
		return;
	}
	if (st.hien_chon_kho) {
		$dau.html(`
			<div class="kho-tieu-de-muc">${__("Chọn kho")}</div>
			<div class="xh2-chon-kho-ds">
				${st.kho_ds
					.map((k) => `<button type="button" class="xh2-chon-kho lh2-chon-kho" data-kho="${_e(k)}">${_e(k)}</button>`)
					.join("")}
			</div>`);
		return;
	}
	// `hien_doi_kho` là kết luận CỦA LUỒNG (nhiều kho + chưa mở phiếu nào), không
	// phải phép so `kho_ds.length > 1 && !phieu` gõ lại ở mỗi lớp vẽ.
	const doi_kho = st.hien_doi_kho
		? `<button type="button" class="xh2-lien-ket-nho lh2-doi-kho">${__("Đổi")}</button>`
		: "";
	const phieu = st.phieu
		? `<span class="xh2-cham">·</span>
			<span class="xh2-ma-phieu">${_e(st.phieu.name)}</span>
			<span class="xh2-mo">${_e(st.phieu.khach_hang || "")}</span>
			<button type="button" class="xh2-lien-ket-nho lh2-ve-danh-sach">${__("← Danh sách")}</button>`
		: "";
	$dau.html(`
		<div class="xh2-kho">
			<span class="xh2-mo">${__("Kho")}</span> <b>${_e(st.kho)}</b> ${doi_kho}
			${phieu}
		</div>`);
}

// Thẻ "lô khác lô đang chốt" — MỌI kết luận (câu giải thích, có cảnh báo hạn không,
// nhãn nút) đọc thẳng từ `st.lo_khac`; màn không tự dựng câu nào.
function _ve_lo_khac($khoi, st) {
	const lk = st.lo_khac;
	if (!lk) return $khoi.empty();
	$khoi.html(`
		<div class="kho-the lh2-the-lo-khac">
			<div>${_dam(lk.cau)}</div>
			${lk.canh_bao ? `<div class="lh2-canh-bao-han">${_e(lk.canh_bao)}</div>` : ""}
			<div class="xh2-mo">${_e(lk.nhac)}</div>
			<button type="button" class="xh2-nut-chinh lh2-xac-nhan-lo-khac">${_e(lk.nhan_nut)}</button>
			<button type="button" class="xh2-lien-ket-nho lh2-bo-lo">${__("Thôi, bỏ qua")}</button>
		</div>`);
}

// Hàng nút đơn vị — `hien_chon_don_vi` là kết luận của luồng ("dưới hai lựa chọn
// thì không có gì để chọn"), không phải `ds.length < 2` gõ lại ở đây.
function _html_chon_don_vi(c) {
	if (!c.hien_chon_don_vi) return "";
	return `
		<div class="xh2-muc">
			<div class="kho-tieu-de-muc">${__("Đơn vị")}</div>
			<div class="lh2-chon-don-vi-ds">
				${c.don_vi_chon
					.map(
						(x) => `<button type="button" class="lh2-chon-don-vi ${
							x.uom === c.don_vi ? "dang-chon" : ""
						}" data-uom="${_e(x.uom)}">${_e(x.uom)}${
							flt(x.he_so) !== 1 ? `<small> = ${_so(x.he_so)} ${_e(c.don_vi_ton)}</small>` : ""
						}</button>`
					)
					.join("")}
			</div>
		</div>`;
}

function _ve_cho($khoi, st) {
	const c = st.cho;
	if (!c) return $khoi.empty();
	$khoi.html(`
		<div class="kho-the lh2-the-cho">
			<div class="kho-the-dau">
				<div class="xh2-dong-tren">
					<span class="kho-nhan-loai loai-lo">${
						c.so_lo ? __("Đang lấy lô") : __("Đang lấy hàng (không lô)")
					}</span>
					<button type="button" class="xh2-lien-ket-nho lh2-bo-lo">${__("Bỏ lô này")}</button>
				</div>
				${
					c.so_lo
						? `<div class="kho-the-ma">${_e(c.so_lo)}</div>`
						: `<div class="kho-the-ten">${_e(c.ten_hang || c.vat_tu)}</div>`
				}
			</div>

			${_html_chon_don_vi(c)}

			<div class="xh2-muc">
				<div class="kho-tieu-de-muc">${__("Số lượng lấy")}${c.don_vi ? ` · ${_e(c.don_vi)}` : ""}</div>
				<div class="xh2-so-luong-hang">
					<button type="button" class="xh2-cong-tru lh2-cong-tru" data-buoc="-1">−</button>
					<input type="number" class="xh2-so-luong lh2-so-luong" inputmode="decimal" min="0" step="any"
						value="${flt(c.so_luong)}" />
					<button type="button" class="xh2-cong-tru lh2-cong-tru" data-buoc="1">+</button>
				</div>
			</div>

			<div class="xh2-muc">
				<div class="kho-tieu-de-muc">${__("Số kiện (số tem)")}</div>
				<div class="xh2-so-luong-hang">
					<button type="button" class="xh2-cong-tru lh2-kien-cong-tru" data-buoc="-1">−</button>
					<span class="lh2-so-kien">${_e(c.so_kien)}</span>
					<button type="button" class="xh2-cong-tru lh2-kien-cong-tru" data-buoc="1">+</button>
				</div>
			</div>
		</div>`);
}

function _ve_danh_sach_phieu($t, st) {
	const ds = st.ds_phieu || [];
	if (!ds.length) {
		$t.html(
			`<div class="kho-bao-o muc-xam">${__("Không có phiếu giao nào đang chờ lấy ở kho này.")}</div>`
		);
		return;
	}
	$t.html(`
		<div class="kho-tieu-de-muc">${__("Phiếu đang chờ lấy · {0}", [ds.length])}</div>
		<div class="lh2-ds-phieu">
			${ds
				.map(
					(p) => `
				<button type="button" class="lh2-mo-phieu" data-phieu="${_e(p.name)}">
					<div class="lh2-mp-dau">
						<span class="xh2-ma-phieu">${_e(p.name)}</span>
						<span class="lh2-mp-sl">${_so(p.da_lay)}/${_so(p.can_lay)}</span>
					</div>
					<div class="xh2-mo">${_e(p.khach_hang || "")} · ${_so(p.so_dong)} ${__("dòng")}</div>
					${
						(p.nguoi_dang_lay || []).length
							? `<div class="lh2-dang-lay">${__("{0} đang lấy", [_e(p.nguoi_dang_lay.join(", "))])}</div>`
							: ""
					}
				</button>`
				)
				.join("")}
		</div>`);
}

// Một dòng hàng. MỌI kết luận đã có sẵn trên `d` (`du`, `ly_do_khong_quet`,
// `hien_nut_chot_thieu`, `banner_chot_thieu`, `cau_thieu_trong_lo`,
// `cau_lo_nen_lay`, `canh_bao_han`, `khac_don_vi`) — vẽ, không nghĩ.
function _html_mot_dong(d) {
	if (d.ly_do_khong_quet) {
		return `
			<div class="lh2-dong lh2-dong-mo">
				<div class="lh2-dong-dau">
					<div class="lh2-dong-ten">${_e(d.ten_hang)}</div>
					<div class="lh2-dong-sl">${_so(d.da_lay)}/${_so(d.can_lay)}<small>${_e(d.don_vi || "")}</small></div>
				</div>
				<div class="xh2-mo">${_e(d.vat_tu)}${d.so_lo ? " · lô " + _e(d.so_lo) : ""}</div>
				<div class="xh2-mo">${_e(d.ly_do_khong_quet)}</div>
			</div>`;
	}

	const chot = d.banner_chot_thieu
		? `<div class="lh2-chot-banner">
				<div>${_dam(d.banner_chot_thieu)}</div>
				<button type="button" class="xh2-lien-ket-nho lh2-bo-chot-thieu" data-dong="${_e(
					d.dong_hang
				)}">${__("Bỏ chốt thiếu")}</button>
			</div>`
		: "";

	const goi_y = d.o_nen_lay.length
		? `<div class="lh2-goi-y-ds">
				<span class="kho-nhan">${__("Nên lấy")}</span>
				${d.o_nen_lay
					.map(
						(g) =>
							`<span class="lh2-goi-y-o"><span class="lh2-ma">${_e(
								g.ma_in_nhan || g.o
							)}</span> <b>${_so(g.so_luong)}</b> ${_e(d.don_vi_ton)}</span>`
					)
					.join("")}
			</div>`
		: "";

	const thieu_lo = d.cau_thieu_trong_lo
		? `<div class="lh2-thieu-lo">${_e(d.cau_thieu_trong_lo)}</div>`
		: "";

	const da_lay_o = d.da_lay_o.length
		? `<div class="lh2-da-lay-ds">
				${d.da_lay_o
					.map(
						(p) => `
					<div class="lh2-da-lay-dong">
						<span class="lh2-ma">${_e(p.ma_in_nhan || p.o)}</span>
						<span class="lh2-da-lay-sl">${_so(p.so_luong_lay)} ${_e(p.don_vi_lay)} · ${__("{0} kiện", [
							_e(p.so_kien),
						])}${p.so_kien_da_in >= p.so_kien ? " ✓" : ""}</span>
						<button type="button" class="xh2-xoa-dong lh2-bo-luot" data-luot="${_e(p.name)}" title="${_e(
							__("Bỏ lượt")
						)}">×</button>
					</div>`
					)
					.join("")}
			</div>`
		: "";

	const lo_nen = d.cau_lo_nen_lay
		? `<div class="xh2-mo">${_e(d.cau_lo_nen_lay)}</div>${
				d.canh_bao_han ? `<div class="lh2-canh-bao-han">${_e(d.canh_bao_han)}</div>` : ""
		  }`
		: "";

	const nut_chot_thieu = d.hien_nut_chot_thieu
		? `<button type="button" class="xh2-lien-ket-nho lh2-chot-thieu" data-dong="${_e(d.dong_hang)}">${__(
				"Chốt thiếu"
		  )}</button>`
		: "";

	return `
		<div class="lh2-dong ${d.du ? "lh2-dong-du" : ""}">
			<div class="lh2-dong-dau">
				<div class="lh2-dong-ten">${_e(d.ten_hang)}</div>
				<div class="lh2-dong-sl">${_so(d.da_lay)}/${_so(d.can_lay)}<small>${_e(d.don_vi || "")}</small>${
		d.khac_don_vi
			? `<div class="xh2-mo">${_so(d.da_lay_ton)}/${_so(d.can_lay_ton)} ${_e(d.don_vi_ton)}</div>`
			: ""
	}</div>
			</div>
			<div class="xh2-mo">${_e(d.vat_tu)}${d.so_lo ? " · lô " + _e(d.so_lo) : ""}${
		d.hsd_chu ? " · HSD " + _e(d.hsd_chu) : ""
	}</div>
			${lo_nen}
			${chot}
			${goi_y}
			${thieu_lo}
			${da_lay_o}
			${nut_chot_thieu}
		</div>`;
}

function _ve_than($t, st) {
	if (!st.kho) return $t.empty();
	if (!st.phieu) return _ve_danh_sach_phieu($t, st);
	$t.html(`
		<div class="kho-tieu-de-muc">${__("Các dòng hàng · {0}", [st.dong.length])}</div>
		${st.dong.map(_html_mot_dong).join("")}`);
}

function _ve_chan($c, st) {
	if (!st.hien_nut_hoan_tat) return $c.empty();
	const tem = st.trang_thai_tem
		? `<div class="lh2-trang-thai-tem ${st.trang_thai_tem.thieu ? "thieu" : ""}">${_e(
				st.trang_thai_tem.chu
		  )}</div>`
		: "";
	$c.html(`${tem}<button type="button" class="xh2-nut-chinh lh2-hoan-tat">${__("Hoàn tất phiếu")}</button>`);
}

// --------------------------------------------------------------------- màn

erpnext.kho_pda.KhoApp.dang_ky_man("lay-hang", {
	tieu_de: __("Lấy hàng"),

	// `tham_so` — phần sau dấu `/` trong hash. TUYẾN `#/lay-hang/<tên phiếu>` của
	// spec §5: mở THẲNG một phiếu giao (bản Desk vẫn có, `lay_hang_pda.js::
	// theo_duong_dan()` đọc `frappe.get_route()[1]`). Soát xét tổng (N3) đo được
	// đường ống này đã có đủ từ Task 1 (`vo.js` cắt và truyền tham số) mà KHÔNG màn
	// nào khai tham số thứ hai, nên tuyến im lặng không chạy: gõ
	// `#/lay-hang/DN-TEST` chỉ gọi `danh_sach_phieu_giao` rồi hiện danh sách, không
	// lỗi, không câu báo — đúng kiểu hỏng im lặng mà module này sinh ra để tránh.
	ve($than, tham_so) {
		// PHẢI là câu lệnh ĐẦU TIÊN: đoạn đổi ca ngay dưới đọc `_luong.doi_kho()` —
		// gọi sau đoạn đó, ở lượt `ve()` đầu tiên `_luong` vẫn còn `null`.
		_dung_luong();
		const _nguoi_dung_hien_tai = erpnext.kho_pda.KhoApp.nguoi_dung;
		if (!_nguoi_dung_hien_tai || _nguoi_dung_hien_tai !== _nguoi_dung_luc_vao) {
			_luong.doi_kho();
			// Người SAU không được thừa hưởng cả cờ "đã mở phiếu này theo đường dẫn"
			// của người TRƯỚC — không dọn thì tuyến sâu im lặng không mở lại phiếu.
			_phieu_theo_duong_dan = null;
			_nguoi_dung_luc_vao = _nguoi_dung_hien_tai;
		}

		$than.html(`
			<div class="man-lay-hang">
				<div class="lh2-dau"></div>
				<div class="lh2-o-quet"></div>
				<div class="lh2-lo-khac"></div>
				<div class="lh2-cho"></div>
				<div class="lh2-than"></div>
				<div class="lh2-chan"></div>
			</div>
		`);

		// MỌI `.on(...)` của màn gắn lên `$goc` — phần tử CON vừa dựng LẠI ở trên,
		// KHÔNG lên `$than` (xem cảnh báo đầu file).
		const $goc = $than.find(".man-lay-hang");

		const $dau = $than.find(".lh2-dau");
		const $lo_khac = $than.find(".lh2-lo-khac");
		const $cho = $than.find(".lh2-cho");
		const $t = $than.find(".lh2-than");
		const $chan = $than.find(".lh2-chan");

		// Số thứ tự lượt quét — bắn hai mã liền nhau thì câu trả lời của mã TRƯỚC có
		// thể bay về SAU câu trả lời của mã sau; không có số này màn hình dừng ở kết
		// quả CŨ dù đã quét mới (cùng lẽ `man_tra_cuu.js`/`man_xep_hang.js`).
		let lan = 0;

		const ve_tat_ca = () => {
			const st = _luong.trang_thai();
			_ve_dau($dau, st);
			_ve_lo_khac($lo_khac, st);
			_ve_cho($cho, st);
			_ve_than($t, st);
			_ve_chan($chan, st);
			this._oq &&
				this._oq.dat_goi_y(st.goi_y_o_quet.chu, st.goi_y_o_quet.nhan_manh ? "nhan-manh" : undefined);
		};

		// `loi.message` là câu THẬT của máy chủ (`KhoApp.goi()` đã rút từ
		// `_server_messages`) — chỉ còn lỗi nghiệp vụ ghi thật sự bất ngờ tới đây,
		// `goi()` đã tự lo 401/403/mất mạng (xem đầu `vo.js`).
		const bao_loi = (loi) => erpnext.kho_pda.KhoApp.bao((loi && loi.message) || __("Có lỗi, thử lại."), "do");

		const nap = () => {
			const st = _luong.trang_thai();
			return (st.phieu ? _luong.lam_moi() : _luong.danh_sach())
				.then(ve_tat_ca)
				.catch(bao_loi);
		};

		// Kết quả của MỘT thao tác luồng: hiện câu báo do luồng quyết, rung theo mức
		// của luồng, vẽ lại. `nap_lai` là cờ luồng bật khi phiếu đã đổi dưới chân.
		const hien = (kq) => {
			if (kq.bao) erpnext.kho_pda.KhoApp.bao(kq.bao, kq.muc || "xam");
			else erpnext.kho_pda.KhoApp.bao();
			_rung(kq);
			ve_tat_ca();
			if (kq.nap_lai) return nap();
		};

		const quet = (ma) => {
			const lan_nay = ++lan;
			erpnext.kho_pda.KhoApp.bao();
			_luong
				.quet(ma)
				.then((kq) => {
					if (lan_nay !== lan) return;
					return hien(kq);
				})
				.catch((loi) => {
					// Máy chủ từ chối ghi (`ghi_da_lay`/`doi_lo`/`tach_dong_theo_lo`) —
					// luồng CỐ Ý không nuốt lỗi này (xem đầu `luong/lay_hang.js`).
					if (lan_nay !== lan) return;
					bao_loi(loi);
				})
				.finally(() => {
					if (lan_nay === lan) this._oq && this._oq.giu_focus();
				});
		};

		this._oq = new erpnext.kho_pda.OQuet({
			cha: $than.find(".lh2-o-quet"),
			vung: $than,
			placeholder: __("Quét tem…"),
			goi_y: "",
			khi_quet: (ma) => quet(ma),
		});

		const giu_focus = () => this._oq && this._oq.giu_focus();

		// Một thao tác GHI có hộp xác nhận: `chuan_bi` tự NẠP LẠI phiếu từ máy chủ và
		// trả câu hỏi (hoặc lý do không hỏi được nữa); `lam` là lời ghi thật.
		const hoi_roi_lam = (chuan_bi, lam) => {
			erpnext.kho_pda.KhoApp.bao();
			chuan_bi()
				.then((h) => {
					ve_tat_ca();
					if (!h.ok) {
						erpnext.kho_pda.KhoApp.bao(h.bao, h.muc || "cam");
						giu_focus();
						return;
					}
					erpnext.kho_pda.hoi({
						noi_dung: h.cau,
						// NHÃN NÚT cũng là câu chữ của LUỒNG (`h.nhan`) — màn không tự gõ
						// "Bỏ lượt"/"Chốt thiếu"/"Duyệt phiếu" nữa.
						nhan: h.nhan || __("Đồng ý"),
						khi_dong_y: () => {
							lam()
								.then(hien)
								.catch((loi) => {
									bao_loi(loi);
									return nap();
								})
								.finally(giu_focus);
						},
						khi_dong: giu_focus,
					});
				})
				.catch((loi) => {
					bao_loi(loi);
					giu_focus();
				});
		};

		$goc.on("click", ".lh2-chon-kho", (ev) => {
			const kho = $(ev.currentTarget).attr("data-kho");
			erpnext.kho_pda.KhoApp.bao();
			_luong.danh_sach(kho).then(ve_tat_ca).catch(bao_loi).finally(giu_focus);
		});

		$goc.on("click", ".lh2-doi-kho", () => {
			_luong.doi_kho();
			erpnext.kho_pda.KhoApp.bao();
			ve_tat_ca();
			giu_focus();
		});

		$goc.on("click", ".lh2-mo-phieu", (ev) => {
			const ten = $(ev.currentTarget).attr("data-phieu");
			erpnext.kho_pda.KhoApp.bao();
			_luong
				.mo(ten)
				.then((st) => {
					ve_tat_ca();
					// `mo()` trả `bao` khi phiếu đã duyệt/huỷ giữa chừng — câu chữ của LUỒNG.
					if (st.bao) erpnext.kho_pda.KhoApp.bao(st.bao, st.muc);
				})
				.catch(bao_loi)
				.finally(giu_focus);
		});

		$goc.on("click", ".lh2-ve-danh-sach", () => {
			erpnext.kho_pda.KhoApp.bao();
			_luong.ve_danh_sach().then(ve_tat_ca).catch(bao_loi).finally(giu_focus);
		});

		$goc.on("click", ".lh2-bo-lo", () => {
			_luong.bo_lo();
			erpnext.kho_pda.KhoApp.bao();
			ve_tat_ca();
			giu_focus();
		});

		// Nút "Đổi sang lô …": lớp vẽ CHỈ nói "người dùng đồng ý" — `doi_lo` hay
		// `tach_dong_theo_lo` là quyết định của LỚP LUỒNG (luật đắt nhất của màn).
		$goc.on("click", ".lh2-xac-nhan-lo-khac", () => {
			_luong
				.xac_nhan_doi_lo()
				.then(hien)
				.catch((loi) => {
					bao_loi(loi);
					return nap();
				})
				.finally(giu_focus);
		});

		$goc.on("click", ".lh2-chon-don-vi", (ev) => {
			_luong.dat_don_vi($(ev.currentTarget).attr("data-uom"));
			ve_tat_ca();
			giu_focus();
		});

		$goc.on("input", ".lh2-so-luong", (ev) => {
			// KHÔNG vẽ lại khi đang gõ (mất vị trí con trỏ) — chỉ cập nhật trạng thái;
			// `change` bên dưới vẽ lại khi gõ xong.
			_luong.dat_so_luong(ev.currentTarget.value);
		});
		$goc.on("change", ".lh2-so-luong", (ev) => {
			_luong.dat_so_luong(ev.currentTarget.value);
			ve_tat_ca();
		});
		// Enter trên ô số lượng: xong sửa số, trả focus cho súng quét.
		$goc.on("keydown", ".lh2-so-luong", (ev) => {
			if (ev.key !== "Enter") return;
			ev.preventDefault();
			ev.currentTarget.blur();
			giu_focus();
		});

		$goc.on("click", ".lh2-cong-tru", (ev) => {
			const buoc = Number($(ev.currentTarget).attr("data-buoc"));
			const st = _luong.trang_thai();
			if (!st.cho) return;
			const sau = _luong.dat_so_luong(flt(st.cho.so_luong) + buoc);
			// Cập nhật TẠI CHỖ, không vẽ lại cả thẻ: vẽ lại làm mất focus và nhấp nháy
			// đúng lúc thủ kho đang bấm liên tiếp (cùng khuôn `man_xep_hang.js`).
			$goc.find(".lh2-so-luong").val(sau.cho ? sau.cho.so_luong : 0);
			$goc.find(".lh2-so-kien").text(sau.cho ? sau.cho.so_kien : "");
		});

		$goc.on("click", ".lh2-kien-cong-tru", (ev) => {
			const buoc = Number($(ev.currentTarget).attr("data-buoc"));
			const st = _luong.trang_thai();
			if (!st.cho) return;
			const sau = _luong.dat_so_kien(flt(st.cho.so_kien) + buoc);
			$goc.find(".lh2-so-kien").text(sau.cho ? sau.cho.so_kien : "");
		});

		$goc.on("click", ".lh2-bo-luot", (ev) => {
			const ten = $(ev.currentTarget).attr("data-luot");
			hoi_roi_lam(
				() => _luong.hoi_bo_luot(ten),
				() => _luong.bo_luot(ten)
			);
		});

		$goc.on("click", ".lh2-chot-thieu", (ev) => {
			const dong = $(ev.currentTarget).attr("data-dong");
			hoi_roi_lam(
				() => _luong.hoi_chot_thieu(dong),
				() => _luong.chot_thieu(dong)
			);
		});

		$goc.on("click", ".lh2-bo-chot-thieu", (ev) => {
			const dong = $(ev.currentTarget).attr("data-dong");
			_luong
				.bo_chot_thieu(dong)
				.then(hien)
				.catch((loi) => {
					bao_loi(loi);
					return nap();
				})
				.finally(giu_focus);
		});

		// "Hoàn tất" — lời GHI nặng nhất của màn (duyệt phiếu giao, trừ sổ vị trí
		// thật). Đi qua `erpnext.kho_pda.hoi()`, hộp KHÔNG nghe phím.
		$goc.on("click", ".lh2-hoan-tat", () => {
			hoi_roi_lam(
				() => _luong.hoi_hoan_tat(),
				() =>
					_luong.hoan_tat().then((kq) =>
						// Sau khi duyệt, phiếu không còn — nạp lại danh sách để thủ kho đi
						// tiếp phiếu sau, GIỮ câu báo của luồng cho lượt vẽ này.
						_luong.danh_sach().then(() => kq)
					)
			);
		});

		// TUYẾN SÂU `#/lay-hang/<tên phiếu>` — cùng khuôn `theo_duong_dan()` của bản
		// Desk (`lay_hang_pda.js`), kể cả cái bẫy nó đã tránh: NHỚ tên phiếu đã mở
		// theo đường dẫn (`_phieu_theo_duong_dan`, biến CẤP MODULE cạnh `_luong` —
		// luồng là singleton sống suốt phiên, cờ này phải sống cùng nó). Không nhớ
		// thì mỗi lượt quay lại màn (từ menu, hash vẫn còn đuôi cũ) sẽ MỞ LẠI phiếu
		// từ máy chủ và ném mất phần đang lấy dở. `decodeURIComponent`: tên phiếu đi
		// qua hash nên dấu cách/ký tự lạ đã bị mã hoá.
		const ten_phieu = tham_so && tham_so.length ? _ten_phieu_tu_hash(tham_so[0]) : null;
		if (ten_phieu && ten_phieu !== _phieu_theo_duong_dan) {
			_phieu_theo_duong_dan = ten_phieu;
			_luong
				.mo(ten_phieu)
				.then((st) => {
					ve_tat_ca();
					// `bao` chỉ có khi phiếu đã duyệt/huỷ — CÂU CHỮ của luồng. Rơi về danh
					// sách, đúng như bản Desk làm.
					if (st.bao) {
						erpnext.kho_pda.KhoApp.bao(st.bao, st.muc);
						return nap();
					}
				})
				.catch((loi) => {
					// Phiếu không tồn tại / không có quyền: câu THẬT của máy chủ, rồi rơi
					// về danh sách thay vì để màn trống.
					bao_loi(loi);
					return nap();
				})
				.finally(giu_focus);
			return;
		}

		nap().finally(giu_focus);
	},

	roi() {
		// `roi()` là móc dọn dẹp DUY NHẤT mà `vo.js::_ve_that()` gọi khi rời màn —
		// không gọi `huy()` thì `OQuet` này rò dần qua mỗi lượt vào/ra màn. Chịu được
		// gọi khi CHƯA dựng gì (`this._oq` còn `undefined`).
		this._oq && this._oq.huy();
		this._oq = null;
	},
});
