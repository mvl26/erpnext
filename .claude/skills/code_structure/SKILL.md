---
name: code_structure
description: Use when creating a new DocType, report, or patch in this repo — any task that creates several files at once and must follow the Miyano ERP folder and naming layout. Not needed for editing a single existing file; the PreToolUse hook covers that.
---

# Cấu trúc file — Miyano ERP

Nguồn sự thật là bảng `RULES` trong `scripts/file_structure/gate.py`.
Tài liệu này chỉ tóm tắt các bộ file hay tạo cùng lúc.

## Tạo DocType mới

    erpnext/<module>/doctype/<snake_case>/
        __init__.py
        <snake_case>.json      # schema — nguồn sự thật của mô hình dữ liệu
        <snake_case>.py        # controller
        <snake_case>.js        # form script (nếu cần)
        test_<snake_case>.py   # BẮT BUỘC trùng tên folder

Sau đó chạy `bench --site miyano migrate` từ bench root `/home/miyano/frappe-bench`.

## Tạo report mới

    erpnext/<module>/report/<snake_case>/
        __init__.py
        <snake_case>.json
        <snake_case>.py
        test_<snake_case>.py   # BẮT BUỘC trùng tên folder

## Tạo patch mới

    erpnext/patches/v15_0/<động_từ>_<danh_từ>.py

Rồi thêm một dòng tương ứng vào `erpnext/patches.txt`. Thiếu dòng này thì patch không chạy.

## Test đặt ở đâu

- Mặc định: `erpnext/<module>/tests/test_*.py` (Accounts dùng `erpnext/accounts/test/`)
- Sub-package tự chứa: `erpnext/<module>/<sub>/tests/`, ví dụ `erpnext/einvoice/tests/`
- Mọi folder test phải có `__init__.py`

**Hai ngoại lệ duy nhất** — Frappe resolve theo đúng đường dẫn
(`frappe/test_runner.py:209`), đặt chỗ khác là `bench run-tests --doctype "X"` không tìm thấy:

- `erpnext/<module>/doctype/<dt>/test_<dt>.py`
- `erpnext/<module>/report/<rp>/test_<rp>.py`

Tên khác tên folder thì **không** thuộc ngoại lệ — chuyển vào `tests/` của module.

## Tài liệu và script

- Tài liệu: `docs/`. Gốc repo chỉ giữ `README.md`, `CLAUDE.md`, `NOTICE.md`
- Spec thiết kế: `docs/superpowers/specs/YYYY-MM-DD-<chủ-đề>-design.md`
- Kế hoạch thực thi: `docs/superpowers/plans/YYYY-MM-DD-<chủ-đề>.md`
- Script: `scripts/`, test của script: `scripts/tests/`

## Khi bị hook chặn

Đọc thông báo — nó đã nêu vị trí đúng. Nếu chắc chắn đó là ngoại lệ chính đáng:
sửa bảng `RULES` trong `gate.py` rồi chạy `python3 -m scripts.file_structure --audit`
để xác nhận không vỡ gì (phải ra 0 vi phạm).
Cần làm gấp thì đặt `MIYANO_SKIP_FILE_STRUCTURE=1`.
