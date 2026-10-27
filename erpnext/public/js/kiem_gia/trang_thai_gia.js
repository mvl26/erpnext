// Tô màu ô "Trạng thái giá" trên dòng Báo giá / Đơn bán hàng, cùng màu với hai báo cáo đối
// soát. Gắn formatter vào docfield_map ở `setup`: lưới và chi tiết dòng dùng bản sao trường
// chép từ đây khi form vẽ chứng từ, nên mang theo formatter.
frappe.provide("erpnext.kiem_gia");

erpnext.kiem_gia.MAU_TRANG_THAI_GIA = {
	Khớp: "green",
	"Thấp hơn": "red",
	"Cao hơn": "orange",
	"Chưa có giá mua": "red",
	"Đang trong thời hạn báo giá": "blue",
	"Bỏ qua": "gray",
};

// "Đang trong thời hạn báo giá" không hiện trên chứng từ (BA): hiện theo chênh lệch như dòng
// thường. Giá trị lưu và quy tắc miễn lý do / chấp thuận giữ nguyên (kiem_chung_tu.py).
erpnext.kiem_gia.trang_thai_hien_thi = function (value, d) {
	if (value !== "Đang trong thời hạn báo giá") return value;
	const cl = flt(d && d.chenh_lech_gia);
	return cl < 0 ? "Thấp hơn" : cl > 0 ? "Cao hơn" : "Khớp";
};

erpnext.kiem_gia.to_mau_trang_thai_gia = function (cdt) {
	const df = (frappe.meta.docfield_map[cdt] || {}).trang_thai_gia;
	if (!df) return;
	df.formatter = (value, _df, _options, doc) => {
		if (!value) return "";
		value = erpnext.kiem_gia.trang_thai_hien_thi(value, doc);
		const color = erpnext.kiem_gia.MAU_TRANG_THAI_GIA[value] || "gray";
		return `<span class="indicator-pill ${color}">${frappe.utils.escape_html(__(value))}</span>`;
	};
};
