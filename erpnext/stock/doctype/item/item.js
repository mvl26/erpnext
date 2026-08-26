frappe.provide("erpnext.item");

const SALES_DOCTYPES = ["Quotation", "Sales Order", "Delivery Note", "Sales Invoice"];
const PURCHASE_DOCTYPES = ["Purchase Order", "Purchase Receipt", "Purchase Invoice"];

frappe.ui.form.on("Item", {
	valuation_method(frm) {
		if (!frm.is_new() && frm.doc.valuation_method === "Moving Average") {
			let stock_exists = frm.doc.__onload && frm.doc.__onload.stock_exists ? 1 : 0;
			let current_valuation_method = frm.doc.__onload.current_valuation_method;

			if (stock_exists && current_valuation_method !== frm.doc.valuation_method) {
				let msg = __(
					"Changing the valuation method to Moving Average will affect new transactions. If backdated entries are added, earlier FIFO-based entries will be reposted, which may change closing balances."
				);
				msg += "<br>";
				msg += __(
					"Also you can't switch back to FIFO after setting the valuation method to Moving Average for this item."
				);
				msg += "<br>";
				msg += __("Do you want to change valuation method?");

				frappe.confirm(
					msg,
					() => {
						frm.set_value("valuation_method", "Moving Average");
					},
					() => {
						frm.set_value("valuation_method", current_valuation_method);
					}
				);
			}
		}
	},

	setup: function (frm) {
		frm.add_fetch("attribute", "numeric_values", "numeric_values");
		frm.add_fetch("attribute", "from_range", "from_range");
		frm.add_fetch("attribute", "to_range", "to_range");
		frm.add_fetch("attribute", "increment", "increment");
		frm.add_fetch("tax_type", "tax_rate", "tax_rate");

		frm.make_methods = {
			Quotation: () => {
				open_form(frm, "Quotation", "Quotation Item", "items");
			},
			"Sales Order": () => {
				open_form(frm, "Sales Order", "Sales Order Item", "items");
			},
			"Delivery Note": () => {
				open_form(frm, "Delivery Note", "Delivery Note Item", "items");
			},
			"Sales Invoice": () => {
				open_form(frm, "Sales Invoice", "Sales Invoice Item", "items");
			},
			"Purchase Order": () => {
				open_form(frm, "Purchase Order", "Purchase Order Item", "items");
			},
			"Purchase Receipt": () => {
				open_form(frm, "Purchase Receipt", "Purchase Receipt Item", "items");
			},
			"Purchase Invoice": () => {
				open_form(frm, "Purchase Invoice", "Purchase Invoice Item", "items");
			},
			"Material Request": () => {
				open_form(frm, "Material Request", "Material Request Item", "items");
			},
			"Stock Entry": () => {
				open_form(frm, "Stock Entry", "Stock Entry Detail", "items");
			},
		};
	},
	onload: function (frm) {
		erpnext.item.setup_queries(frm);
		if (frm.doc.variant_of) {
			frm.fields_dict["attributes"].grid.set_column_disp("attribute_value", true);
		}

		if (frm.doc.is_fixed_asset) {
			frm.trigger("set_asset_naming_series");
		}
	},

	refresh: function (frm) {
		if (frm.doc.is_stock_item) {
			frm.add_custom_button(
				__("Stock Balance"),
				function () {
					frappe.route_options = {
						item_code: frm.doc.name,
					};
					frappe.set_route("query-report", "Stock Balance");
				},
				__("View")
			);
			frm.add_custom_button(
				__("Stock Ledger"),
				function () {
					frappe.route_options = {
						item_code: frm.doc.name,
					};
					frappe.set_route("query-report", "Stock Ledger");
				},
				__("View")
			);
			frm.add_custom_button(
				__("Stock Projected Qty"),
				function () {
					frappe.route_options = {
						item_code: frm.doc.name,
					};
					frappe.set_route("query-report", "Stock Projected Qty");
				},
				__("View")
			);
		}

		if (frm.doc.is_fixed_asset) {
			frm.trigger("is_fixed_asset");
			frm.trigger("auto_create_assets");
		}

		// clear intro
		frm.set_intro();

		if (frm.doc.has_variants) {
			frm.set_intro(
				__(
					"This Item is a Template and cannot be used in transactions. Item attributes will be copied over into the variants unless 'No Copy' is set"
				),
				true
			);

			frm.add_custom_button(
				__("Show Variants"),
				function () {
					frappe.set_route("List", "Item", { variant_of: frm.doc.name });
				},
				__("View")
			);

			frm.add_custom_button(
				__("Item Variant Settings"),
				function () {
					frappe.set_route("Form", "Item Variant Settings");
				},
				__("View")
			);

			frm.add_custom_button(
				__("Variant Details Report"),
				function () {
					frappe.set_route("query-report", "Item Variant Details", { item: frm.doc.name });
				},
				__("View")
			);

			if (frm.doc.variant_based_on === "Item Attribute") {
				frm.add_custom_button(
					__("Single Variant"),
					function () {
						erpnext.item.show_single_variant_dialog(frm);
					},
					__("Create")
				);
				frm.add_custom_button(
					__("Multiple Variants"),
					function () {
						erpnext.item.show_multiple_variants_dialog(frm);
					},
					__("Create")
				);
			} else {
				frm.add_custom_button(
					__("Variant"),
					function () {
						erpnext.item.show_modal_for_manufacturers(frm);
					},
					__("Create")
				);
			}

			// frm.page.set_inner_btn_group_as_primary(__('Create'));
		}
		if (frm.doc.variant_of) {
			frm.set_intro(
				__("This Item is a Variant of {0} (Template).", [
					`<a href="/app/item/${frm.doc.variant_of}" onclick="location.reload()">${frm.doc.variant_of}</a>`,
				]),
				true
			);
		}

		if (frappe.defaults.get_default("item_naming_by") != "Naming Series" || frm.doc.variant_of) {
			frm.toggle_display("naming_series", false);
		} else {
			erpnext.toggle_naming_series();
		}

		erpnext.item.edit_prices_button(frm);
		erpnext.item.toggle_attributes(frm);

		if (!frm.doc.is_fixed_asset) {
			erpnext.item.make_dashboard(frm);
		}

		frm.add_custom_button(__("Duplicate"), function () {
			var new_item = frappe.model.copy_doc(frm.doc);
			// Duplicate item could have different name, causing "copy paste" error.
			if (new_item.item_name === new_item.item_code) {
				new_item.item_name = null;
			}
			if (new_item.item_code === new_item.description || new_item.item_code === new_item.description) {
				new_item.description = null;
			}
			frappe.set_route("Form", "Item", new_item.name);
		});

		const stock_exists = frm.doc.__onload && frm.doc.__onload.stock_exists ? 1 : 0;

		["is_stock_item", "has_serial_no", "has_batch_no", "has_variants"].forEach((fieldname) => {
			frm.set_df_property(fieldname, "read_only", stock_exists);
		});

		frm.toggle_reqd("customer", frm.doc.is_customer_provided_item ? 1 : 0);
	},

	validate: function (frm) {
		erpnext.item.weight_to_validate(frm);
	},

	image: function () {
		refresh_field("image_view");
	},

	is_customer_provided_item: function (frm) {
		frm.toggle_reqd("customer", frm.doc.is_customer_provided_item ? 1 : 0);
	},

	is_fixed_asset: function (frm) {
		// set serial no to false & toggles its visibility
		frm.set_value("has_serial_no", 0);
		frm.set_value("has_batch_no", 0);
		frm.toggle_enable(["has_serial_no", "serial_no_series"], !frm.doc.is_fixed_asset);

		frappe.call({
			method: "erpnext.stock.doctype.item.item.get_asset_naming_series",
			callback: function (r) {
				frm.set_value("is_stock_item", frm.doc.is_fixed_asset ? 0 : 1);
				frm.events.set_asset_naming_series(frm, r.message);
			},
		});

		frm.trigger("auto_create_assets");
	},

	set_asset_naming_series: function (frm, asset_naming_series) {
		if ((frm.doc.__onload && frm.doc.__onload.asset_naming_series) || asset_naming_series) {
			let naming_series =
				(frm.doc.__onload && frm.doc.__onload.asset_naming_series) || asset_naming_series;
			frm.set_df_property("asset_naming_series", "options", naming_series);
		}
	},

	auto_create_assets: function (frm) {
		frm.toggle_reqd(["asset_naming_series"], frm.doc.auto_create_assets);
		frm.toggle_display(["asset_naming_series"], frm.doc.auto_create_assets);
	},

	page_name: frappe.utils.warn_page_name_change,

	item_code: function (frm) {
		if (!frm.doc.item_name) frm.set_value("item_name", frm.doc.item_code);
	},

	is_stock_item: function (frm) {
		if (!frm.doc.is_stock_item) {
			frm.set_value("has_batch_no", 0);
			frm.set_value("create_new_batch", 0);
			frm.set_value("has_serial_no", 0);
		}
	},

	has_variants: function (frm) {
		erpnext.item.toggle_attributes(frm);
	},
});

