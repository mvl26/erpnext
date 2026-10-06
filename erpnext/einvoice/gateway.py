# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Cổng vào duy nhất để gọi Fast — thực hiện đúng trình tự bắt buộc A1.

```
① Ghi Fast EInvoice Log (status = "Đang gửi", request đã che mật khẩu)
② Đặt trạng thái "đang xử lý" lên chứng từ
③ commit                                   ← BẮT BUỘC, trước khi gọi API
④ Gọi Fast
⑤ Ghi response đầy đủ vào Log (kể cả lỗi, kể cả timeout)
⑥ Cập nhật kết quả lên chứng từ            ← việc của tầng gọi
⑦ commit
```

Bước ③ là lý do tồn tại của module này: nếu server sập hoặc mạng đứt giữa
chừng, trong cơ sở dữ liệu vẫn còn bằng chứng "đã gửi đi rồi", để lần sau biết
phải truy vấn (370) thay vì phát hành lại — tránh hai số hóa đơn cho một lần bán.
"""

import json

import frappe
from frappe import _
from frappe.utils import now_datetime

from erpnext.einvoice.errors import describe_error
from erpnext.einvoice.fast_client import FastClient, FastTimeout

# Message dài hơn ngưỡng này gần như chắc chắn là nội dung file base64 (PDF).
# Nhồi cả chuỗi vào log làm phình bảng mà không thêm thông tin gì.
MAX_LOGGED_MESSAGE_CHARS = 1000


def call_fast(fei, action, method, data, purpose, processing_status=None, client=None):
	"""Gọi Fast và để lại dấu vết đầy đủ. Trả về ``FastResponse``.

	``fei`` có thể là ``None`` với các lời gọi chưa gắn hóa đơn nào.
	Ngoại lệ ``FastTimeout`` được ghi log rồi mới ném tiếp — tầng trên cần biết
	để chuyển chứng từ sang "Cần đối soát".
	"""
	client = client or FastClient()

	log = _open_log(fei, action, method, purpose, data)
	if fei and processing_status:
		frappe.db.set_value("Fast EInvoice Document", fei.name, "status", processing_status)
		fei.status = processing_status
	_commit()

	try:
		response = client.excute_command(action=action, method=method, data=data)
	except FastTimeout as exc:
		_close_log(log, status="Timeout", error_message=str(exc))
		_commit()
		raise
	except Exception as exc:
		_close_log(log, status="Lỗi", error_message=str(exc))
		_commit()
		raise

	_record_response(log, response)
	_commit()
	return response


def _open_log(fei, action, method, purpose, data):
	"""Bước ① — bằng chứng "đã định gửi" nằm trong DB trước khi có lời gọi nào."""
	log = frappe.get_doc(
		{
			"doctype": "Fast EInvoice Log",
			"fei_document": fei.name if fei else None,
			"operation": "ExcuteCommand",
			"action": action,
			"method": method,
			"purpose": purpose,
			"status": "Đang gửi",
			"request_json": _readable_request(data),
			"timestamp": now_datetime(),
		}
	)
	log.flags.ignore_permissions = True
	log.insert()
	return log


def _readable_request(data):
	"""Đặc tả C4: JSON **dạng đọc được**, không phải base64.

	Bản base64 thật nằm trong envelope; log giữ bản người đọc được để còn đối
	chiếu với Fast khi có tranh chấp.
	"""
	return json.dumps(data, ensure_ascii=False, indent=1, default=str)


def _record_response(log, response):
	"""Bước ⑤ — ghi cả khi thành công lẫn khi lỗi."""
	if response.success:
		_close_log(log, status="Thành công", response=response)
		return

	described = describe_error(response.error_code, fallback=response.message)
	_close_log(
		log,
		status="Lỗi",
		response=response,
		error_code=response.error_code,
		error_message=f"{described.message} {described.hint}".strip(),
	)


def _close_log(log, status, response=None, error_code=None, error_message=None):
	values = {"status": status, "success": 1 if status == "Thành công" else 0}
	if response is not None:
		values["response_raw"] = _summarise_response(response)
		values["duration_ms"] = response.duration_ms
		if response.request_summary:
			values["request_json"] = _merge_request_log(log, response.request_summary)
	if error_code:
		values["error_code"] = error_code
	if error_message:
		values["error_message"] = error_message

	frappe.db.set_value("Fast EInvoice Log", log.name, values, update_modified=False)
	log.update(values)


def _merge_request_log(log, summary):
	"""Ghép phần envelope (đã che mật khẩu/token) vào cạnh payload đọc được."""
	return json.dumps(
		{"envelope": summary, "payload": json.loads(log.request_json or "{}")},
		ensure_ascii=False,
		indent=1,
		default=str,
	)


def _summarise_response(response):
	"""Rút gọn nội dung file base64 thành mô tả độ dài (đặc tả C4)."""
	message = response.message or ""
	if len(message) > MAX_LOGGED_MESSAGE_CHARS:
		message = _("<nội dung base64, {0} ký tự — không lưu toàn bộ>").format(len(message))
	return json.dumps(
		{"success": response.success, "message": message, "error_code": response.error_code},
		ensure_ascii=False,
		indent=1,
	)


def _commit():
	"""Bước ③/⑦.

	Trong test thì bỏ qua: ``FrappeTestCase`` chạy mọi thứ trong một transaction
	rồi rollback, commit thật sẽ làm dữ liệu test đọng lại trên site. Thứ tự ghi
	log **trước** lời gọi vẫn được kiểm chứng bằng test đọc DB ngay trong lúc gọi.
	"""
	if frappe.flags.in_test:
		return
	frappe.db.commit()
