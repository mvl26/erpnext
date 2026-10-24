"""Dữ liệu demo cho hợp đồng khung và tiếp nhận hóa đơn NCC (Đợt 4 - FRD-MAP-01 phần 1).

Dùng cùng `docs/HDKT_Dot4_Tiep_nhan_hoa_don_NCC.md`. Chạy từ thư mục `sites` của bench:

	cd ~/frappe-bench/sites
	../env/bin/python ../apps/erpnext/scripts/demo_tiep_nhan_hoa_don.py --site erpnext.localhost

Trả cài đặt về như trước lần chạy đầu:

	../env/bin/python ../apps/erpnext/scripts/demo_tiep_nhan_hoa_don.py --site erpnext.localhost --tra-lai

- TỪ CHỐI chạy trên site `miyano` (production).
- Mỗi lần chạy tạo một NCC demo MỚI (`DEMO-D4 NCC 01`, `02`...; MST riêng) cùng hai hợp đồng khung
  đã Nộp, Đơn mua hàng, Phiếu nhập mua (đã Nộp) và tệp XML hóa đơn điện tử cho từng kịch bản; bộ cũ
  không bị đụng. Hợp đồng 1 (HĐK xx/2026) ghi giá chưa VAT, có hạn mức. Hợp đồng 2 (HĐNT xx) theo
  mẫu hợp đồng nguyên tắc: giá đã gồm VAT 5%, không cam kết số lượng, tự động gia hạn.
- Chỉ gán vai trò có sẵn cho người dùng demo, không tạo vai trò. Cần NCC riêng vì mã dòng hợp đồng không được trùng, và Đơn mua chỉ tự gắn hợp
  đồng khung khi NCC có đúng một hợp đồng còn hiệu lực chứa mặt hàng.
- Tệp XML ghi vào `<site>/private/demo_tiep_nhan_hoa_don/<NCC>/`. Mỗi hóa đơn ghi số Đơn mua của
  kịch bản ở phần ghi chú (như yêu cầu NCC ghi số PO lên hóa đơn), nên mỗi phiếu chỉ khớp với Đơn
  mua của kịch bản đó. Từ Windows chọn tệp qua đường dẫn `\\\\wsl.localhost\\...` in ra cuối.
- Cài đặt dùng chung (Cài đặt tiếp nhận hóa đơn, Buying Settings, Accounts Settings, tài khoản
  làm tròn của công ty) được in ra khi đổi. Giá trị trước lần chạy đầu lưu ở
  `<site>/private/demo_tiep_nhan_hoa_don_cai_dat_cu.json` để `--tra-lai`.

Kịch bản (giá chưa VAT, VAT 10%; mã dòng hợp đồng in ra khi chạy):
  A  Đơn mua 500 Ống thông Foley x 12.500; hóa đơn ghi tên khác hợp đồng, không mã -> tầng 3, tạo
     hóa đơn mua nháp, Nộp, lũy kế hợp đồng; tải lại tệp này lần hai -> Từ chối vì trùng
  B  Đơn mua 200 Ống thông Foley; hóa đơn ghi mã hàng của NCC -> tầng 1
  C1 Đơn mua 100 Găng tay khám x 2.000; tên khác -> tầng 3, đề xuất Bảng ánh xạ tên
  C2 Đơn mua 120 Găng tay khám, cùng tên trên hóa đơn, sau khi ánh xạ được duyệt -> tầng 2
  D  Đơn mua 100 Gạc 10cm x 10cm x 5.000; hóa đơn gạc 7,5cm -> không tự khớp, chọn tay
  E  Đơn mua 100 Ống thông Foley x 13.000 (khác giá hợp đồng 12.500) -> cảnh báo chặn, trưởng bộ
     phận (Purchase Manager) duyệt
  F  Hợp đồng 100 Bơm tiêm x 3.000, Đơn mua 100; hóa đơn 120, ghi mã dòng hợp đồng -> vượt hạn mức
  G  như A nhưng MST người mua sai -> Từ chối
  I  Đơn mua 50 Ống thông Foley; tổng thanh toán trên hóa đơn lệch 1.000 -> kiểm số học
  J  Đơn mua 30 Ống thông Foley, CHƯA có Phiếu nhập -> chưa tạo được hóa đơn mua
  K  Đơn mua 500 Ống thông Foley; hóa đơn 300 -> hóa đơn từng phần; xóa hóa đơn nháp mở lại phiếu
  L  Một Đơn mua hai dòng cùng tên theo hợp đồng (hai hãng), 300 mỗi dòng; hóa đơn 250 -> nhiều
     ứng viên, chọn tay
  M  như B, khác số hóa đơn, cùng ngày, cùng tổng tiền -> nghi trùng
  N  Đơn mua 20 Băng dính (không thuộc hợp đồng khung); hóa đơn ghi mã hàng Miyano -> tầng 1, chỉ ghi chú
  O  Hợp đồng 2: Đơn mua 7 hộp kit ELISA x 3.760.952 (= 3.949.000 gồm VAT 5%, làm tròn đến đồng);
     hóa đơn ghi mã hàng NCC 5002 -> khớp, Hóa đơn mua khớp Phiếu nhập
  P  Hợp đồng 2: Đơn mua 12 hộp theo giá 10 - 30 hộp (3.812.500 gồm VAT, chỉ ghi chú trong hợp đồng)
     -> hóa đơn lệch giá hợp đồng, cảnh báo chặn, cần duyệt
"""

