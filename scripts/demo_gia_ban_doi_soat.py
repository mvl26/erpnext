"""Dữ liệu demo cho kiểm giá bán theo hệ số khách hàng (BA12) và báo trước đổi giá (YC4).

Chạy từ thư mục `sites` của bench:

	cd ~/frappe-bench/sites
	../env/bin/python ../apps/erpnext/scripts/demo_gia_ban_doi_soat.py --site erpnext.localhost

- Mọi bản ghi có tiền tố DEMO; chạy lại nhiều lần an toàn: giá demo và chứng từ demo còn
  NHÁP được dựng lại từ đầu, chứng từ demo đã Submit giữ nguyên — trừ báo giá NCC demo đã
  Submit: chuyển Stopped để giá mua luôn bắt đầu từ HĐ nguyên tắc (A01).
- TỪ CHỐI chạy trên site `miyano` (production).
- Bật "Kiểm giá bán" trên site demo.
- Chỉ tạo chứng từ NHÁP; người xem tự Submit để thấy cảnh báo, chặn và email giá mới.

Kịch bản (nghiệm thu BA12):
  A01  DEMO-VT-01: giá HĐ nguyên tắc 123.457 (DEMO Mua - Vietmed), Himedic 1,01 -> đề xuất 124.692
  A02  Supplier Quotation nháp DEMO-Vietmed 125.000 cho DEMO-VT-01: Submit -> đề xuất 126.250
  A03  DEMO-VT-01 cũng có giá HĐ của DEMO-Hùng Minh 118.000: đổi NCC dự kiến trên dòng SO
  A04  SO Himedic thứ hai bán DEMO-VT-01 giá 125.000 (lệch +308) -> Submit cần lý do
  A05  "DEMO Bảng giá Himedic" có DEMO-VT-01 = 120.000 khác đề xuất -> Submit cần 3 thông tin
  A06  SO Himedic có email người đặt đơn himedic.demo@example.com -> Submit gửi thông báo giá mới
  A07  DEMO-Khách lẻ không có hệ số -> không kiểm
  A08  Báo cáo "Doi Soat Gia Mua Gia Ban"
  R08  DEMO-VT-03 không có giá mua (có trong bảng giá Himedic 30.000: chỉ cần lý do)
  Q2   SO Hoàng Lâm có DEMO-VT-01, mặt hàng chưa có trong bảng giá Hoàng Lâm -> khác bảng
       giá, Submit cần 3 thông tin; email ghi giá cũ "Chưa có trong bảng giá"
  +    DEMO-VT-05 bán theo Hộp (10 Cái); DEMO-Hoàng Lâm hệ số 1,05
  +    DEMO-KH B không có hệ số theo khách, có hệ số theo mặt hàng DEMO-VT-01 = 1,08
  +    DEMO-Himedic có người liên hệ chính email himedic.demo@example.com: SO tạo trên form
       tự có email người đặt đơn (A06)

YC4 (báo trước khi đổi giá): "DEMO Bảng giá Himedic" bật Báo trước 7 ngày, bảng giá chờ
"DEMO Bảng giá Himedic - Chờ báo", email demo himedic.demo@example.com; một nháp chờ gửi
DEMO-VT-02 52.000 áp từ D+5 (gửi hôm nay sẽ là Báo gấp, thiếu 2 ngày).
"""

import argparse
import os
import sys

import frappe
from frappe.utils import add_days, getdate, nowdate

SITE_PRODUCTION = "miyano"
HIMEDIC = "DEMO Bảng giá Himedic"
CHO_HIMEDIC = "DEMO Bảng giá Himedic - Chờ báo"
MUA_VIETMED = "DEMO Mua - Vietmed"
MUA_HUNG_MINH = "DEMO Mua - Hùng Minh"
HOANG_LAM = "DEMO Bảng giá Hoàng Lâm"
BAN_LE = "DEMO Bảng giá bán lẻ"
BANG_GIA_DEMO = (MUA_VIETMED, MUA_HUNG_MINH, HIMEDIC, CHO_HIMEDIC, HOANG_LAM, BAN_LE)
EMAIL_DEMO = "himedic.demo@example.com"
# Chỉ dùng vai trò có sẵn (không tạo vai trò): Giám đốc = Sales Manager, nên nhân viên không có vai trò này.
VAI_TRO_GIAM_DOC = "Sales Manager"
NHOM_NHAN_VIEN = ["Sales User", "Sales Master Manager", "Item Manager", "Purchase User"]
NGUOI_DUNG = (
	("demo.nhanvien@example.com", "DEMO Nhân viên", NHOM_NHAN_VIEN),
	("demo.giamdoc@example.com", "DEMO Giám đốc", [*NHOM_NHAN_VIEN, VAI_TRO_GIAM_DOC]),
)
KHO = None
CONG_TY = None


