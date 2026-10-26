# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Đề nghị thanh toán (ĐNTT) sau đối soát (YC5, spec 6.3.7-6.3.8; D6, E9).

- Nộp hóa đơn đã Khớp / có ngoại lệ được duyệt → tạo ĐNTT **nháp** trong cùng transaction: tạo
  lỗi thì hóa đơn không Nộp được. Không dùng mapper chuẩn `make_payment_request` (hành vi của nó
  phụ thuộc `create_pr_in_draft_status`, xem spec 3.4 #1) và không Submit.
- Mọi ĐNTT trỏ vào Hóa đơn mua, tạo bằng bất cứ đường nào: tổng các bản chưa hủy, **tính cả bản
  nháp**, không vượt số tiền hóa đơn. Khóa dòng hóa đơn để hai yêu cầu đồng thời phải xếp hàng.
"""

import frappe
from frappe import _
from frappe.desk.form.assign_to import add as giao_viec
from frappe.utils import cint, flt, get_link_to_form, nowdate

from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_accounting_dimensions
from erpnext.accounts.doctype.payment_request.payment_request import get_amount
from erpnext.accounts.doi_soat_pr_pi.cau_hinh import ap_dung, cau_hinh
from erpnext.accounts.doi_soat_pr_pi.doi_soat import KHOP, NGOAI_LE
from erpnext.accounts.party import get_party_bank_account
from erpnext.accounts.utils import get_currency_precision

# Custom Field sẵn có trên Payment Request ở production (spec 3.5): dùng lại, không thêm trường.
TRUONG_HAN = "custom_thoi_han_thanh_toan"
TRUONG_NGUOI_YEU_CAU = "custom_nguoi_yeu_cau"
TRUONG_TEN_NGUOI_YEU_CAU = "custom_ten_nguoi_yeu_cau"


def tao_khi_nop_hoa_don(doc, method=None):
	"""`on_submit` của Hóa đơn mua."""
	c = cau_hinh()
	if not c.tao_dntt or not ap_dung(doc, c):
		return
	if doc.get("trang_thai_doi_soat_pr") not in (KHOP, NGOAI_LE):
		return
	so_tien = get_amount(doc)
	if not so_tien:
		return  # đã trả đủ (ứng trước, hóa đơn đã thanh toán)

	dntt = frappe.new_doc("Payment Request")
	dntt.update(
		{
			"payment_request_type": "Outward",
			"transaction_date": nowdate(),
			"company": doc.company,
			"party_type": "Supplier",
			"party": doc.supplier,
			"party_name": doc.supplier_name,
			"reference_doctype": doc.doctype,
			"reference_name": doc.name,
			"currency": doc.currency,
			"party_account_currency": doc.party_account_currency or doc.currency,
			"grand_total": so_tien,
			"bank_account": get_party_bank_account("Supplier", doc.supplier),
			"email_to": doc.get("contact_email"),
			"subject": _("Thanh toán hóa đơn {0} của {1}").format(doc.bill_no or doc.name, doc.supplier_name),
			"message": _("Hóa đơn {0} ngày {1}, hạn thanh toán {2}. Đối soát Phiếu nhập: {3}.").format(
				doc.bill_no or doc.name,
				frappe.format(doc.bill_date or doc.posting_date, "Date"),
				frappe.format(doc.due_date, "Date"),
				doc.trang_thai_doi_soat_pr,
			),
			"cost_center": doc.get("cost_center"),
			"project": doc.get("project"),
		}
	)
	for dimension in get_accounting_dimensions():
		dntt.set(dimension, doc.get(dimension))

	meta = frappe.get_meta("Payment Request")
	if meta.has_field(TRUONG_HAN):
		dntt.set(TRUONG_HAN, doc.due_date)
	if meta.has_field(TRUONG_NGUOI_YEU_CAU):
		dntt.set(TRUONG_NGUOI_YEU_CAU, frappe.session.user)
	if meta.has_field(TRUONG_TEN_NGUOI_YEU_CAU):
		dntt.set(TRUONG_TEN_NGUOI_YEU_CAU, frappe.utils.get_fullname(frappe.session.user))

	dntt.flags.mute_email = True
	dntt.insert(ignore_permissions=True)

	# Đính kèm và giao việc là phần phụ: lỗi thì báo, không làm hỏng việc Nộp hóa đơn.
	_lam_phan_phu(_dinh_kem_hoa_don, doc, dntt)
	_lam_phan_phu(_giao_cho_nguoi_duyet, doc, dntt, c)
	frappe.msgprint(
		_("Đã tạo đề nghị thanh toán nháp {0}.").format(get_link_to_form("Payment Request", dntt.name)),
		indicator="green",
		alert=True,
	)
	return dntt


def _lam_phan_phu(ham, *args):
	frappe.db.savepoint("dntt_phan_phu")
	try:
		ham(*args)
	except Exception:
		frappe.db.rollback(save_point="dntt_phan_phu")
		frappe.log_error(title=_("ĐNTT tự tạo: {0} lỗi").format(ham.__name__))
		frappe.msgprint(
			_("Đã tạo đề nghị thanh toán nhưng chưa {0}; xem Error Log.").format(
				_("đính kèm hóa đơn") if ham is _dinh_kem_hoa_don else _("giao việc cho người duyệt")
			),
			indicator="orange",
		)


def _dinh_kem_hoa_don(doc, dntt):
	"""Gắn file hóa đơn gốc vào ĐNTT, trỏ cùng tệp trên đĩa.

	Truyền nội dung dạng bytes thay vì chỉ `file_url`: Frappe đọc lại tệp theo `file_url` và giải mã
	thành chuỗi khi mọi byte là UTF-8 (PDF chỉ có ký tự ASCII), rồi bước kiểm PDF lỗi TypeError. Cùng
	nội dung thì Frappe nhận ra tệp trùng (content hash) nên dùng lại tệp cũ, không ghi bản sao.
	"""
	for name in frappe.get_all(
		"File",
		filters={"attached_to_doctype": doc.doctype, "attached_to_name": doc.name, "is_folder": 0},
		pluck="name",
	):
		f = frappe.get_doc("File", name)
		moi = {
			"doctype": "File",
			"file_name": f.file_name,
			"is_private": f.is_private,
			"attached_to_doctype": dntt.doctype,
			"attached_to_name": dntt.name,
		}
		if f.is_remote_file:
			moi["file_url"] = f.file_url
		else:
			with open(f.get_full_path(), "rb") as tep:
				moi["content"] = tep.read()
		frappe.get_doc(moi).insert(ignore_permissions=True)


def nguoi_duyet_dntt(c=None):
	c = c or cau_hinh()
	if c.nguoi_duyet_dntt:
		ung_vien = [c.nguoi_duyet_dntt]
	elif c.vai_tro_ke_toan_truong:
		ung_vien = frappe.get_all(
			"Has Role",
			filters={"role": c.vai_tro_ke_toan_truong, "parenttype": "User"},
			pluck="parent",
			distinct=True,
		)
	else:
		return []
	return frappe.get_all(
		"User",
		filters={"name": ("in", ung_vien), "enabled": 1, "user_type": "System User"},
		pluck="name",
		order_by="name",
	)


def _giao_cho_nguoi_duyet(doc, dntt, c):
	nguoi = [u for u in nguoi_duyet_dntt(c) if u not in ("Administrator", "Guest")]
	if not nguoi:
		frappe.msgprint(
			_(
				"Chưa có người duyệt đề nghị thanh toán trong Thiết lập mua hàng: {0} chưa được giao cho ai."
			).format(dntt.name),
			indicator="orange",
		)
		return
	giao_viec(
		{
			"doctype": dntt.doctype,
			"name": dntt.name,
			"assign_to": nguoi,
			"description": _("Duyệt đề nghị thanh toán cho hóa đơn {0} ({1}), hạn {2}.").format(
				doc.bill_no or doc.name, doc.supplier_name, frappe.format(doc.due_date, "Date")
			),
			"date": doc.due_date,
		},
		ignore_permissions=True,
	)


# --- doc_events ----------------------------------------------------------------


def kiem_tong_de_nghi(doc, method=None):
	"""`Payment Request.validate` (E9): tổng ĐNTT chưa hủy của một Hóa đơn mua ≤ số tiền hóa đơn.

	ERPNext chỉ cộng các bản đã Submit (spec 3.4 #3), nên hai bản nháp vẫn vượt tổng được. Ở đây
	khóa dòng hóa đơn (`FOR UPDATE`) rồi cộng bằng một lệnh đọc có khóa: lệnh đọc thường trong
	REPEATABLE READ dùng ảnh chụp cũ và không thấy bản vừa được tiến trình kia ghi xong.
	"""
	if doc.reference_doctype != "Purchase Invoice" or not doc.reference_name or doc.docstatus == 2:
		return
	if not cau_hinh().bat:
		return

	hoa_don = frappe.db.sql(
		"""select rounded_total, grand_total, docstatus from `tabPurchase Invoice`
		where name = %s for update""",
		doc.reference_name,
		as_dict=True,
	)
	if not hoa_don:
		return
	hoa_don = hoa_don[0]
	da_co = flt(
		frappe.db.sql(
			"""select coalesce(sum(grand_total), 0) from `tabPayment Request`
			where reference_doctype = 'Purchase Invoice' and reference_name = %s
				and docstatus < 2 and name != %s
			for update""",
			(doc.reference_name, doc.name or ""),
		)[0][0]
	)
	tien_hoa_don = flt(hoa_don.rounded_total) or flt(hoa_don.grand_total)
	tong = da_co + flt(doc.grand_total)
	if flt(tong - tien_hoa_don, get_currency_precision()) > 0:
		frappe.throw(
			_(
				"Tổng đề nghị thanh toán của hóa đơn {0} là {1}, vượt số tiền hóa đơn {2}"
				" (các đề nghị khác chưa hủy, kể cả bản nháp: {3})."
			).format(
				doc.reference_name,
				frappe.format(tong, {"fieldtype": "Currency", "options": doc.currency}),
				frappe.format(tien_hoa_don, {"fieldtype": "Currency", "options": doc.currency}),
				frappe.format(da_co, {"fieldtype": "Currency", "options": doc.currency}),
			),
			title=_("Vượt số tiền hóa đơn"),
		)


def xoa_nhap_khi_huy_hoa_don(doc, method=None):
	"""`on_cancel` của Hóa đơn mua: ĐNTT nháp trỏ vào hóa đơn bị xóa theo (6.3.8). ĐNTT đã Submit
	thì ERPNext đã chặn việc hủy hóa đơn từ trước."""
	if not cint(cau_hinh().bat):
		return
	for ten in frappe.get_all(
		"Payment Request",
		filters={"reference_doctype": doc.doctype, "reference_name": doc.name, "docstatus": 0},
		pluck="name",
	):
		frappe.delete_doc("Payment Request", ten, ignore_permissions=True, force=True)
		doc.add_comment("Info", _("Đã xóa đề nghị thanh toán nháp {0} khi hủy hóa đơn.").format(ten))
