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

frappe.ui.form.on("Batch Entry", {
	refresh(frm) {
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
		if (!frm.doc.items || !frm.doc.items.length) return;

		frappe.confirm(
			__(
				"Đổi phiếu nhập sẽ xoá {0} dòng đang có (kèm số lô và hạn dùng đã gõ). Tiếp tục?",
				[frm.doc.items.length]
			),
			() => {
				frm.clear_table("items");
				frm.refresh_field("items");
				frappe.show_alert({
					message: __("Đã xoá các dòng vì đổi phiếu nhập."),
					indicator: "orange",
				});
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
				frappe.msgprint({
					title: __("Không có dòng nào cần khai lô"),
					message: __(
						"Phiếu nhập {0} không còn dòng hàng quản lý lô nào chưa có số lô. "
						+ "Mặt hàng KHÔNG bật 'Có lô' cũng không hiện ở đây.",
						[frm.doc.phieu_nhap]
					),
					indicator: "green",
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
