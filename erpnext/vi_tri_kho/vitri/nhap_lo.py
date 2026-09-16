"""API máy chủ cho màn hình `Batch Entry` và cho việc in nhãn lô 50×30 (spec khối C §7 Task 7).

Ba hàm, ba việc TÁCH BIỆT — cố ý không gộp, vì gộp là nguồn của đúng lớp lỗi dự
án này đã trả giá nhiều lần ("màn hình nói một đằng, tem in ra một nẻo"):

1. `lay_dong_tu_phieu_nhap` — nạp dòng hàng CÒN THIẾU SỐ LÔ từ phiếu nhập, kèm
   gợi ý ô để hiện ngay trên bảng con, GIÚP thủ kho chứ không quyết định gì.
2. `du_lieu_tem` — xem trước dữ liệu SẼ in lên nhãn, đã ĐỊNH DẠNG SẴN (ngày
   `YYYY/MM/DD`, ô qua `ma_vi_tri.dinh_dang_nhan()`, ĐVT ghép theo §6.3). CHỈ
   ĐỌC — không được phép ghi `custom_o_in_tem`, vì xem trước không phải in.
3. `dat_o_in_tem` — hàm DUY NHẤT được phép GHI `custom_o_in_tem`, và chỉ ghi
   một lần: đã có giá trị thì giữ NGUYÊN. Tem đã in có thể đã dán lên hàng —
   in lại lần hai phải ra đúng tờ giấy như lần đầu (§6.5, §8).

Quyền: `_kiem_tra_quyen()` theo đúng khuôn `xep.py`/`tem.py` — `@frappe.
whitelist()` một mình chỉ chặn khách vãng lai, còn ba hàm này lộ tồn kho theo ô
(`o_goi_y`, F8) nên đăng nhập hợp lệ không phải điều kiện đủ. Dùng lại đúng bộ
vai trò `VAI_TRO_DUOC_XEP`/`VAI_TRO_DUOC_IN_TEM` (không import chéo — mỗi file
`vitri/*.py` tự giữ một bản, đúng tiền lệ `tem.py` đã chọn, để không cột chặt
các module vốn độc lập vào nhau vì một hằng số ba phần tử).

Ruling N (khối B, nhắc lại ở `xep.py`): `goi_y_o` có thể NÉM LỖI cho một (mặt
hàng, lô) — ví dụ gán trỏ vào một nút cây chưa hội tụ (`lft`/`rgt` = 0/0).
Nuốt lỗi đó TỪNG DÒNG, không để nó văng ra khỏi vòng lặp: một mặt hàng hỏng dữ
liệu không được làm SẬP cả danh sách trong khi những mặt hàng lành khác vẫn
đang chờ thủ kho khai lô (hoặc chờ in cả xấp nhãn của phiếu).
"""

import frappe
from frappe import _
from frappe.utils import getdate

from erpnext.vi_tri_kho.vitri.goi_y import goi_y_o
from erpnext.vi_tri_kho.vitri.ma_vi_tri import dinh_dang_nhan

# Cùng bộ vai trò với `xep.VAI_TRO_DUOC_XEP` / `tem.VAI_TRO_DUOC_IN_TEM`: nạp
# dòng hàng và in nhãn đều là việc HẰNG NGÀY của thủ kho, không phải thao tác
# thiết lập chỉ dành cho quản lý (khác `bat_kho.py`).
VAI_TRO_DUOC_DUNG = {"System Manager", "Stock Manager", "Stock User"}

# F8 khi CHƯA có ô nào để in — không đoán (mặt hàng chưa gán, hoặc không suy
# được kho), và KHÔNG chặn in: một nhãn thiếu ô vẫn dán lên hàng được, còn
# thủ kho tự biết đứng trước kệ nào. Xem §6.5.
_KHONG_CO_O = "VT —"


def _kiem_tra_quyen():
	"""`@frappe.whitelist()` một mình chỉ chặn khách vãng lai.

	`lay_dong_tu_phieu_nhap` và `du_lieu_tem` lộ ra tồn kho theo ô (qua gợi ý
	vị trí), `dat_o_in_tem` GHI dữ liệu vận hành của kho — nên đăng nhập hợp
	lệ không phải điều kiện đủ cho cả ba. `Website User` (khách hàng cổng
	`miyano_portal`) không có vai trò nào trong tập này nên bị chặn.
	"""
	if not VAI_TRO_DUOC_DUNG & set(frappe.get_roles()):
		frappe.throw(
			_("Bạn không có quyền dùng chức năng nhập lô / in nhãn."), frappe.PermissionError
		)


