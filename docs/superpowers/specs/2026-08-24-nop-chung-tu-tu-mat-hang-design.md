# Nộp chứng từ từ mặt hàng, và tra cứu theo số hiệu

> Trạng thái: **ĐÃ DUYỆT 2026-08-24.** Ba điểm ở §9 đã chốt, xem bên dưới.
> Bổ sung cho: `docs/superpowers/specs/2026-08-20-ho-so-phap-ly-tbyt-design.md`
> Nguồn yêu cầu: người dùng, sau khi dùng thử form thật (2026-08-24).

## 1. Vấn đề, bằng lời người dùng

> *"Bình thường khi tạo item tôi sẽ tải lên bộ tài liệu của item đó luôn (tôi đã có số hiệu để
> kiểm tra tài liệu đó có chưa rồi), nhưng khi tài liệu có rồi và tôi muốn gắn tài liệu đó cho
> item thì lại phải vào tài liệu rồi tìm số lưu hành của item đó mới gắn được."*

Hai câu, hai vấn đề khác nhau, và một hiểu nhầm do hệ thống không nói rõ.

## 2. Lệch pha: công việc xoay quanh mặt hàng, mô hình xoay quanh chủ thể

Người dùng đứng ở phía **mặt hàng**: họ đang tạo mã hàng, cầm trong tay tập giấy tờ của mã hàng đó.

Mô hình xoay quanh **chủ thể pháp lý**: giấy tờ gắn vào công ty, chủ sở hữu, số lưu hành hoặc lô.

**Cả hai đều đúng.** Mô hình xoay quanh chủ thể chính là thứ mua được tính không-trùng-lặp — bỏ nó
là quay về §5.5 của tài liệu gốc với mọi hệ quả đã phân tích. Vấn đề không nằm ở mô hình, mà nằm ở
**đường vào**: mọi cánh cửa hiện có đều mang hình dạng chủ thể, trong khi người dùng đứng ở phía
mặt hàng.

### Hiện trạng, đo được

- `erpnext/stock/doctype/item/item.js` — **không một chỗ nào** mở `TBYT Regulatory Document`.
  Bảng hồ sơ trên tab *Hồ sơ TBYT* chỉ để **đọc**: nó hiện "Chưa có" cho từng tờ thiếu rồi dừng.
- `so_hieu` trên `TBYT Regulatory Document` là ô `Data` trần — không `unique`, không
  `search_index`, không `in_standard_filter`. Người dùng coi nó là khóa nhận dạng; hệ thống coi nó
  là nhãn hiển thị.

## 3. Phát hiện then chốt: "gắn tờ đã có" chỉ áp dụng cho 4 trên 23 loại

Đây là kết quả phân tích quan trọng nhất, và nó định hình toàn bộ tính năng.

Với **19 loại chỉ cho một phạm vi**, phép "gắn tờ đã có vào mặt hàng này" **không tồn tại về mặt
logic**:

| Tình huống | Thực tế |
|---|---|
| Tờ giấy đã gắn vào đúng chủ thể trong chuỗi của mặt hàng | Mặt hàng **đã có** tờ đó rồi — không có việc gì để làm |
| Tờ giấy gắn vào chủ thể khác | Muốn phủ thêm thì cần dòng phạm vi thứ hai, mà loại này cấm. **Mặt hàng cần một tờ giấy khác**, không phải tờ này |

Ví dụ: `thong_tin_bao_hanh` gắn vào hãng Nipro. Mặt hàng thuộc hãng Terumo không thể "mượn" tờ đó —
nó cần thông tin bảo hành của chính Terumo. Đó là hai tờ giấy khác nhau ngoài đời.

Chỉ **4 loại** cho phép nhiều phạm vi, và cả bốn đều ở cấp Số lưu hành:

- `cfs_giay_luu_hanh`
- `giay_uy_quyen_csh`
- `giay_xac_nhan_bao_hanh`
- `uy_quyen_nhap_khau`

Bốn tờ này do chủ sở hữu cấp nhưng **liệt kê theo sản phẩm** — một tờ CFS thật thường ghi tên nhiều
model. Với chúng, "gắn tờ đã có cho mặt hàng này" là thao tác có thật và có nghĩa.

**Hệ quả thiết kế:** nút "gắn tờ đã có" chỉ được hiện cho 4 loại đó. Với 19 loại còn lại, hiện nút
ấy là mời người dùng làm một việc hệ thống sẽ từ chối — tệ hơn là không có nút.

