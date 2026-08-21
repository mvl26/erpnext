// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

frappe.query_reports["Tinh Trang Ho So TBYT"] = {
	filters: [
		{
			fieldname: "phan_loai",
			label: __("Phân loại"),
			fieldtype: "Select",
			options: "\nA\nB\nC\nD",
		},
		{
			fieldname: "chu_so_huu",
			label: __("Chủ sở hữu"),
			fieldtype: "Link",
			options: "Manufacturer",
		},
		{
			fieldname: "item_group",
			label: __("Nhóm hàng"),
			fieldtype: "Link",
			options: "Item Group",
		},
		{
			fieldname: "chi_hien_thieu",
			label: __("Chỉ hiện hồ sơ chưa đủ"),
			fieldtype: "Check",
			default: 1,
		},
	],
};
