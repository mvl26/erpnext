// Bài test của lớp LUỒNG màn "Đặt ô trên tem hàng loạt" — chạy bằng `node --test`
// trong chính thư mục này (không gói nào thêm, node v18). Cùng khuôn tách lớp mà
// `tra_cuu.js`/`xep_hang.js`/`lay_hang.js` đã dựng — đọc `dat_o.js` trước khi đọc
// tiếp file này, đừng phát minh lại.
//
// BA BÀI ĐẦU chép NGUYÊN VĂN Bước 1 của brief Task 5 — cùng `DS`, cùng `gia_lap`,
// cùng mọi khẳng định. Các bài SAU là bài thêm của Task này.
const { test } = require("node:test");
const assert = require("node:assert");
const { tao } = require("./dat_o.js");

const DS = [
	{ so_lo: "LO-1", vat_tu: "VT1", ton: 10, o_goi_y: "1A01", ly_do: "" },
	{ so_lo: "LO-2", vat_tu: "VT2", ton: 5, o_goi_y: null, ly_do: "mặt hàng chưa gán vị trí" },
];
const gia_lap = (bang) => (duong_dan, doi_so) => Promise.resolve(bang[duong_dan.split(".").pop()](doi_so));

test("nạp xong thì chỉ dòng CÓ ô gợi ý được chọn sẵn", async () => {
	const l = tao({ goi: gia_lap({ lo_chua_co_o: () => DS }) });
	await l.nap("K");
	assert.equal(l.so_dong_chon(), 1);
});

test("dòng đã chọn mà chưa có ô thì KHÔNG cho đặt", async () => {
	const l = tao({ goi: gia_lap({ lo_chua_co_o: () => DS }) });
	await l.nap("K");
	l.chon("LO-2", true);
	assert.equal(l.dat_duoc(), false, "cho đặt khi thiếu ô là đẩy lỗi xuống máy chủ");
	l.dat_o_cho_dong("LO-2", "1A02");
	assert.equal(l.dat_duoc(), true);
});

test("đặt xong trả về số dòng đã đặt và danh sách lỗi riêng", async () => {
	const l = tao({ goi: gia_lap({
		lo_chua_co_o: () => DS,
		dat_o_hang_loat: () => ({ da_dat: ["LO-1"], loi: [{ so_lo: "LO-2", ly_do: "ô vừa bị mặt hàng khác chiếm" }] }),
	}) });
	await l.nap("K");
	l.chon_tat_ca(true);
	l.dat_o_cho_dong("LO-2", "1A02");
	const kq = await l.dat();
	assert.equal(kq.da_dat.length, 1);
	assert.equal(kq.loi[0].so_lo, "LO-2");
});

// --------------------------------------------------------------- bài thêm

// `nap(kho)` với một `kho` đã biết CHỈ được gọi `lo_chua_co_o` — không gì khác.
// `gia_lap` ở trên không có lưới bắt khoá lạ (`bang[ten]` là `undefined` thì gọi
// nó ném `TypeError`), nên ba bài verbatim ở trên ĐÃ chứng minh điều này gián
// tiếp (bảng giả của chúng chỉ có đúng `lo_chua_co_o`/`dat_o_hang_loat`) — bài
// này khoá lại tường minh, đúng ràng buộc "nap(kho) không được lén gọi API khác"
// (soát xét thiết kế trước khi viết mã).
test("nap(kho) không gọi gì ngoài lo_chua_co_o", async () => {
	const l = tao({ goi: gia_lap({ lo_chua_co_o: () => DS }) });
	await assert.doesNotReject(l.nap("K"));
});