## 4. Vậy tra cứu số hiệu để làm gì với 19 loại kia

Vẫn rất có giá trị, nhưng cho **mục đích khác**: chặn trùng ngay tại chỗ nhập.

Khi người dùng gõ một số hiệu đã tồn tại, hệ thống nói ngay tờ đó đang nằm ở đâu. Người dùng tự
quyết:

- **Cùng một tờ giấy, ghi nhầm lần hai** → dừng lại, không tạo bản ghi thừa.
- **Đúng là hai tờ khác nhau trùng số** → tiếp tục, hiếm nhưng có.
- **Cùng một tờ nhưng phủ hai chủ thể** → dấu hiệu loại chứng từ đó **đáng lẽ phải được đánh dấu
  cho phép nhiều phạm vi**. Hệ thống nêu khả năng này để người dùng báo quản trị, không tự sửa.

Hiện tại việc chặn trùng chỉ xảy ra **lúc bấm Lưu**, và chỉ theo cặp (loại, phạm vi) — không theo
số hiệu. Tra cứu số hiệu đẩy phát hiện lên sớm hơn một bước, đúng lúc người dùng còn đang nghĩ về
tờ giấy trong tay.

## 5. Thiết kế

### 5.1. Một cửa vào duy nhất: nút trên từng dòng thiếu

Trong bảng hồ sơ trên tab *Hồ sơ TBYT*, mỗi dòng chưa có chứng từ được thêm một nút **Nộp giấy**.

Bấm vào mở một hộp thoại, không rời khỏi form Item.

### 5.2. Hộp thoại "Nộp chứng từ"

**Dòng đầu tiên, luôn hiện — đây là phần dạy mô hình:**

> Tờ này sẽ gắn vào: **hãng Nipro**
> Mọi mặt hàng của hãng này đều dùng chung.

Câu đó đổi theo cấp phạm vi của loại chứng từ:

| Cấp | Câu hiện ra |
|---|---|
| Company | Gắn vào **Công ty Miyano** — mọi mặt hàng TBYT đều dùng chung |
| Owner | Gắn vào **hãng {tên}** — mọi mặt hàng của hãng đều dùng chung |
| Authorization | Gắn vào **số lưu hành {số}** — mọi mặt hàng cùng số này đều dùng chung |
| Item | Gắn vào **chính mặt hàng này** |

Đây là chỗ người dùng làm điều tự nhiên (nộp giấy cho mặt hàng) trong khi hệ thống làm điều đúng
(gắn vào đúng cấp) — và giải thích vì sao. Không có câu này, thao tác đúng vẫn gây hoang mang.

**Các trường:**

| Trường | Ghi chú |
|---|---|
| Số hiệu | Gõ tới đâu tra tới đó — xem §5.3 |
| Ngày cấp | Bắt buộc |
| Vô thời hạn | Check; bỏ tích thì Ngày hết hạn thành bắt buộc |
| Ngày hết hạn | Hiện khi không tích Vô thời hạn |
| Tệp | Attach, bắt buộc |

**Hai nút:**

- **Tạo mới** — tạo bản ghi ngay trong hộp thoại, đóng lại, làm mới bảng hồ sơ.
- **Mở biểu mẫu đầy đủ** — cho các ca hiếm cần trường mà hộp thoại không có (ví dụ khai
  *Thay thế cho* khi gia hạn). Mở form đã điền sẵn loại chứng từ, phạm vi và những gì đã gõ.

### 5.3. Tra cứu theo số hiệu

Người dùng gõ số hiệu → hệ thống tìm trong các chứng từ **đang hiệu lực** có số hiệu khớp.

**Nếu không thấy:** không hiện gì thêm. Người dùng nộp bình thường.

**Nếu thấy**, hiện một khối kết quả dưới ô Số hiệu:

> **Số hiệu này đã có trong hệ thống**
> `TBYT-CT-2026-00007` · Giấy chứng nhận lưu hành tự do (CFS) · gắn vào 3 số lưu hành · Còn hiệu lực

Kèm hành động, tuỳ loại:

