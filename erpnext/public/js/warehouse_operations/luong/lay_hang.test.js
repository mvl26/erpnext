// Bài test của lớp LUỒNG màn "Lấy hàng theo phiếu giao" — chạy bằng `node --test`
// trong chính thư mục này (không gói nào thêm, node v18).
//
// NĂM BÀI ĐẦU giữ NGUYÊN VĂN Bước 1 của brief Task 4: cùng `PHIEU`, cùng `gia_lap`,
// cùng mọi khẳng định. Chúng khoá bốn luật nghiệp vụ mà mỗi luật đã trả giá bằng
// một sự cố thật ngoài kho (lô hết hạn, đổi/tách lô, đơn vị, số kiện).
//
// Các bài SAU đó là bài thêm của Task này — rà theo rule 7 (gộp lớp KHÔNG được
// phép là một lần cắt tính năng đang chạy): mỗi bài khoá đúng một hành vi mà bản
// Desk `page/lay_hang_pda/lay_hang_pda.js` ĐANG CÓ và có thể rơi rụng lúc rút phần
// quyết định ra (cắt số lượng theo tồn ô, giữ lô đang chờ sau khi bị cắt, chỉ gửi
// `so_kien` khi người dùng đã sửa, hỏi lại máy chủ trước khi bỏ một lượt đã lấy).
const { test } = require("node:test");
const assert = require("node:assert");
const { tao } = require("./lay_hang.js");

const PHIEU = {
	name: "MAT-DN-1",
	dong: [{
		dong_hang: "d1", vat_tu: "VT", ten_hang: "Gạc", so_lo: "LO-1",
		don_vi_dong: "Hộp", he_so_dong: 100, don_vi_ton: "Cái",
		can_lay: 6, da_lay: 0, can_lay_ton: 600, da_lay_ton: 0, can_quet: true,
		don_vi_chon: [{ uom: "Cái", he_so: 1 }, { uom: "Hộp", he_so: 100 }],
		da_lay_o: [], o_nen_lay: [{ o: "1A01", so_luong: 600 }],
	}],
	so_kien_da_in: 0, tong_kien: 0,
};

function gia_lap(bang) {
	return (duong_dan, doi_so) => {
		const ten = duong_dan.split(".").pop();
		if (!bang[ten]) throw new Error("gọi hàm không mong đợi: " + ten);
		return Promise.resolve(bang[ten](doi_so));
	};
}

test("lô hết hạn bị CHẶN, không chuyển sang chờ ô", async () => {
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => PHIEU,
		quet_de_lay: () => ({ loai: "lo", het_han: 1, so_lo: "LO-CU", hsd: "2020-01-01" }),
	}) });
	await l.mo("MAT-DN-1");
	const kq = await l.quet("LO-CU");
	assert.equal(kq.buoc, "cho_lo", "lô hết hạn mà vẫn cho quét ô là vỡ luật 18/09");
	assert.match(kq.bao, /hết hạn/i);
});

test("quét lô KHÁC lô đang chốt thì đòi xác nhận, chưa đổi gì", async () => {
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => PHIEU,
		quet_de_lay: () => ({ loai: "lo_khac", dong_hang: "d1", so_lo: "LO-2", so_lo_dang_chot: "LO-1" }),
	}) });
	await l.mo("MAT-DN-1");
	const kq = await l.quet("LO-2");
	assert.equal(kq.can_xac_nhan, "doi_lo");
});

test("đã lấy một phần rồi đổi lô thì TÁCH DÒNG, chưa lấy gì thì ĐỔI LÔ", async () => {
	const goi_da = [];
	const phieu_da_lay = JSON.parse(JSON.stringify(PHIEU));
	phieu_da_lay.dong[0].da_lay_ton = 200;
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => phieu_da_lay,
		quet_de_lay: () => ({ loai: "lo_khac", dong_hang: "d1", so_lo: "LO-2", so_lo_dang_chot: "LO-1" }),
		tach_dong_theo_lo: (d) => { goi_da.push("tach"); return phieu_da_lay; },
		doi_lo: () => { goi_da.push("doi"); return phieu_da_lay; },
	}) });
	await l.mo("MAT-DN-1");
	await l.quet("LO-2");
	await l.xac_nhan_doi_lo();
	assert.deepEqual(goi_da, ["tach"]);
});