// `lo_chua_co_o` THẬT trả `o_de_xuat`/`ma_in_nhan_de_xuat` (xem `vitri/o_tem.py`),
// KHÔNG phải `o_goi_y` mà ba bài verbatim ở trên dùng — bài Bước 1 của brief tự nó
// đã lệch tên trường với máy chủ thật (quyết định ghi trong báo cáo: `nap()` phải
// CHẤP NHẬN CẢ HAI tên, vì cả hai đều phải chạy được — bài verbatim và sản xuất
// thật). Bài này khoá đúng NHÁNH SẢN XUẤT THẬT, không phải nhánh của bài mẫu.
test("lo_chua_co_o dạng THẬT (o_de_xuat) cũng tự tick đúng dòng có gợi ý", async () => {
	const THAT = [
		{
			so_lo: "LO-3", vat_tu: "VT3", ten_hang: "Ống nghe", ton: 7, dang_o: null,
			o_de_xuat: "1A03", ma_in_nhan_de_xuat: "1A03-N", ly_do: null, hsd: "2027-01-01",
		},
		{
			so_lo: "LO-4", vat_tu: "VT4", ten_hang: "Bơm tiêm", ton: 2, dang_o: null,
			o_de_xuat: null, ma_in_nhan_de_xuat: null, ly_do: "không gợi ý được — xem Error Log", hsd: null,
		},
	];
	const l = tao({ goi: gia_lap({ lo_chua_co_o: () => THAT }) });
	await l.nap("K");
	assert.equal(l.so_dong_chon(), 1);
	const st = l.trang_thai();
	const d3 = st.dong.find((d) => d.so_lo === "LO-3");
	assert.equal(d3.o, "1A03");
	assert.equal(d3.chon, true);
	const d4 = st.dong.find((d) => d.so_lo === "LO-4");
	assert.equal(d4.chon, false);
	assert.equal(d4.ly_do, "không gợi ý được — xem Error Log");
});

// `dat_o_hang_loat` THẬT trả `{xong: [{so_lo, o, ma_in_nhan}], loi: [{so_lo, loi}]}`
// (xem `vitri/o_tem.py::dat_o_hang_loat`) — khác hẳn tên trường bài mẫu của brief
// (`da_dat`/`ly_do`). `dat()` phải đọc được CẢ HAI dạng, và KHÔNG được đánh rơi
// `o`/`ma_in_nhan` của các lô đã đặt xong — màn cần chúng để mời in tem (đúng lỗi
// Task 3 từng đánh rơi "Xem phiếu" khi gộp lớp, rule 7).
test("dat_o_hang_loat dạng THẬT (xong/loi.loi) giữ nguyên o/ma_in_nhan của lô đã đặt", async () => {
	const l = tao({ goi: gia_lap({
		lo_chua_co_o: () => DS,
		dat_o_hang_loat: () => ({
			xong: [{ so_lo: "LO-1", o: "1A01", ma_in_nhan: "1A01-N" }],
			loi: [{ so_lo: "LO-2", loi: "lô đã có ô trên tem (người khác vừa đặt) — nạp lại danh sách" }],
		}),
	}) });
	await l.nap("K");
	l.chon_tat_ca(true);
	l.dat_o_cho_dong("LO-2", "1A02");
	const kq = await l.dat();
	assert.equal(kq.da_dat.length, 1);
	assert.equal(kq.da_dat[0].so_lo, "LO-1");
	assert.equal(kq.da_dat[0].o, "1A01");
	assert.equal(kq.da_dat[0].ma_in_nhan, "1A01-N");
	assert.equal(kq.loi[0].so_lo, "LO-2");
	assert.match(kq.loi[0].ly_do, /đã có ô trên tem/);
});

