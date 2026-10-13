#!/usr/bin/env node
// PHÉP THỬ NGHIỆM THU CỦA KIẾN TRÚC TÁCH LỚP — tự động hoá.
//
// Luật 2 của "Bốn luật rút ra từ Task 1–3" đặt một phép thử cụ thể:
//
//     bọc `tao()` cho lớp LUỒNG trả một câu báo GIẢ;
//     CẢ HAI lớp VẼ phải hiện đúng câu đó.
//
// Phép thử ấy đã bắt được lỗi thật ít nhất hai lần (Task 2: trang Desk lật ngược
// phán quyết của luồng; Task 5: một hàm câu-chữ nằm NGOÀI `tao()` nên lọt lưới),
// nhưng suốt sáu Task nó là một NGHI THỨC TAY — các kịch bản Playwright nằm ở
// `/tmp` và biến mất. Soát xét tổng (M3) xếp đó là thứ giữ cho cả kiến trúc còn
// đúng mà không ai khoá lại. File này khoá nó.
//
// VÌ SAO PHẢI CHẠY TRONG TRÌNH DUYỆT: hai lớp vẽ là JS thao tác DOM. Không bài
// test Python/Node nào trong kho thực thi chúng (soát xét tổng, M4) — mọi thứ về
// hành vi lúc chạy nằm ngoài cổng. Đây là bài đầu tiên thực thi chúng thật.
//
// CÁCH VƯỢT RÀO `_luong` (biến `const`/module-scope, không ai chọc vào được):
// `addInitScript` chạy TRƯỚC mọi script của trang và dựng sẵn chuỗi namespace
// `erpnext.warehouse_operations.luong`, rồi đặt SETTER cho bốn khoá màn. Lớp luồng
// thật, khi nạp, gán `...luong.dat_o = { tao }` — setter bắt đúng khoảnh khắc đó,
// giữ module thật lại và thay bằng một module có `tao()` GIẢ. `frappe.provide` chỉ
// tạo khoá còn THIẾU nên không đạp lên chuỗi ta dựng sẵn. Cách này đã chạy được ở
// vòng soát Task 3, 4, 5.
//
// KHÔNG GHI MỘT DÒNG NÀO VÀO CSDL: `tao()` giả không gọi máy chủ; `goi`/
// `frappe.xcall` trong cả hai môi trường đều bị thay bằng hàm ném lỗi, nên bất kỳ
// lời gọi máy chủ nào cũng LỘ RA thay vì lặng lẽ chạy. Không đăng nhập.
//
// LỚP VẼ DESK CHẠY Ở ĐÂU: trang Desk cần một phiên `/app`. Để bài này chạy được
// mà không cần tài khoản, ta nạp ĐÚNG file JS thật của bốn trang Desk (đọc từ đĩa)
// vào trong chính trang `/kho` — nơi đã có sẵn `frappe-web.bundle.js` (`frappe.
// provide`, `frappe.utils.escape_html`, `frappe.utils.icon`, `frappe.datetime`,
// `__`, `flt`, `format_number`) — rồi dựng thêm một VỎ DESK tối thiểu
// (`frappe.pages`, `frappe.ui.make_app_page`, `frappe.ui.form.make_control`,
// `frappe.ui.Dialog`, `frappe.require`, `frappe.msgprint`...). Thứ được KIỂM là mã
// thật của lớp vẽ; thứ bị giả là cái vỏ Frappe quanh nó và lớp luồng dưới nó —
// đúng hai thứ phép thử này cần giả.
//
// CHẠY:  node scripts/kiem_giao_dien/kiem_cau_chu.js [URL]
// URL mặc định `http://192.168.61.129:8003`. Cần `bench build --app erpnext`
// trước, nếu không là đo bundle CŨ.

const fs = require("fs");
const path = require("path");

// Playwright của app `supplycore` cùng bench — THAM CHIẾU ĐƯỜNG DẪN, cố ý KHÔNG
// thêm gói vào `package.json` của erpnext (bài này là một cổng thủ công, không
// phải một phụ thuộc lúc dựng).
const DUONG_PLAYWRIGHT =
	"/home/hoangvietyeuem/frappe-bench-yhct/apps/supplycore/frontend/node_modules/playwright";

const GOC_APP = path.resolve(__dirname, "..", "..");
const GOC_URL = process.argv[2] || process.env.KHO_URL || "http://192.168.61.129:8003";

