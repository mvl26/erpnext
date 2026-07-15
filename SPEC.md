# Spec: Miyano Go-Live Readiness — Full Trading ERP on TT99 (Phase 8+)

> Status: **DRAFT — awaiting approval.** Phase 1 (Specify) of spec-driven development.
> Supersedes the previous SPEC ("Make TT99 the Default Accounting Everywhere",
> Tasks 21–26, now **shipped** — see git). The TT99 accounting *foundation* is done;
> this phase makes site `miyano` ready to **go live** on the full trading ERP.

## Objective

Bring site `miyano` to **production go-live** for Công ty TNHH Miyano Việt Nam on
the **full trading ERP** — Kế toán + Kho + Bán hàng + Mua hàng + Tài sản cố định —
as a **greenfield** deployment (no legacy system to migrate; master data & opening
balances are entered fresh), with **opening balances at fiscal-year start**.

Deliver **minimal supporting code** (idempotent, VN-guarded config helpers +
validation/readiness commands + a small permission/taxonomy fixture) **plus a
detailed VN go-live runbook**. The goal is a repeatable, verifiable path from
"empty TT99-wired company" to "first real invoice posted on day 1", with every
precondition checkable and every destructive step on the real company gated behind
a backup + explicit confirmation.

**Users:** Miyano's kế toán / kế toán trưởng, thủ kho, nhân viên bán/mua hàng, and
the medcons.vn dev/deployment team running the cutover.

**Success =** running one `go_live_readiness("Miyano")` command prints an all-green
checklist — company on TT99, fiscal year open, defaults + naming series + perpetual
inventory configured, role profiles present, opening trial balance balanced and
100% TT99-numbered, control totals (AR=131, AP=331, stock=156) tie out, verified
backup — and the runbook has walked the team through entering real data to reach it.

## Prior work (shipped, on this branch)

TT99 chart of accounts; Company-level operational defaults (111/112/131/331/632/156/
2141/6424/2411/413…); GTGT + import tax templates; VND default; statutory reports
(B01/B02/B03/B09, tax declarations, sổ kế toán); số-thành-chữ; reusable VN
`setup(company)` hook (Mode of Payment, Asset Categories, item-group defaults,
idempotent + auto-dispatched); the empty **Miyano** company reconfigured onto TT99.
So a VN company is **fully TT99-wired end-to-end**. This phase does not re-do any of
that — it configures the *operational* layer (fiscal periods, naming, stock policy,
users, opening balances) and validates readiness.

## Scope

**In scope**
- Company/module **configuration** for operation: Fiscal Year + periods, perpetual
  inventory + valuation, VN document naming series, VND/number/date formats.
- **Users & permissions**: VN Role Profiles (kế toán, kế toán trưởng, thủ kho, bán
  hàng, mua hàng, quản lý) mapped to ERPNext roles.
- **Master-data scaffolding** (greenfield): Item Group taxonomy for thiết bị & vật
  tư y tế, UOMs, Warehouses, Price Lists, Tax categories; **import templates** (CSV)
  + a **completeness report** for manually-entered Customers/Suppliers/Items.
- **Opening balances** at FY start: tooling + a **validator** (TB nets to zero,
  every account TT99-numbered, AR/AP/stock/asset control totals tie out).
- **Go-live readiness command** + **cutover runbook** (docs/).

**Out of scope (explicitly)**
- Legacy data **migration** (greenfield — none).
- New business-domain features (medical-device lifecycle → `assetcore`; VN
  compliance overlays → `mvl_accounting`; e-invoicing → a later phase).
- Changing anything already shipped in the TT99 foundation.

## Tech Stack

Frappe v15 + ERPNext v15, site `miyano`, Python 3.12 (TABS, 110 cols, ruff, double
quotes), `FrappeTestCase`. Config helpers extend the existing
`erpnext/regional/vietnam/` module and reuse its `_acct(company, number)` resolver
and `CHART_NAME` constant. Readiness/validation are `@frappe.whitelist()` +
`bench execute`-callable. Docs are Markdown under `docs/`.

