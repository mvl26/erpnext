"""Dữ liệu demo cho kiểm giá bán theo % lãi (spec 2026-10-21, mục 9 và 13 — Đợt 1).

Chạy từ thư mục `sites` của bench:

	cd ~/frappe-bench/sites
	../env/bin/python ../apps/erpnext/scripts/demo_gia_ban_doi_soat.py --site erpnext.localhost [--che-do Chặn]

- Mọi bản ghi có tiền tố DEMO-; chạy lại nhiều lần an toàn (bản ghi đã có thì giữ nguyên).
- TỪ CHỐI chạy trên site `miyano` (production).
- Bật "Kiểm giá bán" trên site demo, chế độ theo `--che-do` (mặc định "Chỉ ghi nhận").
- Chỉ tạo chứng từ NHÁP; người xem tự Submit để thấy chặn/duyệt và ghi giá mua.

Kịch bản (mục 9 của spec, phần thuộc Đợt 1):
  1. Himedic 1%, giá NCC mặc định, khớp                  -> SO DEMO Himedic, dòng DEMO-VT-01
  2. Himedic, giá lệch, chờ duyệt                        -> dòng DEMO-VT-02 (thấp hơn 520)
  3. Khách DEMO-KH B có % riêng 2%                         -> SO DEMO KH B
  +  Chưa xác định giá gốc (2 NCC cùng ngày, không có giá) -> DEMO-VT-03, DEMO-VT-04
  +  Bán theo Hộp (quy đổi 10 Cái)                         -> DEMO-VT-05
  +  Báo giá NCC mới (Submit để ghi vào bảng giá mua)       -> Supplier Quotation DEMO-Vietmed
"""

import argparse
import os
import sys

import frappe
from frappe.utils import add_days, getdate, nowdate

SITE_PRODUCTION = "miyano"
VAI_TRO_GIAM_DOC = "DEMO Giám đốc"
VAI_TRO_DUYET = "DEMO Duyệt giá"
NHOM_NHAN_VIEN = ["Sales User", "Sales Manager", "Sales Master Manager", "Item Manager", "Purchase User"]
NGUOI_DUNG = (
	("demo.nhanvien@example.com", "DEMO Nhân viên", NHOM_NHAN_VIEN),
	("demo.duyet@example.com", "DEMO Người duyệt", ["Sales User", VAI_TRO_DUYET]),
	("demo.giamdoc@example.com", "DEMO Giám đốc", [*NHOM_NHAN_VIEN, VAI_TRO_GIAM_DOC]),
)
KHO = None
CONG_TY = None


def main():
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--site", required=True)
	parser.add_argument("--che-do", default="Chỉ ghi nhận", choices=["Chỉ ghi nhận", "Chặn"])
	args = parser.parse_args()
	if args.site == SITE_PRODUCTION:
		sys.exit("Từ chối: không tạo dữ liệu demo trên site production.")

	frappe.init(site=args.site, sites_path=os.getcwd())
	frappe.connect()
	try:
		frappe.set_user("Administrator")
		tao_demo(args.che_do)
		frappe.db.commit()
	finally:
		frappe.destroy()


