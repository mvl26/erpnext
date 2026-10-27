# Runbook go-live phân quyền RBAC – Miyano ERP

Dành cho: người vận hành IT. Nguồn: `TK_01_PhanQuyen_ERP_V2.1_AI.md` mục 12 (Bước 0, 6) và Phụ lục A.
Tài liệu liên quan: `BanGiao_C5_C6_hrms.md` (việc bên hrms), `docs/fast_miyano/go_live_runbook.md` (go-live chung; trỏ về đây cho các Role Profile `RP-*`).

**Quy ước.** Bench ở `/home/miyano/frappe-bench`; chạy mọi lệnh `bench` từ thư mục đó. Site thật là `miyano`, site thử là `erptest`. Ký hiệu **[NGƯỜI]** là bước phải có người cụ thể làm (mật khẩu root DB, `sudo`, số liệu nghiệp vụ). Không làm bước sau khi bước trước chưa đạt.

**Cần biết trước khi bắt đầu**

- Mọi hook RBAC (`hooks.py`: guard workflow, bank account, phạm vi hồ sơ, mail kiểm toán, hạn mức...) chỉ chạy khi site có `mvl_rbac_enabled: 1` trong site_config. Cờ tắt thì mã RBAC không làm gì. Cờ mặc định tắt.
- Thứ tự bắt buộc: **sync trước, cutover sau.** Sync (`erpnext.access.permissions.sync`) tạo role, Role Profile, Custom DocPerm, workflow mới. Cutover (`erpnext.access.permissions.cutover`) mới tắt workflow cũ, gán lại `workflow_state` cho chứng từ cũ, gỡ role/profile cũ.
- Web và worker chạy dưới supervisor với gunicorn `--preload`: sửa Python chỉ có hiệu lực sau khi restart bằng `sudo` (bước 7). Bench `site_config.json` được đọc lại mỗi request nên bật cờ không cần restart, nhưng vẫn restart một lần ở bước 7 cho chắc (mã mới đã nạp).
- Site `miyano` đang `developer_mode = 1`. Scheduler của site gửi mail hàng đợi thật (Email Queue không tự hết hạn): đừng để site thử gửi mail ra ngoài (bước 0b).
- Không chạy bộ test `erpnext.access` trên `miyano` cho phần cần workflow thật: các test đó chỉ chạy khi site có `mvl_rbac_test_site: 1` (nếu không sẽ bị skip, "cần site test (Q8)") vì cache workflow trong Redis dùng chung với web thật.

---

## 0. Sao lưu (Bước 0)

```bash
cd /home/miyano/frappe-bench
bench --site miyano backup --with-files
ls -lh sites/miyano/private/backups | tail -5     # ghi lại tên file .sql.gz vừa tạo
```

Xuất riêng các bảng sẽ bị sync/cutover ghi (phục vụ rollback ở bước 9). Lấy tên DB và mật khẩu từ site_config:

```bash
cd /home/miyano/frappe-bench
DB=$(python3 -c "import json;print(json.load(open('sites/miyano/site_config.json'))['db_name'])")
PW=$(python3 -c "import json;print(json.load(open('sites/miyano/site_config.json'))['db_password'])")
OUT=sites/miyano/private/backups/rbac_pre_$(date +%Y%m%d_%H%M).sql
mysqldump --single-transaction -u"$DB" -p"$PW" "$DB" \
  "tabCustom DocPerm" "tabCustom Role" "tabRole Profile" "tabHas Role" "tabUser Permission" \
  "tabWorkflow" "tabWorkflow Document State" "tabWorkflow Transition" "tabUser Type" "tabUser Type Module" \
  "tabRole" "tabProperty Setter" "tabCustom Field" "tabModule Profile" "tabBlock Module" > "$OUT"
ls -lh "$OUT"
```

Nếu `mysqldump` không dùng được với user DB, dùng tài khoản root: `mysqldump -uroot -p "$DB" ...`. Bảng con `Workflow Document State`, `Workflow Transition`, `User Type Module`, `Block Module` được thêm vào danh sách của Bước 0 vì không có chúng thì không khôi phục được workflow, User Type, Module Profile.

Lưu hai tệp sao lưu (bản `bench backup` và file `rbac_pre_*.sql`) ra máy khác. Kiểm tra: `grep -c "INSERT INTO" "$OUT"` lớn hơn 0.

Cũng lưu lại bản chụp trạng thái thời điểm đó (đọc, không ghi):

```bash
bench --site miyano mariadb -e "select count(*) custom_docperm from \`tabCustom DocPerm\`; select count(*) workflows_on from tabWorkflow where is_active=1; select count(*) users_with_profile from tabUser where role_profile_name is not null and role_profile_name<>'';"
```

## 0b. Site thử `erptest` cho UAT và test tích hợp

**[NGƯỜI]** Cần mật khẩu root của MariaDB.

```bash
cd /home/miyano/frappe-bench
bench new-site erptest --db-root-username root --db-root-password '<MẬT_KHẨU_ROOT>' --admin-password '<MẬT_KHẨU_ADMIN_ERPTEST>'
```

**NGAY SAU `new-site`, TRƯỚC khi restore** (`site_config.json` của erptest được giữ nguyên khi restore, vì restore chỉ ghi file này khi chưa có; nên khóa mail và scheduler từ lúc này):

```bash
bench --site erptest set-config mute_emails 1
bench --site erptest set-config pause_scheduler 1
bench --site erptest set-config allow_tests true
bench --site erptest disable-scheduler
bench --site erptest set-config mvl_rbac_test_site 1
```

