"""Tra cứu ngược: quét một mã bất kỳ, trả lại TOÀN BỘ thông tin đã khai cho lô đó.

CHIỀU NGƯỢC của Task 7/9 (`nhap_lo.du_lieu_tem`, `nhap_lo.dat_o_in_tem`): ở đó,
thủ kho GÕ số lô của NCC rồi hệ IN nhãn 50×30 — mã vạch trên nhãn MÃ HOÁ chính
số lô đó. Ở đây, thủ kho QUÉT LẠI đúng mã vạch trên nhãn đã dán (hoặc quét mã
vật tư, hoặc quét mã kho) và hệ phải trả lại đúng những gì đã khai — yêu cầu
trực tiếp của chủ đầu tư: "quét mã thì ra toàn bộ thông tin đã nhập".

BỌC NGOÀI `erpnext.stock.utils.scan_barcode`, TUYỆT ĐỐI KHÔNG sửa nó (nằm
trong danh sách cấm của kế hoạch). Hàm đó đã phân giải sẵn:

	Item Barcode -> Serial No -> Batch -> Warehouse

Việc của module này chỉ là ĐỌC THÊM phần dữ liệu riêng của Miyano (vị trí cố
định, tồn theo ô, số gói, ngày nhập...) rồi gắn nhãn `loai` để màn hình biết
hiển thị khối nào — KHÔNG dò chữ trong bất kỳ chuỗi hiển thị nào để suy loại,
vì mọi chuỗi đi qua `_()` nên dịch được (bài học đã trả giá ở `goi_y.py`: một
bản JS từng suy trạng thái bằng `includes("tem")` và gộp nhầm hai case khác
nhau). Khoá `loai` (`"lo"` / `"vat_tu"` / `"kho"` / `"o"` / `None`) là giao thức giữa
hai tầng — bên gọi không phải đoán bằng cách xem khoá nào có mặt.

Quét NHẦM là chuyện thường ngày (mã trên vỏ thùng carton, tem vận chuyển, bất
cứ thứ gì có vạch) — `tra_cuu` không bao giờ được ném lỗi ra giữa màn hình
nhập liệu; mọi nhánh không nhận diện được đều trả `{"loai": None}`, không nổ.
"""

import frappe
from frappe import _

from erpnext.stock.utils import scan_barcode
from erpnext.warehouse_operations.vitri.nhat_ky_loi import cat_tieu_de

# Cùng bộ vai trò với `xep.py`/`nhap_lo.py` (không import chéo — mỗi file
# `vitri/*.py` tự giữ một bản hằng số vai trò, đúng tiền lệ đã chọn ở hai file
# đó, để không cột chặt các module vốn độc lập vào nhau vì một hằng số ba phần
# tử). `tra_cuu` lộ tồn kho theo Ô của BẤT KỲ lô nào quét trúng, không phải
# thao tác thiết lập chỉ dành cho quản lý (khác `bat_kho.py`).
VAI_TRO_DUOC_TRA_CUU = {"System Manager", "Stock Manager", "Stock User"}


def _kiem_tra_quyen():
	"""`@frappe.whitelist()` một mình chỉ chặn khách vãng lai — xem `xep.py`.

	`tra_cuu` lộ tồn kho theo Ô của bất kỳ lô nào quét trúng, nên đăng nhập
	hợp lệ không phải điều kiện đủ. `Website User` (khách hàng cổng
	`miyano_portal`) không có vai trò nào ở đây nên bị chặn.
	"""
	if not VAI_TRO_DUOC_TRA_CUU & set(frappe.get_roles()):
		frappe.throw(_("Bạn không có quyền tra cứu theo mã vạch."), frappe.PermissionError)


