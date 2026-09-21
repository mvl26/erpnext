// Đường vào quản lý vị trí ngay trên phiếu Warehouse (module "Warehouse Operations").
//
// Gắn qua `doctype_js` trong erpnext/hooks.py, KHÔNG sửa
// erpnext/stock/doctype/warehouse/warehouse.js — file đó là của upstream và đã
// có sẵn bốn nút; chèn thêm vào đó là tự tạo một điểm xung đột nữa cho mỗi lần
// merge ERPNext bản mới, trong khi hook cho kết quả y hệt.
//
// Ở đây CỐ Ý không dựng lại hộp thoại xem-trước-rồi-xác-nhận. Luồng đó đã nằm
// ở `Warehouse Location Setup`, và nó là luồng ghi dữ liệu (tạo ô, ghi sổ, đổi
// cờ). Có hai bản sao của một luồng như vậy là mời gọi hai bản lệch nhau —
// nên các nút dưới đây chỉ DẪN TỚI hồ sơ đó.

frappe.ui.form.on("Warehouse", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.is_group) return;

		const nhom = __("Vị trí kho");

		if (!frm.doc.custom_quan_ly_vi_tri) {
			frm.add_custom_button(__("Bật quản lý vị trí"), () => mo_thiet_lap(frm), nhom);
			return;
		}

		frm.add_custom_button(__("Ô kệ của kho"), () => {
			frappe.set_route("List", "Storage Location", { kho: frm.doc.name });
		}, nhom);

		[
			[__("Tồn kho theo vị trí"), "Ton Kho Theo Vi Tri"],
			[__("Hàng chưa xếp vị trí"), "Hang Chua Xep Vi Tri"],
			[__("Đối soát tồn vị trí"), "Doi Soat Ton Vi Tri"],
		].forEach(([nhan, bao_cao]) => {
			frm.add_custom_button(nhan, () => {
				frappe.set_route("query-report", bao_cao, { kho: frm.doc.name });
			}, nhom);
		});

		frm.add_custom_button(__("Thiết lập vị trí"), () => mo_thiet_lap(frm), nhom);
	},
});

// Hồ sơ `Warehouse Location Setup` đặt tên theo chính tên kho (autoname:
// field:kho), nên tra được bằng `exists` mà không phải truy vấn danh sách.
function mo_thiet_lap(frm) {
	frappe.db.exists("Warehouse Location Setup", frm.doc.name).then((co) => {
		if (co) {
			frappe.set_route("Form", "Warehouse Location Setup", frm.doc.name);
			return;
		}
		frappe.new_doc("Warehouse Location Setup", { kho: frm.doc.name });
	});
}