@frappe.whitelist()
def lay_dong_tu_phieu_nhap(phieu_nhap: str) -> list[dict]:
	"""Các dòng của `phieu_nhap` còn THIẾU số lô, sẵn sàng đổ vào bảng con.

	Điều kiện lọc (spec §5.3 bước 2): `Item.has_batch_no = 1` (mặt hàng không
	quản lý lô không có gì để thủ kho gõ) và `batch_no` CÒN TRỐNG trên dòng
	phiếu nhập — bấm lại nút này sau khi đã khai lô một phần không được nạp
	lại và nhân đôi công việc đã làm.

	`o_goi_y`/`ly_do_goi_y` gọi `goi_y_o(vat_tu, kho)` — KHÔNG truyền `so_lo`:
	lúc nạp dòng, lô của dòng này CHƯA TỒN TẠI (thủ kho chưa gõ số lô), nên
	nhánh "ưu tiên ô đã in tem" (§8, chỉ chạy khi có `so_lo`) không áp dụng
	được ở đây — đúng tham số mặc định của `goi_y_o(vat_tu, kho, so_lo=None)`.
	"""
	_kiem_tra_quyen()

	dong = frappe.db.sql(
		"""
		select pri.name as dong_phieu_nhap, pri.item_code as vat_tu, pri.item_name as ten_hang,
		       pri.warehouse as kho, pri.qty as so_luong
		from `tabPurchase Receipt Item` pri
		join `tabItem` it on it.name = pri.item_code
		where pri.parent = %(phieu_nhap)s
		  and it.has_batch_no = 1
		  and ifnull(pri.batch_no, '') = ''
		order by pri.idx asc
		""",
		{"phieu_nhap": phieu_nhap},
		as_dict=True,
	)

	for d in dong:
		try:
			o, ly_do, _tem_hong = goi_y_o(d.vat_tu, d.kho)
		except Exception:
			# Ruling N: KHÔNG để lỗi của MỘT mặt hàng làm sập cả danh sách —
			# nút "Lấy dòng hàng từ phiếu nhập" phải mở được cho những mặt
			# hàng lành, trong khi thủ kho vẫn cần khai lô cho TẤT CẢ chúng
			# trong cùng một phiếu. `frappe.log_error` (không truyền `message`)
			# tự chụp traceback hiện tại, giữ dấu vết thật để người vận hành
			# đi sửa dữ liệu gán thay vì lỗi biến mất lặng lẽ.
			frappe.log_error(
				title=f"vi_tri_kho: lay_dong_tu_phieu_nhap goi_y_o loi ({d.vat_tu})"
			)
			o, ly_do = (
				None,
				_(
					"không gợi ý được cho {0} — xem Error Log. KHÔNG PHẢI mặt hàng chưa "
					"gán, đừng gán lại"
				).format(d.vat_tu),
			)
		d["o_goi_y"], d["ly_do_goi_y"] = o, ly_do

	return dong


def _kho_cua_lo(lo) -> str | None:
	"""Suy kho từ chứng từ đã sinh ra lô (§6.5): `reference_name` (một
	`Purchase Receipt`) → dòng của ĐÚNG lô này (khớp bằng `batch_no`, không
	phải `item_code` — một phiếu nhập có thể có hai dòng cùng mặt hàng, khác
	lô, nên khớp theo mặt hàng là mơ hồ) → `warehouse` của dòng đó.

	Không suy ra được (lô không sinh từ phiếu nhập, hoặc `Batch Entry` chưa
	submit nên `batch_no` chưa kịp ghi lên dòng phiếu nhập) → `None`, KHÔNG
	đoán — bên gọi tự quyết định làm gì tiếp (F8 in `VT —`, hoặc không đặt ô).
	"""
	if lo.reference_doctype != "Purchase Receipt" or not lo.reference_name:
		return None
	return frappe.db.get_value(
		"Purchase Receipt Item",
		{"parent": lo.reference_name, "batch_no": lo.name},
		"warehouse",
	)