// Một câu GIẢ RIÊNG cho mỗi màn × mỗi lớp vẽ — riêng để một lượt PASS không thể
// là do đọc nhầm câu của lượt trước còn sót trên màn. Chỉ chữ/số/gạch nối: phép so
// chạy trên `innerText` (đã gỡ thẻ), nên không phụ thuộc lớp vẽ escape kiểu gì.
const dau = (man, lop) => `CAU-GIA-${man.toUpperCase()}-${lop.toUpperCase()}-7391`;

// ----------------------------------------------------------------- các màn
//
// Mỗi màn khai: lớp LUỒNG giả trả gì, và câu giả PHẢI hiện ở đâu. `mo_man` là
// cách đưa lớp vẽ tới lúc hiện câu đó.
const MAN = {
	tra_cuu: {
		ten_app: "tra-cuu",
		desk: "quet_ma_tra_cuu",
		// Câu "Không nhận ra mã này" (`quet().bao`) — phán quyết của luồng, cả hai
		// lớp vẽ chỉ hiện lại.
		luong: (cau) => ({
			quet: () => Promise.resolve({ loai: "khong_ro", du_lieu: null, bao: cau }),
			lich_su: () => [],
			xoa_lich_su: () => {},
			trang_thai_han: () => ({ muc: "khong", chu: "" }),
		}),
		// Cần một lượt QUÉT để `bao` ra màn.
		mo_man: "quet",
	},
	xep_hang: {
		ten_app: "xep-hang",
		desk: "xep_hang_pda",
		// `goi_y_o_quet.chu` — gợi ý dưới ô quét, cả hai lớp vẽ đều gọi
		// `o_quet.dat_goi_y(st.goi_y_o_quet.chu, ...)`.
		luong: (cau) => {
			const st = {
				kho: "KHO-GIA",
				kho_ds: ["KHO-GIA"],
				phieu: null,
				dong: [],
				cho: null,
				o_tren_tem: null,
				buoc: "cho_lo",
				goi_y_o_quet: { chu: cau, nhan_manh: false },
			};
			return {
				trang_thai: () => st,
				mo: () => Promise.resolve(st),
				lam_moi: () => Promise.resolve(st),
				doi_kho: () => st,
				quet: () => Promise.resolve({ buoc: "cho_lo", bao: "", muc: "xam" }),
			};
		},
		mo_man: null,
	},
	lay_hang: {
		ten_app: "lay-hang",
		desk: "lay_hang_pda",
		luong: (cau) => {
			const st = {
				kho: "KHO-GIA",
				kho_ds: ["KHO-GIA"],
				ds_phieu: [],
				phieu: null,
				dong: [],
				cho: null,
				lo_khac: null,
				buoc: "cho_lo",
				goi_y_o_quet: { chu: cau, nhan_manh: false },
				hien_nut_hoan_tat: false,
				trang_thai_tem: null,
				hien_doi_kho: false,
				khong_co_kho: false,
				hien_chon_kho: false,
			};
			return {
				trang_thai: () => st,
				mo: () => Promise.resolve(st),
				danh_sach: () => Promise.resolve(st),
				lam_moi: () => Promise.resolve(st),
				ve_danh_sach: () => Promise.resolve(st),
				doi_kho: () => st,
				quet: () => Promise.resolve({ buoc: "cho_lo", bao: "", muc: "xam" }),
			};
		},
		mo_man: null,
	},
	dat_o: {
		ten_app: "dat-o",
		desk: "dat_o_hang_loat",
		// `cau_dau` — câu mở đầu, cả hai lớp vẽ chỉ ghép vào khung.
		luong: (cau) => {
			const st = {
				kho: "KHO-GIA",
				kho_ds: ["KHO-GIA"],
				dong: [],
				dong_hien: [],
				bo_loc: "",
				cau_loc_trong: null,
				trong: true,
				so_dong_chon: 0,
				so_dong_thieu_o: 0,
				dat_duoc: false,
				cau_dau: cau,
				nhac_may_tinh: "",
				nhan_nut_dat: "nut-gia",
				canh_bao_thieu_o: null,
			};
			return {
				trang_thai: () => st,
				mo: () => Promise.resolve(st),
				nap: () => Promise.resolve(st),
				doi_kho: () => st,
				chon: () => st,
				chon_tat_ca: () => st,
				dat_bo_loc: () => st,
				dat_o_cho_dong: () => st,
				so_dong_chon: () => 0,
				dat_duoc: () => false,
				hoi_dat: () => Promise.resolve({ ok: false, bao: "", muc: "cam" }),
				dat: () => Promise.resolve({ da_dat: [], loi: [], bao: "", muc: "xanh" }),
			};
		},
		mo_man: null,
	},
};