def _vi_tri_co_dinh(vat_tu: str) -> str | None:
	"""Vị trí cố định gán cho `vat_tu`, hoặc `None` nếu chưa gán.

	KHÔNG lọc thêm theo `kho` (khác truy vấn trong `goi_y.goi_y_o`, vốn có
	`and p.kho = %(kho)s`): `Item Location Preference` đặt tên bản ghi bằng
	CHÍNH `vat_tu` (`autoname: field:vat_tu`, trường `vat_tu` còn đánh dấu
	`set_only_once`) nên `name` là PRIMARY KEY của bảng — một mặt hàng CHỈ CÓ
	THỂ có ĐÚNG MỘT dòng gán trong toàn hệ, không phải một dòng cho mỗi kho.
	Hai dòng cùng `vat_tu` khác `kho` là bất khả thi (trùng `name`, Frappe tự
	chặn khi insert). Vì vậy tra theo tên là đủ — không có "vị trí gán cho kho
	khác" nào để lọc nhầm vào, và filter thêm `kho` ở đây sẽ chỉ là hàng thừa.
	"""
	return frappe.db.get_value("Item Location Preference", vat_tu, "vi_tri")


def _ton_theo_o(so_lo: str) -> list[dict]:
	"""Các dòng `Location Balance` còn tồn (`so_luong != 0`) của `so_lo`.

	Sắp theo TÊN Ô (không phải thứ tự cây `lft`): đây là danh sách ĐỌC nhanh
	cho thủ kho đứng trước màn hình quét, không phải gợi ý xếp hàng (khác
	`goi_y.goi_y_o`) — không cần join `Storage Location` chỉ để sắp đúng cây.
	"""
	return frappe.db.sql(
		"""
		select o, kho, so_luong
		from `tabLocation Balance`
		where so_lo = %(so_lo)s and so_luong != 0
		order by o asc
		""",
		{"so_lo": so_lo},
		as_dict=True,
	)


def _so_phieu_nhap_va_ngay_nhap(lo) -> tuple[str | None, object]:
	"""Suy số phiếu nhập + ngày nhập từ chứng từ đã sinh ra lô (§6.5, cùng lẽ
	với `nhap_lo._ngay_nhap_cua_lo` — viết lại ở đây thay vì import hàm riêng
	`_` của module đó, vì nó không phải giao diện công khai giữa hai file).

	Lô KHÔNG sinh từ phiếu nhập (ví dụ tạo tay qua hộp thoại lô sẵn có của
	ERPNext) thì cả hai đều `None` — không suy diễn một ngày/số phiếu không có
	căn cứ.
	"""
	if lo.reference_doctype != "Purchase Receipt" or not lo.reference_name:
		return None, None
	ngay_nhap = frappe.db.get_value("Purchase Receipt", lo.reference_name, "posting_date")
	return lo.reference_name, ngay_nhap


def _tra_cuu_lo(so_lo: str) -> dict:
	"""Toàn bộ thông tin đã khai cho một lô — 11 khoá theo đúng brief Task 10."""
	lo = frappe.get_doc("Batch", so_lo)
	so_phieu_nhap, ngay_nhap = _so_phieu_nhap_va_ngay_nhap(lo)
	ton = _ton_theo_o(so_lo)

	return {
		"loai": "lo",
		"so_lo": lo.name,
		"vat_tu": lo.item,
		"ten_hang": lo.item_name,
		"don_vi": frappe.db.get_value("Item", lo.item, "stock_uom"),
		"hsd": lo.expiry_date,
		"ngay_san_xuat": lo.manufacturing_date,
		"nha_cung_cap": lo.supplier,
		"so_goi": lo.custom_so_goi,
		"ngay_nhap": ngay_nhap,
		"so_phieu_nhap": so_phieu_nhap,
		"vi_tri_co_dinh": _vi_tri_co_dinh(lo.item),
		"o_dang_co_hang": [d.o for d in ton],
		"o_in_tem": lo.custom_o_in_tem,
		"ton_theo_o": ton,
	}


