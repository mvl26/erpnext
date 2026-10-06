// VÒNG SỬA 1 (soát xét `task-2-soat-xet.md`, P3): bốn bài GỐC dưới đây là NGUYÊN
// VĂN Bước 1 của brief — người soát đã xác nhận từng ký tự khớp brief trước vòng
// sửa này. Bài thứ hai ("mã không nhận ra... KHÔNG vào lịch sử") ĐỔI Ở VÒNG NÀY,
// theo đúng chỉ đạo mục 3: hai lớp vẽ từng có hai chính sách lịch sử khác nhau
// (app bỏ mã lạ, Desk giữ mã lạ) — chốt dùng chung bản GIÀU HƠN của Desk (giữ cả mã
// lạ), nên `lich_su()` giờ CÓ chứa các lần quét không nhận ra. Ba bài còn lại giữ
// nguyên logic gốc, không đổi.
const { test } = require("node:test");
const assert = require("node:assert");
const { tao, nhan_loai, NGAY_CAN_DATE } = require("./tra_cuu.js");

const gia_lap = (ket_qua) => (duong_dan, doi_so) => Promise.resolve(ket_qua(duong_dan, doi_so));

test("quét mã lô trả loại 'lo' và giữ vào lịch sử", async () => {
	const l = tao({ goi: gia_lap(() => ({ loai: "lo", so_lo: "LO-1", ten_hang: "Gạc" })) });
	const kq = await l.quet("LO-1");
	assert.equal(kq.loai, "lo");
	assert.equal(l.lich_su().length, 1);
	assert.equal(l.lich_su()[0].du_lieu.so_lo, "LO-1");
});

test("mã không nhận ra thì báo rõ và VẪN vào lịch sử (chính sách dùng chung với Desk, vòng sửa 1)", async () => {
	const l = tao({ goi: gia_lap(() => ({ loai: null })) });
	const kq = await l.quet("XXX");
	assert.equal(kq.loai, "khong_ro");
	assert.match(kq.bao, /Không nhận ra/);
	assert.equal(l.lich_su().length, 1);
	assert.equal(l.lich_su()[0].loai, "khong_ro");
	assert.equal(l.lich_su()[0].du_lieu, null);
});

test("mã rỗng không gọi máy chủ và không vào lịch sử", async () => {
	let so_lan = 0;
	const l = tao({
		goi: () => {
			so_lan += 1;
			return Promise.resolve({});
		},
	});
	await l.quet("   ");
	assert.equal(so_lan, 0);
	assert.equal(l.lich_su().length, 0);
});

test("lịch sử giữ tối đa 20 và mới nhất đứng đầu", async () => {
	const l = tao({ goi: gia_lap((_, d) => ({ loai: "o", ma_o: d.ma })) });
	for (let i = 1; i <= 25; i++) await l.quet("O-" + i);
	assert.equal(l.lich_su().length, 20);
	assert.equal(l.lich_su()[0].du_lieu.ma_o, "O-25");
});

// ------------------------------------------------- bài mới, vòng sửa 1 (mục 3)

test("quét trùng một mã thì gộp lại, không nhân đôi dòng", async () => {
	const l = tao({ goi: gia_lap((_, d) => ({ loai: "o", ma_o: d.ma })) });
	await l.quet("O-1");
	await l.quet("O-2");
	await l.quet("O-1"); // quét lại đúng mã đã có
	assert.equal(l.lich_su().length, 2, "không được thành 3 dòng");
	assert.equal(l.lich_su()[0].ma, "O-1", "dòng gộp lại phải nhảy lên đầu");
});

test("mỗi dòng lịch sử có giờ quét (mặc định: giờ máy trạm)", async () => {
	const l = tao({ goi: gia_lap(() => ({ loai: "lo", so_lo: "LO-1" })) });
	await l.quet("LO-1");
	assert.match(l.lich_su()[0].luc, /^\d{2}:\d{2}:\d{2}$/);
});

