// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam
//
// "Đối chiếu mua vào - bán ra" dựng đúng bố cục file Excel mẫu (Công nợ T10_Himedic):
// dòng tiêu đề, các khối KHÁCH HÀNG / NHÀ CUNG CẤP / ĐỐI CHIẾU, hàng tiêu đề cột, dòng
// TỔNG CỘNG. Số liệu lấy từ cùng `execute()` của report "Doi Chieu Mua Vao Ban Ra" nên
// trang, report và file xuất luôn khớp nhau.

const DCMB_API = "erpnext.accounts.report.doi_chieu_mua_vao_ban_ra.xuat_excel";

// [tiêu đề cột, hậu tố trường, kiểu]; mỗi khối bán / mua dùng chung danh sách này.
const DCMB_KHOI = [
	["Ngày HĐ", "ngay_hd", "ngay"],
	["Tên hàng hóa (nguyên văn hóa đơn)", "ten_hang", "chu"],
	["ĐVT", "dvt", "chu"],
	["SL", "sl", "so"],
	["Đơn giá (chưa VAT)", "don_gia", "gia"],
	["Thành tiền (chưa VAT)", "thanh_tien", "tien"],
	["Thuế suất", "thue_suat", "pt"],
	["Tiền thuế", "tien_thue", "tien"],
	["Tổng sau thuế", "tong", "tien"],
];

// Khối ĐỐI CHIẾU, cùng thứ tự `COT_DOI_CHIEU` (bỏ hai cột mã chứng từ: trang hiện link ở cột số HĐ).
const DCMB_DOI_CHIEU = [
	["Tỷ lệ giá bán / mua", "ty_le_gia", "ty_le"],
	["Chênh lệch giá (%)", "chenh_lech_pt", "pt"],
	["Chênh lệch thành tiền", "chenh_lech_tien", "tien"],
	["Trạng thái", "trang_thai", "trang_thai"],
	["Ghi chú", "ghi_chu", "chu"],
];

// Ô bên bán giống nhau giữa các mảnh của một dòng bán: gộp bằng rowspan như file Excel.
const DCMB_GOP = new Set(["ngay_hd", "ten_hang", "dvt", "don_gia", "thue_suat"]);

// Khớp `TRANG_THAI` / `CHUA_KHOP` trong phan_bo.py; dòng đầu rỗng = mọi dòng.
const DCMB_LOC_TRANG_THAI = [
	"",
	"Khớp",
	"Chưa khớp (mọi loại)",
	"Thiếu đầu vào",
	"Lệch giá",
	"Lệch thuế suất",
	"Lệch ĐVT",
	"Trả hàng",
];

frappe.pages["doi-chieu-mua-ban"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Đối chiếu mua vào - bán ra"),
		single_column: true,
	});

	const tai = frappe.utils.debounce(() => dcmb_tai(page), 300);
	const o = (df) => {
		const field = page.add_field({ ...df, label: __(df.label), change: tai });
		field.$wrapper.prepend(`<div class="dcmb-nhan">${__(df.label)}</div>`);
		return field;
	};
	page.fields = {
		company: o({
			fieldname: "company",
			label: "Công ty",
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		}),
		customer: o({ fieldname: "customer", label: "Khách hàng", fieldtype: "Link", options: "Customer" }),
		from_date: o({
			fieldname: "from_date",
			label: "Từ ngày (HĐ đầu ra)",
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
		}),
		to_date: o({
			fieldname: "to_date",
			label: "Đến ngày (HĐ đầu ra)",
			fieldtype: "Date",
			default: frappe.datetime.month_end(),
		}),
		supplier: o({ fieldname: "supplier", label: "NCC", fieldtype: "Link", options: "Supplier" }),
		trang_thai: o({
			fieldname: "trang_thai",
			label: "Trạng thái",
			fieldtype: "Select",
			options: DCMB_LOC_TRANG_THAI.join("\n"),
		}),
		ty_le_hd: o({
			fieldname: "ty_le_hd",
			label: "Tỷ lệ giá hợp đồng",
			fieldtype: "Float",
			default: 1.01,
		}),
	};

	page.set_primary_action(__("Xuất Excel"), () => {
		const filters = dcmb_bo_loc(page);
		if (!filters) return;
		const url = `/api/method/${DCMB_API}.xuat?filters=${encodeURIComponent(JSON.stringify(filters))}`;
		window.open(frappe.urllib.get_full_url(url));
	});
	page.set_secondary_action(__("Tải lại"), () => dcmb_tai(page));

	// append, không html(): page.main chứa sẵn .page-form (ô lọc) — ghi đè là mất bộ lọc.
	$(`${DCMB_CSS}<div class="dcmb"></div>`).appendTo(page.main);
	dcmb_tai(page);
};

