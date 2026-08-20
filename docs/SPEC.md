# Spec: Miyano VN Accounting — Live Operation on ERPNext Core (Phase 13+)

> Status: **DRAFT — awaiting approval.** Phase 1 (Specify) of spec-driven development.
> Supersedes the previous SPEC ("Miyano Go-Live Readiness", Tasks 27–32 — now
> **shipped**: all 34 VN tests green, runbook in `docs/go_live_runbook.md`).
>
> **Direction decision (user, 2026-07-16):** continue the accounting build **in
> `erpnext` core**, NOT by installing `mvl_accounting`; cut over **early** on
> erpnext-only with **mid-year opening balances**. `mvl_accounting` (~7.4k lines of
> disk-only code, never installed on any site) is **parked**: treat it as a reference
> implementation to study/port ideas from, never as a runtime dependency. This
> consciously overrides the CLAUDE.md note routing VN accounting to
> `mvl_accounting` — that note gets amended once this spec is approved (ask first).

## Objective

Take company **Miyano** (site `miyano`) from "go-live-ready empty TT99 company" to
**operating legally and closing periods on ERPNext alone**:

- **Cut over mid-year**: opening balances as of the cutover date (default
  30/06/2026), real postings from the first day after.
- **Issue hóa đơn điện tử** (NĐ 70/2025) from Sales Invoices — provider integration
  behind an adapter, điều chỉnh/thay thế flows, full issuance log.
- **Print statutory vouchers** (Phụ lục I TT99): Phiếu thu 01-TT, Phiếu chi 02-TT,
  Phiếu nhập kho 01-VT, Phiếu xuất kho 02-VT — consuming the shipped
  `so_thanh_chu` helper (which currently has no consumer).
- **Complete the sổ sách set**: Sổ quỹ tiền mặt (S07-DN), Sổ tiền gửi ngân hàng
  (S08-DN), Sổ chi tiết công nợ theo đối tượng.
- **Close periods**: kết chuyển 5xx/6xx/7xx/8xx → 911 → 4212 as a generated,
  previewable JE set + period lock, wired into a month-end runbook section.
- **File taxes from ERPNext**: 01/GTGT XML export (HTKK/eTax) + bảng kê bán ra /
  mua vào.
- **Finish GĐ2-level gaps**: TT45 khung khấu hao defaults on the VN Asset
  Categories; sổ chi tiết nguyên tệ + TK 007-style FX view; per-employee TNCN
  surface on HRMS payroll data (soft dependency).

**Users:** Miyano kế toán / kế toán trưởng (daily ops, closing, filing), thủ quỹ
(phiếu thu/chi), thủ kho (phiếu nhập/xuất), and the dev team running the cutover.

**Success =** Miyano runs real business on ERPNext: a real Sales Invoice issues a
legal HĐĐT; phiếu thu/chi print in statutory format; month-end closes with 911
zeroed and the period locked; 01/GTGT exports as XML accepted by HTKK/eTax; the
mid-year opening trial balance validates and ties to control totals.

## Scope — five workstreams

**WS-A — Mid-year cutover support** (unblocks the early cutover)
- Extend the opening tooling + `validate_opening_balances` for a mid-year `as_of`
  date: balance-sheet-only opening TB with the H1 result landing in 4212 (default;
  see OQ-2), control totals as already shipped, runbook addendum for mid-year
  cutover (what the kế toán enters, what H1 reporting remains manual).

**WS-B — Hóa đơn điện tử (NĐ 70/2025)**
- Custom fields on Sales Invoice (số hóa đơn, ký hiệu, mã CQT, trạng thái, link to
  log) created idempotently by the VN setup hook.
- New `Vietnam E Invoice Log` DocType (issuance history, XML/PDF attachments,
  điều chỉnh/thay thế lineage).
- Provider-agnostic client + adapter per provider (VNPT-Invoice / Viettel SInvoice /
  M-Invoice — provider choice is OQ-1); a **mock adapter** ships first and is the
  only one tests use. Issuance triggers on SI submit, opt-in via a per-company
  setting; sandbox-first for any real adapter.
