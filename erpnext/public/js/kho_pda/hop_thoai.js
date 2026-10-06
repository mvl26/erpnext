// Hộp hỏi CHỈ nhận thao tác CHẠM.
//
// KHÔNG nghe phím nào hết. Súng quét gửi Enter sau mỗi lần bắn, và một hộp xác
// nhận bắt Enter toàn trang đã DUYỆT NHẦM một phiếu thật ngày 17/09/2026
// (XVT-2026-00007 trên erptest, đã huỷ). Đây là lý do file này tồn tại thay vì
// dùng hộp thoại có sẵn.
//
// NỬA KIA của sự cố 17/09 không phải "hộp nghe Enter" mà là "ô quét phía sau hộp
// vẫn nghe Enter" — che một khung bằng CSS (`.kho-hop-nen`, `position: fixed`)
// không chặn được sự kiện bàn phím, vì trình duyệt gửi phím tới PHẦN TỬ ĐANG
// FOCUS, không phải phần tử đang HIỆN Ở TRÊN CÙNG về mặt hình ảnh. Súng quét gõ
// ký tự vào ô quét đang focus phía sau hộp mà không ai hay. Hộp phải chủ động bỏ
// focus khi mở và báo cho MỌI `OQuet` đang sống tự khoá lại.
//
// ĐẾM TẦNG, KHÔNG PHẢI CỜ BOOLEAN (soát xét vòng 2, N1): bản vá vòng 1 dùng một
// cặp sự kiện "mở"/"đóng" mà mỗi `OQuet` tự nhớ thành true/false — mở hộp A rồi
// mở hộp B (đè lên A) rồi đóng B thì sự kiện "đóng" của B mở khoá cho TẤT CẢ ô
// quét, dù hộp A vẫn còn nguyên trên màn (đo được: súng quét bắn xuyên qua hộp A
// sau khi B đóng). `so_hop_dang_mo` đếm số hộp CÙNG SỐNG; khoá chỉ được coi là gỡ
// khi số này thật sự về 0 — `OQuet` tự hỏi biến này (không nhớ trạng thái cũ),
// nên không có "cặp true/false" nào để lệch nhau nữa.
//
// VẪN GIỮ ĐẾM TẦNG dù `hoi()` nay TỪ CHỐI mở hộp thứ hai (xem chốt ở đầu `hoi()`):
// chốt kia làm hộp chồng nhau không còn xảy ra trên đường thường, nhưng đếm tầng là
// LƯỚI PHÒNG THỦ ở tầng dưới nó — nếu sau này có một luồng được phép mở hộp thứ hai
// một cách có chủ đích, hoặc chốt kia bị ai đó nới ra, thì tính chất "ô quét còn
// khoá chừng nào còn MỘT hộp sống" vẫn đúng mà không phải trả lại bài học đã tốn
// hai vòng sửa. Đổi nó về cờ boolean là đi ngược đúng thứ vòng 2 vừa sửa.
frappe.provide("erpnext.kho_pda");

erpnext.kho_pda.so_hop_dang_mo = 0;

// Hộp nào đang mở được ghi vào đây để `dong_het_hop()` (vo.js gọi khi chuyển
// màn) đóng được HẾT, không chỉ hộp mới nhất — xem `erpnext.kho_pda.dong_het_hop`.
const _hop_dang_mo = new Set();

// Đóng MỌI hộp còn mở — không kích hoạt `khi_dong_y`/`khi_dong` (đây không phải
// người dùng bấm nút nào cả, mà là màn sinh ra hộp đã bị rời bỏ). `vo.js::_ve()`
// gọi hàm này TRƯỚC khi dọn màn cũ (soát xét vòng 2, N3): một hộp `hoi()` thuộc
// về màn đã mở nó — sống sót sang màn khác vừa sai nghĩa (nút của nó gọi callback
// của màn đã rời) vừa để lại một `OQuet` mới (của màn mới) không hề biết nó vẫn
// đang bị một hộp mồ côi che khuất (nối với N2 trong `o_quet.js`).
erpnext.kho_pda.dong_het_hop = function () {
	// Sao mảng ra trước khi lặp: `dong()` tự xoá chính nó khỏi `_hop_dang_mo`
	// NGAY BÊN TRONG vòng lặp — sửa một `Set` đang được duyệt dở là hành vi không
	// chắc chắn.
	Array.from(_hop_dang_mo).forEach((dong) => dong());
};

// Hộp rỗng trả về cho lời gọi BỊ TỪ CHỐI — người gọi có thể giữ giá trị trả về và
// gọi `.dong()`; trả `null` sẽ biến một cú bấm thừa thành `TypeError`.
const _HOP_RONG = { dong: () => {} };

