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
from frappe.utils import cint, flt, now_datetime

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


def on_si_submit(doc, method=None):
	"""doc_events hook — fire-and-log HĐĐT issuance; must never block the submit."""
	try:
		issue_e_invoice(doc.name, si=doc)
	except Exception:
		# Provider errors are already caught and logged inside issue_e_invoice;
		# this guards against unexpected bugs so accounting is never blocked.
		frappe.log_error(title=f"HĐĐT issuance failed for {doc.name}")


@frappe.whitelist()
def issue_e_invoice(sales_invoice, si=None):
	"""Issue a HĐĐT for a submitted Sales Invoice via the company's provider.

	No-op unless the company opted in (``vn_einvoice_enabled``). A provider failure
	records an Error log and stamps the invoice for retry — calling this again (it
	is whitelisted) retries the issuance. Returns the log name, or None on no-op.
	"""
	si = si or frappe.get_doc("Sales Invoice", sales_invoice)
	if si.docstatus != 1:
		return None
	settings = get_e_invoice_settings(si.company)
	if not settings.enabled:
		return None

	payload = build_invoice_payload(si, settings)
	provider = get_provider(settings.provider)
	try:
		result = provider.issue(payload)
	except Exception as exc:
		return _log_issuance(si, settings, payload, error=str(exc))
	return _log_issuance(si, settings, payload, result=result)


def _log_issuance(si, settings, payload, result=None, error=None):
	"""Write the Vietnam E Invoice Log row and stamp the SI custom fields."""
	ok = bool(result and result.get("ok"))
	result = result or {}
	log = frappe.get_doc(
		{
			"doctype": "Vietnam E Invoice Log",
			"sales_invoice": si.name,
			"provider": settings.provider,
			"status": "Issued" if ok else "Error",
			"invoice_number": result.get("invoice_number"),
			"invoice_symbol": result.get("invoice_symbol"),
			"cqt_code": result.get("cqt_code"),
			"issued_at": now_datetime() if ok else None,
			"payload": _as_json(payload),
			"response": _as_json(result) if result else None,
			"xml": result.get("xml"),
			"error_message": error,
		}
	)
	log.flags.ignore_permissions = True
	log.insert()

	frappe.db.set_value(
		"Sales Invoice",
		si.name,
		{
			"vn_einvoice_number": log.invoice_number,
			"vn_einvoice_symbol": log.invoice_symbol,
			"vn_einvoice_cqt_code": log.cqt_code,
			"vn_einvoice_status": log.status,
			"vn_einvoice_log": log.name,
		},
	)
	return log.name
