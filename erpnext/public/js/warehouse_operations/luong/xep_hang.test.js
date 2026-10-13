// QUYẾT ĐỊNH (ghi trong báo cáo Task 3): bốn bài GỐC dưới đây giữ NGUYÊN VĂN mô tả
// kịch bản và mọi khẳng định (`assert`) của Bước 1, brief — nhưng field name trong
// đối tượng giả lập `quet_de_xep`/`them_dong_xep` đã SỬA lại cho khớp hợp đồng THẬT
// của máy chủ (`erpnext/warehouse_operations/vitri/xep.py::_mo_ta_lo` và
// `o_tem.py::kiem_o_tem`), thay vì bản `{ton_chua_xep, o_tren_tem}` viết tắt trong
// brief. Máy chủ THẬT trả `nguon` (mảng {o, ma_in_nhan, la_o_chua_xep, con_xep_duoc})
// + `tu_o_mac_dinh` cho "còn xếp được ở đâu", và `o_tem` là một OBJECT
// `{o, ma_in_nhan, loi, kiem, chua_co_o}` (xem `kiem_o_tem`), không phải một chuỗi
// `o_tren_tem`. Bài test theo bản viết tắt của brief sẽ XANH giả — `luong/xep_hang.js`
// viết để khớp bản đó sẽ ĐỌC SAI dữ liệu thật và hỏng ngay lượt quét đầu tiên trên
// site thật (đo được khi đối chiếu với `erpnext/warehouse_operations/tests/
// test_xep_pda.py::test_quet_lo_ra_mat_hang_nguon_va_mac_dinh_lay_tu_o_chua_xep`).
// Cùng loại quyết định mà Task 1/2 đã từng phải tự sửa chữ mẫu sai trong kế hoạch —
// xem `task-3-report.md`.
const { test } = require("node:test");
const assert = require("node:assert");
const { tao } = require("./xep_hang.js");

function gia_lap(bang) {
	return (duong_dan, doi_so) => {
		const ten = duong_dan.split(".").pop();
		if (!bang[ten]) throw new Error("gọi hàm không mong đợi: " + ten);
		return Promise.resolve(bang[ten](doi_so));
	};
}

// Một lô CÓ ô hợp lệ trên tem — hình dạng thật của `xep._mo_ta_lo()` khi
// `o_tem.kiem_o_tem` không báo lỗi.
function _lo_co_tem(so_lo, o_tem) {
	return {
		loai: "lo",
		vat_tu: "VT",
		ten_hang: "Hàng VT",
		don_vi: "Cái",
		so_lo,
		hsd: null,
		nguon: [{ o: o_tem, ma_in_nhan: o_tem, la_o_chua_xep: false, con_xep_duoc: 10 }],
		tu_o_mac_dinh: o_tem,
		o_tem: { o: o_tem, ma_in_nhan: o_tem, loi: null, kiem: true, chua_co_o: false },
		goi_y: { den_o: o_tem, ma_in_nhan: o_tem, ly_do: "theo ô in trên tem lô " + so_lo, tem_hong: false },
	};
}

function _o_that(ma_o) {
	return { loai: "o", ma_o, ma_in_nhan: ma_o, kho: "K", la_nhom: false };
}

test("quét lô rồi quét ô: hai bước, ghi ở bước hai", async () => {
	let da_them = null;
	const l = tao({
		goi: gia_lap({
			phieu_xep_dang_lam: () => ({ kho: "K", kho_ds: ["K"], phieu: null }),
			quet_de_xep: ({ ma }) => (ma === "LO-1" ? _lo_co_tem("LO-1", "1A01") : _o_that(ma)),
			them_dong_xep: (d) => {
				da_them = d;
				return { name: "XVT-1", kho: "K", dong: [{ name: "d1" }] };
			},
		}),
	});
	await l.mo("K");
	assert.equal((await l.quet("LO-1")).buoc, "cho_o");
	const sau = await l.quet("1A01");
	assert.equal(sau.buoc, "da_ghi");
	assert.equal(da_them.den_o, "1A01");
	assert.equal(da_them.so_lo, "LO-1");
});

test("quét ô SAI so với ô in trên tem thì KHÔNG ghi và báo rõ", async () => {
	let so_lan_them = 0;
	const l = tao({
		goi: gia_lap({
			phieu_xep_dang_lam: () => ({ kho: "K", kho_ds: ["K"], phieu: null }),
			quet_de_xep: ({ ma }) => (ma === "LO-1" ? _lo_co_tem("LO-1", "1A01") : _o_that(ma)),
			them_dong_xep: () => {
				so_lan_them += 1;
				return {};
			},
		}),
	});
	await l.mo("K");
	await l.quet("LO-1");
	const kq = await l.quet("9Z99");
	assert.equal(so_lan_them, 0, "ô sai tem mà vẫn ghi là vỡ luật 19/09/2026");
	assert.equal(kq.buoc, "cho_o");
	assert.match(kq.bao, /SAI Ô|tem ghi ô/i);
});

