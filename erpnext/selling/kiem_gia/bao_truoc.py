# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Báo trước khi đổi giá bán (YC4; spec mục 6.2 và 14).

Bảng giá bán có tích "Báo trước khi đổi giá" (vd. "Bảng giá Himedic") đi kèm một BẢNG GIÁ
CHỜ. Giá mới luôn vào bảng giá chờ trước; chỉ khi Giám đốc "Gửi thông báo đổi giá" thì
dòng mới được chuyển sang bảng giá chính. Nhờ vậy giá chưa báo không bao giờ được áp.

Trên bảng giá chính: không thêm thẳng, không sửa giá/ngày/ĐVT/mặt hàng/khách của dòng có
sẵn, không xóa (giá cũ phải còn để SO cũ đúng giá — D4-4). Ô xác nhận vẫn sửa được.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from erpnext.selling.kiem_gia.cau_hinh import co_quyen_sua_ty_le_lai

CHO_GUI = "Chờ gửi"
DA_GUI = "Đã gửi"
DA_XAC_NHAN = "Đã xác nhận"

TRUONG_PRICE_LIST = ("bao_truoc_khi_doi_gia", "so_ngay_bao_truoc", "bang_gia_cho", "email_nhan_thong_bao")
# Thay một trong các ô này trên dòng giá của bảng giá chính = đổi giá.
TRUONG_GIA = (
	"price_list",
	"item_code",
	"uom",
	"customer",
	"price_list_rate",
	"valid_from",
	"valid_upto",
	"batch_no",
)
TRUONG_THONG_BAO = (
	"trang_thai_thong_bao",
	"ngay_gui_thong_bao",
	"so_ngay_bao_truoc",
	"bao_gap",
	"thong_bao",
	"nguoi_gui_thong_bao",
)


# --- Tra cứu ------------------------------------------------------------------


def bang_gia_chinh_cua(price_list_cho):
	"""Bảng giá chính dùng `price_list_cho` làm bảng giá chờ (None nếu không phải bảng chờ)."""
	if not price_list_cho:
		return None
	return frappe.db.get_value(
		"Price List", {"bao_truoc_khi_doi_gia": 1, "bang_gia_cho": price_list_cho}, "name"
	)


def co_bao_truoc(price_list):
	return bool(price_list) and cint(frappe.db.get_value("Price List", price_list, "bao_truoc_khi_doi_gia"))


# --- Price List (2.1) ----------------------------------------------------------


def kiem_price_list(doc):
	"""Gọi từ `PriceList.validate`."""
	truoc = doc.get_doc_before_save()
	goc = truoc.as_dict() if truoc else {"so_ngay_bao_truoc": 7}
	doi = [
		f for f in TRUONG_PRICE_LIST if (goc.get(f) or "") != (doc.get(f) or "") and f != "so_ngay_bao_truoc"
	]
	if cint(goc.get("so_ngay_bao_truoc")) != cint(doc.get("so_ngay_bao_truoc")) and truoc:
		doi.append("so_ngay_bao_truoc")
	if doi and not co_quyen_sua_ty_le_lai():
		frappe.throw(
			_("Chỉ Giám đốc được đổi cài đặt báo trước khi đổi giá ({0}).").format(
				", ".join(_(doc.meta.get_label(f)) for f in doi)
			),
			frappe.PermissionError,
		)

	if not cint(doc.get("bao_truoc_khi_doi_gia")):
		return
	if not doc.selling:
		frappe.throw(_("Báo trước khi đổi giá chỉ dùng cho bảng giá bán"))
	if cint(doc.get("so_ngay_bao_truoc")) <= 0:
		frappe.throw(_("Số ngày báo trước phải lớn hơn 0"))
	cho = doc.get("bang_gia_cho")
	if not cho:
		frappe.throw(_("Chọn Bảng giá chờ cho {0}").format(doc.name))
	if cho == doc.name:
		frappe.throw(_("Bảng giá chờ phải khác bảng giá chính"))
	pl_cho = frappe.db.get_value(
		"Price List", cho, ["selling", "currency", "bao_truoc_khi_doi_gia"], as_dict=True
	)
	if not pl_cho or not pl_cho.selling or pl_cho.currency != doc.currency:
		frappe.throw(_("Bảng giá chờ {0} phải là bảng giá bán cùng tiền tệ {1}").format(cho, doc.currency))
	if pl_cho.bao_truoc_khi_doi_gia:
		frappe.throw(_("Bảng giá chờ {0} không được tự tích Báo trước khi đổi giá").format(cho))
	khac = frappe.db.get_value(
		"Price List", {"bang_gia_cho": cho, "bao_truoc_khi_doi_gia": 1, "name": ("!=", doc.name)}, "name"
	)
	if khac:
		frappe.throw(_("Bảng giá chờ {0} đang dùng cho {1}").format(cho, khac))


