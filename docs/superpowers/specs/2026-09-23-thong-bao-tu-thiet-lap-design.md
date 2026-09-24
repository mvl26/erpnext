# Thiết kế kỹ thuật — Thông báo tự thiết lập (BA_NTF_V4)

| Thông tin | Nội dung |
| --- | --- |
| Tài liệu nguồn | `docs/BA_ThongBao_TuThietLap_CR01_20260922.md` (V1.0 — bản chốt để build), `docs/CR_01_ThongBaoPO_GuiNCC_20260917_V2.1.md` |
| Phiên bản | V1.1 — 23/09/2026 (đã đồng bộ với mã nguồn sau khi build xong) |
| Hệ thống | Miyano ERP — module `Supply Notification` (`erpnext/supply_notification/`) |
| Nhánh | `feat/vn-mua-ban-thong-bao-tu-dong` |
| Trạng thái mã hiện tại | 12 điểm NTF-01…NTF-12 chạy trên mô hình cứng trong `constants.py`; 2.794 dòng, 50 test |
| Khảo sát site `miyano` 22/09/2026 | 12 điểm giữ nguyên câu chữ hạt giống (`modified_by = Administrator`, chưa ai sửa trên site) · 1 dòng nhật ký gửi · scheduler **đang tắt** · Email Queue `Not Sent` = 1 · chưa có Workspace của module · Address chưa có custom field người nhận · chưa ai được gán role *Quản trị thông báo* |

> **Phát hiện quan trọng cho chuyển đổi:** không có bản ghi điểm nào bị nghiệp vụ sửa câu chữ hay người nhận trên site. Patch chuyển đổi vì vậy chạy trên dữ liệu đúng bằng hạt giống — rủi ro RK5 gần như bằng 0, nhưng patch **vẫn** phải viết theo hướng không ghi đè (mục 8.2) vì site khác và các lần chạy sau.

---

## 1. Mục tiêu thiết kế

Chuyển toàn bộ nghiệp vụ thông báo từ **mã nguồn** sang **dữ liệu cấu hình** người dùng sửa được trên giao diện, giữ nguyên hành vi 12 điểm đang chạy, và đáp ứng CR_01 hoàn toàn bằng cấu hình.

Ranh giới cố định (nguyên tắc 1 của BA, kiểm bằng AC-20):

| Code chịu trách nhiệm | Cấu hình chịu trách nhiệm |
| --- | --- |
| Bắt sự kiện, cache, chạy nền, chống trùng, giới hạn an toàn | Chứng từ nào, thời điểm nào, điều kiện gì |
| Máy đánh giá điều kiện (toán tử) | Trường nào, toán tử nào, giá trị nào |
| Diễn giải phòng ban → người, lọc, khử trùng | Phòng ban nào, người nào, nhóm nào |
| Jinja hộp cát, định dạng tiền/ngày/Link | Tiêu đề, thân email, câu chữ |
| Cách dựng từng **khối** nội dung | Dùng khối nào, cột nào, thứ tự nào |

Sau khi build xong, `constants.py` **chỉ còn**: danh sách DocType cấm, hằng kỹ thuật (tên sự kiện realtime, tên role), và **dữ liệu hạt giống** cho site mới. Không còn `POINTS` được mã chạy đọc trong `events.py` / `reminders.py` / `content.py`.

---

## 2. Kiến trúc tổng thể

```
                    ┌──────────────────────── cấu hình (người dùng sửa) ────────────────────────┐
                    │ Cài đặt thông báo (Single)                                                │
                    │ Điểm thông báo ── Điều kiện · Cột khối · Nhóm người nhận · Mẫu dùng chung │
                    └───────────────────────────────┬──────────────────────────────────────────┘
                                                    │ đọc qua cache (registry.py)
 sự kiện chứng từ                                   ▼
 after_insert / on_submit / on_cancel / on_change ─► events.py ──► conditions.py ──► enqueue
 cron hằng giờ ──────────────────────────────────► reminders.py ─┘                     │
 nút trên form ──────────────────────────────────► manual.py ────────────────────────┐ │
                                                                                     ▼ ▼
                                                              dispatch.py  (chống trùng, trần email,
                                                                            chế độ thử, 3 kênh, nhật ký)
                                                                     │
                            context.py (ngữ cảnh chỉ đọc) ───► content.py ───► blocks.py / snippets
                                                                     │
                                            email nội bộ · in-app + toast · email ra ngoài
```

Mọi đường vào đều đi qua **một** hàm gửi (`dispatch.send`), nên chống trùng, chế độ thử, trần email, nhật ký chỉ viết một lần.

---

## 3. Mô hình dữ liệu

### 3.1. `Supply Notification Settings` (Single, mới)

| Nhóm | Trường | Kiểu | Mặc định | Ghi chú |
| --- | --- | --- | --- | --- |
| Toàn cục | `enabled` | Check | 1 | Tắt = không gửi gì, kể cả nút Thủ công |
| Toàn cục | `test_mode` | Check | 0 | D16 |
| Toàn cục | `test_email` | Data | trống | Bắt buộc khi `test_mode` bật; hạt giống để trống, PO tự điền |
| Email | `default_subject_prefix` | Data | `[SupplyCore]` | Chỉ dùng làm mặc định cho điểm **mới** |
| Email | `internal_footer_snippet` | Link → Snippet | — | Chèn cuối email nội bộ |
| Email | `external_footer_snippet` | Link → Snippet | — | Chèn cuối email ra ngoài |
| Email | `max_item_rows` | Int | 50 | Trần dòng của `bang_mat_hang` |
| In-app | `sound` | Select | `alert` | `alert, chime, click, email, submit, error, cancel, delete` — đúng tên file trong `frappe/public/sounds` |
| In-app | `toast_seconds` | Int | 10 | |
| In-app | `sound_debounce_seconds` | Int | 3 | |
| Nhắc hạn | `reminder_hour` | Int (0–23) | 8 | D31 — một giờ chung |
| An toàn | `hourly_email_cap` | Int | 200 | NF3, 0 = không giới hạn |
| Nhật ký | `auto_log_retention_days` | Int | 180 | D30 |
| Nhật ký | `manual_log_retention_days` | Int | 0 | 0 = giữ vĩnh viễn |

Đọc qua `settings.get_settings()` → `frappe.get_cached_doc`. `on_update` xoá cache điểm + cache boot.

### 3.2. `Supply Notification Point` (dựng lại, giữ tên và dữ liệu)

`autoname: field:code`, `track_changes: 1` (BR3). Form chia **7 thẻ** (Tab Break) đúng mục 5.2 của BA.

