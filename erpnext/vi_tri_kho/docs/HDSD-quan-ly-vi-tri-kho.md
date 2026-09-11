# Hướng dẫn sử dụng: quản lý vị trí kho (giá kệ / ô kệ)

Module **Vi Tri Kho** trong Miyano ERP · giai đoạn 0 + 1 · site `erptest.local`

---

## 0. Trước hết: giai đoạn này làm được gì, CHƯA làm được gì

Đọc mục này trước, để không chờ một tính năng chưa tới.

### ĐÃ có
- Khai sơ đồ kho theo **mã ô 12 ký tự chuẩn SPD**, sinh mã hàng loạt (mục 1b).
- **Bật quản lý vị trí cho từng kho**, chuyển toàn bộ tồn hiện có vào sổ vị trí.
- **Mọi phiếu nhập/xuất tự động vào sổ theo ô và theo lô** — không phải thao tác gì thêm.
- Xuất kho **tự chọn ô theo hạn dùng gần nhất trước (FEFO)**, cùng hạn thì theo đường đi.
- **Huỷ phiếu trả hàng về đúng ô đã lấy**, không phải ô khác.
- Ba báo cáo: tồn theo ô, hàng chưa xếp vị trí, và đối soát.

### CHƯA có (các giai đoạn sau)
- **Chọn ô khi nhập hàng.** Hàng nhập về hiện dồn hết vào ô **"Chưa xếp vị trí"**; thủ kho
  xem báo cáo rồi tự xếp ngoài thực tế. Bảng chọn ô trên phiếu là **giai đoạn 2**.
- **Nút "Gợi ý lấy hàng" và cột Vị trí trên phiếu giao hàng.** Đây chính là thứ chủ dự án
  muốn nhất; hệ đã tự chọn ô đúng ở phía sau, nhưng **chưa in ra phiếu** — **giai đoạn 3**.
- **Phiếu chuyển ô và phiếu kiểm kê theo ô** — **giai đoạn 4**.
- **Quét mã vạch vị trí** — giai đoạn 5.

---

## 1. Vào ở đâu, ai vào được

Mở `http://192.168.61.129:8003`, gõ tên màn hình vào ô tìm kiếm (biểu tượng kính lúp trên
thanh trên cùng), hoặc vào thẳng theo đường dẫn.

| Màn hình | Đường dẫn | Dùng để |
|---|---|---|
| Storage Location | `/app/storage-location` | Xem và sửa danh mục ô |
| Location Generator | `/app/location-generator` | Sinh mã ô hàng loạt |
| Warehouse Location Setup | `/app/warehouse-location-setup` | Bật / tắt / đồng bộ theo kho |
| Tồn kho theo vị trí | `/app/query-report/Ton Kho Theo Vi Tri` | Hàng nào đang ở ô nào |
| Hàng chưa xếp vị trí | `/app/query-report/Hang Chua Xep Vi Tri` | Việc cần dọn của thủ kho |
| Đối soát tồn vị trí | `/app/query-report/Doi Soat Ton Vi Tri` | Kiểm hệ có lệch không |

**Quyền:**
- **Sinh ô, bật/tắt kho, đồng bộ**: chỉ `System Manager` và `Stock Manager`. Đây là thao tác
  **thiết lập**, không phải việc hằng ngày — cố ý không mở cho `Stock User`.
- **Xem ba báo cáo và danh mục ô**: thêm `Stock User`.
- **Khách hàng trên cổng (`Website User`) không vào được gì** — đã chặn và có kiểm thử.

---

## 1b. Mã ô đọc thế nào

Mã ô **12 ký tự**, theo tài liệu `SPD_VanHanh_PhanTichMaViTriKho_20260907_v2` §5.2. Điểm hay
là **nhìn mã biết ngay chỗ đứng**, không phải tra bảng:

```
K1  1B  01   04      03    02        →   K11B01040302
kho khu dãy  khoang  tầng  ô
```

Hệ lưu và hiển thị **đúng 12 ký tự liền** (ô **Mã ô**). Riêng ô **Mã in trên nhãn** giữ dạng
`K11B0104-0302` để in tem — cộng tiền tố `VT ` là **16 ký tự**, vừa đúng giới hạn trường F8
của đặc tả nhãn 50×30 v2.

*(Tài liệu SPD có lúc viết `K1-1B01-04-0302` cho dễ đọc bằng mắt. Đó chỉ là cách trình bày
trong văn bản — phần mềm không sinh chuỗi đó ở đâu cả, đừng đi tìm.)*

| Phần | Dài | Miền giá trị | Cách đánh số |
|---|---|---|---|
| Kho | 2 | chữ + số, ví dụ `K1`, `B1`–`B9` | `K1` kho trung tâm, `B1`… kho vệ tinh |
| Khu | 2 | số + chữ, ví dụ `1B` | theo sơ đồ mặt bằng |
| Dãy | 2 | `01`–`99` | |
| Khoang | 2 | `01`–`99` | trái sang phải |
| Tầng | 2 | `01`–`09` | **đếm từ dưới lên** |
| Ô | 2 | `01`–`99` | trái sang phải |