frappe.ui.form.on("Item Reorder", {
	reorder_levels_add: function (frm, cdt, cdn) {
		var row = frappe.get_doc(cdt, cdn);
		var type = frm.doc.default_material_request_type;
		row.material_request_type = type == "Material Transfer" ? "Transfer" : type;
	},
});

frappe.ui.form.on("Item Customer Detail", {
	customer_items_add: function (frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "customer_group", "");
	},
	customer_name: function (frm, cdt, cdn) {
		set_customer_group(frm, cdt, cdn);
	},
	customer_group: function (frm, cdt, cdn) {
		if (set_customer_group(frm, cdt, cdn)) {
			frappe.msgprint(__("Changing Customer Group for the selected Customer is not allowed."));
		}
	},
});

var set_customer_group = function (frm, cdt, cdn) {
	var row = frappe.get_doc(cdt, cdn);

	if (!row.customer_name) {
		return false;
	}

	frappe.model.with_doc("Customer", row.customer_name, function () {
		var customer = frappe.model.get_doc("Customer", row.customer_name);
		row.customer_group = customer.customer_group;
		refresh_field("customer_group", cdn, "customer_items");
	});
	return true;
};

$.extend(erpnext.item, {
	setup_queries: function (frm) {
		frm.fields_dict["item_defaults"].grid.get_field("expense_account").get_query = function (
			doc,
			cdt,
			cdn
		) {
			const row = locals[cdt][cdn];
			return {
				query: "erpnext.controllers.queries.get_expense_account",
				filters: { company: row.company },
			};
		};

		frm.fields_dict["item_defaults"].grid.get_field("income_account").get_query = function (
			doc,
			cdt,
			cdn
		) {
			const row = locals[cdt][cdn];
			return {
				query: "erpnext.controllers.queries.get_income_account",
				filters: { company: row.company },
			};
		};

		frm.fields_dict["item_defaults"].grid.get_field("default_discount_account").get_query = function (
			doc,
			cdt,
			cdn
		) {
			const row = locals[cdt][cdn];
			return {
				filters: {
					report_type: "Profit and Loss",
					company: row.company,
					is_group: 0,
				},
			};
		};

		frm.fields_dict["item_defaults"].grid.get_field("buying_cost_center").get_query = function (
			doc,
			cdt,
			cdn
		) {
			const row = locals[cdt][cdn];
			return {
				filters: {
					is_group: 0,
					company: row.company,
				},
			};
		};

		frm.fields_dict["item_defaults"].grid.get_field("selling_cost_center").get_query = function (
			doc,
			cdt,
			cdn
		) {
			const row = locals[cdt][cdn];
			return {
				filters: {
					is_group: 0,
					company: row.company,
				},
			};
		};

		frm.fields_dict["taxes"].grid.get_field("tax_type").get_query = function (doc, cdt, cdn) {
			return {
				filters: [
					["Account", "account_type", "in", "Tax, Chargeable, Income Account, Expense Account"],
					["Account", "docstatus", "!=", 2],
				],
			};
		};

		frm.fields_dict["item_group"].get_query = function (doc, cdt, cdn) {
			return {
				filters: [["Item Group", "docstatus", "!=", 2]],
			};
		};

		frm.fields_dict["item_defaults"].grid.get_field("deferred_revenue_account").get_query = function (
			doc,
			cdt,
			cdn
		) {
			return {
				filters: {
					company: locals[cdt][cdn].company,
					root_type: "Liability",
					is_group: 0,
				},
			};
		};

		frm.fields_dict["item_defaults"].grid.get_field("deferred_expense_account").get_query = function (
			doc,
			cdt,
			cdn
		) {
			return {
				filters: {
					company: locals[cdt][cdn].company,
					root_type: "Asset",
					is_group: 0,
				},
			};
		};

		frm.fields_dict["item_defaults"].grid.get_field("default_warehouse").get_query = function (
			doc,
			cdt,
			cdn
		) {
			const row = locals[cdt][cdn];
			return {
				filters: {
					is_group: 0,
					company: row.company,
				},
			};
		};

		frm.fields_dict.reorder_levels.grid.get_field("warehouse_group").get_query = function (
			doc,
			cdt,
			cdn
		) {
			return {
				filters: { is_group: 1 },
			};
		};

		frm.fields_dict.reorder_levels.grid.get_field("warehouse").get_query = function (doc, cdt, cdn) {
			var d = locals[cdt][cdn];

			var filters = {
				is_group: 0,
			};

			if (d.parent_warehouse) {
				filters.extend({ parent_warehouse: d.warehouse_group });
			}

			return {
				filters: filters,
			};
		};

		frm.set_query("default_provisional_account", "item_defaults", (doc, cdt, cdn) => {
			let row = locals[cdt][cdn];
			return {
				filters: {
					company: row.company,
					root_type: ["in", ["Liability", "Asset"]],
					is_group: 0,
				},
			};
		});
	},

	make_dashboard: function (frm) {
		if (frm.doc.__islocal) return;

		// Show Stock Levels only if is_stock_item
		if (frm.doc.is_stock_item) {
			frappe.require("item-dashboard.bundle.js", function () {
				const section = frm.dashboard.add_section("", __("Stock Levels"));
				erpnext.item.item_dashboard = new erpnext.stock.ItemDashboard({
					parent: section,
					item_code: frm.doc.name,
					page_length: 20,
					method: "erpnext.stock.dashboard.item_dashboard.get_data",
					template: "item_dashboard_list",
				});
				erpnext.item.item_dashboard.refresh();
			});
		}
	},

	edit_prices_button: function (frm) {
		frm.add_custom_button(
			__("Add / Edit Prices"),
			function () {
				frappe.set_route("List", "Item Price", { item_code: frm.doc.name });
			},
			__("Actions")
		);
	},

	weight_to_validate: function (frm) {
		if (frm.doc.weight_per_unit && !frm.doc.weight_uom) {
			frappe.msgprint({
				message: __("Please mention 'Weight UOM' along with Weight."),
				title: __("Note"),
			});
		}
	},

	show_modal_for_manufacturers: function (frm) {
		var dialog = new frappe.ui.Dialog({
			fields: [
				{
					fieldtype: "Link",
					fieldname: "manufacturer",
					options: "Manufacturer",
					label: "Manufacturer",
					reqd: 1,
				},
				{
					fieldtype: "Data",
					label: "Manufacturer Part Number",
					fieldname: "manufacturer_part_no",
				},
			],
		});

		dialog.set_primary_action(__("Create"), function () {
			var data = dialog.get_values();
			if (!data) return;

			// call the server to make the variant
			data.template = frm.doc.name;
			frappe.call({
				method: "erpnext.controllers.item_variant.get_variant",
				args: data,
				callback: function (r) {
					var doclist = frappe.model.sync(r.message);
					dialog.hide();
					frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
				},
			});
		});

		dialog.show();
	},

	show_multiple_variants_dialog: function (frm) {
		var me = this;

		let promises = [];
		let attr_val_fields = {};

		function make_fields_from_attribute_values(attr_dict) {
			let fields = [];
			Object.keys(attr_dict).forEach((name, i) => {
				if (i % 3 === 0) {
					fields.push({ fieldtype: "Section Break" });
				}
				fields.push({ fieldtype: "Column Break", label: name });
				attr_dict[name].forEach((value) => {
					fields.push({
						fieldtype: "Check",
						label: value,
						fieldname: value,
						default: 0,
						onchange: function () {
							let selected_attributes = get_selected_attributes();
							let lengths = [];
							Object.keys(selected_attributes).map((key) => {
								lengths.push(selected_attributes[key].length);
							});
							if (lengths.includes(0)) {
								me.multiple_variant_dialog.get_primary_btn().html(__("Create Variants"));
								me.multiple_variant_dialog.disable_primary_action();
							} else {
								let no_of_combinations = lengths.reduce((a, b) => a * b, 1);
								let msg;
								if (no_of_combinations === 1) {
									msg = __("Make {0} Variant", [no_of_combinations]);
								} else {
									msg = __("Make {0} Variants", [no_of_combinations]);
								}
								me.multiple_variant_dialog.get_primary_btn().html(msg);
								me.multiple_variant_dialog.enable_primary_action();
							}
						},
					});
				});
			});
			return fields;
		}

		function make_and_show_dialog(fields) {
			me.multiple_variant_dialog = new frappe.ui.Dialog({
				title: __("Select Attribute Values"),
				fields: [
					frm.doc.image
						? {
								fieldtype: "Check",
								label: __("Create a variant with the template image."),
								fieldname: "use_template_image",
								default: 0,
						  }
						: null,
					{
						fieldtype: "HTML",
						fieldname: "help",
						options: `<label class="control-label">
							${__("Select at least one value from each of the attributes.")}
						</label>`,
					},
				]
					.concat(fields)
					.filter(Boolean),
			});

			me.multiple_variant_dialog.set_primary_action(__("Create Variants"), () => {
				let selected_attributes = get_selected_attributes();
				let use_template_image = me.multiple_variant_dialog.get_value("use_template_image");

				me.multiple_variant_dialog.hide();
				frappe.call({
					method: "erpnext.controllers.item_variant.enqueue_multiple_variant_creation",
					args: {
						item: frm.doc.name,
						args: selected_attributes,
						use_template_image: use_template_image,
					},
					callback: function (r) {
						if (r.message === "queued") {
							frappe.show_alert({
								message: __("Variant creation has been queued."),
								indicator: "orange",
							});
						} else {
							frappe.show_alert({
								message: __("{0} variants created.", [r.message]),
								indicator: "green",
							});
						}
					},
				});
			});

			$($(me.multiple_variant_dialog.$wrapper.find(".form-column")).find(".frappe-control")).css(
				"margin-bottom",
				"0px"
			);

			me.multiple_variant_dialog.disable_primary_action();
			me.multiple_variant_dialog.clear();
			me.multiple_variant_dialog.show();
		}

		function get_selected_attributes() {
			let selected_attributes = {};
			me.multiple_variant_dialog.$wrapper.find(".form-column").each((i, col) => {
				if (i === 0) return;
				let attribute_name = $(col).find(".column-label").html().trim();
				selected_attributes[attribute_name] = [];
				let checked_opts = $(col).find(".checkbox input");
				checked_opts.each((i, opt) => {
					if ($(opt).is(":checked")) {
						selected_attributes[attribute_name].push($(opt).attr("data-fieldname"));
					}
				});
			});

			return selected_attributes;
		}

		frm.doc.attributes.forEach(function (d) {
			if (!d.disabled) {
				let p = new Promise((resolve) => {
					if (!d.numeric_values) {
						frappe
							.call({
								method: "frappe.client.get_list",
								args: {
									doctype: "Item Attribute Value",
									filters: [["parent", "=", d.attribute]],
									fields: ["attribute_value"],
									limit_page_length: 0,
									parent: "Item Attribute",
									order_by: "idx",
								},
							})
							.then((r) => {
								if (r.message) {
									attr_val_fields[d.attribute] = r.message.map(function (d) {
										return d.attribute_value;
									});
									resolve();
								}
							});
					} else {
						let values = [];
						for (var i = d.from_range; i <= d.to_range; i = flt(i + d.increment, 6)) {
							values.push(i);
						}
						attr_val_fields[d.attribute] = values;
						resolve();
					}
				});

				promises.push(p);
			}
		}, this);

		Promise.all(promises).then(() => {
			let fields = make_fields_from_attribute_values(attr_val_fields);
			make_and_show_dialog(fields);
		});
	},

	show_single_variant_dialog: function (frm) {
		var fields = [];

		for (var i = 0; i < frm.doc.attributes.length; i++) {
			var fieldtype, desc;
			var row = frm.doc.attributes[i];

			if (!row.disabled) {
				if (row.numeric_values) {
					fieldtype = "Float";
					desc =
						"Min Value: " +
						row.from_range +
						" , Max Value: " +
						row.to_range +
						", in Increments of: " +
						row.increment;
				} else {
					fieldtype = "Data";
					desc = "";
				}
				fields = fields.concat({
					label: row.attribute,
					fieldname: row.attribute,
					fieldtype: fieldtype,
					reqd: 0,
					description: desc,
				});
			}
		}

		if (frm.doc.image) {
			fields.push({
				fieldtype: "Check",
				label: __("Create a variant with the template image."),
				fieldname: "use_template_image",
				default: 0,
			});
		}

		var d = new frappe.ui.Dialog({
			title: __("Create Variant"),
			fields: fields,
		});

		d.set_primary_action(__("Create"), function () {
			var args = d.get_values();
			if (!args) return;
			frappe.call({
				method: "erpnext.controllers.item_variant.get_variant",
				btn: d.get_primary_btn(),
				args: {
					template: frm.doc.name,
					args: d.get_values(),
				},
				callback: function (r) {
					// returns variant item
					if (r.message) {
						var variant = r.message;
						frappe.msgprint_dialog = frappe.msgprint(
							__("Item Variant {0} already exists with same attributes", [
								repl(
									'<a href="/app/item/%(item_encoded)s" class="strong variant-click">%(item)s</a>',
									{
										item_encoded: encodeURIComponent(variant),
										item: variant,
									}
								),
							])
						);
						frappe.msgprint_dialog.hide_on_page_refresh = true;
						frappe.msgprint_dialog.$wrapper.find(".variant-click").on("click", function () {
							d.hide();
						});
					} else {
						d.hide();
						frappe.call({
							method: "erpnext.controllers.item_variant.create_variant",
							args: {
								item: frm.doc.name,
								args: d.get_values(),
								use_template_image: args.use_template_image,
							},
							callback: function (r) {
								var doclist = frappe.model.sync(r.message);
								frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
							},
						});
					}
				},
			});
		});

		d.show();

		$.each(d.fields_dict, function (i, field) {
			if (field.df.fieldtype !== "Data") {
				return;
			}

			$(field.input_area).addClass("ui-front");

			var input = field.$input.get(0);
			input.awesomplete = new Awesomplete(input, {
				minChars: 0,
				maxItems: 99,
				autoFirst: true,
				list: [],
			});
			input.field = field;

			field.$input
				.on("input", function (e) {
					var term = e.target.value;
					frappe.call({
						method: "erpnext.stock.doctype.item.item.get_item_attribute",
						args: {
							parent: i,
							attribute_value: term,
						},
						callback: function (r) {
							if (r.message) {
								e.target.awesomplete.list = r.message.map(function (d) {
									return d.attribute_value;
								});
							}
						},
					});
				})
				.on("focus", function (e) {
					$(e.target).val("").trigger("input");
				})
				.on("awesomplete-open", () => {
					let modal = field.$input.parents(".modal-dialog")[0];
					if (modal) {
						$(modal).removeClass("modal-dialog-scrollable");
					}
				});
		});
	},

	toggle_attributes: function (frm) {
		if ((frm.doc.has_variants || frm.doc.variant_of) && frm.doc.variant_based_on === "Item Attribute") {
			frm.toggle_display("attributes", true);

			var grid = frm.fields_dict.attributes.grid;

			if (frm.doc.variant_of) {
				// variant

				// value column is displayed but not editable
				grid.set_column_disp("attribute_value", true);
				grid.toggle_enable("attribute_value", false);

				grid.toggle_enable("attribute", false);

				// can't change attributes since they are
				// saved when the variant was created
				frm.toggle_enable("attributes", false);
			} else {
				// template - values not required!

				// make the grid editable
				frm.toggle_enable("attributes", true);

				// value column is hidden
				grid.set_column_disp("attribute_value", false);

				// enable the grid so you can add more attributes
				grid.toggle_enable("attribute", true);
			}
		} else {
			// nothing to do with attributes, hide it
			frm.toggle_display("attributes", false);
		}
		frm.layout.refresh_sections();
	},
});

