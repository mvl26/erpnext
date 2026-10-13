# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Biên bản đối chiếu & xác nhận công nợ (NCC 331 / KH 131).

Chứng từ không sinh bút toán: số liệu đọc từ GL Entry (``figures.py``), Submit = Duyệt,
sau đó hệ thống gửi email và kế toán ghi nhận phản hồi qua ``apply_action`` — trạng
thái do code điều khiển, không dùng Frappe Workflow (D20).
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, cint, get_first_day, get_last_day, getdate, now_datetime, nowdate

from erpnext.debt_reconciliation import constants as C
from erpnext.debt_reconciliation import figures

# action → (trạng thái nguồn, trạng thái đích)
ACTIONS = {
	"resend": ((C.STATUS_SEND_FAILED,), C.STATUS_APPROVED),
	"respond_match": ((C.STATUS_SENT,), C.STATUS_MATCHED),
	"respond_mismatch": ((C.STATUS_SENT, C.STATUS_MATCHED), C.STATUS_DISPUTED),
	"confirm": ((C.STATUS_SENT, C.STATUS_MATCHED, C.STATUS_DISPUTED), C.STATUS_CONFIRMED),
}


def make_statement_no(to_date):
	"""``{MM}.SL MVL-…./{YYYY}`` theo ``to_date`` — để trống phần mã đối tác (D17)."""
	d = getdate(to_date)
	return f"{d.month:02d}.SL MVL-…./{d.year}"


def get_response_deadline(to_date):
	day = cint(frappe.db.get_single_value(C.SETTINGS, "response_deadline_day")) or 6
	next_month = get_first_day(add_months(getdate(to_date), 1))
	return next_month.replace(day=min(day, 28))


def find_existing(party_type, party, from_date, to_date, exclude=None):
	"""Biên bản chưa Hủy của cùng đối tác + kỳ (R-b)."""
	filters = {
		"party_type": party_type,
		"party": party,
		"from_date": from_date,
		"to_date": to_date,
		"docstatus": ["<", 2],
	}
	if exclude:
		filters["name"] = ["!=", exclude]
	return frappe.db.get_value(C.DOCTYPE, filters, "name")


