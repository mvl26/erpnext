// Lớp LUỒNG của màn "Xếp hàng vào ô" — cùng khuôn tách lớp mà Task 2 dựng ở
// `luong/tra_cuu.js` (đọc file đó trước, đừng phát minh lại): phần QUYẾT ĐỊNH
// ("quét mã này thì làm gì", "ô này có đúng ô trên tem không", "số lượng mặc định
// là bao nhiêu", nhãn và câu báo) nằm Ở ĐÂY, dùng chung cho CẢ HAI nơi — màn app PDA
// (`kho_pda/man_xep_hang.js`) và trang Desk cũ
// (`warehouse_operations/page/xep_hang_pda/xep_hang_pda.js`, chuyển sang dùng lớp
// này ở Bước 6 của brief Task 3). File này KHÔNG đụng DOM, không gọi `frappe.*`
// trực tiếp — `goi` (hàm gọi máy chủ) TIÊM TỪ NGOÀI, đúng lý do đã giải thích ở đầu
// `tra_cuu.js`: đây là điều kiện DUY NHẤT để chạy được trong Node lúc `node --test`.
//
// ĐÂY LÀ MÀN ĐẦU TIÊN CÓ GHI (Task 3, brief): mọi quyết định "có được ghi hay
// không" (ô sai tem, số lượng ≤ 0, chưa quét lô, lô chưa có ô trên tem) phải chặn
// ở ĐÂY, TRƯỚC khi gọi máy chủ — không phải vì máy chủ không tự chặn (nó có,
// `LocationTransfer.validate` + `o_tem.chan_neu_sai_o`), mà vì chặn sớm tiết kiệm
// một lượt gọi mạng trên một chiếc PDA có thể đang ở rìa sóng wifi kho, và báo
// được NGAY, không đợi round-trip.
//
// LỖI MÁY CHỦ (validate thật sự từ chối, vd. "chỉ còn 3 chưa lên phiếu") KHÔNG bị
// nuốt ở đây — `quet()`/`xoa_dong()`/`duyet()` để nguyên promise bị TỪ CHỐI (không
// try/catch quanh lời gọi ghi), cho màn (lớp vẽ) tự bắt và hiển thị theo cách của
// môi trường mình (app: `KhoApp.bao(loi.message,"do")`; Desk: `frappe.xcall` tự
// hiện popup). Đây là chốt PHÂN BIỆT quan trọng với các nhánh "quyết định của
// chính luồng" (SAI Ô, chưa quét lô…) — những nhánh đó KHÔNG PHẢI lỗi, là kết quả
// hợp lệ của một lượt quét, nên `quet()` LUÔN resolve cho chúng, không bao giờ ném.
// Đúng tinh thần `man_tra_cuu.js`: "goi() đã tự lo phiên hết hạn/mất mạng — màn chỉ
// còn lỗi nghiệp vụ thật sự bất ngờ phải tự bắt".

function _dich(chu, doi_so) {
	if (typeof __ === "function") return __(chu, doi_so);
	if (!doi_so) return chu;
	return chu.replace(/\{(\d+)\}/g, (_, i) => (doi_so[i] !== undefined ? doi_so[i] : ""));
}

// `frappe.utils.flt` không có trong Node — bản rút gọn đủ dùng cho số lượng gõ tay
// (có thể là chuỗi từ một ô `<input type=number>`, hoặc số thật từ máy chủ).
function _flt(gia_tri) {
	if (typeof gia_tri === "number") return isNaN(gia_tri) ? 0 : gia_tri;
	const n = parseFloat(String(gia_tri == null ? "" : gia_tri).replace(/,/g, ""));
	return isNaN(n) ? 0 : n;
}