function dcmb_bo_loc(page, im_lang) {
	const f = {};
	for (const [k, field] of Object.entries(page.fields)) {
		const v = field.get_value();
		if (v) f[k] = v;
	}
	if (!f.company || !f.customer || !f.from_date || !f.to_date) {
		if (!im_lang) frappe.msgprint(__("Chọn Công ty, Khách hàng và kỳ (Từ ngày / Đến ngày) trước."));
		return null;
	}
	return f;
}

function dcmb_tai(page) {
	const khung = page.main.find(".dcmb");
	const filters = dcmb_bo_loc(page, true);
	if (!filters) {
		khung.html(`<p class="text-muted">${__("Chọn Khách hàng và kỳ để xem bảng đối chiếu.")}</p>`);
		return;
	}
	khung.html(`<p class="text-muted">${__("Đang tải...")}</p>`);
	frappe
		.call(`${DCMB_API}.du_lieu_trang`, { filters })
		.then((r) => khung.html(dcmb_tom_tat(r.message) + dcmb_bang(r.message)));
}

function dcmb_so(v, so_le) {
	const chu = format_number(Math.abs(v), null, so_le);
	return v < 0 ? `<span class="am">(${chu})</span>` : chu;
}

function dcmb_o(v, kieu) {
	if (v === null || v === undefined || v === "") return "";
	if (kieu === "ngay") return frappe.datetime.str_to_user(v);
	if (kieu === "tien") return dcmb_so(v, 0);
	if (kieu === "gia" || kieu === "so") return dcmb_so(v, Number.isInteger(v) ? 0 : 2);
	if (kieu === "pt") return `${dcmb_so(v, Number.isInteger(v) ? 0 : 2)}%`;
	if (kieu === "ty_le") return format_number(v, null, 6);
	if (kieu === "trang_thai") {
		const lop = v === "Khớp" ? "khop" : v === "Trả hàng" ? "tra" : "lech";
		return `<span class="dcmb-tt ${lop}">${frappe.utils.escape_html(v)}</span>`;
	}
	return frappe.utils.escape_html(String(v));
}

// Số HĐ thật ở trên, mã chứng từ (link) ở dưới; chưa có số thì hiện "—" màu cảnh báo.
function dcmb_so_hd(so, doctype, ten) {
	if (!ten) return "";
	const link = `<a class="ma-ct" href="/app/${frappe.router.slug(doctype)}/${encodeURIComponent(ten)}">${frappe.utils.escape_html(ten)}</a>`;
	const chu = so ? frappe.utils.escape_html(so) : `<span class="thieu-so">—</span>`;
	return `${chu}<br>${link}`;
}

function dcmb_khoi(r, hau_to, rowspan) {
	return DCMB_KHOI.map(([, truong, kieu]) => {
		const gop = hau_to === "ban" && DCMB_GOP.has(truong);
		if (gop && rowspan === 0) return "";
		const lop =
			{ so: "so", gia: "so", tien: "so", pt: "so", ngay: "giua" }[kieu] ||
			(truong === "ten_hang" ? "ten" : "");
		const dinh = hau_to === "ban" && truong === "ten_hang" ? " dinh-ten" : "";
		const rs = gop && rowspan > 1 ? ` rowspan="${rowspan}"` : "";
		return `<td class="${lop}${dinh}"${rs}>${dcmb_o(r[`${truong}_${hau_to}`], kieu)}</td>`;
	}).join("");
}