(Không cần `install-app`: `--force restore` thay cả DB bằng bản của `miyano`, đã có đủ app.) Khôi phục bản sao lưu của `miyano` vào `erptest`:

```bash
bench --site erptest --force restore sites/miyano/private/backups/<TÊN_FILE>-database.sql.gz \
  --with-public-files sites/miyano/private/backups/<TÊN_FILE>-files.tar \
  --with-private-files sites/miyano/private/backups/<TÊN_FILE>-private-files.tar
```

Kiểm tra lại sau restore, **trước mọi lệnh khác** (không dùng `show-config`: lệnh đó in cả `db_password`). Chỉ đặt cờ RBAC ở erptest sau khi các kiểm tra này đạt:

```bash
python3 -c "import json;c=json.load(open('sites/erptest/site_config.json'));print({k:c.get(k) for k in ('mute_emails','pause_scheduler','allow_tests','mvl_rbac_test_site')})"
bench --site erptest execute frappe.utils.scheduler.is_scheduler_disabled      # phải in True
bench --site erptest mariadb -e "select status, count(*) from \`tabEmail Queue\` group by status;"
```

Nếu `is_scheduler_disabled` in ra `False`, chạy lại `bench --site erptest disable-scheduler` (restore ghi đè System Settings.enable_scheduler bằng giá trị của `miyano`; `pause_scheduler` trong site_config vẫn chặn scheduler).

Nếu còn thư `Not Sent` thì chuyển sang `Error` trên erptest (không đụng `miyano`), **trước lần migrate đầu tiên**:

```bash
bench --site erptest mariadb -e "update \`tabEmail Queue\` set status='Error' where status in ('Not Sent','Partially Sent');"
```

(Dùng `Error` vì `Cancelled` không phải giá trị hợp lệ của trường status; hàng đợi chỉ gửi các thư `Not Sent` / `Partially Sent`, nên đưa về `Error` là không còn gửi. Không sửa bảng Email Queue Recipient.)

Tắt các tích hợp gửi ra ngoài trên erptest **trước mọi UAT** (bản restore mang theo cấu hình thật). Lệnh đầu **ghi và commit** vào DB của erptest:

```bash
bench --site erptest execute frappe.db.set_single_value --args "['Fast EInvoice Settings','enabled',0]"
bench --site erptest mariadb -e "select name, request_url from tabWebhook where enabled=1; select name, channel, enabled from tabNotification where enabled=1 and channel<>'Email';"
```

Hai câu `select` (chỉ đọc) phải rỗng: không Webhook nào bật và mọi Notification chỉ dùng kênh Email (kênh Email vẫn bị chặn bởi `mute_emails`). Nếu có dòng, tắt trên erptest bằng Desk (bỏ Enabled) rồi chạy lại.

Đặt cờ RBAC (**chỉ erptest**; tuyệt đối không đặt trên `miyano` ở bước này):

```bash
bench --site erptest set-config mvl_rbac_enabled 1
```

Cách mở erptest trên trình duyệt: `miyano` đang là default_site với `serve_default_site`, nên truy cập theo host sẽ về `miyano`. **Khuyến nghị:** chạy server riêng `bench --site erptest serve --port 8001` (dev server, chỉ để UAT) và mở `http://<máy>:8001`, không đụng cấu hình nginx/supervisor. Cách khác: thêm host entry (`/etc/hosts`: `<IP> erptest`) và truy cập bằng đúng tên `erptest`; cách này cần cấu hình nginx/supervisor nên chỉ dùng khi IT chấp nhận.

Migrate **hai lần** (T45):

```bash
bench --site erptest migrate
bench --site erptest migrate
```

Lần 1 chạy sync RBAC và in các dòng `Audit:`/`Cảnh báo:`. Lần 2 phải không có thay đổi nào của sync: dòng `RBAC sync xong:` có `inserted`/`deleted` bằng 0 hoặc không xuất hiện (các khóa đó chỉ có khi có thay đổi; không có Custom DocPerm nào thêm hoặc xóa). Nếu khác 0, dừng lại và báo lập trình viên; không bật cờ ở `miyano`.

Chạy từng module test, **mỗi lần một lệnh bench** (không bao giờ chạy hai lệnh cùng lúc: sẽ deadlock):

```bash
cd /home/miyano/frappe-bench
# cần allow_tests=true (đã đặt ở trên)
for t in erpnext.access.tests.test_assign_share erpnext.access.tests.test_audit_mail \
  erpnext.access.tests.test_bank_account_guard erpnext.access.tests.test_cells \
  erpnext.access.tests.test_contract_scope erpnext.access.tests.test_cutover \
  erpnext.access.tests.test_docperm_sync erpnext.access.tests.test_expand \
  erpnext.access.tests.test_kich_ban_bao_cao erpnext.access.tests.test_kich_ban_he_thong \
  erpnext.access.tests.test_kich_ban_quyen erpnext.access.tests.test_kich_ban_workflow \
  erpnext.access.tests.test_matrix erpnext.access.tests.test_matrix_data \
  erpnext.access.tests.test_matrix_sweep erpnext.access.tests.test_pricing_guard \
  erpnext.access.tests.test_profiles erpnext.access.tests.test_schema erpnext.access.tests.test_scope \
  erpnext.access.tests.test_settings erpnext.access.tests.test_sync erpnext.access.tests.test_temp_profiles \
  erpnext.access.tests.test_ui_roles erpnext.access.tests.test_validate \
  erpnext.access.tests.test_workflow_guard erpnext.access.tests.test_workflows \
  erpnext.einvoice.tests.test_einvoice_roles erpnext.warehouse_operations.tests.test_vai_tro_pda \
  erpnext.supply_notification.tests.test_resend_roles erpnext.regional.vietnam.tests.test_go_live \
  erpnext.setup.doctype.mvl_approval_limits.test_mvl_approval_limits; do
  if bench --site erptest run-tests --module $t > /tmp/rbac_test_$t.log 2>&1; then echo "OK   $t"; else echo "FAIL $t (xem /tmp/rbac_test_$t.log)"; fi
done
```

