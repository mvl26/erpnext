"""Chọn ô để xuất khi chứng từ không khai vị trí.

Thứ tự: hạn dùng gần nhất trước (FEFO), cùng hạn thì theo thu_tu_lay_hang.

Lô KHÔNG có hạn dùng xếp SAU CÙNG. `ifnull(han, '9999-12-31')` chứ không
phải `ifnull(han, '1900-01-01')`: "không biết hạn" khác hẳn "sắp hết hạn",
và đẩy nó lên đầu là ưu tiên xuất đúng những lô mình biết ít nhất.

Lệch khỏi brief (review điều phối, model mạnh hơn, sau khi bản đầu "xong"):
brief KHÔNG làm tròn `can` khi trừ dần qua các ứng viên — với số lượng lẻ
(vd 0.7 + 0.1, cần 0.8), `min(flt(u.so_luong), can)` rồi `can -= lay` để lại
phần dư nhị phân (`can` còn ~9e-17 thay vì đúng 0). Hệ quả kép: (1) nếu hết
ứng viên đúng lúc đó, `can > 0` sai lệch làm `frappe.throw` một phiếu xuất
HOÀN TOÀN hợp lệ ngay trên đường hook bình thường — đúng điều bắt buộc #2
cấm; (2) nếu còn ứng viên tiếp theo, vòng lặp không dừng đúng lúc và ghi
thêm một phần ~0 (dòng sổ vị trí rác). Làm tròn `can` về
`_DO_CHINH_XAC_SO_LUONG` chữ số thập phân sau mỗi lần trừ — cùng độ chính
xác đã dùng ở `vitri/lo.py` (`_DO_CHINH_XAC_SO_LUONG = 6`) — để sai số nhị
phân không vượt ngưỡng so sánh `<= 0` / `> 0`.

VÒNG SỬA 2 (review điều phối): ô `disabled` (Ngừng dùng) bị loại khỏi ứng
viên — ĐÚNG, giữ nguyên hành vi CHẶN (ô ngừng dùng nghĩa là không được lấy
hàng từ đó; hàng ở đó phải chuyển đi bằng phiếu chuyển ô — giai đoạn 4 —
trước đã; bất biến §3 không vỡ vì `tong_ton_vi_tri` vẫn cộng cả ô disabled
vào tổng sổ). Nhưng thông báo THIẾU HÀNG trước đây không phân biệt hai tình
huống khác hẳn nhau: (a) thật sự không đủ hàng trong kho, và (b) đủ hàng
nhưng phần thiếu đang kẹt ở (các) ô đã ngừng dùng — người vận hành đọc "Bin
đủ hàng" mà hệ thống báo "không đủ" sẽ đi tìm sai chỗ. Thêm truy vấn RIÊNG
(chỉ chạy khi sắp throw, không tốn phí ở đường thành công) gộp tồn theo ô ở
CÁC Ô ĐANG disabled cùng (kho, vat_tu[, so_lo]) — nếu > 0, đổi sang thông
báo nêu rõ ô nào, còn bao nhiêu, và việc cần làm (chuyển hàng ra khỏi ô
ngừng dùng, hoặc bật lại ô).
"""

import frappe
from frappe import _
from frappe.utils import flt

HAN_XA = "9999-12-31"
_DO_CHINH_XAC_SO_LUONG = 6  # khớp vitri/lo.py


def chon_o_xuat(kho, vat_tu, so_lo, so_luong: float) -> list[dict]:
	"""Chọn các ô để lấy đủ `so_luong` (số dương). Không đủ → throw.

	`so_lo` có giá trị thì chỉ lấy đúng lô đó; None thì lấy mọi lô theo FEFO.
	"""
	can = flt(so_luong, _DO_CHINH_XAC_SO_LUONG)
	if can <= 0:
		return []

	dieu_kien = "and ifnull(lb.so_lo,'') = %(so_lo)s" if so_lo else ""
	ung_vien = frappe.db.sql(
		f"""
		select lb.o, lb.so_lo, lb.so_luong
		from `tabLocation Balance` lb
		left join `tabBatch` b on b.name = lb.so_lo
		join `tabStorage Location` sl on sl.name = lb.o
		where lb.kho = %(kho)s and lb.vat_tu = %(vat_tu)s and lb.so_luong > 0
		      and ifnull(sl.disabled, 0) = 0
		      {dieu_kien}
		order by ifnull(b.expiry_date, %(han_xa)s) asc,
		         ifnull(sl.thu_tu_lay_hang, 0) asc,
		         lb.o asc
		""",
		{"kho": kho, "vat_tu": vat_tu, "so_lo": so_lo or "", "han_xa": HAN_XA},
		as_dict=True,
	)

	ket_qua = []
	for u in ung_vien:
		if can <= 0:
			break
		lay = min(flt(u.so_luong), can)
		ket_qua.append({"o": u.o, "so_luong": lay})
		can = flt(can - lay, _DO_CHINH_XAC_SO_LUONG)

	if can > 0:
		co = flt(flt(so_luong, _DO_CHINH_XAC_SO_LUONG) - can, _DO_CHINH_XAC_SO_LUONG)
		ten_lo = f" (lô {so_lo})" if so_lo else ""

		o_ngung_dung = frappe.db.sql(
			f"""
			select lb.o, lb.so_luong
			from `tabLocation Balance` lb
			join `tabStorage Location` sl on sl.name = lb.o
			where lb.kho = %(kho)s and lb.vat_tu = %(vat_tu)s and lb.so_luong > 0
			      and ifnull(sl.disabled, 0) = 1
			      {dieu_kien}
			order by lb.o asc
			""",
			{"kho": kho, "vat_tu": vat_tu, "so_lo": so_lo or ""},
			as_dict=True,
		)

		if o_ngung_dung:
			ket_ngung_dung = ", ".join(f"{d.o} ({flt(d.so_luong)})" for d in o_ngung_dung)
			frappe.throw(
				_(
					"Không đủ hàng ở các ô đang dùng để xuất. Mặt hàng {0}{1} tại kho {2}: "
					"cần {3}, ô đang dùng chỉ có {4} (thiếu {5}), nhưng còn {6} nằm ở ô đã "
					"ngừng dùng: {7}. Chuyển hàng ra khỏi ô ngừng dùng hoặc bật lại ô đó rồi "
					"xuất lại."
				).format(
					vat_tu,
					ten_lo,
					kho,
					flt(so_luong),
					co,
					can,
					flt(sum(flt(d.so_luong) for d in o_ngung_dung), _DO_CHINH_XAC_SO_LUONG),
					ket_ngung_dung,
				)
			)

		frappe.throw(
			_("Không đủ hàng để xuất. Mặt hàng {0}{1} tại kho {2}: cần {3}, chỉ có {4}, thiếu {5}.").format(
				vat_tu,
				ten_lo,
				kho,
				flt(so_luong),
				co,
				can,
			)
		)

	return ket_qua
