"""Kiểm trước khi bật đối soát Phiếu nhập ↔ Hóa đơn mua (YC5) trên production — CHỈ ĐỌC.

Gom dữ liệu để chọn giá trị Buying Settings (spec 2026-10-21 mục 16.4): ô cài đặt ERPNext ảnh
hưởng tới luồng, hộp thư gửi đi, tài khoản làm tròn, vai trò ứng viên cho Kế toán trưởng / Ban
Điều hành kèm người đang giữ, người nhận NTF-16 → 19, NCC ứng viên bật thử. Không chọn thay
người dùng: in số liệu và lý do, người có quyền quyết định. Mục 0 kiểm múi giờ, dùng chung cho
mọi đợt.

	cd ~/frappe-bench/sites
	../env/bin/python ../apps/erpnext/scripts/kiem_truoc_trien_khai_yc5.py --site miyano [--ngay 90]

Phiên DB đặt READ ONLY ngay sau khi kết nối: lỡ có lệnh ghi thì MariaDB từ chối, không ghi được.
Chạy được trước khi migrate (lúc đó các ô của YC5 báo "chưa có").
"""

import argparse
import os

import frappe
from frappe.utils import add_days, cint, nowdate

CAN_XEM = "[CẦN XEM]"
DAT = "[ĐẠT]"
MUI_GIO_VN = "Asia/Ho_Chi_Minh"


def tieu_de(text):
	print(f"\n=== {text} ===")


def bang(hang, cot):
	"""In bảng chữ đều cột; `hang` là list dict, `cot` là [(khóa, tiêu đề)]."""
	if not hang:
		print("  (không có)")
		return
	rong = {k: max(len(t), *(len(str(h.get(k, ""))) for h in hang)) for k, t in cot}
	print("  " + "  ".join(t.ljust(rong[k]) for k, t in cot))
	for h in hang:
		print("  " + "  ".join(str(h.get(k, "")).ljust(rong[k]) for k, _t in cot))


def quyen(doctype, loai):
	"""Vai trò có quyền `loai` (submit, create...) ở permlevel 0. Có Custom DocPerm thì Frappe
	bỏ hẳn DocPerm chuẩn của DocType đó."""
	nguon = "Custom DocPerm" if frappe.db.exists("Custom DocPerm", {"parent": doctype}) else "DocPerm"
	return set(frappe.get_all(nguon, filters={"parent": doctype, loai: 1, "permlevel": 0}, pluck="role"))


def nguoi_giu(role):
	nguoi = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent")
	return frappe.get_all(
		"User",
		filters=[
			["name", "in", nguoi or [""]],
			["name", "not in", ["Administrator", "Guest"]],
			["enabled", "=", 1],
			["user_type", "=", "System User"],
		],
		pluck="name",
		order_by="name",
	)


def kiem_mui_gio():
	"""Site test cài ngày 20/10/2026 bị chọn nhầm Etc/GMT+7 (= UTC-7): "hôm nay" của hệ thống chậm
	14 tiếng, lệch ngày chứng từ, hạn nhắc và giờ chạy việc theo lịch của mọi đợt."""
	tieu_de("0. Múi giờ (ngày hôm nay của chứng từ, hạn nhắc, giờ chạy việc theo lịch)")
	he_thong = frappe.db.get_single_value("System Settings", "time_zone")
	print(f"  {DAT if he_thong == MUI_GIO_VN else CAN_XEM:10} System Settings · Time Zone: {he_thong}")
	if he_thong != MUI_GIO_VN:
		print(
			f"             Nên là {MUI_GIO_VN}. Etc/GMT+7 là UTC-7 (ký hiệu POSIX đảo dấu), chậm giờ Việt"
			" Nam 14 tiếng. Giờ đã lưu theo múi giờ cũ không tự dời khi đổi: quyết định trước khi đổi."
		)
	nguoi_dung = frappe.db.sql(
		"""select ifnull(time_zone, '') as mui_gio, count(*) as so from tabUser
		where enabled = 1 group by mui_gio""",
		as_dict=True,
	)
	for h in nguoi_dung:
		h.danh_dau = DAT if h.mui_gio in ("", MUI_GIO_VN) else CAN_XEM
		h.mui_gio = h.mui_gio or "(theo hệ thống)"
	bang(nguoi_dung, [("danh_dau", ""), ("mui_gio", "Múi giờ người dùng"), ("so", "Số người")])