test("đổi đơn vị thì số lượng mặc định lấy phần NGUYÊN của phần còn thiếu", async () => {
	const l = tao({ goi: gia_lap({ mo_phieu_giao: () => PHIEU, quet_de_lay: () => ({
		loai: "lo", dong_hang: "d1", so_lo: "LO-1", vat_tu: "VT",
	}) }) });
	await l.mo("MAT-DN-1");
	await l.quet("LO-1");
	l.dat_don_vi("Hộp");
	assert.equal(l.trang_thai().cho.so_luong, 6);
	l.dat_don_vi("Cái");
	assert.equal(l.trang_thai().cho.so_luong, 600);
});

test("số kiện mặc định: đơn vị đóng gói thì mỗi đơn vị một kiện, đơn vị tồn thì một kiện", async () => {
	const l = tao({ goi: gia_lap({ mo_phieu_giao: () => PHIEU, quet_de_lay: () => ({
		loai: "lo", dong_hang: "d1", so_lo: "LO-1", vat_tu: "VT",
	}) }) });
	await l.mo("MAT-DN-1");
	await l.quet("LO-1");
	l.dat_don_vi("Hộp");
	l.dat_so_luong(5);
	assert.equal(l.trang_thai().cho.so_kien, 5);
	l.dat_don_vi("Cái");
	l.dat_so_luong(300);
	assert.equal(l.trang_thai().cho.so_kien, 1);
});

// ------------------------------------------------- bài thêm (rà theo rule 7)
// Mỗi bài dưới đây khoá đúng MỘT hành vi mà bản Desk ĐANG CÓ trước khi gộp lớp.
// Task 3 từng đánh rơi hai tính năng khi gộp (liên kết "Xem phiếu", phần tô đậm);
// những bài này là lưới chặn cho đúng lớp mất mát đó ở màn nặng nhất.

// Một phiếu độc lập cho từng bài — `PHIEU` ở trên là hằng dùng chung, sửa nó trong
// một bài là làm bài khác xanh/đỏ giả.
function _phieu(sua) {
	const p = JSON.parse(JSON.stringify(PHIEU));
	if (sua) sua(p.dong[0], p);
	return p;
}

function _o(ma_o) {
	return { loai: "o", ma_o, ma_in_nhan: ma_o, kho: "K", la_nhom: false };
}

function _lo(so_lo) {
	return { loai: "lo", dong_hang: "d1", so_lo, vat_tu: "VT", het_han: false };
}

test("số MẶC ĐỊNH cho máy chủ cắt theo tồn ô; số NGƯỜI DÙNG gõ thì KHÔNG", async () => {
	const da_goi = [];
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => _phieu(),
		quet_de_lay: ({ ma }) => (ma === "LO-1" ? _lo("LO-1") : _o(ma)),
		ghi_da_lay: (d) => { da_goi.push(d); return _phieu((x) => { x.da_lay_ton = 600; x.da_lay = 6; }); },
	}) });
	await l.mo("MAT-DN-1");
	await l.quet("LO-1");
	await l.quet("1A01");
	assert.equal(da_goi[0].lay_toi_da_theo_o, 1, "số mặc định phải cho máy chủ cắt theo tồn ô");
	assert.equal(da_goi[0].so_kien, undefined, "chưa sửa số kiện thì KHÔNG gửi — máy chủ tự tính theo số THẬT đã ghi");

	const l2 = tao({ goi: gia_lap({
		mo_phieu_giao: () => _phieu(),
		quet_de_lay: ({ ma }) => (ma === "LO-1" ? _lo("LO-1") : _o(ma)),
		ghi_da_lay: (d) => { da_goi.push(d); return _phieu((x) => { x.da_lay_ton = 300; x.da_lay = 3; }); },
	}) });
	await l2.mo("MAT-DN-1");
	await l2.quet("LO-1");
	l2.dat_so_luong(3);
	l2.dat_so_kien(2);
	await l2.quet("1A01");
	const sau = da_goi[da_goi.length - 1];
	assert.equal(sau.lay_toi_da_theo_o, 0, "số người dùng tự gõ KHÔNG được âm thầm cắt");
	assert.equal(sau.so_kien, 2, "số kiện người dùng đặt phải được gửi lên");
	assert.equal(sau.so_luong, 3);
});

