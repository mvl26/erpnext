"""Bốn thao tác bật quản lý vị trí cho một kho: xem trước, bật, tắt, đồng bộ lại.

Bật KHÔNG phải là tích một checkbox. Nó là quy trình chuyển đổi dữ liệu:
tạo ô CHUA-XEP, đọc tồn hiện có TÁCH THEO TỪNG LÔ, ghi sổ chuyển đổi, dựng
tồn, rồi đối soát. Vì vậy `Warehouse.custom_quan_ly_vi_tri` để read-only và
chỉ module này được đặt.

Task 11 dựng `xem_truoc` — không ghi gì. Task 12 dựng `bat` (Task 13 sẽ
thêm `tat`, `dong_bo_lai`).

`bat()` GHI DỮ LIỆU (tạo ô, ghi sổ, đổi cờ `Warehouse`) — kiểm quyền ở đây
quan trọng HƠN ở `xem_truoc` (chỉ đọc): thiếu kiểm quyền nghĩa là một tài
khoản `Website User` (khách cổng `miyano_portal`) BẬT được quản lý vị trí
cho kho nội bộ, không chỉ đọc được số liệu. `_kiem_tra_quyen()` đứng ở
dòng đầu `bat()`, trước mọi truy vấn — bản nháp trong brief gốc của Task
12 KHÔNG gọi hàm này; đã bổ sung ở đây cùng bài `TestBatQuyen` (xem
`tests/test_bat_kho.py`).

GHI ĐÈ REVIEW so với bản brief gốc: hàm đọc "tồn hiện có" KHÔNG tự viết lại
SQL `sum(case when sbe.name is not null then sbe.qty else sle.actual_qty
end)` — nhánh `else sle.actual_qty` sai với Stock Reconciliation hàng KHÔNG
LÔ (xem docstring `vitri/doi_soat.py`). Dùng lại
`vitri.doi_soat.ton_kho_theo_lo` (Task 10, đã sửa đúng) làm NGUỒN SỰ THẬT
DUY NHẤT — sửa một bên quên bên kia thì "bật kho" và "đối soát" đọc tồn
theo hai cách khác nhau.

VÒNG SỬA 1 (review điều phối, Critical): `xem_truoc` là hàm `@frappe.
whitelist()` đầu tiên của module `vitri/` và ban đầu KHÔNG có kiểm quyền.
`frappe.whitelist()` mặc định chỉ đòi đã đăng nhập, không giới hạn role —
DocPerm trên doctype `Warehouse Location Setup` KHÔNG chặn được RPC này
(RPC không phải đọc doctype). Site `erptest.local` có 10 tài khoản
`Website User` đang hoạt động (khách hàng cổng `miyano_portal`); thiếu
kiểm quyền nghĩa là một tài khoản bệnh viện gọi được RPC này và đọc tồn
theo lô của MỌI kho nội bộ Miyano. Xem `_kiem_tra_quyen`.
"""

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, nowdate

from erpnext.vi_tri_kho.vitri.doi_soat import NGUONG_SAI_SO, doi_soat_kho, ton_kho_theo_lo
from erpnext.vi_tri_kho.vitri.kho import (
	kho_co_quan_ly_vi_tri,
	kiem_tra_dang_o_chua_xep,
	ma_o_chua_xep,
	xoa_cache_kho,
)
from erpnext.vi_tri_kho.vitri.so import dung_lai_ton_vi_tri, ghi_dong_so

# VÒNG SỬA 1 (review điều phối, Q4b): trước đây module này khai lại
# `NGUONG_SAI_SO = 0.0001` thay vì import từ `vitri/doi_soat.py`. Hai
# ngưỡng trôi lệch nhau (một bên sửa, bên kia quên) thì `bat()` sẽ BỎ một
# dòng mà `doi_soat_kho` vẫn TÍNH — kho đó hỏng vĩnh viễn, không cách nào
# bật được nữa (đối soát luôn báo lệch ở đúng dòng bị bỏ). Import thay vì
# khai lại, đúng nguyên tắc "một nguồn sự thật duy nhất" mà module này áp
# dụng cho chính việc đọc tồn (`ton_kho_theo_lo`).

CHUNG_TU_CHUYEN_DOI = "Warehouse Location Setup"

# Cùng vai trò với DocPerm của doctype `Warehouse Location Setup` — một
# nguồn duy nhất giữa "ai được sửa doctype điều phối" và "ai được gọi RPC
# vận hành nó" (xem `_kiem_tra_quyen`).
VAI_TRO_DUOC_XU_LY_VI_TRI = {"System Manager", "Stock Manager"}


