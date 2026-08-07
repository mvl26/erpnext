frappe.ui.form.on("Price List", {
	refresh: function (frm) {
		let me = this;
		frm.add_custom_button(
			__("Add / Edit Prices"),
			function () {
				frappe.route_options = {
					price_list: frm.doc.name,
				};
				frappe.set_route("Report", "Item Price");
			},
			"fa fa-money"
		);
	},
});
