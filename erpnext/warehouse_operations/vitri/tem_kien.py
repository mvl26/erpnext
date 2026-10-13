"""Tem KIỆN cho hàng đã lấy theo phiếu giao (chủ đầu tư 22/09/2026).

Lời chủ đầu tư: "nút in tem để khi tạo phiếu delivery note phải dán tem cho từng mặt
hàng ngoài đời thực"; chốt: MỖI KIỆN MỘT TEM, có số phiếu giao và tên khách; chưa in
đủ tem thì không duyệt được phiếu (`lay_hang.chan_duyet_chua_lay`).

Kiện sinh từ bảng phân bổ (`Location Allocation`): mỗi lượt lấy có `so_kien`, mỗi
kiện mang `so_luong_lay / so_kien` theo `don_vi_lay` (5 Hộp → 5 kiện × 1 Hộp; 300
Cái chia 3 kiện → 3 × 100 Cái). `so_kien_da_in` đếm số kiện ĐẦU của lượt đó đã in.

BỐ CỤC: dùng LẠI nguyên tem lô 50×30 (`tem_lo.js`, các ô F1…F11) — không dựng lưới
thứ hai. Bố cục đó đã đo từng milimét, chặn mã vạch quá dài, xử lý cửa sổ in nhiệt;
một bản thứ hai là hai chỗ phải giữ đúng. Ánh xạ:

    F1  mã hàng              F2  tên hàng
    F3  số lượng trong kiện  F4  "Phiếu <số> · Kiện i/N"
    F5  HSD                  F6  lô
    F7  tên khách            F8  (trống)
    F9  "i/N" — ô chữ to nhất tem, người đóng gói đọc từ xa
    F10 mã vạch = số lô      F11 số lô (gõ tay khi máy quét hỏng)

Mã vạch mang SỐ LÔ (không phải mã kiện): quét tem kiện ở bất kỳ màn hình nào của
module ra đúng lô, như quét tem lô.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

from erpnext.warehouse_operations.vitri.lay_hang import TEN_BANG_PHAN_BO, _kiem_tra_quyen
from erpnext.warehouse_operations.vitri.nhap_lo import _dinh_dang_ngay


def _so(x) -> str:
	"""Số gọn: 100.0 → "100", 2.5 → "2.5"."""
	return f"{flt(x, 3):g}"


def _phan_bo(doc) -> list:
	return list(doc.get(TEN_BANG_PHAN_BO) or [])


def dem_kien(doc) -> tuple[int, int]:
	"""(số kiện đã in tem, tổng số kiện) của phiếu `doc`."""
	tong = da_in = 0
	for p in _phan_bo(doc):
		n = max(1, cint(p.get("so_kien")) or 1)
		tong += n
		da_in += min(n, cint(p.get("so_kien_da_in")))
	return da_in, tong


@frappe.whitelist()
def du_lieu_tem_kien(phieu: str, chi_chua_in: int = 1) -> list[dict]:
	"""Dữ liệu tem cho từng kiện của phiếu giao `phieu`, theo thứ tự lượt lấy.

	`kien_thu`/`tong_kien` đánh số theo (mặt hàng, lô) trên TOÀN phiếu — hai lượt
	cùng lô (hai ô khác nhau) nối tiếp nhau 1…N, không mỗi lượt tự đếm lại từ 1.
	`chi_chua_in=1` bỏ các kiện đã in (`so_kien_da_in`).
	"""
	_kiem_tra_quyen()
	doc = frappe.get_doc("Delivery Note", phieu)
	doc.check_permission("read")
	khach = doc.customer_name or doc.customer

	nhom: dict[tuple, int] = {}
	for p in _phan_bo(doc):
		khoa = (p.vat_tu, p.so_lo or "")
		nhom[khoa] = nhom.get(khoa, 0) + max(1, cint(p.get("so_kien")) or 1)

	dem: dict[tuple, int] = {}
	tem = []
	for p in _phan_bo(doc):
		khoa = (p.vat_tu, p.so_lo or "")
		n = max(1, cint(p.get("so_kien")) or 1)
		da_in = cint(p.get("so_kien_da_in"))
		don_vi = p.get("don_vi_lay") or frappe.get_cached_value("Item", p.vat_tu, "stock_uom")
		sl_lay = flt(p.get("so_luong_lay")) or flt(p.so_luong)
		mot_kien = f"{_so(sl_lay / n)} {don_vi}"
		ten_hang = frappe.get_cached_value("Item", p.vat_tu, "item_name")
		hsd = frappe.db.get_value("Batch", p.so_lo, "expiry_date") if p.so_lo else None
		for k in range(n):
			dem[khoa] = dem.get(khoa, 0) + 1
			if cint(chi_chua_in) and k < da_in:
				continue
			i, tong = dem[khoa], nhom[khoa]
			tem.append(
				{
					"dong_phan_bo": p.name,
					"ma_hang": p.vat_tu,
					"ten_hang": ten_hang,
					"so_lo": p.so_lo,
					"hsd": _dinh_dang_ngay(hsd) if hsd else "",
					"so_luong_kien": mot_kien,
					"so_phieu": doc.name,
					"khach": khach,
					"kien_thu": i,
					"tong_kien": tong,
					"ma_vach": p.so_lo or p.vat_tu,
					# Các ô của bố cục tem lô (`tem_lo.js`) — xem docstring module.
					"F1": p.vat_tu,
					"F2": ten_hang,
					"F3": mot_kien,
					"F4": _("Phiếu {0} · Kiện {1}/{2}").format(doc.name, i, tong),
					"F5": f"HSD {_dinh_dang_ngay(hsd)}" if hsd else "",
					"F6": f"Lô {p.so_lo}" if p.so_lo else "",
					"F7": khach or "",
					"F8": "",
					"F9": f"{i}/{tong}",
					"F10": p.so_lo or p.vat_tu,
					"F11": p.so_lo or p.vat_tu,
				}
			)
	return tem


@frappe.whitelist()
def danh_dau_da_in(phieu: str, dong_phan_bo: str | list | None = None) -> dict:
	"""Đánh dấu mọi kiện (hoặc kiện của các dòng `dong_phan_bo`) là ĐÃ IN tem.

	Gọi sau khi cửa sổ in đã mở. Ghi thẳng từng dòng phân bổ (`db.set_value`),
	KHÔNG `save()` phiếu: in tem xảy ra lúc thủ kho khác có thể đang quét cùng
	phiếu, lưu cả phiếu là đổi `modified` và làm lượt quét của họ báo xung đột.
	Chạy được cả trên phiếu đã duyệt (in lại tem) — trường `allow_on_submit`.
	"""
	_kiem_tra_quyen()
	doc = frappe.get_doc("Delivery Note", phieu)
	doc.check_permission("read")
	if isinstance(dong_phan_bo, str) and dong_phan_bo.startswith("["):
		dong_phan_bo = frappe.parse_json(dong_phan_bo)
	chon = {dong_phan_bo} if isinstance(dong_phan_bo, str) else set(dong_phan_bo or [])
	for p in _phan_bo(doc):
		if chon and p.name not in chon:
			continue
		n = max(1, cint(p.get("so_kien")) or 1)
		if cint(p.get("so_kien_da_in")) != n:
			frappe.db.set_value("Location Allocation", p.name, "so_kien_da_in", n, update_modified=False)
			p.so_kien_da_in = n
	da_in, tong = dem_kien(doc)
	return {"so_kien_da_in": da_in, "tong_kien": tong}