def main():
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--site", required=True)
	args = parser.parse_args()
	if args.site == SITE_PRODUCTION:
		sys.exit("Từ chối: không tạo dữ liệu demo trên site production.")

	frappe.init(site=args.site, sites_path=os.getcwd())
	frappe.connect()
	try:
		frappe.set_user("Administrator")
		tao_demo()
		frappe.db.commit()
	finally:
		frappe.destroy()


def tao_demo():
	global KHO, CONG_TY
	CONG_TY = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
	KHO = frappe.db.get_value("Warehouse", {"company": CONG_TY, "is_group": 0}, "name")
	d = getdate(nowdate())

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

	frappe.db.set_single_value(
		"Selling Settings",
		{
			"bat_kiem_gia_ban": 1,
			"bat_buoc_dinh_kem_van_ban_gia": 0,
			"vai_tro_sua_ty_le_lai": VAI_TRO_GIAM_DOC,
		},
	)
	frappe.clear_document_cache("Selling Settings", "Selling Settings")
	# Như production (P7): chứng từ không tự thêm/ghi đè giá vào bảng giá.
	frappe.db.set_single_value(
		"Stock Settings", {"auto_insert_price_list_rate_if_missing": 0, "update_existing_price_list_rate": 0}
	)
	frappe.clear_document_cache("Stock Settings", "Stock Settings")

	for uom in ("Cái", "Hộp"):
		dam_bao("UOM", uom, {"uom_name": uom, "must_be_whole_number": 1})
	nhom_ncc = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
	for ncc in ("DEMO-Vietmed", "DEMO-Hùng Minh"):
		dam_bao("Supplier", ncc, {"supplier_name": ncc, "supplier_group": nhom_ncc})

	for ten, mua in (
		(MUA_VIETMED, 1),
		(MUA_HUNG_MINH, 1),
		(HIMEDIC, 0),
		(CHO_HIMEDIC, 0),
		(HOANG_LAM, 0),
		(BAN_LE, 0),
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

	for code, ten, ncc_mac_dinh, hop in (
		("DEMO-VT-01", "Găng tay y tế", "DEMO-Vietmed", None),
		("DEMO-VT-02", "Bơm tiêm 5ml", "DEMO-Hùng Minh", None),
		("DEMO-VT-03", "Bông gạc", "DEMO-Vietmed", None),
		("DEMO-VT-05", "Dung dịch sát khuẩn (bán theo Hộp)", "DEMO-Vietmed", 10),
	):
		dam_bao("Item", code, mat_hang(code, ten, ncc_mac_dinh, hop))
		frappe.db.set_value("Item Supplier", {"parent": code, "parenttype": "Item"}, "is_default", 0)
		if not frappe.db.exists("Item Supplier", {"parent": code, "supplier": ncc_mac_dinh}):
			item = frappe.get_doc("Item", code)
			item.append("supplier_items", {"supplier": ncc_mac_dinh})
			item.save(ignore_permissions=True)
		frappe.db.set_value("Item Supplier", {"parent": code, "supplier": ncc_mac_dinh}, "is_default", 1)

	# Sau mặt hàng: hệ số theo mặt hàng của DEMO-KH B trỏ tới DEMO-VT-01.
	nhom_khach = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
	khu_vuc = frappe.db.get_value("Territory", {"is_group": 0}, "name")
	tu_ngay = min(getdate("2026-10-01"), add_days(d, -30))
	for ten, he_so, hop_dong, bang_gia, theo_hang in (
		("DEMO-Himedic", 1.01, "HĐNT-HIMEDIC-2026", HIMEDIC, None),
		("DEMO-Hoàng Lâm", 1.05, "HĐNT-HOANGLAM-2026", HOANG_LAM, None),
		("DEMO-KH B", None, None, None, ("DEMO-VT-01", 1.08)),
		("DEMO-Khách lẻ", None, None, BAN_LE, None),
	):
		dam_bao("Customer", ten, khach(ten, nhom_khach, khu_vuc))
		doc = frappe.get_doc("Customer", ten)
		doc.default_price_list = bang_gia
		doc.set("he_so_gia_ban", [])
		doc.set("he_so_theo_mat_hang", [])
		if he_so:
			doc.append("he_so_gia_ban", {"he_so": he_so, "so_hop_dong": hop_dong, "tu_ngay": tu_ngay})
		if theo_hang:
			doc.append(
				"he_so_theo_mat_hang", {"item_code": theo_hang[0], "he_so": theo_hang[1], "tu_ngay": tu_ngay}
			)
		doc.save(ignore_permissions=True)

	# Người liên hệ chính của Himedic: chọn khách trên form SO là có email người đặt đơn (A06).
	if not frappe.db.exists("Contact", {"email_id": EMAIL_DEMO}):
		frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": "DEMO Himedic đặt hàng",
				"is_primary_contact": 1,
				"email_ids": [{"email_id": EMAIL_DEMO, "is_primary": 1}],
				"links": [{"link_doctype": "Customer", "link_name": "DEMO-Himedic"}],
			}
		).insert(ignore_permissions=True)

	don_demo_cu()

	for bang, code, gia, ngay, ncc in (
		(MUA_VIETMED, "DEMO-VT-01", 123457, -60, "DEMO-Vietmed"),  # A01
		(MUA_HUNG_MINH, "DEMO-VT-01", 118000, -60, "DEMO-Hùng Minh"),  # A03
		(MUA_HUNG_MINH, "DEMO-VT-02", 50000, -60, "DEMO-Hùng Minh"),
		(MUA_VIETMED, "DEMO-VT-05", 10000, -60, "DEMO-Vietmed"),
		(HIMEDIC, "DEMO-VT-01", 120000, -60, None),  # A05: khác đề xuất 124.692
		(HIMEDIC, "DEMO-VT-02", 50500, -60, None),
		(HIMEDIC, "DEMO-VT-05", 10100, -60, None),
		(HIMEDIC, "DEMO-VT-03", 30000, -60, None),  # R08: có trong bảng giá, chỉ thiếu giá mua
		(HOANG_LAM, "DEMO-VT-02", 52500, -60, None),
		(CHO_HIMEDIC, "DEMO-VT-02", 52000, 5, None),  # YC4: nháp chờ gửi
	):
		gia_item(bang, code, gia, add_days(d, ngay), ncc)

	frappe.db.set_value(
		"Price List",
		HIMEDIC,
		{
			"bao_truoc_khi_doi_gia": 1,
			"so_ngay_bao_truoc": 7,
			"bang_gia_cho": CHO_HIMEDIC,
			"email_nhan_thong_bao": EMAIL_DEMO,
		},
	)
	frappe.db.set_value("Item Price", {"price_list": CHO_HIMEDIC}, "trang_thai_thong_bao", "Chờ gửi")

	frappe.get_doc(
		{
			"doctype": "Supplier Quotation",
			"supplier": "DEMO-Vietmed",
			"company": CONG_TY,
			"transaction_date": d,
			"valid_till": add_days(d, 30),
			"items": [
				{"item_code": "DEMO-VT-01", "qty": 100, "uom": "Cái", "rate": 125000, "warehouse": KHO}
			],
		}
	).insert(ignore_permissions=True)  # A02: Submit để thấy giá báo giá đợt

	so_nhap(
		"DEMO-Himedic",
		d,
		[
			("DEMO-VT-01", 10, "Cái", 124692),
			("DEMO-VT-02", 20, "Cái", 50500),
			("DEMO-VT-05", 2, "Hộp", 101000),
		],
		contact_email=EMAIL_DEMO,
	)  # A01, A05, A06
	so_nhap(
		"DEMO-Himedic", d, [("DEMO-VT-01", 5, "Cái", 125000), ("DEMO-VT-03", 3, "Cái", 30000)]
	)  # A04, R08
	so_nhap(
		"DEMO-Hoàng Lâm",
		d,
		[("DEMO-VT-02", 10, "Cái", 52500), ("DEMO-VT-01", 2, "Cái", 129630)],
		selling_price_list=HOANG_LAM,
	)  # Q2: DEMO-VT-01 chưa có trong bảng giá Hoàng Lâm
	so_nhap("DEMO-Khách lẻ", d, [("DEMO-VT-01", 1, "Cái", 150000)], selling_price_list=BAN_LE)  # A07

	in_ket_qua()


