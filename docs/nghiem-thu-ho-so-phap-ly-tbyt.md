# Nghiệm thu hồ sơ pháp lý TBYT

> **Chạy trên:** site `miyano`, nhánh `feat/vn-tbyt-ho-so-phap-ly`
> **Thời lượng:** 45–60 phút · **34 ca** · làm tuần tự, phần sau dùng dữ liệu phần trước
> **Điểm xuất phát:** site trống — 0 chủ sở hữu, 0 số lưu hành, 0 chứng từ

---

## 1. Đọc cột kết quả trước khi bắt đầu

Trong tính năng này, **có những lần "đạt" trông hệt như "hỏng"**. Hệ thống từ chối lưu có thể là
đúng; báo đỏ mà vẫn lưu được cũng có thể là đúng. Mỗi ca ghi rõ nó thuộc loại nào — đối chiếu
đúng loại rồi mới tick.

| Nhãn | Nghĩa | Thế nào là hỏng |
|---|---|---|
| **CHO QUA** | Thao tác phải thành công | Không lưu được |
| **PHẢI CHẶN** | Hệ thống phải từ chối và báo lỗi | Lưu được |
| **CẢNH BÁO, VẪN LƯU** | Hiện cảnh báo **nhưng vẫn lưu được** | Bị chặn — thiếu giấy tờ không được cản trở nghiệp vụ |

## 2. Máy đã kiểm phần nào rồi

123 test tự động phủ logic phân giải, chống trùng, ba trạng thái hết hạn, quyền truy cập và báo
cáo. Bảng này **không lặp lại** những thứ đó. Nó tập trung vào phần chỉ người mới kiểm được:
giao diện, luồng thao tác thật, và cảm giác dùng.

**Phần 3 là phần đáng chú ý nhất.** Nó chỉ được kiểm ở tầng mã nguồn, chưa ai thấy tận mắt trên
trình duyệt. Lần đầu có người mở form thật, một lỗi chặn đã lộ ra ngay ở bảng Phạm vi — đã sửa,
và ca 3.6 dưới đây sinh ra để canh đúng chỗ đó. Đây là bằng chứng rõ nhất rằng test tự động chứng
minh **mô hình đúng**, không chứng minh **form dùng được**.

**Nếu thiếu thời gian:** chạy ca **3.7** rồi Phần 5. Ca 3.7 đi trọn một mặt hàng từ trống trơn tới
đủ hồ sơ — nó chạm gần hết cơ chế trong một lượt. Phần 5 chứng minh điều khiến thiết kế này khác
thiết kế ban đầu. Phần 0 vẫn phải làm trước.

---

## Phần 0 — Chuẩn bị dữ liệu nền

Ba bước này phải xong trước, nếu không sẽ kẹt ngay ở Phần 1.

- [ ] **0.1 — Tạo ít nhất một `Manufacturer`** · *CHO QUA*

  Tìm **Manufacturer** → New → điền **Short Name** → Save.

  **Kết quả:** bản ghi lưu được, tên tài liệu chính là Short Name vừa nhập.

  > **Vì sao trước tiên:** chủ sở hữu là trường bắt buộc của số lưu hành. Chưa có hãng nào thì
  > không tạo nổi số lưu hành ở bước sau.

- [ ] **0.2 — Bật cờ "Là nhóm thiết bị y tế"** · *CHO QUA*

  Mở **Item Group** → lần lượt ba nhóm *Vật tư y tế tiêu hao*, *Hóa chất - sinh phẩm*,
  *Thiết bị y tế và phụ kiện* → tích **Là nhóm thiết bị y tế** → Save.

  **Kết quả:** cả ba nhóm lưu được với cờ đã bật.

  > **Cờ này chỉ là gợi ý.** Nó làm form tự tích ô "Là thiết bị / vật tư y tế" khi chọn nhóm lúc
  > tạo mặt hàng mới — nhưng người dùng vẫn bỏ tích được, và hệ thống nghe theo người dùng. Nhóm
  > *Thiết bị y tế và phụ kiện* có cả phụ kiện không phải thiết bị đăng ký, nên bỏ tích là thao
  > tác chính đáng.

