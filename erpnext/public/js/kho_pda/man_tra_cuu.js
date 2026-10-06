// Màn "Tra cứu" — màn NHẸ NHẤT của app PDA, dựng TRƯỚC các màn khác để thử khuôn
// "tách lớp luồng dùng chung": phần QUYẾT ĐỊNH ("quét mã này ra cái gì", "gọi nó là
// gì", "còn hạn hay không") nằm ở `../warehouse_operations/luong/tra_cuu.js` — CÙNG
// một file mà trang Desk cũ (`quet_ma_tra_cuu.js`, Bước 6 của brief) cũng dùng. File
// này chỉ VẼ: không tự map `loai` → nhãn, không tự viết câu báo, không tự tính hạn
// dùng (vòng sửa 1, soát xét `task-2-soat-xet.md` — tất cả ba thứ đó từng lặp ở đây
// và ở Desk, nay đọc thẳng từ `_ns()`).

frappe.provide("erpnext.kho_pda");

// Namespace của lớp luồng đọc LƯỜI — KHÔNG chụp nhanh (`const _LUONG_NS = ...`) ở
// cấp module. Lý do gộp chung với `_luong`/`_dung_luong()` ngay dưới: một biến
// `const` gán ở cấp module chạy NGAY lúc file này được `import`, tức phụ thuộc
// đúng cái thứ tự `import` mà Task 6 (việc thêm 1) phải dứt điểm. `_ns()` gọi
// `erpnext.warehouse_operations.luong.tra_cuu` LẠI mỗi lần cần, không giữ tham
// chiếu cũ — tới lúc bất kỳ hàm nào bên dưới thật sự CHẠY (luôn luôn là sau khi
// `ve()` chạy lần đầu, tức sau khi toàn bộ `kho_pda.bundle.js` đã nạp xong bất kể
// thứ tự `import`), namespace chắc chắn đã có mặt.
function _ns() {
	return erpnext.warehouse_operations.luong.tra_cuu;
}

// Một luồng SỐNG SUỐT phiên app — KHÔNG dựng lại mỗi lần vào màn (`ve()` chạy lại
// mỗi lần chuyển vào "tra-cuu", kể cả quay lại từ menu). Thủ kho quay ra kiểm việc
// khác rồi vào lại "Tra cứu" vẫn thấy các lần quét gần nhất — dựng luồng mới mỗi
// lần vào màn sẽ xoá sạch lịch sử đó, sai kỳ vọng "lịch sử các lần quét" của Bước 5.
//
// TASK 6, VIỆC THÊM NGOÀI BRIEF 1: dựng LƯỜI ở lần `ve()` ĐẦU TIÊN, KHÔNG ở cấp
// module như bản cũ (`const _luong = _LUONG_NS.tao(...)` chạy NGAY lúc `import`).
// Bản cũ khoá cứng thứ tự các dòng `import` trong `kho_pda.bundle.js`: đảo nhầm
// một dòng (namespace luồng nạp SAU file màn) khiến `.tao()` gọi trên một
// namespace còn `undefined`, ném `TypeError` NGAY LÚC TẢI TRANG — không một bài
// test Python nào ở đây bắt được vì không bài nào thực thi JS trong trình duyệt.
// `_luong` vẫn là biến module-scope (không còn `const`) để giữ ĐÚNG tính
// SINGLETON mà màn Tra cứu dựa vào: `_dung_luong()` chỉ thật sự dựng khi còn
// `null`, mọi lượt `ve()` sau TÁI DÙNG đúng một luồng đó — không mất lịch sử quét
// giữa các lượt vào/ra màn.
let _luong = null;