// CÂU KẾT QUẢ — MỘT NƠI cho CẢ HAI lớp vẽ (rule 2, phép thử "bọc tao() cho câu
// giả"). `dat()` phải TỰ trả `bao`/`muc` (cho dải báo của app) VÀ
// `tieu_de_thanh_cong`/`tieu_de_loi` (cho hai tiêu đề riêng của Desk — hộp mời
// in tem, popup lỗi) — không được để Desk tự gõ lại cùng câu ở một chỗ khác mà
// phép thử bọc `tao()` không chạm tới (soát xét sau Playwright, xem báo cáo
// Task 5 mục "phép thử người soát").
test("dat() tự trả câu kết quả cho CẢ app (bao/muc) lẫn Desk (hai tiêu đề)", async () => {
	const l = tao({ goi: gia_lap({
		lo_chua_co_o: () => DS,
		dat_o_hang_loat: () => ({ da_dat: ["LO-1"], loi: [{ so_lo: "LO-2", ly_do: "hỏng" }] }),
	}) });
	await l.nap("K");
	l.chon_tat_ca(true);
	l.dat_o_cho_dong("LO-2", "1A02");
	const kq = await l.dat();
	assert.match(kq.bao, /Đã đặt ô cho \*\*1\*\* lô/, "app cần dải báo có ** để tô đậm");
	assert.equal(kq.muc, "cam", "còn lỗi thì mức màu phải là cam, không phải xanh");
	assert.equal(kq.tieu_de_thanh_cong, "Đã đặt ô cho 1 lô", "tiêu đề Desk KHÔNG có **");
	assert.equal(kq.tieu_de_loi, "1 lô không đặt được");
});

test("dat() đặt trọn vẹn (không lỗi) thì mức xanh, không có tiêu đề lỗi", async () => {
	const l = tao({ goi: gia_lap({
		lo_chua_co_o: () => DS,
		dat_o_hang_loat: () => ({ xong: [{ so_lo: "LO-1", o: "1A01" }], loi: [] }),
	}) });
	await l.nap("K");
	const kq = await l.dat();
	assert.equal(kq.muc, "xanh");
	assert.equal(kq.tieu_de_loi, null);
	assert.equal(kq.tieu_de_thanh_cong, "Đã đặt ô cho 1 lô");
});

// RÀNG BUỘC RIÊNG CỦA TASK 5 — màn có GHI: hỏi lại máy chủ trước khi hỏi người
// dùng, không dùng số liệu cũ để dựng câu hỏi xác nhận.
test("hoi_dat() nạp lại từ máy chủ trước khi dựng câu hỏi, và không xoá lựa chọn", async () => {
	let so_lan_nap = 0;
	const l = tao({ goi: gia_lap({
		lo_chua_co_o: () => { so_lan_nap += 1; return DS; },
	}) });
	await l.nap("K");
	assert.equal(so_lan_nap, 1);
	l.dat_o_cho_dong("LO-2", "1A02");
	const h = await l.hoi_dat();
	assert.equal(so_lan_nap, 2, "hoi_dat() phải tự gọi lại lo_chua_co_o — không dùng số liệu cũ");
	assert.equal(h.ok, true);
	assert.match(h.cau, /2/, "câu hỏi phải nói đúng số dòng SẼ đặt");
	// Nạp lại KHÔNG được xoá ô người dùng vừa gõ cho LO-2 (Desk gốc: `nap()` không
	// đụng `this.chon`/`this.tick` — chỉ việc "kho đổi" mới xoá).
	assert.equal(l.trang_thai().dong.find((d) => d.so_lo === "LO-2").o, "1A02");
});

test("hoi_dat() không có dòng nào đặt được thì báo, không hỏi", async () => {
	const l = tao({ goi: gia_lap({ lo_chua_co_o: () => DS }) });
	await l.nap("K");
	l.chon("LO-1", false); // bỏ chọn dòng duy nhất đang có ô
	const h = await l.hoi_dat();
	assert.equal(h.ok, false);
});