- [ ] **0.3 — Xác nhận danh mục chứng từ đã nạp đủ** · *CHO QUA*

  Mở danh sách **TBYT Document Type**.

  **Kết quả:** đúng **23** bản ghi. Mở `hop_chuan_hop_quy` — bảng quy tắc phải là
  **A: NC · B: NC · C: TH · D: TH**.

  > **Vì sao kiểm đúng dòng này:** nó là dòng duy nhất trong 23 loại có mức *lật* giữa A/B và C/D.
  > Nếu ai đó chép danh sách A sang C thì mọi dòng khác vẫn đúng, chỉ dòng này sai — nên nó là que
  > thử tốt nhất cho cả bảng.

---

## Phần 1 — Số lưu hành và ràng buộc Loại hình

Đây là thực thể trung tâm. Hồ sơ pháp lý gắn vào số lưu hành, không gắn vào từng mã hàng — nên
mọi thứ ở các phần sau đều dựa vào phần này.

- [ ] **1.1 — Tạo số lưu hành loại C, quan sát trường Loại hình** · *CHO QUA*

  **TBYT Marketing Authorization** → New · **Phân loại** = C · **Chủ sở hữu** = hãng ở 0.1 ·
  **Trạng thái** = Còn hiệu lực · **Ngày cấp** = hôm nay · tích **Vô thời hạn** ·
  **Số lưu hành** cố ý dùng số có dấu gạch chéo: `220000123/PCBA-HN`.

  **Kết quả:** **Loại hình** tự thành *Số đăng ký lưu hành* và **không sửa được**. Bản ghi lưu
  được; tên tài liệu có dạng `TBYT-LH-2026-00001`, còn tiêu đề hiển thị là số thật.

  > **Hai điều đang được kiểm cùng lúc.** Loại hình bị khóa theo phân loại — A/B là số công bố,
  > C/D là số đăng ký, không có ngoại lệ. Và số thật chứa dấu `/` không được dùng làm tên tài
  > liệu vì nó sẽ phá đường dẫn — nên hệ thống đánh số riêng và chỉ *hiển thị* số thật.

- [ ] **1.2 — Đổi Phân loại sang A** · *CHO QUA*

  **Kết quả:** **Loại hình** tự đổi thành *Số công bố tiêu chuẩn* ngay, không cần lưu.

  > Đổi lại về **C** trước khi sang ca tiếp theo — các phần sau giả định số lưu hành này là loại C.

- [ ] **1.3 — Tạo số lưu hành thứ hai, trạng thái "Đang đăng ký", bỏ trống số và ngày** · *CHO QUA*

  **Kết quả:** lưu được, dù **Số lưu hành** và **Ngày cấp** đều trống.

  > **Có chủ ý.** Thực tế phải tạo mã hàng để báo giá hoặc nhập hàng mẫu *trước* khi Cục cấp số.
  > Bắt buộc có số thật ngay từ đầu sẽ chặn nghiệp vụ có thật.

- [ ] **1.4 — Đổi bản ghi 1.3 sang "Còn hiệu lực" nhưng vẫn để trống Ngày cấp** · *PHẢI CHẶN*

  **Kết quả:** không lưu được, hệ thống đòi Ngày cấp.

- [ ] **1.5 — Tích "Vô thời hạn" đồng thời điền "Ngày hết hạn"** · *PHẢI CHẶN*

  **Kết quả:** không lưu được — *"Đã tích Vô thời hạn thì không được điền Ngày hết hạn."*

  > **Vì sao không cho khai cả hai:** nếu ô ngày trống mang đồng thời hai nghĩa — "vô thời hạn" và
  > "chưa nhập" — thì cảnh báo hết hạn hằng ngày hoặc báo động giả liên tục, hoặc im lặng bỏ sót
  > đúng tờ giấy sắp hết hạn. Cả hai đều giết mục tiêu của tính năng.

---

## Phần 2 — Mặt hàng và ràng buộc cứng duy nhất

Toàn bộ tính năng chỉ có **một** thứ bị chặn cứng: mặt hàng y tế phải có số lưu hành. Mọi giấy tờ
khác chỉ cảnh báo.

- [ ] **2.1 — Item nhóm y tế, tích cờ TBYT, bỏ trống Số lưu hành** · *PHẢI CHẶN*

  Item → New → chọn nhóm y tế → tab **Hồ sơ TBYT** → tích ô đầu tiên → Save.

  **Kết quả:** không lưu được — *"Mặt hàng là thiết bị y tế thì bắt buộc phải có Số lưu hành."*

  > **Đây là ràng buộc cứng duy nhất của cả tính năng.** Số lưu hành là cơ sở pháp lý để hàng
  > được phép lưu thông — không có nó thì mã hàng không có lý do tồn tại.

