# HĐĐT — email dạng tra cứu, XML không bắt buộc, Đồng bộ lại, tự gửi sau phát hành — Kế hoạch thi công

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Email gửi hóa đơn chính thức theo mẫu Miyano, có mã tra cứu ngắn đọc từ PDF; XML không còn bắt buộc; nút Đồng bộ lại nằm ngoài, bấm là chạy và báo trường nào đổi; ERP tự gửi hóa đơn cho khách khoảng 1–3 phút sau phát hành.

**Architecture:** Thêm `pdf_lookup.py`, đọc mã tra cứu và link ngay trên các byte PDF mà method 380 trả về. Thêm `invoice_email.py`, dựng biến `hd` cho mẫu email, người gửi, CC. Thêm `auto_send.py` (`send_pending_invoices`), gọi ở cuối mỗi lượt của job tải PDF mỗi phút. Phần đồng bộ lại sửa ngay trong `builder.resync_from_source` và `form_state`. Một patch điền mã tra cứu cho các PDF đã có và thay mẫu email nếu mẫu chưa bị sửa tay.

**Tech Stack:** Frappe v15 / Miyano ERP, `pypdf` 6.12 (có sẵn trong env của bench), Jinja Email Template, `frappe.sendmail`.

**Spec:** `docs/fast_miyano/PHAN_TICH_TU_GUI_HDDT_SAU_PHAT_HANH.md` (bản 2.2). **Mục 11 là quyết định cuối**; chỗ nào mục 1–10 nói khác thì làm theo mục 11.

## Global Constraints

- Chạy lệnh bench từ `/home/miyano/frappe-bench`, `--site miyano`. Test chạy **từng module một, tuần tự** (`--module A --module B` chỉ chạy B; hai lệnh `run-tests` chạy song song sẽ deadlock).
- Python thụt lề bằng **TAB**, dòng tối đa 110 ký tự, chuỗi dùng ngoặc kép. Comment và docstring dùng gạch dài `—`, không dùng `–` (ruff RUF002/003).
- Câu hiển thị cho người dùng viết tiếng Việt và đi qua `_()`.
- **Không commit, không tạo nhánh** (CLAUDE.md). Bước cuối của mỗi task là "để nguyên trong working tree".
- Sửa JSON của DocType nào thì nâng `"modified"` của DocType đó. Riêng `fast_einvoice_document.js` thì bắt buộc phải nâng, nếu không trình duyệt vẫn chạy script cũ lưu trong localStorage.
- Không kiểm chứng bằng `bench console` gọi hàm có ghi dữ liệu (gateway, File, sendmail). Mọi kiểm chứng phải nằm trong test.
- Test không gọi mạng. Fast dùng `FakeTransport` (`tests/test_fast_client.py`), email dùng `Mailbox` (`tests/test_fast_approval.py`).
- `configure()` trong `tests/test_fast_client.py` đặt tường minh mọi cờ của Settings. Cờ mới nào cũng phải thêm vào đó với giá trị mặc định an toàn (`auto_send_invoice=0`).
- Ba test hỏng sẵn, không phải lỗi do thay đổi lần này: `test_fast_folders.test_the_uploaded_xml_is_filed_with_the_invoice`, `test_fast_lookup.test_the_declared_number_comes_from_the_einvoice`, `test_fast_pdf.test_it_downloads_once_fast_has_had_a_minute`.
- Số hóa đơn in nguyên như Fast trả về (`4`), không đệm số 0 (Q9).
- Ký hiệu trong email = `fast_pattern + fast_serial` (`1` + `C26TAA` → `1C26TAA`).

## Review Focus

1. **PDF đổi bố cục hoặc PDF rỗng** (`minimal_pdf_bytes` không có chữ): không được ném lỗi làm hỏng việc tải PDF. Trường mã để trống và có comment, nhưng PDF vẫn được lưu. → test ở Task 3.
2. **Job chạy lại liên tục** (mỗi phút, có thể hai worker cùng chạy): mỗi hóa đơn chỉ được gửi đúng một lần. Kế toán vừa bấm nút 10 thì job phải bỏ qua. → test ở Task 7 (`invoice_send_count` đọc lại bằng `FOR UPDATE`).
3. **Mẫu email trên site đã bị kế toán sửa tay:** patch không được ghi đè, chỉ ghi Error Log. → test ở Task 4.
4. **Email nhận hóa đơn chứa nhiều địa chỉ, có dấu `;` hoặc khoảng trắng; CC trong Settings trùng CC trong dialog:** gửi đủ người, không trùng địa chỉ. → test ở Task 5.
5. **Đồng bộ lại trên chứng từ thiếu địa chỉ hoặc email** (nguồn bị xóa dữ liệu): vẫn lưu được (bỏ qua kiểm tra trường bắt buộc), lỗi hiện ở bảng kiểm tra dữ liệu, không ném lỗi. → test ở Task 6.

## Quyết định chờ chủ đầu tư xác nhận khi review plan

Mục Q7 của tài liệu ghi hai điểm sau là *"Đề xuất, chờ duyệt"*. Plan đang làm theo cả hai, nên cần anh/chị xác nhận:

- **(Q7-1)** Bỏ trạng thái 98 khỏi danh sách được đồng bộ. Nút Đồng bộ lại chỉ hiện ở 01–04 và 99; ở 98 phải bấm *Lấy dữ liệu từ Fast (370)* trước.
- **(Q7-2)** Chỉ đưa hóa đơn về Nháp khi dữ liệu thực sự đổi. Không có gì đổi thì giữ nguyên trạng thái và báo *"Dữ liệu đã khớp với chứng từ nguồn"*.