// Vòng sửa 2 (soát xét, M4): `gio` tiêm từ ngoài, cùng khuôn `goi` — Desk tiêm giờ
// SITE (`frappe.datetime.now_time()`), không còn giờ máy trạm mặc định của lớp
// luồng (khác trước vòng sửa: `new Date()` không phân biệt được Desk chạy trên máy
// tính lệch múi giờ với server).
test("gio() tiêm từ ngoài quyết định giờ ghi trong lịch sử", async () => {
	const l = tao({ goi: gia_lap(() => ({ loai: "lo", so_lo: "LO-1" })), gio: () => "09:09:09" });
	await l.quet("LO-1");
	assert.equal(l.lich_su()[0].luc, "09:09:09");
});

test("xoa_lich_su() dọn sạch lịch sử", async () => {
	const l = tao({ goi: gia_lap(() => ({ loai: "lo", so_lo: "LO-1" })) });
	await l.quet("LO-1");
	assert.equal(l.lich_su().length, 1);
	l.xoa_lich_su();
	assert.equal(l.lich_su().length, 0);
});

// ------------------------------------------------- bài mới, vòng sửa 1 (mục 2, 5)

test("nhan_loai() ánh xạ đúng bốn loại + mặc định 'Không rõ'", () => {
	assert.equal(nhan_loai("lo"), "Lô");
	assert.equal(nhan_loai("vat_tu"), "Vật tư");
	assert.equal(nhan_loai("o"), "Vị trí");
	assert.equal(nhan_loai("kho"), "Kho");
	assert.equal(nhan_loai("khong_ro"), "Không rõ");
	assert.equal(nhan_loai(undefined), "Không rõ");
});

// `trang_thai_han` nay là PHƯƠNG THỨC CỦA THỂ HIỆN, không còn hàm cấp module
// (soát xét tổng, M2) — nó đọc ngày TIÊM VÀO `tao({ngay})`. Bốn bài dưới đây tiêm
// một ngày CỐ ĐỊNH thay vì để hàm tự đọc đồng hồ: bản cũ dựng kỳ vọng bằng CHÍNH
// `new Date()` mà mã dùng, hai vế cùng một đồng hồ nên không bài nào có thể bắt
// được lệch đồng hồ — đúng lớp lỗi M2.
const HOM_NAY = "2026-09-24";
function _luong_ngay(ngay) {
	return tao({ goi: () => Promise.resolve({}), ngay: () => ngay || HOM_NAY });
}

test("trang_thai_han(): không có hsd thì 'khong', không phải lỗi", () => {
	const l = _luong_ngay();
	assert.deepEqual(l.trang_thai_han(null), { muc: "khong", chu: "" });
	assert.deepEqual(l.trang_thai_han(undefined), { muc: "khong", chu: "" });
});

test("trang_thai_han(): hạn xa (ngoài ngưỡng cận date) thì 'con'", () => {
	const l = _luong_ngay();
	// 2026-09-24 + 120 ngày = 2027-01-22, ngoài ngưỡng 90.
	const kq = l.trang_thai_han("2027-01-22");
	assert.equal(kq.muc, "con");
	assert.equal(kq.chu, "Còn 120 ngày");
});

test("trang_thai_han(): trong ngưỡng cận date thì 'can'", () => {
	const l = _luong_ngay();
	// 2026-09-24 + 80 ngày = 2026-12-13, trong ngưỡng 90.
	const kq = l.trang_thai_han("2026-12-13");
	assert.equal(kq.muc, "can");
	assert.equal(kq.chu, "Còn 80 ngày");
	assert.ok(80 <= NGAY_CAN_DATE, "bài này chỉ có nghĩa khi 80 nằm trong ngưỡng");
});

test("trang_thai_han(): đã qua hạn thì 'het'", () => {
	const l = _luong_ngay();
	const kq = l.trang_thai_han("2026-09-19");
	assert.equal(kq.muc, "het");
	assert.equal(kq.chu, "Hết hạn 5 ngày");
});