- Credentials live in `site_config.json`, never in code, fixtures, or git.

**WS-C — Sổ sách, chứng từ in, tax export**
- Reports: Sổ quỹ tiền mặt (S07-DN, thu/chi/tồn running balance on 111x), Sổ tiền
  gửi ngân hàng (S08-DN, per bank account on 112x), Sổ chi tiết công nợ (per party
  on 131/331/141/331x…).
- Print formats: Phiếu thu 01-TT / Phiếu chi 02-TT on Payment Entry, Phiếu nhập kho
  01-VT on Purchase Receipt/Stock Entry, Phiếu xuất kho 02-VT on Delivery Note/Stock
  Entry — VN layout, số-thành-chữ, chữ ký blocks.
- 01/GTGT **XML export** per the HTKK/eTax schema + bảng kê bán ra/mua vào
  (CSV/Excel). Keeps the shipped on-screen report as the source of numbers.

**WS-D — Khóa sổ & kết chuyển 911**
- `ket_chuyen_911(company, period)`: preview (list of closing lines) + execute
  (generated JE set closing 5xx/7xx and 6xx/8xx into 911, result → 4212);
  idempotent per period (re-run = no-op or explicit block); integrates with — does
  not replace — ERPNext's Period Closing Voucher / Accounting Period lock.
- Month-end checklist section added to the runbook (kết chuyển → verify 911 = 0 →
  lock period → run sổ sách/B01/B02).

**WS-E — GĐ2 remainder**
- TT45 useful-life defaults (khung khấu hao) applied to the VN Asset Categories.
- Sổ chi tiết nguyên tệ + TK 007-style FX exposure report (Exchange Rate
  Revaluation itself stays standard; 413 default already shipped).
- Per-employee TNCN report reading HRMS payroll tables **when hrms is installed**
  (degrade gracefully when absent) — upgrades the shipped company-level QT TNCN.

**Out of scope (explicitly)**
- Installing `mvl_accounting` or depending on its tables at runtime (the shipped
  best-effort read in `quyet_toan_tndn` stays as-is).
- BA-doc business features not selected for this phase: ký gửi bệnh viện (QT-03),
  MVL Contract / đấu thầu (QT-02), deferred revenue SaaS (QT-05), dự án 154 / vốn
  hóa 2415 (QT-06/07), báo cáo GDLK NĐ 132, thuế hoãn lại — future phases,
  revisit after the cutover settles.
- Running HRMS payroll itself (only the accounting/reporting surface on its data).
- Legacy TT200 data migration (greenfield — none).

## Tech Stack

Frappe v15 + ERPNext v15, site `miyano`, Python 3.12 (TABS, 110 cols, ruff, double
quotes), `FrappeTestCase`. Extends `erpnext/regional/vietnam/` and reuses
`_acct(company, number)` + `CHART_NAME`. XML via stdlib/`lxml` already available in
the bench — **new Python dependencies = ask first**. Print formats as regional
fixtures (Jinja), reports as Script Reports. E-invoice adapters do network I/O only
inside the adapter module; everything above them is pure and unit-testable.

## Commands

```bash
# Everything runs from the bench root /home/miyano/frappe-bench
bench --site miyano migrate                 # after DocType JSON / custom field changes
bench --site miyano clear-cache

# Workstream entry points (all whitelisted + bench-execute callable)
bench --site miyano execute erpnext.regional.vietnam.go_live.validate_opening_balances --kwargs "{'company':'Miyano','as_of':'2026-06-30'}"
bench --site miyano execute erpnext.regional.vietnam.period_close.ket_chuyen_911 --kwargs "{'company':'Miyano','period':'2026-07','preview':1}"
bench --site miyano execute erpnext.regional.vietnam.e_invoice.issue_e_invoice --kwargs "{'sales_invoice':'<name>'}"

# Tests (per workstream)
bench --site miyano run-tests --module erpnext.regional.vietnam.tests.test_go_live
bench --site miyano run-tests --module erpnext.regional.vietnam.tests.test_period_close
bench --site miyano run-tests --module erpnext.einvoice.tests.test_fast_end_to_end
bench --site miyano run-tests --module erpnext.regional.vietnam.tests.test_books_and_vouchers

# Lint
pre-commit run --all-files
```

