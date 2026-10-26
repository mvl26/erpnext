from frappe.tests.utils import FrappeTestCase

from erpnext.access.permissions.matrix import DocTypeEntry
from erpnext.access.permissions.site import DocTypeInfo, SiteInfo
from erpnext.access.permissions.validate import Problems, validate
from erpnext.access.tests.helpers import small_matrix


def dt(name, submittable=0, single=0, app="erpnext", module="X", high=()):
	return DocTypeInfo(
		name=name,
		app=app,
		module=module,
		is_submittable=bool(submittable),
		issingle=bool(single),
		high_permlevel_fields=frozenset(high),
	)


def site_with(*infos, reports=None):
	return SiteInfo(doctypes={i.name: i for i in infos}, reports=reports or {})


def matrix_with(entries, workflows=None, reports=None):
	m = small_matrix(doctypes=entries)
	m.workflows = workflows or {}
	m.reports = reports or {}
	return m


def has(lines, *needles):
	return any(all(n in line for n in needles) for line in lines)


def wf(states=None, transitions=None, doctypes=("Leave Application",), **extra):
	return {
		"doctypes": list(doctypes),
		"states": states
		if states is not None
		else [
			{"state": "Nháp", "doc_status": 0, "allow_edit": "EMP"},
			{"state": "Đã duyệt", "doc_status": 1, "allow_edit": "LK"},
			{"state": "Từ chối", "doc_status": 0, "allow_edit": "EMP"},
			{"state": "Đã hủy", "doc_status": 2, "allow_edit": "LK"},
		],
		"transitions": transitions if transitions is not None else [],
		**extra,
	}