| Loại chứng từ | Hành động |
|---|---|
| Cho phép nhiều phạm vi (4 loại) | Nút **Gắn tờ này cho mặt hàng** — thêm một dòng phạm vi vào bản ghi cũ |
| Chỉ một phạm vi (19 loại) | Không có nút. Hiện dòng nhắc: *"Loại này chỉ nhận một phạm vi. Nếu đây đúng là cùng một tờ giấy phủ nhiều chủ thể, báo quản trị xem loại chứng từ có cần cho phép nhiều phạm vi không."* |

### 5.4. Ba trường hợp bị chặn, và cách nói cho người dùng

Thao tác "gắn tờ này cho mặt hàng" đi qua đúng bộ kiểm tra đã có ở Task 6. Hộp thoại phải **kiểm
trước và nói bằng tiếng người**, thay vì để người dùng đâm vào lỗi thô:

| Ràng buộc đã có | Khi nào vi phạm | Hộp thoại nói gì |
|---|---|---|
| `_validate_scope_count` | Loại chỉ một phạm vi | Không hiện nút gắn (§5.3) |
| `_validate_single_owner` | Số lưu hành của mặt hàng thuộc hãng khác với các phạm vi đang có | *"Tờ này đang gắn cho các số lưu hành của hãng {A}. Mặt hàng này thuộc hãng {B}, không gắn chung được."* |
| `_validate_no_duplicate_scope` | Số lưu hành này đã có một tờ cùng loại đang hiệu lực | *"Số lưu hành này đã có {tên chứng từ} đang hiệu lực: {mã}. Nếu tờ mới thay thế tờ cũ, dùng biểu mẫu đầy đủ và khai ô Thay thế cho."* |

### 5.5. Suy ra chủ thể đích từ mặt hàng

Hàm suy: `(mặt hàng, loại chứng từ) → chủ thể phải gắn vào`.

| Cấp của loại chứng từ | Chủ thể |
|---|---|
| Company | Công ty mặc định |
| Owner | `chu_so_huu` của số lưu hành mà mặt hàng trỏ tới |
| Authorization | `so_luu_hanh` của mặt hàng |
| Item | Chính mặt hàng |
| Batch | **Không suy được** — xem dưới |

**Cấp Lô nằm ngoài phạm vi tính năng này.** Từ một mặt hàng không suy ra được lô nào, vì mặt hàng
có thể có nhiều lô. Chứng từ cấp lô vốn đã không nằm trong bảng hồ sơ của Item (`ITEM_SCOPES` loại
chúng ra), nên không có dòng nào để bấm — nhất quán, không cần xử lý thêm.

### 5.6. `so_hieu` thành khóa làm việc

Hiện là ô Data trần. Cần:

- `search_index: 1` — để tra cứu không quét toàn bảng khi danh mục lớn
- `in_standard_filter: 1` — để lọc được ngay trên danh sách chứng từ

**Không đặt `unique`.** Hai tờ giấy khác loại có thể trùng số hiệu một cách chính đáng, và nhiều tờ
không có số hiệu. Trùng lặp thật đã được `_validate_no_duplicate_scope` chặn theo cặp (loại, phạm
vi) — đó mới là định nghĩa đúng của "trùng", không phải số hiệu.

## 6. Giao diện phía sau

Ba hàm whitelist mới trên `erpnext/tbyt/status.py` hoặc một module mới `erpnext/tbyt/intake.py`
(chọn khi lập kế hoạch):

```python
get_intake_context(item_code, document_key) -> dict
	# chủ thể đích, tên hiển thị của nó, câu giải thích, loại có cho nhiều phạm vi không

find_documents_by_so_hieu(so_hieu, document_key=None) -> list[dict]
	# các chứng từ đang hiệu lực khớp số hiệu, kèm loại, tóm tắt phạm vi, trạng thái

attach_existing_to_item(item_code, document_name) -> None
	# thêm một dòng phạm vi trỏ đúng chủ thể; để validate cưỡng chế các ràng buộc
```

Việc tạo bản ghi mới dùng luôn `frappe.client.insert` chuẩn của Frappe với payload dựng từ hộp
thoại — không cần hàm riêng, và giữ nguyên mọi kiểm tra ở controller.

**Quyền:** cả ba hàm kiểm `frappe.has_permission("Item", doc=item_code, throw=True)`;
`attach_existing_to_item` kiểm thêm quyền ghi trên `TBYT Regulatory Document`.

## 7. Cố ý không làm