## Project Structure

```
erpnext/regional/vietnam/
  go_live.py                → EXTEND: as_of/mid-year mode for opening validator + tooling
  period_close.py           → NEW: ket_chuyen_911 preview/execute + period-lock glue
  e_invoice.py              → NEW: settings, payload builder, issuance orchestration, log writer
  e_invoice_providers/      → NEW: adapter registry; mock.py first (tests), real adapter
                              (vnpt.py / viettel.py / minvoice.py) once OQ-1 is decided
  tt45.py                   → NEW: khung khấu hao TT45 (account/category → useful-life map)
  setup.py                  → EXTEND: e-invoice custom fields, TT45 wiring (idempotent)
  constants.py              → EXTEND: 911/4212, cash/bank prefixes reuse, e-invoice states
  test_period_close.py, test_e_invoice.py, test_books_and_vouchers.py, test_tt45.py → NEW
erpnext/regional/doctype/vietnam_e_invoice_log/   → NEW DocType (Italy precedent for layout)
erpnext/regional/report/
  so_quy_tien_mat/  so_tien_gui_ngan_hang/  so_chi_tiet_cong_no/   → NEW Script Reports
  to_khai_thue_gtgt_01/     → EXTEND: XML (HTKK/eTax) + bảng kê export
erpnext/regional/print_format/
  phieu_thu/  phieu_chi/  phieu_nhap_kho/  phieu_xuat_kho/         → NEW print formats
docs/go_live_runbook.md     → EXTEND: mid-year cutover addendum + month-end close +
                              e-invoice ops (sandbox → production switch)
```

## Code Style

