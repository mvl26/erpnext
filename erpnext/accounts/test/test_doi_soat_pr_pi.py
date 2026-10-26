# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Đối soát Phiếu nhập ↔ Hóa đơn mua và ĐNTT nháp (YC5, spec 2026-10-21 mục 6.3, tình huống 7.3).

Mỗi test chạy trong savepoint và được hoàn tác. Cài đặt đặt như production (spec 3.5):
`maintain_same_rate` = Warn, `pr_required` = Yes, `round_row_wise_tax` = 1.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, getdate, nowdate

from erpnext.accounts.doi_soat_pr_pi.doi_soat import NHAT_KY, doi_soat_lai, duyet_ngoai_le
from erpnext.accounts.doi_soat_pr_pi.nhac_lech import hoa_don_lech_qua_han, nhac_ke_toan_truong
from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice as pi_tu_po
from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
from erpnext.controllers.accounts_controller import get_taxes_and_charges
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice as pi_tu_pr

GIA = 100000
VAT10 = "GTGT mua vào 10%"
VAT8 = "GTGT mua vào 8%"


class DoiSoatCase(FrappeTestCase):
	def setUp(self):
		frappe.db.savepoint("doi_soat_pr_pi")
		self.addCleanup(frappe.db.rollback, save_point="doi_soat_pr_pi")
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(setattr, frappe.flags, "mute_emails", frappe.flags.mute_emails)
		frappe.flags.mute_emails = True
		self.addCleanup(frappe.clear_document_cache, "Buying Settings", "Buying Settings")
		self.addCleanup(frappe.clear_document_cache, "Accounts Settings", "Accounts Settings")

		self.company = frappe.db.get_value("Company", {}, "name")
		self.abbr = frappe.get_cached_value("Company", self.company, "abbr")
		self.currency = frappe.get_cached_value("Company", self.company, "default_currency")
		self.warehouse = frappe.db.get_value("Warehouse", {"company": self.company, "is_group": 0}, "name")
		self.chi_phi = frappe.db.get_value(
			"Account", {"company": self.company, "is_group": 0, "root_type": "Expense"}, "name"
		)
		# Site test có thể chưa khai tài khoản làm tròn (production đã có): Nộp hóa đơn VND cần nó.
		if not frappe.get_cached_value("Company", self.company, "round_off_account"):
			frappe.db.set_value(
				"Company",
				self.company,
				{
					"round_off_account": self.chi_phi,
					"round_off_cost_center": frappe.get_cached_value("Company", self.company, "cost_center"),
				},
			)
			frappe.clear_document_cache("Company", self.company)
		self.sfx = frappe.generate_hash(length=6)
		for uom in ("_DS Cái", "_DS Hộp"):
			if not frappe.db.exists("UOM", uom):
				frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert(ignore_permissions=True)

		frappe.db.set_single_value(
			"Buying Settings",
			{
				"maintain_same_rate": 1,
				"maintain_same_rate_action": "Warn",
				"pr_required": "Yes",
				"po_required": "No",
				# 0: ERPNext chặn hóa đơn vượt thành tiền Phiếu nhập ngay khi lưu (mặc định ERPNext là 1,
				# khi đó chỉ còn chặn vượt Đơn mua hàng lúc Nộp). Xem TestHoaDonCaoHonPhieuNhap.
				"bill_for_rejected_quantity_in_purchase_invoice": 0,
				"bat_doi_soat_pr_pi": 1,
				"pham_vi_doi_soat": "Mọi nhà cung cấp",
				"tao_dntt_khi_nop_hoa_don": 1,
				"vai_tro_ke_toan_truong": None,
				"vai_tro_ban_dieu_hanh": None,
				"nguoi_duyet_dntt": None,
			},
		)
		frappe.db.set_single_value(
			"Accounts Settings",
			{"round_row_wise_tax": 1, "create_pr_in_draft_status": 1, "over_billing_allowance": 0},
		)
		frappe.clear_document_cache("Buying Settings", "Buying Settings")
		frappe.clear_document_cache("Accounts Settings", "Accounts Settings")
		self.ncc = self.supplier()

	# --- Dữ liệu --------------------------------------------------------------

	def cai_dat(self, **values):
		frappe.db.set_single_value("Buying Settings", values)
		frappe.clear_document_cache("Buying Settings", "Buying Settings")

	def supplier(self, **fields):
		return (
			frappe.get_doc(
				{
					"doctype": "Supplier",
					"supplier_name": f"_DS NCC {frappe.generate_hash(length=6)}",
					"supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"),
					**fields,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def item(self, hop=None, is_stock_item=1):
		doc = frappe.new_doc("Item")
		doc.item_code = f"_DS-{frappe.generate_hash(length=8)}"
		doc.item_name = doc.item_code
		doc.item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
		doc.stock_uom = "_DS Cái"
		doc.is_stock_item = is_stock_item
		if hop:
			doc.append("uoms", {"uom": "_DS Hộp", "conversion_factor": hop})
		if not is_stock_item:
			doc.append("item_defaults", {"company": self.company, "expense_account": self.chi_phi})
		return doc.insert(ignore_permissions=True).name

	def user(self, *roles):
		email = f"_ds_{frappe.generate_hash(length=6)}@example.com"
		doc = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"send_welcome_email": 0,
				"user_type": "System User",
			}
		)
		for role in roles:
			doc.append("roles", {"role": role})
		return doc.insert(ignore_permissions=True).name

	def thue(self, mau=VAT10):
		return get_taxes_and_charges("Purchase Taxes and Charges Template", f"{mau} - {self.abbr}")

	def po(self, rows, thue=VAT10, ncc=None):
		"""`rows`: [(item, qty)] hoặc [(item, qty, rate)]."""
		doc = frappe.get_doc(
			{
				"doctype": "Purchase Order",
				"supplier": ncc or self.ncc,
				"company": self.company,
				"transaction_date": nowdate(),
				"schedule_date": add_days(nowdate(), 7),
				"currency": self.currency,
				"conversion_rate": 1,
				"items": [
					{
						"item_code": r[0],
						"qty": r[1],
						"rate": r[2] if len(r) > 2 else GIA,
						"warehouse": self.warehouse,
						"schedule_date": add_days(nowdate(), 7),
					}
					for r in rows
				],
				"taxes": self.thue(thue) if thue else [],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc

	def pr(self, po, qty=None, warehouse=None):
		doc = make_purchase_receipt(po.name)
		for d in doc.items:
			if qty is not None:
				d.qty = d.received_qty = qty
			if warehouse:
				d.warehouse = warehouse
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc

	def pi(self, nguon, sua=None):
		"""Hóa đơn nháp lập bằng nút Tạo từ Phiếu nhập (hoặc từ Đơn mua hàng)."""
		doc = pi_tu_pr(nguon.name) if nguon.doctype == "Purchase Receipt" else pi_tu_po(nguon.name)
		doc.bill_no = f"HD-{frappe.generate_hash(length=8)}"
		doc.bill_date = nowdate()
		if sua:
			sua(doc)
		frappe.clear_messages()
		doc.insert(ignore_permissions=True)
		return doc

	def tieu_chi(self, pi):
		return [r.tieu_chi for r in pi.chenh_lech_pr]

	def dntt(self, pi):
		return frappe.get_all(
			"Payment Request",
			filters={
				"reference_doctype": "Purchase Invoice",
				"reference_name": pi.name,
				"docstatus": ("<", 2),
			},
			fields=["name", "docstatus", "grand_total", "payment_request_type", "party_type", "party"],
		)


class TestDoiSoatPRPI(DoiSoatCase):
	# --- S1, S6, S7: khớp ------------------------------------------------------

	def test_s1_khop_nop_duoc_va_tao_dntt_nhap_giao_viec(self):
		ke_toan = self.user("Accounts Manager")
		self.cai_dat(nguoi_duyet_dntt=ke_toan)
		pr = self.pr(self.po([(self.item(), 10)]))
		pi = self.pi(pr)
		self.assertEqual(pi.trang_thai_doi_soat_pr, "Khớp")
		self.assertFalse(pi.chenh_lech_pr)

		# Site test không có hộp thư gửi đi: email báo giao việc lỗi thì việc giao bị hoàn tác.
		with patch("frappe.desk.form.assign_to.notify_assignment"):
			pi.submit()
		ds = self.dntt(pi)
		self.assertEqual(len(ds), 1)
		self.assertEqual(ds[0].docstatus, 0, "ĐNTT chỉ được tạo nháp (D6)")
		self.assertEqual(ds[0].payment_request_type, "Outward")
		self.assertEqual((ds[0].party_type, ds[0].party), ("Supplier", self.ncc))
		self.assertEqual(flt(ds[0].grand_total), flt(pi.outstanding_amount))
		self.assertTrue(
			frappe.db.exists(
				"ToDo",
				{"reference_type": "Payment Request", "reference_name": ds[0].name, "allocated_to": ke_toan},
			)
		)

	def test_s6_hoa_don_lap_tu_don_mua_van_duoc_ghep_va_doi_soat(self):
		po = self.po([(self.item(), 10)])
		pr = self.pr(po)
		pi = self.pi(po)
		self.assertEqual(pi.items[0].purchase_receipt, pr.name)
		self.assertEqual(pi.items[0].pr_detail, pr.items[0].name)
		self.assertEqual(pi.trang_thai_doi_soat_pr, "Khớp")

	def test_s7_mot_dong_po_nhan_qua_hai_phieu_nhap_duoc_tach(self):
		po = self.po([(self.item(), 10)])
		pr1 = self.pr(po, qty=6)
		pr2 = self.pr(po, qty=4)
		pi = self.pi(po)
		self.assertEqual([(d.purchase_receipt, flt(d.qty)) for d in pi.items], [(pr1.name, 6), (pr2.name, 4)])
		self.assertEqual(pi.trang_thai_doi_soat_pr, "Khớp")
		pi.submit()

	# --- S2-S5: lệch ----------------------------------------------------------

	def test_s2_lech_so_luong_chan_nop(self):
		pr = self.pr(self.po([(self.item(), 10)]))
		pi = self.pi(pr, lambda pi: setattr(pi.items[0], "qty", 9))
		self.assertEqual(pi.trang_thai_doi_soat_pr, "Lệch")
		self.assertEqual(self.tieu_chi(pi), ["Số lượng"])
		self.assertEqual(flt(pi.chenh_lech_pr[0].muc_lech), -1)
		self.assertRaises(frappe.ValidationError, pi.submit)

	def test_s3_lech_dvt_bi_chan_ngay_khi_luu(self):
		"""ERPNext so ĐVT dòng hóa đơn với dòng Phiếu nhập (`validate_with_previous_doc`) và chặn
		ngay khi lưu, trước cả bước đối soát."""
		item = self.item(hop=10)
		pr = self.pr(self.po([(item, 10)]))

		def nham_hop(pi):
			d = pi.items[0]
			d.uom, d.conversion_factor = "_DS Hộp", 10

		self.assertRaises(frappe.ValidationError, self.pi, pr, nham_hop)

	def test_lech_don_gia(self):
		"""Giá hóa đơn THẤP hơn Phiếu nhập. Giá cao hơn: xem TestHoaDonCaoHonPhieuNhap."""
		pr = self.pr(self.po([(self.item(), 10)]))
		pi = self.pi(pr, lambda pi: setattr(pi.items[0], "rate", GIA - 1))
		self.assertEqual(self.tieu_chi(pi), ["Đơn giá"])
		self.assertEqual(pi.chenh_lech_pr[0].nhanh_goi_y, "(b2) Hóa đơn NCC sai")

	def test_s4_lech_thue_suat_chan_nop(self):
		pr = self.pr(self.po([(self.item(), 10)]))

		def thue_8(pi):
			pi.taxes_and_charges = None
			pi.set("taxes", self.thue(VAT8))

		pi = self.pi(pr, thue_8)
		self.assertIn("Thuế suất", self.tieu_chi(pi))
		self.assertRaises(frappe.ValidationError, pi.submit)

	def test_s5_tong_lech_mot_dong(self):
		pr = self.pr(self.po([(self.item(), 10)]))

		def them_1_dong(pi):
			pi.append(
				"taxes",
				{
					"charge_type": "Actual",
					"account_head": pi.taxes[0].account_head,
					"description": "Lệch làm tròn",
					"tax_amount": 1,
					"category": "Total",
					"add_deduct_tax": "Add",
				},
			)

		pi = self.pi(pr, them_1_dong)
		self.assertEqual(pi.trang_thai_doi_soat_pr, "Lệch")
		self.assertEqual(self.tieu_chi(pi), ["Tổng thuế", "Tổng thanh toán"])
		self.assertEqual(flt(pi.chenh_lech_pr[-1].muc_lech), 1)
		self.assertRaises(frappe.ValidationError, pi.submit)

	def test_hoa_don_thu_hai_cho_phan_con_lai(self):
		"""NCC xuất hai hóa đơn cho một Phiếu nhập: hóa đơn đầu (6/10) cần ngoại lệ; hóa đơn sau
		so với phần còn lại chưa lập hóa đơn (4) nên khớp."""
		pr = self.pr(self.po([(self.item(), 10)]))
		dau = self.pi(pr, lambda pi: setattr(pi.items[0], "qty", 6))
		self.assertEqual(self.tieu_chi(dau), ["Số lượng"])
		duyet_ngoai_le(dau.name, "NCC xuất 2 hóa đơn")
		dau.reload()
		dau.submit()

		sau = self.pi(pr)
		self.assertEqual(flt(sau.items[0].qty), 4)
		self.assertEqual(sau.trang_thai_doi_soat_pr, "Khớp", self.tieu_chi(sau))

	def test_dong_phi_khong_co_tren_phieu_nhap(self):
		pr = self.pr(self.po([(self.item(), 10)]))
		phi = self.item(is_stock_item=0)
		pi = self.pi(pr, lambda pi: pi.append("items", {"item_code": phi, "qty": 1, "rate": 50000}))
		self.assertEqual(self.tieu_chi(pi), ["Ghép dòng"])
		self.assertEqual(pi.chenh_lech_pr[0].nhanh_goi_y, "(b2) Hóa đơn NCC sai")

	# --- S8: ghép mơ hồ ------------------------------------------------------

	def test_s8_ghep_mo_ho_chuyen_xu_ly_tay(self):
		self.cai_dat(pr_required="No")
		po = self.po([(self.item(), 10)])
		self.pr(po, qty=6)
		self.pr(po, qty=4)
		pi = self.pi(po, lambda pi: setattr(pi.items[0], "qty", 5))
		self.assertEqual(self.tieu_chi(pi), ["Ghép dòng"])
		self.assertEqual(pi.chenh_lech_pr[0].nhanh_goi_y, "Cần ghép tay")
		self.assertFalse(pi.items[0].pr_detail)

	def test_s8_bat_buoc_phieu_nhap_thi_bao_ro_ly_do(self):
		po = self.po([(self.item(), 10)])
		self.pr(po, qty=6)
		self.pr(po, qty=4)
		with self.assertRaisesRegex(frappe.ValidationError, "nhiều Phiếu nhập"):
			self.pi(po, lambda pi: setattr(pi.items[0], "qty", 5))

	# --- S9: ngoại lệ --------------------------------------------------------

	def hoa_don_lech(self):
		pr = self.pr(self.po([(self.item(), 10)]))
		return self.pi(pr, lambda pi: setattr(pi.items[0], "qty", 9))

	def test_s9_ngoai_le_do_ke_toan_truong_duyet(self):
		pi = self.hoa_don_lech()
		ktt = self.user("Accounts Manager")
		self.cai_dat(vai_tro_ke_toan_truong="Accounts Manager")

		frappe.set_user(self.user("Accounts User"))
		self.assertRaises(frappe.PermissionError, duyet_ngoai_le, pi.name, "NCC giao thiếu, đã thỏa thuận")

		frappe.set_user(ktt)
		self.assertEqual(duyet_ngoai_le(pi.name, "NCC giao thiếu, đã thỏa thuận"), "Ngoại lệ đã duyệt")
		frappe.set_user("Administrator")

		pi.reload()
		self.assertEqual(pi.nguoi_duyet_ngoai_le, ktt)
		self.assertEqual(pi.ly_do_ngoai_le, "NCC giao thiếu, đã thỏa thuận")
		self.assertTrue(pi.thoi_diem_duyet_ngoai_le)
		pi.submit()
		self.assertEqual(len(self.dntt(pi)), 1)

	def test_s9_ban_dieu_hanh_cung_duyet_duoc(self):
		pi = self.hoa_don_lech()
		self.cai_dat(vai_tro_ke_toan_truong="Accounts Manager", vai_tro_ban_dieu_hanh="Auditor")
		frappe.set_user(self.user("Auditor"))
		self.assertEqual(duyet_ngoai_le(pi.name, "BĐH đồng ý"), "Ngoại lệ đã duyệt")

	def test_ngoai_le_mat_hieu_luc_khi_chenh_lech_doi(self):
		pi = self.hoa_don_lech()
		duyet_ngoai_le(pi.name, "Thử")
		pi.reload()
		pi.items[0].qty = 8
		pi.save()
		self.assertEqual(pi.trang_thai_doi_soat_pr, "Lệch")
		self.assertFalse(pi.nguoi_duyet_ngoai_le)
		self.assertRaises(frappe.ValidationError, pi.submit)

	def test_khong_tu_dien_phe_duyet_qua_form_hay_api(self):
		pi = self.hoa_don_lech()
		pi.nguoi_duyet_ngoai_le = "Administrator"
		pi.ly_do_ngoai_le = "Tự duyệt"
		pi.trang_thai_doi_soat_pr = "Ngoại lệ đã duyệt"
		pi.save()
		self.assertEqual(pi.trang_thai_doi_soat_pr, "Lệch")
		self.assertFalse(pi.nguoi_duyet_ngoai_le)

	# --- S10, S11: sửa Phiếu nhập, hóa đơn mới -------------------------------

	def test_s10_kho_huy_va_sua_phieu_nhap_hoa_don_tu_doi_soat_lai(self):
		pr = self.pr(self.po([(self.item(), 12)]), qty=10)
		pi = self.pi(pr)
		self.assertEqual(pi.trang_thai_doi_soat_pr, "Khớp")

		pr.reload()
		pr.cancel()
		self.assertEqual(
			frappe.db.get_value("Purchase Invoice", pi.name, "trang_thai_doi_soat_pr"), "Chưa đối soát"
		)

		sua = frappe.copy_doc(pr)
		sua.docstatus = 0
		sua.amended_from = pr.name
		# Kho nhận thực tế 11 (phiếu cũ ghi 10). Bản sửa ít hơn hóa đơn thì ERPNext chặn lưu hóa đơn
		# vì vượt thành tiền Phiếu nhập ("Cannot overbill"), trước cả đối soát.
		sua.items[0].qty = sua.items[0].received_qty = 11
		sua.insert(ignore_permissions=True)
		sua.submit()

		pi.reload()
		self.assertEqual(pi.items[0].purchase_receipt, sua.name)
		self.assertEqual(pi.trang_thai_doi_soat_pr, "Lệch")
		self.assertEqual(self.tieu_chi(pi), ["Số lượng"])

	def test_nut_doi_soat_lai_ghep_sang_ban_sua_khi_hook_bo_lo(self):
		pr = self.pr(self.po([(self.item(), 10)]))
		pi = self.pi(pr)
		pr.reload()
		pr.cancel()
		sua = frappe.copy_doc(pr)
		sua.docstatus = 0
		sua.amended_from = pr.name
		sua.insert(ignore_permissions=True)
		with patch("erpnext.accounts.doi_soat_pr_pi.doi_soat._hoa_don_nhap_lien_quan", return_value=[]):
			sua.submit()
		self.assertRaises(frappe.CancelledLinkError, frappe.get_doc("Purchase Invoice", pi.name).save)

		self.assertEqual(doi_soat_lai(pi.name), "Khớp")
		self.assertEqual(
			frappe.db.get_value("Purchase Invoice Item", {"parent": pi.name}, "purchase_receipt"), sua.name
		)

	def test_s11_hoa_don_dieu_chinh_moi_doi_soat_lai_tu_dau(self):
		pr = self.pr(self.po([(self.item(), 10)]))
		cu = self.pi(pr, lambda pi: setattr(pi.items[0], "rate", GIA - 5000))
		self.assertEqual(cu.trang_thai_doi_soat_pr, "Lệch")
		cu.delete()
		self.assertEqual(self.pi(pr).trang_thai_doi_soat_pr, "Khớp")

	# --- S12-S14: ĐNTT -------------------------------------------------------

	def dntt_tay(self, pi, so_tien):
		return frappe.get_doc(
			{
				"doctype": "Payment Request",
				"payment_request_type": "Outward",
				"transaction_date": nowdate(),
				"company": pi.company,
				"party_type": "Supplier",
				"party": pi.supplier,
				"reference_doctype": "Purchase Invoice",
				"reference_name": pi.name,
				"currency": pi.currency,
				"party_account_currency": pi.party_account_currency,
				"grand_total": so_tien,
			}
		).insert(ignore_permissions=True)

	def test_s12_dntt_thu_hai_vuot_tong_bi_chan_tinh_ca_ban_nhap(self):
		pi = self.pi(self.pr(self.po([(self.item(), 10)])))
		pi.submit()
		self.assertEqual(len(self.dntt(pi)), 1)
		with self.assertRaisesRegex(frappe.ValidationError, "vượt số tiền hóa đơn"):
			self.dntt_tay(pi, 1)

	def test_s13_chia_hai_dot_duoc_dot_ba_bi_chan(self):
		self.cai_dat(tao_dntt_khi_nop_hoa_don=0)
		pi = self.pi(self.pr(self.po([(self.item(), 10)])))
		pi.submit()
		tong = flt(pi.rounded_total or pi.grand_total)
		self.dntt_tay(pi, flt(tong * 0.6))
		self.dntt_tay(pi, tong - flt(tong * 0.6))
		with self.assertRaisesRegex(frappe.ValidationError, "vượt số tiền hóa đơn"):
			self.dntt_tay(pi, 1)

	def test_huy_dntt_thi_tao_lai_duoc(self):
		self.cai_dat(tao_dntt_khi_nop_hoa_don=0)
		pi = self.pi(self.pr(self.po([(self.item(), 10)])))
		pi.submit()
		tong = flt(pi.rounded_total or pi.grand_total)
		dau = self.dntt_tay(pi, tong)
		dau.submit()
		dau.cancel()
		self.dntt_tay(pi, tong)

	def test_s14_tao_dntt_loi_thi_hoa_don_khong_nop(self):
		pi = self.pi(self.pr(self.po([(self.item(), 10)])))
		frappe.db.savepoint("s14")
		with patch(
			"erpnext.accounts.doi_soat_pr_pi.de_nghi_thanh_toan.get_amount",
			side_effect=frappe.ValidationError,
		):
			self.assertRaises(frappe.ValidationError, pi.submit)
		frappe.db.rollback(save_point="s14")
		self.assertEqual(frappe.db.get_value("Purchase Invoice", pi.name, "docstatus"), 0)
		self.assertFalse(self.dntt(pi))

	def test_dntt_dinh_kem_file_pdf_cua_hoa_don(self):
		# PDF chỉ có ký tự ASCII: Frappe đọc lại thành chuỗi nếu chỉ chép file_url (lỗi khi kiểm PDF).
		vat = [
			b"<< /Type /Catalog /Pages 2 0 R >>",
			b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
			b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>",
		]
		pdf, vi_tri = b"%PDF-1.4\n", []
		for i, v in enumerate(vat, 1):
			vi_tri.append(len(pdf))
			pdf += b"%d 0 obj %s endobj\n" % (i, v)
		xref = len(pdf)
		pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(vat) + 1)
		pdf += b"".join(b"%010d 00000 n \n" % v for v in vi_tri)
		pdf += b"trailer << /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(vat) + 1, xref)
		pi = self.pi(self.pr(self.po([(self.item(), 10)])))
		goc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"hd-{self.sfx}.pdf",
				"content": pdf,
				"is_private": 1,
				"attached_to_doctype": "Purchase Invoice",
				"attached_to_name": pi.name,
			}
		).insert(ignore_permissions=True)
		pi.reload()
		pi.submit()
		tep = frappe.get_all(
			"File",
			filters={"attached_to_doctype": "Payment Request", "attached_to_name": self.dntt(pi)[0].name},
			pluck="file_url",
		)
		self.assertEqual(tep, [goc.file_url], "trỏ cùng tệp, không ghi bản sao")

	def test_huy_hoa_don_xoa_dntt_nhap(self):
		pi = self.pi(self.pr(self.po([(self.item(), 10)])))
		pi.submit()
		ten = self.dntt(pi)[0].name
		pi.reload()
		pi.cancel()
		self.assertFalse(frappe.db.exists("Payment Request", ten))

	# --- S16, S17, phạm vi ---------------------------------------------------

	def test_s16_kho_khac_doi_soat_nhu_luong_chuan(self):
		kho = frappe.db.get_value(
			"Warehouse",
			{"company": self.company, "is_group": 0, "name": ("!=", self.warehouse)},
			"name",
			order_by="name like '%Himedic%' desc",
		)
		pr = self.pr(self.po([(self.item(), 10)]), warehouse=kho)
		self.assertEqual(self.pi(pr).trang_thai_doi_soat_pr, "Khớp")

	def test_s17_hoa_don_dich_vu_khong_co_phieu_nhap_khong_ap(self):
		po = self.po([(self.item(is_stock_item=0), 1)])
		pi = self.pi(po)
		self.assertFalse(pi.trang_thai_doi_soat_pr)
		pi.submit()
		self.assertFalse(self.dntt(pi))

	def test_tat_cong_tac_thi_khong_doi_soat(self):
		self.cai_dat(bat_doi_soat_pr_pi=0)
		pr = self.pr(self.po([(self.item(), 10)]))
		pi = self.pi(pr, lambda pi: setattr(pi.items[0], "qty", 9))
		self.assertFalse(pi.trang_thai_doi_soat_pr)
		pi.submit()
		self.assertFalse(self.dntt(pi))

	def test_bat_thu_chi_ap_cho_nha_cung_cap_duoc_chon(self):
		self.cai_dat(pham_vi_doi_soat="Chỉ nhà cung cấp được chọn")
		pr = self.pr(self.po([(self.item(), 10)]))
		self.assertFalse(self.pi(pr).trang_thai_doi_soat_pr)

		ncc = self.supplier(doi_soat_pr_pi=1)
		pr = self.pr(self.po([(self.item(), 10)], ncc=ncc))
		self.assertEqual(self.pi(pr).trang_thai_doi_soat_pr, "Khớp")

	# --- Quyền cài đặt -------------------------------------------------------

	def test_chi_system_manager_sua_cai_dat_doi_soat(self):
		frappe.set_user(self.user("Purchase Manager"))
		doc = frappe.get_doc("Buying Settings")
		doc.bat_doi_soat_pr_pi = 0
		self.assertRaises(frappe.PermissionError, doc.save)

	def test_nguoi_lap_hoa_don_khong_tu_bo_nha_cung_cap_khoi_doi_soat(self):
		ncc = self.supplier(doi_soat_pr_pi=1)
		frappe.set_user(self.user("Purchase Manager"))
		doc = frappe.get_doc("Supplier", ncc)
		doc.doi_soat_pr_pi = 0
		self.assertRaises(frappe.PermissionError, doc.save)


