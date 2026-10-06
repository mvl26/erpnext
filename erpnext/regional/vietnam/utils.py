# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Shared helpers for Vietnam (Thông tư 99/2025/TT-BTC) accounting reports.

All statutory reports are computed read-only over the shared GL; these helpers
centralise the GL aggregation and the Vietnamese amount-in-words used by
statements, books, declarations and voucher print formats.
"""

import frappe
from frappe.utils import flt

_ONES = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]


def _read_three(n, full):
	"""Read a 0-999 group. ``full`` forces 'không trăm' for non-leading groups."""
	hundreds, rem = divmod(n, 100)
	tens, ones = divmod(rem, 10)
	words = []

	if hundreds > 0:
		words += [_ONES[hundreds], "trăm"]
	elif full:
		words += ["không", "trăm"]

	if tens == 0:
		if ones > 0:
			if hundreds > 0 or full:
				words.append("lẻ")
			words.append(_ONES[ones])
	elif tens == 1:
		words.append("mười")
		if ones == 5:
			words.append("lăm")
		elif ones > 0:
			words.append(_ONES[ones])
	else:
		words += [_ONES[tens], "mươi"]
		if ones == 1:
			words.append("mốt")
		elif ones == 5:
			words.append("lăm")
		elif ones > 0:
			words.append(_ONES[ones])

	return words


def _unit_for(group_index):
	"""Magnitude words for a group: nghìn / triệu / tỷ (cycling by tỷ)."""
	base = ["", "nghìn", "triệu"][group_index % 3]
	words = [base] if base else []
	words += ["tỷ"] * (group_index // 3)
	return " ".join(words)


def so_thanh_chu(amount, currency_label="đồng"):
	"""Return a Vietnamese amount-in-words, e.g. 1_000_000 -> 'Một triệu đồng'."""
	amount = int(round(flt(amount)))

	if amount == 0:
		text = "không"
	else:
		negative = amount < 0
		n = abs(amount)
		groups = []
		while n > 0:
			groups.append(n % 1000)
			n //= 1000

		parts = []
		last = len(groups) - 1
		for i in range(last, -1, -1):
			if groups[i] == 0:
				continue
			words = _read_three(groups[i], full=(i != last))
			unit = _unit_for(i)
			if unit:
				words.append(unit)
			parts += words

		text = " ".join(parts)
		if negative:
			text = "âm " + text

	text = f"{text} {currency_label}".strip()
	return text[0].upper() + text[1:]


def get_gl_entries(company, from_date, to_date, extra_filters=None):
	"""Non-cancelled GL entries for a company within [from_date, to_date]."""
	filters = {
		"company": company,
		"is_cancelled": 0,
		"posting_date": ["between", [from_date, to_date]],
	}
	if extra_filters:
		filters.update(extra_filters)
	return frappe.get_all(
		"GL Entry",
		filters=filters,
		fields=[
			"posting_date",
			"account",
			"debit",
			"credit",
			"voucher_type",
			"voucher_no",
			"against",
			"party_type",
			"party",
			"remarks",
		],
		order_by="posting_date, creation",
	)


def get_account_balances(company, from_date, to_date):
	"""Per non-group account: opening / period movement / closing (debit-positive).

	Returns ``{account_name: _dict(name, account_number, root_type, account_name,
	opening, debit, credit, closing)}`` where ``opening`` and ``closing`` are net
	debit-minus-credit balances and ``debit``/``credit`` are the period movement.
	"""
	balances = {
		a.name: frappe._dict(
			name=a.name,
			account_number=a.account_number,
			root_type=a.root_type,
			account_name=a.account_name,
			opening=0.0,
			debit=0.0,
			credit=0.0,
			closing=0.0,
		)
		for a in frappe.get_all(
			"Account",
			filters={"company": company, "is_group": 0},
			fields=["name", "account_number", "root_type", "account_name"],
		)
	}

	opening = frappe.db.sql(
		"""
		select account, sum(debit) - sum(credit) as bal
		from `tabGL Entry`
		where company = %s and is_cancelled = 0 and posting_date < %s
		group by account
		""",
		(company, from_date),
		as_dict=True,
	)
	for row in opening:
		if row.account in balances:
			balances[row.account].opening = flt(row.bal)

	period = frappe.db.sql(
		"""
		select account, sum(debit) as dr, sum(credit) as cr
		from `tabGL Entry`
		where company = %s and is_cancelled = 0 and posting_date between %s and %s
		group by account
		""",
		(company, from_date, to_date),
		as_dict=True,
	)
	for row in period:
		if row.account in balances:
			balances[row.account].debit = flt(row.dr)
			balances[row.account].credit = flt(row.cr)

	for b in balances.values():
		b.closing = b.opening + b.debit - b.credit

	return balances


def get_cash_bank_book_rows(company, from_date, to_date, prefix, account=None):
	"""Thu / chi / tồn ledger rows over accounts numbered ``prefix*`` (e.g. 111, 112).

	Shared by Sổ quỹ tiền mặt (S07-DN) and Sổ tiền gửi ngân hàng (S08-DN): an
	opening-balance row, one row per GL entry (thu = debit, chi = credit, running
	tồn), a period-total row and a closing row. ``account`` narrows the book to one
	posting account (một quỹ / một tài khoản ngân hàng).
	"""
	accounts = (
		[account]
		if account
		else frappe.get_all(
			"Account",
			filters={"company": company, "is_group": 0, "account_number": ["like", f"{prefix}%"]},
			pluck="name",
		)
	)
	if not accounts:
		return []

	opening = flt(
		frappe.db.sql(
			"""select sum(debit) - sum(credit) from `tabGL Entry`
			where company=%s and is_cancelled=0 and posting_date < %s and account in %s""",
			(company, from_date, tuple(accounts)),
		)[0][0]
	)

	rows = [{"remarks": "Số dư đầu kỳ", "balance": opening, "is_opening": 1}]
	balance = opening
	total_thu = total_chi = 0.0
	for e in get_gl_entries(company, from_date, to_date, {"account": ["in", accounts]}):
		balance += flt(e.debit) - flt(e.credit)
		total_thu += flt(e.debit)
		total_chi += flt(e.credit)
		rows.append(
			{
				"posting_date": e.posting_date,
				"voucher_type": e.voucher_type,
				"voucher_no": e.voucher_no,
				"account": e.account,
				"remarks": e.remarks,
				"against": e.against,
				"thu": e.debit,
				"chi": e.credit,
				"balance": balance,
			}
		)

	rows.append({"remarks": "Cộng phát sinh", "thu": total_thu, "chi": total_chi, "is_total": 1})
	rows.append({"remarks": "Số dư cuối kỳ", "balance": balance, "is_closing": 1})
	return rows


def _prefixes(prefixes):
	return tuple(str(p) for p in prefixes)


def sum_closing_by_prefix(balances, prefixes):
	"""Net closing balance of accounts whose number starts with any prefix."""
	pfx = _prefixes(prefixes)
	return sum(b.closing for b in balances.values() if (b.account_number or "").startswith(pfx))


def sum_movement_by_prefix(balances, prefixes):
	"""Net period movement (debit - credit) of accounts matching any prefix."""
	pfx = _prefixes(prefixes)
	return sum(
		b.debit - b.credit for b in balances.values() if (b.account_number or "").startswith(pfx)
	)