def tao_demo(che_do):
	global KHO, CONG_TY
	CONG_TY = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
	KHO = frappe.db.get_value("Warehouse", {"company": CONG_TY, "is_group": 0}, "name")
	d = getdate(nowdate())

	# Vai trò và người dùng mẫu để test quyền bằng nút Impersonate (không đặt mật khẩu).
	for vai_tro in (VAI_TRO_GIAM_DOC, VAI_TRO_DUYET):
		dam_bao("Role", vai_tro, {"role_name": vai_tro, "desk_access": 1})
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

	frappe.db.set_single_value(
		"Selling Settings",
		{
			"bat_kiem_gia_ban": 1,
			"che_do_kiem_gia": che_do,
			"ty_le_lai_mac_dinh": 1,
			"vai_tro_sua_ty_le_lai": VAI_TRO_GIAM_DOC,
			"vai_tro_duyet_gia_lech": VAI_TRO_DUYET,
		},
	)
	frappe.clear_document_cache("Selling Settings", "Selling Settings")

	for uom in ("Cái", "Hộp"):
		dam_bao("UOM", uom, {"uom_name": uom, "must_be_whole_number": 1})
	nhom_ncc = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
	for ncc in ("DEMO-Vietmed", "DEMO-Hùng Minh"):
		dam_bao("Supplier", ncc, {"supplier_name": ncc, "supplier_group": nhom_ncc})
	nhom_khach = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
	khu_vuc = frappe.db.get_value("Territory", {"is_group": 0}, "name")
	dam_bao("Customer", "DEMO-Himedic", khach("DEMO-Himedic", nhom_khach, khu_vuc))
	dam_bao("Customer", "DEMO-KH B", khach("DEMO-KH B", nhom_khach, khu_vuc))
	# Đặt lại mỗi lần chạy: khách có thể đã có từ demo cũ mà chưa có % riêng.
	frappe.db.set_value("Customer", "DEMO-KH B", {"ty_le_lai_rieng": 1, "ty_le_lai": 2})

	for code, ten, ncc_mac_dinh, hop in (
		("DEMO-VT-01", "Găng tay y tế (G1, G17, G21)", "DEMO-Vietmed", None),
		("DEMO-VT-02", "Bơm tiêm 5ml (G18)", None, None),
		("DEMO-VT-03", "Bông gạc (G19)", None, None),
		("DEMO-VT-04", "Khẩu trang (G20)", None, None),
		("DEMO-VT-05", "Dung dịch sát khuẩn (G6, G11)", "DEMO-Vietmed", 10),
	):
		dam_bao("Item", code, mat_hang(code, ten, ncc_mac_dinh, hop))

	for ten, mua in (
		("DEMO Mua - Vietmed", 1),
		("DEMO Mua - Hùng Minh", 1),
		("DEMO Bảng giá mua", 1),
		("DEMO Bảng giá Himedic", 0),
	):
		dam_bao(
			"Price List",
			ten,
			{
				"price_list_name": ten,
				"buying": mua,
				"selling": 0 if mua else 1,
				"currency": "VND",
				"enabled": 1,
			},
		)
	frappe.db.set_value("Supplier", "DEMO-Vietmed", "default_price_list", "DEMO Mua - Vietmed")
	frappe.db.set_value("Supplier", "DEMO-Hùng Minh", "default_price_list", "DEMO Mua - Hùng Minh")

	V, H, M, HM = "DEMO Mua - Vietmed", "DEMO Mua - Hùng Minh", "DEMO Bảng giá mua", "DEMO Bảng giá Himedic"
	for bang, code, gia, ngay, ncc in (
		(V, "DEMO-VT-01", 100000, -60, "DEMO-Vietmed"),
		(V, "DEMO-VT-01", 105000, 5, "DEMO-Vietmed"),  # tương lai (G21)
		(M, "DEMO-VT-01", 98000, -10, None),  # mới hơn nhưng không phải NCC mặc định (G17)
		(H, "DEMO-VT-02", 50000, -90, "DEMO-Hùng Minh"),
		(M, "DEMO-VT-02", 52000, -20, None),  # mới nhất (G18)
		(V, "DEMO-VT-03", 20000, -15, "DEMO-Vietmed"),
		(H, "DEMO-VT-03", 21000, -15, "DEMO-Hùng Minh"),  # trùng ngày, khác giá (G19)
		(V, "DEMO-VT-05", 12345.67, -30, "DEMO-Vietmed"),
		(HM, "DEMO-VT-01", 101000, -60, None),
		(HM, "DEMO-VT-02", 52000, -30, None),
		(HM, "DEMO-VT-03", 20500, -30, None),
		(HM, "DEMO-VT-04", 3000, -30, None),
		(HM, "DEMO-VT-05", 12469.1267, -30, None),
	):
		gia_item(bang, code, gia, add_days(d, ngay), ncc)

	so_nhap(
		"DEMO-Himedic",
		HM,
		d,
		[
			("DEMO-VT-01", 10, "Cái"),
			("DEMO-VT-02", 20, "Cái"),
			("DEMO-VT-03", 5, "Cái"),
			("DEMO-VT-04", 100, "Cái"),
			("DEMO-VT-05", 2, "Hộp"),
		],
		ly_do="Demo: giá theo hợp đồng cũ, chờ duyệt",
	)
	so_nhap("DEMO-KH B", HM, d, [("DEMO-VT-01", 1, "Cái")], rate={"DEMO-VT-01": 102000})

	if not frappe.db.exists("Supplier Quotation", {"supplier": "DEMO-Vietmed", "docstatus": 0}):
		frappe.get_doc(
			{
				"doctype": "Supplier Quotation",
				"supplier": "DEMO-Vietmed",
				"company": CONG_TY,
				"transaction_date": d,
				"buying_price_list": V,
				"items": [
					{"item_code": "DEMO-VT-01", "qty": 100, "uom": "Cái", "rate": 107000, "warehouse": KHO}
				],
			}
		).insert(ignore_permissions=True)

	in_ket_qua()


