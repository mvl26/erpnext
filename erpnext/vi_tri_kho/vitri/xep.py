"""Lấy danh sách hàng đang nằm ở ô "Chưa xếp vị trí" để đổ vào phiếu xếp.

CÙNG NGUỒN DỮ LIỆU với báo cáo *Hàng chưa xếp vị trí*
(`report/hang_chua_xep_vi_tri/`) — cùng điều kiện `la_o_chua_xep = 1` và
`so_luong != 0`. Hai chỗ mà nói khác nhau thì thủ kho nhìn báo cáo rồi mở
phiếu, thấy lệch, và mất tin vào cả hai.
"""

import frappe
from frappe import _

from erpnext.vi_tri_kho.vitri.goi_y import goi_y_o

# Giống `tem.py`: thủ kho phải tự làm được, đây là việc hằng ngày chứ không
# phải thao tác thiết lập. Khác `bat_kho.py` (sinh ô, bật kho) vốn chỉ mở
# cho quản lý.
VAI_TRO_DUOC_XEP = {"System Manager", "Stock Manager", "Stock User"}


def _kiem_tra_quyen():
	"""`@frappe.whitelist()` một mình chỉ chặn khách vãng lai.

	Danh sách này lộ ra toàn bộ hàng tồn đang chờ xếp của kho, nên đăng nhập
	hợp lệ không phải điều kiện đủ. `Website User` (khách hàng cổng) không có
	vai trò nào ở đây nên bị chặn.
	"""
	if not VAI_TRO_DUOC_XEP & set(frappe.get_roles()):
		frappe.throw(_("Bạn không có quyền xem hàng chưa xếp vị trí."), frappe.PermissionError)


@frappe.whitelist()
def hang_chua_xep(kho: str) -> list[dict]:
	"""Các dòng tồn ở ô "Chưa xếp vị trí" của `kho`, dạng dòng phiếu sẵn.

	`den_o` được ĐIỀN SẴN từ `goi_y.goi_y_o()` kể từ 15/09/2026. Trước đó nó cố
	ý để trống, vì căn cứ duy nhất khi ấy là `suc_chua` (= 0 trên cả 214 ô) và
	gợi ý sai thì thủ kho tin theo rồi xếp nhầm. Căn cứ nay khác hẳn: mặt hàng
	có vị trí cố định, nên "xếp đâu" trả lời được mà không cần sức chứa.

	Mặt hàng CHƯA gán vẫn để `den_o` trống — không đoán. `ly_do_goi_y` luôn có
	giá trị để màn hình nói được vì sao trống.

	Gợi ý KHÔNG chặn và KHÔNG ghi đè: thủ kho đứng trước kệ biết những thứ hệ
	không biết.
	"""
	_kiem_tra_quyen()
	dong = frappe.db.sql(
		"""
		select lb.vat_tu as vat_tu, nullif(lb.so_lo, '') as so_lo,
		       lb.o as tu_o, lb.so_luong as so_luong
		from `tabLocation Balance` lb
		join `tabStorage Location` sl on sl.name = lb.o
		where sl.la_o_chua_xep = 1 and lb.kho = %(kho)s and lb.so_luong != 0
		order by lb.vat_tu asc, lb.so_lo asc
		""",
		{"kho": kho},
		as_dict=True,
	)

	# Một lời gọi `goi_y_o` cho mỗi MẶT HÀNG, không phải mỗi dòng: một mặt hàng
	# nhiều lô cho ra nhiều dòng nhưng cùng một gợi ý.
	bo_nho: dict[str, tuple] = {}
	for d in dong:
		if d.vat_tu not in bo_nho:
			bo_nho[d.vat_tu] = goi_y_o(d.vat_tu, kho)
		d["den_o"], d["ly_do_goi_y"] = bo_nho[d.vat_tu]
	return dong