test("ô chỉ còn một phần: GIỮ lô đang chờ, số lượng = phần còn thiếu MỚI", async () => {
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => _phieu(),
		quet_de_lay: ({ ma }) => (ma === "LO-1" ? _lo("LO-1") : _o(ma)),
		ghi_da_lay: () => {
			const p = _phieu((x) => { x.da_lay_ton = 200; x.da_lay = 2; });
			p.so_luong_da_ghi = 2;
			p.don_vi_da_ghi = "Hộp";
			return p;
		},
	}) });
	await l.mo("MAT-DN-1");
	await l.quet("LO-1");
	const kq = await l.quet("1A01");
	assert.equal(kq.muc, "cam");
	assert.match(kq.bao, /chỉ còn/i);
	const st = l.trang_thai();
	assert.ok(st.cho, "bỏ lô đang chờ ở đây là bắt thủ kho quét LẠI tem lô — đúng lỗi đã sửa một vòng trước");
	assert.equal(st.cho.so_luong, 4, "600 - 200 = 400 Cái = 4 Hộp");
	assert.equal(st.buoc, "cho_o");
});

test("còn thiếu DƯỚI một đơn vị đóng gói thì rơi về đơn vị tồn", async () => {
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => _phieu((x) => { x.da_lay_ton = 520; x.da_lay = 5.2; }),
		quet_de_lay: () => _lo("LO-1"),
	}) });
	await l.mo("MAT-DN-1");
	await l.quet("LO-1");
	const c = l.trang_thai().cho;
	assert.equal(c.don_vi, "Cái", "80 Cái không đủ một Hộp — ô số lượng hiện 0 là bảo thủ kho không lấy được gì");
	assert.equal(c.so_luong, 80);
});

test("người dùng chạm nút đơn vị thì KHÔNG tự nhảy về đơn vị tồn", async () => {
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => _phieu((x) => { x.da_lay_ton = 520; x.da_lay = 5.2; }),
		quet_de_lay: () => _lo("LO-1"),
	}) });
	await l.mo("MAT-DN-1");
	await l.quet("LO-1");
	l.dat_don_vi("Hộp");
	assert.equal(l.trang_thai().cho.don_vi, "Hộp", "tự đổi lại đơn vị là đổi ý định của người dùng");
	assert.equal(l.trang_thai().cho.so_luong, 0);
});

test("dat_so_luong GIỮ số kiện người dùng đặt; dat_don_vi thì tính lại", async () => {
	const l = tao({ goi: gia_lap({ mo_phieu_giao: () => _phieu(), quet_de_lay: () => _lo("LO-1") }) });
	await l.mo("MAT-DN-1");
	await l.quet("LO-1");
	l.dat_so_kien(3);
	l.dat_so_luong(5);
	assert.equal(l.trang_thai().cho.so_kien, 3, "đổi số lượng không được xoá ý người dùng về số kiện");
	l.dat_don_vi("Cái");
	assert.equal(l.trang_thai().cho.so_kien, 1, "đổi đơn vị là một lượt lấy khác — số kiện tính lại từ đầu");
});

test("đã lấy một phần thì can_xac_nhan là tach_dong (không phải doi_lo)", async () => {
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => _phieu((x) => { x.da_lay_ton = 200; }),
		quet_de_lay: () => ({ loai: "lo_khac", dong_hang: "d1", so_lo: "LO-2", so_lo_dang_chot: "LO-1" }),
	}) });
	await l.mo("MAT-DN-1");
	const kq = await l.quet("LO-2");
	assert.equal(kq.can_xac_nhan, "tach_dong");
	assert.equal(l.trang_thai().lo_khac.viec, "tach_dong");
});

test("quét LẠI đúng tem lô khác = xác nhận, không cần hộp thoại (súng quét gửi Enter)", async () => {
	const goi_da = [];
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => _phieu(),
		quet_de_lay: () => ({ loai: "lo_khac", dong_hang: "d1", so_lo: "LO-2", so_lo_dang_chot: "LO-1" }),
		doi_lo: () => { goi_da.push("doi"); return _phieu((x) => { x.so_lo = "LO-2"; }); },
	}) });
	await l.mo("MAT-DN-1");
	await l.quet("LO-2");
	const kq = await l.quet("LO-2");
	assert.deepEqual(goi_da, ["doi"], "chưa lấy gì thì ĐỔI lô, không tách ra một dòng 0");
	assert.equal(kq.muc, "xanh");
	assert.equal(l.trang_thai().lo_khac, null);
});

