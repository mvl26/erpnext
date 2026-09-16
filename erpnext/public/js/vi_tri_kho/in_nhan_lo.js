// Đường IN nhãn lô, dùng chung cho HAI màn hình: nút "In nhãn cả phiếu" trên
// `Batch Entry` và nút "In nhãn" trên form `Batch`.
//
// VÌ SAO LÀ MỘT FILE RIÊNG (brief Task 9 chỉ liệt kê hai file `batch_entry.js`
// và `batch.js` — đây là chỗ lệch, cố ý, và đây là lý do):
//
//   Hai màn hình chạy CÙNG MỘT trình tự ba bước — `dat_o_in_tem` (ghi, chốt ô
//   lên tem) → `du_lieu_tem` (đọc 11 ô F1…F11 đã định dạng) → `tem_lo.in_xap`
//   (dựng cửa sổ in) — chỉ khác ở chỗ lấy danh sách lô từ đâu: bảng con của
//   phiếu, hay chính bản ghi `Batch` đang mở. Chép trình tự đó làm hai bản là
//   mở đường cho hai bản LỆCH NHAU, và lớp lỗi đó ("màn hình nói một đằng, tem
//   in ra một nẻo") là lớp lỗi cả khối C được dựng lên để tránh — đã ghi ở
//   docstring `nhap_lo.py` và ở đầu `tem_lo.js`. Cụ thể nhất: chỉ cần một bản
//   quên gọi `dat_o_in_tem` trước `du_lieu_tem` là tem in ra F8 = "VT —" trong
//   im lặng, còn ô thì KHÔNG BAO GIỜ được chốt.
//
// THỨ TỰ HAI LỜI GỌI LÀ BẮT BUỘC, không phải sở thích: `du_lieu_tem` CHỈ ĐỌC
// (nó cố ý không ghi `custom_o_in_tem` — xem docstring `nhap_lo.py`). Gọi nó
// trước `dat_o_in_tem` thì F8 chỉ là một phép XEM TRƯỚC, và ô thật được chốt
// SAU đó có thể khác — tờ tem đã in ra nói sai ngay từ giây đầu.
//
// VÌ SAO GỌI `du_lieu_tem` TỪNG LÔ MỘT chứ không truyền cả mảng (hàm máy chủ
// NHẬN mảng): ĐÃ ĐO trên erptest.local 16/09/2026, không phải suy từ mã —
//
//     curl -H "Cookie: sid=…" -X POST …/nhap_lo.du_lieu_tem \
//          --data-urlencode 'so_lo=["A","B"]'
//     -> DoesNotExistError: Batch ["A","B"] not found
//
// `frappe.request.prepare` (frappe/public/js/frappe/request.js:401) JSON.
// stringify mọi đối số kiểu mảng, rồi gửi đi dưới dạng form-encoded; phía máy
// chủ `make_form_dict` chỉ json.loads khi content-type là JSON, nên đối số về
// tới Python là CHUỖI `'["A","B"]'`. Chú giải `list[str] | str` khớp nhánh
// `str` nên pydantic không đổi gì, và `isinstance(so_lo, str)` biến cả chuỗi
// thành MỘT tên lô bịa. Tức là truyền mảng từ JS hỏng ngay tại cú bấm — không
// phải lúc dựng, mà lúc thủ kho bấm In. Đường vòng (ép content-type JSON) thì
// phải bỏ `frappe.call`; đường thẳng là gọi từng lô, và ta đã gọi từng lô cho
// `dat_o_in_tem` rồi nên không thêm hạng chi phí nào mới.
//
// Nạp bằng `frappe.require` từ hai màn hình đó, KHÔNG thêm vào `app_include_js`
// của `hooks.py` — cùng lý do đã ghi ở `tem_lo.js`/`tem_vi_tri.js`: nhãn chỉ
// hai màn hình cần, mà dòng trong `hooks.py` là dòng dễ mất nhất mỗi lần merge.

frappe.provide("erpnext.vi_tri_kho");