def kiem_chung_tu_ban(doc):
	"""Gọi từ `SellingController.validate`: không bán theo bảng giá chờ (giá chưa báo)."""
	pl = doc.get("selling_price_list")
	chinh = bang_gia_chinh_cua(pl)
	if chinh:
		frappe.throw(
			_("{0} là bảng giá chờ (giá chưa báo cho khách). Dùng bảng giá {1}.").format(
				frappe.bold(pl), frappe.bold(chinh)
			)
		)


# --- Item Price (2.2, 2.3) -----------------------------------------------------


def kiem_item_price(doc):
	"""Gọi từ `ItemPrice.validate`."""
	truoc = doc.get_doc_before_save()
	pl_truoc = truoc.price_list if truoc else None
	if doc.flags.tu_thong_bao_doi_gia:
		return
	if not co_bao_truoc(pl_truoc) and bang_gia_chinh_cua(doc.price_list):
		_dong_cho(doc)
		return
	if not (co_bao_truoc(doc.price_list) or co_bao_truoc(pl_truoc)):
		return

	if not truoc:
		frappe.throw(
			_(
				"Bảng giá {0} báo trước khi đổi giá: thêm giá mới vào bảng giá chờ {1}, rồi Giám đốc Gửi thông báo đổi giá."
			).format(
				frappe.bold(doc.price_list),
				frappe.bold(frappe.db.get_value("Price List", doc.price_list, "bang_gia_cho")),
			)
		)

	doi = [f for f in TRUONG_GIA + TRUONG_THONG_BAO if _khac(truoc.get(f), doc.get(f))]
	if doi:
		frappe.throw(
			_(
				"Không sửa được giá đã có trên bảng giá {0} ({1}). Muốn đổi giá: thêm dòng mới vào bảng giá chờ rồi gửi thông báo; giá cũ giữ nguyên."
			).format(frappe.bold(pl_truoc), ", ".join(_(doc.meta.get_label(f)) for f in doi))
		)

	if doc.get("ngay_xac_nhan") and doc.get("trang_thai_thong_bao") == DA_GUI:
		doc.trang_thai_thong_bao = DA_XAC_NHAN
	elif not doc.get("ngay_xac_nhan") and doc.get("trang_thai_thong_bao") == DA_XAC_NHAN:
		doc.trang_thai_thong_bao = DA_GUI


def chan_xoa_item_price(doc):
	"""Gọi từ `ItemPrice.on_trash`."""
	if co_bao_truoc(doc.price_list) and frappe.session.user != "Administrator":
		frappe.throw(
			_("Không xóa giá trên bảng giá {0}: giá cũ phải còn để chứng từ cũ đúng giá.").format(
				frappe.bold(doc.price_list)
			)
		)


def _dong_cho(doc):
	"""Dòng trong bảng giá chờ: luôn ở trạng thái Chờ gửi, chưa có thông tin gửi."""
	doc.trang_thai_thong_bao = CHO_GUI
	for f in (
		"ngay_gui_thong_bao",
		"so_ngay_bao_truoc",
		"bao_gap",
		"thong_bao",
		"nguoi_gui_thong_bao",
		"ngay_xac_nhan",
	):
		doc.set(f, None)


def _khac(a, b):
	if a in (None, "") and b in (None, ""):
		return False
	if hasattr(a, "year") or hasattr(b, "year"):
		return (getdate(a) if a else None) != (getdate(b) if b else None)
	if isinstance(a, int | float) or isinstance(b, int | float):
		return float(a or 0) != float(b or 0)
	return a != b


# --- Gửi thông báo đổi giá (2.4) ----------------------------------------------


