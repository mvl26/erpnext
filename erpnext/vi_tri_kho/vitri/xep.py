"""Lấy danh sách hàng đang nằm ở ô "Chưa xếp vị trí" để đổ vào phiếu xếp.

CÙNG NGUỒN DỮ LIỆU với báo cáo *Hàng chưa xếp vị trí*
(`report/hang_chua_xep_vi_tri/`) — cùng điều kiện `la_o_chua_xep = 1` và
`so_luong != 0`. Hai chỗ mà nói khác nhau thì thủ kho nhìn báo cáo rồi mở
phiếu, thấy lệch, và mất tin vào cả hai.
"""

import frappe
from frappe import _

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

	`den_o` KHÔNG được điền — không có căn cứ nào để gợi ý (trường `suc_chua`
	hiện = 0 trên cả 214 ô), mà gợi ý sai thì thủ kho tin theo rồi xếp nhầm.
	"""
	_kiem_tra_quyen()
	return frappe.db.sql(
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
