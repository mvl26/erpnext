# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Nhắc Kế toán trưởng: hóa đơn mua lệch Phiếu nhập tồn quá N ngày (YC5, spec 6.3.9).

Không dùng điểm nhắc theo ngày của Supply Notification vì hai lẽ: bộ nhắc đó chỉ quét chứng từ đã
Nộp (hóa đơn lệch là bản nháp), và người nhận phải là người giữ "Vai trò Kế toán trưởng" đang
chọn trong Buying Settings — Supply Notification chỉ chọn người nhận theo phòng ban hoặc từng
người. Mỗi sáng gửi MỘT thông báo tổng hợp cho mỗi Kế toán trưởng (chuông + email theo cài đặt
thông báo của người đó), lặp lại hằng ngày tới khi hóa đơn được xử lý.
"""

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import make_notification_logs
from frappe.utils import add_days, date_diff, escape_html, get_link_to_form, today

from erpnext.accounts.doi_soat_pr_pi.cau_hinh import cau_hinh
from erpnext.accounts.doi_soat_pr_pi.doi_soat import CHUA_DOI_SOAT, LECH


def ke_toan_truong(c=None):
	c = c or cau_hinh()
	if not c.vai_tro_ke_toan_truong:
		return []
	nguoi = frappe.get_all(
		"Has Role",
		filters={"role": c.vai_tro_ke_toan_truong, "parenttype": "User"},
		pluck="parent",
		distinct=True,
	)
	return [
		u
		for u in frappe.get_all(
			"User",
			filters={"name": ("in", nguoi or [""]), "enabled": 1, "user_type": "System User"},
			pluck="name",
			order_by="name",
		)
		if u not in ("Administrator", "Guest")
	]


def hoa_don_lech_qua_han(so_ngay, ngay=None):
	return frappe.get_all(
		"Purchase Invoice",
		filters={
			"docstatus": 0,
			"trang_thai_doi_soat_pr": ("in", [LECH, CHUA_DOI_SOAT]),
			"lech_tu_ngay": ("<=", add_days(ngay or today(), -so_ngay)),
		},
		fields=[
			"name",
			"supplier_name",
			"bill_no",
			"grand_total",
			"currency",
			"lech_tu_ngay",
			"trang_thai_doi_soat_pr",
			"nhanh_xu_ly",
			"owner",
		],
		order_by="lech_tu_ngay asc, name asc",
	)


def _noi_dung(ds, ngay):
	dong = "".join(
		"<tr>"
		f"<td>{get_link_to_form('Purchase Invoice', r.name)}</td>"
		f"<td>{escape_html(r.supplier_name or '')}</td>"
		f"<td>{escape_html(r.bill_no or '')}</td>"
		f"<td style='text-align:right'>{frappe.format(r.grand_total, {'fieldtype': 'Currency', 'options': r.currency})}</td>"
		f"<td>{frappe.format(r.lech_tu_ngay, 'Date')} ({date_diff(ngay, r.lech_tu_ngay)} {_('ngày')})</td>"
		f"<td>{escape_html(_(r.trang_thai_doi_soat_pr))}</td>"
		f"<td>{escape_html(r.nhanh_xu_ly or _('Chưa chọn'))}</td>"
		f"<td>{escape_html(frappe.utils.get_fullname(r.owner))}</td>"
		"</tr>"
		for r in ds
	)
	dau = "".join(
		f"<th>{escape_html(t)}</th>"
		for t in (
			_("Hóa đơn"),
			_("Nhà cung cấp"),
			_("Số HĐ NCC"),
			_("Giá trị"),
			_("Lệch từ"),
			_("Trạng thái"),
			_("Nhánh xử lý"),
			_("Người lập"),
		)
	)
	return (
		"<p>"
		+ _("Các hóa đơn mua dưới đây chưa khớp Phiếu nhập mua và chưa Nộp được:")
		+ "</p>"
		+ f"<table border='1' cellpadding='4' cellspacing='0'><thead><tr>{dau}</tr></thead><tbody>{dong}</tbody></table>"
		+ "<p>"
		+ _("Đề nghị đôn đốc xử lý theo nhánh đã chọn, hoặc xem xét Duyệt ngoại lệ.")
		+ "</p>"
	)


def nhac_ke_toan_truong(ngay=None):
	"""Scheduler, 8 giờ sáng hằng ngày (hooks.py). Trả về số hóa đơn đã nhắc."""
	c = cau_hinh()
	if not c.bat or c.so_ngay_nhac_lech <= 0:
		return 0
	ngay = ngay or today()
	ds = hoa_don_lech_qua_han(c.so_ngay_nhac_lech, ngay)
	if not ds:
		return 0
	nguoi = ke_toan_truong(c)
	if not nguoi:
		frappe.log_error(
			title=_("Đối soát PR ↔ PI: không có Kế toán trưởng để nhắc"),
			message=_("Buying Settings chưa chọn Vai trò Kế toán trưởng, hoặc vai trò chưa gán cho ai."),
		)
		return 0

	tieu_de = _("{0} hóa đơn mua lệch Phiếu nhập quá {1} ngày").format(len(ds), c.so_ngay_nhac_lech)
	thong_bao = {
		"type": "Alert",
		"subject": tieu_de,
		"email_content": _noi_dung(ds, ngay),
		"from_user": "Administrator",
	}
	if len(ds) == 1:
		thong_bao.update(document_type="Purchase Invoice", document_name=ds[0].name)
	for u in nguoi:
		frappe.db.savepoint("nhac_lech")
		try:
			make_notification_logs(frappe._dict(thong_bao), [u])
		except Exception:
			frappe.db.rollback(save_point="nhac_lech")
			frappe.log_error(title=_("Đối soát PR ↔ PI: không gửi được nhắc cho {0}").format(u))
	return len(ds)
