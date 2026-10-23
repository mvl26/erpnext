"""Kiểm chạy đồng thời S15 (YC5, spec 6.3.8): hai tiến trình cùng tạo đề nghị thanh toán (ĐNTT)
cho MỘT Hóa đơn mua, mỗi bản bằng đủ số tiền hóa đơn. Đúng thiết kế thì chỉ một bản được tạo,
bản kia bị chặn "vượt số tiền hóa đơn".

Test tuần tự không chứng minh được việc này: phải có hai kết nối DB thật chạy song song. Mỗi
tiến trình dựng sẵn ĐNTT, chờ nhau ở một barrier rồi cùng insert; tiến trình vào trước giữ khóa
dòng hóa đơn thêm 2 giây trước khi commit để tiến trình kia chắc chắn phải xếp hàng.

Chạy lại được nhiều lần; mỗi lần tạo một bộ chứng từ mới có tiền tố DEMO-S15 (giữ lại để xem):

	cd ~/frappe-bench/sites
	../env/bin/python ../apps/erpnext/scripts/kiem_dong_thoi_dntt.py --site erpnext.localhost

Script tạm bật đối soát PR ↔ PI (tắt tự tạo ĐNTT) và tạm điền tài khoản làm tròn nếu công ty
chưa có, rồi trả lại như cũ. Mã thoát 0 khi đúng một bản ĐNTT được tạo.

TỪ CHỐI chạy trên site `miyano` (production).
"""

import argparse
import multiprocessing
import os
import sys
import time

import frappe
from frappe.utils import add_days, nowdate

SITE_PRODUCTION = "miyano"
CAI_DAT = {"bat_doi_soat_pr_pi": 1, "pham_vi_doi_soat": "Mọi nhà cung cấp", "tao_dntt_khi_nop_hoa_don": 0}


def _ket_noi(site, sites_path):
	frappe.init(site=site, sites_path=sites_path)
	frappe.connect()
	frappe.set_user("Administrator")


def _dung_hoa_don():
	"""PO → Phiếu nhập → Hóa đơn mua đã Nộp, đã commit để tiến trình khác thấy."""
	company = frappe.db.get_value("Company", {}, "name")
	warehouse = frappe.db.get_value("Warehouse", {"company": company, "is_group": 0}, "name")
	ncc = frappe.db.get_value("Supplier", {"supplier_name": "DEMO-S15 NCC"}) or (
		frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": "DEMO-S15 NCC",
				"supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"),
			}
		)
		.insert()
		.name
	)
	item = frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": f"DEMO-S15-{frappe.generate_hash(length=6)}",
			"item_name": "DEMO-S15 vật tư",
			"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
			"stock_uom": frappe.db.get_value("UOM", {}, "name"),
			"is_stock_item": 1,
		}
	).insert()

	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
	from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice

	po = frappe.get_doc(
		{
			"doctype": "Purchase Order",
			"supplier": ncc,
			"company": company,
			"transaction_date": nowdate(),
			"schedule_date": add_days(nowdate(), 7),
			"items": [
				{
					"item_code": item.name,
					"qty": 10,
					"rate": 100000,
					"warehouse": warehouse,
					"schedule_date": add_days(nowdate(), 7),
				}
			],
		}
	).insert()
	po.submit()
	pr = make_purchase_receipt(po.name)
	pr.insert()
	pr.submit()
	pi = make_purchase_invoice(pr.name)
	pi.bill_no = f"DEMO-S15-{frappe.generate_hash(length=6)}"
	pi.bill_date = nowdate()
	pi.insert()
	pi.submit()
	frappe.db.commit()
	return pi


def _tao_dntt(site, sites_path, pi_name, so_tien, barrier, ket_qua):
	_ket_noi(site, sites_path)
	try:
		pi = frappe.get_doc("Purchase Invoice", pi_name)
		dntt = frappe.get_doc(
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
		)
		barrier.wait()
		bat_dau = time.monotonic()
		dntt.insert(ignore_permissions=True)
		time.sleep(2)
		frappe.db.commit()
		ket_qua.put(("tạo được", dntt.name, round(time.monotonic() - bat_dau, 1)))
	except Exception as e:
		frappe.db.rollback()
		ket_qua.put(("bị chặn", frappe.utils.strip_html(str(e))[:160], None))
	finally:
		frappe.destroy()


def main():
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--site", required=True)
	args = parser.parse_args()
	if args.site == SITE_PRODUCTION:
		sys.exit("Từ chối: không chạy trên site production.")
	sites_path = os.getcwd()

	_ket_noi(args.site, sites_path)
	cu = {f: frappe.db.get_single_value("Buying Settings", f) for f in CAI_DAT}
	company = frappe.db.get_value("Company", {}, "name")
	lam_tron_cu = frappe.db.get_value("Company", company, ["round_off_account", "round_off_cost_center"])
	dat = False
	try:
		frappe.db.set_single_value("Buying Settings", CAI_DAT)
		if not lam_tron_cu[0]:
			frappe.db.set_value(
				"Company",
				company,
				{
					"round_off_account": frappe.db.get_value(
						"Account", {"company": company, "is_group": 0, "root_type": "Expense"}
					),
					"round_off_cost_center": frappe.get_cached_value("Company", company, "cost_center"),
				},
			)
		frappe.db.commit()
		pi = _dung_hoa_don()
		so_tien = pi.rounded_total or pi.grand_total
		print(f"Hóa đơn {pi.name}, số tiền {so_tien:,.0f}. Hai tiến trình cùng tạo ĐNTT {so_tien:,.0f}...")

		ctx = multiprocessing.get_context("spawn")
		barrier = ctx.Barrier(2)
		ket_qua = ctx.Queue()
		tien_trinh = [
			ctx.Process(target=_tao_dntt, args=(args.site, sites_path, pi.name, so_tien, barrier, ket_qua))
			for _i in range(2)
		]
		for p in tien_trinh:
			p.start()
		for p in tien_trinh:
			p.join(120)
		dong = [ket_qua.get(timeout=5) for _p in tien_trinh]
		for trang_thai, chi_tiet, giay in dong:
			print(f"  - {trang_thai}: {chi_tiet}" + (f" ({giay} giây)" if giay is not None else ""))

		frappe.db.rollback()
		con_lai = frappe.get_all(
			"Payment Request",
			filters={
				"reference_doctype": "Purchase Invoice",
				"reference_name": pi.name,
				"docstatus": ("<", 2),
			},
			pluck="name",
		)
		dat = len(con_lai) == 1 and sorted(t for t, _c, _g in dong) == ["bị chặn", "tạo được"]
		print(f"ĐNTT còn trong DB: {con_lai}. Kết quả: {'ĐẠT' if dat else 'KHÔNG ĐẠT'}")
	finally:
		frappe.db.set_single_value("Buying Settings", cu)
		if not lam_tron_cu[0]:
			frappe.db.set_value(
				"Company", company, {"round_off_account": None, "round_off_cost_center": lam_tron_cu[1]}
			)
		frappe.db.commit()
		frappe.destroy()
	sys.exit(0 if dat else 1)


if __name__ == "__main__":
	main()
