// Màn hình phiếu nhập lô: nạp dòng hàng từ phiếu nhập, rồi in cả xấp nhãn.
//
// Theo khuôn `location_transfer.js` của cùng module — cùng cách gắn nút, cùng
// cách xoá bảng con khi đổi chứng từ gốc, cùng cách TÓM TẮT theo `ly_do_goi_y`
// THẬT thay vì một câu chung chung.
//
// HAI NÚT, HAI TRẠNG THÁI, SO SÁNH BẰNG ===  — đây là món nợ số 1 của Task 8,
// và nó không phải chuyện thẩm mỹ:
//
//   `nhap_lo.dat_o_in_tem` suy kho qua `_kho_cua_lo()`, tức là qua `batch_no`
//   đã ghi lên dòng `Purchase Receipt Item`. `BatchEntry.on_submit` mới ghi
//   trường đó. Gọi trước khi phiếu duyệt → `_kho_cua_lo` trả `None` → `None`
//   → F8 in ra "VT —", KHÔNG có lỗi nào, KHÔNG có cảnh báo nào, và tem đã in
//   thì có thể đã dán lên thùng hàng. Nên nút In không được TỒN TẠI khi
//   `docstatus !== 1`.
//
//   Và phải là `=== 1`, không phải `!== 0`: phiếu ĐÃ HUỶ là `docstatus === 2`.
//   Với `!== 0` thì nút In sống lại trên một phiếu đã huỷ — `on_cancel` vừa gỡ
//   `batch_no` khỏi dòng phiếu nhập, nên `_kho_cua_lo` lại trả `None`, và ta
//   quay đúng về cái hố im lặng vừa lấp. Cùng lý lẽ cho chiều kia: nút "Lấy
//   dòng" là `=== 0`, vì bảng con của phiếu đã duyệt/đã huỷ không sửa được.

const DUONG_IN_NHAN = "/assets/erpnext/js/vi_tri_kho/in_nhan_lo.js";

// Task 10 — quét mã tra cứu: CHIỀU NGƯỢC của việc in nhãn ở trên. Không dùng
// `process_scan()`/`update_table()` của `erpnext.utils.BarcodeScanner`: lớp
// đó hard-code tên trường `item_code`/`batch_no`/`qty` của một bảng con kiểu
// chuẩn ERPNext (`stock_entry.js`, `pick_list.js`...), còn bảng con của phiếu
// này dùng tên trường RIÊNG (`vat_tu`, `so_lo`...) và mục đích ở đây là ĐỌC
// thông tin để XEM, không phải thêm dòng vào bảng — gọi `update_table()` sẽ
// vừa sai tên trường vừa sai cả việc cần làm. Cũng không gắn field
// `scan_barcode` vào lược đồ doctype (cách `BarcodeScanner` đòi hỏi qua
// `frm.fields_dict[scan_field_name]`): mã cần quét là mã trên nhãn ĐÃ IN, tức
// là quét SAU KHI phiếu đã duyệt (`docstatus === 1`) — một trường thường trên
// chứng từ đã duyệt phải `allow_on_submit` mới gõ được, nghĩa là mỗi lần quét
// đều ghi xuống một chứng từ kho ĐÃ DUYỆT, chỉ để chứa một ô nhập tạm thời.
// Cái giá đó không đáng cho một ô không lưu gì cả.
//
// Vì vậy: một khung `frm.dashboard.add_section()` độc lập, KHÔNG gắn với
// field nào của doc — input quét + khung kết quả nằm chung trong đó, gọi
// thẳng `erpnext.vi_tri_kho.vitri.quet.tra_cuu` bằng `frappe.call` (chữ ký
// `tra_cuu(ma)` khác `scan_barcode(search_value)` mà `BarcodeScanner.
// scan_api_call()` hard-code gửi, nên gọi trực tiếp còn rõ ràng hơn là ghi đè
// một phương thức của lớp đó). Máy quét mã vạch cắm ngoài gõ như bàn phím —
// input thường + bắt phím Enter là đủ, không cần control kiểu "Barcode".
const KHOA_KHUNG_QUET = "vi_tri_kho_khung_quet";