import argparse
import json
import os
import sys

import frappe
from frappe.utils import add_days, flt, nowdate

SITE_PRODUCTION = "miyano"
TEP_CAI_DAT_CU = "demo_tiep_nhan_hoa_don_cai_dat_cu.json"
THU_MUC_XML = "demo_tiep_nhan_hoa_don"
MST_MIYANO = "0109529507"
BANG_GIA = "DEMO Mua - Hợp đồng khung"
# Vai trò có sẵn: trưởng bộ phận chuỗi cung ứng duyệt lệch giá / vượt hạn mức (production chọn ở cài đặt).
VAI_TRO_DUYET = "Purchase Manager"
MA_HANG_NCC = "NCC-FL216"
THUE_10 = "GTGT mua vào 10%"
THUE_5 = "GTGT mua vào 5%"
ELISA = ("DEMO-HDK-08", "Ascaris IgG Elisa Kit", 3949000, "5002")
GIA_ELISA_BAC_2 = 3812500
# Thông tin hợp đồng nguyên tắc bắt buộc khi Nộp (theo mẫu 001-GREENTECH/MIYANO, dữ liệu giả).
HOP_DONG = {
	"dai_dien_ben_a": "DEMO Đại diện Miyano",
	"chuc_vu_ben_a": "Giám đốc vận hành",
	"mst_ben_a": MST_MIYANO,
	"dia_chi_ben_a": "DEMO địa chỉ Bên A, Hà Nội",
	"tai_khoan_ben_a": "DEMO-0001",
	"ngan_hang_ben_a": "DEMO Ngân hàng A - Chi nhánh 1",
	"dai_dien_ben_b": "DEMO Đại diện NCC",
	"chuc_vu_ben_b": "Giám đốc",
	"dien_thoai_ben_b": "0240000000",
	"dia_chi_ben_b": "DEMO địa chỉ Bên B, Hà Nội",
	"tai_khoan_ben_b": "DEMO-0002",
	"ngan_hang_ben_b": "DEMO Ngân hàng B - Chi nhánh 2",
	"dia_diem_giao": "Kho Miyano (DEMO)",
	"dieu_kien_bao_quan": "Theo yêu cầu của nhà sản xuất",
}

CAI_DAT = "Supplier Invoice Intake Settings"
CAI_DAT_TIEP_NHAN = {
	"bat_tiep_nhan": 1,
	"mst_nguoi_mua": MST_MIYANO,
	"nguong_canh_bao_han_muc": 90.0,
	"vai_tro_duyet_lech_gia": VAI_TRO_DUYET,
	"vai_tro_duyet_anh_xa": "Purchase Manager",
}
# Như production (spec Đợt 3 mục 3.5): hóa đơn từ phiếu tiếp nhận đi tiếp qua đối soát Phiếu nhập.
BUYING_SETTINGS = {
	"maintain_same_rate": 1,
	"maintain_same_rate_action": "Warn",
	"pr_required": "Yes",
	"blanket_order_allowance": 0,
	"bat_doi_soat_pr_pi": 1,
}
ACCOUNTS_SETTINGS = {"round_row_wise_tax": 1}

NGUOI_DUNG = (
	("demo.nvmuahang@example.com", "DEMO NV Mua hàng", ["Purchase User", "Stock User"]),
	("demo.chuoicungung@example.com", "DEMO Chuỗi cung ứng", ["Purchase Manager", "Purchase User"]),
	("demo.ketoan@example.com", "DEMO Kế toán", ["Accounts User", "Purchase User", "Stock User"]),
	# Xóa hóa đơn mua nháp cần Accounts Manager (Kế toán không có quyền xóa).
	(
		"demo.ketoantruong@example.com",
		"DEMO Kế toán trưởng",
		["Accounts Manager", "Accounts User", "Purchase User", "Stock User"],
	),
)

