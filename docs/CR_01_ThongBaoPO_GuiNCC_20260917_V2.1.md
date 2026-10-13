# CR_01 – Gửi email và thông báo Đơn mua hàng (PO) cho Nhà cung cấp

| Thông tin | Nội dung |
|---|---|
| Mã tài liệu | CR_01 (thay thế CR-NTF03-01 v1.1) |
| Phiên bản | V2.1 – 17/09/2026 |
| Loại | Yêu cầu thay đổi – Change Request (mức nghiệp vụ, do BA/PO lập) |
| Thành phần | SupplyCore – phân hệ Mua hàng (Buying) |
| Giai đoạn SPD | Supply – Cung ứng (bước PO → nhận hàng) |
| Tài liệu liên quan | SRS_06 Buying delta; Spec 05 “Thông báo chuỗi cung ứng” v2.1 – điểm thông báo NTF-03 (bước 3) |
| Người yêu cầu | Tạ Trường Xuân – Product Owner, đại diện kho |
| Dev tiếp nhận / phụ trách | **Hiếu bé** (Dev) – tự chọn giải pháp kỹ thuật |
| CR liên quan | CR_02 – Nút Xác nhận / Từ chối PO ngay trong email (tách riêng, làm sau CR_01) |
| Trạng thái | Chờ xếp vào sprint |

**Lịch sử thay đổi**

| Phiên bản | Ngày | Nội dung |
|---|---|---|
| V1.0 | 10/09/2026 | Bản đầu: bổ sung địa chỉ giao hàng, người nhận, đề nghị xác nhận đơn và quy định báo trước 60 phút vào email PO gửi NCC |
| V1.1 | 10/09/2026 | Địa chỉ và người nhận lấy theo Địa chỉ giao hàng trên PO; chữ ký theo người tạo PO |
| V2.0 | 17/09/2026 | Viết lại ở góc độ nghiệp vụ, bỏ phần hướng dẫn kỹ thuật (Dev tự quyết); thêm thời điểm gửi = khi người phụ trách mua hàng xác nhận gửi; thêm yêu cầu NCC kèm PO của Miyano trong bộ chứng từ giao hàng |
| V2.1 | 17/09/2026 | Dev phụ trách: Hiếu bé; tách yêu cầu “2 nút Xác nhận / Từ chối PO trong email” thành CR_02 riêng, CR_01 chỉ chừa chỗ và ghi phụ thuộc |

---

## 1. Mục đích

Khi Miyano phát hành Đơn mua hàng – Purchase Order (PO), Nhà cung cấp (NCC) cần nhận được một email và thông báo có đủ thông tin để giao hàng đúng nơi, đúng người, đúng cách: địa chỉ giao, người nhận, đề nghị xác nhận đơn và lịch giao, quy định báo trước 60 phút, và yêu cầu **kèm PO của Miyano trong bộ chứng từ giao hàng**.

Yêu cầu cuối cùng nhằm giúp bộ phận nhận hàng của Miyano xác định ngay hàng giao thuộc PO nào, số PO là gì, để lập Phiếu tiếp nhận hàng mua – Purchase Receipt (PR) từ đúng PO, không phải tra cứu hay hỏi lại.

## 2. Yêu cầu nghiệp vụ

**User story**

> Là *người phụ trách mua hàng*, sau khi tạo xong PO tôi muốn **xác nhận gửi** để hệ thống gửi email và thông báo cho NCC với nội dung chuẩn (mục 3), để NCC xác nhận đơn, giao đúng địa chỉ/người nhận, báo trước khi giao và mang theo PO khi giao hàng.

**Luồng nghiệp vụ**

| Bước | Ai | Việc | Kết quả |
|---|---|---|---|
| 1 | Người phụ trách mua hàng | Tạo PO, chọn NCC, mặt hàng, ngày cần hàng và **Địa chỉ giao hàng** (kho Miyano hoặc địa chỉ giao thẳng khách) | PO hoàn chỉnh, đã duyệt theo quy trình hiện hành |
| 2 | Người phụ trách mua hàng | **Xác nhận gửi** email cho NCC ngay trên PO | Hệ thống gửi email + thông báo cho đầu mối liên hệ của NCC; đính kèm PO |
| 3 | Hệ thống | Ghi nhận trên PO: đã gửi cho ai, lúc nào, bởi ai | Người mua hàng và kho nhìn thấy PO đã được gửi hay chưa |
| 4 | NCC | Trả lời xác nhận đơn và thời gian giao dự kiến (giai đoạn CR_01: trả lời email; khi có CR_02: bấm nút Xác nhận / Từ chối ngay trong email) | Phản hồi về thẳng người tạo PO; với CR_02 trạng thái cập nhật trên PO |
| 5 | NCC | Báo trước ≥ 60 phút; giao hàng kèm Phiếu giao hàng/Biên bản bàn giao **và PO của Miyano** | Kho nhận hàng, đối chiếu theo số PO, lập Purchase Receipt từ PO |

