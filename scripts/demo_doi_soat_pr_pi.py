"""Dữ liệu demo cho đối soát Phiếu nhập mua ↔ Hóa đơn mua và ĐNTT nháp (YC5 - Đợt 3).

Dùng cùng `docs/HDKT_Dot3_Doi_soat_PR_PI.md`. Chạy từ thư mục `sites` của bench:

	cd ~/frappe-bench/sites
	../env/bin/python ../apps/erpnext/scripts/demo_doi_soat_pr_pi.py --site erpnext.localhost

Nhắc Kế toán trưởng ngay, không chờ 8 giờ sáng (lùi "Lệch từ ngày" của một hóa đơn rồi chạy job):

	../env/bin/python ../apps/erpnext/scripts/demo_doi_soat_pr_pi.py --site erpnext.localhost \\
		--nhac-lech ACC-PINV-2026-00001

Trả cài đặt về như trước lần chạy đầu:

	../env/bin/python ../apps/erpnext/scripts/demo_doi_soat_pr_pi.py --site erpnext.localhost --tra-lai

- TỪ CHỐI chạy trên site `miyano` (production).
- Mỗi lần chạy tạo một bộ Đơn mua hàng và Phiếu nhập mua MỚI (đã Nộp), không đụng bộ cũ; ô
  "Phiếu giao hàng của NCC" của mỗi Phiếu nhập ghi mã kịch bản (DEMO-D3-A...). Hóa đơn mua do
  người test tự lập theo HDKT.
- Cài đặt dùng chung (Buying Settings, Accounts Settings, tài khoản làm tròn của công ty, ô Áp
  đối soát trên hai NCC demo) được in ra khi đổi. Giá trị trước lần chạy đầu lưu ở
  `<site>/private/demo_doi_soat_pr_pi_cai_dat_cu.json` để `--tra-lai`.
- Site tắt gửi email (`mute_emails`) mà chưa có hộp thư gửi đi: tạo hộp thư "DEMO gửi đi (không
  gửi thật)". Không có nó, Frappe dựng hộp thư giả không có địa chỉ người gửi và mọi thông báo
  email (giao việc, NTF-16 → 19) lỗi. Email chỉ nằm trong hàng đợi; `--tra-lai` xóa hộp thư này.

Kịch bản (NCC DEMO-Vietmed, thuộc phạm vi đối soát, trừ J):
  A  Phiếu nhập 10 DEMO-VT-01 x 100.000, VAT 10%: hóa đơn khớp, Nộp, ĐNTT nháp
  B  như A: hóa đơn 9 cái -> Lệch số lượng, nhắc Kế toán trưởng, duyệt ngoại lệ
  C  20 DEMO-VT-02 x 50.000: hóa đơn 48.000 -> Lệch đơn giá, gửi NCC bảng chênh lệch, lập lại
  D  5 DEMO-VT-01: hóa đơn VAT 8% -> Lệch thuế suất
  E  như A: hóa đơn 120.000 -> cao hơn Phiếu nhập, không duyệt ngoại lệ được
  F  Đơn mua 12, Phiếu nhập 10 DEMO-VT-02: hóa đơn 11 -> Kho sửa Phiếu nhập (nhánh b1)
  G  Đơn mua 10 DEMO-VT-01 nhận qua 2 Phiếu nhập 6 + 4: hóa đơn từ Đơn mua tách 2 dòng
  H  Đơn mua 10 DEMO-VT-02 nhận qua 2 Phiếu nhập 6 + 4: hóa đơn 5 cái không ghép được
  I  như A kèm cước vận chuyển 50.000: hóa đơn từng phần 6 + 4, cước chỉ lập một lần
  J  NCC DEMO-Hùng Minh (ngoài phạm vi), 10 DEMO-VT-02 x 50.000: không đối soát
  K  Đơn mua dịch vụ DEMO-DV-VC (không có Phiếu nhập): không đối soát, không ĐNTT
  L  10 DEMO-VT-05 (ĐVT kho Cái, có Hộp = 10 Cái): hóa đơn đổi sang Hộp bị ERPNext chặn
"""