def _kiem_tra_quyen(thao_tac: str = "xem", doi_tuong: str = "thông tin chuyển đổi vị trí kho"):
	"""Chặn người không có vai trò quản lý kho/vị trí.

	`Website User` (khách hàng cổng) không có vai trò nào trong danh sách
	này nên bị chặn ở đây, bất kể có đăng nhập hợp lệ hay không — đăng nhập
	hợp lệ là điều kiện MẶC ĐỊNH của `frappe.whitelist()`, không phải điều
	kiện đủ để đọc tồn kho nội bộ.

	VÒNG SỬA 1 (review điều phối, Q5): tham số `thao_tac` để thông báo khớp
	đúng hành động bị chặn — trước đây `bat()` (GHI: tạo ô, ghi sổ, đổi cờ)
	dùng nguyên câu "không có quyền XEM thông tin chuyển đổi" của
	`xem_truoc` (chỉ ĐỌC), sai bản chất thao tác bị chặn dù không sai về
	mặt chặn được hay không.

	VÒNG SỬA 1/5 (review điều phối, Task 14, Important 1): thêm tham số
	`doi_tuong` (mặc định giữ nguyên "thông tin chuyển đổi vị trí kho" —
	an toàn ngược cho bốn lời gọi cũ `xem`/`bật`/`tắt`/`đồng bộ lại`, cả
	bốn đều xử lý ĐÚNG một đối tượng: hồ sơ chuyển đổi vị trí kho). Khi
	`vitri/sinh_ma.py` (Task 14) gọi hàm này, đối tượng bị chặn là MÃ Ô,
	không phải hồ sơ chuyển đổi — câu cũ ghép cứng "thông tin chuyển đổi
	vị trí kho" sẽ ra câu vừa sai ngữ pháp vừa sai ngữ nghĩa, ví dụ "Bạn
	không có quyền sinh mã ô thông tin chuyển đổi vị trí kho." Nay
	`sinh_ma.py` truyền `doi_tuong="mã ô"` để có câu đúng: "Bạn không có
	quyền sinh mã ô."
	"""
	if not VAI_TRO_DUOC_XU_LY_VI_TRI & set(frappe.get_roles()):
		frappe.throw(
			_("Bạn không có quyền {0} {1}.").format(thao_tac, doi_tuong),
			frappe.PermissionError,
		)


def _mo_ta_loi_doi_soat(kq: dict) -> str:
	"""Diễn giải NGẮN kết quả `doi_soat_kho` lệch — nêu rõ ĐÚNG (các) phép đo
	nào hỏng, không ghép cứng câu chỉ nói về `dong_lech`.

	CRITICAL 1b (review điều phối): `doi_soat_kho` giờ trả thêm `o_am`/
	`lech_bo_dem` — `khop` có thể False chỉ vì MỘT trong ba phép đo, trong
	khi `dong_lech` (và `so_dong_lech`) vẫn rỗng. Thông báo cũ ghép cứng
	"lệch ở {so_dong_lech} dòng" sẽ đọc thành "lệch ở 0 dòng" kèm danh sách
	rỗng trên một RPC vừa `frappe.throw` thật — đúng loại thông báo sai
	ngữ nghĩa đã từng bị sửa ở `_kiem_tra_quyen(thao_tac, ...)`.
	"""
	phan = []
	if kq["dong_lech"]:
		phan.append(
			_("{0} dòng lệch TỔNG so với tồn kho (dòng đầu: {1})").format(
				kq["so_dong_lech"], frappe.as_json(kq["dong_lech"][:3])
			)
		)
	if kq["o_am"]:
		phan.append(
			_("{0} Ô đang mang tồn ÂM (ô đầu: {1})").format(len(kq["o_am"]), frappe.as_json(kq["o_am"][:3]))
		)
	if kq["lech_bo_dem"]:
		phan.append(
			_("{0} dòng bộ đệm trôi khỏi sổ (dòng đầu: {1})").format(
				len(kq["lech_bo_dem"]), frappe.as_json(kq["lech_bo_dem"][:3])
			)
		)
	return "; ".join(phan)


