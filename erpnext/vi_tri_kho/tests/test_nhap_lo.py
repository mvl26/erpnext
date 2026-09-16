"""Phiếu nhập lô — lược đồ và phép kiểm (spec khối C §5).

Thứ tự các phép kiểm là MỘT PHẦN của spec, không phải chi tiết cài đặt: câu báo
lỗi đầu tiên người dùng thấy phải là câu chỉ đúng chỗ sai. Kiểm độ dài mã vạch
trước khi kiểm trùng số lô thì người gõ nhầm một số lô dài sẽ được bảo là "trùng",
đi sửa sai chỗ.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.vi_tri_kho.tests.test_hook_nhap import _tao_item
from erpnext.vi_tri_kho.tests.test_lo_ncc import _ncc_thu, _ncc_thu_2, _phieu_nhap_nhap
from erpnext.vi_tri_kho.vitri.nhap_lo import dat_o_in_tem, du_lieu_tem, lay_dong_tu_phieu_nhap

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

	def test_so_lo_co_ky_tu_ngoai_ascii_bi_chan_ngay_o_validate(self):
		"""Khoá DÂY NỐI giữa `BatchEntry.validate` và `ma_vach.kiem_tra_ky_tu`.

		`test_ma_vach` đã khoá bản thân phép kiểm; bài này khoá việc nó ĐƯỢC GỌI.
		Nếu dây nối đứt thì phiếu lưu được, và tới lúc in thì JsBarcode ném lỗi,
		`barcode.js` nuốt lỗi, SVG giữ nguyên nội dung lần vẽ trước — tem của lô
		này in ra mã vạch của lô LIỀN TRƯỚC trong cùng xấp, không một dấu hiệu
		nào. Đã tái hiện được trên trình duyệt.
		"""
		for xau in ("LÔ-2026", "7Fr\u20132026"):
			with self.subTest(so_lo=xau):
				be = _phieu_nhap_lo(self.pr, [self._dong(so_lo=xau)])
				with self.assertRaises(frappe.ValidationError) as ctx:
					be.insert(ignore_permissions=True)
				# Câu báo phải nêu đích danh ký tự vi phạm, không phải câu chung
				# chung — xem docstring `kiem_tra_ky_tu`.
				self.assertIn("U+", str(ctx.exception))

	def test_so_lo_ascii_thuan_van_luu_duoc(self):
		"""Vế còn lại: phép kiểm ký tự KHÔNG được chặn nhầm số lô hợp lệ."""
		be = _phieu_nhap_lo(self.pr, [self._dong(so_lo="LOT-2026-A45")])
		be.insert(ignore_permissions=True)
		self.assertEqual(be.items[0].so_lo, "LOT-2026-A45")

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
		be = _phieu_nhap_lo(
			self.pr, [self._dong(so_lo="LO-SUBMIT-1", ngay_san_xuat="2029-06-01")]
		)
		be.insert(ignore_permissions=True)
		be.submit()
		lo = frappe.get_doc("Batch", "LO-SUBMIT-1")
		self.assertEqual(lo.item, self.item)
		self.assertEqual(str(lo.expiry_date), "2030-01-31")
		# manufacturing_date (vòng sửa 1, Việc 2): nhánh TẠO MỚI (batch_entry.py,
		# `_dam_bao_lo`, dict `insert()`) — mutation xoá riêng trường này khỏi
		# dict đó phải làm assert dưới đỏ, độc lập với bài dùng-lại-lô.
		self.assertEqual(str(lo.manufacturing_date), "2029-06-01")
		self.assertEqual(lo.supplier, self.ncc)
		self.assertEqual(lo.reference_doctype, "Purchase Receipt")
		self.assertEqual(lo.reference_name, self.pr.name)
		self.assertTrue(lo.custom_so_goi)

		# "Produces" của brief: mỗi dòng phiếu nhập lô cũng phải có lo_da_tao và
		# so_goi sau submit. Đọc lại từ DB (không dùng be.items[0] trong bộ nhớ)
		# vì `db_set` cũng sửa bản ghi trong bộ nhớ — đọc DB mới thật sự khoá
		# được việc ghi đã XUỐNG được CSDL, không chỉ đứng trong RAM.
		dong = be.items[0].name
		self.assertEqual(
			frappe.db.get_value("Batch Entry Item", dong, "lo_da_tao"), "LO-SUBMIT-1"
		)
		self.assertEqual(
			frappe.db.get_value("Batch Entry Item", dong, "so_goi"), lo.custom_so_goi
		)

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
		chính — dùng lại, và điền HSD nếu lô cũ còn trống.

		`manufacturing_date` của lô cũ được khai SẴN (2028-06-01) còn
		`expiry_date` để TRỐNG — cố tình lệch nhau để một bài chỉ khẳng định
		"đã điền HSD" không đủ phân biệt "chỉ điền chỗ trống" với "ghi đè hết":
		nếu mã ghi đè vô điều kiện, `manufacturing_date` sẽ đổi thành
		`ngay_san_xuat` của dòng phiếu nhập (2029-01-01) — khác 2028-06-01, lộ
		ngay. Đây chính là nhánh "Chỉ ĐIỀN CHỖ TRỐNG, không ghi đè" trong
		`_dam_bao_lo` — lô cũ có thể đã in tem với ngày cũ.
		"""
		lo_cu = frappe.get_doc(
			{
				"doctype": "Batch",
				"batch_id": "LO-DOT-2B",
				"item": self.item,
				"manufacturing_date": "2028-06-01",
			}
		).insert(ignore_permissions=True)
		self.assertFalse(lo_cu.expiry_date)
		self.assertFalse(lo_cu.custom_so_goi)

		be = _phieu_nhap_lo(
			self.pr, [self._dong(so_lo="LO-DOT-2B", ngay_san_xuat="2029-01-01")]
		)
		be.insert(ignore_permissions=True)
		# Không được nổ DuplicateEntryError — "LO-DOT-2B" đã là tên một
		# bản ghi Batch. Submit lỗi tức là mã đang cố TẠO MỚI thay vì DÙNG LẠI.
		be.submit()

		# Đúng MỘT bản ghi Batch tên này tồn tại — không có bản ghi đè lên.
		self.assertEqual(frappe.db.count("Batch", {"name": "LO-DOT-2B"}), 1)

		lo = frappe.get_doc("Batch", "LO-DOT-2B")
		# Chỗ TRỐNG (expiry_date) được điền từ dòng phiếu nhập.
		self.assertEqual(str(lo.expiry_date), "2030-01-31")
		# Chỗ ĐÃ CÓ (manufacturing_date) giữ nguyên — không bị ghi đè bởi
		# ngay_san_xuat="2029-01-01" của dòng phiếu nhập.
		self.assertEqual(str(lo.manufacturing_date), "2028-06-01")
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

		# assertIn nội dung câu báo (vòng sửa 1, Việc 4): `LinkExistsError` cũng
		# là con của `ValidationError`, nên `assertRaises(ValidationError)` một
		# mình có thể xanh vì một lỗi HOÀN TOÀN KHÁC (vd: khoá chết Việc 1 nếu
		# nó tái phát). Mẩu câu dưới đây chỉ xuất hiện trong guard của
		# `on_cancel`, theo đúng tiền lệ `assertIn("trước", ...)` ở trên.
		with self.assertRaises(frappe.ValidationError) as ngu_canh:
			be.cancel()
		self.assertIn("không huỷ phiếu nhập lô được", str(ngu_canh.exception))

		# Chặn phải xảy ra TRƯỚC khi gỡ batch_no — dòng phiếu nhập còn nguyên.
		self.assertEqual(
			frappe.db.get_value("Purchase Receipt Item", self.dong_pr, "batch_no"),
			"LO-HUY-2",
		)

	def test_huy_ca_pr_lan_be_khong_khoa_chet_nhau(self):
		"""Vòng sửa 1, Việc 1 — khoá chết thật đã đo: NCC giao sai, thủ kho
		duyệt `Batch Entry`, kế toán duyệt `Purchase Receipt`, rồi cả hai đều
		cần huỷ. Trước bản vá: huỷ PR → `LinkExistsError` (BE đã duyệt còn
		trỏ tới PR qua `phieu_nhap`, mà `"Batch Entry"` không nằm trong
		`ignore_linked_doctypes` của PR); huỷ BE trước thì guard cũ (`!= 0`)
		chặn luôn cả trường hợp PR ĐÃ HUỶ — không còn đường thoát nào, cả hai
		chứng từ kẹt vĩnh viễn ở docstatus 1.

		Bài này đi ĐÚNG thứ tự kế toán làm thật: huỷ PR trước (phải THÀNH
		CÔNG), huỷ BE sau (phải THÀNH CÔNG), và `Batch` phải còn nguyên ở cuối
		đường — tem đã in không thành rác.
		"""
		be = _phieu_nhap_lo(self.pr, [self._dong(so_lo="LO-KHOA-1")])
		be.insert(ignore_permissions=True)
		be.submit()

		self.pr.reload()
		self.pr.submit()

		# Huỷ PR TRƯỚC — không được ném LinkExistsError.
		self.pr.reload()
		self.pr.cancel()

		# Huỷ BE SAU — PR giờ docstatus=2 (đã huỷ), guard chỉ chặn khi == 1.
		be.reload()
		be.cancel()

		self.assertTrue(frappe.db.exists("Batch", "LO-KHOA-1"))

	def test_dung_lai_lo_dien_manufacturing_date_dang_trong(self):
		"""Vòng sửa 1, Việc 2 — mặt lật của `test_dung_lai_lo_da_co_cua_chinh_
		mat_hang_nay`: ở đó `expiry_date` được điền còn `manufacturing_date`
		được BẢO TOÀN (đã có sẵn). Bài đó không khoá được nhánh NGƯỢC LẠI —
		`manufacturing_date` ĐANG TRỐNG phải được ĐIỀN. Xoá riêng
		`("manufacturing_date", d.ngay_san_xuat)` khỏi vòng điền-chỗ-trống của
		nhánh dùng lại thì bài đó vẫn xanh (vì ở đó trường này không trống),
		còn bài NÀY sẽ đỏ.

		`manufacturing_date` có `default: "Today"` ở LƯỢC ĐỒ LÕI
		(`erpnext/stock/doctype/batch/batch.json`) — đã xác minh bằng
		`bench console`: một `insert()` bình thường KHÔNG BAO GIỜ để trống
		được trường này, kể cả truyền `None` tường minh (default thắng None).
		Ép trống bằng `frappe.db.set_value` thẳng xuống CSDL ngay sau khi tạo —
		mô phỏng lô cũ nhập từ hệ thống trước khi có trường này, hoặc từ một
		đường tạo lô không đi qua `Document.insert()` bình thường.
		"""
		lo_cu = frappe.get_doc(
			{
				"doctype": "Batch",
				"batch_id": "LO-DOT-2C",
				"item": self.item,
				"expiry_date": "2031-12-31",
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Batch", lo_cu.name, "manufacturing_date", None)
		self.assertFalse(frappe.db.get_value("Batch", lo_cu.name, "manufacturing_date"))

		be = _phieu_nhap_lo(
			self.pr,
			[self._dong(so_lo="LO-DOT-2C", hsd="2031-12-31", ngay_san_xuat="2030-01-01")],
		)
		be.insert(ignore_permissions=True)
		be.submit()

		lo = frappe.get_doc("Batch", "LO-DOT-2C")
		self.assertEqual(str(lo.manufacturing_date), "2030-01-01")
		# Chỗ ĐÃ CÓ (expiry_date) vẫn được bảo toàn — kiểm chéo cho chắc.
		self.assertEqual(str(lo.expiry_date), "2031-12-31")

	def test_submit_tao_lo_moi_dung_ncc_cua_batch_entry_khong_dua_vao_moc(self):
		"""Vòng sửa 1, Việc 3 — `lo.supplier` trong `test_submit_tao_lo_day_du`
		KHÔNG phân biệt được "gán tường minh" với "móc `dien_ncc_tu_chung_tu`
		(before_insert) tự điền lại": `nha_cung_cap` trên `Batch Entry` là
		`fetch_from: phieu_nhap.supplier`, và Frappe fetch lại giá trị đó ở
		MỌI lần lưu (kể cả submit, xem `base_document.py::get_invalid_links` —
		`fetch_if_empty` không được đặt cho field này) — nên tại thời điểm
		`on_submit` chạy, `self.nha_cung_cap` LUÔN LUÔN bằng đúng
        `frappe.db.get_value("Purchase Receipt", reference_name, "supplier")`,
		tức đúng giá trị móc sẽ tự suy ra. Không dữ liệu thật nào tách được
		hai đường qua `submit()` bình thường — đã xác minh bằng cách đọc mã
		nguồn Frappe, không đoán.

		Bài này gọi thẳng `_dam_bao_lo` (bạch hộp) với `nha_cung_cap` bị ép
		thành MỘT NCC KHÁC hẳn NCC thật của phiếu nhập (`_ncc_thu_2`, đúng mẫu
		`test_lo_ncc.py`): nếu `_dam_bao_lo` không tự gán `supplier` tường
		minh, `Batch` mới tạo sẽ lấy NCC THẬT của phiếu nhập (`self.ncc`) qua
		móc — khác `ncc_khac` — lộ ra ngay.
		"""
		ncc_khac = _ncc_thu_2()
		be = frappe.new_doc("Batch Entry")
		be.phieu_nhap = self.pr.name
		be.nha_cung_cap = ncc_khac
		d = frappe._dict(so_lo="LO-SUP-DIR", vat_tu=self.item, hsd=None, ngay_san_xuat=None)

		lo = be._dam_bao_lo(d)

		self.assertEqual(lo.supplier, ncc_khac)
		# Đối chứng: NCC thật của phiếu nhập KHÁC ncc_khac — nếu trùng nhau thì
		# bài này cũng không phân biệt được gì, giống lỗi ban đầu.
		self.assertNotEqual(ncc_khac, self.ncc)

	def test_dong_da_bi_be_khac_da_duyet_phu_thi_chan(self):
		"""Vòng sửa 1, Việc 5 — lớp 1 (validate): chặn NGAY LÚC TẠO, không cho
		một `Batch Entry` thứ hai phủ lên dòng đã có `Batch Entry` KHÁC đã
		duyệt. `kiem_tra_dong_thuoc_phieu` chỉ khử trùng TRONG một `Batch
		Entry` — không thấy được xung đột GIỮA hai `Batch Entry` khác nhau."""
		be1 = _phieu_nhap_lo(self.pr, [self._dong(so_lo="LO-PHU-1")])
		be1.insert(ignore_permissions=True)
		be1.submit()

		be2 = _phieu_nhap_lo(self.pr, [self._dong(so_lo="LO-PHU-2")])
		with self.assertRaises(frappe.ValidationError) as ngu_canh:
			be2.insert(ignore_permissions=True)
		self.assertIn(be1.name, str(ngu_canh.exception))

	def test_be_da_huy_khong_chan_be_moi_tren_cung_dong(self):
		"""Mặt lật của bài trên — chốt đúng chữ "ĐÃ DUYỆT" trong bộ lọc
		`docstatus: 1` của `kiem_tra_dong_chua_bi_be_khac_phu`. Huỷ BE1 rồi
		khai lại là đường SỬA SAI DUY NHẤT khi phiếu nhập còn nháp (gõ nhầm số
		lô, huỷ BE, khai lại) — nới bộ lọc ra khớp cả `Batch Entry` đã huỷ thì
		dòng phiếu nhập này khoá chết VĨNH VIỄN, không phiếu nhập lô nào khai
		lại được nữa. Đúng loại khoá chết Việc 1 vừa gỡ, chỉ khác lớp."""
		be1 = _phieu_nhap_lo(self.pr, [self._dong(so_lo="LO-PHU-4")])
		be1.insert(ignore_permissions=True)
		be1.submit()
		be1.cancel()

		be2 = _phieu_nhap_lo(self.pr, [self._dong(so_lo="LO-PHU-5")])
		be2.insert(ignore_permissions=True)
		be2.submit()
		self.assertEqual(
			frappe.db.get_value("Purchase Receipt Item", self.dong_pr, "batch_no"),
			"LO-PHU-5",
		)

	def test_huy_khong_go_batch_no_neu_da_bi_ghi_de_boi_lo_khac(self):
		"""Vòng sửa 1, Việc 5 — lớp 2 (on_cancel), ĐỘC LẬP với lớp 1: nếu
		`batch_no` trên dòng phiếu nhập KHÔNG CÒN bằng đúng lô do CHÍNH `Batch
		Entry` này tạo (một cơ chế khác đã ghi đè), huỷ `Batch Entry` này
		không được xoá giá trị đó. Mô phỏng "cơ chế khác" bằng
		`frappe.db.set_value` thẳng xuống CSDL — không cần dựng lại toàn bộ
		đường một `Batch Entry` thứ hai đi qua để chứng minh lớp phòng vệ
		THỨ HAI này tự đứng vững một mình, không dựa vào lớp 1 phía trên."""
		be = _phieu_nhap_lo(self.pr, [self._dong(so_lo="LO-PHU-3")])
		be.insert(ignore_permissions=True)
		be.submit()
		self.assertEqual(
			frappe.db.get_value("Purchase Receipt Item", self.dong_pr, "batch_no"),
			"LO-PHU-3",
		)

		frappe.get_doc(
			{"doctype": "Batch", "batch_id": "LO-PHU-3B", "item": self.item}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Purchase Receipt Item", self.dong_pr, "batch_no", "LO-PHU-3B")

		be.cancel()

		self.assertEqual(
			frappe.db.get_value("Purchase Receipt Item", self.dong_pr, "batch_no"),
			"LO-PHU-3B",
		)

	def test_dung_lai_lo_dien_ncc_va_chung_tu_dang_trong(self):
		"""Vòng sửa 1, Việc 6: lô do hộp thoại lô sẵn có của ERPNext tạo có thể
		trống cả NCC lẫn chứng từ tham chiếu (`reference_doctype`/
		`reference_name`) — dùng lại lô đó qua phiếu nhập lô phải ĐIỀN, không
		thì tra "lô này của NCC nào, về theo chứng từ nào" mãi mãi ra rỗng dù
		đã có đủ thông tin trong tay lúc submit."""
		lo_cu = frappe.get_doc(
			{"doctype": "Batch", "batch_id": "LO-DIEN-NCC", "item": self.item}
		).insert(ignore_permissions=True)
		self.assertFalse(lo_cu.supplier)
		self.assertFalse(lo_cu.reference_name)

		be = _phieu_nhap_lo(self.pr, [self._dong(so_lo="LO-DIEN-NCC")])
		be.insert(ignore_permissions=True)
		be.submit()

		lo = frappe.get_doc("Batch", "LO-DIEN-NCC")
		self.assertEqual(lo.supplier, self.ncc)
		self.assertEqual(lo.reference_doctype, "Purchase Receipt")
		self.assertEqual(lo.reference_name, self.pr.name)


def _o_vt(ma_o, kho, **kw):
	"""Nút vị trí — tham số hoá `kho` (khác `KHO` cứng của các bộ test khác)
	vì ở đây `kho` suy từ `CONG_TY` của bộ test này."""
	if not frappe.db.exists("Storage Location", ma_o):
		frappe.get_doc({"doctype": "Storage Location", "ma_o": ma_o, "kho": kho, **kw}).insert(
			ignore_permissions=True
		)
	return ma_o


def _gan_vt(vat_tu, vi_tri, kho):
	return frappe.get_doc(
		{"doctype": "Item Location Preference", "vat_tu": vat_tu, "kho": kho, "vi_tri": vi_tri}
	).insert(ignore_permissions=True)


def _tao_item_tem(ma, quy_doi=None, thong_so=None, co_lo=1):
	"""Mặt hàng đủ trường cho `du_lieu_tem`: `custom_thong_so_tem` (F4) và các
	dòng quy đổi ĐVT (F3, §6.3) — `_tao_item` (test_hook_nhap.py) không có."""
	if not frappe.db.exists("Item", ma):
		doc = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": ma,
				"item_name": ma,
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"has_batch_no": co_lo,
				"create_new_batch": co_lo,
				"batch_number_series": f"{ma}-.###" if co_lo else None,
				"custom_thong_so_tem": thong_so or "",
			}
		)
		for uom, cf in quy_doi or []:
			doc.append("uoms", {"uom": uom, "conversion_factor": cf})
		doc.insert(ignore_permissions=True)
	return ma


class TestApiMayChu(FrappeTestCase):
	"""API máy chủ cho màn hình `Batch Entry` và cho việc in nhãn (Task 7).

	`FrappeTestCase` chỉ rollback ở `tearDownClass` (xem `frappe/tests/
	utils.py::_rollback_db`, gắn qua `addClassCleanup`), KHÔNG rollback theo
	từng phương thức — cùng bẫy đã ghi ở `test_gan_vi_tri.py`/`test_goi_y_o.py`.
	Mỗi bài dưới đây tự tạo mặt hàng/mã ô/số lô TÊN RIÊNG (không dùng chung
	giữa các bài) để không đụng khoá chính của bài chạy trước trong cùng lớp.
	"""

	def test_lay_dong_chi_lay_mat_hang_co_lo(self):
		"""Mặt hàng không quản lý lô không có gì để khai. Lấy về là bắt thủ kho
		gõ số lô cho một thứ không có lô."""
		ncc = _ncc_thu()
		kho = frappe.db.get_value("Warehouse", {"company": CONG_TY, "is_group": 0}, "name")
		item_lo = _tao_item("_Test API Co Lo 1", co_lo=1)
		item_khong_lo = _tao_item("_Test API Khong Lo 1", co_lo=0)
		pr = frappe.get_doc(
			{
				"doctype": "Purchase Receipt",
				"company": CONG_TY,
				"supplier": ncc,
				"items": [
					{"item_code": item_lo, "qty": 5, "warehouse": kho, "rate": 1000},
					{"item_code": item_khong_lo, "qty": 5, "warehouse": kho, "rate": 1000},
				],
			}
		).insert(ignore_permissions=True)

		dong = lay_dong_tu_phieu_nhap(pr.name)

		vat_tu_ve = {d["vat_tu"] for d in dong}
		self.assertEqual(len(dong), 1)
		self.assertIn(item_lo, vat_tu_ve)
		self.assertNotIn(item_khong_lo, vat_tu_ve)

	def test_lay_dong_bo_qua_dong_da_co_batch_no(self):
		"""Chạy lại nút 'Lấy dòng' sau khi đã nhập lô một phần không được nhân
		đôi công việc đã làm."""
		ncc = _ncc_thu()
		kho = frappe.db.get_value("Warehouse", {"company": CONG_TY, "is_group": 0}, "name")
		item = _tao_item("_Test API Da Co Batch", co_lo=1)
		pr = frappe.get_doc(
			{
				"doctype": "Purchase Receipt",
				"company": CONG_TY,
				"supplier": ncc,
				"items": [
					{"item_code": item, "qty": 5, "warehouse": kho, "rate": 1000},
					{"item_code": item, "qty": 3, "warehouse": kho, "rate": 1000},
				],
			}
		).insert(ignore_permissions=True)
		# Dòng đầu ĐÃ khai lô — mô phỏng bằng cách ghi thẳng xuống CSDL, đúng
		# đường `BatchEntry.on_submit` dùng thật (`frappe.db.set_value`).
		frappe.db.set_value(
			"Purchase Receipt Item", pr.items[0].name, "batch_no", "PRE-EXISTING-LOT"
		)

		dong = lay_dong_tu_phieu_nhap(pr.name)

		dong_ve = {d["dong_phieu_nhap"] for d in dong}
		self.assertEqual(len(dong), 1)
		self.assertNotIn(pr.items[0].name, dong_ve)
		self.assertIn(pr.items[1].name, dong_ve)

	def test_lay_dong_dien_san_o_goi_y(self):
		"""`o_goi_y`/`ly_do_goi_y` phải điền SẴN từ `goi_y_o` — màn hình không tự
		tính gì thêm."""
		ncc = _ncc_thu()
		kho = frappe.db.get_value("Warehouse", {"company": CONG_TY, "is_group": 0}, "name")
		item = _tao_item("_Test API O Goi Y", co_lo=1)
		o = _o_vt("5D01010101", kho)
		_gan_vt(item, "5D010101", kho)

		pr = frappe.get_doc(
			{
				"doctype": "Purchase Receipt",
				"company": CONG_TY,
				"supplier": ncc,
				"items": [{"item_code": item, "qty": 5, "warehouse": kho, "rate": 1000}],
			}
		).insert(ignore_permissions=True)

		dong = lay_dong_tu_phieu_nhap(pr.name)

		self.assertEqual(len(dong), 1)
		self.assertEqual(dong[0]["o_goi_y"], o)
		self.assertIn("trống", dong[0]["ly_do_goi_y"])

	def test_lay_dong_khong_no_khi_mot_mat_hang_hong_du_lieu_gan(self):
		"""Ruling N của khối B, áp lại ở đây: lỗi của MỘT mặt hàng không được làm
		sập danh sách của CẢ phiếu."""
		ncc = _ncc_thu()
		kho = frappe.db.get_value("Warehouse", {"company": CONG_TY, "is_group": 0}, "name")

		item_lanh = _tao_item("_Test API Lanh", co_lo=1)
		_o_vt("5E01010101", kho)
		_gan_vt(item_lanh, "5E010101", kho)

		item_hong = _tao_item("_Test API Hong", co_lo=1)
		_o_vt("5F01010101", kho)
		_gan_vt(item_hong, "5F010101", kho)
		# Ép toạ độ cây về 0/0 trên ĐÚNG nút được gán (`5F010101`, không phải
		# ô lá) — `goi_y_o` đọc `lft`/`rgt` của nút này rồi `frappe.throw` khi
		# gặp 0/0 (bẫy đã ghi ở `goi_y.py`), mô phỏng một bản ghi gán trỏ vào
		# nút cây chưa hội tụ.
		frappe.db.set_value("Storage Location", "5F010101", {"lft": 0, "rgt": 0})

		pr = frappe.get_doc(
			{
				"doctype": "Purchase Receipt",
				"company": CONG_TY,
				"supplier": ncc,
				"items": [
					{"item_code": item_lanh, "qty": 5, "warehouse": kho, "rate": 1000},
					{"item_code": item_hong, "qty": 5, "warehouse": kho, "rate": 1000},
				],
			}
		).insert(ignore_permissions=True)

		dong = lay_dong_tu_phieu_nhap(pr.name)

		theo_vat_tu = {d["vat_tu"]: d for d in dong}
		# Cả hai dòng đều VỀ ĐỦ — không chỉ "lệnh không ném lỗi", mà mặt hàng
		# LÀNH còn phải mang đúng gợi ý của nó, không bị rỗng lây từ dòng hỏng.
		self.assertEqual(len(dong), 2)
		self.assertEqual(theo_vat_tu[item_lanh]["o_goi_y"], "5E01010101")
		self.assertIsNone(theo_vat_tu[item_hong]["o_goi_y"])
		self.assertIn(item_hong, theo_vat_tu[item_hong]["ly_do_goi_y"])

	def test_du_lieu_tem_du_11_o(self):
		ncc = _ncc_thu()
		kho = frappe.db.get_value("Warehouse", {"company": CONG_TY, "is_group": 0}, "name")
		item = _tao_item("_Test API Tem 11O", co_lo=1)
		pr = _phieu_nhap_nhap(item, kho, ncc)
		be = _phieu_nhap_lo(
			pr,
			[
				{
					"dong_phieu_nhap": pr.items[0].name,
					"vat_tu": item,
					"kho": kho,
					"so_luong": 10,
					"so_lo": "LO-API-11O",
					"hsd": "2031-01-01",
				}
			],
		)
		be.insert(ignore_permissions=True)
		be.submit()

		ket_qua = du_lieu_tem("LO-API-11O")

		self.assertEqual(len(ket_qua), 1)
		self.assertEqual(set(ket_qua[0].keys()), {f"F{i}" for i in range(1, 12)})

	def test_du_lieu_tem_F3_theo_so_dong_quy_doi_dvt(self):
		"""0 dòng quy đổi -> chỉ ĐVT. 1 dòng -> 'Cái (1/hộp)'. 2 dòng -> chỉ ĐVT.

		Nhiều hơn một quy cách thì không có quy cách nào ĐÚNG để in; in bừa một
		dòng là nói sai trên vật thể vật lý mà không ai đối chiếu lại.
		"""
		ncc = _ncc_thu()
		kho = frappe.db.get_value("Warehouse", {"company": CONG_TY, "is_group": 0}, "name")

		item_0 = _tao_item_tem("_Test API F3 Khong Quy Doi", quy_doi=[])
		item_1 = _tao_item_tem("_Test API F3 Mot Quy Doi", quy_doi=[("Box", 1)])
		item_2 = _tao_item_tem("_Test API F3 Hai Quy Doi", quy_doi=[("Box", 1), ("Pair", 2)])

		f3 = {}
		for idx, item in enumerate((item_0, item_1, item_2), start=1):
			pr = _phieu_nhap_nhap(item, kho, ncc)
			so_lo = f"LO-F3-{idx}"
			be = _phieu_nhap_lo(
				pr,
				[
					{
						"dong_phieu_nhap": pr.items[0].name,
						"vat_tu": item,
						"kho": kho,
						"so_luong": 10,
						"so_lo": so_lo,
						"hsd": "2031-01-01",
					}
				],
			)
			be.insert(ignore_permissions=True)
			be.submit()
			f3[item] = du_lieu_tem(so_lo)[0]["F3"]

		self.assertEqual(f3[item_0], "Nos")
		self.assertEqual(f3[item_1], "Nos (1/Box)")
		self.assertEqual(f3[item_2], "Nos")
		# Ba ca chỉ cho ra HAI chuỗi khác nhau — ca 0 và ca 2 TRÙNG NHAU (cùng
		# "chỉ ĐVT"). Thiếu ca 0 hoặc ca 2 thì hai ca còn lại không phân biệt
		# được nhánh "đúng 1 dòng" với nhánh "khác 1 dòng" (0 hay ≥2 dòng).
		self.assertEqual(f3[item_0], f3[item_2])
		self.assertNotEqual(f3[item_0], f3[item_1])

	def test_dat_o_in_tem_lan_dau_thi_dat_lan_sau_giu_nguyen(self):
		"""In lại lần hai phải ra ĐÚNG tờ giấy như lần đầu — lần đầu có thể đã
		dán lên hàng."""
		ncc = _ncc_thu()
		kho = frappe.db.get_value("Warehouse", {"company": CONG_TY, "is_group": 0}, "name")
		item = _tao_item("_Test API Bat Bien", co_lo=1)
		item_khac = _tao_item("_Test API Bat Bien Khac", co_lo=0)

		leaf1 = _o_vt("5G01010101", kho)
		_o_vt("5G01010102", kho)
		_gan_vt(item, "5G010101", kho)

		pr = _phieu_nhap_nhap(item, kho, ncc)
		be = _phieu_nhap_lo(
			pr,
			[
				{
					"dong_phieu_nhap": pr.items[0].name,
					"vat_tu": item,
					"kho": kho,
					"so_luong": 10,
					"so_lo": "LO-BATBIEN-1",
					"hsd": "2031-01-01",
				}
			],
		)
		be.insert(ignore_permissions=True)
		be.submit()

		lan_1 = dat_o_in_tem("LO-BATBIEN-1")
		self.assertEqual(lan_1, leaf1)
		self.assertEqual(
			frappe.db.get_value("Batch", "LO-BATBIEN-1", "custom_o_in_tem"), leaf1
		)

		# Chiếm `leaf1` bằng một mặt hàng KHÁC — nếu `dat_o_in_tem` TÍNH LẠI
		# thay vì đọc giá trị đã lưu, `goi_y_o` sẽ bỏ qua `leaf1` (không còn
		# trống, không cùng hàng) và trả `leaf2` — khác `leaf1`, lộ ngay đột
		# biến "xoá điều kiện bất biến".
		frappe.get_doc(
			{
				"doctype": "Location Balance",
				"o": leaf1,
				"kho": kho,
				"vat_tu": item_khac,
				"so_lo": "",
				"so_luong": 3,
			}
		).insert(ignore_permissions=True)

		lan_2 = dat_o_in_tem("LO-BATBIEN-1")
		self.assertEqual(lan_2, leaf1)

	def test_du_lieu_tem_khong_ghi_du_lieu(self):
		"""Xem trước không được ghi dữ liệu (yêu cầu #4 brief) — hai việc tách
		nhau. Dựng mặt hàng ĐÃ GÁN vị trí để F8 xem trước có ô để gợi ý (không
		rơi vào nhánh "VT —" — nhánh đó không thử thách được việc ghi/không
		ghi), gọi `du_lieu_tem`, rồi khẳng định `custom_o_in_tem` VẪN TRỐNG."""
		ncc = _ncc_thu()
		kho = frappe.db.get_value("Warehouse", {"company": CONG_TY, "is_group": 0}, "name")
		item = _tao_item("_Test API Khong Ghi", co_lo=1)
		_o_vt("5H01010101", kho)
		_gan_vt(item, "5H010101", kho)

		pr = _phieu_nhap_nhap(item, kho, ncc)
		be = _phieu_nhap_lo(
			pr,
			[
				{
					"dong_phieu_nhap": pr.items[0].name,
					"vat_tu": item,
					"kho": kho,
					"so_luong": 10,
					"so_lo": "LO-KHONGGHI-1",
					"hsd": "2031-01-01",
				}
			],
		)
		be.insert(ignore_permissions=True)
		be.submit()

		ket_qua = du_lieu_tem("LO-KHONGGHI-1")

		# Xem trước PHẢI thấy được gợi ý — không rơi vào "VT —" vô nghĩa, thứ
		# không thử thách gì việc ghi/không ghi.
		self.assertNotEqual(ket_qua[0]["F8"], "VT —")
		# Nhưng KHÔNG được ghi xuống CSDL — xem trước, không phải in.
		self.assertFalse(frappe.db.get_value("Batch", "LO-KHONGGHI-1", "custom_o_in_tem"))

	def test_dat_o_in_tem_tra_None_khi_mat_hang_chua_gan(self):
		"""F8 in 'VT —', KHÔNG đoán, và KHÔNG chặn in."""
		ncc = _ncc_thu()
		kho = frappe.db.get_value("Warehouse", {"company": CONG_TY, "is_group": 0}, "name")
		item = _tao_item("_Test API Chua Gan", co_lo=1)  # KHÔNG gán vị trí cố định

		pr = _phieu_nhap_nhap(item, kho, ncc)
		be = _phieu_nhap_lo(
			pr,
			[
				{
					"dong_phieu_nhap": pr.items[0].name,
					"vat_tu": item,
					"kho": kho,
					"so_luong": 10,
					"so_lo": "LO-CHUAGAN-1",
					"hsd": "2031-01-01",
				}
			],
		)
		be.insert(ignore_permissions=True)
		be.submit()

		ket_qua = dat_o_in_tem("LO-CHUAGAN-1")

		self.assertIsNone(ket_qua)
		# KHÔNG đoán: không có gì được ghi xuống CSDL từ lần gọi này.
		self.assertFalse(frappe.db.get_value("Batch", "LO-CHUAGAN-1", "custom_o_in_tem"))


class TestQuyenApiMayChu(FrappeTestCase):
	"""Đối chứng cho yêu cầu #1 (kiểm quyền ở mọi hàm whitelist) — cùng khuôn
	`test_tem.py::TestQuyenInTem`. Không nằm trong 7 bài của brief, nhưng
	"Tám điều" của điều phối nêu đích danh đây là điều bắt buộc phải đúng."""

	def tearDown(self):
		frappe.set_user("Administrator")

	def _nguoi_dung_khong_vai_tro(self):
		ten = "nhaplo-khong-quyen@mo-phong.local"
		if not frappe.db.exists("User", ten):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": ten,
					"first_name": "NhapLo",
					"send_welcome_email": 0,
					"roles": [],
				}
			).insert(ignore_permissions=True)
		return ten

	def test_khach_vang_lai_hop_le_van_bi_chan_ca_ba_ham(self):
		"""Đăng nhập hợp lệ không phải điều kiện đủ — cả ba hàm đều lộ tồn kho
		theo ô hoặc ghi dữ liệu vận hành."""
		frappe.set_user(self._nguoi_dung_khong_vai_tro())
		with self.assertRaises(frappe.PermissionError):
			lay_dong_tu_phieu_nhap("khong-quan-trong")
		with self.assertRaises(frappe.PermissionError):
			du_lieu_tem("khong-quan-trong")
		with self.assertRaises(frappe.PermissionError):
			dat_o_in_tem("khong-quan-trong")
