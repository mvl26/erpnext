frappe.ui.form.on("Newsletter", {
	refresh() {
		erpnext.toggle_naming_series();
	},
});
