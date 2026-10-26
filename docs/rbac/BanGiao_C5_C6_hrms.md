# Bàn giao C5, C6 cho người phụ trách fork hrms

Ngày lập: 2026-10-23. Nguồn: `TK_01_PhanQuyen_ERP_V2.1_AI.md` mục 3.2, 9.3 (WF-BT, ghi chú 3 và 5), 9.4, 11.4; kế hoạch R-14.
Số dòng dưới đây là hiện trạng của `apps/hrms` ngày 2026-10-23 (đã đọc, không sửa). Nếu file đã đổi, tìm theo đoạn code trích.

## 1. Vì sao cần

Bên erpnext đang triển khai phân quyền RBAC (package `erpnext/access`, cờ `mvl_rbac_enabled`). Khi bật cờ, người duyệt công tác và đơn chấm công được cấp theo role mới (`MVL Approver`, `HR Manager`), còn System Manager chỉ còn quyền xem nghiệp vụ. Không có C5, C6 thì ở hrms:

- System Manager và HR User vẫn submit được mọi Attendance Request, và System Manager vẫn chạy được miễn chấm công, nên quyền vượt mức vẫn còn.
- Mỗi lần `bench migrate`, `after_migrate` của hrms (chạy sau erpnext) tạo lại role COO. Nếu workflow `Cong Tac Approval` không còn, hrms dựng lại bản cũ với role COO (code hrms chỉ có HR User, COO, HR Manager; System Manager hay AssetCore Super Admin nếu có là ở workflow cũ trên site, không phải do code hrms). Bản dựng lại cũng chưa có điều kiện `approver_coo`.
- Business Trip không có state `Đã hủy` trong Select `workflow_state`, và `workflow_state` thiếu `no_copy`. Hủy rồi Amend thì phiếu mới chép state cũ, frappe báo "Workflow State transition not allowed".

Phạm vi: chỉ repo `apps/hrms` (fork mvl26/hrms). Phía erpnext không sửa hrms.

## 2. C5 – bỏ quyền vượt mức ở Attendance Request và miễn chấm công

### 2.1 `APPROVER_BYPASS_ROLES`

File `hrms/hr/doctype/attendance_request/attendance_request_miyano.py`, dòng 41 (dùng ở dòng 95 trong `is_authorized_approver`, và `guard_submit` ngay sau).

Hiện tại:

```python
APPROVER_BYPASS_ROLES = {"HR Manager", "HR User", "System Manager"}
```

Đổi thành:

```python
APPROVER_BYPASS_ROLES = {"HR Manager"}
```

Lý do giữ HR Manager: bước cuối của WF-AR do HR Manager thực hiện, nên nhóm này phải được `guard_submit` cho qua. Người duyệt thông thường là `custom_approver` (quản lý trực tiếp, điền ở `set_default_approver` dòng 48-54, đọc lại ở dòng 59).

### 2.2 `only_for` ở miễn chấm công

File `hrms/hr/attendance_exempt.py`, hai chỗ:

- dòng 381, hàm `preview_month`
- dòng 391, hàm `generate_for_month`

Hiện tại (cả hai dòng):

```python
	frappe.only_for(("HR Manager", "System Manager"))
```

Đổi thành:

```python
	frappe.only_for(("HR Manager",))
```

(Lưu ý dấu phẩy: `("HR Manager",)` là tuple. `("HR Manager")` là chuỗi, `only_for` vẫn chạy nhưng nên tránh.)

## 3. C6 – Business Trip và workflow tự phục hồi

### 3.1 Bản tự phục hồi workflow

Hai nơi liên quan:

- `hrms/patches/v15_0/setup_cong_tac_workflow.py`, hàm `ensure_workflow` (dòng 23-78). Tạo role COO (dòng 24-27), tạo Workflow State (`STATES`, dòng 8-15), rồi dừng sớm nếu workflow đã có (dòng 41-42), nếu không thì dựng workflow với role `COO` (dòng 62-63) và các transition khác.
- `hrms/setup_vn_defaults.py`, `ensure_defaults` (dòng 35) gọi `ensure_workflow()` ở dòng 37 và trả về khóa `"coo_role"` (dòng 57).

