from contextlib import contextmanager

import frappe
from frappe import _


def update_doctypes():
	for d in frappe.db.sql(
		"""select df.parent, df.fieldname
		from tabDocField df, tabDocType dt where df.fieldname
		like "%description%" and df.parent = dt.name and dt.istable = 1""",
		as_dict=1,
	):
		dt = frappe.get_doc("DocType", d.parent)

		for f in dt.fields:
			if f.fieldname == d.fieldname and f.fieldtype in ("Text", "Small Text"):
				f.fieldtype = "Text Editor"
				dt.save()
				break


@contextmanager
def payment_app_import_guard():
	msg = _("payments app is not installed. Please contact the Miyano IT team.")
	try:
		yield
	except ImportError:
		frappe.throw(msg, title=_("Missing Payments App"))