- [ ] **2.2 — Chọn số lưu hành loại C ở ca 1.1, rồi lưu** · *CẢNH BÁO, VẪN LƯU*

  **Kết quả:** **Phân loại TBYT** tự điền **C** và không sửa được. Khi lưu, hiện hộp thoại liệt kê
  chứng từ còn thiếu — **nhưng bản ghi vẫn lưu thành công**. **Tình trạng hồ sơ** =
  *Thiếu chứng từ bắt buộc*.

  > **Phân loại suy từ số lưu hành, không nhập tay.** Nhờ vậy hai mặt hàng dùng chung một số lưu
  > hành không thể khai lệch loại — một lớp lỗi báo cáo đơn giản là không xảy ra được.

- [ ] **2.3 — Kiểm bảng chứng từ trên tab "Hồ sơ TBYT"** · *CHO QUA*

  **Kết quả:** bảng liệt kê từng chứng từ kèm mức, cấp lưu và trạng thái. Với loại C phải thấy
  **8 dòng Bắt buộc**, **3 dòng BB có điều kiện**, **2 dòng Nên có**.

  | Phân loại | Bắt buộc | BB có điều kiện | Nên có |
  |:--:|:--:|:--:|:--:|
  | A | 7 | 3 | 3 |
  | B | 8 | 3 | 3 |
  | C | 8 | 3 | 2 |
  | D | 8 | 3 | 2 |

  > **Nhóm "BB có điều kiện" chỉ bị đòi khi Miyano không phải chủ sở hữu số lưu hành** — ba tờ
  > giấy đó (ủy quyền, xác nhận bảo hành, CFS) sinh ra chính vì Miyano đứng tên hộ người khác.
  > Thử bỏ tích **Miyano là chủ sở hữu** trên số lưu hành rồi mở lại mặt hàng: ba dòng đó chuyển
  > thành bắt buộc.

- [ ] **2.4 — Item khác trong nhóm y tế nhưng BỎ TÍCH cờ TBYT** · *CHO QUA*

  **Kết quả:** lưu được bình thường, không đòi số lưu hành, không cảnh báo thiếu chứng từ.

  > **Ca này bảo vệ người dùng khỏi chính hệ thống.** Nhóm *Thiết bị y tế và phụ kiện* có cả phụ
  > kiện không phải thiết bị đăng ký. Nếu hệ thống tự tích lại ô vừa bị bỏ, nó sẽ ghi đè lựa chọn
  > của bạn rồi từ chối lưu vì thiếu số lưu hành — tức là phạt bạn vì chính việc nó vừa làm.

### Bản đồ hồ sơ loại C — đi đâu nộp gì

Sau ca 2.2 mặt hàng báo *Thiếu chứng từ bắt buộc*. Đây là danh sách những gì còn thiếu và **mỗi
tờ gắn vào đâu**. Phần 3 dạy cách nộp một tờ; bảng này cho biết phải nộp bao nhiêu tờ và ở đâu.

| Mức | Chứng từ | Gắn vào |
|---|---|---|
| BB | Bản kết quả phân loại thiết bị y tế | Số lưu hành |
| BB | Giấy chứng nhận đăng ký lưu hành | Số lưu hành |
| BB | Hướng dẫn sử dụng bằng tiếng Việt | Số lưu hành |
| BB | Mẫu nhãn hàng hóa lưu hành tại Việt Nam | Số lưu hành |
| BB | Tài liệu kỹ thuật phục vụ sửa chữa, bảo dưỡng | Số lưu hành |
| BB | Thông tin cơ sở bảo hành | **Chủ sở hữu** |
| BB | Phiếu tiếp nhận công bố đủ điều kiện mua bán TBYT | **Công ty** |
| BB | Thông tin niêm yết giá | **Mặt hàng** |
| BB\* | Giấy ủy quyền của chủ sở hữu TBYT | Số lưu hành |
| BB\* | Giấy xác nhận đủ điều kiện bảo hành | Số lưu hành |
| BB\* | Giấy chứng nhận lưu hành tự do (CFS) | Số lưu hành |
| NC | Giấy chứng nhận ISO 13485 của cơ sở sản xuất | **Chủ sở hữu** |
| NC | Tài liệu mô tả tóm tắt kỹ thuật / CSDT | Số lưu hành |

