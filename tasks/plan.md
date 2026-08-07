# Implementation Plan — Miyano VN Accounting: Live Operation on ERPNext Core (Phase 13+)

Source of truth: `SPEC.md` (Phase 13+, supersedes the shipped go-live spec). Direction
decided by the user 2026-07-16: build **in `erpnext` core**; `mvl_accounting` stays
**parked** (reference-only, never installed, never imported at runtime); **early
cutover** on erpnext-only with **mid-year opening balances**.

Prior phases (Tasks 1–32, shipped): TT99 chart + defaults + GTGT/import tax; statutory
reports (draft-flagged); số-thành-chữ; VN setup hook; go-live tooling + runbook. All
34 VN tests green at plan time.

## Architecture Decisions

- All new code in `erpnext/regional/vietnam/` (+ `erpnext/regional/doctype|report|
  print_format/` for artifacts), reusing `_acct(company, number)` / `CHART_NAME`.
- Every helper: **idempotent**, **VN-guarded**, TT99 accounts by **number**, structured
  results, `bench execute`-callable; key entry points `@frappe.whitelist()`.
- E-invoice: **adapter registry**; the `mock` adapter ships first and is the only one
  tests use; network I/O only inside adapters; credentials only in `site_config.json`.
  The real provider adapter (Task 45) is **blocked on OQ-1** (provider choice).
- Kết chuyển 911 **integrates with** (never replaces) Period Closing Voucher /
  Accounting Period; preview is pure computation, execute posts JEs.
- Mid-year opening default (OQ-2): **BS-only TB, H1 result in 4212**; the `as_of`
  parameter keeps FY-start behavior intact (backward compatible).
- No task in this plan touches the **real Miyano** company — code + scratch-company
  tests + docs only. Real cutover actions remain gated (backup + explicit confirm).

## Task List

### Phase 13 — Mid-year cutover support (WS-A)

- [ ] **Task 33 — Mid-year `as_of` mode for opening tooling + validator.**
  Extend `post_opening_journal_entry` / `validate_opening_balances` with optional
  `as_of` (posting date ≠ FY start): BS-only mode — any P&L (5xx–8xx) account in the
  opening TB fails validation with a specific reason; H1 result expected in 4212;
  control totals unchanged; `go_live_readiness` passes `as_of` through.
  - Acceptance: SPEC success #1 — balanced BS-only TB as of 2026-06-30 passes;
    unbalanced / non-TT99 / P&L-account input fails with the reason; FY-start
    behavior (no `as_of`) unchanged — all 34 existing tests stay green.
  - Verify: `run-tests --module erpnext.regional.vietnam.test_go_live`
  - Files: `go_live.py`, `constants.py`, `test_go_live.py`. Size M. Deps: none.

- [ ] **Task 34 — Runbook addendum: mid-year cutover.**
  `docs/go_live_runbook.md` gains a "Cutover giữa năm" section: what the kế toán
  enters (BS-only TB, số dư 30/06), July backfill, what H1 reporting stays manual
  (per OQ-2 default), exact commands with `as_of`.
  - Acceptance: section exists, commands copy-paste runnable, OQ-2/OQ-3 defaults stated.
  - Verify: manual review (docs-only).
  - Files: `docs/go_live_runbook.md`. Size S. Deps: 33.

### Phase 14 — Chứng từ in & sổ sách (WS-C, part 1 — needed day 1)

- [ ] **Task 35 — Print formats Phiếu thu 01-TT + Phiếu chi 02-TT.**
  Jinja print formats on Payment Entry (receive → thu, pay → chi), Phụ lục I TT99
  layout: company header, số phiếu, người nộp/nhận, lý do, amount + **số-thành-chữ**
  (first real consumer of `so_thanh_chu`), chữ ký blocks. Installed idempotently by
  the VN setup hook.
  - Acceptance: SPEC success #3 (vouchers) — `frappe.get_print` renders non-empty HTML
    containing the amount-in-words for a scratch Payment Entry, both directions.
  - Verify: `run-tests --module erpnext.regional.vietnam.test_books_and_vouchers`
  - Files: `erpnext/regional/print_format/phieu_thu/`, `.../phieu_chi/`, `setup.py`,
    `test_books_and_vouchers.py` (new). Size M. Deps: none.