// Nút "Chọn tất cả dòng có ô" (thiết kế lại cho màn hẹp, brief Bước 5) — CHỈ chọn
// những dòng ĐANG có ô, không kéo theo dòng còn thiếu ô (khác hẳn hộp kiểm đầu
// bảng của Desk gốc, vốn tick TẤT CẢ bất kể có ô hay không) — quyết định ghi
// trong báo cáo.
test("chon_tat_ca(true) chỉ chọn dòng đang có ô", async () => {
	const l = tao({ goi: gia_lap({ lo_chua_co_o: () => DS }) });
	await l.nap("K");
	l.chon_tat_ca(true);
	const st = l.trang_thai();
	assert.equal(st.dong.find((d) => d.so_lo === "LO-1").chon, true);
	assert.equal(st.dong.find((d) => d.so_lo === "LO-2").chon, false, "LO-2 chưa có ô — không tự chọn");
});

test("chon_tat_ca(false) bỏ chọn hết, kể cả dòng có ô", async () => {
	const l = tao({ goi: gia_lap({ lo_chua_co_o: () => DS }) });
	await l.nap("K");
	l.chon_tat_ca(false);
	assert.equal(l.so_dong_chon(), 0);
});

// Đo được trên trình duyệt thật (Playwright, kịch bản Task 5): bỏ tick tay một
// dòng ĐANG có ô rồi bấm "Chọn tất cả dòng có ô" từng khiến dòng đó BẬT TRỞ
// LẠI — nút "tiện" âm thầm xoá quyết định người dùng vừa làm. `chon_tat_ca(true)`
// KHÔNG được ghi đè một lượt bỏ chọn TAY trước đó.
test("chon_tat_ca(true) KHÔNG ghi đè dòng người dùng đã tự bỏ chọn tay", async () => {
	const l = tao({ goi: gia_lap({ lo_chua_co_o: () => DS }) });
	await l.nap("K");
	assert.equal(l.trang_thai().dong.find((d) => d.so_lo === "LO-1").chon, true, "LO-1 tự chọn sẵn (có gợi ý)");
	l.chon("LO-1", false); // người dùng TỰ tay bỏ chọn LO-1
	l.chon_tat_ca(true);
	assert.equal(
		l.trang_thai().dong.find((d) => d.so_lo === "LO-1").chon,
		false,
		"chọn tất cả không được ép chọn lại một dòng vừa bị bỏ tay"
	);
});

// `mo()` — chọn kho trước khi có thể `nap()`. Tái dùng `xep.phieu_xep_dang_lam`
// CHỈ để lấy `kho_ds`/`kho` (không đụng `phieu` — không liên quan màn này); quyết
// định và lý do đầy đủ ở đầu `dat_o.js` và trong báo cáo Task 5.
test("mo() với đúng một kho quản lý vị trí thì tự chọn và nạp luôn", async () => {
	let goi_lo_chua_co_o = 0;
	const l = tao({ goi: gia_lap({
		phieu_xep_dang_lam: () => ({ kho_ds: ["K1"], kho: "K1", phieu: null }),
		lo_chua_co_o: (d) => { goi_lo_chua_co_o += 1; assert.equal(d.kho, "K1"); return DS; },
	}) });
	const st = await l.mo();
	assert.equal(st.kho, "K1");
	assert.equal(goi_lo_chua_co_o, 1, "một kho duy nhất thì tự nạp luôn, không bắt chọn tay");
	assert.equal(st.dong.length, 2);
});

test("mo() với nhiều kho thì để trống, KHÔNG tự nạp lô của kho nào", async () => {
	const l = tao({ goi: gia_lap({
		phieu_xep_dang_lam: () => ({ kho_ds: ["K1", "K2"], kho: null, phieu: null }),
	}) });
	const st = await l.mo();
	assert.equal(st.kho, null);
	assert.deepEqual(st.kho_ds, ["K1", "K2"]);
	assert.equal(st.dong.length, 0);
});

// ------------------------------------------- bài khoá soát xét TỔNG (N1/M5/T1)