test("lô hết hạn KHÔNG ghi gì và KHÔNG đụng lô đang chờ", async () => {
	let so_lan_ghi = 0;
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => _phieu(),
		quet_de_lay: ({ ma }) =>
			ma === "LO-CU"
				? { loai: "lo", dong_hang: "d1", het_han: 1, so_lo: "LO-CU", hsd: "2020-01-01" }
				: _lo("LO-1"),
		ghi_da_lay: () => { so_lan_ghi += 1; return _phieu(); },
	}) });
	await l.mo("MAT-DN-1");
	await l.quet("LO-1");
	const kq = await l.quet("LO-CU");
	assert.equal(so_lan_ghi, 0);
	assert.equal(kq.muc, "do");
	assert.equal(l.trang_thai().cho.so_lo, "LO-1", "lô hết hạn không được cướp chỗ lô đang lấy dở");
});

test("quét ô khi chưa quét lô thì nhắc quét lô, không gọi máy chủ ghi", async () => {
	let so_lan_ghi = 0;
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => _phieu(),
		quet_de_lay: ({ ma }) => _o(ma),
		ghi_da_lay: () => { so_lan_ghi += 1; return _phieu(); },
	}) });
	await l.mo("MAT-DN-1");
	const kq = await l.quet("1A01");
	assert.equal(so_lan_ghi, 0);
	assert.match(kq.bao, /quét tem LÔ/i);
});

test("đang chờ XÁC NHẬN đổi lô mà quét ô thì KHÔNG ghi", async () => {
	let so_lan_ghi = 0;
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => _phieu(),
		quet_de_lay: ({ ma }) =>
			ma === "LO-2"
				? { loai: "lo_khac", dong_hang: "d1", so_lo: "LO-2", so_lo_dang_chot: "LO-1" }
				: _o(ma),
		ghi_da_lay: () => { so_lan_ghi += 1; return _phieu(); },
	}) });
	await l.mo("MAT-DN-1");
	await l.quet("LO-2");
	const kq = await l.quet("1A01");
	assert.equal(so_lan_ghi, 0, "ghi trong lúc chưa chốt được lô nào là ghi vào lô SAI");
	assert.match(kq.bao, /quét tem LÔ/i);
});

test("máy chủ từ chối lượt ghi thì lỗi NỔI LÊN và lô vẫn đang chờ", async () => {
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => _phieu(),
		quet_de_lay: ({ ma }) => (ma === "LO-1" ? _lo("LO-1") : _o(ma)),
		ghi_da_lay: () => { throw new Error("Ô 1A01 chỉ còn 3 của VT, đang xin cấp 600."); },
	}) });
	await l.mo("MAT-DN-1");
	await l.quet("LO-1");
	await assert.rejects(() => l.quet("1A01"), /chỉ còn 3/);
	assert.equal(l.trang_thai().buoc, "cho_o", "máy chủ từ chối thì KHÔNG bắt quét lại từ tem lô");
});

test("chạm một LƯỢT ĐÃ LẤY thì HỎI LẠI MÁY CHỦ trước khi dựng câu hỏi", async () => {
	let so_lan_mo = 0;
	const co_luot = _phieu((x) => {
		x.da_lay_ton = 200;
		x.da_lay = 2;
		x.da_lay_o = [{ name: "p1", o: "1A01", ma_in_nhan: "1A01", so_luong: 200, don_vi_lay: "Hộp", so_luong_lay: 2, so_kien: 2, so_kien_da_in: 0 }];
	});
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => { so_lan_mo += 1; return co_luot; },
	}) });
	await l.mo("MAT-DN-1");
	assert.equal(so_lan_mo, 1);
	const hoi = await l.hoi_bo_luot("p1");
	assert.equal(so_lan_mo, 2, "màn GHI không được quyết định trên ảnh chụp cũ như màn Tra cứu");
	assert.equal(hoi.ok, true);
	assert.match(hoi.cau, /1A01/);
	assert.doesNotMatch(hoi.cau, /\*\*/, "hộp xác nhận escape toàn bộ và KHÔNG hiểu `**` — đánh dấu ở đây sẽ hiện ra hai dấu sao");
});