## Những điểm plan tự quyết (tài liệu không nói rõ)

- **Người gửi khi gửi tay:** lấy họ tên, email, điện thoại của người đang đăng nhập; ô nào trống thì lấy từ Settings. **Khi tự gửi:** lấy hoàn toàn từ Settings (mục 4.1). `reply_to` là email người gửi.
- **CC trong Settings** chỉ áp dụng cho email hóa đơn chính thức (nút 10 và tự gửi), không áp dụng cho email bản nháp.
- **Email không kèm XML:** thêm câu *"Quý khách có thể tải file XML (hóa đơn điện tử gốc) tại trang tra cứu."*, theo Q2 (XML để khách tự tra cứu trên Fast).
- **Ghi nhớ "đã thôi tự gửi":** dùng trường ẩn mới `auto_send_stopped` (Check), không suy ra từ log. Lý do: mỗi lý do dừng (không đọc được mã, quá 30 phút chưa có mã CQT, lỗi 3 lần) chỉ được báo `notify_on_error` một lần.
- **Không làm dải cảnh báo "nguồn đã thay đổi"** (mục 7.2.3b), vì Q7 bỏ mọi cảnh báo và hộp xác nhận quanh nút này.
- **Đổi nhãn `fast_key_search`** thành "keySearch (khóa API, không phải mã tra cứu)", để người dùng không nhầm với mã tra cứu ngắn nữa.

---

### Task 1: Đọc mã tra cứu và link tra cứu từ PDF

**Files:**
- Create: `erpnext/einvoice/pdf_lookup.py`
- Modify: `erpnext/einvoice/tests/test_fixtures.py` (thêm `lookup_pdf_bytes`)
- Test: `erpnext/einvoice/tests/test_fast_pdf_lookup.py`

**Interfaces:**
- Produces: `parse_lookup_text(text: str) -> dict` trả `{"code": str, "url": str}`, phần nào không tìm thấy thì là `""`.
- Produces: `read_lookup_from_pdf(content: bytes) -> dict`, cùng dạng trả về. **Không bao giờ ném lỗi**: PDF hỏng hay không có chữ đều trả `{"code": "", "url": ""}`.
- Produces (test helper): `lookup_pdf_bytes(code="6D A83 217 253 61N 682", url="https://tinvoice.fast.com.vn:8000/") -> bytes`. Đây là PDF hợp lệ, có một content stream font Helvetica in hai dòng `Ma tra cuu hoa don (Invoice code): <code>` và `Tra cuu tai (Search on): <url>`, cộng một comment ngẫu nhiên `% <frappe.generate_hash()>` để File không bị gộp theo hash nội dung.

Regex chỉ neo vào phần tiếng Anh, vì phần tiếng Việt phụ thuộc cách font được mã hóa:
- mã: `\(Invoice code\)\s*:\s*([0-9A-Za-z]+(?:[ \t]+[0-9A-Za-z]+)*)`. Mã chỉ cách nhau bằng dấu cách và dừng ở cuối dòng. `\s*` trước mã nuốt được kiểu `:\n \n` mà pypdf tách ra.
- link: `\(Search on\)\s*:\s*(https?://\S+)`

- [ ] **Step 1: Viết test hỏng** trong `test_fast_pdf_lookup.py` (`FrappeTestCase`):
  - `test_parses_the_text_pypdf_extracts_from_fast_pdfs`: input là đúng chuỗi pypdf lấy ra từ FEI-2026-00005, `"Mã tra cứu hóa đơn\n \n(Invoice code)\n:\n \n6D A83 217 253 61N 682\nTra cứu tại\n \n(Search on)\n:\n \nhttps://tinvoice.fast.com.vn:8000/\n"`, kết quả phải là `{"code": "6D A83 217 253 61N 682", "url": "https://tinvoice.fast.com.vn:8000/"}`.
  - Chạy cùng kiểu đó cho mã của hai PDF thật còn lại: `6D AEA D1F 2JB 724 4FG` và `6D A23 B1C 253 922 860`.
  - `test_missing_labels_give_empty_values`: `parse_lookup_text("không có gì")` phải ra `{"code": "", "url": ""}`.
  - `test_reads_a_real_pdf`: `read_lookup_from_pdf(lookup_pdf_bytes())["code"] == "6D A83 217 253 61N 682"`, `url` khớp giá trị mặc định.
  - `test_a_pdf_without_text_is_not_an_error`: `read_lookup_from_pdf(minimal_pdf_bytes())` phải ra hai giá trị rỗng.
  - `test_garbage_bytes_are_not_an_error`: `read_lookup_from_pdf(b"not a pdf")` phải ra hai giá trị rỗng.
- [ ] **Step 2: Chạy, thấy hỏng** — `bench --site miyano run-tests --module erpnext.einvoice.tests.test_fast_pdf_lookup` → ImportError.
- [ ] **Step 3: Cài đặt** `pdf_lookup.py`: dùng `pypdf.PdfReader(io.BytesIO(content))`, nối `extract_text()` của mọi trang, bọc `except Exception` rồi trả rỗng. Cài `lookup_pdf_bytes` trong `test_fixtures.py`, viết theo khuôn `minimal_pdf_bytes` (tự tính bảng xref), thêm object font `/Type /Font /Subtype /Type1 /BaseFont /Helvetica` và một content stream `BT /F1 10 Tf 50 700 Td (…) Tj 0 -14 Td (…) Tj ET`. Nhớ escape dấu `(` `)` trong chuỗi PDF thành `\(` `\)`.
- [ ] **Step 4: Chạy lại** module trên → PASS.
- [ ] **Step 5:** Để nguyên trong working tree.

