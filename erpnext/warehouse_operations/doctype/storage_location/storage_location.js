// Vẽ TRƯỚC con tem của ô ngay trên form Storage Location.
//
// Trước 14/09/2026 chỗ này chỉ vẽ một mã vạch trần. Nay vẽ đúng con tem sẽ in
// ra — cùng một bộ vẽ với trang in (`public/js/warehouse_operations/tem_vi_tri.js`), nên
// không có đường nào để hai bên nói khác nhau. Xem trước một bố cục khác với
// cái in ra thì tệ hơn là không xem trước gì.
//
// KHÔNG LƯU GÌ THÊM VÀO CSDL. Trường `xem_ma_vach` là fieldtype HTML nên không
// sinh cột; hình được vẽ lại mỗi lần mở form từ các trường đã có sẵn.
//
// VÌ SAO KHÔNG DÙNG THẲNG fieldtype "Barcode" cho trường này: control Barcode
// của Frappe ghi NGƯỢC cả chuỗi SVG vào tài liệu khi nó có `this.doc`
// (frappe/public/js/frappe/form/controls/barcode.js:36 và base_control.js:280).
// Làm vậy thì 214 bản ghi ô sẽ mang 214 cục SVG trong CSDL, cho một thứ chỉ là
// hình vẽ lại của `ma_o` — phình dữ liệu mà không thêm thông tin nào.
//
// VÌ SAO PHẢI MƯỢN control của Frappe chứ không gọi thẳng JsBarcode: thư viện
// jsbarcode được esbuild gói KÍN trong `controls.bundle.*.js` của frappe, không
// lộ ra biến toàn cục. Đường duy nhất chạm tới nó mà không thêm phụ thuộc mới
// vào erpnext/package.json là qua `frappe.ui.form.ControlBarcode` — lớp này CÓ
// nằm trên `frappe.ui.form`. Chi tiết cách bọc nằm ở `tem_vi_tri.js`.

const DUONG_TEM = "/assets/erpnext/js/warehouse_operations/tem_vi_tri.js";

frappe.ui.form.on("Storage Location", {
	refresh(frm) {
		ve_xem_tem(frm);
	},
});

function ve_xem_tem(frm) {
	const truong = frm.get_field("xem_ma_vach");
	if (!truong) return;
	truong.$wrapper.empty();

	// Ô "Chưa xếp vị trí" là ô ẢO, không có kệ thật để dán tem, và mã của nó
	// kèm cả tên kho lẫn dấu cách (ví dụ "ZZZ-CHUA-XEP-Kho Miyano - MYN") nên
	// không tách được thành năm thành phần của tem.
	if (frm.doc.la_o_chua_xep) {
		nhan_nho(truong, __("Ô hệ thống — không dán tem, không cần mã vạch."));
		return;
	}

	// Nút nhóm (Khu / Dãy / Khoang / Tầng) chỉ là nốt trên cây, không ứng với
	// một ô chứa hàng nào. `danh_sach_tem()` phía máy chủ cũng loại chúng ra —
	// nếu ở đây vẫn vẽ một con tem thì form và lệnh in nói khác nhau.
	if (frm.doc.is_group) {
		nhan_nho(truong, __("Nút nhóm — không có kệ thật để dán tem. Tem chỉ in cho ô chứa hàng."));
		return;
	}

	// `barcode` do StorageLocation.validate() phía máy chủ tự điền bằng `ma_o`.
	const ma = frm.doc.barcode || frm.doc.ma_o;
	if (!ma) {
		nhan_nho(truong, __("Lưu bản ghi để xem trước con tem."));
		return;
	}

	const khung = $('<div class="vi-tri-kho-xem-tem-wrap"></div>').appendTo(truong.$wrapper);
	const o_tem = $('<div style="margin-bottom:8px"></div>').appendTo(khung);

	frappe.require(DUONG_TEM, () => {
		erpnext.warehouse_operations.tem.ve_xem_truoc(o_tem, {
			ma_o: ma,
			khu: phan(frm, "khu", 0),
			day: phan(frm, "day", 2),
			khoang: phan(frm, "khoang", 4),
			tang: phan(frm, "tang", 6),
			o: phan(frm, "o", 8),
			kho: frm.doc.kho,
			ten_o: frm.doc.ten_o,
		});
	});

	$(`<div class="text-muted small">
		${__("Máy quét trả ra")}: <b>${frappe.utils.escape_html(ma)}</b> ·
		${__("in từ cây vị trí (nút <b>In tem</b>)")}
	</div>`).appendTo(khung);
}

/** Một thành phần của mã: lấy từ trường đã lưu, thiếu thì cắt từ `ma_o`.
 *
 * CÙNG lưới đỡ với `tem.py::danh_sach_tem` (mệnh đề `substr` trong SQL), và
 * phải cùng: bản ghi lá tạo TRƯỚC khi có năm cột thành phần thì `o` rỗng. Nếu
 * ở đây chỉ kiểm `!frm.doc.o` rồi bỏ cuộc, form sẽ báo "Lưu bản ghi để xem
 * trước" trên một bản ghi ĐÃ lưu hoàn toàn hợp lệ — người dùng bấm Lưu lại,
 * không có gì đổi, và không hiểu vì sao. Tệ hơn nữa là lệnh in VẪN ra tem cho
 * chính ô đó, nên form và máy in nói khác nhau.
 *
 * Hai đường luôn cho cùng kết quả vì mỗi cấp là tiền tố của cấp sau
 * (`ma_vi_tri.py`), nên cắt theo vị trí là phép tách đúng, không phải phép đoán.
 */
function phan(frm, ten, tu) {
	return frm.doc[ten] || String(frm.doc.ma_o || "").substring(tu, tu + 2);
}

function nhan_nho(truong, chu) {
	$(`<div class="text-muted">${chu}</div>`).appendTo(truong.$wrapper);
}
