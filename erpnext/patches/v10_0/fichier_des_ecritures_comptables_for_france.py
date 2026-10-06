import frappe

from erpnext.setup.doctype.company.company import install_country_fixtures


def execute():
	frappe.reload_doc("regional", "report", "fichier_des_ecritures_comptables_[fec]")
	for d in frappe.get_all("Company", filters={"country": "France"}):
		install_country_fixtures(d.name)
