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

TASK 4 (2026-09-11) — `disabled` THỪA KẾ XUỐNG CẢ NHÁNH: trước đây chỉ kiểm
cờ của CHÍNH ô lá. Người vận hành tắt cả một dãy để sửa kệ, hệ vẫn rút hàng
từ dãy đó và KHÔNG CÓ GÌ BÁO — đối soát §3 vẫn khớp vì tổng tồn không đổi.
Vị từ `_TO_TIEN_TAT` dưới đây thay luôn phép kiểm `sl.disabled` cũ ở CẢ HAI
truy vấn (xem chú thích của hằng: hai truy vấn dùng nó theo hai chiều ngược
nhau, sửa một chỗ quên chỗ kia thì hàng dưới nút đã tắt biến mất khỏi cả
hai — không được chọn, cũng không được nhắc tới).

TASK 5 (2026-09-11) — CHỈ ĐỊNH LẤY HÀNG TRONG MỘT NHÁNH: `pham_vi` nhận tên
một `Storage Location` bất kỳ cấp nào (khu/dãy/khoang/tầng/ô); `None` (mặc
định) = toàn kho, tức HÀNH VI CŨ — mọi nơi gọi không truyền `pham_vi` (kể cả
hook `Stock Ledger Entry.on_submit`, đường gọi phổ biến nhất) phải thấy kết
quả y hệt trước khi có tham số này. Lọc bằng `sl.lft between pv_lft and
pv_rgt` — chuẩn "nằm trong nhánh, gồm cả chính nút" của nested set.

BẪY GIỐNG `_TO_TIEN_TAT` NHƯNG LỆCH HƯỚNG, có đo (xem task-5-report.md và
`TestPhamViNgoaiCayKhongDuocGioiHanSai`): nếu `pham_vi` chỉ tên một bản ghi cũ
(tạo trước khi có cây, Task 2 — số lượng thay đổi theo site và theo tiến độ
hội tụ của `cay.py::dam_bao_cay_da_dung()`, KHÔNG cố định) mang
`lft = rgt = 0`, điều kiện trên thành `sl.lft between 0 and
0` = `sl.lft = 0` — khớp MỌI bản ghi 0/0 khác, không riêng nhánh của
`pham_vi`. `_TO_TIEN_TAT` lệch bằng cách LOẠI OAN (đóng băng cả kho khi so
hai bản ghi 0/0 TUỲ Ý); bẫy này lệch bằng cách GỘP OAN — lấy nhầm hàng của ô
không liên quan vào một lệnh gọi tưởng đã giới hạn phạm vi. Không vá được
bằng lại vị từ `<`/`>` chặt của `_TO_TIEN_TAT`: ở đó so hai bản ghi tuỳ ý,
còn ở đây so CHÍNH toạ độ của `pham_vi` — toạ độ đó mới là thứ hỏng. Chặn ở
nguồn: `pham_vi` ngoài cây (`lft`/`rgt` bằng 0) bị từ chối bằng
`frappe.throw` tiếng Việt, không được lặng lẽ trả sai.

