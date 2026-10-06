frappe.ui.form.on("Quality Feedback", {
	template: function (frm) {
		if (frm.doc.template) {
			frm.call("set_parameters");
		}
	},
});