def kiem_tra_khong_phai_kho_tong(kho):
	"""Chặn kho tổng (`is_group`) — không chứa hàng thật.

	Dùng chung giữa `_kiem_tra_kho` (RPC `xem_truoc`/`bat`/`tat`/
	`dong_bo_lai`) và `WarehouseLocationSetup.validate()` — một nguồn
	thông báo duy nhất. Trước vòng sửa này hai nơi chặn cùng một điều kiện
	nhưng bằng hai chuỗi thông báo khác nhau, đúng loại lệch mà chính task
	này khoá ở tầng dữ liệu (tồn vị trí vs tồn kho) nhưng lại để lọt ở tầng
	validate.
	"""
	if frappe.db.get_value("Warehouse", kho, "is_group"):
		frappe.throw(
			_(
				"{0} là kho tổng, không chứa hàng thật nên không bật quản lý vị trí được. "
				"Chọn một kho cụ thể."
			).format(kho)
		)


def _kiem_tra_da_tung_bat(kho):
	"""Chặn `dong_bo_lai()` trên một kho CHƯA TỪNG bật quản lý vị trí.

	Vòng sửa (review advisor, sau khi 9/9 bài xanh): `dong_bo_lai()` gọi
	`_kiem_tra_kho(kho, cho_phep_da_bat=True)`, cố ý bỏ qua cả kiểm tra "đã
	bật" lẫn kiểm tra `trang_thai` để cho phép chạy trên kho đang "Đã tắt"
	(bật lại) hoặc đang "Đang bật" (đối soát lệch chưa rõ nguyên nhân) —
	đúng như brief. Nhưng điều đó cũng vô tình cho phép chạy trên kho CHƯA
	TỪNG bật (không có bản ghi `Warehouse Location Setup` nào) — trên kho
	đó, `ghi_dong_so` (dòng bù đầu tiên) ném thẳng
	`LinkValidationError: Could not find Chứng từ: {kho}` (đã đo thật qua
	console, không suy đoán) vì `Location Ledger Entry.chung_tu` là Dynamic
	Link theo `chung_tu_type="Warehouse Location Setup"` — đúng cái bẫy mà
	docstring `bat()` đã cảnh báo Task 13 (xem "Task 13 lưu ý" ở
	task-12-report.md). Vi phạm ràng buộc toàn cục "thông báo lỗi tiếng
	Việt, không lộ traceback" trên một RPC `@frappe.whitelist()`. Cả hai
	tình huống hợp lệ của brief (bật lại sau tắt; đối soát trên kho đang
	bật) luôn có sẵn bản ghi này, nên chặn ở đây không tốn gì của đường
	thuận.

	VÒNG SỬA 2 (review advisor): bản đầu chỉ chặn `trang_thai is None`
	(không có bản ghi) — DANH SÁCH CẤM, không phải DANH SÁCH CHO PHÉP. Lỗ
	hổng còn lại: `Warehouse Location Setup` cho phép `create` qua UI/Data
	Import (DocPerm `create: 1` cho System Manager/Stock Manager), và
	`trang_thai` mặc định `"Chưa bật"` khi field đó `read_only` trên form
	(read_only không chặn được set qua Data Import hay tạo tay). Một bản
	ghi như vậy có `trang_thai = "Chưa bật"` (không phải `None`) nên lọt
	qua bản kiểm tra cũ, ĐỦ để `ghi_dong_so` không còn ném
	`LinkValidationError` (Dynamic Link đã có chỗ trỏ tới) — `dong_bo_lai()`
	chạy trọn, đổ toàn bộ tồn hiện có vào CHUA-XEP như bù trừ, và bật cờ
	`custom_quan_ly_vi_tri` mà KHÔNG qua transaction "được ăn cả ngã về
	không" của `bat()` (không savepoint, không `dung_lai_ton_vi_tri`,
	không `ngay_bat`/`so_dong_chuyen_doi`) — một `bat()` cửa sau. Sửa bằng
	DANH SÁCH CHO PHÉP thay vì mở rộng danh sách cấm: chỉ đúng 3 giá trị
	`trang_thai` mà một kho ĐÃ TỪNG BẬT có thể mang mới được đi tiếp —
	an toàn hơn về cấu trúc (không cần nhớ cập nhật nếu Select thêm giá trị
	mới sau này).
	"""
	trang_thai = frappe.db.get_value("Warehouse Location Setup", kho, "trang_thai")
	if trang_thai not in ("Đang bật", "Đã tắt", "Cần đồng bộ lại"):
		frappe.throw(
			_(
				'Kho {0} chưa từng bật quản lý vị trí. Chạy chức năng "Bật" trước, '
				'"Đồng bộ lại" chỉ dùng cho kho đã từng bật.'
			).format(kho)
		)