frappe.ui.form.on("UOM Conversion Detail", {
	uom: function (frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		if (row.uom) {
			frappe.call({
				method: "erpnext.stock.doctype.item.item.get_uom_conv_factor",
				args: {
					uom: row.uom,
					stock_uom: frm.doc.stock_uom,
				},
				callback: function (r) {
					if (!r.exc && r.message) {
						frappe.model.set_value(cdt, cdn, "conversion_factor", r.message);
					}
				},
			});
		}
	},
});

frappe.tour["Item"] = [
	{
		fieldname: "item_code",
		title: "Item Code",
		description: __(
			"Enter an Item Code, the name will be auto-filled the same as Item Code on clicking inside the Item Name field."
		),
	},
	{
		fieldname: "item_group",
		title: "Item Group",
		description: __("Select an Item Group."),
	},
	{
		fieldname: "is_stock_item",
		title: "Maintain Stock",
		description: __(
			"If you are maintaining stock of this Item in your Inventory, ERPNext will make a stock ledger entry for each transaction of this item."
		),
	},
	{
		fieldname: "include_item_in_manufacturing",
		title: "Include Item in Manufacturing",
		description: __(
			"This is for raw material Items that'll be used to create finished goods. If the Item is an additional service like 'washing' that'll be used in the BOM, keep this unchecked."
		),
	},
	{
		fieldname: "opening_stock",
		title: "Opening Stock",
		description: __("Enter the opening stock units."),
	},
	{
		fieldname: "valuation_rate",
		title: "Valuation Rate",
		description: __(
			"There are two options to maintain valuation of stock. FIFO (first in - first out) and Moving Average."
		),
	},
	{
		fieldname: "standard_rate",
		title: "Standard Selling Rate",
		description: __(
			"When creating an Item, entering a value for this field will automatically create an Item Price at the backend."
		),
	},
	{
		fieldname: "item_defaults",
		title: "Item Defaults",
		description: __(
			"In this section, you can define Company-wide transaction-related defaults for this Item. Eg. Default Warehouse, Default Price List, Supplier, etc."
		),
	},
];