## Commands

```bash
# Configure + validate on a scratch/real company
bench --site miyano execute erpnext.regional.vietnam.go_live.configure_go_live --kwargs "{'company':'Miyano'}"
bench --site miyano execute erpnext.regional.vietnam.go_live.validate_opening_balances --kwargs "{'company':'Miyano'}"
bench --site miyano execute erpnext.regional.vietnam.go_live.go_live_readiness --kwargs "{'company':'Miyano'}"

# Tests
bench --site miyano run-tests --module erpnext.regional.vietnam.test_go_live

# Standard
bench --site miyano migrate
bench --site miyano console
pre-commit run --all-files
```

## Project Structure

```
erpnext/regional/vietnam/
  go_live.py          → configure_go_live(company): idempotent, VN-guarded config
                        (fiscal year/periods, perpetual inventory + valuation,
                        naming series, VND/number formats).
                        validate_opening_balances(company): TB balances to zero,
                        all TT99-numbered, AR=131/AP=331/stock=156 control totals.
                        go_live_readiness(company): full precondition checklist →
                        structured pass/fail result (whitelisted + CLI).
  role_profiles.py    → ensure_vn_role_profiles(): idempotent VN Role Profiles
                        (kế toán / kế toán trưởng / thủ kho / bán hàng / mua hàng /
                        quản lý) mapped to standard ERPNext roles.
  master_data.py      → seed_item_group_taxonomy(company) for thiết bị & vật tư y
                        tế; master_data_completeness(company) report (flag missing
                        MST/tax id, address, default accounts).
  constants.py        → extend with naming-series + opening-balance constants.
  test_go_live.py     → scratch-company tests for all of the above.
docs/
  go_live_runbook.md  → end-to-end VN cutover runbook (backup → config → master
                        data → opening balances → validate → go-live → day-1 smoke
                        → rollback), with a one-page checklist.
  import_templates/   → CSV templates for Customers / Suppliers / Items.
```

## Code Style

Same conventions as the shipped VN module: reference accounts by **TT99 number**,
resolve to the company's account at runtime via `_acct(company, number)` — never
hard-code company-suffixed names. Every helper is **idempotent** (skip-if-set) and
**VN-guarded** (no-op unless `country == "Vietnam"`). Readiness/validation return a
structured result, never raise on a "not ready" state:

```python
def go_live_readiness(company):
	"""Return a pass/fail checklist of go-live preconditions for a VN company."""
	if frappe.db.get_value("Company", company, "country") != "Vietnam":
		return {"ok": False, "checks": [{"name": "country", "ok": False, "detail": "not VN"}]}
	checks = [
		_check_on_tt99(company),
		_check_fiscal_year_open(company),
		_check_defaults_set(company),
		_check_naming_series(company),
		_check_perpetual_inventory(company),
		_check_role_profiles(),
		_check_opening_balanced(company),   # delegates to validate_opening_balances
		_check_backup_marker(company),
	]
	return {"ok": all(c["ok"] for c in checks), "checks": checks}
```

## Testing Strategy

- **Scratch company** (never the real Miyano): a helper builds a fresh VN company,
  runs `setup()` + `configure_go_live()`, and tests assert the config landed
  (fiscal year exists, perpetual inventory on, naming series present) and is
  **idempotent** (second run = no change/no duplicates).
- **Opening-balance validator**: post a **balanced** TT99 opening TB → validator
  passes; post an **unbalanced** TB, or one using a **non-TT99** account → validator
  fails with a specific reason. Control totals: AR total = 131 balance, AP = 331,
  stock value = 156.
- **Role profiles**: `ensure_vn_role_profiles()` creates the expected profiles once;
  re-run is a no-op.
- **Master-data completeness**: a Customer missing MST is flagged; a complete one is
  not.
