"""Tiến trình LUỒNG NHẬP KHO của một phiếu nhập: khai lô → duyệt → xếp lên kệ.

Chủ đầu tư 23/09/2026: "có sự liên kết luồng … sau khi submit purchase receipt
thì có xếp hàng lên kệ nữa" — trước file này, mỗi bước là một màn hình rời, và
giữa hai bước thủ kho phải TỰ ĐI TÌM chứng từ trên thanh tìm kiếm. Hàm này trả
đúng một câu trả lời cho câu hỏi "phiếu này đang đứng ở đâu trong luồng, bước
tiếp theo là gì", để form phiếu nhập vẽ thanh tiến trình và bật đúng nút.

MỘT nguồn cho phần khai lô: gọi lại `phieu_nhap.chan_doan_phieu_nhap` chứ không
đếm lại dòng ở đây. Hai bản đếm là một ngày nào đó thanh tiến trình bảo "đã khai
đủ" trong khi nút Duyệt vẫn từ chối vì phép chặn đọc bản đếm kia (đúng lớp lỗi
mà docstring `phieu_nhap.py` dựng `_lo_qua_phieu_nhap_lo` để tránh).

CON SỐ "CÒN CHƯA XẾP" ĐO CÁI GÌ: tồn đang nằm ở ô "Chưa xếp vị trí" của những
(kho, mặt hàng, lô) CÓ TRÊN PHIẾU NÀY. Ô chưa xếp là ô DÙNG CHUNG cho cả kho,
nên nếu cùng một lô còn hàng của phiếu nhập khác thì con số này tính chung —
không có cách nào tách ra, vì sổ vị trí ghi theo (ô, mặt hàng, lô) chứ không
theo chứng từ đã đưa hàng vào ô. Câu chữ trên màn hình vì thế nói "hàng của
phiếu này đang chờ xếp", không hứa một con số riêng của phiếu.
"""

import frappe
from frappe.utils import flt

from erpnext.warehouse_operations.vitri.kho import kho_co_quan_ly_vi_tri
from erpnext.warehouse_operations.vitri.phieu_nhap import chan_doan_phieu_nhap


def _dong_phieu(phieu_nhap: str) -> list[dict]:
	return frappe.get_all(
		"Purchase Receipt Item",
		filters={"parent": phieu_nhap},
		fields=["item_code", "batch_no", "warehouse"],
		order_by="idx asc",
	)


def _chua_xep(kho_ds: list[str], cap: set[tuple]) -> list[dict]:
	"""Các dòng tồn ở ô "Chưa xếp vị trí" khớp (kho, mặt hàng, lô) của phiếu.

	Cùng điều kiện `la_o_chua_xep = 1` với `xep.hang_chua_xep` — nút "Xếp hàng
	lên kệ" mở đúng bộ dòng mà hàm kia sẽ đổ ra, nên hai chỗ phải hỏi cùng một
	câu; lệch nhau là thanh tiến trình nói "còn hàng chờ xếp" rồi phiếu xếp mở
	ra trống trơn.
	"""
	if not kho_ds:
		return []
	dong = frappe.db.sql(
		"""
		select lb.kho as kho, lb.vat_tu as vat_tu, lb.so_lo as so_lo, lb.so_luong as so_luong
		from `tabLocation Balance` lb
		join `tabStorage Location` sl on sl.name = lb.o
		where sl.la_o_chua_xep = 1 and lb.so_luong != 0 and lb.kho in %(kho)s
		order by lb.kho asc, lb.vat_tu asc, lb.so_lo asc
		""",
		{"kho": kho_ds},
		as_dict=True,
	)
	return [
		{"kho": d.kho, "vat_tu": d.vat_tu, "so_lo": d.so_lo or None, "so_luong": flt(d.so_luong)}
		for d in dong
		if (d.kho, d.vat_tu, d.so_lo or "") in cap
	]


@frappe.whitelist()
def tien_do_nhap_kho(phieu_nhap: str) -> dict:
	"""Phiếu nhập `phieu_nhap` đang ở bước nào của luồng nhập kho.

	`trang_thai`:
	- `khong_ap_dung`: không dòng nào thuộc kho quản lý vị trí — luồng này không
	  nói gì về phiếu đó;
	- `da_huy`: phiếu đã huỷ;
	- `can_khai_lo`: còn dòng quản lý lô chưa khai lô (bấm "Nhập lô & in nhãn");
	- `khai_du_cho_duyet`: khai đủ rồi, chờ Submit để ghi kho;
	- `cho_xep`: đã duyệt, hàng của phiếu còn ở ô "Chưa xếp vị trí";
	- `da_xep`: đã duyệt và không còn gì ở ô chưa xếp.
	"""
	cd = chan_doan_phieu_nhap(phieu_nhap)  # cũng là chỗ kiểm quyền đọc phiếu
	dong = _dong_phieu(phieu_nhap)
	kho_ds = sorted({d.warehouse for d in dong if d.warehouse and kho_co_quan_ly_vi_tri(d.warehouse)})
	cap = {(d.warehouse, d.item_code, d.batch_no or "") for d in dong if d.warehouse in kho_ds}

	docstatus = cd["docstatus"]
	chua_xep = _chua_xep(kho_ds, cap) if docstatus == 1 else []
	theo_kho: dict[str, float] = {}
	for d in chua_xep:
		theo_kho[d["kho"]] = theo_kho.get(d["kho"], 0.0) + d["so_luong"]

	if not kho_ds:
		trang_thai = "khong_ap_dung"
	elif docstatus == 2:
		trang_thai = "da_huy"
	elif docstatus == 0:
		trang_thai = "can_khai_lo" if cd["dong_can_khai"] else "khai_du_cho_duyet"
	else:
		trang_thai = "cho_xep" if chua_xep else "da_xep"

	return {
		"phieu": phieu_nhap,
		"docstatus": docstatus,
		"trang_thai": trang_thai,
		"kho_quan_ly": kho_ds,
		"dong_can_khai": cd["dong_can_khai"],
		"dong_go_tay": cd["dong_go_tay"],
		"phieu_nhap_lo": cd["phieu_nhap_lo"],
		"phieu_nhap_lo_nhap": cd["phieu_nhap_lo_nhap"],
		"chua_xep": chua_xep,
		"chua_xep_theo_kho": theo_kho,
		"tong_chua_xep": flt(sum(theo_kho.values())),
	}


@frappe.whitelist()
def phieu_nhap_lo_cua_lo(so_lo: str) -> list[str]:
	"""Các phiếu nhập lô ĐÃ DUYỆT đã khai ra lô `so_lo`, mới nhất trước.

	Đường đi ngược của luồng nhập, cho nút "Xem phiếu nhập lô" trên form lô. Phải
	là một hàm máy chủ chứ không phải một lời gọi `get_list` từ trình duyệt: link
	nằm ở BẢNG CON (`Batch Entry Item.lo_da_tao`), và đọc thẳng bảng con qua API
	danh sách đòi người dùng có quyền đọc bảng con đó — thứ không ai cấp cho thủ
	kho. Ở đây kiểm quyền trên chính cái họ đang mở: bản ghi `Batch`.
	"""
	frappe.has_permission("Batch", "read", so_lo, throw=True)
	phieu = frappe.get_all("Batch Entry Item", filters={"lo_da_tao": so_lo}, pluck="parent")
	if not phieu:
		return []
	return frappe.get_all(
		"Batch Entry",
		filters={"docstatus": 1, "name": ("in", sorted(set(phieu)))},
		pluck="name",
		order_by="modified desc",
	)
