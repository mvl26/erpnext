# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Kiểm giá bán trên Quotation và Sales Order theo hệ số khách hàng (BA12 R02-R05, R07,
R08, D04, D07, D08; nghiệm thu A01-A04, A07; PO chốt Q2)."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, nowdate
from frappe.utils.nestedset import get_root_of

from erpnext.selling.kiem_gia.gia_goc import (
	BAO_GIA_DOT,
	CAO_HON,
	CHUA_CO_GIA_MUA,
	HD_NGUYEN_TAC,
	KHOP,
	THAP_HON,
)
from erpnext.selling.kiem_gia.kiem_chung_tu import BO_QUA, tinh_lai
from erpnext.stock.tests.test_item_code_rule import use_naming_mode


class KiemChungTuCase(FrappeTestCase):
	"""Dữ liệu chung: một NCC với bảng giá "Mua - NCC" (HĐ nguyên tắc), một bảng giá bán,
	một khách có hệ số 1,01 (Himedic). Mặt hàng tạo bằng `item()` nhận NCC đó làm NCC mặc
	định và có giá HĐ nguyên tắc."""

	HE_SO = 1.01

	def setUp(self):
		self.addCleanup(frappe.clear_document_cache, "Selling Settings", "Selling Settings")
		self.addCleanup(frappe.clear_document_cache, "Stock Settings", "Stock Settings")
		frappe.db.savepoint("kiem_gia_chung_tu")
		self.addCleanup(frappe.db.rollback, save_point="kiem_gia_chung_tu")
		self.addCleanup(setattr, frappe.flags, "mute_emails", frappe.flags.mute_emails)
		frappe.flags.mute_emails = True  # chỉ ghi Communication, không gửi thật
		use_naming_mode(self, "Item Code")
		# Như production (P7): chứng từ không tự thêm/ghi đè Item Price.
		frappe.db.set_single_value(
			"Stock Settings",
			{"auto_insert_price_list_rate_if_missing": 0, "update_existing_price_list_rate": 0},
		)
		frappe.clear_document_cache("Stock Settings", "Stock Settings")
		self.d = getdate(nowdate())
		self.sfx = frappe.generate_hash(length=6)
		self.company = frappe.db.get_value("Company", {}, "name")
		self.currency = frappe.get_cached_value("Company", self.company, "default_currency")
		self.warehouse = frappe.db.get_value("Warehouse", {"company": self.company, "is_group": 0}, "name")
		for uom in ("_KG Cái", "_KG Hộp"):
			if not frappe.db.exists("UOM", uom):
				frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert(ignore_permissions=True)
		self.bat(1)
		self.ncc = self.supplier()
		self.mua = self.price_list(f"Mua - {self.ncc}", buying=1)
		self.ban = self.price_list("Bán", buying=0)
		self.khach = self.customer(he_so=self.HE_SO)

	# --- Dữ liệu --------------------------------------------------------------

	def bat(self, value):
		frappe.db.set_single_value("Selling Settings", "bat_kiem_gia_ban", value)
		frappe.clear_document_cache("Selling Settings", "Selling Settings")

	def price_list(self, label, buying):
		return (
			frappe.get_doc(
				{
					"doctype": "Price List",
					"price_list_name": f"_KG {label} {self.sfx}",
					"buying": buying,
					"selling": 0 if buying else 1,
					"currency": self.currency,
					"enabled": 1,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def supplier(self):
		return (
			frappe.get_doc(
				{
					"doctype": "Supplier",
					"supplier_name": f"_KG NCC {frappe.generate_hash(length=6)}",
					"supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"),
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def customer(
		self, he_so=None, so_hop_dong="HĐ-KG-01", tu_ngay=None, den_ngay=None, theo_hang=(), **fields
	):
		doc = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": f"_KG Khách {frappe.generate_hash(length=6)}",
				"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
				"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name"),
				"default_price_list": self.ban,
				**fields,
			}
		)
		if he_so:
			doc.append(
				"he_so_gia_ban",
				{
					"he_so": he_so,
					"so_hop_dong": so_hop_dong,
					"tu_ngay": tu_ngay or add_days(self.d, -365),
					"den_ngay": den_ngay,
				},
			)
		for item_code, hs in theo_hang:
			doc.append(
				"he_so_theo_mat_hang",
				{"item_code": item_code, "he_so": hs, "tu_ngay": add_days(self.d, -365)},
			)
		return doc.insert(ignore_permissions=True).name

	def item(self, gia_hd=100000, hop=None, ncc=None, is_stock_item=1, gia_ban=None):
		"""Mặt hàng có NCC mặc định (`ncc`, mặc định NCC chung) và giá HĐ nguyên tắc `gia_hd`.
		`gia_ban`: giá trong bảng giá của khách — không có thì mặt hàng chưa có trong bảng giá,
		tức khác bảng giá (Q2)."""
		doc = frappe.new_doc("Item")
		doc.item_code = f"_KG-{frappe.generate_hash(length=8)}"
		doc.item_name = doc.item_code
		doc.item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
		doc.stock_uom = "_KG Cái"
		doc.is_stock_item = is_stock_item
		if hop:
			doc.append("uoms", {"uom": "_KG Hộp", "conversion_factor": hop})
		ncc = self.ncc if ncc is None else ncc
		if ncc:
			doc.append("supplier_items", {"supplier": ncc, "is_default": 1})
		doc.insert(ignore_permissions=True)
		if gia_hd is not None:
			self.gia_hd(doc.name, gia_hd, ncc=ncc or self.ncc)
		if gia_ban is not None:
			self.gia_ban(doc.name, gia_ban)
		return doc.name

	def gia_hd(self, item, rate, valid_from=None, ncc=None, price_list=None, uom="_KG Cái"):
		"""Giá HĐ nguyên tắc: dòng Item Price của bảng giá "Mua - NCC", có `supplier`."""
		return (
			frappe.get_doc(
				{
					"doctype": "Item Price",
					"price_list": price_list or self.mua,
					"item_code": item,
					"uom": uom,
					"supplier": ncc or self.ncc,
					"price_list_rate": rate,
					"valid_from": valid_from or add_days(self.d, -30),
					"currency": self.currency,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def bao_gia(
		self, item, rate, ncc=None, ngay=None, valid_till=None, uom="_KG Cái", cf=1, submit=True, **fields
	):
		"""Báo giá đợt: Supplier Quotation của NCC (đã Submit nếu `submit`)."""
		doc = frappe.get_doc(
			{
				"doctype": "Supplier Quotation",
				"supplier": ncc or self.ncc,
				"company": self.company,
				"transaction_date": ngay or self.d,
				"valid_till": valid_till,
				"currency": self.currency,
				"conversion_rate": 1,
				"items": [
					{
						"item_code": item,
						"qty": 1,
						"uom": uom,
						"conversion_factor": cf,
						"rate": rate,
						"warehouse": self.warehouse,
					}
				],
				**fields,
			}
		).insert(ignore_permissions=True)
		if submit:
			doc.submit()
		return doc

	def gia_ban(self, item, rate, valid_from=None, uom="_KG Cái", price_list=None):
		"""Giá trong bảng giá bán của khách (R05)."""
		return (
			frappe.get_doc(
				{
					"doctype": "Item Price",
					"price_list": price_list or self.ban,
					"item_code": item,
					"uom": uom,
					"price_list_rate": rate,
					"valid_from": valid_from or add_days(self.d, -30),
					"currency": self.currency,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def row(self, item, rate, uom="_KG Cái", **fields):
		return {
			"item_code": item,
			"qty": 1,
			"uom": uom,
			"rate": rate,
			"warehouse": self.warehouse,
			"delivery_date": add_days(self.d, 7),
			**fields,
		}

	def so(self, rows, customer=None, taxes=(), **fields):
		return frappe.get_doc(
			{
				"doctype": "Sales Order",
				"company": self.company,
				"customer": customer or self.khach,
				"transaction_date": self.d,
				"delivery_date": add_days(self.d, 7),
				"selling_price_list": self.ban,
				"currency": self.currency,
				"ignore_pricing_rule": 1,
				"items": rows,
				"taxes": list(taxes),
				**fields,
			}
		).insert(ignore_permissions=True)

	def canh_bao(self):
		return " ".join(str(m) for m in frappe.message_log)


class TestKiemGiaSalesOrder(KiemChungTuCase):
	def test_a01_principle_contract_price(self):
		item = self.item(123457)
		d = self.so([self.row(item, 124691.57)]).items[0]

		self.assertEqual(d.trang_thai_gia, KHOP)
		self.assertEqual(d.gia_mua, 123457)
		self.assertEqual(d.nguon_gia_mua, HD_NGUYEN_TAC)
		self.assertEqual(d.he_so_gia_ban, 1.01)
		self.assertEqual(d.so_hop_dong_he_so, "HĐ-KG-01")
		self.assertEqual(d.gia_de_xuat, 124691.57)
		self.assertEqual(d.ncc_du_kien, self.ncc)

	def test_a02_batch_quotation_wins_over_the_contract(self):
		item = self.item(123457)
		sq = self.bao_gia(item, 125000)
		d = self.so([self.row(item, 126250)]).items[0]

		self.assertEqual(d.trang_thai_gia, KHOP)
		self.assertEqual((d.gia_mua, d.gia_de_xuat), (125000, 126250))
		self.assertEqual((d.nguon_gia_mua, d.chung_tu_gia_mua), (BAO_GIA_DOT, sq.name))

	def test_a03_changing_the_planned_supplier_recomputes(self):
		item = self.item(123457)
		ncc2 = self.supplier()
		self.gia_hd(item, 200000, ncc=ncc2)
		so = self.so([self.row(item, 124691.57)])
		so.items[0].ncc_du_kien = ncc2
		so.save()
		d = so.items[0]

		self.assertEqual((d.gia_mua, d.gia_de_xuat), (200000, 202000))
		self.assertEqual(d.trang_thai_gia, THAP_HON)

	def test_a03_the_form_shows_the_new_supplier_price_before_saving(self):
		item = self.item(123457)
		ncc2 = self.supplier()
		self.gia_hd(item, 200000, ncc=ncc2)
		so = self.so([self.row(item, 124691.57)])
		dang_sua = so.as_dict()
		dang_sua["items"][0]["ncc_du_kien"] = ncc2
		kq = tinh_lai(frappe.as_json(dang_sua))[so.items[0].name]

		self.assertEqual((kq["gia_mua"], kq["gia_de_xuat"], kq["trang_thai_gia"]), (200000, 202000, THAP_HON))
		# Chưa lưu: DB vẫn giữ kết quả theo NCC cũ.
		self.assertEqual(frappe.db.get_value("Sales Order Item", so.items[0].name, "gia_mua"), 123457)

	def test_an_unsaved_order_is_checked_with_the_default_supplier(self):
		item = self.item(123457)
		dong = self.row(
			item, 124691.57, doctype="Sales Order Item", name="new-sales-order-item-1", conversion_factor=1
		)
		dong["net_rate"] = 124691.57
		kq = tinh_lai(
			{
				"doctype": "Sales Order",
				"name": "new-sales-order-1",
				"__islocal": 1,
				"company": self.company,
				"customer": self.khach,
				"transaction_date": self.d,
				"currency": self.currency,
				"conversion_rate": 1,
				"items": [dong],
			}
		)["new-sales-order-item-1"]

		self.assertEqual((kq["ncc_du_kien"], kq["gia_mua"], kq["trang_thai_gia"]), (self.ncc, 123457, KHOP))

	def test_a04_r04_mismatch_is_flagged_with_the_difference(self):
		item = self.item(123457)
		cao = self.so([self.row(item, 125000)]).items[0]
		thap = self.so([self.row(item, 124000)]).items[0]

		self.assertEqual((cao.trang_thai_gia, cao.chenh_lech_gia), (CAO_HON, 308.43))
		self.assertEqual((thap.trang_thai_gia, thap.chenh_lech_gia), (THAP_HON, -691.57))
		self.assertIn("124.691", self.canh_bao().replace(",", "."))

	def test_the_warning_writes_numbers_in_the_system_number_format(self):
		# Với định dạng số Việt, "-6,250" đọc thành âm sáu phẩy hai lăm.
		item = self.item(123457)
		goc = frappe.db.get_default

		def dinh_dang_viet(key, *args, **kwargs):
			return "#.###,##" if key == "number_format" else goc(key, *args, **kwargs)

		frappe.clear_messages()
		with patch.object(frappe.db, "get_default", side_effect=dinh_dang_viet):
			self.so([self.row(item, 118442)])

		self.assertIn("hệ số 1,01", self.canh_bao())
		self.assertIn("chênh -6.249,57", self.canh_bao())

	def test_d04_no_tolerance_after_rounding_to_four_decimals(self):
		item = self.item(123457)
		self.assertEqual(self.so([self.row(item, 124691.57)]).items[0].trang_thai_gia, KHOP)
		self.assertEqual(self.so([self.row(item, 124691.58)]).items[0].chenh_lech_gia, 0.01)

	def test_a07_r07_customer_without_a_coefficient_is_not_checked(self):
		item = self.item(100000)
		frappe.clear_messages()
		d = self.so([self.row(item, 1)], customer=self.customer()).items[0]

		self.assertFalse(d.trang_thai_gia)
		self.assertIsNone(d.gia_de_xuat)
		self.assertFalse(frappe.message_log)

	def test_r07_expired_coefficient_counts_as_none(self):
		khach = self.customer(he_so=1.05, tu_ngay=add_days(self.d, -60), den_ngay=add_days(self.d, -1))
		self.assertFalse(self.so([self.row(self.item(), 1)], customer=khach).items[0].trang_thai_gia)

	def test_r08_no_buying_price(self):
		d = self.so([self.row(self.item(gia_hd=None), 100000)]).items[0]

		self.assertEqual(d.trang_thai_gia, CHUA_CO_GIA_MUA)
		self.assertIn("Chưa có giá mua để đối soát", d.ghi_chu_gia)

	def test_r08_item_without_any_supplier(self):
		d = self.so([self.row(self.item(gia_hd=None, ncc=""), 100000)]).items[0]

		self.assertEqual(d.trang_thai_gia, CHUA_CO_GIA_MUA)
		self.assertFalse(d.ncc_du_kien)
		self.assertIn("NCC", d.ghi_chu_gia)

	def test_result_is_stored_in_the_database(self):
		item = self.item(123457)
		so = self.so([self.row(item, 125000)])
		saved = frappe.db.get_value(
			"Sales Order Item",
			so.items[0].name,
			["trang_thai_gia", "gia_mua", "gia_de_xuat", "chenh_lech_gia", "he_so_gia_ban", "nguon_gia_mua"],
			as_dict=True,
		)
		self.assertEqual(
			saved,
			{
				"trang_thai_gia": CAO_HON,
				"gia_mua": 123457,
				"gia_de_xuat": 124691.57,
				"chenh_lech_gia": 308.43,
				"he_so_gia_ban": 1.01,
				"nguon_gia_mua": HD_NGUYEN_TAC,
			},
		)

	def test_free_internal_and_non_stock_rows_are_skipped(self):
		item = self.item(100000)
		dich_vu = self.item(100000, is_stock_item=0)
		so = self.so([self.row(item, 0, is_free_item=1), self.row(dich_vu, 5)])
		self.assertEqual([d.trang_thai_gia for d in so.items], [BO_QUA, BO_QUA])

		noi_bo = self.customer(
			he_so=1.01,
			is_internal_customer=1,
			represents_company=self.company,
			companies=[{"company": self.company}],
		)
		self.assertEqual(self.so([self.row(item, 5)], customer=noi_bo).items[0].trang_thai_gia, BO_QUA)

	def test_selling_by_the_box(self):
		item = self.item(1000, hop=10)
		d = self.so([self.row(item, 10100, uom="_KG Hộp")]).items[0]

		self.assertEqual((d.gia_mua, d.gia_de_xuat, d.trang_thai_gia), (10000, 10100, KHOP))

	def test_item_level_coefficient_when_the_customer_has_none(self):
		item = self.item(100000)
		khach = self.customer(theo_hang=[(item, 1.05)])
		d = self.so([self.row(item, 105000)], customer=khach).items[0]

		self.assertEqual((d.he_so_gia_ban, d.trang_thai_gia), (1.05, KHOP))

	def test_saving_again_uses_the_new_buying_price(self):
		item = self.item(100000)
		so = self.so([self.row(item, 101000)])
		self.gia_hd(item, 110000, valid_from=self.d)
		so.save()

		self.assertEqual((so.items[0].gia_de_xuat, so.items[0].trang_thai_gia), (111100, THAP_HON))

	def test_nothing_is_checked_when_switched_off(self):
		self.bat(0)
		self.assertFalse(self.so([self.row(self.item(), 1)]).items[0].trang_thai_gia)

	def test_tax_inclusive_price_is_compared_before_tax(self):
		item = self.item(100000)
		account = frappe.db.get_value(
			"Account", {"company": self.company, "account_type": "Tax", "is_group": 0}
		)
		if not account:
			self.skipTest("Công ty chưa có tài khoản thuế")
		d = self.so(
			[self.row(item, 111100)],
			taxes=[
				{
					"charge_type": "On Net Total",
					"account_head": account,
					"description": "VAT",
					"rate": 10,
					"included_in_print_rate": 1,
				}
			],
		).items[0]
		self.assertEqual(d.trang_thai_gia, KHOP)

	def test_order_level_discount_is_compared_after_discount(self):
		item = self.item(100000)
		d = self.so(
			[self.row(item, 202000)], apply_discount_on="Net Total", additional_discount_percentage=50
		).items[0]
		self.assertEqual(d.trang_thai_gia, KHOP)

	def test_foreign_currency_order_is_compared_in_its_own_currency(self):
		item = self.item(2500000)
		usd = "USD"
		if not frappe.db.exists("Currency", usd) or usd == self.currency:
			self.skipTest("Không có USD")
		d = self.so(
			[self.row(item, 101)], currency=usd, conversion_rate=25000, plc_conversion_rate=25000
		).items[0]

		self.assertEqual((d.gia_mua, d.gia_de_xuat, d.trang_thai_gia), (100, 101, KHOP))


class TestKhacBangGia(KiemChungTuCase):
	"""R05: so giá đề xuất với giá trong bảng giá của khách."""

	def test_a05_proposal_differs_from_the_price_list(self):
		item = self.item(123457)
		self.gia_ban(item, 120000)
		d = self.so([self.row(item, 124691.57)]).items[0]

		self.assertEqual((d.gia_bang_gia, d.khac_bang_gia), (120000, 1))
		self.assertIn("Submit cần số văn bản", self.canh_bao())

	def test_same_as_the_price_list(self):
		item = self.item(123457)
		self.gia_ban(item, 124691.57)
		self.assertEqual(self.so([self.row(item, 124691.57)]).items[0].khac_bang_gia, 0)

	def test_q2_item_missing_from_the_customer_list_is_a_difference(self):
		d = self.so([self.row(self.item(123457), 124691.57)]).items[0]

		self.assertEqual((d.gia_bang_gia, d.ngoai_bang_gia, d.khac_bang_gia), (None, 1, 1))
		self.assertIn("chưa có trong bảng giá KH", self.canh_bao())

	def test_q2_no_buying_price_and_missing_from_the_list(self):
		d = self.so([self.row(self.item(gia_hd=None), 100000)]).items[0]
		self.assertEqual((d.trang_thai_gia, d.ngoai_bang_gia, d.khac_bang_gia), (CHUA_CO_GIA_MUA, 1, 1))

	def test_q2_no_buying_price_but_in_the_list_is_not_a_difference(self):
		d = self.so([self.row(self.item(gia_hd=None, gia_ban=100000), 100000)]).items[0]
		self.assertEqual((d.trang_thai_gia, d.ngoai_bang_gia, d.khac_bang_gia), (CHUA_CO_GIA_MUA, 0, 0))

	def test_q2_choosing_another_list_on_the_order_does_not_dodge_r05(self):
		item = self.item(123457, gia_ban=120000)
		khac = self.price_list("Bán khác", buying=0)
		self.gia_ban(item, 124691.57, price_list=khac)

		d = self.so([self.row(item, 124691.57)], selling_price_list=khac).items[0]

		self.assertEqual((d.gia_bang_gia, d.khac_bang_gia), (120000, 1))

	def test_q2_customer_group_list_when_the_customer_has_none(self):
		item = self.item(123457, gia_ban=124691.57)
		khach = self.customer(he_so=1.01, default_price_list=None, customer_group=self.nhom(self.ban))

		d = self.so([self.row(item, 124691.57)], customer=khach).items[0]

		self.assertEqual((d.gia_bang_gia, d.khac_bang_gia), (124691.57, 0))

	def test_q2_customer_without_any_price_list(self):
		item = self.item(123457, gia_ban=124691.57)
		khach = self.customer(he_so=1.01, default_price_list=None, customer_group=self.nhom(None))

		d = self.so([self.row(item, 124691.57)], customer=khach).items[0]

		self.assertEqual((d.ngoai_bang_gia, d.khac_bang_gia), (1, 1))
		self.assertIn("chưa có bảng giá mặc định", self.canh_bao())

	def test_list_price_is_converted_to_the_order_currency(self):
		usd = "USD"
		if not frappe.db.exists("Currency", usd) or usd == self.currency:
			self.skipTest("Không có USD")
		item = self.item(2500000, gia_ban=2525000)

		d = self.so(
			[self.row(item, 101)], currency=usd, conversion_rate=25000, plc_conversion_rate=25000
		).items[0]

		self.assertEqual((d.gia_bang_gia, d.gia_de_xuat, d.khac_bang_gia), (101, 101, 0))

	def nhom(self, default_price_list):
		return (
			frappe.get_doc(
				{
					"doctype": "Customer Group",
					"customer_group_name": f"_KG Nhóm {frappe.generate_hash(length=6)}",
					"parent_customer_group": get_root_of("Customer Group"),
					"default_price_list": default_price_list,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def test_price_list_by_the_box(self):
		item = self.item(1000, hop=10)
		self.gia_ban(item, 990)
		d = self.so([self.row(item, 10100, uom="_KG Hộp")]).items[0]
		self.assertEqual((d.gia_bang_gia, d.khac_bang_gia), (9900, 1))

	def test_a_customer_specific_price_wins(self):
		item = self.item(100000)
		self.gia_ban(item, 90000)
		frappe.get_doc(
			{
				"doctype": "Item Price",
				"price_list": self.ban,
				"item_code": item,
				"uom": "_KG Cái",
				"customer": self.khach,
				"price_list_rate": 101000,
				"valid_from": add_days(self.d, -30),
			}
		).insert(ignore_permissions=True)
		self.assertEqual(self.so([self.row(item, 101000)]).items[0].khac_bang_gia, 0)


class TestKiemGiaQuotation(KiemChungTuCase):
	def quotation(self, rows, **fields):
		return frappe.get_doc(
			{
				"doctype": "Quotation",
				"company": self.company,
				"quotation_to": "Customer",
				"party_name": self.khach,
				"transaction_date": self.d,
				"selling_price_list": self.ban,
				"currency": self.currency,
				"ignore_pricing_rule": 1,
				"items": rows,
				**fields,
			}
		).insert(ignore_permissions=True)

	def test_quotation_rows_are_checked(self):
		item = self.item(123457)
		d = self.quotation([self.row(item, 125000)]).items[0]
		self.assertEqual((d.trang_thai_gia, d.gia_de_xuat), (CAO_HON, 124691.57))

	def test_a_lead_has_no_coefficient(self):
		lead = frappe.get_doc({"doctype": "Lead", "first_name": f"_KG {self.sfx}"}).insert(
			ignore_permissions=True
		)
		d = self.quotation([self.row(self.item(), 1)], quotation_to="Lead", party_name=lead.name).items[0]
		self.assertFalse(d.trang_thai_gia)


class TestDoiNccSauSubmit(KiemChungTuCase):
	"""SO đã Submit vẫn đổi được NCC dự kiến: dòng kiểm lại theo NCC mới, lệch thì cần lý do;
	giá bán đã chốt với khách không đổi nên không bắt khách chấp thuận lại."""

	def setUp(self):
		super().setUp()
		self.item_a = self.item(123457, gia_ban=124691.57)
		self.ncc2 = self.supplier()
		self.gia_hd(self.item_a, 200000, ncc=self.ncc2)
		self.so_a = self.so([self.row(self.item_a, 124691.57)])
		self.so_a.submit()

	def doi_ncc(self, ncc, **fields):
		so = frappe.get_doc("Sales Order", self.so_a.name)
		so.items[0].ncc_du_kien = ncc
		so.update(fields)
		so.save()
		return so.items[0]

	def test_the_row_is_checked_against_the_new_supplier(self):
		d = self.doi_ncc(self.ncc2, ly_do_lech_gia="NCC cũ hết hàng")

		self.assertEqual((d.gia_mua, d.gia_de_xuat, d.trang_thai_gia), (200000, 202000, THAP_HON))
		self.assertEqual(frappe.db.get_value("Sales Order Item", d.name, "gia_mua"), 200000)
		self.assertIn(self.ncc, d.ghi_chu_gia)

	def test_a_mismatch_still_needs_a_reason(self):
		self.assertRaisesRegex(frappe.ValidationError, "Lý do lệch giá", self.doi_ncc, self.ncc2)

	def test_the_customer_is_not_asked_to_approve_again(self):
		d = self.doi_ncc(self.ncc2, ly_do_lech_gia="NCC cũ hết hàng")

		self.assertEqual((d.gia_bang_gia, d.khac_bang_gia, d.cho_chap_thuan), (124691.57, 0, 0))

	def test_the_form_previews_only_the_changed_row(self):
		dang_sua = self.so_a.as_dict()
		dang_sua["items"][0]["ncc_du_kien"] = self.ncc2
		kq = tinh_lai(frappe.as_json(dang_sua))[self.so_a.items[0].name]
		self.assertEqual((kq["gia_mua"], kq["trang_thai_gia"], kq["khac_bang_gia"]), (200000, THAP_HON, 0))

		# Đổi lại NCC cũ: về đúng kết quả đã lưu.
		dang_sua["items"][0]["ncc_du_kien"] = self.ncc
		kq = tinh_lai(frappe.as_json(dang_sua))[self.so_a.items[0].name]
		self.assertEqual((kq["gia_mua"], kq["trang_thai_gia"]), (123457, KHOP))


class TestNguoiDungCong(KiemChungTuCase):
	def nguoi_cong(self):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": f"_kg_portal_{self.sfx}@example.com",
				"first_name": "Cổng",
				"user_type": "Website User",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.set_user, "Administrator")
		return user.name

	def test_portal_user_does_not_see_the_price_warning(self):
		item = self.item(123457)
		user = self.nguoi_cong()
		frappe.clear_messages()
		frappe.set_user(user)
		d = self.so([self.row(item, 125000)]).items[0]
		frappe.set_user("Administrator")

		self.assertEqual(d.trang_thai_gia, CAO_HON)
		self.assertNotIn("Kiểm giá bán", self.canh_bao())

	def test_portal_user_cannot_recheck_prices_from_the_form(self):
		so = self.so([self.row(self.item(123457), 125000)])
		frappe.set_user(self.nguoi_cong())

		self.assertRaises(frappe.PermissionError, tinh_lai, so.as_json())