def don_demo_cu():
	"""Xóa giá demo và chứng từ demo còn nháp để kịch bản luôn đúng như hướng dẫn."""
	for name in frappe.get_all(
		"Sales Order", filters={"customer": ("like", "DEMO-%"), "docstatus": 0}, pluck="name"
	):
		frappe.delete_doc("Sales Order", name, ignore_permissions=True, force=True)
	for name in frappe.get_all(
		"Supplier Quotation", filters={"supplier": ("like", "DEMO-%"), "docstatus": 0}, pluck="name"
	):
		frappe.delete_doc("Supplier Quotation", name, ignore_permissions=True, force=True)
	# Báo giá đã Submit ở lần test trước vẫn là báo giá đợt còn hiệu lực, che giá HĐ nguyên tắc.
	# Không Hủy được khi đã có Đơn mua lập từ báo giá; Stopped thì kiểm giá bỏ qua (D07).
	for name in frappe.get_all(
		"Supplier Quotation",
		filters={"supplier": ("like", "DEMO-%"), "docstatus": 1, "status": ("!=", "Stopped")},
		pluck="name",
	):
		frappe.db.set_value("Supplier Quotation", name, "status", "Stopped")
	for name in frappe.get_all("Item Price", filters={"price_list": ("in", BANG_GIA_DEMO)}, pluck="name"):
		frappe.delete_doc("Item Price", name, ignore_permissions=True, force=True)


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
		"supplier_items": [{"supplier": ncc_mac_dinh, "is_default": 1}],
	}
	if hop:
		data["uoms"].append({"uom": "Hộp", "conversion_factor": hop})
	return data