- [ ] **Task 36 — Print formats Phiếu nhập kho 01-VT + Phiếu xuất kho 02-VT.**
  Same pattern on Purchase Receipt/Stock Entry (nhập) and Delivery Note/Stock Entry
  (xuất): item table (mã, tên, ĐVT, SL, đơn giá, thành tiền), totals + số-thành-chữ.
  - Acceptance: renders for a scratch stock document of each type.
  - Verify: same module.
  - Files: `.../phieu_nhap_kho/`, `.../phieu_xuat_kho/`, `setup.py`,
    `test_books_and_vouchers.py`. Size M. Deps: 35 (shared layout conventions).

- [ ] **Task 37 — Report Sổ quỹ tiền mặt (S07-DN).**
  Script Report over GL on `111*`: ngày, số phiếu (voucher link), diễn giải, thu,
  chi, tồn (running balance from opening); filters company/account/date range.
  - Acceptance: SPEC success #3 (books) — closing tồn equals GL closing balance for
    the same range on seeded entries.
  - Verify: same module.
  - Files: `erpnext/regional/report/so_quy_tien_mat/`, `utils.py` (shared row
    builder), `test_books_and_vouchers.py`. Size M. Deps: none.

- [ ] **Task 38 — Report Sổ tiền gửi ngân hàng (S08-DN).**
  Same shape on `112*`, grouped/filterable per bank account (child of 112).
  - Acceptance: per-account running balance ties to GL closing.
  - Verify: same module.
  - Files: `erpnext/regional/report/so_tien_gui_ngan_hang/`, `test_books_and_vouchers.py`.
    Size S. Deps: 37 (reuses the row builder).

- [ ] **Task 39 — Report Sổ chi tiết công nợ theo đối tượng.**
  Per-party ledger on `131/331` (+ other party-linked TT99 accounts): opening /
  movements / closing per party with voucher rows; filters company/party type/party/
  account/date.
  - Acceptance: per-party closing ties to GL with party filter; party missing on a
    131/331 row is surfaced (consistent with shipped opening validator rule).
  - Verify: same module.
  - Files: `erpnext/regional/report/so_chi_tiet_cong_no/`, `test_books_and_vouchers.py`.
    Size M. Deps: 37.

### Checkpoint A (after 33–39)
- [ ] Full VN regression green (all suites); pre-commit clean; phiếu formats render;
      books tie to GL. Cutover day-1 paper needs are covered.

### Phase 15 — Hóa đơn điện tử (WS-B — mock-first; real adapter blocked on OQ-1)

- [ ] **Task 40 — E-invoice settings + custom fields (setup hook).**
  Idempotent custom fields: Company (e-invoice enabled, provider, ký hiệu mẫu/serial
  defaults) and Sales Invoice (số HĐĐT, ký hiệu, mã CQT, trạng thái, link to log) —
  created by the VN setup hook, VN-guarded.
  - Acceptance: fields exist after `setup()` on a scratch VN company; re-run no-op;
    non-VN company untouched.
  - Verify: `run-tests --module erpnext.regional.vietnam.test_e_invoice`
  - Files: `setup.py`, `constants.py`, `test_e_invoice.py` (new). Size M. Deps: none.

- [ ] **Task 41 — DocType `Vietnam E Invoice Log`.**
  Log DocType (module Regional): SI link, provider, payload snapshot, số/ký hiệu/mã
  CQT, trạng thái (draft/issued/adjusted/replaced/cancelled), XML/PDF attachments,
  lineage links (adjusts / replaces).
  - Acceptance: DocType installs via migrate; basic CRUD + status transitions tested.
  - Verify: same module + `bench --site miyano migrate` clean.
  - Files: `erpnext/regional/doctype/vietnam_e_invoice_log/` (json/py/tests hook).
    Size M. Deps: none.

- [ ] **Task 42 — Payload builder + adapter registry + mock adapter.**
  `build_invoice_payload(si)` pure (party, MST, lines, thuế suất per GTGT template,
  totals, số-thành-chữ); `get_provider(name)` registry; `providers/mock.py` returns
  deterministic số/ký hiệu/mã CQT + echo XML.
  - Acceptance: payload unit-tested against a scratch SI (totals/tax match SI);
    unknown provider → clear error; mock issue() round-trips.
  - Verify: same module.
  - Files: `e_invoice.py`, `e_invoice_providers/__init__.py`, `.../mock.py`,
    `test_e_invoice.py`. Size M. Deps: 40.

