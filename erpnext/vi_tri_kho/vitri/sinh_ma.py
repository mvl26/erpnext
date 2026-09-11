"""Sinh mã ô hàng loạt theo chuẩn 12 ký tự SPD.

Định dạng do BA chốt (`SPD_VanHanh_PhanTichMaViTriKho_20260907_v2` §5.2) nên
bộ sinh KHÔNG nhận "mẫu mã tự do" như bản trước. Để người dùng tự chế mẫu là
mở đường lệch chuẩn — mà mã ô khoá cứng sau khi tạo và đã in lên tem dán kệ,
nên sửa sau là thứ §5.3 cảnh báo riêng.

Hai ký tự đầu (mã kho) lấy từ `Warehouse.custom_ma_kho_spd`, KHÔNG gõ tay ở
đây: mã đó phải giống nhau cho mọi ô của cùng một kho, để người dùng nhập lại
mỗi lần sinh là mời gọi hai lô ô cùng kho mang hai mã khác nhau.
"""

import frappe
from frappe import _

from erpnext.vi_tri_kho.vitri.bat_kho import _kiem_tra_quyen
from erpnext.vi_tri_kho.vitri.ma_vi_tri import MAU_MA, VI_DU, phan_tich_ma

# §5.2: Dãy 01–99 · Khoang 01–99 · Tầng 01–09 · Ô 01–99.
GIOI_HAN = {"so_day": 99, "so_khoang_moi_day": 99, "so_tang_moi_khoang": 9, "so_o_moi_tang": 99}


def _ma_kho_cua(kho: str) -> str:
	ma = (frappe.db.get_value("Warehouse", kho, "custom_ma_kho_spd") or "").strip().upper()
	if not ma:
		frappe.throw(
			_("Kho {0} chưa khai mã kho SPD. Mở phiếu kho đó và điền ô "
			  "\"Mã kho SPD (2 ký tự)\" — ví dụ K1 cho kho trung tâm, B1–B9 cho kho "
			  "vệ tinh trong bệnh viện.").format(kho)
		)
	return ma


def _so_nguyen(ten: str, gia_tri) -> int:
	try:
		n = int(gia_tri)
	except (TypeError, ValueError):
		frappe.throw(_("{0} phải là số nguyên. Đã nhận: {1}").format(ten, gia_tri))
	toi_da = GIOI_HAN[ten]
	if not 1 <= n <= toi_da:
		frappe.throw(
			_("{0} phải nằm trong khoảng 1–{1}. Đã nhận: {2}.").format(ten, toi_da, n)
		)
	return n


def _liet_ke(kho, khu, so_day, so_khoang_moi_day, so_tang_moi_khoang, so_o_moi_tang):
	"""Trả (danh sách mã, tóm tắt). KHÔNG kiểm quyền — chỗ gọi tự kiểm."""
	ma_kho = _ma_kho_cua(kho)
	khu = (khu or "").strip().upper()

	so_day = _so_nguyen("so_day", so_day)
	so_khoang_moi_day = _so_nguyen("so_khoang_moi_day", so_khoang_moi_day)
	so_tang_moi_khoang = _so_nguyen("so_tang_moi_khoang", so_tang_moi_khoang)
	so_o_moi_tang = _so_nguyen("so_o_moi_tang", so_o_moi_tang)

	ma = [
		f"{ma_kho}{khu}{d:02d}{k:02d}{t:02d}{o:02d}"
		for d in range(1, so_day + 1)
		for k in range(1, so_khoang_moi_day + 1)
		for t in range(1, so_tang_moi_khoang + 1)
		for o in range(1, so_o_moi_tang + 1)
	]

	# Tự soi mã đầu tiên bằng chính bộ phân tích dùng ở `Storage Location`:
	# bắt sai mã kho / sai khu NGAY ở bước xem trước, thay vì để 500 lệnh
	# insert lần lượt vỡ giữa chừng.
	phan_tich_ma(ma[0])

	da_co = set(frappe.get_all("Storage Location", filters={"name": ("in", ma)}, pluck="name"))
	return ma, {
		"kho": kho, "so_o": len(ma), "ma_mau": ma[:20], "trung": sorted(da_co),
	}


@frappe.whitelist()
def xem_truoc_sinh(kho, khu, so_day, so_khoang_moi_day, so_tang_moi_khoang, so_o_moi_tang) -> dict:
	"""Liệt kê mã sẽ sinh và mã đã trùng. KHÔNG ghi gì."""
	_kiem_tra_quyen("xem trước sinh", "mã ô")
	_, kq = _liet_ke(kho, khu, so_day, so_khoang_moi_day, so_tang_moi_khoang, so_o_moi_tang)
	return kq


@frappe.whitelist()
def sinh(kho, khu, so_day, so_khoang_moi_day, so_tang_moi_khoang, so_o_moi_tang) -> dict:
	"""Tạo các ô. Có BẤT KỲ mã trùng nào thì KHÔNG ghi ô nào cả.

	Kiểm hết rồi mới ghi — không phải ghi rồi vỡ giữa chừng, vì "sinh 40 ô rồi
	vỡ ở ô 41" để lại kho nửa vời mà không ai biết ô nào đã có (§5.3).
	"""
	_kiem_tra_quyen("sinh", "mã ô")
	ma, kq = _liet_ke(kho, khu, so_day, so_khoang_moi_day, so_tang_moi_khoang, so_o_moi_tang)

	if kq["trung"]:
		frappe.throw(
			_("{0} mã ô đã tồn tại nên không sinh ô nào cả. Ví dụ: {1}. "
			  "Đổi khu hoặc kích thước rồi thử lại.")
			.format(len(kq["trung"]), ", ".join(kq["trung"][:5]))
		)

	for i, m in enumerate(ma, start=1):
		frappe.get_doc({
			"doctype": "Storage Location", "ma_o": m, "kho": kho, "thu_tu_lay_hang": i,
		}).insert(ignore_permissions=True)

	return {"kho": kho, "so_o_da_tao": len(ma)}