test("lượt đã bị bỏ ở nơi khác thì KHÔNG hỏi, chỉ báo và nạp lại", async () => {
	const l = tao({ goi: gia_lap({ mo_phieu_giao: () => _phieu() }) });
	await l.mo("MAT-DN-1");
	const hoi = await l.hoi_bo_luot("p-khong-co");
	assert.equal(hoi.ok, false);
	assert.match(hoi.bao, /vừa bị bỏ/i);
});

test("mo() KHÔNG nhận phiếu đã duyệt/huỷ, và docstatus vắng mặt = còn nháp", async () => {
	const da_duyet = _phieu();
	da_duyet.docstatus = 1;
	const l = tao({ goi: gia_lap({ mo_phieu_giao: () => da_duyet }) });
	const st = await l.mo("MAT-DN-1");
	assert.equal(st.phieu, null);
	assert.match(st.bao, /đã duyệt/i);

	// `PHIEU` của brief KHÔNG có khoá `docstatus` — so `!== 0` sẽ từ chối một phiếu
	// hoàn toàn bình thường, và cả màn hình chết ngay lượt mở đầu tiên.
	const l2 = tao({ goi: gia_lap({ mo_phieu_giao: () => _phieu() }) });
	const st2 = await l2.mo("MAT-DN-1");
	assert.ok(st2.phieu, "thiếu khoá docstatus phải hiểu là còn nháp");
});

test("câu báo đánh dấu đậm bằng ** quanh số lượng, mã lô và mã ô", async () => {
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => _phieu(),
		quet_de_lay: ({ ma }) => (ma === "LO-1" ? _lo("LO-1") : _o(ma)),
		ghi_da_lay: () => {
			const p = _phieu((x) => { x.da_lay_ton = 600; x.da_lay = 6; });
			p.so_luong_da_ghi = 6;
			p.don_vi_da_ghi = "Hộp";
			return p;
		},
	}) });
	await l.mo("MAT-DN-1");
	await l.quet("LO-1");
	const kq = await l.quet("1A01");
	assert.match(kq.bao, /\*\*6 Hộp\*\*/);
	assert.match(kq.bao, /\*\*1A01\*\*/);
});

test("dòng hàng trả về đã KẾT LUẬN sẵn: đủ/chưa, nút chốt thiếu, câu thiếu lô, lý do không quét", async () => {
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => {
			const p = _phieu((x) => { x.da_lay_ton = 200; x.da_lay = 2; x.thieu_trong_lo = 100; });
			p.dong.push({
				dong_hang: "d2", vat_tu: "DV", ten_hang: "Phí vận chuyển", can_quet: false,
				can_lay: 1, da_lay: 0, can_lay_ton: 0, da_lay_ton: 0,
			});
			return p;
		},
	}) });
	await l.mo("MAT-DN-1");
	const [d1, d2] = l.trang_thai().dong;
	assert.equal(d1.du, false);
	assert.equal(d1.hien_nut_chot_thieu, true);
	assert.match(d1.cau_thieu_trong_lo, /LO-1/);
	assert.match(d1.cau_thieu_trong_lo, /300 Cái/, "lấy được = còn cần 400 trừ phần thiếu 100");
	assert.equal(d1.ly_do_khong_quet, null);
	// Máy chủ (bản cũ) không trả `ly_do_khong_quet` — câu dự phòng là quyết định của
	// LUỒNG, không phải để mỗi lớp vẽ tự gõ một bản (đúng hình dạng lỗi Task 2).
	assert.match(d2.ly_do_khong_quet, /không cần quét/i);
	assert.equal(d2.hien_nut_chot_thieu, false);
});

test("hoan_tat() dọn phiếu, báo có dòng lấy thiếu, và trả tên phiếu cho lớp vẽ tự dựng liên kết", async () => {
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => _phieu(),
		hoan_tat: (d) => {
			assert.equal(d.phieu, "MAT-DN-1");
			return { name: "MAT-DN-1", so_dong: 1, lay_thieu: [{ vat_tu: "VT", so_lo: "LO-1", thieu: 100 }] };
		},
	}) });
	await l.mo("MAT-DN-1");
	const kq = await l.hoan_tat();
	assert.equal(kq.ok, true);
	assert.equal(kq.ten, "MAT-DN-1");
	assert.equal(kq.muc, "xanh");
	assert.match(kq.bao, /\*\*MAT-DN-1\*\*/);
	assert.match(kq.bao, /1 dòng lấy thiếu/);
	assert.equal(l.trang_thai().phieu, null);
});

