#!/usr/bin/env node
// Cổng nghiệm thu cho BẢN ĐÓNG GÓI: chứng minh bốn màn dựng được khi KHÔNG có
// Frappe web bundle — thứ mà bản `/kho` trên web vẫn đang mượn.
//
// VÌ SAO PHẢI CÓ: giao diện dựa vào ~7 toàn cục của Frappe (`__`, `flt`, jQuery,
// `frappe.utils.escape_html`, `frappe.datetime.*`…). Trong app không có Frappe.
// Sót MỘT cái là MỘT màn chết lúc chạy, và không bài test nào của kho bắt được.
//
// KHÁC GÌ `kiem_cau_chu.js` (cổng đã có): cổng kia mở `/kho` TRÊN MÁY CHỦ — nơi
// `frappe-web.bundle.js` có mặt — và giả LỚP LUỒNG để soi câu chữ. Cổng này làm
// ngược lại: mở `file://…/pda_app/www/index.html` (không máy chủ, không Frappe),
// giữ LỚP LUỒNG THẬT, chỉ giả MÁY CHỦ. Hai cổng soi hai thứ khác nhau và không
// thay thế được cho nhau.
//
// NĂM PHÉP KHẲNG ĐỊNH, KHÔNG PHẢI MỘT — "có nội dung + không lỗi" một mình là
// XANH cho cả một lớp shim sai mà vẫn chạy. Mỗi phép dưới đây được ĐO bằng cách
// cố tình làm hỏng đúng một toàn cục rồi chạy lại cổng (kết quả trong
// `task-1-report.md`):
//   1. không `pageerror` VÀ không `unhandledrejection`. Vế sau bắt buộc: ba trong
//      bốn màn vẽ bên trong chuỗi `.then()` (xem `man_lay_hang.js::nap`), nên một
//      toàn cục thiếu ở đó nổi lên dưới dạng promise bị từ chối, KHÔNG phải lỗi
//      cấp trang — `page.on("pageerror")` không thấy.
//   2. thân màn có nội dung thật (không phải khung rỗng).
//   3. chữ hiện ra không chứa `undefined` / `NaN` / `{0}`. Bắt: `frappe.utils.icon`
//      trả `undefined` (in ra chữ "undefined" cạnh ô quét); `__(chu, doi_so)` bỏ
//      qua `doi_so` (in nguyên `{0}`). Không cái nào ném lỗi.
//   4. chữ hiện ra CHỨA đúng con số và ngày đã định dạng (`chu_phai_co`). Ba phép
//      trên BỎ LỌT ba ca đã đo được: `flt` trả CHUỖI (`"1234.5".toLocaleString()`
//      vẫn chạy, chỉ mất dấu nhóm nghìn); `frappe.datetime.str_to_user` VẮNG MẶT
//      (mỗi màn có `.catch(bao_loi)` riêng, nuốt `TypeError` thành một dải báo đỏ
//      rồi màn vẫn "có nội dung"); và mọi ca mà màn vẽ ra khung nhưng không vẽ ra
//      DỮ LIỆU. Kiểm giá trị ĐÃ ĐỊNH DẠNG là cách duy nhất phân biệt.
//   5. dữ liệu giả cắm một thẻ HTML thật (`DAU_HIEU_KHONG_THOAT`) vào một trường
//      TÊN; thẻ đó KHÔNG được trở thành phần tử trong DOM. `frappe.utils.escape_html`
//      hạ cấp thành hàm trả nguyên chuỗi là một hồi quy AN NINH thật (xem
//      `vo.js::_dam`) mà bốn phép trên đều xanh — đo được.
//
// DỮ LIỆU GIẢ CỐ Ý KHÔNG RỖNG: với phiếu `null` và danh sách `[]`, bốn màn chỉ vẽ
// trạng thái trống — `flt`, `str_to_user`, `trang_thai_han` KHÔNG hàm nào chạy, và
// cổng sẽ XANH với một `shim.js` trống rỗng. Mỗi màn vì thế nhận một bộ dữ liệu có
// số lượng và có ngày tháng.
//
// KHÔNG GỌI MÁY CHỦ THẬT: `KhoApp.goi` bị thay bằng bảng tra dưới đây; một đường
// dẫn lạ làm hỏng bài thay vì lặng lẽ đi ra mạng.
//
// CHẠY:  node scripts/kiem_giao_dien/kiem_ban_dong_goi.js
// Cần `scripts/pda/dong-goi.sh` chạy trước (www/ phải có bản dựng).