def _kiem_tra_kho(kho, cho_phep_da_bat=False):
	if not frappe.db.exists("Warehouse", kho):
		frappe.throw(_("Không tìm thấy kho {0}.").format(kho))

	kiem_tra_khong_phai_kho_tong(kho)

	if not cho_phep_da_bat and kho_co_quan_ly_vi_tri(kho):
		frappe.throw(_("Kho {0} đã bật quản lý vị trí rồi.").format(kho))

	# Task 13: chặn bật thẳng lại từ "Đã tắt"/"Cần đồng bộ lại". Trong lúc
	# tắt, kho vẫn xuất nhập bình thường (hook bỏ qua vì `custom_quan_ly_
	# vi_tri` = 0) nên tồn vị trí đứng yên trong khi tồn kho ERPNext đi
	# tiếp — bật thẳng lại sẽ đối soát khớp giả (vì cả ghi sổ mới lẫn kiểm
	# tra đều chỉ nhìn trạng thái hiện tại, không biết đã có khoảng thời
	# gian tồn kho trôi mà sổ vị trí không theo). Đây là cái bẫy chắc chắn
	# có người dẫm nếu không chặn bằng máy; phải đi qua `dong_bo_lai()`.
	# `tat()` và `dong_bo_lai()` đều gọi `_kiem_tra_kho(kho,
	# cho_phep_da_bat=True)` nên không tự vướng điều kiện này.
	trang_thai = frappe.db.get_value("Warehouse Location Setup", kho, "trang_thai")
	if not cho_phep_da_bat and trang_thai in ("Đã tắt", "Cần đồng bộ lại"):
		frappe.throw(
			_(
				"Kho {0} từng bật rồi tắt. Trong lúc tắt kho vẫn xuất nhập nên tồn theo vị trí "
				'đã lệch — phải chạy "Đồng bộ lại" trước, không bật thẳng được.'
			).format(kho)
		)


def _ton_hien_co(kho) -> list[dict]:
	"""Tồn hiện có của kho, TÁCH THEO TỪNG LÔ.

	Ghi một dòng cho mỗi (mặt hàng, kho) mà không tách lô thì tổng vẫn khớp
	Bin nhưng chiều lô mất trắng và KHÔNG BAO GIỜ dựng lại được từ dữ liệu
	quá khứ — mọi thứ xây sau đó đứng trên số liệu sai.

	Dùng lại `ton_kho_theo_lo` (Task 10) thay vì tự viết SQL — xem docstring
	module này và `vitri/doi_soat.py`. Ngưỡng lọc dòng gần-0 áp dụng ở đây
	bằng Python (`ton_kho_theo_lo` không tự lọc, vì `doi_soat_kho` cần giữ
	nguyên để so lệch với vế còn lại).
	"""
	ton = ton_kho_theo_lo(kho)
	return [
		{"vat_tu": vat_tu, "so_lo": so_lo or None, "so_luong": flt(sl)}
		for (vat_tu, so_lo), sl in ton.items()
		if abs(flt(sl)) > NGUONG_SAI_SO
	]


@frappe.whitelist()
def xem_truoc(kho) -> dict:
	"""Liệt kê những gì việc bật SẼ ghi. Không ghi gì cả."""
	_kiem_tra_quyen("xem")
	_kiem_tra_kho(kho)
	dong = _ton_hien_co(kho)

	canh_bao = []
	khong_lo = [d for d in dong if not d["so_lo"]]
	if khong_lo:
		canh_bao.append(
			_('{0} dòng là hàng không quản lý lô — sẽ vào ô "Chưa xếp vị trí" không kèm số lô.').format(
				len(khong_lo)
			)
		)
	am = [d for d in dong if d["so_luong"] < 0]
	if am:
		# VÒNG SỬA (review advisor, sau Critical 1b): câu cũ hứa "sẽ mang số
		# âm ngay từ đầu" — tức BẬT VẪN THÀNH CÔNG, chỉ để lại một ô âm. Từ
		# khi doi_soat_kho() đòi thêm `o_am` sạch mới `khop` (Critical 1b),
		# ô CHUA-XEP mang số âm đó tự làm `khop=False` ngay trong chính lần
		# `bat()` này (kiểm tra ngay sau `dung_lai_ton_vi_tri`) — BẬT SẼ
		# THẤT BẠI (frappe.throw, rollback sạch), không còn "thành công với
		# một ô âm" như trước. Câu cảnh báo cũ vì vậy đã SAI so với hành vi
		# thật — đúng loại lệch giữa "điều màn hình nói" và "điều máy làm"
		# mà cả đợt review này được lập ra để đóng.
		canh_bao.append(
			_(
				"{0} dòng đang có tồn ÂM. BẬT SẼ THẤT BẠI nếu không xử lý tồn âm "
				"trước — từ khi có kiểm tra ô âm, hệ thống không còn cho phép ô "
				'"Chưa xếp vị trí" mang số âm ngay từ đầu.'
			).format(len(am))
		)

	return {
		"kho": kho,
		"so_dong": len(dong),
		"so_lo": len({d["so_lo"] for d in dong if d["so_lo"]}),
		"so_mat_hang": len({d["vat_tu"] for d in dong}),
		"canh_bao": canh_bao,
		"dong": dong,
	}