**Thẻ 1 — Chung:** `code` (Data, chỉ đọc sau khi lưu, JS gợi ý mã kế tiếp `NTF-nn`), `title`, `enabled`, `function_group` (Select: Mua hàng / Bán hàng / Kho / Kế toán / Khác), `is_seed` (Check, ẩn, chỉ đọc — điểm hạt giống, D20), `paused_reason` (Small Text, chỉ đọc — điền khi tự tạm dừng vì trần email), `notes`.

**Thẻ 2 — Khi nào gửi:**

| Trường | Kiểu | Hiện khi |
| --- | --- | --- |
| `reference_doctype` | Link → DocType (query lọc bỏ DocType cấm) | luôn |
| `trigger_event` | Select: `New` · `Submit` · `Cancel` · `Value Change` · `Workflow Transition` · `Date Reminder` · `Manual` | luôn |
| `watch_field` | Autocomplete (trường của chứng từ) | `Value Change` |
| `watch_value` | Data — "chỉ khi đổi **thành** giá trị này" | `Value Change` |
| `workflow_state` | Autocomplete (trạng thái của Workflow đang bật trên chứng từ) | `Workflow Transition` |
| `date_field` | Autocomplete (trường Date/Datetime) | `Date Reminder` |
| `reminder_offsets` | Data, ví dụ `-7, -3, -1` (âm = trước hạn) hoặc `+1, +7` | `Date Reminder` |
| `button_label`, `button_color` (Select), `button_role` (Link → Role, trống = ai có quyền sửa chứng từ — D27), `manual_docstatus` (Select: Đã ghi sổ / Nháp / Cả hai) | | `Manual` |
| `condition_logic` | Select: `VÀ` / `HOẶC` | luôn |
| `conditions` | Table → `Supply Notification Condition` | luôn |

**Thẻ 3 — Gửi cho ai:** `departments` (giữ nguyên child cũ), `users` (giữ nguyên), `recipient_groups` (Table MultiSelect → `Supply Notification Group Link`), `notify_owner`, `notify_triggering_user`, `user_fields` (Table → `Supply Notification Field Ref` — các trường kiểu Link→User trên chứng từ), `allow_opt_out` (D18) · **Ngoài:** `notify_external`, `external_party_contact` (Check, mặc định 1), `external_email_fields` (Table → Field Ref), `external_fixed_emails` (Small Text), `external_groups` (Table MultiSelect) · **CC/BCC:** `cc_owner`, `cc_triggering_user`, `cc_emails`, `bcc_emails` · **Trả lời về:** `reply_to_mode` (Select: Không đặt / Người tạo / Người bấm gửi / Email cố định), `reply_to_email`.

**Thẻ 4 — Kênh:** `send_email`, `send_inapp`, `notify_external` (hiển thị lại, cùng trường với thẻ 3).

**Thẻ 5 — Nội dung nội bộ:** `subject_prefix` (Data, mặc định lấy từ Cài đặt khi tạo mới), `subject_template` (Small Text), `body_template` (Text Editor), `inapp_template` (Small Text, trống = dùng tiêu đề) · **Biến dựng sẵn:** `party_field`, `amount_field`, `main_date_field` (Autocomplete — F12) · **Cấu hình khối:** `item_table_field` (Autocomplete, mặc định `items`), `item_columns` (Table → `Supply Notification Block Column`), `fact_rows` (Table → Block Column), `address_field` (Autocomplete — địa chỉ giao / xuất / thanh toán), `signature_person` (Select: Người tạo / Người bấm gửi) · HTML `available_inserts` (bảng "Có thể chèn", dựng bằng JS).

**Thẻ 6 — Nội dung gửi ra ngoài:** `external_subject_template`, `external_body_template` (Text Editor), `attach_pdf`, `print_format`, `attach_document_files` (Check — tệp đã đính trên chứng từ), `require_pdf` (Check — không tạo được PDF thì không gửi).

**Thẻ 7 — Kiểm tra:** `preview_reference` (Dynamic Link theo `reference_doctype`, không ảnh hưởng gửi thật), HTML `stats_html` (số lần gửi 30 ngày, tỉ lệ lỗi — nạp bằng JS).

**Trường cũ bị gỡ khỏi JSON** (cột vẫn còn trong bảng, patch đọc bằng SQL rồi mới thôi dùng): `filter_note`, `intro_template`, `action_template`, `external_intro_template`, `external_closing`.

**Thanh công cụ (JS):** Xem trước người nhận · Xem trước email · Gửi thử cho tôi · Sao chép điểm · Nhật ký của điểm · Hướng dẫn (?).

### 3.3. Các DocType con và phụ trợ (mới)

| DocType | Loại | Trường |
| --- | --- | --- |
| `Supply Notification Condition` | child | `fieldname` (Autocomplete, hỗ trợ `items.item_group`), `operator` (Select: `=`, `≠`, `>`, `≥`, `<`, `≤`, `Trong danh sách`, `Không trong danh sách`, `Có giá trị`, `Trống`, `Chứa`), `value` (Data) |
| `Supply Notification Block Column` | child | `fieldname` (Autocomplete — trường chứng từ **hoặc** tên biến dựng sẵn), `label` (Data), `only_if_previous_empty` (Check — giữ hành vi "hạn thanh toán, nếu trống thì ngày") |
| `Supply Notification Field Ref` | child | `fieldname` (Autocomplete) |
| `Supply Notification Recipient Group` | chính | `group_name` (autoname), `disabled`, `departments`, `users` (dùng lại 2 child cũ), `fixed_emails` (Small Text), nút *Xem thành viên thực tế* |
| `Supply Notification Group Link` | child (Table MultiSelect) | `group` (Link) |
| `Supply Notification Snippet` | chính | `snippet_name` (autoname), `scope` (Select: `Nội bộ` / `Ngoài` / `Cả hai`), `content` (Text Editor), HTML `used_by` |
| `Supply Notification Opt Out` | chính | `user` (Link), `point` (Link) — unique theo cặp, người nhận tự tạo/xoá từ trang *Thông báo của tôi* |

### 3.4. `Supply Notification Dispatch Log` (bổ sung)

Thêm: `triggered_by` (Link User), `trigger_event` (Data), `is_manual` (Check), `test_mode` (Check), `subject` (Small Text), `cc` (Small Text), `bcc` (Small Text), `attachments` (Small Text), `reason` (Small Text — lý do bỏ qua/lỗi dễ đọc, tách khỏi `remark` kỹ thuật). Nút **Gửi lại** trên dòng `Failed`. Thêm `Link` từ chứng từ nguồn qua `dashboard` của điểm và `additional_timeline_content`.

**Mốc (`milestone`) — quy ước giữ tương thích với dữ liệu cũ:**

