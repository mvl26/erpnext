"""Phiếu nhập lô — lược đồ và phép kiểm (spec khối C §5).

Thứ tự các phép kiểm là MỘT PHẦN của spec, không phải chi tiết cài đặt: câu báo
lỗi đầu tiên người dùng thấy phải là câu chỉ đúng chỗ sai. Kiểm độ dài mã vạch
trước khi kiểm trùng số lô thì người gõ nhầm một số lô dài sẽ được bảo là "trùng",
đi sửa sai chỗ.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.vi_tri_kho.tests.test_hook_nhap import _tao_item
from erpnext.vi_tri_kho.tests.test_lo_ncc import _ncc_thu, _phieu_nhap_nhap

CONG_TY = "Miyano Việt Nam"


def _phieu_nhap_lo(pr, dong: list[dict]):
	"""Dựng `Batch Entry` từ một phiếu nhập, KHÔNG submit."""
	be = frappe.get_doc({"doctype": "Batch Entry", "phieu_nhap": pr.name, "items": dong})
	return be


class TestValidate(FrappeTestCase):
	def setUp(self):
		self.ncc = _ncc_thu()
		self.item = _tao_item("_Test NhapLo Co Lo", co_lo=1)
		self.kho = frappe.db.get_value("Warehouse", {"company": CONG_TY, "is_group": 0}, "name")
		self.pr = _phieu_nhap_nhap(self.item, self.kho, self.ncc)
		self.dong_pr = self.pr.items[0].name

	def _dong(self, **ghi_de):
		d = {
			"dong_phieu_nhap": self.dong_pr,
			"vat_tu": self.item,
			"kho": self.kho,
			"so_luong": 10,
			"so_lo": "LO-TEST-01",
			"hsd": "2030-01-31",
		}
		d.update(ghi_de)
		return d

	def test_phieu_hop_le_thi_luu_duoc(self):
		be = _phieu_nhap_lo(self.pr, [self._dong()])
		be.insert(ignore_permissions=True)
		self.assertEqual(be.nha_cung_cap, self.ncc)

	def test_phieu_nhap_da_submit_thi_chan(self):
		"""Và câu báo phải nói rõ THỨ TỰ đúng, vì đây là lỗi thao tác chứ không
		phải lỗi dữ liệu — người dùng cần biết làm gì tiếp, không phải biết cái
		gì sai."""
		self.pr.submit()
		be = _phieu_nhap_lo(self.pr, [self._dong()])
		with self.assertRaises(frappe.ValidationError) as ngu_canh:
			be.insert(ignore_permissions=True)
		self.assertIn("trước", str(ngu_canh.exception))

	def test_hai_dong_cung_mot_dong_phieu_nhap_thi_chan(self):
		"""Spec §5.4 — một dòng phiếu nhập = một lô."""
		be = _phieu_nhap_lo(
			self.pr, [self._dong(so_lo="LO-A"), self._dong(so_lo="LO-B")]
		)
		with self.assertRaises(frappe.ValidationError):
			be.insert(ignore_permissions=True)

	def test_dong_khong_thuoc_phieu_nhap_dang_chon_thi_chan(self):
		"""Chốt âm: bỏ phép kiểm này ra thì một `dong_phieu_nhap` chép nhầm từ
		phiếu khác sẽ ghi `batch_no` lên một chứng từ KHÔNG liên quan, lúc submit."""
		pr2 = _phieu_nhap_nhap(self.item, self.kho, self.ncc)
		be = _phieu_nhap_lo(self.pr, [self._dong(dong_phieu_nhap=pr2.items[0].name)])
		with self.assertRaises(frappe.ValidationError):
			be.insert(ignore_permissions=True)

	def test_so_lo_bi_cat_khoang_trang_hai_dau(self):
		"""`d.so_lo = (d.so_lo or "").strip()` trong `kiem_tra_so_lo` làm HAI việc,
		không phải một: (1) chặn số lô rỗng — việc này THỪA vì field đã có
		`reqd: 1`, Frappe tự chặn bằng mandatory-field check trước khi tới được
		`validate()` của ta; (2) CHUẨN HOÁ — cắt khoảng trắng thừa ở hai đầu một
		số lô CÒN LẠI ký tự hợp lệ. Việc (2) không thừa chút nào:
		`Batch.autoname` lấy thẳng `batch_id` làm TÊN BẢN GHI, nên khoảng trắng
		thừa đi thẳng vào tên lô, vào mã vạch trên nhãn — máy quét ở kho đọc ra
		một chuỗi không khớp gì cả, hoặc tệ hơn là khớp nhầm. Hỏng âm thầm, trên
		vật thể đã dán lên hàng.

		Bản đầu của bài này (`test_so_lo_chi_co_khoang_trang_thi_chan`) kiểm vế
		(1) bằng `so_lo = "   "`: `reqd: 1` đã lo phần đó rồi nên bài không khoá
		được gì — mutation test xác nhận xoá `.strip()` khỏi `kiem_tra_so_lo`
		không làm bài đó đỏ. Đổi sang kiểm đúng vế (2), đừng đổi ngược lại."""
		be = _phieu_nhap_lo(self.pr, [self._dong(so_lo="  LO-TRANG  ")])
		be.insert(ignore_permissions=True)
		self.assertEqual(be.items[0].so_lo, "LO-TRANG")

	def test_so_lo_qua_dai_thi_chan_truoc_moi_phep_kiem_khac(self):
		"""Thứ tự: mã vạch trước, trùng lô sau. Xem docstring đầu file."""
		be = _phieu_nhap_lo(self.pr, [self._dong(so_lo="A" * 30)])
		with self.assertRaises(frappe.ValidationError) as ngu_canh:
			be.insert(ignore_permissions=True)
		self.assertIn("module", str(ngu_canh.exception))

	def test_so_lo_trung_voi_lo_cua_mat_hang_khac_thi_chan(self):
		item2 = _tao_item("_Test NhapLo Co Lo 2", co_lo=1)
		frappe.get_doc(
			{"doctype": "Batch", "batch_id": "LO-DUNG-CHUNG", "item": item2}
		).insert(ignore_permissions=True)
		be = _phieu_nhap_lo(self.pr, [self._dong(so_lo="LO-DUNG-CHUNG")])
		with self.assertRaises(frappe.ValidationError) as ngu_canh:
			be.insert(ignore_permissions=True)
		self.assertIn(item2, str(ngu_canh.exception))

	def test_so_lo_trung_voi_lo_cua_CHINH_mat_hang_nay_thi_cho_qua(self):
		"""Lô thứ hai về cùng một số lô là chuyện thật (NCC giao làm hai đợt).
		Chặn ở đây là chặn một nghiệp vụ hợp lệ. Task 6 sẽ DÙNG LẠI lô đó thay
		vì tạo mới."""
		frappe.get_doc(
			{"doctype": "Batch", "batch_id": "LO-DOT-2", "item": self.item}
		).insert(ignore_permissions=True)
		be = _phieu_nhap_lo(self.pr, [self._dong(so_lo="LO-DOT-2")])
		be.insert(ignore_permissions=True)

	def test_hsd_truoc_ngay_san_xuat_thi_chan(self):
		be = _phieu_nhap_lo(
			self.pr, [self._dong(ngay_san_xuat="2030-02-01", hsd="2030-01-31")]
		)
		with self.assertRaises(frappe.ValidationError):
			be.insert(ignore_permissions=True)


class TestSubmit(FrappeTestCase):
	def setUp(self):
		self.ncc = _ncc_thu()
		self.item = _tao_item("_Test NhapLo Co Lo", co_lo=1)
		self.kho = frappe.db.get_value("Warehouse", {"company": CONG_TY, "is_group": 0}, "name")
		self.pr = _phieu_nhap_nhap(self.item, self.kho, self.ncc)
		self.dong_pr = self.pr.items[0].name

	def _dong(self, **ghi_de):
		d = {
			"dong_phieu_nhap": self.dong_pr,
			"vat_tu": self.item,
			"kho": self.kho,
			"so_luong": 10,
			"so_lo": "LO-TEST-01",
			"hsd": "2030-01-31",
		}
		d.update(ghi_de)
		return d

	def test_submit_tao_lo_day_du(self):
		be = _phieu_nhap_lo(self.pr, [self._dong(so_lo="LO-SUBMIT-1")])
		be.insert(ignore_permissions=True)
		be.submit()
		lo = frappe.get_doc("Batch", "LO-SUBMIT-1")
		self.assertEqual(lo.item, self.item)
		self.assertEqual(str(lo.expiry_date), "2030-01-31")
		self.assertEqual(lo.supplier, self.ncc)
		self.assertEqual(lo.reference_doctype, "Purchase Receipt")
		self.assertEqual(lo.reference_name, self.pr.name)
		self.assertTrue(lo.custom_so_goi)

	def test_submit_ghi_batch_no_len_dong_phieu_nhap(self):
		be = _phieu_nhap_lo(self.pr, [self._dong(so_lo="LO-SUBMIT-2")])
		be.insert(ignore_permissions=True)
		be.submit()
		self.assertEqual(
			frappe.db.get_value("Purchase Receipt Item", self.dong_pr, "batch_no"),
			"LO-SUBMIT-2",
		)

	def test_phieu_nhap_submit_sau_do_khong_sinh_lo_may_nao_nua(self):
		"""Đây là bài chứng minh cả thiết kế chạy được.

		Nếu `batch_no` không tới được `stock_controller`, ERPNext sẽ tự sinh một
		lô theo `batch_number_series` của mặt hàng và số lô của NCC thành vô dụng
		— đúng thứ cả khối C sinh ra để tránh.
		"""
		be = _phieu_nhap_lo(self.pr, [self._dong(so_lo="LO-SUBMIT-3")])
		be.insert(ignore_permissions=True)
		be.submit()
		truoc = frappe.db.count("Batch", {"item": self.item})
		self.pr.reload()
		self.pr.submit()
		self.assertEqual(frappe.db.count("Batch", {"item": self.item}), truoc)

	def test_so_goi_khac_nhau_giua_hai_lo(self):
		"""Số gọi là thứ người ta ĐỌC CHO NHAU qua kho. Trùng nhau thì câu nói
		trỏ vào hai thùng hàng khác nhau."""
		be1 = _phieu_nhap_lo(self.pr, [self._dong(so_lo="LO-GOI-1")])
		be1.insert(ignore_permissions=True)
		be1.submit()

		# Lô thứ hai phải thuộc một DÒNG PHIẾU NHẬP khác (§5.4: một dòng chỉ
		# nhận một lô) nên dựng một phiếu nhập thứ hai cho cùng mặt hàng.
		pr2 = _phieu_nhap_nhap(self.item, self.kho, self.ncc)
		be2 = frappe.get_doc(
			{
				"doctype": "Batch Entry",
				"phieu_nhap": pr2.name,
				"items": [
					{
						"dong_phieu_nhap": pr2.items[0].name,
						"vat_tu": self.item,
						"kho": self.kho,
						"so_luong": 10,
						"so_lo": "LO-GOI-2",
						"hsd": "2030-01-31",
					}
				],
			}
		)
		be2.insert(ignore_permissions=True)
		be2.submit()

		so_goi_1 = frappe.db.get_value("Batch", "LO-GOI-1", "custom_so_goi")
		so_goi_2 = frappe.db.get_value("Batch", "LO-GOI-2", "custom_so_goi")
		self.assertTrue(so_goi_1)
		self.assertTrue(so_goi_2)
		self.assertNotEqual(so_goi_1, so_goi_2)

	def test_dung_lai_lo_da_co_cua_chinh_mat_hang_nay(self):
		"""NCC giao làm hai đợt cùng một số lô. Không tạo mới, không nổ khoá
		chính — dùng lại, và điền HSD nếu lô cũ còn trống."""
		lo_cu = frappe.get_doc(
			{"doctype": "Batch", "batch_id": "LO-DOT-2B", "item": self.item}
		).insert(ignore_permissions=True)
		self.assertFalse(lo_cu.expiry_date)
		self.assertFalse(lo_cu.custom_so_goi)

		be = _phieu_nhap_lo(self.pr, [self._dong(so_lo="LO-DOT-2B")])
		be.insert(ignore_permissions=True)
		# Không được nổ DuplicateEntryError — "LO-DOT-2B" đã là tên một
		# bản ghi Batch. Submit lỗi tức là mã đang cố TẠO MỚI thay vì DÙNG LẠI.
		be.submit()

		# Đúng MỘT bản ghi Batch tên này tồn tại — không có bản ghi đè lên.
		self.assertEqual(frappe.db.count("Batch", {"name": "LO-DOT-2B"}), 1)

		lo = frappe.get_doc("Batch", "LO-DOT-2B")
		self.assertEqual(str(lo.expiry_date), "2030-01-31")
		self.assertTrue(lo.custom_so_goi)

	def test_huy_khi_phieu_nhap_con_nhap_thi_go_batch_no_va_GIU_lo(self):
		"""Không xoá `Batch`: tem có thể đã in và đang dán trên thùng hàng. Xoá
		bản ghi biến tem thành rác không tra được."""
		be = _phieu_nhap_lo(self.pr, [self._dong(so_lo="LO-HUY-1")])
		be.insert(ignore_permissions=True)
		be.submit()
		self.assertEqual(
			frappe.db.get_value("Purchase Receipt Item", self.dong_pr, "batch_no"),
			"LO-HUY-1",
		)

		be.cancel()

		# Vế 1: batch_no bị GỠ khỏi dòng phiếu nhập.
		self.assertFalse(
			frappe.db.get_value("Purchase Receipt Item", self.dong_pr, "batch_no")
		)
		# Vế 2: bản ghi Batch vẫn CÒN — thiếu vế này thì một cài đặt xoá luôn
		# `Batch` khi huỷ vẫn làm bài xanh.
		self.assertTrue(frappe.db.exists("Batch", "LO-HUY-1"))

	def test_huy_khi_phieu_nhap_da_submit_thi_chan(self):
		"""Tồn đã ghi theo lô. Gỡ lô khỏi một chứng từ đã submit là việc của
		`Purchase Receipt.cancel`, không phải của phiếu này."""
		be = _phieu_nhap_lo(self.pr, [self._dong(so_lo="LO-HUY-2")])
		be.insert(ignore_permissions=True)
		be.submit()

		self.pr.reload()
		self.pr.submit()

		with self.assertRaises(frappe.ValidationError):
			be.cancel()

		# Chặn phải xảy ra TRƯỚC khi gỡ batch_no — dòng phiếu nhập còn nguyên.
		self.assertEqual(
			frappe.db.get_value("Purchase Receipt Item", self.dong_pr, "batch_no"),
			"LO-HUY-2",
		)