function _dung_luong() {
	if (!_luong) {
		// TASK 5 — TIÊM `ngay`/`gio` CHỈ TRONG APP, để phán quyết hết hạn
		// (`trang_thai_han`, lớp luồng) đọc giờ MÁY CHỦ đã đồng bộ (`vo.js`), không
		// bao giờ đọc đồng hồ máy Android (spec §8 — máy quét trong kho không đảm
		// bảo đúng giờ; một lần lệch múi/lệch ngày đã đổi nghĩa hạn dùng của một
		// lô vật tư y tế mà không ai biết cho tới khi thủ kho lấy nhầm).
		//
		// TRÊN WEB (`_la_app()` false) KHÔNG TRUYỀN GÌ CẢ — không phải truyền một
		// hàm trả `null`. `tao({ngay, gio})` chỉ dùng mặc định máy trạm
		// (`_ngay_may_tram`/`_gio_may_tram`) khi CHÍNH THAM SỐ đó falsy; một hàm
		// LUÔN TỒN TẠI (dù bên trong trả `null`) sẽ CHẶN CỨNG lối rơi về mặc định
		// đó — bản web sẽ ngưng đọc đồng hồ TRÌNH DUYỆT (hành vi ĐANG CHẠY, và
		// ràng buộc cứng của cả đợt là bản web `/kho` không đổi hành vi) và đổi
		// sang luôn ẩn chip hạn dùng, một hồi quy thật. Object rỗng (`{}`) khi
		// không phải app giữ `tao()` nhận đúng CHỮ KÝ CŨ — byte behavior không đổi.
		const trong_app = erpnext.kho_pda.KhoApp._la_app();
		_luong = _ns().tao({
			goi: (duong_dan, doi_so) => erpnext.kho_pda.KhoApp.goi(duong_dan, doi_so),
			...(trong_app
				? {
						// Hàm GETTER, không phải giá trị chụp nhanh: `_luong` là SINGLETON
						// sống suốt phiên (xem chú thích đầu file) — lúc dựng, đồng bộ giờ
						// máy chủ (`vo.js::_dong_bo_gio_may_chu()`, gọi từ `khoi_dong()`) rất
						// có thể CHƯA XONG. Gọi LẠI hàm này mỗi lần `trang_thai_han()` chạy
						// (không phải một lần lúc dựng luồng) là điều kiện để lượt quét ĐẦU
						// TIÊN sau khi đồng bộ xong lập tức thấy giá trị mới — không phải đợi
						// mở lại app. Trả `null` khi chưa đồng bộ là CỐ Ý: `_ngay_con_lai`
						// (lớp luồng) không khớp được `String(null)` với khuôn ngày, phán
						// quyết rơi về `{muc: "khong"}` — ẨN chip hạn dùng, KHÔNG đoán liều
						// bằng đồng hồ máy trong khung giây hiếm hoi đó.
						ngay: () => erpnext.kho_pda.KhoApp.ngay_may_chu(),
						gio: () => erpnext.kho_pda.KhoApp.gio_may_chu(),
				  }
				: {}),
		});
	}
	return _luong;
}

// Người đang đứng trước máy lúc `_luong` được dựng — dùng để phát hiện ĐỔI CA
// (soát xét vòng 1, P11/mục 6): `_luong` là singleton cấp module nên lịch sử SỐNG
// QUA cả một phiên hết hạn giữa ca. Máy quét đứng chung ở kho, đổi ca là chuyện
// hằng ngày — nếu người SAU quét thẻ vào (không tải lại trang, đúng thiết kế định
// tuyến hash của `vo.js`) mà không dọn, họ thấy nguyên lịch sử tra cứu của người
// TRƯỚC. Không hook vào `man_the.js` (file của Task 1, ngoài phạm vi sửa của Task
// 2) — thay vào đó tự phát hiện NGAY LÚC MỞ MÀN NÀY: đây là đường DUY NHẤT lịch sử
// cũ có thể lộ ra (không màn nào khác đọc `_luong`), nên chặn ở đây là đủ.
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

// Một dòng nhãn/giá trị — bỏ qua hẳn nếu rỗng, để thẻ không có một hàng trống
// đứng chơ vơ (khác Desk, nơi `o_luoi(..., rong=true)` cố tình vẽ ô rỗng cho một
// cột lưới cân đối; ở đây thẻ xếp DỌC một cột nên không cần giữ chỗ).
function _dong(nhan, gia_tri) {
	if (gia_tri === undefined || gia_tri === null || gia_tri === "") return "";
	return `<div class="kho-dong"><span class="kho-nhan">${_e(nhan)}</span><span class="kho-gt">${_e(
		gia_tri
	)}</span></div>`;
}