test("trang_thai_han(): hết hạn ĐÚNG hôm nay thì 'het', câu riêng", () => {
	const kq = _luong_ngay().trang_thai_han(HOM_NAY);
	assert.equal(kq.muc, "het");
	assert.equal(kq.chu, "Hết hạn hôm nay");
});

// BÀI KHOÁ CỦA M2 — thứ bộ test cũ KHÔNG THỂ có: phán quyết hết hạn phải đổi theo
// ngày TIÊM VÀO. Desk tiêm ngày SITE (`frappe.datetime.get_today()`), app để mặc
// định ngày máy trạm; một máy tính văn phòng lệch múi giờ với site mà không tiêm
// thì hạn dùng của một lô vật tư y tế đổi nghĩa âm thầm. Cùng một `hsd`, hai ngày
// tiêm khác nhau ⇒ hai phán quyết khác nhau.
test("tiêm `ngay` khác nhau thì phán quyết HẾT HẠN đổi theo — không đọc đồng hồ máy", () => {
	const HSD = "2026-09-24";
	const hom_qua = _luong_ngay("2026-09-23").trang_thai_han(HSD);
	const hom_nay = _luong_ngay("2026-09-24").trang_thai_han(HSD);
	const hom_sau = _luong_ngay("2026-09-25").trang_thai_han(HSD);
	assert.equal(hom_qua.muc, "can", "ngày 23 nhìn lô hết hạn ngày 24: CÒN hạn (cận date)");
	assert.equal(hom_qua.chu, "Còn 1 ngày");
	assert.equal(hom_nay.muc, "het", "ngày 24: hết hạn HÔM NAY");
	assert.equal(hom_nay.chu, "Hết hạn hôm nay");
	assert.equal(hom_sau.muc, "het", "ngày 25: đã QUÁ hạn");
	assert.equal(hom_sau.chu, "Hết hạn 1 ngày");
	// Và bài này KHÔNG được xanh nhờ trùng ngày máy: ba phán quyết phải KHÁC nhau.
	assert.notDeepEqual(hom_qua, hom_nay);
	assert.notDeepEqual(hom_nay, hom_sau);
});

// Mặc định (không tiêm `ngay`) vẫn phải chạy — ca app PDA và ca `node --test`.
test("không tiêm `ngay` thì rơi về ngày MÁY TRẠM, không ném lỗi", () => {
	const l = tao({ goi: () => Promise.resolve({}) });
	const d = new Date();
	const hai_so = (n) => String(n).padStart(2, "0");
	const hom_nay = `${d.getFullYear()}-${hai_so(d.getMonth() + 1)}-${hai_so(d.getDate())}`;
	assert.equal(l.trang_thai_han(hom_nay).chu, "Hết hạn hôm nay");
});

