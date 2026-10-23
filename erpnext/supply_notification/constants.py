# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Hằng kỹ thuật và **dữ liệu hạt giống** của tính năng thông báo.

Sau đợt xây lại (BA_NTF_V4), file này không còn là nguồn sự thật của nghiệp vụ:
bộ máy sự kiện, bộ nhắc hạn và bộ dựng nội dung đều đọc **bản ghi cấu hình** chứ
không đọc bảng dưới đây. Những gì còn lại ở đây chỉ có hai vai trò:

1. **Hạt giống cho site mới** — `setup.seed_points` dựng 13 điểm mặc định từ đây,
   và chỉ dựng điểm còn thiếu. Site đang chạy giữ nguyên bản ghi nghiệp vụ đã sửa.
2. **Giới hạn an toàn của bộ máy** — danh sách DocType cấm đặt thông báo (D19),
   tên vai trò, tên sự kiện realtime.

Tham chiếu: docs/superpowers/specs/2026-09-23-thong-bao-tu-thiet-lap-design.md
"""

from erpnext.setup import department_catalog

# --- Loại thời điểm (D12) -------------------------------------------------

NEW = "New"
SUBMIT = "Submit"
CANCEL = "Cancel"
VALUE_CHANGE = "Value Change"
WORKFLOW_TRANSITION = "Workflow Transition"
DATE_REMINDER = "Date Reminder"
MANUAL = "Manual"

#: Giá trị cũ của bản build theo Spec 05c, patch chuyển đổi đổi sang `DATE_REMINDER`.
LEGACY_DUE_REMINDER = "Due Reminder"

#: Loại bắn theo sự kiện lưu chứng từ, dùng để định tuyến trong `events.py`.
DOCUMENT_EVENTS = (NEW, SUBMIT, CANCEL, VALUE_CHANGE, WORKFLOW_TRANSITION)

# --- Giới hạn an toàn -----------------------------------------------------

#: Không đặt thông báo trên các DocType này (D19) — chống vòng lặp thư sinh thư
#: và tránh bắn trên chính nhật ký của tính năng.
BLOCKED_DOCTYPES = (
	"Email Queue",
	"Email Queue Recipient",
	"Notification Log",
	"Notification Settings",
	"Communication",
	"Comment",
	"Version",
	"Error Log",
	"Error Snapshot",
	"Activity Log",
	"Access Log",
	"Route History",
	"Scheduled Job Log",
	"Prepared Report",
	"File",
	"Supply Notification Point",
	"Supply Notification Dispatch Log",
	"Supply Notification Settings",
	"Supply Notification Snippet",
	"Supply Notification Recipient Group",
	"Supply Notification Opt Out",
)

#: Vai trò quản trị cấu hình thông báo (quyết định D2, giữ nguyên từ 05c).
ADMIN_ROLE = "Quản trị thông báo"

#: Sự kiện realtime riêng của Miyano, kèm dữ liệu để dựng toast.
REALTIME_EVENT = "supply_notification"

# --- Hạt giống ------------------------------------------------------------

DEPT_STOCK = department_catalog.STOCK
DEPT_PURCHASE = department_catalog.PURCHASE
DEPT_SALES = department_catalog.SALES
DEPT_ACCOUNTS = department_catalog.ACCOUNTS

#: Tiền tố tiêu đề mặc định cho điểm mới.
DEFAULT_PREFIX = "[SupplyCore]"

#: Cột mặc định của khối bảng mặt hàng.
DEFAULT_ITEM_COLUMNS = (
	("item_code", "Mã vật tư"),
	("item_name", "Tên hàng"),
	("qty", "Số lượng"),
	("uom", "ĐVT"),
)


#: Dòng mặc định của khối số liệu. Dòng trống tự bị bỏ qua khi dựng, và
#: `chi_hien_khi_tren_trong` giữ đúng nếp cũ "có hạn thì hiện hạn, không thì ngày".
def default_fact_rows(amount_label: str = "Giá trị") -> tuple[tuple[str, str, int], ...]:
	return (
		("so_tien", amount_label, 0),
		("han_thanh_toan", "Hạn thanh toán", 0),
		("ngay", "Ngày", 1),
		("so_ngay_con_lai", "Còn lại", 0),
	)


SNIPPET_FOOTER = "Chân email Miyano"
SNIPPET_DELIVERY_RULES = "Quy định giao nhận hàng hoá"
SNIPPET_HOTLINE = "Hotline Miyano"

#: Mẫu nội dung dùng chung gieo sẵn (BA mục 5.4).
SEED_SNIPPETS = (
	{
		"snippet_name": SNIPPET_FOOTER,
		"scope": "Cả hai",
		"content": ("<p>Trân trọng,<br>" "<strong>Công ty TNHH Miyano Việt Nam</strong></p>"),
	},
	{
		"snippet_name": SNIPPET_HOTLINE,
		"scope": "Ngoài",
		"content": "<p>Mọi vướng mắc xin liên hệ bộ phận phụ trách ghi ở cuối thư này.</p>",
	},
	{
		"snippet_name": SNIPPET_DELIVERY_RULES,
		"scope": "Ngoài",
		"content": (
			"<p>Để công tác phối hợp giao nhận hàng hóa diễn ra thuận lợi và hiệu quả,"
			" Công ty TNHH Miyano Việt Nam xin phép đề nghị Quý đối tác lưu ý một số nội dung sau:</p>"
			"<ul>"
			"<li><strong>Thời gian thông báo:</strong> Quý đối tác vui lòng thông báo trước cho"
			" chúng tôi tối thiểu 60 phút trước thời điểm giao hàng dự kiến.</li>"
			"<li><strong>Mục đích:</strong> Việc này giúp chúng tôi chủ động bố trí nhân sự và"
			" không gian để tiếp nhận hàng hóa một cách nhanh chóng nhất.</li>"
			"<li><strong>Lưu ý quan trọng:</strong> Trong trường hợp không nhận được thông tin"
			" báo trước theo thời gian nêu trên, chúng tôi rất tiếc không thể đảm bảo có nhân sự"
			" túc trực để nhận hàng tại thời điểm giao hàng phát sinh.</li>"
			"<li><strong>Chứng từ khi giao hàng:</strong> Khi giao hàng, Quý đối tác vui lòng"
			" cung cấp kèm theo Phiếu giao hàng / Biên bản bàn giao hàng hóa"
			" <strong>bản Đơn mua hàng (PO) của Miyano</strong> (in từ email này). Việc này giúp"
			" bộ phận nhận hàng của chúng tôi xác định đúng hàng giao thuộc đơn nào để tiếp nhận"
			" và đối chiếu nhanh chóng, chính xác.</li>"
			"</ul>"
		),
	},
)

GROUP_PURCHASE = "Mua hàng"
GROUP_SALES = "Bán hàng"
GROUP_STOCK = "Kho"
GROUP_ACCOUNTS = "Kế toán"

#: Cột bảng chênh lệch đối soát Phiếu nhập ↔ Hoá đơn mua (YC5) trong email nội bộ.
_YC5_COT_CHENH_LECH = (
	("dong_hoa_don", "Dòng HĐ"),
	("item_code", "Mặt hàng"),
	("tieu_chi", "Tiêu chí"),
	("gia_tri_pr", "Theo Phiếu nhập"),
	("gia_tri_pi", "Theo Hoá đơn"),
	("nhanh_goi_y", "Gợi ý xử lý"),
)

#: Phần chung của hai điểm "Hoá đơn mua lệch Phiếu nhập" (NTF-16, NTF-17).
_YC5_LECH = {
	"departments": (DEPT_PURCHASE,),
	"notify_owner": 1,
	"notify_external": 0,
	"attach_pdf": 0,
	"print_format": None,
	"party_field": "supplier_name",
	"amount_field": "grand_total",
	"main_date_field": "posting_date",
	"item_table_field": "chenh_lech_pr",
	"item_columns": _YC5_COT_CHENH_LECH,
	"amount_label": "Giá trị hoá đơn",
	"show_stock_report": 0,
	"subject_template": "Hoá đơn mua {{ doc.name }} ({{ ten_doi_tac }}) lệch Phiếu nhập",
	"intro": (
		"Hoá đơn mua {{ doc.name }} của nhà cung cấp {{ ten_doi_tac }}, giá trị {{ so_tien }},"
		" không khớp Phiếu nhập mua ở các điểm dưới đây nên chưa Nộp được."
	),
	"action": (
		"Đề nghị chọn Nhánh xử lý trên hoá đơn: (a) sửa hoá đơn, (b1) báo Kho sửa Phiếu nhập,"
		" (b2) gửi nhà cung cấp bảng chênh lệch để xin hoá đơn điều chỉnh."
	),
	"external_subject_template": "",
	"external_intro": "",
}

#: 13 điểm hạt giống. `intro`/`action`/`external_intro` là **phần câu chữ**;
#: `setup` ghép chúng thành thân email cùng các khối, theo đúng bố cục mà bản
#: build 05c dựng bằng template cứng — nhờ vậy site mới và site cũ giống nhau.
SEED_POINTS = (
	{
		"code": "NTF-01",
		"title": "Đơn bán hàng · Ghi sổ",
		"function_group": GROUP_SALES,
		"reference_doctype": "Sales Order",
		"trigger_event": SUBMIT,
		"conditions": (),
		"notes": "Mọi đơn bán hàng đã ghi sổ.",
		"departments": (DEPT_STOCK,),
		"notify_owner": 1,
		"notify_external": 0,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": "customer_name",
		"amount_field": "grand_total",
		"main_date_field": "transaction_date",
		"amount_label": "Giá trị",
		"show_stock_report": 1,
		"subject_template": (
			"Đơn bán hàng {{ doc.name }} của khách {{ ten_doi_tac }}" " vừa ghi sổ – đề nghị kiểm tra tồn kho"
		),
		"intro": (
			"Đơn bán hàng {{ doc.name }} – khách hàng {{ ten_doi_tac }} vừa được ghi sổ"
			" bởi {{ ten_nguoi_tao }} ngày {{ ngay }}."
		),
		"action": (
			"Vui lòng kiểm tra tồn kho các mặt hàng dưới đây và phản hồi trong ngày."
			" Nếu đủ hàng: soạn hàng và giao (Pick List / Phiếu giao hàng)."
			" Nếu thiếu: tạo Yêu cầu vật tư loại Mua hàng ngay từ đơn này."
		),
		"external_subject_template": "",
		"external_intro": "",
	},
	{
		"code": "NTF-02",
		"title": "Yêu cầu vật tư · Ghi sổ",
		"function_group": GROUP_PURCHASE,
		"reference_doctype": "Material Request",
		"trigger_event": SUBMIT,
		"conditions": (("material_request_type", "=", "Purchase"),),
		"notes": "Chỉ Yêu cầu vật tư loại Mua hàng (Purchase).",
		"departments": (DEPT_PURCHASE,),
		"notify_owner": 0,
		"notify_external": 0,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": None,
		"amount_field": None,
		"main_date_field": "transaction_date",
		"amount_label": "Giá trị",
		"show_stock_report": 0,
		"subject_template": "Yêu cầu vật tư {{ doc.name }} đang chờ tạo Đơn mua hàng",
		"intro": ("Yêu cầu vật tư {{ doc.name }} do {{ ten_nguoi_tao }} lập ngày {{ ngay }} đã được ghi sổ."),
		"action": "Đề nghị xem xét, chọn nhà cung cấp và tạo Đơn mua hàng.",
		"external_subject_template": "",
		"external_intro": "",
	},
	{
		"code": "NTF-03",
		"title": "Đơn mua hàng · Ghi sổ",
		"function_group": GROUP_PURCHASE,
		"reference_doctype": "Purchase Order",
		"trigger_event": SUBMIT,
		"conditions": (),
		"notes": "Mọi đơn mua hàng đã ghi sổ. Việc gửi NCC do điểm NTF-13 đảm nhiệm (CR_01).",
		"departments": (DEPT_STOCK,),
		"notify_owner": 0,
		"notify_external": 0,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": "supplier_name",
		"amount_field": "grand_total",
		"main_date_field": "schedule_date",
		"amount_label": "Giá trị",
		"show_stock_report": 0,
		"subject_template": (
			"Đơn mua hàng {{ doc.name }} – NCC {{ ten_doi_tac }} – dự kiến nhận hàng {{ ngay }}"
		),
		"intro": (
			"Đơn mua hàng {{ doc.name }} gửi nhà cung cấp {{ ten_doi_tac }} đã được ghi sổ,"
			" giá trị {{ so_tien }}, dự kiến nhận hàng ngày {{ ngay }}."
		),
		"action": "Đề nghị bố trí vị trí kho và theo dõi lịch nhận hàng.",
		"external_subject_template": "",
		"external_intro": "",
	},
	{
		"code": "NTF-04",
		"title": "Phiếu nhập mua · Ghi sổ",
		"function_group": GROUP_PURCHASE,
		"reference_doctype": "Purchase Receipt",
		"trigger_event": SUBMIT,
		"conditions": (("is_return", "=", "0"),),
		"notes": "Phiếu nhập mua đã ghi sổ. Phiếu trả hàng NCC không bắn (việc cần làm khác hẳn).",
		"departments": (DEPT_PURCHASE, DEPT_ACCOUNTS),
		"notify_owner": 0,
		"notify_external": 0,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": "supplier_name",
		"amount_field": "grand_total",
		"main_date_field": "posting_date",
		"amount_label": "Giá trị",
		"show_stock_report": 0,
		"subject_template": (
			"Đã nhập kho phiếu {{ doc.name }} từ NCC {{ ten_doi_tac }}"
			" – đề nghị đối chiếu và tạo hoá đơn mua"
		),
		"intro": (
			"Phiếu nhập mua {{ doc.name }} từ nhà cung cấp {{ ten_doi_tac }} đã ghi sổ"
			" ngày {{ ngay }}, giá trị {{ so_tien }}."
		),
		"action": "Đề nghị đối chiếu Đơn mua hàng với Phiếu nhập, sau đó tạo Hoá đơn mua.",
		"external_subject_template": "",
		"external_intro": "",
	},
	{
		"code": "NTF-05",
		"title": "Hoá đơn mua · Ghi sổ",
		"function_group": GROUP_ACCOUNTS,
		"reference_doctype": "Purchase Invoice",
		"trigger_event": SUBMIT,
		"conditions": (("is_return", "=", "0"),),
		"notes": "Hoá đơn mua đã ghi sổ. Hoá đơn trả hàng không bắn (không phát sinh công nợ phải trả).",
		"departments": (DEPT_ACCOUNTS,),
		"notify_owner": 0,
		"notify_external": 0,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": "supplier_name",
		"amount_field": "grand_total",
		"main_date_field": "due_date",
		"amount_label": "Giá trị",
		"show_stock_report": 0,
		"subject_template": "Hoá đơn mua {{ doc.name }} – hạn thanh toán {{ ngay }}",
		"intro": (
			"Hoá đơn mua {{ doc.name }} của nhà cung cấp {{ ten_doi_tac }} đã ghi sổ,"
			" giá trị {{ so_tien }}, hạn thanh toán {{ ngay }}."
		),
		"action": "Đề nghị ghi nhận công nợ và lên lịch chi.",
		"external_subject_template": "",
		"external_intro": "",
	},
	{
		"code": "NTF-06",
		"title": "Hoá đơn mua · Nhắc hạn thanh toán",
		"function_group": GROUP_ACCOUNTS,
		"reference_doctype": "Purchase Invoice",
		"trigger_event": DATE_REMINDER,
		"date_field": "due_date",
		"reminder_offsets": "-7, -3, -1",
		"conditions": (("outstanding_amount", ">", "0"), ("on_hold", "=", "0")),
		"notes": (
			"Hoá đơn mua đã ghi sổ, còn nợ > 0, chưa bị tạm giữ thanh toán," " đến hạn sau 7 / 3 / 1 ngày."
		),
		"departments": (DEPT_ACCOUNTS, DEPT_PURCHASE),
		"notify_owner": 0,
		"notify_external": 0,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": "supplier_name",
		"amount_field": "outstanding_amount",
		"main_date_field": "due_date",
		"amount_label": "Số còn nợ",
		"show_stock_report": 0,
		"allow_opt_out": 0,
		"subject_template": ("Hoá đơn {{ doc.name }} đến hạn thanh toán {{ ngay }} – còn nợ {{ so_tien }}"),
		"intro": (
			"Hoá đơn mua {{ doc.name }} của nhà cung cấp {{ ten_doi_tac }} đến hạn thanh toán"
			" ngày {{ ngay }}, còn {{ so_ngay_con_lai }} ngày, số còn nợ {{ so_tien }}."
		),
		"action": "Đề nghị chuẩn bị chi trả đúng hạn.",
		"external_subject_template": "",
		"external_intro": "",
	},
	{
		"code": "NTF-07",
		"title": "Phiếu giao hàng · Ghi sổ",
		"function_group": GROUP_SALES,
		"reference_doctype": "Delivery Note",
		"trigger_event": SUBMIT,
		"conditions": (("is_return", "=", "0"),),
		"notes": (
			"Phiếu giao hàng đã ghi sổ. Phiếu nhận lại hàng trả KHÔNG bắn — điểm này"
			" gửi thư cho khách, nói 'đơn hàng đang giao' cho một phiếu trả hàng là sai."
		),
		"departments": (DEPT_SALES,),
		"notify_owner": 0,
		"notify_external": 1,
		"attach_pdf": 1,
		"print_format": "Phiếu xuất kho (02-VT)",
		"party_field": "customer_name",
		"amount_field": "grand_total",
		"main_date_field": "posting_date",
		"amount_label": "Giá trị",
		"show_stock_report": 0,
		"subject_template": (
			"Phiếu giao hàng {{ doc.name }} cho khách {{ ten_doi_tac }} đã xuất kho, đang giao"
		),
		"intro": (
			"Phiếu giao hàng {{ doc.name }} cho khách hàng {{ ten_doi_tac }} đã xuất kho ngày {{ ngay }}."
		),
		"action": "Đề nghị theo dõi giao nhận và xác nhận với khách hàng.",
		"external_subject_template": "Đơn hàng {{ doc.name }} của Quý khách đã xuất kho, đang giao",
		"external_intro": (
			"Kính gửi Quý khách {{ ten_doi_tac }},<br><br>"
			"Miyano xin thông báo đơn hàng theo phiếu giao {{ doc.name }} đã xuất kho"
			" ngày {{ ngay }} và đang trên đường giao đến Quý khách."
			" Chi tiết hàng hoá theo phiếu giao đính kèm."
		),
	},
	{
		"code": "NTF-08",
		"title": "Hoá đơn bán · Nhắc hạn thu tiền",
		"function_group": GROUP_ACCOUNTS,
		"reference_doctype": "Sales Invoice",
		"trigger_event": DATE_REMINDER,
		"date_field": "due_date",
		"reminder_offsets": "-7, -3, -1",
		"conditions": (("outstanding_amount", ">", "0"),),
		"notes": "Hoá đơn bán đã ghi sổ, khách còn nợ > 0, đến hạn sau 7 / 3 / 1 ngày.",
		"departments": (DEPT_ACCOUNTS,),
		"notify_owner": 0,
		"notify_external": 0,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": "customer_name",
		"amount_field": "outstanding_amount",
		"main_date_field": "due_date",
		"amount_label": "Số còn nợ",
		"show_stock_report": 0,
		"allow_opt_out": 0,
		"subject_template": (
			"Hoá đơn bán {{ doc.name }} đến hạn thu tiền {{ ngay }} – khách còn nợ {{ so_tien }}"
		),
		"intro": (
			"Hoá đơn bán {{ doc.name }} của khách hàng {{ ten_doi_tac }} đến hạn thu tiền"
			" ngày {{ ngay }}, còn {{ so_ngay_con_lai }} ngày, khách còn nợ {{ so_tien }}."
		),
		"action": "Đề nghị theo dõi và đôn đốc thu hồi công nợ.",
		"external_subject_template": "",
		"external_intro": "",
	},
	{
		"code": "NTF-09",
		"title": "Yêu cầu thanh toán (chi NCC) · Ghi sổ",
		"function_group": GROUP_ACCOUNTS,
		"reference_doctype": "Payment Request",
		"trigger_event": SUBMIT,
		"conditions": (("payment_request_type", "=", "Outward"),),
		"notes": "Chỉ Yêu cầu thanh toán loại chi trả (Outward).",
		"departments": (DEPT_ACCOUNTS,),
		"notify_owner": 0,
		"notify_external": 0,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": "party_name",
		"amount_field": "grand_total",
		"main_date_field": "transaction_date",
		"amount_label": "Giá trị",
		"show_stock_report": 0,
		"subject_template": (
			"Yêu cầu thanh toán {{ doc.name }} cho NCC {{ ten_doi_tac }} – số tiền {{ so_tien }}"
		),
		"intro": (
			"Yêu cầu thanh toán {{ doc.name }} cho nhà cung cấp {{ ten_doi_tac }},"
			" số tiền {{ so_tien }}, do {{ ten_nguoi_tao }} lập ngày {{ ngay }}."
		),
		"action": "Đề nghị kiểm tra chứng từ và thực hiện chi.",
		"external_subject_template": "",
		"external_intro": "",
	},
	{
		"code": "NTF-10",
		"title": "Thanh toán (chi NCC) · Ghi sổ",
		"function_group": GROUP_ACCOUNTS,
		"reference_doctype": "Payment Entry",
		"trigger_event": SUBMIT,
		"conditions": (
			("payment_type", "=", "Pay"),
			("references.reference_doctype", "=", "Purchase Invoice"),
		),
		"notes": (
			"Chi trả NCC theo hoá đơn mua (quyết định PO 06/10/2026). Hoá đơn mua là chứng từ"
			" nguồn ĐỘC QUYỀN của NCC nên điều kiện này tự loại phiếu chi cho nhân viên,"
			" cổ đông và phiếu chuyển nội bộ. Tạm ứng NCC và chi theo bút toán tay là điểm riêng."
		),
		"departments": (DEPT_PURCHASE, DEPT_ACCOUNTS),
		"notify_owner": 0,
		"notify_external": 1,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": "party_name",
		"amount_field": "paid_amount",
		"main_date_field": "posting_date",
		"amount_label": "Giá trị",
		"show_stock_report": 0,
		"subject_template": ("Đã thanh toán {{ so_tien }} cho {{ ten_doi_tac }} theo phiếu {{ doc.name }}"),
		"intro": (
			"Phiếu chi {{ doc.name }} ngày {{ ngay }} đã ghi sổ:"
			" đã thanh toán {{ so_tien }} cho {{ ten_doi_tac }}."
		),
		"action": "Đề nghị đối chiếu công nợ nhà cung cấp và đóng vòng mua hàng.",
		"external_subject_template": "Miyano đã thanh toán {{ so_tien }} theo phiếu {{ doc.name }}",
		"external_intro": (
			"Kính gửi Quý công ty {{ ten_doi_tac }},<br><br>"
			"Miyano xin thông báo đã thực hiện thanh toán số tiền {{ so_tien }} ngày {{ ngay }}"
			" theo phiếu chi {{ doc.name }}. Kính đề nghị Quý công ty kiểm tra tài khoản"
			" và xác nhận đã nhận được."
		),
	},
	{
		"code": "NTF-11",
		"title": "Yêu cầu thanh toán (thu khách) · Ghi sổ",
		"function_group": GROUP_ACCOUNTS,
		"reference_doctype": "Payment Request",
		"trigger_event": SUBMIT,
		"conditions": (("payment_request_type", "=", "Inward"),),
		"notes": "Chỉ Yêu cầu thanh toán loại thu tiền (Inward).",
		"departments": (DEPT_SALES, DEPT_ACCOUNTS),
		"notify_owner": 0,
		"notify_external": 1,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": "party_name",
		"amount_field": "grand_total",
		"main_date_field": "transaction_date",
		"amount_label": "Giá trị",
		"show_stock_report": 0,
		"subject_template": (
			"Đề nghị thanh toán {{ doc.name }} – khách {{ ten_doi_tac }}"
			" – số tiền {{ so_tien }}{% if han_thanh_toan %} – hạn {{ han_thanh_toan }}{% endif %}"
		),
		"intro": (
			"Đề nghị thanh toán {{ doc.name }} gửi khách hàng {{ ten_doi_tac }},"
			" số tiền {{ so_tien }}{% if han_thanh_toan %}, hạn thanh toán {{ han_thanh_toan }}{% endif %}."
		),
		"action": "Đề nghị theo dõi phản hồi của khách hàng và tiến độ thu tiền.",
		"external_subject_template": (
			"Đề nghị thanh toán {{ so_tien }}{% if han_thanh_toan %} – hạn {{ han_thanh_toan }}{% endif %}"
		),
		"external_intro": (
			"Kính gửi Quý khách {{ ten_doi_tac }},<br><br>"
			"Miyano kính đề nghị Quý khách thanh toán số tiền {{ so_tien }} theo đề nghị"
			" thanh toán {{ doc.name }}"
			"{% if han_thanh_toan %}, hạn thanh toán {{ han_thanh_toan }}{% endif %}."
		),
	},
	{
		"code": "NTF-12",
		"title": "Thu tiền (khách) · Ghi sổ",
		"function_group": GROUP_ACCOUNTS,
		"reference_doctype": "Payment Entry",
		"trigger_event": SUBMIT,
		"conditions": (
			("payment_type", "=", "Receive"),
			("references.reference_doctype", "=", "Sales Invoice"),
		),
		"notes": (
			"Thu tiền khách theo hoá đơn bán (quyết định PO 06/10/2026). Hoá đơn bán là chứng từ"
			" nguồn ĐỘC QUYỀN của khách nên điều kiện này tự loại phiếu thu từ nhân viên,"
			" cổ đông và phiếu chuyển nội bộ. Khách đặt cọc là điểm riêng."
		),
		"departments": (DEPT_SALES, DEPT_ACCOUNTS),
		"notify_owner": 0,
		"notify_external": 1,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": "party_name",
		"amount_field": "paid_amount",
		"main_date_field": "posting_date",
		"amount_label": "Giá trị",
		"show_stock_report": 0,
		"subject_template": (
			"Đã nhận thanh toán {{ so_tien }} từ quý khách {{ ten_doi_tac }}"
			" theo phiếu {{ doc.name }} – trân trọng cảm ơn"
		),
		"intro": (
			"Phiếu thu {{ doc.name }} ngày {{ ngay }} đã ghi sổ:"
			" đã nhận {{ so_tien }} từ khách hàng {{ ten_doi_tac }}."
		),
		"action": "Đề nghị ghi nhận khoản thu và đối chiếu công nợ khách hàng.",
		"external_subject_template": (
			"Miyano đã nhận thanh toán {{ so_tien }} – trân trọng cảm ơn Quý khách"
		),
		"external_intro": (
			"Kính gửi Quý khách {{ ten_doi_tac }},<br><br>"
			"Miyano xin xác nhận đã nhận được khoản thanh toán {{ so_tien }} ngày {{ ngay }}"
			" theo phiếu thu {{ doc.name }}. Trân trọng cảm ơn Quý khách."
		),
	},
	# YC4 — báo trước khi đổi giá bán (spec 2026-10-21, mục 6.2.5 và 14). Người nhận là người
	# đã gửi thông báo đổi giá (Giám đốc), qua ô `nguoi_gui_thong_bao` của dòng giá.
	{
		"code": "NTF-14",
		"title": "Đổi giá bán · Nhắc xin khách xác nhận",
		"function_group": GROUP_SALES,
		"reference_doctype": "Item Price",
		"trigger_event": DATE_REMINDER,
		"date_field": "ngay_gui_thong_bao",
		"reminder_offsets": "+2",
		"conditions": (("trang_thai_thong_bao", "=", "Đã gửi"),),
		"notes": "Đã gửi thông báo đổi giá 2 ngày mà khách chưa xác nhận.",
		"user_fields": ("nguoi_gui_thong_bao",),
		"notify_owner": 0,
		"notify_external": 0,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": None,
		"amount_field": "price_list_rate",
		"main_date_field": "valid_from",
		"item_table_field": None,
		"amount_label": "Giá mới",
		"show_stock_report": 0,
		"subject_template": "Giá mới {{ doc.item_code }} ({{ doc.price_list }}) chưa được khách xác nhận",
		"intro": (
			"Thông báo đổi giá {{ doc.item_code }} trên bảng giá {{ doc.price_list }} gửi ngày"
			" {{ doc.ngay_gui_thong_bao }} đến nay chưa có xác nhận của khách. Giá mới {{ so_tien }}"
			" áp dụng từ {{ ngay }}."
		),
		"action": "Đề nghị liên hệ khách xin xác nhận, rồi ghi Ngày khách xác nhận và đính kèm email.",
		"external_subject_template": "",
		"external_intro": "",
	},
	{
		"code": "NTF-15",
		"title": "Đổi giá bán · Giá mới sắp áp dụng",
		"function_group": GROUP_SALES,
		"reference_doctype": "Item Price",
		"trigger_event": DATE_REMINDER,
		"date_field": "valid_from",
		"reminder_offsets": "-1",
		"conditions": (("trang_thai_thong_bao", "Trong danh sách", "Đã gửi, Đã xác nhận"),),
		"notes": "Giá mới đã báo khách, áp dụng từ ngày mai.",
		"user_fields": ("nguoi_gui_thong_bao",),
		"departments": (DEPT_SALES, DEPT_ACCOUNTS),
		"notify_owner": 0,
		"notify_external": 0,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": None,
		"amount_field": "price_list_rate",
		"main_date_field": "valid_from",
		"item_table_field": None,
		"amount_label": "Giá mới",
		"show_stock_report": 0,
		"subject_template": "Từ {{ ngay }}: giá mới {{ doc.item_code }} trên {{ doc.price_list }}",
		"intro": (
			"Giá bán {{ doc.item_code }} trên bảng giá {{ doc.price_list }} đổi thành {{ so_tien }}"
			" từ ngày {{ ngay }} (đã báo khách ngày {{ doc.ngay_gui_thong_bao }})."
		),
		"action": "Đơn hàng từ ngày này lấy giá mới; đơn đặt trước ngày này giữ giá cũ.",
		"external_subject_template": "",
		"external_intro": "",
	},
	# YC5 — đối soát Phiếu nhập ↔ Hóa đơn mua (spec 2026-10-21, mục 6.3.9). Lần lưu đầu không chạy
	# `on_change` nên "lệch ngay khi tạo" cần điểm Tạo mới riêng (NTF-16) bên cạnh điểm Trường
	# thay đổi (NTF-17). Nhắc "lệch tồn quá N ngày" chưa gieo: bộ nhắc hạn chỉ quét chứng từ đã Nộp.
	{
		"code": "NTF-16",
		"title": "Hoá đơn mua · Lệch Phiếu nhập (lúc tạo)",
		"function_group": GROUP_PURCHASE,
		"reference_doctype": "Purchase Invoice",
		"trigger_event": NEW,
		"conditions": (("trang_thai_doi_soat_pr", "=", "Lệch"),),
		"notes": "Hoá đơn mua vừa tạo đã lệch Phiếu nhập (YC5).",
		**_YC5_LECH,
	},
	{
		"code": "NTF-17",
		"title": "Hoá đơn mua · Chuyển sang Lệch Phiếu nhập",
		"function_group": GROUP_PURCHASE,
		"reference_doctype": "Purchase Invoice",
		"trigger_event": VALUE_CHANGE,
		"watch_field": "trang_thai_doi_soat_pr",
		"watch_value": "Lệch",
		"conditions": (),
		"notes": "Hoá đơn mua nháp chuyển sang lệch Phiếu nhập khi lưu lại hoặc khi Phiếu nhập đổi (YC5).",
		**_YC5_LECH,
	},
	{
		"code": "NTF-18",
		"title": "Hoá đơn mua · Lệch do Phiếu nhập sai (b1)",
		"function_group": GROUP_STOCK,
		"reference_doctype": "Purchase Invoice",
		"trigger_event": VALUE_CHANGE,
		"watch_field": "nhanh_xu_ly",
		"watch_value": "(b1) Phiếu nhập mua sai",
		"conditions": (),
		"notes": "Người xử lý chọn nhánh (b1): Kho kiểm lại Phiếu nhập, hủy và lập bản sửa (YC5).",
		"departments": (DEPT_STOCK,),
		"notify_owner": 0,
		"notify_external": 0,
		"attach_pdf": 0,
		"print_format": None,
		"party_field": "supplier_name",
		"amount_field": "grand_total",
		"main_date_field": "posting_date",
		"item_table_field": "chenh_lech_pr",
		"item_columns": _YC5_COT_CHENH_LECH,
		"amount_label": "Giá trị hoá đơn",
		"show_stock_report": 0,
		"subject_template": "Kiểm lại Phiếu nhập cho hoá đơn mua {{ doc.name }} ({{ ten_doi_tac }})",
		"intro": (
			"Hoá đơn mua {{ doc.name }} của nhà cung cấp {{ ten_doi_tac }} lệch Phiếu nhập và được xác định"
			" là do Phiếu nhập sai so với hàng thực nhận."
		),
		"action": (
			"Đề nghị Kho đối chiếu hàng thực nhận; nếu Phiếu nhập sai thì Hủy và Sửa lại phiếu. Hoá đơn"
			" tự đối soát lại khi bản sửa được Nộp."
		),
		"external_subject_template": "",
		"external_intro": "",
	},
)

#: Tra nhanh theo mã điểm.
SEED_POINTS_BY_CODE = {p["code"]: p for p in SEED_POINTS}


#: Điểm NTF-13 — CR_01 "Gửi PO cho NCC" (BA mục 8). Toàn bộ là cấu hình: chứng
#: từ Purchase Order, thời điểm Thủ công, chỉ kênh gửi ra ngoài. Lời văn lấy
#: nguyên từ CR_01 mục 3, đã chỉnh hai chỗ theo quyết định D23 (không đính PDF).
SEED_MANUAL_POINTS = (
	{
		"code": "NTF-13",
		"title": "Đơn mua hàng · Gửi NCC",
		"function_group": GROUP_PURCHASE,
		"reference_doctype": "Purchase Order",
		"trigger_event": MANUAL,
		"button_label": "Gửi cho NCC",
		"button_color": "Chính (xanh)",
		"manual_docstatus": "Đã ghi sổ",
		"conditions": (("status", "≠", "Closed"),),
		"notes": (
			"CR_01: người phụ trách mua hàng chủ động bấm gửi sau khi PO đã ghi sổ."
			" PO đã đóng (Closed) không gửi được."
		),
		"send_email": 0,
		"send_inapp": 0,
		"notify_external": 1,
		"external_party_contact": 1,
		"cc_owner": 1,
		"reply_to_mode": "Người tạo chứng từ",
		"attach_pdf": 0,
		"print_format": None,
		"party_field": "supplier_name",
		"amount_field": "grand_total",
		"main_date_field": "transaction_date",
		"address_field": "shipping_address",
		"signature_person": "Người tạo",
		"subject_prefix": "[Miyano]",
		"item_columns": (
			("stt", "STT"),
			("item_code", "Mã vật tư"),
			("item_name", "Tên hàng"),
			("qty", "Số lượng"),
			("uom", "ĐVT"),
			("schedule_date", "Ngày cần hàng"),
		),
		"external_subject_template": (
			"Đơn mua hàng {{ doc.name }} – đề nghị xác nhận đơn và thời gian giao hàng"
		),
		"external_body_template": (
			"<p>Kính gửi Quý đối tác {{ ten_doi_tac }},</p>"
			"<p>Công ty TNHH Miyano Việt Nam trân trọng gửi Quý đối tác Đơn mua hàng số"
			" {{ doc.name }} ngày {{ ngay }} (chi tiết liệt kê dưới đây).</p>"
			"{{ bang_mat_hang() }}"
			"{{ dia_chi_giao_hang() }}"
			"<p>Quý đối tác xin vui lòng xác nhận đơn hàng và chia sẻ thời gian giao hàng dự kiến.</p>"
			'{{ khoi_phan_hoi("Quý đối tác vui lòng trả lời email này để xác nhận đơn hàng.") }}'
			'{{ mau("' + SNIPPET_DELIVERY_RULES + '") }}'
			"<p>Chúng tôi rất mong nhận được sự hợp tác và hỗ trợ từ Quý đối tác"
			" để đảm bảo tiến độ công việc chung.</p>"
			"<p>Trân trọng,</p>"
			"{{ chu_ky() }}"
		),
	},
	# YC5 nhánh (b2): hoá đơn NCC sai so với hàng thực nhận — gửi NCC bảng chênh lệch, CC người lập
	# hoá đơn (spec 6.3.9). Nút chỉ hiện trên hoá đơn nháp đang lệch.
	{
		"code": "NTF-19",
		"title": "Hoá đơn mua · Gửi NCC bảng chênh lệch (b2)",
		"function_group": GROUP_PURCHASE,
		"reference_doctype": "Purchase Invoice",
		"trigger_event": MANUAL,
		"button_label": "Gửi NCC bảng chênh lệch",
		"button_color": "Cảnh báo (vàng)",
		"manual_docstatus": "Nháp",
		"conditions": (("trang_thai_doi_soat_pr", "=", "Lệch"),),
		"notes": "Nhánh (b2) của YC5: nhà cung cấp phát hành hoá đơn điều chỉnh / thay thế.",
		"send_email": 0,
		"send_inapp": 0,
		"notify_external": 1,
		"external_party_contact": 1,
		"cc_owner": 1,
		"reply_to_mode": "Người tạo chứng từ",
		"attach_pdf": 0,
		"print_format": None,
		"party_field": "supplier_name",
		"amount_field": "grand_total",
		"main_date_field": "bill_date",
		"item_table_field": "chenh_lech_pr",
		"signature_person": "Người tạo",
		"subject_prefix": "[Miyano]",
		"item_columns": (
			("item_code", "Mặt hàng"),
			("tieu_chi", "Nội dung"),
			("gia_tri_pr", "Theo hàng thực nhận"),
			("gia_tri_pi", "Theo hoá đơn"),
		),
		"external_subject_template": (
			"Hoá đơn số {{ doc.bill_no }} – đề nghị kiểm tra chênh lệch với hàng thực nhận"
		),
		"external_body_template": (
			"<p>Kính gửi Quý đối tác {{ ten_doi_tac }},</p>"
			"<p>Công ty TNHH Miyano Việt Nam đã đối chiếu hoá đơn số {{ doc.bill_no }} ngày {{ ngay }}"
			" với hàng thực nhận tại kho và thấy các điểm chênh lệch dưới đây.</p>"
			"{{ bang_mat_hang() }}"
			"<p>Đề nghị Quý đối tác kiểm tra và phát hành hoá đơn điều chỉnh hoặc thay thế theo quy định."
			" Hoá đơn này chưa được ghi nhận công nợ cho tới khi chênh lệch được xử lý.</p>"
			'{{ khoi_phan_hoi("Quý đối tác vui lòng trả lời email này để xác nhận.") }}'
			"<p>Trân trọng,</p>"
			"{{ chu_ky() }}"
		),
	},
)
