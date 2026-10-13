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

from erpnext.warehouse_operations.vitri import so
from erpnext.warehouse_operations.vitri.fefo import chon_o_xuat

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
	"""Ba ô, hai khu. Khu `9Z` giữ hai DÃY khác nhau — dãy `9Z18` và dãy
	`9Z19` (mã dãy là 2 ký tự SAU mã khu: `9Z18` = khu `9Z` + dãy `18`, còn
	`9Z1801` đã là cấp KHOANG — khu `9Z` + dãy `18` + khoang `01`, xem
	`ma_vi_tri.py::TEN_CAP`); khu `9W` không bao giờ bị tắt và là ô ĐỐI
	CHỨNG — nó tồn tại để chứng minh hai điều mà nếu thiếu nó thì không bài
	nào chứng minh được:

	(a) tắt dãy `9Z18` xong vẫn còn hàng để lấy, nên bài 1 khẳng định được
	    "lấy chỗ khác" chứ không phải "ném lỗi";
	(b) thông báo thiếu hàng KHÔNG được gọi tên nó là "ô đã ngừng dùng".
	    Thiếu (b), đột biến chiều thứ hai (gỡ mệnh đề tổ tiên khỏi truy vấn
	    dựng thông báo, để lại `1=1`) vẫn XANH: khi mọi ô có hàng đều nằm
	    dưới nút đã tắt, truy vấn `1=1` trả về ĐÚNG cùng tập ô như vị từ
	    đúng, thông báo giống hệt, không assert nào chết. Đo thật rồi mới
	    thêm ô đối chứng (xem task-4-report.md, "Đột biến chiều 2").
	"""

	def setUp(self):
		self.item = _dam_bao_item("_Test FEFO PhamVi")
		# Ô trong dãy 9Z18 có hạn dùng GẦN NHẤT — FEFO muốn lấy nó TRƯỚC. Nhờ
		# vậy bài 1 chỉ xanh được khi cờ `disabled` của nút cha thắng cả thứ
		# tự FEFO, không phải vì tình cờ nó xếp sau. `day_khac` nằm ở một DÃY
		# KHÁC hẳn (`9Z19`, không phải cùng dãy khác khoang) — tắt nguyên dãy
		# `9Z18` không được kéo theo nó.
		self.trong_day_tat = _o("9Z18010101", thu_tu=1)
		self.day_khac = _o("9Z19010101", thu_tu=2)
		self.khu_khac = _o("9W18010101", thu_tu=3)
		_dam_bao_ton(self.trong_day_tat, self.item, _lo("_T-PV-GAN", self.item, "2026-10-01"), 10)
		_dam_bao_ton(self.day_khac, self.item, _lo("_T-PV-XA", self.item, "2027-10-01"), 10)
		_dam_bao_ton(self.khu_khac, self.item, _lo("_T-PV-XA-NHAT", self.item, "2028-10-01"), 2)

	def tearDown(self):
		# Rollback theo LỚP: cờ `disabled` bài này đặt còn nguyên khi bài sau
		# chạy. Trả về 0 để mỗi bài tự dựng đúng tình huống của nó.
		for nut in ("9Z", "9Z18", "9Z1801", "9Z180101", "9Z19", "9W"):
			if frappe.db.exists("Storage Location", nut):
				frappe.db.set_value("Storage Location", nut, "disabled", 0)

	def test_tat_nut_day_thi_khong_lay_o_trong_day(self):
		"""§8 bài 1: tắt nút DÃY (`9Z18`, 4 ký tự khu+dãy) — không phải nút
		Khoang (`9Z1801`). `trong_day_tat` (khoang 01 của dãy 18) có hạn dùng
		GẦN HƠN, lẽ ra được ưu tiên. Tắt cả dãy `9Z18` thì phải bỏ qua nó và
		lấy dãy `9Z19` — dù FEFO muốn ngược lại.
		"""
		frappe.db.set_value("Storage Location", "9Z18", "disabled", 1)
		ket = chon_o_xuat(KHO, self.item, None, 5)
		self.assertTrue(all(not d["o"].startswith("9Z18") for d in ket), ket)

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

	def test_cau_khuyen_chi_duong_len_nut_cha(self):
		"""VÒNG SỬA 1 (review điều phối): câu khuyên không được dẫn vào ngõ cụt.

		Từ khi `disabled` thừa kế, danh sách "ô đã ngừng dùng" trong thông báo
		gồm CẢ những ô mà bản thân chúng `disabled = 0` — chỉ một nút cha bị
		tắt. Câu khuyên cũ ("...hoặc bật lại ô đó rồi xuất lại") đúng với đời
		trước, giờ thì sai đường: thủ kho mở đúng `9Z18010101`, thấy ô Ngừng
		dùng ĐANG TRỐNG, và bế tắc — không manh mối nào dẫn về nút `9Z1801`
		mới là thứ đang chặn.

		Bài này dựng đúng tình huống đó (nút cha tắt, ô lá vẫn bật) và khoá
		câu chữ phải chỉ đường LÊN TRÊN. Không khoá tên đích danh nút cha:
		`tt` không có phạm vi ngoài `EXISTS` nên nêu tên nó phải nhân bản khối
		`_TO_TIEN_TAT` — việc của một task riêng, nếu cần.
		"""
		frappe.db.set_value("Storage Location", "9Z1801", "disabled", 1)
		self.assertEqual(
			frappe.db.get_value("Storage Location", self.trong_day_tat, "disabled"),
			0,
			"tiền đề: CHÍNH ô lá vẫn đang bật, chỉ nút cha bị tắt",
		)
		# Cần 15 trong khi ô còn dùng được chỉ có 10 + 2 → thiếu thật, mới dựng
		# tới câu thông báo có danh sách ô ngừng dùng.
		with self.assertRaises(frappe.ValidationError) as ctx:
			chon_o_xuat(KHO, self.item, None, 15)
		loi = str(ctx.exception)
		self.assertIn("9Z18010101", loi, "tiền đề: ô lá (đang bật) vẫn bị liệt kê")
		self.assertIn(
			"nút cha",
			loi.lower(),
			"câu khuyên phải nói rõ có thể do một nút cha đang tắt, không thì người "
			"đọc mở ô ra thấy nó vẫn bật rồi bế tắc",
		)
		self.assertNotIn("Traceback", loi)