### Task 2: Trường mới trong Fast EInvoice Settings

**Files:**
- Modify: `erpnext/einvoice/doctype/fast_einvoice_settings/fast_einvoice_settings.json` (nâng `modified`)
- Modify: `erpnext/einvoice/doctype/fast_einvoice_settings/fast_einvoice_settings.py`
- Modify: `erpnext/einvoice/fast_settings.py::get_settings`
- Modify: `erpnext/einvoice/tests/test_fast_client.py::configure` (thêm các khóa mới, `auto_send_invoice=0`)
- Test: `erpnext/einvoice/tests/test_fast_settings.py`

**Interfaces:**
- Produces trong `get_settings()`: `auto_send_invoice: bool`, `lookup_url: str`, `invoice_sender_name: str`, `invoice_sender_phone: str`, `invoice_sender_email: str`, `invoice_email_cc: list[str]` (tách theo `,` hoặc `;`, đã trim, bỏ phần rỗng). Mọi chuỗi đều đã `.strip()`.

Thêm một section mới **"Gửi hóa đơn cho khách"** ngay sau `notify_on_error`, gồm các trường sau. Không có `public_base_url` (Q6).

| fieldname | fieldtype | label | ghi chú |
|---|---|---|---|
| `invoice_delivery_section` | Section Break | Gửi hóa đơn cho khách | |
| `auto_send_invoice` | Check | Tự gửi hóa đơn cho khách sau phát hành | default 0; `depends_on: eval:doc.auto_download_pdf`; description: "Gửi tới Email nhận hóa đơn khoảng 1–3 phút sau phát hành, sau khi Cơ quan Thuế cấp mã." |
| `lookup_url` | Data (options URL) | Trang tra cứu hóa đơn (dự phòng) | description: "Dùng khi không đọc được link tra cứu trong PDF." |
| `invoice_email_cc` | Small Text | CC kế toán Miyano | description: "Nhiều email cách nhau dấu phẩy. Áp dụng cho cả tự gửi và gửi tay." |
| `column_break_invoice_delivery` | Column Break | | |
| `invoice_sender_name` | Data | Người phụ trách gửi hóa đơn | |
| `invoice_sender_phone` | Data | Điện thoại đầu mối | |
| `invoice_sender_email` | Data (options Email) | Email đầu mối (nhận phản hồi) | |

- [ ] **Step 1: Viết test hỏng** trong `test_fast_settings.py`:
  - `test_auto_send_needs_auto_download`: lưu Settings với `auto_send_invoice=1, auto_download_pdf=0` phải ném `frappe.ValidationError`.
  - `test_cc_list_is_split_and_trimmed`: `invoice_email_cc = " a@x.vn; b@x.vn ,, "` → `get_settings().invoice_email_cc == ["a@x.vn", "b@x.vn"]`.
  - `test_invalid_cc_email_is_refused`: `invoice_email_cc = "a@x.vn, khong-phai-email"` khi lưu phải ném `frappe.InvalidEmailAddressError`.
- [ ] **Step 2: Chạy, thấy hỏng.**
- [ ] **Step 3: Cài đặt.** `FastEInvoiceSettings.validate` thêm `_validate_invoice_delivery()`. Hàm này chặn `auto_send_invoice` khi `auto_download_pdf` tắt, với câu báo "Bật “Tự tải PDF sau phát hành” trước — hệ thống chỉ tự gửi khi đã có PDF chính thức.". Mỗi địa chỉ trong `invoice_email_cc` và `invoice_sender_email` đi qua `frappe.utils.validate_email_address(email, throw=True)`. Thêm khóa vào `get_settings`, thêm cờ vào `configure()`.
- [ ] **Step 4: Chạy** `test_fast_settings` → PASS. Chạy thêm `test_fast_client` để chắc `configure()` không hỏng.
- [ ] **Step 5:** Để nguyên trong working tree.

### Task 3: Trường mã tra cứu trên chứng từ, điền khi tải PDF, patch điền cho PDF cũ

**Files:**
- Modify: `erpnext/einvoice/doctype/fast_einvoice_document/fast_einvoice_document.json` (nâng `modified`)
- Modify: `erpnext/einvoice/actions.py::download_official_pdf`
- Create: `erpnext/patches/v15_0/einvoice_lookup_code_and_email_v3.py` + thêm dòng cuối `erpnext/patches.txt`. Patch này **dùng chung với Task 4**.
- Test: `erpnext/einvoice/tests/test_fast_pdf.py`

**Interfaces:**
- Consumes: `pdf_lookup.read_lookup_from_pdf` (Task 1).
- Produces: các trường của FEI `fast_lookup_code` (Data, label "Mã tra cứu in trên hóa đơn"), `fast_lookup_url` (Data options URL, label "Trang tra cứu"). Cả hai đặt sau `public_pdf_url`, `no_copy=1`, **không** read_only, description "Hệ thống tự đọc từ PDF chính thức; không đọc được thì chép tay từ PDF." Thêm `auto_send_stopped` (Check, hidden, read_only, no_copy, label "Đã thôi tự gửi") ở `delivery_section`.
- Produces: `actions.fill_lookup_from_pdf(fei_name: str, content: bytes) -> bool`. Đọc được mã thì ghi đè cả hai trường bằng `db.set_value(..., update_modified=False)` (đọc được link thì mới ghi link) rồi trả `True`. Không đọc được mã thì không đụng giá trị cũ, trả `False`.
- Sửa nhãn và mô tả: `fast_key_search` thành "keySearch (khóa API, không phải mã tra cứu)". Mô tả `official_xml` thành "Không bắt buộc. API Fast chưa có lệnh tải XML; khách tự tải XML trên trang tra cứu. Đã đính ở đây thì email gửi khách kèm theo."

