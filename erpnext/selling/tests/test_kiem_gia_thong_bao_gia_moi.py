# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Thông báo giá mới khi Miyano xác nhận Sales Order (BA12 R06, D10, D12; nghiệm thu A06)."""

import frappe

from erpnext.selling.kiem_gia.thong_bao_gia_moi import lay_thong_bao_gia_moi
from erpnext.selling.tests.test_kiem_gia_chung_tu import KiemChungTuCase

EMAIL = "nguoidatdon.kg@example.com"


class TestThongBaoGiaMoi(KiemChungTuCase):
	def so_gia_moi(self, **fields):
		item = self.item(123457)
		self.gia_ban(item, 120000)
		so = self.so([self.row(item, 124692)], **fields)
		d = so.items[0]
		d.so_van_ban_gia, d.nguoi_dai_dien_kh, d.ngay_chap_thuan_gia = "VB-07/2026", "Ông A", self.d
		so.save()
		return so

	def test_a06_confirming_the_order_emails_the_new_prices(self):
		so = self.so_gia_moi(contact_email=EMAIL)
		so.submit()
		comm_name = frappe.db.get_value("Sales Order", so.name, "thong_bao_gia_moi")
		comm = frappe.get_doc("Communication", comm_name)

		self.assertEqual((comm.reference_doctype, comm.reference_name), ("Sales Order", so.name))
		self.assertIn(EMAIL, comm.recipients)
		self.assertIn("Thông báo giá mới", comm.subject)
		for text in ("VB-07/2026", "120.000", "124.692", so.items[0].item_code):
			self.assertIn(text, comm.content.replace(",", "."))

	def test_portal_gets_the_same_content(self):
		so = self.so_gia_moi(contact_email=EMAIL)
		so.submit()
		kq = lay_thong_bao_gia_moi(so.name)

		self.assertEqual(len(kq["dong"]), 1)
		self.assertEqual(
			{k: kq["dong"][0][k] for k in ("gia_cu", "gia_moi", "so_van_ban")},
			{"gia_cu": 120000, "gia_moi": 124692, "so_van_ban": "VB-07/2026"},
		)

	def test_portal_sees_nothing_before_confirmation(self):
		self.assertEqual(lay_thong_bao_gia_moi(self.so_gia_moi().name)["dong"], [])

	def test_no_new_price_no_email(self):
		item = self.item(123457)
		so = self.so([self.row(item, 124692)], contact_email=EMAIL)
		so.submit()
		self.assertFalse(frappe.db.get_value("Sales Order", so.name, "thong_bao_gia_moi"))

	def test_without_an_orderer_email_it_warns_and_still_confirms(self):
		so = self.so_gia_moi()
		frappe.clear_messages()
		so.submit()

		self.assertEqual(so.docstatus, 1)
		self.assertFalse(frappe.db.get_value("Sales Order", so.name, "thong_bao_gia_moi"))
		self.assertIn("không có email người đặt đơn", self.canh_bao())

	def test_portal_order_falls_back_to_the_portal_user(self):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": f"_kg_cong_{self.sfx}@example.com",
				"first_name": "Cổng",
				"user_type": "Website User",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
		so = self.so_gia_moi()
		frappe.db.set_value("Sales Order", so.name, "owner", user.name)
		so.reload()
		so.submit()
		comm = frappe.db.get_value("Sales Order", so.name, "thong_bao_gia_moi")
		self.assertIn(user.name, frappe.db.get_value("Communication", comm, "recipients"))
