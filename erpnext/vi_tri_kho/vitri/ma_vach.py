"""Đếm module Code 128 — MỘT định nghĩa cho cả phép kiểm lẫn việc vẽ nhãn.

Vì sao không ước lượng theo độ dài chuỗi: Code 128 đổi bộ mã giữa chừng và mỗi
lần đổi tốn một ký hiệu. Một chuỗi TOÀN CHỮ SỐ độ dài LẺ không mã hoá hết được
trong bộ C (bộ C nuốt hai chữ số một lần), nên phải bắt đầu ở bộ B cho chữ số
đầu rồi chèn một ký hiệu chuyển — tốn hai ký hiệu, không phải làm tròn lên một.
Bản nháp spec đã tính sai đúng chỗ này.

Hệ quả nếu tính thiếu: `validate` cho qua một số lô mà nhãn không vẽ nổi trong
khung, JS buộc phải bóp mã vạch xuống dưới 2 dot, và máy quét ĐỌC RA SAI KÝ TỰ
— không phải đọc hỏng. Sai lặng lẽ, trên vật thể đã dán lên hàng.
"""

import frappe
from frappe import _

#: Bề rộng một module, mm. 2 dot trên đầu in nhiệt 203 dpi (1 dot = 1/203 inch
#: = 0,125 mm). 1 dot dưới ngưỡng đọc tin cậy của Code 128; 3 dot làm mã tràn
#: khung. Đây là giá trị DUY NHẤT dùng được trên ZD421 — xem spec §6.2.
X_MM = 0.25

#: Trần số module vẽ được: mã vạch chiếm hết chiều ngang vùng in an toàn của
#: nhãn 50×30 (47,0 mm) ở bề rộng module bắt buộc 0,25 mm.
#:
#: Trước đây có thêm `MODULE_BO_CUC_A = int(28.0 / X_MM)` cho một bố cục đặt mã
#: vạch ở cột trái 29,4 mm. BỐ CỤC ĐÓ ĐÃ BỊ BỎ và hằng số đó đã xoá: Code 128
#: cần vùng yên tĩnh ≥ 10 module = 2,5 mm mỗi đầu, nên 112 module cần
#: 28,0 + 2,5 + 2,5 = 33,0 mm mà cột đó chỉ có 29,4 mm — thiếu 3,6 mm và không
#: cách nào bù. Giữ lại một hằng số quảng cáo rằng "có hỗ trợ bố cục A" chính
#: là thứ khiến người sau khôi phục nó cho giống mockup.
MODULE_TOI_DA = int(47.0 / X_MM)  # 188

#: start (11) + checksum (11) + stop (13). Không phụ thuộc dữ liệu.
_MODULE_CO_DINH = 35

#: Mỗi ký hiệu Code 128 rộng đúng 11 module (trừ stop, đã tính ở trên).
_MODULE_MOI_KY_HIEU = 11


def so_ky_hieu(s: str) -> int:
	"""Số ký hiệu Code 128 cần để mã hoá `s`, kể cả ký hiệu chuyển bộ mã."""
	if not s:
		return 0
	if s.isdigit():
		if len(s) % 2 == 0:
			return len(s) // 2
		# Chữ số đầu đi bộ B, rồi một ký hiệu chuyển sang bộ C cho phần còn lại.
		return 2 + (len(s) - 1) // 2
	return len(s)


def so_module(s: str) -> int:
	"""Bề rộng `s` tính bằng module Code 128."""
	if not s:
		return 0
	return _MODULE_CO_DINH + _MODULE_MOI_KY_HIEU * so_ky_hieu(s)


#: Code 128 chỉ mã hoá được ASCII. `CODE128.valid()` của JsBarcode là
#: `/^[\x00-\x7F\xC8-\xD3]+$/` — dải `\xC8-\xD3` là các ký hiệu điều khiển
#: nội bộ (FNC1…) mà người dùng không bao giờ gõ, nên với dữ liệu nhập tay thì
#: điều kiện thực tế là: MỌI ký tự phải < U+0080.
_MA_HOA_DUOC_TOI_DA = 0x7F