const fs = require("fs");
const path = require("path");

// Playwright của app `supplycore` cùng bench — THAM CHIẾU ĐƯỜNG DẪN, cố ý KHÔNG
// thêm gói vào `package.json` nào (cùng lý do `kiem_cau_chu.js`).
const DUONG_PLAYWRIGHT =
	"/home/hoangvietyeuem/frappe-bench-yhct/apps/supplycore/frontend/node_modules/playwright";

const GOC_APP = path.resolve(__dirname, "..", "..");
const TRANG = path.join(GOC_APP, "pda_app", "www", "index.html");

// Ngày cố định trong dữ liệu giả — KHÔNG lấy theo hôm nay: `trang_thai_han()` phân
// loại theo khoảng cách tới hôm nay, nhưng bài này không kiểm phán quyết đó (đó là
// việc của `node --test` trên lớp luồng), chỉ cần một chuỗi ngày ĐI QUA
// `frappe.datetime.str_to_user`. Cố định thì kết quả bài không đổi theo ngày chạy.
const NGAY_GIA = "2027-03-15";
const NGAY_GIA_NGUOI_DOC = "15-03-2027"; // khuôn `dd-mm-yyyy` của System Settings

// Cắm một thẻ HTML THẬT vào một trường TÊN của dữ liệu giả. Nếu `escape_html` làm
// đúng việc, chuỗi này hiện ra như CHỮ; nếu nó bị hạ cấp thành hàm trả nguyên
// chuỗi thì thẻ trở thành PHẦN TỬ và `getElementById` tìm thấy — đó là toàn bộ
// phép thử. Dùng `<span>` rỗng, không phải `<script>`: chỉ cần chứng minh trình
// duyệt đã DỰNG thẻ, không cần (và không nên) chạy bất cứ thứ gì.
const DAU_HIEU_KHONG_THOAT = '<span id="dau-hieu-khong-thoat"></span>';

