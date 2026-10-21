"""Phiếu nhập lô — khai số lô và HSD cho từng dòng phiếu nhập (spec khối C §5).

VÌ SAO LÀ PHIẾU RIÊNG chứ không phải sửa hộp thoại lô sẵn có của ERPNext: chủ
đầu tư chốt 16/09/2026. Cái giá đã biết và đã chấp nhận — hộp thoại cũ vẫn mở
được và vẫn tạo được lô không tem; §4.3 vá phần dữ liệu, phần số lô máy sinh thì
là lựa chọn nghiệp vụ.

VÌ SAO GHI `batch_no` LÊN DÒNG PHIẾU NHẬP thay vì tự dựng `Serial and Batch
Bundle`: một trường, không có gì khác. Tự dựng bundle là bám vào nội bộ một hệ
thống đã đổi kiến trúc lô một lần giữa v14 và v15 — và sẽ đổi nữa.

ĐÃ ĐO TRÊN erptest.local (16/09/2026), không phải suy từ mã:

    A. sau frappe.db.set_value  batch_no = 'PROBE-LO-001'
    B. sau reload + save (nháp) batch_no = 'PROBE-LO-001'   <- KHÔNG bị xoá
    C. sau submit phiếu nhập    batch_no = 'PROBE-LO-001'
       số Batch của mặt hàng    1 -> 1                      <- KHÔNG sinh lô máy
       bundle                   docstatus 1, dòng con {batch_no: PROBE-LO-001, qty: 10}
    E. scan_barcode('PROBE-LO-001') -> {batch_no, item_code, has_batch_no}

Điểm B là điểm phải đo: `frappe.db.set_value` đi thẳng xuống CSDL, không qua bản
sao trong bộ nhớ. Nếu ai đó mở phiếu nháp ra lưu lại giữa lúc ta ghi và lúc
submit, một bản sao cũ có thể ghi đè `batch_no` về rỗng — và lô của NCC mất mà
không có lỗi nào báo. Đo cho thấy KHÔNG xảy ra. Nếu một bản ERPNext sau này đổi
điều đó, `test_phieu_nhap_submit_sau_do_khong_sinh_lo_may_nao_nua` sẽ đỏ.

Đáng ghi lại: sau submit `use_serial_batch_fields` vẫn bằng 0, tức bundle được
dựng bằng một nhánh KHÁC nhánh `stock_controller.py:231-234`. Không cần biết
nhánh nào — đừng viết mã dựa trên nó. Thứ ràng buộc là KẾT QUẢ đo được ở trên,
và bài test khoá đúng kết quả đó.
"""

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname

#: Tiền tố chỉ để `make_autoname` có khoá đếm riêng; nó bị cắt khỏi giá trị lưu.
_SERIES_SO_GOI = "SOGOI-.####"

#: Mã lô tự sinh — `L26-000123` (anh chốt 19/10/2026). Luôn 10 ký tự nên vừa mã
#: vạch trên tem 50×30, bất kể số lô NCC dài bao nhiêu. Đặt ở đây chứ không dựa
#: vào `Item.batch_number_series`: lô do phiếu nhập lô tạo phải CÙNG một mẫu, không
#: tuỳ cấu hình từng mặt hàng.
_SERIES_MA_LO = "L.YY.-.######"


def _sinh_so_goi() -> str:
	"""Số gọi 4 chữ số, bộ đếm TOÀN CỤC không reset theo năm.

	Không reset vì số gọi là thứ người ta đọc cho nhau qua kho. Trùng lại sau
	một năm là đủ để một câu nói trỏ vào hai thùng hàng khác nhau.

	Vượt 9999 thì số thành 5 chữ số — nhãn phải co cỡ chữ (§6.4), KHÔNG được cắt
	bớt số.
	"""
	return make_autoname(_SERIES_SO_GOI).removeprefix("SOGOI-")


