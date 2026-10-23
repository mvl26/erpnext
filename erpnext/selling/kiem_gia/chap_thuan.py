# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Thông tin khách chấp thuận giá trên dòng Sales Order (BA12 R05, D09; PO chốt Q1, Q10
ngày 22/10/2026).

Dòng "khác bảng giá" (R05) cần 3 thông tin: số văn bản, người đại diện KH, ngày chấp thuận —
thêm tệp văn bản nếu Selling Settings bật `bat_buoc_dinh_kem_van_ban_gia`.

- Q1 — ai nhập: nhân viên sửa được SO thì nhập, không có bước duyệt. Kiểm soát bù: hệ thống
  ghi người nhập và thời điểm trên từng dòng (không gõ tay được), báo cáo A08 hiện hai cột
  này để kế toán hậu kiểm; sau Submit, ô còn trống vẫn điền được, ô đã điền chỉ vai trò Giám
  đốc (`vai_tro_sua_ty_le_lai`) sửa.
- Q10 — "Update Items" thêm/đổi dòng khác bảng giá: không chặn; dòng ở trạng thái "Chờ
  khách chấp thuận giá" (`cho_chap_thuan`). Nhân viên điền thông tin ngay trên SO đã Submit;
  khi đủ, hệ thống gửi email thông báo giá mới bổ sung (R06, `thong_bao_gia_moi.gui_bo_sung`).
  Trong lúc chờ, không tạo được Phiếu giao hàng / Hóa đơn bán cho dòng đó
  (`chan_giao_hoa_don`). Không dùng Amend: SO đã có phiếu giao hay hóa đơn thì không hủy
  được, số SO đổi, liên kết Portal đứt.