function open_form(frm, doctype, child_doctype, parentfield) {
	frappe.model.with_doctype(doctype, () => {
		let new_doc = frappe.model.get_new_doc(doctype);

		let new_child_doc = frappe.model.add_child(new_doc, child_doctype, parentfield);
		new_child_doc.item_code = frm.doc.name;
		new_child_doc.item_name = frm.doc.item_name;
		if (in_list(SALES_DOCTYPES, doctype) && frm.doc.sales_uom) {
			new_child_doc.uom = frm.doc.sales_uom;
		} else if (in_list(PURCHASE_DOCTYPES, doctype) && frm.doc.purchase_uom) {
			new_child_doc.uom = frm.doc.purchase_uom;
		} else {
			new_child_doc.uom = frm.doc.stock_uom;
		}
		new_child_doc.description = frm.doc.description;
		if (!new_child_doc.qty) {
			new_child_doc.qty = 1.0;
		}

		frappe.run_serially([
			() => frappe.ui.form.make_quick_entry(doctype, null, null, new_doc),
			() => {
				frappe.flags.ignore_company_party_validation = true;
				frappe.model.trigger("item_code", frm.doc.name, new_child_doc);
			},
		]);
	});
}

frappe.ui.form.on("Item", {
	item_group(frm) {
		// Nhóm hàng chỉ GỢI Ý, và chỉ lúc tạo mới. Server cố ý không tự suy cờ này:
		// trường Check không diễn tả được "chưa khai" khác "cố ý bỏ tích", nên mọi
		// suy đoán phía server đều có nguy cơ ghi đè lựa chọn của người dùng. Hàng
		// tạo qua API/import phải khai cờ tường minh.
		if (!frm.is_new()) return;
		frappe.db.get_value("Item Group", frm.doc.item_group, "la_tbyt").then((r) => {
			frm.set_value("la_thiet_bi_y_te", cint(r.message && r.message.la_tbyt));
		});
	},
});

