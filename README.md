# Miyano ERP

Hệ thống ERP nội bộ của **Công ty TNHH Miyano Việt Nam** — kinh doanh thiết bị & vật tư y tế.

Đây là **hệ thống nội bộ, không phát hành công khai**. Repo này là bản fork sâu, được sửa trực tiếp trong core để phù hợp nghiệp vụ Miyano (xem [CLAUDE.md](CLAUDE.md) và [SPEC.md](SPEC.md)). Nguồn gốc và giấy phép: xem [NOTICE.md](NOTICE.md).

## Phạm vi nghiệp vụ

- **Kế toán Việt Nam** — tuân thủ Thông tư 99/2025/TT-BTC: hệ thống tài khoản, sổ sách (Sổ cái, Nhật ký chung, Sổ chi tiết, Sổ quỹ tiền mặt, Tiền gửi ngân hàng), báo cáo tài chính B01–B03, B09.
- **Kê khai thuế** — Tờ khai GTGT 01/GTGT (xuất XML kiểu eTax), quyết toán TNCN, quyết toán TNDN.
- **Hóa đơn điện tử (HĐĐT)** — tích hợp nhà cung cấp HĐĐT.
- **Khấu hao TT45** — khung khấu hao theo TT45/2013/TT-BTC trên Asset Category.
- Bán hàng, mua hàng, kho, tài sản, sản xuất, dự án theo nền tảng ERP sẵn có.

## Môi trường

App chạy như **một app trong Frappe bench**, không chạy độc lập. Bench root: `/home/miyano/frappe-bench`, site: `miyano`.

Các app bổ trợ cùng bench/site: `assetcore` (vòng đời thiết bị y tế), `antmed_crm` (CRM), `normcore_dmktkt` / `norm_himedic` (định mức KTKT), `workflowcore`, `hrms`.

## Lệnh thường dùng

Chạy từ bench root (`/home/miyano/frappe-bench`):

```bash
bench start                                   # dev server
bench --site miyano migrate                   # áp schema + patches
bench build --app erpnext                     # build JS/CSS
bench --site miyano clear-cache
bench --site miyano console                   # python shell có app context
```

### Kiểm thử

```bash
bench --site miyano run-tests --app erpnext
bench --site miyano run-tests --module erpnext.regional.vietnam.test_tt45
bench --site miyano run-tests --doctype "Sales Invoice"
```

### Lint / format

```bash
pre-commit run --all-files
ruff check erpnext/
ruff format erpnext/
```

Python style: **thụt lề bằng TAB**, độ dài dòng 110, chuỗi nháy kép.

## Giấy phép

Hệ thống nội bộ, không phát hành công khai, không áp dụng giấy phép công khai. Chi tiết bản quyền: [NOTICE.md](NOTICE.md).