// ---------------------------------------------------------- Task 5, bài mới
//
// `man_tra_cuu.js` (app) tiêm MỘT HÀM GETTER đọc `KhoApp.ngay_may_chu()` — khác
// hẳn ca "không tiêm gì" ở trên (`ngay` là `undefined`, `tao()` tự rơi về
// `_ngay_may_tram`). Trong app, `ngay` LUÔN LÀ MỘT HÀM (có mặt), chỉ là hàm đó có
// thể CHƯA CÓ DỮ LIỆU (đồng bộ với máy chủ chưa xong) và trả `null`. Hai bài dưới
// đây khoá đúng ranh giới đó: một hàm ĐƯỢC TIÊM mà trả `null` phải làm phán quyết
// ẨN đi (không phải lỗi, không phải "còn hạn"), TUYỆT ĐỐI KHÔNG được lặng lẽ rơi
// về `_ngay_may_tram()` (đồng hồ máy) — rơi về đó là dựng lại đúng lỗ hổng cả
// Task này sinh ra để vá, chỉ là ở một khe hẹp hơn (vài trăm mili-giây đầu lúc mở
// app, trước khi đồng bộ xong).
test("Task 5: `ngay` được TIÊM mà trả `null` (chưa đồng bộ máy chủ) → hết hạn ẨN, không ném lỗi, không đoán bằng đồng hồ máy", () => {
	const l = tao({ goi: () => Promise.resolve({}), ngay: () => null });
	// Một `hsd` mà NẾU đọc theo ngày máy trạm hôm nay sẽ luôn ra "hết hạn hôm nay"
	// — chọn đúng ngày hệ thống chạy bài test để phép thử này không thể XANH bằng
	// cách tình cờ đọc đồng hồ máy mà không ai để ý.
	const d = new Date();
	const hai_so = (n) => String(n).padStart(2, "0");
	const hom_nay_may_tram = `${d.getFullYear()}-${hai_so(d.getMonth() + 1)}-${hai_so(d.getDate())}`;
	const kq = l.trang_thai_han(hom_nay_may_tram);
	assert.deepEqual(
		kq,
		{ muc: "khong", chu: "" },
		"ngay() trả null phải cho 'khong' (ẩn chip) — không phải 'het' (nghĩa là đã lặng lẽ đọc đồng hồ máy)"
	);
});

test("Task 5: `gio` được TIÊM mà trả `null` → lịch sử vẫn ghi được, không ném lỗi", () => {
	const l = tao({ goi: () => Promise.resolve({ loai: "lo", so_lo: "LO-1" }), gio: () => null });
	return l.quet("LO-1").then(() => {
		assert.equal(l.lich_su()[0].luc, null, "gio() trả null thì lịch sử cất nguyên null, không tự bịa giờ");
	});
});

// `ngay`/`gio` PHẢI LÀ GETTER SỐNG, GỌI LẠI MỖI LẦN — không phải một giá trị chụp
// nhanh lúc `tao()` chạy. `man_tra_cuu.js` dựng `_luong` là SINGLETON sống suốt
// phiên app (một lần dựng, tái dùng ở mọi lượt vào/ra màn); nếu `tao()` chỉ đọc
// `ngay()` MỘT LẦN lúc dựng thì lượt đồng bộ máy chủ hoàn tất SAU đó (luôn xảy ra
// bất đồng bộ) sẽ không bao giờ được lớp luồng nhìn thấy cho tới khi mở lại app —
// đúng thứ mà `KhoApp.ngay_may_chu()`/`gio_may_chu()` dựa vào để tự "sống dậy"
// ngay khi đồng bộ xong, không cần dựng lại luồng.
test("Task 5: `ngay`/`gio` được GỌI LẠI mỗi lần `trang_thai_han()`/`quet()` chạy, không chụp nhanh lúc `tao()`", async () => {
	let gia_tri_ngay = null; // mô phỏng "chưa đồng bộ"
	let gia_tri_gio = null;
	const l = tao({
		goi: () => Promise.resolve({ loai: "lo", so_lo: "LO-1" }),
		ngay: () => gia_tri_ngay,
		gio: () => gia_tri_gio,
	});

	// Trước khi "đồng bộ": ẩn hạn dùng, và lịch sử chưa có giờ.
	assert.deepEqual(l.trang_thai_han("2026-09-24"), { muc: "khong", chu: "" });
	await l.quet("LO-1");
	assert.equal(l.lich_su()[0].luc, null);

	// "Đồng bộ xong" — CÙNG một thể hiện `l`, không dựng lại `tao()`.
	gia_tri_ngay = "2026-09-24";
	gia_tri_gio = "08:00:00";
	assert.deepEqual(
		l.trang_thai_han("2026-09-24"),
		{ muc: "het", chu: "Hết hạn hôm nay" },
		"cùng một luồng phải thấy giá trị MỚI ngay lập tức, không cần dựng lại tao()"
	);
	await l.quet("LO-1");
	assert.equal(l.lich_su()[0].luc, "08:00:00", "lượt quét SAU khi đồng bộ phải ghi đúng giờ mới");
});