erpnext.vi_tri_kho.in_nhan = (function () {
	// `tem_vi_tri.js` PHẢI đứng trước `tem_lo.js`: `tem_lo.may_vach()` ném lỗi
	// nếu `erpnext.vi_tri_kho.tem.may_ve_ma_vach` chưa có (tem_lo.js:589).
	// `frappe.assets.execute` chạy các mục theo ĐÚNG thứ tự mảng sau khi tải
	// xong (frappe/public/js/frappe/assets.js:107-112), nên thứ tự này là bảo
	// đảm chứ không phải may rủi.
	const DUONG_NAP = [
		"/assets/erpnext/js/vi_tri_kho/tem_vi_tri.js",
		"/assets/erpnext/js/vi_tri_kho/tem_lo.js",
	];

	const M_DAT_O = "erpnext.vi_tri_kho.vitri.nhap_lo.dat_o_in_tem";
	const M_DU_LIEU = "erpnext.vi_tri_kho.vitri.nhap_lo.du_lieu_tem";

	/** Chốt ô rồi lấy dữ liệu tem cho từng lô, TUẦN TỰ, giữ nguyên thứ tự.
	 *
	 * Tuần tự (reduce trên Promise) chứ không `Promise.all`: `dat_o_in_tem`
	 * GHI `Batch.custom_o_in_tem`, và thứ tự tem in ra phải khớp thứ tự dòng
	 * trên phiếu — thủ kho cầm xấp tem đối chiếu với phiếu theo thứ tự. Với
	 * `Promise.all` thì thứ tự kết quả vẫn đúng, nhưng thứ tự GHI thì không,
	 * và một phiếu 30 dòng bắn 60 request song song vào một dev server một
	 * luồng là tự chuốc timeout.
	 */
	function chuoi_du_lieu(danh_sach_lo) {
		const tem = [];
		const khong_co_o = [];

		return danh_sach_lo
			.reduce(
				(truoc, so_lo) =>
					truoc
						.then(() => frappe.xcall(M_DAT_O, { so_lo }))
						.then((o) => {
							// `dat_o_in_tem` trả `null` khi không suy được kho
							// (lô không sinh từ phiếu nhập, hoặc phiếu nhập lô
							// chưa duyệt) hoặc mặt hàng chưa gán vị trí. Spec
							// §6.5 KHÔNG chặn in trong ca này — nhãn vẫn dán
							// lên hàng được — nhưng F8 sẽ in "VT —", và im
							// lặng đúng chỗ này là món nợ số 1 của Task 8.
							// Gom lại để báo MỘT lần sau khi in.
							if (!o) khong_co_o.push(so_lo);
							return frappe.xcall(M_DU_LIEU, { so_lo });
						})
						.then((r) => {
							(r || []).forEach((o) => tem.push(o));
						}),
				Promise.resolve()
			)
			.then(() => ({ tem, khong_co_o }));
	}

	/** Mở cửa sổ in cho `danh_sach_lo` (mảng tên `Batch`), mỗi lô một nhãn. */
	function in_cho_cac_lo(danh_sach_lo) {
		danh_sach_lo = (danh_sach_lo || []).filter(Boolean);
		if (!danh_sach_lo.length) return;

		frappe.require(DUONG_NAP, () => {
			chuoi_du_lieu(danh_sach_lo).then(({ tem, khong_co_o }) => {
				if (khong_co_o.length) {
					// Nói TRƯỚC khi cửa sổ in che mất màn hình. Không chặn in
					// (spec §6.5), chỉ phá vỡ sự im lặng: tem sắp ra có ô
					// trống, và thủ kho phải biết để không đi tìm "VT —" trên
					// kệ.
					frappe.show_alert(
						{
							message: __("{0} nhãn không có ô (in 'VT —'): {1}.", [
								khong_co_o.length,
								khong_co_o.join(", "),
							]),
							indicator: "orange",
						},
						10
					);
				}

				const mo_duoc = erpnext.vi_tri_kho.tem_lo.in_xap(tem);
				if (!mo_duoc) {
					// `in_xap` trả `false` đúng khi `window.open` bị chặn.
					// Không báo thì người dùng bấm In, không có gì xảy ra, và
					// không có gì giải thích — ô CŨNG ĐÃ BỊ CHỐT rồi (đã gọi
					// `dat_o_in_tem`), nên "bấm lại cho chắc" vẫn không ra tem.
					frappe.msgprint({
						title: __("Trình duyệt chặn cửa sổ in"),
						message: __(
							"Nhãn đã dựng xong nhưng trình duyệt không cho mở cửa sổ mới. Cho phép "
							+ "pop-up cho trang này rồi bấm lại — ô in trên tem đã được chốt nên "
							+ "lần in sau ra đúng tờ tem này."
						),
						indicator: "red",
					});
				}
			});
		});
	}

	return { in_cho_cac_lo };
})();
