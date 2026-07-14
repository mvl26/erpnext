# Implementation Plan — Miyano Complete VN Accounting (TT99/2025)

Source of truth: `SPEC.md`. Built **in `erpnext` core** under `erpnext/regional/vietnam/`.
Statutory Mã-số mappings are **research-derived and flagged for accountant
verification** (per the approved spec). Every statement/book ships with a
reconciliation test that proves the *engine* is correct (totals balance / tie to
the GL) even where exact line labels await sign-off.

## Architecture Decisions

- New VN regional module `erpnext/regional/vietnam/` (mirrors italy/uae pattern).
- All reports are **Script Reports** computed **read-only over the shared GL**
  (GL Entry / Account) — no reimplementation of mvl_accounting's period-close /
  CIT / VAT-allocation. Where a declaration needs CIT/VAT-allocation results it
  *reads* mvl_accounting data if present.
- Mã-số → account-range mappings live as **reviewable module constants**, not
  buried in queries, so a kế toán can audit them in one place.
- Shared helpers (GL fetch, per-account balances, số-thành-chữ) built once in
  `utils.py` and reused by every report.

## Phase 1 — Foundation (DONE, Tasks 1–5)

TT99 chart of accounts, operational default accounts, GTGT tax templates,
company currency default, standard-report compatibility. Shipped & committed.

## Phase 2 — Report engine + accounting books

- [x] **Task 6 — VN regional module + shared report utils.**
  Create `erpnext/regional/vietnam/{__init__,utils,constants}.py`. `utils.py`:
  `get_gl_entries(...)`, `get_account_balances(company, from, to)` (opening /
  movement / closing Dr-Cr per account & by number-prefix), `so_thanh_chu(amount)`
  (VND amount → Vietnamese words).
  - Acceptance: `so_thanh_chu(1_000_000) == "Một triệu đồng"` (and 0, lẻ, tỷ cases);
    `get_account_balances` returns correct Dr/Cr per account after a posting.
  - Verify: `run-tests --module erpnext.regional.vietnam.test_utils`.
  - Files: 4. Size M. Deps: none.

- [x] **Task 7 — Bảng cân đối số phát sinh (trial balance).**
  Per account: opening Dr/Cr, phát sinh Dr/Cr, closing Dr/Cr.
  - Acceptance: Σ phát sinh Nợ == Σ phát sinh Có; per-account closing = opening ± movement.
  - Verify: post JEs, assert balanced.
  - Files: 3 (report json + py + test). Size M. Deps: 6.

- [x] **Task 8 — Sổ Cái (general ledger, per account).**
  Entries for one account with running balance, TT99 layout.
  - Acceptance: ending balance == GL balance for that account.
  - Files: 3. Size S/M. Deps: 6.

- [ ] **Task 9 — Sổ chi tiết tài khoản.**
  Detailed ledger with party/voucher for a selected account.
  - Acceptance: reconciles to GL for the account + filters.
  - Files: 3. Size S/M. Deps: 6.

- [ ] **Task 10 — Sổ Nhật ký chung (general journal).**
  Chronological Dr/Cr of all vouchers for the period.
  - Acceptance: Σ Nợ == Σ Có; line count matches GL.
  - Files: 3. Size S/M. Deps: 6.

### Checkpoint: books reconcile to the GL

## Phase 3 — Statutory financial statements

- [ ] **Task 11 — B02-DN Báo cáo KQHĐKD (P&L).**
  Mã số from 5xx/6xx/7xx/8xx with computed subtotals (10/20/30/40/50/60).
  - Acceptance: 10=01−02, 20=10−11, 60=net; ties to TK 911 result.
  - Files: 3. Size M. Deps: 6.

- [ ] **Task 12 — B01-DN Báo cáo tình hình tài chính (balance sheet).**
  Tài sản (100…270) and Nguồn vốn (300/400/440); full form.
  - Acceptance: Mã số 270 (Tổng tài sản) == 440 (Tổng nguồn vốn).
  - Files: 3. Size M. Deps: 6, 11 (current-year profit).

- [ ] **Task 13 — B03-DN Lưu chuyển tiền tệ (indirect method).**
  - Acceptance: net cash flow == change in 111+112+113.
  - Files: 3. Size M. Deps: 6, 11.

- [ ] **Task 14 — B09-DN Thuyết minh BCTC.**
  Required note sections referencing B01/B02 key figures.
  - Acceptance: renders required sections; figures tie to B01/B02.
  - Files: 3. Size M. Deps: 11, 12.

### Checkpoint: B01 balances; B02 ties to 911

## Phase 4 — Tax declarations

- [ ] **Task 15 — Tờ khai thuế GTGT (01/GTGT).**
  Output VAT (33311) vs deductible input VAT (1331) for a period.
  - Acceptance: totals match posted GTGT; số thuế phải nộp = đầu ra − khấu trừ.
  - Files: 3. Size M. Deps: 6.

- [ ] **Task 16 — Quyết toán thuế TNCN.**
  PIT finalization from 3335 / payroll (hrms) where available.
  - Acceptance: renders; totals tie to 3335/334. (Flag: PIT source depends on payroll data.)
  - Files: 3. Size M. Deps: 6.

- [ ] **Task 17 — Quyết toán thuế TNDN.**
  CIT finalization; reads mvl_accounting CIT data if present, else 3334/8211/821.
  - Acceptance: renders; ties to 821/3334.
  - Files: 3. Size M. Deps: 6, 11.

### Checkpoint: GTGT totals match posted VAT

## Phase 5 — Import & foreign currency

- [ ] **Task 18 — Số-thành-chữ trên chứng từ.**
  Jinja/whitelisted method wrapping `so_thanh_chu`; wire into a voucher print format.
  - Acceptance: method returns VN words for an amount; usable from a print format.
  - Files: 2–3 (hooks jinja method + print format + test). Size S. Deps: 6.

- [ ] **Task 19 — Import purchase tax templates.**
  Add "Thuế nhập khẩu" (3333), "Thuế TTĐB nhập khẩu" (3332), "GTGT hàng nhập khẩu"
  (33312) purchase templates to the Vietnam entry in country_wise_tax.json.
  - Acceptance: a VN company gets these templates on the correct TT99 accounts.
  - Files: 2 (json + test). Size S/M. Deps: none (extends Task 3).

- [ ] **Task 20 — Đánh giá lại tỷ giá (exchange difference → 413).**
  Ensure a VN company's unrealized/realized FX difference is wired to 413/515/635.
  - Acceptance: VN company has an exchange-difference account set; test asserts wiring.
  - Files: 2–3. Size M. Deps: 1 (413 in chart).

### Checkpoint: Complete — all reports pass; accounts + company suites green

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Exact TT99 Mã số differ from research | High | Ship as draft + reconciliation tests + verification flag; mappings in one reviewable table |
| Overlap with mvl_accounting (CIT/VAT) | Med | Reports read-only over GL; consume mvl data, never recompute |
| PIT data lives in hrms/payroll | Med | Task 16 renders from available GL (3335); flag payroll dependency |
| Heavy company-creation tests slow suite | Low | Reuse one company per test class; keep integration tests few |

## Open Questions (defaults from SPEC.md; correct anytime)

1. B01 full form vs SME — default full.
2. B03 indirect vs direct — default indirect.
3. TNDN reads mvl_accounting CIT vs recompute — default read.
4. GTGT full deduction vs input allocation — default full deduction.
5. Exact Mã số tables — research-derived, accountant verifies before filing.
