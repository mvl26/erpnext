# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

"""Hóa đơn điện tử (NĐ 70/2025) — settings, payload building, issuance orchestration.

Layering: everything here is pure/DB-only and unit-testable; network I/O lives
exclusively inside the provider adapters (``e_invoice_providers``). Credentials are
read by adapters from ``site_config.json`` — never from code or fixtures. Issuance
is opt-in per company (``vn_einvoice_enabled``, Task 40) and never blocks the
accounting flow: a provider failure leaves the Sales Invoice submitted and records
an Error log for retry.
"""

import json

import frappe
from frappe.utils import cint, flt

from erpnext.regional.vietnam.e_invoice_providers import get_provider
from erpnext.regional.vietnam.utils import so_thanh_chu


def get_e_invoice_settings(company):
	"""Per-company HĐĐT settings from the Company custom fields."""
	values = (
		frappe.db.get_value(
			"Company",
			company,
			["vn_einvoice_enabled", "vn_einvoice_provider", "vn_einvoice_symbol", "tax_id"],
			as_dict=True,
		)
		or frappe._dict()
	)
	return frappe._dict(
		enabled=cint(values.get("vn_einvoice_enabled")),
		provider=values.get("vn_einvoice_provider") or "mock",
		symbol=values.get("vn_einvoice_symbol") or "",
		seller_tax_id=values.get("tax_id") or "",
	)


def build_invoice_payload(si, settings=None):
	"""NĐ70-shaped payload for a Sales Invoice document. Pure — no network."""
	settings = settings or get_e_invoice_settings(si.company)
	return {
		"symbol": settings.symbol,
		"seller": {"name": si.company, "tax_id": settings.seller_tax_id},
		"buyer": {
			"name": si.customer_name or si.customer,
			"tax_id": si.get("tax_id") or "",
			"address": si.get("address_display") or "",
		},
		"invoice": {
			"erp_reference": si.name,
			"posting_date": str(si.posting_date),
			"currency": si.currency,
			"lines": [
				{
					"item": r.item_code or r.item_name,
					"name": r.item_name,
					"uom": r.uom or r.get("stock_uom") or "",
					"qty": flt(r.qty),
					"rate": flt(r.rate),
					"amount": flt(r.amount),
				}
				for r in si.items
			],
			"taxes": [
				{"description": t.description, "rate": flt(t.rate), "amount": flt(t.tax_amount)}
				for t in si.get("taxes") or []
			],
			"net_total": flt(si.net_total),
			"grand_total": flt(si.grand_total),
			"in_words": so_thanh_chu(si.grand_total),
		},
	}


def _as_json(value):
	return json.dumps(value, ensure_ascii=False, indent=1, default=str)