(Vòng lặp chạy tuần tự, mỗi lần một module.) Kiểm tra danh sách còn đủ: `ls apps/erpnext/erpnext/access/tests/test_*.py`.

Mọi module phải xanh và không còn test "skip: cần site test (Q8)", ngoại trừ các kịch bản phụ thuộc hrms (C5/C6), sẽ skip cho tới khi hrms C5/C6 được deploy (bước 3). `test_sync` và `test_workflow_guard` cần `mvl_rbac_test_site` mới chạy phần tích hợp. **T35 (`test_kich_ban_workflow`) cần cutover (remap `workflow_state`) đã chạy trên erptest trước**: chạy cutover thử/thật ở đoạn dưới rồi chạy lại module này nếu lần đầu báo thiếu dữ liệu workflow.

Điền dữ liệu nghiệp vụ trên erptest như bước 2 (và `combined_profiles` như bước 2c), rồi chạy cutover thử, sau đó chạy thật (chỉ trên erptest) theo bước 5:

```bash
bench --site erptest execute erpnext.access.permissions.cutover.run --kwargs "{'dry_run': 1}"
bench --site erptest execute erpnext.access.permissions.cutover.run --kwargs "{'dry_run': 0, 'approved_bank_accounts': ['<Bank Account đã rà>']}"
```

Gán Role Profile thử cho user test (bước 6), rồi để đại diện từng bộ phận làm UAT theo checklist ở bước 8 trên `erptest`. UAT đạt mới sang bước tiếp theo trên `miyano`.

Dọn sau UAT: không cần; `erptest` có thể xóa bằng `bench drop-site erptest --db-root-password '<...>'` khi xong. Không bao giờ bật scheduler hay bỏ `mute_emails` trên `erptest`.

---

## 1. Dọn 2 Company test và Bin âm (Phụ lục A, Bước 0)

Mục đích: Company test `_Test DR Child Acc`, `_Test DR Figures` còn dữ liệu thử; Bin âm chặn việc tắt `allow_negative_stock`.

Kiểm tra (chỉ đọc):

```bash
cd /home/miyano/frappe-bench
bench --site miyano mariadb -e "
select name, creation from tabCompany;
select count(*) bin_am from tabBin where actual_qty < 0;
select item_code, warehouse, actual_qty from tabBin where actual_qty < 0 order by actual_qty limit 50;
select 'GL', count(*) from \`tabGL Entry\` where company in ('_Test DR Child Acc','_Test DR Figures');
select 'SINV', count(*) from \`tabSales Invoice\` where company in ('_Test DR Child Acc','_Test DR Figures');
select 'JE', count(*) from \`tabJournal Entry\` where company in ('_Test DR Child Acc','_Test DR Figures');"
```

- Xóa 2 Company test bằng giao diện (Desk → Company → từng công ty → Menu → Delete). Nếu frappe báo còn liên kết, mở "Linked Documents" và xóa/hủy chứng từ test theo thứ tự (hủy → xóa), hoặc dùng Company → "Delete all Transactions" (nút trên form Company) rồi xóa Company. **[NGƯỜI: kế toán trưởng xác nhận không phải dữ liệu thật trước khi xóa.]** Không dùng `DELETE` SQL trên GL Entry.
- Bin âm: Thủ kho và kế toán kho xử lý từng dòng (nhập bù hoặc Stock Reconciliation). Đạt khi `select count(*) from tabBin where actual_qty < 0` bằng 0.

## 2. Điền `user_scope.json` và H1–H3 (số liệu do doanh nghiệp cung cấp)

**Hai khoản này là quyết định kinh doanh, IT không tự đặt giá trị.** Đưa mẫu cho chủ đầu tư (BGĐ, Kế toán trưởng, Trưởng phòng Mua hàng) điền.

### 2a. `user_scope.json` – phạm vi dữ liệu theo từng user

File `apps/erpnext/erpnext/access/permissions/matrix/user_scope.json`. Hiện là `{"user_scope": {}}`. Khóa là email user; mỗi user liệt kê các giá trị cho loại User Permission cần phạm vi riêng (Warehouse, Price List, Issue Type, Customer, Supplier; xem `user_permission_rules` trong `rules.json`):

```json
{
	"user_scope": {
		"thukho.hn@miyano.com.vn": {"Warehouse": ["Kho Hà Nội - M"]},
		"sale01@miyano.com.vn": {"Customer": ["BV Bắc Ninh"], "Price List": ["Giá bán lẻ"]}
	}
}
```

Giá trị phải là tên bản ghi đang tồn tại trên site (tên không tồn tại bị bỏ qua và ghi vào Audit). User có role cần phạm vi nhưng không có trong file sẽ hiện ở dòng Audit "User chưa có phạm vi trong user_scope". Bảng điền (chủ đầu tư):

