# Connections của phiếu xếp / chuyển vị trí: các dòng sổ vị trí do chính nó ghi.
#
# Sổ vị trí trỏ về chứng từ bằng Dynamic Link (`chung_tu_type` + `chung_tu`) —
# cùng khuôn đã dùng ở `delivery_note_dashboard.py`.

from frappe import _


def get_data():
	return {
		"fieldname": "chung_tu",
		"non_standard_fieldnames": {"Location Ledger Entry": "chung_tu"},
		"dynamic_links": {"chung_tu": ["Location Transfer", "chung_tu_type"]},
		"transactions": [
			{"label": _("Vị trí kho"), "items": ["Location Ledger Entry"]},
		],
	}
