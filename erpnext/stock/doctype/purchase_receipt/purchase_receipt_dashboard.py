from frappe import _


def get_data():
	return {
		"fieldname": "purchase_receipt_no",
		"non_standard_fieldnames": {
			"Purchase Invoice": "purchase_receipt",
			"Asset": "purchase_receipt",
			"Landed Cost Voucher": "receipt_document",
			"Auto Repeat": "reference_document",
			"Purchase Receipt": "return_against",
			"Stock Reservation Entry": "from_voucher_no",
			"Quality Inspection": "reference_name",
			# Vị trí kho (Miyano): phiếu nhập lô trỏ về bằng `phieu_nhap`; sổ vị trí
			# trỏ về bằng Dynamic Link (`chung_tu_type` + `chung_tu`).
			"Batch Entry": "phieu_nhap",
			"Location Ledger Entry": "chung_tu",
		},
		"dynamic_links": {"chung_tu": ["Purchase Receipt", "chung_tu_type"]},
		"internal_links": {
			"Material Request": ["items", "material_request"],
			"Purchase Order": ["items", "purchase_order"],
			"Project": ["items", "project"],
		},
		"transactions": [
			{
				"label": _("Related"),
				"items": ["Purchase Invoice", "Landed Cost Voucher", "Asset", "Stock Reservation Entry"],
			},
			{
				"label": _("Reference"),
				"items": ["Material Request", "Purchase Order", "Quality Inspection", "Project"],
			},
			{"label": _("Returns"), "items": ["Purchase Receipt"]},
			{"label": _("Subscription"), "items": ["Auto Repeat"]},
			{"label": _("Vị trí kho"), "items": ["Batch Entry", "Location Ledger Entry"]},
		],
	}
