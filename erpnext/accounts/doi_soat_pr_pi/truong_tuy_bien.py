# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Trường tùy biến của đối soát Phiếu nhập mua ↔ Hóa đơn mua (YC5, spec 2026-10-21 mục 6.3).

Cùng nguyên tắc với BA12: không sửa JSON DocType chuẩn. Trường thêm là Custom Field, logic gắn
qua `doc_events` / `doctype_js` trong hooks.py. `tao_truong_tuy_bien` chạy ở mỗi lần migrate
(`after_migrate`, TRƯỚC khi gieo điểm thông báo vì các điểm YC5 trỏ vào những trường này) và
chạy lại nhiều lần an toàn (`update=True`).
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

TRANG_THAI = "\nChưa đối soát\nKhớp\nLệch\nNgoại lệ đã duyệt"
NHANH_XU_LY = "\n(a) Hóa đơn mua nhập sai\n(b1) Phiếu nhập mua sai\n(b2) Hóa đơn NCC sai"
PHAM_VI = "Chỉ nhà cung cấp được chọn\nMọi nhà cung cấp"


def _ro(**field):
	"""Ô do server ghi: chỉ đọc, không chép khi Duplicate/Amend, không in."""
	return {"read_only": 1, "no_copy": 1, "print_hide": 1, **field}


