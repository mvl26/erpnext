frappe.query_reports["Thong Bao Doi Gia Bao Gap"] = {
	filters: [
		{
			fieldname: "price_list",
			label: __("Bảng giá"),
			fieldtype: "Link",
			options: "Price List",
			get_query: () => ({ filters: { bao_truoc_khi_doi_gia: 1 } }),
		},
		{
			fieldname: "tu_ngay",
			label: __("Gửi từ ngày"),
			fieldtype: "Date",
		},
		{
			fieldname: "den_ngay",
			label: __("Gửi đến ngày"),
			fieldtype: "Date",
		},
		{
			fieldname: "chi_bao_gap",
			label: __("Chỉ dòng báo gấp"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "chua_xac_nhan",
			label: __("Chỉ dòng khách chưa xác nhận"),
			fieldtype: "Check",
		},
	],
};