@frappe.whitelist()
def bat(kho) -> dict:
	"""Bật quản lý vị trí cho một kho.

	Chạy trong MỘT giao dịch: đối soát cuối cùng mà lệch thì huỷ sạch. Không
	có trạng thái bật nửa vời — một kho bật dở dang thì mọi con số sau đó vô
	nghĩa mà vẫn trông như đang chạy.

	Kiểm quyền là DÒNG ĐẦU TIÊN, trước cả `_kiem_tra_kho` — xem docstring
	module. `_kiem_tra_quyen` dùng lại nguyên hàm của Task 11 (bộ vai trò
	`System Manager` + `Stock Manager`, KHÔNG có `Stock User`: bật/tắt là
	thao tác thiết lập, không phải vận hành hằng ngày).
	"""
	_kiem_tra_quyen("bật")
	_kiem_tra_kho(kho)
	dong = _ton_hien_co(kho)
	diem_luu = "truoc_khi_bat"
	frappe.db.savepoint(diem_luu)

	# Ngoài vòng lặp (vòng sửa 1, Q7): trước đây gọi `frappe.db.get_value`
	# BÊN TRONG vòng lặp 103 dòng — company của một kho không đổi giữa
	# các dòng chuyển đổi cùng một lần `bat()`, nên đó là 103 truy vấn dư
	# thừa cho cùng một giá trị.
	company = frappe.db.get_value("Warehouse", kho, "company")

	o = None
	try:
		o = tao_o_chua_xep(kho)

		# LỆCH SO VỚI BRIEF (Bước 3): `chung_tu` của `Location Ledger Entry`
		# là Dynamic Link theo `chung_tu_type` = "Warehouse Location Setup".
		# Brief gốc ghi sổ (chung_tu=kho) TRƯỚC khi tạo bản ghi
		# `Warehouse Location Setup`, nên `_validate_links()` của Frappe
		# ném `LinkValidationError: Could not find Chứng từ` ngay dòng sổ
		# đầu tiên — lỗi thật, tái hiện được (xem báo cáo Task 12). Dựng
		# trước bản ghi chứng từ (trạng thái tạm "Chưa bật", chỉ có
		# `o_chua_xep`) rồi ghi đè đủ trường bằng `_ghi_setup` lần thứ hai
		# sau khi đối soát khớp — cùng chứng từ nằm trong CÙNG giao dịch
		# nên đối soát lệch vẫn rollback sạch cả hai lần ghi.
		_ghi_setup(kho, {"o_chua_xep": o})

		luc = now_datetime()
		for d in dong:
			ghi_dong_so(
				o=o,
				kho=kho,
				vat_tu=d["vat_tu"],
				so_lo=d["so_lo"],
				so_luong=d["so_luong"],
				chung_tu_type=CHUNG_TU_CHUYEN_DOI,
				chung_tu=kho,
				chung_tu_row="chuyen-doi",
				sle=None,
				ngay=nowdate(),
				thoi_diem=luc,
				company=company,
			)

		dung_lai_ton_vi_tri(kho)

		kq = doi_soat_kho(kho)
		if not kq["khop"]:
			frappe.throw(
				_("Bật quản lý vị trí thất bại: {0}. Kho được giữ nguyên như trước.").format(
					_mo_ta_loi_doi_soat(kq)
				)
			)

		frappe.db.set_value("Warehouse", kho, "custom_quan_ly_vi_tri", 1)
		xoa_cache_kho(kho)
		_ghi_setup(
			kho,
			{
				"trang_thai": "Đang bật",
				"o_chua_xep": o,
				"ngay_bat": luc,
				"ngay_tat": None,
				"so_dong_chuyen_doi": len(dong),
				"so_lo_chuyen_doi": len({d["so_lo"] for d in dong if d["so_lo"]}),
				"lan_doi_soat_cuoi": luc,
				"ket_qua_doi_soat": _("Khớp"),
			},
		)

	except Exception:
		# Bước 4 brief cảnh báo `Storage Location` là nested set nên
		# `insert` "có thể commit ngầm" — bản trước của hàm này XOÁ tường
		# minh `Storage Location` ở đây làm "lưới an toàn" trước khi
		# rollback. VÒNG SỬA 1 (review điều phối, Q1): đã XOÁ khối đó —
		# nó vô tác dụng ở cả hai kịch bản và CÓ HẠI ở kịch bản thứ hai.
		#
		# Đã đọc `frappe/utils/nestedset.py` để xác minh, không suy đoán:
		# đường đi của MỘT node lá mới (không `lft`/`rgt`) là
		# `update_add_node`, chỉ dùng `frappe.qb...run()` — không COMMIT.
		# `auto_commit_on_many_writes` (thứ duy nhất có thể gây commit
		# ngầm trong module này) chỉ được bật trong `rebuild_tree`
		# (nestedset.py:198/203), hàm `bat()` không gọi tới. Vậy:
		#   - Kịch bản THƯỜNG (không commit ngầm): lệnh xoá nằm SAU
		#     savepoint nên bị chính `rollback` bên dưới cuốn đi ngay —
		#     vô tác dụng, chỉ là một câu SQL dư.
		#   - Kịch bản XOÁ ĐỊNH PHÒNG (có commit ngầm xảy ra): COMMIT huỷ
		#     MỌI savepoint hiện có trong MariaDB. Lúc đó `rollback(save_
		#     point=diem_luu)` ngay dòng dưới ném lỗi SQL 1305 "SAVEPOINT
		#     does not exist" TỪ BÊN TRONG khối except — che mất ngoại lệ
		#     gốc (lệch đối soát hay lỗi khác) và trả cho người dùng một
		#     lỗi SQL thô thay vì thông báo tiếng Việt của `frappe.throw`
		#     phía trên. Tệ hơn tình huống nó định phòng.
		# Nói cách khác: nó không phòng được đúng cái nó nói phòng.
		frappe.db.rollback(save_point=diem_luu)
		xoa_cache_kho(kho)
		raise

	return {
		"kho": kho,
		"so_dong": len(dong),
		"so_lo": len({d["so_lo"] for d in dong if d["so_lo"]}),
		"o_chua_xep": o,
		"doi_soat": kq,
	}