- **Readiness**: after full scripted setup on scratch → `go_live_readiness` returns
  `ok: True`; removing any one precondition flips exactly that check to `ok: False`.
- **Regression**: Company suite + all VN suites stay green.

## Success Criteria (specific, testable)

1. `configure_go_live(company)` on a VN company sets: a Fiscal Year covering the
   go-live year (open), perpetual inventory ON with a valuation method, VN naming
   series on SI/PI/JE/PE/Delivery Note/Payment/Stock Entry, and VND number format —
   and is **idempotent**.
2. `ensure_vn_role_profiles()` creates the six VN Role Profiles mapped to ERPNext
   roles; re-run creates no duplicates.
3. `seed_item_group_taxonomy(company)` creates the thiết bị & vật tư y tế Item Group
   tree; `master_data_completeness(company)` flags a Customer/Supplier missing MST or
   a required default.
4. `validate_opening_balances(company)` returns **fail** for an unbalanced TB or a
   non-TT99 account, and **pass** for a balanced, fully-TT99 opening TB whose AR/AP/
   stock control totals tie to 131/331/156.
5. `go_live_readiness(company)` returns a structured checklist; it is **all-green**
   only after config + roles + balanced opening + backup marker are in place, and
   flips exactly the missing check to fail otherwise.
6. `docs/go_live_runbook.md` walks the team end-to-end (backup → config → master
   data → opening balances → validate → go-live → day-1 smoke → rollback) with a
   one-page checklist; CSV import templates exist for Customers/Suppliers/Items.
7. Company suite + all VN suites remain green.

## Boundaries

**Always**
- Feature branch; TDD; idempotent, VN-guarded helpers; accounts by TT99 **number**.
- Build & test every helper on a **scratch** company first.
- Before entering opening balances or running config on the **real Miyano**: take a
  **verified site backup**, and **confirm with the user**.
- Opening balances must **net to zero** and be **100% TT99-numbered** before go-live.

**Ask first**
- Entering **real** opening balances / master data into the live Miyano company.
- Creating **real** user accounts or sending invites.
- Changing **naming series** after any document of that type already exists.
- Enabling/disabling **perpetual inventory** on a company that already has stock.
- Touching `mvl_accounting` / `assetcore` overlays, or anything belonging to those
  apps (VN compliance, medical-device lifecycle).

**Never**
- Post an opening trial balance that does not net to zero.
- Leave any default or opening entry pointing at a **non-TT99** account.
- Go live without a **verified backup** and a **passing** `go_live_readiness`.
- Commit to `develop`; touch pre-existing uncommitted local changes.
- Push proprietary/confidential material to a **public** remote without explicit
  user confirmation of the destination.

## Open Questions (defaults; correct anytime)

1. **Go-live fiscal year**: default = the next fiscal year start (opening balances as
   of 01/01), team confirms the exact year at cutover. (Default: parameterize the
   year in `configure_go_live`; don't hard-code.)
2. **Item Group taxonomy**: default = a small thiết bị y tế / vật tư y tế tree; the
   detailed catalog is entered manually per the runbook. (Default: seed the tree,
   not the items.)
3. **Opening-balance counter account**: enter the **full** opening TB (nets to zero
   via equity 411/421…), or use ERPNext's **Temporary Opening** for a partial load?
   (Default: full TB via equity; Temporary Opening only if the team loads in stages.)
4. **Warehouses**: seed one default kho + let the team add the rest, or model the
   real warehouse tree now? (Default: one default kho; team adds the rest.)
5. **Role Profiles**: the six generic VN roles above — add finer roles (e.g. thủ quỹ,
   kế toán công nợ)? (Default: the six; extend on request.)
6. **Backup marker**: how `go_live_readiness` confirms a backup exists — a
   file/flag the runbook step writes, or check `bench backup` output? (Default: a
   readiness note the operator sets after taking + verifying a backup.)