// N1 — LỖI GHI SAI DỮ LIỆU đã dựng lại được. Bản Desk đổi kho bằng CHÍNH `nap()`
// (ô Link "Kho" của `dat_o_hang_loat.js`), không qua `mo()`; `nap()` cũ không dọn
// `da_chon`/`o_dat`, nên ô gõ dở cho kho A THEO SANG kho B, dòng vẫn tick,
// `dat_duoc` vẫn `true` → gửi lên `[{so_lo:"LO-9", o:"A-01-01"}]`. Máy chủ
// (`o_tem.doi_o_tren_tem`) chỉ kiểm ô có thuộc MỘT kho quản lý vị trí, KHÔNG so
// với kho đang giữ tồn, nên nó CHẤP NHẬN — từ đó `xep_hang` báo SAI Ô vĩnh viễn.
test("N1 — `nap()` sang kho KHÁC phải dọn ô/tick gõ dở của kho cũ", async () => {
	const KHO_A = [{ so_lo: "LO-9", vat_tu: "VT9", ton: 3, o_goi_y: null, ly_do: "" }];
	const KHO_B = [{ so_lo: "LO-9", vat_tu: "VT9", ton: 7, o_goi_y: null, ly_do: "" }];
	let kho_dang_hoi = null;
	const l = tao({ goi: gia_lap({
		lo_chua_co_o: ({ kho }) => {
			kho_dang_hoi = kho;
			return kho === "KHO-A" ? KHO_A : KHO_B;
		},
	}) });
	await l.nap("KHO-A");
	l.dat_o_cho_dong("LO-9", "A-01-01"); // gõ dở một ô CỦA KHO A
	assert.equal(l.trang_thai().dat_duoc, true, "ở kho A thì đúng là đặt được");

	await l.nap("KHO-B"); // đổi kho bằng ĐÚNG đường mà Desk đi
	assert.equal(kho_dang_hoi, "KHO-B");
	const st = l.trang_thai();
	const d = st.dong.find((x) => x.so_lo === "LO-9");
	assert.equal(d.o, "", "ô của kho A KHÔNG được theo sang kho B");
	assert.equal(d.chon, false, "dòng cũng không được giữ tick của kho A");
	assert.equal(st.dat_duoc, false, "không còn gì để gửi lên máy chủ");
});

// Mặt còn lại của N1: `nap()` CÙNG một kho (nạp lại định kỳ, và `hoi_dat()` tự nạp
// lại trước khi hỏi) TUYỆT ĐỐI không được dọn — dọn ở đó là xoá sạch tick ngay
// trước lượt ghi. Bài `hoi_dat()` phía trên đã chạm tới, bài này nói thẳng.
test("N1 — `nap()` CÙNG một kho thì giữ nguyên ô/tick đang làm dở", async () => {
	const l = tao({ goi: gia_lap({ lo_chua_co_o: () => DS }) });
	await l.nap("K");
	l.dat_o_cho_dong("LO-2", "1A02");
	l.chon("LO-1", false);
	await l.nap("K");
	const st = l.trang_thai();
	assert.equal(st.dong.find((d) => d.so_lo === "LO-2").o, "1A02");
	assert.equal(st.dong.find((d) => d.so_lo === "LO-1").chon, false);
});

// `mo()` đi qua CÙNG một luật (không còn bản kiểm riêng của nó).
test("N1 — `mo()` sang kho khác cũng dọn, `mo()` về đúng kho cũ thì không", async () => {
	const l = tao({ goi: gia_lap({
		phieu_xep_dang_lam: ({ kho }) => ({ kho_ds: ["K1", "K2"], kho: kho || "K1", phieu: null }),
		lo_chua_co_o: () => DS,
	}) });
	await l.mo("K1");
	l.dat_o_cho_dong("LO-2", "1A02");
	await l.mo("K1");
	assert.equal(l.trang_thai().dong.find((d) => d.so_lo === "LO-2").o, "1A02", "cùng kho: giữ");
	await l.mo("K2");
	assert.equal(l.trang_thai().dong.find((d) => d.so_lo === "LO-2").o, "", "đổi kho: dọn");
});