**Quy tắc nghiệp vụ**

| # | Quy tắc |
|---|---|
| R1 | Email chỉ được gửi từ PO đã hoàn tất duyệt; không gửi từ PO nháp hoặc đã hủy. |
| R2 | Gửi khi người phụ trách mua hàng **chủ động xác nhận gửi**, không tự động gửi ngay khi ghi sổ. Có thể gửi lại (ví dụ sửa đơn) – hệ thống lưu lịch sử các lần gửi. |
| R3 | Người nhận email = đầu mối liên hệ của NCC trên PO (email; kèm số di động nếu có thông báo kênh khác). Người tạo PO được đồng gửi để theo dõi phản hồi. |
| R4 | Địa chỉ giao hàng, tên người nhận, số điện thoại người nhận **lấy theo Địa chỉ giao hàng chọn trên PO** – không cố định trong mẫu. PO giao kho Miyano hay giao thẳng khách đều đúng địa chỉ. |
| R5 | Chữ ký cuối email = họ tên, điện thoại, email của **người tạo PO**. |
| R6 | Email đính kèm bản in PO (PDF) theo mẫu đang gửi NCC. |
| R7 | Email gửi NCC không chứa đường dẫn nội bộ của hệ thống. |
| R8 | Thông báo nội bộ cho kho (bước 3 trong Spec 05) giữ nguyên, tách riêng khỏi email gửi NCC. |
| R9 | Bố cục email chừa sẵn một khối “Phản hồi của Quý đối tác” ngay dưới câu đề nghị xác nhận; ở CR_01 khối này chỉ là câu chữ (trả lời email), CR_02 sẽ đặt 2 nút vào đúng vị trí đó mà không phải sửa lại nội dung. |

## 3. Nội dung email và thông báo gửi Nhà cung cấp

Phần trong ⟨ ⟩ là thông tin hệ thống tự điền theo từng PO. Lời văn dưới đây là lời văn chính thức, không sửa khi triển khai.

**Tiêu đề:** [Miyano] Đơn mua hàng ⟨số PO⟩ – đề nghị xác nhận đơn và thời gian giao hàng

**Nội dung:**

> Kính gửi Quý đối tác ⟨tên nhà cung cấp⟩,
>
> Công ty TNHH Miyano Việt Nam trân trọng gửi Quý đối tác Đơn mua hàng số ⟨số PO⟩ ngày ⟨ngày đặt hàng⟩ (chi tiết đính kèm và liệt kê dưới đây).
>
> ⟨Bảng mặt hàng: STT | Mã vật tư | Tên hàng | Số lượng | Đơn vị tính | Ngày cần hàng⟩
>
> **Địa chỉ giao hàng:** ⟨địa chỉ giao hàng trên PO⟩
> **Người nhận:** ⟨tên người nhận⟩ – ⟨điện thoại người nhận⟩
>
> Quý đối tác xin vui lòng xác nhận đơn hàng và chia sẻ thời gian giao hàng dự kiến.
>
> *(Vị trí dành cho CR_02: hai nút **Xác nhận đơn hàng** / **Từ chối đơn hàng** – chưa có ở CR_01; NCC trả lời email này để xác nhận.)*
>
> Để công tác phối hợp giao nhận hàng hóa diễn ra thuận lợi và hiệu quả, Công ty TNHH Miyano Việt Nam xin phép đề nghị Quý đối tác lưu ý một số nội dung sau:
>
> - **Thời gian thông báo:** Quý đối tác vui lòng thông báo trước cho chúng tôi tối thiểu 60 phút trước thời điểm giao hàng dự kiến.
> - **Mục đích:** Việc này giúp chúng tôi chủ động bố trí nhân sự và không gian để tiếp nhận hàng hóa một cách nhanh chóng nhất.
> - **Lưu ý quan trọng:** Trong trường hợp không nhận được thông tin báo trước theo thời gian nêu trên, chúng tôi rất tiếc không thể đảm bảo có nhân sự túc trực để nhận hàng tại thời điểm giao hàng phát sinh.
> - **Chứng từ khi giao hàng:** Khi giao hàng, Quý đối tác vui lòng cung cấp kèm theo Phiếu giao hàng / Biên bản bàn giao hàng hóa **bản Đơn mua hàng (PO) của Miyano** (bản in đính kèm email này). Việc này giúp bộ phận nhận hàng của chúng tôi xác định đúng hàng giao thuộc đơn nào để tiếp nhận và đối chiếu nhanh chóng, chính xác.
>
> Chúng tôi rất mong nhận được sự hợp tác và hỗ trợ từ Quý đối tác để đảm bảo tiến độ công việc chung.
>
> Trân trọng,
> ⟨họ tên người tạo PO⟩ – Công ty TNHH Miyano Việt Nam
> Điện thoại: ⟨điện thoại người tạo PO⟩ | Email: ⟨email người tạo PO⟩

