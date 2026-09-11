"""Engine ghi sổ vị trí.

`Location Ledger Entry` là nguồn sự thật, chỉ ghi thêm. `Location Balance`
là bộ đệm dẫn xuất — mọi con số trong đó phải dựng lại được từ sổ, và
`dung_lai_ton_vi_tri()` là đường thoát khi nghi ngờ số liệu.

Không hàm nào ở đây kiểm tra tồn đủ hay không. Việc chặn nằm ở lớp trên
(hook và validate chứng từ) vì chỉ ở đó mới đủ ngữ cảnh để báo lỗi cho
người dùng đọc được.

`so_lo` LUÔN được lưu là chuỗi `''` cho hàng không quản lý lô — KHÔNG BAO
GIỜ là `NULL` (vòng sửa 1, Việc 2). MariaDB coi mỗi `NULL` là một giá trị
khác biệt với mọi `NULL` khác, nên chỉ riêng unique index (o, vat_tu, so_lo)
— patch `them_unique_location_balance` — sẽ KHÔNG chặn được dòng ma cho
hàng không lô nếu vẫn còn lưu NULL. Các câu SELECT dưới đây vẫn giữ
`ifnull(so_lo,'')` để phòng thủ (dữ liệu cũ hoặc ghi tay lỡ để NULL), nhưng
đường ghi (`ghi_dong_so`, `_cong_don_ton`, `dung_lai_ton_vi_tri`) không bao
giờ tự tạo NULL nữa.
"""

import frappe
from frappe.utils import flt, now_datetime


def _ten_dong_ton(o, vat_tu, so_lo):
	"""Tên bản ghi `Location Balance` khớp (o, vat_tu, so_lo), hoặc None."""
	ket_qua = frappe.db.sql(
		"""select name from `tabLocation Balance`
		   where o=%s and vat_tu=%s and ifnull(so_lo,'')=%s""",
		(o, vat_tu, so_lo or ""),
	)
	return ket_qua[0][0] if ket_qua else None


def ghi_dong_so(
	o, kho, vat_tu, so_lo, so_luong,
	chung_tu_type, chung_tu, chung_tu_row, sle,
	ngay, thoi_diem, company, da_huy=0,
) -> str:
	"""Ghi một dòng sổ vị trí và cập nhật bộ đệm tồn. Trả tên dòng sổ."""
	dong = frappe.get_doc({
		"doctype": "Location Ledger Entry",
		"ngay": ngay,
		"thoi_diem": thoi_diem,
		"kho": kho,
		"o": o,
		"vat_tu": vat_tu,
		"so_lo": so_lo or "",
		"so_luong": flt(so_luong),
		"chung_tu_type": chung_tu_type,
		"chung_tu": chung_tu,
		"chung_tu_row": chung_tu_row,
		"sle": sle,
		"da_huy": da_huy,
		"company": company,
	})
	# KHÔNG ignore_links ở đây (vòng sửa 1, Việc 4): Location Ledger Entry là
	# nguồn sự thật cho Task 5-10. Trước đây ignore_links=True tắt kiểm tra
	# khoá ngoại cho TOÀN BỘ doc — không chỉ so_lo/chung_tu mà cả o, kho,
	# vat_tu, company — nghĩa là một mã ô gõ sai hay một kho không tồn tại
	# có thể lọt thẳng vào sổ mà không ai biết. Chứng từ nguồn (o, kho,
	# vat_tu, company, so_lo, chung_tu) phải là bản ghi có thật trước khi
	# gọi hàm này; lớp gọi (Task 5-10) chịu trách nhiệm dựng dữ liệu thật
	# (lô lấy từ Serial and Batch Bundle, chứng từ là voucher thật).
	dong.insert(ignore_permissions=True)
	_cong_don_ton(o, kho, vat_tu, so_lo, flt(so_luong))
	return dong.name


