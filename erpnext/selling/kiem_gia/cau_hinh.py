# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Cấu hình % lãi và quyền sửa (thiết kế mục 6.1.2, quyết định C3, C6, E3).

- Mặc định ở Selling Settings (`ty_le_lai_mac_dinh`, 1%), áp cho mọi khách.
- Khách: tắt kiểm (`kiem_gia_ban`) hoặc đặt % riêng (`ty_le_lai_rieng` + `ty_le_lai`).
- (Khách, mặt hàng): dòng trong bảng Item Customer Detail của mặt hàng, cùng hai cột.
- Thứ tự: (khách, mặt hàng) -> khách -> mặc định.

Chỉ vai trò ở `vai_tro_sua_ty_le_lai` được đổi các giá trị trên (chưa chọn vai trò thì
chỉ System Manager). Kiểm ở server nên chặn được cả form, import và API. % mới có hiệu
lực ngay khi lưu (không có valid_from); lịch sử nằm ở Version (track_changes).
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

CHI_GHI_NHAN = "Chỉ ghi nhận"
CHAN = "Chặn"
TY_LE_LAI_MAC_DINH = 1

# Trường của Selling Settings thuộc tính năng: đổi bất kỳ trường nào cũng cần quyền.
TRUONG_CAI_DAT = (
	"bat_kiem_gia_ban",
	"che_do_kiem_gia",
	"ty_le_lai_mac_dinh",
	"vai_tro_sua_ty_le_lai",
	"vai_tro_duyet_gia_lech",
)
TRUONG_KHACH = ("kiem_gia_ban", "ty_le_lai_rieng", "ty_le_lai")
MAC_DINH_KHACH = {"kiem_gia_ban": 1, "ty_le_lai_rieng": 0, "ty_le_lai": 0}


def cau_hinh():
	s = frappe.get_cached_doc("Selling Settings")
	ty_le = s.get("ty_le_lai_mac_dinh")
	return frappe._dict(
		bat=cint(s.get("bat_kiem_gia_ban")),
		che_do=s.get("che_do_kiem_gia") or CHI_GHI_NHAN,
		ty_le_lai_mac_dinh=TY_LE_LAI_MAC_DINH if ty_le is None else flt(ty_le),
		vai_tro_sua_ty_le_lai=s.get("vai_tro_sua_ty_le_lai"),
		vai_tro_duyet_gia_lech=s.get("vai_tro_duyet_gia_lech"),
	)


def ty_le_lai_ap_dung(customer, item_code):
	"""% lãi cho một (khách, mặt hàng): `_dict(kiem, ty_le_lai, nguon)`.

	`kiem` = 0 khi khách tắt kiểm; khi đó `ty_le_lai` là None.
	"""
	return ty_le_lai_nhieu(customer, [item_code])[item_code]


def ty_le_lai_nhieu(customer, item_codes):
	"""{mã hàng: `_dict(kiem, ty_le_lai, nguon)`} cho một khách, một lượt truy vấn."""
	ch = cau_hinh()
	khach = (
		frappe.get_cached_value("Customer", customer, list(TRUONG_KHACH), as_dict=True) if customer else None
	)
	if khach and not cint(khach.kiem_gia_ban):
		tat = frappe._dict(kiem=0, ty_le_lai=None, nguon=_("Khách tắt kiểm giá"))
		return {code: tat for code in item_codes}

	rieng = {}
	codes = [c for c in item_codes if c]
	if customer and codes:
		rieng = dict(
			frappe.get_all(
				"Item Customer Detail",
				filters={
					"parenttype": "Item",
					"parent": ("in", codes),
					"customer_name": customer,
					"ty_le_lai_rieng": 1,
				},
				fields=["parent", "ty_le_lai"],
				as_list=True,
			)
		)

	if khach and cint(khach.ty_le_lai_rieng):
		chung = frappe._dict(kiem=1, ty_le_lai=flt(khach.ty_le_lai), nguon=_("Khách"))
	else:
		chung = frappe._dict(kiem=1, ty_le_lai=ch.ty_le_lai_mac_dinh, nguon=_("Mặc định"))

	return {
		code: frappe._dict(kiem=1, ty_le_lai=flt(rieng[code]), nguon=_("Mặt hàng - khách"))
		if code in rieng
		else chung
		for code in item_codes
	}


@frappe.whitelist()
def co_quyen_sua_ty_le_lai(vai_tro=None):
	"""Người dùng hiện tại có được sửa % lãi không. `vai_tro` mặc định đọc từ cài đặt."""
	vai_tro = vai_tro or cau_hinh().vai_tro_sua_ty_le_lai or "System Manager"
	return vai_tro in frappe.get_roles()


# --- Kiểm quyền khi lưu ------------------------------------------------------