frappe.ui.form.on("Item", {
	refresh(frm) {
		erpnext_render_tbyt_dossier(frm);
	},
	la_thiet_bi_y_te(frm) {
		erpnext_render_tbyt_dossier(frm);
	},
	so_luu_hanh(frm) {
		erpnext_render_tbyt_dossier(frm);
	},
});

function erpnext_render_tbyt_dossier(frm) {
	const wrapper = frm.get_field("ho_so_tbyt_html");
	if (!wrapper) return;
	if (frm.is_new() || !frm.doc.la_thiet_bi_y_te) {
		wrapper.$wrapper.empty();
		return;
	}

	frappe.call({
		method: "erpnext.tbyt.status.get_item_dashboard",
		args: { item_code: frm.doc.name },
		callback(r) {
			if (!r.message) return;
			wrapper.$wrapper.html(erpnext_tbyt_dossier_html(r.message));
			erpnext_bind_tbyt_dossier_actions(frm, wrapper);
		},
	});
}

function erpnext_tbyt_dossier_html(data) {
	if (!data.rows.length) {
		return `<div class="text-muted">${__("Chưa xác định được bộ chứng từ.")}</div>`;
	}

	const level_label = { BB: "Bắt buộc", "BB*": "BB có điều kiện", NC: "Nên có", TH: "Bổ sung" };
	const body = data.rows
		.map((row) => {
			const expiry = row.khong_thoi_han
				? __("Vô thời hạn")
				: row.ngay_het_han
				? frappe.datetime.str_to_user(row.ngay_het_han)
				: "—";
			const state = row.document
				? `<span class="indicator-pill ${row.trang_thai === "Còn hiệu lực" ? "green" : "red"}">${
						row.trang_thai
				  }</span>`
				: `<span class="indicator-pill ${row.is_required ? "red" : "gray"}">${__("Chưa có")}</span>`;
			const link = row.document
				? `<a href="/app/tbyt-regulatory-document/${encodeURIComponent(
						row.document
				  )}">${frappe.utils.escape_html(row.so_hieu || row.document)}</a>`
				: "";
			// Nút "Nộp giấy" chỉ hiện khi server đã tính can_intake = true (BB, hoặc
			// BB* đang điều kiện thoả) — NC và TH không có nút (§9.2 đặc tả). Gắn qua
			// data-attribute, không onclick nội tuyến: chuỗi này bị vẽ lại toàn bộ mỗi
			// lần refresh nên handler phải là uỷ quyền sự kiện trên phần tử bao.
			const action = row.can_intake
				? `<button type="button" class="btn btn-xs btn-primary" data-tbyt-intake
						data-document-key="${frappe.utils.escape_html(row.document_key)}">
						${__("Nộp giấy")}</button>`
				: "";
			return `<tr>
				<td>${frappe.utils.escape_html(row.document_name)}</td>
				<td>${level_label[row.level] || row.level}</td>
				<td>${row.scope_level}</td>
				<td>${link}</td>
				<td>${expiry}</td>
				<td>${state}</td>
				<td>${action}</td>
			</tr>`;
		})
		.join("");

	return `
		<div class="mb-2"><b>${__("Tình trạng")}:</b> ${data.status || "—"}
			${data.missing ? `· <span class="text-danger">${__("Thiếu")} ${data.missing}</span>` : ""}</div>
		<table class="table table-bordered table-sm">
			<thead><tr>
				<th>${__("Chứng từ")}</th><th>${__("Mức")}</th><th>${__("Cấp lưu")}</th>
				<th>${__("Số hiệu")}</th><th>${__("Hết hạn")}</th><th>${__("Trạng thái")}</th>
				<th>${__("Hành động")}</th>
			</tr></thead>
			<tbody>${body}</tbody>
		</table>`;
}