| User (email) | Warehouse | Price List | Issue Type | Customer | Supplier |
|---|---|---|---|---|---|
| ... | ... | ... | ... | ... | ... |

### 2b. Hạn mức H1–H3 (DocType đơn `MVL Approval Limits`)

Mặc định 0. Giá trị 0 nghĩa là chưa đặt hạn mức; guard đòi duyệt cao hơn. Nhập tại Desk → `MVL Approval Limits` (search), hoặc:

```bash
cd /home/miyano/frappe-bench
bench --site miyano execute frappe.client.set_value --kwargs "{'doctype':'MVL Approval Limits','name':'MVL Approval Limits','fieldname':{'h1':<số>,'h2':<số>,'h3':<số>}}"
```

- **H1** – PO nhân viên Mua hàng tự duyệt (VND).
- **H2** – PO trưởng phòng Mua hàng duyệt; vượt H2 lên BGĐ.
- **H3** – chi tiền, chi phí do Kế toán duyệt; vượt thì lên cấp cao hơn.

Cần: H1 ≤ H2. Người điền và ngày xác nhận ghi vào biên bản. Sau khi nhập, lưu lại giá trị đã duyệt vào hồ sơ go-live. (Doctype đơn này được tạo khi `bench migrate` chạy lần đầu; trên `miyano` nhập sau bước 4 nếu form chưa có.)

### 2c. `combined_profiles` – profile ghép cho user assetcore

Sync chỉ dựng profile ghép `RP-<x>+AC-<assetcore>` cho các cặp **liệt kê** trong `combined_profiles` của `apps/erpnext/erpnext/access/permissions/matrix/roles.json` (hiện là `[]`, chờ quyết định D19). Sync **không** tự suy ra từ Role Profile assetcore hiện có của user. Trước bước 4, với mọi user cần cả quyền ERP lẫn assetcore, thêm cặp:

```json
"combined_profiles": [
	{"erp": "RP-IT-QT", "assetcore": "Quản trị viên IT"}
]
```

`assetcore` là tên Role Profile assetcore **chính xác** trên site (`select name from \`tabRole Profile\` where name not like 'RP-%';`). Cặp có Role Profile assetcore không tồn tại sẽ bị bỏ qua kèm một dòng cảnh báo. Sau đó chạy sync (bước 4); tên profile ghép tạo ra dạng `RP-IT-QT+AC-Quản trị viên IT`, gán ở bước 6.

## 3. hrms C5/C6 phải lên trước

Làm theo `docs/rbac/BanGiao_C5_C6_hrms.md` mục 6. Tóm tắt thứ tự:

1. Người phụ trách fork hrms sửa C5, C6, chạy test hrms, commit trong repo hrms.
2. Deploy hrms lên site và `bench --site miyano migrate` để áp schema Business Trip (có `Đã hủy`, `no_copy`).
3. Deploy erpnext RBAC **khi cờ còn tắt**; migrate hai lần (T45).
4. Chỉ sang bước 4 dưới đây khi T45, T53 và vế Amend của T34 đạt.

C5 có hiệu lực ngay khi hrms được deploy (HR User, System Manager mất quyền bypass Attendance Request; System Manager mất miễn chấm công): báo trước cho Nhân sự. Lý do thứ tự: `after_migrate` của hrms chạy sau erpnext; không có C6, mỗi lần migrate hrms dựng lại workflow `Cong Tac Approval` kiểu cũ và ghi đè kết quả sync.

## 4. Bật cờ trên `miyano`, migrate, đọc audit

Điều kiện: bước 0–3 xong, UAT trên erptest đạt, có người trực. Làm ngoài giờ làm việc.

```bash
cd /home/miyano/frappe-bench
bench --site miyano set-config mvl_rbac_enabled 1
bench --site miyano migrate 2>&1 | tee /tmp/rbac_migrate_$(date +%Y%m%d_%H%M).log
```

(Nếu muốn chạy sync mà không migrate: `bench --site miyano execute erpnext.access.permissions.sync.run`. Lệnh này ném lỗi nếu ma trận sai; `after_migrate` thì chỉ in lỗi và hoàn tác phần RBAC để hook của hrms/assetcore vẫn chạy.)

Đọc kết quả. Dòng cần thấy: `RBAC sync xong: {...}`. Nếu thấy `RBAC matrix lỗi` hoặc `RBAC sync lỗi, đã hoàn tác`: không đi tiếp, gửi log cho lập trình viên (cờ tắt lại bằng `bench --site miyano set-config mvl_rbac_enabled 0`).

Đọc từng dòng `Cảnh báo:` và `Audit:` (danh sách chỉ để rà, sync không tự sửa):

- Employee thiếu `user_id`, `leave_approver`, `expense_approver`; nhân viên chưa có người duyệt ca; Department chưa có approver; người duyệt chưa có profile chứa TBP; `approver_coo` của Business Trip không có AP.
- User nội bộ chưa có Role Profile (sẽ hết ở bước 6); user có AssetCore Super Admin ngoài IT-QT; bản ghi Authorization Rule.
- Report đang khóa; trường perm level > 0 chưa khai báo; profile ghép lệch; User chưa có phạm vi trong user_scope; nhân viên chưa có `reports_to` (đúng 1 gốc là hợp lệ).
- `DocType tạo tay trên site (custom), ngoài ma trận`: DocType tạo bằng Desk trên site đó. Sync không đụng tới quyền của nó (giữ DocPerm đang có). Mở DocType đó và thêm role `MVL *`/role chuẩn cho người cần dùng, vì sau cutover user chỉ còn role của `RP-*`. Report của ma trận không có trên site cũng chỉ là cảnh báo (`R-REPORT`, bỏ qua).
- Cảnh báo page: page của frappe (ví dụ `team-updates`) có role chuẩn ngoài ma trận: ghi nhận, chấp nhận (frappe hợp role chuẩn với Custom Role của page).

