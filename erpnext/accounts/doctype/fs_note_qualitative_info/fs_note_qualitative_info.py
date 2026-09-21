# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class FSNoteQualitativeInfo(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from erpnext.accounts.doctype.fs_accounting_policy_item.fs_accounting_policy_item import FSAccountingPolicyItem
		from erpnext.accounts.doctype.fs_related_party_txn_item.fs_related_party_txn_item import FSRelatedPartyTxnItem
		from erpnext.accounts.doctype.fs_subsidiary_entity_item.fs_subsidiary_entity_item import FSSubsidiaryEntityItem
		from frappe.types import DF

		accounting_policies: DF.Table[FSAccountingPolicyItem]
		accounting_regime: DF.Data | None
		bad_debt_written_off_note: DF.SmallText | None
		business_features_note: DF.SmallText | None
		business_field: DF.Data | None
		company: DF.Link
		comparability_reason: DF.SmallText | None
		comparability_statement: DF.Literal["C\u00f3 th\u1ec3 so s\u00e1nh \u0111\u01b0\u1ee3c", "Kh\u00f4ng th\u1ec3 so s\u00e1nh \u0111\u01b0\u1ee3c"]
		comparative_info_note: DF.SmallText | None
		contingent_liabilities_note: DF.SmallText | None
		currency_change_reason: DF.SmallText | None
		currency_unit: DF.Link | None
		custody_assets_note: DF.SmallText | None
		employee_count: DF.Int
		fiscal_year: DF.Link
		foreign_currency_note: DF.SmallText | None
		form_modification_content: DF.SmallText | None
		form_modification_item: DF.Data | None
		form_modification_reason: DF.SmallText | None
		going_concern_flag: DF.Check
		going_concern_note: DF.SmallText | None
		has_form_modifications: DF.Check
		industry_code: DF.Data | None
		infra_assets_note: DF.SmallText | None
		installment_interest_note: DF.SmallText | None
		key_estimates_note: DF.SmallText | None
		leased_assets_note: DF.SmallText | None
		operating_cycle_months: DF.Int
		other_disclosure_note: DF.SmallText | None
		other_measures_note: DF.SmallText | None
		other_off_balance_note: DF.SmallText | None
		ownership_type: DF.Literal["DNNN", "C\u1ed5 ph\u1ea7n", "TNHH", "H\u1ee3p danh", "T\u01b0 nh\u00e2n"]
		pledged_assets_note: DF.SmallText | None
		prepared_by: DF.Link | None
		related_party_note: DF.SmallText | None
		related_party_transactions: DF.Table[FSRelatedPartyTxnItem]
		report_date: DF.Date | None
		report_type: DF.Literal["B\u00e1o c\u00e1o n\u0103m", "B\u00e1o c\u00e1o gi\u1eefa ni\u00ean \u0111\u1ed9"]
		segment_info_note: DF.SmallText | None
		status: DF.Literal["Nh\u00e1p", "Ho\u00e0n th\u00e0nh", "\u0110\u00e3 duy\u1ec7t"]
		subsequent_events_note: DF.SmallText | None
		subsidiary_entities: DF.Table[FSSubsidiaryEntityItem]
		vas_compliance: DF.Check
		vas_exceptions: DF.SmallText | None
	# end: auto-generated types
	pass