def _cong_don_ton(o, kho, vat_tu, so_lo, delta):
	"""Cộng dồn tồn cho (o, vat_tu, so_lo) bằng MỘT câu SQL nguyên tử.

	(Vòng sửa 1, Việc 3.) Bản cũ đọc-rồi-ghi (SELECT tìm dòng, có thì
	UPDATE, không thì INSERT) — hai lệnh gọi `_cong_don_ton` gần như đồng
	thời cho CÙNG một khoá có thể cùng SELECT thấy "chưa có dòng" (đúng ngữ
	nghĩa transaction: mỗi bên chỉ thấy dữ liệu đã COMMIT của bên kia) rồi
	CÙNG INSERT — sinh 2 dòng `Location Balance` cho một khoá (dòng ma).
	Nếu lúc đó đã có unique index (Việc 1) mà vẫn đọc-rồi-ghi, INSERT thứ
	hai sẽ ném lỗi trùng khoá giữa chừng một giao dịch kho hợp lệ (vd giữa
	`Stock Ledger Entry.on_submit`) — kết cục tệ hơn dòng ma đang chữa.

	`INSERT ... ON DUPLICATE KEY UPDATE` gộp bước kiểm-tồn-tại và bước
	ghi vào MỘT statement; MariaDB tự khoá dòng chỉ mục ở tầng InnoDB cho
	statement đó, nên bên ghi sau (dù đang chờ do khoá) luôn thấy đúng bản
	ghi bên trước vừa tạo và CỘNG DỒN vào đó thay vì tạo dòng mới hay báo
	lỗi. Việc 1 (unique index) và Việc 3 (upsert này) PHẢI đi cùng nhau —
	upsert chỉ nguyên tử được khi có index đó.
	"""
	nguoi_dung = frappe.session.user or "Administrator"
	luc = now_datetime()
	frappe.db.sql(
		"""insert into `tabLocation Balance`
		   (name, o, kho, vat_tu, so_lo, so_luong, cap_nhat_luc,
		    creation, modified, owner, modified_by, docstatus, idx)
		   values (%(name)s, %(o)s, %(kho)s, %(vat_tu)s, %(so_lo)s, %(delta)s,
		           %(luc)s, %(luc)s, %(luc)s, %(nguoi_dung)s, %(nguoi_dung)s, 0, 0)
		   on duplicate key update
		       so_luong = so_luong + values(so_luong),
		       cap_nhat_luc = values(cap_nhat_luc),
		       modified = values(modified),
		       modified_by = values(modified_by)""",
		{
			"name": frappe.generate_hash(length=10),
			"o": o,
			"kho": kho,
			"vat_tu": vat_tu,
			"so_lo": so_lo or "",
			"delta": delta,
			"luc": luc,
			"nguoi_dung": nguoi_dung,
		},
	)


def ton_o(o, vat_tu, so_lo) -> float:
	"""Tồn của một (ô, mặt hàng, lô). Đọc bộ đệm."""
	ten = _ten_dong_ton(o, vat_tu, so_lo)
	return flt(frappe.db.get_value("Location Balance", ten, "so_luong")) if ten else 0.0


def tong_ton_vi_tri(kho, vat_tu, so_lo) -> float:
	"""Tổng tồn của một (mặt hàng, lô) trên TẤT CẢ các ô của kho.

	Theo bất biến ở spec §3, con số này phải bằng Bin.actual_qty.
	"""
	ket_qua = frappe.db.sql(
		"""select sum(so_luong) from `tabLocation Balance`
		   where kho=%s and vat_tu=%s and ifnull(so_lo,'')=%s""",
		(kho, vat_tu, so_lo or ""),
	)
	return flt(ket_qua[0][0] or 0)


def dung_lai_ton_vi_tri(kho=None) -> int:
	"""Dựng lại toàn bộ Location Balance từ sổ. Trả số dòng đã dựng.

	Xoá sạch bộ đệm cũ của phạm vi rồi cộng lại từ đầu — dòng tồn không có
	dấu vết trong sổ sẽ biến mất, đó là điểm mấu chốt. Mỗi tổ hợp
	(o, vat_tu, ifnull(so_lo,'')) chỉ xuất hiện đúng một lần trong tập
	GROUP BY nên không tự đụng unique index (Việc 1) trong phạm vi hàm
	này — chỉ chưa hardening cho trường hợp rebuild chạy đồng thời với ghi
	sổ trực tiếp (xem báo cáo, mục "chưa kiểm chứng").
	"""
	dk_kho = "where kho=%s" if kho else ""
	tham_so = (kho,) if kho else ()

	frappe.db.sql(f"delete from `tabLocation Balance` {dk_kho}", tham_so)

	dong = frappe.db.sql(
		f"""select o, kho, vat_tu, ifnull(so_lo,'') as so_lo, sum(so_luong) as sl
		    from `tabLocation Ledger Entry` {dk_kho}
		    group by o, kho, vat_tu, ifnull(so_lo,'')""",
		tham_so, as_dict=True,
	)

	luc = now_datetime()
	for d in dong:
		frappe.get_doc({
			"doctype": "Location Balance",
			"o": d.o, "kho": d.kho, "vat_tu": d.vat_tu,
			"so_lo": d.so_lo, "so_luong": flt(d.sl), "cap_nhat_luc": luc,
		}).insert(ignore_permissions=True)

	return len(dong)