Xử lý dữ liệu thiếu trên Employee/Department rồi chạy lại `bench --site miyano execute erpnext.access.permissions.sync.run` cho tới khi Audit chỉ còn các mục chấp nhận được. Chạy lại phải idempotent.

## 5. Cutover: dry-run, đọc, rồi chạy thật

**Cửa sổ bảo trì (bước 5 + 6 là MỘT lần).** Cutover thật (`dry_run=0`) gỡ ngay các role cũ khỏi user, nên cho tới khi bước 6 gán `RP-*` xong thì các user đó mất quyền. Vì vậy: UAT trên erptest đã ký duyệt trước; bảng user → profile đã đủ; những người gán profile có mặt; bật bảo trì suốt cửa sổ:

```bash
bench --site miyano set-maintenance-mode on
# ... bước 5 (cutover thật) và bước 6 (gán profile), rồi kiểm tra user không còn thiếu profile ...
bench --site miyano set-maintenance-mode off
```

Dry-run (không ghi) có thể làm trước ngoài cửa sổ.

**Phải phê duyệt Bank Account trước khi cờ có tác dụng với thanh toán.** H3 chặn mọi Payment Entry dùng Bank Account chưa ở trạng thái `Đã duyệt`. **[NGƯỜI: Kế toán trưởng/AM rà danh sách Bank Account đang dùng và chốt tên.]**

```bash
cd /home/miyano/frappe-bench
bench --site miyano mariadb -e "select name, bank, account_name, workflow_state from \`tabBank Account\`;"
```

Chạy thử (không ghi gì):

```bash
bench --site miyano execute erpnext.access.permissions.cutover.run --kwargs "{'dry_run': 1}"
```

Mỗi dòng bắt đầu `[dry-run]`: tắt workflow `MVL Duyệt thanh toán`, xóa `SO Test Workflow` (không phục hồi được ngoài bản sao lưu), gán `workflow_state` cho chứng từ cũ (Leave Application theo `status`: Approved → Đã duyệt, Rejected → Từ chối; chứng từ hủy → Đã hủy), xóa User Type `Employee Self Service`, gỡ/tắt role cũ, xóa 6 Role Profile ERP cũ (Inventory, Manufacturing, Accounts, Sales, Purchase, HR) và Role Profile VN cũ. Dòng `skip:` nghĩa là còn user dùng (User Type ESS còn user giữ; profile còn user giữ), xử lý ở bước 6 rồi chạy lại. Dòng `note: N Bank Account chưa duyệt` nhắc truyền `approved_bank_accounts`.

Đọc kỹ, đối chiếu với số liệu Phụ lục A (Leave Application 25 đã submit/1 hủy, Sales Invoice 4/1, Journal Entry 11...). Đồng ý thì chạy thật:

```bash
bench --site miyano execute erpnext.access.permissions.cutover.run --kwargs "{'dry_run': 0, 'approved_bank_accounts': ['<tên Bank Account 1>', '<tên Bank Account 2>']}"
```

Lệnh idempotent; chạy lại sau khi gán profile (bước 6) để gỡ nốt User Type ESS, role và profile cũ vừa hết người dùng. WF-BT (`Cong Tac Approval`) không bị cutover đụng: sync đã sửa tại chỗ.

**Gỡ System Manager khỏi các page PDA** (frappe hợp role chuẩn của page với Custom Role nên Custom Role không khóa được; role chuẩn của page nằm trong `Has Role`). File JSON của 4 page **cố ý vẫn còn System Manager** (xóa khỏi JSON trước go-live sẽ cắt quyền SYS hiện tại), nên việc gỡ ở đây chỉ là SQL trên DB:

```bash
bench --site miyano mariadb -e "
select parent, role from \`tabHas Role\` where parenttype='Page' and parent in ('lay-hang-pda','xep-hang-pda','quet-ma-tra-cuu','dat-o-hang-loat') order by parent, role;"
```

Nếu còn dòng `System Manager`: xóa bằng Desk (Page → từng page → bỏ dòng System Manager trong bảng Roles → Save), hoặc:

```bash
bench --site miyano mariadb -e "
delete from \`tabHas Role\` where parenttype='Page' and role='System Manager'
  and parent in ('lay-hang-pda','xep-hang-pda','quet-ma-tra-cuu','dat-o-hang-loat');"
bench --site miyano clear-cache
```

Chạy lại câu `select`: không còn `System Manager`. `migrate` chỉ nạp lại một page khi `modified` trong JSON của page đổi, nên **kiểm tra lại các dòng này sau mỗi lần migrate có kèm thay đổi page**. Việc cần lên kế hoạch sau go-live: sửa code gỡ System Manager khỏi 4 file JSON (tăng `modified`). Role còn lại hợp lệ: Stock Manager, Stock User; `MVL Kho PDA` có ở `lay-hang-pda`, `xep-hang-pda`, `quet-ma-tra-cuu` nhưng **không** có ở `dat-o-hang-loat`.

## 6. Gán Role Profile cho từng user

