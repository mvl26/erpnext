// Vẽ mã vạch của ô ngay trên form Storage Location.
//
// KHÔNG lưu gì thêm vào CSDL. Trường `xem_ma_vach` là fieldtype HTML nên không
// sinh cột; hình được vẽ lại mỗi lần mở form từ chuỗi `barcode` đã có sẵn.
//
// VÌ SAO KHÔNG DÙNG THẲNG fieldtype "Barcode" cho trường này: control Barcode của
// Frappe ghi NGƯỢC cả chuỗi SVG vào tài liệu khi nó có `this.doc`
// (frappe/public/js/frappe/form/controls/barcode.js:36 và base_control.js:280).
// Làm vậy thì 214 bản ghi ô sẽ mang 214 cục SVG trong CSDL, cho một thứ chỉ là
// hình vẽ lại của `ma_o` — phình dữ liệu mà không thêm thông tin nào.
//
// VÌ SAO PHẢI MƯỢN control của Frappe chứ không gọi thẳng JsBarcode: thư viện
// jsbarcode được esbuild gói KÍN trong `controls.bundle.*.js` của frappe, không
// lộ ra biến toàn cục. Đường duy nhất chạm tới nó mà không thêm phụ thuộc mới
// vào erpnext/package.json là qua `frappe.ui.form.ControlBarcode` — lớp này CÓ
// nằm trên `frappe.ui.form`.
//
// VÌ SAO VẪN PHẢI TRUYỀN MỘT `doc` (dù là object rỗng): đây là chỗ dễ làm sai
// nhất, đã đo trên trình duyệt ngày 13/09/2026. Trong `set_formatted_input()`
// (barcode.js:35), lệnh vẽ nằm SAU điều kiện `if (!barcode_value && this.doc)`
// — nghĩa là CÙNG một cái `this.doc` vừa cổng việc ghi ngược, vừa cổng việc vẽ.
// Bỏ `doc` đi thì đúng là không ghi gì, nhưng cũng KHÔNG VẼ GÌ: biến `svg` giữ
// nguyên chuỗi thô nên `barcode_area.html(...)` in ra dòng chữ "1A04040402"
// trần, không một vạch nào, và không có lỗi nào trên console để lần ra.
//
// Nên truyền một object rỗng làm `doc`. Control vẽ bình thường, còn chuỗi SVG
// nó ghi ngược thì rơi vào object rỗng đó — object này chết theo lần mở form,
// không dính tới `frm.doc`, không có cột nào trong CSDL. Đã đo: sau khi vẽ,
// `frappe.model.get_doc(...).xem_ma_vach === undefined`.

frappe.ui.form.on("Storage Location", {
	refresh(frm) {
		ve_ma_vach(frm);
	},
});

function ve_ma_vach(frm) {
	const truong = frm.get_field("xem_ma_vach");
	if (!truong) return;
	truong.$wrapper.empty();

	// `barcode` do StorageLocation.validate() phía máy chủ tự điền bằng `ma_o`
	// (storage_location.py:48). Bản ghi chưa lưu thì chưa có.
	const ma = frm.doc.barcode || frm.doc.ma_o;
	if (!ma) {
		nhan_nho(truong, __("Lưu bản ghi để hiện mã vạch."));
		return;
	}

	// Ô "Chưa xếp vị trí" là ô ảo, không có kệ thật để dán tem, và mã của nó
	// kèm cả tên kho lẫn dấu cách (ví dụ "ZZZ-CHUA-XEP-Kho Miyano - MYN") nên
	// tem in ra sẽ dài vô ích.
	if (frm.doc.la_o_chua_xep) {
		nhan_nho(truong, __("Ô hệ thống — không dán tem, không cần mã vạch."));
		return;
	}

	const khung = $('<div class="vi-tri-kho-ma-vach"></div>').appendTo(truong.$wrapper);

	// get_options() của control THAY THẾ toàn bộ mặc định bằng JSON này khi
	// options là JSON hợp lệ (barcode.js:60-66) — nên phải khai đủ, không kế thừa.
	const tuy_chon = {
		format: "CODE128",
		displayValue: true,
		// Mắt người đọc dạng có gạch nối; MÁY QUÉT vẫn trả ra đúng `ma_o` 10 ký
		// tự, vì `text` chỉ đổi chữ hiển thị chứ không đổi thứ được mã hoá.
		text: frm.doc.ma_in_nhan || ma,
		fontSize: 16,
		width: 2,
		height: 60,
		margin: 8,
	};

	// Object rỗng dùng một lần: control cần `doc` để chịu vẽ (xem chú thích đầu
	// file), và chuỗi SVG nó ghi ngược sẽ nằm lại đây thay vì trong `frm.doc`.
	const ho_so_vut_di = {};

	const control = frappe.ui.form.make_control({
		parent: khung,
		render_input: true,
		doc: ho_so_vut_di,
		df: {
			fieldtype: "Barcode",
			fieldname: "hinh",
			label: "",
			options: JSON.stringify(tuy_chon),
		},
	});
	control.set_value(ma);

	// Control kế thừa ControlData nên còn dựng kèm một ô nhập; ở đây chỉ cần
	// phần hình, ô nhập để lại sẽ trông như sửa được mà thật ra không.
	khung.find(".control-input").hide();

	$(`<div class="text-muted small" style="margin-top:4px">
		${__("Máy quét trả ra")}: <b>${frappe.utils.escape_html(ma)}</b>
	</div>`).appendTo(khung);
}

function nhan_nho(truong, chu) {
	$(`<div class="text-muted">${chu}</div>`).appendTo(truong.$wrapper);
}
