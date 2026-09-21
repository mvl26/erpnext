# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Fixture dùng chung cho test Đối chiếu công nợ.

Site ``miyano`` không có ``_Test Company``: test tự tạo công ty VN (TT99) và đối tác có
hậu tố ngẫu nhiên — ``FrappeTestCase`` rollback theo class, không theo từng test.
Custom field của module đã được migrate tạo sẵn; KHÔNG gọi ``setup.run()`` trong test vì
DDL sẽ commit giao dịch test.
"""

import frappe

from erpnext.regional.vietnam.test_setup import make_vn_company


def get_company(name, abbr):
	if frappe.db.exists("Company", name):
		return name
	return make_vn_company(name, abbr)


def account(company, number):
	return frappe.db.get_value("Account", {"company": company, "account_number": number}, "name")


def make_party(party_type, prefix="_Test DR", **fields):
	name = f"{prefix} {party_type} {frappe.generate_hash(length=6)}"
	if party_type == "Customer":
		doc = {
			"doctype": "Customer",
			"customer_name": name,
			"customer_group": "All Customer Groups",
			"territory": "All Territories",
		}
	else:
		doc = {"doctype": "Supplier", "supplier_name": name, "supplier_group": "All Supplier Groups"}
	doc.update(fields)
	return frappe.get_doc(doc).insert(ignore_permissions=True).name


def post(company, party_type, party, dr, cr, posting_date, account_name=None):
	"""JE ghi Nợ/Có TK 331/131 (hoặc ``account_name``) của đối tác, đối ứng 4211."""
	party_account = account_name or account(company, "331" if party_type == "Supplier" else "131")
	je = frappe.new_doc("Journal Entry")
	je.company = company
	je.posting_date = posting_date
	je.append(
		"accounts",
		{
			"account": party_account,
			"party_type": party_type,
			"party": party,
			"debit_in_account_currency": dr,
			"credit_in_account_currency": cr,
		},
	)
	je.append(
		"accounts",
		{
			"account": account(company, "4211"),
			"debit_in_account_currency": cr,
			"credit_in_account_currency": dr,
		},
	)
	je.flags.ignore_permissions = True
	je.insert()
	je.submit()
	return je


def minimal_pdf_bytes(marker=""):
	"""PDF hợp lệ tối thiểu (có xref) — Frappe parse file PDF khi lưu nên byte giả bị từ chối."""
	objects = [
		b"<</Type/Catalog/Pages 2 0 R>>",
		b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
		b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 3 3]>>",
	]
	out = b"%PDF-1.4\n%" + marker.encode() + b"\n"
	offsets = []
	for i, body in enumerate(objects, 1):
		offsets.append(len(out))
		out += f"{i} 0 obj".encode() + body + b"endobj\n"
	xref = len(out)
	out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
	out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
	out += f"trailer<</Size {len(objects) + 1}/Root 1 0 R>>\nstartxref\n{xref}\n%%EOF".encode()
	return out
