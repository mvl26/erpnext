# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Định nghĩa 12 điểm thông báo chuỗi cung ứng.

Đây là nguồn sự thật cho hạt giống cấu hình (`setup.seed_points`) và cho bộ định
tuyến sự kiện (`events.on_submit_handler`). Sửa câu chữ ở đây chỉ đổi giá trị hạt
giống cho site mới — site đang chạy giữ nguyên bản ghi nghiệp vụ đã chỉnh.

Tham chiếu: docs/05c_Spec_KyThuat_Plan_Thong_Bao.md muc 7 va Phu luc A/C.
"""

SUBMIT = "Submit"
DUE_REMINDER = "Due Reminder"

#: Mốc nhắc hạn, tính bằng số ngày trước hạn.
DUE_MILESTONES = (7, 3, 1)

#: Vai trò quản trị cấu hình thông báo (quyết định D2).
ADMIN_ROLE = "Quản trị thông báo"

#: Âm báo in-app (quyết định D6) — tên file trong frappe/public/sounds.
SOUND = "alert"

#: Sự kiện realtime riêng của Miyano, kèm dữ liệu để dựng toast.
REALTIME_EVENT = "supply_notification"

#: Tên phòng ban (chưa kèm viết tắt công ty) dùng khi gieo hạt giống.
DEPT_STOCK = "Kho"
DEPT_PURCHASE = "Mua hàng"
DEPT_SALES = "Kinh doanh"
DEPT_ACCOUNTS = "Kế toán"

#: Hai phòng ban hàm cài đặt tạo bù nếu site chưa có (quyết định D3).
DEPARTMENTS_TO_CREATE = (DEPT_STOCK, DEPT_PURCHASE)

PREFIX = "[SupplyCore]"

_CLOSING = ""

POINTS = (
	{
		"code": "NTF-01",
		"title": "Đơn bán hàng · Ghi sổ",
		"reference_doctype": "Sales Order",
		"trigger_event": SUBMIT,
		"filter_field": None,
		"filter_values": (),
		"filter_note": "Mọi đơn bán hàng đã ghi sổ.",
		"departments": (DEPT_STOCK,),
		"notify_owner": 1,
		"notify_external": 0,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": "customer_name",
		"amount_field": "grand_total",
		"date_field": "transaction_date",
		"show_stock_report": 1,
		"subject_template": (
			"{{ prefix }} Đơn bán hàng {{ doc.name }} của khách {{ party_name }}"
			" vừa ghi sổ – đề nghị kiểm tra tồn kho"
		),
		"intro_template": (
			"Đơn bán hàng {{ doc.name }} – khách hàng {{ party_name }} vừa được ghi sổ"
			" bởi {{ owner_name }} ngày {{ date }}."
		),
		"action_template": (
			"Vui lòng kiểm tra tồn kho các mặt hàng dưới đây và phản hồi trong ngày."
			" Nếu đủ hàng: soạn hàng và giao (Pick List / Phiếu giao hàng)."
			" Nếu thiếu: tạo Yêu cầu vật tư loại Mua hàng ngay từ đơn này."
		),
		"external_subject_template": "",
		"external_intro_template": "",
	},
	{
		"code": "NTF-02",
		"title": "Yêu cầu vật tư · Ghi sổ",
		"reference_doctype": "Material Request",
		"trigger_event": SUBMIT,
		"filter_field": "material_request_type",
		"filter_values": ("Purchase",),
		"filter_note": "Chỉ Yêu cầu vật tư loại Mua hàng (Purchase).",
		"departments": (DEPT_PURCHASE,),
		"notify_owner": 0,
		"notify_external": 0,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": None,
		"amount_field": None,
		"date_field": "transaction_date",
		"show_stock_report": 0,
		"subject_template": "{{ prefix }} Yêu cầu vật tư {{ doc.name }} đang chờ tạo Đơn mua hàng",
		"intro_template": (
			"Yêu cầu vật tư {{ doc.name }} do {{ owner_name }} lập ngày {{ date }} đã được ghi sổ."
		),
		"action_template": "Đề nghị xem xét, chọn nhà cung cấp và tạo Đơn mua hàng.",
		"external_subject_template": "",
		"external_intro_template": "",
	},
	{
		"code": "NTF-03",
		"title": "Đơn mua hàng · Ghi sổ",
		"reference_doctype": "Purchase Order",
		"trigger_event": SUBMIT,
		"filter_field": None,
		"filter_values": (),
		"filter_note": "Mọi đơn mua hàng đã ghi sổ.",
		"departments": (DEPT_STOCK,),
		"notify_owner": 0,
		"notify_external": 1,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": "supplier_name",
		"amount_field": "grand_total",
		"date_field": "schedule_date",
		"show_stock_report": 0,
		"subject_template": (
			"{{ prefix }} Đơn mua hàng {{ doc.name }} – NCC {{ party_name }}"
			" – dự kiến nhận hàng {{ date }}"
		),
		"intro_template": (
			"Đơn mua hàng {{ doc.name }} gửi nhà cung cấp {{ party_name }} đã được ghi sổ,"
			" giá trị {{ amount }}, dự kiến nhận hàng ngày {{ date }}."
		),
		"action_template": "Đề nghị bố trí vị trí kho và theo dõi lịch nhận hàng.",
		"external_subject_template": (
			"{{ prefix }} Đơn mua hàng {{ doc.name }} từ Miyano – dự kiến giao {{ date }}"
		),
		"external_intro_template": (
			"Kính gửi Quý công ty {{ party_name }},<br><br>"
			"Miyano đã phát hành Đơn mua hàng {{ doc.name }} ngày {{ date }},"
			" giá trị {{ amount }}. Kính đề nghị Quý công ty xác nhận đơn hàng và lịch giao."
		),
	},
	{
		"code": "NTF-04",
		"title": "Phiếu nhập mua · Ghi sổ",
		"reference_doctype": "Purchase Receipt",
		"trigger_event": SUBMIT,
		"filter_field": None,
		"filter_values": (),
		"filter_note": "Mọi phiếu nhập mua đã ghi sổ.",
		"departments": (DEPT_PURCHASE, DEPT_ACCOUNTS),
		"notify_owner": 0,
		"notify_external": 0,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": "supplier_name",
		"amount_field": "grand_total",
		"date_field": "posting_date",
		"show_stock_report": 0,
		"subject_template": (
			"{{ prefix }} Đã nhập kho phiếu {{ doc.name }} từ NCC {{ party_name }}"
			" – đề nghị đối chiếu và tạo hoá đơn mua"
		),
		"intro_template": (
			"Phiếu nhập mua {{ doc.name }} từ nhà cung cấp {{ party_name }} đã ghi sổ"
			" ngày {{ date }}, giá trị {{ amount }}."
		),
		"action_template": "Đề nghị đối chiếu Đơn mua hàng với Phiếu nhập, sau đó tạo Hoá đơn mua.",
		"external_subject_template": "",
		"external_intro_template": "",
	},
	{
		"code": "NTF-05",
		"title": "Hoá đơn mua · Ghi sổ",
		"reference_doctype": "Purchase Invoice",
		"trigger_event": SUBMIT,
		"filter_field": None,
		"filter_values": (),
		"filter_note": "Mọi hoá đơn mua đã ghi sổ.",
		"departments": (DEPT_ACCOUNTS,),
		"notify_owner": 0,
		"notify_external": 0,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": "supplier_name",
		"amount_field": "grand_total",
		"date_field": "due_date",
		"show_stock_report": 0,
		"subject_template": "{{ prefix }} Hoá đơn mua {{ doc.name }} – hạn thanh toán {{ date }}",
		"intro_template": (
			"Hoá đơn mua {{ doc.name }} của nhà cung cấp {{ party_name }} đã ghi sổ,"
			" giá trị {{ amount }}, hạn thanh toán {{ date }}."
		),
		"action_template": "Đề nghị ghi nhận công nợ và lên lịch chi.",
		"external_subject_template": "",
		"external_intro_template": "",
	},
	{
		"code": "NTF-06",
		"title": "Hoá đơn mua · Nhắc hạn thanh toán",
		"reference_doctype": "Purchase Invoice",
		"trigger_event": DUE_REMINDER,
		"filter_field": None,
		"filter_values": (),
		"filter_note": "Hoá đơn mua đã ghi sổ, còn nợ > 0, đến hạn sau 7 / 3 / 1 ngày.",
		"departments": (DEPT_ACCOUNTS, DEPT_PURCHASE),
		"notify_owner": 0,
		"notify_external": 0,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": "supplier_name",
		"amount_field": "outstanding_amount",
		"date_field": "due_date",
		"show_stock_report": 0,
		"subject_template": (
			"{{ prefix }} Hoá đơn {{ doc.name }} đến hạn thanh toán {{ date }}" " – còn nợ {{ amount }}"
		),
		"intro_template": (
			"Hoá đơn mua {{ doc.name }} của nhà cung cấp {{ party_name }} đến hạn thanh toán"
			" ngày {{ date }}, còn {{ days_left }} ngày, số còn nợ {{ amount }}."
		),
		"action_template": "Đề nghị chuẩn bị chi trả đúng hạn.",
		"external_subject_template": "",
		"external_intro_template": "",
	},
	{
		"code": "NTF-07",
		"title": "Phiếu giao hàng · Ghi sổ",
		"reference_doctype": "Delivery Note",
		"trigger_event": SUBMIT,
		"filter_field": None,
		"filter_values": (),
		"filter_note": "Mọi phiếu giao hàng đã ghi sổ.",
		"departments": (DEPT_SALES,),
		"notify_owner": 0,
		"notify_external": 1,
		"attach_pdf": 1,
		"print_format": "Phiếu xuất kho (02-VT)",
		"party_field": "customer_name",
		"amount_field": "grand_total",
		"date_field": "posting_date",
		"show_stock_report": 0,
		"subject_template": (
			"{{ prefix }} Phiếu giao hàng {{ doc.name }} cho khách {{ party_name }}" " đã xuất kho, đang giao"
		),
		"intro_template": (
			"Phiếu giao hàng {{ doc.name }} cho khách hàng {{ party_name }} đã xuất kho" " ngày {{ date }}."
		),
		"action_template": "Đề nghị theo dõi giao nhận và xác nhận với khách hàng.",
		"external_subject_template": (
			"{{ prefix }} Đơn hàng {{ doc.name }} của Quý khách đã xuất kho, đang giao"
		),
		"external_intro_template": (
			"Kính gửi Quý khách {{ party_name }},<br><br>"
			"Miyano xin thông báo đơn hàng theo phiếu giao {{ doc.name }} đã xuất kho"
			" ngày {{ date }} và đang trên đường giao đến Quý khách."
			" Chi tiết hàng hoá theo phiếu giao đính kèm."
		),
	},
	{
		"code": "NTF-08",
		"title": "Hoá đơn bán · Nhắc hạn thu tiền",
		"reference_doctype": "Sales Invoice",
		"trigger_event": DUE_REMINDER,
		"filter_field": None,
		"filter_values": (),
		"filter_note": "Hoá đơn bán đã ghi sổ, khách còn nợ > 0, đến hạn sau 7 / 3 / 1 ngày.",
		"departments": (DEPT_ACCOUNTS,),
		"notify_owner": 0,
		"notify_external": 0,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": "customer_name",
		"amount_field": "outstanding_amount",
		"date_field": "due_date",
		"show_stock_report": 0,
		"subject_template": (
			"{{ prefix }} Hoá đơn bán {{ doc.name }} đến hạn thu tiền {{ date }}"
			" – khách còn nợ {{ amount }}"
		),
		"intro_template": (
			"Hoá đơn bán {{ doc.name }} của khách hàng {{ party_name }} đến hạn thu tiền"
			" ngày {{ date }}, còn {{ days_left }} ngày, khách còn nợ {{ amount }}."
		),
		"action_template": "Đề nghị theo dõi và đôn đốc thu hồi công nợ.",
		"external_subject_template": "",
		"external_intro_template": "",
	},
	{
		"code": "NTF-09",
		"title": "Yêu cầu thanh toán (chi NCC) · Ghi sổ",
		"reference_doctype": "Payment Request",
		"trigger_event": SUBMIT,
		"filter_field": "payment_request_type",
		"filter_values": ("Outward",),
		"filter_note": "Chỉ Yêu cầu thanh toán loại chi trả (Outward).",
		"departments": (DEPT_ACCOUNTS,),
		"notify_owner": 0,
		"notify_external": 0,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": "party_name",
		"amount_field": "grand_total",
		"date_field": "transaction_date",
		"show_stock_report": 0,
		"subject_template": (
			"{{ prefix }} Yêu cầu thanh toán {{ doc.name }} cho NCC {{ party_name }}"
			" – số tiền {{ amount }}"
		),
		"intro_template": (
			"Yêu cầu thanh toán {{ doc.name }} cho nhà cung cấp {{ party_name }},"
			" số tiền {{ amount }}, do {{ owner_name }} lập ngày {{ date }}."
		),
		"action_template": "Đề nghị kiểm tra chứng từ và thực hiện chi.",
		"external_subject_template": "",
		"external_intro_template": "",
	},
	{
		"code": "NTF-10",
		"title": "Thanh toán (chi NCC) · Ghi sổ",
		"reference_doctype": "Payment Entry",
		"trigger_event": SUBMIT,
		"filter_field": "payment_type",
		"filter_values": ("Pay",),
		"filter_note": "Chỉ phiếu chi (Pay). Phiếu chuyển nội bộ không bắn.",
		"departments": (DEPT_PURCHASE, DEPT_ACCOUNTS),
		"notify_owner": 0,
		"notify_external": 1,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": "party_name",
		"amount_field": "paid_amount",
		"date_field": "posting_date",
		"show_stock_report": 0,
		"subject_template": (
			"{{ prefix }} Đã thanh toán {{ amount }} cho {{ party_name }}" " theo phiếu {{ doc.name }}"
		),
		"intro_template": (
			"Phiếu chi {{ doc.name }} ngày {{ date }} đã ghi sổ:"
			" đã thanh toán {{ amount }} cho {{ party_name }}."
		),
		"action_template": "Đề nghị đối chiếu công nợ nhà cung cấp và đóng vòng mua hàng.",
		"external_subject_template": (
			"{{ prefix }} Miyano đã thanh toán {{ amount }} theo phiếu {{ doc.name }}"
		),
		"external_intro_template": (
			"Kính gửi Quý công ty {{ party_name }},<br><br>"
			"Miyano xin thông báo đã thực hiện thanh toán số tiền {{ amount }} ngày {{ date }}"
			" theo phiếu chi {{ doc.name }}. Kính đề nghị Quý công ty kiểm tra tài khoản"
			" và xác nhận đã nhận được."
		),
	},
	{
		"code": "NTF-11",
		"title": "Yêu cầu thanh toán (thu khách) · Ghi sổ",
		"reference_doctype": "Payment Request",
		"trigger_event": SUBMIT,
		"filter_field": "payment_request_type",
		"filter_values": ("Inward",),
		"filter_note": "Chỉ Yêu cầu thanh toán loại thu tiền (Inward).",
		"departments": (DEPT_SALES, DEPT_ACCOUNTS),
		"notify_owner": 0,
		"notify_external": 1,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": "party_name",
		"amount_field": "grand_total",
		"date_field": "transaction_date",
		"show_stock_report": 0,
		"subject_template": (
			"{{ prefix }} Đề nghị thanh toán {{ doc.name }} – khách {{ party_name }}"
			" – số tiền {{ amount }}{% if due %} – hạn {{ due }}{% endif %}"
		),
		"intro_template": (
			"Đề nghị thanh toán {{ doc.name }} gửi khách hàng {{ party_name }},"
			" số tiền {{ amount }}{% if due %}, hạn thanh toán {{ due }}{% endif %}."
		),
		"action_template": "Đề nghị theo dõi phản hồi của khách hàng và tiến độ thu tiền.",
		"external_subject_template": (
			"{{ prefix }} Đề nghị thanh toán {{ amount }}" "{% if due %} – hạn {{ due }}{% endif %}"
		),
		"external_intro_template": (
			"Kính gửi Quý khách {{ party_name }},<br><br>"
			"Miyano kính đề nghị Quý khách thanh toán số tiền {{ amount }} theo đề nghị"
			" thanh toán {{ doc.name }}{% if due %}, hạn thanh toán {{ due }}{% endif %}."
		),
	},
	{
		"code": "NTF-12",
		"title": "Thu tiền (khách) · Ghi sổ",
		"reference_doctype": "Payment Entry",
		"trigger_event": SUBMIT,
		"filter_field": "payment_type",
		"filter_values": ("Receive",),
		"filter_note": "Chỉ phiếu thu (Receive). Phiếu chuyển nội bộ không bắn.",
		"departments": (DEPT_SALES, DEPT_ACCOUNTS),
		"notify_owner": 0,
		"notify_external": 1,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": "party_name",
		"amount_field": "paid_amount",
		"date_field": "posting_date",
		"show_stock_report": 0,
		"subject_template": (
			"{{ prefix }} Đã nhận thanh toán {{ amount }} từ quý khách {{ party_name }}"
			" theo phiếu {{ doc.name }} – trân trọng cảm ơn"
		),
		"intro_template": (
			"Phiếu thu {{ doc.name }} ngày {{ date }} đã ghi sổ:"
			" đã nhận {{ amount }} từ khách hàng {{ party_name }}."
		),
		"action_template": "Đề nghị ghi nhận khoản thu và đối chiếu công nợ khách hàng.",
		"external_subject_template": (
			"{{ prefix }} Miyano đã nhận thanh toán {{ amount }} – trân trọng cảm ơn Quý khách"
		),
		"external_intro_template": (
			"Kính gửi Quý khách {{ party_name }},<br><br>"
			"Miyano xin xác nhận đã nhận được khoản thanh toán {{ amount }} ngày {{ date }}"
			" theo phiếu thu {{ doc.name }}. Trân trọng cảm ơn Quý khách."
		),
	},
)

#: Tra nhanh theo mã điểm.
POINTS_BY_CODE = {p["code"]: p for p in POINTS}

#: DocType nào cần nối vào doc_events on_submit.
SUBMIT_DOCTYPES = tuple(sorted({p["reference_doctype"] for p in POINTS if p["trigger_event"] == SUBMIT}))
