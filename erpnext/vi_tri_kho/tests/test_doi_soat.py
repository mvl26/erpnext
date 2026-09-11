"""Đối soát tồn vị trí với tồn kho ERPNext — bất biến của spec §3.

So THEO TỪNG LÔ, không chỉ so tổng. So tổng thôi thì một lỗi gộp lô (mọi lô
ghi so_lo = NULL) vẫn "khớp" — đúng lớp lỗi mà Task 5 sinh ra để phòng.

VÒNG SỬA 1 (review điều phối, Critical): mốc quy chiếu là `Bin.actual_qty`
Ở CẤP MẶT HÀNG (không phải `sum(sle.actual_qty)` — SAI với Stock
Reconciliation hàng không lô, xem docstring `vitri/doi_soat.py`), chia
theo lô qua `Serial and Batch Entry`. `Bin` không dùng làm nguồn DUY NHẤT
được vì thiếu chiều lô, nhưng làm tổng có thẩm quyền ở cấp mặt hàng thì
đúng.

`_nhap` dùng lại `test_hook_nhap._nhap_kho` (Minor 3, review vòng 1) —
tránh trùng lặp một hàm dựng Stock Entry giống hệt.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from erpnext.vi_tri_kho.tests.test_hook_nhap import _bat_kho_tho, _tao_item, _tat_kho_tho
from erpnext.vi_tri_kho.tests.test_hook_nhap import _nhap_kho as _nhap
from erpnext.vi_tri_kho.vitri import so
from erpnext.vi_tri_kho.vitri.doi_soat import doi_soat_kho

KHO = "Kho Miyano - MYN"


class TestKhopThiBaoKhop(FrappeTestCase):
	def setUp(self):
		_bat_kho_tho(KHO)
		self.item = _tao_item("_Test DS Khop")

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_sau_khi_nhap_thi_khop(self):
		_nhap(self.item, 15)
		kq = doi_soat_kho(KHO)
		lech_cua_item = [d for d in kq["dong_lech"] if d["vat_tu"] == self.item]
		self.assertEqual(lech_cua_item, [], f"phải khớp, nhưng lệch: {lech_cua_item}")


class TestLechThiBao(FrappeTestCase):
	# LƯU Ý: mỗi bài trong lớp này PHẢI dùng mặt hàng riêng (không chỉ chung
	# lớp với bài khác) — FrappeTestCase rollback theo LỚP, không theo từng
	# bài (addClassCleanup trong frappe/tests/utils.py). Brief gốc gộp hai
	# bài `test_pha_ton_vi_tri...` và `test_dung_lai_ton...` trong CÙNG một
	# lớp, dùng CHUNG `self.item`; unittest chạy theo alphabet nên
	# `test_dung_lai_ton_thi_het_lech` ('d') chạy trước
	# `test_pha_ton_vi_tri_thi_doi_soat_bat_duoc` ('p'), Stock Entry 10 của
	# bài trước cộng dồn sang bài sau — đo được thật: ton_kho ra 20 thay vì
	# 10. Tách lớp theo mặt hàng riêng để mỗi bài độc lập với thứ tự chạy.
	def setUp(self):
		_bat_kho_tho(KHO)
		self.item = _tao_item("_Test DS Lech")

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_pha_ton_vi_tri_thi_doi_soat_bat_duoc(self):
		_nhap(self.item, 10)
		ten = frappe.db.get_value("Location Balance", {"kho": KHO, "vat_tu": self.item}, "name")
		frappe.db.set_value("Location Balance", ten, "so_luong", 3)

		# KHÔNG khẳng định kq["khop"] toàn kho (Minor 4, review vòng 1):
		# Kho Miyano - MYN có tồn thật chưa chuyển đổi (Task 12) nên
		# kq["khop"] toàn kho luôn False bất kể bài này làm gì — khẳng định
		# đó xanh vì nhiễu nền, không phải vì lý do bài test nêu.
		kq = doi_soat_kho(KHO)
		lech = [d for d in kq["dong_lech"] if d["vat_tu"] == self.item]
		self.assertEqual(len(lech), 1)
		self.assertEqual(lech[0]["ton_vi_tri"], 3)
		self.assertEqual(lech[0]["ton_kho"], 10)
		self.assertEqual(lech[0]["lech"], -7)


class TestDungLaiTonHetLech(FrappeTestCase):
	def setUp(self):
		_bat_kho_tho(KHO)
		self.item = _tao_item("_Test DS DungLai")

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_dung_lai_ton_thi_het_lech(self):
		_nhap(self.item, 10)
		ten = frappe.db.get_value("Location Balance", {"kho": KHO, "vat_tu": self.item}, "name")
		frappe.db.set_value("Location Balance", ten, "so_luong", 3)

		# so kq["khop"] toàn kho là vô nghĩa ở đây: Kho Miyano - MYN đang có
		# tồn thật chưa chuyển đổi (Task 12), nên kq["khop"] LUÔN False cho
		# kho này bất kể bài test làm gì — phải lọc theo mặt hàng của
		# chính bài để kiểm đúng cái đang test.
		lech_truoc = [d for d in doi_soat_kho(KHO)["dong_lech"] if d["vat_tu"] == self.item]
		self.assertEqual(len(lech_truoc), 1, "tiền đề: phải lệch trước khi dựng lại")

		so.dung_lai_ton_vi_tri(KHO)
		lech = [d for d in doi_soat_kho(KHO)["dong_lech"] if d["vat_tu"] == self.item]
		self.assertEqual(lech, [])


class TestSoTheoTungLo(FrappeTestCase):
	def setUp(self):
		_bat_kho_tho(KHO)
		self.item = _tao_item("_Test DS Lo", co_lo=1)

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_gop_lo_lam_mot_thi_bi_bat(self):
		"""Bài chốt: mô phỏng đúng lỗi Task 5 phòng, đối soát phải bắt được.

		QUAN TRỌNG: `kq["khop"]` cho CẢ KHO không dùng được làm khẳng định ở
		đây — `Kho Miyano - MYN` đang có tồn thật mà sổ vị trí chưa chuyển
		đổi (Task 12), nên `khop` toàn kho LUÔN False từ trước khi bài này
		chạy bất cứ việc gì. Một cài đặt chỉ so TỔNG (bỏ hoàn toàn chiều lô)
		cũng làm `assertFalse(kq["khop"])` xanh — không khoá được gì. Phải
		lọc theo mặt hàng của chính bài rồi khẳng định ĐÚNG HÌNH DẠNG của
		lệch: hai dòng lô đối nhau (lô rỗng thừa, lô thật thiếu) cộng lại
		bằng 0 — con số mà một phép so TỔNG sẽ nuốt mất và báo khớp.
		"""
		_nhap(self.item, 10)

		lech_ban_dau = [d for d in doi_soat_kho(KHO)["dong_lech"] if d["vat_tu"] == self.item]
		self.assertEqual(lech_ban_dau, [], "tiền đề: trước khi phá thì mặt hàng này phải khớp")

		dong = frappe.get_all(
			"Location Balance", filters={"kho": KHO, "vat_tu": self.item}, fields=["name", "so_lo"]
		)
		self.assertEqual(len(dong), 1)
		self.assertTrue(dong[0].so_lo, "tiền đề: hook phải ghi được lô")

		# cố tình xoá lô để giả lập lỗi gộp lô
		frappe.db.set_value("Location Balance", dong[0].name, "so_lo", None)

		# Việc (B) (review điều phối, sau khi 147/147 bài "xong"): đã XOÁ
		# `assertFalse(kq["khop"])` toàn kho từng đứng ở đây — nó LUÔN xanh
		# (Kho Miyano - MYN có tồn thật chưa chuyển đổi, và từ Critical 1b
		# còn có thêm lý do thứ hai để `khop` False vô can với bài này), nên
		# không khoá được gì; các khẳng định LỌC THEO MẶT HÀNG bên dưới mới
		# là thứ khoá thật.
		kq = doi_soat_kho(KHO)

		lech = [d for d in kq["dong_lech"] if d["vat_tu"] == self.item]
		self.assertEqual(
			len(lech),
			2,
			f"phải ra đúng 2 dòng cho mặt hàng này: lô rỗng thừa 10, lô thật thiếu 10 — thấy: {lech}",
		)
		tong = sum(d["lech"] for d in lech)
		self.assertAlmostEqual(
			tong,
			0,
			places=6,
			msg=(
				"tổng lệch của hai dòng lô phải bằng 0 — đây chính là điều "
				"làm so TỔNG mù mắt: cộng lại thấy khớp trong khi so THEO "
				f"LÔ (kết quả ở trên) bắt được. Thấy: {lech}"
			),
		)


class TestKiemKeHangKhongLoVanKhop(FrappeTestCase):
	"""Critical (review vòng 1): mốc quy chiếu CŨ `sum(sle.actual_qty)` sai
	với Stock Reconciliation hàng KHÔNG LÔ — ERPNext đặt cứng
	`actual_qty = 0` khi submit (giá trị thật ở `qty_after_transaction`,
	xem `vitri/delta.py`). Bài này là bài DUY NHẤT trong module phủ đúng
	đường đó; 8 bài còn lại đều chỉ đi qua Material Receipt/Issue — đường
	mà actual_qty tình cờ đúng — nên dưới mã cũ CẢ 8 bài đó vẫn xanh dù
	Critical còn nguyên. Dựng chứng từ theo đúng mẫu đã có ở
	`test_hook_nhap.TestThuTuTinhDeltaTruocKhiGhi
	.test_kiem_ke_sau_khi_da_co_ton_phai_khop_tong_moi`."""

	def setUp(self):
		_bat_kho_tho(KHO)
		self.item = _tao_item("_Test DS Kiem Ke")

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_kiem_ke_hang_khong_lo_van_khop(self):
		_nhap(self.item, 10)
		lech_sau_nhap = [d for d in doi_soat_kho(KHO)["dong_lech"] if d["vat_tu"] == self.item]
		self.assertEqual(lech_sau_nhap, [], "tiền đề: sau khi nhập phải khớp")

		sr = frappe.get_doc(
			{
				"doctype": "Stock Reconciliation",
				"company": "Miyano Việt Nam",
				"purpose": "Stock Reconciliation",
				"items": [
					{
						"item_code": self.item,
						"warehouse": KHO,
						"qty": 7,
						"valuation_rate": 1000,
					}
				],
			}
		)
		sr.insert(ignore_permissions=True)
		sr.submit()

		bin_qty = frappe.db.get_value("Bin", {"item_code": self.item, "warehouse": KHO}, "actual_qty")
		self.assertEqual(flt(bin_qty), 7, "tiền đề: ERPNext đã chốt tồn kho = 7 sau kiểm kê")

		lech = [d for d in doi_soat_kho(KHO)["dong_lech"] if d["vat_tu"] == self.item]
		self.assertEqual(
			lech,
			[],
			f"kiểm kê hàng không lô phải vẫn khớp — mốc quy chiếu sai (actual_qty) "
			f"sẽ bỏ qua lần kiểm kê này và báo ton_kho=10 thay vì 7: {lech}",
		)


class TestSoTheoTungLoHaiLo(FrappeTestCase):
	"""I3 (review vòng 1): một khẳng định trong một bài (bài chốt gộp lô)
	đang gánh toàn bộ chiều lô — thêm góc đo khác, phủ đúng đường ĐỌC mới
	(Bin + chia theo Serial and Batch Entry) khi một mặt hàng có HAI lô
	riêng biệt trong cùng kho, không phải một lô duy nhất."""

	def setUp(self):
		_bat_kho_tho(KHO)
		self.item = _tao_item("_Test DS Lo Kep", co_lo=1)

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_hai_lo_khop_rieng_tung_lo(self):
		_nhap(self.item, 10)
		_nhap(self.item, 6)  # lần nhập thứ hai tự sinh một lô khác

		bin_qty = frappe.db.get_value("Bin", {"item_code": self.item, "warehouse": KHO}, "actual_qty")
		self.assertEqual(flt(bin_qty), 16, "tiền đề: Bin cộng dồn cả hai lô")

		lech = [d for d in doi_soat_kho(KHO)["dong_lech"] if d["vat_tu"] == self.item]
		self.assertEqual(lech, [], f"hai lô riêng biệt vẫn phải khớp: {lech}")

		dong = frappe.get_all(
			"Location Balance",
			filters={"kho": KHO, "vat_tu": self.item},
			fields=["name", "so_lo", "so_luong"],
		)
		self.assertEqual(len(dong), 2, "tiền đề: hai lần nhập phải sinh hai lô riêng")

		# Bài chốt gop_lo (TestSoTheoTungLo) đã khoá trường hợp gộp MỘT lô
		# duy nhất; ở đây khoá trường hợp CHỈ MỘT trong nhiều lô bị sai số,
		# (các) lô còn lại vẫn đúng — buộc so_lo phải chỉ đúng ra lô bị pha.
		bi_pha = dong[0]
		frappe.db.set_value("Location Balance", bi_pha.name, "so_luong", flt(bi_pha.so_luong) - 1)

		lech2 = [d for d in doi_soat_kho(KHO)["dong_lech"] if d["vat_tu"] == self.item]
		self.assertEqual(len(lech2), 1, f"chỉ đúng lô bị pha phải lệch: {lech2}")
		self.assertEqual(lech2[0]["so_lo"], bi_pha.so_lo)


class TestXuatHangCoLo(FrappeTestCase):
	"""I2 (review vòng 1): dấu của sbe.qty đúng với đường xuất (đã đo trên
	`serial_and_batch_bundle.py::calculate_total_qty` — is_outward nhân
	-1), nhưng trước vòng sửa này chưa bài nào phủ đường xuất; cả 4 bài gốc
	chỉ dùng Material Receipt. Một hồi quy về abs(sbe.qty) hoặc quay lại
	actual_qty cho dòng có bundle sẽ lọt nếu không có bài này."""

	def setUp(self):
		_bat_kho_tho(KHO)
		self.item = _tao_item("_Test DS Lo Xuat", co_lo=1)

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_xuat_hang_co_lo_van_khop(self):
		_nhap(self.item, 10)

		xuat = frappe.get_doc(
			{
				"doctype": "Stock Entry",
				"stock_entry_type": "Material Issue",
				"company": "Miyano Việt Nam",
				"items": [{"item_code": self.item, "qty": 4, "s_warehouse": KHO}],
			}
		)
		xuat.insert(ignore_permissions=True)
		xuat.submit()

		bin_qty = frappe.db.get_value("Bin", {"item_code": self.item, "warehouse": KHO}, "actual_qty")
		self.assertEqual(flt(bin_qty), 6, "tiền đề: ERPNext đã trừ tồn kho về 6")

		lech = [d for d in doi_soat_kho(KHO)["dong_lech"] if d["vat_tu"] == self.item]
		self.assertEqual(lech, [], f"xuất hàng có lô phải vẫn khớp: {lech}")


class TestHuyChungTuVanKhop(FrappeTestCase):
	"""I1 (review vòng 1): điều kiện `is_cancelled = 0` chưa được kiểm
	chứng — bỏ nó đi thì KHÔNG bài nào đỏ, vì toàn DB thật không có dòng
	SLE `is_cancelled = 1` nào. Lập luận "công cụ vẫn đo được khuyết tật
	huỷ kiểm kê hàng có lô" đặt toàn bộ sức nặng lên đúng vị từ này.

	Dùng mặt hàng CÓ LÔ, không phải không-lô: `is_cancelled` chỉ xuất hiện
	trong câu SQL chia theo lô (join Serial and Batch Entry); với hàng
	không lô, mốc quy chiếu là thẳng `Bin.actual_qty` nên predicate này
	không hề được thực thi cho đường đó — một bài dùng hàng không lô sẽ
	KHÔNG kiểm được gì (xem báo cáo, mục mutation test)."""

	def setUp(self):
		_bat_kho_tho(KHO)
		self.item = _tao_item("_Test DS Huy Lo", co_lo=1)

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_huy_chung_tu_thi_doi_soat_van_khop(self):
		se = _nhap(self.item, 10)
		lech_sau_nhap = [d for d in doi_soat_kho(KHO)["dong_lech"] if d["vat_tu"] == self.item]
		self.assertEqual(lech_sau_nhap, [], "tiền đề: sau khi nhập phải khớp")

		se.cancel()

		lech_sau_huy = [d for d in doi_soat_kho(KHO)["dong_lech"] if d["vat_tu"] == self.item]
		self.assertEqual(
			lech_sau_huy,
			[],
			f"huỷ chứng từ phải đối soát vẫn khớp (cả hai vế cùng về 0): {lech_sau_huy}",
		)


class TestNguongSaiSo(FrappeTestCase):
	"""Minor 2 (review vòng 1): ngưỡng > 0.0001 tồn tại trong code nhưng
	trước vòng sửa này không bài nào phủ nó — mọi số lượng trong suite đều
	nguyên."""

	def setUp(self):
		_bat_kho_tho(KHO)
		self.item = _tao_item("_Test DS Nguong")

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_sai_so_trong_nguong_khong_bao_nhung_vuot_thi_bao(self):
		_nhap(self.item, 10)
		ten = frappe.db.get_value("Location Balance", {"kho": KHO, "vat_tu": self.item}, "name")

		frappe.db.set_value("Location Balance", ten, "so_luong", 10.00005)  # lệch 0.00005 < 0.0001
		lech_trong_nguong = [d for d in doi_soat_kho(KHO)["dong_lech"] if d["vat_tu"] == self.item]
		self.assertEqual(lech_trong_nguong, [], "sai số nhỏ hơn ngưỡng 0.0001 không được báo")

		frappe.db.set_value("Location Balance", ten, "so_luong", 9.9989)  # lệch 0.0011 > 0.0001
		lech_vuot_nguong = [d for d in doi_soat_kho(KHO)["dong_lech"] if d["vat_tu"] == self.item]
		self.assertEqual(len(lech_vuot_nguong), 1, "sai số vượt ngưỡng 0.0001 phải báo")


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


class TestOAm(FrappeTestCase):
	"""CRITICAL 1b (review điều phối, sau khi 147/147 bài "xong"): phép đo
	lẽ ra đã bắt được Critical 1 (LCV/repost đẩy hàng vào CHUA-XEP mà tổng
	vẫn khớp). Khoá bằng kịch bản đúng hình dạng: hai ô của CÙNG (vật tư,
	lô) — một ô âm, một ô bù dư đúng bằng số — để TỔNG (thứ `dong_lech` so)
	vẫn khớp Bin, chỉ `o_am` mới bắt được.
	"""

	def setUp(self):
		_bat_kho_tho(KHO)
		self.o_gan = _o("K19Z11010101", thu_tu=1)

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_o_am_bi_bat_du_tong_van_khop(self):
		# Mặt hàng RIÊNG cho bài này — lớp rollback theo LỚP, dùng chung
		# item với bài kia sẽ cộng dồn/để lại dữ liệu bẩn (nhiều dòng
		# Location Balance cho cùng item khiến get_value không xác định
		# được nhặt đúng dòng nào).
		item = _tao_item("_Test DS O Am A")
		_nhap(item, 10)
		o_chua_xep = frappe.db.get_value("Location Balance", {"kho": KHO, "vat_tu": item}, "o")

		lech_truoc = [d for d in doi_soat_kho(KHO)["dong_lech"] if d["vat_tu"] == item]
		self.assertEqual(lech_truoc, [], "tiền đề: trước khi phá thì phải khớp")

		# San CHUA-XEP xuống -3, o_gan bù +13 — TỔNG (vat_tu, so_lo rỗng) vẫn
		# đúng 10 (-3+13) nên dong_lech sạch; chỉ o_am mới thấy CHUA-XEP âm.
		frappe.db.sql(
			"update `tabLocation Balance` set so_luong = so_luong - 13 where o=%s and vat_tu=%s",
			(o_chua_xep, item),
		)
		frappe.get_doc(
			{
				"doctype": "Location Balance",
				"o": self.o_gan,
				"kho": KHO,
				"vat_tu": item,
				"so_lo": "",
				"so_luong": 13,
			}
		).insert(ignore_permissions=True)

		kq = doi_soat_kho(KHO)
		lech_sau = [d for d in kq["dong_lech"] if d["vat_tu"] == item]
		self.assertEqual(lech_sau, [], f"tiền đề: TỔNG vẫn khớp Bin dù có ô âm: {lech_sau}")

		o_am_cua_item = [d for d in kq["o_am"] if d["vat_tu"] == item]
		self.assertEqual(len(o_am_cua_item), 1, f"phải bắt được đúng 1 ô âm: {kq['o_am']}")
		self.assertEqual(o_am_cua_item[0]["o"], o_chua_xep)
		self.assertEqual(o_am_cua_item[0]["so_luong"], -3)
		self.assertFalse(
			kq["khop"],
			"khop phải False vì có ô âm — dù dong_lech (so TỔNG) sạch, đúng Critical 1b",
		)

	def test_sai_so_am_trong_nguong_khong_bao(self):
		item = _tao_item("_Test DS O Am B")
		_nhap(item, 10)
		ten = frappe.db.get_value("Location Balance", {"kho": KHO, "vat_tu": item}, "name")
		frappe.db.set_value("Location Balance", ten, "so_luong", -0.00005)  # lệch < NGUONG_SAI_SO

		o_am_cua_item = [d for d in doi_soat_kho(KHO)["o_am"] if d["vat_tu"] == item]
		self.assertEqual(o_am_cua_item, [], "dư làm tròn nhỏ hơn ngưỡng không được báo là ô âm")


class TestLechBoDem(FrappeTestCase):
	"""CRITICAL 1b: `Location Balance` phải dựng lại được từ sổ
	`Location Ledger Entry` — kiểm ĐỘC LẬP với `Bin`/ERPNext. Khoá bằng kịch
	bản: đổi bộ đệm sang một ô KHÁC mà không ghi sổ tương ứng — TỔNG theo
	(vật tư, lô) không đổi (dong_lech sạch) nhưng bộ đệm không còn dựng lại
	được từ sổ ở MỨC Ô.
	"""

	def setUp(self):
		_bat_kho_tho(KHO)
		self.o_gan = _o("K19Z10010101", thu_tu=1)

	def tearDown(self):
		_tat_kho_tho(KHO)

	def test_bo_dem_troi_khoi_so_bi_bat_du_tong_van_khop(self):
		# Mặt hàng RIÊNG cho bài này — lớp rollback theo LỚP (không theo từng
		# bài), dùng chung self.item với bài kia sẽ cộng dồn hai lần nhập.
		item = _tao_item("_Test DS Lech Bo Dem A")
		self.item = item
		_nhap(item, 10)
		o_chua_xep = frappe.db.get_value("Location Balance", {"kho": KHO, "vat_tu": item}, "o")

		# Sửa THẲNG bộ đệm — chuyển 3 từ CHUA-XEP sang o_gan mà KHÔNG qua
		# so.ghi_dong_so (không ghi sổ tương ứng). TỔNG (vat_tu, so_lo rỗng)
		# không đổi nên dong_lech sạch; không ô nào âm nên o_am cũng sạch.
		frappe.db.sql(
			"update `tabLocation Balance` set so_luong = so_luong - 3 where o=%s and vat_tu=%s",
			(o_chua_xep, self.item),
		)
		frappe.get_doc(
			{
				"doctype": "Location Balance",
				"o": self.o_gan,
				"kho": KHO,
				"vat_tu": self.item,
				"so_lo": "",
				"so_luong": 3,
			}
		).insert(ignore_permissions=True)

		kq = doi_soat_kho(KHO)
		self.assertEqual(
			[d for d in kq["dong_lech"] if d["vat_tu"] == self.item],
			[],
			"tiền đề: TỔNG vẫn khớp Bin",
		)
		self.assertEqual(
			[d for d in kq["o_am"] if d["vat_tu"] == self.item],
			[],
			"tiền đề: không ô nào âm",
		)

		lech_cua_item = sorted(
			(d for d in kq["lech_bo_dem"] if d["vat_tu"] == self.item),
			key=lambda d: d["o"],
		)
		self.assertEqual(len(lech_cua_item), 2, f"phải bắt lệch ở CẢ HAI ô liên quan: {lech_cua_item}")
		theo_o = {d["o"]: d for d in lech_cua_item}
		self.assertAlmostEqual(theo_o[o_chua_xep]["lech"], -3, places=6)
		self.assertAlmostEqual(theo_o[self.o_gan]["lech"], 3, places=6)
		self.assertFalse(
			kq["khop"],
			"khop phải False vì bộ đệm trôi khỏi sổ — dù dong_lech và o_am đều sạch",
		)

	def test_khop_thi_lech_bo_dem_rong(self):
		item = _tao_item("_Test DS Lech Bo Dem B")
		_nhap(item, 10)
		kq = doi_soat_kho(KHO)
		self.assertEqual([d for d in kq["lech_bo_dem"] if d["vat_tu"] == item], [])