FOLEY = "Ống thông tiểu Foley 2 nhánh cỡ 16Fr"
# (mã, tên, đưa vào hợp đồng khung: (số lượng, đơn giá, quy cách, hãng) hoặc None)
MAT_HANG = (
	("DEMO-HDK-01", FOLEY, (5000, 12500, "16Fr", "DEMO Hãng A")),
	("DEMO-HDK-02", "Gạc phẫu thuật 10cm x 10cm", (1000, 5000, "10cm x 10cm", "DEMO Hãng C")),
	("DEMO-HDK-03", "Găng tay khám nitrile cỡ M", (1000, 2000, "Cỡ M", "DEMO Hãng D")),
	("DEMO-HDK-04", "Bơm tiêm 10ml", (100, 3000, "10ml", "DEMO Hãng E")),
	("DEMO-HDK-05", "Dây truyền dịch", None),
	("DEMO-HDK-06", "Khẩu trang y tế 4 lớp", None),
	("DEMO-HDK-07", f"{FOLEY} - Hãng B", (1000, 12500, "16Fr", "DEMO Hãng B")),
	("DEMO-HDK-09", "Băng dính cuộn 2,5cm x 5m", None),
)


def main():
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--site", required=True)
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
		CAI_DAT: {k: frappe.db.get_single_value(CAI_DAT, k) for k in CAI_DAT_TIEP_NHAN},
		"Buying Settings": {k: frappe.db.get_single_value("Buying Settings", k) for k in BUYING_SETTINGS},
		"Accounts Settings": {
			k: frappe.db.get_single_value("Accounts Settings", k) for k in ACCOUNTS_SETTINGS
		},
		"Company": {
			"name": cong_ty,
			"round_off_account": frappe.db.get_value("Company", cong_ty, "round_off_account"),
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
	_dat(CAI_DAT, CAI_DAT_TIEP_NHAN)
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


def tra_lai():
	tep = _tep_cai_dat_cu()
	if not os.path.exists(tep):
		sys.exit(f"Không có {tep}: chưa chạy demo, hoặc đã trả lại rồi.")
	with open(tep) as f:
		cu = json.load(f)
	print("Trả lại cài đặt:")
	_dat(CAI_DAT, cu[CAI_DAT])
	_dat("Buying Settings", cu["Buying Settings"])
	_dat("Accounts Settings", cu["Accounts Settings"])
	cong_ty = cu["Company"]["name"]
	if frappe.db.get_value("Company", cong_ty, "round_off_account") != cu["Company"]["round_off_account"]:
		frappe.db.set_value("Company", cong_ty, "round_off_account", cu["Company"]["round_off_account"])
		frappe.clear_document_cache("Company", cong_ty)
		print(f"  Company {cong_ty} · round_off_account -> {cu['Company']['round_off_account']!r}")
	os.remove(tep)


# --- Dữ liệu ----------------------------------------------------------------------


def dam_bao(doctype, name, fields):
	if not frappe.db.exists(doctype, name):
		frappe.get_doc({"doctype": doctype, **fields}).insert(ignore_permissions=True)


def _nguoi_dung():
	"""Người dùng mẫu để test quyền bằng nút Impersonate (không đặt mật khẩu). Đã có thì giữ nguyên."""
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


def _ncc_moi(nhom_ncc):
	"""NCC demo mới: tên, MST và mã viết tắt theo số thứ tự lần chạy."""
	n = frappe.db.count("Supplier", {"name": ("like", "DEMO-D4 NCC %")}) + 1
	while frappe.db.exists("Supplier", f"DEMO-D4 NCC {n:02d}"):
		n += 1
	ten = f"DEMO-D4 NCC {n:02d}"
	frappe.get_doc(
		{
			"doctype": "Supplier",
			"supplier_name": ten,
			"supplier_group": nhom_ncc,
			"tax_id": f"0109990{n:03d}",
			"ma_viet_tat": f"D4N{n:02d}",
			"default_price_list": BANG_GIA,
			"doi_soat_pr_pi": 1,
		}
	).insert(ignore_permissions=True)
	return ten, n


def tao_demo():
	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
	from erpnext.buying.tests.mau_hoa_don_xml import xml_hoa_don
	from erpnext.buying.tiep_nhan_hoa_don.hop_dong_khung import gia_chua_vat
	from erpnext.controllers.accounts_controller import get_taxes_and_charges

	cong_ty = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
	abbr = frappe.get_cached_value("Company", cong_ty, "abbr")
	kho = frappe.db.get_value("Warehouse", {"company": cong_ty, "is_group": 0, "name": f"Kho hàng - {abbr}"})
	kho = kho or frappe.db.get_value("Warehouse", {"company": cong_ty, "is_group": 0}, "name")
	mau_thue = f"{THUE_10} - {abbr}"
	mau_thue_5 = f"{THUE_5} - {abbr}"

	_nguoi_dung()
	dam_bao(
		"Price List",
		BANG_GIA,
		{
			"price_list_name": BANG_GIA,
			"buying": 1,
			"currency": frappe.get_cached_value("Company", cong_ty, "default_currency"),
		},
	)
	dat_cai_dat(cong_ty)
	ncc, so_lan = _ncc_moi(frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"))
	mst_ncc = frappe.db.get_value("Supplier", ncc, "tax_id")

	nhom_hang = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
	for uom in ("Cái", "Hộp"):
		dam_bao("UOM", uom, {"uom_name": uom, "must_be_whole_number": 1})
	for code, ten, dvt in [(c, t, "Cái") for c, t, _hdk in MAT_HANG] + [(ELISA[0], ELISA[1], "Hộp")]:
		dam_bao(
			"Item",
			code,
			{
				"item_code": code,
				"item_name": ten,
				"item_group": nhom_hang,
				"stock_uom": dvt,
				"is_stock_item": 1,
			},
		)
	# Mã hàng của NCC (Item Supplier) cho kịch bản B, E: tầng 1 khớp theo mã này.
	item = frappe.get_doc("Item", "DEMO-HDK-01")
	item.append("supplier_items", {"supplier": ncc, "supplier_part_no": MA_HANG_NCC})
	item.save(ignore_permissions=True)

	hdk = frappe.get_doc(
		{
			"doctype": "Blanket Order",
			"blanket_order_type": "Purchasing",
			"supplier": ncc,
			"company": cong_ty,
			"order_no": f"HĐK {so_lan:02d}/2026",
			"order_date": add_days(nowdate(), -30),
			"from_date": add_days(nowdate(), -30),
			"to_date": add_days(nowdate(), 335),
			"bang_gia_mua": BANG_GIA,
			**HOP_DONG,
			"items": [
				{
					"item_code": code,
					"qty": qty,
					"rate": rate,
					"ma_hang_ncc": MA_HANG_NCC if code == "DEMO-HDK-01" else f"NCC-{code[-2:]}",
					# Hai hãng cùng một tên theo hợp đồng (kịch bản L).
					"ten_hdk": FOLEY if code == "DEMO-HDK-07" else ten,
					"quy_cach": quy_cach,
					"chat_lieu": "DEMO",
					"hang_sx": hang,
					"nuoc_sx": "Việt Nam",
					"so_luu_hanh": f"DEMO-SLH-{code[-2:]}",
					"thue_suat": "10%",
				}
				for code, ten, dong in MAT_HANG
				if dong
				for qty, rate, quy_cach, hang in [dong]
			],
		}
	).insert(ignore_permissions=True)
	hdk.submit()
	ma_code, ten_elisa, gia_elisa, ma_ncc_elisa = ELISA
	hdnt = frappe.get_doc(
		{
			"doctype": "Blanket Order",
			"blanket_order_type": "Purchasing",
			"supplier": ncc,
			"company": cong_ty,
			"order_no": f"HĐNT {so_lan:02d}-ELISA/MIYANO",
			"ma_hop_dong": f"NT{so_lan:02d}",
			"order_date": add_days(nowdate(), -10),
			"from_date": add_days(nowdate(), -10),
			"to_date": add_days(nowdate(), 355),
			"bang_gia_mua": BANG_GIA,
			**HOP_DONG,
			"dieu_kien_bao_quan": "2 - 8°C với kit ELISA",
			"gia_gom_vat": 1,
			"gia_gom_chi_phi_giao": 1,
			"khong_cam_ket_so_luong": 1,
			"tu_dong_gia_han": 1,
			"items": [
				{
					"item_code": ma_code,
					"qty": 0,
					"rate": gia_elisa,
					"ma_hang_ncc": ma_ncc_elisa,
					"ten_hdk": ten_elisa,
					"quy_cach": "96 test/hộp",
					"hang_sx": "DEMO New Life",
					"nuoc_sx": "Mỹ",
					"so_luu_hanh": "DEMO-SLH-08",
					"thue_suat": "5%",
					"ghi_chu_gia": "10 - 30 hộp/đơn: 3.812.500 (đã gồm VAT)",
				}
			],
		}
	).insert(ignore_permissions=True)
	hdnt.submit()
	ma_dong = {d.item_code: d.ma_dong_hdk for d in [*hdk.items, *hdnt.items]}

	def po(rows, mau=mau_thue):
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
				"taxes_and_charges": mau,
				"taxes": get_taxes_and_charges("Purchase Taxes and Charges Template", mau),
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc

	def pr(don_mua, ma):
		doc = make_purchase_receipt(don_mua.name)
		doc.supplier_delivery_note = f"DEMO-D4-{ma}"
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc

	thu_muc = frappe.get_site_path("private", THU_MUC_XML, ncc.replace(" ", "_"))
	os.makedirs(thu_muc, exist_ok=True)
	so_hd = iter(range(1, 100))

	def xml(ten_tep, don_mua, dong, **kw):
		kw.setdefault("so", f"{next(so_hd):08d}")
		noi_dung = xml_hoa_don(
			dong,
			ky_hieu="C26TDM",
			ngay=nowdate(),
			mst_ban=mst_ncc,
			ten_ban=ncc,
			ghi_chu=f"Theo đơn đặt hàng {don_mua.name}",
			**kw,
		)
		with open(os.path.join(thu_muc, ten_tep), "wb") as f:
			f.write(noi_dung)
		return ten_tep

	ket_qua = []

	def ghi(ma, viec, tep, don_mua, phieu=None):
		ket_qua.append((ma, viec, tep, don_mua.name, phieu.name if phieu else "-"))

	sonde = "Sonde Foley 2 way size 16"
	don_a = po([("DEMO-HDK-01", 500, 12500)])
	dong_a = [("", sonde, "Cái", 500, 12500, "10%")]
	ghi(
		"A",
		"Tầng 3, tạo hóa đơn, Nộp; tải lại -> trùng",
		xml("A_tang3_ten_khac.xml", don_a, dong_a),
		don_a,
		pr(don_a, "A"),
	)
	don = po([("DEMO-HDK-01", 200, 12500)])
	dong_b = [(MA_HANG_NCC, "Foley catheter 2-way 16Fr", "Cái", 200, 12500, "10%")]
	ghi("B", "Tầng 1 mã hàng NCC", xml("B_tang1_ma_ncc.xml", don, dong_b), don, pr(don, "B"))
	don = po([("DEMO-HDK-03", 100, 2000)])
	dong_c = [("", "Găng khám Nitrile size M", "Cái", 100, 2000, "10%")]
	ghi("C1", "Tầng 3, đề xuất ánh xạ tên", xml("C1_anh_xa_lan_1.xml", don, dong_c), don, pr(don, "C1"))
	# Số lượng khác C1: cùng ngày, cùng tổng tiền thì phiếu C2 bị báo nghi trùng.
	don = po([("DEMO-HDK-03", 120, 2000)])
	dong_c2 = [("", "Găng khám Nitrile size M", "Cái", 120, 2000, "10%")]
	ghi("C2", "Tầng 2 sau khi duyệt ánh xạ", xml("C2_anh_xa_lan_2.xml", don, dong_c2), don, pr(don, "C2"))
	don = po([("DEMO-HDK-02", 100, 5000)])
	dong_d = [("", "Gạc phẫu thuật 7,5cm x 7,5cm", "Cái", 100, 5000, "10%")]
	ghi("D", "Khác quy cách, chọn tay", xml("D_khac_quy_cach.xml", don, dong_d), don, pr(don, "D"))
	don = po([("DEMO-HDK-01", 100, 13000)])
	dong_e = [(MA_HANG_NCC, sonde, "Cái", 100, 13000, "10%")]
	ghi(
		"E",
		"Lệch giá hợp đồng, trưởng bộ phận duyệt",
		xml("E_lech_gia_hdk.xml", don, dong_e),
		don,
		pr(don, "E"),
	)
	don = po([("DEMO-HDK-04", 100, 3000)])
	dong_f = [(ma_dong["DEMO-HDK-04"], "Bơm tiêm 10ml", "Cái", 120, 3000, "10%")]
	ghi("F", "Vượt hạn mức hợp đồng", xml("F_vuot_han_muc.xml", don, dong_f), don, pr(don, "F"))
	ghi(
		"G",
		"Sai MST người mua -> Từ chối",
		xml("G_sai_mst_nguoi_mua.xml", don_a, dong_a, mst_mua="0100000000"),
		don_a,
	)
	don = po([("DEMO-HDK-01", 50, 12500)])
	dong_i = [("", sonde, "Cái", 50, 12500, "10%")]
	ghi(
		"I",
		"Tổng tiền lệch các dòng",
		xml("I_lech_so_hoc.xml", don, dong_i, tong=(625000, 62500, 688500)),
		don,
		pr(don, "I"),
	)
	don = po([("DEMO-HDK-01", 30, 12500)])
	ghi(
		"J",
		"Chưa có Phiếu nhập",
		xml("J_chua_phieu_nhap.xml", don, [("", sonde, "Cái", 30, 12500, "10%")]),
		don,
	)
	don = po([("DEMO-HDK-01", 500, 12500)])
	dong_k = [("", sonde, "Cái", 300, 12500, "10%")]
	ghi("K", "Hóa đơn từng phần, xóa nháp", xml("K_tung_phan.xml", don, dong_k), don, pr(don, "K"))
	don = po([("DEMO-HDK-01", 300, 12500), ("DEMO-HDK-07", 300, 12500)])
	dong_l = [("", sonde, "Cái", 250, 12500, "10%")]
	ghi("L", "Nhiều dòng Đơn mua khớp, chọn tay", xml("L_nhieu_ung_vien.xml", don, dong_l), don, pr(don, "L"))
	don = po([("DEMO-HDK-01", 200, 12500)])
	ghi("M", "Nghi trùng với B", xml("M_nghi_trung.xml", don, dong_b), don, pr(don, "M"))
	don = po([("DEMO-HDK-09", 20, 15000)])
	dong_n = [("DEMO-HDK-09", "Băng dính cuộn 2,5cm x 5m", "Cái", 20, 15000, "10%")]
	ghi("N", "Ngoài hợp đồng khung", xml("N_ngoai_hdk.xml", don, dong_n), don, pr(don, "N"))
	# Hợp đồng 2: giá đã gồm VAT 5% quy về chưa VAT, làm tròn đến đồng như bảng giá mua.
	chua_vat = gia_chua_vat(gia_elisa, "5%", 1)
	don = po([(ma_code, 7, chua_vat)], mau=mau_thue_5)
	dong_o = [(ma_ncc_elisa, ten_elisa, "Hộp", 7, int(chua_vat), "5%")]
	ghi("O", "Giá gồm VAT, khớp", xml("O_gia_gom_vat.xml", don, dong_o), don, pr(don, "O"))
	bac_2 = gia_chua_vat(GIA_ELISA_BAC_2, "5%", 1)
	don = po([(ma_code, 12, bac_2)], mau=mau_thue_5)
	dong_p = [(ma_ncc_elisa, ten_elisa, "Hộp", 12, int(bac_2), "5%")]
	ghi("P", "Giá bậc 2 -> lệch giá hợp đồng", xml("P_gia_bac_2.xml", don, dong_p), don, pr(don, "P"))

	print(f"\nNCC: {ncc} (MST {mst_ncc}, mã viết tắt D4N{so_lan:02d}).")
	print(f"Hợp đồng khung 1: {hdk.name} ({hdk.order_no}). Hợp đồng 2: {hdnt.name} ({hdnt.order_no}).")
	print("Mã dòng hợp đồng: " + ", ".join(f"{k} = {v}" for k, v in ma_dong.items()))
	print("\nKịch bản | Việc | Tệp XML | Đơn mua hàng | Phiếu nhập mua")
	for dong in ket_qua:
		print(" | ".join(dong))
	print(f"\nTệp XML: {thu_muc}")
	distro = os.environ.get("WSL_DISTRO_NAME")
	if distro:
		print("Từ Windows: \\\\wsl.localhost\\" + distro + os.path.abspath(thu_muc).replace("/", "\\"))
	print(
		"\nNgười dùng (Impersonate): "
		+ ", ".join(email for email, _ten, _vai_tro in NGUOI_DUNG)
		+ f". Duyệt lệch giá / vượt hạn mức và duyệt ánh xạ tên: vai trò {VAI_TRO_DUYET}."
	)


if __name__ == "__main__":
	main()
