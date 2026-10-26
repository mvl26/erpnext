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

from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import make_debit_note
from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
from erpnext.buying.tests.mau_hoa_don_xml import MST_MIYANO, xml_hoa_don
from erpnext.buying.tiep_nhan_hoa_don.anh_xa import doi_trang_thai
from erpnext.buying.tiep_nhan_hoa_don.cau_hinh import TRUONG_BAT_BUOC_MAC_DINH, TRUONG_DONG_BAT_BUOC_MAC_DINH
from erpnext.buying.tiep_nhan_hoa_don.doi_soat import duyet_canh_bao, mo_lai, tu_choi, van_tay
from erpnext.buying.tiep_nhan_hoa_don.hoa_don_lien_quan import bo_hoa_don_bi_thay_the
from erpnext.buying.tiep_nhan_hoa_don.tao_hoa_don import tao_hoa_don_mua
from erpnext.controllers.accounts_controller import get_taxes_and_charges
from erpnext.selling.kiem_gia.gia_goc import tim_gia_mua

PHIEU = "Supplier Invoice Intake"
TEN_HDK = "Ống thông tiểu Foley 2 nhánh cỡ 16Fr"
TEN_HD = "Sonde Foley 2 way size 16"
GIA = 12500
# Thông tin các bên bắt buộc khi Nộp (hợp đồng nguyên tắc mẫu); MST Bên B lấy từ thẻ NCC.
CAC_BEN = {
	"order_date": nowdate(),
	"dai_dien_ben_a": "Đại diện A",
	"chuc_vu_ben_a": "Giám đốc vận hành",
	"mst_ben_a": MST_MIYANO,
	"dia_chi_ben_a": "Hà Nội",
	"tai_khoan_ben_a": "0001",
	"ngan_hang_ben_a": "Ngân hàng A",
	"dai_dien_ben_b": "Đại diện B",
	"chuc_vu_ben_b": "Giám đốc",
	"dien_thoai_ben_b": "0240000000",
	"dia_chi_ben_b": "Hà Nội",
	"tai_khoan_ben_b": "0002",
	"ngan_hang_ben_b": "Ngân hàng B",
	"terms": "<p>Điều khoản thử của hợp đồng</p>",
}


