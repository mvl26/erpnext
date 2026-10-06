// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

// `scope_name` trong bảng Phạm vi là Dynamic Link trỏ theo `scope_doctype`, mà
// `scope_doctype` là trường suy ra nên để read-only. Nếu không điền nó phía client thì
// người dùng thêm dòng xong sẽ không chọn được gì: ô trái không gõ được, ô phải không
// biết tìm ở đâu, và cả hai đều bắt buộc. Đây là file giữ cho lưới dùng được.

frappe.ui.form.on("TBYT Regulatory Document", {
	onload(frm) {
		apply_scope_doctype(frm);
	},
	document_type(frm) {
		// Đổi loại chứng từ có thể đổi luôn cấp phạm vi, làm mọi dòng đang có trở nên
		// vô nghĩa — xoá đi còn hơn để người dùng lưu một phạm vi trỏ sai chủ thể.
		frm.clear_table("pham_vi");
		frm.refresh_field("pham_vi");
		apply_scope_doctype(frm);
	},
});

frappe.ui.form.on("TBYT Document Scope", {
	pham_vi_add(frm) {
		apply_scope_doctype(frm);
	},
});

function apply_scope_doctype(frm) {
	if (!frm.doc.document_type) {
		set_scope_hint(frm, null);
		return;
	}
	frappe.call({
		method: "erpnext.tbyt.doctype.tbyt_regulatory_document.tbyt_regulatory_document.get_scope_doctype",
		args: { document_type: frm.doc.document_type },
		callback(r) {
			const target = r.message;
			if (!target) return;
			(frm.doc.pham_vi || []).forEach((row) => {
				if (row.scope_doctype !== target) {
					frappe.model.set_value(row.doctype, row.name, "scope_doctype", target);
				}
			});
			frm.refresh_field("pham_vi");
			set_scope_hint(frm, target);
		},
	});
}

function set_scope_hint(frm, target) {
	const NAMES = {
		Company: __("Công ty"),
		Manufacturer: __("Chủ sở hữu (hãng)"),
		"TBYT Marketing Authorization": __("Số lưu hành"),
		Batch: __("Lô hàng"),
		Item: __("Mặt hàng"),
	};
	const field = frm.fields_dict.pham_vi;
	if (!field) return;
	field.df.description = target
		? __(
				"Tờ giấy này cấp cho: chọn {0}. Một tờ ghi tên nhiều đối tượng thì thêm nhiều dòng — vẫn là một bản ghi.",
				[`<b>${NAMES[target] || target}</b>`]
		  )
		: __(
				"Chọn Loại chứng từ trước — ô bên dưới sẽ tự biết cần chọn Công ty, Chủ sở hữu, Số lưu hành, Lô hàng hay Mặt hàng."
		  );
	frm.refresh_field("pham_vi");
}