import argparse
import json
import os
import sys

import frappe
from frappe.utils import add_days, nowdate

SITE_PRODUCTION = "miyano"
TEP_CAI_DAT_CU = "demo_doi_soat_pr_pi_cai_dat_cu.json"
NCC_THU = "DEMO-Vietmed"
NCC_NGOAI = "DEMO-Hùng Minh"
KE_TOAN_TRUONG = "demo.ketoantruong@example.com"
NHOM_KE_TOAN = ["Accounts User", "Purchase User", "Stock User"]
NGUOI_DUNG = (
	("demo.ketoan@example.com", "DEMO Kế toán", NHOM_KE_TOAN),
	(KE_TOAN_TRUONG, "DEMO Kế toán trưởng", [*NHOM_KE_TOAN, "Accounts Manager"]),
	("demo.muahang@example.com", "DEMO Mua hàng", ["Purchase Manager", "Purchase User", "Stock User"]),
)
# Như production (spec 3.5) để hóa đơn khác giá Đơn mua vẫn tới bước đối soát: "Stop" thì ERPNext
# chặn trước khi có Bảng chênh lệch.
BUYING_SETTINGS = {
	"maintain_same_rate": 1,
	"maintain_same_rate_action": "Warn",
	"pr_required": "Yes",
	"bat_doi_soat_pr_pi": 1,
	"pham_vi_doi_soat": "Chỉ nhà cung cấp được chọn",
	"tao_dntt_khi_nop_hoa_don": 1,
	"vai_tro_ke_toan_truong": "Accounts Manager",
	"vai_tro_ban_dieu_hanh": None,
	"nguoi_duyet_dntt": KE_TOAN_TRUONG,
	"so_ngay_nhac_lech": 3,
}
ACCOUNTS_SETTINGS = {"round_row_wise_tax": 1}
THUE_10 = "GTGT mua vào 10%"
HOP_THU_DEMO = "DEMO gửi đi (không gửi thật)"


def main():
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--site", required=True)
	parser.add_argument(
		"--nhac-lech", metavar="HOA_DON", help="lùi Lệch từ ngày rồi chạy nhắc Kế toán trưởng"
	)
	parser.add_argument("--tra-lai", action="store_true", help="trả cài đặt về như trước lần chạy đầu")
	args = parser.parse_args()
	if args.site == SITE_PRODUCTION:
		sys.exit("Từ chối: không tạo dữ liệu demo trên site production.")

	frappe.init(site=args.site, sites_path=os.getcwd())
	frappe.connect()
	try:
		frappe.set_user("Administrator")
		if args.tra_lai:
			tra_lai()
		elif args.nhac_lech:
			nhac_lech(args.nhac_lech)
		else:
			tao_demo()
		frappe.db.commit()
	finally:
		frappe.destroy()


# --- Cài đặt ----------------------------------------------------------------------


def _tep_cai_dat_cu():
	return frappe.get_site_path("private", TEP_CAI_DAT_CU)


def _cai_dat_hien_tai(cong_ty):
	return {
		"Buying Settings": {k: frappe.db.get_single_value("Buying Settings", k) for k in BUYING_SETTINGS},
		"Accounts Settings": {
			k: frappe.db.get_single_value("Accounts Settings", k) for k in ACCOUNTS_SETTINGS
		},
		"Company": {
			"name": cong_ty,
			"round_off_account": frappe.db.get_value("Company", cong_ty, "round_off_account"),
		},
		"Supplier": {
			ncc: frappe.db.get_value("Supplier", ncc, "doi_soat_pr_pi")
			for ncc in (NCC_THU, NCC_NGOAI)
			if frappe.db.exists("Supplier", ncc)
		},
	}