@frappe.whitelist()
def gui_thong_bao_doi_gia(price_list):
	"""Nút "Gửi thông báo đổi giá" trên bảng giá chính. Chỉ Giám đốc (D2-1).

	Gom mọi dòng trong bảng giá chờ vào MỘT email, rồi chuyển chúng sang bảng giá chính
	với ngày gửi, số ngày báo trước, cờ Báo gấp (dưới số ngày quy định: chỉ cảnh báo —
	D4-2). Ngày hiệu lực trước ngày gửi thì chặn (D2-4). Lỗi ở bất kỳ dòng nào thì không
	dòng nào được chuyển và không email nào được gửi.
	"""
	if not co_quyen_sua_ty_le_lai():
		frappe.throw(_("Chỉ Giám đốc được gửi thông báo đổi giá"), frappe.PermissionError)
	pl = frappe.get_doc("Price List", price_list)
	if not cint(pl.get("bao_truoc_khi_doi_gia")):
		frappe.throw(_("Bảng giá {0} chưa bật Báo trước khi đổi giá").format(price_list))
	if not (pl.get("email_nhan_thong_bao") or "").strip():
		frappe.throw(_("Bảng giá {0} chưa có Email nhận thông báo đổi giá").format(price_list))

	dong = frappe.get_all(
		"Item Price",
		filters={"price_list": pl.bang_gia_cho},
		fields=["name", "item_code", "item_name", "uom", "customer", "price_list_rate", "valid_from"],
		order_by="item_code, valid_from",
	)
	if not dong:
		frappe.throw(_("Bảng giá chờ {0} không có giá nào để gửi").format(pl.bang_gia_cho))

	hom_nay = getdate(nowdate())
	qua_khu = [d for d in dong if not d.valid_from or getdate(d.valid_from) < hom_nay]
	if qua_khu:
		frappe.throw(
			_("Sửa ngày hiệu lực (không được trước hôm nay) cho: {0}").format(
				", ".join(f"{d.item_code} ({d.valid_from or '-'})" for d in qua_khu)
			),
			title=_("Gửi thông báo đổi giá"),
		)

	trung = [
		d
		for d in dong
		if frappe.db.exists(
			"Item Price",
			{
				"price_list": price_list,
				"item_code": d.item_code,
				"uom": d.uom,
				"customer": d.customer or ("is", "not set"),
				"valid_from": d.valid_from,
			},
		)
	]
	if trung:
		frappe.throw(
			_("Bảng giá {0} đã có giá cùng ngày hiệu lực cho: {1}. Sửa ngày hiệu lực của giá chờ.").format(
				price_list, ", ".join(f"{d.item_code} ({d.valid_from})" for d in trung)
			),
			title=_("Gửi thông báo đổi giá"),
		)

	so_ngay_quy_dinh = cint(pl.get("so_ngay_bao_truoc")) or 7
	for d in dong:
		d.so_ngay = (getdate(d.valid_from) - hom_nay).days
		d.bao_gap = d.so_ngay < so_ngay_quy_dinh
		d.gia_cu = _gia_hien_hanh(price_list, d)

	# _make: bỏ kiểm quyền "email" trên Price List — quyền gửi đã kiểm ở trên (D2-1).
	from frappe.core.doctype.communication.email import _make

	comm = _make(
		doctype="Price List",
		name=price_list,
		subject=_("Thông báo thay đổi giá - {0}").format(price_list),
		content=_noi_dung_email(price_list, dong, so_ngay_quy_dinh),
		recipients=pl.email_nhan_thong_bao,
		send_email=True,
	)["name"]

	for d in dong:
		ip = frappe.get_doc("Item Price", d.name)
		ip.flags.tu_thong_bao_doi_gia = True
		ip.price_list = price_list
		ip.trang_thai_thong_bao = DA_GUI
		ip.ngay_gui_thong_bao = hom_nay
		ip.so_ngay_bao_truoc = d.so_ngay
		ip.bao_gap = 1 if d.bao_gap else 0
		ip.thong_bao = comm
		ip.nguoi_gui_thong_bao = frappe.session.user
		ip.save(ignore_permissions=True)

	gap = [d for d in dong if d.bao_gap]
	if gap:
		frappe.msgprint(
			_("Báo gấp (dưới {0} ngày) — nhớ xin khách xác nhận đồng ý áp giá sớm:").format(so_ngay_quy_dinh)
			+ "<ul>"
			+ "".join(
				f"<li>{d.item_code}: {_('áp từ')} {frappe.format(d.valid_from, 'Date')}, "
				f"{_('báo trước {0} ngày, thiếu {1} ngày').format(d.so_ngay, so_ngay_quy_dinh - d.so_ngay)}</li>"
				for d in gap
			)
			+ "</ul>",
			title=_("Gửi thông báo đổi giá"),
			indicator="orange",
		)
	return {"thong_bao": comm, "so_dong": len(dong), "bao_gap": len(gap)}