- [ ] **Step 1: Viết test hỏng** trong `test_fast_pdf.py` (class `TestOfficialPdf`, thêm helper `lookup_envelope()` = `envelope(1, base64(lookup_pdf_bytes()))`):
  - `test_download_reads_the_lookup_code_and_url`: sau khi tải thì `fei.fast_lookup_code == "6D A83 217 253 61N 682"` và `fei.fast_lookup_url == "https://tinvoice.fast.com.vn:8000/"`.
  - `test_unreadable_pdf_keeps_the_pdf_and_leaves_a_comment`: dùng `pdf_envelope()` (PDF không có chữ). Kết quả là `official_pdf` có giá trị, `fast_lookup_code` rỗng, và có Comment chứa "Không đọc được mã tra cứu từ PDF".
  - `test_redownload_overwrites_a_hand_typed_code`: set `fast_lookup_code="SAI"` trước, tải `lookup_envelope()` thì mã thành mã đúng.
  - `test_fill_lookup_from_pdf_keeps_old_value_when_unreadable`: set mã `"X"`, gọi `fill_lookup_from_pdf(name, minimal_pdf_bytes())` phải trả `False` và mã vẫn là `"X"`.
- [ ] **Step 2: Chạy, thấy hỏng.**
- [ ] **Step 3: Cài đặt.** Trong `download_official_pdf`, sau khi `_attach_pdf`, gọi `fill_lookup_from_pdf(doc.name, decode_message(response.message))`. Nếu trả `False` thì thêm comment "Không đọc được mã tra cứu từ PDF — chép mã từ PDF vào trường “Mã tra cứu in trên hóa đơn” rồi gửi tay.". Patch `einvoice_lookup_code_and_email_v3.execute()`: `reload_doc` cả `fast_einvoice_document` và `fast_einvoice_settings`. Với mỗi FEI có `official_pdf` mà chưa có `fast_lookup_code`: lấy `frappe.get_doc("File", {"file_url": official_pdf}).get_content()` rồi gọi `fill_lookup_from_pdf`. Bọc từng chứng từ trong `try` + `log_error`. Cuối patch gọi `setup.upgrade_issued_template()` (hàm này có ở Task 4; trong lúc làm Task 3 thì tạm để trống).
- [ ] **Step 4: Chạy** `test_fast_pdf` → PASS. Chỉ được hỏng `test_it_downloads_once_fast_has_had_a_minute` (hỏng sẵn).
- [ ] **Step 5:** Để nguyên trong working tree.

### Task 4: Mẫu email Miyano và biến `hd`

**Files:**
- Create: `erpnext/einvoice/invoice_email.py`
- Modify: `erpnext/einvoice/setup.py` (mẫu mới, `upgrade_issued_template`, bỏ `_add_public_link_row` / `_LOOKUP_ROW` / `_LINK_ROW`)
- Modify: `erpnext/einvoice/actions.py::_render_template` (nhận thêm `extra_context: dict | None`)
- Test: `erpnext/einvoice/tests/test_fast_invoice_email.py`

**Interfaces:**
- Consumes: `get_settings()` (Task 2), `fast_lookup_code` / `fast_lookup_url` (Task 3).
- Produces: `invoice_email.sender_for(settings, user: str | None) -> dict` có khóa `name`, `phone`, `email`. Khi `user` là `None`, `"Administrator"` hoặc `"Guest"` thì lấy hoàn toàn từ Settings. Ngược lại lấy `full_name`, `email`, `mobile_no` của User, ô nào trống thì lấy ô tương ứng trong Settings.
- Produces: `invoice_email.email_context(doc, settings, sender: dict) -> dict`, các khóa đặt đúng tên biến trong `Mau_Email_Gui_Hoa_Don_Miyano.md`:
  - `nguoi_nhan` = `doc.buyer` hoặc `"Quý khách"`; `ten_khach_hang` = `doc.customer_name`; `so_hd` = `doc.fast_invoice_no`
  - `ngay_hd` = `fast_signed_date` dạng `dd/mm/yyyy`; `ky_hieu` = `pattern+serial`; `ma_cqt` = `tax_verification_code` hoặc `""`
  - `ma_tra_cuu` = `fast_lookup_code`; `link_tra_cuu` = `fast_lookup_url` hoặc `settings.lookup_url` hoặc `""`
  - `so_hop_dong_po`, `han_thanh_toan` lấy `po_no`, `due_date` (`dd/mm/yyyy`) của `doc.sales_invoice`. Không có hóa đơn bán thì để `""`.
  - `tong_tien` = `fmt_money(total_amount, currency=doc.currency)`; `co_xml` = `bool(doc.official_xml)`
  - `nguoi_gui`, `sdt_nguoi_gui`, `email_nguoi_gui` lấy từ `sender`.
- Produces: `invoice_email.cc_for(settings, extra) -> list[str]` = CC trong Settings cộng `extra` (chuỗi hoặc list). Bỏ trùng không phân biệt hoa/thường, giữ thứ tự xuất hiện đầu tiên.
- Produces: `setup.upgrade_issued_template() -> bool`. Thay subject và nội dung mẫu `ISSUED_TEMPLATE` **chỉ khi** `_fingerprint(response_html)` thuộc `_ISSUED_ORIGINAL_FINGERPRINTS`; nếu không thì `frappe.log_error("HĐĐT: giữ nguyên mẫu email đã sửa tay", …)` và trả `False`. `_fingerprint(html) = md5(" ".join(html.split()))`. Tập dấu vân tay gồm `"9cd370d6cdc5710ca07a3ebc8d45fd5c"` (hằng cũ trong `setup.py`, giữ lại nguyên văn dưới tên `_PREVIOUS_ISSUED_HTML` để test dùng) và `"9a64dd30e457f9603bd7eaacf4eb0e6e"` (bản đang có trên site miyano). `_make_email_templates` gọi hàm này khi mẫu đã tồn tại.