Hệ **chặn cứng** mã sai chuẩn — sai một ký tự là không lưu được, kèm thông báo chỉ rõ dạng
đúng. `00` cũng bị chặn, vì tuy đủ 2 chữ số nhưng không có dãy 0 hay tầng 0 nào cả.

> **Mã ô không bao giờ dùng lại.** Dỡ kệ đi thì mã đó "chết" theo, không cấp cho ô khác —
> nếu không, tem cũ còn sót lại sẽ chỉ vào chỗ sai.

---

## 2. Trình tự làm lần đầu (theo đúng thứ tự này)

### Bước 0 — Đặt mã kho (làm một lần cho mỗi kho)

Mở **Warehouse** → kho cần dùng → điền **Mã kho SPD (2 ký tự)**, ví dụ `Kho Miyano - MYN`
đặt là `K1`. Lưu.

Đây là 2 ký tự đầu của mọi mã ô trong kho đó. Để trên kho chứ không bắt gõ lại mỗi lần sinh,
để không có chuyện hai lô ô cùng kho mà khác mã. **Chưa điền thì bước sinh ô sẽ báo lỗi.**

### Bước 1 — Sinh mã ô

Vào **Location Generator** → **New**. Điền:

| Ô nhập | Ý nghĩa | Ví dụ |
|---|---|---|
| Kho | Kho sẽ chứa các ô này (mã kho lấy từ Bước 0) | `Kho Miyano - MYN` |
| Khu (2 ký tự) | Số + chữ, theo sơ đồ mặt bằng | `1B` |
| Số dãy | tối đa 99 | `2` |
| Số khoang mỗi dãy | tối đa 99 | `3` |
| Số tầng mỗi khoang | tối đa **9** | `4` |
| Số ô mỗi tầng | tối đa 99 | `2` |

Không còn ô "Mẫu mã ô" — khuôn mã là chuẩn cứng của SPD, không đặt lại được. Ô **Mẫu mã sinh
ra** chỉ để xem trước, hệ tự điền.

Lưu, rồi bấm **"Xem trước rồi sinh ô"**.

Hộp thoại hiện **sẽ tạo bao nhiêu ô** và **vài mã ví dụ**. Ví dụ trên cho `2 × 3 × 4 × 2` =
**48 ô**, mã chạy từ `K11B01010101` tới `K11B02030402`. Kiểm kỹ rồi mới xác nhận.

> **Mã ô KHÔNG sửa được sau khi tạo.** Muốn đổi phải xoá ô và tạo lại — mà mã đã dùng thì
> không cấp lại. Tem đã in, người đã quen mã: đối chiếu sơ đồ kho cho xong trước khi bấm.

Nếu có mã trùng, hệ **không tạo ô nào cả** và báo mã nào trùng. Sửa khu hoặc số lượng rồi
làm lại — không có chuyện tạo được một nửa.

**Muốn ô nào được lấy hàng trước:** bộ sinh đã tự đánh **Thứ tự lấy hàng** 1, 2, 3… theo
đúng thứ tự mã (dãy → khoang → tầng → ô). Nếu đường đi thật trong kho khác thế, mở từng ô
trong **Storage Location** và sửa lại số — ô gần cửa để số nhỏ.

### Bước 2 — Bật quản lý vị trí cho kho

Vào **Warehouse Location Setup** → **New** → chọn **Kho** → **Lưu**.

Bấm **"Xem trước chuyển đổi"**. Hộp thoại cho biết:
- sẽ ghi **bao nhiêu dòng sổ**, cho bao nhiêu **mặt hàng**, bao nhiêu **lô**;
- **cảnh báo** nếu có hàng không quản lý lô, hoặc có tồn âm.

**Bước xem trước không ghi gì cả** — bấm thoải mái để xem.

Xác nhận trên hộp thoại đó chính là **bật**. *(Không có nút "Bật" riêng — việc bật nằm trong
hộp xác nhận này, cố ý để không ai bật mà chưa xem trước.)*

Toàn bộ tồn hiện có chuyển vào ô **"Chưa xếp vị trí"** của kho, tách theo từng lô. Nếu bước
đối soát cuối cùng phát hiện lệch, hệ **huỷ sạch** và kho quay về đúng như trước — không có
trạng thái bật nửa vời.

### Bước 3 — Kiểm ngay sau khi bật

Mở báo cáo **Đối soát tồn vị trí**, chọn kho. **Rỗng nghĩa là khớp.**

Rồi mở **Hàng chưa xếp vị trí** — lúc này nó liệt kê **toàn bộ tồn**, vì mọi thứ vừa vào ô
"Chưa xếp vị trí". Đó là danh sách việc: xếp hàng vào ô thật ngoài kho, và ở giai đoạn 2 sẽ
có màn hình để khai vị trí.

