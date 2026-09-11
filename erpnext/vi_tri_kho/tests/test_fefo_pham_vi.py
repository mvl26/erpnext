"""Phạm vi của cờ `disabled`: tắt một nút thì tắt CẢ NHÁNH dưới nó.

Trước Task 4, `fefo.py` chỉ kiểm `disabled` của CHÍNH ô lá. Người vận hành
tắt cả một dãy để sửa kệ, hệ vẫn thản nhiên rút hàng từ dãy đó — và không có
gì báo: đối soát (§3) vẫn khớp vì tổng tồn không đổi, chỉ có người leo lên
đúng cái kệ đang tháo mới biết. Lỗi im lặng hoàn toàn.

HAI CHIỀU, không phải một. `fefo.py` dùng `disabled` ở hai truy vấn chạy
ngược nhau: truy vấn CHỌN ỨNG VIÊN loại ô đã tắt, truy vấn DỰNG THÔNG BÁO
tìm đúng những ô đã tắt để nói "còn 40 đang nằm ở ô X đã ngừng dùng". Sửa
mỗi truy vấn thứ nhất thì hàng dưới một nút cha bị tắt biến mất khỏi CẢ HAI:
không được chọn, mà cũng không được nhắc tới — người dùng tắt cả dãy rồi
nhận đúng câu "thiếu hàng" vô nghĩa, không manh mối nào dẫn về dãy mình vừa
tắt. Mỗi chiều có một bài riêng ở đây, và mỗi bài đã được đột biến kiểm
chứng là ĐỎ khi mệnh đề của chiều đó bị gỡ (xem task-4-report.md).
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.vi_tri_kho.vitri import so
from erpnext.vi_tri_kho.vitri.fefo import chon_o_xuat

KHO = "Kho Miyano - MYN"


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


def _lo(ma, item, han=None):
	if not frappe.db.exists("Batch", ma):
		frappe.get_doc({"doctype": "Batch", "batch_id": ma, "item": item, "expiry_date": han}).insert(
			ignore_permissions=True
		)
	return ma


def _dam_bao_item(ma_item):
	if not frappe.db.exists("Item", ma_item):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": ma_item,
				"item_name": ma_item,
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"has_batch_no": 1,
			}
		).insert(ignore_permissions=True)
	return ma_item


def _dam_bao_ton(o, vat_tu, so_lo, sl):
	"""Ghi sổ cho ĐỦ `sl` ở ô đó — chỉ phần còn thiếu.

	`FrappeTestCase` rollback theo LỚP, không theo bài (xem docstring
	`test_fefo.py::_dam_bao_item`): seed đặt trong `setUp` sẽ CỘNG DỒN qua
	từng bài nếu ghi vô điều kiện, làm bài sau thấy 20 thay vì 10. Ghi bù
	đúng phần thiếu nên gọi bao nhiêu lần cũng ra cùng một trạng thái.
	"""
	thieu = sl - so.ton_o(o, vat_tu, so_lo)
	if thieu <= 0:
		return
	so.ghi_dong_so(
		o=o,
		kho=KHO,
		vat_tu=vat_tu,
		so_lo=so_lo,
		so_luong=thieu,
		chung_tu_type="Storage Location",
		chung_tu=o,
		chung_tu_row="r",
		sle=None,
		ngay="2026-09-01",
		thoi_diem="2026-09-01 08:00:00",
		company="Miyano Việt Nam",
	)


class TestTatNutChaThiTatCaNhanh(FrappeTestCase):
	"""Ba ô, hai khu. Khu `9Z` giữ hai nhánh (dãy 01 và dãy 02); khu `9W`
	không bao giờ bị tắt và là ô ĐỐI CHỨNG — nó tồn tại để chứng minh hai
	điều mà nếu thiếu nó thì không bài nào chứng minh được:

	(a) tắt dãy 01 xong vẫn còn hàng để lấy, nên bài 1 khẳng định được "lấy
	    chỗ khác" chứ không phải "ném lỗi";
	(b) thông báo thiếu hàng KHÔNG được gọi tên nó là "ô đã ngừng dùng".
	    Thiếu (b), đột biến chiều thứ hai (gỡ mệnh đề tổ tiên khỏi truy vấn
	    dựng thông báo, để lại `1=1`) vẫn XANH: khi mọi ô có hàng đều nằm
	    dưới nút đã tắt, truy vấn `1=1` trả về ĐÚNG cùng tập ô như vị từ
	    đúng, thông báo giống hệt, không assert nào chết. Đo thật rồi mới
	    thêm ô đối chứng (xem task-4-report.md, "Đột biến chiều 2").
	"""

	def setUp(self):
		self.item = _dam_bao_item("_Test FEFO PhamVi")
		# Ô trong dãy 01 có hạn dùng GẦN NHẤT — FEFO muốn lấy nó TRƯỚC. Nhờ
		# vậy bài 1 chỉ xanh được khi cờ `disabled` của nút cha thắng cả thứ
		# tự FEFO, không phải vì tình cờ nó xếp sau.
		self.trong_day_tat = _o("9Z18010101", thu_tu=1)
		self.day_khac = _o("9Z18020101", thu_tu=2)
		self.khu_khac = _o("9W18010101", thu_tu=3)
		_dam_bao_ton(self.trong_day_tat, self.item, _lo("_T-PV-GAN", self.item, "2026-10-01"), 10)
		_dam_bao_ton(self.day_khac, self.item, _lo("_T-PV-XA", self.item, "2027-10-01"), 10)
		_dam_bao_ton(self.khu_khac, self.item, _lo("_T-PV-XA-NHAT", self.item, "2028-10-01"), 2)

	def tearDown(self):
		# Rollback theo LỚP: cờ `disabled` bài này đặt còn nguyên khi bài sau
		# chạy. Trả về 0 để mỗi bài tự dựng đúng tình huống của nó.
		for nut in ("9Z", "9Z18", "9Z1801", "9Z180101", "9W"):
			if frappe.db.exists("Storage Location", nut):
				frappe.db.set_value("Storage Location", nut, "disabled", 0)

	def test_tat_nut_day_thi_khong_lay_o_trong_day(self):
		# 9Z1801xxxx có hạn dùng GẦN HƠN, lẽ ra được ưu tiên. Tắt cả dãy 01
		# thì phải bỏ qua nó và lấy dãy 02 — dù FEFO muốn ngược lại.
		frappe.db.set_value("Storage Location", "9Z1801", "disabled", 1)
		ket = chon_o_xuat(KHO, self.item, None, 5)
		self.assertTrue(all(not d["o"].startswith("9Z1801") for d in ket), ket)

	def test_tat_nut_khu_thi_bao_ro_hang_dang_ket_o_dau(self):
		"""Khoá nửa thứ hai: thông báo thiếu hàng phải NÊU ĐÍCH DANH ô đang giữ.

		Sửa mỗi truy vấn chọn ứng viên thì hàng dưới nút cha đã tắt biến mất
		khỏi CẢ HAI câu — không được chọn, cũng không được nhắc — và người dùng
		nhận đúng câu "thiếu hàng" vô nghĩa.
		"""
		frappe.db.set_value("Storage Location", "9Z", "disabled", 1)
		with self.assertRaises(frappe.ValidationError) as ctx:
			chon_o_xuat(KHO, self.item, None, 5)
		loi = str(ctx.exception)
		self.assertIn("ngừng dùng", loi.lower())
		self.assertIn("9Z18010101", loi, "phải nêu đích danh ô đang giữ hàng")
		self.assertNotIn(
			"9W18010101",
			loi,
			"ô ở khu KHÁC, không tắt, vẫn đang dùng bình thường — gọi tên nó là "
			"'ô đã ngừng dùng' là nói sai với người vận hành",
		)
		self.assertNotIn("Traceback", loi)


class TestONgoaiCayKhongKeoNhauXuong(FrappeTestCase):
	"""Bản ghi `lft = rgt = 0` không được coi nhau là tổ tiên.

	LỆCH KHỎI BRIEF — có đo. Brief viết vị từ tổ-tiên-hoặc-chính-nó bằng
	`tt.lft <= sl.lft and tt.rgt >= sl.rgt`. Trên site này CẢ 129 bản ghi
	`Storage Location` cũ (tạo trước khi có cây, Task 2) đang mang
	`lft = rgt = 0` — KỂ CẢ ô hệ thống `ZZZ-CHUA-XEP-<kho>`, nơi đang giữ
	toàn bộ tồn của kho thật. Với `<=`/`>=`, hai bản ghi `0/0` bất kỳ thoả
	`0 <= 0 and 0 >= 0`: tắt MỘT ô cũ là mọi ô cũ khác, và ô CHUA-XEP, cùng
	biến mất khỏi ứng viên FEFO — đúng thảm hoạ "một checkbox làm đứng cả
	kho" đã ghi ở `storage_location.py::kiem_tra_khong_doi_dang_o_chua_xep`,
	lần này không chặn được bằng validate vì ô bị tắt là một ô THƯỜNG, tắt
	nó là thao tác hợp lệ. Đã đo thật trên site (xem task-4-report.md).

	Nên vị từ dùng `tt.name = sl.name or (tt.lft < sl.lft and tt.rgt >
	sl.rgt)`: CHẶT ở phần tổ tiên (một nút không bao giờ là tổ tiên THẬT SỰ
	của chính nó) và khớp chính-nó bằng tên. Bản ghi ngoài cây vì thế hành
	xử đúng như phép kiểm `sl.disabled` cũ — không thừa kế cho ai, và cũng
	không nhận thừa kế từ ai.
	"""

	def setUp(self):
		self.item = _dam_bao_item("_Test FEFO PhamVi NgoaiCay")
		self.tat = _o("9V18010101", thu_tu=1)
		self.lanh = _o("9V18010102", thu_tu=2)
		_dam_bao_ton(self.tat, self.item, None, 5)
		_dam_bao_ton(self.lanh, self.item, None, 5)
		# Ép về đúng dạng dữ liệu CŨ trên site: ngoài cây, lft = rgt = 0.
		for o in (self.tat, self.lanh):
			frappe.db.set_value("Storage Location", o, {"lft": 0, "rgt": 0}, update_modified=False)

	def test_tat_mot_o_ngoai_cay_khong_keo_theo_o_ngoai_cay_khac(self):
		frappe.db.set_value("Storage Location", self.tat, "disabled", 1)
		ket = chon_o_xuat(KHO, self.item, None, 3)
		self.assertEqual(
			ket,
			[{"o": self.lanh, "so_luong": 3}],
			"ô lành cùng dạng lft=rgt=0 phải vẫn chọn được; chỉ ô bị tắt bị loại",
		)