Tiêu đề (mục 4.2): `CÔNG TY TNHH MIYANO VIỆT NAM gửi hóa đơn điện tử số {{ doc.fast_invoice_no }} cho {{ doc.customer_name }}`

Nội dung là bản đầy đủ ở mục 6 của mẫu Miyano, dựng thành HTML theo khuôn bảng của mẫu cũ, với các chỉnh sửa sau:
- **bỏ** cụm "và ký điện tử trên hóa đơn";
- dòng Mã CQT, PO, Hạn thanh toán bọc trong `{% if hd.… %}`;
- khối tra cứu chỉ hiện khi có `hd.ma_tra_cuu`, gồm nút `<a href="{{ hd.link_tra_cuu }}">TRA CỨU</a>` (inline style dạng nút), đường dẫn và mã in đậm; không có `link_tra_cuu` thì chỉ ghi mã;
- câu về file đính kèm: `co_xml` → "Đính kèm: hóa đơn dạng PDF và file XML (hóa đơn điện tử gốc).", ngược lại → "Hóa đơn dạng PDF được đính kèm email này để Quý khách tiện lưu trữ. Quý khách có thể tải file XML (hóa đơn điện tử gốc) tại trang tra cứu.";
- **không** có `fast_key_search`, **không** có `public_pdf_url`;
- chân thư: `nguoi_gui` (nếu có), "CÔNG TY TNHH MIYANO VIỆT NAM", rồi "ĐT: … | Email: …" (vế nào trống thì bỏ vế đó).

- [ ] **Step 1: Viết test hỏng** trong `test_fast_invoice_email.py`. Fixture giống `SendInvoiceBase`, thêm `fast_pattern="1"`, `fast_serial="C26TAA"`, `fast_invoice_no="4"`, `fast_lookup_code="6D A83 217 253 61N 682"`, `tax_verification_code="TEST000…TEST"`. Render bằng `_render_template(ISSUED_TEMPLATE, doc, extra_context={"hd": email_context(...)})`.
  - `test_renders_number_symbol_tax_code_and_lookup_code`: trong message phải có `"4"`, `"1C26TAA"`, mã CQT, `"6D A83 217 253 61N 682"`, `"TRA CỨU"`; **không** có `"KS-ABC-123"` (keySearch).
  - `test_subject_follows_the_miyano_pattern`: subject = `"CÔNG TY TNHH MIYANO VIỆT NAM gửi hóa đơn điện tử số 4 cho <customer_name>"`.
  - `test_po_and_due_date_rows_hidden_when_empty`: không có "Theo hợp đồng/đơn hàng"; đặt `po_no` trên SI thì dòng đó hiện ra.
  - `test_settings_lookup_url_is_the_fallback`: `fast_lookup_url` rỗng và `lookup_url="https://tracuu.example/"` thì link trong email là link dự phòng.
  - `test_xml_sentence_follows_the_attachment`: có `official_xml` → câu "PDF và file XML"; không có → câu "tải file XML … tại trang tra cứu".
  - `test_no_esign_promise`: message không chứa "ký điện tử".
  - `test_manual_sender_is_the_logged_in_user_with_settings_fallback`: dùng `frappe.set_user` sang user test có email, không có mobile thì `phone` lấy từ Settings.
  - `test_cc_merges_settings_and_dialog_without_duplicates`: Settings `"kt@miyano.vn"` + extra `"KT@miyano.vn; khac@x.vn"` → `["kt@miyano.vn", "khac@x.vn"]`.
  - `test_original_template_is_upgraded`: ghi `_PREVIOUS_ISSUED_HTML` vào Email Template, gọi `upgrade_issued_template()` phải trả `True` và subject mới.
  - `test_hand_edited_template_is_kept`: ghi `"<p>Mẫu riêng</p>"`, gọi hàm phải trả `False`, nội dung giữ nguyên.
- [ ] **Step 2: Chạy, thấy hỏng.**
- [ ] **Step 3: Cài đặt** `invoice_email.py`, mẫu mới trong `setup.py`, `upgrade_issued_template`, `_render_template(..., extra_context=None)` (gộp vào `{"doc", "frappe"}`). Nối lời gọi `upgrade_issued_template()` vào patch ở Task 3.
- [ ] **Step 4: Chạy** `test_fast_invoice_email`, `test_einvoice_setup`, `test_fast_approval` → PASS. Test cũ nào khẳng định "có `fast_key_search`" hay "có `public_pdf_url`" trong mẫu thì sửa theo Q6 và mục 4.2.
- [ ] **Step 5:** Để nguyên trong working tree.

### Task 5: Nút 10 — XML không bắt buộc, reply_to, CC Settings, người gửi

**Files:**
- Modify: `erpnext/einvoice/actions.py` (`send_invoice_to_customer`, `_send_invoice_via_erp`, `_mark_invoice_sent`)
- Modify: `erpnext/einvoice/doctype/fast_einvoice_document/fast_einvoice_document.js` (mô tả ô CC của `send_invoice`)
- Test: `erpnext/einvoice/tests/test_fast_send_invoice.py`

