#!/usr/bin/env bash
# Bước ĐÓNG GÓI: chép BẢN DỰNG của giao diện `/kho` vào `pda_app/www/` để app mở
# lên là có giao diện sẵn trong máy, không phải tải từ máy chủ.
#
# VÌ SAO CHÉP BẢN DỰNG, KHÔNG CHÉP MÃ NGUỒN: trang `/kho` trên web và app dùng
# CÙNG MỘT `kho_pda.bundle.js`. Có một bản sao mã nguồn thứ hai trong `pda_app/`
# là hai bản giao diện trôi khỏi nhau — rủi ro đã ghi ở §12 của spec. Chép bản
# dựng thì không có cách nào để hai nơi khác nhau: cùng một file, cùng một băm.
#
# VÌ SAO KHÔNG THAY `__MAY_CHU__` NGAY TRONG `pda_app/www/index.html` (khác đoạn
# mẫu của brief Task 1): `index.html` là file ĐƯỢC THEO DÕI trong git. Thay tại
# chỗ thì mỗi lần chạy script này cây làm việc bẩn thêm một địa chỉ máy chủ, và
# lượt dựng của người phát hành sẽ ghi địa chỉ ngrok THẬT vào kho mã nguồn —
# đúng điều ràng buộc "không nhúng địa chỉ máy chủ thật vào mã nguồn kho" cấm.
# Thay vào đó script SINH `pda_app/www/cau-hinh.js` (bị gitignore, giống hai file
# bundle chép vào đây) và `index.html` nạp nó bằng một thẻ `<script src>` tĩnh.
# Rò rỉ địa chỉ thật vì thế là chuyện KHÔNG XẢY RA ĐƯỢC, không phải chuyện phải
# nhớ tránh.
#
# CHẠY:
#   scripts/pda/dong-goi.sh              # dựng lại bundle rồi chép
#   scripts/pda/dong-goi.sh --bo-qua-dung  # chỉ chép (bundle đã dựng sẵn)

set -euo pipefail

GOC_BENCH="/home/hoangvietyeuem/frappe-bench-yhct"
GOC_APP="$GOC_BENCH/apps/erpnext"
WWW="$GOC_APP/pda_app/www"
TEP_CAU_HINH="$GOC_APP/scripts/pda/cau-hinh-may-chu.json"
TEP_GRADLE="$GOC_APP/pda_app/android/app/build.gradle"
THU_MUC_JS="$GOC_BENCH/sites/assets/erpnext/dist/js"
THU_MUC_CSS="$GOC_BENCH/sites/assets/erpnext/dist/css"
BAN_DO_ASSET="$GOC_BENCH/sites/assets/assets.json"
JQUERY_NGUON="$GOC_BENCH/apps/frappe/node_modules/jquery/dist/jquery.min.js"

BO_QUA_DUNG=0
if [ "${1:-}" = "--bo-qua-dung" ]; then
	BO_QUA_DUNG=1
fi

loi() {
	echo "dong-goi.sh: $*" >&2
	exit 1
}

