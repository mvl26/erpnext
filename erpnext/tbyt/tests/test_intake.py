# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Đường nộp chứng từ từ mặt hàng — bốn hàm phía server của `erpnext.tbyt.intake`.

`find_documents_by_so_hieu` truy vấn TOÀN CỤC trên `TBYT Regulatory Document`, và
`FrappeTestCase` chỉ rollback một lần ở cuối lớp, không theo từng test. Mọi khẳng
định ở đây vì vậy bám theo `name` của một bản ghi cụ thể — không bao giờ theo số
đếm hay theo sự vắng mặt của một loại.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

import erpnext
from erpnext.tbyt.doctype.tbyt_marketing_authorization.test_tbyt_marketing_authorization import (
	make_authorization,
	make_manufacturer,
)
from erpnext.tbyt.intake import (
	attach_existing_to_item,
	create_document_for_item,
	find_documents_by_so_hieu,
	get_intake_context,
)
from erpnext.tbyt.resolver import get_item_documents
from erpnext.tbyt.status import get_item_status
from erpnext.tbyt.tests.test_expiry import make_regulatory_document
from erpnext.tbyt.tests.test_item_fields import make_item, make_item_group

AUTH_DOCTYPE = "TBYT Marketing Authorization"


class TestIntake(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.tbyt.setup import setup_tbyt_masters

		setup_tbyt_masters()

	def setUp(self):
		self.suffix = frappe.generate_hash(length=6)

	# --- get_intake_context: suy chủ thể theo §5.5 đặc tả ---

	def test_context_resolves_owner_level(self):
		owner = make_manufacturer(f"_Test TBYT Hang CTXOWN-{self.suffix}")
		auth = make_authorization(so_luu_hanh=f"_TEST-SLH-CTXOWN-{self.suffix}", chu_so_huu=owner)
		item = make_item(f"_TEST-TBYT-CTXOWN-{self.suffix}", la_thiet_bi_y_te=1, so_luu_hanh=auth.name)

		ctx = get_intake_context(item.name, "thong_tin_bao_hanh")

		self.assertEqual(ctx["scope_level"], "Owner")
		self.assertEqual(ctx["scope_doctype"], "Manufacturer")
		self.assertEqual(ctx["scope_name"], owner)
		self.assertIn(owner, ctx["explain"])

	def test_context_resolves_authorization_level(self):
		auth = make_authorization(so_luu_hanh=f"_TEST-SLH-CTXAUTH-{self.suffix}")
		item = make_item(f"_TEST-TBYT-CTXAUTH-{self.suffix}", la_thiet_bi_y_te=1, so_luu_hanh=auth.name)

		ctx = get_intake_context(item.name, "hdsd_tieng_viet")

		self.assertEqual(ctx["scope_level"], "Authorization")
		self.assertEqual(ctx["scope_doctype"], AUTH_DOCTYPE)
		self.assertEqual(ctx["scope_name"], auth.name)

	def test_context_resolves_company_and_item_levels(self):
		auth = make_authorization(so_luu_hanh=f"_TEST-SLH-CTXCI-{self.suffix}")
		item = make_item(f"_TEST-TBYT-CTXCI-{self.suffix}", la_thiet_bi_y_te=1, so_luu_hanh=auth.name)

		company_ctx = get_intake_context(item.name, "cong_bo_dk_mua_ban")
		self.assertEqual(company_ctx["scope_level"], "Company")
		self.assertEqual(company_ctx["scope_doctype"], "Company")
		self.assertEqual(company_ctx["scope_name"], erpnext.get_default_company())

		item_ctx = get_intake_context(item.name, "niem_yet_gia")
		self.assertEqual(item_ctx["scope_level"], "Item")
		self.assertEqual(item_ctx["scope_doctype"], "Item")
		self.assertEqual(item_ctx["scope_name"], item.name)

	def test_context_is_none_for_batch_level(self):
		auth = make_authorization(so_luu_hanh=f"_TEST-SLH-CTXBATCH-{self.suffix}")
		item = make_item(f"_TEST-TBYT-CTXBATCH-{self.suffix}", la_thiet_bi_y_te=1, so_luu_hanh=auth.name)

		self.assertIsNone(get_intake_context(item.name, "cq_chung_nhan_chat_luong"))

	def test_context_is_none_for_non_medical_item(self):
		group = make_item_group("_Test Nhom Thuong", la_tbyt=0)
		item = make_item(f"_TEST-TBYT-CTXNONMED-{self.suffix}", item_group=group)

		self.assertIsNone(get_intake_context(item.name, "hdsd_tieng_viet"))

	# --- find_documents_by_so_hieu: chặn trùng sớm, không thay đổi mô hình ---

	def test_lookup_ignores_short_input(self):
		with patch("frappe.db.sql", side_effect=AssertionError("khong duoc cham DB")):
			result = find_documents_by_so_hieu("ab")

		self.assertEqual(result, [])

	def test_lookup_finds_active_document_by_name(self):
		auth = make_authorization(so_luu_hanh=f"_TEST-SLH-LKP-{self.suffix}")
		so_hieu = f"_TEST-SH-LKP-{self.suffix}"
		doc = make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, auth.name, so_hieu=so_hieu)

		results = find_documents_by_so_hieu(so_hieu)
		match = next((r for r in results if r["name"] == doc.name), None)

		self.assertIsNotNone(match)
		self.assertEqual(match["document_type"], "hdsd_tieng_viet")
		self.assertEqual(match["so_hieu"], so_hieu)
		self.assertEqual(match["scope_count"], 1)

	def test_lookup_skips_inactive(self):
		auth = make_authorization(so_luu_hanh=f"_TEST-SLH-LKPINACT-{self.suffix}")
		so_hieu = f"_TEST-SH-LKPINACT-{self.suffix}"
		doc = make_regulatory_document(
			"hdsd_tieng_viet", AUTH_DOCTYPE, auth.name, so_hieu=so_hieu, is_active=0
		)

		results = find_documents_by_so_hieu(so_hieu)

		self.assertFalse(any(r["name"] == doc.name for r in results))

	def test_lookup_flags_already_covers_item(self):
		auth = make_authorization(so_luu_hanh=f"_TEST-SLH-LKPCOVER-{self.suffix}")
		item = make_item(f"_TEST-TBYT-LKPCOVER-{self.suffix}", la_thiet_bi_y_te=1, so_luu_hanh=auth.name)
		so_hieu = f"_TEST-SH-LKPCOVER-{self.suffix}"
		doc = make_regulatory_document("hdsd_tieng_viet", AUTH_DOCTYPE, auth.name, so_hieu=so_hieu)

		results = find_documents_by_so_hieu(so_hieu, item_code=item.name)
		match = next(r for r in results if r["name"] == doc.name)

		self.assertEqual(match["already_covers_item"], 1)

	def test_lookup_requires_document_read_permission(self):
		"""Không `item_code` không có nghĩa là không cần quyền — endpoint vẫn công khai.

		Người dùng không giữ System Manager lẫn Item Manager (hai vai trò duy nhất
		được đọc `TBYT Regulatory Document`) phải bị chặn, kể cả khi tra cứu không
		gắn với mặt hàng nào.
		"""
		email = f"_test_intake_noperm_{self.suffix}@example.com"
		user = frappe.new_doc("User")
		user.email = email
		user.first_name = "Test Intake Noperm"
		user.send_welcome_email = 0
		user.insert(ignore_permissions=True)
		self.assertEqual(list(user.roles), [])

		frappe.set_user(email)
		try:
			with self.assertRaises(frappe.PermissionError):
				find_documents_by_so_hieu(f"_TEST-SH-NOPERM-{self.suffix}")
		finally:
			frappe.set_user("Administrator")

	def test_lookup_escapes_like_wildcards_in_so_hieu(self):
		"""Gạch dưới thật trong số hiệu không được khớp bừa như ký tự đại diện.

		Không thoát `_` thì tra "SH-X_01" sẽ khớp cả "SH-XA01" — hai số hiệu khác
		nhau trông giống là cùng một tờ, đúng lỗi mà việc tra số hiệu sinh ra để
		tránh (§4 đặc tả: chặn trùng đúng, không chặn nhầm).
		"""
		literal_underscore = f"_TEST-SH-ESC_{self.suffix}"
		decoy = f"_TEST-SH-ESCX{self.suffix}"
		auth = make_authorization(so_luu_hanh=f"_TEST-SLH-ESC-{self.suffix}")
		doc_with_underscore = make_regulatory_document(
			"hdsd_tieng_viet", AUTH_DOCTYPE, auth.name, so_hieu=literal_underscore
		)
		decoy_auth = make_authorization(so_luu_hanh=f"_TEST-SLH-ESCX-{self.suffix}")
		decoy_doc = make_regulatory_document(
			"cfs_giay_luu_hanh", AUTH_DOCTYPE, decoy_auth.name, so_hieu=decoy, khong_thoi_han=1
		)

		results = find_documents_by_so_hieu(literal_underscore)
		names = {r["name"] for r in results}

		self.assertIn(doc_with_underscore.name, names)
		self.assertNotIn(decoy_doc.name, names)

	# --- attach_existing_to_item: chỉ có nghĩa cho bốn loại đa phạm vi ---

	def test_attach_adds_scope_row(self):
		owner = make_manufacturer(f"_Test TBYT Hang ATTACH-{self.suffix}")
		auth1 = make_authorization(so_luu_hanh=f"_TEST-SLH-ATT1-{self.suffix}", chu_so_huu=owner)
		auth2 = make_authorization(so_luu_hanh=f"_TEST-SLH-ATT2-{self.suffix}", chu_so_huu=owner)
		item2 = make_item(f"_TEST-TBYT-ATT2-{self.suffix}", la_thiet_bi_y_te=1, so_luu_hanh=auth2.name)
		doc = make_regulatory_document(
			"cfs_giay_luu_hanh",
			AUTH_DOCTYPE,
			auth1.name,
			so_hieu=f"_TEST-SH-ATT-{self.suffix}",
			khong_thoi_han=1,
		)

		result = attach_existing_to_item(item2.name, doc.name)
		self.assertEqual(result["document"], doc.name)

		doc.reload()
		self.assertEqual(len(doc.pham_vi), 2)
		self.assertIn(auth2.name, {row.scope_name for row in doc.pham_vi})

		rows = {r["document_key"]: r for r in get_item_documents(item2.name)}
		self.assertEqual(rows["cfs_giay_luu_hanh"]["document"], doc.name)

	def test_attach_is_idempotent(self):
		owner = make_manufacturer(f"_Test TBYT Hang IDEMP-{self.suffix}")
		auth1 = make_authorization(so_luu_hanh=f"_TEST-SLH-IDEMP1-{self.suffix}", chu_so_huu=owner)
		auth2 = make_authorization(so_luu_hanh=f"_TEST-SLH-IDEMP2-{self.suffix}", chu_so_huu=owner)
		item2 = make_item(f"_TEST-TBYT-IDEMP2-{self.suffix}", la_thiet_bi_y_te=1, so_luu_hanh=auth2.name)
		doc = make_regulatory_document(
			"cfs_giay_luu_hanh",
			AUTH_DOCTYPE,
			auth1.name,
			so_hieu=f"_TEST-SH-IDEMP-{self.suffix}",
			khong_thoi_han=1,
		)

		attach_existing_to_item(item2.name, doc.name)
		attach_existing_to_item(item2.name, doc.name)

		doc.reload()
		self.assertEqual(len(doc.pham_vi), 2)

	def test_attach_rejects_single_scope_type(self):
		auth_a = make_authorization(so_luu_hanh=f"_TEST-SLH-SINGLE-A-{self.suffix}")
		auth_b = make_authorization(so_luu_hanh=f"_TEST-SLH-SINGLE-B-{self.suffix}")
		item_b = make_item(f"_TEST-TBYT-SINGLE-B-{self.suffix}", la_thiet_bi_y_te=1, so_luu_hanh=auth_b.name)
		doc = make_regulatory_document(
			"hdsd_tieng_viet", AUTH_DOCTYPE, auth_a.name, so_hieu=f"_TEST-SH-SINGLE-{self.suffix}"
		)

		with self.assertRaises(frappe.ValidationError) as ctx:
			attach_existing_to_item(item_b.name, doc.name)

		self.assertIn("chỉ nhận một phạm vi", str(ctx.exception))

	def test_attach_rejects_different_owner(self):
		owner_a = make_manufacturer(f"_Test TBYT Hang OWNERA-{self.suffix}")
		owner_b = make_manufacturer(f"_Test TBYT Hang OWNERB-{self.suffix}")
		auth_a = make_authorization(so_luu_hanh=f"_TEST-SLH-OWNA-{self.suffix}", chu_so_huu=owner_a)
		auth_b = make_authorization(so_luu_hanh=f"_TEST-SLH-OWNB-{self.suffix}", chu_so_huu=owner_b)
		item_b = make_item(f"_TEST-TBYT-OWNB-{self.suffix}", la_thiet_bi_y_te=1, so_luu_hanh=auth_b.name)
		doc = make_regulatory_document(
			"cfs_giay_luu_hanh",
			AUTH_DOCTYPE,
			auth_a.name,
			so_hieu=f"_TEST-SH-OWN-{self.suffix}",
			khong_thoi_han=1,
		)

		with self.assertRaises(frappe.ValidationError) as ctx:
			attach_existing_to_item(item_b.name, doc.name)

		message = str(ctx.exception)
		self.assertIn(owner_a, message)
		self.assertIn(owner_b, message)

	def test_attach_rejects_when_scope_already_taken(self):
		owner = make_manufacturer(f"_Test TBYT Hang TAKEN-{self.suffix}")
		auth_x = make_authorization(so_luu_hanh=f"_TEST-SLH-TAKENX-{self.suffix}", chu_so_huu=owner)
		auth_y = make_authorization(so_luu_hanh=f"_TEST-SLH-TAKENY-{self.suffix}", chu_so_huu=owner)
		item_x = make_item(f"_TEST-TBYT-TAKENX-{self.suffix}", la_thiet_bi_y_te=1, so_luu_hanh=auth_x.name)

		doc1 = make_regulatory_document(
			"cfs_giay_luu_hanh",
			AUTH_DOCTYPE,
			auth_x.name,
			so_hieu=f"_TEST-SH-TAKEN1-{self.suffix}",
			khong_thoi_han=1,
		)
		doc2 = make_regulatory_document(
			"cfs_giay_luu_hanh",
			AUTH_DOCTYPE,
			auth_y.name,
			so_hieu=f"_TEST-SH-TAKEN2-{self.suffix}",
			khong_thoi_han=1,
		)

		with self.assertRaises(frappe.ValidationError) as ctx:
			attach_existing_to_item(item_x.name, doc2.name)

		self.assertIn(doc1.name, str(ctx.exception))

	# --- create_document_for_item: tạo và lưu ngay, kèm trạng thái mới ---

	def test_create_saves_immediately(self):
		auth = make_authorization(so_luu_hanh=f"_TEST-SLH-CREATE-{self.suffix}")
		item = make_item(f"_TEST-TBYT-CREATE-{self.suffix}", la_thiet_bi_y_te=1, so_luu_hanh=auth.name)

		result = create_document_for_item(
			item.name,
			"hdsd_tieng_viet",
			so_hieu=f"_TEST-SH-CREATE-{self.suffix}",
			ngay_cap="2026-01-01",
			khong_thoi_han="1",
			ngay_het_han=None,
			file_url="/private/files/_test_tbyt.pdf",
		)

		doc = frappe.get_doc("TBYT Regulatory Document", result["document"])
		self.assertEqual(doc.document_type, "hdsd_tieng_viet")
		self.assertEqual(len(doc.pham_vi), 1)
		self.assertEqual(doc.pham_vi[0].scope_name, auth.name)

	def test_create_returns_new_item_status(self):
		auth = make_authorization(so_luu_hanh=f"_TEST-SLH-CREATESTAT-{self.suffix}")
		item = make_item(f"_TEST-TBYT-CREATESTAT-{self.suffix}", la_thiet_bi_y_te=1, so_luu_hanh=auth.name)

		result = create_document_for_item(
			item.name,
			"niem_yet_gia",
			so_hieu=f"_TEST-SH-CREATESTAT-{self.suffix}",
			ngay_cap="2026-01-01",
			khong_thoi_han=1,
			ngay_het_han=None,
			file_url="/private/files/_test_tbyt.pdf",
		)

		self.assertEqual(result["tinh_trang_ho_so"], get_item_status(item.name))

	def test_create_inherits_to_sibling_item(self):
		"""Ca quan trọng nhất: tiện lợi mới không đánh đổi bằng tính thừa hưởng."""
		owner = make_manufacturer(f"_Test TBYT Hang INHERIT-{self.suffix}")
		auth_a = make_authorization(so_luu_hanh=f"_TEST-SLH-INHA-{self.suffix}", chu_so_huu=owner)
		auth_b = make_authorization(so_luu_hanh=f"_TEST-SLH-INHB-{self.suffix}", chu_so_huu=owner)
		item_a = make_item(f"_TEST-TBYT-INHA-{self.suffix}", la_thiet_bi_y_te=1, so_luu_hanh=auth_a.name)
		item_b = make_item(f"_TEST-TBYT-INHB-{self.suffix}", la_thiet_bi_y_te=1, so_luu_hanh=auth_b.name)

		result = create_document_for_item(
			item_a.name,
			"thong_tin_bao_hanh",
			so_hieu=f"_TEST-SH-INH-{self.suffix}",
			ngay_cap="2026-01-01",
			khong_thoi_han=1,
			ngay_het_han=None,
			file_url="/private/files/_test_tbyt.pdf",
		)

		rows = {r["document_key"]: r for r in get_item_documents(item_b.name)}
		self.assertEqual(rows["thong_tin_bao_hanh"]["document"], result["document"])
