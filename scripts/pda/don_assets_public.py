#!/usr/bin/env python3
"""Dọn file THỪA trong `android/app/src/main/assets/public/` sau khi chép `www/`.

GỌI TỪ `scripts/pda/dong-goi.sh` — xem khối chú thích ở đó để biết vì sao bản thứ
ba này tồn tại và vì sao nó phải được đồng bộ trong CÙNG một lượt với `www/`.

VIỆC CỦA FILE NÀY, nói gọn: `cp -R www/. assets/public/` chỉ THÊM và ĐÈ, nó không
xoá. Đổi tên (hay bỏ hẳn) một file trong `www/` thì bản cũ nằm lại trong
`assets/public/` và đi thẳng vào APK — một file mồ côi mà không cổng nào đọc tới.

VÌ SAO KHÔNG `rm -rf` CẢ THƯ MỤC RỒI CHÉP LẠI (cách ngắn hơn, và là cách bản đầu
đã làm): `npx cap sync` TỰ SINH `cordova.js` + `cordova_plugins.js` vào đây. Đo
được ngay ở lượt chạy đầu tiên — bài
`test_giao_dien.test_task6_www_va_assets_public_khop_tung_byte` đỏ với đúng hai
tên đó. Xoá sạch nghĩa là ta xoá sản phẩm của một công cụ khác: `cap sync` sinh
lại được, nhưng ai dựng APK mà bỏ qua bước đó sẽ có một APK thiếu hai file ấy —
ta vừa tạo ra đúng loại hỏng im lặng mà cả việc này sinh ra để chặn.

DANH SÁCH ĐÍCH DANH, KHÔNG PHẢI MỘT LUẬT MƠ HỒ: bỏ qua đúng những cái tên
Capacitor sở hữu. Bất kỳ file lạ nào khác vẫn bị dọn, và bài test trên vẫn đỏ nếu
có file lạ nào sót lại — "file nào lạ cũng bỏ qua" thì chẳng canh gì nữa.
"""

import os
import sys

#: Do `npx cap sync` sinh ra trong `assets/public/`, không đến từ `www/`.
CUA_CAPACITOR = {"cordova.js", "cordova_plugins.js", "cordova-js-src"}


def don(www: str, dich: str) -> list[str]:
	co_trong_www = set()
	for thu_muc, _, ds in os.walk(www):
		for t in ds:
			co_trong_www.add(os.path.relpath(os.path.join(thu_muc, t), www))

	da_xoa = []
	for thu_muc, _, ds in os.walk(dich):
		for t in ds:
			tuong_doi = os.path.relpath(os.path.join(thu_muc, t), dich)
			if tuong_doi in co_trong_www:
				continue
			# So phần ĐẦU đường dẫn: `cordova-js-src` là một thư mục.
			if tuong_doi.split(os.sep)[0] in CUA_CAPACITOR:
				continue
			os.remove(os.path.join(thu_muc, t))
			da_xoa.append(tuong_doi)
	return da_xoa


if __name__ == "__main__":
	for ten in don(sys.argv[1], sys.argv[2]):
		print(f"    assets/public/     -- đã xoá file thừa của lượt cũ: {ten}")
