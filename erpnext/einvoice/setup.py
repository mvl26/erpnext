# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Dựng custom field trên Sales Invoice (mục C5), hai Role của Giai đoạn 2, hai mẫu email.

Từ bản 3.0 hóa đơn lập từ Sales Invoice. Bảy custom field trên Delivery Note của
bản 2.0 vẫn được dựng nhưng **ẩn**: sáu hóa đơn đã phát hành theo bản 2.0 vẫn
ghi bản sao vào đó, xóa đi là mất dấu.

Chạy được nhiều lần: gọi lại không nhân đôi trường hay quyền. Được gọi từ patch
(cho site đang chạy) và từ VN company setup (cho công ty mới).
"""

import hashlib

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property

from erpnext.einvoice.constants import STATUSES

# Kế toán làm nháp, gửi khách, xem PDF. Kế toán trưởng thêm quyền phát hành,
# điều chỉnh, thay thế, hủy — tức là mọi hành động tiêu số hóa đơn thật.
ROLE_STAFF = "Kế toán HĐĐT"
ROLE_CHIEF = "Kế toán trưởng HĐĐT"

EINVOICE_STATUS_OPTIONS = "\n".join(("", *STATUSES))


DRAFT_TEMPLATE = "Fast HĐĐT - Bản nháp gửi khách"
ISSUED_TEMPLATE = "Fast HĐĐT - Hóa đơn chính thức"

# Mẫu email nêu chứng từ nguồn: hóa đơn bán, hoặc phiếu giao với bản ghi bản 2.0.
_SOURCE_REF = "{{ doc.sales_invoice or doc.delivery_note }}"
_SOURCE_PHRASE = "{% if doc.sales_invoice %}hóa đơn bán{% else %}phiếu giao{% endif %}"

# Các đoạn của mẫu bản 2.0 và đoạn thay thế — chỉ dùng để nâng mẫu đã có trên site.
_V2_SNIPPETS = (
	("cho phiếu giao\n<b>{{ doc.delivery_note }}</b>", f"cho {_SOURCE_PHRASE}\n<b>{_SOURCE_REF}</b>"),
	("{{ doc.delivery_note }}", _SOURCE_REF),
)

# Mẫu email hóa đơn chính thức theo mẫu Miyano (`docs/fast_miyano/Mau_Email_Gui_Hoa_Don_Miyano.md`,
# mục 6) — khách tra cứu trên cổng Fast bằng mã tra cứu in trên PDF. Mọi biến nằm
# trong `hd` (xem `einvoice.invoice_email.email_context`). Không có `keySearch` (khóa
# API, khách không dùng được) và không có link PDF công khai của ERP (Q6).
ISSUED_SUBJECT = "CÔNG TY TNHH MIYANO VIỆT NAM gửi hóa đơn điện tử số {{ doc.fast_invoice_no }} cho {{ doc.customer_name }}"
ISSUED_HTML = """<p>Kính gửi: {{ hd.nguoi_nhan }} – {{ hd.ten_khach_hang }}</p>
<p>CÔNG TY TNHH MIYANO VIỆT NAM xin trân trọng cảm ơn Quý khách hàng đã tin tưởng và hợp tác.</p>
<p>Chúng tôi xin gửi Quý khách Hóa đơn giá trị gia tăng với các thông tin như sau:</p>
<table cellpadding="4">
<tr><td>Số:</td><td><b>{{ hd.so_hd }}</b></td></tr>
<tr><td>Ngày:</td><td>{{ hd.ngay_hd }}</td></tr>
<tr><td>Ký hiệu:</td><td>{{ hd.ky_hieu }}</td></tr>
{% if hd.ma_cqt %}<tr><td>Mã của cơ quan thuế:</td><td>{{ hd.ma_cqt }}</td></tr>{% endif %}
{% if hd.so_hop_dong_po %}<tr><td>Theo hợp đồng/đơn hàng:</td><td>{{ hd.so_hop_dong_po }}</td></tr>{% endif %}
<tr><td>Tổng tiền thanh toán:</td><td><b>{{ hd.tong_tien }}</b></td></tr>
{% if hd.han_thanh_toan %}<tr><td>Hạn thanh toán:</td><td>{{ hd.han_thanh_toan }}</td></tr>{% endif %}
</table>
{% if hd.ma_tra_cuu %}{% if hd.link_tra_cuu %}<p>Để tra cứu hóa đơn, Quý khách vui lòng nhấn nút
<a href="{{ hd.link_tra_cuu }}" style="display:inline-block;padding:6px 16px;background:#1a73e8;color:#ffffff;text-decoration:none;border-radius:4px;font-weight:bold">TRA CỨU</a>
hoặc truy cập đường dẫn <a href="{{ hd.link_tra_cuu }}">{{ hd.link_tra_cuu }}</a> và nhập mã số: <b>{{ hd.ma_tra_cuu }}</b></p>
{% else %}<p>Để tra cứu hóa đơn, Quý khách vui lòng nhập mã số <b>{{ hd.ma_tra_cuu }}</b> trên trang tra cứu hóa đơn điện tử.</p>
{% endif %}{% endif %}
{% if hd.co_xml %}<p>Đính kèm: hóa đơn dạng PDF và file XML (hóa đơn điện tử gốc).</p>
{% else %}<p>Hóa đơn dạng PDF được đính kèm email này để Quý khách tiện lưu trữ.{% if hd.ma_tra_cuu %}
Quý khách có thể tải file XML (hóa đơn điện tử gốc) tại trang tra cứu.{% endif %}</p>
{% endif %}
<p>Quý khách vui lòng kiểm tra, đối chiếu nội dung ghi trên hóa đơn. Nếu có sai sót hoặc cần
điều chỉnh thông tin (tên đơn vị, mã số thuế, địa chỉ…), xin phản hồi lại email này hoặc
liên hệ trực tiếp để chúng tôi xử lý kịp thời.</p>
<p>Trân trọng kính chào!</p>
<p>{% if hd.nguoi_gui %}{{ hd.nguoi_gui }}<br>{% endif %}CÔNG TY TNHH MIYANO VIỆT NAM
{% if hd.sdt_nguoi_gui or hd.email_nguoi_gui %}<br>{% if hd.sdt_nguoi_gui %}ĐT: {{ hd.sdt_nguoi_gui }}{% endif %}
{% if hd.sdt_nguoi_gui and hd.email_nguoi_gui %} | {% endif %}{% if hd.email_nguoi_gui %}Email: {{ hd.email_nguoi_gui }}{% endif %}{% endif %}</p>"""

# Mẫu hóa đơn chính thức trước bản email tra cứu — giữ nguyên văn để nhận ra mẫu
# chưa bị sửa tay (`upgrade_issued_template`). Không dùng để gửi.
_PREVIOUS_ISSUED_HTML = """<p>Kính gửi Quý khách,</p>
<p>Công ty TNHH Miyano Việt Nam xin gửi hóa đơn điện tử cho {% if doc.sales_invoice %}hóa đơn bán{% else %}phiếu giao{% endif %}
<b>{{ doc.sales_invoice or doc.delivery_note }}</b>.</p>
<table cellpadding="4">
<tr><td>Số hóa đơn</td><td><b>{{ doc.fast_invoice_no }}</b></td></tr>
<tr><td>Ký hiệu</td><td>{{ doc.fast_serial }}</td></tr>
<tr><td>Mẫu số</td><td>{{ doc.fast_pattern }}</td></tr>
<tr><td>Ngày phát hành</td><td>{{ frappe.format_value(doc.fast_signed_date, {"fieldtype": "Date"}) }}</td></tr>
<tr><td>Mã tra cứu</td><td><b>{{ doc.fast_key_search }}</b></td></tr>
{% if doc.public_pdf_url %}<tr><td>Xem / tải hóa đơn</td><td><a href="{{ doc.public_pdf_url }}">{{ doc.public_pdf_url }}</a></td></tr>{% endif %}
<tr><td>Tổng thanh toán</td><td><b>{{ frappe.format_value(doc.total_amount, {"fieldtype": "Currency"}) }}</b></td></tr>
<tr><td>Bằng chữ</td><td>{{ doc.amount_in_words }}</td></tr>
</table>
<p>Quý khách có thể xem và tải hóa đơn qua link ở trên, hoặc dùng <b>mã tra cứu</b> để tra
cứu hóa đơn trên cổng của nhà cung cấp dịch vụ hóa đơn điện tử.</p>
<p>Trân trọng,<br>Công ty TNHH Miyano Việt Nam</p>"""

# Dấu vân tay (md5 của nội dung đã gộp khoảng trắng) của các bản mẫu do hệ thống
# tạo: hằng số cũ ở trên, và bản đang có trên site miyano (đoạn kết khác hằng số
# vì được tạo từ một phiên bản cũ hơn của file này).
_ISSUED_ORIGINAL_FINGERPRINTS = frozenset(
	{
		"9cd370d6cdc5710ca07a3ebc8d45fd5c",
		"9a64dd30e457f9603bd7eaacf4eb0e6e",
	}
)


def setup_einvoice():
	_make_sales_invoice_fields()
	_make_delivery_note_fields()
	_make_roles()
	_grant_permissions()
	_make_email_templates()


def _make_email_templates():
	"""Hai mẫu email của mục E3 / E7.

	Mẫu bản nháp **bắt buộc** có dòng cảnh báo chưa có giá trị pháp lý: bản PDF ở
	trạng thái 01—04 chưa có số hóa đơn, chưa ký số, chưa lên Cơ quan Thuế. Gửi
	đi mà không nói rõ là để khách hiểu nhầm đã có hóa đơn.
	"""
	templates = (
		(
			DRAFT_TEMPLATE,
			"[BẢN NHÁP hóa đơn] {{ doc.sales_invoice or doc.delivery_note }} — Miyano Việt Nam",
			"""<p>Kính gửi Quý khách,</p>