test("gợi ý dưới ô quét đi theo đúng bước đang đứng", async () => {
	const l = tao({ goi: gia_lap({
		danh_sach_phieu_giao: () => ({ kho_ds: ["K"], kho: "K", phieu: [{ name: "MAT-DN-1" }] }),
		mo_phieu_giao: () => _phieu(),
		quet_de_lay: () => _lo("LO-1"),
	}) });
	await l.danh_sach("K");
	assert.match(l.trang_thai().goi_y_o_quet.chu, /Chọn phiếu giao/);
	await l.mo("MAT-DN-1");
	assert.match(l.trang_thai().goi_y_o_quet.chu, /① Quét tem LÔ/);
	await l.quet("LO-1");
	const g = l.trang_thai().goi_y_o_quet;
	assert.match(g.chu, /② Quét tem Ô cho lô LO-1/);
	assert.equal(g.nhan_manh, true);
});

// -------------------------------- bài thêm vòng soát: chốt thiếu + nhãn nút hộp

test("hoi_chot_thieu HỎI LẠI MÁY CHỦ; chot_thieu/bo_chot_thieu gửi đúng tham số", async () => {
	let so_lan_mo = 0;
	const goi_da = [];
	const chua_du = () => _phieu((x) => { x.da_lay_ton = 200; x.da_lay = 2; });
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => { so_lan_mo += 1; return chua_du(); },
		chot_thieu: (d) => { goi_da.push(["chot", d.phieu, d.dong_hang]); const p = chua_du(); p.dong[0].da_chot_thieu = true; p.dong[0].chot_thieu_boi = "thukho@x"; p.dong[0].chot_thieu_luc = "2026-09-23 10:00:00"; return p; },
		bo_chot_thieu: (d) => { goi_da.push(["bo", d.phieu, d.dong_hang]); return chua_du(); },
	}) });
	await l.mo("MAT-DN-1");
	assert.equal(so_lan_mo, 1);
	const h = await l.hoi_chot_thieu("d1");
	assert.equal(so_lan_mo, 2, "hộp 'chỉ lấy được 2/6' dựng từ ảnh chụp cũ là hỏi về một con số có thể đã khác");
	assert.equal(h.ok, true);
	assert.match(h.cau, /2\/6/);
	assert.equal(h.nhan, "Chốt thiếu", "nhãn nút của hộp cũng là câu chữ của LUỒNG");

	const st = await l.chot_thieu("d1");
	assert.deepEqual(goi_da[0], ["chot", "MAT-DN-1", "d1"]);
	// `bao` rỗng CÓ CHỦ ĐÍCH: kết quả hiện ngay trên dòng hàng (banner + nút đổi chỗ).
	assert.equal(st.bao, "");
	assert.match(st.dong[0].banner_chot_thieu, /Đã chốt thiếu bởi \*\*thukho@x\*\*/);
	assert.equal(st.dong[0].hien_nut_chot_thieu, false, "đã chốt rồi thì không còn nút chốt");

	const st2 = await l.bo_chot_thieu("d1");
	assert.deepEqual(goi_da[1], ["bo", "MAT-DN-1", "d1"]);
	assert.match(st2.bao, /gỡ cờ chốt thiếu/i);
	assert.equal(st2.dong[0].banner_chot_thieu, null);
});

test("dòng không còn trên phiếu thì hoi_chot_thieu KHÔNG hỏi, chỉ báo", async () => {
	const l = tao({ goi: gia_lap({ mo_phieu_giao: () => _phieu() }) });
	await l.mo("MAT-DN-1");
	const h = await l.hoi_chot_thieu("d-khong-co");
	assert.equal(h.ok, false);
	assert.match(h.bao, /không còn trên phiếu/i);
});