- [ ] **Task 43 — Issuance orchestration on SI submit.**
  `issue_e_invoice(si)` wired via hooks (`doc_events` on Sales Invoice on_submit):
  opt-in per company setting; writes the log, stamps SI fields; failure leaves SI
  submitted but logs the error state (never blocks accounting on provider downtime —
  retry path via whitelisted method).
  - Acceptance: SPEC success #2 — submit on enabled scratch company + mock → log
    created, SI stamped; disabled company → no-op; provider error → SI stays
    submitted, log records failure, retry succeeds.
  - Verify: same module + full VN regression.
  - Files: `e_invoice.py`, `erpnext/hooks.py`, `test_e_invoice.py`. Size M. Deps: 41, 42.

- [ ] **Task 44 — Điều chỉnh / thay thế flows.**
  Issue adjustment (hóa đơn điều chỉnh, from a return/credit-note SI) and replacement
  (hóa đơn thay thế) via the provider; lineage recorded on the log (adjusts/replaces
  links); original log status updated.
  - Acceptance: lineage chain asserted across the log records; statuses correct.
  - Verify: same module.
  - Files: `e_invoice.py`, `test_e_invoice.py`, log DocType json (links). Size M.
    Deps: 43.

- [ ] **Task 45 — Real provider adapter + sandbox verification. [BLOCKED: OQ-1]**
  Implement `providers/<chosen>.py` against the chosen provider's sandbox; manual
  sandbox round-trip documented. **Do not start** until the provider + sandbox
  credentials exist (user provides; credentials only in `site_config.json`).
  - Acceptance: sandbox issuance round-trip verified manually; zero secrets in git.
  - Files: `e_invoice_providers/<provider>.py`, docs. Size M. Deps: 43 + OQ-1.

### Checkpoint B (after 40–44; 45 pending OQ-1)
- [ ] SI submit on scratch issues via mock end-to-end; regression green. The moment a
      provider is chosen, only Task 45 remains for legal issuance.

### Phase 16 — Khóa sổ & kết chuyển 911 (WS-D — needed first month-end)

- [ ] **Task 46 — `period_close.py`: kết chuyển preview (pure).**
  `ket_chuyen_911(company, period, preview=1)`: compute closing lines from GL for the
  period — Dr 5xx/7xx → 911, 911 → Cr 6xx/8xx, net → 4212 — returning a structured
  line list + expected 911 zero-check; no writes.
  - Acceptance: on seeded revenue+expense scratch data, preview lists exactly the
    expected lines and net result; empty period → empty preview, ok:true.
  - Verify: `run-tests --module erpnext.regional.vietnam.test_period_close`
  - Files: `period_close.py` (new), `constants.py`, `test_period_close.py` (new).
    Size M. Deps: none.

- [ ] **Task 47 — Kết chuyển execute + period lock (idempotent).**
  `preview=0`: post the JE set (marked, linked to period), verify 911 nets to zero
  after posting, then create/close the **Accounting Period** for the month; re-run
  for a closed period → structured "already closed" (no duplicate JEs); cancel path
  documented (unlock = kế toán trưởng, ask-first).
  - Acceptance: SPEC success #4 — 5xx–8xx and 911 zero after execute; result in 4212;
    period locked (posting into it blocked); re-run no-op.
  - Verify: same module + full VN regression.
  - Files: `period_close.py`, `test_period_close.py`. Size M. Deps: 46.

- [ ] **Task 48 — Runbook: month-end close section.**
  Kết chuyển → verify 911=0 → lock → run sổ sách/B01/B02 checklist, with commands.
  - Acceptance: section exists with copy-paste commands; ask-first gates stated.
  - Verify: manual review (docs-only).
  - Files: `docs/go_live_runbook.md`. Size S. Deps: 47.

### Phase 17 — Kê khai & export (WS-C, part 2 — needed first filing)

- [ ] **Task 49 — Bảng kê bán ra / mua vào export.**
  Whitelisted export from the 01/GTGT data source: bảng kê hóa đơn bán ra & mua vào
  (số/ký hiệu/ngày HĐ, MST, tên đối tác, doanh số, thuế suất, tiền thuế) as CSV/XLSX.
  - Acceptance: export rows tie to the on-screen report totals on seeded data.
  - Verify: `run-tests --module erpnext.regional.report.to_khai_thue_gtgt_01.test_to_khai_thue_gtgt_01`
  - Files: `to_khai_thue_gtgt_01/` (+small util), tests. Size M. Deps: none
    (uses shipped report; e-invoice fields from Task 40 enrich rows when present).

