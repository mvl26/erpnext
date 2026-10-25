# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Tạo Hóa đơn mua nháp từ Phiếu tiếp nhận đã đối soát (spec 2026-10-23 mục 6; FR-19, BR-09, BR-11).

Hóa đơn chỉ ở dạng nháp: Kế toán kiểm rồi Nộp (FR-23). Mỗi dòng gắn Đơn mua và Phiếu nhập — số lượng
phân bổ vào các dòng Phiếu nhập còn chưa lập hóa đơn theo thứ tự ngày nhập — để hóa đơn đi tiếp qua
đối soát Phiếu nhập ↔ Hóa đơn của Đợt 3 như hóa đơn nhập tay. Hóa đơn gốc có hóa đơn điều chỉnh: lập
theo số sau điều chỉnh, một Hóa đơn mua cho cả hai (`hoa_don_lien_quan`).

Trạng thái phiếu đi theo Hóa đơn mua: nháp → Đã tạo nháp hóa đơn mua, hoặc Lệch PR-PI (ST-05a) khi đối
soát Đợt 3 báo Lệch; Nộp → Đã ghi sổ; hủy / xóa → phiếu mở lại.
"""

import frappe
from frappe import _
from frappe.utils import flt, get_link_to_form, now_datetime

from erpnext.accounts.doi_soat_pr_pi.doi_soat import LECH
from erpnext.accounts.doi_soat_pr_pi.ghep_dong import con_cho_lap_hoa_don
from erpnext.buying.tiep_nhan_hoa_don import hoa_don_lien_quan
from erpnext.buying.tiep_nhan_hoa_don.cau_hinh import bo_chuan_hoa
from erpnext.buying.tiep_nhan_hoa_don.doi_soat import (
	CHO_XU_LY,
	CHON_TAY,
	DA_DOI_SOAT,
	DA_GHI_SO,
	DA_TAO_HD,
	DIEU_CHINH,
	LECH_PR_PI,
	TANG_2,
	TANG_3,
	TU_CHOI,
	don_gia,
	so_luong,
	xoa_hoa_don_nhap,
)
from erpnext.buying.tiep_nhan_hoa_don.hop_dong_khung import cap_nhat_da_lap_hoa_don
from erpnext.controllers.accounts_controller import get_taxes_and_charges

PHIEU = "Supplier Invoice Intake"


def _phan_bo_phieu_nhap(po_detail, sl_kho):
	"""[(Phiếu nhập, dòng Phiếu nhập, số lượng ĐVT kho)] theo thứ tự ngày nhập, và cờ "còn phần chưa
	lập hóa đơn" (hóa đơn từng phần). Hóa đơn nhiều hơn phần còn lại thì dồn phần dư vào phiếu cuối
	để đối soát Đợt 3 báo Lệch số lượng, không lặng lẽ cắt bớt."""
	pri = frappe.qb.DocType("Purchase Receipt Item")
	pr = frappe.qb.DocType("Purchase Receipt")
	dong = (
		frappe.qb.from_(pri)
		.join(pr)
		.on(pr.name == pri.parent)
		.select(pri.name, pri.parent)
		.where((pri.purchase_order_item == po_detail) & (pr.docstatus == 1) & (pr.is_return == 0))
		.orderby(pr.posting_date)
		.orderby(pr.posting_time)
		.orderby(pr.creation)
		.run(as_dict=True)
	)
	if not dong:
		return [], False
	con = con_cho_lap_hoa_don([d.name for d in dong])
	phan, can = [], sl_kho
	for d in dong:
		q = min(flt(con.get(d.name)), can)
		if q > 0:
			phan.append([d.parent, d.name, q])
			can -= q
	if can > 1e-9:
		if phan:
			phan[-1][2] += can
		else:
			phan = [[dong[-1].parent, dong[-1].name, can]]
	tung_phan = any(flt(con.get(prd)) - q > 1e-9 for _pr, prd, q in phan)
	return phan, tung_phan


@frappe.whitelist()
def tao_hoa_don_mua(phieu):
	doc = frappe.get_doc(PHIEU, phieu)
	doc.check_permission("write")
	if doc.tinh_chat_hoa_don == DIEU_CHINH:
		return _lap_theo_dieu_chinh(doc)
	if doc.purchase_invoice and frappe.db.get_value(
		"Purchase Invoice", doc.purchase_invoice, "docstatus"
	) in (0, 1):
		frappe.throw(
			_("Phiếu đã có Hóa đơn mua {0}.").format(
				get_link_to_form("Purchase Invoice", doc.purchase_invoice)
			)
		)
	if doc.trang_thai != DA_DOI_SOAT:
		frappe.throw(_("Phiếu chưa đối soát xong (trạng thái {0}).").format(doc.trang_thai))
	bi_thay_the = hoa_don_lien_quan.ly_do_bi_thay_the(doc)
	if bi_thay_the:
		frappe.throw(bi_thay_the + " " + _("Lưu lại phiếu để chuyển Từ chối."))
	dieu_chinh = [p for p in hoa_don_lien_quan.phieu_dieu_chinh(doc.name) if p.dieu_chinh_hop_le]

	pi = frappe.new_doc("Purchase Invoice")
	pi.update(
		{
			"company": doc.company,
			"supplier": doc.supplier,
			"bill_no": doc.so_hoa_don,
			"bill_date": doc.ngay_hoa_don,
			"phieu_tiep_nhan": doc.name,
		}
	)
	tung_phan, don_mua, loi = False, [], []
	for row in doc.items:
		sl = so_luong(row)
		if row.get("dieu_chinh") and not sl:
			continue  # điều chỉnh giảm hết số lượng
		po = frappe.db.get_value(
			"Purchase Order Item",
			row.po_detail,
			["parent", "uom", "conversion_factor", "warehouse", "item_code"],
			as_dict=True,
		)
		cf = flt(po.conversion_factor) or 1
		chung = {
			"item_code": row.item_code,
			"uom": po.uom,
			"conversion_factor": cf,
			"rate": don_gia(row),
			"purchase_order": po.parent,
			"po_detail": row.po_detail,
			"warehouse": po.warehouse,
			"ten_tren_hoa_don": row.ten_hang_hd,
			"hop_dong_khung": row.blanket_order,
			"ma_dong_hdk": row.ma_dong_hdk,
			"cach_khop": row.cach_khop,
			"diem_khop": row.diem_khop,
		}
		if po.parent not in don_mua:
			don_mua.append(po.parent)
		if not frappe.get_cached_value("Item", row.item_code, "is_stock_item"):
			pi.append("items", {**chung, "qty": sl})
			continue
		phan, tp = _phan_bo_phieu_nhap(row.po_detail, sl * cf)
		if not phan:
			loi.append(
				_("Dòng {0} ({1}): chưa có Phiếu nhập mua cho Đơn mua {2}. Chờ Kho nhập hàng.").format(
					row.idx, row.item_code, po.parent
				)
			)
			continue
		tung_phan = tung_phan or tp
		for pr, pr_detail, q in phan:
			pi.append(
				"items",
				{**chung, "qty": flt(q / cf, 6), "purchase_receipt": pr, "pr_detail": pr_detail},
			)
	if loi:
		frappe.throw("<br>".join(loi), title=_("Chưa tạo được Hóa đơn mua"))
	if not pi.items:
		frappe.throw(_("Sau điều chỉnh không còn dòng nào để lập Hóa đơn mua."))
	if dieu_chinh:
		pi.hoa_don_dieu_chinh = "\n".join(
			_("{0} {1} ngày {2} (phiếu {3})").format(
				p.ky_hieu, p.so_hoa_don, frappe.format_value(p.ngay_hoa_don, {"fieldtype": "Date"}), p.name
			)
			for p in dieu_chinh
		)

	mau_thue = frappe.db.get_value("Purchase Order", don_mua[0], "taxes_and_charges") if don_mua else None
	if mau_thue:
		pi.taxes_and_charges = mau_thue
		pi.set("taxes", get_taxes_and_charges("Purchase Taxes and Charges Template", mau_thue))
	if tung_phan and pi.meta.has_field("hoa_don_tung_phan"):
		pi.hoa_don_tung_phan = 1
	pi.set_missing_values()
	pi.flags.ignore_permissions = True
	pi.insert()

	_dinh_kem(doc, pi)
	doc.db_set({"purchase_invoice": pi.name, "trang_thai": DA_TAO_HD})
	doc.add_comment("Info", _("Đã tạo Hóa đơn mua nháp {0}.").format(pi.name))
	for p in dieu_chinh:
		_dinh_kem(p, pi)
		frappe.db.set_value(PHIEU, p.name, {"purchase_invoice": pi.name, "trang_thai": DA_TAO_HD})
		frappe.get_doc(PHIEU, p.name).add_comment(
			"Info", _("Gộp vào Hóa đơn mua nháp {0} của hóa đơn gốc {1}.").format(pi.name, doc.name)
		)
	_ghi_anh_xa(doc)
	dong_bo_phieu(pi)
	return pi.name


def _lap_theo_dieu_chinh(dc):
	"""Phiếu hóa đơn điều chỉnh: lập (lại) Hóa đơn mua nháp của hóa đơn gốc theo số sau điều chỉnh.
	Bản nháp cũ của hóa đơn gốc bị xóa; lỗi ở bước nào thì cả lần bấm được hoàn tác."""
	if dc.trang_thai != DA_DOI_SOAT or not dc.phieu_lien_quan:
		frappe.throw(_("Phiếu điều chỉnh chưa xử lý xong (trạng thái {0}).").format(dc.trang_thai))
	goc = frappe.get_doc(PHIEU, dc.phieu_lien_quan)
	if goc.purchase_invoice:
		trang_thai_hd = frappe.db.get_value("Purchase Invoice", goc.purchase_invoice, "docstatus")
		if trang_thai_hd == 1:
			frappe.throw(_("Hóa đơn gốc đã ghi sổ ở Hóa đơn mua {0}.").format(goc.purchase_invoice))
		if trang_thai_hd == 0:
			xoa_hoa_don_nhap(goc.purchase_invoice)
		goc.reload()
	goc.flags.ignore_permissions = True
	goc.save()
	if goc.trang_thai != DA_DOI_SOAT:
		frappe.throw(
			_("Phiếu gốc {0} chưa đối soát xong sau khi gộp điều chỉnh ({1}). {2}").format(
				get_link_to_form(PHIEU, goc.name), goc.trang_thai, goc.canh_bao or ""
			),
			title=_("Chưa lập được Hóa đơn mua"),
		)
	return tao_hoa_don_mua(goc.name)


def _dinh_kem(doc, pi):
	"""Tệp XML gốc gắn sang hóa đơn: bản ghi File mới trỏ cùng tệp, không chép nội dung."""
	f = frappe.db.get_value("File", {"file_url": doc.tep_hoa_don}, ["file_name", "is_private"], as_dict=True)
	if not f:
		return
	frappe.get_doc(
		{
			"doctype": "File",
			"file_url": doc.tep_hoa_don,
			"file_name": f.file_name,
			"is_private": f.is_private,
			"attached_to_doctype": "Purchase Invoice",
			"attached_to_name": pi.name,
		}
	).insert(ignore_permissions=True)


def _ghi_anh_xa(doc):
	"""FR-22: khớp ở tầng 3 / chọn tay → đề xuất Bảng ánh xạ tên (Chờ duyệt); tầng 2 → đếm số lần dùng."""
	bo = bo_chuan_hoa()
	for row in doc.items:
		ten = bo.chuan_hoa(row.ten_hang_hd)
		if not ten:
			continue
		if row.cach_khop == TANG_2:
			for ten_ax in frappe.get_all(
				"Supplier Item Alias",
				filters={"supplier": doc.supplier, "ten_chuan_hoa": ten, "trang_thai": "Đang dùng"},
				pluck="name",
			):
				frappe.db.set_value(
					"Supplier Item Alias",
					ten_ax,
					{
						"so_lan_dung": (
							frappe.db.get_value("Supplier Item Alias", ten_ax, "so_lan_dung") or 0
						)
						+ 1,
						"lan_cuoi": now_datetime(),
					},
					update_modified=False,
				)
		elif row.cach_khop in (TANG_3, CHON_TAY) and not frappe.db.exists(
			"Supplier Item Alias",
			{"supplier": doc.supplier, "ten_chuan_hoa": ten, "trang_thai": ("!=", "Ngừng dùng")},
		):
			frappe.get_doc(
				{
					"doctype": "Supplier Item Alias",
					"supplier": doc.supplier,
					"ten_tren_hoa_don": row.ten_hang_hd,
					"item_code": row.item_code,
					"trang_thai": "Chờ duyệt",
					"nguon": "Khớp theo Đơn mua" if row.cach_khop == TANG_3 else "Người dùng chọn tay",
					"phieu_tiep_nhan": doc.name,
				}
			).insert(ignore_permissions=True)


# --- doc_events của Purchase Invoice ---------------------------------------------


def _po_details(doc):
	return {d.po_detail for d in doc.items if d.get("po_detail")}


def _phieu_cua(doc):
	return frappe.get_all(
		PHIEU,
		filters={"purchase_invoice": doc.name},
		fields=["name", "trang_thai", "tinh_chat_hoa_don", "hoa_don_mua_lien_quan"],
	)


def khi_luu_hoa_don(doc, method=None):
	"""`on_update` (cả lúc Nộp): nối Hóa đơn mua kế toán lập tay cho hóa đơn điều chỉnh; ST-05 / ST-05a."""
	_noi_phieu_dieu_chinh(doc)
	dong_bo_phieu(doc)


def dong_bo_phieu(pi):
	"""ST-05 / ST-05a: phiếu của Hóa đơn mua nháp đi theo kết quả đối soát Phiếu nhập (Đợt 3)."""
	if pi.docstatus != 0:
		return
	moi = LECH_PR_PI if pi.get("trang_thai_doi_soat_pr") == LECH else DA_TAO_HD
	for p in _phieu_cua(pi):
		if p.trang_thai in (DA_TAO_HD, LECH_PR_PI) and p.trang_thai != moi:
			frappe.db.set_value(PHIEU, p.name, "trang_thai", moi)
			frappe.get_doc(PHIEU, p.name).add_comment(
				"Info",
				(
					_("Hóa đơn mua {0} lệch Phiếu nhập mua: phiếu chuyển {1}.")
					if moi == LECH_PR_PI
					else _("Hóa đơn mua {0} hết lệch Phiếu nhập mua: phiếu về {1}.")
				).format(pi.name, moi),
			)


def _noi_phieu_dieu_chinh(pi):
	"""Hóa đơn gốc đã ghi sổ: kế toán lập tay Hóa đơn mua trả hàng / bổ sung với Số hóa đơn NCC = số
	hóa đơn điều chỉnh. Lưu chứng từ đó thì phiếu điều chỉnh đang chờ nối vào nó."""
	if pi.get("phieu_tiep_nhan") or not pi.bill_no or _phieu_cua(pi):
		return
	so = hoa_don_lien_quan.so_hd(pi.bill_no)
	cho = [
		p
		for p in frappe.get_all(
			PHIEU,
			filters={
				"supplier": pi.supplier,
				"tinh_chat_hoa_don": DIEU_CHINH,
				"purchase_invoice": ("is", "not set"),
				"trang_thai": ("!=", TU_CHOI),
			},
			fields=["name", "so_hoa_don", "hoa_don_mua_lien_quan"],
		)
		if hoa_don_lien_quan.so_hd(p.so_hoa_don) == so
		and p.hoa_don_mua_lien_quan
		and frappe.db.get_value("Purchase Invoice", p.hoa_don_mua_lien_quan, "docstatus") == 1
	]
	if len(cho) != 1:
		return
	frappe.db.set_value(PHIEU, cho[0].name, {"purchase_invoice": pi.name, "trang_thai": DA_TAO_HD})
	pi.db_set("phieu_tiep_nhan", cho[0].name, update_modified=False)
	frappe.get_doc(PHIEU, cho[0].name).add_comment(
		"Info", _("Nối vào Hóa đơn mua {0} kế toán lập cho hóa đơn điều chỉnh này.").format(pi.name)
	)


def khi_nop_hoa_don(doc, method=None):
	cap_nhat_da_lap_hoa_don(_po_details(doc))
	for p in _phieu_cua(doc):
		frappe.db.set_value(PHIEU, p.name, "trang_thai", DA_GHI_SO)


def khi_huy_hoa_don(doc, method=None):
	cap_nhat_da_lap_hoa_don(_po_details(doc))
	hoa_don_lien_quan.tinh_lai_theo_goc(_tra_phieu(doc, _("Hóa đơn mua {0} đã hủy.")))


def khi_xoa_hoa_don(doc, method=None):
	"""`on_trash`: hóa đơn nháp bị xóa thì phiếu mở lại, tạo được hóa đơn khác. Phiếu thay thế / điều
	chỉnh trỏ tới hóa đơn này như hóa đơn mua của hóa đơn gốc: gỡ trỏ để Frappe không chặn xóa (lần lưu
	sau tính lại)."""
	doc.flags.phieu_da_tra = _tra_phieu(doc, _("Hóa đơn mua nháp {0} đã xóa."))
	for ten in frappe.get_all(PHIEU, filters={"hoa_don_mua_lien_quan": doc.name}, pluck="name"):
		frappe.db.set_value(PHIEU, ten, "hoa_don_mua_lien_quan", None, update_modified=False)


def sau_khi_xoa_hoa_don(doc, method=None):
	"""`after_delete`: hóa đơn đã ra khỏi cơ sở dữ liệu, tính lại được phiếu thay thế / điều chỉnh."""
	hoa_don_lien_quan.tinh_lai_theo_goc(doc.flags.get("phieu_da_tra") or [])


def _tra_phieu(doc, ghi_chu):
	"""Các phiếu trỏ vào hóa đơn mở lại; trả về tên các phiếu đó. Phiếu điều chỉnh nối vào chứng từ lập
	tay (hóa đơn gốc đã ghi sổ) về Chờ xử lý thủ công, chờ chứng từ khác."""
	ds = _phieu_cua(doc)
	for p in ds:
		cho_lap_tay = (
			p.tinh_chat_hoa_don == DIEU_CHINH
			and p.hoa_don_mua_lien_quan
			and p.hoa_don_mua_lien_quan != doc.name
			and frappe.db.get_value("Purchase Invoice", p.hoa_don_mua_lien_quan, "docstatus") == 1
		)
		frappe.db.set_value(
			PHIEU, p.name, {"trang_thai": CHO_XU_LY if cho_lap_tay else DA_DOI_SOAT, "purchase_invoice": None}
		)
		frappe.get_doc(PHIEU, p.name).add_comment("Info", ghi_chu.format(doc.name))
	return [p.name for p in ds]