def _tra_cuu_vat_tu(vat_tu: str) -> dict:
	"""Mặt hàng + vị trí cố định + các lô CÒN TỒN theo ô, hạn gần nhất trước.

	Khoá tồn tên là `lo_con_ton`, CỐ Ý không phải `ton_theo_o`: `ton_theo_o` là
	khoá của nhánh LÔ, và bài `test_quet_ma_vat_tu_thi_tra_ve_mat_hang_khong_gia_vo_la_lo`
	khoá rằng nhánh vật tư không mang khoá nào của nhánh lô. Hai hình dạng khác
	nhau (dòng ở đây có thêm `so_lo`, `hsd`) thì hai tên khác nhau.

	Sắp theo HSD tăng dần (lô không hạn xuống cuối), rồi theo ô: thủ kho cầm
	PDA đi lấy hàng thì lô sắp hết hạn phải nằm trên cùng — cùng thứ tự FEFO
	mà hệ tự chọn khi xuất.
	"""
	item = frappe.db.get_value(
		"Item", vat_tu, ["name", "item_name", "stock_uom", "has_batch_no"], as_dict=True
	)
	gan = frappe.db.get_value("Item Location Preference", vat_tu, ["kho", "vi_tri"], as_dict=True)
	lo_con_ton = frappe.db.sql(
		"""
		select lb.so_lo as so_lo, b.expiry_date as hsd, lb.o as o, lb.kho as kho, lb.so_luong as so_luong
		from `tabLocation Balance` lb
		left join `tabBatch` b on b.name = lb.so_lo
		where lb.vat_tu = %(vat_tu)s and lb.so_luong != 0
		order by b.expiry_date is null, b.expiry_date asc, lb.so_lo asc, lb.o asc
		""",
		{"vat_tu": vat_tu},
		as_dict=True,
	)
	return {
		"loai": "vat_tu",
		"vat_tu": item.name,
		"ten_hang": item.item_name,
		"don_vi": item.stock_uom,
		"co_lo": bool(item.has_batch_no),
		"vi_tri_co_dinh": gan.vi_tri if gan else None,
		"kho_co_dinh": gan.kho if gan else None,
		"lo_con_ton": lo_con_ton,
	}


def _tra_cuu_kho(kho: str) -> dict:
	"""Tóm tắt một kho: có quản lý vị trí không, bao nhiêu ô, bao nhiêu ô đang có hàng.

	Đếm Ô LÁ (`is_group = 0`) đang dùng — tem dán trên kệ là tem ô lá; đếm cả
	nút Khu/Dãy vào thì con số không khớp thứ thủ kho nhìn thấy ngoài kho.
	"""
	wh = frappe.db.get_value(
		"Warehouse", kho, ["name", "warehouse_name", "custom_quan_ly_vi_tri"], as_dict=True
	)
	so_o = frappe.db.count("Storage Location", {"kho": kho, "is_group": 0, "disabled": 0})
	so_o_co_hang = frappe.db.sql(
		"select count(distinct o) from `tabLocation Balance` where kho = %s and so_luong != 0", kho
	)[0][0]
	return {
		"loai": "kho",
		"kho": wh.name,
		"ten_kho": wh.warehouse_name,
		"quan_ly_vi_tri": bool(wh.custom_quan_ly_vi_tri),
		"so_o": so_o,
		"so_o_co_hang": so_o_co_hang,
	}


# Nút nhóm (Khu/Dãy) có thể chứa hàng trăm ô. PDA không cuộn nổi chừng đó, và
# người quét tem cấp tầng muốn biết "tầng này đang có gì", không phải bản kê
# toàn kho — đủ dài để thấy, kèm tổng số dòng thật để biết là còn nữa.
TRAN_DONG_HANG_TRONG_O = 50


def _tim_o(ma: str) -> str | None:
	"""Mã ô từ chuỗi quét: đúng `name`, đúng `barcode`, hoặc đúng mã in trên nhãn.

	`barcode` mặc định bằng `ma_o` (`StorageLocation.validate`) nhưng sửa được;
	`ma_in_nhan` (`1A0101-0101`) là chuỗi người ta GÕ TAY khi tem mờ không quét
	được — cả hai đều là cách hợp lệ để chỉ tới một ô.
	"""
	if frappe.db.exists("Storage Location", ma):
		return ma
	return frappe.db.get_value("Storage Location", {"barcode": ma}) or frappe.db.get_value(
		"Storage Location", {"ma_in_nhan": ma}
	)


