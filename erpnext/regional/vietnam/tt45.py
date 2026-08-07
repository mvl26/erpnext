# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Khung khấu hao TT45/2013/TT-BTC — useful-life defaults for VN Asset Categories.

TT45 gives per-asset-group useful-life RANGES; these defaults pick a sensible
point inside the range for Miyano's asset mix (thiết bị y tế, phần mềm) and are
meant as starting values: only empty depreciation rows are filled — a category the
kế toán already tuned is never overwritten. Monthly straight-line depreciation
(frequency 1 tháng), which is the common VN practice.
"""

import frappe

# Asset Category → useful life in years.
# Hữu hình: máy móc/thiết bị y tế — khung TT45 6–10 năm → 8.
# Vô hình: phần mềm máy tính — khung TT45 2–20 năm (thực tế 3–8) → 5.
TT45_USEFUL_LIFE_YEARS = {
	"Tài sản cố định hữu hình": 8,
	"Tài sản cố định vô hình": 5,
}


def apply_tt45_useful_life():
	"""Idempotently fill depreciation defaults on the VN Asset Categories."""
	from erpnext.regional.vietnam.setup import drop_rows_of_deleted_companies

	for name, years in TT45_USEFUL_LIFE_YEARS.items():
		if not frappe.db.exists("Asset Category", name):
			continue
		category = frappe.get_doc("Asset Category", name)
		# Same global doc as the setup hook — a stale row would fail this save too.
		pruned = drop_rows_of_deleted_companies(category)
		if _fill_depreciation_defaults(category, years) or pruned:
			category.flags.ignore_permissions = True
			category.save()


def _fill_depreciation_defaults(category, years):
	"""Fill only missing values; return True when something changed."""
	defaults = {
		"depreciation_method": "Straight Line",
		"total_number_of_depreciations": years * 12,  # khấu hao theo tháng
		"frequency_of_depreciation": 1,
	}
	if not category.finance_books:
		category.append("finance_books", defaults)
		return True

	changed = False
	for row in category.finance_books:
		if not row.total_number_of_depreciations:
			row.update(defaults)
			changed = True
	return changed
