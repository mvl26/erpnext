# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Sinh Biên bản đối chiếu công nợ (FR-04, FR-20, D16).

Ba lối vào — job ngày 01, hộp thoại "Sinh biên bản kỳ", form tạo mới — đều đi qua
``build_statement`` và cùng hàm tính số ``figures.compute_from_totals`` (R-a).
"""

import frappe
from frappe import _
from frappe.utils import add_months, get_first_day, get_last_day, getdate, nowdate

from erpnext.debt_reconciliation import constants as C
from erpnext.debt_reconciliation import figures
from erpnext.debt_reconciliation.doctype.debt_reconciliation_statement.debt_reconciliation_statement import (
	find_existing,
)

# Hộp thoại chạy đồng bộ tới ngưỡng này, lớn hơn thì đẩy vào hàng đợi
SYNC_LIMIT = 20
LOCK_TTL = 60


def previous_month(today=None):
	first = get_first_day(add_months(getdate(today or nowdate()), -1))
	return first, get_last_day(first)


def _lock_key(party_type, party, from_date):
	return f"{frappe.local.site}:dr:{party_type}:{party}:{from_date}"


def build_statement(company, party_type, party, from_date, to_date, source, totals=None):
	"""Tạo 1 biên bản Nháp; nếu đối tác đã có biên bản kỳ đó thì trả bản đang có.

	Trả về ``(name, created)``. ``totals`` là số GL đã gom sẵn của đối tác (bản hàng
	loạt); để trống thì truy vấn riêng cho đối tác này.
	"""
	existing = find_existing(party_type, party, from_date, to_date)
	if existing:
		return existing, False

	# Khoá Redis tránh job và người dùng cùng tạo một lúc (4.4 TKKT). Dùng lệnh raw
	# set/delete theo cặp — delete_value() của Frappe thêm tiền tố nên sẽ không xoá được.
	cache = frappe.cache()
	key = _lock_key(party_type, party, from_date)
	if not cache.set(key, 1, nx=True, ex=LOCK_TTL):
		frappe.throw(_("Biên bản của {0} đang được tạo bởi tiến trình khác, thử lại sau.").format(party))
	try:
		existing = find_existing(party_type, party, from_date, to_date)
		if existing:
			return existing, False

		if totals is None:
			totals = figures.get_gl_totals(company, party_type, from_date, to_date, party=party).get(party)

		doc = frappe.new_doc(C.DOCTYPE)
		doc.update(
			{
				"company": company,
				"party_type": party_type,
				"party": party,
				"from_date": from_date,
				"to_date": to_date,
				"posting_date": nowdate(),
				"creation_source": source,
			}
		)
		doc.set_party_details()
		doc.apply_figures(figures.compute_from_totals(party_type, totals))
		doc.insert()
		return doc.name, True
	finally:
		cache.delete(key)


@frappe.whitelist()
def find_existing_statement(party_type, party, from_date, to_date, exclude=None):
	"""Form tạo mới dùng để mở bản đang có thay vì tạo bản thứ hai (R-b)."""
	frappe.has_permission(C.DOCTYPE, "read", throw=True)
	return find_existing(party_type, party, from_date, to_date, exclude=exclude)


def get_candidate_parties(company, party_type, from_date, to_date, parties=None):
	"""``[(party, totals)]``. Không chỉ định → đối tác đạt D1, đang hoạt động, không loại trừ.

	Có chỉ định (người dùng chọn) → giữ nguyên danh sách, kể cả đối tác không đạt D1 (R-d).
	"""
	accounts = figures.get_party_accounts(company, party_type)
	totals = figures.get_gl_totals(company, party_type, from_date, to_date, accounts=accounts)

	if parties:
		return [(p, totals.get(p)) for p in parties]

	active = set(
		frappe.get_all(
			party_type,
			filters={"disabled": 0, "exclude_reconciliation": 0, "name": ["in", list(totals) or [""]]},
			pluck="name",
		)
	)
	result = []
	for party in sorted(totals):
		if party in active and figures.compute_from_totals(party_type, totals[party]).meets_d1:
			result.append((party, totals[party]))
	return result


def generate_for_period(company, from_date, to_date, party_type=None, parties=None, source=C.SOURCE_AUTO):
	"""Sinh biên bản cho cả kỳ; lỗi của một đối tác không làm hỏng cả lô (UC-01 E2)."""
	result = {"created": [], "existing": [], "failed": []}
	for pt in [party_type] if party_type else ["Supplier", "Customer"]:
		if not figures.get_party_accounts(company, pt, throw=bool(party_type)):
			continue
		for party, totals in get_candidate_parties(company, pt, from_date, to_date, parties):
			row = {"party_type": pt, "party": party}
			try:
				frappe.db.savepoint("dr_generate")
				name, created = build_statement(company, pt, party, from_date, to_date, source, totals)
				row["name"] = name
				result["created" if created else "existing"].append(row)
			except Exception as e:
				frappe.db.rollback(save_point="dr_generate")
				frappe.clear_last_message()
				row["error"] = str(e) or e.__class__.__name__
				result["failed"].append(row)
				frappe.log_error(
					title=_("Sinh biên bản đối chiếu công nợ lỗi: {0}").format(party),
					reference_doctype=C.DOCTYPE,
				)
	return result


@frappe.whitelist()
def generate_statements(from_date, to_date, party_type, parties=None, company=None):
	"""Hộp thoại "Sinh biên bản kỳ" (FR-20b). Để trống ``parties`` = mọi đối tác đạt D1."""
	frappe.only_for((C.MANAGER_ROLE, C.USER_ROLE))
	frappe.has_permission(C.DOCTYPE, "create", throw=True)
	if party_type not in ("Supplier", "Customer"):
		frappe.throw(_("Chọn Loại đối tác."))
	company = company or frappe.defaults.get_user_default("Company")
	parties = frappe.parse_json(parties) if isinstance(parties, str) else parties
	parties = [p for p in (parties or []) if p]

	kwargs = dict(
		company=company,
		from_date=str(getdate(from_date)),
		to_date=str(getdate(to_date)),
		party_type=party_type,
		parties=parties,
		source=C.SOURCE_MANUAL,
	)
	count = len(parties) if parties else len(get_candidate_parties(company, party_type, from_date, to_date))
	if count <= SYNC_LIMIT:
		return {"queued": False, **generate_for_period(**kwargs)}

	frappe.enqueue(
		"erpnext.debt_reconciliation.generation.run_and_notify",
		queue="long",
		timeout=1500,
		user=frappe.session.user,
		enqueue_after_commit=True,
		now=frappe.flags.in_test,
		**kwargs,
	)
	return {"queued": True}


def run_and_notify(user=None, **kwargs):
	result = generate_for_period(**kwargs)
	notify_summary(result, kwargs["from_date"], kwargs["to_date"], [user] if user else None)
	return result


def auto_generate(today=None):
	"""Job ngày 01: sinh cho tháng liền trước, mọi công ty có TK 331/131 (FR-04)."""
	from_date, to_date = previous_month(today)
	combined = {"created": [], "existing": [], "failed": []}
	for company in frappe.get_all("Company", pluck="name"):
		result = generate_for_period(company, str(from_date), str(to_date), source=C.SOURCE_AUTO)
		for k in combined:
			combined[k] += result[k]
	notify_summary(combined, from_date, to_date)
	return combined


def notify_summary(result, from_date, to_date, users=None):
	"""1 Notification Log tóm tắt cho người chạy / người nhận nhắc hạn."""
	recipients = users or get_reminder_recipients()
	if not recipients:
		return
	subject = _("Sinh biên bản đối chiếu công nợ kỳ {0} – {1}: tạo {2}, đã có {3}, lỗi {4}").format(
		frappe.utils.formatdate(from_date),
		frappe.utils.formatdate(to_date),
		len(result["created"]),
		len(result["existing"]),
		len(result["failed"]),
	)
	lines = [f"{r['party']}: {r['error']}" for r in result["failed"]]
	make_notification(recipients, subject, "<br>".join(lines))


def make_notification(recipients, subject, message="", document_name=None):
	from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

	users = [u for u in recipients if frappe.db.exists("User", u)]
	if not users:
		return
	doc = {"type": "Alert", "subject": subject, "email_content": message}
	if document_name:
		doc.update({"document_type": C.DOCTYPE, "document_name": document_name})
	enqueue_create_notification(users, doc)


def get_reminder_recipients():
	raw = frappe.db.get_single_value(C.SETTINGS, "reminder_recipients") or ""
	return [line.strip() for line in raw.replace(",", "\n").splitlines() if line.strip()]