function erpnext_bind_tbyt_dossier_actions(frm, wrapper) {
	// `.off` trước `.on` mỗi lần vẽ lại để không chồng handler qua các lần refresh —
	// bản thân `wrapper.$wrapper` không bị thay, chỉ nội dung bên trong bị thay.
	wrapper.$wrapper.off("click.tbyt-intake").on("click.tbyt-intake", "[data-tbyt-intake]", function () {
		erpnext_open_tbyt_intake_dialog(frm, $(this).attr("data-document-key"));
	});
}

// Sau khi tạo mới hoặc gắn thành công một chứng từ, TUYỆT ĐỐI không gọi
// frm.reload_doc() — Item có thể đang có sửa đổi chưa lưu và nạp lại sẽ xoá
// mất (§9.1 đặc tả). Chỉ cập nhật tại chỗ đúng hai thứ đã đổi, lấy thẳng từ
// phản hồi của server: việc làm mới trạng thái chạy nền qua
// enqueue_after_commit, nên đọc lại frm.doc lúc này vẫn ra giá trị cũ.
function erpnext_apply_tbyt_intake_result(frm, result) {
	// Gán thẳng, không dùng frm.set_value — set_value sẽ đánh dấu form dirty
	// trong khi người dùng không sửa gì.
	frm.doc.tinh_trang_ho_so = result.tinh_trang_ho_so;
	frm.refresh_field("tinh_trang_ho_so");
	erpnext_render_tbyt_dossier(frm);
}

