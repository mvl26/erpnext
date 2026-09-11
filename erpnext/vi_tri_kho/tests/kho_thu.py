"""Kho THỬ riêng cho các bài mutate toàn bộ trạng thái chuyển đổi của một kho.

Vì sao phải có, ghi lại kẻo ai đó "dọn gọn" bằng cách trỏ về `Kho Miyano - MYN`:

`test_bat_kho._don_sach()` xoá THẲNG BẰNG SQL toàn bộ sổ vị trí, tồn vị trí, ô
hệ thống và hồ sơ chuyển đổi của một kho, rồi tắt cờ quản lý vị trí. Trước
10/09/2026 việc đó gần như vô hại: `Kho Miyano - MYN` chưa bật nên không có gì
để xoá. Từ khi chủ dự án bật kho thật (103 dòng sổ), mỗi lần chạy suite là một
lần xoá sạch rồi dựng lại — nằm trong transaction nên chạy trót lọt thì rollback
trả lại nguyên vẹn (đã đo).

Rủi ro không nằm ở lần chạy trót lọt mà ở lần chạy BỊ GIẾT GIỮA CHỪNG. Bench này
có tiền lệ: ba bench chung một máy, hết RAM là `ReadTimeout` giết ngang; và dự án
đã một lần phải dọn "trạng thái site còn sót từ lần chạy vỡ" (103 dòng
`Location Ledger Entry`, một `Warehouse Location Setup` treo ở "Đã tắt"). Nếu lần
đó xảy ra bây giờ, thứ bị mất là dữ liệu chuyển đổi thật của chủ dự án.

Kho thử cắt hẳn lớp rủi ro đó: các bài vẫn xoá và dựng lại thoả thích, chỉ là
trên kho của riêng chúng.
"""

import frappe

TEN_KHO_THU = "_Test Kho Chuyen Doi - MYN"

ITEM_KHONG_LO = "_Test KhoThu Khong Lo"
ITEM_CO_LO = "_Test KhoThu Co Lo"


def _tao_kho():
	if not frappe.db.exists("Warehouse", TEN_KHO_THU):
		frappe.get_doc(
			{
				"doctype": "Warehouse",
				"warehouse_name": "_Test Kho Chuyen Doi",
				"company": "Miyano Việt Nam",
				"is_group": 0,
			}
		).insert(ignore_permissions=True)
	return TEN_KHO_THU


def _nhap(item, qty):
	se = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"company": "Miyano Việt Nam",
			"items": [{"item_code": item, "qty": qty, "t_warehouse": TEN_KHO_THU, "basic_rate": 1000}],
		}
	)
	se.insert(ignore_permissions=True)
	se.submit()
	return se


def dam_bao_kho_thu() -> str:
	"""Dựng kho thử CÓ TỒN, gồm cả hàng có lô lẫn hàng không lô. Trả tên kho.

	Phải có CẢ HAI loại: `test_ghi_mot_dong_cho_moi_lo` khẳng định có ít nhất
	một dòng mang `so_lo` thật (nếu không, cả kho rơi vào ngăn không-lô và bài
	đó xanh mà không kiểm được chiều lô), còn cảnh báo "hàng không quản lý lô"
	chỉ nổ khi có hàng không lô.

	Gọi lại nhiều lần được: `FrappeTestCase` rollback theo LỚP nên mỗi lớp phải
	tự dựng lại phần của mình.
	"""
	from erpnext.vi_tri_kho.tests.test_hook_nhap import _tao_item

	_tao_kho()
	for item, co_lo in ((ITEM_KHONG_LO, 0), (ITEM_CO_LO, 1)):
		_tao_item(item, co_lo=co_lo)
		ton = frappe.db.get_value("Bin", {"item_code": item, "warehouse": TEN_KHO_THU}, "actual_qty")
		if not ton:
			_nhap(item, 20)
	return TEN_KHO_THU
