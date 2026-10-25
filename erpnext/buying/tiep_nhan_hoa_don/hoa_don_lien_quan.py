# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Hóa đơn thay thế và hóa đơn điều chỉnh (NĐ 123/2020 Điều 19; XML `TTChung/TTHDLQuan`).

Hóa đơn gốc tìm theo MST người bán + ký hiệu + số hóa đơn ghi trong phần hóa đơn liên quan.

Thay thế: hóa đơn mới thay toàn bộ hóa đơn cũ. Hóa đơn cũ chưa có Hóa đơn mua thì phiếu của nó tự Từ
chối. Có Hóa đơn mua nháp thì phiếu mới dừng cho tới khi bản nháp được bỏ (nút Bỏ hóa đơn bị thay
thế); đã ghi sổ thì phải hủy Hóa đơn mua đó trước.

Điều chỉnh: hóa đơn chỉ ghi phần tăng (dương) / giảm (âm). Hóa đơn gốc chưa ghi sổ thì gộp vào MỘT
Hóa đơn mua theo số SAU điều chỉnh: mỗi dòng điều chỉnh cộng vào dòng hóa đơn gốc nó điều chỉnh, và
phiếu gốc đối soát, lập hóa đơn trên số đó. Hóa đơn gốc đã ghi sổ thì kế toán lập tay Hóa đơn mua trả
hàng / bổ sung với Số hóa đơn NCC = số hóa đơn điều chỉnh; phiếu tự nối vào chứng từ đó.
"""

import math

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.buying.tiep_nhan_hoa_don.cau_hinh import bo_chuan_hoa
from erpnext.buying.tiep_nhan_hoa_don.doi_soat import (
	CHUA_KHOP,
	CO_HOA_DON,
	DA_KHOP,
	DIEU_CHINH,
	DONG_GOC,
	DUNG_SAI_TIEN,
	THAY_THE,
	TU_CHOI,
	_so,
	_tien,
	xoa_hoa_don_nhap,
)

PHIEU = "Supplier Invoice Intake"
KIEU_SO_LUONG = "Số lượng"
KIEU_DON_GIA = "Đơn giá"


def so_hd(so):
	"""Số hóa đơn so theo giá trị: 0000123 = 123."""
	so = (so or "").strip()
	return (so.lstrip("0") or so) if so.isdigit() else so


def tim_hoa_don_goc(doc):
	"""(phiếu, Hóa đơn mua) của hóa đơn bị thay thế / bị điều chỉnh. Nhiều phiếu cùng hóa đơn (bản trùng
	bị Từ chối): giữ phiếu đang nối, rồi phiếu chưa Từ chối, rồi phiếu cũ nhất."""
	so = so_hd(doc.so_hoa_don_lien_quan)
	if not (so and doc.mst_nguoi_ban):
		return None, None
	ds = [
		p
		for p in frappe.get_all(
			PHIEU,
			filters={
				"name": ("!=", doc.name or ""),
				"mst_nguoi_ban": doc.mst_nguoi_ban,
				"ky_hieu": doc.ky_hieu_lien_quan,
			},
			fields=["name", "so_hoa_don", "trang_thai", "purchase_invoice"],
			order_by="creation",
		)
		if so_hd(p.so_hoa_don) == so
	]
	ds.sort(key=lambda p: (p.name != doc.phieu_lien_quan, p.trang_thai == TU_CHOI))
	phieu = ds[0] if ds else None

	hd = None
	if phieu and phieu.purchase_invoice:
		hd = frappe.db.get_value(
			"Purchase Invoice", phieu.purchase_invoice, ["name", "docstatus"], as_dict=True
		)
	if not (hd and hd.docstatus < 2) and doc.supplier:
		# Hóa đơn gốc nhập tay (không qua phiếu, hoặc phiếu bị Từ chối vì trùng Hóa đơn mua đó).
		hd = _hoa_don_mua_theo_so(doc.supplier, doc.so_hoa_don_lien_quan)
	return phieu, (hd if hd and hd.docstatus < 2 else None)


def _hoa_don_mua_theo_so(supplier, so, bo_qua=None):
	ds = frappe.get_all(
		"Purchase Invoice",
		filters={
			"supplier": supplier,
			"docstatus": ("<", 2),
			"bill_no": ("in", list({so, so_hd(so)})),
			"name": ("not in", bo_qua or [""]),
		},
		fields=["name", "docstatus", "phieu_tiep_nhan"],
		order_by="docstatus desc, creation",
	)
	return ds[0] if ds else None


def ly_do_bi_thay_the(doc):
	"""Phiếu bị một hóa đơn thay thế (chưa Từ chối) trỏ tới thì Từ chối, kèm lý do."""
	if not doc.name:
		return None
	tt = frappe.get_all(
		PHIEU,
		filters={"phieu_lien_quan": doc.name, "tinh_chat_hoa_don": THAY_THE, "trang_thai": ("!=", TU_CHOI)},
		fields=["name", "ky_hieu", "so_hoa_don"],
		order_by="creation",
		limit=1,
	)
	if tt:
		return _("Hóa đơn đã bị thay thế bởi hóa đơn {0} {1} (phiếu {2}).").format(
			tt[0].ky_hieu, tt[0].so_hoa_don, tt[0].name
		)


# --- Đầu phiếu thay thế / điều chỉnh -----------------------------------------------------


def kiem(doc, canh_bao):
	"""Tìm hóa đơn gốc, ghi liên kết. Trả về True khi phiếu phải dừng ở Chờ xử lý thủ công."""
	phieu = hd = None
	if doc.tinh_chat_hoa_don in (THAY_THE, DIEU_CHINH):
		phieu, hd = tim_hoa_don_goc(doc)
	doc.phieu_lien_quan = phieu.name if phieu else None
	doc.hoa_don_mua_lien_quan = hd.name if hd else None
	if doc.tinh_chat_hoa_don not in (THAY_THE, DIEU_CHINH):
		return False

	ten = f"{doc.ky_hieu_lien_quan or ''} {doc.so_hoa_don_lien_quan or ''}".strip()
	phieu_lap = bool(hd and phieu and phieu.purchase_invoice == hd.name)
	if doc.tinh_chat_hoa_don == THAY_THE:
		return _kiem_thay_the(phieu, hd, phieu_lap, ten, canh_bao)
	return _kiem_dieu_chinh(doc, phieu, hd, phieu_lap, ten, canh_bao)


def _kiem_thay_the(phieu, hd, phieu_lap, ten, canh_bao):
	if hd and hd.docstatus == 1:
		canh_bao.append(
			_(
				"Hóa đơn bị thay thế {0} đã ghi sổ ở Hóa đơn mua {1}: hủy hóa đơn mua đó (gỡ thanh toán,"
				" Đề nghị thanh toán nếu có) rồi Lưu lại phiếu này."
			).format(ten, hd.name)
		)
		return True
	if hd and phieu_lap:
		canh_bao.append(
			_(
				"Hóa đơn bị thay thế {0} đang có Hóa đơn mua nháp {1} (phiếu {2}): bấm Bỏ hóa đơn bị"
				" thay thế để xóa bản nháp đó; phiếu {2} chuyển Từ chối."
			).format(ten, hd.name, phieu.name)
		)
		return True
	if hd:
		canh_bao.append(
			_(
				"Hóa đơn bị thay thế {0} đang có Hóa đơn mua nháp {1} nhập tay: xóa bản nháp đó rồi Lưu"
				" lại phiếu này."
			).format(ten, hd.name)
		)
		return True
	if not phieu:
		canh_bao.append(_("Thay thế hóa đơn {0}; hóa đơn đó chưa có trên hệ thống.").format(ten))
	return False


def _kiem_dieu_chinh(doc, phieu, hd, phieu_lap, ten, canh_bao):
	# Phiếu đang nối vào Hóa đơn mua thì đã khóa (xu_ly không tính lại): tới đây là chưa nối, hoặc
	# chứng từ lập tay đã bị hủy.
	doc.purchase_invoice = None
	if not (phieu or hd):
		canh_bao.append(
			_(
				"Chưa có hóa đơn gốc {0} trên hệ thống: tiếp nhận hóa đơn gốc trước rồi Lưu lại phiếu này."
			).format(ten)
		)
		return True
	if phieu and phieu.trang_thai == TU_CHOI and not hd:
		canh_bao.append(
			_(
				"Phiếu {0} của hóa đơn gốc {1} đã Từ chối: không gộp được điều chỉnh. Mở lại phiếu đó, hoặc"
				" Từ chối phiếu này."
			).format(phieu.name, ten)
		)
		return True
	if hd and hd.docstatus == 1:
		lap = doc.supplier and _hoa_don_mua_theo_so(doc.supplier, doc.so_hoa_don, bo_qua=[hd.name])
		if lap and lap.phieu_tiep_nhan in (None, "", doc.name):
			doc.purchase_invoice = lap.name  # xu_ly đặt trạng thái theo chứng từ này
			return False
		canh_bao.append(
			_(
				"Hóa đơn gốc {0} đã ghi sổ ở Hóa đơn mua {1}. Kế toán lập tay Hóa đơn mua trả hàng (điều"
				" chỉnh giảm) hoặc Hóa đơn mua bổ sung (điều chỉnh tăng), Số hóa đơn NCC ghi {2}; phiếu"
				" này tự nối vào chứng từ đó."
			).format(ten, hd.name, doc.so_hoa_don)
		)
		return True
	if hd and not phieu_lap:
		canh_bao.append(
			_(
				"Hóa đơn gốc {0} nhập tay ở Hóa đơn mua nháp {1}: sửa tay hóa đơn đó theo số sau điều"
				" chỉnh rồi Từ chối phiếu này."
			).format(ten, hd.name)
		)
		return True
	return False


# --- Dòng hóa đơn điều chỉnh --------------------------------------------------------------


def khop_dieu_chinh(doc, c, canh_bao):
	"""Gắn mỗi dòng với dòng hóa đơn gốc nó điều chỉnh — mã trên hóa đơn, rồi tên chuẩn hóa, rồi hóa đơn
	gốc chỉ có một dòng; không được thì người dùng chọn STT — và kiểu điều chỉnh (Số lượng / Đơn giá).
	Trả về True khi phải xử lý ngoài hệ thống (đổi thuế suất)."""
	goc = frappe.get_doc(PHIEU, doc.phieu_lien_quan) if doc.phieu_lien_quan else None
	dong_goc = {r.stt: r for r in goc.items} if goc else {}
	bo = bo_chuan_hoa(c)
	chan = False
	for row in doc.items:
		for f in (
			"item_code",
			"purchase_order",
			"po_detail",
			"blanket_order",
			"ma_dong_hdk",
			"cach_khop",
			"diem_khop",
			"canh_bao",
			"canh_bao_chan",
		):
			row.set(f, None)
		if not (row.chon_tay and row.dong_goc in dong_goc):
			row.chon_tay = 0
			row.dong_goc = _tim_dong_goc(row, list(dong_goc.values()), bo)
			row.kieu_dieu_chinh = None
		g = dong_goc.get(row.dong_goc)
		if not g:
			row.trang_thai_dong = CHUA_KHOP
			if dong_goc:
				row.canh_bao = _("Chọn Dòng hóa đơn gốc (STT 1 – {0}) mà dòng này điều chỉnh.").format(
					max(dong_goc)
				)
			continue
		row.update(
			{
				"kieu_dieu_chinh": row.kieu_dieu_chinh or _kieu(row, g),
				"item_code": g.item_code,
				"purchase_order": g.purchase_order,
				"po_detail": g.po_detail,
				"blanket_order": g.blanket_order,
				"ma_dong_hdk": g.ma_dong_hdk,
				"cach_khop": DONG_GOC,
				"trang_thai_dong": DA_KHOP,
			}
		)
		if row.thue_suat and g.thue_suat and row.thue_suat != g.thue_suat:
			chan = True
			row.canh_bao = _(
				"Điều chỉnh thuế suất {0} → {1}: hệ thống không gộp được. Kế toán xử lý tay rồi Từ chối"
				" phiếu này."
			).format(g.thue_suat, row.thue_suat)
	return chan


def _tim_dong_goc(row, dong_goc, bo):
	ma = (row.ma_hang_hd or "").strip()
	if ma:
		cung = [g for g in dong_goc if (g.ma_hang_hd or "").strip() == ma]
		if len(cung) == 1:
			return cung[0].stt
	ten = bo.chuan_hoa(row.ten_hang_hd)
	if ten:
		cung = [g for g in dong_goc if bo.chuan_hoa(g.ten_hang_hd) == ten]
		if len(cung) == 1:
			return cung[0].stt
		# Tên dòng điều chỉnh hay kèm lời như "Điều chỉnh giảm số lượng ..." trước tên hàng.
		cung = [g for g in dong_goc if bo.chuan_hoa(g.ten_hang_hd) and bo.chuan_hoa(g.ten_hang_hd) in ten]
		if len(cung) == 1:
			return cung[0].stt
	return dong_goc[0].stt if len(dong_goc) == 1 else None


def _kieu(row, g):
	"""Đơn giá trên dòng bằng đơn giá hóa đơn gốc: dòng đổi số lượng. Không ghi số lượng, hoặc đơn giá
	là phần chênh: dòng đổi giá, số lượng giữ nguyên."""
	if not flt(row.so_luong):
		return KIEU_DON_GIA
	return KIEU_SO_LUONG if abs(abs(flt(row.don_gia)) - flt(g.don_gia)) <= DUNG_SAI_TIEN else KIEU_DON_GIA


def _sl_tang(d):
	"""Phần tăng (giảm: âm) của số lượng. Hóa đơn có thể ghi dấu âm ở số lượng hoặc ở đơn giá: lấy dấu
	theo thành tiền."""
	if d.kieu_dieu_chinh != KIEU_SO_LUONG:
		return 0
	if not flt(d.thanh_tien):
		return flt(d.so_luong)
	return math.copysign(abs(flt(d.so_luong)), flt(d.thanh_tien))


# --- Phiếu hóa đơn gốc: gộp điều chỉnh ---------------------------------------------------


def phieu_dieu_chinh(goc):
	"""Phiếu điều chỉnh của phiếu gốc còn hiệu lực, chưa nối vào Hóa đơn mua nào."""
	return frappe.get_all(
		PHIEU,
		filters={
			"phieu_lien_quan": goc,
			"tinh_chat_hoa_don": DIEU_CHINH,
			"trang_thai": ("!=", TU_CHOI),
			"purchase_invoice": ("is", "not set"),
		},
		fields=["name", "ky_hieu", "so_hoa_don", "ngay_hoa_don", "dieu_chinh_hop_le", "tep_hoa_don"],
		order_by="ngay_hoa_don, creation",
	)


def ap_dieu_chinh(doc, canh_bao):
	"""Cộng các hóa đơn điều chỉnh đã xử lý xong vào từng dòng; số sau điều chỉnh dùng để đối soát và
	lập Hóa đơn mua. Trả về True khi còn hóa đơn điều chỉnh chưa xử lý xong hoặc số sau điều chỉnh âm."""
	ds = phieu_dieu_chinh(doc.name) if doc.name else []
	chan = False
	for p in ds:
		if not p.dieu_chinh_hop_le:
			chan = True
			canh_bao.append(
				_("Hóa đơn điều chỉnh {0} {1} (phiếu {2}) chưa xử lý xong: xử lý phiếu đó trước.").format(
					p.ky_hieu, p.so_hoa_don, p.name
				)
			)
	xong = {p.name: p for p in ds if p.dieu_chinh_hop_le}
	dong = frappe.get_all(
		"Supplier Invoice Intake Item",
		filters={"parenttype": PHIEU, "parent": ("in", list(xong) or [""])},
		fields=["parent", "dong_goc", "kieu_dieu_chinh", "so_luong", "thanh_tien"],
		order_by="parent, idx",
	)
	for row in doc.items:
		cua = [d for d in dong if d.dong_goc == row.stt]
		if not cua:
			row.update(
				dict.fromkeys(("dieu_chinh", "so_luong_sau_dc", "don_gia_sau_dc", "thanh_tien_sau_dc"))
			)
			continue
		sl = flt(row.so_luong) + sum(_sl_tang(d) for d in cua)
		tien = flt(row.thanh_tien) + sum(flt(d.thanh_tien) for d in cua)
		row.update(
			{
				"so_luong_sau_dc": sl,
				"thanh_tien_sau_dc": tien,
				"don_gia_sau_dc": tien / sl if sl else 0,
				"dieu_chinh": "\n".join(
					_("{0} {1} ({2}): số lượng {3}, thành tiền {4}").format(
						xong[d.parent].ky_hieu,
						xong[d.parent].so_hoa_don,
						d.kieu_dieu_chinh,
						_co_dau(_so, _sl_tang(d)),
						_co_dau(_tien, d.thanh_tien),
					)
					for d in cua
				),
			}
		)
		if sl < 0 or tien < 0 or (not sl and abs(tien) > DUNG_SAI_TIEN):
			chan = True
			canh_bao.append(
				_(
					"Dòng {0}: sau điều chỉnh số lượng {1}, thành tiền {2} — không hợp lệ, kiểm lại hóa đơn"
					" điều chỉnh."
				).format(row.stt, _so(sl), _tien(tien))
			)
	return chan


def _co_dau(dinh_dang, x):
	return ("+" if flt(x) > 0 else "") + dinh_dang(x)


# --- Tính lại phiếu liên quan -------------------------------------------------------------


def sau_khi_luu(doc, method=None):
	"""`on_update` / `after_delete` của phiếu thay thế / điều chỉnh: tính lại phiếu hóa đơn gốc (bị thay
	thế thì Từ chối; điều chỉnh thì gộp số sau điều chỉnh), trừ khi phiếu gốc đã có Hóa đơn mua."""
	truoc = doc.get_doc_before_save() if method == "on_update" else None
	for ten in {doc.phieu_lien_quan, truoc and truoc.phieu_lien_quan} - {None}:
		if not frappe.db.exists(PHIEU, ten):
			continue
		goc = frappe.get_doc(PHIEU, ten)
		if goc.purchase_invoice and goc.trang_thai in CO_HOA_DON:
			continue
		goc.flags.ignore_permissions = True
		goc.save()
	if (
		method == "on_update"
		and doc.purchase_invoice
		and doc.tinh_chat_hoa_don == DIEU_CHINH
		and not frappe.db.get_value("Purchase Invoice", doc.purchase_invoice, "phieu_tiep_nhan")
	):
		# Hóa đơn mua kế toán lập tay cho hóa đơn điều chỉnh: trỏ ngược về phiếu.
		frappe.db.set_value(
			"Purchase Invoice", doc.purchase_invoice, "phieu_tiep_nhan", doc.name, update_modified=False
		)


def tinh_lai_theo_goc(goc):
	"""Phiếu gốc vừa thôi trỏ vào Hóa đơn mua (hóa đơn bị xóa / hủy): tính lại các phiếu thay thế /
	điều chỉnh của nó; các phiếu đó tính lại phiếu gốc khi lưu."""
	for ten in frappe.get_all(
		PHIEU,
		filters={
			"phieu_lien_quan": ("in", list(goc) or [""]),
			"trang_thai": ("!=", TU_CHOI),
			"purchase_invoice": ("is", "not set"),
		},
		pluck="name",
	):
		p = frappe.get_doc(PHIEU, ten)
		p.flags.ignore_permissions = True
		p.save()


@frappe.whitelist()
def bo_hoa_don_bi_thay_the(phieu):
	"""Phiếu hóa đơn thay thế: xóa Hóa đơn mua nháp của hóa đơn bị thay thế (bản nháp phiếu tiếp nhận
	lập); phiếu cũ chuyển Từ chối, phiếu này đối soát tiếp."""
	doc = frappe.get_doc(PHIEU, phieu)
	doc.check_permission("write")
	hd = doc.phieu_lien_quan and frappe.db.get_value(PHIEU, doc.phieu_lien_quan, "purchase_invoice")
	if (
		doc.tinh_chat_hoa_don != THAY_THE
		or not hd
		or frappe.db.get_value("Purchase Invoice", hd, "docstatus") != 0
	):
		frappe.throw(_("Hóa đơn bị thay thế không có Hóa đơn mua nháp do phiếu tiếp nhận lập."))
	xoa_hoa_don_nhap(hd)
	doc.reload()
	doc.save()
	return doc.trang_thai
