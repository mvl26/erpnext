frappe.query_reports["Ton Kho Theo Vi Tri"] = {
	filters: [
		{ fieldname: "kho", label: "Kho", fieldtype: "Link", options: "Warehouse" },
		{ fieldname: "vat_tu", label: "Mặt hàng", fieldtype: "Link", options: "Item" },
	],
};