// Máy chủ GIẢ — bảng tra "đường dẫn hàm whitelist → phần `message` máy chủ trả về".
// Viết dưới dạng NGUỒN CHUỖI vì nó được tiêm vào trang qua `page.evaluate`.
function nguon_may_chu_gia() {
	return `
		(function () {
			var V = ${JSON.stringify({ ngay: NGAY_GIA, xss: DAU_HIEU_KHONG_THOAT })};
			var BANG = {
				// Tra cứu: một LÔ đầy đủ — số lượng (flt), hạn dùng + ngày SX + ngày
				// nhập (str_to_user), tồn theo ô (flt trong vòng lặp).
				"erpnext.warehouse_operations.vitri.quet.tra_cuu": {
					loai: "lo",
					so_lo: "LO-GIA-001",
					vat_tu: "VT-GIA-001",
					ten_hang: "Găng tay khám bệnh cỡ M" + V.xss,
					don_vi: "Hộp",
					hsd: V.ngay,
					ngay_san_xuat: "2025-03-15",
					ngay_nhap: "2025-04-02",
					so_goi: 12,
					so_phieu_nhap: "PN-GIA-001",
					nha_cung_cap: "NCC Giả",
					vi_tri_co_dinh: "7A01010101",
					o_in_tem: "7A01010101",
					ton_theo_o: [
						{ o: "7A01010101", so_luong: 1234.5 },
						{ o: "7A01010102", so_luong: 8 },
					],
				},
				// Xếp hàng: một phiếu nháp có hai dòng — nhãn dòng + số lượng.
				"erpnext.warehouse_operations.vitri.xep.phieu_xep_dang_lam": {
					kho: "Kho Giả - MYN",
					kho_ds: ["Kho Giả - MYN"],
					phieu: {
						name: "XEP-GIA-0001",
						dong: [
							{
								name: "dong-1",
								so_lo: "LO-GIA-001",
								vat_tu: "VT-GIA-001",
								ten_hang: "Găng tay khám bệnh cỡ M" + V.xss,
								tu_o: "7A01010101",
								den_o: "7A01010102",
								so_luong: 250,
								don_vi: "Hộp",
							},
							{
								name: "dong-2",
								vat_tu: "VT-GIA-002",
								ten_hang: "Bơm tiêm 5ml",
								tu_o_chua_xep: true,
								den_o: "7A01020101",
								so_luong: 1000,
								don_vi: "Cái",
							},
						],
					},
				},
				// Lấy hàng: danh sách phiếu giao — mỗi thẻ in "đã lấy / cần lấy" và số
				// dòng qua \`flt\`.
				"erpnext.warehouse_operations.vitri.lay_hang.danh_sach_phieu_giao": {
					kho: "Kho Giả - MYN",
					kho_ds: ["Kho Giả - MYN"],
					phieu: [
						{
							name: "DN-GIA-0001",
							khach_hang: "Bệnh viện Giả" + V.xss,
							da_lay: 3,
							can_lay: 1250,
							so_dong: 4,
							nguoi_dang_lay: [],
						},
						{
							name: "DN-GIA-0002",
							khach_hang: "Phòng khám Giả",
							da_lay: 0,
							can_lay: 25,
							so_dong: 2,
							nguoi_dang_lay: ["thukho-gia"],
						},
					],
				},
				// Đặt ô: các lô chưa có ô — tồn (flt) + HSD (str_to_user).
				"erpnext.warehouse_operations.vitri.o_tem.lo_chua_co_o": [
					{
						so_lo: "LO-GIA-001",
						vat_tu: "VT-GIA-001",
						ten_hang: "Găng tay khám bệnh cỡ M" + V.xss,
						ton: 1242.5,
						dang_o: "7A01010101",
						hsd: V.ngay,
						o_goi_y: "7A01010102",
						ma_in_nhan_goi_y: "7A01010102",
					},
					{
						so_lo: "LO-GIA-002",
						vat_tu: "VT-GIA-002",
						ten_hang: "Bơm tiêm 5ml",
						ton: 1000,
						dang_o: null,
						hsd: null,
						o_goi_y: null,
						ma_in_nhan_goi_y: null,
						ly_do: "Mặt hàng chưa gán vị trí cố định.",
					},
				],
			};
			window.__may_chu_gia = function (duong_dan) {
				if (!(duong_dan in BANG)) {
					return Promise.reject(new Error("MAY CHU GIA khong biet duong dan: " + duong_dan));
				}
				// Bản sao sâu mỗi lượt: lớp luồng giữ lại và sửa tại chỗ (\`_chuan_hoa_dong\`
				// trải object ra, nhưng \`phieu.dong\` thì dùng thẳng) — trả CÙNG một object
				// cho hai màn sẽ để màn trước làm bẩn dữ liệu của màn sau.
				return Promise.resolve(JSON.parse(JSON.stringify(BANG[duong_dan])));
			};
			// Lấy hàng chỉ cần danh sách để vẽ; khai luôn \`mo_phieu_giao\` để nếu màn
			// lỡ mở một phiếu thì hỏng LỘ RA bằng câu trên, không đi ra mạng thật.
		})();
	`;
}