// Script chèn TRƯỚC mọi script của trang: dựng chuỗi namespace + setter bắt đúng
// lúc lớp luồng thật đăng ký.
function script_chan(ten_luong, luong_gia_nguon) {
	return `
		(function () {
			window.__cau_gia_luong = ${luong_gia_nguon};
			window.erpnext = window.erpnext || {};
			erpnext.warehouse_operations = erpnext.warehouse_operations || {};
			var ns = (erpnext.warehouse_operations.luong = erpnext.warehouse_operations.luong || {});
			var that = null;
			Object.defineProperty(ns, ${JSON.stringify(ten_luong)}, {
				configurable: true,
				enumerable: true,
				get: function () {
					if (!that) return undefined;
					// Giữ nguyên mọi thứ module thật xuất ra (hằng số, hàm thuần như
					// \`nhan_loai\`) — CHỈ thay \`tao\`. Phép thử này nói về \`tao()\`.
					var thay = Object.assign({}, that);
					thay.tao = function () { return window.__cau_gia_luong; };
					return thay;
				},
				set: function (v) { that = v; },
			});
		})();
	`;
}

// Vỏ Desk tối thiểu + nạp file JS THẬT của một trang Desk, rồi chạy `on_page_load`.
const VO_DESK = `
	(function () {
		var $ = window.jQuery;
		// Frappe thật tự sinh khoá khi trang gán frappe.pages["x"].on_page_load.
		frappe.pages = new Proxy({}, { get: function (t, k) { if (!(k in t)) t[k] = {}; return t[k]; } });
		frappe.require = function (duong, cb) { if (cb) cb(); return Promise.resolve(); };
		frappe.xcall = function (d) { return Promise.reject(new Error("KHONG DUOC GOI MAY CHU: " + d)); };
		frappe.call = frappe.xcall;
		frappe.msgprint = function (o) { window.__desk_msgprint = o; };
		frappe.confirm = function (cau, co) { window.__desk_confirm = cau; };
		frappe.show_alert = function (o) { window.__desk_alert = o; };
		frappe.get_route = function () { return ["x"]; };
		frappe.set_route = function () {};
		frappe.session = frappe.session || {};
		frappe.session.user = frappe.session.user || "Administrator";
		frappe.session.user_fullname = frappe.session.user_fullname || "Administrator";
		frappe.ui = frappe.ui || {};
		frappe.ui.Dialog = function (o) {
			this.opts = o; window.__desk_dialog = o;
			this.show = function () {}; this.hide = function () {};
		};
		frappe.ui.form = frappe.ui.form || {};
		// Link control giả: chỉ cần một ô nhập + \`get_value\`/\`set_value\`.
		frappe.ui.form.make_control = function (o) {
			var $w = $('<div class="ctrl-gia"><input type="text"></div>').appendTo(o.parent);
			var c = {
				$wrapper: $w,
				df: o.df,
				get_value: function () { return $w.find("input").val(); },
				set_value: function (v) { $w.find("input").val(v == null ? "" : v); return Promise.resolve(); },
			};
			$w.find("input").on("change", function () { o.df.change && o.df.change(); });
			return c;
		};
		frappe.ui.make_app_page = function (o) {
			var $main = $('<div class="page-main"></div>').appendTo(o.parent);
			var $btn = $('<button class="btn-primary-gia"></button>').appendTo(o.parent);
			return {
				main: $main,
				btn_primary: $btn,
				wrapper: o.parent,
				add_field: function (df) {
					var $f = $('<div class="field-gia"><input type="text"></div>').appendTo(o.parent);
					return {
						df: df, $wrapper: $f,
						get_value: function () { return $f.find("input").val(); },
						set_value: function (v) { $f.find("input").val(v == null ? "" : v); },
					};
				},
				set_primary_action: function (nhan, fn) { $btn.text(nhan).off("click").on("click", fn); },
				set_indicator: function () {},
				set_title: function () {},
			};
		};
	})();
`;

function ma_trang_desk(thu_muc) {
	const p = path.join(GOC_APP, "erpnext", "warehouse_operations", "page", thu_muc, `${thu_muc}.js`);
	return fs.readFileSync(p, "utf-8");
}

// Tên route Desk (`frappe.pages["<slug>"]`) đọc từ chính file `.json` của trang —
// không đoán từ tên thư mục.
function route_desk(thu_muc) {
	const p = path.join(GOC_APP, "erpnext", "warehouse_operations", "page", thu_muc, `${thu_muc}.json`);
	return JSON.parse(fs.readFileSync(p, "utf-8")).name;
}