`pham_vi` áp vào CẢ HAI truy vấn dưới đây, không chỉ truy vấn chọn ứng viên:
áp một chiều thì câu thông báo thiếu hàng sẽ đi mách hàng đang kẹt ở NHÁNH
KHÁC — nhánh mà lệnh gọi không hề hỏi tới — vừa gây nhiễu vừa sai ngữ nghĩa
của tham số (người gọi xin xuất trong dãy X thì không có lý do được nghe kể
về hàng ngừng dùng ở dãy Y).
"""


import frappe
from frappe import _
from frappe.utils import flt

HAN_XA = "9999-12-31"
_DO_CHINH_XAC_SO_LUONG = 6  # khớp vitri/lo.py

# Tổ-tiên-HOẶC-CHÍNH-NÓ đang bị tắt. Dùng ở HAI chỗ theo HAI CHIỀU ngược
# nhau: truy vấn chọn ứng viên phủ định nó (loại ô), truy vấn dựng thông báo
# khẳng định nó (tìm đúng những ô đó để nói hàng đang kẹt ở đâu). Sửa một
# chỗ quên chỗ kia thì hàng nằm dưới một nút cha bị tắt biến mất khỏi cả
# hai: không được chọn, mà cũng không được nhắc tới trong thông báo thiếu
# hàng — người dùng tắt cả dãy rồi nhận đúng câu "thiếu hàng" vô nghĩa.
#
# LỆCH KHỎI BRIEF, có đo (xem task-4-report.md). Brief viết
# `tt.lft <= sl.lft and tt.rgt >= sl.rgt` cho gọn — "đúng cho cả chính nút
# đó". Đúng với cây lành, nhưng các bản ghi cũ (tạo trước khi có cây, Task 2)
# mang `lft = rgt = 0` cho tới khi `cay.py::dam_bao_cay_da_dung()` hội tụ
# hết — số lượng thay đổi theo site và theo thời điểm, KHÔNG cố định — kể cả
# ô hệ thống `ZZZ-CHUA-XEP-<kho>` đang giữ toàn bộ tồn của kho thật. Hai bản
# ghi `0/0` bất kỳ đều thoả `0 <= 0 and 0 >= 0`, nên tắt MỘT ô cũ — một thao
# tác hoàn toàn hợp lệ, đúng thứ tính năng này sinh ra để làm — sẽ loại luôn mọi ô cũ
# khác VÀ ô CHUA-XEP khỏi ứng viên: `frappe.throw` giữa
# `Stock Ledger Entry.on_submit`, cuộn ngược mọi phiếu xuất của kho. Đúng
# thảm hoạ "một checkbox làm đứng cả kho" đã ghi ở
# `storage_location.py::kiem_tra_khong_doi_dang_o_chua_xep`, lần này validate
# không chặn được vì ô bị tắt là ô THƯỜNG.
#
# Nên: CHẶT ở phần tổ tiên (`<`/`>` — một nút không bao giờ là tổ tiên thật
# sự của chính nó) và khớp chính-nó bằng TÊN. Bản ghi ngoài cây vì thế hành
# xử đúng như phép kiểm `sl.disabled` cũ: không thừa kế cho ai, không nhận
# thừa kế từ ai. Khoá bằng
# `test_fefo_pham_vi.py::TestONgoaiCayKhongKeoNhauXuong`.
_TO_TIEN_TAT = """exists (
	select 1 from `tabStorage Location` tt
	where ifnull(tt.disabled, 0) = 1
	  and (tt.name = sl.name or (tt.lft < sl.lft and tt.rgt > sl.rgt))
)"""


def chon_o_xuat(kho, vat_tu, so_lo, so_luong: float, pham_vi: str | None = None) -> list[dict]:
	"""Chọn các ô để lấy đủ `so_luong` (số dương). Không đủ → throw.

	`so_lo` có giá trị thì chỉ lấy đúng lô đó; None thì lấy mọi lô theo FEFO.
	`pham_vi` có giá trị thì chỉ xét trong nhánh của `Storage Location` đó
	(bất kỳ cấp nào); `None` (mặc định) = toàn kho, hành vi cũ.
	"""
	can = flt(so_luong, _DO_CHINH_XAC_SO_LUONG)
	if can <= 0:
		return []

	dieu_kien = "and ifnull(lb.so_lo,'') = %(so_lo)s" if so_lo else ""
	tham_so = {"kho": kho, "vat_tu": vat_tu, "so_lo": so_lo or "", "han_xa": HAN_XA}
	loc_pham_vi = ""
	if pham_vi:
		moc = frappe.db.get_value("Storage Location", pham_vi, ["lft", "rgt"], as_dict=True)
		if not moc:
			frappe.throw(_("Vị trí {0} không tồn tại.").format(pham_vi))
		if not moc.lft or not moc.rgt:
			# Bẫy GIỐNG `_TO_TIEN_TAT` nhưng LỆCH HƯỚNG: các bản ghi cũ (tạo
			# trước Task 2, số lượng KHÔNG cố định — giảm dần khi cây hội tụ
			# qua `cay.py::dam_bao_cay_da_dung()`) mang lft = rgt = 0. Nếu cho
			# qua, điều kiện dưới thành `sl.lft between 0 and 0` = `sl.lft = 0`
			# — khớp MỌI bản ghi
			# 0/0 khác, không riêng nhánh của `pham_vi`: một `pham_vi` ngoài
			# cây sẽ GỘP OAN hàng của những ô hoàn toàn không liên quan (đã đo
			# thật, xem task-5-report.md và
			# test_fefo_pham_vi.py::TestPhamViNgoaiCayKhongDuocGioiHanSai).
			# Không vá được bằng vị từ `<`/`>` chặt như `_TO_TIEN_TAT` — ở đó
			# so hai bản ghi TUỲ Ý với nhau, còn ở đây so CHÍNH toạ độ của
			# `pham_vi`, và toạ độ đó mới là thứ hỏng. Chặn ở nguồn.
			frappe.throw(
				_(
					"Vị trí {0} chưa nằm trong cây vị trí (chưa có toạ độ trong cây) nên "
					"không dùng được để giới hạn phạm vi lấy hàng. Cập nhật lại vị trí này "
					"(lưu lại để cây tính lại toạ độ) trước khi dùng làm phạm vi."
				).format(pham_vi)
			)
		loc_pham_vi = "and sl.lft between %(pv_lft)s and %(pv_rgt)s"
		tham_so.update({"pv_lft": moc.lft, "pv_rgt": moc.rgt})

	ung_vien = frappe.db.sql(
		f"""
		select lb.o, lb.so_lo, lb.so_luong
		from `tabLocation Balance` lb
		left join `tabBatch` b on b.name = lb.so_lo
		join `tabStorage Location` sl on sl.name = lb.o
		where lb.kho = %(kho)s and lb.vat_tu = %(vat_tu)s and lb.so_luong > 0
		      and not {_TO_TIEN_TAT}
		      {dieu_kien}
		      {loc_pham_vi}
		order by ifnull(b.expiry_date, %(han_xa)s) asc,
		         ifnull(sl.thu_tu_lay_hang, 0) asc,
		         lb.o asc
		""",
		tham_so,
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
			      and {_TO_TIEN_TAT}
			      {dieu_kien}
			      {loc_pham_vi}
			order by lb.o asc
			""",
			tham_so,
			as_dict=True,
		)

		if o_ngung_dung:
			ket_ngung_dung = ", ".join(f"{d.o} ({flt(d.so_luong)})" for d in o_ngung_dung)
			# VÒNG SỬA 1 (review điều phối): câu khuyên phải chỉ được đường LÊN
			# TRÊN. Từ khi `disabled` thừa kế xuống cả nhánh, danh sách này gồm
			# cả những ô mà bản thân chúng đang BẬT — chỉ một nút cha bị tắt.
			# Câu cũ ("hoặc bật lại ô đó") đúng với đời trước, giờ dẫn vào ngõ
			# cụt: thủ kho mở đúng ô được nêu tên, thấy ô Ngừng dùng đang
			# trống, và không có manh mối nào dẫn về nút cha mới là thứ đang
			# chặn. KHÔNG nêu đích danh nút cha ở đây: `tt` không có phạm vi
			# ngoài `EXISTS` nên muốn lấy tên nó phải dán `_TO_TIEN_TAT` lần
			# thứ hai — nhân bản đúng khối logic mà cả task này dựng ra để
			# dùng chung. Cần nêu tên thì đó là một task riêng.
			#
			# RÀ TOÀN NHÁNH (mục A2): câu này throw TRƯỚC câu "thiếu hàng
			# trong phạm vi {0}" ở dưới (chỉ tới được khi `o_ngung_dung`
			# rỗng), nên khi CÓ `pham_vi` VÀ ô ngừng dùng NẰM TRONG phạm vi đó
			# (cả hai truy vấn — ứng viên và ô ngừng dùng — đều đã lọc theo
			# `pham_vi`), người dùng nhận đúng câu này, không phải câu có tên
			# phạm vi. `co`/`can` ở đây đã bị lọc theo `pham_vi` (xem
			# `loc_pham_vi` ở cả hai truy vấn phía trên) nên đọc như số liệu
			# TOÀN KHO nếu không nêu tên phạm vi — cùng lớp lỗi mà vòng sửa 1
			# đã xử lý cho câu "thiếu hàng trong phạm vi" ở dưới, bị bỏ sót ở
			# đây. Khi có `pham_vi`, nêu rõ số liệu chỉ tính TRONG phạm vi đó.
			if pham_vi:
				frappe.throw(
					_(
						"Không đủ hàng ở các ô đang dùng để xuất trong phạm vi {0}. Mặt hàng "
						"{1}{2} tại kho {3}: trong phạm vi này cần {4}, ô đang dùng chỉ có {5} "
						"(thiếu {6}), nhưng còn {7} nằm ở ô đã ngừng dùng trong phạm vi này: "
						"{8}. Chuyển hàng ra khỏi những ô đó, hoặc bật lại chúng rồi xuất lại. "
						"Nếu mở ra thấy ô vẫn đang bật thì một NÚT CHA của nó (khu/dãy/khoang/"
						"tầng) đang tắt — cả nhánh dưới nút đó ngừng dùng theo: lần ngược lên "
						"trên trong cây vị trí để tìm và bật nút cha đó. Kho có thể còn hàng ở "
						"các vị trí khác ngoài phạm vi này."
					).format(
						pham_vi,
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
				_(
					"Không đủ hàng ở các ô đang dùng để xuất. Mặt hàng {0}{1} tại kho {2}: "
					"cần {3}, ô đang dùng chỉ có {4} (thiếu {5}), nhưng còn {6} nằm ở ô đã "
					"ngừng dùng: {7}. Chuyển hàng ra khỏi những ô đó, hoặc bật lại chúng rồi "
					"xuất lại. Nếu mở ra thấy ô vẫn đang bật thì một NÚT CHA của nó "
					"(khu/dãy/khoang/tầng) đang tắt — cả nhánh dưới nút đó ngừng dùng theo: "
					"lần ngược lên trên trong cây vị trí để tìm và bật nút cha đó."
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

		if pham_vi:
			# VÒNG SỬA 1/5 (review điều phối): mặt trái của rủi ro brief cảnh
			# báo. Brief lo "mách sai nhánh" (đã chặn ở trên — `pham_vi` áp
			# vào cả hai truy vấn). Nhưng câu chung "tại kho {2}: cần {3}, chỉ
			# có {4}" đọc như số liệu TOÀN KHO, trong khi `co`/`can` ở đây chỉ
			# tính trên các ứng viên ĐÃ LỌC theo `pham_vi` — đo thật: phạm vi
			# tồn 2, cần 5 → báo "chỉ có 2, thiếu 3", trong khi kho thật có
			# 12. Người đọc sẽ đi tìm một vấn đề tồn kho không tồn tại. Nêu
			# đích danh `pham_vi` và nói rõ số liệu chỉ tính trong phạm vi đó.
			frappe.throw(
				_(
					"Không đủ hàng trong phạm vi {0}. Mặt hàng {1}{2} tại kho {3}: trong "
					"phạm vi này cần {4}, chỉ có {5}, thiếu {6}. Kho có thể còn hàng ở các vị "
					"trí khác ngoài phạm vi này."
				).format(pham_vi, vat_tu, ten_lo, kho, flt(so_luong), co, can)
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