frappe.ui.form.on("Batch Entry", {
	refresh(frm) {
		_dung_khung_quet(frm);

		if (frm.doc.docstatus === 0) {
			// Nút hiện NGAY CẢ KHI `phieu_nhap` còn trống, và điều kiện được
			// kiểm TRONG `lay_dong()` chứ không ở đây. Bản đầu gắn thêm
			// `if (frm.doc.phieu_nhap)` quanh chỗ này và nó HỎNG trên máy thật:
			// `refresh` chỉ chạy lúc mở/lưu/nạp lại form, KHÔNG chạy lại khi
			// người dùng chọn xong phiếu nhập. Nên trên một phiếu mới, thủ kho
			// chọn phiếu nhập rồi ngồi nhìn một màn hình KHÔNG CÓ NÚT NÀO, cho
			// tới khi tình cờ bấm Lưu. Đã thấy tận mắt trên trình duyệt trước
			// khi sửa (16/09/2026) — đây không phải lo xa.
			frm.add_custom_button(__("Lấy dòng hàng từ phiếu nhập"), () => lay_dong(frm));

			// Mở từ nút "Nhập lô & in nhãn" trên phiếu nhập (`purchase_receipt.js`):
			// phiếu mới đã mang sẵn `phieu_nhap`. Xem `tu_nap_neu_can`.
			tu_nap_neu_can(frm);
			return;
		}

		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("In nhãn cả phiếu"), () => in_nhan_ca_phieu(frm));
		}
	},

	phieu_nhap(frm) {
		// Dòng của phiếu cũ không thuộc phiếu mới — `kiem_tra_dong_thuoc_phieu`
		// phía máy chủ sẽ chặn lúc lưu (`batch_entry.py`). Xoá luôn ở đây để
		// thủ kho khỏi phải sửa từng dòng rồi mới biết, đúng khuôn `kho(frm)`
		// ở `location_transfer.js`.
		//
		// Khác `location_transfer.js` một chỗ: HỎI trước khi xoá. Ở phiếu xếp,
		// dòng bị xoá là dòng máy chủ vừa đổ xuống, lấy lại một cú bấm. Ở đây
		// dòng mang SỐ LÔ và HẠN DÙNG do thủ kho GÕ TAY từ vỏ thùng — gõ lại
		// hai chục dòng vì một cú chọn nhầm phiếu là mất việc thật, và mất
		// trong im lặng.
		//
		// Đếm DÒNG THẬT, không đếm `items.length` — xem `dong_that`. Bản cũ đếm
		// `items.length` nên trên một phiếu MỚI, chọn phiếu nhập là bật hộp "sẽ xoá 1
		// dòng đang có (kèm số lô và hạn dùng đã gõ)" trong khi dòng đó là dòng trống
		// Frappe tự thêm — cảnh báo mất dữ liệu khi chẳng có dữ liệu nào.
		if (!dong_that(frm).length) {
			tu_nap_neu_can(frm);
			return;
		}

		frappe.confirm(
			__(
				"Đổi phiếu nhập sẽ xoá {0} dòng đang có (kèm số lô và hạn dùng đã gõ). Tiếp tục?",
				[dong_that(frm).length]
			),
			() => {
				frm.clear_table("items");
				frm.refresh_field("items");
				frappe.show_alert({
					message: __("Đã xoá các dòng vì đổi phiếu nhập."),
					indicator: "orange",
				});
				tu_nap_neu_can(frm);
			},
			() => {
				// Trả `phieu_nhap` về giá trị cũ thì phải nhớ giá trị cũ — mà
				// `frappe.ui.form.on` không đưa nó cho ta. Nên không tự ý khôi
				// phục; chỉ nói rõ hệ đang ở trạng thái nào để thủ kho quyết
				// định. Im lặng ở đây là tệ nhất: bảng con vẫn là của phiếu
				// cũ trong khi ô phiếu nhập đã là phiếu mới.
				frappe.show_alert({
					message: __(
						"Đã giữ nguyên các dòng cũ — chúng vẫn thuộc phiếu nhập TRƯỚC. Lưu sẽ báo lỗi."
					),
					indicator: "red",
				});
			}
		);
	},
});