def tao_o_chua_xep(kho) -> str:
	"""Tạo (hoặc tái dùng) ô CHUA-XEP của kho. Trả mã ô.

	ĐÂY LÀ CÁCH DUY NHẤT ĐƯỢC PHÉP tạo ô hệ thống — kể cả trong test.
	Hàm công khai (bỏ tiền tố `_`) chính vì lý do đó, không phải vì có ai
	ngoài module này cần gọi lúc chạy thật.

	Vì sao phải cưỡng chế: bốn chỗ trong bộ test từng tự `insert()` một ô
	`la_o_chua_xep=1` bằng tay và KHÔNG đặt `thu_tu_lay_hang`, nên ô test
	nhận mặc định 0 (lấy ĐẦU TIÊN) trong khi ô thật ở đây là 9999 (lấy SAU
	CÙNG). Một bài FEFO đã khoá đúng chiều ngược lại suốt nhiều tháng và
	vẫn xanh, vì nó tự dựng một thế giới mà production không bao giờ sinh
	ra. Chỉ lộ khi kho thật được bật (10/09/2026). Test gọi hàm này thì
	lệch đó không tái diễn được.

	VÒNG SỬA 1 (review điều phối, Q6): trước đây, nếu ĐÃ có một bản ghi
	`Storage Location` trùng mã (`ma_o_chua_xep(kho)`), hàm nhận bừa và
	coi đó là ô CHUA-XEP hợp lệ — không kiểm `kho`, `la_o_chua_xep`,
	`is_group`, `disabled`. `la_o_chua_xep` là field `read_only` trên
	form nên KHÔNG chặn được việc ai đó tạo tay (qua Data Import, API,
	hay đơn giản đặt trùng mã) một ô cùng tên nhưng thiếu cờ đó. Hậu quả
	IM LẶNG: `bat()` vẫn đổ toàn bộ tồn hiện có vào ô sai dạng này, và
	mọi logic lọc theo `la_o_chua_xep` (vd FEFO ở các task sau) sẽ không
	nhận ra đây là ô gom hàng chưa xếp — hàng "biến mất" khỏi luồng lấy
	hàng bình thường mà không có lỗi nào báo. Chặn tường minh: bản ghi có
	sẵn phải đúng kho, đúng cờ `la_o_chua_xep`, không phải nhóm, không bị
	vô hiệu hoá; sai một trong số đó thì báo lỗi tiếng Việt thay vì âm
	thầm dùng nhầm.

	CRITICAL 2 (review điều phối, vòng sau khi 147/147 bài "xong"): phép
	kiểm dạng giờ dùng CHUNG `kiem_tra_dang_o_chua_xep` (`vitri/kho.py`) với
	`o_chua_xep()` — trước đây hai nơi chép cùng một vị từ, đúng loại lệch
	mà chính hàm này được viết ra để chặn (ở tầng dữ liệu) nhưng lại để lọt
	ở tầng mã nguồn của chính module này.
	"""
	ma = ma_o_chua_xep(kho)
	if frappe.db.exists("Storage Location", ma):
		kiem_tra_dang_o_chua_xep(kho, ma)
		return ma
	frappe.get_doc(
		{
			"doctype": "Storage Location",
			"ma_o": ma,
			"ten_o": _("Chưa xếp vị trí"),
			"kho": kho,
			"cap_do": "Ô",
			"la_o_chua_xep": 1,
			# 9999 = lấy SAU CÙNG, có chủ đích. `thu_tu_lay_hang` là thứ tự đường đi
			# trong kho, mà ô này không ứng với chỗ nào ngoài kho nên không có vị trí
			# trên đường đi. Khi cùng hạn dùng, lấy từ một ô đã xếp đàng hoàng bao giờ
			# cũng hơn lấy từ đống chưa xếp: thủ kho biết đi tới đâu.
			"thu_tu_lay_hang": 9999,
		}
	).insert(ignore_permissions=True)
	return ma