test("quét ô khi chưa quét lô thì nhắc quét lô, không gọi máy chủ ghi", async () => {
	let so_lan_them = 0;
	const l = tao({
		goi: gia_lap({
			phieu_xep_dang_lam: () => ({ kho: "K", kho_ds: ["K"], phieu: null }),
			quet_de_xep: () => _o_that("1A01"),
			them_dong_xep: () => {
				so_lan_them += 1;
				return {};
			},
		}),
	});
	await l.mo("K");
	const kq = await l.quet("1A01");
	assert.equal(so_lan_them, 0);
	assert.match(kq.bao, /quét tem LÔ|quét lô/i);
});

test("lô chưa có ô trên tem thì đòi đặt ô, không cho xếp", async () => {
	const l = tao({
		goi: gia_lap({
			phieu_xep_dang_lam: () => ({ kho: "K", kho_ds: ["K"], phieu: null }),
			quet_de_xep: () => ({
				loai: "lo",
				vat_tu: "VT",
				ten_hang: "Hàng VT",
				don_vi: "Cái",
				so_lo: "LO-2",
				hsd: null,
				nguon: [{ o: "ZZZ-CHUA-XEP", ma_in_nhan: null, la_o_chua_xep: true, con_xep_duoc: 5 }],
				tu_o_mac_dinh: "ZZZ-CHUA-XEP",
				o_tem: { o: null, ma_in_nhan: null, kiem: true, chua_co_o: true, loi: "Lô LO-2 chưa có ô trên tem." },
				goi_y: { den_o: null, ma_in_nhan: null, ly_do: "chưa gán", tem_hong: false },
			}),
		}),
	});
	await l.mo("K");
	const kq = await l.quet("LO-2");
	assert.equal(kq.can_xac_nhan, "dat_o_tren_tem");
	assert.match(kq.bao, /chưa có ô trên tem/i);
});

// ------------------------------------------------------- bài thêm (rà theo brief)

test("mã hàng CÓ quản lý lô mà quét mã hàng (không phải tem lô) thì nhắc quét tem LÔ", async () => {
	const l = tao({
		goi: gia_lap({
			phieu_xep_dang_lam: () => ({ kho: "K", kho_ds: ["K"], phieu: null }),
			quet_de_xep: () => ({ loai: "can_quet_lo", vat_tu: "VT", ten_hang: "Hàng VT" }),
		}),
	});
	await l.mo("K");
	const kq = await l.quet("VT");
	assert.equal(kq.buoc, "cho_lo");
	assert.match(kq.bao, /quét tem LÔ/);
});

test("mã không nhận ra thì báo rõ, không ném lỗi", async () => {
	const l = tao({
		goi: gia_lap({
			phieu_xep_dang_lam: () => ({ kho: "K", kho_ds: ["K"], phieu: null }),
			quet_de_xep: () => ({ loai: null }),
		}),
	});
	await l.mo("K");
	const kq = await l.quet("9Z-XXX");
	assert.match(kq.bao, /Không nhận ra/);
});

test("lô hết hàng để xếp (nguồn rỗng) thì báo, không đổi bước", async () => {
	const l = tao({
		goi: gia_lap({
			phieu_xep_dang_lam: () => ({ kho: "K", kho_ds: ["K"], phieu: null }),
			quet_de_xep: () => ({
				loai: "lo",
				vat_tu: "VT",
				so_lo: "LO-3",
				nguon: [],
				tu_o_mac_dinh: null,
				o_tem: { o: null, ma_in_nhan: null, kiem: false, chua_co_o: false, loi: null },
				goi_y: {},
			}),
		}),
	});
	await l.mo("K");
	const kq = await l.quet("LO-3");
	assert.equal(kq.buoc, "cho_lo");
	assert.match(kq.bao, /không còn hàng/i);
});

test("dat_so_luong() kẹp trong [0, con_xep_duoc của nguồn đang chọn]", async () => {
	const l = tao({
		goi: gia_lap({
			phieu_xep_dang_lam: () => ({ kho: "K", kho_ds: ["K"], phieu: null }),
			quet_de_xep: () => _lo_co_tem("LO-1", "1A01"),
		}),
	});
	await l.mo("K");
	await l.quet("LO-1");
	l.dat_so_luong(999);
	assert.equal(l.trang_thai().cho.so_luong, 10);
	l.dat_so_luong(-5);
	assert.equal(l.trang_thai().cho.so_luong, 0);
});

