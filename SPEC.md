# Spec: Miyano ERP — Complete Vietnamese Accounting (Thông tư 99/2025/TT-BTC)

> Status: **DRAFT — awaiting approval.** Phase 1 (Specify) of spec-driven development.
> Once approved, the plan is regenerated into `tasks/plan.md` + `tasks/todo.md`.

## Objective

Turn ERPNext into a complete, Vietnam-compliant accounting system for **Công ty
TNHH Miyano Việt Nam** — a medical-equipment / vật tư y tế trading business —
conforming to **Thông tư 99/2025/TT-BTC**. Building on the delivered foundation
(TT99 chart of accounts, operational accounts, GTGT tax templates, VND defaults,
standard-report compatibility), this phase adds the statutory outputs and the
import / foreign-currency handling a real VN business needs to close its books
and file with the authorities.

**Users**
- Kế toán viên / kế toán trưởng (accountants) — daily entry, month/quarter/year close, filing.
- Giám đốc (management) — financial statements, KQKD.
- medcons.vn dev team — maintainers.

**What success looks like** — from ERPNext alone, a Miyano accountant can:
1. Produce TT99 **statutory financial statements**: B01-DN (Bảng CĐKT), B02-DN
   (Báo cáo KQHĐKD), B03-DN (Lưu chuyển tiền tệ), B09-DN (Thuyết minh BCTC).
2. Generate **tax declarations**: Tờ khai thuế GTGT (01/GTGT), quyết toán thuế
   TNCN, quyết toán thuế TNDN.
3. Print **statutory accounting books**: Sổ Nhật ký chung, Sổ Cái, Sổ chi tiết
   tài khoản, Bảng cân đối số phát sinh.
4. Correctly account for **imports & foreign currency**: USD/foreign-currency
   purchases, thuế nhập khẩu & TTĐB on imported equipment, đánh giá lại tỷ giá
   (TK 413), and Vietnamese số-thành-chữ on printed vouchers.

All amounts in **VND**; all GTGT via the TT99 accounts (33311 đầu ra / 1331 khấu trừ).

## Scope & Placement

**Everything is built in `erpnext` core** (this hard-forked app), consistent with
the fork philosophy ("ERPNext itself becomes Miyano's product") and the user's
explicit direction. VN-specific artifacts follow ERPNext's regional pattern under
`erpnext/regional/vietnam/`.

**Coordination with `mvl_accounting`** (shares the site DB). That app already
implements: period close via TK 911, CIT provisional / loss carryforward / offset,
VAT input allocation, consignment reconciliation, opening balances, MVL master
overlays, payroll mapping, related-party log. Therefore:
- This spec's reports/declarations/books are **read-only over the shared GL**
  (Account / GL Entry), so they do **not** reimplement mvl_accounting's compute
  logic. Where a declaration needs CIT/VAT-allocation results (e.g. quyết toán
  TNDN, tờ khai GTGT), it **consumes** mvl_accounting's data if present rather
  than recomputing. (See Open Questions.)
- We do **not** rebuild period-close / CIT / VAT-allocation / consignment.

**Out of scope (this phase):** e-invoice / Hóa đơn điện tử (separate integration
project); payroll computation; the mvl_accounting-owned compute logic above.

## Tech Stack

- Frappe Framework **v15** + ERPNext **v15**, site `miyano` (shared DB).
- **Python 3.12** — TABS for indentation, line length 110, double-quoted strings
  (ruff), enforced by pre-commit (ruff + prettier + eslint).
- Reports: Frappe **Script Report** (statutory statements/declarations/books need
  computed line items) and Query Report where a plain query suffices.
- Client: `frappe.ui.form.on` JS; print formats (Jinja) for voucher số-thành-chữ.
- Data model changes: DocType JSON + Custom Fields via fixtures/patches.
- Tests: `frappe.tests.utils.FrappeTestCase` / `unittest`, transaction-rolled-back.

## Commands

Run from the bench root `/home/miyano/frappe-bench`, site `miyano`:

```bash
bench --site miyano migrate                 # apply DocType/patch changes
bench build --app erpnext                   # rebuild JS/CSS bundles
bench --site miyano clear-cache
bench --site miyano console                 # Frappe shell

# Tests
bench --site miyano run-tests --app erpnext
bench --site miyano run-tests --module erpnext.regional.vietnam.report.<report>.test_<report>
bench --site miyano run-tests --doctype "Account"

# Lint / format (gate = pre-commit)
pre-commit run --all-files
ruff check erpnext/ ; ruff format erpnext/
```

## Project Structure

New and touched locations (all under `erpnext/`):

```
erpnext/regional/vietnam/                         → NEW VN regional module
  __init__.py
  setup.py                                        → update_regional_tax_settings, VN custom fields
  utils.py                                        → shared: number-to-VND-words, account-range helpers
  vietnam.py / constants.py                       → Mã-số → account-range mapping tables
  report/
    bao_cao_tinh_hinh_tai_chinh_b01/              → B01-DN Bảng CĐKT (Script Report)
    bao_cao_kqhdkd_b02/                           → B02-DN KQHĐKD
    bao_cao_luu_chuyen_tien_te_b03/               → B03-DN LCTT
    thuyet_minh_bctc_b09/                          → B09-DN Thuyết minh
    to_khai_thue_gtgt_01/                          → Tờ khai GTGT 01/GTGT
    quyet_toan_tncn/                               → Quyết toán TNCN
    quyet_toan_tndn/                               → Quyết toán TNDN
    so_nhat_ky_chung/                              → Sổ Nhật ký chung
    so_cai/                                        → Sổ Cái (per account)
    so_chi_tiet_tai_khoan/                         → Sổ chi tiết tài khoản
    bang_can_doi_so_phat_sinh/                     → Bảng cân đối số phát sinh
    test_*.py                                      → tests colocated per report
erpnext/accounts/ ...                             → import/FX: extend controllers/doctypes as needed
erpnext/setup/setup_wizard/data/country_wise_tax.json → additional import-duty/TTĐB templates
tasks/plan.md, tasks/todo.md                      → regenerated after approval
SPEC.md                                           → this file
```

Each statutory report ships as a folder with `<name>.json` (Report doc, `report_type:
Script Report`), `<name>.py` (`execute(filters)`), and `test_<name>.py`.

## Code Style

Match surrounding ERPNext code: tabs, 110 cols, double quotes, `frappe._()` for
user-facing strings. Statutory reports map **Mã số → account balances** via an
explicit, reviewable table (never hard-coded magic in the query):

```python
# erpnext/regional/vietnam/report/bao_cao_kqhdkd_b02/bao_cao_kqhdkd_b02.py
import frappe
from frappe import _

from erpnext.regional.vietnam.utils import get_account_balances

# TT99 B02-DN — each line: (mã số, chỉ tiêu, account-number prefixes, sign).
# RESEARCH-DERIVED from TT99/TT200 lineage — VERIFY Mã số with kế toán before filing.
B02_LINES = (
	("01", "Doanh thu bán hàng và cung cấp dịch vụ", ["511"], +1),
	("02", "Các khoản giảm trừ doanh thu", ["521"], +1),
	("10", "Doanh thu thuần", ["511"], ["521"]),  # 01 - 02 (computed)
	("11", "Giá vốn hàng bán", ["632"], +1),
	# ...
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	balances = get_account_balances(filters.company, filters.from_date, filters.to_date)
	columns = [
		{"label": _("Mã số"), "fieldname": "ma_so", "fieldtype": "Data", "width": 70},
		{"label": _("Chỉ tiêu"), "fieldname": "chi_tieu", "fieldtype": "Data", "width": 360},
		{"label": _("Số tiền"), "fieldname": "so_tien", "fieldtype": "Currency", "width": 160},
	]
	data = [build_line(line, balances) for line in B02_LINES]
	return columns, data
```

Mapping tables live as module constants so an accountant can review them in one place.

## Testing Strategy

- **Framework:** `FrappeTestCase` (DB, rolled back) for report integration;
  `unittest` for pure mapping-table structure.