function lay_dong(frm) {
	if (!frm.doc.phieu_nhap) {
		frappe.msgprint({
			title: __("Chưa chọn phiếu nhập"),
			message: __("Chọn phiếu nhập ở trên trước — dòng hàng được lấy từ chính phiếu đó."),
			indicator: "orange",
		});
		return;
	}

	frappe.call({
		method: "erpnext.vi_tri_kho.vitri.nhap_lo.lay_dong_tu_phieu_nhap",
		args: { phieu_nhap: frm.doc.phieu_nhap },
		callback(r) {
			const dong = r.message || [];
			if (!dong.length) {
				// Câu báo cũ ở đây chỉ nói "không còn dòng hàng quản lý lô nào chưa
				// có số lô" — đúng về kỹ thuật, nhưng chủ đầu tư gặp nó ngày
				// 17/09/2026 trên một phiếu nhập ĐÃ DUYỆT mà số lô là ngày tháng gõ
				// tay, và câu đó không nói gì về cả hai điều ấy. Ba nguyên nhân cần
				// ba việc khác nhau, nên hỏi máy chủ vì sao thay vì đoán ở đây.
				// Câu chữ sống ở `phieu_nhap._cau_bao` — một chỗ, dùng chung với nút
				// trên phiếu nhập.
				frappe
					.call({
						method: "erpnext.vi_tri_kho.vitri.phieu_nhap.chan_doan_phieu_nhap",
						args: { phieu_nhap: frm.doc.phieu_nhap },
					})
					.then((r2) => {
						const cd = r2.message || {};
						frappe.msgprint({
							title: __("Không có dòng nào cần khai lô"),
							message: cd.cau_bao,
							// Cam khi có việc phải sửa (đã duyệt, hay lô gõ tay);
							// xanh dương khi chỉ là thông tin.
							indicator: cd.docstatus || (cd.dong_go_tay || []).length ? "orange" : "blue",
						});
					});
				return;
			}

			frm.clear_table("items");
			dong.forEach((d) => {
				const c = frm.add_child("items");
				c.dong_phieu_nhap = d.dong_phieu_nhap;
				c.vat_tu = d.vat_tu;
				c.ten_hang = d.ten_hang;
				c.kho = d.kho;
				c.so_luong = d.so_luong;
				// `o_goi_y`/`ly_do_goi_y` là GỢI Ý, không phải quyết định —
				// chúng chỉ để thủ kho biết hàng này sẽ về đâu khi tem in ra.
				// Bỏ hai dòng này thì Task 7 đã trả đúng dữ liệu mà màn hình
				// không hiện gì, và cả gợi ý vị trí vô hình trên phiếu nhập lô.
				c.o_goi_y = d.o_goi_y;
				c.ly_do_goi_y = d.ly_do_goi_y;
			});
			frm.refresh_field("items");
			frappe.show_alert({
				message: __("Đã lấy {0} dòng. Gõ số lô và hạn dùng cho từng dòng.", [
					dong.length,
				]),
				indicator: "blue",
			});

			// Tóm tắt các dòng KHÔNG có ô gợi ý, gộp theo `ly_do_goi_y` THẬT.
			//
			// Ruling O (khối B, chép cả lý do theo đúng yêu cầu brief Task 9):
			// `ly_do_goi_y` của `goi_y_o()` có ÍT NHẤT BA nguyên nhân khác hẳn
			// nhau — "chưa gán", "vùng đã đầy", và (Ruling N) "lỗi dữ liệu vị
			// trí". Mỗi nguyên nhân cần một HÀNH ĐỘNG khác nhau của thủ kho (đi
			// gán / đi dọn hoặc mở rộng vùng / báo lỗi dữ liệu). Một câu cố định
			// "chưa gán vị trí cố định" cho MỌI dòng rỗng từng khiến ca "đã gán
			// nhưng hết chỗ" bị đọc nhầm thành "chưa gán" — đúng lớp lỗi "màn
			// hình nói sai sự thật" đã dính hai lần trước đó trong dự án.
			//
			// KHÔNG có nhóm "tem cũ không dùng được" ở màn hình này, và đó là
			// chủ ý chứ không phải thiếu sót: `lay_dong_tu_phieu_nhap` gọi
			// `goi_y_o(vat_tu, kho)` KHÔNG kèm `so_lo` (lúc nạp dòng thì lô
			// chưa tồn tại — thủ kho chưa gõ), mà `tem_hong` chỉ có thể bật khi
			// CÓ `so_lo` (`goi_y.py`: `if so_lo:`). Thêm nhóm đó ở đây là dựng
			// một cảnh báo không bao giờ bật — tệ hơn là không có, vì nó khiến
			// người đọc mã tin rằng ca đó đã được phủ.
			const chua_co_goi_y = dong.filter((d) => !d.o_goi_y);
			if (!chua_co_goi_y.length) return;

			const theo_ly_do = {};
			chua_co_goi_y.forEach((d) => {
				const ly_do = d.ly_do_goi_y || __("không rõ lý do");
				theo_ly_do[ly_do] = (theo_ly_do[ly_do] || 0) + 1;
			});
			const tom_tat = Object.keys(theo_ly_do)
				.map((ly_do) => __("{0} dòng ({1})", [theo_ly_do[ly_do], ly_do]))
				.join(", ");

			frappe.show_alert(
				{
					message: __("{0} dòng chưa có ô gợi ý: {1}.", [
						chua_co_goi_y.length,
						tom_tat,
					]),
					indicator: "orange",
				},
				10
			);
		},
	});
}