def _gia_hien_hanh(price_list, d):
	"""Giá đang áp ngay trước ngày hiệu lực của dòng mới (để email ghi giá cũ -> giá mới)."""
	r = frappe.db.sql(
		"""select price_list_rate from `tabItem Price`
		where price_list = %s and item_code = %s and uom = %s and ifnull(customer, '') = %s
			and ifnull(valid_from, '2000-01-01') < %s
			and (valid_upto is null or valid_upto >= %s)
		order by valid_from desc limit 1""",
		(price_list, d.item_code, d.uom, d.customer or "", d.valid_from, d.valid_from),
	)
	return r[0][0] if r else None


def _noi_dung_email(price_list, dong, so_ngay_quy_dinh):
	hang = "".join(
		"<tr>"
		f"<td>{frappe.utils.escape_html(d.item_code)}</td>"
		f"<td>{frappe.utils.escape_html(d.item_name or '')}</td>"
		f"<td>{frappe.utils.escape_html(d.uom)}</td>"
		f"<td style='text-align:right'>{frappe.format(d.gia_cu, 'Currency') if d.gia_cu is not None else '-'}</td>"
		f"<td style='text-align:right'><b>{frappe.format(d.price_list_rate, 'Currency')}</b></td>"
		f"<td>{frappe.format(d.valid_from, 'Date')}</td>"
		"</tr>"
		for d in dong
	)
	return (
		"<p>"
		+ _("Kính gửi Quý khách,")
		+ "</p><p>"
		+ _("Công ty TNHH Miyano Việt Nam xin thông báo thay đổi giá các mặt hàng dưới đây:")
		+ "</p>"
		"<table border='1' cellpadding='4' cellspacing='0'>"
		"<tr><th>"
		+ "</th><th>".join(
			[_("Mã hàng"), _("Tên hàng"), _("ĐVT"), _("Giá hiện tại"), _("Giá mới"), _("Áp dụng từ ngày")]
		)
		+ "</th></tr>"
		+ hang
		+ "</table><p>"
		+ _("Giá chưa gồm VAT. Đơn hàng đặt trước ngày áp dụng giữ giá hiện tại.")
		+ "</p><p>"
		+ _("Kính đề nghị Quý khách phản hồi email này để xác nhận.")
		+ "</p>"
	)


# --- Báo giá NCC -> nháp giá trong bảng giá chờ (2.5) ------------------------


def ghi_chu_de_xuat(supplier_quotation):
	"""Dấu nối nháp giá với báo giá NCC đã sinh ra nó (so khớp nguyên văn khi hủy báo giá)."""
	return f"Đề xuất từ báo giá NCC: {supplier_quotation}"


