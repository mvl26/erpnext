# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""B09-DN — Thuyết minh báo cáo tài chính (VN notes to the financial statements).

Renders the standard note sections plus supplementary key figures pulled from the
GL that tie to B01/B02. Narrative content is RESEARCH-DERIVED from TT99 and should
be adapted/verified by a kế toán before filing.
"""

import frappe
from frappe import _

from erpnext.regional.vietnam.utils import get_account_balances, sum_movement_by_prefix

VERIFY_NOTE = _(
	"⚠️ Bản nháp — Nội dung thuyết minh theo TT99 cần kế toán rà soát trước khi nộp."
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters), VERIFY_NOTE


def get_columns():
	return [
		{"label": _("Chỉ tiêu"), "fieldname": "chi_tieu", "fieldtype": "Data", "width": 320},
		{"label": _("Nội dung"), "fieldname": "noi_dung", "fieldtype": "Data", "width": 460},
		{"label": _("Giá trị"), "fieldname": "gia_tri", "fieldtype": "Currency", "width": 160},
	]


def get_data(filters):
	if not (filters.company and filters.from_date and filters.to_date):
		return []

	b = get_account_balances(filters.company, filters.from_date, filters.to_date)

	def closing(prefixes):
		return sum(
			x.closing for x in b.values() if (x.account_number or "").startswith(tuple(prefixes))
		)

	rows = [
		{"chi_tieu": _("I. Đặc điểm hoạt động của doanh nghiệp"), "is_header": 1},
		{
			"chi_tieu": _("Hình thức sở hữu vốn"),
			"noi_dung": _("Công ty trách nhiệm hữu hạn."),
		},
		{"chi_tieu": _("II. Kỳ kế toán, đơn vị tiền tệ sử dụng"), "is_header": 1},
		{"chi_tieu": _("Kỳ kế toán năm"), "noi_dung": _("Từ ngày 01/01 đến 31/12.")},
		{"chi_tieu": _("Đơn vị tiền tệ sử dụng"), "noi_dung": _("Đồng Việt Nam (VND).")},
		{"chi_tieu": _("III. Chuẩn mực và chế độ kế toán áp dụng"), "is_header": 1},
		{
			"chi_tieu": _("Chế độ kế toán áp dụng"),
			"noi_dung": _(
				"Thông tư số 99/2025/TT-BTC ngày 27/10/2025 của Bộ Tài chính về chế độ "
				"kế toán doanh nghiệp."
			),
		},
		{"chi_tieu": _("IV. Các chính sách kế toán áp dụng"), "is_header": 1},
		{
			"chi_tieu": _("Nguyên tắc ghi nhận hàng tồn kho"),
			"noi_dung": _("Giá gốc; giá xuất kho theo bình quân gia quyền."),
		},
		{
			"chi_tieu": _("Nguyên tắc khấu hao TSCĐ"),
			"noi_dung": _("Phương pháp đường thẳng."),
		},
		{
			"chi_tieu": _("V. Thông tin bổ sung cho các khoản mục BCTC"),
			"is_header": 1,
		},
		{
			"chi_tieu": _("Tiền và các khoản tương đương tiền"),
			"gia_tri": closing(["111", "112", "113"]),
		},
		{
			"chi_tieu": _("Các khoản phải thu ngắn hạn"),
			"gia_tri": closing(["131", "136", "138", "141"]),
		},
		{
			"chi_tieu": _("Hàng tồn kho"),
			"gia_tri": closing(["151", "152", "153", "154", "155", "156", "157", "158"]),
		},
		{"chi_tieu": _("Phải trả người bán"), "gia_tri": -closing(["331"])},
		{
			"chi_tieu": _("Doanh thu bán hàng và cung cấp dịch vụ"),
			"gia_tri": -sum_movement_by_prefix(b, ["511"]),
		},
		{"chi_tieu": _("Giá vốn hàng bán"), "gia_tri": sum_movement_by_prefix(b, ["632"])},
		{"chi_tieu": _("VI. Những thông tin khác"), "is_header": 1},
		{"chi_tieu": _("Sự kiện sau ngày kết thúc kỳ kế toán"), "noi_dung": _("Không có.")},
	]
	return rows
