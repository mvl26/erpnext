# Spec: Make TT99 the Default Accounting Everywhere (Miyano)

> Status: **DRAFT — awaiting approval.** Phase 1 (Specify) of spec-driven development.
> Supersedes the previous SPEC (VN chart + statutory reports, now shipped — see git).

## Objective

Make the **Thông tư 99/2025/TT-BTC** chart the *operative* accounting for Công ty
TNHH Miyano Việt Nam — not just an available template, but the wiring every module
actually uses. Concretely:

1. **Switch the existing `Miyano` company onto the TT99 chart.** It currently runs
   the English "Standard" chart (Debtors/Cash/Stock In Hand…, no TT99 numbers) but
   is **empty** — 0 GL entries, 0 invoices, 0 stock ledger, 0 items/customers/
   suppliers/asset-categories — so the switch is safe (nothing references the old
   accounts). Rebuild its chart and re-wire all defaults to TT99 numbers.
2. **A reusable VN company-setup hook** so *any* Vietnam company auto-wires every
   module/master-data account link to the correct TT99 account number — assets,
   stock/items, buying/selling parties, invoices, tax, mode of payment, warehouses.
3. **Revise all accounting defaults/logic to resolve to TT99 accounts** — the goal
   is that no default anywhere still points at a non-TT99 (English) account.

**Users:** Miyano's kế toán and the medcons.vn dev team.

**Success = ** on a VN company, every account a transaction touches by default is a
TT99-numbered account: bán hàng → 131/511/33311, mua hàng → 331/632/1331, nhập kho
→ 156, khấu hao → 211/2141/6424, thu/chi tiền → 111/112.

## Prior work (done, on this branch)

TT99 chart of accounts; operational default accounts wired to Company defaults
(Cash 111, Bank 112, Receivable 131, Payable 331, COGS 632, Stock 156, Round Off,
SRBNB, Stock Adjustment, Accumulated Depreciation 2141, Depreciation 6424, CWIP
2411, Write Off, Exchange Gain/Loss, Disposal, Unrealized FX 413…); GTGT + import
tax templates; VND default; statutory reports (B01/B02/B03/B09, tax declarations,
sổ kế toán); số-thành-chữ. **So Company-level defaults are already TT99.** This
phase extends wiring to master data / modules and to the Miyano company itself.

## Wiring surface (what must resolve to TT99)

| Area | Where the link lives | Target TT99 account(s) |
|------|----------------------|------------------------|
| Company defaults | `Company.*_account` | done (111/112/131/331/632/156/2141/6424/2411/413/…) |
| Cash/Bank payments | `Mode of Payment Account.default_account` | Cash → 111, Bank → 112 |
| Fixed assets | `Asset Category Account` (per company) | fixed 211/213, accum dep 2141/2143, dep exp 6424, CWIP 2411 |
| Stock / warehouses | `Warehouse.account` (else Company default) | 156 |
| Item accounts | `Item Default` → `Item Group` default → Company default | income 511, expense/giá vốn 632 |
| Party accounts | `Party Account` (else Company default) | Customer → 131, Supplier → 331 |
| Sales/Purchase invoice | resolved from item/party/company + tax template | 131/511/33311, 331/632/1331 |
| Round-off / write-off / FX / disposal | Company defaults | done |

Most flow from Company defaults (already TT99). The genuinely new wiring: **Asset
Categories**, **Mode of Payment** accounts, and explicit **Item Group / Warehouse /
Party** defaults for robustness.

## Tech Stack

Frappe v15 + ERPNext v15, site `miyano`, Python 3.12 (TABS, 110 cols, ruff),
`FrappeTestCase`. The reusable hook uses ERPNext's regional dispatch
(`install_country_fixtures` → `erpnext.regional.<country>.setup.setup`).

## Commands

```bash
bench --site miyano migrate
bench --site miyano console
bench --site miyano run-tests --module erpnext.regional.vietnam.test_setup
bench --site miyano run-tests --module erpnext.setup.doctype.company.test_company
pre-commit run --all-files
```

## Project Structure

```
erpnext/regional/vietnam/
  setup.py            → setup(company): dispatch on VN company creation;
                        wires Asset Categories, Mode of Payment, Warehouse,
                        Item Group defaults, party defaults to TT99 numbers.
  constants.py        → TT99 account-number constants (extend existing).
  test_setup.py       → hook tests (create VN company, assert every link → TT99).
erpnext/patches/v15_xx/reconfigure_miyano_to_tt99.py
                      → one-time, guarded: only if company empty; backs up old
                        account list; rebuilds chart on TT99; re-wires; verifies.
erpnext/patches.txt   → register the patch.
erpnext/setup/doctype/company/company.py
                      → extend set_default_accounts / regional dispatch as needed.
```

