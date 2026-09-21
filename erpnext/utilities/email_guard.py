# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Chặn email tới địa chỉ đã ngừng gửi và chặn vòng lặp thư trả về (bounce).

Hai luật này trước đây là Server Script tạo trên giao diện ("Khong gui toi dia
chi da ngung gui", "Chan vong lap thu tra ve (bounce)"). Server Script nằm trong
DB nhưng công tắc bật nó nằm ở ``common_site_config.json``: chuyển server bằng
backup là mang theo script mà không mang theo công tắc, và mọi chức năng gửi mail
(kể cả gửi hóa đơn Fast) chết với lỗi "Server Scripts are disabled" dù chẳng
liên quan gì tới script. Đưa vào code thì luật đi theo git, có test, không phụ
thuộc cấu hình bench.
"""

import frappe

BOUNCE_SENDER_MARKERS = ("mailer-daemon", "postmaster")

BOUNCE_SUBJECT_MARKERS = (
	"delivery status notification",
	"undelivered mail",
	"mail delivery failed",
	"delivery has failed",
	"returned mail",
	"failure notice",
	"delivery incomplete",
)

# Dấu hiệu lỗi vĩnh viễn — địa chỉ không tồn tại, gửi lại cũng vô ích.
HARD_BOUNCE_MARKERS = (
	"address not found",
	"5.1.1",
	"user unknown",
	"no such user",
	"does not exist",
	"recipient address rejected",
	"mailbox unavailable",
	"550 5.1",
	"account that you tried to reach",
)

# Địa chỉ chứa các chuỗi này không bao giờ bị đưa vào danh sách ngừng gửi:
# địa chỉ nội bộ, của máy chủ thư, hoặc địa chỉ hệ thống.
SKIP_ADDRESS_MARKERS = (
	"miyano.com.vn",
	"medcons.vn",
	"googlemail.com",
	"google.com",
	"mailer-daemon",
	"postmaster",
	"gmail-smtp",
	"example.com",
	"sentry",
	"erpnext.com",
	"noreply",
	"no-reply",
)

# Chỉ đọc phần đầu thư báo lỗi — phần sau thường trích nguyên thư gốc, quét cả
# vào là đưa nhầm địa chỉ khách vào danh sách ngừng gửi.
BOUNCE_HEAD_CHARS = 1800
FINAL_RECIPIENT_CHARS = 200

ADDRESS_SEPARATORS = (
	"<",
	">",
	"&nbsp;",
	"&lt;",
	"&gt;",
	"&quot;",
	"(",
	")",
	",",
	";",
	"=",
	"[",
	"]",
	"|",
	"*",
	"rfc822",
	":",
)


def is_globally_unsubscribed(email):
	return bool(frappe.db.exists("Email Unsubscribe", {"email": email, "global_unsubscribe": 1}))


# --- Email Queue: before_insert ----------------------------------------------


def block_unsubscribed_recipients(doc, method=None):
	"""Bỏ người nhận đã ngừng gửi; nếu không còn ai thì đánh dấu thư là lỗi.

	Không ``throw``: thư lỗi nằm lại trong Email Queue với lý do rõ ràng, còn
	chứng từ gốc (hóa đơn, báo giá…) vẫn lưu được bình thường.
	"""
	keep, blocked = [], []
	for row in doc.recipients or []:
		email = (row.recipient or "").strip().lower()
		if email and is_globally_unsubscribed(email):
			blocked.append(email)
		else:
			keep.append(row)

	if not blocked:
		return
	if keep:
		doc.set("recipients", keep)
	else:
		doc.status = "Error"
		doc.error = "Da chan gui: dia chi khong ton tai / da ngung gui - " + ", ".join(blocked)


# --- Communication: before_insert --------------------------------------------


def handle_bounce(doc, method=None):
	"""Tách thư trả về khỏi chứng từ và ngừng gửi tới địa chỉ không tồn tại."""
	if (doc.sent_or_received or "") != "Received" or not is_bounce(doc):
		return

	# Gỡ liên kết với chứng từ để ERP không chuyển tiếp thư trả về cho khách —
	# chuyển tiếp lại sinh bounce mới, thành vòng lặp.
	doc.reference_doctype = None
	doc.reference_name = None
	doc.in_reply_to = None
	doc.unread_notification_sent = 1

	body = (doc.content or "").lower()
	if not any(marker in body for marker in HARD_BOUNCE_MARKERS):
		return
	for email in extract_bounced_addresses(body):
		unsubscribe(email)


def is_bounce(doc):
	sender = (doc.sender or "").lower()
	subject = (doc.subject or "").lower()
	return any(m in sender for m in BOUNCE_SENDER_MARKERS) or any(
		m in subject for m in BOUNCE_SUBJECT_MARKERS
	)


def extract_bounced_addresses(body):
	head = body[:BOUNCE_HEAD_CHARS]
	for part in body.split("final-recipient")[1:]:
		head += " " + part[:FINAL_RECIPIENT_CHARS]
	for separator in ADDRESS_SEPARATORS:
		head = head.replace(separator, " ")

	found = []
	for token in head.split():
		token = token.strip(".").strip("'").strip()
		if not _looks_like_address(token):
			continue
		if any(marker in token for marker in SKIP_ADDRESS_MARKERS):
			continue
		if token not in found:
			found.append(token)
	return found


def _looks_like_address(token):
	return "@" in token and 6 < len(token) < 120 and "." in token.split("@")[-1]


def unsubscribe(email):
	if not is_globally_unsubscribed(email):
		frappe.get_doc({"doctype": "Email Unsubscribe", "email": email, "global_unsubscribe": 1}).insert(
			ignore_permissions=True
		)
	for name in frappe.get_all("Contact", filters={"email_id": email}, pluck="name"):
		frappe.db.set_value("Contact", name, "unsubscribed", 1)
	if frappe.db.exists("User", email):
		frappe.db.set_value("User", email, "unsubscribed", 1)