def _tt(phieu):
	return frappe.db.get_value(PHIEU, phieu, "trang_thai")


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
				"truong_bat_buoc_hdk": "\n".join(TRUONG_BAT_BUOC_MAC_DINH),
				"truong_bat_buoc_dong_hdk": "\n".join(TRUONG_DONG_BAT_BUOC_MAC_DINH),
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

	def hdk(self, dong, so="2601", nop=True, quyen=False, **dau):
		"""`dong`: [(item, qty, rate)] hoặc thêm dict trường riêng của dòng; `dau`: trường đầu phiếu;
		`quyen`: kiểm quyền của người dùng hiện tại khi lưu (mặc định bỏ qua)."""
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
				**CAC_BEN,
				**dau,
				"items": [
					{
						"item_code": d[0],
						"qty": d[1],
						"rate": d[2],
						"ma_hang_ncc": f"NCC-{d[0][-6:]}",
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
		).insert(ignore_permissions=not quyen)
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

	def test_thieu_thong_tin_hop_dong_khong_nop_duoc(self):
		# Bên B: NCC của test chưa có hợp đồng nào nên không được tự điền (Bên A thì được điền theo hợp
		# đồng gần nhất của công ty trên site).
		doc = self.hdk([(self.item(), 100, GIA)], nop=False, dai_dien_ben_b="", tai_khoan_ben_b="")
		self.assertRaisesRegex(frappe.ValidationError, "Đại diện Bên B.*Số tài khoản Bên B", doc.submit)

	def test_truong_bat_buoc_theo_cai_dat(self):
		"""Mỗi NCC một kiểu hợp đồng: trường bắt buộc khi Nộp chọn ở Cài đặt, không cố định (D4-13)."""
		cai_dat = "Supplier Invoice Intake Settings"
		frappe.db.set_single_value(cai_dat, {"truong_bat_buoc_hdk": "", "truong_bat_buoc_dong_hdk": ""})
		trong = {f: "" for f in CAC_BEN if f != "order_date"}
		dong = {f: "" for f in ("ten_hdk", "quy_cach", "hang_sx", "nuoc_sx", "so_luu_hanh", "thue_suat")}
		self.hdk([(self.item(), 100, GIA, dong)], **trong)  # chỉ còn trường hệ thống cần: Nộp được

		frappe.db.set_single_value(cai_dat, "truong_bat_buoc_hdk", "tep_hop_dong")
		doc = self.hdk([(self.item(), 100, GIA)], so="2602", nop=False)
		self.assertRaisesRegex(frappe.ValidationError, "Tệp hợp đồng đã ký", doc.submit)

		s = frappe.get_doc(cai_dat)
		s.truong_bat_buoc_dong_hdk = "quy_cach\nkhong_co_truong_nay"
		self.assertRaisesRegex(frappe.ValidationError, "khong_co_truong_nay", s.save)

	def test_tu_dien_thong_tin_cac_ben_theo_hop_dong_gan_nhat(self):
		# Từ ngày mới nhất để là "hợp đồng gần nhất" của công ty dù site đã có hợp đồng khác.
		self.hdk([(self.item(), 100, GIA)], from_date=add_days(nowdate(), 1))
		trong = {f: "" for f in CAC_BEN if f.endswith(("_ben_a", "_ben_b"))}
		doc = self.hdk([(self.item(), 100, GIA)], so="2602", nop=False, **trong)
		self.assertEqual(
			(doc.dai_dien_ben_a, doc.tai_khoan_ben_b, doc.mst_ben_b),
			(CAC_BEN["dai_dien_ben_a"], CAC_BEN["tai_khoan_ben_b"], self.mst),
		)

	def test_gia_gom_vat_quy_ve_chua_vat(self):
		item = self.item(ten="Ascaris IgG Elisa Kit")
		dong = {"thue_suat": "5%", "ten_hdk": "Ascaris IgG Elisa Kit", "ma_hang_ncc": "5002"}
		hdk = self.hdk([(item, 0, 3949000, dong)], gia_gom_vat=1, khong_cam_ket_so_luong=1)
		chua_vat = 3760952  # 3.949.000 / 1,05 làm tròn đến đồng
		gia = frappe.db.get_value("Item Price", {"hop_dong_khung": hdk.name}, ["price_list_rate", "note"])
		self.assertEqual(flt(gia[0]), chua_vat)
		self.assertIn("đã gồm VAT 5%", gia[1])
		self.assertEqual(flt(tim_gia_mua(item, self.ncc, nowdate(), self.company).gia_kho), chua_vat)
		po = self.po([(item, 7, chua_vat)])
		self.assertEqual(flt(po.items[0].blanket_order_rate), chua_vat)
		# ERPNext trên form điền Đơn giá đơn khung = giá hợp đồng (đã gồm VAT); khi Lưu quy về chưa VAT.
		doc = frappe.copy_doc(po)
		doc.items[0].blanket_order_rate = 3949000
		doc.insert(ignore_permissions=True)
		self.assertEqual(flt(doc.items[0].blanket_order_rate), chua_vat)

		# Hóa đơn ghi đơn giá chưa VAT chẵn đồng: không cảnh báo, và Hóa đơn mua tạo ra khớp Phiếu nhập
		# (Đợt 3 so 0 đồng) vì Đơn mua / Phiếu nhập cũng mang giá chẵn đồng.
		self.pr(po)
		p = self.phieu([("5002", "Ascaris IgG Elisa Kit", "Cái", 7, 3760952, "5%")])
		self.assertEqual((p.items[0].cach_khop, p.items[0].canh_bao_chan), ("Tầng 1 - Mã", 0))
		pi = frappe.get_doc("Purchase Invoice", tao_hoa_don_mua(p.name))
		self.assertEqual(pi.trang_thai_doi_soat_pr, "Khớp")
		# Hóa đơn theo giá 10 - 30 hộp (chỉ ghi chú trong hợp đồng): lệch giá, chặn.
		p = self.phieu([("5002", "Ascaris IgG Elisa Kit", "Cái", 7, 3630952, "5%")])
		self.assertTrue(p.items[0].canh_bao_chan)
		self.assertIn("đã gồm VAT 5%", p.items[0].canh_bao)

		# NCC làm tròn lên 1 đồng: phiếu không cảnh báo, đối soát Đợt 3 cho dung sai 1 đồng (D4-12).
		po2 = self.po([(item, 7, chua_vat)])
		self.pr(po2)
		p = self.phieu(
			[("5002", "Ascaris IgG Elisa Kit", "Cái", 7, chua_vat + 1, "5%")], ghi_chu=f"PO {po2.name}"
		)
		self.assertEqual((p.purchase_order, p.items[0].canh_bao_chan), (po2.name, 0))
		pi = frappe.get_doc("Purchase Invoice", tao_hoa_don_mua(p.name))
		self.assertEqual((flt(pi.items[0].rate), pi.trang_thai_doi_soat_pr), (chua_vat + 1, "Khớp"))

	def test_gia_gom_vat_hang_gia_thap_nop_duoc_khi_hoa_don_cao_hon_1_dong(self):
		"""ERPNext chỉ cho vượt thành tiền dòng Đơn mua 0,01%: 10 x 5.001 so với 10 x 5.000 là 0,02%.
		Dòng thuộc hợp đồng giá gồm VAT, trong dung sai, Khớp thì phải Nộp được (D4-12)."""
		item = self.item(ten="RF-Absorbent 20ml")
		dong = {"thue_suat": "5%", "ten_hdk": "RF-Absorbent 20ml", "ma_hang_ncc": "Z200"}
		self.hdk([(item, 0, 5250, dong)], gia_gom_vat=1, khong_cam_ket_so_luong=1)  # 5.000 chưa VAT
		po = self.po([(item, 10, 5000)])
		self.pr(po)
		p = self.phieu([("Z200", "RF-Absorbent 20ml", "Cái", 10, 5001, "5%")], ghi_chu=f"PO {po.name}")
		self.assertEqual(p.trang_thai, "Đã đối soát")
		pi = frappe.get_doc("Purchase Invoice", tao_hoa_don_mua(p.name))
		self.assertEqual(pi.trang_thai_doi_soat_pr, "Khớp")
		pi.submit()
		self.assertEqual(pi.docstatus, 1)

		# Lệch 2 đồng / đơn vị: ngoài dung sai, đối soát Đợt 3 báo Lệch.
		po = self.po([(item, 10, 5000)])
		self.pr(po)
		p = self.phieu([("Z200", "RF-Absorbent 20ml", "Cái", 10, 5002, "5%")], ghi_chu=f"PO {po.name}")
		self.assertTrue(p.items[0].canh_bao_chan, "phiếu tiếp nhận cũng chỉ cho 1 đồng")

	def test_khong_cam_ket_so_luong(self):
		item = self.item()
		doc = self.hdk([(item, 0, GIA)], nop=False)
		self.assertRaisesRegex(frappe.ValidationError, "số lượng hợp đồng phải lớn hơn 0", doc.submit)
		self.hdk([(item, 0, GIA)], so="2602", khong_cam_ket_so_luong=1)
		frappe.clear_messages()
		po = self.po([(item, 5000, GIA)])  # không giới hạn: ERPNext không chặn, không cảnh báo
		self.assertTrue(po.items[0].blanket_order)
		self.assertNotIn("hạn mức", " ".join(str(m) for m in frappe.get_message_log()))
		self.pr(po)
		p = self.phieu([("", TEN_HD, "Cái", 5000, GIA, "10%")])
		self.assertFalse(p.items[0].canh_bao_chan)

	def test_dvt_hop_dong_phai_la_dvt_kho(self):
		khac = frappe.db.get_value("UOM", {"name": ("!=", self.uom)}, "name")
		self.assertRaisesRegex(
			frappe.ValidationError,
			"ĐVT theo hợp đồng",
			self.hdk,
			[(self.item(), 100, GIA, {"dvt_hdk": khac})],
			nop=False,
		)

	def test_tang1_ma_hang_ncc_ghi_trong_hop_dong(self):
		item = self.item()
		self.hdk([(item, 1000, GIA, {"ma_hang_ncc": "GT-5041"})])
		po = self.po([(item, 100, GIA)])
		self.pr(po)
		p = self.phieu([("GT-5041", "Tên khác hẳn", "Cái", 100, GIA, "10%")])
		self.assertEqual((p.items[0].item_code, p.items[0].cach_khop), (item, "Tầng 1 - Mã"))

	def test_phu_luc_doi_gia_va_them_hang(self):
		a, b = self.item(), self.item()
		goc = self.hdk([(a, 1000, GIA)], so="HĐ 26/01")
		pl = self.hdk(
			[(a, 1000, GIA + 1000), (b, 500, GIA)],
			so="",
			nop=False,
			hop_dong_goc=goc.name,
			from_date=add_days(nowdate(), -5),
		)
		self.assertEqual(pl.order_no, "HĐ 26/01")
		self.assertEqual(
			[d.ma_dong_hdk[-3:] for d in pl.items], ["002", "003"], "phụ lục đánh số tiếp hợp đồng gốc"
		)
		self.assertRaisesRegex(frappe.ValidationError, "Số phụ lục", pl.submit)
		pl.reload()
		pl.so_phu_luc = "01"
		pl.submit()
		po = self.po([(a, 10, GIA + 1000)])
		self.assertEqual(po.items[0].blanket_order, pl.name, "gắn phụ lục, không gắn hợp đồng gốc")
		# Người dùng tích Theo đơn khung trên form: ERPNext tự chọn hợp đồng gốc; khi Lưu chuyển sang phụ lục.
		doc = frappe.copy_doc(po)
		doc.items[0].update(
			{"against_blanket_order": 1, "blanket_order": goc.name, "blanket_order_rate": GIA}
		)
		doc.insert(ignore_permissions=True)
		self.assertEqual(
			(doc.items[0].blanket_order, flt(doc.items[0].blanket_order_rate)), (pl.name, GIA + 1000)
		)
		self.assertEqual(flt(tim_gia_mua(a, self.ncc, nowdate(), self.company).gia_kho), GIA + 1000)

		cung_ngay = self.hdk([(a, 10, GIA + 2000)], so="", nop=False, hop_dong_goc=goc.name, so_phu_luc="02")
		self.assertRaisesRegex(frappe.ValidationError, "Từ ngày sau", cung_ngay.submit)


class TestQuyenDonKhung(TiepNhanCase):
	def setUp(self):
		super().setUp()
		from erpnext.buying.tiep_nhan_hoa_don.truong_tuy_bien import phan_quyen_don_khung

		# Dựng lại quyền theo code hiện tại (site có thể còn quyền cũ); hoàn tác cùng savepoint của test.
		frappe.db.delete("Custom DocPerm", {"parent": "Blanket Order"})
		phan_quyen_don_khung()
		self.addCleanup(frappe.clear_cache, doctype="Blanket Order")

	def test_nhan_vien_nhap_giam_doc_nop(self):
		item = self.item()
		frappe.set_user(self.user("Purchase User"))
		doc = self.hdk([(item, 100, GIA)], nop=False, quyen=True)
		self.assertRaises(frappe.PermissionError, doc.submit)
		frappe.set_user(self.user("Purchase Manager"))
		self.assertRaises(frappe.PermissionError, frappe.get_doc("Blanket Order", doc.name).submit)
		frappe.set_user(self.user("Sales Manager"))
		frappe.get_doc("Blanket Order", doc.name).submit()
		self.assertEqual(frappe.db.get_value("Blanket Order", doc.name, "docstatus"), 1)

	def test_ke_toan_chi_xem(self):
		item = self.item()
		frappe.set_user(self.user("Accounts User"))
		self.assertRaises(frappe.PermissionError, self.hdk, [(item, 100, GIA)], nop=False, quyen=True)


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
		self.assertRaises(frappe.PermissionError, doi_trang_thai, ax.name, "Đang dùng")
		frappe.set_user(self.user("Sales Manager"))  # giám đốc duyệt (D4-10), chỉ cần vai trò này
		self.assertEqual(doi_trang_thai(ax.name, "Đang dùng"), 1)

	def test_sua_anh_xa_da_duyet_phai_duyet_lai(self):
		a, b = self.item(), self.item()
		ax = frappe.get_doc(
			{
				"doctype": "Supplier Item Alias",
				"supplier": self.ncc,
				"ten_tren_hoa_don": "Tên B",
				"item_code": a,
			}
		).insert(ignore_permissions=True)
		giam_doc = self.user("Sales Manager")
		nhan_vien = self.user("Purchase User")
		frappe.set_user(giam_doc)
		doi_trang_thai(ax.name, "Đang dùng")

		frappe.set_user(nhan_vien)
		ax = frappe.get_doc("Supplier Item Alias", ax.name)
		ax.ten_tren_hoa_don = "TÊN B"  # cùng tên chuẩn hóa: ánh xạ không đổi
		ax.save()
		self.assertEqual((ax.trang_thai, ax.nguoi_duyet), ("Đang dùng", giam_doc))
		ax.update({"item_code": b, "nguoi_duyet": nhan_vien})  # tự ghi người duyệt cũng bị bỏ
		ax.save()
		self.assertEqual((ax.trang_thai, ax.nguoi_duyet, ax.thoi_diem_duyet), ("Chờ duyệt", None, None))

		frappe.set_user(giam_doc)
		doi_trang_thai(ax.name, "Đang dùng")
		ax = frappe.get_doc("Supplier Item Alias", ax.name)
		ax.item_code = a  # chính người duyệt sửa: coi như duyệt lại
		ax.save()
		self.assertEqual((ax.trang_thai, ax.nguoi_duyet), ("Đang dùng", giam_doc))

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


class TestTrangThaiVaTuChoi(TiepNhanCase):
	def test_st05a_lech_pr_pi_roi_ve_da_tao_nhap(self):
		item = self.item()
		self.hdk([(item, 1000, GIA)])
		self.pr(self.po([(item, 500, GIA)]), qty=480)  # Kho nhận thiếu 20
		p = self.phieu([("", TEN_HD, "Cái", 500, GIA, "10%")])
		self.assertEqual(p.trang_thai, "Đã đối soát")

		pi = frappe.get_doc("Purchase Invoice", tao_hoa_don_mua(p.name))
		self.assertEqual(pi.trang_thai_doi_soat_pr, "Lệch")
		self.assertEqual(_tt(p.name), "Lệch PR-PI", "ST-05a")
		pi.save()
		self.assertEqual(_tt(p.name), "Lệch PR-PI")

		pi.items[0].qty = 480  # nhánh (a): sửa hóa đơn theo số Kho thực nhận
		pi.save()
		self.assertEqual(pi.trang_thai_doi_soat_pr, "Khớp")
		self.assertEqual(_tt(p.name), "Đã tạo nháp hóa đơn mua")

	def test_tu_choi_tay_xoa_hoa_don_nhap_va_mo_lai(self):
		self.du_bo()
		p = self.phieu([("", TEN_HD, "Cái", 500, GIA, "10%")])
		pi = tao_hoa_don_mua(p.name)
		self.assertRaises(frappe.ValidationError, tu_choi, p.name, " ")
		self.assertEqual(tu_choi(p.name, "NCC báo hủy hóa đơn"), "Từ chối")
		self.assertFalse(frappe.db.exists("Purchase Invoice", pi))
		p.reload()
		self.assertEqual(
			(p.tu_choi_tay, p.nguoi_tu_choi, p.ly_do_tu_choi, p.purchase_invoice),
			(1, "Administrator", "NCC báo hủy hóa đơn", None),
		)
		p.tu_choi_tay = 0  # sửa thẳng qua form / API không bỏ được Từ chối tay
		p.save()
		self.assertEqual((p.trang_thai, p.tu_choi_tay), ("Từ chối", 1))

		self.assertEqual(mo_lai(p.name), "Đã đối soát")
		p.reload()
		self.assertFalse(p.tu_choi_tay or p.ly_do_tu_choi or p.nguoi_tu_choi)
		self.assertRaises(frappe.ValidationError, mo_lai, p.name)

	def test_tu_choi_tay_khong_ap_cho_phieu_da_ghi_so(self):
		self.du_bo()
		p = self.phieu([("", TEN_HD, "Cái", 500, GIA, "10%")])
		frappe.get_doc("Purchase Invoice", tao_hoa_don_mua(p.name)).submit()
		self.assertRaisesRegex(frappe.ValidationError, "hủy hóa đơn đó trước", tu_choi, p.name, "thử")

	def test_ke_toan_chi_xem_phieu(self):
		self.du_bo()
		p = self.phieu([("", TEN_HD, "Cái", 500, GIA, "10%")])
		frappe.set_user(self.user("Accounts Manager"))
		self.assertTrue(frappe.has_permission(PHIEU, "read", doc=p.name))
		self.assertFalse(frappe.has_permission(PHIEU, "write", doc=p.name))
		self.assertFalse(frappe.has_permission(PHIEU, "create"))
		self.assertRaises(frappe.PermissionError, tu_choi, p.name, "thử")
		self.assertRaises(frappe.PermissionError, tao_hoa_don_mua, p.name)

	def test_giam_doc_chi_co_sales_manager_xem_phieu_va_duyet(self):
		item = self.item(ma_ncc="ABC-FL216")
		self.hdk([(item, 1000, GIA)])
		self.pr(self.po([(item, 100, GIA + 500)]))
		p = self.phieu([("ABC-FL216", TEN_HD, "Cái", 100, GIA + 500, "10%")])
		frappe.set_user(self.user("Sales Manager"))
		self.assertTrue(frappe.has_permission(PHIEU, "read", doc=p.name))
		self.assertFalse(frappe.has_permission(PHIEU, "write", doc=p.name))
		self.assertEqual(duyet_canh_bao(p.name, "Giám đốc đồng ý giá mới"), "Đã đối soát")

	def test_khong_gia_mao_duoc_phe_duyet_canh_bao(self):
		item = self.item(ma_ncc="ABC-FL216")
		self.hdk([(item, 1000, GIA)])
		self.pr(self.po([(item, 100, GIA + 500)]))
		p = self.phieu([("ABC-FL216", TEN_HD, "Cái", 100, GIA + 500, "10%")])
		self.assertTrue(p.items[0].canh_bao_chan)
		p.update(
			{"ly_do_duyet": "tự duyệt", "nguoi_duyet": "Administrator", "dau_van_tay_canh_bao": van_tay(p)}
		)
		p.save()
		self.assertEqual((p.trang_thai, p.nguoi_duyet), ("Chờ xử lý thủ công", None))


class TestHoaDonThayThe(TiepNhanCase):
	def thay_the(self, so_goc, so=None):
		return self.phieu(
			[("", TEN_HD, "Cái", 500, GIA, "10%")],
			so=so or frappe.generate_hash(length=8),
			lien_quan=("1", "C26TAB", so_goc, "2026-10-23"),
		)

	def test_goc_chua_co_hoa_don_mua_tu_choi_phieu_cu(self):
		self.du_bo()
		goc = self.phieu([("", TEN_HD, "Cái", 500, GIA, "10%")], so="0000101")
		tt = self.thay_the("101")  # số không có số 0 đầu vẫn nhận ra
		self.assertEqual(
			(tt.tinh_chat_hoa_don, tt.phieu_lien_quan, tt.trang_thai), ("Thay thế", goc.name, "Đã đối soát")
		)
		self.assertFalse(tt.nghi_trung, "cùng ngày, cùng tổng với hóa đơn bị thay thế: không phải trùng")
		goc.reload()
		self.assertEqual(goc.trang_thai, "Từ chối")
		self.assertIn("bị thay thế", goc.ly_do_tu_choi)
		self.assertRaises(frappe.ValidationError, tao_hoa_don_mua, goc.name)
		self.assertTrue(tao_hoa_don_mua(tt.name))

		tu_choi(tt.name, "NCC gửi nhầm hóa đơn thay thế")
		self.assertEqual(_tt(goc.name), "Đã đối soát", "hóa đơn thay thế bị Từ chối thì phiếu cũ mở lại")

	def test_goc_co_hoa_don_nhap_bo_ban_nhap(self):
		self.du_bo()
		goc = self.phieu([("", TEN_HD, "Cái", 500, GIA, "10%")], so="0000201")
		pi = tao_hoa_don_mua(goc.name)
		tt = self.thay_the("0000201")
		self.assertEqual(tt.trang_thai, "Chờ xử lý thủ công")
		self.assertIn("Bỏ hóa đơn bị thay thế", tt.canh_bao)
		self.assertEqual(bo_hoa_don_bi_thay_the(tt.name), "Đã đối soát")
		self.assertFalse(frappe.db.exists("Purchase Invoice", pi))
		self.assertEqual(_tt(goc.name), "Từ chối")

	def test_goc_da_ghi_so_phai_huy_truoc(self):
		self.du_bo()
		goc = self.phieu([("", TEN_HD, "Cái", 500, GIA, "10%")], so="0000301")
		pi = frappe.get_doc("Purchase Invoice", tao_hoa_don_mua(goc.name))
		pi.submit()
		tt = self.thay_the("0000301")
		self.assertEqual(tt.trang_thai, "Chờ xử lý thủ công")
		self.assertIn("đã ghi sổ", tt.canh_bao)
		self.assertRaises(frappe.ValidationError, bo_hoa_don_bi_thay_the, tt.name)
		pi.cancel()
		self.assertEqual((_tt(tt.name), _tt(goc.name)), ("Đã đối soát", "Từ chối"))

	def test_hoa_don_cu_chua_tiep_nhan(self):
		self.du_bo()
		tt = self.thay_the("0009999")
		self.assertEqual((tt.trang_thai, tt.phieu_lien_quan), ("Đã đối soát", None))
		self.assertIn("chưa có trên hệ thống", tt.canh_bao)


class TestHoaDonDieuChinh(TiepNhanCase):
	def dieu_chinh(self, so_goc, dong, so=None):
		return self.phieu(
			dong, so=so or frappe.generate_hash(length=8), lien_quan=("2", "C26TAB", so_goc, "2026-10-23")
		)

	def test_b2_giam_so_luong_gop_vao_mot_hoa_don_mua(self):
		item = self.item()
		self.hdk([(item, 1000, GIA)])
		self.pr(self.po([(item, 500, GIA)]), qty=480)
		goc = self.phieu([("", TEN_HD, "Cái", 500, GIA, "10%")], so="0000401")
		cu = tao_hoa_don_mua(goc.name)
		self.assertEqual(_tt(goc.name), "Lệch PR-PI")

		dc = self.dieu_chinh("0000401", [("", TEN_HD, "Cái", -20, GIA, "10%")], so="0000402")
		r = dc.items[0]
		self.assertEqual(
			(dc.trang_thai, dc.phieu_lien_quan, dc.hoa_don_mua_lien_quan), ("Đã đối soát", goc.name, cu)
		)
		self.assertEqual(
			(r.dong_goc, r.kieu_dieu_chinh, r.item_code, r.cach_khop),
			(1, "Số lượng", item, "Dòng hóa đơn gốc"),
		)
		self.assertEqual(_tt(goc.name), "Lệch PR-PI", "phiếu gốc giữ hóa đơn nháp cũ tới khi lập lại")

		lap_cu = frappe.db.get_value("Purchase Invoice", cu, "creation")
		moi = frappe.get_doc("Purchase Invoice", tao_hoa_don_mua(dc.name))
		# Bản nháp cũ bị xóa, bản mới lập lại (Frappe có thể cấp lại đúng số vừa xóa).
		self.assertNotEqual(moi.creation, lap_cu)
		self.assertEqual(frappe.db.count("Purchase Invoice", {"supplier": self.ncc, "docstatus": 0}), 1)
		self.assertEqual(
			(flt(moi.items[0].qty), moi.bill_no, moi.trang_thai_doi_soat_pr), (480, "0000401", "Khớp")
		)
		self.assertIn("0000402", moi.hoa_don_dieu_chinh)
		self.assertEqual(
			frappe.db.count(
				"File", {"attached_to_doctype": "Purchase Invoice", "attached_to_name": moi.name}
			),
			2,
		)
		goc.reload()
		self.assertEqual((flt(goc.items[0].so_luong_sau_dc), flt(goc.items[0].don_gia_sau_dc)), (480, GIA))
		for ten in (goc.name, dc.name):
			self.assertEqual(
				frappe.db.get_value(PHIEU, ten, ["trang_thai", "purchase_invoice"]),
				("Đã tạo nháp hóa đơn mua", moi.name),
			)

		moi.submit()
		self.assertEqual((_tt(goc.name), _tt(dc.name)), ("Đã ghi sổ", "Đã ghi sổ"))
		moi.cancel()
		self.assertEqual((_tt(goc.name), _tt(dc.name)), ("Đã đối soát", "Đã đối soát"))

	def test_ke_toan_xoa_ban_nhap_roi_mua_hang_lap_lai(self):
		"""Kế toán chỉ xem phiếu, nhân viên mua hàng không xóa được Hóa đơn mua: kế toán xóa bản nháp trên
		Hóa đơn mua, phiếu tự tính lại, nhân viên mua hàng bấm Lập."""
		item = self.item()
		self.hdk([(item, 1000, GIA)])
		self.pr(self.po([(item, 500, GIA)]), qty=480)
		goc = self.phieu([("", TEN_HD, "Cái", 500, GIA, "10%")], so="0000451")
		cu = tao_hoa_don_mua(goc.name)
		dc = self.dieu_chinh("0000451", [("", TEN_HD, "Cái", -20, GIA, "10%")])
		frappe.delete_doc("Purchase Invoice", cu)  # Kế toán (có quyền xóa) xóa bản nháp
		self.assertEqual(_tt(goc.name), "Đã đối soát")
		self.assertEqual(flt(frappe.get_doc(PHIEU, goc.name).items[0].so_luong_sau_dc), 480)
		frappe.set_user(self.user("Purchase User"))
		moi = frappe.get_doc("Purchase Invoice", tao_hoa_don_mua(dc.name))
		self.assertEqual((flt(moi.items[0].qty), moi.trang_thai_doi_soat_pr), (480, "Khớp"))

	def test_giam_gia_truoc_khi_lap_hoa_don(self):
		item = self.item(ma_ncc="ABC-FL216")
		self.hdk([(item, 1000, GIA)])
		self.pr(self.po([(item, 500, GIA)]))
		goc = self.phieu([("ABC-FL216", TEN_HD, "Cái", 500, GIA + 100, "10%")], so="0000501")
		self.assertEqual(goc.trang_thai, "Chờ xử lý thủ công")
		self.assertIn("khác giá hợp đồng khung", goc.items[0].canh_bao)

		dc = self.dieu_chinh("0000501", [("ABC-FL216", TEN_HD, "Cái", 500, -100, "10%")])
		self.assertEqual((dc.items[0].kieu_dieu_chinh, dc.trang_thai), ("Đơn giá", "Đã đối soát"))
		goc.reload()
		self.assertEqual(
			(goc.trang_thai, flt(goc.items[0].so_luong_sau_dc), flt(goc.items[0].don_gia_sau_dc)),
			("Đã đối soát", 500, GIA),
		)
		pi = frappe.get_doc("Purchase Invoice", tao_hoa_don_mua(goc.name))
		self.assertEqual((flt(pi.items[0].rate), pi.trang_thai_doi_soat_pr), (GIA, "Khớp"))
		self.assertEqual(_tt(dc.name), "Đã tạo nháp hóa đơn mua")

	def test_goc_da_ghi_so_ke_toan_lap_hoa_don_tra_hang(self):
		self.du_bo()
		goc = self.phieu([("", TEN_HD, "Cái", 500, GIA, "10%")], so="0000601")
		pi = frappe.get_doc("Purchase Invoice", tao_hoa_don_mua(goc.name))
		pi.submit()
		dc = self.dieu_chinh("0000601", [("", TEN_HD, "Cái", -20, GIA, "10%")], so="0000602")
		self.assertEqual(dc.trang_thai, "Chờ xử lý thủ công")
		self.assertIn("lập tay", dc.canh_bao)
		self.assertRaises(frappe.ValidationError, tao_hoa_don_mua, dc.name)

		tra = make_debit_note(pi.name)
		tra.bill_no = "602"  # số không có số 0 đầu vẫn nối được
		tra.items[0].qty = -20
		tra.insert()
		self.assertEqual(
			frappe.db.get_value(PHIEU, dc.name, ["trang_thai", "purchase_invoice"]),
			("Đã tạo nháp hóa đơn mua", tra.name),
		)
		self.assertEqual(frappe.db.get_value("Purchase Invoice", tra.name, "phieu_tiep_nhan"), dc.name)
		frappe.delete_doc("Purchase Invoice", tra.name)
		self.assertEqual(
			frappe.db.get_value(PHIEU, dc.name, ["trang_thai", "purchase_invoice"]),
			("Chờ xử lý thủ công", None),
		)

	def test_chua_co_hoa_don_goc(self):
		self.du_bo()
		dc = self.dieu_chinh("0009998", [("", TEN_HD, "Cái", -20, GIA, "10%")])
		self.assertEqual(dc.trang_thai, "Chờ xử lý thủ công")
		self.assertIn("Chưa có hóa đơn gốc", dc.canh_bao)

	def test_doi_thue_suat_xu_ly_tay_va_chan_phieu_goc(self):
		self.du_bo()
		goc = self.phieu([("", TEN_HD, "Cái", 500, GIA, "10%")], so="0000701")
		dc = self.dieu_chinh("0000701", [("", TEN_HD, "Cái", 0, 0, "8%", 1, -62500)])
		self.assertEqual(dc.trang_thai, "Chờ xử lý thủ công")
		self.assertIn("thuế suất", dc.items[0].canh_bao)
		goc.reload()
		self.assertEqual(goc.trang_thai, "Chờ xử lý thủ công")
		self.assertIn("chưa xử lý xong", goc.canh_bao)
		tu_choi(dc.name, "Kế toán xử lý tay")
		self.assertEqual(_tt(goc.name), "Đã đối soát")

	def test_chon_tay_dong_goc(self):
		a = self.item()
		b = self.item(ten="Găng tay khám nitrile cỡ M")
		self.hdk(
			[(a, 1000, GIA), (b, 1000, 3000, {"ten_hdk": "Găng tay khám nitrile cỡ M", "quy_cach": "M"})]
		)
		self.pr(self.po([(a, 500, GIA), (b, 100, 3000)]))
		goc = self.phieu(
			[("", TEN_HD, "Cái", 500, GIA, "10%"), ("", "Găng tay nitrile size M", "Cái", 100, 3000, "10%")],
			so="0000801",
		)
		dc = self.dieu_chinh("0000801", [("", "Điều chỉnh giảm theo biên bản", "Cái", -10, 3000, "10%")])
		self.assertEqual((dc.items[0].trang_thai_dong, dc.trang_thai), ("Chưa khớp", "Chờ xử lý thủ công"))
		dc.items[0].dong_goc, dc.items[0].chon_tay = 2, 1
		dc.save()
		self.assertEqual((dc.items[0].kieu_dieu_chinh, dc.trang_thai), ("Số lượng", "Đã đối soát"))
		goc.reload()
		self.assertEqual(flt(goc.items[1].so_luong_sau_dc), 90)
		self.assertFalse(goc.items[0].dieu_chinh)