def _dat(doctype, values):
	for k, v in values.items():
		cu = frappe.db.get_single_value(doctype, k)
		if str(cu or "") != str(v or ""):
			print(f"  {doctype} · {k}: {cu!r} -> {v!r}")
	frappe.db.set_single_value(doctype, values)
	frappe.clear_document_cache(doctype, doctype)


def dat_cai_dat(cong_ty):
	tep = _tep_cai_dat_cu()
	if not os.path.exists(tep):
		with open(tep, "w") as f:
			json.dump(_cai_dat_hien_tai(cong_ty), f, ensure_ascii=False, indent=1, default=str)
		print(f"Đã lưu cài đặt cũ vào {tep} (dùng --tra-lai để trả lại).")

	print("Cài đặt:")
	_dat("Buying Settings", BUYING_SETTINGS)
	_dat("Accounts Settings", ACCOUNTS_SETTINGS)
	if not frappe.db.get_value("Company", cong_ty, "round_off_account"):
		# Nộp hóa đơn VND cần tài khoản làm tròn; production đã có.
		tk = frappe.db.get_value(
			"Account", {"company": cong_ty, "is_group": 0, "account_type": "Round Off"}, "name"
		)
		frappe.db.set_value(
			"Company",
			cong_ty,
			{
				"round_off_account": tk,
				"round_off_cost_center": frappe.db.get_value("Company", cong_ty, "round_off_cost_center")
				or frappe.db.get_value("Company", cong_ty, "cost_center"),
			},
		)
		frappe.clear_document_cache("Company", cong_ty)
		print(f"  Company {cong_ty} · round_off_account: None -> {tk!r}")
	for ncc, ap in ((NCC_THU, 1), (NCC_NGOAI, 0)):
		if frappe.db.get_value("Supplier", ncc, "doi_soat_pr_pi") != ap:
			frappe.db.set_value("Supplier", ncc, "doi_soat_pr_pi", ap)
			print(f"  Supplier {ncc} · doi_soat_pr_pi -> {ap}")
	_hop_thu_gui_di()


def _hop_thu_gui_di():
	"""Chỉ khi site không gửi email thật: hộp thư giả có địa chỉ người gửi để email vào hàng đợi."""
	if not frappe.are_emails_muted():
		return
	if frappe.db.exists("Email Account", {"enable_outgoing": 1, "default_outgoing": 1}):
		return
	frappe.get_doc(
		{
			"doctype": "Email Account",
			"email_account_name": HOP_THU_DEMO,
			"email_id": "erp.demo@example.com",
			"enable_outgoing": 1,
			"default_outgoing": 1,
			"smtp_server": "smtp.example.invalid",
			"smtp_port": 587,
			"no_smtp_authentication": 1,
			"enable_incoming": 0,
		}
	).insert(ignore_permissions=True)
	print(f"  Email Account {HOP_THU_DEMO!r} (erp.demo@example.com) tạo mới: site tắt gửi email")


def tra_lai():
	tep = _tep_cai_dat_cu()
	if not os.path.exists(tep):
		sys.exit(f"Không có {tep}: chưa chạy demo, hoặc đã trả lại rồi.")
	with open(tep) as f:
		cu = json.load(f)
	print("Trả lại cài đặt:")
	_dat("Buying Settings", cu["Buying Settings"])
	_dat("Accounts Settings", cu["Accounts Settings"])
	cong_ty = cu["Company"]["name"]
	if frappe.db.get_value("Company", cong_ty, "round_off_account") != cu["Company"]["round_off_account"]:
		frappe.db.set_value("Company", cong_ty, "round_off_account", cu["Company"]["round_off_account"])
		frappe.clear_document_cache("Company", cong_ty)
		print(f"  Company {cong_ty} · round_off_account -> {cu['Company']['round_off_account']!r}")
	for ncc, ap in cu["Supplier"].items():
		frappe.db.set_value("Supplier", ncc, "doi_soat_pr_pi", ap)
		print(f"  Supplier {ncc} · doi_soat_pr_pi -> {ap}")
	if frappe.db.exists("Email Account", HOP_THU_DEMO):
		frappe.delete_doc("Email Account", HOP_THU_DEMO, ignore_permissions=True, force=True)
		print(f"  Email Account {HOP_THU_DEMO!r} đã xóa")
	os.remove(tep)


