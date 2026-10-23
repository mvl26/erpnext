# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Hóa đơn mua cao hơn Phiếu nhập / Đơn mua hàng đi vào luồng đối soát (YC5, quyết định 23/10/2026).

ERPNext có hai lớp chặn "vượt hóa đơn":
- Lúc lưu: tiền dòng hóa đơn vượt thành tiền dòng Phiếu nhập (`validate_multiple_billing`, "Cannot
  overbill"), trừ khi Buying Settings bật "Bill for Rejected Quantity".
- Lúc Nộp: tổng đã lập hóa đơn vượt thành tiền dòng Đơn mua hàng (`check_overflow_with_allowance`,
  "This document is over limit by").
Hai lớp này chặn trước khi hóa đơn có Bảng chênh lệch, nên không gửi được NCC (b2), không duyệt
được ngoại lệ. Ô Over Billing Allowance của Accounts Settings thì áp cho cả hóa đơn bán.

Cách làm, chỉ cho Hóa đơn mua thuộc phạm vi đối soát, không sửa core: thay hai hàm đó trên CHÍNH
đối tượng hóa đơn đang lưu (thuộc tính của instance, không đổi class):
- Lúc lưu: bỏ kiểm vượt Phiếu nhập — đối soát 0 đồng đã bắt mọi khoản cao hơn và chặn Nộp.
- Lúc Nộp: bỏ kiểm vượt Đơn mua hàng CHỈ khi hóa đơn có ngoại lệ đã được duyệt.
ERPNext đổi tên hàm thì phần thay không còn tác dụng và chặn chuẩn quay lại (an toàn); test
`TestHoaDonCaoHonPhieuNhap` báo việc đó.

Lớp chặn thứ ba KHÔNG bỏ: lúc Nộp, tổng hóa đơn vượt giá trị dòng Phiếu nhập
(`purchase_receipt.update_billing_percentage`). Đó là chốt giữ đúng giá trị tồn kho (kho đã ghi
theo giá Phiếu nhập). `vuot_gia_tri_phieu_nhap` cho nút Duyệt ngoại lệ báo trước thay vì duyệt
xong mới bị chặn.
"""

import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import cint, flt


def bo_chan_vuot_phieu_nhap(doc):
	"""Gọi ở `before_validate`, khi hóa đơn thuộc phạm vi đối soát."""
	goc = doc.validate_multiple_billing

	def validate_multiple_billing(ref_dt, item_ref_dn, based_on):
		if ref_dt == "Purchase Receipt":
			return  # đối soát 0 đồng thay thế, xem docstring module
		return goc(ref_dt, item_ref_dn, based_on)

	doc.validate_multiple_billing = validate_multiple_billing


def cho_vuot_don_mua_khi_co_ngoai_le(doc):
	"""Gọi ở `before_submit`, khi hóa đơn có ngoại lệ đã được duyệt."""
	goc = doc.check_overflow_with_allowance

	def check_overflow_with_allowance(item, args):
		if "qty" in args["target_ref_field"]:
			return goc(item, args)
		frappe.msgprint(
			_(
				"Dòng {0} ({1}) vượt thành tiền Đơn mua hàng {2}; cho Nộp vì {3} đã duyệt ngoại lệ đối soát."
			).format(item.get("idx"), item.get("item_code"), item.get("parent"), doc.nguoi_duyet_ngoai_le),
			indicator="orange",
			alert=True,
		)

	doc.check_overflow_with_allowance = check_overflow_with_allowance


def vuot_gia_tri_phieu_nhap(doc):
	"""Dòng Phiếu nhập mà tổng đã lập hóa đơn (gồm hóa đơn này) vượt giá trị dòng quá mức ERPNext
	cho phép. ERPNext chặn việc này lúc Nộp (`purchase_receipt.update_billing_percentage`) để giữ
	đúng giá trị tồn kho, và không có chỗ gắn hook để bỏ qua cho riêng một hóa đơn — nên ngoại lệ
	không cứu được hóa đơn loại này: phải sửa Phiếu nhập theo giá đúng (b1) hoặc xin NCC hóa đơn
	điều chỉnh (b2). Trả về [(dòng hóa đơn, mặt hàng, % vượt)]."""
	from erpnext.controllers.status_updater import get_allowance_for

	if cint(frappe.db.get_single_value("Buying Settings", "set_landed_cost_based_on_purchase_invoice_rate")):
		return []  # ERPNext điều chỉnh giá trị kho theo giá hóa đơn thay vì chặn
	ten = list({d.pr_detail for d in doc.items if d.pr_detail})
	if not ten:
		return []

	dong_pr = {
		r.name: r
		for r in frappe.get_all(
			"Purchase Receipt Item",
			filters={"name": ("in", ten)},
			fields=["name", "item_code", "amount", "rejected_qty", "rate"],
		)
	}
	pii = frappe.qb.DocType("Purchase Invoice Item")
	da_lap = dict(
		frappe.qb.from_(pii)
		.select(pii.pr_detail, Sum(pii.amount))
		.where(pii.pr_detail.isin(ten))
		.where(pii.docstatus == 1)
		.where(pii.parent != doc.name)
		.groupby(pii.pr_detail)
		.run()
	)
	lap_ca_tu_choi = cint(
		frappe.db.get_single_value("Buying Settings", "bill_for_rejected_quantity_in_purchase_invoice")
	)

	ket_qua = []
	for ten_dong, r in dong_pr.items():
		gia_tri = flt(r.amount) + (flt(r.rejected_qty) * flt(r.rate) if lap_ca_tu_choi else 0)
		cac_dong = [d for d in doc.items if d.pr_detail == ten_dong]
		da_lap_moi = flt(da_lap.get(ten_dong)) + sum(flt(d.amount) for d in cac_dong)
		if not gia_tri or da_lap_moi <= gia_tri:
			continue
		phan_tram = flt(da_lap_moi / gia_tri, 2) * 100 - 100
		if phan_tram > get_allowance_for(r.item_code, {}, None, None, "amount")[0]:
			ket_qua.append((", ".join(str(d.idx) for d in cac_dong), r.item_code, phan_tram))
	return ket_qua