// Bốn màn. `mo_man` = thao tác cần làm sau khi vào màn để nội dung thật hiện ra.
//
// `chu_phai_co` = giá trị ĐÃ ĐỊNH DẠNG phải đọc được trên màn. Mỗi chuỗi là dấu
// vân tay của MỘT toàn cục làm đúng việc, chọn sao cho một shim hạ cấp là lệch
// ngay: số có dấu nhóm nghìn kiểu `vi-VN` (`1.234,5`) chỉ ra được khi `flt` trả
// một SỐ THẬT — trả chuỗi thì `toLocaleString` in "1234.5"; ngày `dd-mm-yyyy` chỉ
// ra được khi `frappe.datetime.str_to_user` có mặt VÀ đảo đúng thứ tự.
const MAN = [
	{
		ten: "tra-cuu",
		mo_man: "quet",
		chu_phai_co: [
			{ chu: "1.234,5", vi_sao: "flt() + toLocaleString('vi-VN') trên tồn theo ô" },
			{ chu: NGAY_GIA_NGUOI_DOC, vi_sao: "frappe.datetime.str_to_user() trên hạn dùng" },
		],
	},
	{
		ten: "xep-hang",
		mo_man: null,
		chu_phai_co: [{ chu: "1.000", vi_sao: "flt() + toLocaleString('vi-VN') trên số lượng dòng phiếu" }],
	},
	{
		ten: "lay-hang",
		mo_man: null,
		chu_phai_co: [{ chu: "1.250", vi_sao: "flt() + toLocaleString('vi-VN') trên 'đã lấy/cần lấy'" }],
	},
	{
		ten: "dat-o",
		mo_man: null,
		chu_phai_co: [
			{ chu: "1.242,5", vi_sao: "flt() + toLocaleString('vi-VN') trên tồn" },
			{ chu: NGAY_GIA_NGUOI_DOC, vi_sao: "frappe.datetime.str_to_user() trên HSD" },
		],
	},
];

// Chuỗi KHÔNG ĐƯỢC hiện ra màn. Mỗi chuỗi là dấu vết của một shim CÓ MẶT nhưng
// TRẢ SAI — hạng lỗi không ném exception nào, nên hai phép "không lỗi"/"có nội
// dung" đều bỏ lọt.
const CHU_CAM = [
	{ chu: "undefined", vi_sao: "một shim trả undefined và bị nội suy thẳng vào HTML (ví dụ frappe.utils.icon)" },
	{ chu: "NaN", vi_sao: "flt() không đổi được chuỗi thành số" },
	{ chu: "{0}", vi_sao: "__(chu, doi_so) bỏ qua doi_so, không thay chỗ trống" },
];

// Bắt cả lỗi cấp trang LẪN promise bị từ chối. Chạy TRƯỚC mọi script của trang để
// không bỏ sót lỗi ngay lúc tải bundle.
const SCRIPT_BAT_LOI = `
	window.__loi_async = [];
	window.addEventListener("unhandledrejection", function (e) {
		window.__loi_async.push(String((e.reason && e.reason.stack) || e.reason));
	});
`;