def _so_goi_tu_phieu_nhap(phieu_nhap: str) -> str:
	"""Số gọi = phần SỐ CUỐI của tên phiếu nhập: `MAT-PRE-2026-00027` -> `00027`.

	Chủ đầu tư chốt 14/10/2026: số gọi phải là số của phiếu nhập, để thủ kho
	đọc số trên tem là biết hàng về theo phiếu nào. Mọi lô của CÙNG một phiếu
	nhập vì thế mang chung một số gọi; hai phiếu khác nhau thì khác số.

	Giữ nguyên số 0 đứng đầu — đó là đúng chuỗi in trên phiếu nhập. Phiếu sửa
	(`amended_from`) mang hậu tố `-1`, `-2`… sau số gốc: bỏ hậu tố đó để số gọi
	vẫn là số của phiếu gốc. Tên không kết thúc bằng chữ số (series tuỳ biến
	lạ) thì lui về bộ đếm cũ `_sinh_so_goi` chứ không để trống ô to nhất trên tem.
	"""
	goc = phieu_nhap
	if frappe.db.get_value("Purchase Receipt", phieu_nhap, "amended_from"):
		goc = phieu_nhap.rsplit("-", 1)[0]
	m = re.search(r"(\d+)$", goc)
	return m.group(1) if m else _sinh_so_goi()