## Code Style

TT99 account numbers referenced by **number**, resolved to the company's account
name at runtime — never hard-code company-suffixed names:

```python
def _acct(company, number):
	return frappe.db.get_value(
		"Account", {"company": company, "account_number": number, "is_group": 0}, "name"
	)

def setup(company):
	"""Wire a Vietnam company's module accounts to TT99 numbers (idempotent)."""
	if frappe.db.get_value("Company", company, "country") != "Vietnam":
		return
	_wire_mode_of_payment(company)      # Cash -> 111, Bank -> 112
	_create_asset_categories(company)   # 211/2141/6424/2411, 213/2143
	_wire_item_group_defaults(company)  # income 511, expense 632
	# ... each step idempotent (skip if already set)
```

Every step is **idempotent** (safe to re-run) and **guarded** (only for VN companies).

## Testing Strategy

- **Hook test** (`FrappeTestCase`): create a VN company, then assert:
  Mode of Payment Cash → 111 & Bank → 112; an Asset Category exists with
  fixed 211 / accum-dep 2141 / dep-exp 6424 / CWIP 2411; a new **Item** resolves
  income 511 / expense 632; a new **Customer/Supplier** posts to 131/331 (via a
  test Sales/Purchase Invoice or party-account resolution).
- **Idempotency test**: running setup twice creates no duplicates.
- **Miyano reconfigure test / dry-run**: after the patch, `Miyano.chart_of_accounts`
  is the TT99 chart, defaults resolve to TT99 numbers, and **no English account
  remains** — asserted against a scratch copy so the real company isn't a test
  fixture.
- **Regression**: Company suite + all VN suites stay green.

## Boundaries

**Always**
- Feature branch; TDD; idempotent, VN-guarded wiring.
- Reference accounts by **number**, resolve at runtime.
- Before reconfiguring Miyano: **assert it is empty** (0 GL, 0 stock, 0 party/item),
  **back up** the old account list to a file, and **confirm with the user** before
  the destructive delete/rebuild.

**Ask first**
- Reconfiguring ANY company that is not empty (has GL/stock/master data).
- Touching `mvl_accounting`'s customer/supplier/account overlays.
- Adding new default DocTypes (Asset Category names, Item Groups) that overlap
  existing master data.

**Never**
- Swap the chart of a company that has GL entries or stock ledger entries.
- Delete an account referenced by any GL entry / transaction.
- Commit to `develop`; touch pre-existing uncommitted local changes.
- Leave a default pointing at a non-TT99 account after this phase.

## Success Criteria (specific, testable)

1. Creating a VN company auto-creates **Asset Categories** whose per-company
   accounts are 211/2141/6424/2411 (hữu hình) and 213/2143 (vô hình).
2. VN company **Mode of Payment**: Cash.default_account → 111, Bank → 112.
3. A new **Item** on a VN company resolves income → 511, expense → 632 (via
   Item Group / Company defaults).
4. A new **Customer** → Receivable 131; new **Supplier** → Payable 331 (a test
   invoice posts to those accounts).
5. A test **Sales Invoice** posts Dr 131 / Cr 511 / Cr 33311; a test **Purchase
   Invoice** posts Dr 632(or 156)/Dr 1331 / Cr 331.
6. **Miyano** ends up on the TT99 chart: `chart_of_accounts` = the VN chart,
   default_receivable → 131, default_payable → 331, default_inventory → 156,
   default_expense → 632, default_income → 511; **zero** English (numberless)
   accounts remain; old list backed up.
7. `setup(company)` is **idempotent** (second run = no duplicates, no errors).
8. Company suite + all VN suites remain green.

## Open Questions (defaults; correct anytime)

1. **Asset Categories to create**: default set = "Tài sản cố định hữu hình" (211),
   "Tài sản cố định vô hình" (213). Add medical-equipment-specific categories
   (thiết bị y tế) mapped to 211? (Default: the two generic ones.)
2. **Warehouse accounts**: set each warehouse's account to 156, or leave to fall
   back to Company default_inventory? (Default: leave fallback; don't override.)
3. **Party accounts**: rely on Company default_receivable/payable (131/331) for all
   parties, or also write per-group `Party Account` rows? (Default: rely on Company
   defaults; no per-party overrides.)
4. **mvl_accounting**: its `mvl_customer`/`mvl_supplier` overlays are left untouched;
   confirm they don't set conflicting party accounts.
5. **Miyano switch mechanism**: delete-and-rebuild the empty chart vs. delete the
   company and recreate. (Default: delete accounts + rebuild on TT99 in place,
   preserving the company record and its name/settings.)