**[NGƯỜI]** Bảng user → profile do chủ đầu tư điền trước ngày go-live. Các Role Profile `RP-*` do sync tạo (không tự tạo tay). Mẫu bảng:

| User (email) | Role Profile | Ghi chú |
|---|---|---|
| ... | RP-KHO-TK | Thủ kho |
| ... | RP-IT-QT+AC-Quản trị viên IT | User đang có role assetcore: dùng profile ghép |

- User chỉ dùng ERP: chọn đúng một `RP-*`.
- User đang có role assetcore (khoảng 11 user chỉ có role assetcore, các tài khoản kỹ thuật): dùng **profile ghép `RP-*+AC-*`** (tên dạng `RP-IT-QT+AC-Quản trị viên IT`; chỉ tồn tại nếu cặp đã được khai trong `combined_profiles`, bước 2c) để không mất role assetcore. Không gán `RP-*` thường cho họ vì ghi đè role assetcore.
- Thu hẹp 2 tài khoản quản trị (đang giữ 82–96 role) về `RP-IT-QT` hoặc `RP-BGD-GDVH`. Administrator không đổi.
- Sau khi gán: gỡ role lẻ cũ còn sót; khóa tài khoản không dùng nữa (Desk → User → Enabled = 0).

Gán từng user qua Desk (User → ô Role Profile → Save), hoặc hàng loạt:

```bash
cd /home/miyano/frappe-bench
bench --site miyano console <<'PY'
import frappe
bang = {  # email: Role Profile; chép từ bảng chủ đầu tư điền
    # "a@miyano.com.vn": "RP-KHO-TK",
}
for email, profile in bang.items():
    u = frappe.get_doc("User", email)
    u.role_profile_name = profile
    u.save()
frappe.db.commit()
PY
```

Rồi chạy lại sync để dựng User Permission theo profile và đối chiếu Audit, rồi cutover lần nữa:

```bash
bench --site miyano execute erpnext.access.permissions.sync.run
bench --site miyano execute erpnext.access.permissions.cutover.run --kwargs "{'dry_run': 1}"
bench --site miyano execute erpnext.access.permissions.cutover.run --kwargs "{'dry_run': 0}"
bench --site miyano mariadb -e "select name from tabUser where enabled=1 and user_type='System User' and (role_profile_name is null or role_profile_name='');"
```

Câu cuối phải trả về rỗng (trừ Administrator/Guest).

## 7. Restart (bằng người có sudo)

**[NGƯỜI có sudo]** Claude và tài khoản vận hành thường không có quyền này:

```bash
sudo supervisorctl restart frappe-bench-web: frappe-bench-workers:
sudo supervisorctl status
```

Cả hai nhóm phải `RUNNING`. Sau đó:

```bash
cd /home/miyano/frappe-bench
bench --site miyano clear-cache
```

Việc này nạp mã Python mới vào gunicorn `--preload` và làm worker nhận cờ/hook RBAC. Trước restart, người dùng đang mở form có thể thấy hành vi cũ.

## 8. Checklist UAT (trên `erptest` trước, trên `miyano` sau cutover)

Mỗi dòng: dùng một user thật của bộ phận, kết quả đúng như mô tả; ghi Đạt/Không đạt, người kiểm, ngày.

**Kiểm tra chung**

- [ ] **T08** – user PDA (`RP-KHO-PDA`) đăng nhập; mở `/app/sales-invoice` và `/app/stock-balance`. Đúng: chỉ thấy workspace Quản lý kho và 3 trang PDA; hai đường dẫn kia bị chặn.
- [ ] **T46b** – user PDA sửa đơn giá trên Delivery Note khi lấy hàng. Đúng: bị chặn (Maintain Same Rate = Stop).
- [ ] **T49** – nhân viên mở form Leave Application, chọn người duyệt; Trưởng bộ phận giao Task cho đồng nghiệp. Đúng: danh sách user hiện ra (dòng `Desk User` select trên User được giữ).
- [ ] T45 – migrate hai lần, lần 2 `inserted 0, deleted 0`, workflow `Cong Tac Approval` không bị hrms ghi đè.
- [ ] System Manager không còn vào được page PDA (`/app/lay-hang-pda`, `/app/xep-hang-pda`, `/app/quet-ma-tra-cuu`, `/app/dat-o-hang-loat`).

**Một kịch bản cho mỗi bộ phận**

- [ ] Mua hàng (RP-MH-NV, RP-MH-TP): nhân viên tạo PO ≤ H1 tự duyệt; PO > H1 lên Trưởng phòng; PO > H2 lên BGĐ; người tạo không tự duyệt PO của mình.
- [ ] Kinh doanh (RP-KD-NV, RP-KD-TP): tạo Sales Order, Quotation; chỉ thấy khách hàng trong phạm vi `user_scope`; không thấy giá vốn.
- [ ] Kho (RP-KHO-TK, RP-KHO-TP, RP-KHO-PDA): nhập/xuất kho đúng Warehouse được gán; Stock Reconciliation đi qua Chờ KTT; user PDA quét và xếp hàng được trên page PDA.
- [ ] Kế toán (RP-KT-NV, RP-KT-KTT): duyệt Payment Entry với Bank Account đã duyệt; Payment Entry dùng Bank Account chưa duyệt bị chặn (H3); Journal Entry đi qua WF-JE; không sửa được chứng từ ở trạng thái khóa.
- [ ] Nhân sự (RP-NS-NV, RP-NS-TP): duyệt Leave Application, Attendance Request, Shift Request; tạo Business Trip; Salary Slip chỉ HR/AM thấy; nhân viên chỉ xem phiếu lương của mình.
- [ ] Trưởng bộ phận: chỉ duyệt đơn nghỉ/ca/công tác của cấp dưới `reports_to`; Business Trip chỉ `approver_coo` được Duyệt/Từ chối.
- [ ] BGĐ/GĐVH (RP-BGD-GDVH, RP-BGD-GD): duyệt PO vượt H2, xem báo cáo; không có quyền admin hệ thống.
- [ ] IT (RP-IT-QT): quản user và role; không có quyền nghiệp vụ tài chính; user assetcore vẫn dùng được assetcore (profile ghép).
- [ ] Nhân viên thường (RP-NV): chỉ xem hồ sơ và phiếu lương của chính mình (H8).

