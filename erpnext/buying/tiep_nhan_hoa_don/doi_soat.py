# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Phiếu tiếp nhận hóa đơn NCC: đọc tệp, kiểm, đối soát 4 tầng (spec 2026-10-23 mục 4, 5; FRD mục 10).

Chạy trong `validate` của phiếu, mỗi lần Lưu tính lại từ đầu (dòng Chọn tay giữ lựa chọn của người
dùng). Khi đã có Hóa đơn mua nháp / đã ghi sổ thì phiếu khóa, không tính lại.
"""

import hashlib
import json

import frappe
from frappe import _
from frappe.query_builder import Order
from frappe.query_builder.functions import Sum
from frappe.utils import flt, fmt_money, getdate, now_datetime, today

from erpnext.buying.tiep_nhan_hoa_don.cau_hinh import bo_chuan_hoa, cai_dat, co_quyen_duyet_lech_gia
from erpnext.buying.tiep_nhan_hoa_don.chuan_hoa import bo_dau
from erpnext.buying.tiep_nhan_hoa_don.doc_xml import HANG_HOA, LoiDocHoaDon, chuan_mst, doc_hoa_don_xml
from erpnext.buying.tiep_nhan_hoa_don.hop_dong_khung import DUNG_SAI_GIA_GOM_VAT, gia_chua_vat

MOI = "Mới tiếp nhận"
DA_TRICH_XUAT = "Đã trích xuất"
DA_DOI_SOAT = "Đã đối soát"
CHO_XU_LY = "Chờ xử lý thủ công"
DA_TAO_HD = "Đã tạo nháp hóa đơn mua"
DA_GHI_SO = "Đã ghi sổ"
TU_CHOI = "Từ chối"

TANG_1 = "Tầng 1 - Mã"
TANG_2 = "Tầng 2 - Ánh xạ tên"
TANG_3 = "Tầng 3 - Đơn mua"
CHON_TAY = "Chọn tay"

DA_KHOP = "Đã khớp"
CHO_XAC_NHAN = "Chờ xác nhận"
CHUA_KHOP = "Chưa khớp"

TRUONG_DUYET = ("ly_do_duyet", "nguoi_duyet", "thoi_diem_duyet", "dau_van_tay_canh_bao")
DUNG_SAI_TIEN = 0.5  # VND: hóa đơn ghi đến đồng, giá trên chứng từ có thể có phần lẻ


def xu_ly(doc):
	"""`validate` của Supplier Invoice Intake."""
	if doc.trang_thai in (DA_TAO_HD, DA_GHI_SO) and doc.purchase_invoice:
		return
	c = cai_dat()
	canh_bao = []
	if doc.tep_hoa_don and doc.tep_hoa_don != doc.tep_da_doc:
		if not _doc_tep(doc):
			return
	if not doc.du_lieu_trich_xuat:
		doc.trang_thai = MOI
		return

	_tim_ncc(doc, canh_bao)
	if _tu_choi(doc, c, canh_bao):
		doc.canh_bao = "\n".join(canh_bao)
		return
	doc.ly_do_tu_choi = None
	_kiem_so_hoc(doc, canh_bao)
	_kiem_nghi_trung(doc, canh_bao)
	if doc.supplier:
		DoiSoat(doc, c).chay()
	doc.canh_bao = "\n".join(canh_bao)
	_ghi_trang_thai(doc)


# --- Đọc tệp ----------------------------------------------------------------------


def _noi_dung_tep(url):
	ten = frappe.db.get_value("File", {"file_url": url}, "name", order_by="creation desc")
	if not ten:
		raise LoiDocHoaDon(_("Không tìm thấy tệp {0}.").format(url))
	noi_dung = frappe.get_doc("File", ten).get_content()
	return noi_dung.encode() if isinstance(noi_dung, str) else noi_dung


def _doc_tep(doc):
	try:
		kq = doc_hoa_don_xml(_noi_dung_tep(doc.tep_hoa_don))
	except LoiDocHoaDon as e:
		doc.trang_thai = MOI
		doc.du_lieu_trich_xuat = None
		doc.canh_bao = str(e)
		frappe.msgprint(str(e), title=_("Chưa đọc được hóa đơn"), indicator="red")
		return False

	doc.update(
		{
			"tep_da_doc": doc.tep_hoa_don,
			"du_lieu_trich_xuat": json.dumps(kq, ensure_ascii=False, indent=1),
			"ky_hieu": kq["ky_hieu"],
			"so_hoa_don": kq["so_hoa_don"],
			"ngay_hoa_don": getdate(kq["ngay"]) if kq["ngay"] else None,
			"ten_nguoi_ban": kq["ncc"]["ten"],
			"mst_nguoi_ban": kq["ncc"]["mst"],
			"ten_nguoi_mua": kq["nguoi_mua"]["ten"],
			"mst_nguoi_mua": kq["nguoi_mua"]["mst"],
			"so_po_tren_hoa_don": kq["so_po_ghi_tren_hoa_don"],
			"tong_tien_hang": kq["tong_tien_hang"],
			"tien_thue": kq["tien_thue"],
			"tong_thanh_toan": kq["tong_thanh_toan"],
			"trang_thai": DA_TRICH_XUAT,
			"supplier": None,
			"purchase_order": None,
			"purchase_invoice": None,
			"da_kiem_so_hoc": 0,
			"da_kiem_khong_trung": 0,
		}
	)
	for f in TRUONG_DUYET:
		doc.set(f, None)
	if kq["so_po_ghi_tren_hoa_don"] and frappe.db.exists(
		"Purchase Order", {"name": kq["so_po_ghi_tren_hoa_don"], "docstatus": 1}
	):
		doc.purchase_order = kq["so_po_ghi_tren_hoa_don"]
	doc.set("items", [])
	for d in kq["dong_hang"]:
		if d["tinh_chat"] != HANG_HOA:
			continue  # khuyến mại, chiết khấu, ghi chú: không có mặt hàng để khớp
		doc.append(
			"items",
			{
				"stt": d["stt"],
				"ma_hang_hd": d["ma_hang"],
				"ten_hang_hd": d["ten_hang"],
				"dvt_hd": d["dvt"],
				"so_luong": d["so_luong"],
				"don_gia": d["don_gia"],
				"thanh_tien": d["thanh_tien"],
				"thue_suat": d["thue_suat"],
			},
		)
	return True


def _du_lieu(doc):
	return json.loads(doc.du_lieu_trich_xuat or "{}")


# --- Kiểm đầu phiếu ------------------------------------------------------------------


def _tim_ncc(doc, canh_bao):
	if doc.supplier or not doc.mst_nguoi_ban:
		return
	mst = chuan_mst(doc.mst_nguoi_ban)
	ds = [
		r.name
		for r in frappe.get_all(
			"Supplier", filters={"tax_id": ("is", "set"), "disabled": 0}, fields=["name", "tax_id"]
		)
		if chuan_mst(r.tax_id) == mst
	]
	if len(ds) == 1:
		doc.supplier = ds[0]
	elif ds:
		canh_bao.append(
			_("Nhiều nhà cung cấp cùng MST {0}: {1}. Chọn Nhà cung cấp.").format(mst, ", ".join(ds))
		)
	else:
		canh_bao.append(_("Không có nhà cung cấp nào mang MST {0}. Chọn Nhà cung cấp.").format(mst))


def _tu_choi(doc, c, canh_bao):
	"""FR-16 (sai người mua) và BR-08 / TC-11 (đã tiếp nhận): dừng, không đối soát."""
	ly_do = None
	mst = c.mst_nguoi_mua or frappe.db.get_value("Company", doc.company, "tax_id")
	if not mst:
		canh_bao.append(
			_(
				"Chưa cài MST người mua (Cài đặt tiếp nhận hóa đơn hoặc MST công ty): chưa kiểm được người mua."
			)
		)
	elif chuan_mst(doc.mst_nguoi_mua) != chuan_mst(mst):
		ly_do = _("MST người mua trên hóa đơn ({0}) khác MST của công ty ({1}).").format(
			doc.mst_nguoi_mua or "-", mst
		)

	if not ly_do and doc.so_hoa_don:
		trung = frappe.get_all(
			"Supplier Invoice Intake",
			filters={
				"name": ("!=", doc.name or ""),
				"trang_thai": ("!=", TU_CHOI),
				"mst_nguoi_ban": doc.mst_nguoi_ban,
				"ky_hieu": doc.ky_hieu,
				"so_hoa_don": doc.so_hoa_don,
			},
			pluck="name",
		)
		if trung:
			ly_do = _("Hóa đơn {0} {1} đã được tiếp nhận ở phiếu {2}.").format(
				doc.ky_hieu, doc.so_hoa_don, trung[0]
			)
		elif doc.supplier:
			hd = frappe.get_all(
				"Purchase Invoice",
				filters={
					"supplier": doc.supplier,
					"bill_no": doc.so_hoa_don,
					"docstatus": ("<", 2),
					"name": ("!=", doc.purchase_invoice or ""),
				},
				pluck="name",
			)
			if hd:
				ly_do = _("Đã có Hóa đơn mua {0} cùng nhà cung cấp, cùng số hóa đơn {1}.").format(
					hd[0], doc.so_hoa_don
				)

	if ly_do:
		doc.trang_thai = TU_CHOI
		doc.ly_do_tu_choi = ly_do
		return True
	return False


def _kiem_so_hoc(doc, canh_bao):
	"""11.1: tổng tiền hàng, thuế, thanh toán phải khớp các dòng (chiết khấu thương mại trừ vào tổng)."""
	dong = _du_lieu(doc).get("dong_hang") or []
	tien_hang = sum(flt(d["thanh_tien"]) for d in dong if d["tinh_chat"] == HANG_HOA) - sum(
		flt(d["thanh_tien"]) for d in dong if d["tinh_chat"] == 3
	)
	thue = sum(
		flt(d["thanh_tien"]) * flt(d["thue_suat"].rstrip("%")) / 100
		for d in dong
		if d["tinh_chat"] == HANG_HOA and d["thue_suat"][:1].isdigit()
	)
	dung_sai = max(len(dong), 1)  # làm tròn từng dòng lệch tối đa 1 đồng / dòng
	lech = []
	if abs(tien_hang - flt(doc.tong_tien_hang)) > DUNG_SAI_TIEN:
		lech.append(
			_("tổng tiền hàng {0}, cộng các dòng {1}").format(_tien(doc.tong_tien_hang), _tien(tien_hang))
		)
	if abs(thue - flt(doc.tien_thue)) > dung_sai:
		lech.append(_("tiền thuế {0}, tính theo dòng {1}").format(_tien(doc.tien_thue), _tien(thue)))
	if abs(flt(doc.tong_tien_hang) + flt(doc.tien_thue) - flt(doc.tong_thanh_toan)) > DUNG_SAI_TIEN:
		lech.append(_("tổng thanh toán {0} khác tiền hàng + thuế").format(_tien(doc.tong_thanh_toan)))
	doc.lech_so_hoc = 1 if lech else 0
	if lech:
		canh_bao.append(_("Số học trên hóa đơn không cân đối: {0}.").format("; ".join(lech)))
	else:
		doc.da_kiem_so_hoc = 0


def _kiem_nghi_trung(doc, canh_bao):
	"""FR-17: cùng NCC, cùng ngày, cùng tổng tiền với hóa đơn khác (khác số) thì nghi ghi nhận trùng."""
	khac = []
	if doc.mst_nguoi_ban and doc.ngay_hoa_don:
		khac = frappe.get_all(
			"Supplier Invoice Intake",
			filters={
				"name": ("!=", doc.name or ""),
				"trang_thai": ("!=", TU_CHOI),
				"mst_nguoi_ban": doc.mst_nguoi_ban,
				"ngay_hoa_don": doc.ngay_hoa_don,
				"tong_thanh_toan": doc.tong_thanh_toan,
			},
			pluck="name",
		)
	if doc.supplier and doc.ngay_hoa_don:
		khac += frappe.get_all(
			"Purchase Invoice",
			filters={
				"supplier": doc.supplier,
				"bill_date": doc.ngay_hoa_don,
				"grand_total": doc.tong_thanh_toan,
				"docstatus": ("<", 2),
				"name": ("!=", doc.purchase_invoice or ""),
			},
			pluck="name",
		)
	doc.nghi_trung = 1 if khac else 0
	if khac:
		canh_bao.append(
			_(
				"Nghi trùng: {0} cùng nhà cung cấp, cùng ngày, cùng tổng tiền. Kiểm rồi tích Đã kiểm, không trùng."
			).format(", ".join(khac))
		)
	else:
		doc.da_kiem_khong_trung = 0


def _tien(x):
	# Bỏ phần lẻ khi chẵn đồng (13.000); giữ khi có lẻ để hai giá lệch dưới 1 đồng không in giống nhau.
	return fmt_money(flt(x), precision=0 if flt(x).is_integer() else 2)


def _so(x):
	"""Số lượng theo định dạng số của hệ thống (120, 1.880), không in 120.0."""
	return frappe.format_value(flt(x), {"fieldtype": "Float"})


# --- Đối soát 4 tầng -----------------------------------------------------------------


class DoiSoat:
	def __init__(self, doc, c):
		self.doc, self.c = doc, c
		self.bo = bo_chuan_hoa(c)
		self.ngay = doc.ngay_hoa_don or getdate(today())
		self.hdk = self._dong_hdk()
		self.don_mua = self._dong_don_mua()
		self.ma_ncc = dict(
			frappe.get_all(
				"Item Supplier",
				filters={"supplier": doc.supplier, "supplier_part_no": ("is", "set")},
				fields=["supplier_part_no", "parent"],
				as_list=True,
			)
		)

	def _dong_hdk(self):
		"""Dòng HĐK còn hiệu lực của NCC; phụ lục (Từ ngày sau) đứng trước hợp đồng gốc."""
		bo = frappe.qb.DocType("Blanket Order")
		boi = frappe.qb.DocType("Blanket Order Item")
		dong = (
			frappe.qb.from_(boi)
			.join(bo)
			.on(bo.name == boi.parent)
			.select(
				bo.name.as_("blanket_order"),
				boi.item_code,
				boi.ma_dong_hdk,
				boi.party_item_code,
				boi.ma_hang_ncc,
				boi.ten_hdk,
				boi.rate,
				boi.thue_suat,
				boi.qty,
				boi.da_lap_hoa_don,
				bo.gia_gom_vat,
			)
			.where(
				(bo.docstatus == 1)
				& (bo.blanket_order_type == "Purchasing")
				& (bo.supplier == self.doc.supplier)
				& (bo.company == self.doc.company)
				& (bo.from_date <= self.ngay)
				& (bo.to_date >= self.ngay)
			)
			.orderby(bo.from_date, order=Order.desc)
			.run(as_dict=True)
		)
		for h in dong:
			h.gia_chua_vat = gia_chua_vat(h.rate, h.thue_suat, h.gia_gom_vat)
		return dong

	def _dong_don_mua(self):
		"""Dòng Đơn mua đã Nộp của NCC còn số lượng chưa lập hóa đơn (theo Hóa đơn mua đã Nộp)."""
		po = frappe.qb.DocType("Purchase Order")
		poi = frappe.qb.DocType("Purchase Order Item")
		pii = frappe.qb.DocType("Purchase Invoice Item")
		dong = (
			frappe.qb.from_(poi)
			.join(po)
			.on(po.name == poi.parent)
			.select(
				poi.name,
				poi.parent,
				poi.item_code,
				poi.item_name,
				poi.uom,
				poi.conversion_factor,
				poi.rate,
				poi.stock_qty,
				poi.blanket_order,
				po.transaction_date,
			)
			.where(
				(po.docstatus == 1)
				& (po.supplier == self.doc.supplier)
				& (po.company == self.doc.company)
				& po.status.notin(["Closed", "On Hold"])
			)
			.orderby(po.transaction_date)
			.orderby(po.name)
			.orderby(poi.idx)
			.run(as_dict=True)
		)
		ten = [d.name for d in dong]
		lap = {}
		if ten:
			lap = dict(
				frappe.qb.from_(pii)
				.select(pii.po_detail, Sum(pii.stock_qty))
				.where((pii.docstatus == 1) & pii.po_detail.isin(ten))
				.groupby(pii.po_detail)
				.run()
			)
		for d in dong:
			d.con_lai = flt(d.stock_qty) - flt(lap.get(d.name))
		return [d for d in dong if d.con_lai > 0]

	# --- Từng dòng ---

	def chay(self):
		self.da_phan = {}  # dòng Đơn mua -> số lượng (ĐVT kho) đã gán cho các dòng phiếu này
		for row in self.doc.items:
			for f in ("cach_khop", "diem_khop", "blanket_order", "ma_dong_hdk", "canh_bao", "canh_bao_chan"):
				row.set(f, None)
			ghi_chu = []
			if row.chon_tay and row.item_code:
				self._khop_tay(row)
			else:
				row.chon_tay = 0
				row.item_code = row.purchase_order = row.po_detail = None
				self._tu_dong(row, ghi_chu)
			self._canh_bao(row, ghi_chu)
		dong = self.doc.items
		tu_dong = [r for r in dong if r.trang_thai_dong == DA_KHOP and r.cach_khop != CHON_TAY]
		self.doc.ty_le_khop = flt(100 * len(tu_dong) / len(dong), 1) if dong else 0

	def _ten_doi_chieu(self, item, blanket_order=None):
		h = next(
			(
				h
				for h in self.hdk
				if h.item_code == item and (not blanket_order or h.blanket_order == blanket_order)
			),
			None,
		)
		return (h and h.ten_hdk) or frappe.get_cached_value("Item", item, "item_name") or item

	def _tu_dong(self, row, ghi_chu):
		ten, khoa = row.ten_hang_hd, self.bo.khoa_quy_cach(row.ten_hang_hd)
		item = dong_po = None
		cach, diem = None, 0

		# Tầng 1: mã trên hóa đơn
		ma = (row.ma_hang_hd or "").strip()
		if ma:
			ung_vien = {
				h.item_code for h in self.hdk if ma in (h.ma_dong_hdk, h.party_item_code, h.ma_hang_ncc)
			}
			if ma in self.ma_ncc:
				ung_vien.add(self.ma_ncc[ma])
			if frappe.db.exists("Item", ma):
				ung_vien.add(ma)
			if len(ung_vien) == 1:
				item, cach, diem = ung_vien.pop(), TANG_1, 1
				if self.bo.khoa_quy_cach(self._ten_doi_chieu(item)) != khoa:
					ghi_chu.append(
						(
							_("Mã khớp nhưng quy cách trong tên khác mặt hàng {0}: kiểm lại.").format(item),
							False,
						)
					)

		# Tầng 2: Bảng ánh xạ tên của NCC
		if not item:
			ax = set(
				frappe.get_all(
					"Supplier Item Alias",
					filters={
						"supplier": self.doc.supplier,
						"ten_chuan_hoa": self.bo.chuan_hoa(ten),
						"trang_thai": "Đang dùng",
					},
					pluck="item_code",
				)
			)
			if len(ax) == 1:
				item, cach, diem = ax.pop(), TANG_2, 1

		# Tầng 3: dòng Đơn mua — cùng quy cách, ĐVT, đơn giá, còn đủ số lượng, tên đủ giống
		if not item:
			ung_vien = []
			for p in self._dong_po_uu_tien():
				if (
					not self._cung_dvt(row.dvt_hd, p.uom)
					or abs(flt(row.don_gia) - flt(p.rate)) > DUNG_SAI_TIEN
				):
					continue
				if self._con_lai(p) + 1e-9 < flt(row.so_luong) * (flt(p.conversion_factor) or 1):
					continue
				ten_ss = self._ten_doi_chieu(p.item_code, p.blanket_order) if p.blanket_order else p.item_name
				if self.bo.khoa_quy_cach(ten_ss) != khoa:
					continue
				d = self.bo.diem(ten, ten_ss, self.c.trong_so_jaccard, self.c.trong_so_chuoi)
				if d >= self.c.nguong_xac_nhan:
					ung_vien.append((p, d))
			if len(ung_vien) == 1:
				dong_po, diem = ung_vien[0]
				item, cach = dong_po.item_code, TANG_3
			elif ung_vien:
				ghi_chu.append(
					(
						_("Nhiều dòng Đơn mua có thể khớp ({0}): chọn tay.").format(
							", ".join(f"{p.parent} · {p.item_code}" for p, _d in ung_vien)
						),
						False,
					)
				)

		if not item:
			row.trang_thai_dong = CHUA_KHOP
			row.item_code = row.purchase_order = row.po_detail = None
			if not ghi_chu:
				ghi_chu.append((_("Không khớp được ở tầng 1 – 3: chọn mặt hàng (tầng 4)."), False))
			return
		row.item_code, row.cach_khop, row.diem_khop = item, cach, diem
		self._gan_don_mua(row, dong_po)
		cho = cach == TANG_3 and diem < self.c.nguong_tu_dong and not row.da_xac_nhan
		row.trang_thai_dong = CHO_XAC_NHAN if cho else DA_KHOP

	def _khop_tay(self, row):
		row.cach_khop = CHON_TAY
		row.diem_khop = self.bo.diem(
			row.ten_hang_hd,
			self._ten_doi_chieu(row.item_code),
			self.c.trong_so_jaccard,
			self.c.trong_so_chuoi,
		)
		self._gan_don_mua(row, None)
		row.trang_thai_dong = DA_KHOP

	def _dong_po_uu_tien(self):
		po = self.doc.purchase_order
		if po:
			cua_po = [p for p in self.don_mua if p.parent == po]
			if cua_po:
				return cua_po
		return self.don_mua

	def _con_lai(self, p):
		return flt(p.con_lai) - flt(self.da_phan.get(p.name))

	def _gan_don_mua(self, row, dong_po):
		"""Chọn dòng Đơn mua cho mặt hàng đã nhận ra: ưu tiên Đơn mua trên dòng / trên phiếu, rồi dòng
		còn đúng bằng số lượng hóa đơn, rồi đơn cũ nhất còn đủ."""
		if not dong_po:
			sl = flt(row.so_luong)
			ung_vien = [p for p in self.don_mua if p.item_code == row.item_code and self._con_lai(p) > 0]
			if row.purchase_order and row.chon_tay:
				ung_vien = [p for p in ung_vien if p.parent == row.purchase_order]
			elif self.doc.purchase_order:
				ung_vien = [p for p in ung_vien if p.parent == self.doc.purchase_order] or ung_vien
			du = [p for p in ung_vien if self._con_lai(p) + 1e-9 >= sl * (flt(p.conversion_factor) or 1)]
			dung = [p for p in du if abs(self._con_lai(p) - sl * (flt(p.conversion_factor) or 1)) < 1e-9]
			dong_po = (dung if len(dung) == 1 else du or ung_vien or [None])[0]
		if dong_po:
			row.purchase_order, row.po_detail = dong_po.parent, dong_po.name
			self.da_phan[dong_po.name] = flt(self.da_phan.get(dong_po.name)) + flt(row.so_luong) * (
				flt(dong_po.conversion_factor) or 1
			)
		else:
			row.purchase_order = row.po_detail = None

	@staticmethod
	def _cung_dvt(a, b):
		return bo_dau(a or "").strip().lower() == bo_dau(b or "").strip().lower()

	# --- Cảnh báo theo hợp đồng khung (BR-05, BR-06, BR-07) ---

	def _canh_bao(self, row, ghi_chu):
		if row.item_code and not row.po_detail:
			row.trang_thai_dong = CHUA_KHOP
			ghi_chu.append(
				(
					_(
						"Đã nhận ra mặt hàng {0} nhưng chưa có dòng Đơn mua hàng còn số lượng: kiểm Đơn mua."
					).format(row.item_code),
					False,
				)
			)
		if row.item_code and row.po_detail:
			p = next((p for p in self.don_mua if p.name == row.po_detail), None) or frappe._dict(
				frappe.db.get_value(
					"Purchase Order Item",
					row.po_detail,
					["uom", "conversion_factor", "blanket_order"],
					as_dict=True,
				)
			)
			cf = flt(p.conversion_factor) or 1
			h = next(
				(
					h
					for h in self.hdk
					if h.item_code == row.item_code
					and (not p.blanket_order or h.blanket_order == p.blanket_order)
				),
				None,
			)
			if h:
				row.blanket_order, row.ma_dong_hdk = h.blanket_order, h.ma_dong_hdk
				gia_hdk = flt(h.gia_chua_vat) * cf
				# Giá gồm VAT: 1 đồng trên đơn giá hóa đơn, như đối soát Đợt 3 (D4-12).
				nguong = DUNG_SAI_GIA_GOM_VAT if h.gia_gom_vat else DUNG_SAI_TIEN * cf
				if abs(flt(row.don_gia) - gia_hdk) > nguong:
					goc = (
						_(" (chưa VAT; hợp đồng ghi {0} đã gồm VAT {1})").format(
							_tien(flt(h.rate) * cf), h.thue_suat
						)
						if h.gia_gom_vat
						else ""
					)
					ghi_chu.append(
						(
							_("Đơn giá {0} khác giá hợp đồng khung {1}{2} ({3}).").format(
								_tien(row.don_gia), _tien(gia_hdk), goc, h.ma_dong_hdk
							),
							True,
						)
					)
				con = flt(h.qty) - flt(h.da_lap_hoa_don)
				# Số lượng 0: hợp đồng không cam kết số lượng, không có hạn mức.
				if flt(h.qty) and flt(row.so_luong) * cf > con + 1e-9:
					ghi_chu.append(
						(
							_("Vượt hạn mức hợp đồng khung: còn {0}, hóa đơn {1} (ĐVT kho).").format(
								_so(con), _so(flt(row.so_luong) * cf)
							),
							True,
						)
					)
				if h.thue_suat and row.thue_suat and h.thue_suat != row.thue_suat:
					ghi_chu.append(
						(
							_("Thuế suất {0} khác hợp đồng khung {1}.").format(row.thue_suat, h.thue_suat),
							False,
						)
					)
			else:
				ghi_chu.append((_("Không thuộc hợp đồng khung còn hiệu lực."), False))
			if not self._cung_dvt(row.dvt_hd, p.uom):
				ghi_chu.append(
					(_("ĐVT trên hóa đơn {0} khác ĐVT Đơn mua {1}.").format(row.dvt_hd, p.uom), False)
				)
		row.canh_bao = "\n".join(t for t, _chan in ghi_chu) or None
		row.canh_bao_chan = 1 if any(chan for _t, chan in ghi_chu) else 0


# --- Trạng thái, phê duyệt --------------------------------------------------------


def van_tay(doc):
	chan = [[r.idx, r.canh_bao] for r in doc.items if r.canh_bao_chan]
	return hashlib.sha1(json.dumps(chan, ensure_ascii=False).encode()).hexdigest()[:20] if chan else None


def _ghi_trang_thai(doc):
	dau = van_tay(doc)
	duyet = doc.flags.get("duyet_canh_bao")
	if duyet and dau:
		doc.update({"ly_do_duyet": duyet.ly_do, "nguoi_duyet": duyet.nguoi, "thoi_diem_duyet": duyet.luc})
		doc.dau_van_tay_canh_bao = dau
	elif doc.nguoi_duyet and doc.dau_van_tay_canh_bao != dau:
		if dau:
			frappe.msgprint(
				_("Cảnh báo đã thay đổi sau khi {0} duyệt, nên phê duyệt cũ không còn hiệu lực.").format(
					doc.nguoi_duyet
				),
				indicator="orange",
			)
		for f in TRUONG_DUYET:
			doc.set(f, None)
	da_duyet = bool(dau and doc.nguoi_duyet and doc.dau_van_tay_canh_bao == dau)
	xong = (
		doc.supplier
		and doc.items
		and all(r.trang_thai_dong == DA_KHOP for r in doc.items)
		and (not dau or da_duyet)
		and (not doc.lech_so_hoc or doc.da_kiem_so_hoc)
		and (not doc.nghi_trung or doc.da_kiem_khong_trung)
	)
	doc.trang_thai = DA_DOI_SOAT if xong else CHO_XU_LY


@frappe.whitelist()
def duyet_canh_bao(phieu, ly_do):
	"""BR-05 / BR-06: người có vai trò duyệt lệch giá cho đi tiếp dù lệch giá HĐK / vượt hạn mức."""
	ly_do = (ly_do or "").strip()
	if not ly_do:
		frappe.throw(_("Nhập lý do duyệt."))
	if not co_quyen_duyet_lech_gia():
		frappe.throw(_("Bạn không có vai trò duyệt lệch giá / vượt hạn mức."), frappe.PermissionError)
	doc = frappe.get_doc("Supplier Invoice Intake", phieu)
	doc.check_permission("read")
	if doc.trang_thai in (DA_TAO_HD, DA_GHI_SO, TU_CHOI):
		frappe.throw(_("Phiếu đang ở trạng thái {0}, không duyệt được.").format(doc.trang_thai))
	if not van_tay(doc):
		frappe.throw(_("Phiếu không có cảnh báo cần duyệt."))
	doc.flags.duyet_canh_bao = frappe._dict(ly_do=ly_do, nguoi=frappe.session.user, luc=now_datetime())
	doc.flags.ignore_permissions = True
	doc.save()
	return doc.trang_thai