erpnext.kho_pda.hoi = function ({ noi_dung, nhan, khi_dong_y, khi_dong }) {
	// CHỐT CHỐNG BẤM LẠI (soát xét tổng lần 2, CŨ-1): đang có hộp mở thì KHÔNG mở
	// thêm hộp nào nữa. Đo được trước bản vá: chạm "Hoàn tất phiếu" ba lần liên
	// tiếp trên màn Lấy hàng bật ra BA hộp chồng nhau, đồng ý cả ba thì `hoan_tat`
	// — lệnh DUYỆT phiếu giao và trừ sổ vị trí thật — chạy ĐÚNG BA LẦN. Đúng hình
	// dạng sự cố 17/09/2026, chỉ khác nguồn gõ: lần đó là Enter của súng quét, lần
	// này là ngón tay đeo găng chạm lại vì màn chưa kịp phản hồi. Thứ duy nhất ngăn
	// hậu quả hôm nay là máy chủ từ chối lượt thứ hai — tức đang an toàn nhờ MAY,
	// không nhờ thiết kế, và câu đỏ nó trả về ("người khác vừa đặt") còn nói SAI SỰ
	// THẬT: "người khác" chính là cú bấm thứ hai của chính thủ kho.
	//
	// CHẶN Ở ĐÂY, MỘT CHỖ, chứ không vá từng nút ở bốn màn: bốn màn đều đi qua hàm
	// này cho MỌI lời GHI (khuôn chung của app, không có ngoại lệ theo màn), nên
	// một chốt ở đây phủ cả những nút chưa ai viết. Vá từng nút là đúng kiểu trùng
	// lặp mà cả đợt gộp lớp này sinh ra để gỡ.
	//
	// ĐÃ RÀ: không luồng hợp lệ nào của bốn màn cần hai hộp chồng nhau — cả năm lời
	// gọi `hoi()` (xep_hang ×2, lay_hang ×2, dat_o ×1) đều nằm trong một trình nghe
	// `click` ở cấp ngoài cùng, không lời gọi nào nằm trong `khi_dong_y` của lời gọi
	// khác. Nếu sau này có một luồng thật sự cần hộp thứ hai, phải sửa Ở ĐÂY cho có
	// chủ đích, không phải lách bằng cách gọi thẳng DOM.
	//
	// KHÔNG gọi `khi_dong`/`khi_dong_y` khi từ chối: không có gì xảy ra cả, và ô
	// quét vẫn đang bị hộp THỨ NHẤT khoá — đúng chỗ nó phải ở.
	if (erpnext.kho_pda.so_hop_dang_mo > 0) return _HOP_RONG;

	if (document.activeElement && document.activeElement.blur) document.activeElement.blur();

	// Dựng DOM TRƯỚC, tăng đếm SAU khi chắc chắn dựng xong: nếu template ném lỗi
	// giữa chừng (`noi_dung`/`nhan` là thứ gì đó khiến chuỗi mẫu vỡ) mà tăng đếm
	// trước, `so_hop_dang_mo` kẹt ở số dương mãi mãi — KHOÁ HẲN mọi ô quét trên
	// trang cho tới khi tải lại, một hỏng còn nặng hơn cả lỗ hổng đang vá.
	const $nen = $(`
		<div class="kho-hop-nen">
			<div class="kho-hop">
				<div class="kho-hop-noi-dung">${frappe.utils.escape_html(noi_dung)}</div>
				<button type="button" class="kho-hop-dong-y">${frappe.utils.escape_html(nhan)}</button>
				<button type="button" class="kho-hop-thoi">${__("Không")}</button>
			</div>
		</div>
	`).appendTo(document.body);

	erpnext.kho_pda.so_hop_dang_mo++;
	document.dispatchEvent(new CustomEvent("kho-hop-doi"));

	let da_dong = false;
	const dong = () => {
		// `dong_het_hop()` và một cú bấm nút thật có thể gọi trùng nhau (chuyển màn
		// đúng lúc người dùng vừa chạm) — không chặn thì đếm bị trừ hai lần cho một
		// hộp, số `so_hop_dang_mo` âm mãi mãi và không hộp nào khoá lại được nữa.
		if (da_dong) return;
		da_dong = true;
		_hop_dang_mo.delete(dong);
		$nen.remove();
		erpnext.kho_pda.so_hop_dang_mo--;
		document.dispatchEvent(new CustomEvent("kho-hop-doi"));
	};
	_hop_dang_mo.add(dong);

	$nen.find(".kho-hop-dong-y").on("click", () => {
		dong();
		khi_dong_y && khi_dong_y();
	});
	$nen.find(".kho-hop-thoi").on("click", () => {
		dong();
		khi_dong && khi_dong();
	});
	return { dong };
};