Sau UAT trên `miyano`, người kiểm tra gửi biên bản; còn mục "Không đạt" thì đưa vào rollback (bước 9) hoặc sửa ma trận rồi sync lại.

## 9. Rollback

Chọn mức nhẹ nhất đủ dùng.

**9a. Tắt cờ (hoàn tác hành vi mã, không hoàn tác dữ liệu):**

```bash
cd /home/miyano/frappe-bench
bench --site miyano set-config mvl_rbac_enabled 0
```

Tắt cờ chỉ tắt hook và các guard. **Không** tắt các workflow RBAC đã tạo và không xóa Custom DocPerm; workflow vẫn điều khiển nút duyệt của form. Vì vậy phải làm tiếp 9b.

**9b. Tắt các workflow RBAC.** Có 21 workflow do sync tạo (tên theo `workflows.workflow_name`: `<mã> <DocType>`; WF-BT dùng tên cố định `Cong Tac Approval`):

```bash
bench --site miyano mariadb -e "
update tabWorkflow set is_active = 0 where name in (
 'WF-PO Purchase Order','WF-SO Sales Order','WF-SI Sales Invoice','WF-PI Purchase Invoice',
 'WF-PE Payment Entry','WF-JE Journal Entry','WF-SE Stock Entry','WF-SR Stock Reconciliation',
 'WF-BA Bank Account','WF-LA Leave Application','WF-LA Shift Request',
 'WF-AR Attendance Request','WF-AR Compensatory Leave Request',
 'WF-EC Expense Claim','WF-EC Employee Advance','WF-PAY Payroll Entry',
 'WF-HR Salary Structure Assignment','WF-HR Employee Promotion','WF-HR Employee Transfer','WF-HR Job Offer',
 'Cong Tac Approval');
select name, is_active from tabWorkflow where name like 'WF-%' or name='Cong Tac Approval';"
bench --site miyano clear-cache
```

Mọi dòng phải `is_active = 0`. (Kiểm tra danh sách tên với `select name from tabWorkflow where name like 'WF-%'`; tên thật của site là chuẩn.) Workflow legacy `MVL Duyệt thanh toán` đã bị cutover tắt: bật lại nếu cần (`update tabWorkflow set is_active=1 where name='MVL Duyệt thanh toán';`). `SO Test Workflow` đã xóa, chỉ phục hồi từ bản sao lưu.

Phải **cả hai** (9a và 9b): chỉ tắt cờ thì workflow RBAC còn bật; chỉ tắt workflow thì guard còn chạy.

**9c. Restart (bước 7)** để web/worker bỏ trạng thái cũ. Với WF-BT: hrms sẽ dựng lại workflow cũ ở lần migrate sau nếu workflow bị xóa; tắt (`is_active=0`) thì hrms không dựng lại.

**9d. Nếu cần khôi phục các bảng đã xuất ở Bước 0** (mất mọi thay đổi quyền/role sau thời điểm sao lưu, kể cả user được gán profile sau đó): **[NGƯỜI]** chốt trước. Bật bảo trì suốt lúc khôi phục.

```bash
cd /home/miyano/frappe-bench
bench --site miyano set-maintenance-mode on
bench --site miyano set-config mvl_rbac_enabled 0
mysql -u"$DB" -p"$PW" "$DB" < sites/miyano/private/backups/rbac_pre_<NGÀY_GIỜ>.sql
bench --site miyano clear-cache
# restart (bước 7) SAU clear-cache, rồi:
bench --site miyano set-maintenance-mode off
```

Đặt lại `DB` và `PW` như bước 0.

**Khôi phục bảng KHÔNG hoàn tác được:**

- `tabUser.role_profile_name` (bảng User không nằm trong file xuất) vẫn trỏ tới `RP-*` đã không còn. Chỉ khi rollback hoàn toàn, bỏ trỏ cho user đang dùng `RP-%`: `bench --site miyano mariadb -e "update tabUser set role_profile_name=NULL where role_profile_name like 'RP-%';"` (rồi gán lại role cũ cho user bằng Desk theo bản ghi trước cutover).
- `workflow_state` của chứng từ đã được remap; trạng thái Bank Account đã duyệt; User Type `Employee Self Service` đã xóa (bảng User Type có trong dump nên được khôi phục, nhưng không có user nào giữ nó).

Nếu cần phục hồi các thứ này, dùng bản `bench backup` ở bước 0.

