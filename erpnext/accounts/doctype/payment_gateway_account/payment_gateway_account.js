frappe.ui.form.on("Payment Gateway Account", {
	refresh(frm) {
		erpnext.utils.check_payments_app();
		if (!frm.doc.__islocal) {
			frm.set_df_property("payment_gateway", "read_only", 1);
		}
	},

	setup(frm) {
		frm.set_query("payment_account", function () {
			return {
				filters: {
					company: frm.doc.company,
				},
			};
		});
	},
});