CUSTOM_FIELDS = {
	"Buying Settings": [
		{
			"fieldname": "doi_soat_pr_pi_section",
			"fieldtype": "Section Break",
			"label": "Đối soát Phiếu nhập mua ↔ Hóa đơn mua",
			"insert_after": "project_update_frequency",
		},
		{
			"fieldname": "bat_doi_soat_pr_pi",
			"fieldtype": "Check",
			"default": "0",
			"label": "Bật đối soát Phiếu nhập ↔ Hóa đơn mua",
			"description": "Hóa đơn mua có dòng lấy từ Phiếu nhập mua phải khớp 0 đồng (từng dòng và tổng) mới Nộp được, trừ khi có ngoại lệ được duyệt. Hóa đơn cao hơn Phiếu nhập vẫn lưu được để hiện trong Bảng chênh lệch; không cần đổi Over Billing Allowance.",
			"insert_after": "doi_soat_pr_pi_section",
		},
		{
			"fieldname": "pham_vi_doi_soat",
			"fieldtype": "Select",
			"options": PHAM_VI,
			"default": "Chỉ nhà cung cấp được chọn",
			"label": "Phạm vi áp dụng",
			"description": "Bật thử: chọn nhà cung cấp bằng ô Áp đối soát Phiếu nhập ↔ Hóa đơn trên hồ sơ nhà cung cấp.",
			"depends_on": "bat_doi_soat_pr_pi",
			"insert_after": "bat_doi_soat_pr_pi",
		},
		{
			"fieldname": "tao_dntt_khi_nop_hoa_don",
			"fieldtype": "Check",
			"default": "1",
			"label": "Tự tạo đề nghị thanh toán nháp khi Nộp hóa đơn",
			"description": "Áp cho hóa đơn đã khớp hoặc có ngoại lệ được duyệt. Đề nghị thanh toán chỉ ở dạng nháp và được giao cho người duyệt.",
			"depends_on": "bat_doi_soat_pr_pi",
			"insert_after": "pham_vi_doi_soat",
		},
		{
			"fieldname": "column_break_doi_soat_pr_pi",
			"fieldtype": "Column Break",
			"insert_after": "tao_dntt_khi_nop_hoa_don",
		},
		{
			"fieldname": "vai_tro_ke_toan_truong",
			"fieldtype": "Link",
			"options": "Role",
			"label": "Vai trò Kế toán trưởng",
			"description": "Duyệt ngoại lệ cho hóa đơn còn lệch, nhận nhắc hóa đơn lệch quá hạn. Để trống cả hai ô vai trò: chỉ System Manager duyệt được.",
			"depends_on": "bat_doi_soat_pr_pi",
			"insert_after": "column_break_doi_soat_pr_pi",
		},
		{
			"fieldname": "vai_tro_ban_dieu_hanh",
			"fieldtype": "Link",
			"options": "Role",
			"label": "Vai trò Ban Điều hành",
			"description": "Cũng được duyệt ngoại lệ.",
			"depends_on": "bat_doi_soat_pr_pi",
			"insert_after": "vai_tro_ke_toan_truong",
		},
		{
			"fieldname": "nguoi_duyet_dntt",
			"fieldtype": "Link",
			"options": "User",
			"label": "Người duyệt đề nghị thanh toán",
			"description": "Được giao việc khi hệ thống tạo đề nghị thanh toán nháp. Để trống: giao cho mọi người có Vai trò Kế toán trưởng.",
			"depends_on": "eval:doc.bat_doi_soat_pr_pi && doc.tao_dntt_khi_nop_hoa_don",
			"insert_after": "vai_tro_ban_dieu_hanh",
		},
		{
			"fieldname": "so_ngay_nhac_lech",
			"fieldtype": "Int",
			"default": "3",
			"non_negative": 1,
			"label": "Nhắc Kế toán trưởng khi lệch quá (ngày)",
			"description": "Mỗi sáng gửi Kế toán trưởng (người có Vai trò Kế toán trưởng) danh sách hóa đơn mua nháp còn lệch / chưa đối soát từ quá số ngày này. 0: không nhắc.",
			"depends_on": "bat_doi_soat_pr_pi",
			"insert_after": "nguoi_duyet_dntt",
		},
	],
	"Supplier": [
		{
			"fieldname": "doi_soat_pr_pi",
			"fieldtype": "Check",
			"default": "0",
			"label": "Áp đối soát Phiếu nhập ↔ Hóa đơn",
			"description": "Chỉ có tác dụng khi Thiết lập mua hàng chọn phạm vi Chỉ nhà cung cấp được chọn. Chỉ người duyệt ngoại lệ hoặc System Manager được đổi.",
			"insert_after": "allow_purchase_invoice_creation_without_purchase_receipt",
		},
	],
	"Purchase Invoice": [
		{
			"fieldname": "doi_soat_pr_section",
			"fieldtype": "Section Break",
			"label": "Đối soát với Phiếu nhập mua",
			"insert_after": "items",
			"collapsible": 1,
			"collapsible_depends_on": "eval:['Lệch','Chưa đối soát'].includes(doc.trang_thai_doi_soat_pr)",
			"depends_on": "trang_thai_doi_soat_pr",
		},
		_ro(
			fieldname="trang_thai_doi_soat_pr",
			fieldtype="Select",
			options=TRANG_THAI,
			label="Trạng thái đối soát",
			in_standard_filter=1,
			insert_after="doi_soat_pr_section",
		),
		_ro(
			fieldname="thoi_diem_doi_soat",
			fieldtype="Datetime",
			label="Đối soát lúc",
			insert_after="trang_thai_doi_soat_pr",
		),
		# Ngày hóa đơn bắt đầu lệch: căn cứ nhắc Kế toán trưởng khi lệch tồn quá N ngày.
		_ro(
			fieldname="lech_tu_ngay",
			fieldtype="Date",
			label="Lệch từ ngày",
			depends_on="lech_tu_ngay",
			insert_after="thoi_diem_doi_soat",
		),
		{
			"fieldname": "nhanh_xu_ly",
			"fieldtype": "Select",
			"options": NHANH_XU_LY,
			"label": "Nhánh xử lý",
			"description": "Người xử lý chọn: (a) Mua hàng sửa hóa đơn; (b1) Kho hủy và sửa Phiếu nhập; (b2) gửi nhà cung cấp bảng chênh lệch để xin hóa đơn điều chỉnh.",
			"depends_on": "eval:doc.trang_thai_doi_soat_pr == 'Lệch'",
			"insert_after": "lech_tu_ngay",
			"no_copy": 1,
			"print_hide": 1,
		},
		{
			"fieldname": "hoa_don_tung_phan",
			"fieldtype": "Check",
			"label": "Hóa đơn từng phần",
			"description": "Tích khi nhà cung cấp xuất nhiều hóa đơn cho cùng Phiếu nhập: số lượng được ít hơn phần chưa lập hóa đơn (không được nhiều hơn); đơn giá, thuế, thành tiền vẫn phải khớp. Hóa đơn cuối lấy hết phần còn lại thì không cần tích.",
			"insert_after": "nhanh_xu_ly",
			"no_copy": 1,
			"print_hide": 1,
		},
		{
			"fieldname": "column_break_doi_soat_pr",
			"fieldtype": "Column Break",
			"insert_after": "hoa_don_tung_phan",
		},
		_ro(
			fieldname="ly_do_ngoai_le",
			fieldtype="Small Text",
			label="Lý do ngoại lệ",
			depends_on="ly_do_ngoai_le",
			insert_after="column_break_doi_soat_pr",
		),
		_ro(
			fieldname="nguoi_duyet_ngoai_le",
			fieldtype="Link",
			options="User",
			label="Người duyệt ngoại lệ",
			depends_on="nguoi_duyet_ngoai_le",
			insert_after="ly_do_ngoai_le",
		),
		_ro(
			fieldname="thoi_diem_duyet_ngoai_le",
			fieldtype="Datetime",
			label="Thời điểm duyệt ngoại lệ",
			depends_on="nguoi_duyet_ngoai_le",
			insert_after="nguoi_duyet_ngoai_le",
		),
		# Ngoại lệ gắn với đúng bảng chênh lệch lúc duyệt: hóa đơn sửa làm chênh lệch đổi thì
		# phê duyệt mất hiệu lực.
		_ro(
			fieldname="dau_van_tay_chenh_lech",
			fieldtype="Data",
			label="Dấu vân tay chênh lệch đã duyệt",
			hidden=1,
			insert_after="thoi_diem_duyet_ngoai_le",
		),
		{
			"fieldname": "chenh_lech_pr_section",
			"fieldtype": "Section Break",
			"insert_after": "dau_van_tay_chenh_lech",
			"depends_on": "eval:(doc.chenh_lech_pr || []).length",
		},
		_ro(
			fieldname="chenh_lech_pr",
			fieldtype="Table",
			options="Purchase Invoice PR Difference",
			label="Bảng chênh lệch",
			insert_after="chenh_lech_pr_section",
		),
	],
}


def tao_truong_tuy_bien():
	"""Gọi từ `after_migrate`."""
	create_custom_fields(CUSTOM_FIELDS, update=True)