// M5 — ô lọc và "chọn tất cả" phải nói CÙNG một thứ. Lọc còn một thẻ trên màn 4
// inch, bấm "Chọn tất cả dòng có ô" rồi bấm nút chính từng GHI cho cả những lô
// KHÔNG NHÌN THẤY.
test("M5 — `chon_tat_ca(true)` chỉ chạm tập ĐANG LỌC", async () => {
	const BA = [
		{ so_lo: "LO-1", vat_tu: "VT1", ten_hang: "Gạc", ton: 1, o_goi_y: "1A01" },
		{ so_lo: "LO-2", vat_tu: "VT2", ten_hang: "Kim", ton: 2, o_goi_y: "1A02" },
		{ so_lo: "LO-3", vat_tu: "VT3", ten_hang: "Bông", ton: 3, o_goi_y: "1A03" },
	];
	const l = tao({ goi: gia_lap({ lo_chua_co_o: () => BA }) });
	await l.nap("K");
	l.dat_bo_loc("LO-2");
	const st_loc = l.trang_thai();
	assert.equal(st_loc.dong_hien.length, 1, "ô lọc còn đúng một thẻ");
	assert.equal(st_loc.dong.length, 3, "`dong` vẫn là toàn bộ — Desk không có ô lọc, vẽ hết");

	l.chon_tat_ca(true);

	// ĐO BẰNG GÌ: cả ba dòng đều có ô gợi ý nên đều đang tick sẵn theo MẶC ĐỊNH
	// (`_co_chon`: chưa ai đụng thì "có ô thì tick") — nhìn cột `chon` ngay sau khi
	// bấm thì không phân biệt được dòng nào vừa bị nút này GHIM. Xoá ô của cả ba:
	// dòng đã bị ghim `da_chon = true` giữ nguyên tick, dòng chưa ai đụng rơi về
	// mặc định "không có ô ⇒ không tick". Đó là dấu vết duy nhất của việc nút vừa
	// chạm vào dòng nào.
	["LO-1", "LO-2", "LO-3"].forEach((x) => l.dat_o_cho_dong(x, ""));
	const st = l.trang_thai();
	assert.equal(st.dong.find((d) => d.so_lo === "LO-2").chon, true, "thẻ đang nhìn thấy: nút có ghim");
	assert.equal(st.dong.find((d) => d.so_lo === "LO-1").chon, false, "lô KHÔNG nhìn thấy: nút không chạm tới");
	assert.equal(st.dong.find((d) => d.so_lo === "LO-3").chon, false);
	assert.equal(st.so_dong_chon, 1);
});

test("M5 — `chon_tat_ca(false)` cũng chỉ chạm tập đang lọc (đối xứng)", async () => {
	const l = tao({ goi: gia_lap({ lo_chua_co_o: () => DS }) });
	await l.nap("K");
	l.chon("LO-2", true);
	assert.equal(l.so_dong_chon(), 2);
	l.dat_bo_loc("LO-1");
	l.chon_tat_ca(false);
	const st = l.trang_thai();
	assert.equal(st.dong.find((d) => d.so_lo === "LO-1").chon, false, "đang hiện: bỏ chọn");
	assert.equal(st.dong.find((d) => d.so_lo === "LO-2").chon, true, "bị lọc che: giữ nguyên quyết định cũ");
});

test("M5 — đổi kho thì ô lọc reset; ô lọc không khớp gì thì luồng tự trả câu báo", async () => {
	const l = tao({ goi: gia_lap({ lo_chua_co_o: () => DS }) });
	await l.nap("K1");
	l.dat_bo_loc("khong-co-gi-khop");
	const st = l.trang_thai();
	assert.equal(st.dong_hien.length, 0);
	assert.equal(st.cau_loc_trong, "Không có dòng nào khớp bộ lọc.", "câu này là của LUỒNG, không của lớp vẽ");
	await l.nap("K2");
	assert.equal(l.trang_thai().bo_loc, "", "kho mới thì ô lọc của kho cũ hết nghĩa");
	assert.equal(l.trang_thai().cau_loc_trong, null);
});

