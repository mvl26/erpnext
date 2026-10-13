"""Lấy số lô từ Serial and Batch Bundle, KHÔNG từ sle.batch_no.

ERPNext v15 không ghi batch_no lên Stock Ledger Entry nữa (field còn đó
nhưng bỏ không); số lô nằm ở các dòng con Serial and Batch Entry. Đo trên
erptest.local: 0/56 dòng SLE của hàng có lô mang batch_no, 56/56 mang
serial_and_batch_bundle.

Đọc sai chỗ này thì 80/164 mặt hàng ghi so_lo = NULL, gộp mọi lô làm một —
và báo cáo đối soát VẪN BÁO KHỚP vì tổng số lượng đúng. Bộ test này là lưới
duy nhất bắt được lớp lỗi đó.

Một dòng SLE có thể mang NHIỀU lô → trả về nhiều phần tử, không phải một.

Vòng sửa 1 (điều phối): huỷ chứng từ đảo dấu actual_qty trên SLE
(erpnext/stock/stock_ledger.py:80) nhưng KHÔNG đổi bản ghi Serial and Batch
Bundle đã submit — nên ở đường huỷ, tổng bundle và delta LỆCH DẤU nhau.
delta là TỔNG có thẩm quyền, bundle chỉ cho TỶ LỆ chia giữa các lô. Khi
khớp nhau: giữ nguyên dòng con. Khi lệch: scale theo delta, tổng sau scale
phải đúng tuyệt đối, không xấp xỉ.

Vòng sửa 2 (review): guard "tổng bundle ~0" phải chạy SAU khi so khớp
delta, dùng ngưỡng sai số chứ không so `== 0` tuyệt đối — nếu không, một
tổng bundle gần-0 do sai số dấu phẩy động (0.1+0.2-0.3 != 0) lọt qua guard
rồi bị dùng làm mẫu số, sinh số lượng khổng lồ (~1e16) dù tổng vẫn đúng
delta. Thêm bài test khoá nguyên danh sách cho ca scale (không chỉ
len/sum), bài cho nhánh không-có-dòng-con, và bài cho mẫu số gần-0.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.warehouse_operations.vitri.lo import tach_theo_lo


class _SleGia:
	"""Đủ thuộc tính cho tach_theo_lo, không cần chạm DB."""

	def __init__(self, bundle=None, batch_no=None):
		self.serial_and_batch_bundle = bundle
		self.batch_no = batch_no


class TestHangKhongLo(FrappeTestCase):
	def test_khong_bundle_khong_batch_thi_mot_dong_lo_rong(self):
		ket_qua = tach_theo_lo(_SleGia(), delta=7)
		self.assertEqual(ket_qua, [{"so_lo": None, "so_luong": 7}])

	def test_delta_am_giu_nguyen_dau(self):
		ket_qua = tach_theo_lo(_SleGia(), delta=-3)
		self.assertEqual(ket_qua, [{"so_lo": None, "so_luong": -3}])


class TestHangCoLo(FrappeTestCase):
	def setUp(self):
		self.bundle = frappe.get_doc(
			{
				"doctype": "Serial and Batch Bundle",
				"item_code": "_Test Item Lo",
				"warehouse": "Kho Miyano - MYN",
				"type_of_transaction": "Inward",
				"voucher_type": "Stock Entry",
				"entries": [
					{"batch_no": "_T-LO-1", "qty": 6},
					{"batch_no": "_T-LO-2", "qty": 4},
				],
			}
		)

	def test_mot_sle_nhieu_lo_tra_nhieu_dong(self):
		# dùng bundle giả trong DB để không phụ thuộc dữ liệu sẵn có
		ten = _luu_bundle_tho(self.bundle)
		ket_qua = tach_theo_lo(_SleGia(bundle=ten), delta=10)
		self.assertEqual(len(ket_qua), 2)
		self.assertEqual({d["so_lo"] for d in ket_qua}, {"_T-LO-1", "_T-LO-2"})
		self.assertEqual(sum(d["so_luong"] for d in ket_qua), 10)

	def test_khong_bao_gio_doc_sle_batch_no_khi_co_bundle(self):
		ten = _luu_bundle_tho(self.bundle)
		# batch_no cố tình sai — nếu hàm đọc nó thì bài này đỏ
		ket_qua = tach_theo_lo(_SleGia(bundle=ten, batch_no="LO-SAI"), delta=10)
		self.assertNotIn("LO-SAI", {d["so_lo"] for d in ket_qua})

	def test_khi_khong_lech_giu_nguyen_dong_con_khong_scale(self):
		"""Ca KHÔNG lệch: tổng bundle == delta → trả nguyên xi dòng con,
		không scale, không làm tròn mất mát. Khoá cả GIÁ TRỊ từng phần tử
		(6 và 4), không chỉ tổng — nếu code lỡ scale-rồi-làm-tròn ngay cả
		khi không cần, 6/10*10 vẫn ra 6 nên bài trên (test_mot_sle_...) không
		bắt được, bài này thì có (kiểm cả cặp giá trị, không chỉ set so_lo)."""
		ten = _luu_bundle_tho(self.bundle)
		ket_qua = tach_theo_lo(_SleGia(bundle=ten), delta=10)
		self.assertEqual(
			sorted(ket_qua, key=lambda d: d["so_lo"]),
			[{"so_lo": "_T-LO-1", "so_luong": 6}, {"so_lo": "_T-LO-2", "so_luong": 4}],
		)

	def test_huy_dao_dau_bundle_khong_doi_thi_scale_dao_dau_theo_delta(self):
		"""Vòng sửa 1 (điều phối): huỷ chứng từ đảo dấu actual_qty trên SLE
		(erpnext/stock/stock_ledger.py:80, sle["actual_qty"] = -flt(...)),
		nhưng KHÔNG đổi gì trên Serial and Batch Bundle đã submit trước đó.
		Ở đường huỷ (khi Task 9 không tìm được dòng sổ gốc để đảo — chứng từ
		lập trước khi kho bật quản lý vị trí), tổng bundle và delta LỆCH DẤU.
		Nếu bundle thắng, huỷ một phiếu NHẬP (+6, +4) sẽ ghi vào sổ vị trí
		như một phiếu XUẤT — tồn ma. Đây là bài chống lưng bắt buộc của
		vòng sửa 1; không có nó thì cả vòng sửa vô nghĩa.
		"""
		ten = _luu_bundle_tho(self.bundle)  # bundle vẫn dương: +6, +4 (tổng 10)
		ket_qua = tach_theo_lo(_SleGia(bundle=ten), delta=-10)
		self.assertEqual(
			sorted(ket_qua, key=lambda d: d["so_lo"]),
			[{"so_lo": "_T-LO-1", "so_luong": -6}, {"so_lo": "_T-LO-2", "so_luong": -4}],
		)
		self.assertEqual(sum(d["so_luong"] for d in ket_qua), -10)

	def test_khi_lech_scale_theo_delta_giu_ty_le_bundle(self):
		"""Ca lệch tổng quát, không phải huỷ: bundle tổng 10 (6+4, tỷ lệ
		3:2) nhưng delta=99. `delta` là tổng có thẩm quyền, bundle chỉ cho
		tỷ lệ — kết quả phải giữ đúng tỷ lệ 3:2 và tổng đúng 99, không phải
		giữ nguyên 6 và 4 (hành vi cũ trước vòng sửa 1, đã lỗi thời)."""
		ten = _luu_bundle_tho(self.bundle)
		ket_qua = tach_theo_lo(_SleGia(bundle=ten), delta=99)
		theo_lo = {d["so_lo"]: d["so_luong"] for d in ket_qua}
		self.assertEqual(theo_lo, {"_T-LO-1": 59.4, "_T-LO-2": 39.6})
		self.assertEqual(sum(theo_lo.values()), 99)

	def test_scale_le_tong_dung_bang_delta_khong_xap_xi(self):
		"""Ca scale lẻ: bundle ba lô bằng nhau (1,1,1 — tổng 3) không chia
		hết delta=10. Yêu cầu bắt buộc: TỔNG sau scale đúng bằng delta,
		không phải xấp xỉ — làm tròn từng phần tử rồi cộng dồn sẽ lệch vài
		phần nghìn, và cái lệch đó chảy thẳng vào sổ vị trí.

		Vòng sửa 2 (review): khoá NGUYÊN DANH SÁCH, không chỉ len/sum — một
		cài đặt trả [10, 0, 0] vẫn đúng len=3 và sum=10 nhưng phá nát tỷ lệ
		giữa các lô, bài trước không bắt được điều đó."""
		ten = _luu_bundle_tho(_bundle_ba_lo_bang_nhau())
		ket_qua = tach_theo_lo(_SleGia(bundle=ten), delta=10)
		self.assertEqual(
			ket_qua,
			[
				{"so_lo": "_T-LO-LE-1", "so_luong": 3.333333},
				{"so_lo": "_T-LO-LE-2", "so_luong": 3.333333},
				{"so_lo": "_T-LO-LE-3", "so_luong": 3.333334},
			],
		)

	def test_scale_le_delta_am_tong_dung_bang_delta(self):
		"""Biến thể delta âm của bài trên — đảm bảo remainder-ở-phần-tử-cuối
		vẫn ép tổng đúng tuyệt đối khi delta âm, không chỉ khi delta dương."""
		ten = _luu_bundle_tho(_bundle_ba_lo_bang_nhau())
		ket_qua = tach_theo_lo(_SleGia(bundle=ten), delta=-10)
		self.assertEqual(
			ket_qua,
			[
				{"so_lo": "_T-LO-LE-1", "so_luong": -3.333333},
				{"so_lo": "_T-LO-LE-2", "so_luong": -3.333333},
				{"so_lo": "_T-LO-LE-3", "so_luong": -3.333334},
			],
		)
		self.assertEqual(sum(d["so_luong"] for d in ket_qua), -10)

	def test_bundle_khong_co_dong_con_thi_mot_dong_lo_rong(self):
		"""Vòng sửa 2 (review): nhánh `not dong` chưa có bài test riêng —
		bundle có thật nhưng không có dòng Serial and Batch Entry con nào
		(ví dụ dữ liệu hỏng) phải rơi về một dòng chung, không được lỗi."""
		bundle_rong = frappe.get_doc(
			{
				"doctype": "Serial and Batch Bundle",
				"item_code": "_Test Item Lo",
				"warehouse": "Kho Miyano - MYN",
				"type_of_transaction": "Inward",
				"voucher_type": "Stock Entry",
				"entries": [],
			}
		)
		ten = _luu_bundle_tho(bundle_rong)
		ket_qua = tach_theo_lo(_SleGia(bundle=ten), delta=5)
		self.assertEqual(ket_qua, [{"so_lo": None, "so_luong": 5}])

	def test_tong_bundle_gan_khong_do_sai_so_dau_phay_dong_khong_no_so(self):
		"""Vòng sửa 2 (review) — lỗ Important: dòng con [0.1, 0.2, -0.3]
		cộng lại ra 5.55e-17 (không bằng 0 tuyệt đối, do sai số dấu phẩy
		động), KHÔNG bằng delta=5. Nếu guard so `tong_bundle == 0` chính
		xác và chạy trước khi so khớp delta, ca này lọt qua và rơi vào
		nhánh scale rồi CHIA CHO SỐ GẦN-0 → số lượng từng lô cỡ ±1e16 dù
		tổng vẫn đúng bằng delta (đối soát Task 10 không bắt được). Bài
		này khẳng định không có số nào vượt quá |delta| — không nổ số."""
		bundle_gan_khong = frappe.get_doc(
			{
				"doctype": "Serial and Batch Bundle",
				"item_code": "_Test Item Lo",
				"warehouse": "Kho Miyano - MYN",
				"type_of_transaction": "Inward",
				"voucher_type": "Stock Entry",
				"entries": [
					{"batch_no": "_T-LO-GK-1", "qty": 0.1},
					{"batch_no": "_T-LO-GK-2", "qty": 0.2},
					{"batch_no": "_T-LO-GK-3", "qty": -0.3},
				],
			}
		)
		ten = _luu_bundle_tho(bundle_gan_khong)
		ket_qua = tach_theo_lo(_SleGia(bundle=ten), delta=5)
		for d in ket_qua:
			self.assertLessEqual(
				abs(d["so_luong"]),
				5,
				f"số lượng {d['so_luong']} vượt quá |delta|=5 — mẫu số gần-0 đã bị chia",
			)
		self.assertEqual(sum(d["so_luong"] for d in ket_qua), 5)


def _bundle_ba_lo_bang_nhau():
	"""Bundle ba lô bằng nhau (1,1,1) — dùng cho các bài scale lẻ."""
	return frappe.get_doc(
		{
			"doctype": "Serial and Batch Bundle",
			"item_code": "_Test Item Lo",
			"warehouse": "Kho Miyano - MYN",
			"type_of_transaction": "Inward",
			"voucher_type": "Stock Entry",
			"entries": [
				{"batch_no": "_T-LO-LE-1", "qty": 1},
				{"batch_no": "_T-LO-LE-2", "qty": 1},
				{"batch_no": "_T-LO-LE-3", "qty": 1},
			],
		}
	)


def _luu_bundle_tho(doc):
	"""Ghi thẳng bundle + dòng con, bỏ qua validate của ERPNext.

	Bundle thật cần Item bật lô, kho, và ràng buộc tồn — dựng đủ ngần ấy chỉ
	để test một hàm đọc là quá tốn. Ghi thô giữ bài test nhanh và đúng trọng tâm.
	"""
	ten = frappe.generate_hash(length=20)
	frappe.db.sql(
		"""insert into `tabSerial and Batch Bundle`
		   (name, creation, modified, owner, modified_by, item_code, warehouse, voucher_type, docstatus)
		   values (%s, now(), now(), 'Administrator', 'Administrator', %s, %s, %s, 1)""",
		(ten, doc.item_code, doc.warehouse, doc.voucher_type),
	)
	for i, e in enumerate(doc.entries):
		# `doc.entries` là các Document con (frappe.get_doc đã tự chuyển các
		# dict lúc dựng), không còn là dict — phải đọc bằng thuộc tính, không
		# subscript. Đây là chỗ lệch duy nhất so với brief (xem báo cáo).
		frappe.db.sql(
			"""insert into `tabSerial and Batch Entry`
			   (name, creation, modified, owner, modified_by, parent, parenttype, parentfield, idx, batch_no, qty)
			   values (%s, now(), now(), 'Administrator', 'Administrator', %s,
			           'Serial and Batch Bundle', 'entries', %s, %s, %s)""",
			(frappe.generate_hash(length=20), ten, i + 1, e.batch_no, e.qty),
		)
	return ten
