# Plan — Vietnamese Accounting Localization (Thông tư 99/2025/TT-BTC)

Goal: make ERPNext's accounting default to the Vietnamese chart of accounts and
compliance conventions of **Thông tư 99/2025/TT-BTC** for Công ty TNHH Miyano
Việt Nam (medical-equipment / thiết bị & vật tư y tế trading).

Source of truth for the account list: `docs/hệ thống tài khoản kế toán.pdf`
(Phụ lục II — Hệ thống tài khoản kế toán doanh nghiệp, TT 99/2025/TT-BTC).

The chart-of-accounts template mechanism lives in ERPNext core
(`erpnext/accounts/doctype/account/chart_of_accounts/verified/*.json`), so the
default COA belongs **here in this app**, not in `mvl_accounting`. VN-specific
posting rules and TT-99 compliance reports remain candidates for `mvl_accounting`.

## Tasks

- [x] **Task 1 — Default TT99 Chart of Accounts template.** ✅ Done
      (`verified/vn_chart_of_accounts.json`, 184 accounts; test
      `test_vn_chart_of_accounts.py`, 8 tests; company smoke wired all 10
      default accounts to the correct TT99 numbers).
  Add `verified/vn_chart_of_accounts.json` reproducing the full TT99 account
  tree (Cấp 1 → Cấp 4) under 5 `root_type` roots, with `account_number` on every
  account and `account_type` on the accounts ERPNext auto-wires to company
  defaults (Cash 111, Bank 112, Receivable 131, Payable 331, COGS 632,
  Fixed Asset 211-213, Accumulated Depreciation 214x, Depreciation 6424,
  Capital Work in Progress 2411, Stock 156, Income 511/515/711, Tax 133x/333x,
  Expense 62x/63x/64x/81x/82x, Equity 41x/42x).
  Acceptance: the JSON is valid, `country_code=vn`; it is discoverable via
  `get_charts_for_country("Vietnam")`; the tree parses via
  `build_tree_from_json`; key accounts carry the expected root_type/account_type.

- [x] **Task 2 — Operational accounts + item/warehouse defaults.** ✅ Done
  Added 9 unnumbered operational accounts to the VN chart (6 by account_type:
  Round Off, Stock Received But Not Billed, Stock Adjustment, Expenses Included
  In Valuation, Asset Received But Not Billed, Expenses Included In Asset
  Valuation; 3 by canonical name: Write Off, Exchange Gain/Loss, Gain/Loss on
  Asset Disposal). End-to-end test confirms a VN company now populates all 9
  operational default-account fields.

- [x] **Task 3 — Vietnam default tax templates.** ✅ Done
  Replaced the stub Vietnam entry in `country_wise_tax.json` with detailed GTGT
  setup: Sales templates (GTGT bán ra 10/8/5/0% → 33311), Purchase templates
  (GTGT mua vào 10/8/5/0% → 1331), Item Tax Templates (GTGT 10/8/5/0%, each
  covering both 33311 and 1331) and Tax Categories. End-to-end test confirms a
  VN company creates them on the real TT99 accounts.

- [ ] **Task 4 — Company/region defaults.**
  Regional hook so a Vietnam company defaults to VND, VN number format, and the
  TT99 chart selected automatically in the setup wizard.

- [ ] **Task 5 — TT99 financial statements.**
  Report mappings for Bảng cân đối kế toán (B01-DN) and Báo cáo KQHĐKD (B02-DN).

Tasks are ordered by dependency: Task 1 is the foundation; 2–5 build on it.