# Tìm bản dựng của MỘT bundle. Tên file mang băm nội dung (`kho_pda.bundle.JSOAH7HH.js`)
# nên không hằng số hoá được — băm đổi mỗi lần nội dung đổi.
#
# NGUỒN CHÍNH là `sites/assets/assets.json`: đó là bảng tra mà CHÍNH Frappe dùng để
# quyết `include_script('kho_pda.bundle.js')` trên trang `/kho` phục vụ file nào. Đọc
# từ đó là cách duy nhất chắc chắn app và web nhận ĐÚNG CÙNG MỘT file — glob thư mục
# chỉ tìm "một file trông giống thế", và `dist/` hoàn toàn có thể còn sót bản băm cũ
# của lần dựng trước mà không ai dọn.
#
# Glob vẫn chạy, làm ĐỐI CHỨNG theo đúng yêu cầu của brief: 0 file khớp là dựng hỏng
# (dừng); nhiều hơn 1 file khớp mà không có bảng tra thì không có cách nào chọn đúng
# (dừng) — có bảng tra thì chỉ cảnh báo và nêu tên các bản thừa để còn dọn.
tim_ban_dung() {
	local khoa="$1" thu_muc="$2" duoi="$3"
	local tu_ban_do="" duong=""

	if [ -f "$BAN_DO_ASSET" ]; then
		tu_ban_do="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2],""))' \
			"$BAN_DO_ASSET" "$khoa")"
	fi

	local -a khop=()
	local f
	shopt -s nullglob
	for f in "$thu_muc"/kho_pda.bundle.*."$duoi"; do
		khop+=("$f")
	done
	shopt -u nullglob

	if [ "${#khop[@]}" -eq 0 ]; then
		loi "không tìm thấy bản dựng nào khớp $thu_muc/kho_pda.bundle.*.$duoi — chạy 'bench build --app erpnext' trước."
	fi

	if [ -n "$tu_ban_do" ]; then
		# `assets.json` giữ đường dẫn URL (`/assets/erpnext/dist/js/...`); gốc của nó
		# trên đĩa là `sites/`.
		duong="$GOC_BENCH/sites${tu_ban_do}"
		[ -f "$duong" ] || loi "assets.json trỏ '$khoa' tới $duong nhưng file đó không có trên đĩa — dựng lại đi."
		if [ "${#khop[@]}" -gt 1 ]; then
			echo "  cảnh báo: $thu_muc còn ${#khop[@]} bản băm của kho_pda.bundle.$duoi;" \
				"dùng bản assets.json trỏ tới ($(basename "$duong")), các bản còn lại là rác của lần dựng cũ." >&2
		fi
		echo "$duong"
		return
	fi

	[ "${#khop[@]}" -eq 1 ] || loi "có ${#khop[@]} bản dựng khớp kho_pda.bundle.*.$duoi và không đọc được assets.json — không đoán được bản nào đang phục vụ."
	echo "${khop[0]}"
}

if [ "$BO_QUA_DUNG" -eq 0 ]; then
	echo "==> bench build --app erpnext"
	(cd "$GOC_BENCH" && bench build --app erpnext)
else
	echo "==> bỏ qua bench build (--bo-qua-dung)"
fi

[ -f "$TEP_CAU_HINH" ] || loi "thiếu $TEP_CAU_HINH"
MAY_CHU="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["may_chu"])' "$TEP_CAU_HINH")"
[ -n "$MAY_CHU" ] || loi "'may_chu' rỗng trong $TEP_CAU_HINH"

# BẢN THỬ HAY BẢN PHÁT HÀNH? So địa chỉ đóng gói với địa chỉ phát hành.
#
# MẶC ĐỊNH NGHIÊNG VỀ "BẢN THỬ": khoá `may_chu_phat_hanh` VẮNG MẶT hoặc RỖNG cũng
# tính là khác. Sự cố đang chặn là thủ kho cầm một bản trỏ máy chủ thử mà không
# biết; một dải cam thừa chỉ gây phiền, một dải cam THIẾU chính là sự cố đó. Dùng
# `.get()` chứ không `["..."]`: `set -e` cộng một `KeyError` là một vệt traceback
# Python thay cho một câu tiếng Việt, và file cấu hình của bản cũ chưa có khoá này.
#
# So trên chuỗi ĐÃ CHUẨN HOÁ (cắt khoảng trắng và dấu `/` ở đuôi) — địa chỉ là thứ
# người phát hành dán tay, một dấu `/` thừa không được biến bản thật thành bản thử.
BAN_THU="$(python3 - "$TEP_CAU_HINH" <<'PY'
import json, sys

cau_hinh = json.load(open(sys.argv[1], encoding="utf-8"))
chuan = lambda s: (s or "").strip().rstrip("/")
print("1" if chuan(cau_hinh.get("may_chu_phat_hanh")) != chuan(cau_hinh.get("may_chu")) else "0")
PY
)"