// Đường dẫn máy chủ — NGUYÊN VĂN từ Interfaces của brief Task 3, một chỗ duy nhất
// để sửa nếu `vitri/xep.py`/`vitri/o_tem.py` đổi tên hàm.
const API_PHIEU_XEP_DANG_LAM = "erpnext.warehouse_operations.vitri.xep.phieu_xep_dang_lam";
const API_QUET_DE_XEP = "erpnext.warehouse_operations.vitri.xep.quet_de_xep";
const API_THEM_DONG_XEP = "erpnext.warehouse_operations.vitri.xep.them_dong_xep";
const API_XOA_DONG_XEP = "erpnext.warehouse_operations.vitri.xep.xoa_dong_xep";
const API_DUYET_PHIEU_XEP = "erpnext.warehouse_operations.vitri.xep.duyet_phieu_xep";
const API_DOI_O_TREN_TEM = "erpnext.warehouse_operations.vitri.o_tem.doi_o_tren_tem";

// Câu báo — MỘT NƠI (soát xét Task 2, P4: lặp câu ở ba nơi là nợ, sửa một chỗ quên
// chỗ kia). Không dùng thẻ HTML (`<b>…</b>`) như bản Desk gốc: `KhoApp.bao()`
// (vo.js, Task 1) LUÔN escape chuỗi truyền vào — thẻ đậm sẽ hiện ra thành chữ
// `&lt;b&gt;` trên màn app. Rớt phần tô đậm, GIỮ NGUYÊN mọi giá trị động (số, mã,
// tên) — không phải một quyết định nghiệp vụ, không cắt gì.
// SOÁT XÉT VÒNG 1 (Task 3, mục 3): cặp `**…**` đánh dấu phần lớp vẽ nên TÔ ĐẬM —
// đúng những giá trị bản Desk gốc từng bọc `<b>…</b>` (số lượng, mã ô, mã lô —
// những thứ thủ kho cần liếc nhanh nhất trên màn 4 inch), KHÔNG bọc những placeholder
// còn lại (đơn vị, tên hàng…), giữ ĐÚNG NGUYÊN vị trí tô đậm gốc. Đây là CHỮ THƯỜNG
// có quy ước, không phải HTML — lớp vẽ (`vo.js::_dam()`/tương đương ở Desk) tự
// escape TRƯỚC rồi mới đổi `**x**` thành `<b>x</b>` CỦA RIÊNG NÓ, nên máy chủ không
// có cách nào nhét được một thẻ thật qua chuỗi này (xem `vo.js`). Khoá bằng
// `xep_hang.test.js` ("câu báo đánh dấu đậm...").
const CAU_KHONG_NHAN_RA = "Không nhận ra mã **{0}**.";
const CAU_CAN_QUET_LO = "{0} có quản lý lô — quét tem LÔ trên thùng, không quét mã hàng.";
const CAU_CHUA_CHON_KHO = "Chọn kho trước khi quét.";
const CAU_LO_HET_HANG = "Lô **{0}** không còn hàng nào để xếp ở kho này (hoặc đã lên hết phiếu).";
const CAU_TEM_VI_TRI_MA_CHUA_QUET_LO = "Đây là tem vị trí **{0}**. Quét tem LÔ trước, rồi mới quét tem ô.";
const CAU_LO_O_NHIEU_O = "Lô này đang nằm ở nhiều ô — chạm chọn ô LẤY hàng ra trước.";
const CAU_SO_LUONG_PHAI_DUONG = "Số lượng phải lớn hơn 0.";
const CAU_SAI_O = "SAI Ô. Ô {0} không phải ô in trên tem lô {1} — tem ghi ô **{2}**.";
const CAU_DA_XEP = "Đã xếp **{0}** {1} {2} → **{3}**";
const CAU_QUET_O_DE_DAT_TEM = "Quét tem Ô muốn đặt làm ô trên tem của lô **{0}**.";
const CAU_DA_DAT_O_TEM =
	"Ô trên tem lô **{0}** giờ là **{1}**. NHỚ IN LẠI TEM trên máy tính và dán lên thùng. " +
	"Quét tem ô đó lần nữa để xếp hàng vào.";
