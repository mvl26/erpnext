# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""HĐĐT provider adapters — the only layer allowed to do network I/O.

Each adapter exposes ``issue(payload)`` (and, for lineage flows, ``adjust``/
``replace``) returning ``{ok, invoice_number, invoice_symbol, cqt_code, xml, ...}``.
Real adapters (VNPT-Invoice / Viettel SInvoice / M-Invoice — pending the provider
decision, OQ-1) read their credentials from ``site_config.json`` keys, never from
code. ``mock`` is deterministic and in-process: it is the only adapter tests use.
"""

import frappe
from frappe import _

from erpnext.regional.vietnam.e_invoice_providers import mock

PROVIDERS = {"mock": mock.MockProvider}


def get_provider(name):
	cls = PROVIDERS.get((name or "").strip().lower())
	if not cls:
		frappe.throw(_("Nhà cung cấp HĐĐT không được hỗ trợ: {0}").format(name))
	return cls()
