# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Chặn Submit Sales Order lệch giá ở chế độ "Chặn" (spec mục 6.1.5, quyết định C3; bước 1.5)."""

import json

import frappe

from erpnext.controllers.accounts_controller import update_child_qty_rate
from erpnext.selling.kiem_gia.cau_hinh import CHAN, CHI_GHI_NHAN
from erpnext.selling.kiem_gia.kiem_chung_tu import duyet_gia_lech
from erpnext.selling.tests.test_kiem_gia_chung_tu import KiemChungTuCase

VAI_TRO_DUYET = "_KG Duyệt giá"
VAI_TRO_SUA = "_KG Giám đốc"


class TestDuyetGiaLech(KiemChungTuCase):
	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.set_user, "Administrator")
		for role in (VAI_TRO_DUYET, VAI_TRO_SUA):
			if not frappe.db.exists("Role", role):
				frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
					ignore_permissions=True
				)
		frappe.db.set_single_value(
			"Selling Settings",
			{
				"che_do_kiem_gia": CHAN,
				"vai_tro_duyet_gia_lech": VAI_TRO_DUYET,
				"vai_tro_sua_ty_le_lai": VAI_TRO_SUA,
			},
		)
		frappe.clear_document_cache("Selling Settings", "Selling Settings")
		self.nhan_vien = self.user("nv", ["Sales User"])
		self.nguoi_duyet = self.user("duyet", ["Sales User", VAI_TRO_DUYET])

	def user(self, label, roles):
		return (
			frappe.get_doc(
				{
					"doctype": "User",
					"email": f"_kg_{label}_{self.sfx}@example.com",
					"first_name": f"KG {label}",
					"send_welcome_email": 0,
					"roles": [{"role": r} for r in roles],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def so_lech(self, ly_do=None):
		so = self.so([self.row(self.item(100000), 101000), self.row(self.item(100000), 99000)])
		if ly_do:
			so.ly_do_lech_gia = ly_do
			so.save(ignore_permissions=True)
		return so

	def submit_as(self, user, so):
		frappe.set_user(user)
		try:
			so.reload()
			so.submit()
		finally:
			frappe.set_user("Administrator")

	def test_a_mismatch_needs_a_reason(self):
		so = self.so_lech()

		with self.assertRaisesRegex(frappe.ValidationError, "Lý do lệch giá"):
			self.submit_as(self.nhan_vien, so)

	def test_a_mismatch_with_a_reason_still_needs_an_approver(self):
		so = self.so_lech("Giá theo hợp đồng khung")

		with self.assertRaisesRegex(frappe.ValidationError, "chưa được duyệt"):
			self.submit_as(self.nhan_vien, so)

	def test_approved_order_can_be_submitted_by_its_maker(self):
		so = self.so_lech("Giá theo hợp đồng khung")
		frappe.set_user(self.nguoi_duyet)
		duyet_gia_lech(so.name)

		self.submit_as(self.nhan_vien, so)

		so.reload()
		self.assertEqual(so.docstatus, 1)
		self.assertEqual(so.nguoi_duyet_gia, self.nguoi_duyet)
		self.assertTrue(so.thoi_diem_duyet_gia)

	def test_changing_a_mismatched_row_after_approval_needs_a_new_approval(self):
		so = self.so_lech("Giá theo hợp đồng khung")
		frappe.set_user(self.nguoi_duyet)
		duyet_gia_lech(so.name)
		frappe.set_user("Administrator")
		so.reload()
		so.items[1].rate = 95000
		so.save(ignore_permissions=True)

		self.assertFalse(so.nguoi_duyet_gia)
		with self.assertRaisesRegex(frappe.ValidationError, "chưa được duyệt"):
			self.submit_as(self.nhan_vien, so)

	def test_changing_a_matching_row_keeps_the_approval(self):
		so = self.so_lech("Giá theo hợp đồng khung")
		frappe.set_user(self.nguoi_duyet)
		duyet_gia_lech(so.name)
		frappe.set_user("Administrator")
		so.reload()
		so.items[0].qty = 2
		so.save(ignore_permissions=True)

		self.assertEqual(so.nguoi_duyet_gia, self.nguoi_duyet)

	def test_the_approver_may_submit_directly(self):
		so = self.so_lech("Khách mua số lượng lớn")

		self.submit_as(self.nguoi_duyet, so)

		self.assertEqual(frappe.db.get_value("Sales Order", so.name, "nguoi_duyet_gia"), self.nguoi_duyet)

	def test_the_margin_owner_may_approve_too(self):
		giam_doc = self.user("gd", ["Sales User", VAI_TRO_SUA])
		so = self.so_lech("Khách mua số lượng lớn")

		self.submit_as(giam_doc, so)

		self.assertEqual(frappe.db.get_value("Sales Order", so.name, "docstatus"), 1)

	def test_staff_cannot_approve(self):
		so = self.so_lech("Giá theo hợp đồng khung")
		frappe.set_user(self.nhan_vien)

		self.assertRaises(frappe.PermissionError, duyet_gia_lech, so.name)

	def test_approval_needs_a_saved_reason(self):
		so = self.so_lech()
		frappe.set_user(self.nguoi_duyet)

		self.assertRaisesRegex(frappe.ValidationError, "Lý do lệch giá", duyet_gia_lech, so.name)

	def test_unknown_buying_price_counts_as_a_mismatch(self):
		so = self.so([self.row(self.item(None), 5000)])

		with self.assertRaisesRegex(frappe.ValidationError, "Lý do lệch giá"):
			self.submit_as(self.nhan_vien, so)

	def test_matching_order_submits_without_approval(self):
		so = self.so([self.row(self.item(100000), 101000)])

		self.submit_as(self.nhan_vien, so)

		self.assertFalse(frappe.db.get_value("Sales Order", so.name, "nguoi_duyet_gia"))

	def test_record_only_mode_does_not_block(self):
		frappe.db.set_single_value("Selling Settings", "che_do_kiem_gia", CHI_GHI_NHAN)
		frappe.clear_document_cache("Selling Settings", "Selling Settings")
		so = self.so_lech()

		self.submit_as(self.nhan_vien, so)

		self.assertEqual(frappe.db.get_value("Sales Order", so.name, "docstatus"), 1)

	def test_update_items_after_submit_is_checked_too(self):
		so = self.so([self.row(self.item(100000), 101000)])
		self.submit_as(self.nhan_vien, so)
		d = so.items[0]
		trans_items = json.dumps(
			[{"docname": d.name, "item_code": d.item_code, "qty": d.qty, "rate": 90000, "uom": d.uom}]
		)

		frappe.set_user(self.nhan_vien)
		with self.assertRaisesRegex(frappe.ValidationError, "Lý do lệch giá"):
			update_child_qty_rate("Sales Order", trans_items, so.name)
