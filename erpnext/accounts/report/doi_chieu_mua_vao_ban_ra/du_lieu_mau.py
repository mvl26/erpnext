# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Dữ liệu mẫu cho báo cáo Đối chiếu mua vào - bán ra: mọi trường hợp ghép bán - mua.

Chỉ cho site thử (developer_mode, không phải `miyano`). Chạy:

    bench --site erptest.local execute erpnext.accounts.report.doi_chieu_mua_vao_ban_ra.du_lieu_mau.tao

Khách Himedic, công ty Miyano, tháng 10/2026 (vài chứng từ tháng 09 để có ca "kỳ
trước"). Chạy lại không nhân bản: thấy HĐ NCC `00011069` của DEKA thì dừng.

| Ca | Tình huống                                         | Bảng hiện                                   |
|----|----------------------------------------------------|---------------------------------------------|
| A  | 1 SO 4 dòng → 1 PO → 1 PI → 1 SI (DEKA, 5%)         | 4 dòng khớp đủ hai bên                      |
| B  | 1 dòng bán, NCC xuất 2 HĐ (AN HƯNG 4 + 2)           | 1 dòng bán tách 2 dòng, 2 số HĐ đầu vào     |
| C  | 1 HĐ mua ngày 30/09, khách lấy 2 lần (VietMed 3+1)  | 2 dòng bán chia nhau 1 dòng mua; ngày 30/09 |
| D  | Kỳ trước đã bán 2/5 (HÙNG MINH)                    | Tháng 10 chỉ hiện 3, ghép phần mua còn lại  |
| E  | Bán 5, NCC mới xuất HĐ 3 (VIS)                     | 2 dòng: 3 khớp, 2 trống bên NCC             |
| F  | Đã đặt PO, NCC chưa xuất HĐ (GREENTECH)            | Trống bên NCC                               |
| G  | Bán thẳng, không qua đơn hàng                       | Trống bên NCC                               |
| H  | HĐ mua chưa nhập số HĐ NCC (TCBIO)                 | Số HĐ đầu vào = mã chứng từ ACC-PINV-…      |
| I  | Thuế 8% (ĐẠI XUÂN)                                 | Thuế suất 8%                                |
| J  | 2 dòng cùng mã, giá lẻ (Avanta, 10%)               | Thuế từng dòng cộng lại khớp tổng HĐ        |
| K  | Khách trả lại 20 đĩa của ca A                      | Dòng âm, trống bên NCC                      |
| L  | Hàng không chịu thuế (DEKA, 0%)                    | Thuế suất 0%, tiền thuế 0                   |
| M  | Bán giá x 1,02 thay vì 1,01 (DEKA)                 | Trạng thái "Lệch giá"                       |
| N  | Bán thuế 10%, NCC xuất 8% (ĐẠI XUÂN)               | Trạng thái "Lệch thuế suất"                 |

`tao()` gọi thêm `bo_sung()`: ca M, N và số HĐĐT đã phát hành cho mọi hoá đơn bán
trừ ca G (để thấy cảnh báo "Chưa có số HĐĐT"). `bo_sung()` chạy riêng được, cũng
không nhân bản.
"""

import frappe
from frappe.utils import flt

from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice
from erpnext.controllers.sales_and_purchase_return import make_return_doc
from erpnext.selling.doctype.sales_order.sales_order import make_purchase_order, make_sales_invoice

COMPANY = "Miyano"
CUSTOMER = "Himedic"
WAREHOUSE = "Stores - M"
NGAY_SO = "2026-09-25"
LAI = 1.01  # giá bán = giá mua x 1,01 như file mẫu

HANG = {
	"DCMB-COLUMBIA": ("Môi trường nuôi cấy vi sinh vật (MELAB Columbia Agar + 5% Sheep Blood)", "Đĩa"),
	"DCMB-CHOCOLATE": (
		"Môi trường nuôi cấy vi sinh vật (MELAB Chocolate Sheep Blood Agar + MultiVitox)",
		"Đĩa",
	),
	"DCMB-MACCONKEY": ("Môi trường nuôi cấy vi sinh vật (MELAB MacConkey Agar)", "Đĩa"),
	"DCMB-SABOURAUD": ("Môi trường nuôi cấy vi sinh vật (MELAB Sabouraud Dextrose Agar)", "Đĩa"),
	"DCMB-DILUENT": ("M-53D Diluent (20L/thùng)", "Thùng"),
	"DCMB-SUBSTRATE": ("Substrate solution (4x115ml/hộp)", "Hộp"),
	"DCMB-HCV": ("08498598190 Elecsys Anti-HCV II", "Hộp"),
	"DCMB-TOPPURE": ("TopPURE® Serum Viral DNA/RNA Extraction Kit", "Hộp"),
	"DCMB-PROTIA": ("PROTIA Allergy-Q 64 Food IgE", "Hộp"),
	"DCMB-CON96": ("Cồn 96 độ (Đóng gói: 30 lít/can)", "Lít"),
	"DCMB-ONGSERUM": ("Ống nghiệm Serum (Đóng gói: 100 ống/hộp)", "Hộp"),
	"DCMB-GBS": ("AccuPid GBS Detection Kit", "Bộ"),
	"DCMB-KHAYTHU": ("Khay thử xét nghiệm định tính HBsAg", "Test"),
	"DCMB-PIPETTE": ("Pipet nhựa tiệt trùng 3ml", "Hộp"),
}
NCC = [
	"DEKA",
	"AN HƯNG",
	"VietMed",
	"HÙNG MINH",
	"VIS",
	"GREENTECH",
	"TCBIO",
	"ĐẠI XUÂN",
	"Avanta Diagnostics",
]


def _chan_prod():
	if frappe.local.site == "miyano" or not frappe.conf.developer_mode:
		frappe.throw("Chỉ chạy dữ liệu mẫu trên site thử (developer_mode), không chạy trên prod.")


def tao():
	_chan_prod()
	ncc = {ten: _ncc(ten) for ten in NCC}
	if frappe.db.exists("Purchase Invoice", {"bill_no": "00011069", "supplier": ncc["DEKA"], "docstatus": 1}):
		print("Dữ liệu mẫu đã có - bỏ qua phần A-L.")
		bo_sung()
		return
	for ma, (ten, dvt) in HANG.items():
		_hang(ma, ten, dvt)

	# A — khớp đủ, 4 dòng, 1 PO, 1 PI
	so_a = _so(
		[
			("DCMB-COLUMBIA", 120, 20000),
			("DCMB-CHOCOLATE", 60, 26600),
			("DCMB-MACCONKEY", 20, 27520),
			("DCMB-SABOURAUD", 40, 17600),
		],
		5,
	)
	po_a = _po(so_a, ncc["DEKA"], 5)
	_pi(po_a, "00011069", "2026-10-05")
	si_a = _si(so_a, "2026-10-07")

	# B — 1 dòng bán, 2 HĐ mua
	so_b = _so([("DCMB-DILUENT", 6, 1428571.43)], 5)
	po_b = _po(so_b, ncc["AN HƯNG"], 5)
	_pi(po_b, "00000576", "2026-10-01", {"DCMB-DILUENT": 4})
	_pi(po_b, "00000590", "2026-10-06")
	_si(so_b, "2026-10-07")

	# C — 1 HĐ mua tháng trước, bán 2 lần trong tháng
	so_c = _so([("DCMB-SUBSTRATE", 4, 3714285.75)], 5)
	_pi(_po(so_c, ncc["VietMed"], 5), "00003057", "2026-09-30")
	_si(so_c, "2026-10-09", {"DCMB-SUBSTRATE": 3})
	_si(so_c, "2026-10-15")

	# D — kỳ trước đã bán một phần
	so_d = _so([("DCMB-HCV", 5, 3146784.8)], 5)
	_pi(_po(so_d, ncc["HÙNG MINH"], 5), "00000304", "2026-09-28")
	_si(so_d, "2026-09-29", {"DCMB-HCV": 2})
	_si(so_d, "2026-10-12")

	# E — bán nhiều hơn số đã có HĐ mua
	so_e = _so([("DCMB-TOPPURE", 5, 1714285.71)], 5)
	_pi(_po(so_e, ncc["VIS"], 5), "00001058", "2026-10-05", {"DCMB-TOPPURE": 3})
	_si(so_e, "2026-10-07")

	# F — có PO, NCC chưa xuất HĐ
	so_f = _so([("DCMB-PROTIA", 5, 10095238.09)], 5)
	_po(so_f, ncc["GREENTECH"], 5)
	_si(so_f, "2026-10-13")

	# G — bán thẳng, không qua đơn hàng
	_si_thang([("DCMB-CON96", 60, 35109.52)], "2026-10-13", 5)

	# H — HĐ mua chưa nhập số HĐ NCC
	so_h = _so([("DCMB-ONGSERUM", 24, 104761.9)], 5)
	_pi(_po(so_h, ncc["TCBIO"], 5), None, "2026-10-13")
	_si(so_h, "2026-10-13")

	# I — thuế 8%
	so_i = _so([("DCMB-GBS", 1, 3615741)], 8)
	_pi(_po(so_i, ncc["ĐẠI XUÂN"], 8), "00001180", "2026-10-09")
	_si(so_i, "2026-10-09")

	# J — 2 dòng cùng mã, giá lẻ, thuế 10%
	so_j = _so([("DCMB-KHAYTHU", 90, 26800), ("DCMB-KHAYTHU", 30, 12600.33)], 10)
	_pi(_po(so_j, ncc["Avanta Diagnostics"], 10), "00008995", "2026-10-14")
	_si(so_j, "2026-10-15")

	# K — khách trả lại 20 đĩa Columbia của ca A
	_tra_hang(si_a, "DCMB-COLUMBIA", 20, "2026-10-20")

	# L — không chịu thuế
	so_l = _so([("DCMB-PIPETTE", 10, 150000)], 0)
	_pi(_po(so_l, ncc["DEKA"], 0), "00011120", "2026-10-16")
	_si(so_l, "2026-10-19")

	print("Đã tạo dữ liệu mẫu: khách Himedic, công ty Miyano, tháng 10-2026.")
	bo_sung()


def bo_sung():
	"""Ca M, N và số HĐĐT cho hoá đơn bán tháng 10 của Himedic."""
	_chan_prod()
	ncc = {ten: _ncc(ten) for ten in NCC}
	if not frappe.db.exists("Purchase Invoice", {"bill_no": "00011201", "docstatus": 1}):
		for ma, ten, dvt in (
			("DCMB-GANG", "Găng tay y tế không bột (100 chiếc/hộp)", "Hộp"),
			("DCMB-HBA1C", "Hóa chất xét nghiệm HbA1c (2x60 test/hộp)", "Hộp"),
		):
			HANG[ma] = (ten, dvt)
			_hang(ma, ten, dvt)

		# M — bán lệch tỷ lệ hợp đồng
		so_m = _so([("DCMB-GANG", 50, 68000)], 5, lai=1.02)
		_pi(_po(so_m, ncc["DEKA"], 5), "00011201", "2026-10-16")
		_si(so_m, "2026-10-21")

		# N — bán 10%, NCC xuất 8%
		so_n = _so([("DCMB-HBA1C", 3, 2450000)], 10)
		_pi(_po(so_n, ncc["ĐẠI XUÂN"], 8), "00001215", "2026-10-17")
		_si(so_n, "2026-10-22")
		print("Đã thêm ca M (lệch giá), N (lệch thuế suất).")
	_so_hddt()


def _so_hddt():
	"""HĐĐT 'Đã phát hành' cho các hoá đơn bán tháng 10 chưa có số, trừ hoá đơn bán thẳng (ca G).

	Ghi thẳng bảng (`db_insert`) vì chỉ cần số để báo cáo tra; không qua luồng phát hành.
	"""
	si = frappe.get_all(
		"Sales Invoice",
		filters={
			"customer": CUSTOMER,
			"company": COMPANY,
			"docstatus": 1,
			"posting_date": ("between", ["2026-10-01", "2026-10-31"]),
		},
		fields=["name", "posting_date"],
		order_by="posting_date asc, name asc",
	)
	ban_thang = set(frappe.get_all("Sales Invoice Item", filters={"item_code": "DCMB-CON96"}, pluck="parent"))
	so = 18
	for s in si:
		if s.name in ban_thang:
			continue
		if not frappe.db.exists("Fast EInvoice Document", {"sales_invoice": s.name}):
			doc = frappe.get_doc(
				{
					"doctype": "Fast EInvoice Document",
					"source_doctype": "Sales Invoice",
					"sales_invoice": s.name,
					"customer": CUSTOMER,
					"invoice_type": "Hóa đơn gốc",
					"status": "06 - Đã phát hành",
					"invoice_date": s.posting_date,
					"fast_invoice_no": f"{so:08d}",
					"fast_serial": "1C26TMV",
					"fast_signed_date": s.posting_date,
				}
			)
			doc.set_new_name()
			doc.db_insert()
		so += 1
	print("Đã gán số HĐĐT cho hoá đơn bán tháng 10 (trừ ca G).")


def _tk_vat():
	return frappe.db.get_value("Account", {"company": COMPANY, "account_type": "Tax", "is_group": 0}, "name")


def _thue(rate, mua=False):
	if not rate:
		return []
	row = {
		"charge_type": "On Net Total",
		"account_head": _tk_vat(),
		"rate": rate,
		"description": f"Thuế GTGT {rate}%",
	}
	if mua:
		row.update({"category": "Total", "add_deduct_tax": "Add"})
	return [row]


def _luu(doc):
	doc.flags.ignore_permissions = True
	doc.insert()
	doc.submit()
	return doc


def _ncc(ten):
	if frappe.db.exists("Supplier", ten):
		return ten
	return (
		frappe.get_doc({"doctype": "Supplier", "supplier_name": ten, "supplier_group": "All Supplier Groups"})
		.insert(ignore_permissions=True)
		.name
	)


def _hang(ma, ten, dvt):
	if not frappe.db.exists("UOM", dvt):
		frappe.get_doc({"doctype": "UOM", "uom_name": dvt, "enabled": 1}).insert(ignore_permissions=True)
	if frappe.db.exists("Item", ma):
		return
	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": ma,
			"item_name": ten[:140],
			"description": ten,
			"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups",
			"stock_uom": dvt,
			"is_stock_item": 1,
			"include_item_in_manufacturing": 0,
		}
	).insert(ignore_permissions=True)


def _so(dong, vat, lai=LAI):
	"""SO với `dong = [(mã, SL, giá mua)]`; giá bán = giá mua x `lai` (mặc định 1,01). Giá mua nhớ vào `_gia_mua`."""
	so = frappe.get_doc(
		{
			"doctype": "Sales Order",
			"company": COMPANY,
			"customer": CUSTOMER,
			"transaction_date": NGAY_SO,
			"delivery_date": "2026-10-31",
			"currency": "VND",
			"conversion_rate": 1,
			"items": [
				{
					"item_code": ma,
					"qty": sl,
					"rate": flt(gia * lai, 2),
					"uom": HANG[ma][1],
					"conversion_factor": 1,
					"warehouse": WAREHOUSE,
					"delivery_date": "2026-10-31",
				}
				for ma, sl, gia in dong
			],
			"taxes": _thue(vat),
		}
	)
	_luu(so)
	so._gia_mua = [gia for _ma, _sl, gia in dong]
	return so


def _po(so, supplier, vat):
	po = make_purchase_order(so.name, [{"item_code": it.item_code} for it in so.items])
	po.supplier = supplier
	po.transaction_date = NGAY_SO
	po.schedule_date = "2026-10-31"
	po.taxes = []
	for r in _thue(vat, mua=True):
		po.append("taxes", r)
	gia = {it.name: g for it, g in zip(so.items, so._gia_mua, strict=True)}
	for it in po.items:
		it.rate = gia[it.sales_order_item]
		it.schedule_date = "2026-10-31"
	return _luu(po)


def _pi(po, bill_no, ngay, sl=None):
	pi = make_purchase_invoice(po.name)
	pi.bill_no = bill_no
	pi.bill_date = ngay if bill_no else None
	pi.posting_date = ngay
	pi.set_posting_time = 1
	pi.update_stock = 0
	for it in pi.items:
		if sl and it.item_code in sl:
			it.qty = sl[it.item_code]
	return _luu(pi)


def _si(so, ngay, sl=None):
	si = make_sales_invoice(so.name)
	si.posting_date = ngay
	si.set_posting_time = 1
	si.update_stock = 0
	for it in si.items:
		if sl and it.item_code in sl:
			it.qty = sl[it.item_code]
	return _luu(si)


def _si_thang(dong, ngay, vat):
	return _luu(
		frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": COMPANY,
				"customer": CUSTOMER,
				"posting_date": ngay,
				"set_posting_time": 1,
				"currency": "VND",
				"conversion_rate": 1,
				"items": [
					{
						"item_code": ma,
						"qty": sl,
						"rate": flt(gia * LAI, 2),
						"uom": HANG[ma][1],
						"conversion_factor": 1,
					}
					for ma, sl, gia in dong
				],
				"taxes": _thue(vat),
			}
		)
	)


def _tra_hang(si, item_code, sl, ngay):
	tra = make_return_doc("Sales Invoice", si.name)
	tra.posting_date = ngay
	tra.set_posting_time = 1
	tra.items = [it for it in tra.items if it.item_code == item_code]
	tra.items[0].qty = -sl
	return _luu(tra)
