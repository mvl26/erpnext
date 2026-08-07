# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

import frappe


def execute():
	"""Rebrand the UI app name on sites installed before the Miyano rebrand.

	`System Settings.app_name` drives the browser title and in-app branding; existing
	sites still carry the value written by patches/v13_0/set_app_name.py.
	"""
	if frappe.db.get_single_value("System Settings", "app_name") == "ERPNext":
		frappe.db.set_single_value("System Settings", "app_name", "Miyano ERP")