def _ngay_nhap_cua_lo(lo):
	"""Ngày nhập (F7) = `posting_date` của phiếu nhập sinh ra lô. `None` nếu
	lô không sinh từ phiếu nhập — không suy diễn một ngày không có căn cứ."""
	if lo.reference_doctype != "Purchase Receipt" or not lo.reference_name:
		return None
	return frappe.db.get_value("Purchase Receipt", lo.reference_name, "posting_date")


def _dinh_dang_ngay(d) -> str:
	"""`YYYY/MM/DD` theo §6.1 bảng ô — định dạng SẴN ở đây, không để JS tự làm
	(mở đường cho nhãn in và màn hình xem trước nói khác nhau, xem docstring
	module)."""
	return getdate(d).strftime("%Y/%m/%d") if d else ""


def _f3_don_vi_tinh(item) -> str:
	"""Ô F3 — ĐVT và quy cách, theo đúng luật §6.3.

	`Item.uoms` LUÔN có ít nhất một dòng cho chính `stock_uom` (ERPNext tự
	thêm ở `add_default_uom_in_conversion_factor_table`, `conversion_factor
	= 1`) — nên "0 dòng quy đổi" trong ngôn ngữ nghiệp vụ nghĩa là "0 dòng có
	`uom != stock_uom`" trong dữ liệu thật, KHÔNG phải `len(item.uoms) == 0`.
	Lọc đúng vế đó trước khi đếm.

	Đúng MỘT dòng `uom != stock_uom` → `"{stock_uom} ({conversion_factor}/
	{uom})"`. Không dòng nào, hoặc từ hai dòng trở lên → chỉ `stock_uom`:
	nhiều hơn một quy cách thì không có quy cách nào ĐÚNG để in, in bừa một
	dòng là nói sai trên vật thể vật lý mà không ai đối chiếu lại.
	"""
	quy_doi = [d for d in item.uoms if d.uom != item.stock_uom]
	if len(quy_doi) == 1:
		d = quy_doi[0]
		# `:g` bỏ ".0" thừa (1.0 -> "1") mà vẫn giữ phần thập phân khi cần
		# (2.5 -> "2.5") — hệ số quy đổi là số người đọc, không phải số máy.
		return f"{item.stock_uom} ({d.conversion_factor:g}/{d.uom})"
	return item.stock_uom


def _f8_xem_truoc(lo, kho) -> str:
	"""Ô F8 — CHỈ ĐỌC, không bao giờ ghi `custom_o_in_tem` (yêu cầu #4 brief:
	xem trước không được ghi dữ liệu — việc ghi là của `dat_o_in_tem`).

	`custom_o_in_tem` đã có → dùng ĐÚNG ô đó (tem đã ứng nghiệm — xem trước
	phải khớp với tờ tem thật sẽ in, hoặc đã in). Còn trống → xem trước ô SẼ
	được `dat_o_in_tem` gán khi in thật, bằng cách gọi `goi_y_o` (đọc, không
	ghi). Không tính được ô nào (chưa gán vị trí cố định, không suy được kho,
	hoặc `goi_y_o` ném lỗi vì dữ liệu toạ độ hỏng — Ruling N, không được để
	MỘT lô hỏng làm sập cả lượt xem trước "cả phiếu") → `"VT —"`, không đoán,
	không chặn in (yêu cầu #5 brief).
	"""
	if lo.custom_o_in_tem:
		return dinh_dang_nhan(lo.custom_o_in_tem)

	if kho:
		try:
			o, _ly_do, _tem_hong = goi_y_o(lo.item, kho, lo.name)
		except Exception:
			frappe.log_error(title=f"vi_tri_kho: du_lieu_tem goi_y_o loi ({lo.name})")
			o = None
		if o:
			return dinh_dang_nhan(o)

	return _KHONG_CO_O