| Loại | Chuỗi mốc |
| --- | --- |
| Tạo mới / Ghi sổ / Huỷ | `new` / `submit` / `cancel` (cũ: `submit` — giữ nguyên) |
| Trường thay đổi | `change:<fieldname>:<giá trị mới>` |
| Chuyển trạng thái duyệt | `wf:<trạng thái>` |
| Nhắc theo ngày | `d7`, `d3`, `d1` cho mốc **âm** (giữ đúng chuỗi cũ) · `q1`, `q7` cho mốc **dương** (quá hạn) |
| Thủ công | `manual` (không chống trùng, D17) |

Trường `milestone` **bỏ giới hạn 16 ký tự** của bản cũ (mốc `change:<trường>:<giá trị>` dài hơn thế); `dispatch` cắt ở 140 ký tự khi ghi và khi tra chống trùng. Giữ giới hạn cũ thì mọi lần bắn *Trường thay đổi* chết trong im lặng ngay ở bước ghi nhật ký — đúng lỗi đã gặp khi build.

---

## 4. Bộ máy (các module Python)

### 4.1. `registry.py` (mới) — cache cấu hình, NF1

- `doctypes_with_points()` → `set[str]`, cache Redis khoá `sn:doctypes`, dựng bằng một truy vấn `get_all("Supply Notification Point", {"enabled": 1}, pluck="reference_doctype")`.
- `points_for(doctype, trigger_event)` → danh sách `frappe.get_cached_doc` của điểm khớp.
- `clear_cache()` gọi từ `on_update` / `on_trash` của Point, Group, Snippet, Settings → **F7**: sửa cấu hình có hiệu lực ngay, không cần deploy.
- Thoát sớm: `if doc.doctype not in doctypes_with_points(): return` — một lần đọc Redis (đã có local cache trong request), đạt NF1.

### 4.2. `events.py` — nối `doc_events["*"]`

Bốn móc duy nhất, thay cho 8 DocType nối tay trong `hooks.py`:

| Móc | Loại thời điểm phục vụ |
| --- | --- |
| `after_insert` | `New` |
| `on_submit` | `Submit` |
| `on_cancel` | `Cancel` |
| `on_change` | `Value Change`, `Workflow Transition` |

**Vì sao `on_change` chứ không phải `on_update`:** `Document.db_set` (frappe `model/document.py:1290`) chạy `on_change`, còn `on_update` thì không. Các trường trạng thái của ERPNext (`delivery_status`, `per_received`, `status`, `workflow_state` khi chuyển bằng Workflow Action) đều được ghi bằng `db_set`; nối vào `on_update` sẽ bỏ sót đúng AC-02/AC-03. `db_set` cũng tự nạp `doc_before_save` trước khi chạy (dòng 1260), nên so sánh giá trị cũ/mới luôn có dữ liệu.

So sánh qua `events.value_changed`: bỏ qua khi `doc.flags.in_insert`; **trống ↔ trống không tính là đổi** (`None` và chuỗi rỗng), và trường số so theo số (`None` = `0` = `0.0`). Thiếu bước chuẩn hoá này thì một lần ghi sổ — vốn điền 0 vào hàng loạt trường số — bắn "giá trị đã đổi" cho những trường chưa ai đụng tới. Sau đó mới xét `watch_value`.

Mọi việc gửi đẩy sang `frappe.enqueue(..., queue="short", enqueue_after_commit=True, now=frappe.flags.in_test)` — cặp cờ bắt buộc theo `test-env-quirks`. Toàn hàm bọc `try/except` ghi Error Log (BR1: không bao giờ chặn chứng từ).

Danh sách DocType cấm (D19) nằm trong `constants.BLOCKED_DOCTYPES`: `Email Queue`, `Notification Log`, `Communication`, `Comment`, `Version`, `Error Log`, `Activity Log`, `Scheduled Job Log`, `Supply Notification Dispatch Log`, `Supply Notification Point`, `Supply Notification Settings`, `File`, `Access Log`, `Route History`, `Prepared Report` + mọi DocType `issingle` hoặc `istable`.

### 4.3. `conditions.py` (mới)

```python
def match(point, doc) -> bool:
	"""Chứng từ có thoả bảng điều kiện của điểm không (VÀ / HOẶC)."""
```

- Trường thường: so sánh trên giá trị đã ép kiểu theo `df.fieldtype` (số → `flt`, ngày → `getdate`, còn lại → chuỗi không phân biệt hoa thường với `Chứa`).
- Trường bảng con `items.item_group`: thoả khi **ít nhất một dòng** thoả (F6).
- `to_filters(point)` — với logic `VÀ` và điều kiện không thuộc bảng con, sinh bộ lọc SQL để `reminders.py` lọc ngay trong truy vấn thay vì nạp hết chứng từ.
- Điều kiện trỏ tới trường không tồn tại → coi như **không thoả** và ghi Error Log một lần (không nổ giữa lúc ghi sổ); khi lưu điểm thì V3 chặn từ đầu.
- Điều kiện **ngày** mà một vế không ép được kiểu → **không thoả**. Lùi về so chuỗi là cái bẫy im lặng: `"chữ" > "2026-01-01"` đúng theo thứ tự ký tự, và một điều kiện ngày hỏng biến thành thông báo bắn nhầm.

### 4.4. `context.py` (mới) — ngữ cảnh chỉ đọc, NF2

**Lỗ hổng đang có phải đóng trước:** `content.build_context` truyền thẳng `doc` (đối tượng `Document`) vào Jinja, nên mẫu gọi được `doc.db_set(...)`, `doc.delete()`. Khi quyền sửa mẫu được giao cho người không phải Dev thì đây là lỗ hổng thật.

Thiết kế mới:

- `ImmutableSandboxedEnvironment(autoescape=True)` cho thân email; bản `autoescape=False` cho tiêu đề (tiêu đề là văn bản thuần, kết quả đưa qua `strip_html`).
- `doc` trong ngữ cảnh là `doc.as_dict()` — `frappe._dict` thuần, bảng con là `list[dict]`. Không có `Document`, không có `frappe`, không có module nào.
- Biến dựng sẵn (F12): `ten_doi_tac`, `ten_nguoi_tao`, `nguoi_bam_gui`, `so_tien`, `ngay`, `han_thanh_toan`, `so_ngay_con_lai`, `trang_thai`, `ten_cong_ty`, `tien_to`. Giữ **bí danh** cho tên cũ (`prefix`, `party_name`, `owner_name`, `amount`, `date`, `due`, `days_left`) để mẫu đã sửa trên site không gãy.
- Hàm: `truong("fieldname")` — giá trị **đã định dạng** (tiền `1.234.567 ₫`, ngày `dd-mm-yyyy`, Link chỉ hiện tên hiển thị khi DocType đó bật `show_title_field_in_link` — nếu luôn hiện tiêu đề thì cột "Mã vật tư" trong email hoá ra tên hàng, vì Item đặt tên theo mã); `mau("Tên mẫu")` — chèn Mẫu dùng chung; các khối ở 4.5.
- `han_thanh_toan` giữ hành vi D9 hiện có: lấy trường hạn trên chứng từ, không có thì tra sang chứng từ được dẫn chiếu (`reference_doctype`/`reference_name`) — đây là ngữ nghĩa của **biến dựng sẵn**, do code chịu, không phải điều kiện nghiệp vụ.
- `QuietUndefined`: biến lạ render thành chuỗi rỗng khi gửi thật (không chặn nghiệp vụ), nhưng **báo lỗi** khi lưu (V2) và khi xem trước.
- `context.methods_called`: mẫu gọi hàm trên chứng từ (`{{ doc.db_set(...) }}`) bị chặn **hai lớp** — hộp cát không thực thi lúc chạy, và lúc lưu báo rõ "mẫu chỉ được đọc dữ liệu chứng từ, không gọi được hàm db_set()".

