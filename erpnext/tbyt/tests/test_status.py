# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Trạng thái hồ sơ của Item — sáu giá trị, xếp từ nặng tới nhẹ.

Nhãn cuối cố ý là "Đủ hồ sơ mặt hàng" chứ KHÔNG phải "Đủ": chứng từ cấp lô
(CQ, CO — đều là BB ở cả bốn phân loại) không tính ở cấp Item, nên nói "Đủ" là
nói dối. Trạng thái cấp lô xem ở Batch và trong báo cáo.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

import erpnext
from erpnext.tbyt import constants
from erpnext.tbyt.doctype.tbyt_marketing_authorization.test_tbyt_marketing_authorization import (
	make_authorization,
)
from erpnext.tbyt.status import get_item_dashboard, get_item_status, update_item_status
from erpnext.tbyt.tests.test_expiry import make_regulatory_document
from erpnext.tbyt.tests.test_item_fields import make_item, make_item_group

AUTH_DOCTYPE = "TBYT Marketing Authorization"


def upload_everything_required(item, auth):
	"""Tải lên mọi chứng từ bắt buộc còn thiếu — dùng để đẩy Item tới trạng thái Đủ.

	Ở cấp module để `test_refresh.py` tái dùng thay vì chép lại lần hai.
	"""
	from erpnext.tbyt.resolver import get_item_documents

	for row in get_item_documents(item.name):
		if not row["is_required"] or row["document"]:
			continue
		scope_map = {
			constants.SCOPE_COMPANY: ("Company", erpnext.get_default_company()),
			constants.SCOPE_OWNER: ("Manufacturer", auth.chu_so_huu),
			constants.SCOPE_AUTHORIZATION: (AUTH_DOCTYPE, auth.name),
			constants.SCOPE_ITEM: ("Item", item.name),
		}
		scope_doctype, scope_name = scope_map[row["scope_level"]]
		make_regulatory_document(row["document_key"], scope_doctype, scope_name)


