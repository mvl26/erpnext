# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Báo trước khi đổi giá bán (YC4; spec mục 6.2 và 14).

Bảng giá bán có tích "Báo trước khi đổi giá" (vd. "Bảng giá Himedic") đi kèm một BẢNG GIÁ
CHỜ. Giá mới luôn vào bảng giá chờ trước; chỉ khi Giám đốc "Gửi thông báo đổi giá" thì
dòng mới được chuyển sang bảng giá chính. Nhờ vậy giá chưa báo không bao giờ được áp.

Trên bảng giá chính: không thêm thẳng, không sửa giá/ngày/ĐVT/mặt hàng/khách của dòng có
sẵn, không xóa (giá cũ phải còn để SO cũ đúng giá — D4-4). Ô xác nhận vẫn sửa được.

Giá mới do người nhập vào bảng giá chờ — hệ thống không tự tạo nháp từ báo giá NCC (BA12
D09: bảng giá khách hàng cập nhật thủ công). Trường trên Price List / Item Price là Custom
Field (`truong_tuy_bien.py`), gắn logic qua hooks.py.
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


def kiem_price_list(doc, method=None):
	"""`validate` của Price List."""
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


def kiem_chung_tu_ban(doc, method=None):
	"""`validate` của chứng từ bán: không bán theo bảng giá chờ (giá chưa báo)."""
	pl = doc.get("selling_price_list")
	chinh = bang_gia_chinh_cua(pl)
	if chinh:
		frappe.throw(
			_("{0} là bảng giá chờ (giá chưa báo cho khách). Dùng bảng giá {1}.").format(
				frappe.bold(pl), frappe.bold(chinh)
			)
		)


# --- Item Price (2.2, 2.3) -----------------------------------------------------


def kiem_item_price(doc, method=None):
	"""`validate` của Item Price."""
	truoc = doc.get_doc_before_save()
	pl_truoc = truoc.price_list if truoc else None
	if doc.flags.tu_thong_bao_doi_gia:
		return
	chinh = None if co_bao_truoc(pl_truoc) else bang_gia_chinh_cua(doc.price_list)
	if chinh:
		_dong_cho(doc)
		_chan_chong_lan(doc, chinh)
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


def chan_xoa_item_price(doc, method=None):
	"""`on_trash` của Item Price."""
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


def _chan_chong_lan(doc, chinh):
	"""Lưu dòng giá chờ: không chồng khoảng ngày với giá khác (T10)."""
	for _d, k in cap_chong_lan(chinh, [doc]):
		frappe.throw(
			_(
				"Giá {0} ({1}) {2} chồng lên giá {3} của bảng giá {4}. Mỗi ngày chỉ một giá: dùng ngày hiệu lực từ khác và để trống Hiệu lực đến, giá sau tự thay giá trước. Muốn quay về giá cũ thì thêm một dòng giá mới."
			).format(frappe.bold(doc.item_code), doc.uom, _khoang_chu(doc), _khoang_chu(k), k.price_list)
		)


def _khac(a, b):
	if a in (None, "") and b in (None, ""):
		return False
	if hasattr(a, "year") or hasattr(b, "year"):
		return (getdate(a) if a else None) != (getdate(b) if b else None)
	if isinstance(a, int | float) or isinstance(b, int | float):
		return float(a or 0) != float(b or 0)
	return a != b


# --- Khoảng ngày (T10) ---------------------------------------------------------


def _khoang(d):
	return getdate(d.valid_from or "2000-01-01"), getdate(d.valid_upto) if d.valid_upto else None


def _khoang_chu(d):
	tu, den = _khoang(d)
	if den is None:
		return _("từ {0}").format(frappe.format(tu, "Date"))
	return f"{frappe.format(tu, 'Date')} → {frappe.format(den, 'Date')}"


def chong_lan(a, b):
	"""T10: hai dòng giá cùng mặt hàng, ĐVT, khách, lô có cùng hiệu lực ở một ngày nào đó.

	Giá sau không có Hiệu lực đến tự thay giá trước từ ngày của nó (T1b, spec 6.2.1): đó là cách
	đổi giá, không phải chồng lấn. Chồng lấn là: cùng ngày hiệu lực từ (không biết áp giá nào);
	giá trước có Hiệu lực đến kéo sang giá sau; hoặc giá sau có Hiệu lực đến trong khi giá trước
	còn hiệu lực — hết hạn thì giá trước tự quay lại mà khách không được báo (email đổi giá chỉ
	ghi ngày áp dụng)."""
	(tu_1, den_1), (tu_2, den_2) = sorted((_khoang(a), _khoang(b)), key=lambda k: k[0])
	if tu_1 == tu_2:
		return True
	if den_1 is not None:
		return den_1 >= tu_2
	return den_2 is not None


def _khoa(d):
	return (d.item_code, d.uom, d.customer or "", d.batch_no or "")


def cap_chong_lan(chinh, dong):
	"""[(dòng trong `dong`, dòng khác)] chồng khoảng ngày (T10), xét cả bảng giá chính lẫn bảng
	giá chờ của nó; mỗi cặp một lần."""
	cho = frappe.db.get_value("Price List", chinh, "bang_gia_cho")
	tat_ca = frappe.get_all(
		"Item Price",
		filters={"price_list": ("in", [chinh, cho]), "item_code": ("in", list({d.item_code for d in dong}))},
		fields=["name", "price_list", "item_code", "uom", "customer", "batch_no", "valid_from", "valid_upto"],
	)
	kq, da_xet = [], set()
	for d in dong:
		for k in tat_ca:
			cap = frozenset((d.name, k.name))
			if k.name == d.name or cap in da_xet or _khoa(k) != _khoa(d) or not chong_lan(d, k):
				continue
			da_xet.add(cap)
			kq.append((d, k))
	return kq


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
		fields=[
			"name",
			"item_code",
			"item_name",
			"uom",
			"customer",
			"batch_no",
			"price_list_rate",
			"valid_from",
			"valid_upto",
		],
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

	# T10. Giá chờ đã kiểm lúc lưu; kiểm lại vì bảng giá chính hay giá chờ khác có thể đổi sau đó.
	chong = cap_chong_lan(price_list, dong)
	if chong:
		frappe.throw(
			_("Giá chờ chồng khoảng ngày với giá khác, sửa giá chờ trước khi gửi:")
			+ "<ul>"
			+ "".join(
				f"<li>{d.item_code} ({d.uom}): {_khoang_chu(d)} — {_khoang_chu(k)} ({k.price_list})</li>"
				for d, k in chong
			)
			+ "</ul>",
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
