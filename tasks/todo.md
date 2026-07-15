# TODO — Miyano Go-Live Readiness (Full Trading ERP on TT99)

Prior phases (Tasks 1–26) shipped: TT99 chart, operational defaults, GTGT/import
tax, VND default, statutory reports, số-thành-chữ, VN `setup()` hook, Miyano
reconfigured onto TT99. This phase makes site `miyano` **ready to go live** on the
full trading ERP (greenfield, opening balances at FY start, minimal code + runbook).
See `SPEC.md` and `tasks/plan.md` for acceptance criteria and dependencies.

## Phase 8 — Company & module configuration
- [ ] Task 27 — `configure_go_live(company)`: Fiscal Year + periods, perpetual inventory + valuation, VN naming series (SI/PI/JE/PE/DN/Stock Entry), VND formats — idempotent, VN-guarded

## Phase 9 — Users & permissions
- [ ] Task 28 — `ensure_vn_role_profiles()`: six VN Role Profiles (kế toán, kế toán trưởng, thủ kho, bán hàng, mua hàng, quản lý) → ERPNext roles, idempotent

## Phase 10 — Master-data scaffolding (greenfield)
- [ ] Task 29 — Item Group taxonomy (thiết bị & vật tư y tế) + default kho/UOM/price list/tax categories; `master_data_completeness()` report; CSV import templates

## Phase 11 — Opening balances (FY start)
- [ ] Task 30 — Opening JE tooling + `validate_opening_balances(company)` (nets to zero, 100% TT99, AR=131/AP=331/stock=156 control totals)

## Phase 12 — Go-live readiness & cutover
- [ ] Task 31 — `go_live_readiness(company)` command (whitelisted + CLI): full precondition checklist → structured pass/fail
- [ ] Task 32 — `docs/go_live_runbook.md` end-to-end VN cutover + one-page checklist + import templates

## Go-live gate (not a code task)
- [ ] Real Miyano cutover: verified backup + all-green readiness + **explicit user confirmation** before any real opening balance / config is entered on the live company