# --- Nhắc Kế toán trưởng ------------------------------------------------------------


def nhac_lech(hoa_don):
	from erpnext.accounts.doi_soat_pr_pi.cau_hinh import cau_hinh
	from erpnext.accounts.doi_soat_pr_pi.nhac_lech import nhac_ke_toan_truong

	pi = frappe.db.get_value(
		"Purchase Invoice", hoa_don, ["docstatus", "trang_thai_doi_soat_pr"], as_dict=True
	)
	if not pi or pi.docstatus != 0 or pi.trang_thai_doi_soat_pr not in ("Lệch", "Chưa đối soát"):
		sys.exit(f"{hoa_don}: cần hóa đơn nháp đang Lệch hoặc Chưa đối soát.")
	so_ngay = cau_hinh().so_ngay_nhac_lech
	frappe.db.set_value(
		"Purchase Invoice", hoa_don, "lech_tu_ngay", add_days(nowdate(), -so_ngay), update_modified=False
	)
	print(f"{hoa_don}: Lệch từ ngày lùi về {so_ngay} ngày trước.")
	print(f"Đã nhắc Kế toán trưởng {nhac_ke_toan_truong()} hóa đơn.")


# --- Dữ liệu ----------------------------------------------------------------------


def dam_bao(doctype, name, fields):
	if not frappe.db.exists(doctype, name):
		frappe.get_doc({"doctype": doctype, **fields}).insert(ignore_permissions=True)


