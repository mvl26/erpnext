# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Ghép dòng Hóa đơn mua với dòng Phiếu nhập mua (YC5, spec 6.3.2).

- Dòng đã có `pr_detail` (hóa đơn lập bằng nút Tạo từ Phiếu nhập): giữ nguyên. Nếu Phiếu nhập
  đó đã bị hủy và có bản sửa đã Nộp (nhánh b1), chuyển sang dòng tương ứng của bản sửa.
- Dòng chỉ có `po_detail` (hóa đơn lập từ Đơn mua hàng): tìm dòng Phiếu nhập có
  `purchase_order_item` trùng. Một dòng PO nhận qua nhiều Phiếu nhập thì tách dòng hóa đơn theo
  số chưa lập hóa đơn của từng phiếu. Từ hai cách ghép trở lên: để người dùng ghép tay.

Kết quả ghép của từng dòng nằm ở `row.flags.ghep_pr` để bước đối soát đọc lại trong cùng lần lưu.
"""

import frappe
from frappe import _
from frappe.query_builder.functions import Abs, Sum
from frappe.utils import cint, flt

DA_GHEP = "da_ghep"
KHONG_CO = "khong_co"
MO_HO = "mo_ho"
DA_LAP_DU = "da_lap_du"


def con_cho_lap_hoa_don(pr_details, tru_hoa_don=None):
	"""{dòng Phiếu nhập: số lượng theo ĐVT kho đã nhận nhưng chưa lập hóa đơn}.

	Cùng cách tính với nút Tạo → Hóa đơn mua của ERPNext (`purchase_receipt.make_purchase_invoice`):
	số nhận (hoặc cả số bị từ chối nếu Thiết lập mua hàng cho lập hóa đơn phần từ chối) trừ phần đã
	lập hóa đơn Đã Nộp và phần trả lại. Khác ERPNext ở chỗ tính theo ĐVT kho và bỏ qua hóa đơn
	`tru_hoa_don` (hóa đơn đang đối soát).
	"""
	ten = list({n for n in pr_details if n})
	if not ten:
		return {}

	dong = frappe.get_all(
		"Purchase Receipt Item",
		filters={"name": ("in", ten)},
		fields=["name", "stock_qty", "received_qty", "rejected_qty", "conversion_factor"],
	)

	pii = frappe.qb.DocType("Purchase Invoice Item")
	q = (
		frappe.qb.from_(pii)
		.select(pii.pr_detail, Sum(pii.stock_qty))
		.where(pii.pr_detail.isin(ten))
		.where(pii.docstatus == 1)
		.groupby(pii.pr_detail)
	)
	if tru_hoa_don:
		q = q.where(pii.parent != tru_hoa_don)
	da_lap = dict(q.run())

	pri = frappe.qb.DocType("Purchase Receipt Item")
	pr = frappe.qb.DocType("Purchase Receipt")
	da_tra = dict(
		frappe.qb.from_(pri)
		.join(pr)
		.on(pr.name == pri.parent)
		.select(pri.purchase_receipt_item, Sum(Abs(pri.stock_qty)))
		.where(pri.purchase_receipt_item.isin(ten))
		.where(pr.docstatus == 1)
		.where(pr.is_return == 1)
		.groupby(pri.purchase_receipt_item)
		.run()
	)

	lap_ca_tu_choi = cint(
		frappe.db.get_single_value("Buying Settings", "bill_for_rejected_quantity_in_purchase_invoice")
	)
	ket_qua = {}
	for r in dong:
		cf = flt(r.conversion_factor) or 1
		if lap_ca_tu_choi:
			con = flt(r.received_qty) * cf - flt(da_lap.get(r.name))
		else:
			con = flt(r.stock_qty) - flt(da_lap.get(r.name))
			tra = flt(da_tra.get(r.name))
			if tra and flt(r.rejected_qty):
				tra -= flt(r.rejected_qty) * cf
			con -= max(tra, 0)
		ket_qua[r.name] = max(con, 0)
	return ket_qua


def _sl_kho(d):
	"""Số lượng theo ĐVT kho. Tính lại từ `qty`: ở `before_validate`, `stock_qty` vẫn là giá trị
	cũ nếu người dùng vừa sửa số lượng (ERPNext tính lại sau, trong controller)."""
	return flt(flt(d.qty) * (flt(d.conversion_factor) or 1), d.precision("stock_qty"))


def _dong_phieu_nhap(filters):
	pri = frappe.qb.DocType("Purchase Receipt Item")
	pr = frappe.qb.DocType("Purchase Receipt")
	q = (
		frappe.qb.from_(pri)
		.join(pr)
		.on(pr.name == pri.parent)
		.select(
			pri.name,
			pri.parent,
			pri.idx,
			pri.item_code,
			pri.purchase_order_item,
			pr.docstatus,
			pr.is_return,
		)
		.orderby(pr.posting_date)
		.orderby(pr.posting_time)
		.orderby(pr.creation)
		.orderby(pri.idx)
	)
	for field, value in filters.items():
		q = q.where(pri[field].isin(value) if isinstance(value, list | tuple) else pri[field] == value)
	return q.run(as_dict=True)


def _phieu_sua(pr_name):
	"""Bản sửa đã Nộp gần nhất của một Phiếu nhập đã hủy, đi theo chuỗi `amended_from`."""
	ten = pr_name
	for _i in range(20):
		moi = frappe.db.get_value(
			"Purchase Receipt",
			{"amended_from": ten},
			["name", "docstatus"],
			as_dict=True,
			order_by="creation desc",
		)
		if not moi or moi.docstatus == 0:
			return None
		if moi.docstatus == 1:
			return moi.name
		ten = moi.name
	return None


def _dong_thay_the(d, dong_cu):
	"""Dòng của bản sửa ứng với `dong_cu` (dòng Phiếu nhập đã hủy), hoặc None nếu không rõ."""
	phieu_moi = _phieu_sua(dong_cu.parent)
	if not phieu_moi:
		return None
	dong_moi = _dong_phieu_nhap({"parent": phieu_moi})
	if dong_cu.purchase_order_item:
		ung_vien = [r for r in dong_moi if r.purchase_order_item == dong_cu.purchase_order_item]
	else:
		ung_vien = [r for r in dong_moi if r.item_code == d.item_code]
	if len(ung_vien) > 1:
		ung_vien = [r for r in ung_vien if r.idx == dong_cu.idx]
	return ung_vien[0] if len(ung_vien) == 1 else None


def _chan_khi_bat_buoc_phieu_nhap(doc):
	"""Production bật "Purchase Receipt Required": dòng hàng kho không ghép được sẽ bị ERPNext chặn
	bằng câu "Purchase Receipt Required for item", không nói vì sao. Báo rõ lý do trước."""
	if frappe.db.get_single_value("Buying Settings", "pr_required") != "Yes":
		return
	if frappe.get_cached_value(
		"Supplier", doc.supplier, "allow_purchase_invoice_creation_without_purchase_receipt"
	):
		return
	loi = []
	for d in doc.items:
		ghep = d.flags.get("ghep_pr") or (KHONG_CO,)
		if ghep[0] not in (MO_HO, DA_LAP_DU):
			continue
		if not frappe.get_cached_value("Item", d.item_code, "is_stock_item"):
			continue
		if ghep[0] == MO_HO:
			loi.append(
				_("Dòng {0} ({1}): nhiều Phiếu nhập có thể ghép ({2}).").format(
					d.idx, d.item_code, ", ".join(ghep[1])
				)
			)
		else:
			loi.append(
				_("Dòng {0} ({1}): mọi Phiếu nhập của dòng đơn mua đã có hóa đơn ({2}).").format(
					d.idx, d.item_code, ", ".join(ghep[1])
				)
			)
	if loi:
		frappe.throw(
			"<br>".join(loi)
			+ "<br><br>"
			+ _("Xóa dòng rồi dùng Lấy mặt hàng từ → Phiếu nhập mua để chọn đúng phiếu."),
			title=_("Không ghép được Phiếu nhập mua"),
		)


def ghep(doc):
	"""`before_validate` của Hóa đơn mua (chỉ gọi khi hóa đơn thuộc phạm vi đối soát).

	Chạy trước controller để ERPNext tính lại thành tiền cho dòng vừa tách và kiểm
	`pr_required` trên dòng đã gắn Phiếu nhập.
	"""
	thong_bao = []
	da_phan = {}  # dòng Phiếu nhập -> số lượng (ĐVT kho) đã gắn cho các dòng hóa đơn này

	co_pr = [d for d in doc.items if d.pr_detail]
	cu = {r.name: r for r in _dong_phieu_nhap({"name": [d.pr_detail for d in co_pr]})} if co_pr else {}
	for d in co_pr:
		dong = cu.get(d.pr_detail)
		if dong and dong.docstatus == 1:
			d.flags.ghep_pr = (DA_GHEP,)
		elif dong and dong.docstatus == 2:
			# Chưa có bản sửa thì giữ nguyên: Frappe không cho lưu chứng từ trỏ vào phiếu đã hủy
			# (CancelledLinkError) cho tới khi Kho Nộp bản sửa.
			moi = _dong_thay_the(d, dong)
			if moi:
				d.purchase_receipt, d.pr_detail = moi.parent, moi.name
				thong_bao.append(
					_("Dòng {0}: chuyển từ Phiếu nhập đã hủy {1} sang bản sửa {2}.").format(
						d.idx, dong.parent, moi.parent
					)
				)
			d.flags.ghep_pr = (DA_GHEP,)
		else:
			d.flags.ghep_pr = (KHONG_CO,)
		if d.flags.ghep_pr[0] == DA_GHEP:
			da_phan[d.pr_detail] = da_phan.get(d.pr_detail, 0) + _sl_kho(d)

	chi_co_po = [d for d in doc.items if not d.pr_detail and d.po_detail]
	ung_vien = {}
	if chi_co_po:
		for r in _dong_phieu_nhap({"purchase_order_item": [d.po_detail for d in chi_co_po]}):
			if r.docstatus == 1 and not r.is_return:
				ung_vien.setdefault(r.purchase_order_item, []).append(r)
	con = con_cho_lap_hoa_don([r.name for rows in ung_vien.values() for r in rows], tru_hoa_don=doc.name)

	tach = {}  # dòng hóa đơn gốc -> các dòng mới tách ra
	for d in chi_co_po:
		cac_dong = ung_vien.get(d.po_detail) or []
		if d.purchase_receipt:
			# Dòng đã ghi số Phiếu nhập (ví dụ nhập qua API) thì chỉ ghép trong phiếu đó.
			cac_dong = [r for r in cac_dong if r.parent == d.purchase_receipt]
		if not cac_dong:
			d.flags.ghep_pr = (KHONG_CO,)
			continue
		con_lai = [(r, flt(con.get(r.name)) - flt(da_phan.get(r.name))) for r in cac_dong]
		con_lai = [(r, q) for r, q in con_lai if flt(q, d.precision("stock_qty")) > 0]
		if not con_lai:
			d.flags.ghep_pr = (DA_LAP_DU, [r.parent for r in cac_dong])
			continue

		can = _sl_kho(d)
		if len(con_lai) == 1:
			chon = con_lai
		elif not flt(sum(q for _r, q in con_lai) - can, d.precision("stock_qty")):
			chon = con_lai  # đúng tổng số còn lại của các phiếu: tách theo từng phiếu
		else:
			khop = [(r, q) for r, q in con_lai if not flt(q - can, d.precision("stock_qty"))]
			if len(khop) != 1:
				d.flags.ghep_pr = (MO_HO, list(dict.fromkeys(r.parent for r, _q in con_lai)))
				continue
			chon = khop

		if len(chon) == 1:
			r = chon[0][0]
			d.purchase_receipt, d.pr_detail = r.parent, r.name
			d.flags.ghep_pr = (DA_GHEP,)
			da_phan[r.name] = da_phan.get(r.name, 0) + can
			thong_bao.append(_("Dòng {0}: ghép với Phiếu nhập {1}.").format(d.idx, r.parent))
			continue

		cf = flt(d.conversion_factor) or 1
		moi = []
		for k, (r, q) in enumerate(chon):
			row = d if k == 0 else doc.append("items", d.as_dict(no_default_fields=True))
			row.qty = flt(q / cf, row.precision("qty"))
			row.stock_qty = q
			row.purchase_receipt, row.pr_detail = r.parent, r.name
			row.flags.ghep_pr = (DA_GHEP,)
			da_phan[r.name] = da_phan.get(r.name, 0) + q
			if k:
				moi.append(row)
		tach[id(d)] = moi
		thong_bao.append(
			_("Dòng {0}: tách theo {1} Phiếu nhập ({2}).").format(
				d.idx, len(chon), ", ".join(r.parent for r, _q in chon)
			)
		)

	for d in doc.items:
		if not d.flags.get("ghep_pr"):
			d.flags.ghep_pr = (DA_GHEP,) if d.pr_detail else (KHONG_CO,)

	if tach:
		# Dòng tách ra đứng ngay sau dòng gốc, không dồn xuống cuối bảng.
		moi = {id(r) for rows in tach.values() for r in rows}
		thu_tu = []
		for d in doc.items:
			if id(d) in moi:
				continue
			thu_tu.append(d)
			thu_tu.extend(tach.get(id(d), ()))
		doc.items = thu_tu
		for i, d in enumerate(doc.items, 1):
			d.idx = i

	_chan_khi_bat_buoc_phieu_nhap(doc)

	if thong_bao and not doc.flags.get("doi_soat_tu_phieu_nhap"):
		frappe.msgprint(
			"<br>".join(thong_bao), title=_("Ghép dòng với Phiếu nhập mua"), indicator="blue", alert=False
		)