**Interfaces:**
- Consumes: `invoice_email.sender_for`, `email_context`, `cc_for` (Task 4).
- Produces: `_send_invoice_via_erp(doc, to, cc, subject, message, mailer, sender=None, purpose=None, auto=False) -> dict`. `sender=None` nghĩa là `sender_for(settings, frappe.session.user)`. `purpose` mặc định là "Gửi hóa đơn chính thức cho khách". Mailer ném lỗi thì `_close_email_log(log, ok=False, error_message=str(e))` rồi **ném lại**. Hàm vẫn chặn khi thiếu `official_pdf`.
- Produces: `_mark_invoice_sent(doc, to, auto=False)`. Khi `auto=True` thì comment là "Hệ thống đã tự gửi hóa đơn chính thức tới {0}.".
- Lời gọi mailer: `attachments` = PDF, kèm thêm XML nếu có; `cc=cc_for(settings, cc)`; `reply_to=sender["email"] or None`; render với `extra_context={"hd": email_context(doc, settings, sender)}`.

- [ ] **Step 1: Viết test hỏng.** Sửa `test_erp_sending_needs_the_xml_too` thành `test_erp_sending_without_xml_attaches_only_the_pdf` (chưa có XML → gửi thành công, `attachments == [{"file_url": official_pdf}]`). Giữ `test_the_email_carries_both_the_pdf_and_the_xml`. Thêm:
  - `test_missing_pdf_still_blocks`
  - `test_reply_to_is_the_sender_email`: Settings `invoice_sender_email="hd@miyano.vn"`, gửi bằng Administrator → `mailbox.sent[0]["reply_to"] == "hd@miyano.vn"`.
  - `test_settings_cc_is_added`: CC trong Settings xuất hiện trong `mailbox.sent[0]["cc"]`, cùng với CC của dialog.
  - `test_failed_mailer_marks_the_log_failed`: mailer ném `Exception` → `assertRaises`. Log Email cuối cùng có `success == 0` và `status == "Lỗi"`. `invoice_send_count` vẫn bằng 0.
- [ ] **Step 2: Chạy, thấy hỏng.**
- [ ] **Step 3: Cài đặt** theo Interfaces. Trong JS, ô `cc` của `send_invoice` thêm `description: __("Hệ thống tự CC thêm hộp thư kế toán trong Fast EInvoice Settings.")`.
- [ ] **Step 4: Chạy** `test_fast_send_invoice` → PASS.
- [ ] **Step 5:** Để nguyên trong working tree.

### Task 6: Nút Đồng bộ lại — đặt ngoài, bấm là chạy, báo trường đổi

**Files:**
- Modify: `erpnext/einvoice/constants.py` (thêm `RESYNC_STATUSES`)
- Modify: `erpnext/einvoice/builder.py::resync_from_source` (+ helper `_resync_snapshot`)
- Modify: `erpnext/einvoice/form_state.py` (nút `resync`: nhãn, cấp 0, trạng thái; `_fallback_buttons`; câu trong `_release_stuck_issuance`; docstring về cấp 0)
- Modify: `erpnext/einvoice/doctype/fast_einvoice_document/fast_einvoice_document.js` (`run_button` cấp 0, `button_group` trả `null` cho `resync`)
- Test: `erpnext/einvoice/tests/test_fast_builder.py`, `test_fast_form_state.py`, `test_fast_end_to_end.py`

**Interfaces:**
- Produces: `RESYNC_STATUSES = frozenset({STATUS_DRAFT, STATUS_DRAFT_VIEWED, STATUS_AWAITING_CUSTOMER, STATUS_CUSTOMER_APPROVED, STATUS_ERROR})` (Q7-1: không có 98).
- Produces: `resync_from_source(fei) -> dict`, có dạng `{"ok": True, "changed": list[str], "message": str}`.
  - Không đổi gì: `changed == []`, message "Dữ liệu đã khớp với chứng từ nguồn — không có gì thay đổi.", **không lưu**, trạng thái và `revision_count` giữ nguyên (Q7-2).
  - Có đổi: lưu với `flags.ignore_mandatory = True`. Trạng thái về Nháp, `revision_count` cộng 1 nếu không phải từ 01 (giữ quy tắc cũ). Message "Đã đồng bộ lại từ chứng từ nguồn. Các trường thay đổi:<br>" cộng danh sách dòng `"<Nhãn>: <cũ> → <mới>"`, rồi câu "Hóa đơn đã về Nháp." nếu trước đó không ở 01.
- Snapshot dùng để so sánh gồm các trường master mà `_copy_from_source` ghi: `customer, customer_code, customer_name, customer_tax_code, customer_type, address, buyer, phone_number, email_deliver, payment_method, currency, exchange_rate, human_name, totals_manual_override, amount, tax_amount, total_amount`. Bỏ `invoice_date`. Nhãn lấy từ `meta.get_label`. Dòng hàng so theo tuple `(item_code, item_name, uom, flt(qty, 6), flt(price, 6), flt(discount_amount, 6), str(tax_rate))`. Khác thì thêm một mục "Dòng hàng: <n cũ> dòng → <n mới> dòng (có thay đổi)".
- Nút `resync`: nhãn "Đồng bộ lại từ chứng từ nguồn" (bỏ nhãn riêng "từ phiếu giao"), cấp **0**, trạng thái `RESYNC_STATUSES`.
- JS: `run_button` thêm `if (button.level === 0) return call_action(frm, button, {});`. `call_action` vẫn hiện `result.message` như hiện nay.