def kiem_tra_ky_tu(s: str, nhan: str) -> None:
	"""`throw` nếu `s` có ký tự Code 128 không mã hoá được, NÊU ĐÍCH DANH ký tự đó.

	VÌ SAO PHẢI CHẶN TỪ ĐÂY chứ không để tới lúc in: JsBarcode ném lỗi khi gặp
	ký tự ngoài ASCII, `frappe/form/controls/barcode.js` NUỐT lỗi đó, và phần tử
	SVG giữ nguyên nội dung của lần vẽ TRƯỚC. Hệ quả đã tái hiện được: tem của
	lô `LÔ-2026` in chữ `LÔ-2026` dưới mã vạch, còn mã vạch quét ra `25L4125` —
	số lô của con tem liền trước trong cùng xấp. Phía JS nay đã chặn
	(`_ve_vao_control` ở `tem_vi_tri.js`, và nhánh "đo hỏng" ở `tem_lo.js` bỏ
	hẳn mã vạch), nhưng lúc ấy thủ kho đã gõ xong số lô và phiếu đã submit. Chặn
	ở `validate` là chặn lúc người ta còn đang nhìn ô nhập.

	Câu báo phải NÊU ĐÍCH DANH ký tự và vị trí. "Số lô có ký tự không mã hoá
	được" là câu khiến thủ kho xoá bừa vài ký tự rồi thử lại — mà số lô cắt bớt
	là số lô SAI dán lên hàng. Hai thủ phạm hay gặp nhất là dấu tiếng Việt và
	dấu gạch ngang dài `–` (U+2013) dán từ phiếu đóng gói của nhà cung cấp, nên
	câu báo nói thẳng cả hai.
	"""
	if not s:
		return

	for i, c in enumerate(s):
		if ord(c) <= _MA_HOA_DUOC_TOI_DA:
			continue
		frappe.throw(
			_(
				"Số {0} '{1}' có ký tự '{2}' (U+{3:04X}) ở vị trí {4} — mã vạch Code 128 "
				"không mã hoá được ký tự này, nên nhãn sẽ không có mã vạch để quét. "
				"Code 128 chỉ nhận chữ cái không dấu, chữ số và dấu câu ASCII. Hai thứ "
				"hay lọt vào nhất là DẤU TIẾNG VIỆT và dấu gạch ngang dài '–' (U+2013) "
				"dán từ phiếu của nhà cung cấp — hãy gõ lại bằng dấu trừ '-' thường. "
				"ĐỪNG xoá bớt ký tự: số lô cắt bớt là số lô sai dán lên hàng."
			).format(nhan, s, c, ord(c), i + 1)
		)


def kiem_tra_do_dai(s: str, nhan: str) -> None:
	"""`throw` nếu `s` không vẽ nổi trong vùng in, kèm CON SỐ cụ thể.

	`nhan` là tên thứ đang kiểm, để câu báo đọc được ("số lô", "mã vật tư").

	Câu báo phải nói đang bao nhiêu / được bao nhiêu / suy ra bao nhiêu ký tự.
	Một câu chung chung khiến người dùng cắt bừa vài ký tự rồi thử lại — và số
	lô cắt bớt là số lô SAI dán lên hàng.
	"""
	m = so_module(s)
	if m <= MODULE_TOI_DA:
		return

	frappe.throw(
		_(
			"Số {0} '{1}' dài {2} ký tự, cần {3} module mã vạch nhưng nhãn 50×30 chỉ "
			"chứa được {4} module. Giới hạn thực tế: 26 chữ số (độ dài chẵn), "
			"23 chữ số (độ dài lẻ), hoặc 13 ký tự nếu có chữ. Không thu nhỏ mã vạch "
			"được: dưới 2 dot trên máy in nhiệt thì máy quét đọc ra SAI ký tự."
		).format(nhan, s, len(s), m, MODULE_TOI_DA)
	)


def kiem_ky_tu_lo(doc, method=None):
	"""Móc `doc_events["Batch"]["validate"]` — chặn ký tự không mã hoá được ở
	MỌI đường tạo lô, không riêng `Batch Entry`.

	`BatchEntry.validate` đã gọi `kiem_tra_ky_tu`, nhưng lô còn sinh bằng nhiều
	đường khác: hộp thoại lô sẵn có của ERPNext trên dòng phiếu nhập, nhập liệu
	trực tiếp trên doctype `Batch`, Data Import. Bịt một đường mà bỏ các đường
	kia thì lỗi vẫn tới được máy in.

	GỌI LẠI `kiem_tra_ky_tu`, KHÔNG chép luật vào đây: hai bản cài đặt của cùng
	một luật thì một ngày nào đó lệch nhau, và khi ấy một đường tạo lô chặn còn
	đường kia không — đúng kiểu hỏng mà cả file này sinh ra để ngăn.

	CHỈ kiểm lúc TẠO MỚI. `validate` chạy lại ở mọi lần lưu, mà `batch_id` là
	tên bản ghi nên một lô cũ lỡ có ký tự xấu thì không sửa được nữa (đổi tên
	là chuyện khác). Kiểm cả lúc cập nhật thì bản ghi đó thành một thứ KHÔNG
	AI LƯU LẠI ĐƯỢC: ai mở form `Batch` sửa hạn dùng, sửa nhà cung cấp, rồi
	bấm Save là `validate` chạy và nổ, trong khi thứ làm nó nổ lại không sửa
	được. Chặn lúc tạo là chặn đúng lúc còn sửa được.

	(ĐÍNH CHÍNH một ví dụ tôi từng viết ở đây: `recalculate_batch_qty` của
	ERPNext dùng `db_set`, mà `db_set` KHÔNG kích `validate` —
	`frappe/model/document.py:1240` ghi rõ. Nên "ERPNext tự cập nhật
	`batch_qty` sẽ nổ" KHÔNG phải nguy cơ thật. Đường vào thật là form và mọi
	lời gọi `.save()`.)

	KHÔNG sửa `erpnext/stock/doctype/batch/batch.py` (brief cấm) — đi qua
	`doc_events` trong `hooks.py`, đúng cơ chế `dien_ncc_tu_chung_tu` đang dùng.
	"""
	if not doc.is_new():
		return

	ma = doc.get("batch_id") or doc.get("name")
	if ma:
		kiem_tra_ky_tu(ma, _("lô"))