// TASK 6 — HỘP CÓ Ô NHẬP, dùng đúng một chỗ: lối ẩn khai địa chỉ máy chủ
// (`man_the.js`). Tách riêng khỏi `hoi()` vì `hoi()` là hộp XÁC NHẬN (hai nút,
// không ô nhập) và cả bốn màn nghiệp vụ dựa vào hình dạng đó.
//
// CHUNG MỘT BỘ ĐẾM `so_hop_dang_mo` VÀ CHUNG SỰ KIỆN `kho-hop-doi` với `hoi()` —
// không phải để tiết kiệm dòng mà vì đó LÀ cơ chế khoá ô quét: hộp này mở ra ngay
// trên màn thẻ, nơi có một `OQuet` đang nghe bàn phím. Không đếm chung thì súng
// quét vẫn bắn xuyên qua hộp vào ô quét phía sau — đúng nửa sau của sự cố
// 17/09/2026 mô tả ở đầu file.
//
// Ô NHẬP NÀY KHÔNG NGHE BÀN PHÍM — KỂ CẢ ĐỂ CHẶN, và đó là luật của cả file
// (nửa trước của sự cố 17/09): súng quét gửi Enter sau mỗi lần bắn. Một cú bắn
// lạc vào ô địa chỉ mà Enter tự lưu là chiếc máy đổi sang một địa chỉ rác giữa
// ca. Cách chặn ở đây là CẤU TRÚC, không phải một trình nghe: ô nhập KHÔNG nằm
// trong một `<form>` nào, nên Enter không có gì để gửi đi — không nút nào được
// bấm, không hàm nào chạy. Thêm một `keydown` để `preventDefault` sẽ vừa vô ích
// vừa phá đúng bất biến mà `test_hop_thoai_khong_bat_phim_nao` canh (một trình
// nghe bàn phím trong file này, hôm nay vô hại, mai có người thêm một dòng vào).
// Lưu CHỈ xảy ra khi có ngón tay chạm nút.
erpnext.kho_pda.hoi_chuoi = function ({ noi_dung, gia_tri, goi_y, nhan, nhan_phu, khi_luu, khi_phu, khi_dong }) {
	if (erpnext.kho_pda.so_hop_dang_mo > 0) return _HOP_RONG;

	if (document.activeElement && document.activeElement.blur) document.activeElement.blur();

	const e = frappe.utils.escape_html;
	const $nen = $(`
		<div class="kho-hop-nen">
			<div class="kho-hop kho-hop-chuoi">
				<div class="kho-hop-noi-dung">${e(noi_dung)}</div>
				<input type="url" class="kho-hop-nhap" inputmode="url" autocomplete="off"
					autocapitalize="off" autocorrect="off" spellcheck="false"
					placeholder="${e(goi_y || "")}" value="${e(gia_tri || "")}" />
				<div class="kho-hop-loi"></div>
				<button type="button" class="kho-hop-dong-y">${e(nhan)}</button>
				${nhan_phu ? `<button type="button" class="kho-hop-phu">${e(nhan_phu)}</button>` : ""}
				<button type="button" class="kho-hop-thoi">${__("Đóng")}</button>
			</div>
		</div>
	`).appendTo(document.body);

	erpnext.kho_pda.so_hop_dang_mo++;
	document.dispatchEvent(new CustomEvent("kho-hop-doi"));

	let da_dong = false;
	const dong = () => {
		if (da_dong) return;
		da_dong = true;
		_hop_dang_mo.delete(dong);
		$nen.remove();
		erpnext.kho_pda.so_hop_dang_mo--;
		document.dispatchEvent(new CustomEvent("kho-hop-doi"));
	};
	_hop_dang_mo.add(dong);

	const $nhap = $nen.find(".kho-hop-nhap");
	const $loi = $nen.find(".kho-hop-loi");

	// `khi_luu` trả CÂU LỖI (chuỗi rỗng = xong). Hộp tự đóng khi xong, tự hiện lỗi
	// và ĐỨNG YÊN khi chưa xong — người gõ sai không mất cái vừa gõ.
	$nen.find(".kho-hop-dong-y").on("click", () => {
		const loi = khi_luu ? khi_luu(String($nhap.val() || "")) : "";
		if (loi) {
			$loi.text(loi);
			return;
		}
		dong();
	});
	if (nhan_phu) {
		$nen.find(".kho-hop-phu").on("click", () => {
			dong();
			khi_phu && khi_phu();
		});
	}
	$nen.find(".kho-hop-thoi").on("click", () => {
		dong();
		khi_dong && khi_dong();
	});
	return { dong };
};
