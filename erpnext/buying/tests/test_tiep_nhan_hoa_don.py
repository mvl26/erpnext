# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Hợp đồng khung, Phiếu tiếp nhận hóa đơn NCC, đối soát 4 tầng, Hóa đơn mua nháp (Đợt 4, spec
2026-10-23; test case FRD-MAP-01 mục 17).

Mỗi test chạy trong savepoint và được hoàn tác. Cài đặt đặt như production: `pr_required` = Yes,
đối soát Phiếu nhập ↔ Hóa đơn (Đợt 3) bật cho mọi NCC, không tự tạo ĐNTT.
"""

import random

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, nowdate

from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
from erpnext.buying.tests.mau_hoa_don_xml import MST_MIYANO, xml_hoa_don
from erpnext.buying.tiep_nhan_hoa_don.anh_xa import doi_trang_thai
from erpnext.buying.tiep_nhan_hoa_don.doi_soat import duyet_canh_bao
from erpnext.buying.tiep_nhan_hoa_don.tao_hoa_don import tao_hoa_don_mua
from erpnext.controllers.accounts_controller import get_taxes_and_charges
from erpnext.selling.kiem_gia.gia_goc import tim_gia_mua

TEN_HDK = "Ống thông tiểu Foley 2 nhánh cỡ 16Fr"
TEN_HD = "Sonde Foley 2 way size 16"
GIA = 12500


class TiepNhanCase(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("tiep_nhan_hd")
		self.addCleanup(frappe.db.rollback, save_point="tiep_nhan_hd")
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(setattr, frappe.flags, "mute_emails", frappe.flags.mute_emails)
		frappe.flags.mute_emails = True
		for dt in ("Buying Settings", "Accounts Settings", "Supplier Invoice Intake Settings"):
			self.addCleanup(frappe.clear_document_cache, dt, dt)

		self.company = frappe.db.get_value("Company", {}, "name")
		self.abbr = frappe.get_cached_value("Company", self.company, "abbr")
		self.kho = frappe.db.get_value("Warehouse", {"company": self.company, "is_group": 0}, "name")
		if not frappe.get_cached_value("Company", self.company, "round_off_account"):
			frappe.db.set_value(
				"Company",
				self.company,
				{
					"round_off_account": frappe.db.get_value(
						"Account", {"company": self.company, "is_group": 0, "root_type": "Expense"}, "name"
					),
					"round_off_cost_center": frappe.get_cached_value("Company", self.company, "cost_center"),
				},
			)
			frappe.clear_document_cache("Company", self.company)
		frappe.db.set_single_value(
			"Buying Settings",
			{
				"maintain_same_rate": 1,
				"maintain_same_rate_action": "Warn",
				"pr_required": "Yes",
				"bill_for_rejected_quantity_in_purchase_invoice": 0,
				"blanket_order_allowance": 0,
				"bat_doi_soat_pr_pi": 1,
				"pham_vi_doi_soat": "Mọi nhà cung cấp",
				"tao_dntt_khi_nop_hoa_don": 0,
				"vai_tro_ban_dieu_hanh": None,
			},
		)
		frappe.db.set_single_value("Accounts Settings", {"round_row_wise_tax": 1})
		frappe.db.set_single_value(
			"Supplier Invoice Intake Settings",
			{
				"bat_tiep_nhan": 1,
				"mst_nguoi_mua": MST_MIYANO,
				"vai_tro_duyet_lech_gia": None,
				"vai_tro_duyet_anh_xa": None,
				"nguong_canh_bao_han_muc": 90,
			},
		)
		for dt in ("Buying Settings", "Accounts Settings", "Supplier Invoice Intake Settings"):
			frappe.clear_document_cache(dt, dt)

		self.mst = "0" + "".join(random.choices("0123456789", k=9))
		self.ncc = (
			frappe.get_doc(
				{
					"doctype": "Supplier",
					"supplier_name": f"_TN NCC {frappe.generate_hash(length=6)}",
					"supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"),
					"tax_id": self.mst,
					"ma_viet_tat": "ABC",
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
		self.bang_gia = (
			frappe.get_doc(
				{
					"doctype": "Price List",
					"price_list_name": f"_TN Mua {frappe.generate_hash(length=6)}",
					"buying": 1,
					"currency": frappe.get_cached_value("Company", self.company, "default_currency"),
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
		self.uom = frappe.db.get_value("UOM", {"name": "Cái"}) or frappe.db.get_value("UOM", {}, "name")

	# --- Dữ liệu ---

	def item(self, ten=TEN_HDK, ma_ncc=None):
		doc = frappe.new_doc("Item")
		doc.item_code = f"_TN-{frappe.generate_hash(length=8)}"
		doc.item_name = ten
		doc.item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
		doc.stock_uom = self.uom
		doc.is_stock_item = 1
		if ma_ncc:
			doc.append("supplier_items", {"supplier": self.ncc, "supplier_part_no": ma_ncc})
		return doc.insert(ignore_permissions=True).name

	def hdk(self, dong, so="2601", nop=True):
		"""`dong`: [(item, qty, rate)] hoặc thêm dict trường riêng của dòng."""
		doc = frappe.get_doc(
			{
				"doctype": "Blanket Order",
				"blanket_order_type": "Purchasing",
				"supplier": self.ncc,
				"company": self.company,
				"order_no": so,
				"from_date": add_days(nowdate(), -30),
				"to_date": add_days(nowdate(), 300),
				"bang_gia_mua": self.bang_gia,
				"items": [
					{
						"item_code": d[0],
						"qty": d[1],
						"rate": d[2],
						"ten_hdk": TEN_HDK,
						"quy_cach": "16Fr",
						"hang_sx": "Hãng A",
						"nuoc_sx": "Malaysia",
						"so_luu_hanh": "SLH-01",
						"thue_suat": "10%",
						**(d[3] if len(d) > 3 else {}),
					}
					for d in dong
				],
			}
		).insert(ignore_permissions=True)
		if nop:
			doc.submit()
		return doc

	def po(self, dong, ngay=None):
		doc = frappe.get_doc(
			{
				"doctype": "Purchase Order",
				"supplier": self.ncc,
				"company": self.company,
				"transaction_date": ngay or nowdate(),
				"schedule_date": add_days(nowdate(), 7),
				"items": [
					{
						"item_code": i,
						"qty": q,
						"rate": r,
						"warehouse": self.kho,
						"schedule_date": add_days(nowdate(), 7),
					}
					for i, q, r in dong
				],
				"taxes_and_charges": f"GTGT mua vào 10% - {self.abbr}",
				"taxes": get_taxes_and_charges(
					"Purchase Taxes and Charges Template", f"GTGT mua vào 10% - {self.abbr}"
				),
			}
		).insert(ignore_permissions=True)
		doc.submit()
		return doc

	def pr(self, po, qty=None):
		doc = make_purchase_receipt(po.name)
		for d in doc.items:
			if qty is not None:
				d.qty = d.received_qty = qty
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc

	def phieu(self, dong, **kw):
		kw.setdefault("mst_ban", self.mst)
		tep = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"hd-{frappe.generate_hash(length=6)}.xml",
				"content": xml_hoa_don(dong, so=kw.pop("so", frappe.generate_hash(length=8)), **kw),
				"is_private": 1,
			}
		).insert(ignore_permissions=True)
		frappe.clear_messages()
		return frappe.get_doc(
			{"doctype": "Supplier Invoice Intake", "company": self.company, "tep_hoa_don": tep.file_url}
		).insert(ignore_permissions=True)

	def user(self, *roles):
		email = f"_tn_{frappe.generate_hash(length=6)}@example.com"
		doc = frappe.get_doc({"doctype": "User", "email": email, "first_name": "TN", "send_welcome_email": 0})
		for r in roles:
			doc.append("roles", {"role": r})
		return doc.insert(ignore_permissions=True).name

	def du_bo(self, qty=500, rate=GIA, ma_ncc=None, han_muc=1000):
		"""Mặt hàng có HĐK, Đơn mua, Phiếu nhập đủ — luồng thường gặp."""
		item = self.item(ma_ncc=ma_ncc)
		hdk = self.hdk([(item, han_muc, rate)])
		po = self.po([(item, qty, rate)])
		pr = self.pr(po)
		return item, hdk, po, pr


class TestHopDongKhung(TiepNhanCase):
	def test_nop_ghi_gia_hd_nguyen_tac_huy_thi_xoa(self):
		item = self.item()
		hdk = self.hdk([(item, 100, GIA)])
		gia = frappe.get_all(
			"Item Price",
			filters={"item_code": item, "price_list": self.bang_gia, "supplier": self.ncc},
			fields=["price_list_rate", "hop_dong_khung", "valid_from", "valid_upto"],
		)
		self.assertEqual(len(gia), 1)
		self.assertEqual((flt(gia[0].price_list_rate), gia[0].hop_dong_khung), (GIA, hdk.name))
		# Kiểm giá bán Đợt 1 đọc đúng giá này là giá HĐ nguyên tắc (D4-2).
		kq = tim_gia_mua(item, self.ncc, nowdate(), self.company)
		self.assertEqual((flt(kq.gia_kho), kq.nguon), (GIA, "HĐ nguyên tắc"))

		hdk.cancel()
		self.assertFalse(frappe.db.exists("Item Price", {"hop_dong_khung": hdk.name}))

	def test_ma_dong_tu_sinh_khong_trung(self):
		item = self.item()
		nhom = frappe.get_cached_value("Item", item, "item_group")
		frappe.db.set_value("Item Group", nhom, "ma_viet_tat", "FOL")
		hdk = self.hdk([(item, 100, GIA)], so="HĐ 26/01")
		self.assertEqual(hdk.items[0].ma_dong_hdk, "ABC-HD2601-FOL-001")
		self.assertRaisesRegex(
			frappe.ValidationError,
			"Mã dòng hợp đồng đã dùng",
			self.hdk,
			[(self.item(), 10, GIA, {"ma_dong_hdk": "ABC-HD2601-FOL-001"})],
			nop=False,
		)

	def test_thieu_thong_tin_dong_khong_nop_duoc(self):
		doc = self.hdk([(self.item(), 100, GIA, {"so_luu_hanh": "", "thue_suat": ""})], nop=False)
		self.assertRaisesRegex(frappe.ValidationError, "Số lưu hành", doc.submit)

	def test_po_tu_gan_hdk_canh_bao_va_chan_vuot_han_muc(self):
		item = self.item()
		hdk = self.hdk([(item, 100, GIA)])
		po = self.po([(item, 95, GIA)])
		self.assertEqual((po.items[0].blanket_order, po.items[0].against_blanket_order), (hdk.name, 1))
		self.assertIn("hạn mức hợp đồng khung", " ".join(str(m) for m in frappe.get_message_log()))
		self.assertEqual(
			flt(frappe.db.get_value("Blanket Order Item", {"parent": hdk.name}, "ordered_qty")), 95
		)
		self.assertRaises(frappe.ValidationError, self.po, [(item, 10, GIA)])


class TestTiepNhanHoaDon(TiepNhanCase):
	def test_tc12_tang3_ten_khac_hop_dong_tao_hoa_don_nop_va_huy(self):
		item, hdk, po, pr = self.du_bo()
		p = self.phieu([("", TEN_HD, "Cái", 500, GIA, "10%")])
		r = p.items[0]
		self.assertEqual((r.item_code, r.cach_khop, r.trang_thai_dong), (item, "Tầng 3 - Đơn mua", "Đã khớp"))
		self.assertGreaterEqual(flt(r.diem_khop), 0.75)
		self.assertEqual(
			(r.po_detail, r.blanket_order, r.ma_dong_hdk),
			(po.items[0].name, hdk.name, hdk.items[0].ma_dong_hdk),
		)
		self.assertEqual((p.trang_thai, p.supplier, flt(p.ty_le_khop)), ("Đã đối soát", self.ncc, 100))

		pi = frappe.get_doc("Purchase Invoice", tao_hoa_don_mua(p.name))
		self.assertEqual(pi.docstatus, 0, "BR-09: chỉ tạo nháp")
		d = pi.items[0]
		self.assertEqual((d.purchase_receipt, d.pr_detail, flt(d.qty)), (pr.name, pr.items[0].name, 500))
		self.assertEqual(
			(d.ten_tren_hoa_don, d.hop_dong_khung, pi.phieu_tiep_nhan), (TEN_HD, hdk.name, p.name)
		)
		self.assertEqual(pi.trang_thai_doi_soat_pr, "Khớp", "Đợt 3 đối soát hóa đơn này như hóa đơn nhập tay")
		self.assertTrue(
			frappe.db.exists("File", {"attached_to_doctype": "Purchase Invoice", "attached_to_name": pi.name})
		)
		self.assertEqual(
			frappe.db.get_value("Supplier Invoice Intake", p.name, "trang_thai"), "Đã tạo nháp hóa đơn mua"
		)
		ax = frappe.get_all(
			"Supplier Item Alias", filters={"supplier": self.ncc}, fields=["item_code", "trang_thai", "nguon"]
		)
		self.assertEqual(ax, [{"item_code": item, "trang_thai": "Chờ duyệt", "nguon": "Khớp theo Đơn mua"}])

		pi.submit()
		self.assertEqual(frappe.db.get_value("Supplier Invoice Intake", p.name, "trang_thai"), "Đã ghi sổ")
		self.assertEqual(
			flt(frappe.db.get_value("Blanket Order Item", {"parent": hdk.name}, "da_lap_hoa_don")), 500
		)
		pi.cancel()
		self.assertEqual(
			frappe.db.get_value("Supplier Invoice Intake", p.name, ["trang_thai", "purchase_invoice"]),
			("Đã đối soát", None),
		)
		self.assertEqual(
			flt(frappe.db.get_value("Blanket Order Item", {"parent": hdk.name}, "da_lap_hoa_don")), 0
		)

	def test_tang1_ma_hang_ncc(self):
		item, *_ = self.du_bo(ma_ncc="ABC-FL216")
		p = self.phieu([("ABC-FL216", "Tên NCC đặt khác hẳn 16", "Cái", 500, GIA, "10%")])
		self.assertEqual((p.items[0].item_code, p.items[0].cach_khop), (item, "Tầng 1 - Mã"))
		self.assertEqual(p.trang_thai, "Đã đối soát")

	def test_tang2_chi_dung_anh_xa_dang_dung(self):
		item, *_ = self.du_bo()
		ten = "Ong sonde tieu loai dac biet 16"
		ax = frappe.get_doc(
			{
				"doctype": "Supplier Item Alias",
				"supplier": self.ncc,
				"ten_tren_hoa_don": ten,
				"item_code": item,
			}
		).insert(ignore_permissions=True)
		p = self.phieu([("", ten, "Cái", 500, GIA + 1, "10%")])  # khác giá Đơn mua: tầng 3 không khớp
		self.assertEqual(p.items[0].trang_thai_dong, "Chưa khớp", "ánh xạ Chờ duyệt chưa được dùng")
		doi_trang_thai(ax.name, "Đang dùng")
		p.save()
		self.assertEqual((p.items[0].item_code, p.items[0].cach_khop), (item, "Tầng 2 - Ánh xạ tên"))

	def test_tc13_khac_quy_cach_khong_khop_chon_tay(self):
		item = self.item(ten="Gạc phẫu thuật 10cm x 10cm")
		self.hdk([(item, 1000, 5000, {"ten_hdk": "Gạc phẫu thuật 10cm x 10cm", "quy_cach": "10cm"})])
		po = self.po([(item, 100, 5000)])
		self.pr(po)
		p = self.phieu([("", "Gạc phẫu thuật 7,5cm x 7,5cm", "Cái", 100, 5000, "10%")])
		self.assertEqual((p.items[0].trang_thai_dong, p.trang_thai), ("Chưa khớp", "Chờ xử lý thủ công"))

		p.items[0].item_code, p.items[0].chon_tay = item, 1
		p.save()
		self.assertEqual(
			(p.items[0].cach_khop, p.items[0].trang_thai_dong, p.trang_thai),
			("Chọn tay", "Đã khớp", "Đã đối soát"),
		)

	def test_tc10_sai_mst_nguoi_mua_tu_choi(self):
		self.du_bo()
		p = self.phieu([("", TEN_HD, "Cái", 500, GIA, "10%")], mst_mua="0100000000")
		self.assertEqual(p.trang_thai, "Từ chối")
		self.assertIn("MST người mua", p.ly_do_tu_choi)

	def test_tc11_hoa_don_da_tiep_nhan_tu_choi(self):
		self.du_bo()
		self.phieu([("", TEN_HD, "Cái", 500, GIA, "10%")], so="0000777")
		lan2 = self.phieu([("", TEN_HD, "Cái", 500, GIA, "10%")], so="0000777")
		self.assertEqual(lan2.trang_thai, "Từ chối")
		self.assertIn("đã được tiếp nhận", lan2.ly_do_tu_choi)

	def test_tc14_lech_gia_hdk_chan_den_khi_duoc_duyet(self):
		item = self.item(ma_ncc="ABC-FL216")
		self.hdk([(item, 1000, GIA)])
		po = self.po([(item, 100, GIA + 500)])  # PO đặt giá khác hợp đồng; hóa đơn theo PO
		self.pr(po)
		p = self.phieu([("ABC-FL216", TEN_HD, "Cái", 100, GIA + 500, "10%")])
		self.assertTrue(p.items[0].canh_bao_chan)
		self.assertIn("khác giá hợp đồng khung", p.items[0].canh_bao)
		self.assertEqual(p.trang_thai, "Chờ xử lý thủ công")
		self.assertRaises(frappe.ValidationError, tao_hoa_don_mua, p.name)

		frappe.set_user(self.user("Purchase User"))
		self.assertRaises(frappe.PermissionError, duyet_canh_bao, p.name, "thử")
		frappe.set_user(self.user("System Manager"))
		self.assertEqual(duyet_canh_bao(p.name, "Ban Điều hành đồng ý giá mới"), "Đã đối soát")

	def test_vuot_han_muc_hdk_chan(self):
		item = self.item(ma_ncc="ABC-FL216")
		hdk = self.hdk([(item, 1000, GIA)])
		frappe.db.set_value("Blanket Order Item", {"parent": hdk.name}, "da_lap_hoa_don", 950)
		po = self.po([(item, 40, GIA)])
		self.pr(po)
		p = self.phieu([("ABC-FL216", TEN_HD, "Cái", 40, GIA, "10%")])
		self.assertFalse(p.items[0].canh_bao_chan)
		frappe.db.set_value("Blanket Order Item", {"parent": hdk.name}, "da_lap_hoa_don", 980)
		p.save()
		self.assertTrue(p.items[0].canh_bao_chan)
		self.assertIn("Vượt hạn mức hợp đồng khung", p.items[0].canh_bao)

	def test_so_hoc_lech_can_kiem(self):
		self.du_bo()
		p = self.phieu([("", TEN_HD, "Cái", 500, GIA, "10%")], tong=(6250000, 625000, 6875001))
		self.assertTrue(p.lech_so_hoc)
		self.assertEqual(p.trang_thai, "Chờ xử lý thủ công")
		p.da_kiem_so_hoc = 1
		p.save()
		self.assertEqual(p.trang_thai, "Đã đối soát")

	def test_chua_co_phieu_nhap_chua_tao_hoa_don(self):
		item = self.item()
		self.hdk([(item, 1000, GIA)])
		self.po([(item, 500, GIA)])
		p = self.phieu([("", TEN_HD, "Cái", 500, GIA, "10%")])
		self.assertEqual(p.trang_thai, "Đã đối soát")
		self.assertRaisesRegex(frappe.ValidationError, "chưa có Phiếu nhập", tao_hoa_don_mua, p.name)

	def test_hoa_don_tung_phan_va_xoa_hoa_don_nhap_mo_lai_phieu(self):
		self.du_bo(qty=500)
		p = self.phieu([("", TEN_HD, "Cái", 300, GIA, "10%")])
		pi = frappe.get_doc("Purchase Invoice", tao_hoa_don_mua(p.name))
		self.assertEqual((pi.hoa_don_tung_phan, pi.trang_thai_doi_soat_pr), (1, "Khớp"))
		frappe.delete_doc("Purchase Invoice", pi.name)
		self.assertEqual(
			frappe.db.get_value("Supplier Invoice Intake", p.name, ["trang_thai", "purchase_invoice"]),
			("Đã đối soát", None),
		)

	def test_br10_nhieu_dong_don_mua_khong_tu_chon(self):
		a, b = self.item(), self.item()
		self.hdk([(a, 1000, GIA), (b, 1000, GIA)])
		po = self.po([(a, 500, GIA), (b, 500, GIA)])
		self.pr(po)
		p = self.phieu([("", TEN_HD, "Cái", 500, GIA, "10%")])
		self.assertEqual(p.items[0].trang_thai_dong, "Chưa khớp")
		self.assertIn("Nhiều dòng Đơn mua", p.items[0].canh_bao)


class TestBangAnhXa(TiepNhanCase):
	def test_chi_nguoi_duyet_doi_trang_thai(self):
		item = self.item()
		frappe.set_user(self.user("Purchase User"))
		self.assertRaises(
			frappe.PermissionError,
			frappe.get_doc(
				{
					"doctype": "Supplier Item Alias",
					"supplier": self.ncc,
					"ten_tren_hoa_don": "Tên A",
					"item_code": item,
					"trang_thai": "Đang dùng",
				}
			).insert,
		)
		ax = frappe.get_doc(
			{
				"doctype": "Supplier Item Alias",
				"supplier": self.ncc,
				"ten_tren_hoa_don": "Tên A",
				"item_code": item,
			}
		).insert()
		self.assertRaises(frappe.PermissionError, doi_trang_thai, ax.name, "Đang dùng")
		frappe.set_user(self.user("Purchase Manager"))
		self.assertEqual(doi_trang_thai(ax.name, "Đang dùng"), 1)

	def test_khong_trung_ten_chuan_hoa_trong_mot_ncc(self):
		item = self.item()
		frappe.get_doc(
			{
				"doctype": "Supplier Item Alias",
				"supplier": self.ncc,
				"ten_tren_hoa_don": "Găng khám size M",
				"item_code": item,
			}
		).insert(ignore_permissions=True)
		self.assertRaises(
			frappe.ValidationError,
			frappe.get_doc(
				{
					"doctype": "Supplier Item Alias",
					"supplier": self.ncc,
					"ten_tren_hoa_don": "GĂNG TAY KHÁM cỡ M",
					"item_code": item,
				}
			).insert,
			ignore_permissions=True,
		)
