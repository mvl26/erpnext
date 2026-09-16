"""Quét mã tra cứu — chiều NGƯỢC của `nhap_lo.du_lieu_tem` (Task 10).

Thủ kho khai số lô trên `Batch Entry`, hệ in nhãn 50×30 — mã vạch trên nhãn mã
hoá chính số lô đó. Bài này khoá chiều ngược lại: quét đúng mã đó (hoặc mã vật
tư, hoặc mã kho) phải trả về đúng những gì đã khai, không thiếu không bịa, và
KHÔNG BAO GIỜ ném lỗi ra giữa màn hình nhập liệu dù quét trúng bất cứ thứ gì.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.vi_tri_kho.tests.test_hook_nhap import _tao_item
from erpnext.vi_tri_kho.tests.test_lo_ncc import _ncc_thu, _phieu_nhap_nhap
from erpnext.vi_tri_kho.vitri.nhat_ky_loi import TRAN_DO_DAI_TIEU_DE
from erpnext.vi_tri_kho.vitri.quet import tra_cuu

CONG_TY = "Miyano Việt Nam"
KHO = "Kho Miyano - MYN"

# Chuỗi CỐ ĐỊNH (không phải sinh ngẫu nhiên) để bài test dễ đọc và dễ debug —
# nhưng đúng vì thế phải tự dọn cache của `scan_barcode` ở `setUp` (xem đó).
SO_LO = "QUET-LO-0001"
MA_KHONG_TON_TAI = "MA-KHONG-TON-TAI-XYZ-999"
MA_VACH_VAT_TU = "_TEST-QUET-BARCODE-0001"
# `scan_barcode` phân giải Warehouse bằng CHÍNH `name` của nó (không phải
# barcode riêng) — dùng thẳng `KHO`, một Warehouse có thật, không tạo thêm.
MA_KHO = KHO

# Ô lá + tổ tiên: khu "9Q" đã có tiền lệ dùng cho dữ liệu scratch ở
# `test_cay_vi_tri.py` (dãy "18") — chọn dãy "50" để KHÔNG trùng, xem docstring
# đó về hậu quả của việc trùng tiền tố ô giữa hai bộ test.
VI_TRI = "9Q50010101"


def _o(ma_o, kho=KHO):
	if not frappe.db.exists("Storage Location", ma_o):
		frappe.get_doc({"doctype": "Storage Location", "ma_o": ma_o, "kho": kho}).insert(
			ignore_permissions=True
		)
	return ma_o


def _gan(vat_tu, vi_tri, kho=KHO):
	if not frappe.db.exists("Item Location Preference", vat_tu):
		frappe.get_doc(
			{"doctype": "Item Location Preference", "vat_tu": vat_tu, "kho": kho, "vi_tri": vi_tri}
		).insert(ignore_permissions=True)


def _ton_lo(o, vat_tu, so_lo, so_luong, kho=KHO):
	ten = frappe.db.get_value("Location Balance", {"o": o, "vat_tu": vat_tu, "so_lo": so_lo}, "name")
	if ten:
		frappe.db.set_value("Location Balance", ten, "so_luong", so_luong)
		return
	frappe.get_doc(
		{
			"doctype": "Location Balance",
			"o": o,
			"kho": kho,
			"vat_tu": vat_tu,
			"so_lo": so_lo,
			"so_luong": so_luong,
		}
	).insert(ignore_permissions=True)


def _phieu_nhap_lo(pr, dong):
	"""Dựng `Batch Entry` từ một phiếu nhập, KHÔNG submit — khuôn `test_nhap_lo.py`."""
	return frappe.get_doc({"doctype": "Batch Entry", "phieu_nhap": pr.name, "items": dong})


class TestTraCuu(FrappeTestCase):
	def setUp(self):
		# `scan_barcode` (bị bọc, không sửa) TỰ CACHE kết quả trong
		# `frappe.cache()` (Redis) 120 giây, khoá theo CHÍNH chuỗi quét —
		# Redis KHÔNG nằm trong transaction DB nên KHÔNG bị rollback theo lớp
		# của `FrappeTestCase`. Chạy lại module này hai lần liên tiếp trong
		# cùng 120 giây (đúng yêu cầu "chạy hai lần liên tiếp" của kế hoạch)
		# mà không xoá cache thì lần hai đọc phải kết quả CACHE của LẦN TRƯỚC
		# — trỏ vào một `Batch`/`Purchase Receipt` đã bị rollback, `get_doc`
		# ném `DoesNotExistError`, bị nuốt bởi `except Exception` trong
		# `tra_cuu`, và bài đỏ SAI CHỖ (không phải vì mã sai, mà vì cache cũ).
		# Xoá cache ở đầu MỖI bài để không phụ thuộc thứ tự chạy hay khoảng
		# cách thời gian giữa hai lần `run-tests`.
		for ma in (SO_LO, MA_KHONG_TON_TAI, MA_VACH_VAT_TU, MA_KHO):
			frappe.cache().delete_value(f"erpnext:barcode_scan:{ma}")

		self.ncc = _ncc_thu()
		self.item = _tao_item("_Test Quet Co Lo", co_lo=1)
		self.pr = _phieu_nhap_nhap(self.item, KHO, self.ncc, qty=10)
		self.dong_pr = self.pr.items[0].name

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_quet_so_lo_ra_du_thong_tin(self):
		"""11 khoá: ten_hang, hsd, ngay_san_xuat, nha_cung_cap, so_goi, ngay_nhap,
		so_phieu_nhap, vi_tri_co_dinh, o_dang_co_hang, o_in_tem, ton_theo_o."""
		_o(VI_TRI)
		_gan(self.item, VI_TRI)

		be = _phieu_nhap_lo(
			self.pr,
			[
				{
					"dong_phieu_nhap": self.dong_pr,
					"vat_tu": self.item,
					"kho": KHO,
					"so_luong": 10,
					"so_lo": SO_LO,
					"ngay_san_xuat": "2026-01-01",
					"hsd": "2030-01-31",
				}
			],
		)
		be.insert(ignore_permissions=True)
		be.submit()

		# Tem ĐÃ IN cho lô này — đặt thẳng xuống CSDL đúng cách `dat_o_in_tem`
		# (`nhap_lo.py`) tự làm, vì trường `custom_o_in_tem` là `read_only: 1`
		# trên lược đồ. Đặt tường minh (không để trống) để bài kiểm ĐƯỢC giá
		# trị THẬT của trường, không phải chỉ "không phải lỗi" — một cài đặt
		# luôn trả `o_in_tem = None` vẫn qua được nếu bài chỉ `assertIsNone`.
		frappe.db.set_value("Batch", SO_LO, "custom_o_in_tem", VI_TRI)

		_ton_lo(VI_TRI, self.item, SO_LO, 6)

		ket_qua = tra_cuu(SO_LO)

		ten_hang_that = frappe.db.get_value("Item", self.item, "item_name")

		self.assertEqual(ket_qua["loai"], "lo")
		self.assertEqual(ket_qua["so_lo"], SO_LO)
		self.assertEqual(ket_qua["vat_tu"], self.item)
		self.assertEqual(ket_qua["ten_hang"], ten_hang_that)
		self.assertEqual(str(ket_qua["hsd"]), "2030-01-31")
		self.assertEqual(str(ket_qua["ngay_san_xuat"]), "2026-01-01")
		self.assertEqual(ket_qua["nha_cung_cap"], self.ncc)
		self.assertTrue(ket_qua["so_goi"], "custom_so_goi phải được BatchEntry.on_submit sinh ra")
		self.assertEqual(str(ket_qua["ngay_nhap"]), str(self.pr.posting_date))
		self.assertEqual(ket_qua["so_phieu_nhap"], self.pr.name)
		self.assertEqual(ket_qua["vi_tri_co_dinh"], VI_TRI)
		self.assertEqual(ket_qua["o_dang_co_hang"], [VI_TRI])
		self.assertEqual(ket_qua["o_in_tem"], VI_TRI)
		self.assertEqual(len(ket_qua["ton_theo_o"]), 1)
		self.assertEqual(ket_qua["ton_theo_o"][0]["o"], VI_TRI)
		self.assertEqual(float(ket_qua["ton_theo_o"][0]["so_luong"]), 6.0)

	def test_quet_ma_khong_ton_tai_thi_tra_rong_chu_khong_no(self):
		"""Thủ kho quét nhầm một mã bất kỳ trong kho. Nổ ra traceback giữa màn
		hình nhập liệu là cách nhanh nhất để họ thôi dùng chức năng này."""
		# `assertEqual` với DICT CỤ THỂ, không chỉ `assertIsNone`/thử-không-nổ:
		# phải khẳng định TRẢ RỖNG (`{"loai": None}`), khác hẳn "không ném lỗi
		# nhưng trả bậy" — hai điều khác nhau, và brief nêu đích danh bẫy này.
		self.assertEqual(tra_cuu(MA_KHONG_TON_TAI), {"loai": None})

		# Mã trống/None — cùng một lớp "quét nhầm", cùng phải trả rỗng.
		self.assertEqual(tra_cuu(""), {"loai": None})

	def test_quet_ma_vat_tu_thi_tra_ve_mat_hang_khong_gia_vo_la_lo(self):
		"""`scan_barcode` phân giải cả Item Barcode. Trả về phải nói rõ LOẠI, vì
		màn hình hiển thị khác nhau cho lô và cho mặt hàng."""
		item_khong_lo = _tao_item("_Test Quet Khong Lo", co_lo=0)
		item_doc = frappe.get_doc("Item", item_khong_lo)
		if not frappe.db.exists("Item Barcode", {"barcode": MA_VACH_VAT_TU, "parent": item_khong_lo}):
			item_doc.append("barcodes", {"barcode": MA_VACH_VAT_TU})
			item_doc.save(ignore_permissions=True)

		ket_qua = tra_cuu(MA_VACH_VAT_TU)

		# Vế BẮT BUỘC theo brief: khẳng định ĐÚNG `loai == "vat_tu"`, không chỉ
		# "có trả về gì đó" — thiếu vế này thì một cài đặt luôn trả `loai = "lo"`
		# vẫn xanh (đọc được `vat_tu`/`ten_hang` từ MỌI nhánh).
		self.assertEqual(ket_qua["loai"], "vat_tu")
		self.assertEqual(ket_qua["vat_tu"], item_khong_lo)
		# KHÔNG được giả vờ là lô: không có bất kỳ khoá nào chỉ "lo" mới có.
		for khoa_cua_lo in ("hsd", "ngay_san_xuat", "nha_cung_cap", "so_lo", "ton_theo_o"):
			self.assertNotIn(khoa_cua_lo, ket_qua)

	def test_quet_ma_kho_tra_ve_loai_kho(self):
		"""Vòng sửa 1/5 (điều phối): `loai` là HỢP ĐỒNG phía JS dựa vào để chọn
		hiển thị gì — ba nhánh kia đã có bài khoá, nhánh `kho` không có lý do gì
		để là ngoại lệ, dù brief gốc chỉ định đúng bốn bài (không có bài này).

		`scan_barcode` phân giải Warehouse bằng CHÍNH `name` của nó (khác hẳn
		đường Item Barcode/Batch — xem nhánh cuối `stock/utils.py::scan_barcode`),
		nên quét thẳng `KHO` — một `Warehouse` có thật, không cần dựng thêm gì.
		"""
		ket_qua = tra_cuu(MA_KHO)

		# Vế BẮT BUỘC — khẳng định ĐÚNG `loai == "kho"`, không chỉ "có trả về gì
		# đó": một cài đặt lỡ gộp nhánh `kho` vào nhánh `vat_tu` (hoặc bỏ sót,
		# rơi xuống `None`) vẫn "trả về một dict" nhưng SAI hợp đồng.
		self.assertEqual(ket_qua["loai"], "kho")
		self.assertEqual(ket_qua["kho"], MA_KHO)
		# Không giả vờ là lô/vật tư: không lẫn khoá của hai nhánh kia vào đây.
		for khoa_khac_nhanh in ("so_lo", "vat_tu", "ten_hang", "ton_theo_o"):
			self.assertNotIn(khoa_khac_nhanh, ket_qua)

	def test_ma_rat_dai_khong_lam_no_luoi_an_toan(self):
		"""Vòng sửa 2/5 (điều phối, Important): lưới an toàn (`except Exception`
		+ `frappe.log_error`) tự nó có thể ném lỗi.

		`Error Log.method` là `Data(140)`. Nếu `_tra_cuu_khong_kiem_quyen` ném
		lỗi (ép bằng `scan_barcode` giả lập ở đây) VÀ `ma` đủ dài để tiêu đề
		ghép thô vượt 140, thì CHÍNH `frappe.log_error()` — đang NẰM TRONG
		khối `except` — ném `CharacterLengthExceededError`, văng ra NGOÀI khối
		đó. Bài này ép cả hai điều kiện cùng lúc rồi khẳng định `tra_cuu` vẫn
		trả về bình thường — không phải chỉ "không ném lỗi lạ nào", mà đúng
		`{"loai": None}`, cùng hình dạng với ca "quét nhầm" khác.
		"""
		# Ký tự KHÔNG lặp lại "M" đơn điệu (dễ đụng một mã đã dùng ở bài
		# khác nếu ai đó thêm bài mới sau này) — nhưng vẫn cố định để dọn
		# đúng dòng bằng LIKE ở cuối bài. Đủ dài để CHẮC CHẮN vượt trần dù
		# tiền tố tiêu đề đổi độ dài sau này.
		ma_rat_dai = "QUET-RAT-DAI-" + ("Z" * (TRAN_DO_DAI_TIEU_DE + 50))

		with patch(
			"erpnext.vi_tri_kho.vitri.quet.scan_barcode",
			side_effect=RuntimeError("giả lập lỗi dữ liệu để buộc nhánh log_error chạy"),
		):
			ket_qua = tra_cuu(ma_rat_dai)

		self.assertEqual(ket_qua, {"loai": None})

		# Đối chứng: `log_error` phải THẬT SỰ chạy tới cùng (ghi được một dòng
		# Error Log cho ĐÚNG mã này), không phải "không ném lỗi vì log_error
		# đã âm thầm hỏng theo cách khác". Dòng ghi được phải có tiêu đề đã
		# CẮT — điểm cắt (133 ký tự thô + đuôi) rơi trong tiền tố "QUET-RAT-
		# DAI-" nên tìm bằng LIKE trên chính tiền tố đó vẫn khớp đúng dòng.
		dong_error_log = frappe.get_all(
			"Error Log", filters={"method": ["like", "%QUET-RAT-DAI-%"]}, pluck="method"
		)
		self.assertEqual(len(dong_error_log), 1, "phải ghi đúng một dòng Error Log cho mã này")
		self.assertLessEqual(len(dong_error_log[0]), TRAN_DO_DAI_TIEU_DE)

		# `log_error` KHÔNG bị `FrappeTestCase` rollback (đã đo — xem ghi chú
		# cùng ý ở `test_phieu_xep_vi_tri.py`) nên phải tự dọn, không để rác
		# trên CSDL thật.
		frappe.db.delete("Error Log", {"method": ["like", "%QUET-RAT-DAI-%"]})

	def test_khong_co_vai_tro_kho_thi_bi_chan(self):
		"""Hàm này lộ tồn kho theo ô — đăng nhập hợp lệ không phải điều kiện đủ.
		Khuôn `xep._kiem_tra_quyen()`."""
		ten = "quet-khong-quyen@mo-phong.local"
		if not frappe.db.exists("User", ten):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": ten,
					"first_name": "Quet",
					"send_welcome_email": 0,
					"roles": [],
				}
			).insert(ignore_permissions=True)

		# Xác nhận NGƯỜI DÙNG THẬT SỰ KHÔNG có ba vai trò kho — không chỉ mong
		# đợi ngoại lệ suông: nếu `_nguoi_dung_khong_vai_tro` lỡ tạo ra một
		# người dùng CÓ vai trò (ví dụ do một Role Profile mặc định gán thêm),
		# bài này phải tự lộ ra thay vì lặng lẽ pass do PermissionError bật
		# lên vì một lý do khác (ví dụ site chưa cấu hình).
		vai_tro_hien_co = set(frappe.get_roles(ten))
		self.assertFalse(
			vai_tro_hien_co & {"System Manager", "Stock Manager", "Stock User"},
			f"người dùng thử phải KHÔNG có vai trò kho nào, hiện có: {vai_tro_hien_co}",
		)

		frappe.set_user(ten)
		with self.assertRaises(frappe.PermissionError):
			tra_cuu("bat-ky-ma-nao")
