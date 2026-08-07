# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""One-time: switch the Miyano company from the English Standard chart onto the
TT99 chart of accounts. Guarded (only runs if the company is empty) and idempotent
(no-op once the company is already on the TT99 chart). Backs up the old account
list to the site's private files first.

NOT registered in patches.txt until the destructive rebuild is explicitly
confirmed — the reconfigure deletes the company's existing accounts.
"""

import frappe

from erpnext.regional.vietnam.reconfigure import reconfigure_company_to_vn_chart

COMPANY = "Miyano"


def execute():
	if not frappe.db.exists("Company", COMPANY):
		return
	if frappe.db.get_value("Company", COMPANY, "country") != "Vietnam":
		return
	reconfigure_company_to_vn_chart(COMPANY)
