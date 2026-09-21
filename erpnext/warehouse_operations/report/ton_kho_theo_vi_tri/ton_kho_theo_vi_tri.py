"""Tồn theo từng ô, xếp theo đường đi lấy hàng, gộp cộng dồn lên từng cấp cha.

Cây `Storage Location` suy ra từ mã (Task 2) và mọi ô LÁ khi lưu đều tự sinh
đủ tổ tiên qua `dam_bao_to_tien()` — nhưng KHÔNG PHẢI mọi bản ghi trên mọi
site đều đi qua đường đó: các ô tạo trước khi có mô hình cây (mã 12 ký tự cũ,
còn mã kho) và ô hệ thống `ZZZ-CHUA-XEP-<kho>` đều KHÔNG có tổ tiên,
`parent_storage_location` để trống — và cho tới khi `cay.py::dam_bao_cay_da_
dung()` hội tụ (chạy lại ở mỗi `bench migrate`, xem docstring của hàm đó),
những bản ghi kiểu này còn mang `lft = rgt = 0`. Dùng `lft between` để cộng
dồn sẽ gộp NHẦM mọi bản ghi 0/0 với nhau — kể cả những bản ghi không hề liên
quan tới nhau (đúng bẫy `_TO_TIEN_TAT` mô tả kỹ ở `fefo.py`) — nên không dùng
toạ độ nested-set ở báo cáo này. Cũng không suy cha từ tiền tố mã
(`ma_o[:2]`, `[:4]`, …) vì các ô cũ 12 ký tự và ô hệ thống không theo chuẩn
10 ký tự của `ma_vi_tri.py`; gọi `cap_do()`/`ma_cha()` trên chúng sẽ
`frappe.throw` giữa một báo cáo chỉ để XEM.

Cách chọn: cộng dồn bằng CHÍNH liên kết `parent_storage_location` đã lưu sẵn
trên `Storage Location` — nguồn này do `StorageLocation.validate()` tính lại
mỗi lần lưu (Task 2), không suy diễn lại ở đây, không gọi hàm nào của
`ma_vi_tri.py`. Ô nào có `parent_storage_location = NULL` (chưa dựng cây,
hoặc ô hệ thống CHUA-XEP) thì đứng nguyên là dòng rời ở gốc cây — trung
thực với dữ liệu hôm nay, không bịa ra một nút cha không có thật. Nhờ vậy
`ZZZ-CHUA-XEP-<kho>` (đứng ngoài cây) vẫn luôn hiện diện trong báo cáo, ngay
cả khi nó đang giữ toàn bộ tồn của kho.

QUAN TRỌNG — `parent_field`/`name_field` khai trong `ton_kho_theo_vi_tri.js`
KHÔNG đủ để hiện dạng cây. Đọc mã nguồn gói `frappe-datatable`
(`datamanager.js`, `rowmanager.js`) cho thấy thư viện suy `isLeaf`/quan hệ
cha-con HOÀN TOÀN từ (a) trường số `indent` trên MỖI dòng và (b) THỨ TỰ CÁC
DÒNG TRONG MẢNG trả về (dòng cha phải đứng ngay trước cụm con của nó) —
không hề đọc `parent_field`/`name_field` để tự dựng cây (hai khoá đó chỉ
được `frappe/desk/query_report.py::add_total_row` dùng cho việc khác). Và
`frappe/public/js/.../query_report.js` chỉ coi báo cáo là cây
(`this.tree_report = this.data.some(d => "indent" in d)`) khi có ít nhất một
dòng mang khoá `indent`. Vì vậy, ngoài việc trả `parent_o`, hàm này còn phải
tự XẾP LẠI mảng kết quả theo thứ tự cha-trước-con và gắn `indent` cho từng
dòng — xem `_dung_cay()`.

Trả về dạng DICT cho mỗi dòng (không còn list vị trí) để mang thêm các cột
phụ `parent_o`/`is_group`/`indent`.
"""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}
	dieu_kien = ["lb.so_luong != 0"]
	tham_so = {}

	if filters.get("kho"):
		dieu_kien.append("lb.kho = %(kho)s")
		tham_so["kho"] = filters["kho"]
	if filters.get("vat_tu"):
		dieu_kien.append("lb.vat_tu = %(vat_tu)s")
		tham_so["vat_tu"] = filters["vat_tu"]

	dong_la = frappe.db.sql(
		f"""
		select lb.o as o, sl.ten_o as ten_o, lb.kho as kho, lb.vat_tu as vat_tu,
		       lb.so_lo as so_lo, b.expiry_date as expiry_date, lb.so_luong as so_luong,
		       sl.parent_storage_location as parent_o
		from `tabLocation Balance` lb
		join `tabStorage Location` sl on sl.name = lb.o
		left join `tabBatch` b on b.name = lb.so_lo
		where {' and '.join(dieu_kien)}
		order by ifnull(sl.thu_tu_lay_hang, 0) asc, lb.o asc, lb.vat_tu asc
		""",
		tham_so,
		as_dict=True,
	)
	for d in dong_la:
		d["is_group"] = 0

	dong_nhom = _gop_theo_cap(dong_la)
	return _cot(), _dung_cay(dong_la, dong_nhom)