- **Không cho gắn giấy thẳng vào mặt hàng** cho các loại vốn thuộc cấp cao hơn. Nộp *từ* mặt hàng
  không có nghĩa là gắn *vào* mặt hàng. Làm khác đi là dựng lại chính vấn đề trùng lặp mà cả thiết
  kế sinh ra để tránh.
- **Không đặt `unique` cho số hiệu** — lý do ở §5.6.
- **Không tự sửa cờ `cho_phep_nhieu_pham_vi`** khi phát hiện số hiệu trùng ở loại một-phạm-vi. Chỉ
  nêu khả năng cho người dùng báo quản trị. Đó là quyết định về danh mục pháp lý, không phải việc
  hệ thống tự làm.
- **Không đụng cấp Lô** — §5.5.

## 8. Kiểm thử

| Ca | Nội dung |
|---|---|
| Suy chủ thể | Bốn cấp Company/Owner/Authorization/Item suy đúng từ một mặt hàng; cấp Batch trả về rỗng |
| Câu giải thích | Mỗi cấp sinh đúng câu, có tên chủ thể thật |
| Tra số hiệu — không thấy | Trả danh sách rỗng, không lỗi |
| Tra số hiệu — thấy | Trả đúng bản ghi, kèm tóm tắt phạm vi; **khẳng định theo tên bản ghi cụ thể**, không theo số đếm toàn cục |
| Gắn tờ đã có — thành công | Loại nhiều phạm vi, cùng hãng, chưa trùng → thêm được dòng, mặt hàng chuyển sang đã có |
| Gắn tờ đã có — chặn vì loại một phạm vi | Ném lỗi, thông điệp nêu rõ loại chỉ nhận một phạm vi |
| Gắn tờ đã có — chặn vì khác hãng | Ném lỗi, thông điệp nêu tên cả hai hãng |
| Gắn tờ đã có — chặn vì đã có tờ cùng loại | Ném lỗi, thông điệp nêu mã bản ghi đang giữ chỗ |
| Quyền | Người không có quyền đọc Item bị chặn ở cả ba hàm |
| Thừa hưởng | Nộp một tờ cấp Chủ sở hữu từ mặt hàng A → mặt hàng B cùng hãng cũng có ngay |

Ca cuối là ca quan trọng nhất: nó chứng minh nộp *từ* mặt hàng vẫn giữ nguyên tính thừa hưởng, tức
là tiện lợi mới không đánh đổi bằng nguyên tắc cũ.

## 9. Ba điểm đã chốt (2026-08-24)

**9.1 — Lưu ngay, không giữ nháp.** Hộp thoại tạo và lưu bản ghi chứng từ **ngay khi bấm**, không
giữ trạng thái trung gian. Lý do người dùng nêu: tránh mất dữ liệu nếu trang bị nạp lại.

Kèm theo một ràng buộc bắt buộc: **không được gọi `frm.reload_doc()` sau khi nộp.** Mặt hàng có thể
đang có thay đổi chưa lưu, và nạp lại sẽ xoá mất. Thay vào đó, sau khi tạo xong chỉ cập nhật **tại
chỗ** đúng hai thứ đã đổi:

- trường `tinh_trang_ho_so` — gán thẳng vào `frm.doc` rồi `refresh_field`, **không** dùng
  `frm.set_value` (nó sẽ đánh dấu form là dirty trong khi người dùng không sửa gì)
- bảng hồ sơ HTML — gọi lại `get_item_dashboard` và vẽ lại

Hai hàm tạo và gắn đều trả về `tinh_trang_ho_so` mới để client cập nhật mà không cần hỏi lại.

**9.2 — Chỉ BB và BB\*.** Nút *Nộp giấy* chỉ hiện trên dòng đang **bị đòi**: mức `BB`, và mức
`BB*` khi điều kiện thoả. Dòng `NC` và `TH` không có nút — chúng không phải nghĩa vụ, và thêm nút ở
đó chỉ làm loãng chỗ cần chú ý.

**9.3 — Tra ngay khi gõ, vừa tra vừa nhập.** Tra cứu số hiệu chạy **trong lúc gõ**, không đợi rời ô.
Người dùng chấp nhận chi phí truy vấn: danh mục chứng từ không lớn, và có `search_index` trên
`so_hieu` thì tra theo số hiệu rất nhanh.

Chống dội truy vấn bằng `frappe.utils.debounce` khoảng 300 ms và bỏ qua chuỗi ngắn hơn 3 ký tự.
