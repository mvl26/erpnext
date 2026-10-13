frappe.treeview_settings["Item Group"] = {
	ignore_fields: ["parent_item_group"],
	fields: [
		{ fieldtype: "Data", fieldname: "item_group_name", label: __("Item Group Name"), reqd: 1 },
		{
			fieldtype: "Data",
			fieldname: "item_group_code",
			label: __("Mã nhóm (Item Group Code)"),
			description: __("Dùng để sinh mã vật tư. Chữ không dấu và số, tối đa 3 ký tự."),
			// Bắt buộc khi đang sinh mã vật tư theo quy tắc, giống form Nhóm hàng.
			reqd: frappe.defaults.get_default("item_naming_by") === "Quy tắc mã vật tư" ? 1 : 0,
		},
		{
			fieldtype: "Check",
			fieldname: "is_group",
			label: __("Is Group"),
			description: __("Further sub-groups can only be created under records marked as 'Group'"),
		},
	],
};