**Thông báo kênh khác (SMS / portal, nếu đã bật theo Spec 05):** nội dung rút gọn, cùng ý: số PO, đề nghị xác nhận, báo trước 60 phút, mang theo PO khi giao; số liên hệ = điện thoại người nhận hàng trên PO. Ví dụ (không dấu): *MIYANO: Don mua hang ⟨số PO⟩ da phat hanh. Vui long xac nhan don, bao truoc 60p va mang theo PO khi giao. LH: ⟨điện thoại người nhận⟩*.

## 4. Dữ liệu cần chuẩn hóa trước khi dùng

| Dữ liệu | Yêu cầu | Người phụ trách |
|---|---|---|
| Địa chỉ giao hàng “Kho Miyano” | Có địa chỉ đầy đủ, tên người nhận hàng và số điện thoại; đặt làm địa chỉ giao mặc định khi tạo PO | Xuân |
| Địa chỉ giao thẳng khách hàng | Địa chỉ giao của từng khách có tên người nhận + số điện thoại | Anh Hiếu (mua hàng/bán hàng) |
| Đầu mối liên hệ NCC | Mỗi NCC có liên hệ chính với email (và số di động) | Anh Hiếu |
| Hồ sơ người tạo PO | Họ tên, số điện thoại trên tài khoản người dùng | Từng người dùng |

## 5. Tiêu chí nghiệm thu – Acceptance Criteria

- [ ] AC1. Trên PO đã duyệt có thao tác “Gửi cho NCC”; PO nháp hoặc đã hủy không gửi được.
- [ ] AC2. Sau khi xác nhận gửi, NCC nhận email trong vòng 2 phút với đúng tiêu đề, đủ nội dung mục 3 (kể cả đoạn yêu cầu kèm PO khi giao hàng), đúng bảng mặt hàng, có PDF PO đính kèm, không có đường dẫn nội bộ.
- [ ] AC3. Địa chỉ, tên và điện thoại người nhận trong email khớp với Địa chỉ giao hàng chọn trên PO; đổi địa chỉ trên PO thì email đổi theo (kiểm tra 1 PO giao kho Miyano, 1 PO giao thẳng khách).
- [ ] AC4. Chữ ký email hiển thị đúng người tạo PO (kiểm tra với 2 người tạo khác nhau); NCC bấm trả lời thì email về người tạo PO.
- [ ] AC5. PO hiển thị được lịch sử gửi (ai gửi, lúc nào, gửi tới email nào); gửi lại lần 2 vẫn ghi nhận.
- [ ] AC6. NCC thiếu email liên hệ → hệ thống báo rõ cho người gửi, không gửi trống, không lỗi PO.
- [ ] AC7. Thông báo nội bộ cho kho vẫn hoạt động như trước và không bị gửi nhầm sang NCC.
- [ ] AC8. Chạy thật với tối thiểu 1 NCC: NCC xác nhận đơn qua email và giao hàng có kèm PO; kho lập Purchase Receipt từ đúng PO đó.

## 6. Phạm vi và lưu ý

| Hạng mục | Nội dung |
|---|---|
| Trong phạm vi | Email + thông báo gửi NCC khi phát hành PO; lịch sử gửi trên PO; dữ liệu địa chỉ giao hàng/người nhận. |
| Ngoài phạm vi | Nút Xác nhận / Từ chối PO trong email và cập nhật trạng thái về ERP (**CR_02**); xác nhận PO trên Supplier Portal (SRS_08, GĐ2); SMS brandname (theo tiến độ Spec 05); thay đổi mẫu in PO. |
| Để Dev quyết định | Cách triển khai kỹ thuật (cấu hình chuẩn hay customize), cách lưu tên/điện thoại người nhận trên địa chỉ, cách ghi lịch sử gửi. Dev trình bày phương án tại sprint planning; ưu tiên cấu hình chuẩn ERPNext theo nguyên tắc dự án. |
| Rủi ro nghiệp vụ | NCC vẫn giao không kèm PO → kho vẫn phải tra cứu; giảm thiểu bằng nhắc lại trong SMS và đối chiếu định kỳ với NCC hay vi phạm. Người tạo PO chọn sai địa chỉ giao → email sai theo; giảm thiểu bằng địa chỉ mặc định là kho Miyano. |

## 7. Phê duyệt

| Vai trò | Họ tên | Ngày | Ý kiến |
|---|---|---|---|
| Người yêu cầu (PO / kho) | Tạ Trường Xuân | 17/09/2026 | |
| Người dùng mua hàng | Anh Hiếu | | |
| Dev tiếp nhận | Hiếu bé | | |
| Nghiệm thu | Tạ Trường Xuân | | |
