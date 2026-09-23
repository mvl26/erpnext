// In TEM KIỆN cho hàng đã lấy theo phiếu giao (22/09/2026) — dùng chung cho nút
// "In tem kiện" trên form phiếu giao và trong hộp thoại lấy hàng.
//
// Bố cục là NGUYÊN tem lô 50×30 (`tem_lo.js`): máy chủ (`vitri/tem_kien.py`) đã
// ánh xạ dữ liệu kiện vào các ô F1…F11 — xem docstring ở đó. File này chỉ nối
// ba bước: đọc dữ liệu → mở cửa sổ in → đánh dấu đã in.
//
// ĐÁNH DẤU SAU KHI CỬA SỔ IN MỞ ĐƯỢC, không trước: `so_kien_da_in` là điều kiện
// để duyệt phiếu. Đánh dấu trước mà trình duyệt chặn pop-up thì phiếu duyệt
// được trong khi chưa có tờ tem nào ra máy in.
//
// Nạp bằng `frappe.require` (không vào `app_include_js`) — cùng lý do `in_nhan_lo.js`.

frappe.provide("erpnext.warehouse_operations");

erpnext.warehouse_operations.tem_kien = (function () {
	// `tem_vi_tri.js` PHẢI đứng trước `tem_lo.js` — xem `in_nhan_lo.js`.
	const DUONG_NAP = [
		"/assets/erpnext/js/warehouse_operations/tem_vi_tri.js",
		"/assets/erpnext/js/warehouse_operations/tem_lo.js",
	];
	const M_DU_LIEU = "erpnext.warehouse_operations.vitri.tem_kien.du_lieu_tem_kien";
	const M_DANH_DAU = "erpnext.warehouse_operations.vitri.tem_kien.danh_dau_da_in";

	/** In tem kiện của phiếu `phieu`. `chi_chua_in` (mặc định 1): chỉ kiện chưa in;
	 * 0 = in lại cả phiếu. Trả Promise → `{so_kien_da_in, tong_kien}`, hoặc `null`
	 * khi không có gì để in / cửa sổ in bị chặn. */
	function in_tem(phieu, chi_chua_in) {
		chi_chua_in = chi_chua_in === undefined ? 1 : chi_chua_in ? 1 : 0;
		return new Promise((xong) => {
			frappe.require(DUONG_NAP, () => {
				frappe
					.xcall(M_DU_LIEU, { phieu, chi_chua_in })
					.then((tem) => {
						if (!tem || !tem.length) {
							frappe.show_alert({ message: __("Không còn kiện nào chưa in tem."), indicator: "blue" });
							return xong(null);
						}
						if (!erpnext.warehouse_operations.tem_lo.in_xap(tem)) {
							frappe.msgprint({
								title: __("Trình duyệt chặn cửa sổ in"),
								message: __(
									"Chưa in được tem kiện: trình duyệt không cho mở cửa sổ mới. "
										+ "Cho phép pop-up cho trang này rồi bấm lại. Chưa kiện nào được "
										+ "đánh dấu đã in."
								),
								indicator: "red",
							});
							return xong(null);
						}
						const dong = [...new Set(tem.map((t) => t.dong_phan_bo))];
						return frappe
							.xcall(M_DANH_DAU, { phieu, dong_phan_bo: dong })
							.then((kq) => {
								frappe.show_alert({
									message: __("Đã in {0} tem kiện · {1}/{2} kiện có tem", [
										tem.length,
										kq.so_kien_da_in,
										kq.tong_kien,
									]),
									indicator: "green",
								});
								xong(kq);
							});
					})
					.catch(() => xong(null));
			});
		});
	}

	return { in_tem };
})();
