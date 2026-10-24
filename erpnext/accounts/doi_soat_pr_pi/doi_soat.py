# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Đối soát Hóa đơn mua với Phiếu nhập mua, dung sai 0 đồng (YC5, spec 6.3.3-6.3.6; D7, E7-E10).

Thời điểm chạy (6.3.5): mỗi lần lưu hóa đơn nháp (kể cả nút Đối soát lại), khi Phiếu nhập liên
quan được Nộp hoặc bị hủy, và một lần nữa lúc Nộp hóa đơn. Mỗi lần tính lại từ đầu nên cho cùng
kết quả. `before_submit` chặn hóa đơn chưa Khớp, trừ khi có ngoại lệ được duyệt (E8).

So theo ĐVT kho và giá trước thuế (`net_rate`) để "cùng kiểu thuế" (thuế gồm trong đơn giá hay
không đều so được). Số lượng hóa đơn phải bằng số Phiếu nhập đã nhận chưa lập hóa đơn.
"""

import hashlib
import json

import frappe
from frappe import _
from frappe.utils import cint, flt, fmt_money, now_datetime, today

from erpnext.accounts.doi_soat_pr_pi import ghep_dong, vuot_hoa_don
from erpnext.accounts.doi_soat_pr_pi.cau_hinh import ap_dung, cau_hinh, co_quyen_duyet_ngoai_le

KHOP = "Khớp"
LECH = "Lệch"
NGOAI_LE = "Ngoại lệ đã duyệt"
CHUA_DOI_SOAT = "Chưa đối soát"

GOI_Y_HD_MUA = "(a) Hóa đơn mua nhập sai"
GOI_Y_PHIEU_NHAP = "(b1) Phiếu nhập mua sai"
GOI_Y_HD_NCC = "(b2) Hóa đơn NCC sai"
GOI_Y_GHEP_TAY = "Cần ghép tay"

TRUONG_NGOAI_LE = (
	"ly_do_ngoai_le",
	"nguoi_duyet_ngoai_le",
	"thoi_diem_duyet_ngoai_le",
	"dau_van_tay_chenh_lech",
)


# --- doc_events của Purchase Invoice -----------------------------------------


def _bo_qua(doc):
	return getattr(doc, "_action", None) in ("cancel", "update_after_submit") or doc.docstatus == 2


def truoc_validate(doc, method=None):
	"""`before_validate`: ghép dòng trước khi controller ERPNext tính tiền và kiểm `pr_required`."""
	if _bo_qua(doc) or not ap_dung(doc):
		return
	ghep_dong.ghep(doc)
	vuot_hoa_don.bo_chan_vuot_phieu_nhap(doc)


def khi_validate(doc, method=None):
	"""`validate`: đối soát và ghi trạng thái, bảng chênh lệch."""
	if _bo_qua(doc):
		return
	_giu_phe_duyet(doc)
	if not ap_dung(doc) or not _co_lien_ket_phieu_nhap(doc):
		_xoa_ket_qua(doc)
	else:
		_ghi_ket_qua(doc, tinh_chenh_lech(doc))
		_bao_phan_con_lai(doc)
	_ghi_ngay_lech(doc)


def _bao_phan_con_lai(doc):
	"""Hóa đơn từng phần: nhắc phần Phiếu nhập còn chờ hóa đơn tiếp theo của NCC."""
	con = doc.flags.get("con_chua_lap_hoa_don")
	if not con or doc.flags.get("doi_soat_tu_phieu_nhap") or getattr(doc, "_action", None) != "save":
		return
	frappe.msgprint(
		_("Hóa đơn từng phần. Còn chờ hóa đơn tiếp theo của nhà cung cấp:")
		+ "<ul>"
		+ "".join(f"<li>{frappe.bold(pr)} · {item}: {_so(sl)} {dvt}</li>" for pr, item, sl, dvt in con)
		+ "</ul>",
		title=_("Đối soát Phiếu nhập mua"),
		indicator="blue",
	)


def truoc_khi_nop(doc, method=None):
	"""`before_submit`: chặn hóa đơn còn lệch và chưa có ngoại lệ được duyệt (6.3.5)."""
	trang_thai = doc.get("trang_thai_doi_soat_pr")
	if trang_thai == NGOAI_LE:
		vuot_hoa_don.cho_vuot_don_mua_khi_co_ngoai_le(doc)
	elif trang_thai == KHOP:
		vuot_hoa_don.cho_vuot_don_mua_trong_dung_sai_gia_gom_vat(doc)
	if not trang_thai or trang_thai in (KHOP, NGOAI_LE):
		return
	frappe.throw(
		_("Hóa đơn chưa khớp Phiếu nhập mua ({0}), chưa Nộp được:").format(trang_thai)
		+ _danh_sach_html(doc.get("chenh_lech_pr"))
		+ _(
			"Sửa theo nhánh xử lý rồi lưu lại để đối soát lại, hoặc nhờ Kế toán trưởng / Ban Điều hành"
			" bấm Duyệt ngoại lệ."
		),
		title=_("Lệch Phiếu nhập mua"),
	)


def khi_tai(doc, method=None):
	"""`onload`: cho form biết người đang xem có được duyệt ngoại lệ không."""
	if doc.get("trang_thai_doi_soat_pr"):
		doc.set_onload("co_quyen_duyet_ngoai_le", co_quyen_duyet_ngoai_le())


# --- Duyệt ngoại lệ (E8) ------------------------------------------------------


@frappe.whitelist()
def duyet_ngoai_le(hoa_don, ly_do):
	"""Kế toán trưởng / Ban Điều hành cho Nộp hóa đơn còn lệch. Phê duyệt gắn với đúng bảng chênh
	lệch lúc duyệt: hóa đơn bị sửa làm chênh lệch đổi thì phê duyệt mất hiệu lực."""
	ly_do = (ly_do or "").strip()
	if not ly_do:
		frappe.throw(_("Nhập lý do ngoại lệ."))
	if not co_quyen_duyet_ngoai_le():
		frappe.throw(_("Bạn không có vai trò duyệt ngoại lệ đối soát."), frappe.PermissionError)

	doc = frappe.get_doc("Purchase Invoice", hoa_don)
	doc.check_permission("read")
	if doc.docstatus != 0:
		frappe.throw(_("Chỉ duyệt ngoại lệ cho hóa đơn nháp."))
	vuot = vuot_hoa_don.vuot_gia_tri_phieu_nhap(doc)
	if vuot:
		frappe.throw(
			_("Hóa đơn vượt giá trị hàng đã nhập kho:")
			+ "<ul>"
			+ "".join(
				"<li>" + _("Dòng {0} ({1}): vượt {2}%").format(dong, item, flt(pt, 2)) + "</li>"
				for dong, item, pt in vuot
			)
			+ "</ul>"
			+ _(
				"Ngoại lệ không cho Nộp được hóa đơn này: ERPNext không cho lập hóa đơn vượt giá trị Phiếu"
				" nhập vì giá trị tồn kho sẽ sai. Nếu giá mới là đúng, sửa Phiếu nhập theo giá mới (nhánh"
				" b1); nếu nhà cung cấp tính sai, xin hóa đơn điều chỉnh (nhánh b2)."
			),
			title=_("Không duyệt ngoại lệ được"),
		)

	doc.flags.duyet_ngoai_le = frappe._dict(ly_do=ly_do, nguoi=frappe.session.user, luc=now_datetime())
	doc.flags.ignore_permissions = True
	doc.save()
	return doc.trang_thai_doi_soat_pr


# --- Chạy lại khi Phiếu nhập đổi (6.3.5, nhánh b1) ----------------------------


def _hoa_don_nhap_lien_quan(pr):
	pii = frappe.qb.DocType("Purchase Invoice Item")
	pi = frappe.qb.DocType("Purchase Invoice")
	dong = [d.name for d in pr.items]
	po = [d.purchase_order_item for d in pr.items if d.purchase_order_item]

	dieu_kien = (pii.purchase_receipt == pr.name) | pii.pr_detail.isin(dong or [""])
	if po:
		dieu_kien |= pii.po_detail.isin(po)
	if pr.amended_from:
		dieu_kien |= pii.purchase_receipt == pr.amended_from
	return (
		frappe.qb.from_(pii)
		.join(pi)
		.on(pi.name == pii.parent)
		.select(pii.parent)
		.distinct()
		.where(pi.docstatus == 0)
		.where(dieu_kien)
		.run(pluck=True)
	)


def khi_nop_phieu_nhap(doc, method=None):
	"""`on_submit` của Phiếu nhập mua: đối soát lại các hóa đơn nháp liên quan.

	Bản sửa của phiếu đã hủy (nhánh b1): ghép lại TRƯỚC khi lưu, vì Frappe kiểm liên kết tới
	chứng từ đã hủy trước mọi hook. Lưu hóa đơn trong savepoint: hóa đơn lưu lỗi (vì lý do khác)
	không được làm hỏng việc Nộp Phiếu nhập — hóa đơn đó chuyển về "Chưa đối soát" và vẫn bị đối
	soát lại khi Nộp.
	"""
	if not cau_hinh().bat or cint(doc.is_return):
		return
	for ten in _hoa_don_nhap_lien_quan(doc):
		pi = frappe.get_doc("Purchase Invoice", ten)
		if not ap_dung(pi):
			continue
		frappe.db.savepoint("doi_soat_pr_pi")
		try:
			pi.flags.ignore_permissions = True
			pi.flags.doi_soat_tu_phieu_nhap = doc.name
			ghep_dong.ghep(pi)
			pi.save()
		except Exception:
			frappe.db.rollback(save_point="doi_soat_pr_pi")
			_danh_dau_chua_doi_soat(ten, doc.name)
			frappe.log_error(
				title=_("Đối soát PR ↔ PI: không lưu được hóa đơn {0}").format(ten),
				reference_doctype="Purchase Invoice",
				reference_name=ten,
			)


def khi_huy_phieu_nhap(doc, method=None):
	"""`on_cancel` của Phiếu nhập mua (nhánh b1: Kho hủy để sửa). Hóa đơn nháp còn trỏ vào phiếu
	này không lưu được (Frappe chặn liên kết tới chứng từ đã hủy) cho tới khi bản sửa được Nộp,
	nên chỉ đánh dấu "Chưa đối soát"."""
	if not cau_hinh().bat or cint(doc.is_return):
		return
	for ten in _hoa_don_nhap_lien_quan(doc):
		_danh_dau_chua_doi_soat(ten, doc.name)


@frappe.whitelist()
def doi_soat_lai(hoa_don):
	"""Nút Đối soát lại: ghép dòng rồi lưu. Ghép trước khi lưu để hóa đơn còn trỏ vào Phiếu nhập
	đã hủy chuyển được sang bản sửa (lưu thẳng thì Frappe báo CancelledLinkError)."""
	doc = frappe.get_doc("Purchase Invoice", hoa_don)
	doc.check_permission("write")
	if doc.docstatus != 0:
		frappe.throw(_("Chỉ đối soát lại hóa đơn nháp."))
	if ap_dung(doc):
		ghep_dong.ghep(doc)
	doc.save()
	return doc.trang_thai_doi_soat_pr


def _danh_dau_chua_doi_soat(hoa_don, phieu_nhap):
	cu = frappe.db.get_value(
		"Purchase Invoice", hoa_don, ["trang_thai_doi_soat_pr", "lech_tu_ngay"], as_dict=True
	)
	if not cu.trang_thai_doi_soat_pr:
		return
	frappe.db.set_value(
		"Purchase Invoice",
		hoa_don,
		{"trang_thai_doi_soat_pr": CHUA_DOI_SOAT, "lech_tu_ngay": cu.lech_tu_ngay or today()},
		update_modified=False,
	)
	frappe.get_doc("Purchase Invoice", hoa_don).add_comment(
		"Info",
		_("Phiếu nhập mua {0} vừa thay đổi; hóa đơn sẽ được đối soát lại khi lưu hoặc Nộp.").format(
			phieu_nhap
		),
	)


# --- Ghi kết quả ------------------------------------------------------------------


def _co_lien_ket_phieu_nhap(doc):
	"""E7: chỉ đối soát hóa đơn có dòng gắn (hoặc có thể gắn) Phiếu nhập. Hóa đơn dịch vụ không
	có Phiếu nhập thì không áp."""
	return any(
		d.pr_detail or (d.flags.get("ghep_pr") or (ghep_dong.KHONG_CO,))[0] != ghep_dong.KHONG_CO
		for d in doc.items
	)


def _giu_phe_duyet(doc):
	"""Ô duyệt ngoại lệ chỉ đổi qua `duyet_ngoai_le`: giá trị gửi lên từ form, API hay import đều
	bị trả về giá trị đang lưu."""
	if doc.flags.get("duyet_ngoai_le"):
		return
	truoc = doc.get_doc_before_save()
	for f in TRUONG_NGOAI_LE:
		doc.set(f, truoc.get(f) if truoc else None)


def _xoa_ket_qua(doc):
	if not (doc.get("trang_thai_doi_soat_pr") or doc.get("chenh_lech_pr")):
		return
	doc.trang_thai_doi_soat_pr = None
	doc.thoi_diem_doi_soat = None
	doc.nhanh_xu_ly = None
	doc.set("chenh_lech_pr", [])
	for f in TRUONG_NGOAI_LE:
		doc.set(f, None)


def _ghi_ngay_lech(doc):
	"""Ngày hóa đơn bắt đầu chưa khớp (Lệch / Chưa đối soát), để nhắc Kế toán trưởng khi tồn quá N
	ngày. Server tự tính từ bản đang lưu: giữ ngày cũ khi hóa đơn vẫn chưa xử lý xong, xóa khi đã
	khớp hoặc có ngoại lệ được duyệt."""
	if doc.get("trang_thai_doi_soat_pr") in (LECH, CHUA_DOI_SOAT):
		truoc = doc.get_doc_before_save()
		doc.lech_tu_ngay = (truoc.get("lech_tu_ngay") if truoc else None) or today()
	else:
		doc.lech_tu_ngay = None


def van_tay(chenh_lech):
	khoa = [
		[r.get("dong_hoa_don"), r.get("tieu_chi"), r.get("gia_tri_pr"), r.get("gia_tri_pi")]
		for r in chenh_lech
	]
	return hashlib.sha1(json.dumps(khoa, ensure_ascii=False).encode()).hexdigest()[:20]


def _ghi_ket_qua(doc, chenh_lech):
	doc.set("chenh_lech_pr", chenh_lech)
	doc.thoi_diem_doi_soat = now_datetime()
	if not chenh_lech:
		doc.trang_thai_doi_soat_pr = KHOP
		doc.nhanh_xu_ly = None
		for f in TRUONG_NGOAI_LE:
			doc.set(f, None)
		return

	dau = van_tay(chenh_lech)
	duyet = doc.flags.get("duyet_ngoai_le")
	if duyet:
		doc.ly_do_ngoai_le = duyet.ly_do
		doc.nguoi_duyet_ngoai_le = duyet.nguoi
		doc.thoi_diem_duyet_ngoai_le = duyet.luc
		doc.dau_van_tay_chenh_lech = dau
		doc.trang_thai_doi_soat_pr = NGOAI_LE
		return
	if doc.nguoi_duyet_ngoai_le and doc.dau_van_tay_chenh_lech == dau:
		doc.trang_thai_doi_soat_pr = NGOAI_LE
		return

	if doc.nguoi_duyet_ngoai_le and not doc.flags.get("doi_soat_tu_phieu_nhap"):
		frappe.msgprint(
			_(
				"Chênh lệch đã thay đổi sau khi {0} duyệt ngoại lệ, nên phê duyệt cũ không còn hiệu lực."
			).format(doc.nguoi_duyet_ngoai_le),
			indicator="orange",
		)
	for f in TRUONG_NGOAI_LE:
		doc.set(f, None)
	doc.trang_thai_doi_soat_pr = LECH
	if getattr(doc, "_action", None) == "save" and not doc.flags.get("doi_soat_tu_phieu_nhap"):
		frappe.msgprint(
			_("Hóa đơn lệch Phiếu nhập mua ở {0} điểm (xem Bảng chênh lệch). Chưa Nộp được.").format(
				len(chenh_lech)
			),
			title=_("Đối soát Phiếu nhập mua"),
			indicator="orange",
		)


def _danh_sach_html(chenh_lech, gioi_han=10):
	dong = []
	for r in (chenh_lech or [])[:gioi_han]:
		vi_tri = _("Dòng {0}").format(r.dong_hoa_don) if r.dong_hoa_don else _("Tổng")
		dong.append(
			f"<li>{vi_tri} · {_(r.tieu_chi)}{(' · ' + r.item_code) if r.item_code else ''}: "
			+ _("Phiếu nhập {0}, Hóa đơn {1}").format(r.gia_tri_pr or "-", r.gia_tri_pi or "-")
			+ "</li>"
		)
	con = len(chenh_lech or []) - gioi_han
	if con > 0:
		dong.append("<li>" + _("... và {0} điểm khác").format(con) + "</li>")
	return f"<ul>{''.join(dong)}</ul>"


# --- Tính chênh lệch --------------------------------------------------------------


def _so(value, precision=None):
	"""Số hiển thị trong bảng chênh lệch: số nguyên không kèm phần thập phân."""
	precision = 3 if precision is None else precision
	value = flt(value, precision)
	return fmt_money(value, precision=0 if value.is_integer() else precision)


def _la_thue_tren_tien_hang(t):
	return (
		t.charge_type == "On Net Total" and t.category != "Valuation" and (t.add_deduct_tax or "Add") == "Add"
	)


def _phi_co_dinh(thue):
	"""Phí cố định (loại Actual: cước vận chuyển, phí bốc xếp...) cộng vào tổng chứng từ, có dấu."""
	return sum(
		flt(t.tax_amount) * (-1 if t.add_deduct_tax == "Deduct" else 1)
		for t in thue
		if t.charge_type == "Actual" and t.category != "Valuation"
	)


def _phi_co_dinh_con_lai(phieu_nhap, tru_hoa_don):
	"""Phí cố định của các Phiếu nhập chưa được hóa đơn mua nào (đã Nộp) lập. Hóa đơn khác lập
	chung với Phiếu nhập ngoài nhóm này thì cả phí của nó bị tính trừ ở đây — sai lệch nghiêng về
	phía báo Lệch, không bỏ sót."""
	thue = frappe.get_all(
		"Purchase Taxes and Charges",
		filters={"parenttype": "Purchase Receipt", "parent": ("in", phieu_nhap)},
		fields=["charge_type", "category", "add_deduct_tax", "tax_amount"],
	)
	hoa_don_khac = frappe.get_all(
		"Purchase Invoice",
		filters={
			"name": (
				"in",
				frappe.get_all(
					"Purchase Invoice Item",
					filters={
						"purchase_receipt": ("in", phieu_nhap),
						"docstatus": 1,
						"parent": ("!=", tru_hoa_don),
					},
					pluck="parent",
					distinct=True,
				)
				or [""],
			),
			"is_return": 0,
		},
		pluck="name",
	)
	da_lap = frappe.get_all(
		"Purchase Taxes and Charges",
		filters={"parenttype": "Purchase Invoice", "parent": ("in", hoa_don_khac or [""])},
		fields=["charge_type", "category", "add_deduct_tax", "tax_amount"],
	)
	return _phi_co_dinh(thue) - _phi_co_dinh(da_lap)


def thue_suat(dong, thue):
	"""Tổng thuế suất (%) của một dòng, tính như ERPNext (`_get_tax_rate`): thuế suất theo mặt hàng
	(Item Tax Template) nếu có tài khoản đó, không thì thuế suất của dòng thuế. Chỉ xét thuế tính
	trên tiền hàng và cộng vào tổng hóa đơn."""
	theo_hang = json.loads(dong.get("item_tax_rate") or "{}")
	return flt(sum(flt(theo_hang.get(t.account_head, t.rate)) for t in thue if _la_thue_tren_tien_hang(t)), 4)


def _du_lieu_phieu_nhap(ten_dong):
	dong = {
		r.name: r
		for r in frappe.get_all(
			"Purchase Receipt Item",
			filters={"name": ("in", ten_dong or [""])},
			fields=[
				"name",
				"parent",
				"item_code",
				"uom",
				"stock_uom",
				"conversion_factor",
				"qty",
				"stock_qty",
				"net_rate",
				"net_amount",
				"item_tax_rate",
			],
		)
	}
	phieu = {
		r.name: r
		for r in frappe.get_all(
			"Purchase Receipt",
			filters={"name": ("in", list({r.parent for r in dong.values()}) or [""])},
			fields=["name", "net_total", "grand_total"],
		)
	}
	thue = {}
	for t in frappe.get_all(
		"Purchase Taxes and Charges",
		filters={"parenttype": "Purchase Receipt", "parent": ("in", list(phieu) or [""])},
		fields=["parent", "charge_type", "category", "add_deduct_tax", "account_head", "rate"],
		order_by="idx",
	):
		thue.setdefault(t.parent, []).append(t)
	return dong, phieu, thue


def tinh_chenh_lech(doc):
	"""Danh sách chênh lệch (rỗng = khớp). Dòng trước, tổng sau; tổng chỉ so khi mọi dòng đã khớp
	để một sai lệch không bị liệt kê hai lần."""
	chenh = []

	def them(tieu_chi, dong, phieu_nhap, gia_tri_pr, gia_tri_pi, **kw):
		chenh.append(
			frappe._dict(
				dong_hoa_don=str(dong) if dong else None,
				tieu_chi=tieu_chi,
				purchase_receipt=phieu_nhap,
				gia_tri_pr=gia_tri_pr,
				gia_tri_pi=gia_tri_pi,
				**kw,
			)
		)

	ten_dong = [d.pr_detail for d in doc.items if d.pr_detail]
	pr_items, phieu, thue_phieu = _du_lieu_phieu_nhap(ten_dong)
	# Dòng gắn hợp đồng khung giá đã gồm VAT (Đợt 4, D4-12): giá chưa VAT là số quy đổi, NCC có thể làm
	# tròn khác 1 đồng / ĐVT kho. Dung sai chỉ cho các dòng này; dòng khác vẫn so 0 đồng.
	from erpnext.buying.tiep_nhan_hoa_don.hop_dong_khung import (
		DUNG_SAI_GIA_GOM_VAT,
		dong_don_mua_gia_gom_vat,
	)

	gom_vat = dong_don_mua_gia_gom_vat({d.po_detail for d in doc.items if d.get("po_detail")})
	dung_sai_tien_hang = dung_sai_thue = 0.0
	con = ghep_dong.con_cho_lap_hoa_don(ten_dong, tru_hoa_don=doc.name)
	hang_kho = set(
		frappe.get_all(
			"Item",
			filters={"name": ("in", list({d.item_code for d in doc.items}) or [""]), "is_stock_item": 1},
			pluck="name",
		)
	)
	p_tien = doc.precision("net_total")

	# --- Ghép dòng ---
	nhom = {}  # dòng Phiếu nhập -> các dòng hóa đơn gắn vào nó
	for d in doc.items:
		ghep = d.flags.get("ghep_pr") or ((ghep_dong.DA_GHEP,) if d.pr_detail else (ghep_dong.KHONG_CO,))
		sl_hd = f"{_so(d.qty)} {d.uom}"
		if ghep[0] == ghep_dong.MO_HO:
			them(
				"Ghép dòng",
				d.idx,
				", ".join(ghep[1]),
				_("Nhiều Phiếu nhập có thể ghép"),
				sl_hd,
				item_code=d.item_code,
				nhanh_goi_y=GOI_Y_GHEP_TAY,
				ghi_chu=_("Xóa dòng này rồi dùng Lấy mặt hàng từ → Phiếu nhập mua để chọn đúng phiếu."),
			)
		elif ghep[0] == ghep_dong.DA_LAP_DU:
			them(
				"Ghép dòng",
				d.idx,
				", ".join(ghep[1]),
				_("Đã lập hóa đơn đủ"),
				sl_hd,
				item_code=d.item_code,
				nhanh_goi_y=GOI_Y_HD_MUA,
				ghi_chu=_(
					"Mọi Phiếu nhập của dòng đơn mua này đã có hóa đơn: có thể đang lập hóa đơn trùng."
				),
			)
		elif d.pr_detail in pr_items:
			nhom.setdefault(d.pr_detail, []).append(d)
		else:
			kho = d.item_code in hang_kho
			them(
				"Ghép dòng",
				d.idx,
				None,
				_("Không có trên Phiếu nhập"),
				f"{sl_hd}, {_so(d.net_amount, p_tien)}",
				item_code=d.item_code,
				nhanh_goi_y=GOI_Y_PHIEU_NHAP if kho else GOI_Y_HD_NCC,
				ghi_chu=_("Hàng chưa nhập kho, hoặc dòng không lấy từ Phiếu nhập.")
				if kho
				else _("Khoản không có trên Phiếu nhập (phí, dịch vụ)."),
			)

	# --- Từng dòng Phiếu nhập ---
	lam_tron_tung_dong = cint(frappe.db.get_single_value("Accounts Settings", "round_row_wise_tax"))
	# Hóa đơn từng phần (NCC xuất nhiều hóa đơn cho một Phiếu nhập): được ít hơn phần chưa lập hóa
	# đơn, không được nhiều hơn; giá, thuế, tiền vẫn so như thường trên phần được lập.
	tung_phan = cint(doc.get("hoa_don_tung_phan"))
	doc.flags.con_chua_lap_hoa_don = []
	tien_hang_ky_vong = thue_ky_vong = 0.0
	tron_ven = True  # mọi Phiếu nhập được lập hóa đơn trọn một lần, ngay trong hóa đơn này
	dong_theo_phieu = {}

	for ten, cac_dong in nhom.items():
		p = pr_items[ten]
		vi_tri = ", ".join(str(d.idx) for d in cac_dong)
		dong_theo_phieu.setdefault(p.parent, set()).add(ten)

		# Mặt hàng, ĐVT, tiền tệ khác Phiếu nhập: ERPNext đã chặn ngay khi lưu
		# (`validate_with_previous_doc`), nên ở đây chỉ còn số lượng, giá, thuế và tiền.
		p_sl = cac_dong[0].precision("stock_qty")
		p_gia = cac_dong[0].precision("net_rate")
		gia_pr = flt(p.net_rate) / (flt(p.conversion_factor) or 1)
		sl_pr = flt(con.get(ten))
		sl_hd = sum(flt(d.stock_qty) for d in cac_dong)
		lech_sl = flt(sl_hd - sl_pr, p_sl)
		if tung_phan and lech_sl < 0:
			doc.flags.con_chua_lap_hoa_don.append((p.parent, p.item_code, -lech_sl, p.stock_uom))
			lech_sl = 0
		sl_ky_vong = sl_hd if tung_phan and not lech_sl else sl_pr  # số được lập hóa đơn lần này
		# 1 đồng trên đơn giá ghi ở hóa đơn (ĐVT của dòng), tức 1 / hệ số quy đổi theo ĐVT kho.
		dung_sai = DUNG_SAI_GIA_GOM_VAT if any(d.get("po_detail") in gom_vat for d in cac_dong) else 0
		lech_gia = [
			(d, flt(d.net_rate) / (flt(d.conversion_factor) or 1))
			for d in cac_dong
			if abs(flt(flt(d.net_rate) / (flt(d.conversion_factor) or 1) - gia_pr, p_gia))
			> dung_sai / (flt(d.conversion_factor) or 1)
		]
		dung_sai_dong = dung_sai * sum(flt(d.qty) for d in cac_dong)
		if lech_sl or flt(sl_ky_vong - flt(p.stock_qty), p_sl):
			tron_ven = False

		if lech_sl:
			them(
				"Số lượng",
				vi_tri,
				p.parent,
				f"{_so(sl_pr)} {p.stock_uom}",
				f"{_so(sl_hd)} {p.stock_uom}",
				item_code=p.item_code,
				muc_lech=lech_sl,
				nhanh_goi_y=GOI_Y_PHIEU_NHAP,
				ghi_chu=_("Hóa đơn từng phần không được nhiều hơn phần chưa lập hóa đơn.")
				if tung_phan
				else _("Phiếu nhập: số đã nhận chưa lập hóa đơn, theo ĐVT kho."),
			)
		for d, gia_hd in lech_gia:
			them(
				"Đơn giá",
				d.idx,
				p.parent,
				f"{_so(gia_pr, p_gia)} / {p.stock_uom}",
				f"{_so(gia_hd, p_gia)} / {p.stock_uom}",
				item_code=p.item_code,
				muc_lech=flt(gia_hd - gia_pr, p_gia),
				nhanh_goi_y=GOI_Y_HD_NCC,
				ghi_chu=_("Giá trước thuế, theo ĐVT kho."),
			)

		ts_pr = thue_suat(p, thue_phieu.get(p.parent, []))
		for d in cac_dong:
			ts_hd = thue_suat(d, doc.taxes)
			if flt(ts_hd - ts_pr, 4):
				them(
					"Thuế suất",
					d.idx,
					p.parent,
					f"{_so(ts_pr)}%",
					f"{_so(ts_hd)}%",
					item_code=p.item_code,
					muc_lech=flt(ts_hd - ts_pr, 4),
					nhanh_goi_y=GOI_Y_HD_NCC,
				)

		# Thành tiền kỳ vọng: lấy trọn dòng Phiếu nhập thì đúng thành tiền của phiếu (giữ cách làm
		# tròn của phiếu); lấy một phần thì đơn giá x số lượng, như ERPNext tính trên hóa đơn.
		if not flt(sl_ky_vong - flt(p.stock_qty), p_sl):
			tien_pr = flt(p.net_amount, p_tien)
		else:
			tien_pr = flt(gia_pr * sl_ky_vong, p_tien)
		tien_hd = flt(sum(flt(d.net_amount) for d in cac_dong), p_tien)
		if not (lech_sl or lech_gia) and abs(flt(tien_hd - tien_pr, p_tien)) > dung_sai_dong:
			them(
				"Thành tiền",
				vi_tri,
				p.parent,
				_so(tien_pr, p_tien),
				_so(tien_hd, p_tien),
				item_code=p.item_code,
				muc_lech=flt(tien_hd - tien_pr, p_tien),
				nhanh_goi_y=GOI_Y_HD_NCC,
			)
		tien_hang_ky_vong += tien_pr
		if dung_sai:
			dung_sai_tien_hang += dung_sai_dong
			dung_sai_thue += dung_sai_dong * ts_pr / 100 + 1  # + làm tròn thuế của dòng
		theo_hang = json.loads(p.item_tax_rate or "{}")
		for t in thue_phieu.get(p.parent, []):
			if _la_thue_tren_tien_hang(t):
				tien_thue = tien_pr * flt(theo_hang.get(t.account_head, t.rate)) / 100
				thue_ky_vong += flt(tien_thue, p_tien) if lam_tron_tung_dong else tien_thue

	if chenh or not nhom:
		return chenh

	# --- Tổng (6.3.3) ---
	if tron_ven:
		tat_ca = frappe.get_all(
			"Purchase Receipt Item", filters={"parent": ("in", list(dong_theo_phieu))}, pluck="name"
		)
		tron_ven = set(tat_ca) == set().union(*dong_theo_phieu.values())
	if tron_ven:
		# Trường hợp thường gặp (hóa đơn lập bằng nút Tạo từ phiếu, lấy trọn phiếu): so thẳng với
		# tổng ERPNext đã tính trên phiếu, gồm cả thuế / phí cố định và chiết khấu cả phiếu.
		tien_hang_ky_vong = sum(flt(phieu[n].net_total) for n in dong_theo_phieu)
		tong_ky_vong = sum(flt(phieu[n].grand_total) for n in dong_theo_phieu)
	else:
		# Không lấy trọn Phiếu nhập (hóa đơn từng phần, hóa đơn cho phần còn lại): phí cố định của
		# phiếu không chia theo số lượng được. Hóa đơn không ghi phí, hoặc ghi đúng phần phí chưa
		# hóa đơn nào lập, đều khớp. Lập hóa đơn từ phiếu thì ERPNext chép sẵn dòng phí vào MỌI hóa
		# đơn, nên hóa đơn thứ hai còn giữ dòng đó sẽ Lệch (phí lập hai lần).
		phi_hd = _phi_co_dinh(doc.taxes)
		phi_ky_vong = _phi_co_dinh_con_lai(list(dong_theo_phieu), doc.name) if flt(phi_hd, p_tien) else 0
		tong_ky_vong = tien_hang_ky_vong + thue_ky_vong + phi_ky_vong
	tien_hang_ky_vong = flt(tien_hang_ky_vong, p_tien)
	tong_ky_vong = flt(tong_ky_vong, p_tien)

	pr_lien_quan = ", ".join(dong_theo_phieu)
	for tieu_chi, ky_vong, thuc_te, dung_sai in (
		("Tổng tiền hàng", tien_hang_ky_vong, flt(doc.net_total, p_tien), dung_sai_tien_hang),
		(
			"Tổng thuế",
			flt(tong_ky_vong - tien_hang_ky_vong, p_tien),
			flt(flt(doc.grand_total) - flt(doc.net_total), p_tien),
			dung_sai_thue,
		),
		("Tổng thanh toán", tong_ky_vong, flt(doc.grand_total, p_tien), dung_sai_tien_hang + dung_sai_thue),
	):
		if abs(flt(thuc_te - ky_vong, p_tien)) > dung_sai:
			them(
				tieu_chi,
				None,
				pr_lien_quan,
				_so(ky_vong, p_tien),
				_so(thuc_te, p_tien),
				muc_lech=flt(thuc_te - ky_vong, p_tien),
				nhanh_goi_y=GOI_Y_HD_NCC,
			)
	return chenh