def _du_lieu_mot_lo(so_lo: str) -> dict:
	lo = frappe.get_doc("Batch", so_lo)
	item = frappe.get_doc("Item", lo.item)
	kho = _kho_cua_lo(lo)
	ngay_nhap = _ngay_nhap_cua_lo(lo)

	return {
		"F1": item.name,
		"F2": item.item_name,
		"F3": _f3_don_vi_tinh(item),
		# F4 trống thì để TRẮNG (§6.1) — chuỗi rỗng, không phải một placeholder
		# nào khác, để lưới cố định của JS giữ đúng chiều cao ô mà không dồn
		# hàng dưới lên.
		"F4": item.custom_thong_so_tem or "",
		"F5": f"HSD {_dinh_dang_ngay(lo.expiry_date)}" if lo.expiry_date else "",
		"F6": f"Lô {lo.batch_id}",
		"F7": f"NHẬP {_dinh_dang_ngay(ngay_nhap)}" if ngay_nhap else "",
		"F8": _f8_xem_truoc(lo, kho),
		"F9": lo.custom_so_goi or "",
		# F10/F11 mã hoá và in lại đúng SỐ LÔ — nguyên văn, JS chỉ đặt vào
		# `JsBarcode` (F10) và dưới mã vạch (F11), không tự định dạng gì thêm.
		"F10": lo.batch_id,
		"F11": lo.batch_id,
	}


@frappe.whitelist()
def du_lieu_tem(so_lo: list[str] | str) -> list[dict]:
	"""Dữ liệu ĐÃ ĐỊNH DẠNG SẴN cho nhãn 50×30 của một hoặc nhiều lô — 11 ô
	F1–F11 mỗi lô. Thứ tự trả về khớp thứ tự `so_lo` truyền vào.

	CHỈ ĐỌC — không gọi `dat_o_in_tem`, không ghi `custom_o_in_tem` (yêu cầu
	#4 brief). Trộn việc GHI vào hàm XEM TRƯỚC là mở đường cho một lần mở màn
	hình xem trước (không hề bấm in) âm thầm "chốt" một ô lên tem, trước khi
	thủ kho kịp quyết định in hay không.
	"""
	_kiem_tra_quyen()
	danh_sach = [so_lo] if isinstance(so_lo, str) else list(so_lo)
	return [_du_lieu_mot_lo(sl) for sl in danh_sach]


@frappe.whitelist()
def dat_o_in_tem(so_lo: str) -> str | None:
	"""Đặt `Batch.custom_o_in_tem` nếu CÒN TRỐNG, rồi trả ô đó. Hàm DUY NHẤT
	được phép ghi trường này (§8: "in xong ghi lại").

	BẤT BIẾN theo lần gọi: đã có giá trị → trả NGUYÊN giá trị đó, không tính
	lại — kể cả khi tính lại sẽ ra một ô khác (dữ liệu kho đổi giữa hai lần
	in). In lại lần hai phải ra ĐÚNG tờ giấy như lần đầu, vì lần đầu có thể đã
	dán lên hàng (§6.5).

	Còn trống: suy kho qua `_kho_cua_lo`, rồi gọi `goi_y_o(item, kho, so_lo)`.
	Không suy được kho, `goi_y_o` không gợi ý được (mặt hàng chưa gán vị trí
	cố định), hoặc `goi_y_o` ném lỗi (dữ liệu toạ độ hỏng) → trả `None`, KHÔNG
	đoán và KHÔNG chặn in — màn hình vẽ nhãn với F8 = `"VT —"` (`du_lieu_tem`,
	`_f8_xem_truoc`) chứ không dừng cả lượt in vì một lô chưa gán được ô.
	"""
	_kiem_tra_quyen()
	lo = frappe.get_doc("Batch", so_lo)
	if lo.custom_o_in_tem:
		return lo.custom_o_in_tem

	kho = _kho_cua_lo(lo)
	if not kho:
		return None

	try:
		o, _ly_do, _tem_hong = goi_y_o(lo.item, kho, lo.name)
	except Exception:
		frappe.log_error(title=f"vi_tri_kho: dat_o_in_tem goi_y_o loi ({so_lo})")
		return None
	if not o:
		return None

	# Đi thẳng xuống CSDL: `custom_o_in_tem` là `read_only: 1` trên lược đồ
	# (chỉ engine này được đặt, theo đúng chủ đích §4.2), và ta không cần các
	# hook `validate`/`before_save` khác của `Batch` chạy lại chỉ để ghi một
	# trường.
	frappe.db.set_value("Batch", so_lo, "custom_o_in_tem", o)
	return o