**Text Editor và Jinja.** Thân email là `Text Editor` (Quill) cho nghiệp vụ soạn có định dạng. Quill escape `<`, `>`, `&` trong text node, nên `{% if x > 0 %}` bị lưu thành `&gt;`. Trước khi render, `context.unescape_jinja(template)` chạy `html.unescape` **chỉ bên trong** các cặp `{{ … }}` / `{% … %}` (regex trên delimiter), phần HTML còn lại giữ nguyên. Có test riêng cho việc này.

### 4.5. `blocks.py` (mới) — 7 khối dựng sẵn (F13)

| Hàm | Tuỳ chọn người dùng | Phạm vi |
| --- | --- | --- |
| `bang_mat_hang()` | bảng con (`item_table_field`), cột + nhãn + thứ tự (`item_columns`), trần dòng từ Cài đặt, cột STT | cả hai |
| `khoi_so_lieu()` | dòng + nhãn (`fact_rows`), cờ `only_if_previous_empty` | cả hai |
| `dia_chi_giao_hang()` | trường địa chỉ (`address_field`) + trường liên hệ (`contact_field`); hiện địa chỉ, người nhận, điện thoại — xem 4.5.1 | cả hai |
| `chu_ky()` | người tạo hay người bấm gửi (`signature_person`); họ tên – công ty / điện thoại / email | cả hai |
| `khoi_phan_hoi(cau="…")` | câu chữ (CR_02 sẽ thay bằng 2 nút, không phải sửa lại nội dung — R9) | ngoài |
| `nut_mo_chung_tu(nhan="…")` | nhãn | **chỉ nội bộ** |
| `link_bao_cao("Stock Balance", nhan="…")` | báo cáo | **chỉ nội bộ** |

Khối trả `Markup`; ở ngữ cảnh ngoài, hai khối nội bộ **không được nạp vào môi trường** → V4 chặn ngay khi lưu, và nếu lọt thì render rỗng.

#### 4.5.1. `dia_chi_giao_hang` — **sửa D21: không thêm Custom Field vào Address**

Quyết định của PO 23/09/2026 (thay cho D21 của BA): PO và SO **đã** trỏ tới bản ghi `Address` rồi (`shipping_address`, `dispatch_address`, `supplier_address` trên PO; `shipping_address_name`, `customer_address` trên SO) — khối đọc thẳng từ đó, **không** thêm trường mới vào Address. Chưa điền thì để trống, không chặn gửi.

Nguồn lấy dữ liệu, theo thứ tự ưu tiên:

| Dòng | Nguồn |
| --- | --- |
| Địa chỉ | `Address` mà `address_field` trỏ tới → `frappe.get_address_display` (luôn hiện, kể cả khi rỗng) |
| Người nhận | Contact ở `contact_field` trên chứng từ → Contact có `Contact.address` = địa chỉ đó. **Không** lùi về `Address.address_title`: đó là nhãn địa chỉ ("Kho Miyano"), không phải một con người — lấy nhầm thì cảnh báo thiếu dữ liệu không bao giờ bật |
| Điện thoại | `Address.phone` → điện thoại của Contact tìm được ở trên |

Thiếu người nhận thì bỏ dòng người nhận (còn điện thoại thì hiện riêng dòng điện thoại); thiếu cả hai thì email chỉ có dòng địa chỉ — không in nhãn trống. Đồng thời hộp xác nhận của nút Thủ công **cảnh báo rõ** là địa chỉ chưa có người nhận/điện thoại, và báo cáo *"Địa chỉ giao hàng thiếu người nhận/điện thoại"* liệt kê để nghiệp vụ bổ sung (CR_01 mục 4 — việc của anh Hiếu/Xuân, không phải của hệ thống).

Hệ quả: bước B7 **không còn** phần Custom Field, `setup.py` không đụng tới `Address`, và CR_01 AC3 kiểm bằng dữ liệu Address có sẵn.

### 4.6. `content.py` (viết lại)

`render(point, doc, scope, milestone, triggered_by)` → `{subject, body, inapp}`:

1. Dựng ngữ cảnh (4.4) theo `scope` (`internal` / `external`).
2. Tiêu đề = `subject_prefix` + render `subject_template`, qua `strip_html`.
3. Thân = render `body_template` (đã `unescape_jinja`) + chân email từ Snippet trong Cài đặt.
4. Câu in-app = `inapp_template` hoặc tiêu đề.
5. Mẫu hỏng khi **gửi thật** → ghi Error Log, dùng phần render được, không chặn (giữ nguyên tinh thần `_render` hiện tại nhưng không còn fallback về `constants`).

Hai file `templates/internal_email.html`, `external_email.html` **bỏ** — bố cục nay do thân email + khối quyết định. Khối dùng template con riêng trong `templates/blocks/`.

### 4.7. `resolver.py` (mở rộng)

`resolve(point, doc, triggered_by)` → `Recipients(internal_users, internal_emails, external_emails, cc, bcc, reply_to, warnings)`.