- **Location:** `test_<report>.py` colocated with each report.
- **Per-report integration test** (the core proof): create a VN company, post
  representative Journal Entries / Invoices, run the report, assert specific
  **Mã số lines carry the expected totals** and that the statement balances
  (e.g. B01 Tổng tài sản == Tổng nguồn vốn; B02 lợi nhuận ties to TK 911).
- **Structure tests:** every Mã số referenced maps to real TT99 accounts; no
  account is double-counted or orphaned across a statement.
- **Regression:** `run-tests --module erpnext.accounts...` and the Company suite
  stay green (foundation unchanged).
- **Test sizing:** majority small/structural; a few medium integration tests per
  report. Reuse the existing VN test helpers under
  `erpnext/accounts/doctype/account/chart_of_accounts/`.

## Boundaries

**Always**
- Work on a feature branch; TDD (RED→GREEN); one commit per task; tabs / 110 cols.
- Compute reports from the shared GL (Account / GL Entry); keep VND as company currency.
- Mark every statutory output **"draft — verify Mã số against TT99 before filing"**
  (in report description + a header note), per the "you research, I verify" decision.
- Run the accounts + company regression suites before each commit.

**Ask first**
- Changing shared GL / controller behavior that affects **all** companies on the site.
- Adding Custom Fields or DocTypes that **overlap** anything mvl_accounting defines.
- Any declaration that needs CIT / VAT-allocation numbers — confirm whether to read
  mvl_accounting's tables or compute independently.
- Adding a third-party dependency.

**Never**
- Reimplement mvl_accounting's period-close / CIT / VAT-allocation / consignment logic.
- Commit to `develop`; commit secrets; touch the pre-existing uncommitted local changes.
- Present a statutory report as filing-ready without the verification flag.
- Remove or skip existing ERPNext tests to make the suite pass.

## Success Criteria (specific, testable)

1. **B01-DN** renders in TT99 format; for a company with postings, **Tổng cộng
   tài sản == Tổng cộng nguồn vốn** (a test asserts equality) and key Mã số
   (100/200/270/300/400/440) carry correct account-range totals.
2. **B02-DN** renders; Mã số 10 (DT thuần), 20 (LN gộp), 50 (LN trước thuế),
   60 (LN sau thuế) compute correctly from 5xx/6xx/8xx and tie to TK 911.
3. **B03-DN** renders (direct or indirect method — chosen in plan) and net cash
   change ties to the movement of 111/112/113.
4. **B09-DN** renders the required note sections referencing the above.
5. **Tờ khai GTGT 01/GTGT**: output VAT (33311) and deductible input VAT (1331)
   totals for a period match the posted GTGT; số thuế phải nộp computed.
6. **Quyết toán TNCN / TNDN**: render with the expected líne items (TNDN reads
   CIT results per the resolved Open Question).
7. **Sổ Nhật ký chung / Sổ Cái / Sổ chi tiết / Bảng CĐSPS**: reconcile to GL
   Entry totals (a test asserts Sổ Cái balance == GL balance per account; Bảng
   CĐSPS debit total == credit total).
8. **Import & FX**: a USD purchase invoice with import duty + GTGT posts correct
   VND GL entries; tỷ giá revaluation posts to 413; vouchers print VND số-thành-chữ.
9. All new reports pass their tests; existing ERPNext accounts + company suites
   remain green; pre-commit clean.

## Open Questions

1. **B01-DN form:** TT99 uses "Báo cáo tình hình tài chính" — confirm whether
   Miyano files the full form or the SME (doanh nghiệp nhỏ và vừa) variant, as it
   changes the Mã số set. (Default assumption: full form.)
2. **B03-DN method:** direct (trực tiếp) vs indirect (gián tiếp) cash-flow. (Default: indirect.)
3. **TNDN finalization:** read CIT provisional / loss data from mvl_accounting
   (`mvl_cit_provisional`, `cit_loss_*`) or compute in the report? Affects coupling.
4. **Tờ khai GTGT** deduction: does Miyano use full deduction (khấu trừ toàn bộ)
   or need VAT input allocation (mvl `vat_input_allocation`) for mixed
   taxable/non-taxable sales of vật tư y tế?
5. **Exact Mã số tables** for every statement are research-derived (TT99/TT200
   lineage) pending accountant sign-off — the primary verification gate.
```