Yêu cầu: khi phải dựng lại workflow, tạo đúng WF-BT của spec 9.3:

- Role `MVL Approver` thay `COO`. Không có System Manager hay AssetCore Super Admin trong bất kỳ transition nào.
- Hai transition từ `Chờ COO duyệt` (Duyệt, Từ chối) có điều kiện `doc.approver_coo == frappe.session.user`.
- Tên state giữ nguyên (`Nháp`, `Chờ COO duyệt`, `COO đã duyệt`, `Đã ra QĐ`, `Hoàn tất`, `Từ chối`). Đã có 4 bản ghi ở COO đã duyệt / Đã ra QĐ, đổi tên sẽ làm lưu phiếu báo lỗi Select.
- Giữ tên workflow `Cong Tac Approval` và giữ `return` sớm khi workflow đã tồn tại (dòng 41-42). Đây là điều kiện để T45 đạt: hrms không bao giờ ghi đè workflow đã có. Hệ quả: trên site đã có workflow, giá trị sync đã sửa (kể cả `allow_edit` = `LK` ở Chờ COO duyệt) được giữ nguyên; bản dựng lại chỉ dùng khi workflow bị xóa hẳn.

Mã đề xuất (thay phần tạo role và transition):

```python
APPROVER_ROLE = "MVL Approver"  # role cấp qua RBAC (erpnext/access); thay cho COO
COND = "doc.approver_coo == frappe.session.user"


def ensure_workflow():
	if not frappe.db.exists("Role", APPROVER_ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": APPROVER_ROLE, "desk_access": 1}).insert(
			ignore_permissions=True
		)
	# ... STATES, ACTIONS giữ nguyên ...
	if frappe.db.exists("Workflow", "Cong Tac Approval"):
		return
	# ... states giữ nguyên ...
			"transitions": [
				{"state": "Nháp", "action": "Gửi duyệt", "next_state": "Chờ COO duyệt", "allowed": "HR User"},
				{
					"state": "Chờ COO duyệt",
					"action": "Duyệt",
					"next_state": "COO đã duyệt",
					"allowed": APPROVER_ROLE,
					"condition": COND,
				},
				{
					"state": "Chờ COO duyệt",
					"action": "Từ chối",
					"next_state": "Từ chối",
					"allowed": APPROVER_ROLE,
					"condition": COND,
				},
				{"state": "COO đã duyệt", "action": "Ra QĐ", "next_state": "Đã ra QĐ", "allowed": "HR Manager"},
				{"state": "Đã ra QĐ", "action": "Hoàn tất", "next_state": "Hoàn tất", "allowed": "HR Manager"},
			],
```

Các state `allow_edit` ở dòng 53-58 giữ như hiện tại, khớp WF-BT (Nháp, Từ chối: HR User; Chờ COO duyệt: bản của erpnext đặt `LK` tức khóa, ở hrms có thể giữ HR User vì sync sẽ sửa tại chỗ). Nếu thêm state `Đã hủy` vào `STATES` (style `Danger`) thì state có sẵn khi sync cần.

Khi đổi, cập nhật `coo_role` trong `ensure_defaults` (dòng 57) thành kiểm tra `APPROVER_ROLE` và sửa các test đang assert khóa này trong `hrms/tests/test_setup_vn_defaults.py`.

### 3.2 `business_trip.json`

File `hrms/hr/doctype/business_trip/business_trip.json`, trường `workflow_state` (dòng 121-130).

Hiện tại:

```json
   "fieldname": "workflow_state",
   "fieldtype": "Select",
   "label": "Trạng thái",
   "options": "\nNháp\nChờ COO duyệt\nCOO đã duyệt\nĐã ra QĐ\nHoàn tất\nTừ chối",
   "default": "Nháp",
   "read_only": 1,
   "allow_on_submit": 1,
```

Đổi thành (thêm `Đã hủy` cuối danh sách, thêm `no_copy`):

