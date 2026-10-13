frappe.ui.form.on("Brand", {
	refresh: function (frm) {
		// Mã đã lưu thì khóa: nó đã, hoặc sắp, nằm trong mã vật tư.
		const rule_mode = frappe.defaults.get_default("item_naming_by") === "Quy tắc mã vật tư";
		const locked = rule_mode && !frm.is_new() && !!frm.doc.brand_code;
		frm.set_df_property("brand_code", "read_only", locked ? 1 : 0);
		if (!locked) return;

		const name = frm.doc.name;
		frappe.call("erpnext.stock.item_code_rule.may_change_codes").then((r) => {
			if (!r.message || frm.doc.name !== name) return;
			frm.add_custom_button(__("Đổi mã thương hiệu (Change Brand Code)"), () => {
				frm.set_df_property("brand_code", "read_only", 0);
			});
		});
	},

	setup: (frm) => {
		frm.set_query("default_warehouse", "brand_defaults", function (doc, cdt, cdn) {
			const row = locals[cdt][cdn];
			return {
				filters: { company: row.company },
			};
		});

		frm.set_query("default_discount_account", "brand_defaults", function (doc, cdt, cdn) {
			const row = locals[cdt][cdn];
			return {
				filters: {
					report_type: "Profit and Loss",
					company: row.company,
					is_group: 0,
				},
			};
		});

		frm.set_query("buying_cost_center", "brand_defaults", function (doc, cdt, cdn) {
			const row = locals[cdt][cdn];
			return {
				filters: {
					is_group: 0,
					company: row.company,
				},
			};
		});

		frm.set_query("expense_account", "brand_defaults", function (doc, cdt, cdn) {
			const row = locals[cdt][cdn];
			return {
				query: "erpnext.controllers.queries.get_expense_account",
				filters: { company: row.company },
			};
		});

		frm.set_query("default_provisional_account", "brand_defaults", function (doc, cdt, cdn) {
			const row = locals[cdt][cdn];
			return {
				filters: {
					company: row.company,
					root_type: ["in", ["Liability", "Asset"]],
					is_group: 0,
				},
			};
		});

		frm.set_query("selling_cost_center", "brand_defaults", function (doc, cdt, cdn) {
			const row = locals[cdt][cdn];
			return {
				filters: {
					is_group: 0,
					company: row.company,
				},
			};
		});

		frm.set_query("income_account", "brand_defaults", function (doc, cdt, cdn) {
			const row = locals[cdt][cdn];
			return {
				query: "erpnext.controllers.queries.get_income_account",
				filters: { company: row.company },
			};
		});
	},
});