async function thu_mot_man(browser, dn) {
	const ctx = await browser.newContext({ viewport: { width: 360, height: 640 } });
	const page = await ctx.newPage();
	const loi = [];
	page.on("pageerror", (e) => loi.push(String(e)));
	await page.addInitScript(SCRIPT_BAT_LOI);
	// TASK 5: `khoi_dong()` (vo.js) tự bắn một lời gọi đồng bộ giờ máy chủ
	// (`gio_may_chu`) ngay khi mở app — cờ này tắt nó ĐÚNG Ở ĐÂY, vì "KHÔNG GỌI
	// MÁY CHỦ THẬT" là bất biến CỦA BÀI NÀY (xem khối chú thích đầu file): trang
	// `file://` này không có máy chủ giả nào để nhận lời gọi đó, và `KHO_MAY_CHU`
	// dưới đây trỏ vào một địa chỉ thật ngoài kho mã — một lượt gọi lọt ra ngoài
	// là đúng thứ bất biến đó cấm.
	await page.addInitScript(`window.KHO_BO_QUA_DONG_BO_GIO = true;`);
	try {
		await page.goto("file://" + TRANG);
		// Không `networkidle`: trang `file://` không có yêu cầu mạng nào để chờ rỗi.
		// Đợi đúng thứ cần: khung do `vo.js` dựng. Hết giờ = bundle chết lúc tải —
		// ca ĐỎ mà bài này sinh ra để bắt, nên để lỗi hết giờ nổi lên nguyên vẹn.
		await page.waitForSelector("#kho-app .kho-than", { timeout: 5000 });

		await page.evaluate(nguon_may_chu_gia());
		await page.evaluate(() => {
			const a = erpnext.kho_pda.KhoApp;
			// Vỏ đóng gói khởi động ở trạng thái khách (ép về màn thẻ). Gỡ cờ đó —
			// KHÔNG đăng nhập, không gọi máy chủ — để đi thẳng tới màn nghiệp vụ.
			a.la_khach = false;
			a.nguoi_dung = "thukho-gia";
			a.goi = (duong_dan) => window.__may_chu_gia(duong_dan);
		});
		await page.evaluate((ten) => erpnext.kho_pda.KhoApp.di(ten), dn.ten);
		await page.waitForTimeout(600);

		if (dn.mo_man === "quet") {
			await page.fill(".oq-nhap", "LO-GIA-001");
			await page.press(".oq-nhap", "Enter");
			await page.waitForTimeout(600);
		}

		const do_duoc = await page.evaluate(() => ({
			than: document.querySelector("#kho-app .kho-than").innerText,
			toan_than: document.body.innerText,
			man: erpnext.kho_pda.KhoApp.man_hien_tai,
			loi_async: window.__loi_async.slice(),
			// `getElementById`, KHÔNG tìm chuỗi trong `innerHTML`: chỉ phần tử ĐÃ DỰNG
			// mới trả về khác `null`, còn cùng chuỗi ấy nằm dưới dạng chữ đã thoát
			// (`&lt;span…`) thì không.
			the_khong_thoat: !!document.getElementById("dau-hieu-khong-thoat"),
		}));
		loi.push(...do_duoc.loi_async);

		const sai = [];
		if (loi.length) sai.push(`lỗi JS: ${loi.slice(0, 3).join(" | ")}`);
		if (do_duoc.man !== dn.ten) sai.push(`màn đang hiện là "${do_duoc.man}", không phải "${dn.ten}"`);
		if (do_duoc.than.trim().length < 20) sai.push("thân màn gần như rỗng — lớp vẽ không dựng được gì");
		for (const cam of CHU_CAM) {
			if (do_duoc.toan_than.includes(cam.chu)) {
				sai.push(`màn in ra "${cam.chu}" — ${cam.vi_sao}`);
			}
		}
		for (const can of dn.chu_phai_co) {
			if (!do_duoc.toan_than.includes(can.chu)) {
				sai.push(`không thấy "${can.chu}" trên màn — ${can.vi_sao}`);
			}
		}
		if (do_duoc.the_khong_thoat) {
			sai.push("thẻ HTML trong dữ liệu máy chủ đã DỰNG thành phần tử — frappe.utils.escape_html không thoát");
		}
		return sai;
	} catch (e) {
		return [`${e && e.message ? e.message : String(e)}`, ...loi.slice(0, 3)];
	} finally {
		await ctx.close();
	}
}

(async () => {
	if (!fs.existsSync(TRANG)) {
		console.error(`Không thấy ${TRANG}`);
		process.exit(1);
	}
	for (const ten of ["kho_pda.bundle.js", "kho_pda.bundle.css"]) {
		if (!fs.existsSync(path.join(path.dirname(TRANG), ten))) {
			console.error(`Thiếu ${ten} trong pda_app/www — chạy scripts/pda/dong-goi.sh trước.`);
			process.exit(1);
		}
	}

	const { chromium } = require(DUONG_PLAYWRIGHT);
	const browser = await chromium.launch();
	let hong = 0;
	console.log(`Cổng BẢN ĐÓNG GÓI — bốn màn dựng được khi KHÔNG có Frappe\n  ${TRANG}\n`);
	try {
		for (const dn of MAN) {
			const sai = await thu_mot_man(browser, dn);
			if (sai.length) {
				hong += 1;
				console.log(`FAIL  ${dn.ten}`);
				for (const s of sai) console.log(`        ${s}`);
			} else {
				console.log(`PASS  ${dn.ten}`);
			}
		}
	} finally {
		await browser.close();
	}
	console.log(`\n${hong ? `${hong}/${MAN.length} màn HỎNG` : `Tất cả PASS — ${MAN.length}/${MAN.length} màn`}`);
	process.exit(hong ? 1 : 0);
})();
