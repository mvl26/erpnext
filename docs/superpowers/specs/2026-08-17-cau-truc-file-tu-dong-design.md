# Cấu trúc file tự động — nắn AI ngay lúc gõ sai đường dẫn

> Trạng thái: **DRAFT — chờ duyệt.** Giai đoạn Specify.
> Bối cảnh: sau đợt dọn 3 file test lệch chuẩn + 2 file docs ở gốc repo (2026-08-17).

## 1. Mục tiêu & phạm vi

Mọi file do AI tạo trong repo này phải đúng thư mục và đúng quy ước tên, **không phụ thuộc
vào việc AI có nhớ đọc tài liệu hay không**.

Phạm vi: 3 hoạt động (viết code BE, viết test, viết spec) + 6 loại file đặc thù Frappe
(DocType, report, patch, fixture, print format, workspace).

**Vấn đề cần giải, nói thẳng:** `CLAUDE.md:76` đã có mục *"Where test files go — mandatory"*,
viết rõ ràng, nằm trong context mọi request. Vậy mà 3 file test vẫn bị đặt sai chỗ và 2 file
tài liệu vẫn nằm ở gốc repo. **Tài liệu thụ động đã được chứng minh là không đủ.** Thiết kế
này không viết thêm chữ để nhắc; nó dựng một cơ chế chặn mà AI không né được.

## 2. Quyết định đã chốt

| # | Quyết định | Chốt bởi |
|---|---|---|
| 1 | Cưỡng chế bằng **hook trong phiên AI**, không phải pre-commit | Người dùng |
| 2 | Phạm vi kiểm: **toàn bộ cây thư mục**, không chỉ test/docs/script | Người dùng (đã nghe cảnh báo báo nhầm) |
| 3 | Luật **suy từ repo hiện tại**, không viết theo lý tưởng | Người dùng |
| 4 | Hình hài: **hook dạy ngay lúc sai**, skill chỉ đóng vai phụ | Người dùng |
| 5 | Kiến trúc **hai lớp tách bạch** (cổng / dạy) | Người dùng — hướng C |
| 6 | **Tối ưu token**: tránh skill thừa, hướng dẫn thừa, task thừa | Người dùng |
| 7 | Tên skill: **`code_structure`** (gạch dưới) | Người dùng, sau khi nghe cảnh báo — xem §8 |

## 3. Kiến trúc hai lớp

Tách vì hai lớp có yêu cầu độ chính xác **khác hẳn nhau**:

**Lớp cổng** — trả lời đúng một bit: *đường dẫn này hợp lệ hay không*. Lớp này quyết định
chặn hay cho qua, nên sai một lần là mất lòng tin và hook sẽ bị tắt. Bắt buộc chính xác tuyệt đối.

**Lớp dạy** — chỉ chạy **sau khi** lớp cổng đã kết luận "sai", trả lời: *vậy đúng là gì*.
Lớp này chỉ sinh chữ, không quyết định chặn. Đoán sai loại file thì lời khuyên chưa trúng,
nhưng không chặn nhầm ai — và AI vẫn thấy danh sách mẫu hợp lệ bên dưới.

Đây chính là lý do chọn hướng C thay vì hướng B (thẻ khuôn thuần): rủi ro "đoán sai loại
file rồi chặn nhầm" bị vô hiệu hoá về mặt kiến trúc, không phải bằng cách cẩn thận hơn.

### Nguyên tắc fail-open

Checker mà tự nó lỗi (exception, thiếu Python, file luật hỏng) thì **exit 0 — cho qua**.
Không bao giờ chặn việc của người dùng vì bug của chính công cụ. Lấy từ prior art
`sdd-cache-pre.sh` đang chạy trên máy này.

### Đường thoát

Hai mức, cho hai tình huống khác nhau:

- `MIYANO_SKIP_FILE_STRUCTURE=1` — tắt hook cho một lệnh hoặc một phiên. Dùng khi gặp ca
  ngoại lệ chính đáng mà bảng luật chưa lường được, cần làm ngay.
- Sửa thẳng bảng luật trong `gate.py` — cách đúng về lâu dài. Bảng để dạng phẳng, dễ đọc,
  sửa xong chạy lại `--audit` là biết có vỡ gì không.

Có đường thoát vì không có nó thì khi bị kẹt, phản ứng tự nhiên là gỡ luôn hook — mất cả hệ thống.

## 4. Ngân sách token

Ràng buộc #6 quyết định chỗ đặt từng mẩu thông tin. Nguyên tắc: **thông tin chỉ tới AI
đúng lúc cần, không sớm hơn.**