def _gop_theo_cap(dong_la: list[dict]) -> dict[str, dict]:
	"""Cộng dồn `so_luong` lên từng nút cha, leo bằng `parent_storage_location`.

	Trả `{ten_nut: dòng}` cho mỗi nút cha có tổng khác 0, kèm `parent_o` của
	CHÍNH nút đó để leo tiếp lên các cấp trên. Không gọi `cap_do()` hay
	`ma_cha()` — chỉ đọc lại đúng trường đã lưu, xem docstring module.
	"""
	tong: dict[str, float] = {}
	da_biet: dict[str, dict] = {}

	bien_gioi = {d["parent_o"] for d in dong_la if d.get("parent_o")}
	while bien_gioi:
		can_tra = [ten for ten in bien_gioi if ten not in da_biet]
		if can_tra:
			for hang in frappe.get_all(
				"Storage Location",
				filters={"name": ["in", can_tra]},
				fields=["name", "ten_o", "kho", "parent_storage_location"],
			):
				da_biet[hang.name] = hang
		bien_gioi = {
			da_biet[ten]["parent_storage_location"]
			for ten in bien_gioi
			if ten in da_biet and da_biet[ten]["parent_storage_location"]
		}

	# ĐI ĐÚNG CHUỖI parent_o của TỪNG lá — không cộng vào mọi nút đã biết
	# (đột biến đã đo: cộng nhầm vào mọi nút trong `da_biet` vẫn giữ đúng
	# tổng ở nút GỐC chung của mọi nhánh, nhưng sai ở các nút CON — xem
	# task-6-report.md).
	for d in dong_la:
		cha = d.get("parent_o")
		so_luong = flt(d["so_luong"])
		while cha:
			tong[cha] = tong.get(cha, 0) + so_luong
			hang = da_biet.get(cha)
			cha = hang["parent_storage_location"] if hang else None

	dong_nhom = {}
	for ten, so_luong in tong.items():
		if not so_luong:
			continue
		hang = da_biet.get(ten, {})
		dong_nhom[ten] = {
			"o": ten,
			"ten_o": hang.get("ten_o") or ten,
			"kho": hang.get("kho"),
			"vat_tu": None,
			"so_lo": None,
			"expiry_date": None,
			"so_luong": so_luong,
			"parent_o": hang.get("parent_storage_location"),
			"is_group": 1,
		}
	return dong_nhom


def _dung_cay(dong_la: list[dict], dong_nhom: dict[str, dict]) -> list[dict]:
	"""Xếp lá + nhóm thành MỘT danh sách PHẲNG, cha luôn đứng trước cụm con
	của nó, và gắn `indent` — đúng thứ `frappe-datatable` đọc (xem docstring
	module). Mỗi nút (lá hoặc nhóm) chỉ được đưa vào cây MỘT LẦN dù nhiều lá
	cùng chung một nhánh tổ tiên.
	"""
	con_cua: dict[str, list[dict]] = {}
	da_dua_vao_cay: set[str] = set()
	goc: list[dict] = []

	def dua_nut_nhom_vao_cay(ten: str) -> None:
		if ten in da_dua_vao_cay or ten not in dong_nhom:
			return
		da_dua_vao_cay.add(ten)
		nut = dong_nhom[ten]
		cha = nut.get("parent_o")
		if cha and cha in dong_nhom:
			dua_nut_nhom_vao_cay(cha)
			con_cua.setdefault(cha, []).append(nut)
		else:
			goc.append(nut)

	for d in dong_la:
		cha = d.get("parent_o")
		if cha and cha in dong_nhom:
			dua_nut_nhom_vao_cay(cha)
			con_cua.setdefault(cha, []).append(d)
		else:
			goc.append(d)

	ket_qua: list[dict] = []

	def phang_hoa(nut: dict, do_sau: int) -> None:
		nut["indent"] = do_sau
		ket_qua.append(nut)
		for con in con_cua.get(nut["o"], []):
			phang_hoa(con, do_sau + 1)

	for nut in goc:
		phang_hoa(nut, 0)

	return ket_qua


def _cot():
	return [
		{"label": _("Ô"), "fieldname": "o", "fieldtype": "Link", "options": "Storage Location", "width": 160},
		{"label": _("Tên ô"), "fieldname": "ten_o", "fieldtype": "Data", "width": 160},
		{"label": _("Kho"), "fieldname": "kho", "fieldtype": "Link", "options": "Warehouse", "width": 160},
		{"label": _("Mặt hàng"), "fieldname": "vat_tu", "fieldtype": "Link", "options": "Item", "width": 220},
		{"label": _("Số lô"), "fieldname": "so_lo", "fieldtype": "Link", "options": "Batch", "width": 170},
		{"label": _("Hạn dùng"), "fieldname": "expiry_date", "fieldtype": "Date", "width": 110},
		{"label": _("Số lượng"), "fieldname": "so_luong", "fieldtype": "Float", "width": 110},
		{
			"label": _("Ô cha"),
			"fieldname": "parent_o",
			"fieldtype": "Link",
			"options": "Storage Location",
			"width": 160,
			"hidden": 1,
		},
	]