def dam_bao(doctype, name, data):
	if not frappe.db.exists(doctype, name):
		frappe.get_doc({"doctype": doctype, **data}).insert(ignore_permissions=True)


def khach(ten, nhom, khu_vuc, **fields):
	return {
		"customer_name": ten,
		"customer_type": "Company",
		"customer_group": nhom,
		"territory": khu_vuc,
		**fields,
	}


def mat_hang(code, ten, ncc_mac_dinh, hop):
	data = {
		"item_code": code,
		"item_name": ten,
		"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name"),
		"stock_uom": "Cái",
		"is_stock_item": 1,
		"uoms": [{"uom": "Cái", "conversion_factor": 1}],
		"item_defaults": [{"company": CONG_TY, "default_warehouse": KHO}],
	}
	if hop:
		data["uoms"].append({"uom": "Hộp", "conversion_factor": hop})
	if ncc_mac_dinh:
		data["supplier_items"] = [{"supplier": ncc_mac_dinh, "is_default": 1}]
	return data


def gia_item(bang, code, gia, ngay, ncc):
	"""Dòng giá demo nhận ra theo (bảng giá, mặt hàng, giá). Chạy lại ngày khác thì dời ngày
	hiệu lực theo hôm nay, để kịch bản (vd. giá tương lai D+5) luôn đúng như hướng dẫn."""
	f = {"price_list": bang, "item_code": code, "uom": "Cái", "price_list_rate": gia}
	name = frappe.db.get_value("Item Price", f)
	if name:
		frappe.db.set_value("Item Price", name, "valid_from", ngay)
		return
	frappe.get_doc(
		{"doctype": "Item Price", **f, "valid_from": ngay, "supplier": ncc, "currency": "VND"}
	).insert(ignore_permissions=True)


def so_nhap(customer, price_list, ngay, dong, ly_do=None, rate=None):
	if frappe.db.exists("Sales Order", {"customer": customer, "docstatus": 0}):
		return
	so = frappe.get_doc(
		{
			"doctype": "Sales Order",
			"customer": customer,
			"company": CONG_TY,
			"transaction_date": ngay,
			"delivery_date": add_days(ngay, 7),
			"selling_price_list": price_list,
			"ly_do_lech_gia": ly_do,
			"items": [
				{
					"item_code": code,
					"qty": qty,
					"uom": uom,
					"warehouse": KHO,
					"delivery_date": add_days(ngay, 7),
					**({"rate": (rate or {})[code]} if code in (rate or {}) else {}),
				}
				for code, qty, uom in dong
			],
		}
	)
	so.insert(ignore_permissions=True)


def in_ket_qua():
	for so in frappe.get_all(
		"Sales Order", filters={"customer": ("like", "DEMO-%"), "docstatus": 0}, pluck="name"
	):
		doc = frappe.get_doc("Sales Order", so)
		doc.save(ignore_permissions=True)  # tính lại theo dữ liệu mới nhất
		print(f"{doc.name} ({doc.customer})")
		for d in doc.items:
			print(f"  {d.idx}. {d.item_code} {d.uom}: {d.rate} | chuẩn {d.gia_chuan} | {d.trang_thai_gia}")


if __name__ == "__main__":
	main()
