# Implementation Plan — Miyano Go-Live Readiness (Full Trading ERP on TT99)

Source of truth: `SPEC.md`. Built **in `erpnext` core**, extending
`erpnext/regional/vietnam/`. **Minimal, idempotent, VN-guarded** helpers +
validation/readiness commands, **plus a detailed VN go-live runbook**. Every helper
is built & tested on a **scratch** company first; every destructive step on the real
Miyano is gated behind a **verified backup + explicit user confirmation**.

## Architecture Decisions

- New module `erpnext/regional/vietnam/go_live.py` for config + validation +
  readiness; `role_profiles.py` and `master_data.py` for the fixture/seed helpers.
- Reuse the shipped `setup.py` `_acct(company, number)` resolver and `CHART_NAME`;
  reference every account by **TT99 number**, resolved at runtime.
- Every helper: **idempotent** (skip-if-set), **VN-guarded** (no-op unless
  `country == "Vietnam"`), callable via `bench execute`, key ones `@frappe.whitelist()`.
- Readiness/validation **return structured pass/fail** results — never raise on a
  "not ready" state.
- Greenfield: no migration code. Master data is entered manually per the runbook;
  code only **scaffolds** (taxonomy tree, import templates) and **validates**
  (completeness, opening-balance integrity).

## Prior phases (shipped, Tasks 1–26)

TT99 chart; operational Company defaults; GTGT/import tax; VND default; statutory
reports (B01/B02/B03/B09, tax declarations, sổ kế toán); số-thành-chữ; reusable VN
`setup(company)` hook; empty **Miyano** reconfigured onto TT99. A VN company is fully
TT99-wired end-to-end. This plan adds the **operational + go-live** layer.

## Phase 8 — Company & module configuration (config, low code)

- [x] **Task 27 — `configure_go_live(company)`: fiscal periods, stock policy, naming, formats.**
  Idempotent, VN-guarded helper that ensures: a Fiscal Year covering the go-live year
  (parameterized, open); perpetual inventory ON + a valuation method; VN naming series
  on Sales Invoice / Purchase Invoice / Journal Entry / Payment Entry / Delivery Note /
  Stock Entry; VND number/date format on the company. No hard-coded year.
  - Acceptance: SPEC success #1 — after run, all four config areas set; second run is a no-op.
  - Verify: `run-tests --module erpnext.regional.vietnam.test_go_live` (config + idempotency).
  - Files: `go_live.py`, `constants.py`, `test_go_live.py`. Size M. Deps: none (Tasks 21–26).

## Phase 9 — Users & permissions (minimal fixture code)

- [x] **Task 28 — `ensure_vn_role_profiles()`: VN Role Profiles.**
  Idempotently create six Role Profiles — Kế toán, Kế toán trưởng, Thủ kho, Bán hàng,
  Mua hàng, Quản lý — each mapped to the appropriate standard ERPNext roles (Accounts
  User/Manager, Stock User, Sales User, Purchase User, etc.). No real user accounts
  created (those are runbook steps, gated on user confirmation).
  - Acceptance: SPEC success #2 — six profiles exist with expected role sets; re-run no-op.
  - Files: `role_profiles.py`, `test_go_live.py`. Size S/M. Deps: none.

## Phase 10 — Master-data scaffolding (greenfield: seed tree + validate)

- [x] **Task 29 — Master-data taxonomy + completeness report + import templates.**
  `seed_item_group_taxonomy(company)`: create a thiết bị y tế / vật tư y tế Item Group
  tree (leaf groups inherit income 511 / expense 632 via existing defaults). Seed one
  default Warehouse, base UOMs, a default Price List, VN tax categories.
  `master_data_completeness(company)`: report flagging Customers/Suppliers missing MST
  (tax id) / address, and Items missing a default account resolution. Add CSV import
  templates under `docs/import_templates/`.
  - Acceptance: SPEC success #3 — taxonomy created; completeness flags a Customer
    missing MST; a complete master is not flagged.
  - Files: `master_data.py`, `docs/import_templates/`, `test_go_live.py`. Size M. Deps: 27.