const CAU_DA_DUYET =
	"Đã ghi phiếu {0} — {1} dòng. Quét tem lô để bắt đầu phiếu mới.";
const CAU_DA_BO_DONG = "Đã bỏ một dòng.";

function tao({ goi }) {
	// -------------------------------------------------------------- trạng thái
	let kho = null;
	let kho_ds = [];
	let phieu = null;
	// Lô đang chờ quét tem Ô để xếp — `null` = đang ở bước ① (chờ quét lô). Hình
	// dạng: nguyên văn `_mo_ta_lo()` của máy chủ (`vat_tu, ten_hang, don_vi, so_lo,
	// hsd, nguon, o_tem, goi_y`) CỘNG hai trường máy chủ không biết: `tu_o` (ô đang
	// CHỌN để lấy hàng ra, có thể đổi bằng `chon_nguon`) và `so_luong` (số định xếp).
	let cho = null;
	// Lô vừa quét mà CHƯA có ô trên tem — chờ người dùng bấm "Đặt ô trên tem" rồi
	// quét tem Ô muốn đặt. `dat_o` khác `cho`: đây không phải một lô SẮP XẾP, mà là
	// một lô đang chờ được GẮN Ô lên tem trước đã.
	let dat_o = null;
	let cho_quet_dat_o = false;

	// ---------------------------------------------------------------- nội bộ

	function _nguon_dang_chon() {
		return cho && (cho.nguon || []).find((n) => n.o === cho.tu_o);
	}

	function _dat_so_luong_theo_nguon() {
		const n = _nguon_dang_chon();
		cho.so_luong = n ? _flt(n.con_xep_duoc) : 0;
	}

	function _goi_y_o_quet() {
		if (!kho) return { chu: _dich("Chọn kho để bắt đầu"), nhan_manh: false };
		if (cho_quet_dat_o && dat_o) {
			return { chu: _dich("Quét tem Ô để đặt lên tem lô {0}", [dat_o.so_lo]), nhan_manh: true };
		}
		if (cho) {
			const g = cho.goi_y || {};
			return g.theo_tem
				? { chu: _dich("② Quét tem ô {0} (ô trên tem lô)", [g.ma_in_nhan || g.den_o]), nhan_manh: true }
				: {
						chu: _dich("② Quét tem Ô trên kệ để xếp {0}", [cho.so_lo || cho.ten_hang]),
						nhan_manh: true,
				  };
		}
		return { chu: _dich("① Quét tem LÔ cần xếp"), nhan_manh: false };
	}

	// Một lô MỚI vừa được nhận diện — luật 19/09/2026 (ô phải khớp ô in trên tem)
	// quyết định NGAY tại đây, trước khi lô có cơ hội trở thành `cho`: lô chưa có ô
	// / ô hỏng thì KHÔNG được xếp, dừng ngay, không đợi tới lúc quét ô mới báo (thủ
	// kho đỡ phải ôm thùng ra tới kệ rồi mới biết phải quay về in tem).
	//
	// Luôn dọn `dat_o`/`cho_quet_dat_o` khi một lô MỚI được xử lý (kể cả khi lô đó
	// hoá ra vẫn chưa có ô) — một lô khác được quét trong lúc màn đang "chờ đặt ô
	// trên tem" của lô TRƯỚC nghĩa là thủ kho đã đổi ý, không còn ở giữa luồng đặt
	// ô đó nữa; không dọn thì `dat_o`/`cho_quet_dat_o` treo lại một trạng thái không
	// còn khớp với `cho` hiện tại (bản Desk gốc có kẽ hở này — xem quyết định trong
	// báo cáo Task 3).
	function _nhan_lo(d) {
		dat_o = null;
		cho_quet_dat_o = false;
		if (!d.nguon || !d.nguon.length) {
			cho = null;
			return { buoc: "cho_lo", bao: _dich(CAU_LO_HET_HANG, [d.so_lo || d.vat_tu]), muc: "cam" };
		}
		const t = d.o_tem || {};
		if (t.kiem && t.loi) {
			cho = null;
			// Lô CHƯA có ô trên tem: thủ kho đặt được ngay tại kệ (chủ đầu tư,
			// 20/09/2026) — `can_xac_nhan` báo cho lớp vẽ biết hiện nút "Đặt ô trên
			// tem". Ô trên tem HỎNG là ca khác: đổi ô đã có là quyền trưởng kho, làm
			// trên máy tính — không có nút, không có `can_xac_nhan`.
			dat_o = t.chua_co_o ? { vat_tu: d.vat_tu, so_lo: d.so_lo, ten_hang: d.ten_hang } : null;
			return {
				buoc: "cho_lo",
				bao: t.loi,
				muc: "do",
				can_xac_nhan: t.chua_co_o ? "dat_o_tren_tem" : undefined,
			};
		}
		if (t.kiem) {
			// Ô trên tem HỢP LỆ: gợi ý máy chủ trả về (`goi_y_o`, dựa trên vùng gán)
			// bị THAY THẾ hoàn toàn bởi ô trên tem — luật 19/09/2026 không chừa chỗ
			// cho một gợi ý "hay hơn" nào khác một khi tem đã có ô.
			d.goi_y = { den_o: t.o, ma_in_nhan: t.ma_in_nhan, theo_tem: true };
		}
		cho = { ...d, tu_o: d.tu_o_mac_dinh, so_luong: 0 };
		_dat_so_luong_theo_nguon();
		return { buoc: "cho_o", bao: "", muc: "xam" };
	}

	async function _them_dong(o) {
		const c = cho;
		const ket_qua = await goi(API_THEM_DONG_XEP, {
			kho,
			vat_tu: c.vat_tu,
			so_lo: c.so_lo,
			tu_o: c.tu_o,
			den_o: o.ma_o,
			so_luong: c.so_luong,
		});
		// Chỉ đổi trạng thái SAU KHI máy chủ xác nhận ghi thành công — lời gọi ở
		// trên ném lỗi (số lượng vượt tồn, ô nhóm, ngừng dùng…) thì `cho` GIỮ
		// NGUYÊN, để thủ kho quét lại đúng ô hoặc sửa số lượng, không phải quét lại
		// từ đầu tem LÔ.
		phieu = ket_qua;
		const bao = _dich(CAU_DA_XEP, [
			String(c.so_luong),
			c.don_vi || "",
			c.so_lo || c.ten_hang,
			o.ma_in_nhan || o.ma_o,
		]);
		cho = null;
		return { buoc: "da_ghi", bao, muc: "xanh" };
	}

	function _nhan_o(o) {
		if (!cho) {
			return {
				buoc: "cho_lo",
				bao: _dich(CAU_TEM_VI_TRI_MA_CHUA_QUET_LO, [o.ma_in_nhan || o.ma_o]),
				muc: "cam",
			};
		}
		if (!cho.tu_o) {
			return { buoc: "cho_o", bao: _dich(CAU_LO_O_NHIEU_O), muc: "cam" };
		}
		if (!(_flt(cho.so_luong) > 0)) {
			return { buoc: "cho_o", bao: _dich(CAU_SO_LUONG_PHAI_DUONG), muc: "cam" };
		}
		const g = cho.goi_y || {};
		if (g.theo_tem && o.ma_o !== g.den_o) {
			return {
				buoc: "cho_o",
				bao: _dich(CAU_SAI_O, [o.ma_in_nhan || o.ma_o, cho.so_lo, g.ma_in_nhan || g.den_o]),
				muc: "do",
			};
		}
		return _them_dong(o);
	}

	// -------------------------------------------------- đặt ô trên tem (nhánh phụ)

	async function _dat_o_tem(o) {
		const lo = dat_o;
		const kq = await goi(API_DOI_O_TREN_TEM, { so_lo: lo.so_lo, o_moi: o.ma_o });
		cho_quet_dat_o = false;
		dat_o = null;
		const bao = _dich(CAU_DA_DAT_O_TEM, [lo.so_lo, kq.ma_in_nhan || kq.o]);
		// Nạp lại thẻ lô: giờ đã có ô trên tem nên xếp được ngay — thủ kho không
		// phải quét lại tem LÔ lần hai chỉ để hệ tự xác nhận việc mình vừa làm.
		const d = await goi(API_QUET_DE_XEP, { kho, ma: lo.so_lo });
		if (d && d.loai === "lo") {
			const ket_qua = _nhan_lo(d);
			return { buoc: ket_qua.buoc, bao, muc: "xanh", can_xac_nhan: ket_qua.can_xac_nhan };
		}
		return { buoc: "cho_lo", bao, muc: "xanh" };
	}

	async function _dat_o_tem_qua_quet(ma) {
		const d = await goi(API_QUET_DE_XEP, { kho, ma });
		if (!d || d.loai !== "o") {
			// Không phải tem Ô — nhắc lại, KHÔNG rời khỏi chế độ đặt ô: thủ kho có
			// thể vừa quét nhầm một tem khác trong lúc tay đang cầm tem Ô định đặt.
			// (Cải tiến so với bản Desk gốc: bản gốc chỉ chặn nhánh này bên TRONG
			// `nhan_o`, nên một tem LÔ quét nhầm giữa lúc "chờ đặt ô" sẽ lẳng lặng
			// coi như một lượt quét lô MỚI mà quên dọn `dat_o`/`cho_quet_dat_o` —
			// xem quyết định này trong báo cáo Task 3.)
			return {
				buoc: "cho_lo",
				bao: _dich(CAU_QUET_O_DE_DAT_TEM, [dat_o.so_lo]),
				muc: "cam",
				can_xac_nhan: "dat_o_tren_tem",
			};
		}
		return _dat_o_tem(d);
	}

	// --------------------------------------------------------------- API công bố

	async function mo(kho_muon) {
		cho = null;
		dat_o = null;
		cho_quet_dat_o = false;
		const r = await goi(API_PHIEU_XEP_DANG_LAM, { kho: kho_muon || null });
		kho_ds = r.kho_ds || [];
		kho = r.kho;
		phieu = r.phieu;
		return trang_thai();
	}

	// Nạp lại phiếu của kho HIỆN TẠI — dùng khi quay lại màn (Desk: `on_page_show`)
	// hoặc sau khi `duyet()` bị máy chủ từ chối (phiếu/dòng có thể đã đổi). KHÔNG
	// đụng `cho`/`dat_o` — đây không phải một lượt "mở màn mới", chỉ là "đọc lại
	// đúng những gì máy chủ đang giữ cho kho này".
	async function lam_moi() {
		const r = await goi(API_PHIEU_XEP_DANG_LAM, { kho });
		kho_ds = r.kho_ds || [];
		kho = r.kho;
		phieu = r.phieu;
		return trang_thai();
	}

	// "Đổi kho": về màn chọn kho. KHÔNG gọi máy chủ — không truyền kho thì máy chủ
	// tự chọn lại đúng kho vừa rời (kho của phiếu nháp gần nhất, xem
	// `phieu_xep_dang_lam`), một vòng round-trip vô ích cho đúng việc "quay lại nơi
	// vừa đứng" (nguyên quyết định của Desk gốc, Bước "Chọn kho" — giữ lại vì đúng,
	// không phải phát sinh mới).
	function doi_kho() {
		kho = null;
		phieu = null;
		cho = null;
		dat_o = null;
		cho_quet_dat_o = false;
		return trang_thai();
	}

	async function quet(ma) {
		const ma_sach = String(ma == null ? "" : ma).trim();
		if (!ma_sach) return { buoc: cho ? "cho_o" : "cho_lo", bao: "", muc: "xam" };
		if (!kho) return { buoc: "cho_lo", bao: _dich(CAU_CHUA_CHON_KHO), muc: "cam" };

		if (cho_quet_dat_o && dat_o) return _dat_o_tem_qua_quet(ma_sach);

		const d = await goi(API_QUET_DE_XEP, { kho, ma: ma_sach });
		if (!d || !d.loai) {
			return { buoc: cho ? "cho_o" : "cho_lo", bao: _dich(CAU_KHONG_NHAN_RA, [ma_sach]), muc: "xam" };
		}
		if (d.loai === "can_quet_lo") {
			return {
				buoc: cho ? "cho_o" : "cho_lo",
				bao: _dich(CAU_CAN_QUET_LO, [d.ten_hang || d.vat_tu]),
				muc: "cam",
			};
		}
		if (d.loai === "lo") return _nhan_lo(d);
		if (d.loai === "o") return _nhan_o(d);
		return { buoc: cho ? "cho_o" : "cho_lo", bao: _dich(CAU_KHONG_NHAN_RA, [ma_sach]), muc: "xam" };
	}

	function dat_so_luong(so) {
		if (!cho) return trang_thai();
		const n = _nguon_dang_chon();
		const toi_da = n ? _flt(n.con_xep_duoc) : Infinity;
		cho.so_luong = Math.min(toi_da, Math.max(0, _flt(so)));
		return trang_thai();
	}

	// Đổi Ô LẤY HÀNG khi một lô đang nằm ở nhiều ô (ca CHUYỂN Ô) — không có trong
	// danh sách "Produces" của brief (chỉ liệt `mo/quet/dat_so_luong/xoa_dong/
	// duyet/trang_thai`), nhưng bản Desk gốc CÓ tính năng này (`chon_nguon`, nút
	// "Lấy từ ô — chạm để đổi") — rule 5 (gộp lấy bản GIÀU hơn) đòi giữ lại, đúng
	// cách `tra_cuu.js` cũng thêm nhiều hàm ngoài "Produces" gốc của brief Task 2.
	function chon_nguon(o) {
		if (!cho) return trang_thai();
		cho.tu_o = o;
		_dat_so_luong_theo_nguon();
		return trang_thai();
	}

	// "Bỏ lô này" — huỷ lô đang chờ xếp, về lại bước ① mà KHÔNG ghi gì (chưa gọi
	// máy chủ lần nào ở bước này). Cùng lý do thêm ngoài "Produces": tính năng có
	// sẵn ở Desk gốc, không được phép rơi rụng khi gộp lớp.
	function bo_lo() {
		cho = null;
		return trang_thai();
	}

	// Bấm "Đặt ô trên tem": chuyển sang chế độ chờ quét tem Ô để GẮN lên tem (khác
	// hẳn quét tem Ô để XẾP). Chỉ có tác dụng khi đang thật sự có một lô chờ đặt ô
	// (`can_xac_nhan: "dat_o_tren_tem"` từ một lượt `quet()` trước đó).
	function bat_dau_dat_o() {
		if (!dat_o) return trang_thai();
		cho_quet_dat_o = true;
		return trang_thai();
	}

	// Huỷ chế độ "chờ đặt ô trên tem" — Desk gốc KHÔNG có lối thoát này (chỉ ra
	// khỏi chế độ bằng cách đặt ô thành công, hoặc âm thầm bằng kẽ hở đã sửa ở
	// `_nhan_lo`/`_dat_o_tem_qua_quet` phía trên). Thêm một cách THOÁT TƯỜNG MINH
	// là cải tiến hợp lý cho một màn có GHI: bấm nhầm "Đặt ô trên tem" không nên
	// bắt thủ kho phải quét một tem Ô thật để quay lại bước quét lô.
	function huy_dat_o() {
		cho_quet_dat_o = false;
		dat_o = null;
		return trang_thai();
	}

	// SOÁT XÉT VÒNG 1 (Task 3, mục 5): `bao`/`muc` của "Đã bỏ một dòng." từng do
	// LỚP VẼ tự đặt (`man_xep_hang.js:391` gõ nguyên văn, `xep_hang_pda.js` cũng
	// gõ riêng) — vi phạm luật 1 của khuôn ("lớp luồng sở hữu MỌI quyết định, kể cả
	// nhãn và câu báo"). Chuyển vào đây, MỘT nơi.
	async function xoa_dong(ten_dong) {
		const r = await goi(API_XOA_DONG_XEP, { phieu: phieu.name, dong: ten_dong });
		phieu = r || null;
		return { ...trang_thai(), bao: _dich(CAU_DA_BO_DONG), muc: "xam" };
	}

	async function duyet() {
		if (!phieu || !phieu.dong.length) return { ok: false, bao: "" };
		const ten = phieu.name;
		const so_dong = phieu.dong.length;
		// KHÔNG try/catch ở đây — máy chủ từ chối (dòng/ô sai lệch phát sinh sau khi
		// đã lên phiếu) phải NỔI LÊN cho lớp vẽ tự `lam_moi()` rồi hiện đúng câu máy
		// chủ trả về (nguyên ý `duyet_phieu_xep`: hỏng thì phiếu nháp và các dòng
		// còn NGUYÊN, không phải lỗi của luồng để tự bịa cách xử lý).
		const kq = await goi(API_DUYET_PHIEU_XEP, { phieu: ten });
		phieu = null;
		cho = null;
		return {
			ok: true,
			ten: kq.name || ten,
			so_dong: kq.so_dong || so_dong,
			bao: _dich(CAU_DA_DUYET, [kq.name || ten, kq.so_dong || so_dong]),
			// `muc` (mức màu của dải báo) từng do LỚP VẼ tự chọn "xanh" cố định
			// (`man_xep_hang.js:414` — soát xét vòng 1, mục 5). Duyệt phiếu LUÔN là
			// tin tốt khi tới được đây (nhánh lỗi ném ở dòng trên, không rơi xuống
			// đây), nên "xanh" là một HẰNG SỐ hợp lý — nhưng hằng số đó phải sống ở
			// lớp luồng, không phải mỗi lớp vẽ tự nhớ riêng một bản.
			muc: "xanh",
		};
	}

	function trang_thai() {
		return {
			kho,
			kho_ds: kho_ds.slice(),
			phieu,
			dong: phieu ? phieu.dong : [],
			cho,
			o_tren_tem: dat_o
				? {
						so_lo: dat_o.so_lo,
						vat_tu: dat_o.vat_tu,
						ten_hang: dat_o.ten_hang,
						dang_cho_quet: cho_quet_dat_o,
				  }
				: null,
			buoc: cho ? "cho_o" : "cho_lo",
			goi_y_o_quet: _goi_y_o_quet(),
		};
	}

	return {
		mo,
		lam_moi,
		doi_kho,
		quet,
		dat_so_luong,
		chon_nguon,
		bo_lo,
		bat_dau_dat_o,
		huy_dat_o,
		xoa_dong,
		duyet,
		trang_thai,
	};
}

// ------------------------------------------------------------- hai môi trường
// HAI CÂU `if` ĐỘC LẬP, KHÔNG `if/else` — chép NGUYÊN lý do đầy đủ ở cuối
// `tra_cuu.js` (esbuild bọc `__commonJS` nên `typeof module` đúng cả trong trình
// duyệt; hai `if` rời không phụ thuộc thứ tự viết, khác `if/else`).
if (typeof frappe !== "undefined" && frappe.provide) {
	frappe.provide("erpnext.warehouse_operations.luong");
	erpnext.warehouse_operations.luong.xep_hang = { tao };
}
if (typeof module !== "undefined" && module.exports) {
	module.exports = { tao };
}