> **Đọc cột bên phải kỹ — đó là toàn bộ ý tưởng của thiết kế.** Chỉ **một** tờ trong 13 tờ gắn vào
> mặt hàng (niêm yết giá). Năm tờ gắn vào số lưu hành, hai tờ vào chủ sở hữu, một tờ vào công ty.
> Nghĩa là mặt hàng thứ hai dùng chung số lưu hành sẽ **tự có sẵn 12 trong 13 tờ** — bạn chỉ nhập
> thêm đúng thông tin niêm yết giá. Ca 5.3 kiểm chính điều này.
>
> Ba tờ **BB\*** chỉ bị đòi khi bỏ tích *Miyano là chủ sở hữu số lưu hành*. Nếu Miyano tự đứng
> tên thì ba tờ đó không cần.

---

## Phần 3 — Tải chứng từ lên

**Phần cần chú ý nhất.** Đường đi này mới được thêm và **chưa ai xác minh trên trình duyệt** — mọi
thứ khác trong bảng đều đã có test tự động phủ, riêng chuỗi thao tác dưới đây thì chưa.

> **Nếu ca 3.1 không chạy đúng:** đừng cố xoay xở. Ghi lại chính xác điều bạn thấy — nút có hiện
> không, bấm vào có mở form mới không, form đó điền sẵn được gì — rồi báo lại. Ca 3.6 đi đường New
> trắng, không phụ thuộc cái nút, nên công việc không bị chặn.
>
> **Trước khi bắt đầu phần này, bấm `Ctrl+Shift+R`** để trình duyệt nạp lại script form. Nếu bảng
> Phạm vi vẫn không nhập được, gần như chắc chắn là trang đang chạy bản script cũ.

- [ ] **3.1 — Mở số lưu hành loại C → bấm "Tải chứng từ lên"** · *CHO QUA*

  **Kết quả:** mở form **TBYT Regulatory Document** mới, trong đó **Loại chứng từ** đã điền sẵn
  `gcn_dang_ky_luu_hanh`, và bảng **Phạm vi** đã có **một dòng** trỏ về đúng số lưu hành vừa mở.

  > Nếu loại chứng từ điền sẵn là `so_cong_bo_tieu_chuan` thì số lưu hành đang là loại A hoặc B —
  > quay lại kiểm ca 1.2 xem đã đổi phân loại về C chưa.

- [ ] **3.2 — Điền và lưu chứng từ** · *CHO QUA*

  **Số hiệu** dùng số có dấu gạch chéo và dấu tiếng Việt để thử, ví dụ `SLH-2026/Đ-01` ·
  **Ngày cấp** = hôm nay · tích **Vô thời hạn** · **Tệp** đính một PDF bất kỳ → Save.

  **Kết quả:** lưu được. **Trạng thái** tự thành *Còn hiệu lực*.

- [ ] **3.3 — Quay lại form số lưu hành, làm mới trang** · *CHO QUA*

  **Kết quả:** mục **Chứng từ đã gắn** hiện bản ghi vừa tạo, kèm số hiệu và trạng thái, bấm vào
  mở được.

- [ ] **3.4 — Kiểm tệp đã được xếp chỗ và đổi tên** · *CHO QUA*

  Mở **File** → tìm tệp vừa tải lên.

  **Kết quả:**
  - Tên đổi thành dạng `SLH__SLH-2026-D-01__2026-08-24.pdf` — dấu `/` và dấu tiếng Việt đã xử lý
  - Thư mục là `Home/TBYT/03-So-luu-hanh/<số lưu hành>/`
  - Tệp ở chế độ **riêng tư**
  - Chỉ có **một** bản ghi File cho tệp này, không phải hai

  > **Nhìn tên là biết giấy gì, số nào, cấp ngày nào** — không cần mở ERP. Đây cũng là ca kiểm
  > việc dấu gạch chéo trong số hiệu không tạo ra tầng thư mục ma.