function erpnext_open_tbyt_intake_dialog(frm, document_key) {
	frappe.call({
		method: "erpnext.tbyt.intake.get_intake_context",
		args: { item_code: frm.doc.name, document_key: document_key },
		callback(r) {
			const ctx = r.message;
			if (!ctx) {
				frappe.msgprint({
					title: __("Không nộp được"),
					indicator: "red",
					message: __("Không xác định được chủ thể để nộp chứng từ này cho mặt hàng."),
				});
				return;
			}
			erpnext_show_tbyt_intake_dialog(frm, document_key, ctx);
		},
	});
}

// Câu `explain` là chỗ người dùng hiểu ra rằng nộp TỪ mặt hàng không phải gắn
// VÀO mặt hàng — dùng nguyên văn, không rút gọn, chỉ in đậm tên chủ thể.
function erpnext_tbyt_intake_explain_html(ctx) {
	const escaped_explain = frappe.utils.escape_html(ctx.explain || "");
	const escaped_label = frappe.utils.escape_html(ctx.scope_label || "");
	const bolded =
		escaped_label && escaped_explain.includes(escaped_label)
			? escaped_explain.replace(escaped_label, `<b>${escaped_label}</b>`)
			: escaped_explain;
	return `<div class="alert alert-info">${bolded}</div>`;
}