def kiem_cai_dat():
	tieu_de("1. Ô cài đặt ERPNext ảnh hưởng tới đối soát")
	bs = frappe._dict(frappe.db.get_singles_dict("Buying Settings", cast=True))
	acs = frappe._dict(frappe.db.get_singles_dict("Accounts Settings", cast=True))
	for nhan, gia_tri, tot, ghi_chu in (
		(
			"Buying Settings · Set Landed Cost Based on Purchase Invoice Rate",
			cint(bs.set_landed_cost_based_on_purchase_invoice_rate),
			0,
			"Bật thì ERPNext sửa giá trị kho theo giá hóa đơn thay vì chặn hóa đơn vượt giá trị Phiếu"
			" nhập (lớp chặn (3)). Nên để TẮT.",
		),
		(
			"Buying Settings · Bill for Rejected Quantity in Purchase Invoice",
			cint(bs.bill_for_rejected_quantity_in_purchase_invoice),
			None,
			"Bật (mặc định ERPNext): hóa đơn được tính cả số bị từ chối; ERPNext không chặn 'Cannot"
			" overbill' lúc lưu. Không ảnh hưởng đối soát (đối soát so với số đã nhận).",
		),
		(
			"Buying Settings · Purchase Receipt Required",
			bs.pr_required or "",
			None,
			"'Yes': mọi hóa đơn phải có Phiếu nhập, trừ NCC được miễn (mục 5).",
		),
		(
			"Buying Settings · Maintain Same Rate Throughout the Purchase Cycle",
			f"{cint(bs.maintain_same_rate)} / {bs.maintain_same_rate_action or ''}",
			None,
			"Bật + 'Stop' thì ERPNext chặn hóa đơn khác giá Đơn mua trước cả đối soát.",
		),
		(
			"Accounts Settings · Over Billing Allowance (%)",
			acs.over_billing_allowance or 0,
			None,
			"YC5 không cần đổi ô này (D3-5).",
		),
		(
			"Accounts Settings · Round Tax Amount Row-wise",
			cint(acs.round_row_wise_tax),
			None,
			"Đối soát tính thuế kỳ vọng theo đúng ô này.",
		),
	):
		danh_dau = "" if tot is None else (DAT if gia_tri == tot else CAN_XEM)
		print(f"  {danh_dau:10} {nhan}: {gia_tri}\n             {ghi_chu}")

	tieu_de("2. Hộp thư gửi đi (email giao việc ĐNTT, email nhắc Kế toán trưởng, NTF-16 → 19)")
	hop_thu = frappe.get_all(
		"Email Account",
		filters={"enable_outgoing": 1},
		fields=["name", "email_id", "default_outgoing"],
		order_by="default_outgoing desc, name",
	)
	if not any(cint(h.default_outgoing) for h in hop_thu):
		print(f"  {CAN_XEM} Không có hộp thư gửi đi mặc định: chỉ có thông báo chuông, không có email.")
	bang(hop_thu, [("name", "Hộp thư"), ("email_id", "Địa chỉ"), ("default_outgoing", "Mặc định")])

	tieu_de("3. Tài khoản làm tròn của công ty (thiếu thì Nộp hóa đơn mua lỗi)")
	cong_ty = frappe.get_all("Company", fields=["name", "round_off_account", "round_off_cost_center"])
	for c in cong_ty:
		c.danh_dau = DAT if c.round_off_account and c.round_off_cost_center else CAN_XEM
	bang(
		cong_ty,
		[
			("danh_dau", ""),
			("name", "Công ty"),
			("round_off_account", "TK làm tròn"),
			("round_off_cost_center", "TT chi phí"),
		],
	)


def kiem_truong_yc5():
	tieu_de("4. Cài đặt YC5 hiện tại")
	if not frappe.db.exists("Custom Field", {"dt": "Buying Settings", "fieldname": "bat_doi_soat_pr_pi"}):
		print("  Chưa có (site chưa migrate code YC5). Bình thường nếu chạy trước khi triển khai.")
		return
	bs = frappe._dict(frappe.db.get_singles_dict("Buying Settings", cast=True))
	for k in (
		"bat_doi_soat_pr_pi",
		"pham_vi_doi_soat",
		"tao_dntt_khi_nop_hoa_don",
		"vai_tro_ke_toan_truong",
		"vai_tro_ban_dieu_hanh",
		"nguoi_duyet_dntt",
		"so_ngay_nhac_lech",
	):
		print(f"  {k}: {bs.get(k)}")
	print("  NCC đang tích Áp đối soát:", frappe.get_all("Supplier", {"doi_soat_pr_pi": 1}, pluck="name"))


