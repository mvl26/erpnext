# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Trường hợp biên của Đợt 1 tìm ra khi review (spec mục 13.3)."""

import json

import frappe
from frappe.utils import add_days

from erpnext.controllers.accounts_controller import update_child_qty_rate
from erpnext.selling.kiem_gia.cau_hinh import CHAN
from erpnext.selling.kiem_gia.gia_goc import KHONG_CO_GIA_MUA, KHOP, THAP_HON, tim_gia_goc
from erpnext.selling.kiem_gia.kiem_chung_tu import BO_QUA
from erpnext.selling.report.doi_chieu_gia_ban_gia_mua.doi_chieu_gia_ban_gia_mua import execute
from erpnext.selling.tests.test_kiem_gia_chung_tu import KiemChungTuCase


class TestTruongHopBien(KiemChungTuCase):
	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.set_user, "Administrator")

	def che_do(self, value, **settings):
		frappe.db.set_single_value("Selling Settings", {"che_do_kiem_gia": value, **settings})
		frappe.clear_document_cache("Selling Settings", "Selling Settings")

	def messages(self, title="Kiểm giá bán"):
		return [m for m in frappe.get_message_log() if m.get("title") == title]

	# --- Tiền tệ, chiết khấu, loại mặt hàng -------------------------------------

	def test_foreign_currency_order_is_compared_in_its_own_currency(self):
		usd = frappe.get_doc(
			{
				"doctype": "Price List",
				"price_list_name": f"_KG Bán USD {self.sfx}",
				"selling": 1,
				"currency": "USD",
				"enabled": 1,
			}
		).insert(ignore_permissions=True)
		item = self.item(100000)
		so = frappe.get_doc(
			{
				"doctype": "Sales Order",
				"company": self.company,
				"customer": self.khach,
				"transaction_date": self.d,
				"delivery_date": add_days(self.d, 7),
				"selling_price_list": usd.name,
				"currency": "USD",
				"conversion_rate": 25000,
				"plc_conversion_rate": 25000,
				"price_list_currency": "USD",
				"ignore_pricing_rule": 1,
				"items": [self.row(item, 4.04)],
			}
		).insert(ignore_permissions=True)

		d = so.items[0]
		self.assertEqual((d.trang_thai_gia, d.gia_goc, d.gia_chuan), (KHOP, 4, 4.04))

	def test_order_level_discount_is_compared_after_discount(self):
		so = self.so([self.row(self.item(100000), 101000)])
		so.apply_discount_on = "Net Total"
		so.additional_discount_percentage = 10
		so.save(ignore_permissions=True)

		d = so.items[0]
		self.assertEqual(d.net_rate, 90900)
		self.assertEqual((d.trang_thai_gia, d.chenh_lech), (THAP_HON, -10100))

	def test_non_stock_items_are_skipped(self):
		dich_vu = frappe.new_doc("Item")
		dich_vu.item_code = f"_KG-DV-{self.sfx}"
		dich_vu.item_name = "Phí vận chuyển"
		dich_vu.item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
		dich_vu.stock_uom = "_KG Cái"
		dich_vu.is_stock_item = 0
		dich_vu.insert(ignore_permissions=True)

		d = self.so([self.row(dich_vu.name, 50000)]).items[0]

		self.assertEqual(d.trang_thai_gia, BO_QUA)

	def test_non_stock_line_does_not_block_in_block_mode(self):
		self.che_do(CHAN)
		dich_vu = frappe.new_doc("Item")
		dich_vu.item_code = f"_KG-DV-{self.sfx}"
		dich_vu.item_name = "Phí vận chuyển"
		dich_vu.item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
		dich_vu.stock_uom = "_KG Cái"
		dich_vu.is_stock_item = 0
		dich_vu.insert(ignore_permissions=True)
		so = self.so([self.row(self.item(100000), 101000), self.row(dich_vu.name, 50000)])

		so.submit()

		self.assertEqual(so.docstatus, 1)

	def test_price_in_a_uom_the_item_does_not_know_is_ignored(self):
		item = self.item(None)
		frappe.get_doc(
			{
				"doctype": "Item Price",
				"price_list": self.mua,
				"item_code": item,
				"uom": "_KG Hộp",
				"price_list_rate": 1000000,
				"valid_from": add_days(self.d, -5),
				"currency": self.currency,
			}
		).insert(ignore_permissions=True)

		self.assertEqual(tim_gia_goc(item, self.d).trang_thai, KHONG_CO_GIA_MUA)
		self.assertIn("chưa khai hệ số", tim_gia_goc(item, self.d).ly_do)

	def test_report_uses_configured_margins_when_left_blank(self):
		item = self.item(100000)
		khach_2 = self.customer(ty_le_lai_rieng=1, ty_le_lai=2)
		khach_tat = self.customer(kiem_gia_ban=0)
		for khach, gia in ((None, 101000), (khach_2, 102000), (khach_tat, 1)):
			frappe.get_doc(
				{
					"doctype": "Item Price",
					"price_list": self.ban,
					"item_code": item,
					"uom": "_KG Cái",
					"customer": khach,
					"price_list_rate": gia,
					"valid_from": add_days(self.d, -5),
					"currency": self.currency,
				}
			).insert(ignore_permissions=True)

		_cols, data = execute({"price_list": self.ban, "ngay": self.d, "company": self.company})
		rows = {r.customer: r for r in data}

		self.assertEqual((rows[None].trang_thai, rows[None].ty_le_lai), (KHOP, 1))
		self.assertEqual((rows[khach_2].trang_thai, rows[khach_2].ty_le_lai), (KHOP, 2))
		self.assertEqual(rows[khach_tat].trang_thai, BO_QUA)

	# --- Khách xem qua cổng không được thấy giá mua ------------------------------

	def test_portal_user_does_not_see_the_price_warning(self):
		khach_web = frappe.get_doc(
			{
				"doctype": "User",
				"email": f"_kg_web_{self.sfx}@example.com",
				"first_name": "KG web",
				"user_type": "Website User",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
		frappe.set_user(khach_web.name)
		frappe.clear_messages()

		so = self.so([self.row(self.item(100000), 99000)])

		self.assertEqual(so.items[0].trang_thai_gia, THAP_HON)
		self.assertFalse(self.messages())

	# --- Cấu hình ---------------------------------------------------------------

	def test_two_rate_rows_for_one_customer_on_an_item_are_rejected(self):
		row = {"customer_name": self.khach, "ty_le_lai_rieng": 1}
		self.assertRaisesRegex(
			frappe.ValidationError,
			"mỗi khách một dòng",
			self.item,
			100000,
			customer_items=[{**row, "ty_le_lai": 1}, {**row, "ty_le_lai": 2}],
		)

	def test_copying_a_customer_does_not_copy_its_rate(self):
		khach = frappe.get_doc("Customer", self.customer(ty_le_lai_rieng=1, ty_le_lai=2))

		ban_sao = frappe.copy_doc(khach, ignore_no_copy=False)  # như nút Duplicate
		ban_sao.customer_name = f"{khach.customer_name} - bản sao"
		nhan_vien = frappe.get_doc(
			{
				"doctype": "User",
				"email": f"_kg_nv_{self.sfx}@example.com",
				"first_name": "KG nv",
				"send_welcome_email": 0,
				"roles": [{"role": "Sales User"}],
			}
		).insert(ignore_permissions=True)
		frappe.db.set_single_value("Selling Settings", "vai_tro_sua_ty_le_lai", "_KG Không ai có")
		frappe.clear_document_cache("Selling Settings", "Selling Settings")
		frappe.set_user(nhan_vien.name)
		ban_sao.insert(ignore_permissions=True)  # nhân viên copy được, không bị chặn

		stored = frappe.db.get_value(
			"Customer", ban_sao.name, ["kiem_gia_ban", "ty_le_lai_rieng", "ty_le_lai"]
		)
		self.assertEqual(tuple(stored), (1, 0, 0))

	# --- Duyệt, sửa sau Submit, sửa lại chứng từ --------------------------------

	def test_amended_order_starts_without_approval(self):
		self.che_do(CHAN)
		so = self.so([self.row(self.item(100000), 99000)])
		so.ly_do_lech_gia = "Khách lớn"
		so.save(ignore_permissions=True)
		so.submit()  # Administrator là người duyệt
		self.assertTrue(so.nguoi_duyet_gia)
		so.cancel()

		ban_sua = frappe.copy_doc(so)  # Amend chép cả ô no_copy (create_new.js, from_amend)
		ban_sua.amended_from = so.name
		ban_sua.docstatus = 0
		ban_sua.insert(ignore_permissions=True)

		self.assertFalse(ban_sua.nguoi_duyet_gia or ban_sua.ma_duyet_gia)
		self.assertEqual(ban_sua.ly_do_lech_gia, "Khách lớn")

	def test_forged_approval_sent_through_the_api_is_ignored(self):
		from erpnext.selling.kiem_gia.kiem_chung_tu import dau_van_tay, dong_lech

		self.che_do(CHAN, vai_tro_duyet_gia_lech=None, vai_tro_sua_ty_le_lai="_KG Không ai có")
		nhan_vien = frappe.get_doc(
			{
				"doctype": "User",
				"email": f"_kg_nv_{self.sfx}@example.com",
				"first_name": "KG nv",
				"send_welcome_email": 0,
				"roles": [{"role": "Sales User"}],
			}
		).insert(ignore_permissions=True)
		so = self.so([self.row(self.item(100000), 99000)])
		frappe.set_user(nhan_vien.name)
		so.ly_do_lech_gia = "Tự duyệt"
		so.nguoi_duyet_gia = "Administrator"
		so.ma_duyet_gia = dau_van_tay(so, dong_lech(so))
		so.save(ignore_permissions=True)

		self.assertFalse(frappe.db.get_value("Sales Order", so.name, "ma_duyet_gia"))
		self.assertRaisesRegex(frappe.ValidationError, "chưa được duyệt", so.submit)

	def test_update_items_in_record_only_mode_refreshes_the_rows(self):
		so = self.so([self.row(self.item(100000), 101000)])
		so.submit()
		d = so.items[0]

		update_child_qty_rate(
			"Sales Order",
			json.dumps(
				[{"docname": d.name, "item_code": d.item_code, "qty": 1, "rate": 99000, "uom": d.uom}]
			),
			so.name,
		)

		stored = frappe.db.get_value(
			"Sales Order Item", d.name, ["rate", "trang_thai_gia", "chenh_lech"], as_dict=True
		)
		self.assertEqual((stored.rate, stored.trang_thai_gia, stored.chenh_lech), (99000, THAP_HON, -2000))

	def test_quotation_is_never_blocked(self):
		self.che_do(CHAN)
		q = frappe.get_doc(
			{
				"doctype": "Quotation",
				"company": self.company,
				"quotation_to": "Customer",
				"party_name": self.khach,
				"transaction_date": self.d,
				"valid_till": add_days(self.d, 30),
				"selling_price_list": self.ban,
				"currency": self.currency,
				"ignore_pricing_rule": 1,
				"items": [self.row(self.item(100000), 1)],
			}
		).insert(ignore_permissions=True)

		q.submit()

		self.assertEqual(q.docstatus, 1)

	def test_switching_off_lets_a_blocked_order_through(self):
		self.che_do(CHAN, vai_tro_duyet_gia_lech=None)
		so = self.so([self.row(self.item(100000), 1)])
		self.bat(0)

		so.submit()

		self.assertEqual(so.docstatus, 1)

	# --- Báo cáo, báo giá NCC, PO ----------------------------------------------

	def test_report_refuses_a_price_list_in_another_currency(self):
		usd = frappe.get_doc(
			{
				"doctype": "Price List",
				"price_list_name": f"_KG Bán USD {self.sfx}",
				"selling": 1,
				"currency": "USD",
				"enabled": 1,
			}
		).insert(ignore_permissions=True)

		self.assertRaisesRegex(
			frappe.ValidationError,
			"tiền tệ công ty",
			execute,
			{"price_list": usd.name, "company": self.company},
		)

	def test_supplier_quotation_discount_is_stored_after_discount(self):
		item = self.item(None)
		ncc = frappe.new_doc("Supplier")
		ncc.supplier_name = f"_KG NCC {self.sfx}"
		ncc.supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
		ncc.default_price_list = self.mua
		ncc.insert(ignore_permissions=True)
		sq = frappe.get_doc(
			{
				"doctype": "Supplier Quotation",
				"supplier": ncc.name,
				"company": self.company,
				"transaction_date": self.d,
				"currency": self.currency,
				"buying_price_list": self.mua,
				"apply_discount_on": "Net Total",
				"additional_discount_percentage": 10,
				"items": [{"item_code": item, "qty": 1, "uom": "_KG Cái", "rate": 100000}],
			}
		).insert(ignore_permissions=True)

		sq.submit()

		self.assertEqual(tim_gia_goc(item, self.d).gia_goc, 90000)

	def test_purchase_order_discount_is_taken_into_account(self):
		item = self.item(100000)
		so = self.so([self.row(item, 101000)])
		so.submit()
		ncc = frappe.new_doc("Supplier")
		ncc.supplier_name = f"_KG NCC {self.sfx}"
		ncc.supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
		ncc.insert(ignore_permissions=True)
		frappe.clear_messages()

		frappe.get_doc(
			{
				"doctype": "Purchase Order",
				"supplier": ncc.name,
				"company": self.company,
				"transaction_date": self.d,
				"schedule_date": add_days(self.d, 7),
				"currency": self.currency,
				"apply_discount_on": "Net Total",
				"additional_discount_percentage": 10,
				"items": [
					{
						"item_code": item,
						"qty": 1,
						"uom": "_KG Cái",
						"rate": 105000,
						"warehouse": self.warehouse,
						"schedule_date": add_days(self.d, 7),
						"sales_order": so.name,
						"sales_order_item": so.items[0].name,
					}
				],
			}
		).insert(ignore_permissions=True)

		self.assertFalse(self.messages("Kiểm giá mua"))


class TestDuyetSauReview(KiemChungTuCase):
	"""Lỗi review độc lập (spec 13.3, R9-R14)."""

	che_do = TestTruongHopBien.che_do

	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.set_user, "Administrator")
		self.che_do(CHAN, vai_tro_duyet_gia_lech="_KG Duyệt", vai_tro_sua_ty_le_lai="_KG Không ai có")
		if not frappe.db.exists("Role", "_KG Duyệt"):
			frappe.get_doc({"doctype": "Role", "role_name": "_KG Duyệt", "desk_access": 1}).insert(
				ignore_permissions=True
			)
		self.nhan_vien = self.nguoi("nv", ["Sales User"])
		self.nguoi_duyet = self.nguoi("duyet", ["Sales User", "_KG Duyệt"])

	def nguoi(self, label, roles):
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

	def test_order_discount_added_after_approval_needs_a_new_approval(self):
		from erpnext.selling.kiem_gia.kiem_chung_tu import duyet_gia_lech

		so = self.so([self.row(self.item(100000), 100000)])
		so.ly_do_lech_gia = "Khách lớn"
		so.save(ignore_permissions=True)
		frappe.set_user(self.nguoi_duyet)
		duyet_gia_lech(so.name)
		frappe.set_user("Administrator")
		so.reload()
		so.apply_discount_on = "Net Total"
		so.additional_discount_percentage = 40
		so.save(ignore_permissions=True)

		self.assertFalse(so.nguoi_duyet_gia)
		frappe.set_user(self.nhan_vien)
		self.assertRaisesRegex(frappe.ValidationError, "chưa được duyệt", so.submit)

	def test_editing_the_reason_after_approval_needs_a_new_approval(self):
		from erpnext.selling.kiem_gia.kiem_chung_tu import duyet_gia_lech

		so = self.so([self.row(self.item(100000), 100000)])
		so.ly_do_lech_gia = "Khách lớn"
		so.save(ignore_permissions=True)
		frappe.set_user(self.nguoi_duyet)
		duyet_gia_lech(so.name)
		frappe.set_user("Administrator")
		so.reload()
		so.ly_do_lech_gia = "Lý do khác"
		so.save(ignore_permissions=True)

		self.assertFalse(so.nguoi_duyet_gia)

	def test_update_items_on_an_old_order_only_checks_changed_rows(self):
		self.bat(0)
		cu = self.item(100000)
		so = self.so([self.row(cu, 1), self.row(self.item(100000), 101000)])
		so.submit()  # Submit khi chưa bật kiểm: dòng 1 lệch nhưng không ai duyệt
		self.bat(1)
		d = so.items[1]

		frappe.set_user(self.nhan_vien)
		update_child_qty_rate(
			"Sales Order",
			json.dumps(
				[
					{"docname": so.items[0].name, "item_code": cu, "qty": 1, "rate": 1, "uom": "_KG Cái"},
					{"docname": d.name, "item_code": d.item_code, "qty": 2, "rate": 101000, "uom": d.uom},
				]
			),
			so.name,
		)

		self.assertEqual(frappe.db.get_value("Sales Order Item", d.name, "qty"), 2)

	def test_portal_user_gets_a_generic_message(self):
		from erpnext.selling.kiem_gia.kiem_chung_tu import kiem_truoc_submit

		so = self.so([self.row(self.item(100000), 1)])
		khach_web = frappe.get_doc(
			{
				"doctype": "User",
				"email": f"_kg_web2_{self.sfx}@example.com",
				"first_name": "KG web",
				"user_type": "Website User",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
		frappe.set_user(khach_web.name)

		with self.assertRaises(frappe.ValidationError) as ctx:
			kiem_truoc_submit(so)
		self.assertNotIn("Thấp hơn", str(ctx.exception))
		self.assertIn("Miyano kiểm tra giá", str(ctx.exception))