function dcmb_doi_chieu(r) {
	return DCMB_DOI_CHIEU.map(([, truong, kieu]) => {
		const lop =
			{ ty_le: "so", pt: "so", tien: "so" }[kieu] || (truong === "ghi_chu" ? "ghi-chu" : "giua");
		// Dòng trả hàng: link về hoá đơn bán gốc ngay dưới ghi chú.
		const goc =
			truong === "ghi_chu" && r.tra_cho
				? `<br><a class="ma-ct" href="/app/sales-invoice/${encodeURIComponent(r.tra_cho)}">${frappe.utils.escape_html(r.tra_cho)}</a>`
				: "";
		return `<td class="${lop}">${dcmb_o(r[truong], kieu)}${goc}</td>`;
	}).join("");
}

function dcmb_tom_tat(kq) {
	const tong = ((kq && kq.data) || []).find((r) => r.la_tong);
	if (!tong) return "";
	const tt = tong.tom_tat || {};
	const dem = Object.entries(tt.dem || {})
		.filter(([, v]) => v)
		.map(([k, v]) => `${frappe.utils.escape_html(k)}: <b>${v}</b>`)
		.join(" · ");
	const the = (nhan, gia_tri, canh_bao) =>
		`<div class="dcmb-the${canh_bao ? " canh-bao" : ""}"><div class="nhan">${__(nhan)}</div><div class="so-lon">${gia_tri}</div></div>`;
	return `<div class="dcmb-tom-tat">
		${the("Doanh thu có đầu vào khớp", dcmb_o(tt.doanh_thu_co_dau_vao, "tien"))}
		${the("Doanh thu thiếu đầu vào", dcmb_o(tt.doanh_thu_thieu_dau_vao, "tien"), tt.doanh_thu_thieu_dau_vao > 0)}
		${the("Tỷ lệ giá bình quân (đã ghép)", tong.ty_le_gia == null ? "—" : dcmb_o(tong.ty_le_gia, "ty_le"))}
		${the("Chênh lệch (đã ghép)", dcmb_o(tong.chenh_lech_tien, "tien"))}
		${the("Số HĐ bán / mua", `${tt.so_hd_ban || 0} / ${tt.so_hd_mua || 0}`)}
		${the("Số dòng lệch (đã ghép)", tt.so_dong_lech || 0, tt.so_dong_lech > 0)}
		<div class="dcmb-dem">${dem}</div>
	</div>`;
}