| Đường | Tần suất | Xử lý | Chi phí |
|---|---|---|---|
| `CLAUDE.md` | Mọi request, mọi phiên | Cắt còn ~6 dòng trỏ đi, thay mục test ~10 dòng hiện có | **Net âm** |
| Hook lúc đúng | Mỗi Write/Edit | Im lặng tuyệt đối: exit 0, không stdout | **0** |
| Hook lúc sai | Hiếm | ≤12 dòng, chỉ thẻ khuôn liên quan | Thấp |
| Skill `code-structure` | Chỉ khi tạo nhiều file cùng lúc | 1 file ≤100 dòng, không reference file con | Thấp, có chủ đích |

Vì sao hook thắng tài liệu về mặt token: **tài liệu trả tiền mọi lúc, hook chỉ trả tiền lúc sai.**

Vì sao vẫn cần skill: tạo 1 DocType = 4 file. Không có skill thì AI bị chặn 4 lần liên tiếp,
mỗi lần là một round-trip — đắt hơn nhiều so với đọc skill một lần. Nên skill **chỉ** trigger
cho "tạo DocType / report / patch mới". Sửa một file lẻ thì để hook lo, không đụng skill.

## 5. Bản đồ loại file

Suy từ 4.673 file đang tracked. Con số là số file thật khớp mỗi dạng.

| Loại | Mẫu đường dẫn | Số file |
|---|---|---|
| `doctype` | `erpnext/<mod>/doctype/<snake>/<snake>.{py,json,js}` | 2.439 |
| `doctype-test` | `erpnext/<mod>/doctype/<snake>/test_<snake>.py` — **ngoại lệ framework** | ↑ |
| `doctype-data` | `erpnext/<mod>/doctype/<dt>/<subdir>/**` (vd `chart_of_accounts/`) | 108 |
| `report` | `erpnext/<mod>/report/<snake>/<snake>.{py,json,js}` | 799 |
| `report-test` | `erpnext/<mod>/report/<snake>/test_<snake>.py` — **ngoại lệ framework** | ↑ |
| `report-shared` | `erpnext/<mod>/report/<file>.py` (helper dùng chung) | 5 |
| `module-test` | `erpnext/<mod>/tests/test_*.py` + `__init__.py` (Accounts dùng `test/`) | 54 |
| `subpkg-test` | `erpnext/<mod>/<sub>/tests/test_*.py` | 12 |
| `module-code` | `erpnext/<mod>/<file>.py` | 66 |
| `subpkg-code` | `erpnext/<mod>/<sub>/<file>.py` (vd `regional/vietnam/`) | 41 |
| `patch` | `erpnext/patches/v15_0/<động từ>_<danh từ>.py` + dòng trong `patches.txt` | 375 |
| `fixture` | `erpnext/<mod>/<fixture_kind>/<snake>/<snake>.json` | 324 |
| `app-subsystem` | `erpnext/{public,templates,www,translations,startup,config}/**` | 282 |
| `spec` | `docs/superpowers/specs/YYYY-MM-DD-<chủ-đề>-design.md` | — |
| `doc` | `docs/**` (`.md`, và cả `.pdf`/`.csv` tư liệu) | 11 |
| `script` | `scripts/**` — cho phép cả gói con (`scripts/file_structure/`) và `scripts/tests/` | 0 (tạo mới) |
| `repo-root` | Chỉ `README.md`, `CLAUDE.md`, `NOTICE.md` + file cấu hình | 14 |

**Hai ngoại lệ framework — tuyệt đối không được nắn:** `doctype/<dt>/test_<dt>.py` và
`report/<rp>/test_<rp>.py`. Frappe resolve theo đúng đường dẫn này
(`frappe/test_runner.py:209`, `get_module_name(doctype, module, "test_")`). Đặt chỗ khác là
`bench run-tests --doctype "X"` không tìm thấy.

## 6. Hạng mục thực thi

| File | Vai trò |
|---|---|
| `scripts/file_structure/gate.py` | Lớp cổng. Bảng regex precompute sẵn — **không** quét `git ls-files` lúc chạy hook |
| `scripts/file_structure/cards.py` | Lớp dạy. ~14 thẻ khuôn, mỗi thẻ ≤8 dòng |
| `scripts/file_structure/__main__.py` | CLI: `--hook`, `--audit`, `--check <path>` |
| `scripts/tests/test_file_structure.py` | Test cho checker (viết trước, theo TDD) |
| `.claude/skills/code_structure/SKILL.md` | Skill, trigger hẹp: tạo DocType/report/patch mới |
| `.claude/settings.json` | Thêm hook `PreToolUse` khớp `Write\|Edit` |
| `CLAUDE.md` | Thay mục dòng 76-84 bằng ~6 dòng trỏ về script |