# PHIÊN BẢN CỦA CHÍNH APP — nguồn duy nhất là `versionName` trong `build.gradle`.
#
# VÌ SAO ĐÚNG CHỖ NÀY chứ không `package.json`: TÊN FILE APK sinh ra từ đúng biến
# ấy (`outputFileName = "miyano-pda-${variant.versionName}-..."` trong cùng file),
# và phía máy chủ chỉ có TÊN FILE để so — `cai_app.ban_cai_moi_nhat` trả về một
# bản ghi `File`, không có ô "phiên bản" nào. Lấy từ `package.json` (đang ghi
# "1.0.0") là so một chuỗi với một chuỗi khác hẳn: dải nhắc sẽ bật lên vĩnh viễn
# ngay cả khi máy đang cầm đúng bản mới nhất.
#
# TRỐNG THÌ KHÔNG SINH BIẾN, và đó là mặt an toàn: `vo.js::ban_app()` trả rỗng →
# không so được → KHÔNG nhắc. Một dải nhắc THIẾU chỉ làm chậm một lượt nâng cấp;
# một dải nhắc SAI dạy thủ kho bỏ qua mọi dải nhắc về sau.
BAN_APP="$(sed -n 's/^[[:space:]]*versionName[[:space:]]*"\([^"]*\)".*/\1/p' "$TEP_GRADLE" | head -1)"
[ -n "$BAN_APP" ] || loi "không đọc được versionName trong $TEP_GRADLE — dải nhắc bản mới sẽ không bao giờ hiện."
# BẮT BUỘC DẠNG `X.Y` (có ít nhất một dấu chấm). Đây là HỢP ĐỒNG với
# `vo.js::_ban_tu_ten_tep`, không phải một sở thích: phía máy chủ chỉ có TÊN FILE
# để so, và tên file người phát hành đặt thường có NGÀY trong đó
# (`miyano-pda-1.0-kho-2026-09-24.apk` — đang nằm trên máy chủ thử). Hàm kia phân
# biệt "số hiệu" với "ngày tháng" bằng đúng dấu chấm. `versionName "2"` sẽ làm cả
# cơ chế nhắc IM LẶNG VĨNH VIỄN mà không một dấu hiệu nào — chặn ngay ở đây, lúc
# còn có người đang nhìn màn hình.
# VÒNG SỬA CUỐI (soát tổng, T6-1) — SIẾT THÀNH ĐÚNG HAI ĐOẠN, mỗi đoạn 1–3 chữ số.
# Trước đây chỉ đòi "có dấu chấm", nên `versionName "1.2.3"` đi lọt — mà phía máy
# chủ KHÔNG phân biệt được `1.2.3` với một ngày viết kiểu `24.09.26`. Hàm rút phiên
# bản (`vo.js::_ban_tu_ten_tep`, `cai_app.py::_phien_ban_tu_ten`) vì thế chỉ nhận
# hai đoạn; một `versionName` ba đoạn sẽ làm cơ chế nhắc IM LẶNG VĨNH VIỄN. Chặn ở
# đây là chặn lúc còn có người đang nhìn màn hình.
if ! printf '%s' "$BAN_APP" | grep -Eq '^[0-9]{1,3}\.[0-9]{1,3}$'; then
	loi "versionName '$BAN_APP' trong $TEP_GRADLE phải là ĐÚNG HAI đoạn số, mỗi đoạn 1-3 chữ số (ví dụ 1.0, 1.10, 2.0). Khuôn này là HỢP ĐỒNG với vo.js::_ban_tu_ten_tep và cai_app.py::_phien_ban_tu_ten — lệch khuôn thì dải nhắc bản mới im lặng vĩnh viễn."
fi

BUNDLE_JS="$(tim_ban_dung "kho_pda.bundle.js" "$THU_MUC_JS" "js")"
BUNDLE_CSS="$(tim_ban_dung "kho_pda.bundle.css" "$THU_MUC_CSS" "css")"

mkdir -p "$WWW/vendor"
# `cp` giữ NỘI DUNG, không phải một liên kết: file trong `www/` phải tự đứng được
# khi Capacitor gói cả thư mục vào APK — một symlink trỏ ra ngoài kho thì trong máy
# quét không còn gì ở đầu kia.
cp -f "$BUNDLE_JS" "$WWW/kho_pda.bundle.js"
cp -f "$BUNDLE_CSS" "$WWW/kho_pda.bundle.css"

# jQuery là SẢN PHẨM ĐƯỢC THEO DÕI của Task 1, không phải bản chép lại mỗi lượt
# dựng: chép đè mỗi lần sẽ âm thầm đổi một file có trong git khi ai đó nâng cấp
# `node_modules` của frappe. Chỉ tự lấy khi THIẾU (máy mới, ai đó lỡ xoá).
if [ ! -f "$WWW/vendor/jquery.min.js" ]; then
	[ -f "$JQUERY_NGUON" ] || loi "thiếu $WWW/vendor/jquery.min.js và không tìm thấy $JQUERY_NGUON để lấy."
	cp -f "$JQUERY_NGUON" "$WWW/vendor/jquery.min.js"
	echo "  đã lấy jquery.min.js từ node_modules của frappe (file này THUỘC kho, không bị gitignore)."
fi

# Ghi bằng một heredoc KHÔNG nội suy cho phần thân, riêng địa chỉ thì chèn qua
# `printf %s` — địa chỉ là dữ liệu từ file JSON, không được để shell diễn giải.
{
	printf '%s\n' '// SINH TỰ ĐỘNG bởi scripts/pda/dong-goi.sh — ĐỪNG sửa tay, lượt đóng gói sau ghi đè.'
	printf '%s\n' '// Địa chỉ máy chủ mà bản đóng gói này gọi tới. Nằm ở file RIÊNG (bị gitignore) chứ'
	printf '%s\n' '// không nằm trong index.html vì index.html được git theo dõi: một lượt dựng của'
	printf '%s\n' '// người phát hành sẽ ghi địa chỉ thật vào kho mã nguồn. Nguồn giá trị:'
	printf '%s\n' '// scripts/pda/cau-hinh-may-chu.json.'
	printf 'window.KHO_MAY_CHU = %s;\n' "$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$MAY_CHU")"
	printf '%s\n' ''
	printf '%s\n' '// PHIÊN BẢN CỦA CHÍNH BẢN CÀI NÀY, lấy từ `versionName` trong'
	printf '%s\n' '// `pda_app/android/app/build.gradle` — cùng biến sinh ra TÊN FILE APK. Màn menu'
	printf '%s\n' '// so nó với tên bản cài mới nhất trên máy chủ để quyết có hiện dải nhắc hay'
	printf '%s\n' '// không (`vo.js::ban_moi_hon`). Thiếu dòng này thì KHÔNG nhắc, không nhắc sai.'
	printf 'window.KHO_BAN_APP = %s;\n' "$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$BAN_APP")"
	if [ "$BAN_THU" = "1" ]; then
		printf '%s\n' ''
		printf '%s\n' '// Địa chỉ đóng gói KHÁC địa chỉ phát hành (hoặc địa chỉ phát hành bỏ trống) —'
		printf '%s\n' '// màn thẻ và màn menu hiện dải cam "BẢN THỬ". Bản phát hành thật (hai địa chỉ'
		printf '%s\n' '// bằng nhau) KHÔNG có dòng này, nên dải đó tự tắt, không ai phải nhớ tắt.'
		printf '%s\n' 'window.KHO_BAN_THU = true;'
	fi
} > "$WWW/cau-hinh.js"

