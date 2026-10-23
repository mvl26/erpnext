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

erpnext.kiem_gia.to_mau_trang_thai_gia = function (cdt) {
	const df = (frappe.meta.docfield_map[cdt] || {}).trang_thai_gia;
	if (!df) return;
	df.formatter = (value) => {
		if (!value) return "";
		const color = erpnext.kiem_gia.MAU_TRANG_THAI_GIA[value] || "gray";
		return `<span class="indicator-pill ${color}">${frappe.utils.escape_html(__(value))}</span>`;
	};
};