test("chon_nguon() đổi ô lấy hàng và tính lại số lượng mặc định", async () => {
	const l = tao({
		goi: gia_lap({
			phieu_xep_dang_lam: () => ({ kho: "K", kho_ds: ["K"], phieu: null }),
			quet_de_xep: () => ({
				loai: "lo",
				vat_tu: "VT",
				so_lo: "LO-1",
				nguon: [
					{ o: "CHUA-XEP", ma_in_nhan: null, la_o_chua_xep: true, con_xep_duoc: 30 },
					{ o: "1A01", ma_in_nhan: "1A01", la_o_chua_xep: false, con_xep_duoc: 8 },
				],
				tu_o_mac_dinh: "CHUA-XEP",
				o_tem: { o: null, ma_in_nhan: null, kiem: false, chua_co_o: false, loi: null },
				goi_y: {},
			}),
		}),
	});
	await l.mo("K");
	await l.quet("LO-1");
	assert.equal(l.trang_thai().cho.so_luong, 30);
	l.chon_nguon("1A01");
	assert.equal(l.trang_thai().cho.tu_o, "1A01");
	assert.equal(l.trang_thai().cho.so_luong, 8);
});

test("bo_lo() huỷ lô đang chờ, về lại bước chờ lô", async () => {
	const l = tao({
		goi: gia_lap({
			phieu_xep_dang_lam: () => ({ kho: "K", kho_ds: ["K"], phieu: null }),
			quet_de_xep: () => _lo_co_tem("LO-1", "1A01"),
		}),
	});
	await l.mo("K");
	await l.quet("LO-1");
	assert.equal(l.trang_thai().buoc, "cho_o");
	l.bo_lo();
	assert.equal(l.trang_thai().buoc, "cho_lo");
	assert.equal(l.trang_thai().cho, null);
});

test("lỗi nghiệp vụ khi ghi dòng (máy chủ chặn) không bị luồng nuốt — nổi lên cho màn tự bắt", async () => {
	const l = tao({
		goi: gia_lap({
			phieu_xep_dang_lam: () => ({ kho: "K", kho_ds: ["K"], phieu: null }),
			quet_de_xep: ({ ma }) => (ma === "LO-1" ? _lo_co_tem("LO-1", "1A01") : _o_that(ma)),
			them_dong_xep: () => {
				throw new Error("Ô 1A01 chỉ còn 3 chưa lên phiếu — không xếp 10 được.");
			},
		}),
	});
	await l.mo("K");
	await l.quet("LO-1");
	await assert.rejects(() => l.quet("1A01"), /chỉ còn 3/);
	// Lô vẫn đang chờ — không bị xoá vì máy chủ từ chối ghi.
	assert.equal(l.trang_thai().buoc, "cho_o");
});

test("đặt ô trên tem: quét ô rồi lô tự chuyển sang chờ xếp vào đúng ô đó", async () => {
	let da_doi = null;
	const l = tao({
		goi: gia_lap({
			phieu_xep_dang_lam: () => ({ kho: "K", kho_ds: ["K"], phieu: null }),
			quet_de_xep: ({ ma }) => {
				if (ma === "LO-2" && !da_doi) {
					return {
						loai: "lo",
						vat_tu: "VT",
						so_lo: "LO-2",
						nguon: [{ o: "CHUA-XEP", ma_in_nhan: null, la_o_chua_xep: true, con_xep_duoc: 5 }],
						tu_o_mac_dinh: "CHUA-XEP",
						o_tem: { o: null, ma_in_nhan: null, kiem: true, chua_co_o: true, loi: "chưa có ô trên tem" },
						goi_y: {},
					};
				}
				if (ma === "LO-2" && da_doi) return _lo_co_tem("LO-2", "9B01");
				return _o_that(ma);
			},
			doi_o_tren_tem: (d) => {
				da_doi = d;
				return { o: d.o_moi, ma_in_nhan: d.o_moi, o_cu: null };
			},
		}),
	});
	await l.mo("K");
	const b1 = await l.quet("LO-2");
	assert.equal(b1.can_xac_nhan, "dat_o_tren_tem");
	l.bat_dau_dat_o();
	assert.equal(l.trang_thai().o_tren_tem.dang_cho_quet, true);
	const b2 = await l.quet("9B01");
	assert.equal(da_doi.so_lo, "LO-2");
	assert.equal(da_doi.o_moi, "9B01");
	assert.equal(b2.buoc, "cho_o");
	assert.equal(l.trang_thai().o_tren_tem, null);
	assert.equal(l.trang_thai().cho.tu_o, "9B01");
});