def gia_item(bang, code, gia, ngay, ncc):
	ip = frappe.get_doc(
		{
			"doctype": "Item Price",
			"price_list": bang,
			"item_code": code,
			"uom": "Cái",
			"price_list_rate": gia,
			"valid_from": ngay,
			"supplier": ncc,
			"currency": "VND",
		}
	)
	# Gieo dữ liệu demo: được ghi thẳng vào bảng giá có báo trước.
	ip.flags.tu_thong_bao_doi_gia = True
	ip.insert(ignore_permissions=True)


def so_nhap(customer, ngay, dong, **fields):
	frappe.get_doc(
		{
			"doctype": "Sales Order",
			"customer": customer,
			"company": CONG_TY,
			"transaction_date": ngay,
			"delivery_date": add_days(ngay, 7),
			"selling_price_list": HIMEDIC,
			"ignore_pricing_rule": 1,
			"order_type": "Sales",
			"items": [
				{
					"item_code": code,
					"qty": qty,
					"uom": uom,
					"rate": rate,
					"warehouse": KHO,
					"delivery_date": add_days(ngay, 7),
				}
				for code, qty, uom, rate in dong
			],
			**fields,
		}
	).insert(ignore_permissions=True)


def in_ket_qua():
	for so in frappe.get_all(
		"Sales Order",
		filters={"customer": ("like", "DEMO-%"), "docstatus": 0},
		pluck="name",
		order_by="creation",
	):
		doc = frappe.get_doc("Sales Order", so)
		print(f"{doc.name} ({doc.customer})")
		for d in doc.items:
			print(
				f"  {d.idx}. {d.item_code} {d.uom}: {d.rate} | mua {d.gia_mua} ({d.nguon_gia_mua}) x {d.he_so_gia_ban}"
				f" = {d.gia_de_xuat} | {d.trang_thai_gia or 'không kiểm'}"
				+ (
					(
						" | chưa có trong bảng giá"
						if d.ngoai_bang_gia
						else f" | khác bảng giá {d.gia_bang_gia}"
					)
					if d.khac_bang_gia
					else ""
				)
				+ (" | chờ khách chấp thuận" if d.cho_chap_thuan else "")
			)


if __name__ == "__main__":
	main()