- [ ] **3.5 — Thay tệp đính kèm bằng một PDF khác, lưu** · *CHO QUA*

  **Kết quả:** sau khi lưu và làm mới, trường **Tệp** trỏ tới **tệp mới** — không âm thầm quay về
  tệp cũ.

  > **Ca này từng hỏng và đã được sửa.** Trước đó hệ thống lặng lẽ hoàn tác lựa chọn của người
  > dùng, đưa trường Tệp về file cũ mà không báo gì. Đáng bỏ 30 giây kiểm lại.

- [ ] **3.6 — Tạo chứng từ từ đường New trắng, không qua nút** · *CHO QUA*

  **TBYT Regulatory Document** → New (không đi từ form số lưu hành).

  1. **Loại chứng từ** = `hdsd_tieng_viet` — chọn ô này **trước tiên**
  2. Quan sát dòng gợi ý dưới bảng **Phạm vi**: phải đổi thành *"Tờ giấy này cấp cho: chọn **Số
     lưu hành**"*
  3. Bảng **Phạm vi** → thêm dòng. Cột **Loại đối tượng** tự điền; cột **Áp dụng cho** bấm vào
     phải tìm được số lưu hành
  4. Điền số hiệu, ngày cấp, tích **Vô thời hạn**, đính tệp → Save

  **Kết quả:** lưu được. Thử thêm: đổi **Loại chứng từ** sang `iso_13485_nha_san_xuat` — bảng Phạm
  vi bị **xóa sạch** và dòng gợi ý đổi thành *"chọn **Chủ sở hữu (hãng)**"*.

  > **Ca này sinh ra từ một lỗi chặn có thật.** Trước khi sửa, đường New trắng hoàn toàn không
  > dùng được: cột *Loại đối tượng* là read-only nên không gõ được, còn cột *Áp dụng cho* là
  > Dynamic Link nên không biết tìm ở đâu khi ô kia trống — mà cả hai đều bắt buộc. Bế tắc.
  > 123 test không bắt được vì test nào cũng dựng bản ghi bằng code, không test nào bấm "thêm
  > dòng" trên lưới.
  >
  > **Vì sao đổi loại chứng từ lại xóa bảng:** đổi loại có thể đổi luôn cấp phạm vi. Giữ lại dòng
  > cũ nghĩa là lưu một phạm vi trỏ sai chủ thể — tệ hơn là bắt nhập lại.

- [ ] **3.7 — Đi trọn: nộp đủ và xem trạng thái chuyển xanh** · *CHO QUA*

  Dùng bản đồ ở cuối Phần 2. Nộp lần lượt **8 tờ BB**, mỗi tờ một bản ghi chứng từ. Với mỗi tờ:
  chọn đúng **Loại chứng từ**, thêm một dòng Phạm vi trỏ đúng chủ thể trong cột "Gắn vào", đính
  tệp bất kỳ, điền số hiệu và ngày cấp, tích **Vô thời hạn**, Save.

  Ba tờ gắn vào **Chủ sở hữu** / **Công ty** / **Mặt hàng** là chỗ dễ nhầm nhất — đọc lại cột bên
  phải của bản đồ trước khi làm.

  Sau tờ cuối cùng, mở lại mặt hàng và làm mới trang.

  **Kết quả:** **Tình trạng hồ sơ** chuyển thành *Đủ hồ sơ mặt hàng*. Bảng chứng từ trên tab
  **Hồ sơ TBYT** không còn dòng nào ở trạng thái chưa có, trừ các dòng *Nên có*.

  > **Đây là ca trả lời câu hỏi "rồi sao nữa".** Các ca trước kiểm từng cơ chế riêng lẻ; ca này đi
  > trọn một mặt hàng từ lúc trống trơn tới lúc đủ hồ sơ. Nếu chỉ chạy được một ca trong cả Phần 3,
  > chạy ca này.
  >
  > Nhãn là *Đủ hồ sơ mặt hàng*, **không phải "Đủ"** — vì chứng từ cấp lô (CQ, CO) cố ý không tính
  > ở đây. Ca 6.3 lo phần đó.