function dcmb_bang(kq) {
	const data = (kq && kq.data) || [];
	const so_cot = 1 + 2 * (2 + DCMB_KHOI.length) + DCMB_DOI_CHIEU.length;
	const tieu_de_khoi = (doi_tac, so_hd, mau) =>
		[doi_tac, so_hd, ...DCMB_KHOI.map(([t]) => t)]
			.map((t) => {
				const dinh = t === DCMB_KHOI[1][0] && doi_tac === "KH" ? " dinh-ten" : "";
				return `<th class="${mau}${dinh}">${__(t)}</th>`;
			})
			.join("");

	// Số dòng liền nhau cùng STT: dòng đầu nhóm mang rowspan, các dòng sau bỏ ô gộp (0).
	const rowspan = data.map((r, i) => {
		if (r.la_tong || (i > 0 && data[i - 1].stt === r.stt && !data[i - 1].la_tong)) return 0;
		let n = 1;
		while (i + n < data.length && !data[i + n].la_tong && data[i + n].stt === r.stt) n++;
		return n;
	});

	const than = data.length
		? data
				.map((r, i) => {
					if (r.la_tong) {
						const o = (k) => `<td class="so">${dcmb_o(r[k], "tien")}</td>`;
						return `<tr class="tong">
							<td class="dinh-stt"></td><td></td><td></td><td></td>
							<td class="ten dinh-ten">${__("TỔNG CỘNG")}</td>
							<td></td><td></td><td></td>
							${o("thanh_tien_ban")}<td></td>${o("tien_thue_ban")}${o("tong_ban")}
							<td></td><td></td><td></td><td></td><td></td><td></td><td></td>
							${o("thanh_tien_mua")}<td></td>${o("tien_thue_mua")}${o("tong_mua")}
							<td class="so">${r.ty_le_gia == null ? "" : dcmb_o(r.ty_le_gia, "ty_le")}</td>
							<td class="so">${dcmb_o(r.chenh_lech_pt, "pt")}</td>
							${o("chenh_lech_tien")}<td></td><td></td>
						</tr>`;
					}
					const rs = rowspan[i];
					const gop = (html) =>
						rs === 0 ? "" : rs > 1 ? html.replace("<td", `<td rowspan="${rs}"`) : html;
					const lop = r.trang_thai === "Khớp" ? "" : ' class="co-van-de"';
					return `<tr${lop}>
						${gop(`<td class="giua dinh-stt">${r.stt}${r.manh ? `<div class="manh">${__("tách")} ${r.manh.split("/")[1]}</div>` : ""}</td>`)}
						${gop(`<td class="doi-tac">${dcmb_o(r.kh)}</td>`)}
						${gop(`<td class="giua so-hd-ra">${dcmb_so_hd(r.so_hd_ban, "Sales Invoice", r.sales_invoice)}</td>`)}
						${dcmb_khoi(r, "ban", rs)}
						<td class="doi-tac">${dcmb_o(r.ncc)}</td>
						<td class="giua">${dcmb_so_hd(r.so_hd_mua, "Purchase Invoice", r.purchase_invoice)}</td>
						${dcmb_khoi(r, "mua")}
						${dcmb_doi_chieu(r)}
					</tr>`;
				})
				.join("")
		: `<tr><td colspan="${so_cot}" class="giua text-muted">${__("Không có dòng nào khớp bộ lọc trong kỳ.")}</td></tr>`;

	return `<div class="dcmb-cuon">
		<table class="dcmb-bang">
			<thead>
				<tr><th colspan="${so_cot}" class="tieu-de"><span>${frappe.utils.escape_html(kq.tieu_de || "")}<small>${frappe.utils.escape_html(kq.ghi_chu_ky || "")}</small></span></th></tr>
				<tr class="khoi">
					<th class="dinh-stt mau-ncc"></th>
					<th class="mau-kh" colspan="${2 + DCMB_KHOI.length}">${__("KHÁCH HÀNG")} ${frappe.utils.escape_html(kq.ten_kh || "")}</th>
					<th class="mau-ncc" colspan="${2 + DCMB_KHOI.length}">${__("NHÀ CUNG CẤP")}</th>
					<th class="mau-dc" colspan="${DCMB_DOI_CHIEU.length}">${__("ĐỐI CHIẾU")}</th>
				</tr>
				<tr class="cot">
					<th class="dinh-stt mau-ncc">${__("STT")}</th>
					${tieu_de_khoi("KH", "Số HĐ đầu ra", "mau-kh")}
					${tieu_de_khoi("NCC", "Số HĐ đầu vào", "mau-ncc")}
					${DCMB_DOI_CHIEU.map(([t]) => `<th class="mau-dc">${__(t)}</th>`).join("")}
				</tr>
			</thead>
			<tbody>${than}</tbody>
		</table>
	</div>`;
}