def _tra_cuu_o(ma_o: str) -> dict:
	"""Một ô (hoặc một nút nhóm): nó là gì, mặt hàng nào giữ nó, đang chứa gì.

	Hàng trong ô tính theo CẢ NHÁNH `[lft, rgt]` — với ô lá thì nhánh chỉ có
	chính nó, với tem cấp tầng thì là mọi ô con.

	Mặt hàng cố định là gán nằm ở CHÍNH nút này hoặc một TỔ TIÊN của nó — KHÔNG
	dùng `gan.chu_cua_nhanh` (điều kiện GIAO nhánh, bắt cả con cháu). Hai câu hỏi
	khác nhau: phép chặn khi gán hỏi "nhánh này có đụng ai không", còn người
	quét tem hỏi "chỗ này của mặt hàng nào". Quét tem cả một Dãy chứa năm mặt
	hàng mà bảo "mặt hàng cố định: <mặt hàng đầu tiên tìm thấy>" là nói sai —
	đã thấy tận mắt trên dữ liệu erptest khi kiểm trang PDA.
	"""
	o = frappe.db.get_value(
		"Storage Location",
		ma_o,
		["name", "ma_in_nhan", "ten_o", "kho", "is_group", "disabled", "loai_vi_tri", "lft", "rgt"],
		as_dict=True,
	)
	ket_qua = {
		"loai": "o",
		"ma_o": o.name,
		"ma_in_nhan": o.ma_in_nhan,
		"ten_o": o.ten_o,
		"kho": o.kho,
		"la_nhom": bool(o.is_group),
		"ngung_dung": bool(o.disabled),
		"loai_vi_tri": o.loai_vi_tri,
		"mat_hang_co_dinh": None,
		"hang_trong_o": [],
		"so_dong_hang": 0,
	}
	# `lft`/`rgt` rỗng: cùng bẫy `between 0 and 0` đã ghi ở `goi_y.py` — khớp
	# mọi bản ghi 0/0 toàn hệ. Trả ô không kèm hàng, không đoán.
	if not o.lft or not o.rgt:
		return ket_qua

	chu = frappe.db.sql(
		"""
		select p.vat_tu as vat_tu, p.vi_tri as vi_tri
		from `tabItem Location Preference` p
		join `tabStorage Location` s on s.name = p.vi_tri
		where s.lft <= %(lft)s and s.rgt >= %(rgt)s
		order by s.lft desc
		limit 1
		""",
		{"lft": o.lft, "rgt": o.rgt},
		as_dict=True,
	)
	chu = chu[0] if chu else None
	if chu:
		ket_qua["mat_hang_co_dinh"] = {
			"vat_tu": chu.vat_tu,
			"ten_hang": frappe.db.get_value("Item", chu.vat_tu, "item_name"),
			"vi_tri": chu.vi_tri,
		}

	tham_so = {"lft": o.lft, "rgt": o.rgt, "kho": o.kho}
	ket_qua["so_dong_hang"] = frappe.db.sql(
		"""
		select count(*) from `tabLocation Balance` lb
		join `tabStorage Location` sl on sl.name = lb.o
		where sl.kho = %(kho)s and sl.lft between %(lft)s and %(rgt)s and lb.so_luong != 0
		""",
		tham_so,
	)[0][0]
	ket_qua["hang_trong_o"] = frappe.db.sql(
		"""
		select lb.o as o, lb.vat_tu as vat_tu, i.item_name as ten_hang, i.stock_uom as don_vi,
			lb.so_lo as so_lo, b.expiry_date as hsd, lb.so_luong as so_luong
		from `tabLocation Balance` lb
		join `tabStorage Location` sl on sl.name = lb.o
		left join `tabItem` i on i.name = lb.vat_tu
		left join `tabBatch` b on b.name = lb.so_lo
		where sl.kho = %(kho)s and sl.lft between %(lft)s and %(rgt)s and lb.so_luong != 0
		order by sl.lft asc, b.expiry_date is null, b.expiry_date asc
		limit %(tran)s
		""",
		{**tham_so, "tran": TRAN_DONG_HANG_TRONG_O},
		as_dict=True,
	)
	return ket_qua


