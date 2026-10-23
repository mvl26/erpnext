# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Thông báo giá mới cho khách khi Miyano xác nhận Sales Order (BA12 R06, D10, D12).

Khi SO được Submit (Miyano xác nhận) mà có dòng "đề xuất khác bảng giá" (R05), hệ thống:
- gửi email cho người đặt đơn: mặt hàng, giá cũ (bảng giá KH), giá mới (giá trên SO),
  số văn bản; email lưu thành Communication trên timeline của SO và gắn vào ô
  `thong_bao_gia_moi`;
- để Portal (app `miyano_portal`, do Việt làm) hiển thị CÙNG nội dung qua
  `lay_thong_bao_gia_moi` — logic nằm ở đây, Portal chỉ hiển thị.

Người đặt đơn: email liên hệ của SO (`contact_email`); không có thì email của người tạo SO
nếu đó là tài khoản cổng (Website User).

Chỉ báo dòng khách đã chấp thuận. Dòng thêm bằng "Update Items" sau Submit chờ khách chấp
thuận (Q10); khi nhân viên nhập đủ thông tin, `gui_bo_sung` gửi email bổ sung cho các dòng
đó. Mặt hàng chưa có trong bảng giá KH: giá cũ ghi "Chưa có trong bảng giá" (Q2).
"""

import frappe
from frappe import _
from frappe.core.doctype.communication.email import _make
from frappe.utils import cint, flt

CHUA_CO_TRONG_BANG_GIA = "Chưa có trong bảng giá"


def gui_khi_xac_nhan(doc, method=None):
	"""`on_submit` của Sales Order."""
	from erpnext.selling.kiem_gia.cau_hinh import cau_hinh

	dong = dong_gia_moi(doc) if cau_hinh().bat else []
	if dong:
		_gui(doc, dong)


def gui_bo_sung(doc, method=None):
	"""`on_update_after_submit` của Sales Order (Q10): dòng vừa được nhập đủ thông tin khách
	chấp thuận trên SO đã Submit (`chap_thuan.ghi_chap_thuan` đánh dấu)."""
	vua_du = set(doc.flags.get("dong_vua_chap_thuan") or ())
	dong = [d for d in doc.get("items") if d.name in vua_du]
	if dong:
		_gui(doc, dong, bo_sung=True)


def _gui(doc, dong, bo_sung=False):
	email = nguoi_dat_don(doc)
	if not email:
		frappe.msgprint(
			_("SO có giá mới nhưng không có email người đặt đơn: chưa gửi được thông báo giá mới cho khách."),
			title=_("Thông báo giá mới"),
			indicator="orange",
		)
		return
	tieu_de = (
		_("Thông báo giá mới (bổ sung) - Đơn hàng {0}") if bo_sung else _("Thông báo giá mới - Đơn hàng {0}")
	)
	comm = _make(
		doctype=doc.doctype,
		name=doc.name,
		subject=tieu_de.format(doc.name),
		content=noi_dung(doc, dong, bo_sung),
		recipients=email,
		send_email=True,
	)
	# Ô giữ thông báo đầu tiên; thông báo bổ sung xem trên timeline của SO.
	if not doc.get("thong_bao_gia_moi"):
		doc.db_set("thong_bao_gia_moi", comm["name"])


@frappe.whitelist()
def lay_thong_bao_gia_moi(sales_order):
	"""Dữ liệu thông báo giá mới của một SO đã xác nhận, cho Portal hiển thị (R06).

	Trả về `{"sales_order", "customer", "ngay", "dong": [{item_code, item_name, uom,
	gia_cu, gia_moi, so_van_ban, ngay_chap_thuan}]}`; SO chưa xác nhận hoặc không có giá
	mới thì `dong` rỗng. `gia_cu` là null khi mặt hàng chưa có trong bảng giá KH — hiển thị
	"Chưa có trong bảng giá" như email. Dòng còn chờ khách chấp thuận chưa có ở đây. Quyền:
	người xem được SO (khách qua cổng chỉ thấy đơn của mình).
	"""
	doc = frappe.get_doc("Sales Order", sales_order)
	doc.check_permission("read")
	dong = dong_gia_moi(doc) if doc.docstatus == 1 else []
	return {
		"sales_order": doc.name,
		"customer": doc.customer,
		"ngay": doc.transaction_date,
		"dong": [
			{
				"item_code": d.item_code,
				"item_name": d.item_name,
				"uom": d.uom,
				"gia_cu": None if cint(d.get("ngoai_bang_gia")) else flt(d.gia_bang_gia),
				"gia_moi": flt(d.rate),
				"so_van_ban": d.so_van_ban_gia,
				"ngay_chap_thuan": d.ngay_chap_thuan_gia,
			}
			for d in dong
		],
	}


def dong_gia_moi(doc):
	"""Dòng khác bảng giá (R05) đã có đủ thông tin khách chấp thuận."""
	return [d for d in doc.get("items") if cint(d.get("khac_bang_gia")) and not cint(d.get("cho_chap_thuan"))]


def nguoi_dat_don(doc):
	if doc.get("contact_email"):
		return doc.contact_email
	if frappe.db.get_value("User", doc.owner, "user_type") == "Website User":
		return doc.owner
	return None


def noi_dung(doc, dong, bo_sung=False):
	hang = "".join(
		"<tr>"
		f"<td>{frappe.utils.escape_html(d.item_code)}</td>"
		f"<td>{frappe.utils.escape_html(d.item_name or '')}</td>"
		f"<td>{frappe.utils.escape_html(d.uom or '')}</td>"
		f"<td style='text-align:right'>{_gia_cu(doc, d)}</td>"
		f"<td style='text-align:right'>{frappe.format(d.rate, {'fieldtype': 'Currency', 'options': 'currency'}, doc=doc)}</td>"
		f"<td>{frappe.utils.escape_html(d.so_van_ban_gia or '')}</td>"
		"</tr>"
		for d in dong
	)
	return (
		"<p>"
		+ _("Kính gửi Quý khách {0},").format(frappe.utils.escape_html(doc.customer_name or doc.customer))
		+ "</p><p>"
		+ (
			_(
				"Miyano bổ sung thông báo giá mới cho đơn hàng {0} ngày {1}. Các mặt hàng dưới đây áp dụng giá mới theo văn bản đã được Quý khách chấp thuận:"
			)
			if bo_sung
			else _(
				"Miyano đã xác nhận đơn hàng {0} ngày {1}. Các mặt hàng dưới đây áp dụng giá mới theo văn bản đã được Quý khách chấp thuận:"
			)
		).format(doc.name, frappe.format(doc.transaction_date, "Date"))
		+ "</p><table border='1' cellpadding='4' style='border-collapse:collapse'><thead><tr>"
		+ "".join(
			f"<th>{h}</th>"
			for h in (_("Mã hàng"), _("Tên hàng"), _("ĐVT"), _("Giá cũ"), _("Giá mới"), _("Số văn bản"))
		)
		+ f"</tr></thead><tbody>{hang}</tbody></table>"
	)


def _gia_cu(doc, d):
	if cint(d.get("ngoai_bang_gia")):
		return _(CHUA_CO_TRONG_BANG_GIA)
	return frappe.format(d.gia_bang_gia, {"fieldtype": "Currency", "options": "currency"}, doc=doc)