function erpnext_show_tbyt_intake_dialog(frm, document_key, ctx) {
	const dialog = new frappe.ui.Dialog({
		title: __("Nộp chứng từ") + ": " + (ctx.document_name || document_key),
		fields: [
			{ fieldname: "explain_html", fieldtype: "HTML", options: erpnext_tbyt_intake_explain_html(ctx) },
			{ fieldname: "so_hieu", fieldtype: "Data", label: __("Số hiệu") },
			{ fieldname: "lookup_html", fieldtype: "HTML" },
			{
				fieldname: "ngay_cap",
				fieldtype: "Date",
				label: __("Ngày cấp"),
				reqd: 1,
				default: frappe.datetime.get_today(),
			},
			{
				fieldname: "khong_thoi_han",
				fieldtype: "Check",
				label: __("Vô thời hạn"),
				default: ctx.mac_dinh_co_thoi_han ? 0 : 1,
			},
			{
				fieldname: "ngay_het_han",
				fieldtype: "Date",
				label: __("Ngày hết hạn"),
				depends_on: "eval:!doc.khong_thoi_han",
				mandatory_depends_on: "eval:!doc.khong_thoi_han",
			},
			{
				fieldname: "file_url",
				fieldtype: "Attach",
				label: __("Tệp đính kèm"),
				reqd: 1,
			},
		],
		primary_action_label: __("Tạo mới"),
		primary_action(values) {
			frappe.call({
				method: "erpnext.tbyt.intake.create_document_for_item",
				args: {
					item_code: frm.doc.name,
					document_key: document_key,
					so_hieu: values.so_hieu,
					ngay_cap: values.ngay_cap,
					khong_thoi_han: values.khong_thoi_han,
					ngay_het_han: values.ngay_het_han,
					file_url: values.file_url,
				},
				freeze: true,
				callback(r) {
					if (!r.message) return;
					erpnext_apply_tbyt_intake_result(frm, r.message);
					dialog.hide();
					frappe.show_alert({ message: __("Đã nộp chứng từ."), indicator: "green" });
				},
			});
		},
		secondary_action_label: __("Mở biểu mẫu đầy đủ"),
		secondary_action() {
			// Ca hiếm cần trường mà hộp thoại không có (ví dụ Thay thế cho khi gia
			// hạn). get_values(true) lấy những gì đã gõ mà KHÔNG bắt buộc phải hợp lệ
			// — người dùng đang chuyển sang form đầy đủ chính vì hộp thoại không đủ.
			const values = dialog.get_values(true) || {};
			dialog.hide();
			// init_callback (tham số thứ ba của frappe.new_doc) là cách ĐÚNG để điền
			// dòng phạm vi — xem tbyt_marketing_authorization.js: route_options chỉ
			// sao chép được các trường khớp tên field thật trên bản ghi (document_type,
			// so_hieu, ...), không có cơ chế nào sao chép bảng con, nên phạm vi phải
			// được thêm bằng frappe.model.add_child bên trong callback này.
			frappe.new_doc(
				"TBYT Regulatory Document",
				{
					document_type: document_key,
					so_hieu: values.so_hieu,
					ngay_cap: values.ngay_cap,
					khong_thoi_han: values.khong_thoi_han,
					ngay_het_han: values.ngay_het_han,
					file: values.file_url,
				},
				(doc) => {
					const row = frappe.model.add_child(doc, "pham_vi");
					row.scope_name = ctx.scope_name;
				}
			);
		},
	});

	erpnext_bind_tbyt_so_hieu_lookup(dialog, frm, document_key);
	dialog.show();
}

// Tra cứu số hiệu lúc gõ (§9.3 đặc tả): chống dội 300ms, bỏ qua chuỗi ngắn hơn
// 3 ký tự — cả hai đều thực hiện lại ở đây dù server cũng đã chặn chuỗi ngắn,
// vì bỏ qua sớm ở client tránh gọi mạng cho mọi phím gõ đầu tiên.
function erpnext_bind_tbyt_so_hieu_lookup(dialog, frm, document_key) {
	const $lookup_wrapper = dialog.get_field("lookup_html").$wrapper;

	const run_lookup = frappe.utils.debounce(() => {
		const so_hieu = (dialog.get_value("so_hieu") || "").trim();
		if (so_hieu.length < 3) {
			$lookup_wrapper.empty();
			return;
		}
		frappe.call({
			method: "erpnext.tbyt.intake.find_documents_by_so_hieu",
			args: { so_hieu: so_hieu, item_code: frm.doc.name, document_key: document_key },
			callback(r) {
				$lookup_wrapper.html(erpnext_tbyt_lookup_html(r.message || []));
			},
		});
	}, 300);

	dialog.get_field("so_hieu").$input.on("input", run_lookup);

	$lookup_wrapper.off("click.tbyt-attach").on("click.tbyt-attach", "[data-tbyt-attach]", function () {
		const document_name = $(this).attr("data-document-name");
		frappe.call({
			method: "erpnext.tbyt.intake.attach_existing_to_item",
			args: { item_code: frm.doc.name, document_name: document_name },
			freeze: true,
			callback(r) {
				if (!r.message) return;
				erpnext_apply_tbyt_intake_result(frm, r.message);
				dialog.hide();
				frappe.show_alert({ message: __("Đã gắn chứng từ cho mặt hàng."), indicator: "green" });
			},
		});
	});
}

function erpnext_tbyt_lookup_html(results) {
	if (!results.length) {
		// Không có kết quả — xoá trống, không hiện gì (§3 brief / §5.3 đặc tả).
		return "";
	}

	const rows = results
		.map((row) => {
			const name = frappe.utils.escape_html(row.name);
			const document_name = frappe.utils.escape_html(row.document_name || row.document_type || "");
			const scope_summary = frappe.utils.escape_html(row.scope_summary || "");
			const trang_thai = frappe.utils.escape_html(row.trang_thai || "");

			let action;
			if (row.already_covers_item) {
				action = `<div class="text-muted">${__("Mặt hàng này đã có sẵn tờ này")}</div>`;
			} else if (row.allows_multi) {
				action = `<button type="button" class="btn btn-xs btn-primary" data-tbyt-attach
						data-document-name="${name}">${__("Gắn tờ này cho mặt hàng")}</button>`;
			} else {
				action = `<div class="text-muted">${__(
					"Loại này chỉ nhận một phạm vi. Nếu đây đúng là cùng một tờ giấy phủ nhiều chủ thể, báo quản trị xem loại chứng từ có cần cho phép nhiều phạm vi không."
				)}</div>`;
			}

			return `<div class="tbyt-intake-lookup-row mb-2">
					<div>${name} · ${document_name} · ${scope_summary} · ${trang_thai}</div>
					${action}
				</div>`;
		})
		.join("");

	return `<div class="mb-2"><b>${__("Số hiệu này đã có trong hệ thống")}</b></div>${rows}`;
}