- Nội bộ (F8): phòng ban (gồm phòng con — giữ nguyên `expand_departments`) + người cụ thể + **nhóm người nhận** + người tạo + **trường User trên chứng từ** (`user_fields`) + người bấm gửi; trừ Administrator/Guest/khoá/không email/**đã tự tắt điểm này** (`Supply Notification Opt Out`); khử trùng.
- Ngoài (F9) theo thứ tự: `external_email_fields` trên chứng từ → `contact_email` / `email_to` → Contact chính của đối tác → email hồ sơ đối tác → `external_fixed_emails` + nhóm ngoài. Không có → bỏ phần gửi ngoài, ghi `Skipped` kèm lý do; loại **Thủ công** báo ngay trong hộp xác nhận và khoá nút Gửi (AC6).
- F10: email ngoài gửi **tách riêng** khỏi email nội bộ, hai lần `sendmail` khác nhau.

### 4.8. `dispatch.py` (viết lại quanh một hàm gửi)

```python
def send(point, doc, milestone, *, triggered_by=None, force=False, test_to=None) -> str  # tên dòng nhật ký
```

Thứ tự kiểm: Cài đặt `enabled` → điểm `enabled` → chống trùng (`force` bỏ qua — dùng cho *Gửi lại* và loại Thủ công) → **trần email/giờ** (NF3: đếm dòng nhật ký của điểm trong 1 giờ; vượt thì đặt `enabled = 0`, ghi `paused_reason`, báo quản trị, ghi `Skipped`) → dựng người nhận → dựng nội dung → gửi 3 kênh độc lập → ghi nhật ký.

**Chế độ thử (D16):** một hàm bọc duy nhất quanh `frappe.sendmail` — khi `test_mode` bật, mọi `recipients/cc/bcc` thay bằng `test_email`, tiêu đề thêm `[THỬ → <email gốc>]`, nhật ký ghi `test_mode = 1`. In-app vẫn chạy bình thường (chỉ tới người nội bộ, không có rủi ro gửi nhầm đối tác).

**Đính kèm (thẻ 6):** PDF theo mẫu in + tệp đã đính trên chứng từ; `require_pdf` bật mà không tạo được PDF → không gửi, ghi `Failed` với lý do đọc được.

### 4.9. `manual.py` (mới) — loại Thủ công (F5)

- `get_buttons(doctype, docname)` → các điểm Thủ công đang bật, thoả `manual_docstatus` + điều kiện + quyền (role `button_role`, hoặc quyền `write` trên chứng từ — D27), kèm số lần đã gửi và mô tả lần cuối.
- `get_confirmation(point, doctype, docname)` → người nhận, CC, tệp, số lần đã gửi, cảnh báo thiếu dữ liệu, HTML xem trước.
- `send(point, doctype, docname)` — `@frappe.whitelist()`, **kiểm quyền lại ở máy chủ** (AC1: gọi API trực tiếp trên PO nháp/đã huỷ bị từ chối), chạy **đồng bộ** để báo lỗi thẳng cho người bấm (BR1), `force=True` (mỗi lần bấm là một lần gửi — D17).

### 4.10. `preview.py` (mới)

`preview_recipients(point_json, sample_doc)` · `preview_email(point_json, reference)` · `send_test_to_me(point_json)` (chỉ email người đang thao tác, tiêu đề `[THỬ]`, **không** ghi nhật ký nghiệp vụ — AC-11) · `field_options(doctype)` (trường cha + trường bảng con, nhãn tiếng Việt, cho hộp *Chèn trường*) · `workflow_states(doctype)` · `suggest_code()` · `point_stats(point)`.

Nhận `point_json` (giá trị đang có trên form, kể cả chưa lưu) thay vì chỉ tên điểm — xem trước đúng cái người dùng vừa gõ.

### 4.11. `reminders.py` (viết lại)

- Cron đổi từ `0 8 * * *` sang **`0 * * * *`**; hàm `run_hourly()` tự so `now().hour` với `settings.reminder_hour` → đổi giờ nhắc không cần sửa `hooks.py` (D31).
- Quét theo cấu hình: mỗi điểm `Date Reminder` → với mỗi mốc trong `reminder_offsets`, lấy chứng từ có `date_field == today - offset` (mốc `-7` ⇒ hạn sau 7 ngày), `docstatus = 1` nếu chứng từ submittable, cộng bộ lọc từ `conditions.to_filters`, rồi `conditions.match` phần còn lại.
- Không chạy bù mốc đã trôi qua (F4); chống trùng theo mốc do nhật ký lo.
- `clear_old_dispatch_logs()` tách hai hạn: tự động `auto_log_retention_days`, thủ công `manual_log_retention_days` (0 = vĩnh viễn).

### 4.12. `setup.py` (mở rộng, chạy lại được — NF6)

Tạo (nếu thiếu): role *Quản trị thông báo* (**chỉ tạo role, không gán cho tài khoản nào** — quyết định 23/09/2026), bản ghi Cài đặt (chế độ thử **tắt**, ô email thử **để trống** — PO tự điền khi nghiệm thu), phòng ban theo danh mục chuẩn, **Mẫu dùng chung** hạt giống (*Chân email Miyano*, *Quy định giao nhận hàng hoá*, *Hotline*), 13 điểm hạt giống (NTF-01…NTF-13) với `is_seed = 1`, Workspace, hai báo cáo dữ liệu thiếu. **Không đụng tới `Address`** (4.5.1). **Không ghi đè** bản ghi đã có.

---

## 5. Kiểm tra khi lưu (V1–V8) — `supply_notification_point.py`

| # | Kiểm | Thông báo |
| --- | --- | --- |
| V1 | Cú pháp Jinja của 4 ô mẫu (`TemplateSyntaxError` → vị trí) | "Tiêu đề lỗi ở '{{ doc.name ': thiếu dấu }}" |
| V2 | Biến/`truong()` trỏ tới trường không có trên chứng từ; gợi ý bằng `difflib.get_close_matches` | "Trường `supplier_nam` không có trên Đơn mua hàng. Có phải ý bạn là `supplier_name`?" |
| V3 | Điều kiện: trường tồn tại, giá trị nằm trong danh sách chọn (Select/Link) | "Loại yêu cầu không có giá trị 'Mua'. Chọn một trong: Purchase, Material Transfer…" |
| V4 | Nội dung ngoài chứa khối/mẫu nội bộ hoặc chuỗi `/app/`, `get_url_to_form` | "Email gửi NCC/khách không được chứa đường dẫn nội bộ." |
| V5 | Điểm bật mà không kênh nào, hoặc kênh bật mà không nguồn người nhận | "Đã bật email nội bộ nhưng chưa chọn người nhận." |
| V6 | Mẫu in thuộc đúng chứng từ nguồn (đã có) | giữ nguyên |
| V7 | Thiếu tham số theo loại thời điểm | "Chọn trường ngày để nhắc." |
| V8 | Chứng từ nguồn nằm trong danh sách cấm (D19) | "Không đặt thông báo trên Email Queue." |

Cảnh báo **không chặn** (`frappe.msgprint` dải vàng): điểm tự động vừa bật sẽ gửi ở lần kế tiếp · phòng ban chưa có nhân viên gắn `user_id` · đang bật *Chế độ thử* · `Date Reminder` mà scheduler đang tắt.

Xoá điểm (D20): `on_trash` chặn khi `is_seed` hoặc đã có dòng nhật ký — "Điểm đã có lịch sử gửi, hãy tắt thay vì xoá."

---

## 6. Giao diện

| Thành phần | File | Nội dung |
| --- | --- | --- |
| Form điểm | `doctype/supply_notification_point/supply_notification_point.js` | 7 thẻ, dòng hướng dẫn mỗi thẻ, nạp Autocomplete trường/trạng thái theo `reference_doctype`, bảng *Có thể chèn*, nút **Chèn trường / Chèn khối / Chèn mẫu**, 6 nút thanh công cụ, hộp *Bắt đầu từ* khi tạo mới (Trống / Báo nội bộ khi ghi sổ / Nhắc hạn theo ngày / Gửi đối tác bằng nút) |
| Nút Thủ công trên mọi chứng từ | `public/js/utils/supply_notification_manual.js` | `$(document).on("form-refresh", …)`; chỉ gọi máy chủ khi `frappe.boot.supply_notification.manual_doctypes` chứa DocType đó; nhiều điểm → gom vào nút nhóm **"Gửi thông báo"**; hộp xác nhận; dòng chỉ báo *"Đã gửi NCC 2 lần — lần cuối …"* |
| Toast | `public/js/utils/supply_notification_toast.js` | Đọc `sound`, `toast_seconds`, `sound_debounce_seconds` từ `frappe.boot` thay vì hằng số trong JS (AC-13) |
| Boot | `erpnext/startup/boot.py` + `extend_bootinfo` | Bơm `manual_doctypes` + thông số in-app; lấy từ cache của `registry.py` |
| Workspace | `supply_notification/workspace/thong_bao/` | Thẻ số (gửi hôm nay, lỗi 7 ngày, điểm đang bật, đang chế độ thử?), lối tắt Điểm / Nhóm / Mẫu / Cài đặt / Nhật ký / thư chưa gửi, liên kết hướng dẫn |
| Trang hướng dẫn | `supply_notification/page/huong_dan_thong_bao/` | 5 bước tạo điểm, 4 ví dụ hoàn chỉnh, lỗi thường gặp |
| Thông báo của tôi | `supply_notification/page/thong_bao_cua_toi/` | Danh sách điểm mình đang nhận, bật/tắt với điểm `allow_opt_out` |
| Báo cáo dữ liệu thiếu | `supply_notification/report/dia_chi_giao_hang_thieu_nguoi_nhan/`, `.../doi_tac_thieu_email_lien_he/` | Hỗ trợ chuẩn hoá dữ liệu CR_01 mục 4 |

> **Bẫy đã biết (`form-script-browser-cache`):** mọi thay đổi `.js` của DocType chỉ tới trình duyệt khi `modified` của DocType đổi. Patch chuyển đổi kết thúc bằng việc bump `modified` của `Supply Notification Point` và các DocType chứng từ có nút Thủ công; người dùng vẫn cần **Reload** từ menu avatar (không phải Ctrl+Shift+R).

---

## 7. Phi chức năng

| # | Cách đạt |
| --- | --- |
| NF1 | `registry.doctypes_with_points()` một lần đọc cache; DocType không có điểm → thoát trước mọi truy vấn |
| NF2 | `ImmutableSandboxedEnvironment` + ngữ cảnh toàn `dict`; test AC-10 khẳng định `{{ doc.db_set(...) }}` và `{{ frappe }}` không thực thi và chứng từ không đổi |
| NF3 | Trần email/giờ trong `dispatch.send`, tự tạm dừng + báo quản trị |
| NF4 | Mọi nhãn, hướng dẫn, thông báo lỗi tiếng Việt có dấu |
| NF5 | Site không có `hrms`/`Employee` → phần theo phòng ban trả rỗng, không lỗi (đã có, giữ) |
| NF6 | `setup.py` idempotent; cấu hình xuất/nhập bằng Data Export/Import chuẩn (mọi cấu hình là bản ghi DocType thường) |
| BR3 | `track_changes = 1` trên Point, Group, Snippet, Settings; quyền: *Quản trị thông báo* + System Manager có `create/write/delete`, role khác chỉ `read` (AC-17) |
| BR5 | V4 khi lưu + môi trường ngoài không nạp khối nội bộ |

---

## 8. Chuyển đổi 12 điểm và CR_01

### 8.1. Ánh xạ mô hình cũ → mới

| Cũ (`constants.py`) | Mới (dữ liệu của điểm) |
| --- | --- |
| `reference_doctype`, `trigger_event = Submit` | `reference_doctype`, `trigger_event = Submit` |
| `trigger_event = Due Reminder` | `trigger_event = Date Reminder`, `date_field` = `date_field` cũ, `reminder_offsets = -7, -3, -1`, thêm điều kiện `outstanding_amount > 0` |
| `filter_field` + `filter_values` | một dòng `conditions`: `<field>` `Trong danh sách` `<giá trị>` |
| `filter_note` | `notes` |
| `party_field`, `amount_field`, `date_field` | `party_field`, `amount_field`, `main_date_field` |
| `intro_template` + bảng/khối + link + `action_template` | `body_template` ghép đúng thứ tự đang hiển thị: intro → `khoi_so_lieu()` → `bang_mat_hang()` → `nut_mo_chung_tu()` (+ `link_bao_cao("Stock Balance")` nếu `show_stock_report`) → action |
| `_facts()` trong code | `fact_rows`: `<amount_field>` nhãn "Giá trị"/"Số còn nợ" · `han_thanh_toan` "Hạn thanh toán" · `ngay` "Ngày" (cờ `only_if_previous_empty`) · `so_ngay_con_lai` "Còn lại" |
| cột bảng mặt hàng cứng | `item_columns`: Mã vật tư · Tên hàng · Số lượng · ĐVT |
| `external_intro_template` + `external_closing` | `external_body_template` |
| `PREFIX` | `subject_prefix` từng điểm |

### 8.2. Patch `erpnext/patches/v15_0/migrate_supply_notification_v2.py` (post_model_sync)

1. Đọc giá trị cũ bằng SQL thô (cột vẫn còn sau khi gỡ khỏi JSON).
2. Với **mỗi** điểm: chỉ điền trường mới; **không đụng** ô nào mà nghiệp vụ đã sửa khác hạt giống (so với `constants.SEED_POINTS`) — ghép câu chữ đã sửa vào `body_template` theo đúng thứ tự.
3. Đổi `trigger_event` `Due Reminder` → `Date Reminder`; gắn `is_seed = 1` cho NTF-01…NTF-12.
4. NTF-03: **tắt** kênh "Email ra ngoài" (CR_01 R2/R8/AC7), giữ nguyên phần nội bộ cho kho.
5. Tạo NTF-13 (mục 8.3) nếu chưa có.
6. Dọn: bump `modified` của các DocType liên quan, `frappe.clear_cache()`.
7. **Kiểm chứng tự động** (AC-18): với mỗi điểm, render nội dung trước/sau trên cùng chứng từ mẫu và so sánh — chạy trong test `test_migration.py`, không chạy trong patch.

### 8.3. NTF-13 "Đơn mua hàng · Gửi NCC" — CR_01 bằng cấu hình

| Mục | Giá trị |
| --- | --- |
| Chứng từ · thời điểm | `Purchase Order` · `Manual` |
| Nút | Nhãn "Gửi cho NCC", `manual_docstatus = Đã ghi sổ`, `button_role` trống (ai sửa được PO — D27) |
| Điều kiện | `status` `≠` `Closed` (D29: Completed gửi được) |
| Người nhận | Ngoài: đầu mối liên hệ NCC · CC: người tạo · Trả lời về: người tạo |
| Tiêu đề | `[Miyano] Đơn mua hàng {{ doc.name }} – đề nghị xác nhận đơn và thời gian giao hàng` |
| Thân | Lời văn CR_01 mục 3 (đã chỉnh theo D23) + `bang_mat_hang()` (STT, Mã vật tư, Tên hàng, Số lượng, ĐVT, **Ngày cần hàng**) + `dia_chi_giao_hang()` + `khoi_phan_hoi()` + `mau("Quy định giao nhận hàng hoá")` + `chu_ky()` |
| Đính kèm | **Không** (D23) |
| Kênh | Chỉ "Email ra ngoài" |

Phần **code dùng chung** mà CR_01 kéo theo (không có dòng nào riêng cho PO): loại thời điểm Thủ công, CC / Trả lời về, khối `dia_chi_giao_hang` · `chu_ky` · `khoi_phan_hoi`, Custom Field `Address.nguoi_nhan_hang`, dòng chỉ báo "đã gửi" trên chứng từ nguồn.

---

## 9. Chiến lược test (`erpnext/supply_notification/tests/`)

| File | Nội dung |
| --- | --- |
| `test_conditions.py` | 11 toán tử × kiểu trường; bảng con "ít nhất một dòng"; VÀ/HOẶC; `to_filters` |
| `test_context.py` | Hộp cát (AC-10: `db_set`, `frappe`, `__class__`); `truong()` định dạng tiền/ngày/Link; `unescape_jinja`; biến dựng sẵn và bí danh cũ |
| `test_blocks.py` | 7 khối, chọn cột, trần dòng, khối nội bộ vắng mặt ở ngữ cảnh ngoài |
| `test_validation.py` | V1–V8 và các cảnh báo không chặn |
| `test_events.py` (viết lại) | 5 loại thời điểm tự động, `on_change` với `db_set`, thoát sớm khi DocType không có điểm |
| `test_dispatch.py` (mở rộng) | Chống trùng, 3 kênh, chế độ thử (AC-12), trần email (AC-16), gửi lại (AC-15), tách email nội/ngoại (F10) |
| `test_manual.py` | AC1 (API từ chối PO nháp/huỷ), AC5 (2 lần gửi = 2 dòng), AC6 (NCC thiếu email → khoá gửi, không có thư trống) |
| `test_preview.py` | Xem trước người nhận/email, gửi thử (AC-11) |
| `test_reminders.py` (viết lại) | Mốc âm/dương, giờ chạy theo Cài đặt, không chạy bù, chống trùng trong ngày |
| `test_resolver.py` (mở rộng) | Nhóm người nhận (AC-08), trường User trên chứng từ, opt-out (AC-14) |
| `test_migration.py` | AC-18: email trước/sau chuyển đổi giống nhau; AC-20: `grep` mã chạy không còn tên DocType/trường nghiệp vụ |

Ràng buộc môi trường (ghi nhớ `test-env-quirks`, `verify-without-polluting-the-site`): fixture tự dựng và get-or-create (site không có Item/Customer/Supplier); `FrappeTestCase` rollback ở **class scope**; tạo Custom Field trong test **chốt giao dịch**; không kiểm chứng bằng `bench console` trên site thật; một `--module` mỗi lần gọi `bench`; test gửi ngoài luôn chạy với chế độ thử.

---

## 10. Thứ tự build

| Bước | Nội dung | Ra được |
| --- | --- | --- |
| **B1** | `Supply Notification Settings`, `settings.py`, `registry.py`, 4 DocType con mới | nền cấu hình |
| **B2** | `conditions.py` + test | máy điều kiện |
| **B3** | `context.py` (đóng lỗ hổng NF2), `blocks.py`, `content.py` mới + test | máy nội dung |
| **B4** | Dựng lại DocType Point (7 thẻ) + V1–V8 + `resolver.py` mở rộng | cấu hình đầy đủ |
| **B5** | `events.py` (`doc_events["*"]`), `dispatch.py`, `reminders.py`, gỡ nối cứng trong `hooks.py` | bộ máy chung (AC-01…AC-04) |
| **B6** | Patch chuyển đổi + `test_migration.py` | **AC-18, AC-20** — 12 điểm chạy như cũ trên nền mới |
| **B7** | `manual.py`, JS nút Thủ công, khối địa chỉ/chữ ký/phản hồi, Mẫu dùng chung, NTF-13 | **CR_01 AC1–AC8** |
| **B8** | `preview.py`, form JS đầy đủ, chế độ thử, mẫu khởi tạo | AC-06…AC-12 |
| **B9** | Workspace, trang hướng dẫn, *Thông báo của tôi*, opt-out, gửi lại, trần email, thống kê, 2 báo cáo dữ liệu thiếu | AC-13…AC-17, AC-19 |
| **B10** | Chạy toàn bộ `erpnext.supply_notification.tests`, `pre-commit run --files …`, HDSD Word có ảnh chụp thật | nghiệm thu |

Sau mỗi bước chạm DocType JSON: `bench --site miyano migrate`; chạm JS: `bench build --app erpnext`; luôn gọi từ bench root `/home/miyano/frappe-bench`.

---

## 11. Việc cần người quyết trước khi chạm site

| # | Việc | Vì sao phải hỏi |
| --- | --- | --- |
| Q1 | ~~Custom Field `Address.nguoi_nhan_hang` (D21)~~ | **Đã chốt 23/09/2026: không thêm.** Khối địa chỉ đọc từ Address chứng từ đang trỏ tới (4.5.1) |
| Q2 | ~~Bật scheduler~~ | **Đã bật 23/09/2026**, đang tick đều. Hàng đợi lúc bật chỉ có 1 thư tồn tới địa chỉ giả |
| Q2b | Mở `suspend_email_queue` | **Chưa mở** theo quyết định PO 23/09/2026. Đây là **công tắc thứ hai** của site, độc lập với scheduler: `frappe.email.queue.flush` thoát ngay khi `suspend_email_queue = 1`, nên thư chỉ nằm trong hàng đợi. Mở ra là thư đi thật, kể cả thư của app khác (`assetcore`) mà Chế độ thử của tính năng này không chặn được |
| Q3 | ~~Địa chỉ nhận thư của Chế độ thử~~ | **Đã chốt: để trống**, PO tự điền khi nghiệm thu |
| Q4 | ~~Ai được gán role *Quản trị thông báo*~~ | **Đã chốt: chỉ tạo role, không gán ai.** PO tự gán trong Desk |

Không làm nếu không được yêu cầu rõ: thao tác git (tạo nhánh, commit, push), sửa app `mvl_accounting`, gửi email thật tới NCC/khách khi test.

---

## 12. Rủi ro thiết kế và cách xử

| # | Rủi ro | Xử |
| --- | --- | --- |
| T1 | Quill (Text Editor) làm hỏng cú pháp Jinja | `unescape_jinja` chỉ trong delimiter + test riêng; V1 bắt phần còn lại khi lưu |
| T2 | `on_change` bắn nhiều lần trong một giao dịch (nhiều `db_set` liên tiếp) | Chống trùng theo mốc `change:<field>:<giá trị>`; chỉ bắn khi giá trị **thực sự** đổi |
| T3 | `doc_events["*"]` chạy trên mọi DocType, kể cả job nền lớn | Thoát sớm bằng cache; DocType cấm (D19) chặn vòng lặp thư sinh thư |
| T4 | Mẫu do người dùng viết làm chậm/treo job | Jinja hộp cát, trần dòng bảng, khối do code dựng; lỗi mẫu chỉ ghi log |
| T5 | Bỏ `templates/*.html` làm đổi bố cục thư của 12 điểm | `test_migration.py` so sánh nội dung render trước/sau (AC-18) |
| T6 | Người nhận tự tắt điểm bắt buộc | `allow_opt_out` mặc định **tắt**; nhắc hạn (NTF-06/08) không cho tắt (D18) |

---

## 13. Trạng thái build (cập nhật 23/09/2026)

**Đã xong và đã chạy trên site `miyano`** (migrate + build asset + 195 test xanh):

| Bước | Nội dung | Bằng chứng |
| --- | --- | --- |
| B1 | Cài đặt thông báo (Single), `registry` cache, 6 DocType mới | `bench migrate` sạch |
| B2 | `conditions.py` — 11 toán tử, bảng con, VÀ/HOẶC, đẩy lọc xuống SQL | `test_conditions` 17 ✓ |
| B3 | `context.py` (đóng lỗ hổng NF2), `blocks.py` 7 khối, `content.py` | `test_context` 22 ✓ · `test_blocks` 16 ✓ |
| B4 | Form 7 thẻ + V1–V8 + `resolver` mở rộng (nhóm, trường User, CC/BCC, opt-out) | `test_validation` 27 ✓ · `test_resolver` 23 ✓ |
| B5 | `doc_events["*"]`, `dispatch.send` một cửa, nhắc theo giờ cấu hình | `test_events` 15 ✓ · `test_dispatch` 16 ✓ · `test_reminders` 12 ✓ |
| B6 | Patch chuyển đổi 12 điểm + kiểm ranh giới code | `test_migration` 13 ✓ (AC-18, AC-20) |
| B7 | `manual.py`, JS nút Thủ công, NTF-13 cho CR_01 | `test_manual` 15 ✓ (AC1, AC2, AC4, AC5, AC6) |
| B8 | `preview.py`, form JS đầy đủ, chế độ thử, gửi thử | `test_preview` 12 ✓ (AC-11, AC-12) |
| B9 | Workspace, 2 trang Desk, opt-out, gửi lại, trần thư, 2 báo cáo dữ liệu thiếu | `test_my_notifications` 7 ✓ · 2 test báo cáo ✓ |

Gate chất lượng: `pre-commit run --files …` **Passed** toàn bộ (ruff + prettier + eslint);
`python3 -m scripts.file_structure --audit` → **0 vi phạm / 5066 file**.

**Khác với thiết kế ban đầu, đã ghi lại vì có lý do:**

1. **Không thêm Custom Field vào `Address`** (mục 4.5.1) — quyết định PO 23/09/2026.
2. **Tên người nhận chỉ lấy từ Liên hệ**, không lấy `address_title`: lấy nhãn địa chỉ làm tên
   người thì email ghi "Người nhận: Kho Miyano" và cảnh báo thiếu dữ liệu không bao giờ bật.
3. **Link hiện tên hiển thị chỉ khi DocType bật `show_title_field_in_link`** — nếu không, cột
   "Mã vật tư" trong email hoá ra tên hàng (Item đặt tên theo mã).
4. **"Trường thay đổi" bỏ qua trống → 0**: ghi sổ điền 0 vào hàng loạt trường số, so thô sẽ
   bắn thông báo cho những trường chưa ai đụng tới.
5. **Điều kiện ngày không ép được kiểu thì coi là KHÔNG thoả**: `"chữ" > "2026-01-01"` đúng theo
   thứ tự ký tự — một điều kiện hỏng sẽ lặng lẽ bắn nhầm.
6. **Mốc (`milestone`) bỏ giới hạn 16 ký tự**: mốc `change:<trường>:<giá trị>` dài hơn, và giới
   hạn cũ làm mọi lần bắn "Trường thay đổi" chết trong im lặng.

**Còn lại (cần người thật, không code được tiếp):**

| # | Việc | Ai |
| --- | --- | --- |
| 1 | AC-19: một người nghiệp vụ mới đọc trang hướng dẫn rồi tự tạo điểm ≤ 30 phút | BA + một người dùng thật |
| 2 | AC3 / AC8 của CR_01: chạy thật với ít nhất một NCC, kiểm địa chỉ giao kho và giao thẳng khách | Xuân, anh Hiếu |
| 3 | Chuẩn hoá dữ liệu: liên hệ NCC có email, địa chỉ giao có người nhận + điện thoại (dùng 2 báo cáo mới) | anh Hiếu, Xuân |
| 4 | Bật scheduler sau khi đã bật **Chế độ thử** và dọn Email Queue tồn (RK1) | PO quyết, Dev thực hiện |
| 5 | Điền *Email nhận thư thử* trong Cài đặt thông báo; gán role *Quản trị thông báo* | PO |
| 6 | HDSD bản Word có ảnh chụp thật (theo tiền lệ HDSD Warehouse Operations) | BA, sau khi nghiệm thu giao diện |