class BatchEntry(Document):
	def validate(self):
		# Thứ tự này là một phần của spec (§5.5), không phải chi tiết cài đặt:
		# câu báo lỗi ĐẦU TIÊN người dùng thấy phải chỉ đúng chỗ sai.
		self.kiem_tra_phieu_nhap_con_nhap()
		self.kiem_tra_dong_thuoc_phieu()
		self.kiem_tra_dong_chua_bi_be_khac_phu()
		self.kiem_tra_so_lo()
		self.kiem_tra_ngay()

	def kiem_tra_phieu_nhap_con_nhap(self):
		trang_thai = frappe.db.get_value("Purchase Receipt", self.phieu_nhap, "docstatus")
		if trang_thai != 0:
			frappe.throw(
				_(
					"Phiếu nhập {0} đã duyệt nên không gắn được số lô nữa. Phải nhập lô "
					"TRƯỚC rồi mới duyệt phiếu nhập — duyệt trước thì ERPNext đã tự sinh "
					"số lô máy và số lô của nhà cung cấp mất luôn."
				).format(self.phieu_nhap)
			)

	def kiem_tra_dong_thuoc_phieu(self):
		"""Mỗi dòng phiếu nhập xuất hiện đúng một lần, và phải là dòng của ĐÚNG
		phiếu đang chọn.

		Vế thứ hai không thừa: không có nó thì một `dong_phieu_nhap` chép nhầm từ
		phiếu khác sẽ khiến `on_submit` ghi `batch_no` lên một chứng từ không
		liên quan — sửa dữ liệu của người khác, im lặng.
		"""
		hop_le = set(
			frappe.get_all(
				"Purchase Receipt Item",
				filters={"parent": self.phieu_nhap},
				pluck="name",
			)
		)
		da_thay = set()
		for d in self.items:
			if d.dong_phieu_nhap not in hop_le:
				frappe.throw(
					_("Dòng {0}: dòng hàng không thuộc phiếu nhập {1}.").format(
						d.idx, self.phieu_nhap
					)
				)
			if d.dong_phieu_nhap in da_thay:
				frappe.throw(
					_(
						"Dòng {0}: mỗi dòng phiếu nhập chỉ nhận MỘT số lô. Hàng về hai lô "
						"thì tách dòng trên phiếu nhập — tách rồi số lượng theo từng lô "
						"cũng đúng luôn trên chứng từ."
					).format(d.idx)
				)
			da_thay.add(d.dong_phieu_nhap)

	def kiem_tra_dong_chua_bi_be_khac_phu(self):
		"""Một dòng phiếu nhập chỉ được đúng MỘT `Batch Entry` ĐÃ DUYỆT phủ lên.

		`kiem_tra_dong_thuoc_phieu` chỉ khử trùng TRONG một `Batch Entry` này —
		không thấy được xung đột GIỮA hai `Batch Entry` khác nhau. Kịch bản thật
		(vòng sửa 1, Việc 5): BE1 duyệt ghi `LO-A` lên dòng X; ai đó tạo BE2 ghi
		`LO-B` lên CHÍNH dòng X đó rồi duyệt tiếp — huỷ BE2 sau đó sẽ xoá trắng
		`batch_no` của dòng X, làm tem `LO-A` (do BE1 tạo, có thể đã dán lên
		thùng hàng) thành mồ côi, và khi phiếu nhập duyệt ERPNext tự sinh một lô
		máy thay thế — đúng thứ cả khối C sinh ra để tránh.
		"""
		for d in self.items:
			be_khac = frappe.db.get_value(
				"Batch Entry Item",
				{
					"dong_phieu_nhap": d.dong_phieu_nhap,
					"docstatus": 1,
					"parent": ["!=", self.name or ""],
				},
				"parent",
			)
			if be_khac:
				frappe.throw(
					_(
						"Dòng {0}: dòng hàng này đã được phiếu nhập lô {1} (đã duyệt) khai "
						"số lô rồi. Huỷ {1} trước nếu muốn khai lại."
					).format(d.idx, be_khac)
				)

	def kiem_tra_so_lo(self):
		for d in self.items:
			d.so_lo = (d.so_lo or "").strip()
			if not d.so_lo:
				frappe.throw(_("Dòng {0}: chưa có số lô.").format(d.idx))
			# Không còn kiểm ký tự/độ dài theo mã vạch, cũng không chặn số lô đã
			# thuộc mặt hàng khác (spec tách số lô 19/10/2026): mã vạch giờ in MÃ
			# LÔ tự sinh, còn số lô NCC được trùng giữa các mặt hàng — hai mặt hàng
			# chung số lô là chuyện thật, gặp nhiều lần.

	def kiem_tra_ngay(self):
		for d in self.items:
			if d.ngay_san_xuat and d.hsd and d.hsd < d.ngay_san_xuat:
				frappe.throw(
					_("Dòng {0}: hạn dùng {1} trước ngày sản xuất {2}.").format(
						d.idx, d.hsd, d.ngay_san_xuat
					)
				)

	def on_submit(self):
		for d in self.items:
			lo = self._dam_bao_lo(d)
			d.db_set("lo_da_tao", lo.name, update_modified=False)
			d.db_set("so_goi", lo.custom_so_goi, update_modified=False)
			# `db_set` trên dòng chứng từ NHÁP: `Purchase Receipt` chưa submit nên
			# sửa hợp lệ, và đi thẳng xuống DB để không kích lại `validate` của cả
			# phiếu nhập (nó sẽ tính lại thuế, tỉ giá, và có thể `throw` vì một lý
			# do không liên quan gì tới việc ta đang làm).
			frappe.db.set_value(
				"Purchase Receipt Item", d.dong_phieu_nhap, "batch_no", lo.name
			)

	def _dam_bao_lo(self, d):
		"""Trả về bản ghi `Batch` cho dòng `d` — dùng lại nếu đã có.

		Dùng lại chứ không tạo mới vì NCC giao làm hai đợt cùng một số lô là
		chuyện thật. Lô nhận diện theo (mặt hàng, số lô, HSD) — xem
		`_tim_lo_co_san`.
		"""
		ma_lo = self._tim_lo_co_san(d)
		if ma_lo:
			lo = frappe.get_doc("Batch", ma_lo)
			# Chỉ ĐIỀN CHỖ TRỐNG, không ghi đè: lô cũ có thể đã in tem với HSD cũ.
			# `supplier`/`reference_doctype`/`reference_name` vào chung vòng này
			# (vòng sửa 1, Việc 6): lô do hộp thoại lô sẵn có của ERPNext tạo có
			# thể trống cả ba trường — dùng lại lô đó qua phiếu nhập lô thì phải
			# điền, không thì "lô này của NCC nào, về theo chứng từ nào" mãi mãi
			# trả rỗng dù đã có đủ thông tin trong tay lúc này.
			doi = False
			for truong, gia_tri in (
				("expiry_date", d.hsd),
				("manufacturing_date", d.ngay_san_xuat),
				("supplier", self.nha_cung_cap),
				("reference_doctype", "Purchase Receipt"),
				("reference_name", self.phieu_nhap),
			):
				if gia_tri and not lo.get(truong):
					lo.set(truong, gia_tri)
					doi = True
			if not lo.custom_so_goi:
				lo.custom_so_goi = _so_goi_tu_phieu_nhap(self.phieu_nhap)
				doi = True
			if doi:
				lo.save(ignore_permissions=True)
			return lo

		return frappe.get_doc(
			{
				"doctype": "Batch",
				"batch_id": make_autoname(_SERIES_MA_LO),
				"custom_so_lo": d.so_lo,
				"item": d.vat_tu,
				"expiry_date": d.hsd,
				"manufacturing_date": d.ngay_san_xuat,
				"supplier": self.nha_cung_cap,
				"reference_doctype": "Purchase Receipt",
				"reference_name": self.phieu_nhap,
				"custom_so_goi": _so_goi_tu_phieu_nhap(self.phieu_nhap),
			}
		).insert(ignore_permissions=True)

	def _tim_lo_co_san(self, d) -> str | None:
		"""Mã lô đã có cho (mặt hàng, số lô, HSD) của dòng `d`, hoặc None.

		Anh chốt 19/10/2026: cùng mặt hàng + số lô + HSD là MỘT lô; khác HSD
		thì tách lô mới; khác NCC vẫn là một lô. HSD rỗng coi như một giá trị.

		Ngoại lệ (E1): không có lô đúng HSD mà có ĐÚNG MỘT lô cùng mặt hàng +
		số lô CHƯA có HSD (lô cũ, tạo trước khi khai HSD) thì dùng lại lô đó —
		nhánh "chỉ điền chỗ trống" của `_dam_bao_lo` điền HSD vào. Không vậy
		một lô thật bị tách đôi, sai FEFO, sai truy vết thu hồi, sai kiểm kê.

		Nhiều hơn một lô khớp là dữ liệu đã lệch — báo, không đoán.
		"""
		dieu_kien = {"item": d.vat_tu, "custom_so_lo": d.so_lo}
		lan_tim = [d.hsd or ("is", "not set")]
		if d.hsd:
			lan_tim.append(("is", "not set"))
		for hsd in lan_tim:
			ds = frappe.get_all("Batch", filters={**dieu_kien, "expiry_date": hsd}, pluck="name")
			if len(ds) > 1:
				frappe.throw(
					_(
						"Dòng {0}: mặt hàng {1} có {2} lô cùng số lô '{3}' ({4}) — không biết "
						"dùng lô nào. Báo quản trị gộp hoặc sửa các lô đó trước."
					).format(d.idx, d.vat_tu, len(ds), d.so_lo, ", ".join(ds))
				)
			if ds:
				return ds[0]
		return None

	def on_cancel(self):
		trang_thai = frappe.db.get_value("Purchase Receipt", self.phieu_nhap, "docstatus")
		# CHỈ chặn khi phiếu nhập đang Ở TRẠNG THÁI ĐÃ DUYỆT (1). Phiếu ĐÃ HUỶ
		# (2) hoặc không còn (None — đã bị xoá) thì PHẢI cho huỷ phiếu nhập lô —
		# đó chính là đường thoát khi cả hai chứng từ cùng cần huỷ (vòng sửa 1,
		# Việc 1: NCC giao sai, kế toán huỷ PR trước, thủ kho huỷ BE sau).
		# `PurchaseReceipt.on_cancel` tự gỡ `batch_no` về rỗng qua
		# `delete_auto_created_batches()` (đã xác minh: KHÔNG xoá bản ghi
		# `Batch`, chỉ đặt `batch_no`/`serial_and_batch_bundle` = None trên
		# dòng), nên tới đây mà phiếu đã huỷ thì `batch_no` vốn đã rỗng sẵn —
		# vòng gỡ dưới đây chỉ là vô hại, không phải việc chính của nhánh này.
		if trang_thai == 1:
			frappe.throw(
				_(
					"Phiếu nhập {0} đã duyệt nên không huỷ phiếu nhập lô được. Tồn đã ghi "
					"theo lô rồi — muốn gỡ thì huỷ chính phiếu nhập."
				).format(self.phieu_nhap)
			)

		for d in self.items:
			# Chỉ gỡ nếu `batch_no` ĐANG BẰNG ĐÚNG lô do CHÍNH dòng này tạo
			# (vòng sửa 1, Việc 5 — lớp phòng vệ thứ hai, độc lập với
			# `kiem_tra_dong_chua_bi_be_khac_phu`): nếu một `Batch Entry` khác
			# đã ghi đè `batch_no` bằng lô của NÓ, huỷ phiếu này không được xoá
			# giá trị của người khác. Và nếu phiếu nhập đã huỷ, giá trị hiện tại
			# thường đã là None rồi — so sánh vẫn đúng, chỉ là không làm gì.
			gia_tri_hien_tai = frappe.db.get_value(
				"Purchase Receipt Item", d.dong_phieu_nhap, "batch_no"
			)
			if gia_tri_hien_tai != d.lo_da_tao:
				continue
			# GỠ `batch_no`, GIỮ bản ghi `Batch`. Tem có thể đã in và đang dán trên
			# thùng hàng; xoá bản ghi biến tờ tem đó thành rác không tra được.
			frappe.db.set_value("Purchase Receipt Item", d.dong_phieu_nhap, "batch_no", None)
