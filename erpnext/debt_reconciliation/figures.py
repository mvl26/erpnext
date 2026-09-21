# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Hàm tính số dùng chung cho Biên bản đối chiếu công nợ (FR-05, D7, D9, D11, D12, D18).

Được gọi bởi cả job sinh đầu tháng, nút "Lấy số liệu từ sổ" và hộp thoại "Sinh biên
bản kỳ" — lập tay hay tự động đều ra số giống hệt nhau (R-a). Chỉ đọc GL Entry, không
ghi DB.

Quy ước giá trị có hướng: dương = đối tác/Miyano còn nợ (NCC 331: Miyano còn nợ NCC →
Dư Có; KH 131: khách còn nợ Miyano → Dư Nợ). Mọi số lưu xuống field đều là trị tuyệt
đối kèm chiều dư (D9).
"""

import frappe
from frappe import _
from frappe.utils import flt
from frappe.utils.nestedset import get_descendants_of

from erpnext.debt_reconciliation.constants import DIR_CREDIT, DIR_DEBIT, DIR_ZERO, SETTINGS
from erpnext.regional.vietnam.utils import so_thanh_chu


def get_account_number(party_type):
	fieldname = "payable_account_number" if party_type == "Supplier" else "receivable_account_number"
	default = "331" if party_type == "Supplier" else "131"
	return (frappe.db.get_single_value(SETTINGS, fieldname) or default).strip()


def get_party_accounts(company, party_type, throw=True):
	"""TK 331/131 của công ty và toàn bộ tài khoản lá bên dưới (D7).

	Tìm theo ``account_number`` chứ không theo tên — tên thật trên site là
	``331 - Phải trả cho người bán - M``.
	"""
	number = get_account_number(party_type)
	root = frappe.db.get_value(
		"Account", {"company": company, "account_number": number}, ["name", "is_group"], as_dict=True
	)
	if not root:
		if throw:
			frappe.throw(
				_("Công ty {0} chưa có tài khoản số {1} — kiểm tra Cài đặt đối chiếu công nợ.").format(
					company, number
				)
			)
		return []
	if not root.is_group:
		return [root.name]
	descendants = get_descendants_of("Account", root.name)
	if not descendants:
		return []
	return frappe.get_all("Account", filters={"name": ["in", descendants], "is_group": 0}, pluck="name")


def get_gl_totals(company, party_type, from_date, to_date, party=None, accounts=None):
	"""``{party: _dict(d0, c0, d, c)}`` trong một truy vấn (NFR-01, không N+1).

	``d0``/``c0`` là tổng Nợ/Có trước ``from_date``; ``d``/``c`` là tổng trong kỳ.
	"""
	accounts = accounts if accounts is not None else get_party_accounts(company, party_type)
	if not accounts:
		return {}

	party_condition = "and party = %(party)s" if party else ""
	rows = frappe.db.sql(
		f"""
		select party,
			sum(case when posting_date < %(from_date)s then debit else 0 end) as d0,
			sum(case when posting_date < %(from_date)s then credit else 0 end) as c0,
			sum(case when posting_date >= %(from_date)s then debit else 0 end) as d,
			sum(case when posting_date >= %(from_date)s then credit else 0 end) as c
		from `tabGL Entry`
		where company = %(company)s and is_cancelled = 0
			and party_type = %(party_type)s and ifnull(party, '') != ''
			and account in %(accounts)s
			and posting_date <= %(to_date)s
			{party_condition}
		group by party
		""",
		{
			"company": company,
			"party_type": party_type,
			"party": party,
			"accounts": tuple(accounts),
			"from_date": from_date,
			"to_date": to_date,
		},
		as_dict=True,
	)
	return {
		r.party: frappe._dict(d0=flt(r.d0, 0), c0=flt(r.c0, 0), d=flt(r.d, 0), c=flt(r.c, 0)) for r in rows
	}


def signed_opening(party_type, d0, c0):
	"""Dư đầu gốc có hướng ``G_đ``. NCC đổi dấu so với quy ước Nợ - Có của ERPNext."""
	return flt(c0 - d0, 0) if party_type == "Supplier" else flt(d0 - c0, 0)


def direction_of(party_type, signed_value):
	value = flt(signed_value, 0)
	if not value:
		return DIR_ZERO
	owed = DIR_CREDIT if party_type == "Supplier" else DIR_DEBIT
	prepaid = DIR_DEBIT if party_type == "Supplier" else DIR_CREDIT
	return owed if value > 0 else prepaid


def to_signed(party_type, amount, direction):
	"""Ngược của (abs, chiều dư) → giá trị có hướng."""
	if direction == DIR_ZERO or not flt(amount):
		return 0.0
	return flt(amount, 0) if direction == direction_of(party_type, 1) else -flt(amount, 0)


def compute(party_type, g_open, d, c, opening_interest=0, interest_in_period=0):
	"""Công thức SRS 12.6 (D18). Thuần — không đọc/ghi DB.

	``g_open``: dư đầu gốc có hướng; ``d``/``c``: phát sinh Nợ/Có gốc trong kỳ;
	lãi quá hạn nhập tay. Trả về dict gồm field lưu được và các giá trị có hướng
	(``opening``, ``closing``) cùng danh sách ``interest_errors`` theo D12.
	"""
	g_open, d, c = flt(g_open, 0), flt(d, 0), flt(c, 0)
	l_open, l_period = flt(opening_interest, 0), flt(interest_in_period, 0)

	opening = g_open + l_open
	if party_type == "Supplier":
		closing_before_interest = opening + c - d
	else:
		closing_before_interest = opening + d - c
	closing = flt(closing_before_interest + l_period, 0)

	errors = []
	if l_open < 0 or l_period < 0:
		errors.append(_("Lãi quá hạn không được âm."))
	if l_open > 0 and g_open <= 0:
		errors.append(_("Chỉ được nhập lãi quá hạn đầu kỳ khi dư đầu kỳ ở chiều còn nợ (D12)."))
	if l_period > 0 and flt(closing_before_interest, 0) <= 0:
		errors.append(_("Chỉ được nhập lãi quá hạn phát sinh khi dư cuối kỳ ở chiều còn nợ (D12)."))

	return frappe._dict(
		opening_principal=abs(g_open),
		opening_direction=direction_of(party_type, opening),
		debit_in_period=d,
		credit_in_period=c,
		closing_balance=abs(closing),
		balance_direction=direction_of(party_type, closing),
		amount_in_words=so_thanh_chu(abs(closing)),
		meets_d1=bool(closing or d or c),
		opening=opening,
		closing=closing,
		interest_errors=errors,
	)


def get_figures(company, party_type, party, from_date, to_date, opening_interest=0, interest_in_period=0):
	"""Số liệu một đối tác lấy thẳng từ GL (dùng cho nút "Lấy số liệu từ sổ")."""
	totals = get_gl_totals(company, party_type, from_date, to_date, party=party).get(party)
	return compute_from_totals(party_type, totals, opening_interest, interest_in_period)


def compute_from_totals(party_type, totals, opening_interest=0, interest_in_period=0):
	totals = totals or frappe._dict(d0=0, c0=0, d=0, c=0)
	return compute(
		party_type,
		signed_opening(party_type, totals.d0, totals.c0),
		totals.d,
		totals.c,
		opening_interest,
		interest_in_period,
	)