Hợp đồng hook (đã xác nhận bằng prior art `sdd-cache-pre.sh` trên máy này): stdin là JSON,
đọc `.tool_input.file_path`; `exit 0` cho qua; `exit 2` chặn và đẩy stderr về cho AI;
có sẵn biến `CLAUDE_PROJECT_DIR`.

## 7. Ngoài phạm vi (cố ý)

- **Không** gắn pre-commit — người dùng đã chọn chặn-trong-phiên. Script vẫn sẵn sàng để gắn
  sau, nhưng lưu ý `pre-commit` hiện **chưa** `install` vào `.git/hooks/` (chỉ có `.sample`),
  nên kể cả gắn cũng chưa chạy cho tới khi chạy `pre-commit install`.
- **Không** chặn theo nội dung file. Quy ước `class TestFoo(FrappeTestCase)` chỉ **cảnh báo**,
  vì có ngoại lệ chính đáng (class helper, test gộp nhiều case) và chặn nhầm sẽ làm mất lòng tin.
- **Không** chặn khi sửa file đã tồn tại. Chỉ chặn lúc **tạo file mới**. Đây là thứ làm cho
  mức "toàn bộ cây thư mục" sống được — không có nó, mỗi lần sửa file upstream là một lần báo nhầm.
- **Không** dùng subagent hay workflow ở bất kỳ đâu trong luồng (ràng buộc #6).
- **Không** dọn ~130 file `README.md` trong các folder doctype. Đó là di sản upstream hợp lệ.

## 8. Ràng buộc kỹ thuật đã xác minh

- **Tên skill dùng gạch dưới là đi ngược quy ước.** `writing-skills/SKILL.md:98` ghi tên skill
  chỉ nên dùng chữ, số và gạch ngang; 26 skill đang cài không cái nào dùng gạch dưới.
  **Người dùng vẫn chọn `code_structure`** sau khi nghe cảnh báo.
  **ĐÃ KIỂM CHỨNG (2026-08-17): tên gạch dưới load bình thường.** Một phiên headless
  (`claude -p`) liệt kê `code_structure` trong danh sách skill khả dụng. Vậy gạch dưới chỉ
  lệch quy ước chứ không hỏng chức năng — cảnh báo ban đầu là thừa. Giữ `code_structure`.
- **`git ls-files` bọc ngoặc kép tên file có dấu tiếng Việt.** Repo có 2 file PDF tiếng Việt
  trong `docs/`. Phải dùng `git ls-files -z` (hoặc `-c core.quotePath=false`), nếu không
  `--audit` sẽ báo nhầm 2 file này.

## 9. Kiểm chứng

Mỗi tiêu chí phải có output lệnh thật, không suy đoán.

1. `--audit` ra **0 vi phạm trên toàn bộ file tracked** (hiện là 4.673). Chưa đạt nghĩa là
   luật sai, không phải repo sai.
2. Test checker chạy xanh: bộ đường dẫn phải-đậu và phải-rớt, gồm cả 2 ngoại lệ framework
   và 5 đường dẫn vừa được sửa trong đợt dọn hôm nay.
3. **Thử hook thật**: cố `Write` một file test sai chỗ → chứng minh bị chặn, và thông báo
   trả về nêu đúng vị trí đích.
4. **Thử fail-open**: làm hỏng file luật → chứng minh hook cho qua chứ không chặn.
5. `CLAUDE.md` sau khi sửa phải **ngắn hơn** trước (đo bằng số dòng và số ký tự).
6. Hook lúc đúng không in gì ra stdout/stderr.
7. **Skill `code_structure` load được thật** — xem §8. Chứng minh bằng việc skill xuất hiện
   trong danh sách skill khả dụng của một phiên mới, không suy đoán từ tên thư mục.

## 10. Rủi ro

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Báo nhầm → người dùng tắt hook | **Cao** | Cổng kiểm chứng 0/4673; chỉ chặn file mới; có biến môi trường bypass |
| Luật trôi lệch khỏi tài liệu | Trung bình | `CLAUDE.md` và skill **trỏ về** script, không chép lại bảng luật |
| Bảng luật lỗi thời khi repo thêm dạng mới | Trung bình | `--audit` chạy lại được bất cứ lúc nào; thêm dạng là sửa một bảng |
| Lớp dạy đoán sai loại file | Thấp | Theo kiến trúc, đoán sai không gây chặn nhầm |
| Bug trong checker chặn oan | Thấp | Fail-open |

## 11. Thứ tự thực thi

1. Test cho checker (đỏ trước)
2. Lớp cổng + bảng luật → chạy `--audit` tới khi 0/4673
3. Lớp dạy (thẻ khuôn)
4. CLI `--hook`, thử tay
5. Gắn hook vào `.claude/settings.json`, thử chặn thật
6. Skill `code-structure`
7. Cắt ngắn `CLAUDE.md`
8. Chạy lại toàn bộ mục §9