function in_nhan_ca_phieu(frm) {
	// `lo_da_tao` do `on_submit` ghi bằng `db_set` — phiếu đã duyệt thì mọi
	// dòng đều có. Vẫn lọc `Boolean` phòng ca phiếu duyệt từ trước khi có
	// trường này.
	const lo = (frm.doc.items || []).map((d) => d.lo_da_tao).filter(Boolean);
	if (!lo.length) {
		frappe.msgprint({
			title: __("Chưa có lô nào để in"),
			message: __(
				"Không dòng nào trên phiếu này có lô đã tạo. Duyệt phiếu sẽ tạo lô cho từng dòng."
			),
			indicator: "orange",
		});
		return;
	}

	frappe.require(DUONG_IN_NHAN, () => {
		erpnext.vi_tri_kho.in_nhan.in_cho_cac_lo(lo);
	});
}

function _dung_khung_quet(frm) {
	// `refresh` chạy lại nhiều lần (mở form, lưu, nạp lại) — CHỈ dựng khung khi
	// nó CHƯA CÓ TRONG DOM, không phải chỉ dựa vào biến `frm[KHOA_KHUNG_QUET]`
	// còn giữ tham chiếu hay không.
	//
	// Bẫy ĐÃ ĐO trên mã nguồn `frappe/public/js/frappe/form/dashboard.js`
	// (KHÔNG phải suy diễn): mỗi lần `frm.refresh()` chạy (sau khi lưu, sau
	// khi nạp lại), `Form.refresh_header()` gọi `dashboard.refresh()`, và
	// `Dashboard.refresh()` MỞ ĐẦU bằng `this.reset()` — hàm này xoá THẲNG
	// mọi phần tử con khớp `.custom` (`this.parent.find(".custom").remove()`).
	// `add_section()` mặc định gắn ĐÚNG class `"custom"` đó. Nếu guard ở đây
	// chỉ kiểm biến `frm[KHOA_KHUNG_QUET]` (một tham chiếu jQuery) thì sau cú
	// `reset()` đầu tiên, biến đó vẫn "có giá trị" nhưng đang trỏ vào một nút
	// DOM ĐÃ BỊ GỠ — khung quét biến mất vĩnh viễn sau lần lưu/nạp lại ĐẦU
	// TIÊN mà không có cách nào tự hồi phục, đúng họ lỗi "refresh chạy lại mà
	// mã cũ tưởng nó chỉ chạy một lần" đã ghi ở đầu file này (món nợ số 1,
	// Task 8). Hai lớp phòng vệ, không lớp nào thừa:
	//
	//   1. Đặt `css_class` RIÊNG (không phải mặc định `"custom"`) khi gọi
	//      `add_section` bên dưới — `reset()` không còn khớp được khung này,
	//      nên nó KHÔNG BỊ XOÁ ở lần `refresh()` kế tiếp, không cần dựng lại.
	//   2. Vẫn kiểm DOM THẬT (`document.body.contains(...)`), không chỉ biến
	//      JS — phòng một đường gỡ DOM khác trong tương lai mà lớp 1 không
	//      lường trước (ví dụ đổi tab, đổi layout).
	if (frm[KHOA_KHUNG_QUET] && document.body.contains(frm[KHOA_KHUNG_QUET][0])) return;

	const than = frm.dashboard.add_section(
		`<div class="vi-tri-kho-khung-quet">
			<input type="text" class="form-control input-sm vi-tri-kho-quet-o-nhap"
				placeholder="${__("Quét mã vạch trên nhãn (lô / vật tư / kho)...")}" />
			<div class="vi-tri-kho-quet-ket-qua text-muted small" style="margin-top: 10px;"></div>
		</div>`,
		__("Quét mã tra cứu"),
		"vi-tri-kho-khung-quet-section"
	);
	frm[KHOA_KHUNG_QUET] = than;

	// Máy quét mã vạch cắm ngoài mô phỏng bàn phím: gõ nhanh rồi tự gửi phím
	// Enter — không cần nút bấm, chỉ cần bắt đúng phím này.
	than.find(".vi-tri-kho-quet-o-nhap").on("keydown", (ev) => {
		if (ev.key !== "Enter") return;
		ev.preventDefault();
		const $o_nhap = $(ev.currentTarget);
		const ma = ($o_nhap.val() || "").trim();
		$o_nhap.val("");
		if (!ma) return;
		_quet_va_hien_thi(frm, ma);
	});
}