- [ ] **Task 50 — 01/GTGT XML export (HTKK/eTax).**
  Build the declaration XML per the HTKK 01/GTGT schema (golden sample checked in,
  hand-verified); numbers come from the shipped report; schema-validate when an XSD
  is available.
  - Acceptance: SPEC success #3 (XML) — output matches the golden file on seeded
    data; malformed/mixed-company input → structured error.
  - Verify: same module.
  - Files: `to_khai_thue_gtgt_01/`, golden file under the report dir, tests. Size M.
    Deps: 49. **Risk:** exact schema version — flag output "cần kế toán kiểm tra
    trước khi nộp" (OQ-5 pattern) until KTT signs off.

### Phase 18 — GĐ2 remainder (WS-E)

- [ ] **Task 51 — TT45 khung khấu hao defaults.**
  `tt45.py`: TT45 useful-life map for the VN Asset Categories (+ any new standard
  categories); setup hook applies `total_number_of_depreciations`/frequency
  idempotently; existing categories with explicit values untouched.
  - Acceptance: SPEC success #5 — categories carry TT45 lives after setup; re-run
    no-op; user-modified values preserved.
  - Verify: `run-tests --module erpnext.regional.vietnam.test_tt45`
  - Files: `tt45.py` (new), `setup.py`, `test_tt45.py` (new). Size M. Deps: none.

- [ ] **Task 52 — Sổ chi tiết nguyên tệ + TK 007-style FX view.**
  Report: per foreign-currency account (1122/1312/3312/341…) rows in nguyên tệ +
  VND, running balances both currencies (007-style memo view for cash accounts).
  - Acceptance: on seeded multi-currency entries, nguyên tệ and VND balances tie to
    GL `debit/credit_in_account_currency` vs base amounts.
  - Verify: `run-tests --module erpnext.regional.vietnam.test_books_and_vouchers`
  - Files: `erpnext/regional/report/so_chi_tiet_nguyen_te/`, tests. Size M. Deps: none.

- [ ] **Task 53 — Per-employee TNCN surface (HRMS soft dependency).**
  Upgrade QT TNCN: when `hrms` tables exist, list per-employee taxable income / TNCN
  withheld (reads Salary Slip data); when absent, degrade to the shipped
  company-level GL summary with a notice. No hard import of hrms at module load.
  - Acceptance: SPEC success #5 — rows appear with seeded hrms data; graceful
    degradation asserted by simulating absence.
  - Verify: `run-tests --module erpnext.regional.report.quyet_toan_tncn.test_quyet_toan_tncn`
  - Files: `quyet_toan_tncn/`, tests. Size M. Deps: none.

### Checkpoint C — Complete
- [ ] All new suites + all shipped VN suites (34) green; `pre-commit run --all-files`
      clean; `bench --site miyano migrate` clean; runbook covers mid-year cutover +
      month-end + e-invoice ops. Task 45 explicitly reported if still blocked.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| E-invoice provider undecided (OQ-1) | High (legal for real sales) | Adapter architecture: everything but Task 45 proceeds on mock; real adapter is one bounded task once chosen |
| HTKK/eTax XML schema drift or wrong version | High (rejected filing) | Golden-file + XSD when available; draft-flag output until kế toán trưởng verifies first filing |
| Mid-year opening method disputed later (OQ-2) | Med | Parameterized `as_of`, BS-only default; decision recorded in runbook; KTT sign-off before real entry |
| Kết chuyển posts wrong JE set on real data | High | Preview-first API; scratch-only tests; execute on real Miyano is a runbook step behind backup + confirm |
| Duplication drift vs parked `mvl_accounting` | Med | Reference-only rule (OQ-6); never import; note ported design decisions in commit messages |
| Provider downtime blocking sales postings | Med | Issuance failure never blocks SI submit; error state + retry method |
| hrms absent/renamed tables break TNCN report | Low | Soft dependency, runtime capability check, graceful degrade (tested) |

## Open Questions (defaults from SPEC.md)

1. **OQ-1** provider HĐĐT — Task 45 blocked until chosen; mock unblocks the rest.
2. **OQ-2** mid-year opening — default BS-only + H1 result in 4212; KTT decides.
3. **OQ-3** cutover date — default số dư 30/06/2026, July backfill.
4. **OQ-4** VAT cadence — default quý; runbook states both.
5. **OQ-5** draft mã-số sign-off — human runbook/UAT step, not code.
6. **OQ-6** mvl_accounting — read for design only; re-implement in erpnext idiom.