def _tra_cuu_khong_kiem_quyen(ma: str) -> dict:
	"""Thân thật của `tra_cuu`, TÁCH khỏi phép kiểm quyền để bọc try/except
	đúng MỘT LẦN ở hàm công khai (điều #2 brief: quét nhầm không được nổ) mà
	KHÔNG lẫn với `_kiem_tra_quyen()` — `frappe.PermissionError` phải VĂNG RA
	nguyên vẹn, không bị nuốt chung với lỗi dữ liệu.
	"""
	ma = (ma or "").strip()
	if not ma:
		return {"loai": None}

	# `scan_barcode` đã thử theo thứ tự Item Barcode -> Serial No -> Batch ->
	# Warehouse và luôn trả `dict` (rỗng nếu không khớp gì) — không bao giờ
	# `None`, nhưng `or {}` vẫn giữ cho chắc, vì bên gọi tuyệt đối không được
	# `.get()` trên `None`.
	ket_qua = scan_barcode(ma) or {}

	# Đúng thứ tự ưu tiên `scan_barcode` trả: khớp Serial No hoặc Batch đều có
	# khoá `batch_no` (Serial No resolve tiếp ra Batch của chính nó) — cả hai
	# đường đều LÀ một lô đối với người quét, nên gộp chung một nhánh.
	if ket_qua.get("batch_no"):
		return _tra_cuu_lo(ket_qua["batch_no"])

	if ket_qua.get("warehouse"):
		return _tra_cuu_kho(ket_qua["warehouse"])

	if ket_qua.get("item_code"):
		# Quét trúng Item Barcode mà mặt hàng đó CÓ quản lý lô (has_batch_no):
		# đây vẫn LÀ mặt hàng, KHÔNG phải lô — `scan_barcode` không tự suy ra
		# lô nào từ một mã vạch gắn trên bao bì gốc của mặt hàng. Trả `loai =
		# "vat_tu"` đúng sự thật, không giả vờ là lô (điều #3 brief — chính là
		# bài `test_quet_ma_vat_tu_thi_tra_ve_mat_hang_khong_gia_vo_la_lo`).
		return _tra_cuu_vat_tu(ket_qua["item_code"])

	# Hai nguồn `scan_barcode` không biết, thêm cho trang quét riêng trên PDA:
	# tem VỊ TRÍ dán trên kệ (mã ô), và mã vật tư GÕ TAY. Đặt SAU `scan_barcode`
	# để không đổi nghĩa của bất kỳ mã nào đã tra được trước đây.
	ma_o = _tim_o(ma)
	if ma_o:
		return _tra_cuu_o(ma_o)

	if frappe.db.exists("Item", ma):
		return _tra_cuu_vat_tu(ma)

	return {"loai": None}


@frappe.whitelist()
def tra_cuu(ma: str) -> dict:
	"""Quét `ma` (mã vạch/số lô/mã vật tư/mã kho), trả TOÀN BỘ thông tin đã
	khai cho lô đó — xem docstring module để biết hình dạng đầy đủ.

	`ma` LUÔN là một chuỗi qua lớp gọi từ xa của Frappe (Task 9 đã đo và vá
	đúng bẫy này ở `nhap_lo._danh_sach_lo`, xem docstring ở đó). Chữ ký ở đây
	chỉ nhận MỘT mã — không phải danh sách — nên không có `frappe.parse_json`
	nào cần gọi: không hứa nhận `list` thì không có lời hứa nào để không giữ
	được.
	"""
	_kiem_tra_quyen()
	try:
		return _tra_cuu_khong_kiem_quyen(ma)
	except Exception:
		# Điều #2 brief: quét nhầm MỘT mã bất kỳ (vỏ thùng, tem vận chuyển,
		# bất cứ thứ gì có vạch) không được làm nổ traceback giữa màn hình
		# nhập liệu — đó là cách nhanh nhất khiến thủ kho thôi dùng chức năng
		# này. Không nuốt câm lặng: `frappe.log_error` tự chụp traceback hiện
		# tại, giữ dấu vết thật để người vận hành tra khi cần (cùng khuôn Ruling
		# N đã dùng ở `xep.py`/`nhap_lo.py`).
		#
		# `cat_tieu_de` BẮT BUỘC (review điều phối, vòng sửa 2/5): `title` đi
		# vào `Error Log.method` — cột `Data(140)`. Không cắt thì một `ma` đủ
		# dài (mã quét/số lô GÕ TAY không có trần) khiến CHÍNH `log_error()`
		# này ném `CharacterLengthExceededError`, văng ra NGOÀI khối `except`
		# đang bao nó — đúng lưới an toàn tự thủng ở lối thoát hiểm của nó.
		# Xem lý lẽ đầy đủ ở `nhat_ky_loi.py`.
		frappe.log_error(title=cat_tieu_de(f"vi_tri_kho: tra_cuu loi ({ma})"))
		return {"loai": None}
