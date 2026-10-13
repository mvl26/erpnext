# Connections của phiếu nhập lô (chủ đầu tư 23/09/2026: "tạo những connection cho
# các doctype và luồng mới").
#
# TẤT CẢ đều là `internal_links`: không doctype nào mang trường Link trỏ NGƯỢC về
# `Batch Entry` — phiếu nhập lô ghi kết quả của nó lên `Purchase Receipt Item.
# batch_no` và sinh `Batch`, chứ không ai trỏ về nó. `internal_links` đọc link từ
# chính phiếu đang mở: chuỗi = trường ở phiếu cha, [bảng con, trường] = trường ở
# dòng con (`frappe/desk/notifications.py: get_internal_links`).

from frappe import _


def get_data():
	return {
		"fieldname": "phieu_nhap",
		"internal_links": {
			"Purchase Receipt": "phieu_nhap",
			"Batch": ["items", "lo_da_tao"],
		},
		"transactions": [
			{"label": _("Nhập kho"), "items": ["Purchase Receipt"]},
			{"label": _("Lô đã tạo"), "items": ["Batch"]},
		],
	}