<p>Công ty TNHH Miyano Việt Nam xin gửi <b>BẢN NHÁP</b> hóa đơn cho {% if doc.sales_invoice %}hóa đơn bán{% else %}phiếu giao{% endif %}
<b>{{ doc.sales_invoice or doc.delivery_note }}</b> để Quý khách kiểm tra thông tin: tên đơn vị, mã số thuế,
địa chỉ, tên hàng, số lượng, đơn giá và thuế suất.</p>
<table cellpadding="4">
<tr><td>Đơn vị mua</td><td><b>{{ doc.customer_name }}</b></td></tr>
<tr><td>Mã số thuế</td><td>{{ doc.customer_tax_code or "—" }}</td></tr>
<tr><td>Địa chỉ</td><td>{{ doc.address }}</td></tr>
<tr><td>Tiền hàng</td><td>{{ frappe.format_value(doc.amount, {"fieldtype": "Currency"}) }}</td></tr>
<tr><td>Tiền thuế</td><td>{{ frappe.format_value(doc.tax_amount, {"fieldtype": "Currency"}) }}</td></tr>
<tr><td>Tổng thanh toán</td><td><b>{{ frappe.format_value(doc.total_amount, {"fieldtype": "Currency"}) }}</b></td></tr>
<tr><td>Bằng chữ</td><td>{{ doc.amount_in_words }}</td></tr>
</table>
<p style="color:#b00"><b>Lưu ý: đây là BẢN NHÁP, chưa có số hóa đơn và CHƯA CÓ GIÁ TRỊ PHÁP LÝ.</b>
Sau khi Quý khách xác nhận thông tin chính xác, chúng tôi sẽ phát hành hóa đơn điện tử
chính thức và gửi lại.</p>
<p>Mọi điều chỉnh xin phản hồi lại email này.</p>
<p>Trân trọng,<br>Công ty TNHH Miyano Việt Nam</p>""",
		),
		(ISSUED_TEMPLATE, ISSUED_SUBJECT, ISSUED_HTML),
	)

	for name, subject, response in templates:
		if frappe.db.exists("Email Template", name):
			if name == ISSUED_TEMPLATE:
				upgrade_issued_template()
			_retarget_to_sales_invoice(name)
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Email Template",
				"name": name,
				"subject": subject,
				"use_html": 1,
				"response_html": response,
				"response": response,
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()


def _retarget_to_sales_invoice(name):
	"""Mẫu đã tạo theo bản 2.0 nêu số phiếu giao: bản ghi mới không có phiếu giao nên tiêu đề ra trống.

	Chỉ thay đúng các đoạn của mẫu gốc. Đoạn nào đã bị sửa tay thì để nguyên —
	không đoán chỗ sửa trong nội dung người khác viết; kiểm tra tay mẫu trên site
	sau khi triển khai (mục K7).
	"""
	template = frappe.get_doc("Email Template", name)
	changed = False
	for fieldname in ("subject", "response_html", "response"):
		value = template.get(fieldname) or ""
		updated = value
		for old, new in _V2_SNIPPETS:
			updated = updated.replace(old, new)
		if updated != value:
			template.set(fieldname, updated)
			changed = True
	if changed:
		template.flags.ignore_permissions = True
		template.save()


def upgrade_issued_template():
	"""Thay mẫu email hóa đơn chính thức bằng mẫu Miyano — chỉ khi mẫu còn nguyên bản hệ thống tạo.

	Mẫu kế toán đã sửa tay thì giữ nguyên và ghi Error Log: không đoán chỗ sửa
	trong nội dung người khác viết. Trả ``True`` nếu đã thay.
	"""
	if not frappe.db.exists("Email Template", ISSUED_TEMPLATE):
		return False
	template = frappe.get_doc("Email Template", ISSUED_TEMPLATE)
	html = template.response_html or template.response or ""
	if _fingerprint(html) == _fingerprint(ISSUED_HTML):
		return False
	if _fingerprint(html) not in _ISSUED_ORIGINAL_FINGERPRINTS:
		frappe.log_error(
			title="HĐĐT: giữ nguyên mẫu email đã sửa tay",
			message=(
				f"Mẫu “{ISSUED_TEMPLATE}” đã bị sửa tay nên không được thay bằng mẫu email tra cứu mới. "
				"Mẫu mới cần mã tra cứu ({{ hd.ma_tra_cuu }}) thay cho keySearch — sửa tay theo "
				"docs/fast_miyano/PHAN_TICH_TU_GUI_HDDT_SAU_PHAT_HANH.md mục 4.2."
			),
		)
		return False

	template.update(
		{"subject": ISSUED_SUBJECT, "use_html": 1, "response_html": ISSUED_HTML, "response": ISSUED_HTML}
	)
	template.flags.ignore_permissions = True
	template.save()
	return True


def _fingerprint(html):
	return hashlib.md5(" ".join((html or "").split()).encode()).hexdigest()


def _make_sales_invoice_fields():
	"""Mục C5 — bản sao số hóa đơn / trạng thái HĐĐT trên hóa đơn bán, chỉ để hiển thị.

	Ba ràng buộc, mỗi cái sinh từ một lỗi đã mắc ở bản 2.0:

	- **Không có Link trỏ ngược** về `Fast EInvoice Document`: hai Link trỏ vòng
	  vào nhau từng làm không xóa được bản nháp, không hủy được chứng từ nguồn.
	  Liên kết hiện qua mục Connections của hóa đơn bán.
	- **`no_copy` ở mọi trường**: lõi chép mọi trường trùng tên khi lập hóa đơn
	  bán từ phiếu giao, lập hóa đơn trả hàng hay sửa lại (amend).
	- **Chỉ để hiển thị**: bản sao có thể trôi, không báo cáo nào đọc nó.
	"""
	create_custom_fields(
		{
			"Sales Invoice": [
				dict(
					fieldname="fast_einvoice_section",
					fieldtype="Section Break",
					label="Hóa đơn điện tử",
					insert_after="amended_from",
					collapsible=1,
					depends_on="eval:doc.docstatus > 0",
				),
				dict(
					fieldname="fast_invoice_no",
					fieldtype="Data",
					label="Số HĐĐT",
					insert_after="fast_einvoice_section",
					read_only=1,
					no_copy=1,
					in_standard_filter=1,
				),
				dict(
					fieldname="fast_einvoice_status",
					fieldtype="Select",
					label="Trạng thái HĐĐT",
					options=EINVOICE_STATUS_OPTIONS,
					insert_after="fast_invoice_no",
					read_only=1,
					no_copy=1,
					in_standard_filter=1,
				),
				dict(
					fieldname="fast_einvoice_column",
					fieldtype="Column Break",
					insert_after="fast_einvoice_status",
				),
				dict(
					fieldname="fast_key_search",
					fieldtype="Data",
					label="Mã tra cứu",
					insert_after="fast_einvoice_column",
					read_only=1,
					no_copy=1,
					hidden=1,
					description="Bản sao dự phòng của keySearch, phòng khi chứng từ HĐĐT bị xóa.",
				),
				dict(
					fieldname="fast_einvoice_pdf_url",
					fieldtype="Data",
					options="URL",
					label="Link xem hóa đơn",
					insert_after="fast_key_search",
					read_only=1,
					no_copy=1,
					description="Link công khai tới PDF hóa đơn chính thức — gửi được cho khách.",
				),
			]
		},
		update=True,
	)


def _make_delivery_note_fields():
	"""Bảy trường của bản 2.0 trên phiếu giao — **ẩn, không xóa** (mục C5, K4 #6).

	Sáu hóa đơn đã phát hành theo bản 2.0 vẫn ghi bản sao vào đây. Phiếu giao chỉ
	hiển thị trạng thái suy ra qua hóa đơn bán (`form_state.get_delivery_note_state`).
	"""
	create_custom_fields(
		{
			"Delivery Note": [
				dict(
					fieldname="fast_einvoice_section",
					fieldtype="Section Break",
					label="Hóa đơn điện tử",
					insert_after="is_return",
					collapsible=1,
					hidden=1,
				),
				dict(
					fieldname="fast_einvoice",
					fieldtype="Link",
					label="Chứng từ HĐĐT",
					options="Fast EInvoice Document",
					insert_after="fast_einvoice_section",
					read_only=1,
					no_copy=1,
					hidden=1,
				),
				dict(
					fieldname="fast_invoice_no",
					fieldtype="Data",
					label="Số hóa đơn điện tử",
					insert_after="fast_einvoice",
					read_only=1,
					no_copy=1,
					hidden=1,
				),
				dict(
					fieldname="fast_einvoice_column",
					fieldtype="Column Break",
					insert_after="fast_invoice_no",
					hidden=1,
				),
				dict(
					fieldname="fast_einvoice_status",
					fieldtype="Select",
					label="Trạng thái HĐĐT",
					options=EINVOICE_STATUS_OPTIONS,
					insert_after="fast_einvoice_column",
					read_only=1,
					no_copy=1,
					hidden=1,
				),
				dict(
					fieldname="fast_key_search",
					fieldtype="Data",
					label="Mã tra cứu",
					insert_after="fast_einvoice_status",
					read_only=1,
					no_copy=1,
					hidden=1,
					description="Bản sao dự phòng của keySearch, phòng khi chứng từ HĐĐT bị xóa.",
				),
				dict(
					fieldname="fast_einvoice_pdf_url",
					fieldtype="Data",
					options="URL",
					label="Link xem hóa đơn",
					insert_after="fast_key_search",
					read_only=1,
					no_copy=1,
					hidden=1,
				),
			]
		},
		update=True,
	)


def _make_roles():
	for role in (ROLE_STAFF, ROLE_CHIEF):
		if not frappe.db.exists("Role", role):
			doc = frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1, "is_custom": 1})
			doc.flags.ignore_permissions = True
			doc.insert()


def _grant_permissions():
	"""Kế toán soạn hóa đơn; chỉ kế toán trưởng được xóa.

	Nhật ký chỉ đọc với cả hai role: log là bằng chứng đối chiếu với Fast và Cơ
	quan Thuế, sửa được thì hết là bằng chứng.
	"""
	matrix = (
		("Fast EInvoice Document", ROLE_STAFF, {"read": 1, "write": 1, "create": 1, "delete": 0}),
		("Fast EInvoice Document", ROLE_CHIEF, {"read": 1, "write": 1, "create": 1, "delete": 1}),
		("Fast EInvoice Log", ROLE_STAFF, {"read": 1, "write": 0, "create": 0, "delete": 0}),
		("Fast EInvoice Log", ROLE_CHIEF, {"read": 1, "write": 0, "create": 0, "delete": 0}),
		("Fast EInvoice Settings", ROLE_CHIEF, {"read": 1, "write": 0, "create": 0, "delete": 0}),
		("Fast EInvoice Settings", ROLE_STAFF, {"read": 1, "write": 0, "create": 0, "delete": 0}),
	)
	for doctype, role, properties in matrix:
		if not frappe.db.exists("DocType", doctype):
			continue
		add_permission(doctype, role, 0)
		for name, value in properties.items():
			update_permission_property(doctype, role, 0, name, value)


def is_chief_accountant(user=None):
	"""Ai được bấm các nút tiêu số hóa đơn thật (phát hành, hủy nội bộ)."""
	roles = frappe.get_roles(user or frappe.session.user)
	return ROLE_CHIEF in roles or "System Manager" in roles
