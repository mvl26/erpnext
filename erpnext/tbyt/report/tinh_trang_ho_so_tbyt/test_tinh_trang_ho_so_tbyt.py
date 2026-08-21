# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Báo cáo tổng hợp — cơ chế kiểm soát chính vì hệ thống không chặn nghiệp vụ.

Cột "Hồ sơ cấp lô" tồn tại để bù cho việc trạng thái Item cố ý bỏ qua CQ và CO:
nếu không có cột này thì hai chứng từ BB ở cả bốn phân loại sẽ không ai theo dõi.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.tbyt import constants
from erpnext.tbyt.doctype.tbyt_marketing_authorization.test_tbyt_marketing_authorization import (
	make_authorization,
)
from erpnext.tbyt.report.tinh_trang_ho_so_tbyt.tinh_trang_ho_so_tbyt import execute
from erpnext.tbyt.tests.test_expiry import make_regulatory_document
from erpnext.tbyt.tests.test_item_fields import make_item
from erpnext.tbyt.tests.test_status import upload_everything_required

AUTH_DOCTYPE = "TBYT Marketing Authorization"


def _make_batch(item_code, batch_id):
	doc = frappe.new_doc("Batch")
	doc.item = item_code
	doc.batch_id = batch_id
	doc.insert(ignore_permissions=True)
	return doc


class TestTinhTrangHoSoTBYT(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.tbyt.setup import setup_tbyt_masters

		setup_tbyt_masters()

	def setUp(self):
		self.suffix = frappe.generate_hash(length=6)
		self.auth = make_authorization(so_luu_hanh=f"_TEST-SLH-RPT-{self.suffix}", phan_loai="B")
		self.item = make_item(f"_TEST-TBYT-RPT-{self.suffix}", la_thiet_bi_y_te=1, so_luu_hanh=self.auth.name)

	def _row(self, rows):
		return next((r for r in rows if r["item_code"] == self.item.name), None)

	def test_report_lists_medical_items(self):
		_columns, rows = execute({})
		self.assertIsNotNone(self._row(rows))

	def test_report_counts_missing_required_documents(self):
		_columns, rows = execute({})
		row = self._row(rows)
		self.assertGreater(row["bb_thieu"], 0)

	def test_report_counts_drop_as_documents_arrive(self):
		_columns, before_rows = execute({})
		before = self._row(before_rows)["bb_thieu"]
		make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, self.auth.name)
		_columns, after_rows = execute({})
		self.assertEqual(self._row(after_rows)["bb_thieu"], before - 1)

	def test_report_reports_batch_level_coverage_separately(self):
		"""CQ và CO là BB ở cả bốn phân loại nhưng không tính vào trạng thái Item."""
		_columns, rows = execute({})
		row = self._row(rows)
		self.assertIn("ho_so_lo", row)
		self.assertEqual(row["ho_so_lo"], "Chưa có lô")

	def test_report_counts_batch_coverage_when_batches_exist(self):
		"""Site gần như không có Batch nào — phải tự dựng để chạm nhánh đếm thật.

		Một lô đủ cả CQ lẫn CO, một lô thiếu CO: kỳ vọng "1/2 lô", không phải
		nhánh rỗng "Chưa có lô".
		"""
		frappe.db.set_value("Item", self.item.name, "has_batch_no", 1)
		batch_ok = _make_batch(self.item.name, f"_TEST-LO-OK-{self.suffix}")
		batch_thieu = _make_batch(self.item.name, f"_TEST-LO-THIEU-{self.suffix}")
		make_regulatory_document("cq_chung_nhan_chat_luong", "Batch", batch_ok.name)
		make_regulatory_document("co_chung_nhan_xuat_xu", "Batch", batch_ok.name)
		make_regulatory_document("cq_chung_nhan_chat_luong", "Batch", batch_thieu.name)

		_columns, rows = execute({})
		row = self._row(rows)
		self.assertEqual(row["ho_so_lo"], "1/2 lô")

	def test_filter_only_incomplete_hides_complete_items(self):
		_columns, rows = execute({"chi_hien_thieu": 1})
		self.assertTrue(all(r["tinh_trang_ho_so"] != constants.ITEM_STATUS_OK for r in rows))

	def test_incomplete_batch_paperwork_survives_the_default_filter(self):
		"""Đủ hồ sơ mặt hàng nhưng lô thiếu CQ/CO thì vẫn phải hiện.

		Trạng thái của Item cố ý bỏ qua chứng từ cấp lô, nên nếu bộ lọc "chỉ hiện
		hồ sơ chưa đủ" chỉ nhìn trạng thái đó thì nó sẽ giấu đúng khoảng trống mà
		cột Hồ sơ cấp lô sinh ra để phơi bày — và bộ lọc này bật sẵn.
		"""
		upload_everything_required(self.item, self.auth)
		frappe.db.set_value("Item", self.item.name, "has_batch_no", 1)
		frappe.get_doc(
			{
				"doctype": "Batch",
				"item": self.item.name,
				"batch_id": f"_TEST-LO-GAP-{self.suffix}",
			}
		).insert(ignore_permissions=True)

		_columns, rows = execute({"chi_hien_thieu": 1})
		row = self._row(rows)
		self.assertIsNotNone(row, "Mặt hàng có lô thiếu CQ/CO bị bộ lọc mặc định giấu mất")
		self.assertEqual(row["ho_so_lo"], "0/1 lô")

	def test_filter_by_device_class(self):
		_columns, rows = execute({"phan_loai": "B"})
		self.assertTrue(all(r["phan_loai_tbyt"] == "B" for r in rows))
		self.assertIsNotNone(self._row(rows))

	def test_filter_by_device_class_uses_live_authorization_value_not_stale_fetch(self):
		"""`phan_loai_tbyt` là fetch_from, chỉ đồng bộ khi Item được lưu lại.

		Đổi phân loại thẳng dưới DB (bỏ qua việc lưu Item) để mô phỏng bản sao bị
		cũ, rồi kỳ vọng bộ lọc vẫn tìm thấy mặt hàng theo phân loại MỚI vì báo
		cáo phải đọc `phan_loai` sống từ số lưu hành, không tin bản fetch cũ.
		"""
		frappe.db.set_value(AUTH_DOCTYPE, self.auth.name, "phan_loai", "C")
		self.assertEqual(frappe.db.get_value("Item", self.item.name, "phan_loai_tbyt"), "B")

		_columns, rows = execute({"phan_loai": "C"})
		row = self._row(rows)
		self.assertIsNotNone(row, "Đổi phân loại trên số lưu hành phải phản ánh ngay trong bộ lọc")
		self.assertEqual(row["phan_loai_tbyt"], "C")

	def test_columns_expose_the_expiry_horizon(self):
		columns, _rows = execute({})
		fieldnames = {c["fieldname"] for c in columns}
		self.assertIn("ngay_het_han_gan_nhat", fieldnames)
		self.assertIn("chung_tu_het_han", fieldnames)