- [ ] **Step 1: Viết/sửa test.**
  - `test_fast_builder`: `test_resync_without_changes_keeps_status` (đặt 03, đồng bộ ngay thì vẫn 03, `changed == []`, `revision_count` không đổi); `test_resync_reports_the_changed_email` (đổi `email_id` của Customer thì `changed` có đúng một mục chứa "Email nhận hóa đơn"); `test_resync_saves_even_when_the_source_lost_the_address` (xóa địa chỉ nguồn sao cho `address` rỗng thì không ném lỗi, `doc.address == ""`); `test_resync_is_refused_at_98`. Các test cũ như `test_resync_returns_an_approved_invoice_to_draft` phải tạo ra thay đổi ở nguồn trước rồi mới khẳng định về Nháp.
  - `test_fast_form_state`: `resync` có `level == 0`; không có nút `resync` ở `98 - Cần đối soát`; nhãn là "Đồng bộ lại từ chứng từ nguồn" cho cả nguồn SI và nguồn phiếu giao (thay `test_the_resync_label_names_the_real_source`); `_fallback_buttons` ở 98 không có `resync`.
  - `test_fast_end_to_end::test_resyncing_a_draft_does_not_inflate_the_revision_count` vẫn phải qua.
- [ ] **Step 2: Chạy, thấy hỏng.**
- [ ] **Step 3: Cài đặt** theo Interfaces. Câu trong `_release_stuck_issuance` bỏ vế "hoặc Đồng bộ lại từ chứng từ nguồn rồi phát hành lại".
- [ ] **Step 4: Chạy** `test_fast_builder`, `test_fast_form_state`, `test_fast_end_to_end` (từng module) → PASS.
- [ ] **Step 5:** Để nguyên trong working tree.

### Task 7: Tự gửi sau phát hành

**Files:**
- Create: `erpnext/einvoice/auto_send.py`
- Modify: `erpnext/einvoice/actions.py::download_pending_official_pdfs` (thêm tham số `_mailer=None`; gọi `send_pending_invoices` ở cuối, bọc `try` riêng)
- Test: `erpnext/einvoice/tests/test_fast_auto_send.py`

**Interfaces:**
- Consumes: `_send_invoice_via_erp(..., sender=, purpose=, auto=True)` (Task 5), `invoice_email.sender_for(settings, None)` (Task 4), `tax_status._apply_tax_status(doc, client)`, `fast_settings.get_notify_recipients()`, trường `auto_send_stopped` (Task 3).
- Produces: `send_pending_invoices(client=None, mailer=None) -> list[str]`, trả tên các chứng từ **đã gửi** trong lượt.
- Hằng số: `AUTO_SEND_WINDOW_HOURS = 24`, `AUTO_SEND_TAX_WAIT_MINUTES = 30`, `AUTO_SEND_MAX_FAILURES = 3`, `AUTO_SEND_PURPOSE = "Tự gửi hóa đơn cho khách"`, `TAX_RECHECK_SECONDS = 60`.

Quy tắc. Mục 6.2, đã trừ các điều kiện mà Q3 và Q4 bỏ:
1. Chỉ chạy khi `settings.enabled and settings.auto_send_invoice`. **Không** kiểm tra môi trường TEST, **không** kiểm tra hàng đợi email (Q4).
2. Ứng viên lọc trong SQL: `status in (06, 08)`, `official_pdf` có giá trị, `invoice_send_count = 0`, `auto_send_stopped = 0`, `issued_time >= now − 24h`. Sắp xếp theo `issued_time asc`.
3. Với từng ứng viên, theo thứ tự:
   - `email_deliver` rỗng → bỏ qua, không tính là lỗi.
   - `fast_lookup_code` rỗng → `_stop(doc, "Không đọc được mã tra cứu từ PDF — chép mã vào chứng từ rồi bấm Gửi hóa đơn cho khách để gửi tay.")`.
   - `tax_verification_code` rỗng: nếu `tax_checked_time` rỗng hoặc đã quá 60 giây thì gọi `_apply_tax_status(doc, client)` rồi `doc.reload()`. Sau đó `status == 09` → bỏ qua (cảnh báo từ chối đã gửi rồi). Vẫn chưa có mã mà `issued_time` đã quá 30 phút → `_stop(doc, "Quá 30 phút chưa có mã của Cơ quan Thuế — bấm Gửi hóa đơn cho khách khi đã có mã.")`. Ngược lại thì chờ lượt sau.
   - Chống trùng: `frappe.db.sql("select invoice_send_count from `tabFast EInvoice Document` where name=%s for update", name)`. Kết quả > 0 thì bỏ qua.
   - Gửi qua `_send_invoice_via_erp(doc, recipients(email_deliver), None, None, None, mailer, sender=sender_for(settings, None), purpose=AUTO_SEND_PURPOSE, auto=True)`.
   - Gặp lỗi thì `frappe.log_error`, rồi đếm log `{"fei_document": name, "operation": "Email", "purpose": AUTO_SEND_PURPOSE, "success": 0}`. Đủ 3 → `_stop(doc, "Tự gửi lỗi 3 lần — bấm Gửi hóa đơn cho khách để gửi tay.")`. Một hóa đơn lỗi không được dừng cả lô.
4. `_stop(doc, reason)`: set `auto_send_stopped=1` (`update_modified=False`), thêm comment `reason`, gửi `frappe.sendmail` tới `get_notify_recipients()` với tiêu đề "[HĐĐT] Cần gửi tay hóa đơn {số}". Lỗi khi báo thì chỉ ghi `log_error`, giống `_notify_rejection`.