test("doi_kho() đặt lại kho/phiếu/lô đang chờ mà KHÔNG gọi máy chủ", async () => {
	let so_lan_goi = 0;
	const l = tao({
		goi: gia_lap({
			phieu_xep_dang_lam: () => {
				so_lan_goi += 1;
				return { kho: "K", kho_ds: ["K", "K2"], phieu: null };
			},
			quet_de_xep: () => _lo_co_tem("LO-1", "1A01"),
		}),
	});
	await l.mo("K");
	await l.quet("LO-1");
	assert.equal(so_lan_goi, 1);
	l.doi_kho();
	assert.equal(so_lan_goi, 1, "đổi kho không gọi máy chủ — server tự chọn lại nếu nạp lại");
	assert.equal(l.trang_thai().kho, null);
	assert.equal(l.trang_thai().cho, null);
});

test("xoa_dong() gọi máy chủ đúng tham số và cập nhật phiếu", async () => {
	const l = tao({
		goi: gia_lap({
			phieu_xep_dang_lam: () => ({
				kho: "K",
				kho_ds: ["K"],
				phieu: { name: "XVT-1", kho: "K", dong: [{ name: "d1" }, { name: "d2" }] },
			}),
			xoa_dong_xep: (d) => {
				assert.equal(d.phieu, "XVT-1");
				assert.equal(d.dong, "d1");
				return { name: "XVT-1", kho: "K", dong: [{ name: "d2" }] };
			},
		}),
	});
	await l.mo("K");
	const st = await l.xoa_dong("d1");
	assert.equal(st.dong.length, 1);
	// Soát xét vòng 1, mục 5: câu báo + mức màu của "đã bỏ dòng" là quyết định của
	// LUỒNG, không phải lớp vẽ tự gõ riêng.
	assert.match(st.bao, /Đã bỏ một dòng/);
	assert.equal(st.muc, "xam");
});

test("duyet() thành công thì dọn phiếu/lô đang chờ và báo số dòng", async () => {
	const l = tao({
		goi: gia_lap({
			phieu_xep_dang_lam: () => ({
				kho: "K",
				kho_ds: ["K"],
				phieu: { name: "XVT-1", kho: "K", dong: [{ name: "d1" }] },
			}),
			duyet_phieu_xep: (d) => {
				assert.equal(d.phieu, "XVT-1");
				return { name: "XVT-1", so_dong: 1 };
			},
		}),
	});
	await l.mo("K");
	const kq = await l.duyet();
	assert.equal(kq.ok, true);
	assert.equal(kq.ten, "XVT-1");
	assert.equal(l.trang_thai().phieu, null);
	// Soát xét vòng 1, mục 5: mức màu "xanh" cho duyệt thành công là quyết định của
	// LUỒNG, không phải lớp vẽ tự chọn cố định.
	assert.equal(kq.muc, "xanh");
});

// ------------------------------------------------- bài thêm, soát xét vòng 1

test("câu báo đánh dấu đậm bằng ** quanh số lượng và mã ô — lớp vẽ tự tô đậm an toàn từ đó", async () => {
	const l = tao({
		goi: gia_lap({
			phieu_xep_dang_lam: () => ({ kho: "K", kho_ds: ["K"], phieu: null }),
			quet_de_xep: ({ ma }) => (ma === "LO-1" ? _lo_co_tem("LO-1", "1A01") : _o_that(ma)),
			them_dong_xep: () => ({ name: "XVT-1", kho: "K", dong: [{ name: "d1" }] }),
		}),
	});
	await l.mo("K");
	await l.quet("LO-1");
	const sau = await l.quet("1A01");
	// "Đã xếp **10** Cái ... → **1A01**" — số lượng và mã ô đích đều nằm giữa **.
	assert.match(sau.bao, /\*\*10\*\*/);
	assert.match(sau.bao, /\*\*1A01\*\*/);
});

test("câu SAI Ô đánh dấu đậm đúng ô ghi trên tem (placeholder thứ ba), không đánh dấu ô vừa quét sai", async () => {
	const l = tao({
		goi: gia_lap({
			phieu_xep_dang_lam: () => ({ kho: "K", kho_ds: ["K"], phieu: null }),
			quet_de_xep: ({ ma }) => (ma === "LO-1" ? _lo_co_tem("LO-1", "1A01") : _o_that(ma)),
		}),
	});
	await l.mo("K");
	await l.quet("LO-1");
	const kq = await l.quet("9Z99");
	assert.match(kq.bao, /tem ghi ô \*\*1A01\*\*/);
	assert.doesNotMatch(kq.bao, /\*\*9Z99\*\*/);
});