`cho_chap_thuan` chỉ tính lại khi dòng được kiểm giá lại hoặc thông tin chấp thuận đổi, nên
bật bắt buộc tệp đính kèm không đưa các dòng đã chấp thuận trước đó về trạng thái chờ.
"""

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from erpnext.selling.kiem_gia.cau_hinh import cau_hinh, co_quyen_sua_ty_le_lai

TRUONG_CHAP_THUAN = ("so_van_ban_gia", "nguoi_dai_dien_kh", "ngay_chap_thuan_gia")
TEP_VAN_BAN = "tep_van_ban_gia"
TRUONG_GHI_NHAN = (*TRUONG_CHAP_THUAN, TEP_VAN_BAN)


def truong_bat_buoc():
	"""Các ô phải có để dòng khác bảng giá được coi là khách đã chấp thuận."""
	return TRUONG_CHAP_THUAN + ((TEP_VAN_BAN,) if cau_hinh().dinh_kem else ())


def thieu(d, truong):
	return [f for f in truong if not _gia_tri(d.get(f))]


def _gia_tri(v):
	return "" if v is None else str(v).strip()


def ghi_chap_thuan(doc, truoc=None, kiem_lai=(), sau_submit=False):
	"""Cập nhật trạng thái chờ, người nhập, thời điểm nhập cho từng dòng SO.

	`truoc`: bản trong DB trước lần lưu này. Trước Submit, trạng thái chờ tính lại cho mọi
	dòng. Sau Submit, chỉ tính lại cho dòng vừa kiểm giá lại (`kiem_lai`, "Update Items") hoặc
	vừa đổi thông tin chấp thuận; dòng khác giữ giá trị đã lưu. Người nhập / thời điểm chỉ đổi
	khi thông tin chấp thuận đổi — giá trị gửi lên khác đi đều bị trả về như cũ.

	Sau Submit: sửa ô đã điền cần quyền Giám đốc; dòng vừa hết chờ được ghi vào
	`doc.flags.dong_vua_chap_thuan` để gửi thông báo giá mới bổ sung sau khi lưu.
	"""
	truong = truong_bat_buoc()
	cu = {d.name: d for d in (truoc.get("items") if truoc else [])}
	sua_da_dien, vua_du = [], []
	for d in doc.get("items"):
		c = cu.get(d.name) or frappe._dict()
		doi = [f for f in TRUONG_GHI_NHAN if _gia_tri(d.get(f)) != _gia_tri(c.get(f))]
		if doi:
			co_gia_tri = any(_gia_tri(d.get(f)) for f in TRUONG_GHI_NHAN)
			d.nguoi_nhap_chap_thuan = frappe.session.user if co_gia_tri else None
			d.thoi_diem_nhap_chap_thuan = now_datetime() if co_gia_tri else None
			if sau_submit:
				sua_da_dien += [(d, f) for f in doi if _gia_tri(c.get(f))]
		else:
			d.nguoi_nhap_chap_thuan = c.get("nguoi_nhap_chap_thuan")
			d.thoi_diem_nhap_chap_thuan = c.get("thoi_diem_nhap_chap_thuan")

		if not sau_submit or doi or d.name in kiem_lai:
			d.cho_chap_thuan = 1 if cint(d.get("khac_bang_gia")) and thieu(d, truong) else 0
		else:
			d.cho_chap_thuan = cint(c.get("cho_chap_thuan"))
		if (
			sau_submit
			and cint(c.get("cho_chap_thuan"))
			and cint(d.get("khac_bang_gia"))
			and not d.cho_chap_thuan
		):
			vua_du.append(d.name)

	if sua_da_dien and not co_quyen_sua_ty_le_lai():
		meta = frappe.get_meta("Sales Order Item")
		chi_tiet = "".join(
			"<li>"
			+ _("Dòng {0} - {1}: {2}").format(d.idx, frappe.bold(d.item_code), _(meta.get_label(f)))
			+ "</li>"
			for d, f in sua_da_dien
		)
		frappe.throw(
			_(
				"Thông tin khách chấp thuận đã điền chỉ vai trò {0} được sửa (ô còn trống thì vẫn điền được):"
			).format(frappe.bold(cau_hinh().vai_tro_sua_ty_le_lai or "System Manager"))
			+ f"<ul>{chi_tiet}</ul>",
			frappe.PermissionError,
			title=_("Kiểm giá bán"),
		)
	doc.flags.dong_vua_chap_thuan = vua_du


def chan_giao_hoa_don(doc, method=None):
	"""`validate` của Delivery Note / Sales Invoice (Q10): không lập phiếu cho dòng SO còn chờ
	khách chấp thuận giá. Chỉ đọc trạng thái đã lưu trên dòng SO — không kiểm lại giá ở hóa
	đơn (BA12 để ngoài phạm vi)."""
	if cint(doc.get("is_return")) or not cau_hinh().bat:
		return
	dong_so = {d.so_detail for d in doc.get("items") if d.get("so_detail")}
	if not dong_so:
		return
	cho = {
		r.name: r
		for r in frappe.get_all(
			"Sales Order Item",
			filters={"name": ("in", list(dong_so)), "cho_chap_thuan": 1, "docstatus": 1},
			fields=["name", "parent", "idx"],
		)
	}
	if not cho:
		return
	chi_tiet = "".join(
		"<li>"
		+ _("Dòng {0} - {1}: dòng {2} của {3}").format(
			d.idx, frappe.bold(d.item_code), cho[d.so_detail].idx, cho[d.so_detail].parent
		)
		+ "</li>"
		for d in doc.get("items")
		if d.get("so_detail") in cho
	)
	frappe.throw(
		_(
			"Khách chưa chấp thuận giá mới của các dòng đơn hàng dưới đây. Nhập số văn bản, người đại diện KH, ngày chấp thuận trên dòng của Sales Order rồi bấm Cập nhật, hoặc bỏ các dòng này khỏi phiếu:"
		)
		+ f"<ul>{chi_tiet}</ul>",
		title=_("Chờ khách chấp thuận giá"),
	)