def _ghi_setup(kho, gia_tri: dict):
	if frappe.db.exists("Warehouse Location Setup", kho):
		doc = frappe.get_doc("Warehouse Location Setup", kho)
	else:
		doc = frappe.get_doc({"doctype": "Warehouse Location Setup", "kho": kho})
	doc.update(gia_tri)
	doc.save(ignore_permissions=True)


@frappe.whitelist()
def tat(kho) -> dict:
	"""Ngừng ghi sổ vị trí cho kho. Sổ cũ giữ nguyên, không xoá dòng nào.

	`tat()` GHI dữ liệu (đổi cờ `Warehouse`, đổi trạng thái) — kiểm quyền
	là dòng đầu tiên, cùng lý do và cùng bộ vai trò đã áp dụng cho `bat()`
	(xem docstring module và `_kiem_tra_quyen`).
	"""
	_kiem_tra_quyen("tắt")
	_kiem_tra_kho(kho, cho_phep_da_bat=True)
	if not kho_co_quan_ly_vi_tri(kho):
		frappe.throw(_("Kho {0} chưa bật quản lý vị trí.").format(kho))

	frappe.db.set_value("Warehouse", kho, "custom_quan_ly_vi_tri", 0)
	xoa_cache_kho(kho)
	_ghi_setup(kho, {"trang_thai": "Đã tắt", "ngay_tat": now_datetime()})
	return {"kho": kho, "trang_thai": "Đã tắt"}


