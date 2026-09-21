frappe.query_reports["Doi Soat Ton Vi Tri"] = {
	filters: [
		{
			fieldname: "kho",
			label: "Kho",
			fieldtype: "Link",
			options: "Warehouse",
			reqd: 1,
			get_query: () => ({ filters: { custom_quan_ly_vi_tri: 1 } }),
		},
	],
};