test("nhãn nút của CẢ BA hộp xác nhận do lớp luồng trả, không phải lớp vẽ tự gõ", async () => {
	const co_luot = _phieu((x) => {
		x.da_lay_ton = 200;
		x.da_lay = 2;
		x.da_lay_o = [{ name: "p1", o: "1A01", ma_in_nhan: "1A01", so_luong: 200, don_vi_lay: "Hộp", so_luong_lay: 2, so_kien: 2, so_kien_da_in: 2 }];
	});
	const l = tao({ goi: gia_lap({ mo_phieu_giao: () => co_luot }) });
	await l.mo("MAT-DN-1");
	assert.equal((await l.hoi_bo_luot("p1")).nhan, "Bỏ lượt");
	assert.equal((await l.hoi_chot_thieu("d1")).nhan, "Chốt thiếu");
	assert.equal((await l.hoi_hoan_tat()).nhan, "Duyệt phiếu");
});

// ---------------------------------------------------- Task 5, mục dọn 1
//
// `can_xac_nhan` (trả lúc QUÉT) và hàm THẬT `xac_nhan_doi_lo()` chọn (lúc ĐỒNG Ý)
// từng tự chép riêng cùng một biểu thức `_flt(dong.da_lay_ton) > 0` ở BA nơi —
// nhãn nút (`_the_lo_khac().nhan_nut`) là một trong ba, và nó KHÔNG hề đọc biểu
// thức đó: nút luôn mang chữ "Đổi sang lô {0}" bất kể `viec`. Hai bài dưới đây
// khoá cả hai trạng thái (`da_lay_ton = 0` và `da_lay_ton > 0`) và chứng minh BA
// thứ luôn khớp nhau sau khi gộp về `_viec_doi_lo`: nhãn nút, `can_xac_nhan`, và
// hàm THẬT SỰ được `goi()` gọi.
test("CHƯA lấy gì: nhãn nút nói ĐỔI, can_xac_nhan là doi_lo, hàm thật gọi doi_lo", async () => {
	const goi_da = [];
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => _phieu(),
		quet_de_lay: () => ({ loai: "lo_khac", dong_hang: "d1", so_lo: "LO-2", so_lo_dang_chot: "LO-1" }),
		doi_lo: () => { goi_da.push("doi"); return _phieu((x) => { x.so_lo = "LO-2"; }); },
	}) });
	await l.mo("MAT-DN-1");
	const kq = await l.quet("LO-2");
	assert.equal(kq.can_xac_nhan, "doi_lo");
	const lk = l.trang_thai().lo_khac;
	assert.equal(lk.viec, "doi_lo");
	assert.equal(lk.nhan_nut, "Đổi sang lô LO-2", "chưa lấy gì thì nút phải nói ĐỔI, không phải TÁCH");
	await l.xac_nhan_doi_lo();
	assert.deepEqual(goi_da, ["doi"]);
});

test("ĐÃ lấy một phần: nhãn nút nói TÁCH, can_xac_nhan là tach_dong, hàm thật gọi tach_dong_theo_lo", async () => {
	const goi_da = [];
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => _phieu((x) => { x.da_lay_ton = 200; x.da_lay = 2; }),
		quet_de_lay: () => ({ loai: "lo_khac", dong_hang: "d1", so_lo: "LO-2", so_lo_dang_chot: "LO-1" }),
		tach_dong_theo_lo: () => { goi_da.push("tach"); return _phieu((x) => { x.da_lay_ton = 200; }); },
	}) });
	await l.mo("MAT-DN-1");
	const kq = await l.quet("LO-2");
	assert.equal(kq.can_xac_nhan, "tach_dong");
	const lk = l.trang_thai().lo_khac;
	assert.equal(lk.viec, "tach_dong");
	assert.equal(
		lk.nhan_nut,
		"Tách sang lô LO-2",
		"đã lấy một phần thì nút phải nói TÁCH — trước bản vá này nó vẫn nói 'Đổi sang lô LO-2' dù hàm thật chạy tach_dong_theo_lo"
	);
	await l.xac_nhan_doi_lo();
	assert.deepEqual(goi_da, ["tach"]);
});

// ---------------------------------------------- bài khoá M1 (soát xét tổng)

