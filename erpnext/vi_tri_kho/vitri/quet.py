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
nhau). Khoá `loai` (`"lo"` / `"vat_tu"` / `"kho"` / `None`) là giao thức giữa
hai tầng — bên gọi không phải đoán bằng cách xem khoá nào có mặt.

Quét NHẦM là chuyện thường ngày (mã trên vỏ thùng carton, tem vận chuyển, bất
cứ thứ gì có vạch) — `tra_cuu` không bao giờ được ném lỗi ra giữa màn hình
nhập liệu; mọi nhánh không nhận diện được đều trả `{"loai": None}`, không nổ.
"""

import frappe
from frappe import _

from erpnext.stock.utils import scan_barcode
from erpnext.vi_tri_kho.vitri.nhat_ky_loi import cat_tieu_de

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


def _tra_cuu_khong_kiem_quyen(ma: str) -> dict:
	"""Thân thật của `tra_cuu`, TÁCH khỏi phép kiểm quyền để bọc try/except
	đúng MỘT LẦN ở hàm công khai (điều #2 brief: quét nhầm không được nổ) mà
	KHÔNG lẫn với `_kiem_tra_quyen()` — `frappe.PermissionError` phải VĂNG RA
	nguyên vẹn, không bị nuốt chung với lỗi dữ liệu.
	"""
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
		return {"loai": "kho", "kho": ket_qua["warehouse"]}

	if ket_qua.get("item_code"):
		# Quét trúng Item Barcode mà mặt hàng đó CÓ quản lý lô (has_batch_no):
		# đây vẫn LÀ mặt hàng, KHÔNG phải lô — `scan_barcode` không tự suy ra
		# lô nào từ một mã vạch gắn trên bao bì gốc của mặt hàng. Trả `loai =
		# "vat_tu"` đúng sự thật, không giả vờ là lô (điều #3 brief — chính là
		# bài `test_quet_ma_vat_tu_thi_tra_ve_mat_hang_khong_gia_vo_la_lo`).
		ten_hang = frappe.db.get_value("Item", ket_qua["item_code"], "item_name")
		return {"loai": "vat_tu", "vat_tu": ket_qua["item_code"], "ten_hang": ten_hang}

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