def de_xuat_tu_bao_gia(doc, item_codes):
	"""Gọi từ `ghi_gia_mua` sau khi báo giá NCC ghi giá mua mới cho `item_codes`.

	Với mỗi bảng giá có báo trước mà mặt hàng đang có giá: giá chuẩn mới = giá gốc hôm nay
	(theo đúng cách kiểm giá, Đợt 1) x (1 + % lãi của khách dùng bảng giá đó). Khác giá đang
	áp thì tạo NHÁP trong bảng giá chờ, ngày hiệu lực = hôm nay (D2-3), báo Giám đốc.
	"""
	from erpnext.selling.kiem_gia.cau_hinh import cau_hinh, ty_le_lai_nhieu
	from erpnext.selling.kiem_gia.gia_goc import tim_gia_goc_nhieu, tinh_gia_chuan

	if not item_codes:
		return []
	hom_nay = getdate(nowdate())
	gia_goc = tim_gia_goc_nhieu(item_codes, hom_nay, doc.company)
	precision = frappe.get_precision("Item Price", "price_list_rate")
	tao = []
	for pl in frappe.get_all(
		"Price List",
		filters={"bao_truoc_khi_doi_gia": 1, "enabled": 1},
		fields=["name", "bang_gia_cho"],
	):
		if not pl.bang_gia_cho:
			continue
		khach = frappe.db.get_value("Customer", {"default_price_list": pl.name, "disabled": 0}, "name")
		ty_le = ty_le_lai_nhieu(khach, item_codes)
		for code in item_codes:
			goc, tl = gia_goc[code], ty_le[code]
			if goc.gia_goc is None or not tl.kiem:
				continue
			hien_hanh = frappe.db.sql(
				"""select uom, price_list_rate from `tabItem Price`
				where price_list = %s and item_code = %s and ifnull(customer, '') = ''
					and ifnull(valid_from, '2000-01-01') <= %s
					and (valid_upto is null or valid_upto >= %s)
				order by valid_from desc limit 1""",
				(pl.name, code, hom_nay, hom_nay),
				as_dict=True,
			)
			if not hien_hanh:
				continue  # mặt hàng chưa bán theo bảng giá này
			uom = hien_hanh[0].uom
			cf = _he_so(code, uom)
			if not cf:
				continue
			gia_moi = tinh_gia_chuan(goc.gia_goc, cf, tl.ty_le_lai, precision)
			if flt(gia_moi, precision) == flt(hien_hanh[0].price_list_rate, precision):
				continue
			if frappe.db.exists(
				"Item Price",
				{"price_list": pl.bang_gia_cho, "item_code": code, "uom": uom, "valid_from": hom_nay},
			):
				continue  # đã có nháp hôm nay; Giám đốc tự xem
			frappe.get_doc(
				{
					"doctype": "Item Price",
					"price_list": pl.bang_gia_cho,
					"item_code": code,
					"uom": uom,
					"price_list_rate": gia_moi,
					"valid_from": hom_nay,
					"note": ghi_chu_de_xuat(doc.name),
				}
			).insert(ignore_permissions=True)
			tao.append((pl.name, code, hien_hanh[0].price_list_rate, gia_moi))

	if tao:
		_bao_giam_doc(doc, tao, cau_hinh().vai_tro_sua_ty_le_lai)
	return tao


def xoa_de_xuat(doc):
	"""Gọi từ `xoa_gia_mua` (hủy báo giá NCC): xóa nháp còn nằm trong bảng giá chờ."""
	for name in frappe.get_all("Item Price", filters={"note": ghi_chu_de_xuat(doc.name)}, pluck="name"):
		if bang_gia_chinh_cua(frappe.db.get_value("Item Price", name, "price_list")):
			frappe.delete_doc("Item Price", name, ignore_permissions=True)


def _he_so(item_code, uom):
	if uom == frappe.get_cached_value("Item", item_code, "stock_uom"):
		return 1
	return flt(
		frappe.db.get_value(
			"UOM Conversion Detail",
			{"parent": item_code, "parenttype": "Item", "uom": uom},
			"conversion_factor",
		)
	)


def _bao_giam_doc(doc, tao, vai_tro):
	"""Thông báo trong hệ thống (chuông) cho người có vai trò Giám đốc, và cảnh báo trên màn hình."""
	from frappe.desk.doctype.notification_log.notification_log import make_notification_logs

	dong = "".join(
		f"<li>{pl}: {code} {frappe.format(cu, 'Currency')} → <b>{frappe.format(moi, 'Currency')}</b></li>"
		for pl, code, cu, moi in tao
	)
	noi_dung = _("Báo giá NCC {0} làm đổi giá bán. Đã tạo nháp trong bảng giá chờ:").format(doc.name)
	if vai_tro:
		users = frappe.get_all(
			"Has Role",
			filters={"role": vai_tro, "parenttype": "User"},
			pluck="parent",
			distinct=True,
		)
		if users:
			make_notification_logs(
				frappe._dict(
					subject=_("Có nháp đổi giá chờ gửi thông báo (báo giá NCC {0})").format(doc.name),
					email_content=noi_dung + f"<ul>{dong}</ul>",
					type="Alert",
					document_type="Price List",
					document_name=tao[0][0],
					from_user=frappe.session.user,
				),
				users,
			)
	if not frappe.flags.in_import:
		frappe.msgprint(
			noi_dung + f"<ul>{dong}</ul>" + _("Giám đốc sửa ngày hiệu lực rồi Gửi thông báo đổi giá."),
			title=_("Đổi giá bán"),
			indicator="blue",
		)