def kiem_vai_tro():
	tieu_de("5. Vai trò ứng viên cho Kế toán trưởng / Ban Điều hành")
	nop_hd = quyen("Purchase Invoice", "submit")
	tao_dntt = quyen("Payment Request", "create")
	ung_vien = sorted((nop_hd & tao_dntt) - {"System Manager", "Administrator"})
	print(
		"  Vai trò vừa Nộp được Hóa đơn mua vừa tạo được Yêu cầu thanh toán (spec D3-3: vai trò đang"
		" đối soát PR-PI và tạo Payment Request). Ít người giữ = sát chức danh hơn:"
	)
	hang = []
	for role in ung_vien:
		nguoi = nguoi_giu(role)
		hang.append(
			{
				"role": role,
				"so": len(nguoi),
				"nguoi": ", ".join(nguoi[:6]) + (" ..." if len(nguoi) > 6 else ""),
			}
		)
	hang.sort(key=lambda h: h["so"])
	bang(hang, [("role", "Vai trò"), ("so", "Số người"), ("nguoi", "Người giữ")])

	theo_ten = frappe.get_all(
		"Role",
		filters={"disabled": 0},
		or_filters=[
			["role_name", "like", f"%{t}%"]
			for t in ("Kế toán", "Ke toan", "Accounts Manager", "Giám đốc", "Điều hành", "Director", "CEO")
		],
		pluck="name",
	)
	khac = sorted(set(theo_ten) - set(ung_vien))
	if khac:
		print("\n  Vai trò khác có tên gợi chức danh (KHÔNG đủ quyền trên, chọn thì cần cấp thêm quyền):")
		bang(
			[{"role": r, "nguoi": ", ".join(nguoi_giu(r)[:6])} for r in khac],
			[("role", "Vai trò"), ("nguoi", "Người giữ")],
		)


def kiem_nguoi_nhan():
	from erpnext.setup import department_catalog
	from erpnext.supply_notification import resolver

	tieu_de("6. Người nhận NTF-16 → 19 (phòng Mua hàng, phòng Kho, theo hồ sơ Nhân viên)")
	cong_ty = frappe.defaults.get_global_default("company")
	for key, ten in ((department_catalog.PURCHASE, "Mua hàng"), (department_catalog.STOCK, "Kho")):
		phong = department_catalog.find_department(key, cong_ty)
		if not phong:
			print(f"  {CAN_XEM} Phòng {ten}: chưa có phòng ban (migrate sẽ tạo, nhưng chưa có ai nhận).")
			continue
		nguoi = sorted(resolver.users_in_departments([phong]))
		thieu = resolver.employees_without_user([phong])
		print(f"  {DAT if nguoi else CAN_XEM} Phòng {ten} ({phong}): {len(nguoi)} người nhận {nguoi}")
		if thieu:
			print(f"             Nhân viên chưa gắn tài khoản (không nhận được): {thieu}")


