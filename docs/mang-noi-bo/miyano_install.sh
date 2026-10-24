#!/usr/bin/env bash
# =====================================================================
#  Cài "Mạng nội bộ Miyano" (Gameplan - nhánh miyano-v15) vào ERP Frappe v15
#  Chạy bằng user sở hữu bench (vd: mvl), KHÔNG chạy bằng root.
#
#  Cách dùng:
#    bash miyano_install.sh [NGUỒN]
#  NGUỒN (tùy chọn):
#    - URL git:   https://github.com/mvl26/gameplan   (mặc định)
#    - file bundle: /đường/dẫn/gameplan-miyano-v15.bundle
#  Biến môi trường: BENCH_DIR (mặc định ~/frappe-bench), SITE (mặc định miyano)
# =====================================================================
set -euo pipefail

BENCH_DIR="${BENCH_DIR:-$HOME/frappe-bench}"
SITE="${SITE:-miyano}"
SRC="${1:-https://github.com/mvl26/gameplan}"
BRANCH="miyano-v15"

cd "$BENCH_DIR"
echo "== Bench: $BENCH_DIR | Site: $SITE | Nguồn: $SRC"

echo "== 1/6 Sao lưu site (database + tệp) trước khi cài..."
bench --site "$SITE" backup --with-files

echo "== 2/6 Tải mã nguồn app gameplan (nhánh $BRANCH)..."
if [ -d apps/gameplan ]; then
	echo "   apps/gameplan đã có sẵn -> bỏ qua bước tải."
else
	if [[ "$SRC" == *.bundle ]]; then
		TMP_SRC="$(mktemp -d)/gameplan"
		git clone -b "$BRANCH" "$SRC" "$TMP_SRC"
		bench get-app --skip-assets gameplan "$TMP_SRC"
	else
		bench get-app --skip-assets --branch "$BRANCH" gameplan "$SRC"
	fi
fi

echo "== 3/6 Cài app vào site..."
if bench --site "$SITE" list-apps | grep -q "^gameplan"; then
	echo "   Đã cài -> chạy migrate để cập nhật."
	bench --site "$SITE" migrate
else
	bench --site "$SITE" install-app gameplan
fi

echo "== 4/6 Liên kết giao diện đã build sẵn (không cần Node/RAM để build)..."
bench build --app gameplan

echo "== 5/6 Tạo không gian 'Miyano Việt Nam', 5 nhóm, đồng bộ nhân sự từ HR..."
bench --site "$SITE" execute gameplan.miyano.setup.setup_miyano

echo "== 6/6 Khởi động lại dịch vụ..."
bench restart || echo "   (Nếu dùng supervisor/systemd riêng, hãy tự khởi động lại web & worker.)"

echo
echo "XONG. Mở https://erp.miyano.com.vn/g (hoặc mục 'Mạng nội bộ' ngay dưới Trang chủ trên ERP)."