# ============================================================================
# BẢN THỨ BA — `android/app/src/main/assets/public/` (vòng sửa cuối, soát tổng V8)
# ============================================================================
#
# Ba cổng nghiệm thu đều đọc `pda_app/www/`. Nhưng APK KHÔNG đóng gói từ đó — nó
# đóng gói từ `android/app/src/main/assets/public/`, một BẢN THỨ BA mà `npx cap
# sync` chép sang. Cảnh hỏng: sửa giao diện → chạy `dong-goi.sh` → ba cổng XANH →
# `./gradlew assembleRelease` mà QUÊN `npx cap sync` → APK mang bản cũ, kèm một
# chứng nhận xanh đầy đủ. Hôm nay hai bản trùng md5 là MAY, không phải được canh.
#
# CHỌN CHÉP LUÔN, KHÔNG CHỌN "CẢNH BÁO RỒI THÔI", và cũng không gọi `npx cap sync`
# từ đây:
#   · cảnh báo thì vẫn quên được, mà đây là lỗi im lặng — đúng loại phải chặn bằng
#     cấu trúc chứ không bằng trí nhớ;
#   · gọi `npx cap sync` từ script này buộc MỌI lượt chạy cổng phải có Node +
#     `pda_app/node_modules` + (có thể) Android SDK, trong khi ba cổng Playwright
#     chỉ cần `www/`. Một phép `cp` thì không cần gì cả.
# `npx cap sync android` VẪN nằm trong quy trình dựng APK (README §B) — nó còn làm
# việc khác (`capacitor.config.json`, `native-bridge.js`, cập nhật plugin); chạy
# sau bước này thì nó chép lại ĐÚNG những byte vừa chép, không đổi gì.
#
# XOÁ FILE THỪA Ở ĐÍCH: đổi tên một file trong `www/` mà chỉ chép thêm thì bản
# cũ còn nằm lại trong APK.
#
# NHƯNG KHÔNG `rm -rf` CẢ THƯ MỤC — đo được ngay ở lượt đầu: `npx cap sync` TỰ
# SINH `cordova.js` và `cordova_plugins.js` vào đây, hai file KHÔNG có trong
# `www/` và không thuộc về ta. Xoá sạch rồi chép lại là ta vừa xoá sản phẩm của
# một công cụ khác; nó tự sinh lại ở lượt `cap sync` kế tiếp, nhưng ai dựng APK
# mà bỏ qua `cap sync` sẽ được một APK thiếu hai file đó. Giữ nguyên thứ của
# Capacitor, chỉ dọn thứ của ta.
ASSETS_PUBLIC="$GOC_APP/pda_app/android/app/src/main/assets/public"
if [ -d "$(dirname "$ASSETS_PUBLIC")" ]; then
	mkdir -p "$ASSETS_PUBLIC"
	cp -R "$WWW/." "$ASSETS_PUBLIC/"
	python3 "$GOC_APP/scripts/pda/don_assets_public.py" "$WWW" "$ASSETS_PUBLIC"
	echo "    assets/public/     <- đã đồng bộ từ www/ (bản APK sẽ đóng gói)"
else
	echo "    assets/public/     (chưa có dự án android — bỏ qua)" >&2
fi

echo "==> đã đóng gói vào $WWW"
echo "    kho_pda.bundle.js  <- $(basename "$BUNDLE_JS")"
echo "    kho_pda.bundle.css <- $(basename "$BUNDLE_CSS")"
echo "    cau-hinh.js        -> KHO_MAY_CHU = $MAY_CHU"
echo "    cau-hinh.js        -> KHO_BAN_APP = $BAN_APP (versionName trong build.gradle)"
if [ "$BAN_THU" = "1" ]; then
	echo "    cau-hinh.js        -> KHO_BAN_THU = true (dải cam 'BẢN THỬ' SẼ HIỆN — 'may_chu_phat_hanh' khác/rỗng)"
else
	echo "    cau-hinh.js        -> KHO_BAN_THU không sinh (bản PHÁT HÀNH: may_chu == may_chu_phat_hanh)"
fi