class TestHoaDonCaoHonPhieuNhap(DoiSoatCase):
	"""Hóa đơn cao hơn Phiếu nhập / Đơn mua hàng (quyết định 23/10/2026): hóa đơn thuộc phạm vi đối
	soát vẫn lưu được để vào Bảng chênh lệch; lúc Nộp chỉ được vượt Đơn mua hàng khi đã có ngoại lệ
	được duyệt. Không dùng Over Billing Allowance (cài đặt chung, áp cả hóa đơn bán). Cài đặt như
	setUp: `bill_for_rejected_quantity_in_purchase_invoice` = 0, không cho vượt."""

	def test_cao_hon_phieu_nhap_van_luu_duoc_va_bi_chan_nop(self):
		pr = self.pr(self.po([(self.item(), 10)]))
		pi = self.pi(pr, lambda pi: setattr(pi.items[0], "rate", GIA * 1.2))
		self.assertEqual(pi.trang_thai_doi_soat_pr, "Lệch")
		self.assertEqual(self.tieu_chi(pi), ["Đơn giá"])
		self.assertEqual(flt(pi.chenh_lech_pr[0].muc_lech), GIA * 0.2)
		self.assertRaisesRegex(frappe.ValidationError, "chưa khớp Phiếu nhập", pi.submit)

	def test_cao_hon_phieu_nhap_thi_khong_duyet_ngoai_le_duoc(self):
		"""ERPNext chặn lúc Nộp hóa đơn vượt giá trị Phiếu nhập (giữ đúng giá trị tồn kho), không bỏ
		qua được cho riêng một hóa đơn: nút Duyệt ngoại lệ báo trước, chỉ đường sửa Phiếu nhập (b1)
		hoặc xin hóa đơn điều chỉnh (b2)."""
		pr = self.pr(self.po([(self.item(), 10)]))
		pi = self.pi(pr, lambda pi: setattr(pi.items[0], "rate", GIA * 1.2))
		self.assertRaisesRegex(
			frappe.ValidationError, "vượt giá trị hàng đã nhập kho", duyet_ngoai_le, pi.name, "Thử"
		)
		self.assertFalse(frappe.db.get_value("Purchase Invoice", pi.name, "nguoi_duyet_ngoai_le"))

	def test_ngoai_le_duoc_duyet_thi_nop_duoc_du_vuot_don_mua(self):
		"""Phiếu nhập giá 120% Đơn mua (maintain_same_rate = Warn chỉ cảnh báo), hóa đơn 110%: thấp hơn
		Phiếu nhập nên lệch; có ngoại lệ thì Nộp được dù vượt thành tiền Đơn mua hàng."""
		po = self.po([(self.item(), 10)])
		doc = make_purchase_receipt(po.name)
		doc.items[0].rate = GIA * 1.2
		doc.insert(ignore_permissions=True)
		doc.submit()
		pi = self.pi(doc, lambda pi: setattr(pi.items[0], "rate", GIA * 1.1))
		self.assertEqual(self.tieu_chi(pi), ["Đơn giá"])
		duyet_ngoai_le(pi.name, "BĐH đồng ý giá 110%")
		pi.reload()
		pi.submit()
		self.assertEqual(flt(self.dntt(pi)[0].grand_total), flt(pi.outstanding_amount))

	def test_so_luong_nhieu_hon_phieu_nhap_vao_bang_chenh_lech(self):
		pr = self.pr(self.po([(self.item(), 12)]), qty=10)
		pi = self.pi(pr, lambda pi: setattr(pi.items[0], "qty", 11))
		self.assertEqual(self.tieu_chi(pi), ["Số lượng"])
		self.assertEqual(flt(pi.chenh_lech_pr[0].muc_lech), 1)

	def test_ngoai_pham_vi_doi_soat_erpnext_van_chan_khi_luu(self):
		self.cai_dat(pham_vi_doi_soat="Chỉ nhà cung cấp được chọn")
		pr = self.pr(self.po([(self.item(), 10)]))
		self.assertRaisesRegex(
			frappe.ValidationError,
			"overbill",
			self.pi,
			pr,
			lambda pi: setattr(pi.items[0], "rate", GIA * 1.2),
		)

	def test_khop_phieu_nhap_nhung_vuot_don_mua_van_bi_erpnext_chan(self):
		"""Phiếu nhập giá cao hơn Đơn mua (maintain_same_rate = Warn chỉ cảnh báo), hóa đơn khớp
		Phiếu nhập: không có ngoại lệ nên chặn vượt Đơn mua hàng chuẩn vẫn áp."""
		po = self.po([(self.item(), 10)])
		doc = make_purchase_receipt(po.name)
		doc.items[0].rate = GIA * 1.2
		doc.insert(ignore_permissions=True)
		doc.submit()
		pi = self.pi(doc)
		self.assertEqual(pi.trang_thai_doi_soat_pr, "Khớp")
		self.assertRaisesRegex(frappe.ValidationError, "over limit", pi.submit)


