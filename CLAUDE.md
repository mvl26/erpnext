# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

This repo is **ERPNext being hard-forked into the bespoke ERP of Công ty TNHH Miyano Việt Nam** — a medical-equipment (thiết bị & vật tư y tế) business — with Vietnamese localization and compliance. It is not a vanilla install and not a clean overlay: **the ERPNext code itself is edited to become Miyano's product.** Shaping core to fit Miyano's business is the goal, not staying upgrade-clean.

It runs as one app inside a Frappe *bench* (site `miyano`), not standalone. **Run every `bench` command from the bench root `/home/miyano/frappe-bench`** (not this app directory), passing `--site miyano`.

## Golden rule for changes

- **Edit the relevant ERPNext module directly** to meet a Miyano requirement — don't route around core. Bending core to fit the business is the point of this fork.
- Forked off upstream `version-15`: keep changes coherent and grouped in the right module, and stay aware of where you diverge. Use `git blame`/`git log` for a file's history and any prior local edits — for context, not as a reason to avoid changing it.
- Put large, self-contained capabilities in a complementary bench app (below); changes to core ERP behavior belong here, in this app.
- Use Frappe's built-in customization (Custom Field, Client Script, Property Setter, Workflow) for config-level tweaks that need no code; write code for real business logic.

## Project context

Miyano's deployment (built by a Vietnamese team, medcons.vn) layers several **complementary custom apps** on the same bench and site `miyano`, sharing one database with this app:

- **`mvl_accounting`** — Kế toán tuân thủ Thông tư 99/2025/TT-BTC (VN); requires `erpnext` + `hrms`.
  **PARKED (decision 2026-07-16):** VN accounting is built **in this app** (`erpnext/regional/vietnam/` + related core edits) — see `SPEC.md`. `mvl_accounting` is disk-only, NOT installed on site `miyano`; treat its code as a tested reference to study, never install it, never import from it at runtime, and never touch its working tree (it has uncommitted local changes).
- **`assetcore`** — Medical Equipment Lifecycle Management (HTM) — vòng đời thiết bị y tế.
- **`antmed_crm`** — CRM quản lý kinh doanh thiết bị & vật tư y tế.
- **`normcore_dmktkt` / `norm_himedic`** — Định mức Kinh tế Kỹ thuật dịch vụ y tế.
- **`workflowcore`** — Quản lý workflow + AI.
- **`hrms`** — Frappe HR (dependency of `mvl_accounting`).

Because these share the site DB, changes here can affect — and be affected by — those apps. When a feature is clearly one of theirs (e.g. medical-device lifecycle → `assetcore`, CRM → `antmed_crm`), make the change in that app, not here. **Exception:** VN accounting/compliance (TT99, HĐĐT, sổ sách, kê khai) belongs **here** in erpnext core — `mvl_accounting` is parked (see above).

## Common commands

Run from the bench root (`/home/miyano/frappe-bench`):

```bash
# Dev server (web + workers + scheduler, via Procfile)
bench start

# Apply DB schema changes + run patches after editing DocType JSON or patches.txt
bench --site miyano migrate

# Rebuild JS/CSS bundles after editing .js/.scss/.vue assets
bench build --app erpnext
bench --site miyano clear-cache          # clear server + Redis cache
bench --site miyano clear-website-cache

# Interactive Python shell with the Frappe app context loaded
bench --site miyano console
```

### Tests

```bash
# Whole app
bench --site miyano run-tests --app erpnext

# A single module (dotted path to a test_*.py file)
bench --site miyano run-tests --module erpnext.selling.doctype.sales_order.test_sales_order

# Every test for one DocType
bench --site miyano run-tests --doctype "Sales Order"

# A single test method
bench --site miyano run-tests --module erpnext.selling.doctype.sales_order.test_sales_order --test test_so_billed_amount

# Parallel run, as CI does it
bench --site miyano run-parallel-tests --app erpnext
```

Tests subclass `frappe.tests.utils.FrappeTestCase` (or `IntegrationTestCase`) and run inside a transaction that is rolled back. Fixture data lives in `test_records.json` next to each DocType.

### Lint / format

The gate is **pre-commit** (ruff + prettier + eslint). Config: `.pre-commit-config.yaml`, `pyproject.toml`, `.eslintrc`.

```bash
pre-commit run --all-files          # everything
ruff check erpnext/                 # Python lint
ruff format erpnext/                # Python format
```

**Python style is unusual: indent with TABS, not spaces**, line length 110, double-quoted strings (ruff enforces this; that's why `E101`/`W191` are ignored). Match the surrounding file.

## Architecture

### DocType-centric structure

Everything is organized around **DocTypes** (the Frappe model/schema unit), grouped into **modules** listed in `erpnext/modules.txt` (Accounts, Selling, Buying, Stock, Manufacturing, CRM, Projects, Assets, Subcontracting, Support, Regional, …). Each module is a top-level folder under `erpnext/`.

A DocType lives at `erpnext/<module>/doctype/<snake_case_name>/` and typically contains:

- `<name>.json` — schema, fields, permissions, naming. **The source of truth for the data model.** Edit this (or the Form Builder in developer mode), then `bench migrate`.
- `<name>.py` — server-side controller: a class subclassing `Document` with hooks like `validate`, `on_submit`, `before_save`, `on_cancel`.
- `<name>.js` — client-side form script (`frappe.ui.form.on(...)`).
- `<name>_list.js`, `<name>_dashboard.py` — list view and connections/dashboard config.
- `test_<name>.py` — tests.

### Shared transaction controllers

Most transactional DocTypes do **not** inherit `Document` directly — they inherit a base controller in `erpnext/controllers/` that centralizes shared business logic. Trace behavior up this chain before editing a specific DocType:

- `AccountsController` (`accounts_controller.py`) — base for anything that hits the GL (invoices, payments, journal entries); handles taxes, currency, GL entries.
- `SellingController` / `BuyingController` — sales vs purchase transaction logic.
- `StockController` — stock ledger and valuation for anything moving inventory.
- `SubcontractingController`, `TaxesAndTotals`, `StatusUpdater` — subcontracting, tax/total computation, and cross-document status rollups.

When adding Miyano logic that spans many documents (e.g. a shared validation across all sales transactions), put it on the appropriate controller rather than duplicating it per DocType.

### hooks.py — the wiring

`erpnext/hooks.py` is the central integration file. It declares (non-exhaustive): `doc_events` (server-side event handlers bound to DocTypes), `scheduler_events` (cron/scheduled jobs), `override_doctype_class` and `override_whitelisted_methods` (behavior overrides), asset bundles, fixtures, and setup-wizard stages. When wiring cross-cutting behavior, register it here.

### Patches (data migrations)

`erpnext/patches.txt` lists migration scripts under `erpnext/patches/` that run in order on `bench migrate`. Add a patch when a code change requires backfilling or transforming existing data; entries are permanent and run once per site.

### Other conventions

- **Regional customizations** live in `erpnext/regional/` (country-specific tax, compliance, reports) and are dispatched via hooks — Vietnam-specific localization belongs there (or in `mvl_accounting`), not inline in generic modules.
- Server methods callable from the client must be decorated `@frappe.whitelist()`.
- The pre-commit `no-commit-to-branch` hook blocks direct commits to `develop` (the current working branch). Create a feature branch before committing, or adjust the hook if the team's workflow commits to `develop` directly.