class TestItemStatus(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.tbyt.setup import setup_tbyt_masters

		setup_tbyt_masters()

	def setUp(self):
		self.suffix = frappe.generate_hash(length=6)

	def _make(self, device_class="A", **auth_kwargs):
		auth = make_authorization(
			so_luu_hanh=f"_TEST-SLH-ST-{self.suffix}", phan_loai=device_class, **auth_kwargs
		)
		item = make_item(f"_TEST-TBYT-ST-{self.suffix}", la_thiet_bi_y_te=1, so_luu_hanh=auth.name)
		return item, auth

	def _upload_everything_required(self, item, auth):
		upload_everything_required(item, auth)

	def test_non_medical_item_has_no_status(self):
		group = make_item_group("_Test Nhom Thuong", la_tbyt=0)
		item = make_item(f"_TEST-TBYT-ST-NONMED-{self.suffix}", item_group=group)
		self.assertIsNone(get_item_status(item.name))

	def test_pending_authorization_outranks_missing_documents(self):
		item, _ = self._make()
		frappe.db.set_value(AUTH_DOCTYPE, item.so_luu_hanh, "trang_thai", constants.AUTH_STATUS_PENDING)
		self.assertEqual(get_item_status(item.name), constants.ITEM_STATUS_AUTH_PENDING)

	def test_lapsed_authorization_outranks_everything(self):
		"""Số lưu hành hết hiệu lực là sự kiện tuân thủ nặng nhất — phải hiện lên trước."""
		item, auth = self._make()
		self._upload_everything_required(item, auth)
		frappe.db.set_value(AUTH_DOCTYPE, auth.name, "trang_thai", constants.AUTH_STATUS_REVOKED)
		self.assertEqual(get_item_status(item.name), constants.ITEM_STATUS_AUTH_INVALID)

	def test_missing_required_document_is_reported(self):
		item, _ = self._make()
		self.assertEqual(get_item_status(item.name), constants.ITEM_STATUS_MISSING)

	def test_expired_document_outranks_missing(self):
		item, auth = self._make()
		make_regulatory_document(
			"hdsd_tieng_viet",
			AUTH_DOCTYPE,
			auth.name,
			khong_thoi_han=0,
			ngay_het_han=add_days(today(), -1),
		)
		self.assertEqual(get_item_status(item.name), constants.ITEM_STATUS_EXPIRED)

	def test_complete_dossier_reports_item_level_completeness(self):
		item, auth = self._make()
		self._upload_everything_required(item, auth)
		self.assertEqual(get_item_status(item.name), constants.ITEM_STATUS_OK)

	def test_a_dangling_authorization_link_never_reads_as_complete(self):
		"""Xoá số lưu hành mà Item còn trỏ tới — tuyệt đối không được xanh.

		Dọn dữ liệu bằng `ignore_links`, script dọn dẹp hay Transaction Deletion
		Record đều tạo ra được cảnh này. `frappe.db.get_value` trả None, và None
		không khớp nhánh thu hồi/hết hiệu lực lẫn nhánh đang đăng ký — không chặn
		lại thì mặt hàng trôi thẳng xuống "Đủ hồ sơ mặt hàng" đúng lúc cơ sở pháp
		lý của nó đã bốc hơi.
		"""
		item, auth = self._make()
		self._upload_everything_required(item, auth)
		self.assertEqual(get_item_status(item.name), constants.ITEM_STATUS_OK)

		frappe.delete_doc(AUTH_DOCTYPE, auth.name, force=1, ignore_permissions=True)
		self.assertFalse(frappe.db.exists(AUTH_DOCTYPE, auth.name))
		self.assertEqual(get_item_status(item.name), constants.ITEM_STATUS_AUTH_INVALID)

	def test_an_empty_resolution_reads_as_broken_not_complete(self):
		"""Không phân giải ra dòng nào thì không có gì để đối chiếu — cấm kết luận "đủ"."""
		from erpnext.tbyt.resolver import get_item_documents

		item, auth = self._make()
		# Số lưu hành mất phân loại thì resolver không tra được ma trận và trả rỗng —
		# cùng hình dạng dữ liệu với ca danh mục 23 loại chứng từ vắng mặt.
		frappe.db.set_value(AUTH_DOCTYPE, auth.name, "phan_loai", None)
		self.assertEqual(get_item_documents(item.name), [])
		self.assertEqual(get_item_status(item.name), constants.ITEM_STATUS_AUTH_INVALID)

	def test_expiring_document_is_reported_once_nothing_is_missing(self):
		item, auth = self._make()
		self._upload_everything_required(item, auth)
		doc_name = frappe.db.get_value(
			"TBYT Regulatory Document", {"document_type": "hdsd_tieng_viet"}, "name"
		)
		doc = frappe.get_doc("TBYT Regulatory Document", doc_name)
		doc.khong_thoi_han = 0
		doc.ngay_het_han = add_days(today(), constants.EXPIRY_WARNING_DAYS - 5)
		doc.save(ignore_permissions=True)
		self.assertEqual(get_item_status(item.name), constants.ITEM_STATUS_EXPIRING)

	def test_update_item_status_persists_without_bumping_modified(self):
		item, _ = self._make()
		before = frappe.db.get_value("Item", item.name, "modified")
		update_item_status(item.name)
		after = frappe.db.get_value("Item", item.name, "modified")
		self.assertEqual(
			frappe.db.get_value("Item", item.name, "tinh_trang_ho_so"),
			constants.ITEM_STATUS_MISSING,
		)
		self.assertEqual(before, after)

	def test_can_intake_flags_a_missing_required_row(self):
		"""BB thiếu là dòng có nút Nộp giấy — `hdsd_tieng_viet` là BB ở mọi phân loại."""
		item, _ = self._make()
		rows = {r["document_key"]: r for r in get_item_dashboard(item.name)["rows"]}
		self.assertTrue(rows["hdsd_tieng_viet"]["can_intake"])

	def test_can_intake_is_true_for_a_nice_to_have_row_when_absent(self):
		"""Người dùng đã đổi quyết định: NC giờ cũng nộp trực tiếp được, không chỉ BB/BB*.

		`hop_chuan_hop_quy` là NC ở phân loại A. Trước đây NC không có nút Nộp giấy;
		giờ mọi dòng chưa có chứng từ đều có, kể cả NC.
		"""
		item, auth = self._make(device_class="A")
		rows = {r["document_key"]: r for r in get_item_dashboard(item.name)["rows"]}
		self.assertTrue(rows["hop_chuan_hop_quy"]["can_intake"])

		make_regulatory_document("hop_chuan_hop_quy", AUTH_DOCTYPE, auth.name)
		rows = {r["document_key"]: r for r in get_item_dashboard(item.name)["rows"]}
		self.assertFalse(rows["hop_chuan_hop_quy"]["can_intake"])

	def test_can_intake_is_true_for_a_th_row_when_absent(self):
		"""TH cũng nộp trực tiếp được — đây chính là lý do nó phải được hiện ra.

		Trước đây resolver bỏ hẳn dòng TH chưa có giấy nên không có gì để bấm. Giờ
		dòng vẫn hiện và `can_intake` là True cho tới khi có giấy — `ke_khai_gia`
		là TH ở mọi phân loại, phạm vi Item nên nộp thẳng không cần đụng tới Số lưu hành.
		"""
		item, _ = self._make(device_class="B")
		rows = {r["document_key"]: r for r in get_item_dashboard(item.name)["rows"]}
		self.assertTrue(rows["ke_khai_gia"]["is_supplementary"])
		self.assertTrue(rows["ke_khai_gia"]["can_intake"])

		make_regulatory_document("ke_khai_gia", "Item", item.name)
		rows = {r["document_key"]: r for r in get_item_dashboard(item.name)["rows"]}
		self.assertFalse(rows["ke_khai_gia"]["can_intake"])

	def test_can_intake_is_false_once_the_document_exists(self):
		item, auth = self._make()
		self._upload_everything_required(item, auth)
		rows = {r["document_key"]: r for r in get_item_dashboard(item.name)["rows"]}
		self.assertFalse(rows["hdsd_tieng_viet"]["can_intake"])

	def test_dashboard_missing_count_excludes_nc_and_th_rows(self):
		"""`missing` chỉ đếm BB/BB* đang bị đòi — không cộng dồn dòng NC hay TH nào.

		Từ khi resolver luôn trả cả dòng TH chưa có giấy, phải canh rằng con số này
		không âm thầm phình lên vì những dòng không phải nghĩa vụ.
		"""
		item, _ = self._make(device_class="B")
		data = get_item_dashboard(item.name)
		rows = data["rows"]
		optional_missing = [r for r in rows if not r["is_required"] and not r["document"]]
		self.assertTrue(optional_missing, "Ca kiem tra vo nghia neu khong co dong tuy chon nao thieu")
		required_missing = sum(1 for r in rows if r["is_required"] and not r["document"])
		self.assertEqual(data["missing"], required_missing)

	def test_complete_dossier_ignores_missing_nc_and_th(self):
		"""Đủ hết BB/BB* thỏa điều kiện là ĐỦ — dù NC và TH còn chưa có giấy nào.

		Từ khi resolver luôn trả cả dòng TH chưa có giấy (trước đây bị bỏ hẳn), phải
		canh rằng trạng thái Item không âm thầm rớt xuống MISSING vì những dòng đó.
		"""
		from erpnext.tbyt.resolver import get_item_documents

		item, auth = self._make(device_class="B")
		self._upload_everything_required(item, auth)
		rows = get_item_documents(item.name)
		optional_missing = [r for r in rows if not r["is_required"] and not r["document"]]
		self.assertTrue(optional_missing, "Ca kiem tra vo nghia neu khong con dong tuy chon nao thieu")
		self.assertEqual(get_item_status(item.name), constants.ITEM_STATUS_OK)

	def test_saving_a_medical_item_warns_but_does_not_block(self):
		"""Cảnh báo, không chặn — chứng từ về dần theo tiến độ nhà cung cấp gửi."""
		item, _ = self._make()
		item.item_name = "Doi ten de luu lai"
		item.save(ignore_permissions=True)
		messages = frappe.get_message_log()
		self.assertTrue(
			any("chứng từ" in str(m).lower() for m in messages),
			"Phải có cảnh báo thiếu chứng từ trong message log",
		)