- [ ] **3.8 — Nút "Nộp giấy" ngay trên bảng hồ sơ của mặt hàng** · *CHO QUA*

  Mở mặt hàng → tab **Hồ sơ TBYT** → nhìn bảng chứng từ.

  **Kết quả:** các dòng mức **Bắt buộc** và **BB có điều kiện** đang thiếu đều có nút **Nộp giấy**.
  Dòng mức **Nên có** **không** có nút.

  Bấm nút ở dòng *Giấy chứng nhận ISO 13485*. Hộp thoại mở ra, dòng đầu tiên ghi:
  *"Tờ này sẽ gắn vào **hãng {tên hãng}** — mọi mặt hàng của hãng đều dùng chung."*

  > **Đọc kỹ câu đó — nó là điểm mấu chốt của cả mô hình.** Bạn nộp giấy *từ* mặt hàng, nhưng
  > hệ thống gắn nó *vào hãng*, vì ISO 13485 là giấy của nhà máy chứ không phải của một mã hàng.
  > Nhờ vậy mọi mặt hàng khác của hãng đó tự có luôn.

- [ ] **3.9 — Nộp xong, mặt hàng cập nhật ngay và không mất dữ liệu đang sửa** · *CHO QUA*

  Trước khi bấm nút Nộp giấy, **sửa một trường bất kỳ** trên mặt hàng (ví dụ đổi Tên hàng) nhưng
  **đừng lưu**. Rồi mới bấm Nộp giấy, điền số hiệu, ngày cấp, tích Vô thời hạn, đính tệp → Tạo mới.

  **Kết quả:**
  - Bảng hồ sơ cập nhật ngay, dòng vừa nộp chuyển sang đã có
  - Trường **Tình trạng hồ sơ** đổi theo
  - **Thay đổi chưa lưu của bạn vẫn còn nguyên**, và form vẫn ở trạng thái chưa lưu

  > **Ca này canh một lỗi dễ mắc.** Cách làm ngây thơ là nạp lại cả bản ghi sau khi nộp — và như
  > vậy sẽ xoá sạch những gì bạn đang sửa dở. Hệ thống cố ý chỉ cập nhật đúng hai thứ đã đổi.

- [ ] **3.10 — Tra số hiệu: biết tờ giấy đã có hay chưa** · *CHO QUA*

  Bấm **Nộp giấy** ở một dòng khác. Trong ô **Số hiệu**, gõ số hiệu của tờ **đã nộp ở ca 3.9**.

  **Kết quả:** gõ tới ký tự thứ ba trở đi, dưới ô hiện khối kết quả nêu mã bản ghi, tên loại chứng
  từ, phạm vi và trạng thái. Vì mặt hàng này đã có sẵn tờ đó, khối ghi *"Mặt hàng này đã có sẵn tờ
  này"* và **không** có nút gắn.

  Thử thêm: gõ 1–2 ký tự → không tra, không hiện gì.

- [ ] **3.11 — Gắn một tờ CFS đã có cho mặt hàng khác** · *CHO QUA*

  Cần: hai số lưu hành **cùng một hãng**, đều bỏ tích *Miyano là chủ sở hữu* và tích *Hàng nhập
  khẩu*; mỗi số một mặt hàng.

  1. Từ mặt hàng thứ nhất, nộp một tờ `cfs_giay_luu_hanh`, ghi nhớ số hiệu
  2. Mở mặt hàng thứ hai → bấm **Nộp giấy** ở dòng CFS → gõ đúng số hiệu đó
  3. Khối kết quả hiện tờ vừa nộp, kèm nút **Gắn tờ này cho mặt hàng** → bấm

  **Kết quả:** mặt hàng thứ hai có ngay tờ CFS đó, và **số bản ghi chứng từ không tăng** — vẫn là
  một tờ giấy, giờ phủ hai số lưu hành.

  > **Đây là ca duy nhất trong bảng kiểm tra được đường "dùng lại tờ đã có".** Nó chỉ có nghĩa với
  > 4 loại chứng từ cho phép nhiều phạm vi. Với 19 loại còn lại, nút gắn cố ý **không** hiện — vì
  > một tờ giấy của hãng này không thể trở thành giấy của hãng khác.

**Đường làm thủ công, nếu nút không chạy:** **TBYT Regulatory Document** → New → **Loại chứng từ**
= `gcn_dang_ky_luu_hanh` (loại C/D) hoặc `so_cong_bo_tieu_chuan` (loại A/B) → bảng **Phạm vi**
thêm một dòng, chọn số lưu hành → đính tệp, điền số hiệu và ngày cấp → Save. Kết quả giống hệt;
nút chỉ là lối tắt.

---

## Phần 4 — Ba trạng thái hiệu lực