// Dòng "Hạn dùng" CÓ kèm dải cận date — ngưỡng/phân loại đọc từ lớp luồng
// (`trang_thai_han`, vòng sửa 1 mục 5): trước vòng này chỉ Desk tính, app quét
// CÙNG một lô lại im lặng không nói gì về hạn, dù đây là câu hỏi đầu tiên của thủ
// kho khi cầm một lô vật tư y tế lên.
function _dong_han(nhan, hsd) {
	const han = _dung_luong().trang_thai_han(hsd);
	const gt = hsd ? _e(_ngay(hsd)) : _e(__("Không có"));
	const chip = han.chu ? `<span class="kho-han-chip muc-${han.muc}">${_e(han.chu)}</span>` : "";
	return `<div class="kho-dong"><span class="kho-nhan">${_e(nhan)}</span><span class="kho-gt">${gt}${
		chip ? " " + chip : ""
	}</span></div>`;
}

function _tieu_de_muc(chu) {
	return `<div class="kho-tieu-de-muc">${_e(chu)}</div>`;
}

// Một dòng trong bảng lô/hàng — `chinh_html` do người gọi tự ghép + escape sẵn
// (chứa cả tên/mã lẫn dải cận date nếu có), hàm này chỉ lo phần số lượng + đơn vị.
function _dong_bang(chinh_html, so_luong, don_vi) {
	return `
		<div class="kho-dong-bang">
			<span class="kho-dong-chinh">${chinh_html}</span>
			<span class="kho-so">${_so(so_luong)}${don_vi ? " " + _e(don_vi) : ""}</span>
		</div>`;
}

function _chip_han_nho(hsd) {
	const han = _dung_luong().trang_thai_han(hsd);
	return han.chu ? ` <span class="kho-han-chip-nho muc-${han.muc}">${_e(han.chu)}</span>` : "";
}

// --------------------------------------------------------------------- thẻ

function _the_lo(d) {
	const ton = d.ton_theo_o || [];
	const tong = ton.reduce((t, x) => t + flt(x.so_luong), 0);
	return `
		<div class="kho-the">
			<div class="kho-the-dau">
				<span class="kho-nhan-loai loai-lo">${_ns().nhan_loai("lo")}</span>
				<div class="kho-the-ma">${_e(d.so_lo)}</div>
				<div class="kho-the-ten">${_e(d.ten_hang || d.vat_tu)}</div>
				<div class="kho-the-mo">${_e(d.vat_tu)}${d.don_vi ? " · " + _e(d.don_vi) : ""}</div>
			</div>
			${_dong_han(__("Hạn dùng"), d.hsd)}
			${_dong(__("Ngày SX"), _ngay(d.ngay_san_xuat))}
			${_dong(__("Ngày nhập"), _ngay(d.ngay_nhap))}
			${_dong(__("Số gói"), d.so_goi)}
			${_dong(__("Phiếu nhập"), d.so_phieu_nhap)}
			${_dong(__("Nhà cung cấp"), d.nha_cung_cap)}
			${_dong(__("Vị trí cố định"), d.vi_tri_co_dinh)}
			${_dong(__("Tem in"), d.o_in_tem)}
			${_tieu_de_muc(__("Tồn theo ô"))}
			${_bang_o(ton, d.don_vi)}
			${ton.length > 1 ? _dong(__("Tổng"), _so(tong) + (d.don_vi ? " " + d.don_vi : "")) : ""}
		</div>`;
}

function _the_vat_tu(d) {
	const lo = d.lo_con_ton || [];
	return `
		<div class="kho-the">
			<div class="kho-the-dau">
				<span class="kho-nhan-loai loai-vat_tu">${_ns().nhan_loai("vat_tu")}</span>
				<div class="kho-the-ten">${_e(d.ten_hang || d.vat_tu)}</div>
				<div class="kho-the-mo">${_e(d.vat_tu)}${d.don_vi ? " · " + _e(d.don_vi) : ""}</div>
			</div>
			${_dong(__("Vị trí cố định"), d.vi_tri_co_dinh || __("Chưa gán"))}
			${_dong(__("Kho cố định"), d.kho_co_dinh)}
			${_tieu_de_muc(d.co_lo ? __("Lô còn tồn · hạn gần trước") : __("Tồn theo ô"))}
			${
				lo.length
					? `<div class="kho-bang">${lo
							.map((x) =>
								_dong_bang(
									(d.co_lo ? _e(x.so_lo) + " · " : "") + _e(x.o) + _chip_han_nho(x.hsd),
									x.so_luong,
									d.don_vi
								)
							)
							.join("")}</div>`
					: `<div class="kho-trong">${__("Không còn tồn ở ô nào")}</div>`
			}
		</div>`;
}