**WF-BT khi rollback:** tắt `Cong Tac Approval` (9b) khiến Business Trip không còn workflow. Muốn giữ luồng cũ của Business Trip thì chỉ khôi phục các dòng của workflow đó từ file xuất bước 0 (`tabWorkflow`, `tabWorkflow Document State`, `tabWorkflow Transition` với `name`/`parent` = `Cong Tac Approval`), không khôi phục toàn bảng. Sau rollback, kiểm tra Business Trip: mở một phiếu đang `Chờ COO duyệt` và xác nhận nút duyệt còn hoạt động như trước. File sao lưu có `DROP TABLE` + tạo lại từng bảng; sau đó restart (bước 7). Cột `Custom Field` đã thêm không tự biến mất (vô hại). Nếu hỏng toàn bộ site: `bench --site miyano --force restore <file -database.sql.gz>` từ bản `bench backup` ở bước 0.

## 10. Việc theo sau

- **WF-BT "Đã hủy"** (sau khi hrms C6 đã deploy): trong repo erpnext, thêm vào `WF-BT` trong `erpnext/access/permissions/matrix/workflows.json` state `{"state": "Đã hủy", "doc_status": 2, "allow_edit": "LK"}` và bỏ miễn trừ `WF_NO_CANCEL_YET` trong `validate.py`; chạy `sync.run`. Làm trước C6 thì lưu phiếu hủy báo lỗi Select. Tới khi đó T34 vế Đã hủy còn mở.
- Cập nhật `docs/fast_miyano/go_live_runbook.md` bước 2 sau khi cutover xong.
- Thông báo cho người dùng: đổi quyền, nút duyệt mới, hạn mức H1–H3.

---

## Dọn role và Role Profile dư thừa (tự động mỗi lần migrate)

`erpnext.access.permissions.cleanup` chạy ở đầu `after_migrate` của erpnext trên **mọi** lần `bench migrate`, bật cờ
`mvl_rbac_enabled` hay chưa. Nó chỉ xóa thứ đã chết — không ai dùng, không cấp quyền gì, không app đang cài nào tạo lại:

| Nhóm | Xóa | Điều kiện |
|---|---|---|
| Workflow chết | `SO Test Workflow` (test core `test_sales_order`), `MVL Duyệt thanh toán` (fixture của `mvl_accounting`, app không cài) | không còn liên kết; chứng từ giữ nguyên `workflow_state` và docstatus |
| Workflow RBAC (khi `workflows_enabled: false`) | mọi workflow sync dựng từ `workflows.json` (`WF-PO Purchase Order`, `WF-SO Sales Order`…); `Cong Tac Approval` chỉ khi sync đã sửa nó (có điều kiện G11), hrms tự dựng lại bản gốc ngay trong lần migrate đó. Cột `workflow_state` trong list view được ẩn lại | không còn liên kết; chứng từ đang "Chờ …" thành nháp thường, ai có quyền Submit trên DocType thì submit được |
| Role của app không cài / test | role của `mvl_accounting`, `antmed_crm`, `normcore`/`norm_himedic`, `Test Approver`, `Test Junior Approver`, `Analytics` (danh sách `DEAD_ROLES`) | không còn liên kết nào ngoài user; user đang giữ thì bị gỡ (role không cấp quyền gì) |
| Tên do RBAC sở hữu | role `MVL *` và profile `RP-*` (kể cả profile ghép) mà matrix không còn liệt kê | không user nào giữ |
| Profile cũ | `Inventory`, `Manufacturing`, `Accounts`, `Sales`, `Purchase`, `HR`, các profile phòng ban VN cũ | không user nào giữ |
| Bản thử của test | profile `ZZ-AC-*` | không user nào giữ |
| User test | user có email ở domain test (`example.com/.org/.net/.invalid`, `test.local`, `assetcore.test`) cùng Contact frappe tạo cho họ | không còn liên kết nào (vd. IMM Audit Trail giữ user lại); Contact có gắn đối tác thì giữ |
| Contact mồ côi | Contact email test mà user đã bị xóa (frappe chỉ gỡ liên kết, không xóa Contact) | không gắn đối tác, không bị gì liên kết tới |

Mọi lần xóa chạy kiểm liên kết của frappe trước (`check_if_doc_is_linked`) rồi `delete_doc` không `force`, nên còn bất kỳ
Link nào (DocPerm, Custom DocPerm, Workflow, Workflow Action, Report/Page, profile, user…) thì bản ghi được giữ và in
`skip: … — <liên kết>`. Bản xóa được lưu trong **Deleted Document** (khôi phục được). Role chuẩn của app đang cài
(`retired_roles` trong `rules.json`) không xóa ở đây — import DocType sẽ tạo lại — cutover tắt chúng.

Xem trước (chỉ đọc), rồi chạy thật ngoài lần migrate nếu cần:

```bash
cd /home/miyano/frappe-bench
bench --site miyano execute erpnext.access.permissions.cleanup.run
bench --site miyano execute erpnext.access.permissions.cleanup.run --kwargs "{'dry_run': 0}"
```

Dry-run không xóa thật, nên thứ chỉ được giải phóng sau một bước xóa trước (`Test Approver` sau khi xóa
`SO Test Workflow`) hiện là `skip` trong bản xem trước; lần chạy thật xóa được.

Error Log `snqtg9mldg` (test ghi log ngày 2026-10-23) không thuộc phạm vi tự động — xóa tay một lần:
`bench --site miyano execute frappe.delete_doc --args "['Error Log', 'snqtg9mldg']"`.

Lần đầu trên `miyano` (2026-10-26) lần dọn mất khoảng 2 phút (4.124 Contact mồ côi); các lần sau chỉ vài giây.
Test nào gọi `sync.after_migrate` phải patch `sync._cleanup_roles` (after_migrate có commit).
