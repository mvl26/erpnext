"""Đối soát tồn vị trí ↔ tồn kho — lưới an toàn của toàn hệ.

Với MỘT kho đã chọn: báo cáo rỗng nghĩa là KHỚP. Có dòng nghĩa là sổ vị trí
đã lệch khỏi sổ kho ERPNext và phải xử lý trước khi tin bất kỳ con số nào
khác.

VÒNG SỬA 1 (review điều phối, I4): `reqd: 1` trên filter `kho` chỉ chặn ở
UI (`doi_soat_ton_vi_tri.js`), KHÔNG chặn khi gọi thẳng qua
`frappe.desk.query_report.run` hay `bench execute` — chính đường đã dùng để
nghiệm thu Task 10. Thiếu kho phải `frappe.throw`, không được lặng lẽ trả
`[]` — `[]` khi thiếu filter và `[]` khi thật sự khớp là hai tình huống
khác nhau, gộp làm một sẽ khiến "chưa chọn kho" trông giống "đã đối soát và
khớp".

CRITICAL 1b (review điều phối, sau khi 147/147 bài "xong"): `doi_soat_kho`
giờ trả thêm hai phép đo (`o_am`, `lech_bo_dem`) — báo cáo này phải HIỆN
được cả ba loại lệch, không chỉ `dong_lech`, nếu không màn hình vận hành
(nơi thủ kho thật sự nhìn) vẫn mù trước đúng lớp lỗi mà Critical 1 vừa lộ
ra dù hàm lõi đã bắt được. Ba loại lệch có HÌNH DẠNG cột khác nhau
(`dong_lech`: vật tư/lô/tồn vị trí/tồn kho/lệch; `o_am`: ô/vật tư/lô/số
lượng âm; `lech_bo_dem`: ô/vật tư/lô/bộ đệm/sổ/lệch) nên gộp vào MỘT bảng
bằng cột `loai` phân biệt, các cột không áp dụng để trống — giữ báo cáo một
bảng duy nhất thay vì ba báo cáo riêng (đắt hơn, và người vận hành phải mở
ba tab để thấy hết vấn đề của một kho).
"""

import frappe
from frappe import _

from erpnext.vi_tri_kho.vitri.doi_soat import doi_soat_kho


def execute(filters=None):
	filters = filters or {}
	kho = filters.get("kho")
	if not kho:
		frappe.throw(_("Chọn kho để đối soát."))

	kq = doi_soat_kho(kho)
	dong = []
	for d in kq["dong_lech"]:
		dong.append([_("Lệch tồn"), None, d["vat_tu"], d["so_lo"], d["ton_vi_tri"], d["ton_kho"], d["lech"]])
	for d in kq["o_am"]:
		dong.append([_("Ô âm"), d["o"], d["vat_tu"], d["so_lo"], d["so_luong"], None, None])
	for d in kq["lech_bo_dem"]:
		dong.append([_("Lệch bộ đệm"), d["o"], d["vat_tu"], d["so_lo"], d["bo_dem"], d["so_sach"], d["lech"]])

	return _cot(), dong


def _cot():
	return [
		{"label": _("Loại lệch"), "fieldname": "loai", "fieldtype": "Data", "width": 110},
		{"label": _("Ô"), "fieldname": "o", "fieldtype": "Link", "options": "Storage Location", "width": 150},
		{"label": _("Mặt hàng"), "fieldname": "vat_tu", "fieldtype": "Link", "options": "Item", "width": 220},
		{"label": _("Số lô"), "fieldname": "so_lo", "fieldtype": "Link", "options": "Batch", "width": 150},
		{
			"label": _("Tồn vị trí / Số lượng / Bộ đệm"),
			"fieldname": "gia_tri_1",
			"fieldtype": "Float",
			"width": 160,
		},
		{"label": _("Tồn kho ERPNext / Sổ"), "fieldname": "gia_tri_2", "fieldtype": "Float", "width": 150},
		{"label": _("Lệch"), "fieldname": "lech", "fieldtype": "Float", "width": 100},
	]