function _the_o(d) {
	const hang = d.hang_trong_o || [];
	const mh = d.mat_hang_co_dinh;
	return `
		<div class="kho-the">
			<div class="kho-the-dau">
				<span class="kho-nhan-loai loai-o">${_ns().nhan_loai("o")}</span>
				<div class="kho-the-ma">${_e(d.ma_in_nhan || d.ma_o)}</div>
				<div class="kho-the-mo">${_e(d.kho)}${d.ten_o ? " · " + _e(d.ten_o) : ""}</div>
				${d.la_nhom ? `<span class="kho-co">${__("Nhóm ô")}</span>` : ""}
				${d.ngung_dung ? `<span class="kho-co kho-co-do">${__("Ngừng dùng")}</span>` : ""}
			</div>
			${_tieu_de_muc(__("Mặt hàng cố định"))}
			${
				mh
					? `<div class="kho-dong-bang"><span class="kho-dong-chinh">${_e(
							mh.ten_hang || mh.vat_tu
					  )}</span><span class="kho-mo-nho">${_e(mh.vat_tu)}</span></div>`
					: `<div class="kho-trong">${__("Chưa mặt hàng nào giữ vị trí này")}</div>`
			}
			${_tieu_de_muc(__("Đang chứa"))}
			${
				hang.length
					? `<div class="kho-bang">${hang
							.map((x) =>
								_dong_bang(
									_e(x.ten_hang || x.vat_tu) +
										(x.so_lo ? " · " + _e(x.so_lo) : "") +
										_chip_han_nho(x.hsd),
									x.so_luong,
									x.don_vi
								)
							)
							.join("")}</div>
						${
							d.so_dong_hang > hang.length
								? `<div class="kho-trong">${__("… và {0} dòng nữa", [
										d.so_dong_hang - hang.length,
								  ])}</div>`
								: ""
						}`
					: `<div class="kho-trong">${__("Ô trống")}</div>`
			}
		</div>`;
}

function _the_kho(d) {
	return `
		<div class="kho-the">
			<div class="kho-the-dau">
				<span class="kho-nhan-loai loai-kho">${_ns().nhan_loai("kho")}</span>
				<div class="kho-the-ten">${_e(d.ten_kho || d.kho)}</div>
				${d.ten_kho && d.ten_kho !== d.kho ? `<div class="kho-the-mo">${_e(d.kho)}</div>` : ""}
			</div>
			${_dong(__("Quản lý vị trí"), d.quan_ly_vi_tri ? __("Có") : __("Chưa bật"))}
			${d.quan_ly_vi_tri ? _dong(__("Số ô đang dùng"), d.so_o) : ""}
			${d.quan_ly_vi_tri ? _dong(__("Số ô có hàng"), d.so_o_co_hang) : ""}
		</div>`;
}

// `bao` là phán quyết CỦA LỚP LUỒNG (vòng sửa 1 mục 1/2) — hiện ĐÚNG chuỗi đó, một
// khi có (quét thật); lúc hiện lại từ lịch sử (không có `kq.bao` sống) mới rơi về
// câu MẶC ĐỊNH.
//
// VÒNG SỬA 2 (soát xét, M5): hai câu dưới đây gõ NGUYÊN VĂN bằng `__("...")`,
// KHÔNG đọc qua `_ns().CAU_KHONG_RO`/`MO_TA_KHONG_RO` như vòng trước —
// `__(<biến>)` chạy ĐÚNG lúc thi hành nhưng bộ rút chuỗi dịch của Frappe chỉ nhận
// diện `__(` đi ngay sau bởi một chuỗi chữ, không lần theo được giá trị biến; hai
// câu này sẽ biến mất khỏi catalog dịch. Hằng số trong lớp luồng vẫn là NGUỒN Ý
// NGHĨA — đổi câu thì sửa ở đó trước, hai chỗ `__("...")` dưới đây tự tay khớp lại.
function _the_khong_ro(bao) {
	return `
		<div class="kho-the kho-the-cho">
			<div class="kho-the-ten">${_e(bao || __("Không nhận ra mã này."))}</div>
			<div class="kho-the-mo">${__(
				"Không phải tem lô, tem vị trí, mã vật tư hay mã kho. Có thể vừa quét nhầm mã trên vỏ thùng."
			)}</div>
		</div>`;
}

