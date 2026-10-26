"""Read-only snapshot of what the site has — DocTypes and Reports of frappe, erpnext and hrms."""

from dataclasses import dataclass, field

import frappe

APPS = ("frappe", "erpnext", "hrms")


@dataclass
class DocTypeInfo:
	name: str
	app: str
	module: str
	is_submittable: bool
	issingle: bool
	high_permlevel_fields: frozenset[str] = frozenset()
	custom: bool = False  # made in the desk on this site (``tabDocType.custom``), not shipped by an app


@dataclass
class SiteInfo:
	doctypes: dict[str, DocTypeInfo] = field(default_factory=dict)
	reports: dict[str, str] = field(default_factory=dict)  # report name -> ref_doctype

	@classmethod
	def from_db(cls) -> "SiteInfo":
		rows = frappe.db.sql(
			"""
			SELECT dt.name, dt.module, m.app_name, dt.issingle, dt.is_submittable, dt.custom
			FROM `tabDocType` dt
			JOIN `tabModule Def` m ON m.name = dt.module
			WHERE m.app_name IN %(apps)s AND dt.istable = 0
			""",
			{"apps": APPS},
			as_dict=True,
		)
		doctypes = {}
		for row in rows:
			meta = frappe.get_meta(row.name)
			doctypes[row.name] = DocTypeInfo(
				name=row.name,
				app=row.app_name,
				module=row.module,
				is_submittable=bool(row.is_submittable),
				issingle=bool(row.issingle),
				high_permlevel_fields=frozenset(
					df.fieldname for df in meta.get_high_permlevel_fields() if getattr(df, "fieldname", None)
				),
				custom=bool(row.custom),
			)
		report_rows = frappe.db.sql(
			"""
			SELECT r.name, r.ref_doctype
			FROM `tabReport` r
			JOIN `tabModule Def` m ON m.name = r.module
			WHERE m.app_name IN %(apps)s
			""",
			{"apps": APPS},
			as_dict=True,
		)
		return cls(doctypes=doctypes, reports={r.name: r.ref_doctype for r in report_rows})