Một tờ giấy có thể **có hạn** hoặc **vô thời hạn**. Hệ thống phải phân biệt được hai điều đó với
"chưa ai nhập ngày".

- [ ] **4.1 — Chứng từ mới, KHÔNG tích Vô thời hạn và BỎ TRỐNG Ngày hết hạn** · *PHẢI CHẶN*

  **Kết quả:** không lưu được — *"Chưa tích Vô thời hạn thì bắt buộc phải điền Ngày hết hạn."*

  > **Đây là ca quan trọng nhất Phần 4.** Nó đóng khoảng mờ: sau ca này, một ô ngày trống chỉ còn
  > đúng một nghĩa là "vô thời hạn". Nhờ vậy cảnh báo hằng ngày mới đáng tin.

- [ ] **4.2 — Chứng từ `hdsd_tieng_viet` gắn vào SLH loại C, hết hạn trong vòng 90 ngày** · *CHO QUA*

  **Kết quả:** **Trạng thái** = *Sắp hết hạn*.

- [ ] **4.3 — Sửa ngày hết hạn về quá khứ, lưu, mở lại mặt hàng** · *CHO QUA*

  **Kết quả:** chứng từ chuyển *Hết hạn*. Mặt hàng chuyển **Tình trạng hồ sơ** =
  *Có chứng từ hết hạn*.

- [ ] **4.4 — Đặt số lưu hành sang "Bị thu hồi", mở lại mặt hàng** · *CHO QUA*

  **Kết quả:** **Tình trạng hồ sơ** = *Số lưu hành hết hiệu lực* — đè lên mọi trạng thái khác.

  > Đặt lại về **Còn hiệu lực** trước khi sang Phần 5. Số lưu hành mất hiệu lực là sự kiện tuân
  > thủ nặng nhất, nên nó chiếm chỗ hiển thị bất kể giấy tờ khác ra sao.

---

## Phần 5 — Không trùng, và thừa hưởng

Đây là phần chứng minh lý do cả mô hình này tồn tại. Nếu chỉ chạy được một phần trong cả bảng,
hãy chạy phần này.

- [ ] **5.1 — Chứng từ THỨ HAI cùng loại `gcn_dang_ky_luu_hanh`, cùng số lưu hành** · *PHẢI CHẶN*

  **Kết quả:** không lưu được. Thông báo nêu tên bản ghi đang giữ chỗ và nhắc dùng trường
  **Thay thế cho**.

- [ ] **5.2 — Vẫn form đó, khai "Thay thế cho" = bản ghi cũ, rồi lưu** · *CHO QUA*

  **Kết quả:** lưu được. Mở bản ghi cũ: **Đang hiệu lực** đã tắt, **Trạng thái** = *Đã thay thế*.
  Tệp của nó chuyển vào thư mục con `_Luu-tru/`.

  > **Gia hạn không ghi đè.** Bản cũ vẫn tra được — cần thiết khi phải chứng minh tại thời điểm
  > bán hàng, giấy tờ nào đang có hiệu lực.

- [ ] **5.3 — Mặt hàng THỨ HAI trỏ vào CÙNG số lưu hành** · *CHO QUA*

  Trước khi tạo, ghi lại số bản ghi hiện có trong danh sách **TBYT Regulatory Document**.

  **Kết quả:** mặt hàng mới **đã sẵn có** mọi chứng từ mà mặt hàng thứ nhất có — không phải nhập
  lại gì. Và số bản ghi chứng từ **không tăng**.

  > **Đây là toàn bộ lý do mô hình này tồn tại.** Thiết kế ban đầu gắn tệp thẳng vào từng mã hàng
  > — cùng tình huống này sẽ sinh ra hai bộ metadata độc lập, mỗi bộ một ngày hết hạn phải gia hạn
  > riêng, và sót một bộ là báo cáo tuân thủ sai. Ở đây một tờ giấy tồn tại đúng một lần.