class TestONgoaiCayKhongKeoNhauXuong(FrappeTestCase):
	"""Bản ghi `lft = rgt = 0` không được coi nhau là tổ tiên.

	LỆCH KHỎI BRIEF — có đo. Brief viết vị từ tổ-tiên-hoặc-chính-nó bằng
	`tt.lft <= sl.lft and tt.rgt >= sl.rgt`. Các bản ghi `Storage Location`
	cũ (tạo trước khi có cây, Task 2) mang `lft = rgt = 0` cho tới khi
	`cay.py::dam_bao_cay_da_dung()` hội tụ hết — số lượng thay đổi theo site
	và theo thời điểm, KHÔNG cố định — KỂ CẢ ô hệ thống `ZZZ-CHUA-XEP-<kho>`,
	nơi đang giữ toàn bộ tồn của kho thật. Với `<=`/`>=`, hai bản ghi `0/0` bất
	kỳ thoả `0 <= 0 and 0 >= 0`: tắt MỘT ô cũ là mọi ô cũ khác, và ô CHUA-XEP, cùng
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


class TestPhamViGioiHanTrongNhanh(FrappeTestCase):
	"""TASK 5: `pham_vi` ép chọn hàng chỉ trong MỘT nhánh, dù ngược FEFO.

	Nhánh NGOÀI phạm vi ("9Z1801") có hạn dùng GẦN HƠN nhánh TRONG phạm vi
	("9Z1802"). Cố ý ngược: nếu `pham_vi` không có tác dụng gì (mutation:
	tham số bị bỏ qua, hoặc `loc_pham_vi` không được chèn vào truy vấn chọn
	ứng viên), FEFO bình thường đã chọn đúng nhánh ngoài rồi (hạn gần hơn) —
	bài 1 sẽ đỏ vì kết quả chứa ô KHÔNG bắt đầu bằng "9Z1802". Nếu dựng hai
	nhánh với hạn dùng ngược lại (trong phạm vi hạn gần hơn), `pham_vi` có
	bị bỏ qua hoàn toàn thì FEFO vẫn tình cờ chọn đúng nhánh đó — bài không
	chứng minh được gì (xem yêu cầu điều phối).
	"""

	def setUp(self):
		self.item = _dam_bao_item("_Test FEFO PhamVi GioiHan")
		self.trong_pham_vi = _o("9Z18020101", thu_tu=1)
		self.ngoai_pham_vi = _o("9Z18010101", thu_tu=2)
		_dam_bao_ton(self.trong_pham_vi, self.item, _lo("_T-PV-XA", self.item, "2027-10-01"), 10)
		_dam_bao_ton(self.ngoai_pham_vi, self.item, _lo("_T-PV-GAN", self.item, "2026-10-01"), 10)

	def test_pham_vi_gioi_han_trong_nhanh(self):
		# khoang 02 (mã "9Z1802", trong dãy "9Z18") có hạn dùng XA HƠN, FEFO
		# bình thường sẽ không chọn nó
		ket = chon_o_xuat(KHO, self.item, None, 5, pham_vi="9Z1802")
		self.assertTrue(all(d["o"].startswith("9Z1802") for d in ket), ket)

	def test_pham_vi_rong_giu_nguyen_hanh_vi_cu(self):
		"""VÒNG SỬA 1/5 (review điều phối): bản trước so hai lời gọi
		`chon_o_xuat` với nhau — cả hai đều rơi vào `if pham_vi:` → False,
		cùng một câu SQL, CÙNG MỘT đường code. Đó là bài tự-so-với-chính-
		mình: cơ chế tham số mặc định của Python đã đảm bảo sẵn, bài không
		khoá thêm gì — gọi nó "quan trọng nhất" là overclaim.

		Sửa: vế kỳ vọng dựng TAY (không gọi lại `chon_o_xuat`). `ngoai_pham_vi`
		có hạn GẦN HƠN (2026-10-01) và một mình đủ 5, nên FEFO không-giới-hạn
		phải chọn ĐÚNG nó, đủ số — biết trước từ chính fixture ở `setUp`,
		không suy ra từ công thức đang kiểm.

		Bằng chứng THẬT cho "hành vi cũ không đổi" không phải bài này — mà là
		các bài Task 1-4 sẵn có (`test_fefo.py`, `test_cay_vi_tri.py`, ...):
		chúng gọi `chon_o_xuat` với 4 tham số VỊ TRÍ (không có `pham_vi`) và
		vẫn xanh sau khi thêm tham số thứ 5 có mặc định — đó mới là hồi quy
		được khoá thật, không phải phép so sánh vòng ở đây.
		"""
		ky_vong = [{"o": self.ngoai_pham_vi, "so_luong": 5.0}]
		self.assertEqual(chon_o_xuat(KHO, self.item, None, 5), ky_vong)
		self.assertEqual(chon_o_xuat(KHO, self.item, None, 5, pham_vi=None), ky_vong)

	def test_pham_vi_khong_ton_tai_bao_loi_tieng_viet(self):
		with self.assertRaises(frappe.ValidationError) as ctx:
			chon_o_xuat(KHO, self.item, None, 5, pham_vi="9Z9999")
		self.assertIn("không tồn tại", str(ctx.exception).lower())
		self.assertNotIn("Traceback", str(ctx.exception))
		self.assertNotIn("None", str(ctx.exception))


class TestPhamViApDungCaHaiTruyVan(FrappeTestCase):
	"""TASK 5, nhấn lại của điều phối (không có nguyên văn trong brief):
	`pham_vi` phải áp vào CẢ HAI truy vấn — chọn ứng viên VÀ dựng thông báo
	thiếu hàng — không chỉ truy vấn thứ nhất.

	Dựng: ô ĐANG DÙNG trong phạm vi chỉ có 2 (thiếu so với cần 5), còn một ô
	NGOÀI phạm vi (khoang khác, cùng khu/dãy nhưng ngoài phạm vi Khoang đang
	xét) đang NGỪNG DÙNG giữ 10. Nếu `pham_vi` chỉ được
	chèn vào truy vấn chọn ứng viên (mutation: quên chèn `{loc_pham_vi}` vào
	truy vấn `o_ngung_dung`), truy vấn thứ hai sẽ thấy ô ngoài phạm vi đó
	đang giữ hàng và đổi sang thông báo "còn hàng kẹt ở ô ngừng dùng: <ô
	ngoài phạm vi>" — mách một nhánh mà lệnh gọi không hề hỏi tới. Bài này
	khoá: trong tình huống đó, thông báo phải là câu "không đủ hàng" bình
	thường (không nhánh nào TRONG phạm vi đang ngừng dùng), và không được
	nêu tên ô ngoài phạm vi.
	"""

	def setUp(self):
		self.item = _dam_bao_item("_Test FEFO PhamVi CaHaiTruyVan")
		self.trong_pham_vi = _o("9Z18020102", thu_tu=1)
		self.ngoai_pham_vi_tat = _o("9Z18010102", thu_tu=2)
		_dam_bao_ton(self.trong_pham_vi, self.item, None, 2)
		_dam_bao_ton(self.ngoai_pham_vi_tat, self.item, None, 10)
		frappe.db.set_value("Storage Location", self.ngoai_pham_vi_tat, "disabled", 1)

	def tearDown(self):
		frappe.db.set_value("Storage Location", self.ngoai_pham_vi_tat, "disabled", 0)

	def test_khong_mach_hang_ngung_dung_ngoai_pham_vi(self):
		"""VÒNG SỬA 1/5 (review điều phối): bài này rơi đúng vào câu throw
		"không đủ hàng" chung — review chỉ ra câu đó đọc như số liệu TOÀN
		KHO ("cần 5, chỉ có 2, thiếu 3") trong khi kho thật có 12 (2 trong
		phạm vi + 10 ở ô ngừng dùng ngoài phạm vi). Bài trước chỉ khoá
		"không nhắc ô ngoài phạm vi", không khoá câu chữ mới phải NÊU TÊN
		`pham_vi` và nói rõ số liệu chỉ tính trong phạm vi đó — thêm hai
		assert dưới để khớp câu đã sửa.
		"""
		with self.assertRaises(frappe.ValidationError) as ctx:
			chon_o_xuat(KHO, self.item, None, 5, pham_vi="9Z1802")
		loi = str(ctx.exception)
		self.assertNotIn(
			self.ngoai_pham_vi_tat,
			loi,
			"ô ngừng dùng nằm NGOÀI phạm vi được hỏi — không được nêu tên trong "
			"thông báo của một lệnh gọi chỉ xin xuất trong phạm vi khác",
		)
		self.assertNotIn(
			"ngừng dùng",
			loi.lower(),
			"trong PHẠM VI được hỏi không có ô nào ngừng dùng giữ hàng — phải là "
			"câu 'không đủ hàng' thông thường, không phải câu nhắc ô ngừng dùng",
		)
		self.assertIn("thiếu", loi.lower())
		self.assertIn(
			"9Z1802",
			loi,
			"số liệu chỉ tính trong phạm vi này — câu phải nêu đích danh phạm vi, "
			"không để người đọc hiểu nhầm 2/5 là số liệu toàn kho",
		)
		self.assertIn(
			"phạm vi",
			loi.lower(),
			"phải nói rõ đây là thiếu hàng TRONG PHẠM VI, không phải toàn kho",
		)
		self.assertNotIn("Traceback", loi)

	def test_bao_dung_pham_vi_khi_o_ngung_dung_nam_trong_pham_vi(self):
		"""RÀ TOÀN NHÁNH mục A2: ca ghép còn thiếu — ô ngừng dùng giữ hàng
		NẰM TRONG chính `pham_vi` được hỏi (khác bài phía trên, nơi ô ngừng
		dùng nằm NGOÀI phạm vi). Câu throw đúng ở ca này là câu "ngừng dùng"
		(`fefo.py`, nhánh throw ĐẦU — chỉ tới nhánh có tên `pham_vi` khi
		`o_ngung_dung` RỖNG) — nhưng TRƯỚC khi vá, câu "ngừng dùng" không hề
		nêu tên `pham_vi`, đọc như số liệu TOÀN KHO dù `co`/`can` đã bị lọc
		theo phạm vi. Dùng item/mã ô RIÊNG (tiền tố `9T18`, không đụng
		`self.trong_pham_vi`/`self.ngoai_pham_vi_tat` của `setUp`) — bài này
		tự dựng đúng tình huống của mình, không dựa vào bài khác.
		"""
		item = _dam_bao_item("_Test FEFO PhamVi CaHaiTruyVan Ghep")
		dang_dung = _o("9T18020101", thu_tu=1)
		ngung_dung_trong_pham_vi = _o("9T18020102", thu_tu=2)
		_dam_bao_ton(dang_dung, item, None, 2)
		_dam_bao_ton(ngung_dung_trong_pham_vi, item, None, 10)
		frappe.db.set_value("Storage Location", ngung_dung_trong_pham_vi, "disabled", 1)
		try:
			with self.assertRaises(frappe.ValidationError) as ctx:
				chon_o_xuat(KHO, item, None, 5, pham_vi="9T1802")
			loi = str(ctx.exception)
			self.assertIn(
				"ngừng dùng",
				loi.lower(),
				"ô ngừng dùng giữ hàng NẰM TRONG phạm vi -> phải là câu 'ngừng dùng', "
				"không phải câu 'không đủ hàng' chung chung",
			)
			self.assertIn(
				"9T1802",
				loi,
				"câu 'ngừng dùng' cũng phải nêu tên phạm vi -- không nêu thì số liệu "
				"đọc như toàn kho dù co/can đã bị lọc theo pham_vi",
			)
			self.assertIn(
				"phạm vi",
				loi.lower(),
				"phải nói rõ số liệu này chỉ tính TRONG phạm vi, không phải toàn kho",
			)
			self.assertIn(
				ngung_dung_trong_pham_vi,
				loi,
				"vẫn phải nêu đích danh ô đang giữ hàng ngừng dùng",
			)
			self.assertNotIn("Traceback", loi)
		finally:
			frappe.db.set_value("Storage Location", ngung_dung_trong_pham_vi, "disabled", 0)


class TestPhamViNgoaiCayKhongDuocGioiHanSai(FrappeTestCase):
	"""`pham_vi` trên một bản ghi NGOÀI CÂY (`lft = rgt = 0` — bản ghi cũ, tạo
	trước khi có cây, còn tồn tại cho tới khi `cay.py::dam_bao_cay_da_dung()`
	hội tụ hết; xem `_TO_TIEN_TAT`) dính đúng cái bẫy `_TO_TIEN_TAT` được
	viết ra để tránh, nhưng ở PHÍA LỌC PHẠM VI: điều kiện trở thành
	`sl.lft between 0 and 0` = `sl.lft = 0`, khớp MỌI bản ghi 0/0 khác — kể cả
	những ô không liên quan gì tới nhánh của `pham_vi`. Đã ĐO THẬT (xem
	task-5-report.md): `pham_vi=<ô A, lft=rgt=0, tồn 2>` xuất 4 khi có ô B
	KHÔNG liên quan (cũng lft=rgt=0, tồn 5) trả về CẢ hai ô — hàng của ô B lọt
	vào một lệnh gọi tưởng chỉ giới hạn trong ô A.

	Không tự sinh SAI (khác hướng `_TO_TIEN_TAT`): `_TO_TIEN_TAT` lệch bằng
	cách LOẠI OAN (đóng băng cả kho); bẫy này lệch bằng cách GỘP OAN (lấy
	nhầm hàng của nhánh khác). Không thể dùng lại vị từ `<`/`>` chặt của
	`_TO_TIEN_TAT` ở đây — `pham_vi` không so hai bản ghi tuỳ ý, mà so
	CHÍNH bản ghi đó với các ô khác qua tọa độ của riêng nó, và tọa độ đó
	chính là thứ bị hỏng khi ngoài cây. Nên chặn ở NGUỒN: từ chối dùng một
	bản ghi ngoài cây làm `pham_vi`, báo tiếng Việt rõ ràng thay vì lặng lẽ
	trả sai.
	"""

	def setUp(self):
		self.item = _dam_bao_item("_Test FEFO PhamVi NgoaiCay GioiHan")
		self.trong_pham_vi = _o("9U18010101", thu_tu=1)
		self.khong_lien_quan = _o("9U18010102", thu_tu=2)
		_dam_bao_ton(self.trong_pham_vi, self.item, None, 2)
		_dam_bao_ton(self.khong_lien_quan, self.item, None, 5)
		for o in (self.trong_pham_vi, self.khong_lien_quan):
			frappe.db.set_value("Storage Location", o, {"lft": 0, "rgt": 0}, update_modified=False)

	def test_pham_vi_ngoai_cay_bao_loi_khong_lay_nham_o_khac(self):
		with self.assertRaises(frappe.ValidationError) as ctx:
			chon_o_xuat(KHO, self.item, None, 4, pham_vi=self.trong_pham_vi)
		loi = str(ctx.exception)
		self.assertIn("cây vị trí", loi.lower())
		self.assertNotIn("Traceback", loi)
		self.assertNotIn("None", loi)