@frappe.whitelist()
def dong_bo_lai(kho) -> dict:
	"""So tồn vị trí với tồn kho, phần chênh ghi bù vào CHUA-XEP.

	Ghi THÊM bút toán bù, không sửa và không xoá dòng cũ — sổ vẫn chỉ ghi
	thêm. Dùng cho hai tình huống: bật lại sau khi tắt, và khi đối soát báo
	lệch mà chưa rõ nguyên nhân.

	Kiểm quyền là dòng đầu tiên — hàm này còn GHI NHIỀU hơn `tat()` (thêm
	dòng sổ bù), cùng lý do đã áp dụng cho `bat()`/`tat()`.

	CRITICAL 1b (review điều phối, sau khi 147/147 bài "xong") — QUYẾT ĐỊNH
	CÓ Ý THỨC, không phải tác dụng phụ: `doi_soat_kho` giờ đòi CẢ BA phép đo
	sạch mới `khop`. Bút toán bù ở đây CHỈ sửa được lớp `dong_lech` (chênh
	TỔNG so với Bin) — nó KHÔNG thể sửa một ô đang âm (`o_am`) hay bộ đệm
	trôi khỏi sổ (`lech_bo_dem`), vì ghi thêm vào CHUA-XEP không đụng tới ô
	bị hỏng hay quan hệ bộ đệm↔sổ. Có hai lựa chọn: (a) giữ nguyên gate
	`kq["khop"]` — hàm tiếp tục THẤT BẠI nếu kho còn `o_am`/`lech_bo_dem`,
	dù đã bù xong `dong_lech`; (b) nới gate về chỉ còn `dong_lech` (khôi
	phục đúng phạm vi brief gốc). Chọn (a): một kho có ô âm hay bộ đệm trôi
	khỏi sổ đang mang một VẤN ĐỀ DỮ LIỆU thật sự — để `dong_bo_lai()` báo
	"đồng bộ xong, khớp" trong tình huống đó là ĐÚNG CÁI SAI mà Critical 1
	vừa lộ ra (đối soát báo khớp trong khi có gì đó thật sự hỏng). Người vận
	hành cần biết còn vấn đề CHƯA sửa được bằng thao tác này, không phải một
	xác nhận giả. Hệ quả: `dong_bo_lai()` trên một kho có ô âm/bộ đệm lệch
	từ TRƯỚC (không do chính lần đồng bộ này gây ra) sẽ LUÔN throw — không
	còn là lối thoát vận hành cho MỌI tình huống lệch như trước Critical 1b;
	thông báo phải nói RÕ đó là vấn đề gì để người vận hành biết cần xử lý gì
	tiếp (không phải chạy lại chính RPC này). Khoá bằng
	`test_tat_va_dong_bo.TestDongBoLaiOAmKhongTuSua`.
	"""
	_kiem_tra_quyen("đồng bộ lại")
	_kiem_tra_kho(kho, cho_phep_da_bat=True)
	_kiem_tra_da_tung_bat(kho)

	o = tao_o_chua_xep(kho)
	lech = doi_soat_kho(kho)["dong_lech"]
	luc = now_datetime()
	company = frappe.db.get_value("Warehouse", kho, "company")

	for d in lech:
		bu = flt(d["ton_kho"]) - flt(d["ton_vi_tri"])
		if not bu:
			continue
		ghi_dong_so(
			o=o,
			kho=kho,
			vat_tu=d["vat_tu"],
			so_lo=d["so_lo"],
			so_luong=bu,
			chung_tu_type=CHUNG_TU_CHUYEN_DOI,
			chung_tu=kho,
			chung_tu_row="dong-bo-lai",
			sle=None,
			ngay=nowdate(),
			thoi_diem=luc,
			company=company,
		)

	kq = doi_soat_kho(kho)
	if not kq["khop"]:
		frappe.throw(
			_(
				"Đồng bộ lại đã ghi bù xong phần chênh tổng, nhưng vẫn còn: {0}. "
				'Bút toán bù vào "Chưa xếp vị trí" KHÔNG sửa được ô âm hay bộ đệm '
				"trôi khỏi sổ — cần kiểm tra dữ liệu trực tiếp (vd. Dựng lại tồn vị "
				"trí) trước khi thử lại."
			).format(_mo_ta_loi_doi_soat(kq))
		)

	frappe.db.set_value("Warehouse", kho, "custom_quan_ly_vi_tri", 1)
	xoa_cache_kho(kho)
	_ghi_setup(
		kho,
		{
			"trang_thai": "Đang bật",
			"o_chua_xep": o,
			# Việc (A) (review điều phối, sau khi 147/147 bài "xong"): trước đây
			# chỉ đổi trang_thai — Warehouse Location Setup là ĐIỂM ĐIỀU KHIỂN
			# DUY NHẤT (docstring module), nên nó phải hiện đúng con số của LẦN
			# ĐỒNG BỘ NÀY, không phải giữ nguyên ngày tắt cũ và số dòng của lần
			# bật ĐẦU TIÊN cạnh trạng thái "Đang bật" mới — đọc vào trông như
			# vừa mới bật với đúng dữ liệu cũ, sai cả hai.
			"ngay_bat": luc,
			"ngay_tat": None,
			"so_dong_chuyen_doi": len(lech),
			"so_lo_chuyen_doi": len({d["so_lo"] for d in lech if d["so_lo"]}),
			"lan_doi_soat_cuoi": luc,
			"ket_qua_doi_soat": _("Khớp sau khi đồng bộ lại"),
		},
	)

	return {"kho": kho, "so_dong_bu": len(lech), "doi_soat": kq}