```json
   "fieldname": "workflow_state",
   "fieldtype": "Select",
   "label": "Trạng thái",
   "options": "\nNháp\nChờ COO duyệt\nCOO đã duyệt\nĐã ra QĐ\nHoàn tất\nTừ chối\nĐã hủy",
   "default": "Nháp",
   "no_copy": 1,
   "read_only": 1,
   "allow_on_submit": 1,
```

Đồng thời nâng `modified` (dòng 169, hiện `"2026-07-08 00:00:00.000000"`) lên thời điểm sửa, nếu không `bench migrate` không đồng bộ lại schema. Trường `amended_from` ở dòng 157-163 đã có `no_copy`, nên mẫu này khớp.

Sau đó chạy `bench --site <site> migrate` để áp schema.

## 4. Phía erpnext đã làm gì

- Ma trận `erpnext/access/permissions/matrix/workflows.json`, mục `WF-BT` (dòng 1160) áp cho Business Trip. Người tạo: HU. Sáu state giữ đúng tên hiện có, `doc_status` như workflow cũ (Nháp 0, Chờ COO duyệt 0, COO đã duyệt 1, Đã ra QĐ 1, Hoàn tất 1, Từ chối 0). Năm transition: Nháp -> Chờ COO duyệt (HU); Chờ COO duyệt -> COO đã duyệt (Duyệt) và -> Từ chối (cả hai role AP, điều kiện `doc.approver_coo == frappe.session.user`); COO đã duyệt -> Đã ra QĐ và Đã ra QĐ -> Hoàn tất (HM). Trong đó AP = `MVL Approver`, HU = HR User, HM = HR Manager.
- Sync (`erpnext.access.permissions.sync.run`, đăng ký cuối `after_migrate` của erpnext) **sửa tại chỗ** workflow `Cong Tac Approval` (tên cố định `FIXED_NAMES` trong `erpnext/access/permissions/workflows.py:25`), không xóa, không tạo workflow mới.
- Bước validate của sync (`erpnext/access/permissions/validate.py` dòng 286-289, hằng `WF_NO_CANCEL_YET = "WF-BT"`, dòng 17) chỉ **cảnh báo** (không chặn) vì WF-BT chưa có state `Đã hủy` (doc_status 2). Cảnh báo này nói về ma trận WF-BT, không phải danh sách Select của hrms.
- **Việc còn lại bên erpnext sau khi hrms ship C6** (một follow-up trong repo này): thêm vào WF-BT trong `workflows.json` state `{"state": "Đã hủy", "doc_status": 2, "allow_edit": "LK"}` và bỏ miễn trừ `WF_NO_CANCEL_YET`. Lý do: `erpnext/access/workflow_guard.py` `before_cancel` (dòng 350) chỉ chuyển phiếu sang state doc_status 2 khi workflow có state đó; hiện WF-BT không có nên hủy Business Trip không vào `Đã hủy`. Thứ tự: hrms C6 (Select có giá trị `Đã hủy`) trước, rồi mới thêm state vào WF-BT, nếu không lưu phiếu hủy báo lỗi Select.
- Phân vai: C6 sửa **Amend** (`no_copy` làm phiếu mới bắt đầu ở `Nháp`) và làm `Đã hủy` thành giá trị lưu được. Phiếu hủy rơi vào `Đã hủy` cần cả C6 lẫn follow-up erpnext ở trên.

## 5. Test phải chạy

Test của erpnext (trên site test, không dùng site thật):

| Mã | Nội dung | Kỳ vọng |
|---|---|---|
| T34 | Hủy rồi Amend một Business Trip đã duyệt | Phiếu Amend bắt đầu từ `Nháp`, lưu không lỗi (cần C6). Phiếu hủy ở `Đã hủy` chỉ đạt khi có **cả** C6 và follow-up erpnext (state `Đã hủy` trong WF-BT, mục 4); trước đó chỉ kiểm vế Amend |
| T45 | Chạy `bench migrate` hai lần liên tiếp | `after_migrate` của hrms không ghi đè hay khôi phục WF-BT cũ; sync lần hai báo 0 thay đổi (0/0) |
| T53 | Attendance Request: người `custom_approver` duyệt; một trưởng bộ phận khác duyệt | Người được giao duyệt được; người khác bị chặn (`guard_submit`). Phải đi qua API thật (submit bằng session của từng user): `guard_submit` return sớm khi `frappe.flags.in_test` (dòng 106) nên test trong runner không kiểm được |
| T47 | Gán profile ghép RP-IT-QT + AC-Quản trị viên IT, lưu User hai lần | Chỉ liên quan nếu sửa luồng gán role; không cần với C5, C6 thuần |