class DebtReconciliationStatement(Document):
	def validate(self):
		self.validate_period()
		self.validate_duplicate()
		if not self.party_name or (not self.is_new() and self.has_value_changed("party")):
			self.set_party_details()
		if not self.is_new() and any(
			self.has_value_changed(f) for f in ("company", "party_type", "party", "from_date", "to_date")
		):
			# Số liệu đã lấy không còn ứng với đối tác/kỳ mới → phải lấy lại trước khi duyệt
			self.figures_fetched_on = None
		self.set_defaults()
		self.statement_no = make_statement_no(self.to_date)
		self.response_deadline = get_response_deadline(self.to_date)
		if self.docstatus == 0:
			self.status = C.STATUS_DRAFT
		self.recompute_totals()
		self.set_warnings()

	def before_submit(self):
		if not self.figures_fetched_on:
			frappe.throw(_('Chưa lấy số liệu từ sổ — bấm "Lấy số liệu từ sổ" trước khi duyệt.'))
		self.status = C.STATUS_APPROVED

	def on_submit(self):
		frappe.enqueue(
			"erpnext.debt_reconciliation.publishing.send_statement",
			name=self.name,
			enqueue_after_commit=True,
			now=frappe.flags.in_test,
		)

	def on_cancel(self):
		self.db_set("status", C.STATUS_CANCELLED)

	# ------------------------------------------------------------------ validate

	def validate_period(self):
		from_date, to_date = getdate(self.from_date), getdate(self.to_date)
		# R-c: kỳ tròn tháng — nếu sau này cho kỳ lẻ thì chỉ bỏ kiểm tra này
		if from_date != get_first_day(from_date) or to_date != get_last_day(from_date):
			frappe.throw(_("Kỳ đối chiếu phải tròn một tháng: từ ngày 01 đến ngày cuối cùng của cùng tháng."))

	def validate_duplicate(self):
		existing = find_existing(self.party_type, self.party, self.from_date, self.to_date, exclude=self.name)
		if existing:
			frappe.throw(
				_(
					"Đối tác {0} đã có biên bản {1} cho kỳ này. Mỗi đối tác mỗi kỳ chỉ có 1 biên bản chưa Hủy."
				).format(frappe.bold(self.party), frappe.utils.get_link_to_form(C.DOCTYPE, existing)),
				title=_("Đã có biên bản"),
			)

	def set_defaults(self):
		settings = frappe.get_cached_doc(C.SETTINGS)
		if not self.company_representative:
			self.company_representative = settings.company_representative
		if not self.company_representative_title:
			self.company_representative_title = settings.company_representative_title
		if not self.posting_date:
			self.posting_date = nowdate()

	def recompute_totals(self):
		"""Tính lại dư cuối/chiều dư/bằng chữ từ số gốc đã lấy + lãi nhập tay (D12, D18)."""
		result = figures.compute(
			self.party_type,
			self.signed_opening_principal(),
			self.debit_in_period,
			self.credit_in_period,
			self.opening_interest,
			self.interest_in_period,
		)
		if result.interest_errors:
			frappe.throw("<br>".join(result.interest_errors), title=_("Lãi quá hạn không hợp lệ"))
		self.opening_direction = result.opening_direction
		self.closing_balance = result.closing_balance
		self.balance_direction = result.balance_direction
		self.amount_in_words = result.amount_in_words

	def signed_opening_principal(self):
		# Lãi đầu kỳ chỉ có khi gốc ở chiều còn nợ, nên chiều của dư đầu kỳ cũng là chiều của gốc
		return figures.to_signed(self.party_type, self.opening_principal, self.opening_direction)

	def set_warnings(self):
		warnings = []
		if not self.reconciliation_email:
			warnings.append(_("Đối tác chưa có email nhận đối chiếu."))
		if not self.framework_contract_no:
			warnings.append(_('Đối tác chưa có số HĐ nguyên tắc (bản in để "…").'))
		if self.figures_fetched_on and not (
			self.closing_balance or self.debit_in_period or self.credit_in_period
		):
			warnings.append(_("Đối tác không có số dư và không có phát sinh trong kỳ."))
		if frappe.db.get_value(self.party_type, self.party, "exclude_reconciliation"):
			warnings.append(_('Đối tác đang bật "Loại trừ đối chiếu".'))
		self.missing_party_warning = "\n".join(warnings)

	# ------------------------------------------------------------- party & số liệu

	@frappe.whitelist()
	def set_party_details(self):
		if not (self.party_type and self.party):
			return
		name_field = "supplier_name" if self.party_type == "Supplier" else "customer_name"
		party = frappe.db.get_value(
			self.party_type,
			self.party,
			[
				name_field,
				"tax_id",
				"email_id",
				"mobile_no",
				"framework_contract_no",
				"framework_contract_date",
				"representative_name",
				"representative_title",
				"reconciliation_email",
			],
			as_dict=True,
		)
		if not party:
			return
		self.party_name = party.get(name_field) or self.party
		self.party_tax_id = party.tax_id
		self.framework_contract_no = party.framework_contract_no
		self.framework_contract_date = party.framework_contract_date
		self.party_representative = party.representative_name
		self.party_representative_title = party.representative_title
		self.reconciliation_email = party.reconciliation_email or party.email_id
		self.party_address, address_phone = get_party_address(self.party_type, self.party)
		self.party_phone = address_phone or party.mobile_no

	@frappe.whitelist()
	def fetch_figures(self):
		"""Nút "Lấy số liệu từ sổ" — bấm lại bao nhiêu lần cũng được khi còn Nháp (R-e)."""
		if self.docstatus != 0:
			frappe.throw(_("Chỉ lấy lại số liệu khi biên bản còn Nháp; muốn đổi phải Hủy rồi Sửa đổi."))
		self.check_permission("write")
		self.set_party_details()
		totals = figures.get_gl_totals(
			self.company, self.party_type, self.from_date, self.to_date, party=self.party
		).get(self.party)
		self.apply_figures(figures.compute_from_totals(self.party_type, totals))

	def apply_figures(self, result):
		self.opening_principal = result.opening_principal
		self.opening_direction = result.opening_direction
		self.debit_in_period = result.debit_in_period
		self.credit_in_period = result.credit_in_period
		self.opening_interest = 0
		self.interest_in_period = 0
		self.closing_balance = result.closing_balance
		self.balance_direction = result.balance_direction
		self.amount_in_words = result.amount_in_words
		self.figures_fetched_on = now_datetime()

	# ---------------------------------------------------------------- trạng thái

	@frappe.whitelist()
	def apply_action(self, action, **data):
		C.require_manager()
		if self.docstatus != 1:
			frappe.throw(_("Chỉ thao tác được trên biên bản đã duyệt."))
		if action not in ACTIONS:
			frappe.throw(_("Thao tác không hợp lệ: {0}").format(action))
		from_states, to_state = ACTIONS[action]
		if self.status not in from_states:
			frappe.throw(
				_("Không thể thực hiện thao tác này khi biên bản đang ở trạng thái {0}.").format(
					frappe.bold(self.status)
				)
			)
		getattr(self, f"_action_{action}")(to_state, frappe._dict(data))
		self.add_comment("Info", _("Chuyển trạng thái: {0}").format(to_state))
		return self.status

	def _action_resend(self, to_state, data):
		if data.get("email"):
			frappe.utils.validate_email_address(data.email, throw=True)
			self.db_set("reconciliation_email", data.email.strip())
		self.db_set({"status": to_state, "send_error": None})
		from erpnext.debt_reconciliation.publishing import send_statement

		send_statement(self.name)
		self.reload()

	def _action_respond_match(self, to_state, data):
		self.db_set(
			{
				"status": to_state,
				"partner_response": C.RESPONSE_MATCH,
				"responded_on": data.get("responded_on") or nowdate(),
			}
		)

	def _action_respond_mismatch(self, to_state, data):
		if not data.get("dispute_note") or data.get("dispute_amount") in (None, ""):
			frappe.throw(_("Chênh lệch bắt buộc có Số theo đối tác và Diễn giải chênh lệch."))
		if frappe.utils.flt(data.dispute_amount) < 0:
			frappe.throw(_("Số theo đối tác phải là số dương (D9)."))
		self.db_set(
			{
				"status": to_state,
				"partner_response": C.RESPONSE_MISMATCH,
				"responded_on": data.get("responded_on") or nowdate(),
				"dispute_amount": frappe.utils.flt(data.dispute_amount),
				"dispute_note": data.dispute_note,
			}
		)

	def _action_confirm(self, to_state, data):
		if data.get("confirmation_method") not in (C.CONFIRM_HARD_COPY, C.CONFIRM_E_SIGN):
			frappe.throw(_("Chọn Cách xác nhận (C1 - Bản cứng hoặc C2 - Ký điện tử)."))
		if not data.get("signed_copy"):
			frappe.throw(_("Đính kèm Bản xác nhận có ký trước khi chuyển Đã xác nhận."))
		values = {
			"status": to_state,
			"confirmation_method": data.confirmation_method,
			"signed_copy": data.signed_copy,
			"confirmed_on": data.get("confirmed_on") or nowdate(),
			"confirmed_via": "Thủ công",
		}
		if data.get("dispute_resolution"):
			values["dispute_resolution"] = data.dispute_resolution
		attach_file_to(data.signed_copy, self)
		if self.partner_response == C.RESPONSE_NONE:
			# UC-04 E2: xác nhận thẳng khi chưa từng phản hồi → coi như Khớp
			values["partner_response"] = C.RESPONSE_MATCH
			values["responded_on"] = values["confirmed_on"]
		self.db_set(values)


def attach_file_to(file_url, doc):
	"""File tải lên từ hộp thoại chưa gắn với chứng từ nào → gắn vào biên bản."""
	file_name = frappe.db.get_value(
		"File", {"file_url": file_url, "attached_to_name": ["is", "not set"]}, "name"
	)
	if file_name:
		frappe.db.set_value(
			"File", file_name, {"attached_to_doctype": doc.doctype, "attached_to_name": doc.name}
		)


def get_party_address(party_type, party):
	"""(địa chỉ một dòng, điện thoại) từ địa chỉ mặc định của đối tác."""
	from frappe.contacts.doctype.address.address import get_default_address

	address_name = get_default_address(party_type, party)
	if not address_name:
		return None, None
	address = frappe.db.get_value(
		"Address",
		address_name,
		["address_line1", "address_line2", "city", "state", "country", "phone"],
		as_dict=True,
	)
	parts = [address.address_line1, address.address_line2, address.city, address.state, address.country]
	return ", ".join(p for p in parts if p), address.phone