Same conventions as the shipped VN module — accounts by **TT99 number** resolved at
runtime, idempotent + VN-guarded helpers, structured results (never raise on a "not
ready" state). New for this phase: network only inside provider adapters, pure
payload builders above them, secrets only from site config:

```python
def issue_e_invoice(sales_invoice_name):
	"""Issue a HĐĐT for a submitted Sales Invoice via the configured provider."""
	si = frappe.get_doc("Sales Invoice", sales_invoice_name)
	settings = get_e_invoice_settings(si.company)
	if not settings.enabled:
		return None
	provider = get_provider(settings.provider)      # adapter registry; "mock" in tests
	payload = build_invoice_payload(si)             # pure, unit-testable, no I/O
	result = provider.issue(payload)                # network I/O lives only here
	return log_issuance(si, result)                 # Vietnam E Invoice Log + SI fields
```

## Testing Strategy

- **Scratch company only** (never the real Miyano): existing helper builds a fresh
  VN company; each suite seeds its own entries.
- **E-invoice**: all tests run against the **mock adapter** — no network, no real
  credentials, ever. Payload builder covered by pure unit tests; điều chỉnh/thay thế
  lineage asserted on the log DocType.
- **Kết chuyển 911**: seed revenue + expense entries → preview lists the expected
  closing lines; execute zeroes 5xx–8xx and 911, books the result to 4212; re-run
  for the same period is a no-op/blocked; cancel path restores.
- **Mid-year opening**: balanced BS-only TB as of 30/06 → pass; unbalanced or
  non-TT99 → fail with the specific reason; control totals tie (131/331/15x).
- **Books**: sổ quỹ running balance equals GL closing balance for 111x on the same
  range; same for 112x and per-party 131/331.
- **Print formats**: render smoke via `frappe.get_print` — non-empty HTML containing
  the số-thành-chữ line.
- **XML export**: golden-file comparison against a hand-verified sample; schema
  validation when an XSD is available.
- **Regression**: all shipped VN suites (34 tests) + report suites stay green.

## Boundaries

**Always**
- Feature branch; TDD; tabs; accounts by TT99 **number** via `_acct`; idempotent,
  VN-guarded helpers; build & test on a **scratch** company first.
- E-invoice credentials only in `site_config.json`; tests only on the mock adapter.
- Before any action on the **real Miyano** (opening balances, period lock, enabling
  live e-invoice issuance): verified backup + explicit user confirmation.

**Ask first**
- Choosing/contracting the e-invoice provider; entering sandbox or production
  credentials anywhere.
- Posting real opening balances; locking a real period; issuing a real HĐĐT.
- Amending the CLAUDE.md app-boundary note (planned once this spec is approved).
- Adding any Python/JS dependency; changing semantics of already-shipped VN reports
  or naming series.
- Anything inside `mvl_accounting` (it has uncommitted local changes — hands off).

**Never**
- Commit credentials, tokens, or provider URLs with embedded secrets.
- Issue a real HĐĐT from a test, scratch company, or CI.
- Post an opening TB that doesn't net to zero or uses a non-TT99 account.
- Unlock/modify a closed period without kế toán trưởng sign-off.
- Commit to `develop`; touch pre-existing uncommitted changes in other apps.

## Success Criteria (specific, testable)

1. **WS-A**: `validate_opening_balances(company, as_of="2026-06-30")` passes on a
   balanced, fully-TT99, BS-only mid-year TB with tying control totals, and fails
   (with the reason) on unbalanced / non-TT99 / P&L-account input; runbook has a
   mid-year addendum.
2. **WS-B**: on a scratch company with e-invoice enabled and the mock provider,
   submitting an SI creates a `Vietnam E Invoice Log` with số/ký hiệu/mã CQT/XML and
   stamps the SI fields; điều chỉnh and thay thế create linked log entries; the repo
   contains zero credentials; live issuance requires per-company opt-in + real
   adapter + user confirmation.
3. **WS-C**: sổ quỹ/sổ TGNH/sổ công nợ each render on seeded data and tie to GL
   closing balances; all four phiếu print formats render with số-thành-chữ; 01/GTGT
   XML matches the golden file / validates against the schema.
4. **WS-D**: kết chuyển preview → execute zeroes 5xx–8xx and 911 with the result in
   4212 and locks the period; re-run is a no-op/blocked; month-end section exists in
   the runbook.
5. **WS-E**: VN Asset Categories carry TT45 useful lives after setup; sổ nguyên tệ /
   007 report renders; per-employee TNCN lists rows when HRMS payroll data exists
   and degrades gracefully when hrms is absent.
6. All shipped VN suites (34 tests) plus the new suites are green; `pre-commit`
   passes.

## Open Questions (defaults; correct anytime)

1. **OQ-1 — E-invoice provider**: VNPT-Invoice, Viettel SInvoice, or M-Invoice? Needs
   a contract + sandbox credentials. *Default: build adapter interface + mock now;
   the real adapter task stays blocked until the provider is chosen.*
2. **OQ-2 — Mid-year opening method**: BS-only TB with the H1-2026 result in 4212
   (default — simplest, but FY2026 B02/B03 from ERPNext then cover H2 only and H1
   must be combined manually at year-end), or replay cumulative H1 P&L movements so
   full-year statements come from ERPNext? **Kế toán trưởng decides.**
3. **OQ-3 — Cutover date**: số dư đến 30/06/2026 with July backfilled by kế toán
   (default), or 31/07/2026 clean start from August?
4. **OQ-4 — VAT filing cadence**: tháng or quý (default: quý) — drives the export
   cadence and the first-filing deadline in the runbook.
5. **OQ-5 — Draft mã-số sign-off**: the shipped B01/B02/B03/B09 mappings are
   research-derived and flagged "cần kế toán kiểm tra" — schedule kế toán trưởng
   verification as a runbook/UAT step (human task, not code).
6. **OQ-6 — Porting from `mvl_accounting`**: its disk-only `period_close`, VAT
   allocation, and payroll-mapping services are tested reference code by the same
   team. *Default: read for design, re-implement in erpnext idiom; never import
   from the app at runtime.*