## Phase 11 — Opening balances (FY-start)

- [x] **Task 30 — Opening-balance tooling + `validate_opening_balances(company)`.**
  Helper to post an **Opening Journal Entry** from a `{TT99 number: (dr, cr)}` mapping
  (resolved via `_acct`, `is_opening=Yes`). Validator asserts: the opening TB **nets to
  zero**; **every** opening entry uses a TT99-numbered account; control totals tie —
  AR total → 131, AP total → 331, stock value → 156 (and asset gross/accum-dep →
  211/2141 when present). Runbook documents entering AR/AP via **Opening Invoice
  Creation Tool**, stock via **Stock Reconciliation**, fixed assets via Asset records.
  - Acceptance: SPEC success #4 — validator fails on unbalanced TB / non-TT99 account;
    passes on a balanced, fully-TT99 opening TB with tying control totals.
  - Files: `go_live.py`, `constants.py`, `test_go_live.py`. Size M. Deps: 27.

## Phase 12 — Go-live readiness & cutover runbook

- [ ] **Task 31 — `go_live_readiness(company)` command (whitelisted + CLI).**
  Run all preconditions → structured checklist: on TT99, fiscal year open, Company
  defaults set, naming series present, perpetual inventory on, ≥1 warehouse, VN role
  profiles exist, opening TB balanced (delegates to Task 30), no numberless accounts,
  verified-backup marker present. Returns `{ok, checks:[{name, ok, detail}]}`; a thin
  formatter prints a readable pass/fail table for `bench execute`.
  - Acceptance: SPEC success #5 — all-green only when every precondition met; removing
    any one flips exactly that check to fail.
  - Files: `go_live.py`, `test_go_live.py`. Size M. Deps: 27–30.

- [ ] **Task 32 — Go-live runbook + checklist (docs).**
  `docs/go_live_runbook.md`: end-to-end VN cutover — pre-go-live **backup & verify**;
  `configure_go_live`; seed + import master data; enter opening balances (GL / AR / AP
  / stock / assets); `validate_opening_balances`; create users + assign role profiles;
  `go_live_readiness` all-green; set go-live date; **day-1 smoke tests** (post a real
  SI/PI, a payment, a stock movement); **rollback** via backup restore. Include a
  one-page printable checklist. Mostly docs; no automated test (manual review).
  - Acceptance: SPEC success #6 — runbook covers every stage with the exact commands;
    import templates referenced; rollback documented.
  - Files: `docs/go_live_runbook.md`, `docs/import_templates/`. Size M. Deps: 27–31.

### Checkpoint: `go_live_readiness("<scratch>")` is all-green after the runbook's
### scripted setup; the real-Miyano cutover is executed only after a verified backup
### and explicit user confirmation (never automatically).

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Opening balances entered wrong on real company | High | Validator (nets-to-zero, TT99-only, control totals) + backup + scratch-first + confirm |
| Naming series changed after documents exist | Med | Guard/warn in `configure_go_live`; runbook sets series before any document |
| Perpetual inventory toggled on a company with stock | Med | Guard: only configure on empty stock; ask-first otherwise |
| Overlap with mvl_accounting / assetcore masters | Med | Don't touch their overlays; seed only generic taxonomy; rely on Company defaults |
| Readiness "passes" but backup not actually taken | High | Backup marker is operator-set post-verify; runbook makes it a hard gate |
| Real user accounts created prematurely | Med | Task 28 creates only Role Profiles; real users are a runbook step gated on confirmation |

## Open Questions (defaults from SPEC.md)

1. Go-live fiscal year — parameterized, team confirms at cutover.
2. Item Group taxonomy — seed the tree, not the item catalog.
3. Opening counter account — full TB via equity (Temporary Opening only if staged).
4. Warehouses — one default kho; team adds the rest.
5. Role Profiles — the six generic VN roles; extend on request.
6. Backup marker — operator-set readiness note after taking + verifying a backup.
