from frappe import _


def get_data():
	return {
		"fieldname": "batch_no",
		# Sổ vị trí (Miyano) gọi tên lô là `so_lo`. Phiếu nhập lô KHÔNG lên được tab
		# này: nó giữ số lô ở bảng con, mà Connections chỉ tìm trường Link trên chính
		# doctype đích — form lô có nút "Xem phiếu nhập lô" thay cho việc đó
		# (`public/js/warehouse_operations/batch.js`).
		"non_standard_fieldnames": {"Location Ledger Entry": "so_lo"},
		"transactions": [
			{"label": _("Vị trí kho"), "items": ["Location Ledger Entry"]},
			{"label": _("Buy"), "items": ["Purchase Invoice", "Purchase Receipt"]},
			{"label": _("Sell"), "items": ["Sales Invoice", "Delivery Note"]},
			{"label": _("Move"), "items": ["Serial and Batch Bundle"]},
			{"label": _("Quality"), "items": ["Quality Inspection"]},
		],
	}