class TestValidate(FrappeTestCase):
	SHOW_TRANSACTION_COMMIT_WARNINGS = True

	def check_wf(self, workflow, code="WF-LA", dtname="Leave Application"):
		m = matrix_with(
			{dtname: DocTypeEntry(state="matrix", perms={"EMP": "R"}, workflow=code)}, {code: workflow}
		)
		return validate(m, site_with(dt(dtname)))

	def test_clean_matrix_has_no_problems(self):
		m = matrix_with({"Journal Entry": DocTypeEntry(state="matrix", perms={"AM": "CRWSXA"})})
		p = validate(m, site_with(dt("Journal Entry", submittable=1)))
		self.assertIsInstance(p, Problems)
		self.assertEqual(p.errors, [])

	def test_unclassified_doctype_is_error(self):
		m = matrix_with({"ToDo": DocTypeEntry(state="keep_standard")})
		p = validate(m, site_with(dt("ToDo"), dt("Note")))
		self.assertTrue(has(p.errors, "Note", "9.3.1"))
		self.assertFalse(has(p.errors, "ToDo"))

	def test_matrix_doctype_missing_on_site_is_warning(self):
		m = matrix_with({"Ghost": DocTypeEntry(state="g1_only")})
		p = validate(m, site_with())
		self.assertTrue(has(p.warnings, "Ghost"))
		self.assertEqual(p.errors, [])

	def test_foreign_app_doctype_is_warning_only(self):
		m = matrix_with({"Asset Repair": DocTypeEntry(state="matrix", perms={"AM": "CRWSXAD"})})
		p = validate(m, site_with(dt("Asset Repair", submittable=1, app="assetcore")))
		self.assertTrue(has(p.warnings, "Asset Repair"))
		self.assertEqual(p.errors, [])

	def test_submit_on_non_submittable_is_error(self):
		m = matrix_with({"Supplier": DocTypeEntry(state="matrix", perms={"PM": "CRWS"})})
		p = validate(m, site_with(dt("Supplier")))
		self.assertTrue(has(p.errors, "Supplier", "S/X/A"))

	def test_delete_on_submittable_is_error(self):
		m = matrix_with({"Journal Entry": DocTypeEntry(state="matrix", perms={"AM": "CRWSXAD"})})
		p = validate(m, site_with(dt("Journal Entry", submittable=1)))
		self.assertTrue(has(p.errors, "Journal Entry", "quyền D (delete)"))

	def test_submittable_without_submit_is_error_unless_exempt(self):
		entries = {"Journal Entry": DocTypeEntry(state="matrix", perms={"AM": "CRW"})}
		p = validate(matrix_with(entries), site_with(dt("Journal Entry", submittable=1)))
		self.assertTrue(has(p.errors, "Journal Entry", "không role nào có S"))
		entries = {"Leave Ledger Entry": DocTypeEntry(state="matrix", perms={"HM": "R"})}
		p = validate(matrix_with(entries), site_with(dt("Leave Ledger Entry", submittable=1)))
		self.assertEqual(p.errors, [])

	def test_single_with_extra_rights_is_error(self):
		m = matrix_with({"Buying Settings": DocTypeEntry(state="matrix", perms={"PM": "RWP"})})
		p = validate(m, site_with(dt("Buying Settings", single=1)))
		self.assertTrue(has(p.errors, "Buying Settings", "Single"))

	def test_undeclared_high_permlevel_field_is_error(self):
		m = matrix_with({"Item": DocTypeEntry(state="matrix", perms={"IM": "CRW"})})
		p = validate(m, site_with(dt("Item", high=["valuation_rate"])))
		self.assertTrue(has(p.errors, "Item", "G9", "valuation_rate"))

	def test_keep_standard_skips_g9(self):
		m = matrix_with({"Item": DocTypeEntry(state="keep_standard")})
		p = validate(m, site_with(dt("Item", high=["valuation_rate"])))
		self.assertEqual(p.errors, [])

	def test_permlevel_cell_mismatch_is_error(self):
		spec = {1: {"fields": ["valuation_rate"], "read": ["AM"], "write": ["AM"]}}
		entry = DocTypeEntry(state="matrix", perms={"IM": "CRW W1 W2", "AM": "R"}, permlevel=spec)
		p = validate(matrix_with({"Item": entry}), site_with(dt("Item", high=["valuation_rate"])))
		self.assertTrue(has(p.errors, "Item", "G9", "W1"))
		self.assertTrue(has(p.errors, "Item", "G9", "permlevel 2"))

	def test_permlevel_consistent_passes(self):
		spec = {1: {"fields": ["valuation_rate"], "read": ["AM"], "write": ["IM"]}}
		entry = DocTypeEntry(state="matrix", perms={"IM": "CRW W1", "AM": "R R1"}, permlevel=spec)
		p = validate(matrix_with({"Item": entry}), site_with(dt("Item", high=["valuation_rate"])))
		self.assertEqual(p.errors, [])

	def test_permlevel_entry_needs_keys(self):
		entry = DocTypeEntry(state="matrix", perms={"IM": "CRW"}, permlevel={1: {"fields": ["x"]}})
		p = validate(matrix_with({"Item": entry}), site_with(dt("Item")))
		self.assertTrue(has(p.errors, "Item", "G9", "read"))

	def test_unknown_role_code_is_error(self):
		m = matrix_with({"Supplier": DocTypeEntry(state="matrix", perms={"ZZZ": "R"})})
		p = validate(m, site_with(dt("Supplier")))
		self.assertTrue(has(p.errors, "Supplier", "ZZZ"))

	def test_profile_with_unknown_item_is_error(self):
		m = matrix_with({})
		m.role_profiles = {"Prof": ["NOPE"]}
		p = validate(m, site_with())
		self.assertTrue(has(p.errors, "Prof", "NOPE"))

	def test_pda_only_on_ref_master(self):
		m = matrix_with({"Supplier": DocTypeEntry(state="matrix", perms={"PM": "R"}, pda=True)})
		p = validate(m, site_with(dt("Supplier")))
		self.assertTrue(has(p.errors, "Supplier", "pda"))

	def test_scope_problems_are_errors(self):
		entry = DocTypeEntry(state="matrix", perms={"PM": "R"}, scope={"PM": "x", "PU": "o"})
		p = validate(matrix_with({"Supplier": entry}), site_with(dt("Supplier")))
		self.assertTrue(has(p.errors, "Supplier", "scope", "x"))
		self.assertTrue(has(p.errors, "Supplier", "scope", "PU"))

	def test_report_role_without_read_on_ref_doctype_is_error(self):
		entries = {"Supplier": DocTypeEntry(state="matrix", perms={"PM": "R"})}
		m = matrix_with(entries, reports={"Supplier Report": ["PM", "STU"]})
		p = validate(m, site_with(dt("Supplier"), reports={"Supplier Report": "Supplier"}))
		self.assertTrue(has(p.errors, "Supplier Report", "R3", "STU"))
		self.assertFalse(has(p.errors, "Supplier Report", "PM"))

	def test_report_not_on_site_is_error_and_unknown_ref_is_warning(self):
		entries = {"Supplier": DocTypeEntry(state="matrix", perms={"PM": "R"})}
		m = matrix_with(entries, reports={"Gone": ["PM"], "Other": ["PM"], "NoRef": ["PM"]})
		p = validate(m, site_with(dt("Supplier"), reports={"Other": "Elsewhere", "NoRef": ""}))
		self.assertTrue(has(p.errors, "Gone"))
		self.assertTrue(has(p.warnings, "Other", "R3"))
		self.assertFalse(has(p.errors, "Other") or has(p.errors, "NoRef"))

	def test_workflow_state_field_must_be_workflow_state(self):
		p = self.check_wf(wf(workflow_state_field="status"))
		self.assertTrue(has(p.errors, "WF-LA", "9.2.1"))

	def test_first_draft_state_must_be_nhap(self):
		states = [
			{"state": "Soạn", "doc_status": 0},
			{"state": "Đã duyệt", "doc_status": 1},
			{"state": "Đã hủy", "doc_status": 2},
		]
		self.assertTrue(has(self.check_wf(wf(states=states)).errors, "WF-LA", "9.2.4", "Nháp"))

	def test_first_submitted_state_must_not_be_rejected(self):
		states = [
			{"state": "Nháp", "doc_status": 0},
			{"state": "Từ chối", "doc_status": 1},
			{"state": "Đã duyệt", "doc_status": 1},
			{"state": "Đã hủy", "doc_status": 2},
		]
		self.assertTrue(has(self.check_wf(wf(states=states)).errors, "WF-LA", "9.2.4", "Từ chối"))

	def test_cancelled_state_required_and_unreachable(self):
		states = [{"state": "Nháp", "doc_status": 0}, {"state": "Đã duyệt", "doc_status": 1}]
		self.assertTrue(has(self.check_wf(wf(states=states)).errors, "WF-LA", "thiếu state"))
		trans = [{"from": "Đã duyệt", "action": "Hủy", "to": "Đã hủy", "roles": ["HM"]}]
		self.assertTrue(has(self.check_wf(wf(transitions=trans)).errors, "WF-LA", "dẫn vào"))

	def test_draft_only_workflow_on_non_submittable_needs_no_cancelled_state(self):
		states = [{"state": "Nháp", "doc_status": 0}, {"state": "Đã duyệt", "doc_status": 0}]
		p = self.check_wf(wf(states=states, doctypes=("Bank Account",)), "WF-BA", "Bank Account")
		self.assertEqual(p.errors, [])
		m = matrix_with(
			{"Bank Account": DocTypeEntry(state="matrix", perms={"AU": "R"}, workflow="WF-BA")},
			{"WF-BA": wf(states=states, doctypes=("Bank Account",))},
		)
		p = validate(m, site_with(dt("Bank Account", submittable=1)))
		self.assertTrue(has(p.errors, "WF-BA", "thiếu state"))

	def test_update_doctypes_limits_update_field_check(self):
		states = [
			{"state": "Nháp", "doc_status": 0},
			{
				"state": "Đã duyệt",
				"doc_status": 1,
				"update_field": "approval_status",
				"update_value": "Approved",
				"update_doctypes": ["Expense Claim"],
			},
			{"state": "Đã hủy", "doc_status": 2},
		]
		entries = {
			dt_name: DocTypeEntry(state="matrix", perms={"EMP": "R"}, workflow="WF-EC")
			for dt_name in ("Expense Claim", "Employee Advance")
		}
		workflow = wf(states=states, doctypes=("Expense Claim", "Employee Advance"))
		site = site_with(dt("Expense Claim"), dt("Employee Advance"))
		self.assertEqual(validate(matrix_with(entries, {"WF-EC": workflow}), site).errors, [])
		del states[1]["update_doctypes"]
		p = validate(matrix_with(entries, {"WF-EC": workflow}), site)
		self.assertTrue(has(p.errors, "WF-EC", "9.2.2", "Employee Advance"))

	def test_workflow_creator_codes_checked(self):
		self.assertTrue(has(self.check_wf(wf(creators=["QQQ"])).errors, "WF-LA", "creators", "QQQ"))
		self.assertTrue(has(self.check_wf(wf()).warnings, "WF-LA", "Mở lại"))

	def test_wf_bt_missing_cancelled_is_warning_only(self):
		states = [{"state": "Nháp", "doc_status": 0}, {"state": "Đã duyệt", "doc_status": 1}]
		p = self.check_wf(wf(states=states, doctypes=("Business Trip",)), "WF-BT", "Business Trip")
		self.assertTrue(has(p.warnings, "WF-BT", "Đã hủy"))
		self.assertEqual(p.errors, [])

	def test_update_field_on_controller_status_is_error(self):
		states = [
			{"state": "Nháp", "doc_status": 0},
			{"state": "Đã duyệt", "doc_status": 1, "update_field": "status", "update_value": "Approved"},
			{"state": "Đã hủy", "doc_status": 2},
		]
		p = self.check_wf(wf(states=states, doctypes=("Sales Order",)), "WF-SO", "Sales Order")
		self.assertTrue(has(p.errors, "WF-SO", "9.2.2", "Sales Order"))

	def test_allowed_update_field_passes(self):
		states = [
			{"state": "Nháp", "doc_status": 0},
			{"state": "Đã duyệt", "doc_status": 1, "update_field": "status", "update_value": "Approved"},
			{"state": "Đã hủy", "doc_status": 2},
		]
		self.assertEqual(self.check_wf(wf(states=states)).errors, [])

	def test_self_approve_must_target_first_submitted_state(self):
		states = [
			{"state": "Nháp", "doc_status": 0},
			{"state": "Đã duyệt", "doc_status": 1},
			{"state": "Đã ghi sổ", "doc_status": 1},
			{"state": "Đã hủy", "doc_status": 2},
		]
		trans = [{"from": "Nháp", "action": "Ghi sổ", "to": "Đã ghi sổ", "roles": ["AU"]}]
		self.assertTrue(has(self.check_wf(wf(states=states, transitions=trans)).errors, "WF-LA", "R-17"))
		trans[0]["to"] = "Đã duyệt"
		self.assertFalse(has(self.check_wf(wf(states=states, transitions=trans)).errors, "R-17"))

	def test_workflow_link_consistency(self):
		m = matrix_with({"Supplier": DocTypeEntry(state="matrix", perms={"PM": "R"}, workflow="WF-X")})
		p = validate(m, site_with(dt("Supplier")))
		self.assertTrue(has(p.errors, "Supplier", "WF-X"))
		m = matrix_with(
			{"Supplier": DocTypeEntry(state="matrix", perms={"PM": "R"})},
			{"WF-X": wf(doctypes=("Supplier",))},
		)
		p = validate(m, site_with(dt("Supplier")))
		self.assertTrue(has(p.errors, "WF-X", "Supplier"))

	def test_transition_role_must_exist(self):
		trans = [{"from": "Nháp", "action": "Gửi", "to": "Đã duyệt", "roles": ["QQQ"]}]
		self.assertTrue(has(self.check_wf(wf(transitions=trans)).errors, "WF-LA", "QQQ"))

	def test_non_string_cell_is_error_not_exception(self):
		m = matrix_with({"Supplier": DocTypeEntry(state="matrix", perms={"PM": 5}, scope={"PM": 3})})
		p = validate(m, site_with(dt("Supplier")))
		self.assertTrue(has(p.errors, "Supplier", "cell"))
		self.assertTrue(has(p.errors, "Supplier", "scope"))

	def test_state_missing_doc_status_is_error(self):
		states = [{"state": "Nháp"}, {"state": "Đã hủy", "doc_status": 2}]
		self.assertTrue(has(self.check_wf(wf(states=states)).errors, "WF-LA", "9.2", "doc_status"))

	def test_non_dict_transition_is_error(self):
		p = self.check_wf(wf(transitions=["Nháp"]))
		self.assertTrue(has(p.errors, "WF-LA", "9.2", "transition"))

	def test_empty_workflow_doctypes_is_error(self):
		m = matrix_with({}, {"WF-X": wf(doctypes=())})
		self.assertTrue(has(validate(m, site_with()).errors, "WF-X", "9.3", "doctypes trống"))

	def test_cancelled_state_needs_exact_name(self):
		states = [
			{"state": "Nháp", "doc_status": 0},
			{"state": "Đã duyệt", "doc_status": 1},
			{"state": "Hủy", "doc_status": 2},
		]
		self.assertTrue(has(self.check_wf(wf(states=states)).errors, "WF-LA", "thiếu state"))

	def test_report_with_bad_ref_cell_does_not_raise(self):
		entries = {"Supplier": DocTypeEntry(state="matrix", perms={"PM": "Z"})}
		m = matrix_with(entries, reports={"Supplier Report": ["PM"]})
		p = validate(m, site_with(dt("Supplier"), reports={"Supplier Report": "Supplier"}))
		self.assertTrue(has(p.errors, "Supplier", "cell"))

	def test_pru_is_exempt_from_r3(self):
		entries = {"Supplier": DocTypeEntry(state="matrix", perms={"PM": "R"})}
		m = matrix_with(entries, reports={"Supplier Report": ["PM", "PRU"]})
		p = validate(m, site_with(dt("Supplier"), reports={"Supplier Report": "Supplier"}))
		self.assertEqual(p.errors, [])

	def test_transition_role_needs_write_and_submit(self):
		trans = [
			{"from": "Nháp", "action": "Gửi", "to": "Đã duyệt", "roles": ["EMP", "HM"]},
			{"from": "Nháp", "action": "Từ chối", "to": "Từ chối", "roles": ["EMP"]},
		]
		m = matrix_with(
			{
				"Leave Application": DocTypeEntry(
					state="matrix", perms={"EMP": "R", "HM": "RW"}, workflow="WF-LA"
				)
			},
			{"WF-LA": wf(transitions=trans)},
		)
		p = validate(m, site_with(dt("Leave Application", submittable=1)))
		self.assertTrue(has(p.errors, "WF-LA", "9.2.T", "EMP", "write", "Leave Application"))
		self.assertTrue(has(p.errors, "WF-LA", "9.2.T", "HM", "submit"))
		self.assertFalse(has(p.errors, "9.2.T", "HM", "write"))

	def test_transition_with_enough_rights_passes(self):
		trans = [{"from": "Nháp", "action": "Gửi", "to": "Đã duyệt", "roles": ["HM"]}]
		m = matrix_with(
			{"Leave Application": DocTypeEntry(state="matrix", perms={"HM": "RWS"}, workflow="WF-LA")},
			{"WF-LA": wf(transitions=trans)},
		)
		p = validate(m, site_with(dt("Leave Application", submittable=1)))
		self.assertFalse(has(p.errors, "9.2.T"))

	def test_per_doctype_condition_key_must_be_in_doctypes(self):
		trans = [
			{
				"from": "Nháp",
				"action": "Gửi",
				"to": "Từ chối",
				"roles": ["EMP"],
				"per_doctype_condition": {"Leave Aplication": "doc.x", "Leave Application": "doc.y"},
			}
		]
		p = self.check_wf(wf(transitions=trans))
		self.assertTrue(has(p.errors, "WF-LA", "9.3.K", "Leave Aplication"))
		self.assertFalse(has(p.errors, "9.3.K", "'Leave Application'"))

	def test_empty_report_page_or_role_names_is_error(self):
		m = matrix_with({}, reports={"Empty Report": []})
		m.pages = {"empty-page": []}
		m.roles["PU"].names = ()
		p = validate(m, site_with(reports={"Empty Report": None}))
		self.assertTrue(has(p.errors, "Empty Report", "11.2.E"))
		self.assertTrue(has(p.errors, "empty-page", "11.2.E"))
		self.assertTrue(has(p.errors, "PU", "11.2.E"))

	def test_except_doctypes_must_be_in_doctypes(self):
		trans = [
			{"from": "Nháp", "action": "Gửi", "to": "Từ chối", "roles": ["EMP"], "except_doctypes": ["Nope"]}
		]
		self.assertTrue(has(self.check_wf(wf(transitions=trans)).errors, "WF-LA", "9.3.K", "except_doctypes"))

	def test_except_doctypes_skips_transition_rights_check(self):
		trans = [
			{
				"from": "Nháp",
				"action": "Gửi",
				"to": "Từ chối",
				"roles": ["EMP"],
				"except_doctypes": ["Leave Application"],
			}
		]
		self.assertFalse(has(self.check_wf(wf(transitions=trans)).errors, "9.2.T"))