def kiem_selling_settings(doc):
	"""Gọi từ `SellingSettings.validate`. Quyền xét theo vai trò TRƯỚC khi sửa, để không ai
	tự gán vai trò cho mình rồi sửa luôn."""
	truoc = doc.get_doc_before_save()
	if not truoc:
		return
	doi = [f for f in TRUONG_CAI_DAT if _khac(truoc.get(f), doc.get(f))]
	if doi and not co_quyen_sua_ty_le_lai(truoc.get("vai_tro_sua_ty_le_lai")):
		_tu_choi(doc, doi)
	if flt(doc.get("ty_le_lai_mac_dinh")) < 0:
		frappe.throw(_("% lãi mặc định không được âm"))
	if cint(doc.get("bat_kiem_gia_ban")):
		_canh_bao_tu_cap_nhat_gia()


def _canh_bao_tu_cap_nhat_gia():
	"""Stock Settings tự thêm/ghi đè Item Price khi gõ giá trên chứng từ (get_item_details.
	insert_item_price): giá mua làm giá gốc có thể bị đổi ngầm (quyết định P7)."""
	s = frappe.get_cached_doc("Stock Settings")
	if cint(s.get("auto_insert_price_list_rate_if_missing")) or cint(
		s.get("update_existing_price_list_rate")
	):
		frappe.msgprint(
			_(
				"Stock Settings đang bật tự thêm/cập nhật giá vào bảng giá khi lập chứng từ. Giá mua dùng làm giá gốc có thể bị đổi ngầm — nên tắt hai ô Auto Insert Price List Rate If Missing và Update Existing Price List Rate."
			),
			title=_("Kiểm giá bán"),
			indicator="orange",
		)


def kiem_khach(doc):
	"""Gọi từ `Customer.validate`. Khách mới chỉ cần quyền khi khác giá trị mặc định."""
	truoc = doc.get_doc_before_save()
	goc = truoc.as_dict() if truoc else MAC_DINH_KHACH
	doi = [f for f in TRUONG_KHACH if _khac(goc.get(f), doc.get(f))]
	if doi and not co_quyen_sua_ty_le_lai():
		_tu_choi(doc, doi)
	if flt(doc.get("ty_le_lai")) < 0:
		frappe.throw(_("% lãi không được âm"))


def kiem_mat_hang(doc):
	"""Gọi từ `Item.validate`: % riêng theo khách trong bảng Item Customer Detail."""
	# Khách có % lãi riêng chỉ được một dòng: ERPNext lấy mã hàng của khách từ dòng ĐẦU TIÊN
	# của khách (get_item_details) hoặc dòng CUỐI (Blanket Order); thêm dòng chỉ có % sẽ làm
	# mất mã hàng. Ghi % vào chính dòng mã hàng của khách.
	so_dong = {}
	for d in doc.get("customer_items", []):
		if d.customer_name:
			so_dong[d.customer_name] = so_dong.get(d.customer_name, 0) + 1
	for d in doc.get("customer_items", []):
		if cint(d.get("ty_le_lai_rieng")):
			if not d.customer_name:
				frappe.throw(_("Dòng {0} bảng mã hàng theo khách: % lãi riêng cần chọn khách").format(d.idx))
			if so_dong[d.customer_name] > 1:
				frappe.throw(
					_(
						"Khách {0} có nhiều dòng trong bảng mã hàng theo khách. Ghi % lãi riêng vào chính dòng mã hàng của khách (mỗi khách một dòng)."
					).format(d.customer_name)
				)
			if flt(d.get("ty_le_lai")) < 0:
				frappe.throw(_("Dòng {0} bảng mã hàng theo khách: % lãi không được âm").format(d.idx))
		elif not d.ref_code:
			frappe.throw(
				_("Dòng {0} bảng mã hàng theo khách: nhập mã hàng của khách hoặc % lãi riêng").format(d.idx)
			)

	truoc = doc.get_doc_before_save()
	if _ty_le_theo_khach(truoc) != _ty_le_theo_khach(doc) and not co_quyen_sua_ty_le_lai():
		_tu_choi(doc, ["customer_items.ty_le_lai"])


def _ty_le_theo_khach(doc):
	if not doc:
		return set()
	return {
		(d.customer_name, flt(d.get("ty_le_lai"), 6))
		for d in doc.get("customer_items", [])
		if cint(d.get("ty_le_lai_rieng"))
	}


def _khac(a, b):
	if isinstance(a, int | float) or isinstance(b, int | float):
		return flt(a, 6) != flt(b, 6)
	return (a or "") != (b or "")


def _tu_choi(doc, fields):
	meta = frappe.get_meta(doc.doctype)
	nhan = ", ".join(_(meta.get_label(f)) if "." not in f else _("% lãi theo khách") for f in fields)
	frappe.throw(
		_("Bạn không có quyền sửa {0}. Chỉ vai trò {1} được sửa % lãi.").format(
			nhan, frappe.bold(cau_hinh().vai_tro_sua_ty_le_lai or "System Manager")
		),
		frappe.PermissionError,
	)
