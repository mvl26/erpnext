"""Hiển thị số lô NCC thay cho mã lô (spec `2026-10-19-so-lo-tach-khoi-ma-lo-design.md`).

Mã lô (tên bản ghi `Batch`, `L26-000123`) là khoá: mọi bảng nối bằng nó, mã vạch
in nó, JS gửi nó ngược lên máy chủ. Số lô (`custom_so_lo`) là chữ in trên bao bì
NCC — được trùng giữa các mặt hàng — và là thứ người đọc nhận ra. Vì vậy payload
GIỮ khoá `so_lo` mang mã lô, chỉ THÊM `so_lo_hien_thi` cho lớp vẽ.

Lô không tìm thấy hoặc chưa có số lô thì rơi về chính mã: màn hình không bao giờ
hiện ô trống thay cho một lô có thật.
"""

import functools
from collections.abc import Iterable

import frappe


def so_lo_cua(ma_lo: str | None) -> str:
	"""Số lô của một lô; rỗng hoặc lô không tồn tại thì trả lại chính mã."""
	if not ma_lo:
		return ""
	return frappe.db.get_value("Batch", ma_lo, "custom_so_lo") or ma_lo


def so_lo_theo_ma(ds_ma: Iterable[str | None]) -> dict[str, str]:
	"""{mã lô: số lô} cho cả danh sách bằng MỘT truy vấn — dùng cho bảng báo cáo,
	nơi gọi `so_lo_cua` từng dòng sẽ thành N truy vấn."""
	ma = {m for m in ds_ma if m}
	if not ma:
		return {}
	co = dict(
		frappe.get_all(
			"Batch",
			filters={"name": ("in", sorted(ma))},
			fields=["name", "custom_so_lo"],
			as_list=True,
		)
	)
	return {m: co.get(m) or m for m in ma}


def gan_so_lo_hien_thi(dong: list[dict], khoa: str = "so_lo") -> list[dict]:
	"""Thêm `so_lo_hien_thi` cho từng dict theo mã lô ở `khoa`; sửa tại chỗ."""
	bang = so_lo_theo_ma(d.get(khoa) for d in dong)
	for d in dong:
		ma = d.get(khoa)
		d["so_lo_hien_thi"] = bang.get(ma, ma or "")
	return dong


def tim_lo(ma_go: str | None) -> list[dict]:
	"""Mọi lô mà người dùng có thể đang gõ tay: TÊN lô trùng (tem cũ, mã vạch
	mờ) HOẶC số lô trùng (đọc trên bao bì). Một chuỗi có thể khớp cả hai ở hai
	mặt hàng khác nhau (E3) — trả hết để người dùng chọn, không đoán."""
	ma_go = (ma_go or "").strip()
	if not ma_go:
		return []
	truong = ["name", "custom_so_lo", "item", "item_name", "expiry_date"]
	ten = frappe.get_all("Batch", filters={"name": ma_go}, fields=truong)
	so = frappe.get_all("Batch", filters={"custom_so_lo": ma_go}, fields=truong)
	gap = {lo.name: lo for lo in ten + so}
	ds = sorted(gap.values(), key=lambda lo: (lo.item or "", str(lo.expiry_date or ""), lo.name))
	return [
		{
			"ma_lo": lo.name,
			"so_lo_hien_thi": lo.custom_so_lo or lo.name,
			"vat_tu": lo.item,
			"ten_hang": lo.item_name,
			"hsd": lo.expiry_date,
		}
		for lo in ds
	]


# Khoá mang mã lô trong payload các màn kho -> khoá hiển thị đi kèm. `so_lo` theo
# quy ước chung; hai khoá kia là của màn lấy hàng (`lay_hang.py`).
_KHOA_HIEN_THI = {
	"so_lo": "so_lo_hien_thi",
	"lo_nen_lay": "lo_nen_lay_hien_thi",
	"so_lo_dang_chot": "so_lo_dang_chot_hien_thi",
}


def gan_hien_thi_toan_bo(kq):
	"""Đi khắp payload (dict/list lồng nhau) của một endpoint màn kho: dict nào có
	khoá mã lô ở `_KHOA_HIEN_THI` thì THÊM khoá hiển thị tương ứng. Sửa tại chỗ,
	trả lại `kq`; một truy vấn cho cả payload.

	Gọi ở chỗ `return` của endpoint thay vì sửa từng chỗ dựng dict: payload lấy
	hàng có mã lô ở nhiều độ sâu (dòng hàng, `lo_khac`, `cho`…), sót một chỗ là
	màn đó hiện mã thay số lô mà không bài nào biết.
	"""
	gap: list[dict] = []

	def di(x):
		if isinstance(x, dict):
			if any(k in x for k in _KHOA_HIEN_THI):
				gap.append(x)
			for v in x.values():
				di(v)
		elif isinstance(x, list | tuple):
			for v in x:
				di(v)

	di(kq)
	bang = so_lo_theo_ma(d.get(k) for d in gap for k in _KHOA_HIEN_THI)
	for d in gap:
		for k, k_ht in _KHOA_HIEN_THI.items():
			if k in d:
				ma = d[k]
				d[k_ht] = bang.get(ma, ma or "") if ma else ma
	return kq


def kem_so_lo_hien_thi(ham):
	"""Decorator cho endpoint màn kho: chạy `gan_hien_thi_toan_bo` trên kết quả.
	Đặt DƯỚI `@frappe.whitelist()` để whitelist nhận bản đã bọc."""

	@functools.wraps(ham)
	def boc(*args, **kwargs):
		return gan_hien_thi_toan_bo(ham(*args, **kwargs))

	return boc