function _quet_va_hien_thi(frm, ma) {
	const $ket_qua = frm[KHOA_KHUNG_QUET].find(".vi-tri-kho-quet-ket-qua");
	$ket_qua.html(frappe.utils.escape_html(__("Đang tra cứu...")));

	frappe.call({
		method: "erpnext.vi_tri_kho.vitri.quet.tra_cuu",
		args: { ma: ma },
		callback(r) {
			// `tra_cuu` không bao giờ ném lỗi (bọc `try/except` ở máy chủ,
			// điều #2 brief Task 10) — nhánh "không tìm thấy" là `loai: null`
			// chứ KHÔNG PHẢI một exception `frappe.call` phải bắt riêng.
			const du_lieu = r && r.message;
			if (!du_lieu || !du_lieu.loai) {
				$ket_qua.html(
					`<span class="text-danger">${frappe.utils.escape_html(
						__("Không tìm thấy thông tin cho mã {0}.", [ma])
					)}</span>`
				);
				return;
			}
			$ket_qua.html(_ve_khung_ket_qua(du_lieu));
		},
	});
}

function _dong_thong_tin(nhan, gia_tri) {
	// Bỏ qua dòng có giá trị RỖNG (`undefined`/`null`/chuỗi rỗng/0 dòng) thay
	// vì in một dòng trống — khung kết quả chỉ nên nói những gì THẬT SỰ biết,
	// đúng tinh thần "không suy diễn" xuyên suốt cả kế hoạch (`goi_y_o` trả
	// `None` thay vì đoán, `nhap_lo` để trống F4 thay vì placeholder).
	if (gia_tri === undefined || gia_tri === null || gia_tri === "") return "";
	return `<div><b>${frappe.utils.escape_html(nhan)}:</b> ${frappe.utils.escape_html(
		String(gia_tri)
	)}</div>`;
}