const DCMB_CSS = `<style>
	.page-container[data-page-route="doi-chieu-mua-ban"] .container { max-width: 100%; }
	.page-container[data-page-route="doi-chieu-mua-ban"] .page-form { align-items: flex-end; }
	.dcmb-nhan { font-size: 11px; color: var(--text-muted); margin-bottom: 2px; white-space: nowrap; }
	.page-container[data-page-route="doi-chieu-mua-ban"] .page-form .placeholder { display: none; }
	.dcmb-tom-tat { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; align-items: stretch; }
	.dcmb-the { border: 1px solid var(--border-color); border-radius: 6px; padding: 6px 10px; background: var(--card-bg); min-width: 150px; }
	.dcmb-the .nhan { font-size: 11px; color: var(--text-muted); }
	.dcmb-the .so-lon { font-size: 15px; font-weight: 700; }
	.dcmb-the.canh-bao { border-color: var(--red-300); background: var(--red-50); }
	.dcmb-the.canh-bao .so-lon { color: var(--red-600); }
	.dcmb-dem { align-self: center; font-size: 12px; color: var(--text-muted); }
	.dcmb-cuon { overflow: auto; max-height: calc(100vh - 300px); border: 1px solid var(--border-color); }
	.dcmb-bang { border-collapse: separate; border-spacing: 0; font-family: "Times New Roman", Times, serif; font-size: 13px; color: #000; min-width: 100%; background: var(--card-bg); }
	.dcmb-bang th, .dcmb-bang td { border-right: 1px solid #BFBFBF; border-bottom: 1px solid #BFBFBF; padding: 4px 6px; vertical-align: top; background: #fff; }
	.dcmb-bang thead { position: sticky; top: 0; z-index: 3; }
	.dcmb-bang th { text-align: center; vertical-align: middle; font-weight: 700; font-size: 14px; color: #fff; }
	.dcmb-bang th.tieu-de { font-size: 22px; font-weight: 400; padding: 8px; background: #fff; color: #000; text-align: left; }
	.dcmb-bang th.tieu-de span { position: sticky; left: 8px; display: inline-block; }
	.dcmb-bang th.tieu-de small { display: block; font-size: 11px; font-weight: 400; font-style: italic; color: var(--text-muted); }
	.dcmb-bang .dinh-stt { position: sticky; left: 0; z-index: 2; width: 48px; min-width: 48px; max-width: 48px; }
	.dcmb-bang .dinh-ten { position: sticky; left: 48px; z-index: 2; box-shadow: 2px 0 0 var(--gray-400); }
	.dcmb-bang thead .dinh-stt, .dcmb-bang thead .dinh-ten { z-index: 4; }
	.dcmb-bang td.doi-tac { min-width: 170px; }
	/* Màu đúng file mẫu Công nợ T10_Himedic: xem các hằng _MAU_* trong xuat_excel.py. */
	.dcmb-bang th.mau-ncc { background: #1F2A4A; }
	.dcmb-bang th.mau-kh { background: #5B8DD9; }
	.dcmb-bang th.mau-dc { background: #595959; }
	.dcmb-bang td.so-hd-ra { background: #FFF2CC; }
	.dcmb-bang tr.cot th { white-space: normal; min-width: 70px; }
	.dcmb-bang td.so { text-align: right; white-space: nowrap; }
	.dcmb-bang td.giua { text-align: center; white-space: nowrap; }
	.dcmb-bang td.ten { min-width: 260px; }
	.dcmb-bang td.ghi-chu { min-width: 220px; color: var(--text-muted); }
	.dcmb-bang .am { color: var(--red-600); }
	.dcmb-bang .ma-ct { font-size: 10px; color: var(--text-muted); }
	.dcmb-bang .thieu-so { color: var(--orange-600); font-weight: 700; }
	.dcmb-bang .manh { font-size: 10px; color: var(--text-muted); }
	.dcmb-bang tr.co-van-de td.dinh-stt { box-shadow: inset 3px 0 0 var(--red-500); }
	.dcmb-tt { padding: 1px 6px; border-radius: 8px; font-size: 11px; white-space: nowrap; }
	.dcmb-tt.khop { background: var(--green-100); color: var(--green-800); }
	.dcmb-tt.lech { background: var(--red-100); color: var(--red-800); }
	.dcmb-tt.tra { background: var(--orange-100); color: var(--orange-800); }
	.dcmb-bang tr.tong td { font-weight: 700; background: #E8EEF8; }
	.dcmb-bang tbody tr:not(.tong):hover td:not(.so-hd-ra) { background: #F5F8FD; }
</style>`;
