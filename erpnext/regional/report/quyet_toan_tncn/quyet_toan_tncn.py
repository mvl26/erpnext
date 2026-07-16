# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Quyết toán thuế TNCN (VN personal income tax summary).

Summarises PIT from the GL account 3335 (thuế thu nhập cá nhân): đã khấu trừ
(credit movement), đã nộp NSNN (debit movement), còn phải nộp (closing). When
payroll data is available (hrms installed, submitted Salary Slips in the period),
a per-employee section follows — thu nhập (gross) and TNCN withheld per người
lao động, read from the slips' income-tax deduction rows. Without hrms the report
degrades to the GL summary alone. Flagged for accountant verification.
"""

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.regional.vietnam.utils import get_account_balances

VERIFY_NOTE = _(
	"⚠️ Bản nháp — Tổng hợp từ TK 3335; chi tiết theo nhân viên lấy từ Salary Slip "
	"(hrms) khi có. Kế toán kiểm tra trước khi nộp 05/QTT-TNCN."
)

PIT_ACCOUNT = "3335"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters), VERIFY_NOTE


def get_columns():
	return [
		{"label": _("Chỉ tiêu"), "fieldname": "chi_tieu", "fieldtype": "Data", "width": 340},
		{"label": _("Số tiền"), "fieldname": "so_tien", "fieldtype": "Currency", "width": 160},
		{"label": _("Mã NV"), "fieldname": "employee", "fieldtype": "Data", "width": 120},
		{"label": _("Nhân viên"), "fieldname": "employee_name", "fieldtype": "Data", "width": 180},
		{"label": _("Thu nhập"), "fieldname": "thu_nhap", "fieldtype": "Currency", "width": 140},
		{"label": _("TNCN khấu trừ"), "fieldname": "tncn", "fieldtype": "Currency", "width": 140},
	]


def get_data(filters):
	if not (filters.company and filters.from_date and filters.to_date):
		return []

	b = get_account_balances(filters.company, filters.from_date, filters.to_date)
	pit = [x for x in b.values() if (x.account_number or "").startswith(PIT_ACCOUNT)]

	opening = -sum(x.opening for x in pit)  # còn phải nộp đầu kỳ (credit-positive)
	withheld = sum(x.credit for x in pit)  # phát sinh khấu trừ
	paid = sum(x.debit for x in pit)  # đã nộp NSNN
	closing = -sum(x.closing for x in pit)  # còn phải nộp cuối kỳ

	rows = [
		{"chi_tieu": _("Thuế TNCN còn phải nộp đầu kỳ"), "so_tien": opening},
		{"chi_tieu": _("Thuế TNCN đã khấu trừ trong kỳ"), "so_tien": withheld},
		{"chi_tieu": _("Thuế TNCN đã nộp Ngân sách Nhà nước"), "so_tien": paid},
		{"chi_tieu": _("Thuế TNCN còn phải nộp cuối kỳ"), "so_tien": closing, "is_total": 1},
	]
	rows += get_employee_rows(filters)
	return rows


# --- Per-employee detail (hrms soft dependency) --------------------------------


def _has_hrms():
	return "hrms" in frappe.get_installed_apps() and frappe.db.table_exists("Salary Slip")


def get_employee_rows(filters):
	"""Per-employee thu nhập / TNCN from submitted Salary Slips; [] without hrms."""
	if not _has_hrms():
		return []

	slips = frappe.get_all(
		"Salary Slip",
		filters={
			"company": filters.company,
			"docstatus": 1,
			"start_date": [">=", filters.from_date],
			"end_date": ["<=", filters.to_date],
		},
		fields=["name", "employee", "employee_name", "gross_pay"],
	)
	if not slips:
		return []

	tax_components = frappe.get_all(
		"Salary Component", filters={"is_income_tax_component": 1}, pluck="name"
	)
	tax_by_slip = {}
	if tax_components:
		for row in frappe.get_all(
			"Salary Detail",
			filters={
				"parenttype": "Salary Slip",
				"parentfield": "deductions",
				"parent": ["in", [s.name for s in slips]],
				"salary_component": ["in", tax_components],
			},
			fields=["parent", "amount"],
		):
			tax_by_slip[row.parent] = tax_by_slip.get(row.parent, 0.0) + flt(row.amount)

	by_employee = {}
	for slip in slips:
		entry = by_employee.setdefault(
			slip.employee,
			{"employee": slip.employee, "employee_name": slip.employee_name, "thu_nhap": 0.0, "tncn": 0.0},
		)
		entry["thu_nhap"] += flt(slip.gross_pay)
		entry["tncn"] += tax_by_slip.get(slip.name, 0.0)

	header = {"chi_tieu": _("— Chi tiết theo nhân viên (từ payroll) —"), "is_section": 1}
	return [header, *sorted(by_employee.values(), key=lambda r: r["employee"])]