- [ ] **5.4 — Một tờ CFS phủ nhiều số lưu hành** · *CHO QUA*

  Tạo số lưu hành thứ ba, **cùng chủ sở hữu**, loại C, bỏ tích **Miyano là chủ sở hữu**, tích
  **Hàng nhập khẩu**. Làm tương tự với số lưu hành ở ca 1.1. Tạo chứng từ `cfs_giay_luu_hanh`,
  bảng **Phạm vi** thêm **hai dòng** — mỗi dòng một số lưu hành.

  **Kết quả:** lưu được thành **một** bản ghi. Mọi mặt hàng thuộc cả hai số lưu hành đều thấy tờ
  CFS đó.

  > **Một CFS thật thường liệt kê nhiều sản phẩm.** Nếu buộc mỗi số lưu hành một bản ghi thì cùng
  > tờ giấy bị nhân bản; nếu gắn ở cấp hãng thì mọi mặt hàng của hãng đều nhận vơ, kể cả mặt hàng
  > không có trong tờ CFS. Bảng phạm vi thoát cả hai.

---

## Phần 6 — Làm mới tức thì và báo cáo

Đã chốt hệ thống không chặn nghiệp vụ ở đâu cả — nên báo cáo là **bề mặt kiểm soát duy nhất còn
lại**.

- [ ] **6.1 — Tải lên chứng từ cấp CHỦ SỞ HỮU rồi kiểm mặt hàng ngay** · *CHO QUA*

  Tạo chứng từ `thong_tin_bao_hanh`, bảng Phạm vi chọn **hãng** (không phải số lưu hành) → Save.
  Mở lại mặt hàng, làm mới trang.

  **Kết quả:** dòng *Thông tin cơ sở bảo hành* chuyển sang đã có **ngay lập tức**, không phải chờ
  hôm sau.

  > **Ca này bảo vệ lòng tin vào chỉ báo.** Nếu trạng thái chỉ được cập nhật lúc nửa đêm, người
  > dùng vừa làm đúng việc mà hệ thống vẫn báo đỏ — và họ sẽ nhanh chóng thôi đọc chỉ báo.

- [ ] **6.2 — Mở báo cáo "Tinh Trang Ho So TBYT"** · *CHO QUA*

  **Kết quả:** liệt kê các mặt hàng y tế kèm số chứng từ còn thiếu theo từng mức, ngày hết hạn gần
  nhất, và cột **Hồ sơ cấp lô**. Thử bộ lọc **Phân loại** và **Chủ sở hữu**.

- [ ] **6.3 — Mặt hàng đủ hồ sơ cấp mặt hàng nhưng lô thiếu giấy — vẫn phải hiện** · *CHO QUA*

  Chọn một mặt hàng, bật **Has Batch No**, tạo một **Batch** cho nó, không gắn CQ và CO cho lô đó.
  Mở báo cáo, **giữ nguyên** bộ lọc "Chỉ hiện hồ sơ chưa đủ" đang bật sẵn.

  **Kết quả:** mặt hàng đó **vẫn xuất hiện**, cột **Hồ sơ cấp lô** ghi `0/1 lô`.

  > **Ca này từng hỏng và đã được sửa.** Trạng thái của mặt hàng cố ý bỏ qua chứng từ cấp lô — nên
  > nếu bộ lọc chỉ nhìn trạng thái đó, nó sẽ giấu đi đúng khoảng trống mà cột Hồ sơ cấp lô sinh ra
  > để phơi bày. Mà bộ lọc ấy bật sẵn.

---

## Giới hạn đã biết, không phải lỗi

Gặp phải thì ghi nhận, đừng ghi là lỗi.

| Giới hạn | Biểu hiện | Khi nào cần xử lý |
|---|---|---|
| **Một công ty** | Chứng từ cấp công ty chỉ phân giải theo công ty mặc định | Khi site có công ty thứ hai |
| **Item variant** | Biến thể tạo từ mặt hàng mẫu không kế thừa cờ TBYT và số lưu hành | Trước khi bắt đầu dùng biến thể |
| **Quy mô** | Phân giải tốn nhiều truy vấn mỗi mặt hàng; chậm dần khi danh mục lớn | Trước khi vượt vài nghìn mã hàng |
| **Nhập hàng loạt** | Import không có cột cờ y tế sẽ tạo mặt hàng không được theo dõi; có cảnh báo khi lưu nhưng không tự bật cờ | Đưa cột đó vào mẫu import |

---

## Ký nhận

| Mục | |
|---|---|
| Người nghiệm thu | |
| Ngày | |
| Số ca đạt / tổng | / 34 |
| Kết luận | |

**Ca không đạt và mô tả cụ thể:**

<br><br><br>

> Khi báo lỗi, ghi kèm: **mã ca**, **điều bạn thấy**, và **điều bảng này nói phải thấy**.