---

## 3. Vận hành hằng ngày

**Không phải thao tác gì thêm.** Cứ nhập/xuất bằng chứng từ ERPNext như cũ — hệ tự ghi sổ vị
trí ở phía sau.

| Việc | Hệ làm gì |
|---|---|
| Nhập kho (Purchase Receipt, Stock Entry) | Hàng vào ô **"Chưa xếp vị trí"** |
| Xuất kho / giao hàng (Delivery Note, Stock Entry) | Hệ **tự chọn ô** theo hạn dùng gần nhất trước; cùng hạn thì theo thứ tự lấy hàng |
| Huỷ phiếu | Hàng về **đúng ô đã lấy**, không phải ô khác |
| Kiểm kê (Stock Reconciliation) | Sổ vị trí điều chỉnh theo |

**Việc hằng ngày của thủ kho:** mở **Hàng chưa xếp vị trí**, xếp hàng vào ô thật.

**Việc hằng tuần của quản lý:** mở **Đối soát tồn vị trí**. Rỗng là tốt.

---

## 4. Khi báo cáo đối soát có dòng

Đối soát kiểm **ba** thứ. Đọc cột `loai` để biết gặp loại nào:

| Loại | Nghĩa | Làm gì |
|---|---|---|
| Lệch tồn | Tổng tồn các ô ≠ tồn kho ERPNext | Vào Warehouse Location Setup → **"Đồng bộ lại"** |
| Ô âm | Có ô mang số lượng âm | **Không** bấm Đồng bộ lại (nó sẽ báo lỗi). Xem mục dưới |
| Lệch bộ đệm | Bộ nhớ đệm trôi khỏi sổ | Dựng lại tồn vị trí (xem mục dưới) |

**"Đồng bộ lại" chỉ chữa được loại thứ nhất.** Với ô âm hoặc lệch bộ đệm, nó **cố ý ném lỗi**
thay vì âm thầm ghi đè — vì hai loại đó là dấu hiệu dữ liệu hỏng, không phải lệch thường.

Khi đó cần chạy **dựng lại tồn vị trí** (thao tác kỹ thuật, gọi qua bench):

```
bench --site erptest.local execute miyano_wms.vitri.so.dung_lai_ton_vi_tri --kwargs "{'kho': 'Kho Miyano - MYN'}"
```

Hàm này xoá bộ đệm và **cộng lại từ đầu từ sổ**. Sổ không bao giờ bị sửa hay xoá — nó chỉ ghi
thêm — nên thao tác này an toàn, chạy lại bao nhiêu lần cũng được.

---

## 5. Tắt và bật lại

**Tắt** (Warehouse Location Setup → "Tắt quản lý vị trí"): hệ ngừng ghi sổ cho kho đó. **Sổ cũ
giữ nguyên**, không xoá gì.

**Không bật thẳng lại được.** Trong lúc tắt kho vẫn xuất nhập, nên tồn vị trí đứng yên trong
khi tồn kho đi tiếp. Phải bấm **"Đồng bộ lại"** trước — nó ghi bù phần chênh vào ô "Chưa xếp
vị trí" rồi mới bật lại. Đây là chặn cố ý, không phải lỗi.

---

## 6. Bốn điều dễ gây hiểu nhầm

**Ô "Chưa xếp vị trí" là ô hệ thống.** Mỗi kho đúng một ô, mã `ZZZ-CHUA-XEP`. Không xoá
được, không đặt "Ngừng dùng" được — vì nó là van an toàn: mọi thứ không rõ vị trí đều rơi
vào đó thay vì làm hỏng số liệu. Đây là ô **duy nhất** không theo chuẩn 12 ký tự; nó được
miễn kiểm định dạng, và tên đặt bắt đầu bằng `ZZZ` để luôn xếp cuối danh sách.

**Ô "Chưa xếp vị trí" được lấy hàng SAU CÙNG, không phải trước.** Nó mang thứ tự lấy hàng
9999. Cùng hạn dùng thì hệ lấy từ ô đã xếp đàng hoàng trước — thủ kho biết đi tới đâu; chỉ
khi các ô thật cạn hàng mới rút tới đống chưa xếp. Hàng ở đó vẫn là hàng thật và vẫn xuất
được bình thường.

**Ô đặt "Ngừng dùng" vẫn được tính vào tồn, nhưng không được lấy hàng.** Nếu hàng chỉ còn ở ô
ngừng dùng, phiếu xuất sẽ bị chặn với thông báo **nói rõ ô nào đang giữ hàng** — không phải
câu "thiếu hàng" chung chung. Chuyển hàng khỏi ô đó, hoặc bật lại ô.

**Báo cáo đối soát rỗng mới là tốt.** Nó không phải báo cáo tồn kho — nó là báo cáo *sai lệch*.
Muốn xem tồn thì mở **Tồn kho theo vị trí**.
