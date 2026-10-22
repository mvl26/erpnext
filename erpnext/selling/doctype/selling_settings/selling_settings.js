frappe.ui.form.on("Selling Settings", {
	after_save(frm) {
		frappe.boot.user.defaults.editable_price_list_rate = frm.doc.editable_price_list_rate;
	},
});