// BẾ TẮC GIỮA KHO — dựng lại ĐÚNG kịch bản `soat-tong.md` mục M1: dòng bán **1 Hộp
// = 100 Cái**, hàng nằm ở HAI ô mỗi ô 50 Cái. Lấy hết ô A xong, phần còn thiếu là
// 50 Cái — NỬA một Hộp. Nhánh "ô chỉ còn một phần" của `ghi()` từng tự tính
// `Math.floor(0,5) = 0` mà THIẾU phép rơi về đơn vị tồn (phép mà `_nhan_lo` có),
// nên quét ô B ăn ngay "Số lượng phải lớn hơn 0" và thủ kho tắc giữa kho, lối
// thoát duy nhất là tự chạm nút "Cái" mà không có gì trên màn nói thế. Nay CẢ HAI
// chỗ gọi cùng một `_dat_so_mac_dinh()`.
test("M1 — ô chỉ còn NỬA đơn vị đóng gói: rơi về đơn vị tồn, KHÔNG để số lượng về 0", async () => {
	// Dòng 1 Hộp = 100 Cái.
	const mot_hop = (x) => {
		x.can_lay = 1;
		x.da_lay = 0;
		x.can_lay_ton = 100;
		x.da_lay_ton = 0;
		x.o_nen_lay = [{ o: "1A01", so_luong: 50 }, { o: "1A02", so_luong: 50 }];
	};
	const l = tao({ goi: gia_lap({
		mo_phieu_giao: () => _phieu(mot_hop),
		quet_de_lay: ({ ma }) => (ma === "LO-1" ? _lo("LO-1") : _o(ma)),
		// Ô A chỉ còn 50 Cái — máy chủ cắt lượt ghi còn 0,5 Hộp.
		ghi_da_lay: () => {
			const p = _phieu((x) => {
				mot_hop(x);
				x.da_lay_ton = 50;
				x.da_lay = 0.5;
			});
			p.so_luong_da_ghi = 0.5;
			p.don_vi_da_ghi = "Hộp";
			return p;
		},
	}) });
	await l.mo("MAT-DN-1");
	await l.quet("LO-1");
	assert.equal(l.trang_thai().cho.don_vi, "Hộp", "trước khi quét ô: đơn vị của DÒNG");
	assert.equal(l.trang_thai().cho.so_luong, 1);

	const kq = await l.quet("1A01");
	assert.match(kq.bao, /chỉ còn/i, "máy chủ đã cắt — màn phải nói ô chỉ còn bao nhiêu");
	const c = l.trang_thai().cho;
	assert.ok(c, "vẫn GIỮ lô đang chờ để quét ô kế tiếp");
	assert.equal(c.don_vi, "Cái", "0,5 Hộp không phải một số quét được — phải rơi về đơn vị TỒN");
	assert.equal(c.so_luong, 50, "50 Cái còn thiếu, không phải 0");
	assert.ok(c.so_luong > 0, "số lượng 0 là bế tắc: quét ô B ăn 'Số lượng phải lớn hơn 0'");
	// Và nó vẫn là số MẶC ĐỊNH, không phải số "người dùng tự gõ": ô B phải được phép
	// cắt tiếp theo tồn. `da_sua_so_luong` cố ý KHÔNG công bố ra `trang_thai()` (xem
	// `_the_cho`), nên đo bằng HỆ QUẢ quan sát được — cờ `lay_toi_da_theo_o` của lượt
	// ghi kế tiếp.
	const da_goi = [];
	const l2 = tao({ goi: gia_lap({
		mo_phieu_giao: () => _phieu(mot_hop),
		quet_de_lay: ({ ma }) => (ma === "LO-1" ? _lo("LO-1") : _o(ma)),
		ghi_da_lay: (d) => {
			da_goi.push(d);
			const p = _phieu((x) => {
				mot_hop(x);
				x.da_lay_ton = 50;
				x.da_lay = 0.5;
			});
			p.so_luong_da_ghi = 0.5;
			p.don_vi_da_ghi = "Hộp";
			return p;
		},
	}) });
	await l2.mo("MAT-DN-1");
	await l2.quet("LO-1");
	await l2.quet("1A01");
	await l2.quet("1A02");
	assert.equal(da_goi.length, 2, "ô B phải ghi được — không bị chặn bởi 'số lượng phải > 0'");
	assert.equal(da_goi[1].so_luong, 50);
	assert.equal(da_goi[1].don_vi, "Cái");
	assert.equal(da_goi[1].lay_toi_da_theo_o, 1, "vẫn là số MẶC ĐỊNH — máy chủ được phép cắt theo tồn ô B");
});
