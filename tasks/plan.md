# Implementation Plan — Make TT99 the Default Accounting Everywhere (Miyano)

Source of truth: `SPEC.md`. Built **in `erpnext` core**. A reusable, idempotent,
VN-guarded `setup(company)` hook wires every module/master-data account link to
the correct TT99 account number; then a guarded patch switches the empty Miyano
company onto TT99.

## Architecture Decisions

- Hook lives at `erpnext/regional/vietnam/setup.py` (`setup(company)`), dispatched
  by ERPNext's `install_country_fixtures` on VN company creation and callable
  standalone (used by the Miyano patch).
- Every wiring step is **idempotent** (skip if already set) and **VN-guarded**.
- Accounts referenced by **number**, resolved to the company's account at runtime.
- Company-level defaults are already TT99 (prior phase); this phase adds the
  master-data layer + reconfigures Miyano.

## Prior phases (done): TT99 chart, operational defaults, GTGT/import tax, VND
default, statutory reports (B01/B02/B03/B09, tax declarations, sổ kế toán),
số-thành-chữ, unrealized FX → 413.

## Phase 6 — Default module wiring (reusable hook)

- [x] **Task 21 — VN setup hook + Mode of Payment accounts.**
  Create `erpnext/regional/vietnam/setup.py` `setup(company)`; wire Mode of Payment
  Cash.default_account → 111, Bank → 112. Confirm dispatch on VN company creation.
  - Acceptance: after creating a VN company, Cash MoP → 111 and Bank MoP → 112.
  - Verify: `run-tests --module erpnext.regional.vietnam.test_setup`.
  - Files: setup.py, test_setup.py (+ maybe company.py/hook). Size M. Deps: none.

- [ ] **Task 22 — Default Asset Categories on TT99.**
  `_create_asset_categories`: "Tài sản cố định hữu hình" (fixed 211, hao mòn 2141,
  chi phí khấu hao 6424, CWIP 2411) and "Tài sản cố định vô hình" (213, 2143, 6424,
  2411).
  - Acceptance: both Asset Categories exist with per-company accounts on those numbers.
  - Files: setup.py, test_setup.py. Size M. Deps: 21.

- [ ] **Task 23 — Item Group defaults resolve to TT99.**
  `_wire_item_group_defaults`: set "All Item Groups" item_group_defaults for the VN
  company → income 511, expense 632.
  - Acceptance: a new Item on the VN company resolves income 511 / expense 632.
  - Files: setup.py, test_setup.py. Size M. Deps: 21.

- [ ] **Task 24 — End-to-end invoice posting on TT99.**
  Integration proof (fix any gaps): a Sales Invoice posts Dr 131 / Cr 511 / Cr
  33311 (GTGT đầu ra); a Purchase Invoice posts Dr 632|156 / Dr 1331 / Cr 331.
  - Acceptance: the GL entries hit the expected TT99 accounts.
  - Files: test_setup.py (+ fixes if needed). Size M. Deps: 21, 22, 23.

- [ ] **Task 25 — Idempotency + auto-dispatch.**
  `setup(company)` run twice → no duplicates/errors; and it fires automatically for
  a newly-created VN company (not only when called explicitly).
  - Acceptance: second run is a no-op; a fresh VN company already has MoP/asset
    categories/item-group defaults without an explicit setup() call.
  - Files: setup.py, test_setup.py. Size S/M. Deps: 21-23.

### Checkpoint: a fresh VN company is fully TT99-wired end-to-end.

## Phase 7 — Reconfigure Miyano

- [ ] **Task 26 — Switch the empty Miyano company to TT99 (guarded patch).**
  `erpnext/patches/.../reconfigure_miyano_to_tt99.py`: guard that the company is
  empty (0 GL/stock/party/item/asset); **back up** the old account list to a file;
  delete the English accounts; rebuild the chart on the VN template; re-run
  set_default_accounts + `setup(company)`; verify no numberless account remains.
  **Build and test on a scratch company first; apply to the real Miyano only after
  explicit user confirmation** (irreversible DB change).
  - Acceptance: Miyano.chart_of_accounts = VN chart; default_receivable 131,
    default_payable 331, default_inventory 156, default_expense 632, default_income
    511; zero numberless accounts; backup file written.
  - Files: patch + patches.txt + test. Size M. Deps: 21-25.

### Checkpoint: Complete — Miyano on TT99; all defaults & suites green.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Destructive chart swap on a real company | High | Guard on emptiness; back up; test on scratch; confirm before apply |
| install_country_fixtures dispatch differs | Med | Verify mechanism in Task 21; fall back to explicit call in company setup |
| Overlap with mvl_accounting party/master | Med | Don't touch mvl overlays; rely on company defaults |
| Idempotency (dup asset categories / MoP rows) | Med | Skip-if-exists guards + Task 25 test |

## Open Questions (defaults from SPEC.md)

1. Asset Categories: generic hữu hình (211) + vô hình (213) — default.
2. Warehouse accounts: leave fallback to 156 — default.
3. Party accounts: rely on company 131/331 — default.
4. mvl_accounting overlays untouched.
5. Miyano switch: delete-accounts-and-rebuild in place — default.