// T1 — `dat()` cũ xoá SẠCH lựa chọn, nên dòng LỖI rơi về mặc định "có ô thì tick"
// và TỰ TICK LẠI: bấm nút lần hai là gửi lại đúng dòng máy chủ vừa từ chối, với
// đúng cái ô vừa bị từ chối.
test("T1 — dòng bị máy chủ TỪ CHỐI không được tự tick lại sau `dat()`", async () => {
	let lan = 0;
	const l = tao({ goi: gia_lap({
		// LO-1 đặt xong thì máy chủ không trả nó ở lần nạp sau nữa (nó đã có ô).
		lo_chua_co_o: () => (++lan === 1 ? DS : DS.filter((d) => d.so_lo !== "LO-1")),
		dat_o_hang_loat: () => ({
			xong: [{ so_lo: "LO-1", o: "1A01" }],
			loi: [{ so_lo: "LO-2", loi: "ô vừa bị mặt hàng khác chiếm" }],
		}),
	}) });
	await l.nap("K");
	l.dat_o_cho_dong("LO-2", "1A02");
	assert.equal(l.so_dong_chon(), 2);
	await l.dat();
	const st = l.trang_thai();
	const d2 = st.dong.find((d) => d.so_lo === "LO-2");
	assert.equal(d2.chon, false, "bấm lần hai sẽ gửi lại đúng dòng vừa bị từ chối");
	assert.equal(d2.o, "1A02", "nhưng GIỮ ô đã gõ — nó đứng cạnh lý do từ chối trên cùng một thẻ");
	assert.equal(d2.loi_dat, "ô vừa bị mặt hàng khác chiếm");
	assert.equal(st.dat_duoc, false, "không còn dòng nào chọn ⇒ nút chính tắt");
});

// Mặt còn lại của T1: người dùng SỬA ô của dòng lỗi là đang chữa nó — tick trở về
// mặc định ("có ô thì tick"), không bắt bấm thêm một cú vào hộp kiểm.
test("T1 — sửa ô của dòng vừa bị từ chối thì tick trở lại theo mặc định", async () => {
	const l = tao({ goi: gia_lap({
		lo_chua_co_o: () => DS,
		dat_o_hang_loat: () => ({ xong: [], loi: [{ so_lo: "LO-1", loi: "ô đang có hàng khác" }] }),
	}) });
	await l.nap("K");
	await l.dat();
	assert.equal(l.trang_thai().dong.find((d) => d.so_lo === "LO-1").chon, false);
	l.dat_o_cho_dong("LO-1", "1A09");
	const d = l.trang_thai().dong.find((x) => x.so_lo === "LO-1");
	assert.equal(d.chon, true);
	assert.equal(d.loi_dat, null, "sửa ô rồi mà còn giữ lý do cũ là nói dối về việc vừa làm");
});

test("T1 — dòng ĐẶT XONG thì xoá hẳn tick/ô (nó biến khỏi danh sách lần nạp sau)", async () => {
	let lan = 0;
	const l = tao({ goi: gia_lap({
		// Lần nạp sau khi đặt xong: LO-1 đã có ô nên máy chủ không trả nó nữa.
		lo_chua_co_o: () => (++lan === 1 ? DS : DS.filter((d) => d.so_lo !== "LO-1")),
		dat_o_hang_loat: () => ({ xong: [{ so_lo: "LO-1", o: "1A01" }], loi: [] }),
	}) });
	await l.nap("K");
	await l.dat();
	const st = l.trang_thai();
	assert.equal(st.dong.length, 1);
	assert.equal(st.so_dong_chon, 0, "LO-2 chưa có ô nên không tự tick; không còn rác của LO-1");
});