Test của hrms cần chạy lại (sau sửa):

- `hrms/hr/doctype/attendance_request/test_attendance_request_miyano.py` (C5, `APPROVER_BYPASS_ROLES`)
- `hrms/hr/tests/test_attendance_exempt.py` (C5, `only_for`)
- `hrms/hr/doctype/business_trip/test_business_trip.py` (C6)
- `hrms/tests/test_setup_vn_defaults.py` (C6, `coo_role` và workflow dựng lại)

Test hrms hiện có sẽ **vỡ** sau C6 và phải sửa cùng lúc:

- `hrms/hr/doctype/business_trip/test_business_trip.py`: dòng 15 và 23 dùng role COO; dòng 104, 107 nhắc COO; dòng 114-115 `assertIn("COO", roles["Duyệt"])` và `roles["Từ chối"]` -> đổi sang `MVL Approver`. Mọi test gọi `apply_workflow(doc, "Duyệt")` hoặc `"Từ chối"` phải đặt `approver_coo` = user đang thao tác, vì transition có điều kiện `doc.approver_coo == frappe.session.user`; user đó phải có role `MVL Approver`.
- `hrms/tests/test_setup_vn_defaults.py`: dòng 17-25 assert role COO tồn tại và `summary["coo_role"]`.

Cần thêm test: `System Manager` không submit được Attendance Request của người khác và gọi `preview_month` bị `PermissionError`; workflow dựng lại có role `MVL Approver`, có điều kiện `approver_coo`, không có System Manager.

## 6. Thứ tự triển khai

1. Sửa C5, C6 trong hrms, chạy test hrms ở mục 5, commit trong repo hrms (do người phụ trách repo đó).
2. Deploy hrms lên site, chạy `bench migrate` để áp schema Business Trip.
3. Deploy erpnext với RBAC nhưng **chưa bật** `mvl_rbac_enabled`; chạy migrate hai lần, kiểm T45.
4. Chỉ bật `mvl_rbac_enabled` sau khi T45, T53 và vế Amend của T34 đạt; vế `Đã hủy` của T34 đạt sau follow-up erpnext ở mục 4.

Lưu ý C5 có hiệu lực ngay khi hrms được deploy, trước khi bật cờ erpnext: HR User và System Manager mất quyền bypass submit Attendance Request, System Manager mất quyền chạy miễn chấm công. Báo trước cho bộ phận Nhân sự.

Nếu C5 chưa vào mà đã bật cờ, System Manager mất quyền nghiệp vụ ở erpnext nhưng vẫn vượt quyền ở hrms. Nếu C6 chưa vào, Amend Business Trip vẫn lỗi; nếu thiếu follow-up erpnext, Business Trip hủy không vào `Đã hủy` và sync còn cảnh báo.

## 7. Cảnh báo R-14

`apps/hrms` hiện có **33 file thay đổi chưa commit** (31 sửa, 2 file mới chưa theo dõi) trong working tree, thời điểm sửa file từ 2026-09-23 đến 2026-10-13 (commit gần nhất ngày 2026-09-23). Các thay đổi này không thuộc C5, C6 và không liệt kê ở đây. Trước khi làm:

- Xem `git status` và `git diff` để biết cái nào là của người khác, nhất là các file C5, C6 ở trên có thể đã có sửa dở.
- Tách commit C5, C6 riêng; không gộp, không `git add -A`, không reset hay stash thay đổi chưa commit của người khác.
- Hỏi chủ các thay đổi chưa commit trước khi rebase hoặc đổi nhánh.
- Phía erpnext không sửa và không commit gì trong hrms.