function _the_cho() {
	return `
		<div class="kho-the kho-the-cho">
			<div class="kho-the-mo">${__("Bắn mã (tem lô, tem vị trí, mã vật tư, mã kho) để tra cứu.")}</div>
		</div>`;
}

function _bang_o(ds, don_vi) {
	if (!ds.length) return `<div class="kho-trong">${__("Lô này chưa xếp vào ô nào")}</div>`;
	return `<div class="kho-bang">${ds
		.map((x) => _dong_bang(_e(x.o), x.so_luong, don_vi))
		.join("")}</div>`;
}

function _ve_the(kq) {
	const ve = { lo: _the_lo, vat_tu: _the_vat_tu, o: _the_o, kho: _the_kho }[kq.loai];
	return ve ? ve(kq.du_lieu) : _the_khong_ro(kq.bao);
}

erpnext.kho_pda.KhoApp.dang_ky_man("tra-cuu", {
	tieu_de: __("Tra cứu"),

	// `tham_so` — phần sau dấu `/` trong hash (`vo.js::_theo_hash` cắt ra,
	// `vo.js::_ve_that` truyền vào). Màn này KHÔNG có tuyến sâu nào trong spec §5;
	// NHẬN ĐÚNG CHỮ KÝ rồi bỏ qua là CỐ Ý. Soát xét tổng (N3): `vo.js` đã truyền
	// tham số từ Task 1 mà KHÔNG màn nào khai tham số thứ hai, nên tuyến
	// `#/lay-hang/<phiếu>` im lặng không chạy suốt sáu Task. Khai đủ ở cả bốn màn
	// để chữ ký là MỘT — không ai phải nhớ màn nào nhận, màn nào không.
	ve($than, tham_so) {
		// PHẢI là câu lệnh ĐẦU TIÊN: đoạn đổi ca ngay dưới đọc `_luong.xoa_lich_su()`
		// — gọi sau đoạn đó, ở lượt `ve()` đầu tiên `_luong` vẫn còn `null`, ném
		// `TypeError` ngay khi mở màn lần đầu.
		_dung_luong();
		const _nguoi_dung_hien_tai = erpnext.kho_pda.KhoApp.nguoi_dung;
		// Đổi ca: người đang đứng trước máy KHÁC người lần cuối màn này được mở
		// (soát xét vòng 1, P11/mục 6) — lịch sử của người trước không phải của
		// người này, dọn sạch trước khi vẽ.
		//
		// CHỐT HỞ CA BIÊN (soát xét vòng 2, M1): `KhoApp.nguoi_dung` lấy qua
		// `frappe.auth.get_logged_user` trong `man_the.js`, có `.catch(() => "")` —
		// wifi kho chập chờn (điều kiện THƯỜNG TRỰC, không phải ca hiếm) khiến lời
		// gọi đó lỗi, `nguoi_dung` thành `""`. Hai ca LIÊN TIẾP cùng gặp lỗi mạng
		// thì cả hai đều `""` — so bằng `!==` đơn thuần sẽ thấy "không đổi" (`"" ===
		// ""`) và KHÔNG dọn, để lịch sử người trước lọt sang người sau. Coi `""` là
		// "KHÔNG XÁC ĐỊNH": bất kể giá trị lần trước là gì, luôn dọn khi giá trị
		// HIỆN TẠI là `""` — thà xoá oan lịch sử của chính chủ (họ quét lại là có
		// ngay, cái giá rẻ) còn hơn để một người khác đọc được dữ liệu người trước
		// (cái giá đắt, và là đúng thứ mục 6 sinh ra để chặn).
		if (!_nguoi_dung_hien_tai || _nguoi_dung_hien_tai !== _nguoi_dung_luc_vao) {
			_luong.xoa_lich_su();
			_nguoi_dung_luc_vao = _nguoi_dung_hien_tai;
		}

		$than.html(`
			<div class="man-tra-cuu">
				<div class="tc-o"></div>
				<div class="tc-ket-qua"></div>
				<div class="tc-lich-su"></div>
			</div>
		`);

		const $ket_qua = $than.find(".tc-ket-qua");
		const $lich_su = $than.find(".tc-lich-su");
		// Số thứ tự lượt quét — cùng lẽ `this.lan` của trang Desk (`quet_ma_tra_cuu.js`):
		// bắn hai mã liền nhau (tay run, quét trượt rồi quét lại ngay) thì câu trả
		// lời của mã TRƯỚC có thể bay VỀ SAU câu trả lời của mã sau; không có số này
		// thì màn hình dừng lại ở kết quả CŨ dù đã quét mã MỚI.
		let lan = 0;

		const ve_ket_qua = (kq) => $ket_qua.html(_ve_the(kq));

		const ve_lich_su = () => {
			const ds = _luong.lich_su();
			if (!ds.length) return $lich_su.empty();
			$lich_su.html(`
				${_tieu_de_muc(__("Vừa quét"))}
				${ds
					.map(
						(x, i) => `
					<div class="tc-dong-lich-su ${x.loai === "khong_ro" ? "khong-thay" : ""}" data-idx="${i}" role="button">
						<span class="kho-nhan-loai loai-${x.loai === "khong_ro" ? "khong" : _e(x.loai)}">${_ns().nhan_loai(
							x.loai
						)}</span>
						<span class="tc-lich-su-chu">
							<span class="tc-lich-su-ma">${_e(x.ma)}</span>
						</span>
						<span class="tc-lich-su-luc">${_e(x.luc ? x.luc.slice(0, 5) : "")}</span>
					</div>`
					)
					.join("")}
			`);
		};

		const quet = (ma) => {
			const lan_nay = ++lan;
			erpnext.kho_pda.KhoApp.bao();
			_luong
				.quet(ma)
				.then((kq) => {
					if (lan_nay !== lan) return; // một lượt quét khác đã tới sau — bỏ kết quả trễ này
					ve_ket_qua(kq);
					if (kq.bao) erpnext.kho_pda.KhoApp.bao(kq.bao, "cam");
					ve_lich_su();
				})
				.catch((loi) => {
					// KHÔNG bắt 401/403/mất mạng ở đây — `KhoApp.goi()` đã tự lo (đưa về
					// màn thẻ / ném câu tiếng Việt sẵn). Nhánh này chỉ còn lỗi nghiệp vụ
					// thật sự bất ngờ (ví dụ `PermissionError` — tài khoản mất vai trò
					// kho giữa ca) — vẫn phải hiện gì đó, không để màn im lặng treo.
					if (lan_nay !== lan) return;
					erpnext.kho_pda.KhoApp.bao((loi && loi.message) || __("Có lỗi, thử lại."), "do");
				})
				.finally(() => {
					if (lan_nay === lan) this._oq && this._oq.giu_focus();
				});
		};

		this._oq = new erpnext.kho_pda.OQuet({
			cha: $than.find(".tc-o"),
			vung: $than,
			goi_y: __("Quét tem lô, tem vị trí, mã vật tư…"),
			khi_quet: quet,
		});

		$lich_su.on("click", ".tc-dong-lich-su", (ev) => {
			const x = _luong.lich_su()[Number($(ev.currentTarget).attr("data-idx"))];
			if (x) ve_ket_qua({ loai: x.loai, du_lieu: x.du_lieu });
			this._oq && this._oq.giu_focus();
		});

		// Chưa quét gì trong lượt vào màn NÀY — không tự hiện lại kết quả của lần
		// quét trước (dù `_luong` còn nhớ): Bước 5 chỉ hứa "chạm vào một dòng lịch
		// sử thì hiện lại chi tiết", không hứa tự động hiện khi vào màn.
		$ket_qua.html(_the_cho());
		ve_lich_su();
	},

	roi() {
		// `roi()` là móc dọn dẹp DUY NHẤT mà `vo.js::_ve_that()` gọi khi rời màn —
		// không gọi `huy()` ở đây thì listener của `OQuet` này (trên `document`, trên
		// `$than`) sống mãi dù DOM đã bị xoá, rò dần qua mỗi lượt vào/ra màn này
		// (đúng lỗi Task 1 đã trả giá — xem `kho_pda/man_the.js`).
		this._oq && this._oq.huy();
		this._oq = null;
	},
});
