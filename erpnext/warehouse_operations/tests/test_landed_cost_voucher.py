"""Critical 1 (review điều phối, sau khi 147/147 bài "xong") — Landed Cost
Voucher (và bất kỳ repost nào dùng cùng cơ chế) đẩy hàng vào CHUA-XEP mà
đối soát không bắt được.

Cơ chế đã đọc mã nguồn xác nhận: `erpnext/stock/doctype/landed_cost_voucher/
landed_cost_voucher.py:243-250` làm hai bước trên chứng từ NHẬP đã submit —
KHÔNG hề huỷ/nhập lại thật:

    doc.docstatus = 2
    doc.update_stock_ledger(..., via_landed_cost_voucher=True)   # bước 1
    doc.docstatus = 1
    doc.update_stock_ledger(..., via_landed_cost_voucher=True)   # bước 2

Cả hai đi qua `make_sl_entries` -> `make_entry()` -> `sle.submit()` -> hook
nổ hai lần. Bước 1 sinh SLE `is_cancelled=1`: `dao_theo_o_goc()` đảo đúng ô
gốc, cờ `da_huy=1`. Bước 2 sinh SLE `is_cancelled=0`, `so_luong > 0`: trước
Critical 1, đường thường (`_ghi_mot_phan`) dồn THẲNG vào CHUA-XEP bất kể
chứng từ gốc đã ở ô nào — hàng "di chuyển" ảo sang CHUA-XEP mà không có
thao tác kho thật nào tương ứng. TỔNG vẫn khớp Bin nên `doi_soat_kho` (bản
cũ) báo "khớp" 100% — đúng loại lỗi âm thầm mà spec §3 lập ra để phòng
nhưng lọt qua vì phép so sánh không đủ mịn (Critical 1b bổ sung hai phép đo
mới để bắt việc này từ hướng khác — xem `test_doi_soat.py`).

`erpnext/stock/doctype/repost_item_valuation/repost_item_valuation.py`
(`recreate_stock_ledger_entries`) dùng CÙNG cơ chế hai bước — không cần LCV
thật vẫn dẫm phải; vì vậy các bài dưới đây MÔ PHỎNG đúng chuỗi hai bước
(brief cho phép khi không dựng nổi LCV thật) thay vì dựng LCV đầy đủ (đòi
account/chi phí không liên quan tới cái đang thử) — gọi thẳng đúng cặp lệnh
mà `landed_cost_voucher.py` tự chạy trên chứng từ gốc.

DIỄN GIẢI QUAN TRỌNG (đã đo thực nghiệm trên erptest.local trước khi viết
bài, xem báo cáo mục "Critical 1"): với một Purchase Receipt bình thường
(GĐ2 Location Allocation CHƯA có), "ô cũ" mà `dao_theo_o_goc` tìm ra LUÔN
LÀ CHUA-XEP — vì hook hiện tại KHÔNG có cách nào khác để nhập hàng vào một
ô thật. Kết quả: nếu chỉ nhập PR bình thường rồi mô phỏng LCV, cả đường
BUGGY (dồn CHUA-XEP) lẫn đường ĐÃ SỬA (trả về "ô cũ") đều hội tụ về CHUA-XEP
— không phân biệt được, đo thực tế xác nhận điều này (xem báo cáo). Vì vậy
bài khoá chính (`test_lcv_khong_day_hang_da_xep_vao_chua_xep`) SEED một
dòng sổ vị trí tại một Ô THẬT cho ĐÚNG `chung_tu_row` của PR, mô phỏng đúng
kết quả mà GĐ2 Location Allocation sẽ tạo ra khi nó tồn tại — KHÔNG mock bất
kỳ hàm nào đang được kiểm (`dao_theo_o_goc`, `_tra_lai_o_da_dao`,
`ghi_so_vi_tri` đều chạy thật qua hook `Stock Ledger Entry.on_submit`).
Để seed được (không tạo hai dòng sổ cho cùng chung_tu_row), submit PR lúc
kho CHƯA bật quản lý vị trí (hook bỏ qua, không tự ghi CHUA-XEP), rồi bật
kho và ghi tay đúng MỘT dòng tại ô thật.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from erpnext.warehouse_operations.tests.test_hook_nhap import _bat_kho_tho, _tao_item, _tat_kho_tho
from erpnext.warehouse_operations.vitri import kho as vk
from erpnext.warehouse_operations.vitri import so

KHO = "Kho Miyano - MYN"
SUPPLIER = "hoang nam"


def _o(ma_o, thu_tu=0):
	if not frappe.db.exists("Storage Location", ma_o):
		frappe.get_doc(
			{
				"doctype": "Storage Location",
				"ma_o": ma_o,
				"kho": KHO,
				"thu_tu_lay_hang": thu_tu,
			}
		).insert(ignore_permissions=True)
	return ma_o


def _nhap_pr(item, qty, kho=KHO, rate=1000):
	pr = frappe.get_doc(
		{
			"doctype": "Purchase Receipt",
			"supplier": SUPPLIER,
			"company": "Miyano Việt Nam",
			"items": [{"item_code": item, "qty": qty, "rate": rate, "warehouse": kho}],
		}
	)
	pr.insert(ignore_permissions=True)
	pr.submit()
	return pr


def _mo_phong_lcv(pr_name):
	"""Mô phỏng đúng chuỗi hai bước `landed_cost_voucher.py:243-250` (đã đọc
	mã nguồn xác nhận, xem docstring module) — KHÔNG dựng Landed Cost
	Voucher đầy đủ (đòi tài khoản/chi phí không liên quan tới cái đang thử)
	mà gọi thẳng đúng cặp lệnh ERPNext tự chạy trên chứng từ gốc."""
	doc = frappe.get_doc("Purchase Receipt", pr_name)
	doc.docstatus = 2
	doc.update_stock_ledger(allow_negative_stock=True, via_landed_cost_voucher=True)
	doc.docstatus = 1
	doc.make_bundle_using_old_serial_batch_fields(via_landed_cost_voucher=True)
	doc.update_stock_ledger(allow_negative_stock=True, via_landed_cost_voucher=True)


class TestLcvKhongDayHangVaoChuaXep(FrappeTestCase):
	def setUp(self):
		_tat_kho_tho(KHO)  # PR submit lúc kho CHƯA bật — xem docstring module
		self.item = _tao_item("_Test WMS LCV")
		self.o_gan = _o("9Z22010101", thu_tu=1)

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_lcv_khong_day_hang_da_xep_vao_chua_xep(self):
		pr = _nhap_pr(self.item, 10)
		row_name = pr.items[0].name
		self.assertEqual(
			frappe.db.count("Location Ledger Entry", {"chung_tu": pr.name}),
			0,
			"tiền đề: kho chưa bật lúc PR submit nên hook chưa ghi dòng nào",
		)

		_bat_kho_tho(KHO)
		# Seed đúng MỘT dòng sổ vị trí tại o_gan cho chung_tu_row của PR —
		# mô phỏng kết quả GĐ2 Location Allocation sẽ tạo ra. Không mock.
		so.ghi_dong_so(
			o=self.o_gan,
			kho=KHO,
			vat_tu=self.item,
			so_lo=None,
			so_luong=10,
			chung_tu_type="Purchase Receipt",
			chung_tu=pr.name,
			chung_tu_row=row_name,
			sle=None,
			ngay="2026-09-01",
			thoi_diem="2026-09-01 08:30:00",
			company="Miyano Việt Nam",
		)
		self.assertEqual(so.ton_o(self.o_gan, self.item, None), 10, "tiền đề: đã seed vào o_gan")

		_mo_phong_lcv(pr.name)

		self.assertEqual(
			so.ton_o(self.o_gan, self.item, None),
			10,
			"hàng phải Ở LẠI o_gan sau LCV — Critical 1: nếu hook dồn nhầm vào "
			"CHUA-XEP, o_gan sẽ về 0 trong khi tổng vẫn khớp Bin (đối soát cũ "
			"không bắt được), đúng khiếm khuyết review chỉ ra. ĐÃ ĐO: bài này ĐỎ "
			"trước khi sửa (o_gan về 0.0, CHUA-XEP thành 10.0) — xem báo cáo.",
		)
		self.assertEqual(
			so.ton_o(vk.o_chua_xep(KHO), self.item, None),
			0,
			"CHUA-XEP không được nhận thêm hàng từ LCV",
		)

		bin_qty = frappe.db.get_value("Bin", {"item_code": self.item, "warehouse": KHO}, "actual_qty")
		self.assertEqual(flt(bin_qty), 10, "tiền đề: LCV không đổi số lượng, chỉ đổi giá vốn")
		self.assertEqual(so.tong_ton_vi_tri(KHO, self.item, None), 10, "bất biến §3 vẫn đúng ở TỔNG")

	def test_huy_that_su_sau_lcv_van_tra_dung_o(self):
		"""Chứng minh sửa 1a KHÔNG chỉ "không hồi quy" mà còn GHÉP ĐÚNG vào
		đường huỷ thật: dòng mà `_tra_lai_o_da_dao` ghi lại mang `da_huy=0`
		(mặc định) nên một lần HUỶ THẬT của PR sau đó phải tìm thấy đúng nó
		qua `dao_theo_o_goc` và trả hàng về lại o_gan — không rơi xuống
		CHUA-XEP như thể chưa từng có dòng gốc nào."""
		pr = _nhap_pr(self.item, 10)
		row_name = pr.items[0].name
		_bat_kho_tho(KHO)
		so.ghi_dong_so(
			o=self.o_gan,
			kho=KHO,
			vat_tu=self.item,
			so_lo=None,
			so_luong=10,
			chung_tu_type="Purchase Receipt",
			chung_tu=pr.name,
			chung_tu_row=row_name,
			sle=None,
			ngay="2026-09-01",
			thoi_diem="2026-09-01 08:30:00",
			company="Miyano Việt Nam",
		)

		_mo_phong_lcv(pr.name)
		self.assertEqual(so.ton_o(self.o_gan, self.item, None), 10, "tiền đề: sau LCV vẫn ở o_gan")

		pr.reload()
		pr.cancel()

		self.assertEqual(
			so.ton_o(self.o_gan, self.item, None),
			0,
			"huỷ THẬT sau LCV phải trả hàng về 0 tại o_gan — dòng do 1a ghi lại "
			"(da_huy=0) phải được dao_theo_o_goc tìm thấy và đảo đúng, không bị "
			"coi là 'chưa từng có dòng gốc'",
		)
		bin_qty = frappe.db.get_value("Bin", {"item_code": self.item, "warehouse": KHO}, "actual_qty")
		self.assertEqual(flt(bin_qty), 0, "tiền đề: ERPNext đã đưa tồn kho về 0 sau huỷ PR")
		self.assertEqual(so.tong_ton_vi_tri(KHO, self.item, None), 0, "bất biến §3 vẫn đúng sau huỷ")