- [ ] **Step 1: Viết test hỏng** trong `test_fast_auto_send.py`. Fixture: `configure(enabled=1, auto_download_pdf=1, auto_send_invoice=1, ...)`; FEI ở 06, `issued_time = now − 3 phút`, có `official_pdf` (tải bằng `lookup_envelope()`), có `fast_lookup_code`, `tax_verification_code`, `email_deliver="kh@x.vn"`; mailer là `Mailbox()`.
  - `test_disabled_sends_nothing`
  - `test_sends_exactly_once`: chạy hai lượt, `len(mailbox.sent) == 1`, trả `[name]` rồi `[]`.
  - `test_issued_moves_to_sent_and_tax_accepted_stays`: 06 → 07; đặt 08 thì vẫn 08.
  - `test_skips_without_pdf`, `test_skips_without_email` (không dừng hẳn: `auto_send_stopped == 0`), `test_skips_when_issued_over_24h_ago`, `test_skips_when_already_sent_by_hand` (`invoice_send_count=1`).
  - `test_missing_lookup_code_stops_and_notifies_once`: chạy hai lượt thì `auto_send_stopped == 1`, đúng 1 comment, không gửi gì.
  - `test_waits_for_the_tax_code`: không có mã CQT, `FakeTransport` trả 8200 rỗng → không gửi, `auto_send_stopped == 0`.
  - `test_sends_once_the_tax_office_accepts`: không có mã CQT, 8200 trả `taxStatus "3"` kèm `verificationCode` → gửi, trạng thái 08 (không lên 07).
  - `test_rejected_by_tax_office_is_not_sent`: 8200 trả `taxStatus "4"` → không gửi.
  - `test_gives_up_after_30_minutes_without_tax_code`: `issued_time = now − 31 phút`, 8200 rỗng → `auto_send_stopped == 1`.
  - `test_three_mailer_failures_stop_auto_send`: mailer luôn ném lỗi, chạy ba lượt → `auto_send_stopped == 1`, `invoice_send_count == 0`.
  - `test_the_pdf_job_triggers_the_send`: FEI chưa có PDF, `issued_time = now − 2 phút`, đã có mã CQT. Gọi `download_pending_official_pdfs(client=…lookup_envelope(), _sleep=lambda s: None, _mailer=mailbox)` → `len(mailbox.sent) == 1`.
- [ ] **Step 2: Chạy, thấy hỏng.**
- [ ] **Step 3: Cài đặt** `auto_send.py`, nối vào `download_pending_official_pdfs`. Import `send_pending_invoices` **bên trong hàm**, vì `auto_send` import `actions` và `tax_status`, còn `tax_status` lại import `actions`. Lời gọi phải chạy cả khi lượt đó không có PDF nào để tải: tách `return tried` ra sau khối gọi gửi.
- [ ] **Step 4: Chạy** `test_fast_auto_send`, `test_fast_pdf`, `test_fast_tax_status` → PASS. `test_fast_pdf` chỉ được hỏng đúng 1 test hỏng sẵn.
- [ ] **Step 5:** Để nguyên trong working tree.

### Task 8: Runbook, migrate, toàn bộ test module, lint

**Files:**
- Modify: `docs/fast_miyano/RUNBOOK_HDDT_FAST.md`: mục 2 thêm cách bật tự gửi và điền đầu mối/CC; mục 3 thay câu "phải có XML"; mục 4 thêm mục "4.7 Không tự gửi được" (thiếu mã tra cứu, quá 30 phút chưa có mã CQT, lỗi 3 lần → gửi tay bằng nút 10).
- Modify: `docs/fast_miyano/PHAN_TICH_TU_GUI_HDDT_SAU_PHAT_HANH.md`: trong khối đầu trang, thay câu "Chưa có dòng mã nào được sửa" bằng một dòng trỏ tới plan này.

- [ ] **Step 1:** Chạy `pre-commit run --files <mọi file đã sửa/tạo>` cho tới khi sạch.
- [ ] **Step 2:** Chạy **từng module** của `erpnext/einvoice/tests/` và `erpnext/einvoice/report/doi_soat_hoa_don_dien_tu/test_doi_soat_hoa_don_dien_tu.py`, tuần tự. Chỉ được phép hỏng 3 test hỏng sẵn đã nêu ở Global Constraints. Test nào khác hỏng thì làm A/B: `git show HEAD:<file>` ra scratchpad, chạy lại bản cũ để so (không dùng `git stash`).
- [ ] **Step 3:** `bench --site miyano migrate`. Sau đó kiểm tra chỉ đọc bằng `bench --site miyano mariadb`:
  - `fast_lookup_code` của FEI-2026-00001/00003/00005 lần lượt là `6D AEA D1F 2JB 724 4FG`, `6D A23 B1C 253 922 860`, `6D A83 217 253 61N 682`;
  - subject của Email Template "Fast HĐĐT - Hóa đơn chính thức" bắt đầu bằng "CÔNG TY TNHH MIYANO VIỆT NAM gửi hóa đơn điện tử số";
  - Error Log không có dòng mới của patch.
- [ ] **Step 4:** `bench build --app erpnext` không bắt buộc (JS form không đi qua bundle), nhưng `modified` của FEI phải lớn hơn bản cũ.
- [ ] **Step 5:** Báo lại cho chủ đầu tư:
  - cần chạy `sudo supervisorctl restart frappe-bench-web: frappe-bench-workers:` thì gunicorn và worker mới nhận code mới;
  - trình duyệt cần bấm *Reload* trong menu tài khoản;
  - `auto_send_invoice` mặc định **tắt**. Trước khi bật cần điền đầu mối và CC trong Settings.

  Để nguyên mọi thay đổi trong working tree, không commit.
