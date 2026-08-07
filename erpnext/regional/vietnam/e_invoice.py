# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

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


def _issued_log(sales_invoice):
	"""Name of the log for an already-issued HĐĐT on this invoice, else ``None``.

	Read from the database, not from a passed-in document: ``_log_issuance`` stamps
	the invoice with ``db.set_value``, so an in-memory doc can still look unissued
	right after a successful issuance. Error logs carry no number, so a failed
	attempt stays retryable.
	"""
	stamped = frappe.db.get_value(
		"Sales Invoice", sales_invoice, ["vn_einvoice_number", "vn_einvoice_log"], as_dict=True
	)
	return stamped.vn_einvoice_log if stamped and stamped.vn_einvoice_number else None


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

	No-op unless the company opted in (``vn_einvoice_enabled``). A return invoice
	whose original carries an issued HĐĐT is issued as a hóa đơn điều chỉnh with
	lineage. A provider failure records an Error log and stamps the invoice for
	retry — calling this again (it is whitelisted) retries. Returns the log name.

	An invoice that already carries a HĐĐT number is never issued again: a real
	provider would mint a second legal số for one sale. Correcting an issued invoice
	goes through điều chỉnh (hóa đơn trả lại) or ``issue_replacement``.
	"""
	si = si or frappe.get_doc("Sales Invoice", sales_invoice)
	if si.docstatus != 1:
		return None
	settings = get_e_invoice_settings(si.company)
	if not settings.enabled:
		return None

	if issued := _issued_log(si.name):
		return issued

	adjusts = None
	if si.get("is_return") and si.get("return_against"):
		adjusts = frappe.db.get_value("Sales Invoice", si.return_against, "vn_einvoice_log")

	payload = build_invoice_payload(si, settings)
	provider = get_provider(settings.provider)
	try:
		result = provider.adjust(payload, adjusts) if adjusts else provider.issue(payload)
	except Exception as exc:
		return _log_issuance(si, settings, payload, error=str(exc), adjusts=adjusts)
	return _log_issuance(si, settings, payload, result=result, adjusts=adjusts)


@frappe.whitelist()
def issue_replacement(sales_invoice, replaces_invoice):
	"""Issue a hóa đơn thay thế: ``sales_invoice`` replaces ``replaces_invoice``.

	Explicit operator action (whitelisted, never automatic): the replacement gets
	its own số from the provider, the log records the lineage and the original log
	is marked Replaced.
	"""
	si = frappe.get_doc("Sales Invoice", sales_invoice)
	if si.docstatus != 1:
		frappe.throw(frappe._("Hóa đơn thay thế phải được submit trước khi phát hành HĐĐT"))
	settings = get_e_invoice_settings(si.company)
	if not settings.enabled:
		return None

	replaces = frappe.db.get_value("Sales Invoice", replaces_invoice, "vn_einvoice_log")
	if not replaces:
		frappe.throw(frappe._("Hóa đơn gốc {0} chưa có HĐĐT để thay thế").format(replaces_invoice))

	payload = build_invoice_payload(si, settings)
	provider = get_provider(settings.provider)
	try:
		result = provider.replace(payload, replaces)
	except Exception as exc:
		return _log_issuance(si, settings, payload, error=str(exc), replaces=replaces)
	return _log_issuance(si, settings, payload, result=result, replaces=replaces)


def _log_issuance(si, settings, payload, result=None, error=None, adjusts=None, replaces=None):
	"""Write the Vietnam E Invoice Log row, stamp the SI, and update lineage."""
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
			"adjusts": adjusts,
			"replaces": replaces,
		}
	)
	log.flags.ignore_permissions = True
	log.insert()

	if ok and adjusts:
		frappe.db.set_value("Vietnam E Invoice Log", adjusts, "status", "Adjusted")
	if ok and replaces:
		frappe.db.set_value("Vietnam E Invoice Log", replaces, "status", "Replaced")

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
