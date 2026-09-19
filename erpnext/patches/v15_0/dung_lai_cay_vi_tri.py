"""Dựng `lft`/`rgt` lần đầu cho `Storage Location` (spec §7, Task 8, 11/09/2026).

`StorageLocation` kế thừa `NestedSet` từ Task 2 (2026-09-11), nhưng bất kỳ bản
ghi nào được TẠO TRƯỚC thời điểm đó (mã 12 ký tự cũ, hoặc ô hệ thống
`ZZZ-CHUA-XEP-<kho>` tạo qua `bat_kho.tao_o_chua_xep()` trước khi có cây) vẫn
mang `lft = rgt = 0` — không ai gọi lại `on_update()`/`update_nsm()` cho nó kể
từ khi trường tồn tại. Trên `erptest.local`, Task 8 đã xoá 128 ô cũ và sinh
lại + `rebuild_tree()` bằng tay; patch này làm đúng việc đó CHO MỌI SITE
KHÁC (đặc biệt site `miyano`, cài đặt riêng, không tự động thừa hưởng thao
tác tay đã làm trên `erptest.local` — xem `miyano-portal-install-patch-trap`).

VÒNG SỬA 2/5 (review điều phối): patch này CHỈ còn là một LẦN GỌI vào
`erpnext.vi_tri_kho.vitri.cay.dam_bao_cay_da_dung()` — đọc docstring của hàm
đó để hiểu đầy đủ phán quyết F5+F11 (kiểm `disabled` trước khi rebuild) và
vì sao logic không còn nằm hẳn ở đây.

**Vì sao giữ patch này song song với `after_migrate`, không xoá hẳn:** patch
chạy đúng MỘT LẦN, đúng VỊ TRÍ đã khai trong `patches.txt` — với một site CÀI
MỚI, đây là cách duy nhất đảm bảo cây được dựng theo đúng THỨ TỰ so với các
patch xếp SAU nó (patch sau có thể giả định cây đã có toạ độ). `after_migrate`
(`erpnext/hooks.py`) chạy SAU toàn bộ patch của lần migrate đó, nên không thay
được vai trò "đúng thứ tự" này — nó thay vai trò KHÁC: hội tụ LẠI ở mọi lần
migrate sau, việc mà một patch (bị `Patch Log` khoá sau khi chạy một lần) làm
không được. Hai cơ chế bổ sung cho nhau, không thừa: patch lo lần ĐẦU đúng
thứ tự, `after_migrate` lo mọi lần SAU không bị bỏ quên.
"""

from erpnext.vi_tri_kho.vitri.cay import dam_bao_cay_da_dung


def execute():
	dam_bao_cay_da_dung()