def kiem_ncc(so_ngay):
	tieu_de(f"7. NCC ứng viên bật thử ({so_ngay} ngày gần nhất, chứng từ đã Nộp)")
	tu_ngay = add_days(nowdate(), -so_ngay)
	co_mien = frappe.get_meta("Supplier").has_field(
		"allow_purchase_invoice_creation_without_purchase_receipt"
	)
	ncc = {}

	def gop(cot, rows):
		for supplier, so in rows:
			ncc.setdefault(supplier, frappe._dict(supplier=supplier))[cot] = so

	gop(
		"so_pr",
		frappe.db.sql(
			"""select supplier, count(name) from `tabPurchase Receipt`
			where docstatus = 1 and is_return = 0 and posting_date >= %s group by supplier""",
			tu_ngay,
		),
	)
	gop(
		"so_hd",
		frappe.db.sql(
			"""select supplier, count(name) from `tabPurchase Invoice`
			where docstatus = 1 and is_return = 0 and posting_date >= %s group by supplier""",
			tu_ngay,
		),
	)
	gop(
		"hd_tu_pr",
		frappe.db.sql(
			"""select pi.supplier, count(distinct pi.name) from `tabPurchase Invoice` pi
			join `tabPurchase Invoice Item` pii on pii.parent = pi.name
			where pi.docstatus = 1 and pi.is_return = 0 and pi.posting_date >= %s
				and ifnull(pii.purchase_receipt, '') != ''
			group by pi.supplier""",
			tu_ngay,
		),
	)
	# Hóa đơn có ít nhất một dòng khác giá Phiếu nhập (giá trước thuế, theo ĐVT kho): đây là các
	# hóa đơn mà đối soát sẽ báo Lệch.
	gop(
		"hd_lech_gia",
		frappe.db.sql(
			"""select pi.supplier, count(distinct pi.name) from `tabPurchase Invoice` pi
			join `tabPurchase Invoice Item` pii on pii.parent = pi.name
			join `tabPurchase Receipt Item` pri on pri.name = pii.pr_detail
			where pi.docstatus = 1 and pi.is_return = 0 and pi.posting_date >= %s
				and abs(pii.net_rate / if(pii.conversion_factor, pii.conversion_factor, 1)
					- pri.net_rate / if(pri.conversion_factor, pri.conversion_factor, 1)) >= 0.01
			group by pi.supplier""",
			tu_ngay,
		),
	)
	# Phiếu nhập được lập trong nhiều hóa đơn: NCC này cần ô Hóa đơn từng phần.
	gop(
		"pr_nhieu_hd",
		frappe.db.sql(
			"""select supplier, count(*) from (
				select pi.supplier, pii.purchase_receipt from `tabPurchase Invoice` pi
				join `tabPurchase Invoice Item` pii on pii.parent = pi.name
				where pi.docstatus = 1 and pi.is_return = 0 and pi.posting_date >= %s
					and ifnull(pii.purchase_receipt, '') != ''
				group by pi.supplier, pii.purchase_receipt having count(distinct pi.name) > 1
			) t group by supplier""",
			tu_ngay,
		),
	)
	gop(
		"pr_co_phi",
		frappe.db.sql(
			"""select pr.supplier, count(distinct pr.name) from `tabPurchase Receipt` pr
			join `tabPurchase Taxes and Charges` t on t.parent = pr.name and t.parenttype = 'Purchase Receipt'
			where pr.docstatus = 1 and pr.is_return = 0 and pr.posting_date >= %s and t.charge_type = 'Actual'
			group by pr.supplier""",
			tu_ngay,
		),
	)
	if co_mien:
		for s in frappe.get_all(
			"Supplier",
			filters={"name": ("in", list(ncc) or [""])},
			fields=["name", "allow_purchase_invoice_creation_without_purchase_receipt as mien"],
		):
			ncc[s.name].mien_pr = cint(s.mien)

	so_lieu = ("so_pr", "so_hd", "hd_tu_pr", "hd_lech_gia", "pr_nhieu_hd", "pr_co_phi")
	for h in ncc.values():
		for k in so_lieu:
			h.setdefault(k, 0)
	hang = sorted(ncc.values(), key=lambda h: (-h.hd_tu_pr, h.supplier))[:15]
	print(
		"  Xếp theo số hóa đơn lập từ Phiếu nhập. NCC hợp để thử: có đều hóa đơn từ Phiếu nhập (vài"
		" hóa đơn mỗi tháng), hàng hóa chứ không phải dịch vụ, Miễn PR = 0. Cột Lệch giá cho biết đối"
		" soát sẽ báo Lệch bao nhiêu hóa đơn nếu giữ cách làm cũ."
	)
	bang(
		hang,
		[
			("supplier", "NCC"),
			("so_pr", "Phiếu nhập"),
			("so_hd", "Hóa đơn"),
			("hd_tu_pr", "HĐ từ PR"),
			("hd_lech_gia", "HĐ lệch giá"),
			("pr_nhieu_hd", "PR nhiều HĐ"),
			("pr_co_phi", "PR có phí cố định"),
		]
		+ ([("mien_pr", "Miễn PR")] if co_mien else []),
	)


def main():
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--site", required=True)
	parser.add_argument("--ngay", type=int, default=90, help="số ngày gần nhất để thống kê NCC")
	args = parser.parse_args()

	frappe.init(site=args.site, sites_path=os.getcwd())
	frappe.connect()
	try:
		frappe.db.sql("SET SESSION TRANSACTION READ ONLY")
		frappe.db.rollback()  # giao dịch kế tiếp mới mang thuộc tính READ ONLY
		print(f"Site {args.site}, ngày {nowdate()} — chỉ đọc")
		kiem_mui_gio()
		kiem_cai_dat()
		kiem_truong_yc5()
		kiem_vai_tro()
		kiem_nguoi_nhan()
		kiem_ncc(args.ngay)
	finally:
		frappe.db.rollback()
		frappe.destroy()


if __name__ == "__main__":
	main()
