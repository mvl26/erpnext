# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Cài đặt và quyền của đối soát Phiếu nhập mua ↔ Hóa đơn mua (YC5).

- Công tắc, phạm vi (bật thử theo nhà cung cấp), tự tạo ĐNTT: Buying Settings.
- Duyệt ngoại lệ (E8): hai ô vai trò Kế toán trưởng / Ban Điều hành, không tạo vai trò mới.
  Để trống cả hai: chỉ System Manager.
- Ai cũng có thể đọc cài đặt qua `cau_hinh()`, nhưng chỉ System Manager sửa được các ô YC5
  (Purchase Manager có quyền ghi Buying Settings, không được tự gán mình làm người duyệt).
"""

import frappe
from frappe import _
from frappe.utils import cint

TRUONG_CAI_DAT = (
	"bat_doi_soat_pr_pi",
	"pham_vi_doi_soat",
	"tao_dntt_khi_nop_hoa_don",
	"vai_tro_ke_toan_truong",
	"vai_tro_ban_dieu_hanh",
	"nguoi_duyet_dntt",
	"so_ngay_nhac_lech",
)
CHI_NCC_CHON = "Chỉ nhà cung cấp được chọn"


def cau_hinh():
	# Đọc thẳng DB, không qua cache Redis (như BA12 `kiem_gia.cau_hinh`): công tắc và quyền
	# phải đúng giá trị đang lưu kể cả khi cài đặt bị ghi bằng set_single_value.
	s = frappe._dict(frappe.db.get_singles_dict("Buying Settings", cast=True))
	return frappe._dict(
		bat=cint(s.get("bat_doi_soat_pr_pi")),
		chi_ncc_chon=(s.get("pham_vi_doi_soat") or CHI_NCC_CHON) == CHI_NCC_CHON,
		tao_dntt=cint(s.get("tao_dntt_khi_nop_hoa_don")),
		vai_tro_duyet=[r for r in (s.get("vai_tro_ke_toan_truong"), s.get("vai_tro_ban_dieu_hanh")) if r],
		vai_tro_ke_toan_truong=s.get("vai_tro_ke_toan_truong"),
		nguoi_duyet_dntt=s.get("nguoi_duyet_dntt"),
		so_ngay_nhac_lech=cint(s.get("so_ngay_nhac_lech")),
	)


def ap_dung(doc, c=None):
	"""Hóa đơn này có thuộc phạm vi đối soát không (chưa xét dòng có liên kết Phiếu nhập)."""
	c = c or cau_hinh()
	if not c.bat or doc.doctype != "Purchase Invoice":
		return False
	# Hóa đơn trả hàng và hóa đơn tự nhập kho (update_stock) không có Phiếu nhập để so.
	if cint(doc.is_return) or cint(doc.update_stock):
		return False
	if c.chi_ncc_chon and not frappe.db.get_value("Supplier", doc.supplier, "doi_soat_pr_pi"):
		return False
	return True


def co_quyen_duyet_ngoai_le(c=None):
	if frappe.session.user == "Administrator":
		return True
	vai_tro = (c or cau_hinh()).vai_tro_duyet or ["System Manager"]
	return bool(set(vai_tro) & set(frappe.get_roles()))


def _la_quan_tri():
	return frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles()


# --- doc_events -----------------------------------------------------------------


def kiem_buying_settings(doc, method=None):
	"""`Buying Settings.validate`: chỉ System Manager đổi được các ô YC5."""
	truoc = doc.get_doc_before_save()
	doi = [f for f in TRUONG_CAI_DAT if truoc and (truoc.get(f) or "") != (doc.get(f) or "")]
	if doi and not _la_quan_tri():
		frappe.throw(
			_("Chỉ System Manager được sửa cài đặt đối soát Phiếu nhập ↔ Hóa đơn: {0}.").format(
				", ".join(_(doc.meta.get_label(f)) for f in doi)
			),
			frappe.PermissionError,
		)


def kiem_supplier(doc, method=None):
	"""`Supplier.validate`: bật / tắt áp đối soát cho nhà cung cấp là việc của người duyệt
	ngoại lệ, không phải của người lập hóa đơn."""
	truoc = doc.get_doc_before_save()
	cu = cint(truoc.get("doi_soat_pr_pi")) if truoc else 0
	if cint(doc.get("doi_soat_pr_pi")) != cu and not (_la_quan_tri() or co_quyen_duyet_ngoai_le()):
		frappe.throw(
			_("Chỉ người duyệt ngoại lệ đối soát hoặc System Manager được đổi ô {0}.").format(
				frappe.bold(_(doc.meta.get_label("doi_soat_pr_pi")))
			),
			frappe.PermissionError,
		)