def tao_demo():
	from erpnext.controllers.accounts_controller import get_taxes_and_charges

	cong_ty = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
	abbr = frappe.get_cached_value("Company", cong_ty, "abbr")
	kho = frappe.db.get_value("Warehouse", {"company": cong_ty, "is_group": 0, "name": f"Kho hàng - {abbr}"})
	kho = kho or frappe.db.get_value("Warehouse", {"company": cong_ty, "is_group": 0}, "name")
	thue = get_taxes_and_charges("Purchase Taxes and Charges Template", f"{THUE_10} - {abbr}")

	# Người dùng mẫu để test quyền bằng nút Impersonate (không đặt mật khẩu).
	for email, ten, vai_tro in NGUOI_DUNG:
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": ten,
					"send_welcome_email": 0,
					"roles": [{"role": r} for r in vai_tro],
				}
			).insert(ignore_permissions=True)

	nhom_ncc = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
	for ncc in (NCC_THU, NCC_NGOAI):
		dam_bao("Supplier", ncc, {"supplier_name": ncc, "supplier_group": nhom_ncc})
	dat_cai_dat(cong_ty)

	nhom_hang = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
	for uom in ("Cái", "Hộp"):
		dam_bao("UOM", uom, {"uom_name": uom, "must_be_whole_number": 1})
	for code, ten, hop in (
		("DEMO-VT-01", "Găng tay y tế", None),
		("DEMO-VT-02", "Bơm tiêm 5ml", None),
		("DEMO-VT-05", "Dung dịch sát khuẩn (bán theo Hộp)", 10),
	):
		uoms = [{"uom": "Cái", "conversion_factor": 1}]
		if hop:
			uoms.append({"uom": "Hộp", "conversion_factor": hop})
		dam_bao(
			"Item",
			code,
			{
				"item_code": code,
				"item_name": ten,
				"item_group": nhom_hang,
				"stock_uom": "Cái",
				"is_stock_item": 1,
				"uoms": uoms,
			},
		)
	chi_phi = frappe.db.get_value("Company", cong_ty, "default_expense_account") or frappe.db.get_value(
		"Account", {"company": cong_ty, "is_group": 0, "root_type": "Expense"}, "name"
	)
	dam_bao(
		"Item",
		"DEMO-DV-VC",
		{
			"item_code": "DEMO-DV-VC",
			"item_name": "Cước vận chuyển (dịch vụ)",
			"item_group": nhom_hang,
			"stock_uom": "Cái",
			"is_stock_item": 0,
			"item_defaults": [{"company": cong_ty, "expense_account": chi_phi}],
		},
	)

	def po(rows, ncc=NCC_THU):
		doc = frappe.get_doc(
			{
				"doctype": "Purchase Order",
				"supplier": ncc,
				"company": cong_ty,
				"transaction_date": nowdate(),
				"schedule_date": add_days(nowdate(), 7),
				"items": [
					{
						"item_code": item,
						"qty": qty,
						"rate": rate,
						"warehouse": kho,
						"schedule_date": add_days(nowdate(), 7),
					}
					for item, qty, rate in rows
				],
				"taxes": [dict(t) for t in thue],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc

	def pr(don_mua, ma, qty=None, phi=None):
		from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

		doc = make_purchase_receipt(don_mua.name)
		doc.supplier_delivery_note = f"DEMO-D3-{ma}"
		for d in doc.items:
			if qty is not None:
				d.qty = d.received_qty = qty
		if phi:
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

	ket_qua = []

	def ghi(ma, viec, don_mua, *phieu):
		ket_qua.append((ma, viec, don_mua.name, ", ".join(p.name for p in phieu) or "-"))

	don = po([("DEMO-VT-01", 10, 100000)])
	ghi("A", "Khớp, Nộp, ĐNTT nháp", don, pr(don, "A"))
	don = po([("DEMO-VT-01", 10, 100000)])
	ghi("B", "Lệch số lượng, nhắc, ngoại lệ", don, pr(don, "B"))
	don = po([("DEMO-VT-02", 20, 50000)])
	ghi("C", "Lệch đơn giá, gửi NCC (b2)", don, pr(don, "C"))
	don = po([("DEMO-VT-01", 5, 100000)])
	ghi("D", "Lệch thuế suất", don, pr(don, "D"))
	don = po([("DEMO-VT-01", 10, 100000)])
	ghi("E", "Cao hơn Phiếu nhập", don, pr(don, "E"))
	don = po([("DEMO-VT-02", 12, 50000)])
	ghi("F", "Kho sửa Phiếu nhập (b1)", don, pr(don, "F", qty=10))
	don = po([("DEMO-VT-01", 10, 100000)])
	ghi("G", "Hóa đơn từ Đơn mua tách dòng", don, pr(don, "G", qty=6), pr(don, "G", qty=4))
	don = po([("DEMO-VT-02", 10, 50000)])
	ghi("H", "Không ghép được, ghép tay", don, pr(don, "H", qty=6), pr(don, "H", qty=4))
	don = po([("DEMO-VT-01", 10, 100000)])
	ghi("I", "Hóa đơn từng phần, cước", don, pr(don, "I", phi=50000))
	don = po([("DEMO-VT-02", 10, 50000)], ncc=NCC_NGOAI)
	ghi("J", "NCC ngoài phạm vi", don, pr(don, "J"))
	ghi("K", "Dịch vụ, không Phiếu nhập", po([("DEMO-DV-VC", 1, 200000)]))
	don = po([("DEMO-VT-05", 10, 10000)])
	ghi("L", "Đổi ĐVT trên hóa đơn", don, pr(don, "L"))

	print("\nKịch bản | Việc | Đơn mua hàng | Phiếu nhập mua")
	for dong in ket_qua:
		print(" | ".join(dong))
	print(
		"\nNgười dùng (Impersonate): "
		+ ", ".join(email for email, _ten, _vai_tro in NGUOI_DUNG)
		+ f". Vai trò Kế toán trưởng: {BUYING_SETTINGS['vai_tro_ke_toan_truong']}."
	)


if __name__ == "__main__":
	main()
