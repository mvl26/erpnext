# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Dữ liệu cho email hóa đơn chính thức theo mẫu Miyano (phân tích "Tự gửi HĐĐT", mục 4.1).

Mẫu email chỉ đọc biến ``hd``; mọi chỗ ghép, định dạng, lấy dự phòng nằm ở đây
để mẫu (do kế toán có thể sửa tay) không phải chứa logic. Tên khóa đặt đúng tên
biến trong ``docs/fast_miyano/Mau_Email_Gui_Hoa_Don_Miyano.md``.
"""

import frappe
from frappe.utils import fmt_money, get_fullname, getdate

from erpnext.einvoice.fast_settings import split_emails

# Hai tài khoản này không phải người thật đang bấm nút — job nền chạy dưới
# Administrator. Người gửi khi đó là đầu mối trong Settings.
_SYSTEM_USERS = frozenset({"Administrator", "Guest"})


def sender_for(settings, user=None):
	"""Người đứng tên gửi: ``{"name", "phone", "email"}``.

	Tự gửi không có người bấm nút nên lấy đầu mối cố định trong Settings. Gửi tay
	thì lấy người đang đăng nhập — khách phản hồi tới đúng người vừa gửi — và ô nào
	người đó không có thì lấy ô tương ứng của Settings.
	"""
	fallback = {
		"name": settings.invoice_sender_name or "",
		"phone": settings.invoice_sender_phone or "",
		"email": settings.invoice_sender_email or "",
	}
	if not user or user in _SYSTEM_USERS:
		return fallback

	email, mobile = frappe.db.get_value("User", user, ["email", "mobile_no"]) or ("", "")
	return {
		"name": get_fullname(user) or fallback["name"],
		"phone": mobile or fallback["phone"],
		"email": email or fallback["email"],
	}


def cc_for(settings, extra=None):
	"""CC kế toán trong Settings cộng CC người gửi tự thêm — bỏ trùng, giữ thứ tự gặp đầu tiên."""
	if isinstance(extra, list | tuple):
		extra = ",".join(value or "" for value in extra)
	seen, result = set(), []
	for email in [*settings.invoice_email_cc, *split_emails(extra)]:
		if email.lower() not in seen:
			seen.add(email.lower())
			result.append(email)
	return result


def email_context(doc, settings, sender):
	"""Biến ``hd`` của mẫu email hóa đơn chính thức."""
	po_no, due_date = _source_terms(doc)
	return {
		"nguoi_nhan": (doc.buyer or "").strip() or "Quý khách",
		"ten_khach_hang": doc.customer_name,
		# In nguyên số Fast trả về, không đệm số 0 (Q9).
		"so_hd": doc.fast_invoice_no,
		"ngay_hd": _dmy(doc.fast_signed_date),
		# Fast trả mẫu số và ký hiệu riêng; trên PDF in gộp: 1 + C26TAA = 1C26TAA.
		"ky_hieu": f"{doc.fast_pattern or ''}{doc.fast_serial or ''}",
		"ma_cqt": doc.tax_verification_code or "",
		"ma_tra_cuu": doc.get("fast_lookup_code") or "",
		"link_tra_cuu": doc.get("fast_lookup_url") or settings.lookup_url or "",
		"so_hop_dong_po": po_no,
		"tong_tien": fmt_money(doc.total_amount, currency=doc.currency),
		"han_thanh_toan": due_date,
		"co_xml": bool(doc.official_xml),
		"nguoi_gui": sender.get("name") or "",
		"sdt_nguoi_gui": sender.get("phone") or "",
		"email_nguoi_gui": sender.get("email") or "",
	}


def _source_terms(doc):
	"""Số hợp đồng/PO và hạn thanh toán — chỉ hóa đơn bán mới có."""
	if not doc.get("sales_invoice"):
		return "", ""
	values = frappe.db.get_value("Sales Invoice", doc.sales_invoice, ["po_no", "due_date"], as_dict=True)
	if not values:
		return "", ""
	return (values.po_no or "").strip(), _dmy(values.due_date)


def _dmy(value):
	return getdate(value).strftime("%d/%m/%Y") if value else ""
