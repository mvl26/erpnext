# import frappe
from frappe.model.document import Document


class ProcessPaymentReconciliationLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from erpnext.accounts.doctype.process_payment_reconciliation_log_allocations.process_payment_reconciliation_log_allocations import (
			ProcessPaymentReconciliationLogAllocations,
		)

		allocated: DF.Check
		allocations: DF.Table[ProcessPaymentReconciliationLogAllocations]
		error_log: DF.LongText | None
		process_pr: DF.Link
		reconciled: DF.Check
		reconciled_entries: DF.Int
		status: DF.Literal["Running", "Paused", "Reconciled", "Partially Reconciled", "Failed", "Cancelled"]
		total_allocations: DF.Int
	# end: auto-generated types

	pass