class TestHoaDonTungPhan(DoiSoatCase):
	"""NCC xuất nhiều hóa đơn cho một Phiếu nhập (quyết định 23/10/2026): ô Hóa đơn từng phần."""

	def tung_phan(self, qty, **sua):
		def _sua(pi):
			pi.hoa_don_tung_phan = 1
			pi.items[0].qty = qty
			for k, v in sua.items():
				setattr(pi.items[0], k, v)

		return _sua

	def test_it_hon_phan_chua_lap_thi_khop_hoa_don_sau_khop_phan_con_lai(self):
		pr = self.pr(self.po([(self.item(), 10)]))
		dau = self.pi(pr, self.tung_phan(6))
		self.assertEqual(dau.trang_thai_doi_soat_pr, "Khớp", self.tieu_chi(dau))
		self.assertEqual(dau.flags.con_chua_lap_hoa_don[0][2], 4)
		dau.submit()

		sau = self.pi(pr)
		self.assertEqual(flt(sau.items[0].qty), 4)
		self.assertEqual(sau.trang_thai_doi_soat_pr, "Khớp", self.tieu_chi(sau))
		sau.submit()

	def test_tung_phan_van_so_gia(self):
		pr = self.pr(self.po([(self.item(), 10)]))
		pi = self.pi(pr, self.tung_phan(6, rate=GIA - 1))
		self.assertEqual(self.tieu_chi(pi), ["Đơn giá"])

	def test_tung_phan_khong_duoc_nhieu_hon_phan_chua_lap(self):
		pr = self.pr(self.po([(self.item(), 12)]), qty=10)
		pi = self.pi(pr, self.tung_phan(11))
		self.assertEqual(self.tieu_chi(pi), ["Số lượng"])

	def test_khong_tich_thi_it_hon_van_lech(self):
		pr = self.pr(self.po([(self.item(), 10)]))
		pi = self.pi(pr, lambda pi: setattr(pi.items[0], "qty", 6))
		self.assertEqual(self.tieu_chi(pi), ["Số lượng"])

	def pr_co_phi(self, phi=50_000):
		"""Phiếu nhập 10 cái kèm cước vận chuyển cố định; lập hóa đơn từ phiếu thì ERPNext chép
		dòng cước sang mọi hóa đơn."""
		doc = make_purchase_receipt(self.po([(self.item(), 10)]).name)
		doc.append(
			"taxes",
			{
				"charge_type": "Actual",
				"account_head": doc.taxes[0].account_head,
				"description": "Cước vận chuyển",
				"tax_amount": phi,
				"category": "Total",
				"add_deduct_tax": "Add",
			},
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc

	@staticmethod
	def bo_phi(pi):
		pi.set("taxes", [t for t in pi.taxes if t.charge_type != "Actual"])

	def test_phi_co_dinh_lap_o_hoa_don_dau_thi_hoa_don_sau_bo_phi(self):
		pr = self.pr_co_phi()
		dau = self.pi(pr, self.tung_phan(6))
		self.assertIn("Actual", [t.charge_type for t in dau.taxes])
		self.assertEqual(dau.trang_thai_doi_soat_pr, "Khớp", self.tieu_chi(dau))
		dau.submit()

		sau = self.pi(pr)
		self.assertEqual(self.tieu_chi(sau), ["Tổng thuế", "Tổng thanh toán"])
		self.assertEqual(flt(sau.chenh_lech_pr[-1].muc_lech), 50_000)
		self.bo_phi(sau)
		sau.save()
		self.assertEqual(sau.trang_thai_doi_soat_pr, "Khớp", self.tieu_chi(sau))

	def test_phi_co_dinh_lap_o_hoa_don_cuoi(self):
		pr = self.pr_co_phi()
		dau = self.pi(pr, lambda pi: (self.tung_phan(6)(pi), self.bo_phi(pi)))
		self.assertEqual(dau.trang_thai_doi_soat_pr, "Khớp", self.tieu_chi(dau))
		dau.submit()

		sau = self.pi(pr)
		self.assertEqual(sau.trang_thai_doi_soat_pr, "Khớp", self.tieu_chi(sau))

	def test_phi_co_dinh_khac_phieu_nhap_van_lech(self):
		pr = self.pr_co_phi()

		def phi_khac(pi):
			self.tung_phan(6)(pi)
			next(t for t in pi.taxes if t.charge_type == "Actual").tax_amount = 60_000

		pi = self.pi(pr, phi_khac)
		self.assertEqual(self.tieu_chi(pi), ["Tổng thuế", "Tổng thanh toán"])
		self.assertEqual(flt(pi.chenh_lech_pr[-1].muc_lech), 10_000)


class TestNhacLechTon(DoiSoatCase):
	"""Nhắc Kế toán trưởng khi hóa đơn lệch tồn quá N ngày (spec 6.3.9)."""

	def hoa_don_lech(self):
		pr = self.pr(self.po([(self.item(), 10)]))
		return self.pi(pr, lambda pi: setattr(pi.items[0], "qty", 9))

	def lui_ngay_lech(self, pi, so_ngay):
		frappe.db.set_value("Purchase Invoice", pi.name, "lech_tu_ngay", add_days(nowdate(), -so_ngay))

	def test_lech_tu_ngay_giu_ngay_dau_xoa_khi_khop(self):
		pi = self.hoa_don_lech()
		self.assertEqual(getdate(pi.lech_tu_ngay), getdate(nowdate()))

		self.lui_ngay_lech(pi, 5)
		pi.reload()
		pi.items[0].qty = 8
		pi.save()
		self.assertEqual(pi.trang_thai_doi_soat_pr, "Lệch")
		self.assertEqual(getdate(pi.lech_tu_ngay), getdate(add_days(nowdate(), -5)))

		pi.items[0].qty = 10
		pi.save()
		self.assertEqual(pi.trang_thai_doi_soat_pr, "Khớp")
		self.assertFalse(pi.lech_tu_ngay)

	def test_ngoai_le_da_duyet_thi_khong_con_nhac(self):
		pi = self.hoa_don_lech()
		duyet_ngoai_le(pi.name, "Thử")
		self.assertFalse(frappe.db.get_value("Purchase Invoice", pi.name, "lech_tu_ngay"))

	def test_nhac_ke_toan_truong_khi_qua_han(self):
		ktt = self.user("Accounts Manager")
		self.cai_dat(vai_tro_ke_toan_truong="Accounts Manager", so_ngay_nhac_lech=3)
		pi = self.hoa_don_lech()
		self.lui_ngay_lech(pi, 3)

		# Site test không có hộp thư gửi đi: chỉ kiểm thông báo trong hệ thống (chuông).
		with patch("frappe.desk.doctype.notification_log.notification_log.send_notification_email"):
			self.assertGreaterEqual(nhac_ke_toan_truong(), 1)
		log = frappe.get_all(
			"Notification Log", filters={"for_user": ktt}, fields=["subject", "email_content"], limit=1
		)
		self.assertTrue(log)
		self.assertIn("lệch Phiếu nhập quá 3 ngày", log[0].subject)
		self.assertIn(pi.name, log[0].email_content)

	def test_chua_qua_han_hoac_tat_nhac_thi_khong_nhac(self):
		self.cai_dat(vai_tro_ke_toan_truong="Accounts Manager", so_ngay_nhac_lech=3)
		pi = self.hoa_don_lech()
		self.lui_ngay_lech(pi, 2)
		self.assertNotIn(pi.name, [r.name for r in hoa_don_lech_qua_han(3)])

		self.lui_ngay_lech(pi, 3)
		self.assertIn(pi.name, [r.name for r in hoa_don_lech_qua_han(3)])
		self.cai_dat(so_ngay_nhac_lech=0)
		self.assertEqual(nhac_ke_toan_truong(), 0)


class TestNhatKyDoiSoat(DoiSoatCase):
	"""6.3.4: nhật ký đối soát không xóa được. Bảng chênh lệch trên hóa đơn chỉ giữ kết quả mới nhất;
	nhật ký giữ mọi lần kết quả thay đổi."""

	def nhat_ky(self, pi):
		return frappe.get_all(
			NHAT_KY,
			filters={"hoa_don": pi.name},
			fields=["su_kien", "trang_thai", "so_diem_lech", "phieu_nhap", "ly_do", "chi_tiet", "nguoi"],
			order_by="creation",
		)

	def test_ghi_khi_ket_qua_doi_va_khi_nop(self):
		pr = self.pr(self.po([(self.item(), 10)]))
		pi = self.pi(pr, lambda pi: setattr(pi.items[0], "qty", 9))
		pi.save()  # lưu lại mà kết quả không đổi: không ghi thêm
		pi.items[0].qty = 10
		pi.save()
		pi.submit()

		nk = self.nhat_ky(pi)
		self.assertEqual(
			[(r.su_kien, r.trang_thai, r.so_diem_lech) for r in nk],
			[("Đối soát", "Lệch", 1), ("Đối soát", "Khớp", 0), ("Nộp hóa đơn", "Khớp", 0)],
		)
		self.assertIn("Số lượng", nk[0].chi_tiet)
		self.assertEqual(nk[0].nguoi, "Administrator")

	def test_ghi_lan_duyet_ngoai_le_kem_ly_do(self):
		pr = self.pr(self.po([(self.item(), 10)]))
		pi = self.pi(pr, lambda pi: setattr(pi.items[0], "qty", 9))
		duyet_ngoai_le(pi.name, "NCC giao thiếu, đã thỏa thuận")

		nk = self.nhat_ky(pi)
		self.assertEqual(
			[(r.su_kien, r.trang_thai) for r in nk],
			[("Đối soát", "Lệch"), ("Duyệt ngoại lệ", "Ngoại lệ đã duyệt")],
		)
		self.assertEqual(nk[1].ly_do, "NCC giao thiếu, đã thỏa thuận")

	def test_ghi_khi_phieu_nhap_bi_huy_va_khi_ban_sua_duoc_nop(self):
		pr = self.pr(self.po([(self.item(), 12)]), qty=10)
		pi = self.pi(pr)
		pr.reload()
		pr.cancel()
		sua = frappe.copy_doc(pr)
		sua.docstatus = 0
		sua.amended_from = pr.name
		sua.items[0].qty = sua.items[0].received_qty = 11
		sua.insert(ignore_permissions=True)
		sua.submit()

		self.assertEqual(
			[(r.su_kien, r.trang_thai, r.phieu_nhap) for r in self.nhat_ky(pi)],
			[
				("Đối soát", "Khớp", None),
				("Phiếu nhập thay đổi", "Chưa đối soát", pr.name),
				("Đối soát", "Lệch", sua.name),
			],
		)

	def test_xoa_hoa_don_nhap_van_duoc_va_nhat_ky_con_lai(self):
		pr = self.pr(self.po([(self.item(), 10)]))
		pi = self.pi(pr, lambda pi: setattr(pi.items[0], "qty", 9))
		ten = pi.name
		pi.delete()

		self.assertEqual(frappe.db.count(NHAT_KY, {"hoa_don": ten}), 1)

	def test_chuoi_buoc_hdkt_c1_den_c10(self):
		"""HDKT Đợt 3 C11: thứ tự nhật ký sau các bước C1 → C10."""
		pr = self.pr(self.po([(self.item(), 10)]))
		pi = self.pi(pr, lambda pi: setattr(pi.items[0], "qty", 9))  # C1
		duyet_ngoai_le(pi.name, "NCC giao thiếu 1, đã thỏa thuận")  # C7
		for qty in (8, 9):  # C8, C9
			pi.reload()
			pi.items[0].qty = qty
			pi.save()
		duyet_ngoai_le(pi.name, "Duyệt lại")  # C10
		pi.reload()
		pi.submit()

		self.assertEqual(
			[(r.su_kien, r.trang_thai) for r in self.nhat_ky(pi)],
			[
				("Đối soát", "Lệch"),
				("Duyệt ngoại lệ", "Ngoại lệ đã duyệt"),
				("Đối soát", "Lệch"),
				("Đối soát", "Lệch"),
				("Duyệt ngoại lệ", "Ngoại lệ đã duyệt"),
				("Nộp hóa đơn", "Ngoại lệ đã duyệt"),
			],
		)
		self.assertIn("Hóa đơn 8", self.nhat_ky(pi)[2].chi_tiet)