function _ve_khung_ket_qua(d) {
	// Rẽ nhánh THEO KHOÁ `loai` — KHÔNG dò chữ trong bất kỳ chuỗi nào để suy
	// loại (bài học đã trả giá ở `goi_y.py`/`location_transfer.js`: chuỗi
	// hiển thị đi qua `__()` nên dịch được, so khớp chuỗi con sẽ âm thầm gộp
	// nhầm hoặc khớp 0 dòng khi đổi ngôn ngữ).
	if (d.loai === "lo") {
		const o_dang_co_hang = (d.o_dang_co_hang || []).join(", ");
		const ton_theo_o = (d.ton_theo_o || [])
			.map(
				(dong) =>
					`<li>${frappe.utils.escape_html(dong.o)}: ${frappe.utils.escape_html(
						String(dong.so_luong)
					)}</li>`
			)
			.join("");

		return [
			`<div><b>${__("Loại")}:</b> ${__("Lô")}</div>`,
			_dong_thong_tin(__("Số lô"), d.so_lo),
			_dong_thong_tin(__("Mã vật tư"), d.vat_tu),
			_dong_thong_tin(__("Tên hàng"), d.ten_hang),
			_dong_thong_tin(__("Hạn dùng"), d.hsd),
			_dong_thong_tin(__("Ngày sản xuất"), d.ngay_san_xuat),
			_dong_thong_tin(__("Nhà cung cấp"), d.nha_cung_cap),
			_dong_thong_tin(__("Số gói"), d.so_goi),
			_dong_thong_tin(__("Ngày nhập"), d.ngay_nhap),
			_dong_thong_tin(__("Phiếu nhập"), d.so_phieu_nhap),
			_dong_thong_tin(__("Vị trí cố định"), d.vi_tri_co_dinh),
			_dong_thong_tin(__("Ô đang có hàng"), o_dang_co_hang),
			_dong_thong_tin(__("Ô đã in tem"), d.o_in_tem),
			ton_theo_o
				? `<div><b>${__("Tồn theo ô")}:</b><ul style="margin-bottom:0">${ton_theo_o}</ul></div>`
				: "",
		]
			.filter(Boolean)
			.join("");
	}

	if (d.loai === "vat_tu") {
		return [
			`<div><b>${__("Loại")}:</b> ${__("Mặt hàng")}</div>`,
			_dong_thong_tin(__("Mã vật tư"), d.vat_tu),
			_dong_thong_tin(__("Tên hàng"), d.ten_hang),
		]
			.filter(Boolean)
			.join("");
	}

	if (d.loai === "kho") {
		return [`<div><b>${__("Loại")}:</b> ${__("Kho")}</div>`, _dong_thong_tin(__("Kho"), d.kho)]
			.filter(Boolean)
			.join("");
	}

	return "";
}

// Dòng có DỮ LIỆU THẬT trong bảng con.
//
// `items` là bảng bắt buộc (`reqd`), nên Frappe tự thêm MỘT dòng trống vào mọi
// phiếu mới. Mọi phép "bảng con có dòng chưa" phải đi qua hàm này chứ không đếm
// `items.length`: đếm thẳng thì phiếu mới luôn "đã có 1 dòng". Đã hỏng thật hai
// chỗ trước khi có hàm này (kiểm trên trình duyệt 17/09/2026) — tự nạp dòng không
// bao giờ chạy, và chọn phiếu nhập bật cảnh báo mất dữ liệu cho một dòng trống.
// Có `so_lo` cũng tính là dòng thật: người dùng có thể gõ lô vào chính dòng trống.
function dong_that(frm) {
	return (frm.doc.items || []).filter((d) => d.dong_phieu_nhap || d.vat_tu || d.so_lo);
}

// Tự nạp dòng hàng khi phiếu nháp đã có `phieu_nhap` mà chưa có dòng thật — cả khi
// mở từ nút trên phiếu nhập, lẫn khi thủ kho tự chọn phiếu nhập. Bắt người vừa chọn
// phiếu nhập lại phải bấm thêm "Lấy dòng" mới thấy dòng hàng là làm đúng cái luồng
// chủ đầu tư chê hôm 17/09.
//
// Khoá theo `tên phiếu | phiếu nhập`, không phải cờ true/false: đối tượng `frm`
// được Frappe dùng lại cho MỌI bản ghi cùng doctype trong phiên, nên một cờ boolean
// ở phiếu thứ nhất sẽ chặn tự nạp ở phiếu thứ hai; và đổi phiếu nhập thì phải nạp lại.
function tu_nap_neu_can(frm) {
	const khoa = `${frm.doc.name}|${frm.doc.phieu_nhap}`;
	if (frm.doc.docstatus !== 0 || !frm.doc.phieu_nhap || dong_that(frm).length) return;
	if (frm.__da_tu_nap_cho === khoa) return;
	frm.__da_tu_nap_cho = khoa;
	lay_dong(frm);
}