async function mo_trang(browser, ten_luong, luong_gia_nguon) {
	const ctx = await browser.newContext({ viewport: { width: 360, height: 640 } });
	const page = await ctx.newPage();
	const loi_js = [];
	page.on("pageerror", (e) => loi_js.push(String(e)));
	await page.addInitScript(script_chan(ten_luong, luong_gia_nguon));
	await page.goto(`${GOC_URL}/kho`, { waitUntil: "networkidle" });
	return { ctx, page, loi_js };
}

async function thu_lop_app(browser, ten_man, dn) {
	const cau = dau(ten_man, "app");
	const { ctx, page, loi_js } = await mo_trang(browser, ten_man, `(${dn.luong.toString()})(${JSON.stringify(cau)})`);
	try {
		// Trang `/kho` ép khách về màn thẻ. Gỡ cờ khách (KHÔNG đăng nhập, không gọi
		// máy chủ) rồi đi thẳng tới màn cần kiểm.
		await page.evaluate(() => {
			const a = erpnext.kho_pda.KhoApp;
			a.la_khach = false;
			a.nguoi_dung = "nguoi-gia";
			a.goi = () => Promise.reject(new Error("KHONG DUOC GOI MAY CHU"));
		});
		await page.evaluate((t) => erpnext.kho_pda.KhoApp.di(t), dn.ten_app);
		await page.waitForTimeout(400);
		if (dn.mo_man === "quet") {
			await page.fill(".oq-nhap", "MA-GIA");
			await page.press(".oq-nhap", "Enter");
			await page.waitForTimeout(400);
		}
		const chu = await page.evaluate(() => document.body.innerText);
		return { cau, thay: chu.includes(cau), loi_js };
	} finally {
		await ctx.close();
	}
}

async function thu_lop_desk(browser, ten_man, dn) {
	const cau = dau(ten_man, "desk");
	const { ctx, page, loi_js } = await mo_trang(browser, ten_man, `(${dn.luong.toString()})(${JSON.stringify(cau)})`);
	try {
		await page.evaluate(VO_DESK);
		await page.addScriptTag({ url: "/assets/erpnext/js/warehouse_operations/o_quet.js" });
		await page.addScriptTag({ content: ma_trang_desk(dn.desk) });
		await page.evaluate((route) => {
			const vo = document.createElement("div");
			vo.id = "vo-desk";
			document.body.appendChild(vo);
			frappe.pages[route].on_page_load(vo);
		}, route_desk(dn.desk));
		await page.waitForTimeout(500);
		if (dn.mo_man === "quet") {
			await page.fill("#vo-desk .oq-nhap", "MA-GIA");
			await page.press("#vo-desk .oq-nhap", "Enter");
			await page.waitForTimeout(400);
		}
		const chu = await page.evaluate(() => document.getElementById("vo-desk").innerText);
		return { cau, thay: chu.includes(cau), loi_js };
	} finally {
		await ctx.close();
	}
}

(async () => {
	const { chromium } = require(DUONG_PLAYWRIGHT);
	const browser = await chromium.launch();
	let hong = 0;
	console.log(`Phép thử "bọc tao() — cả hai lớp vẽ phải hiện câu của luồng"  ·  ${GOC_URL}\n`);
	try {
		for (const [ten_man, dn] of Object.entries(MAN)) {
			for (const [lop, chay] of [["app", thu_lop_app], ["desk", thu_lop_desk]]) {
				let kq;
				try {
					kq = await chay(browser, ten_man, dn);
				} catch (e) {
					kq = { cau: dau(ten_man, lop), thay: false, loi_js: [String(e)] };
				}
				const ok = kq.thay;
				if (!ok) hong += 1;
				console.log(
					`${ok ? "PASS" : "FAIL"}  ${ten_man.padEnd(10)} ${lop.padEnd(5)}  ${kq.cau}` +
						(ok ? "" : `\n        KHÔNG thấy câu của luồng trên màn — lớp vẽ đang tự kết luận.`)
				);
				if (kq.loi_js && kq.loi_js.length) {
					console.log(`        lỗi JS: ${kq.loi_js.slice(0, 3).join(" | ")}`);
				}
			}
		}
	} finally {
		await browser.close();
	}
	console.log(`\n${hong ? `${hong} phép thử HỎNG` : "Tất cả PASS — 4 màn × 2 lớp vẽ"}`);
	process.exit(hong ? 1 : 0);
})();
