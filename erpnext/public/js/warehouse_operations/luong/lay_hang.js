// Lớp LUỒNG của màn "Lấy hàng theo phiếu giao" — cùng khuôn tách lớp mà Task 2
// dựng ở `luong/tra_cuu.js` và Task 3 nhân bản ở `luong/xep_hang.js` (đọc hai file
// đó trước, đừng phát minh lại): phần QUYẾT ĐỊNH ("quét mã này thì làm gì", "lô này
// có lấy được không", "số lượng/đơn vị/số kiện mặc định là bao nhiêu", nhãn và câu
// báo) nằm Ở ĐÂY, dùng chung cho CẢ HAI nơi — màn app PDA (`kho_pda/man_lay_hang.js`)
// và trang Desk cũ (`warehouse_operations/page/lay_hang_pda/lay_hang_pda.js`,
// chuyển sang dùng lớp này ở Bước 6 của brief Task 4).
//
// File này KHÔNG đụng DOM, không gọi `frappe.*` trực tiếp — mọi thứ phụ thuộc môi
// trường TIÊM TỪ NGOÀI qua `tao({goi, ngay})`; đây là điều kiện DUY NHẤT để chạy
// được trong Node lúc `node --test`, và là điều mà bài test tĩnh
// `test_giao_dien.py::test_luong_khong_dung_dom_va_api_cua_desk` khoá lại.
//
// VÌ SAO `ngay` (không phải `gio` như `tra_cuu.js`): màn này không GHI giờ vào đâu
// cả — nó chỉ cần ĐỊNH DẠNG vài ngày đã có sẵn (hạn dùng của lô, lúc chốt thiếu)
// cho người đọc. Định dạng ngày là chuyện của môi trường (Desk có
// `frappe.datetime.str_to_user`, Node thì không), nhưng CÂU CHỮ quanh nó là quyết
// định của lớp luồng (rule 2) — nên cái tiêm vào là một hàm ĐỊNH DẠNG, không phải
// một đồng hồ. Không tiêm thì rơi về nguyên văn chuỗi ngày của máy chủ: xấu hơn,
// không bao giờ SAI.
//
// ĐÂY LÀ MÀN GHI NẶNG NHẤT của app (929 dòng bản Desk), đụng bốn luật nghiệp vụ mà
// mỗi luật đã trả giá bằng một sự cố thật ngoài kho:
//   1. lô HẾT HẠN: CHẶN HẲN — không phải "quét lại để xác nhận". Công ty vật tư y
//      tế; giao một lô hết hạn là sự cố có hồ sơ (`quet_de_lay` trả `het_han`).
//   2. lô KHÁC lô đang chốt: đòi xác nhận; ĐÃ lấy một phần → `tach_dong_theo_lo`,
//      CHƯA lấy gì → `doi_lo`. Quyết định này thuộc LỚP LUỒNG (`xac_nhan_doi_lo`),
//      lớp vẽ KHÔNG được tự chọn gọi hàm nào — đây là luật đắt nhất của màn.
//   3. ĐƠN VỊ: đổi đơn vị thì số lượng mặc định = phần còn thiếu quy theo đơn vị
//      đó; đơn vị đóng gói lấy PHẦN NGUYÊN; còn thiếu dưới một đơn vị thì rơi về
//      đơn vị tồn.
//   4. SỐ KIỆN mặc định: đơn vị đóng gói → mỗi đơn vị một kiện; đơn vị tồn → một
//      kiện; người dùng sửa thì GIỮ ý họ.
//
// HỎI LẠI MÁY CHỦ TRƯỚC KHI QUYẾT (ràng buộc riêng của Task 4): màn Tra cứu (Task
// 2) chạm một dòng lịch sử → 0 lời gọi máy chủ, hiện lại ảnh chụp cũ — chấp nhận
// được ở một màn CHỈ ĐỌC. Đây là màn GHI: quyết định dựa trên số liệu cũ là SAI.
// Vì vậy mọi lối "chạm vào một lượt ĐÃ LẤY / một dòng đã chốt thiếu / nút Hoàn tất"
// đi qua một hàm `hoi_*()` TỰ NẠP LẠI phiếu từ máy chủ trước khi dựng câu hỏi —
// xem `_nap_lai_phieu()`.
//
// LỖI MÁY CHỦ (validate thật sự từ chối: "ô chỉ còn 3", "dòng này đã ghi 2 lượt
// lấy…") KHÔNG bị nuốt ở đây — các hàm GHI để nguyên promise bị TỪ CHỐI cho lớp vẽ
// tự bắt và hiển thị theo cách của môi trường mình (app: `KhoApp.bao(loi.message,
// "do")`; Desk: `frappe.xcall` tự hiện popup). Khác hẳn các nhánh "quyết định của
// chính luồng" (lô hết hạn, chưa quét lô, đã lấy đủ…) — những nhánh đó KHÔNG PHẢI
// lỗi, là kết quả hợp lệ của một lượt quét, nên `quet()` LUÔN resolve cho chúng.

function _dich(chu, doi_so) {
	if (typeof __ === "function") return __(chu, doi_so);
	if (!doi_so) return chu;
	return chu.replace(/\{(\d+)\}/g, (_, i) => (doi_so[i] !== undefined ? doi_so[i] : ""));
}

// `frappe.utils.flt` không có trong Node — bản rút gọn đủ dùng cho số lượng gõ tay
// (có thể là chuỗi từ một ô nhập số, hoặc số thật từ máy chủ).
function _flt(gia_tri) {
	if (typeof gia_tri === "number") return isNaN(gia_tri) ? 0 : gia_tri;
	const n = parseFloat(String(gia_tri == null ? "" : gia_tri).replace(/,/g, ""));
	return isNaN(n) ? 0 : n;
}

// `flt(x, 6)` của Frappe (làm tròn 6 chữ số thập phân) KHÔNG có ở đây: `_flt` trên
// chỉ nhận MỘT đối số, đúng khuôn `xep_hang.js`. Bản Desk có vài chỗ gọi
// `flt(..., 6)` — chép thẳng sang sẽ lặng lẽ bỏ đối số thứ hai và giữ nguyên đuôi
// dấu phẩy động (600.0000000000001 hiện lên ô số lượng). Viết tường minh ở đây.
function _lam_tron(gia_tri, chu_so) {
	const he = Math.pow(10, chu_so === undefined ? 6 : chu_so);
	return Math.round(_flt(gia_tri) * he) / he;
}

const _SAI_SO = 1e-9;

// LUẬT 2 ở MỘT NƠI (Task 5, mục dọn 1 của brief). Trước bản vá này, BA chỗ (nhãn
// nút của `_the_lo_khac`, cờ `can_xac_nhan` mà `_hoi_doi_lo` trả lúc QUÉT, và
// đường dẫn thật `xac_nhan_doi_lo` chọn lúc ĐỒNG Ý) mỗi nơi tự chép cùng một
// biểu thức `_flt(dong.da_lay_ton) > 0` — giống hệt nhau HÔM NAY, không có gì
// khoá lại NGÀY MAI. Người soát dựng được ca: `_hoi_doi_lo` tính nhãn "đổi lô"
// lúc QUÉT; giữa lúc chờ người dùng bấm ĐỒNG Ý, `da_lay_ton` của dòng đổi (một
// lượt lấy khác ghi vào CHÍNH dòng đó qua một hành động khác trên cùng phiên —
// vd `bo_luot`/`ghi` cho một dòng khác trả về nguyên `phieu` mới từ máy chủ,
// cuốn theo số liệu MỚI của dòng này); `xac_nhan_doi_lo()` tính LẠI và gọi
// `tach_dong_theo_lo` — ĐÚNG theo dữ liệu mới nhất — nhưng nút vừa bấm còn mang
// chữ "Đổi sang lô" từ lượt quét cũ: nhãn nói một đằng, hàm chạy một nẻo (hành
// động vẫn đúng — luồng luôn tính lại từ dữ liệu MỚI trước khi ghi, xem chú
// thích `xac_nhan_doi_lo` — chỉ chữ hiển thị lệch một nhịp).
//
// Gộp về MỘT hàm không xoá được khoảng thời gian giữa "quét" và "đồng ý" (không
// tránh được — người dùng cần thời gian đọc câu hỏi), nhưng đảm bảo NHÃN và HÀM
// THẬT luôn cùng một công thức: còn ĐÚNG một chỗ để đọc/sửa luật "đổi hay tách",
// không phải ba bản chép tay có thể lệch nhau vì gõ nhầm một trong số đó.
function _viec_doi_lo(dong) {
	return dong && _flt(dong.da_lay_ton) > 0 ? "tach_dong" : "doi_lo";
}

// Đường dẫn máy chủ — NGUYÊN VĂN từ "Interfaces" của brief Task 4, một chỗ duy nhất
// để sửa nếu `vitri/lay_hang.py` đổi tên hàm.
const _API = "erpnext.warehouse_operations.vitri.lay_hang.";
const API_DANH_SACH_PHIEU_GIAO = _API + "danh_sach_phieu_giao";
const API_MO_PHIEU_GIAO = _API + "mo_phieu_giao";
const API_QUET_DE_LAY = _API + "quet_de_lay";
const API_GHI_DA_LAY = _API + "ghi_da_lay";
const API_BO_DONG_DA_LAY = _API + "bo_dong_da_lay";
const API_DOI_LO = _API + "doi_lo";
const API_TACH_DONG_THEO_LO = _API + "tach_dong_theo_lo";
const API_CHOT_THIEU = _API + "chot_thieu";
const API_BO_CHOT_THIEU = _API + "bo_chot_thieu";
const API_HOAN_TAT = _API + "hoan_tat";

// Câu báo — MỘT NƠI (soát xét Task 2, P4: lặp câu ở ba nơi là nợ, sửa một chỗ quên
// chỗ kia). Cặp `**…**` đánh dấu phần lớp vẽ nên TÔ ĐẬM — đúng những giá trị bản
// Desk gốc bọc `<b>…</b>` (số lượng, mã ô, mã lô: thứ thủ kho cần liếc nhanh nhất
// trên màn 4 inch). Đây là CHỮ THƯỜNG có quy ước, KHÔNG phải HTML: lớp vẽ
// (`vo.js::_dam()` và bản mirror của Desk) escape TOÀN BỘ TRƯỚC rồi mới đổi `**x**`
// thành `<b>x</b>` CỦA RIÊNG NÓ, nên máy chủ không có cách nào nhét một thẻ thật
// qua chuỗi này.
const CAU_CHUA_CHON_PHIEU = "Chọn phiếu giao trước khi quét.";
const CAU_LO_HET_HAN =
	"CHẶN: lô **{0}** đã hết hạn ngày {1} — không lấy được trên PDA. Muốn xuất lô hết hạn " +
	"thì thao tác trên form Phiếu giao hàng (máy tính).";
const CAU_PHIEU_VUA_DOI = "Phiếu vừa thay đổi — đang nạp lại.";
const CAU_DA_LAY_DU = "Dòng này đã lấy đủ.";
const CAU_CAN_QUET_LO = "{0} có quản lý lô — quét tem LÔ trên thùng, không quét mã hàng.";
const CAU_KHONG_NHAN_RA = "Không nhận ra mã **{0}**, hoặc lô này không nằm trong phiếu.";
const CAU_CHUA_QUET_LO =
	"Quét tem LÔ (hoặc mã hàng, nếu mặt hàng không quản lý lô) trước, rồi mới quét tem ô.";
const CAU_SO_LUONG_PHAI_DUONG = "Số lượng phải lớn hơn 0.";
const CAU_DA_LAY = "Đã lấy **{0} {1}** {2} ở **{3}**";
const CAU_O_CHI_CON = "Ô **{0}** chỉ còn **{1}** {2} — đã lấy {1}, quét ô khác cho phần còn lại.";
const CAU_DA_CHUYEN_LO = "Đã chuyển sang lô **{0}**. Quét lại tem lô để lấy.";
const CAU_DA_BO_LUOT = "Đã bỏ một lượt lấy.";
const CAU_DA_GO_CHOT_THIEU = "Đã gỡ cờ chốt thiếu.";
const CAU_DA_DUYET = "Đã duyệt **{0}**.";
const CAU_DUYET_CO_THIEU = "Có {0} dòng lấy thiếu — xem ghi chú trên phiếu.";
const CAU_PHIEU_DA_XONG = "Phiếu **{0}** đã {1} — không lấy hàng được nữa.";
const CAU_LO_KHAC = "Lô **{0}** (HSD {1}) KHÁC lô đang chốt **{2}** (HSD {3}) của cùng mặt hàng.";
const CAU_HAN_XA_HON = "Lô mới có hạn XA HƠN lô đang chốt — kiểm tra kỹ trước khi đổi.";
const CAU_QUET_LAI_DE_DOI_LO = "Quét LẠI tem {0} để xác nhận, hoặc chạm nút bên dưới.";
const NHAN_NUT_DOI_LO = "Đổi sang lô {0}";
// Nhãn RIÊNG cho ca TÁCH DÒNG (Task 5, mục dọn 1) — trước bản vá này nút LUÔN
// mang chữ "Đổi sang lô {0}" bất kể `viec` là "doi_lo" hay "tach_dong", nên một
// khi `viec` là "tach_dong" (đã lấy một phần lô cũ) thì chữ trên nút nói "đổi"
// trong khi hàm thật sự chạy là TÁCH DÒNG — đúng ca người soát dựng được. Hai
// nhãn khác nhau vì hai việc khác nhau về BẢN CHẤT chứng từ (đổi lô tại chỗ vs.
// tách dòng cũ ra làm hai) dù cùng một hành vi "đổi sang lô X" trong mắt người
// dùng — chữ nói đúng việc SẼ xảy ra, không chỉ đúng cảm giác chung chung.
const NHAN_NUT_TACH_DONG = "Tách sang lô {0}";
const CAU_LY_DO_KHONG_QUET_MAC_DINH = "Kho không quản lý vị trí — lấy tay, không cần quét.";
const CAU_THIEU_TRONG_LO = "Lô {0} chỉ còn {1} — lấy hết rồi quét tem lô khác cho phần còn lại {2}.";
const CAU_THIEU_TRONG_KHO = "Kho chỉ còn {0} — lấy hết rồi báo thủ kho phần còn thiếu {1}.";
const CAU_LO_NEN_LAY = "Nên lấy lô {0}";
const CAU_LO_TREN_PHIEU_MUON_HON = "Lô trên phiếu hết hạn muộn hơn lô {0}";
const CAU_BANNER_CHOT_THIEU = "Đã chốt thiếu bởi **{0}** lúc {1}.";
const CAU_TEM_KIEN = "{0}/{1} kiện đã in tem";
const CAU_TEM_KIEN_THIEU = "in ở máy tính (form phiếu giao › In tem kiện)";

// Câu HỎI (nội dung hộp xác nhận). CHỮ THƯỜNG, KHÔNG `**`: hộp xác nhận của app
// (`kho_pda/hop_thoai.js`) escape TOÀN BỘ `noi_dung` và KHÔNG diễn giải `**` —
// đánh dấu ở đây sẽ hiện ra hai dấu sao trên màn PDA.
const HOI_BO_LUOT = "Bỏ lượt lấy {0} {1} ở ô {2} khỏi phiếu?";
// NHÃN NÚT của hộp xác nhận cũng là câu chữ — thuộc lớp luồng, cùng lẽ với
// `lo_khac.nhan_nut`. Trước vòng sửa này hai lớp vẽ mỗi nơi tự gõ `__("Bỏ lượt")`
// / `__("Chốt thiếu")` / `__("Duyệt phiếu")`, trong khi nhãn nút "Đổi sang lô …"
// lại do luồng trả — một sự KHÔNG NHẤT QUÁN mà rule 2 sẽ soi đúng vào.
const NHAN_BO_LUOT = "Bỏ lượt";
const NHAN_CHOT_THIEU = "Chốt thiếu";
const NHAN_DUYET_PHIEU = "Duyệt phiếu";
const HOI_CHOT_THIEU = "Chốt {0} chỉ lấy được {1}/{2}? Phiếu giao sẽ hạ số lượng xuống.";
const HOI_HOAN_TAT = "Duyệt phiếu giao {0}? Kho sẽ trừ đúng các ô vừa quét.";
const BAO_LUOT_DA_BI_BO = "Lượt lấy này vừa bị bỏ ở nơi khác — màn hình đã nạp lại.";
const BAO_DONG_DA_BIEN_MAT = "Dòng hàng này không còn trên phiếu — màn hình đã nạp lại.";
const BAO_KHONG_CON_PHIEU = "Không còn phiếu nào đang mở.";

// Gợi ý dưới ô quét.
const GOI_Y_CHON_KHO = "Chọn kho để bắt đầu";
const GOI_Y_CHON_PHIEU = "Chọn phiếu giao để bắt đầu";
const GOI_Y_QUET_LAI_DOI_LO = "Quét LẠI tem {0} để đổi lô";
const GOI_Y_QUET_O_CHO_LO = "② Quét tem Ô cho lô {0}";
const GOI_Y_QUET_O_CHO_HANG = "② Quét tem Ô cho {0}";
const GOI_Y_QUET_LO = "① Quét tem LÔ (hoặc mã hàng, nếu mặt hàng không quản lý lô)";

function tao({ goi, ngay }) {
	// Định dạng ngày cho NGƯỜI ĐỌC. Không tiêm thì trả nguyên văn chuỗi máy chủ
	// (`2026-09-23`) — đọc được, chỉ là không theo thói quen Việt Nam; thà vậy còn
	// hơn lẳng lặng tự định dạng theo múi giờ MÁY TRẠM (cùng lẽ `gio` ở `tra_cuu.js`).
	const _ngay = (gia_tri) => (gia_tri ? (ngay ? ngay(gia_tri) : String(gia_tri)) : "");

	// -------------------------------------------------------------- trạng thái
	let kho = null;
	let kho_ds = [];
	let ds_phieu = [];
	// Kết quả `mo_phieu_giao` gần nhất — `null` = đang ở màn DANH SÁCH phiếu.
	let phieu = null;
	// Lô đang chờ quét ô. `null` = đang ở bước ① (chờ quét lô).
	// { dong_hang, so_lo, vat_tu, ten_hang, don_vi, he_so, so_luong,
	//   da_sua_so_luong, so_kien (người dùng đặt, `null` = để luồng tự tính),
	//   lo_khac } — `lo_khac` khác `null` khi đang CHỜ XÁC NHẬN đổi/tách lô, lúc
	// đó chưa có gì được ghi và chưa có lô nào thật sự đang chờ ô.
	let cho = null;

	// ---------------------------------------------------------------- nội bộ

	function _dong(dong_hang) {
		return ((phieu && phieu.dong) || []).find((x) => x.dong_hang === dong_hang) || null;
	}

	function _con_ton(d) {
		return Math.max(0, _flt(d.can_lay_ton) - _flt(d.da_lay_ton));
	}

	function _buoc() {
		return cho && !cho.lo_khac ? "cho_o" : "cho_lo";
	}

	// Số kiện MẶC ĐỊNH khi người dùng chưa sửa — CÙNG luật với `ghi_da_lay` máy chủ:
	// đơn vị đóng gói thì mỗi đơn vị một kiện, đơn vị tồn thì cả lượt một kiện.
	function _so_kien_mac_dinh(c) {
		return _flt(c.he_so) !== 1 ? Math.max(1, Math.round(_flt(c.so_luong))) : 1;
	}

	// Đổi đơn vị lấy: số lượng mặc định = phần còn thiếu quy theo đơn vị mới; đơn vị
	// đóng gói lấy PHẦN NGUYÊN (phần lẻ lấy tiếp bằng đơn vị nhỏ hơn — không làm
	// tròn LÊN, vì làm tròn là ghi lên phiếu một số hàng KHÁC số thủ kho thật sự
	// lấy). Trả `true` khi đổi được (đơn vị có trong `don_vi_chon` của dòng).
	function _dat_don_vi_that(uom) {
		const d = cho && _dong(cho.dong_hang);
		if (!d) return false;
		const dv = (d.don_vi_chon || []).find((x) => x.uom === uom);
		if (!dv) return false;
		const con_ton = _con_ton(d);
		cho.don_vi = dv.uom;
		cho.he_so = _flt(dv.he_so) || 1;
		cho.so_luong = cho.he_so === 1 ? _lam_tron(con_ton) : Math.floor(con_ton / cho.he_so + _SAI_SO);
		// Số lượng vừa tính lại là số MẶC ĐỊNH — `ghi()` được phép để máy chủ cắt nó
		// theo tồn thật của ô (`lay_toi_da_theo_o`). Và số kiện cũng phải tính lại từ
		// đầu: giữ số kiện của đơn vị CŨ (vd 5 kiện cho 5 Hộp) khi vừa đổi sang Cái là
		// mang ý định của một lượt khác sang lượt này.
		cho.da_sua_so_luong = false;
		cho.so_kien = null;
		return true;
	}

	// SỐ LƯỢNG MẶC ĐỊNH của lô đang chờ — MỘT NƠI DUY NHẤT (soát xét tổng, M1).
	//
	// Đơn vị mặc định = đơn vị CỦA DÒNG (thứ in trên phiếu giao). Dòng bán theo đơn
	// vị đóng gói: gợi ý phần NGUYÊN (5,8 Hộp → 5 Hộp); còn thiếu dưới MỘT đơn vị
	// đóng gói (80 Cái của một dòng bán theo Hộp 100) thì RƠI VỀ ĐƠN VỊ TỒN — không
	// thì ô số lượng hiện 0 và thủ kho tưởng không lấy được gì.
	//
	// VÌ SAO LÀ MỘT HÀM: quyết định này TỪNG được viết hai lần TRONG CÙNG FILE NÀY —
	// ở `_nhan_lo` (có phép rơi về đơn vị tồn) và ở nhánh "ô chỉ còn một phần" của
	// `ghi()` (Math.floor trần, KHÔNG có phép rơi). Bản thiếu dựng lại được một BẾ
	// TẮC GIỮA KHO: dòng 1 Hộp = 100 Cái, hàng nằm ở hai ô mỗi ô 50 Cái — lấy hết ô
	// A xong số lượng về 0, quét ô B ra "Số lượng phải lớn hơn 0", thủ kho tắc, lối
	// thoát duy nhất là tự chạm nút đơn vị "Cái" mà không có gì trên màn nói thế.
	// Kế thừa từ bản Desk cũ (`lay_hang_pda.js:429` có y hệt), nhưng gộp lớp chính
	// là lúc thấy nó.
	//
	// Chỉ ở ĐÂY (lúc nhận lô / lúc bị cắt theo tồn ô), KHÔNG ở `dat_don_vi()`: người
	// dùng TỰ chạm "Hộp" mà còn thiếu 80 Cái thì họ đang định lấy Hộp thật — tự nhảy
	// về Cái là đổi ý định của họ (đúng ranh giới mà `da_sua_so_luong` giữ ở chỗ
	// khác).
	//
	// `_dat_don_vi_that` tính lại `so_luong` từ `_con_ton(dòng)` — tức PHẦN CÒN
	// THIẾU MỚI NHẤT của dòng theo `phieu` đang giữ, nên hàm này đúng ở CẢ HAI chỗ
	// gọi mà không cần ai truyền số vào; điều kiện bắt buộc là `phieu` đã được cập
	// nhật TRƯỚC khi gọi (cả hai chỗ gọi đều thoả).
	function _dat_so_mac_dinh(dong) {
		if (_dat_don_vi_that(cho.don_vi) && _flt(cho.he_so) !== 1 && !(_flt(cho.so_luong) > 0)) {
			_dat_don_vi_that(dong.don_vi_ton);
		}
	}

	// Một lô/mặt hàng MỚI vừa được nhận diện (lô đang chốt đúng trên dòng).
	function _nhan_lo(d) {
		const dong = _dong(d.dong_hang);
		if (!dong) {
			// `quet_de_lay` đọc phiếu MỚI từ CSDL; `phieu.dong` là bản đệm từ lần
			// `mo_phieu_giao` trước — lệch nhau khi có người khác (hoặc chính mình ở
			// `xac_nhan_doi_lo`) vừa thêm/tách dòng. Báo và đòi nạp lại, thay vì nổ một
			// `TypeError` câm trên `dong.can_lay_ton` (đúng kiểu hỏng im lặng cả module
			// này phải tránh).
			return { buoc: _buoc(), bao: _dich(CAU_PHIEU_VUA_DOI), muc: "cam", nap_lai: true };
		}
		if (_con_ton(dong) <= _SAI_SO) {
			// KHÔNG đổi `cho`: lượt quét này không mở ra việc gì, giữ nguyên lô (nếu có)
			// mà thủ kho đang làm dở.
			return { buoc: _buoc(), bao: _dich(CAU_DA_LAY_DU), muc: "xam" };
		}
		// Quét lô mới khi đang chờ ô cho lô cũ: THAY lô cũ — chưa có gì được ghi.
		// `so_lo` có thể là `null` (mặt hàng không quản lý lô, xem `quet_de_lay`) — giữ
		// `vat_tu`/`ten_hang` để thẻ "đang chờ" và gợi ý dưới ô quét có gì để hiện thay
		// cho một mã lô không tồn tại.
		cho = {
			dong_hang: d.dong_hang,
			so_lo: d.so_lo === undefined ? null : d.so_lo,
			vat_tu: d.vat_tu,
			ten_hang: dong.ten_hang,
			don_vi: dong.don_vi_dong,
			he_so: _flt(dong.he_so_dong) || 1,
			so_luong: _lam_tron(_flt(dong.can_lay) - _flt(dong.da_lay)),
			da_sua_so_luong: false,
			so_kien: null,
			lo_khac: null,
		};
		_dat_so_mac_dinh(dong);
		return { buoc: "cho_o", bao: "", muc: "xam" };
	}

	// Lô KHÁC lô đang chốt trên dòng: đòi xác nhận. Quét LẠI đúng tem đó là một cách
	// xác nhận (không hộp thoại — Enter của súng quét bấm luôn nút "Có" của một hộp
	// bắt phím, xem `kho_pda/hop_thoai.js`), chạm nút cũng là một cách.
	function _hoi_doi_lo(d) {
		const dong = _dong(d.dong_hang);
		if (!dong) {
			cho = null;
			return { buoc: "cho_lo", bao: _dich(CAU_PHIEU_VUA_DOI), muc: "cam", nap_lai: true };
		}
		if (cho && cho.lo_khac && cho.lo_khac.so_lo === d.so_lo) return xac_nhan_doi_lo();
		cho = { dong_hang: d.dong_hang, so_lo: null, so_luong: 0, so_kien: null, lo_khac: d };
		return {
			buoc: "cho_lo",
			bao: _dich(CAU_LO_KHAC, [
				d.so_lo,
				_ngay(d.hsd) || "—",
				d.so_lo_dang_chot || "—",
				_ngay(d.hsd_dang_chot) || "—",
			]),
			muc: "cam",
			// `can_xac_nhan` nói cho lớp vẽ biết PHẢI HỎI, và hỏi về việc gì (nhãn nút,
			// câu cảnh báo) — nó KHÔNG phải cái nút bấm để chọn hàm máy chủ. Hàm nào
			// thật sự được gọi do `xac_nhan_doi_lo()` tự tính LẠI lúc người dùng đồng ý
			// (phiếu có thể đã đổi giữa lúc chờ), xem hàm đó. Tính bằng ĐÚNG `_viec_doi_lo`
			// mà `xac_nhan_doi_lo`/`_the_lo_khac` cũng dùng (Task 5, mục dọn 1) — một giá
			// trị SNAPSHOT tại lúc quét vẫn có thể lệch với lúc đồng ý (xem chú thích ở
			// hàm đó), nhưng không còn LỆCH CÔNG THỨC nữa.
			can_xac_nhan: _viec_doi_lo(dong),
		};
	}

	// ------------------------------------------------------- nạp lại từ máy chủ

	async function _nap_lai_phieu() {
		if (!phieu) return null;
		phieu = await goi(API_MO_PHIEU_GIAO, { phieu: phieu.name });
		return phieu;
	}

	// --------------------------------------------------------------- API công bố

	/** Danh sách phiếu giao đang chờ lấy của một kho (`null` = để máy chủ tự chọn). */
	async function danh_sach(kho_muon) {
		phieu = null;
		cho = null;
		const r = await goi(API_DANH_SACH_PHIEU_GIAO, { kho: kho_muon === undefined ? kho : kho_muon });
		kho_ds = r.kho_ds || [];
		kho = r.kho;
		ds_phieu = r.phieu || [];
		return trang_thai();
	}

	/** Mở một phiếu giao để lấy hàng. CHỈ gọi `mo_phieu_giao` — danh sách kho là
	 * việc của `danh_sach()`; gộp hai lời gọi vào đây là bắt mỗi lần mở phiếu phải
	 * trả thêm một vòng round-trip trên wifi kho. */
	async function mo(ten_phieu) {
		cho = null;
		const p = await goi(API_MO_PHIEU_GIAO, { phieu: ten_phieu });
		// `docstatus` FALSY (0, hoặc vắng mặt) = còn nháp. KHÔNG so `!== 0`: một
		// payload thiếu khoá `docstatus` sẽ bị coi là "đã duyệt" và màn hình từ chối
		// một phiếu hoàn toàn bình thường.
		if (p && p.docstatus) {
			phieu = null;
			return {
				...trang_thai(),
				bao: _dich(CAU_PHIEU_DA_XONG, [ten_phieu, p.docstatus === 1 ? _dich("duyệt") : _dich("huỷ")]),
				muc: "cam",
			};
		}
		phieu = p;
		// Kho của phiếu — để nút "← Danh sách"/"Đổi" biết quay về đâu khi vào thẳng
		// một phiếu (đường dẫn sâu `/app/lay-hang-pda/<phiếu>` của Desk).
		if (p && p.kho) kho = p.kho;
		return trang_thai();
	}

	/** Đọc lại đúng những gì máy chủ đang giữ: phiếu đang mở, hoặc danh sách của kho
	 * hiện tại. KHÔNG đụng `cho` — đây không phải một lượt "mở màn mới". */
	async function lam_moi() {
		if (!phieu) return danh_sach(kho);
		await _nap_lai_phieu();
		return trang_thai();
	}

	/** Nút "← Danh sách": rời phiếu, nạp lại danh sách của kho hiện tại. */
	async function ve_danh_sach() {
		phieu = null;
		cho = null;
		return danh_sach(kho);
	}

	/** Nút "Đổi" kho: về màn chọn kho. KHÔNG gọi máy chủ — không truyền kho thì máy
	 * chủ tự chọn lại đúng kho vừa rời khi chỉ có một kho quản lý vị trí (nguyên
	 * quyết định của Desk gốc, giữ lại vì đúng). */
	function doi_kho() {
		kho = null;
		phieu = null;
		ds_phieu = [];
		cho = null;
		return trang_thai();
	}

	async function quet(ma) {
		const ma_sach = String(ma == null ? "" : ma).trim();
		if (!ma_sach) return { buoc: _buoc(), bao: "", muc: "xam" };
		if (!phieu) return { buoc: "cho_lo", bao: _dich(CAU_CHUA_CHON_PHIEU), muc: "cam" };

		const d = (await goi(API_QUET_DE_LAY, { phieu: phieu.name, ma: ma_sach })) || { loai: null };

		// LUẬT 1 — lô HẾT HẠN: CHẶN HẲN. Kiểm TRƯỚC mọi thứ khác (kể cả trước khi tra
		// dòng hàng): `quet_de_lay` đã so hạn với HÔM NAY THẬT, và một lô hết hạn
		// không được phép chạm tới `cho` dù chỉ một nhịp. Đây KHÔNG phải "quét lại để
		// xác nhận" như nhánh `lo_khac` — quét lại tem đó vẫn phải bị chặn y hệt.
		if ((d.loai === "lo" || d.loai === "lo_khac") && d.het_han) {
			return {
				buoc: _buoc(),
				bao: _dich(CAU_LO_HET_HAN, [d.so_lo, _ngay(d.hsd) || "—"]),
				muc: "do",
			};
		}
		if (d.loai === "lo") return _nhan_lo(d);
		if (d.loai === "lo_khac") return _hoi_doi_lo(d);
		if (d.loai === "o") return ghi({ o: d.ma_o, ma_in_nhan: d.ma_in_nhan });
		if (d.loai === "can_quet_lo") {
			// Chỉ hiện câu nhắc — KHÔNG đổi `cho`: giữ nguyên trạng thái đang chờ (nếu
			// có) của lượt trước, cùng khuôn `xep_hang.js`.
			return { buoc: _buoc(), bao: _dich(CAU_CAN_QUET_LO, [d.ten_hang || d.vat_tu]), muc: "cam" };
		}
		return { buoc: _buoc(), bao: _dich(CAU_KHONG_NHAN_RA, [ma_sach]), muc: "xam" };
	}

	/** LUẬT 2 — người dùng đồng ý đổi sang lô vừa quét.
	 *
	 * ĐÂY LÀ LUẬT ĐẮT NHẤT CỦA MÀN: lớp vẽ KHÔNG được tự chọn gọi `tach_dong_theo_lo`
	 * hay `doi_lo`. Đã lấy được một phần của lô CŨ thì phải TÁCH dòng (chốt dòng cũ ở
	 * số đã lấy, đẻ dòng mới cho phần còn lại — `use_serial_batch_fields = 1` nên MỘT
	 * dòng phiếu giao chỉ mang MỘT lô); chưa lấy gì thì ĐỔI lô tại chỗ (tách ra một
	 * dòng 0 là để lại rác trên chứng từ bán hàng).
	 *
	 * Đo "đã lấy được gì chưa" bằng `da_lay_ton` (ĐƠN VỊ TỒN), KHÔNG bằng `da_lay` —
	 * khác bản Desk gốc, và đây là một QUYẾT ĐỊNH, không phải chép sót: bảng phân bổ
	 * `Location Allocation` (thứ `tach_dong_theo_lo` thật sự nhìn) đo bằng đơn vị
	 * TỒN, còn `da_lay` là số DẪN XUẤT (`da_lay_ton / he_so`, máy chủ làm tròn 6 chữ
	 * số) — một lượt đã lấy rất nhỏ so với hệ số đóng gói lớn có thể làm tròn về 0 và
	 * biến một ca TÁCH thành một ca ĐỔI, mà `doi_lo` sẽ bị máy chủ từ chối ("dòng này
	 * đã ghi N lượt lấy") — thủ kho kẹt giữa kho không có đường đi tiếp.
	 *
	 * Tính LẠI ngay lúc đồng ý, không đọc `can_xac_nhan` đã trả ở lượt quét trước:
	 * giữa lúc chờ xác nhận, một lượt lấy ở máy khác có thể đã đổi `da_lay_ton`. */
	async function xac_nhan_doi_lo() {
		const lk = cho && cho.lo_khac;
		if (!lk) return { buoc: _buoc(), bao: "", muc: "xam" };
		const dong = _dong(lk.dong_hang);
		if (!dong) {
			cho = null;
			return { buoc: "cho_lo", bao: _dich(CAU_PHIEU_VUA_DOI), muc: "cam", nap_lai: true };
		}
		const duong_dan = _viec_doi_lo(dong) === "tach_dong" ? API_TACH_DONG_THEO_LO : API_DOI_LO;
		// KHÔNG try/catch: máy chủ từ chối (lô của mặt hàng khác, dòng có bundle
		// serial/lô…) phải NỔI LÊN cho lớp vẽ tự hiện — và `cho` giữ NGUYÊN để thủ
		// kho thấy mình vẫn đang ở giữa việc xác nhận.
		const p = await goi(duong_dan, {
			phieu: phieu.name,
			dong_hang: lk.dong_hang,
			so_lo_moi: lk.so_lo,
		});
		phieu = p;
		cho = null;
		return { buoc: "cho_lo", bao: _dich(CAU_DA_CHUYEN_LO, [lk.so_lo]), muc: "xanh" };
	}

	/** Ghi một lượt lấy vào ô `o`. Gọi từ `quet()` khi quét trúng tem ô; công bố ra
	 * ngoài để lớp vẽ dùng được cho một nút "lấy ở ô gợi ý" nếu cần. */
	async function ghi({ o, ma_in_nhan }) {
		// KHÔNG kiểm "đã quét lô chưa" bằng `!cho.so_lo`: mặt hàng KHÔNG quản lý lô
		// hợp lệ mang `so_lo = null` ngay cả khi đã sẵn sàng nhận ô. Trạng thái CHƯA
		// sẵn sàng đúng là `!cho` (chưa quét gì) hoặc `cho.lo_khac` (đang chờ xác nhận
		// đổi lô).
		if (!cho || cho.lo_khac) {
			return { buoc: "cho_lo", bao: _dich(CAU_CHUA_QUET_LO), muc: "cam" };
		}
		const c = cho;
		if (!(_flt(c.so_luong) > 0)) {
			return { buoc: "cho_o", bao: _dich(CAU_SO_LUONG_PHAI_DUONG), muc: "cam" };
		}
		const yeu_cau = _flt(c.so_luong);
		// Số lượng còn là MẶC ĐỊNH (người dùng chưa tự sửa): cho máy chủ được cắt
		// xuống theo tồn thật của ô vừa quét (`lay_toi_da_theo_o`) — đúng ca hay gặp
		// nhất, ô gợi ý có ÍT hơn phần còn thiếu của cả dòng. Người dùng ĐÃ TỰ gõ số
		// thì gọi như cũ: cắt âm thầm số họ nhập là đổi ý định của họ.
		const theo_ton_o = !c.da_sua_so_luong;
		const doi_so = {
			phieu: phieu.name,
			dong_hang: c.dong_hang,
			so_lo: c.so_lo,
			o: o,
			so_luong: c.so_luong,
			lay_toi_da_theo_o: theo_ton_o ? 1 : 0,
			don_vi: c.don_vi,
		};
		// Chỉ gửi số kiện khi NGƯỜI DÙNG đã sửa: số lượng có thể bị cắt theo tồn của
		// ô, và máy chủ tính số kiện mặc định theo số THẬT đã ghi — gửi kèm số kiện
		// tính theo số CHƯA cắt là in thừa tem.
		if (c.so_kien != null) doi_so.so_kien = c.so_kien;
		const p = await goi(API_GHI_DA_LAY, doi_so);
		// Chỉ đổi trạng thái SAU KHI máy chủ xác nhận ghi: lời gọi trên ném lỗi (ô
		// chỉ còn N, ô ngừng dùng…) thì `cho` GIỮ NGUYÊN, thủ kho quét lại đúng ô
		// hoặc sửa số lượng, không phải quét lại từ đầu tem LÔ.
		phieu = p;
		const da_ghi = p.so_luong_da_ghi != null ? _flt(p.so_luong_da_ghi) : yeu_cau;
		const bi_cat = theo_ton_o && da_ghi < yeu_cau - _SAI_SO;
		// Đọc lại phần CÒN THIẾU của dòng từ CHÍNH payload máy chủ vừa trả (không tự
		// trừ tay `yeu_cau - da_ghi`): máy chủ là nguồn sự thật duy nhất, và một lượt
		// ghi khác (máy khác) có thể đã đổi `da_lay_ton` của dòng ngay giữa lúc này.
		const dong_moi = (p.dong || []).find((x) => x.dong_hang === c.dong_hang);
		// Theo ĐƠN VỊ ĐANG CHỌN (có thể khác đơn vị của dòng).
		const con_lai_dong = dong_moi ? _con_ton(dong_moi) / (_flt(c.he_so) || 1) : 0;
		const dv_ghi = p.don_vi_da_ghi || c.don_vi || "";
		if (bi_cat && con_lai_dong > _SAI_SO) {
			// GIỮ nguyên lô/dòng đang chờ — bỏ nó ở đây (bản Desk trước một vòng sửa)
			// bắt thủ kho quét LẠI tem lô trước khi quét ô kế tiếp, trái với chính câu
			// HDSD ("hệ TỰ lấy đúng số ô còn… Không cần sửa số tay"), và bước ② biến
			// mất khỏi màn hình đúng lúc thủ kho cần nó nhất. Chỉ cập nhật số lượng =
			// phần còn thiếu MỚI, và hạ `da_sua_so_luong` về `false` — số này lại là
			// MẶC ĐỊNH, cho phép ô kế tiếp tiếp tục tự cắt theo tồn nếu cần.
			//
			// Số mặc định do `_dat_so_mac_dinh()` quyết — CÙNG hàm mà `_nhan_lo` dùng
			// (soát xét tổng, M1: nhánh này từng tự tính `Math.floor(con_lai_dong)` mà
			// THIẾU phép rơi về đơn vị tồn, nên lấy hết ô A của một dòng 1 Hộp = 100
			// Cái chia đôi hai ô làm số lượng về 0 và quét ô B bị chặn). `so_luong` gán
			// ở đây chỉ là giá trị nền cho ca `_dat_don_vi_that` không đổi được đơn vị
			// (đơn vị của dòng không còn trong `don_vi_chon`) — giữ đúng số cũ, không
			// để rơi về 0.
			cho = {
				dong_hang: c.dong_hang,
				so_lo: c.so_lo,
				vat_tu: c.vat_tu,
				ten_hang: c.ten_hang,
				don_vi: c.don_vi,
				he_so: c.he_so,
				so_luong:
					_flt(c.he_so) === 1 ? _lam_tron(con_lai_dong) : Math.floor(con_lai_dong + _SAI_SO),
				da_sua_so_luong: false,
				so_kien: null,
				lo_khac: null,
			};
			_dat_so_mac_dinh(dong_moi);
			return {
				buoc: "cho_ghi",
				bao: _dich(CAU_O_CHI_CON, [ma_in_nhan || o, String(da_ghi), dv_ghi]),
				muc: "cam",
			};
		}
		cho = null;
		return {
			buoc: "cho_ghi",
			bao: _dich(CAU_DA_LAY, [
				String(da_ghi),
				dv_ghi,
				c.so_lo || c.ten_hang || c.vat_tu || "",
				ma_in_nhan || o,
			]),
			muc: "xanh",
		};
	}

	/** LUẬT 3 — đổi đơn vị lấy. */
	function dat_don_vi(uom) {
		if (!cho || cho.lo_khac) return trang_thai();
		_dat_don_vi_that(uom);
		return trang_thai();
	}

	function dat_so_luong(so) {
		if (!cho || cho.lo_khac) return trang_thai();
		cho.so_luong = Math.max(0, _flt(so));
		// Người dùng đã TỰ sửa số — từ đây `ghi()` không còn được âm thầm cắt số này
		// theo tồn của ô. KHÔNG đụng `so_kien`: đổi số lượng thì số kiện MẶC ĐỊNH tự
		// tính lại theo số mới (xem `_so_kien_mac_dinh`), còn số kiện người dùng đã
		// tự đặt thì vẫn là ý của họ (LUẬT 4).
		cho.da_sua_so_luong = true;
		return trang_thai();
	}

	/** LUẬT 4 — số kiện do người dùng đặt. Tối thiểu 1: không có lượt lấy nào 0 kiện. */
	function dat_so_kien(n) {
		if (!cho || cho.lo_khac) return trang_thai();
		cho.so_kien = Math.max(1, Math.round(_flt(n)));
		return trang_thai();
	}

	/** "Bỏ lô này" — huỷ lô đang chờ (kể cả đang chờ xác nhận đổi lô), về bước ① mà
	 * KHÔNG ghi gì. Bản Desk không có lối thoát này cho nhánh `lo_khac`: bấm nhầm
	 * rồi thì chỉ còn cách quét một tem khác. */
	function bo_lo() {
		cho = null;
		return trang_thai();
	}

	// ------------------------------------------- chạm vào một LƯỢT ĐÃ LẤY: hỏi lại

	/** Chuẩn bị bỏ một lượt đã lấy: NẠP LẠI PHIẾU TỪ MÁY CHỦ rồi mới dựng câu hỏi.
	 *
	 * Đây là ràng buộc riêng của Task 4. Màn Tra cứu chạm một dòng lịch sử và hiện
	 * lại ảnh chụp cũ với 0 lời gọi máy chủ — chấp nhận được ở một màn CHỈ ĐỌC. Ở
	 * màn GHI này, hộp "Bỏ lượt lấy 5 Hộp ở ô 1A01?" dựng từ số liệu cũ có thể đang
	 * mô tả một lượt mà người khác vừa bỏ, hoặc một số lượng đã khác. Hỏi lại trước
	 * khi hỏi người dùng. */
	async function hoi_bo_luot(ten_luot) {
		if (!phieu) return { ok: false, bao: _dich(BAO_KHONG_CON_PHIEU), muc: "cam" };
		await _nap_lai_phieu();
		let luot = null;
		for (const d of phieu.dong || []) {
			const tim = (d.da_lay_o || []).find((p) => p.name === ten_luot);
			if (tim) {
				luot = tim;
				break;
			}
		}
		if (!luot) return { ok: false, bao: _dich(BAO_LUOT_DA_BI_BO), muc: "cam" };
		return {
			ok: true,
			nhan: _dich(NHAN_BO_LUOT),
			cau: _dich(HOI_BO_LUOT, [
				String(_flt(luot.so_luong_lay)),
				luot.don_vi_lay || "",
				luot.ma_in_nhan || luot.o,
			]),
		};
	}

	// Ba hàm GHI dưới đây LUÔN đi sau một `hoi_*()` (nơi đã kiểm `phieu`), nhưng vẫn
	// tự chặn: một lớp vẽ tương lai gọi thẳng chúng phải nhận một lỗi NÓI ĐƯỢC chứ
	// không phải `TypeError` câm trên `phieu.name`.
	function _doi_phieu_dang_mo() {
		if (!phieu) throw new Error(_dich(BAO_KHONG_CON_PHIEU));
		return phieu.name;
	}

	async function bo_luot(ten_luot) {
		const p = await goi(API_BO_DONG_DA_LAY, { phieu: _doi_phieu_dang_mo(), ten_dong: ten_luot });
		phieu = p;
		return { ...trang_thai(), bao: _dich(CAU_DA_BO_LUOT), muc: "xam" };
	}

	/** Chuẩn bị chốt thiếu — cùng lý do `hoi_bo_luot`: câu hỏi nói "chỉ lấy được
	 * 3/10", và 3 là một con số phải ĐÚNG LÚC BẤM, không phải lúc mở phiếu. */
	async function hoi_chot_thieu(dong_hang) {
		if (!phieu) return { ok: false, bao: _dich(BAO_KHONG_CON_PHIEU), muc: "cam" };
		await _nap_lai_phieu();
		const d = _dong(dong_hang);
		if (!d) return { ok: false, bao: _dich(BAO_DONG_DA_BIEN_MAT), muc: "cam" };
		return {
			ok: true,
			nhan: _dich(NHAN_CHOT_THIEU),
			cau: _dich(HOI_CHOT_THIEU, [
				d.ten_hang || d.vat_tu,
				String(_lam_tron(d.da_lay, 3)),
				String(_lam_tron(d.can_lay, 3)),
			]),
		};
	}

	async function chot_thieu(dong_hang) {
		const p = await goi(API_CHOT_THIEU, { phieu: _doi_phieu_dang_mo(), dong_hang });
		phieu = p;
		// `bao` RỖNG có chủ đích (giữ đúng bản Desk gốc): kết quả của "chốt thiếu"
		// hiện ngay trên chính dòng hàng — banner "Đã chốt thiếu bởi X lúc Y" cộng
		// nút "Bỏ chốt thiếu" thay chỗ nút "Chốt thiếu" — nên một dải báo nữa chỉ
		// lặp lại điều màn hình đã nói to hơn.
		return { ...trang_thai(), bao: "", muc: "xam" };
	}

	async function bo_chot_thieu(dong_hang) {
		const p = await goi(API_BO_CHOT_THIEU, { phieu: _doi_phieu_dang_mo(), dong_hang });
		phieu = p;
		return { ...trang_thai(), bao: _dich(CAU_DA_GO_CHOT_THIEU), muc: "xam" };
	}

	/** Chuẩn bị hoàn tất — nạp lại trước khi hỏi, cùng lý do trên: nút "Hoàn tất" là
	 * lời GHI nặng nhất của màn (duyệt phiếu giao, trừ sổ vị trí thật). */
	async function hoi_hoan_tat() {
		if (!phieu) return { ok: false, bao: _dich(BAO_KHONG_CON_PHIEU), muc: "cam" };
		await _nap_lai_phieu();
		return { ok: true, nhan: _dich(NHAN_DUYET_PHIEU), cau: _dich(HOI_HOAN_TAT, [phieu.name]) };
	}

	async function hoan_tat() {
		const ten = _doi_phieu_dang_mo();
		// KHÔNG try/catch: máy chủ chặn (chưa lấy đủ, chưa in đủ tem kiện — xem
		// `chan_duyet_chua_lay`) phải nổi lên NGUYÊN VĂN cho lớp vẽ, và phiếu còn
		// nguyên nháp (`hoan_tat` rollback theo savepoint).
		const kq = await goi(API_HOAN_TAT, { phieu: ten });
		phieu = null;
		cho = null;
		const lay_thieu = kq.lay_thieu || [];
		const bao =
			_dich(CAU_DA_DUYET, [kq.name || ten]) +
			(lay_thieu.length ? " " + _dich(CAU_DUYET_CO_THIEU, [lay_thieu.length]) : "");
		return {
			ok: true,
			ten: kq.name || ten,
			so_dong: kq.so_dong,
			lay_thieu,
			bao,
			// Duyệt phiếu LUÔN là tin tốt khi tới được đây (nhánh lỗi ném ở dòng trên)
			// — nhưng hằng số "xanh" đó phải sống ở lớp luồng, không phải mỗi lớp vẽ
			// tự nhớ một bản (soát xét Task 3, mục 5).
			muc: "xanh",
		};
	}

	// ------------------------------------------------------------------ trạng thái

	// Gợi ý hiện dưới ô quét — CÂU CHỮ là quyết định của luồng, lớp vẽ chỉ đặt vào.
	function _goi_y_o_quet() {
		// Hỏi `kho`, KHÔNG hỏi `kho_ds.length`: vào thẳng một phiếu qua đường dẫn sâu
		// (`/app/lay-hang-pda/<phiếu>`) thì kho đã biết (lấy từ chính phiếu) trong khi
		// danh sách kho còn rỗng — bản Desk gốc phải gọi thêm `danh_sach_phieu_giao` ở
		// NỀN chỉ để lấp chỗ trống đó. Không cần: nút "Đổi" kho dù sao cũng chỉ hiện
		// khi CHƯA mở phiếu nào, và "← Danh sách" tự nạp danh sách khi bấm.
		if (!kho) return { chu: _dich(GOI_Y_CHON_KHO), nhan_manh: false };
		if (!phieu) return { chu: _dich(GOI_Y_CHON_PHIEU), nhan_manh: false };
		if (cho && cho.lo_khac) {
			return { chu: _dich(GOI_Y_QUET_LAI_DOI_LO, [cho.lo_khac.so_lo]), nhan_manh: true };
		}
		if (cho) {
			// `so_lo` có thể là `null` (mặt hàng không quản lý lô) — nhắc theo tên hàng
			// thay vì in ra "lô null".
			return {
				chu: cho.so_lo
					? _dich(GOI_Y_QUET_O_CHO_LO, [cho.so_lo])
					: _dich(GOI_Y_QUET_O_CHO_HANG, [cho.ten_hang || cho.vat_tu || ""]),
				nhan_manh: true,
			};
		}
		return { chu: _dich(GOI_Y_QUET_LO), nhan_manh: false };
	}

	// Thẻ "lô khác" — mọi kết luận (câu giải thích, có cảnh báo hạn hay không, nhãn
	// nút) quyết ở đây; lớp vẽ chỉ ghép HTML quanh chúng.
	function _the_lo_khac() {
		const lk = cho && cho.lo_khac;
		if (!lk) return null;
		const dong = _dong(lk.dong_hang);
		// `viec` tính bằng ĐÚNG `_viec_doi_lo` mà `xac_nhan_doi_lo()` cũng dùng để
		// chọn hàm thật (Task 5, mục dọn 1) — nhãn nút đọc theo `viec` NGAY DƯỚI
		// ĐÂY, không còn một chữ "Đổi sang lô" cố định che mất ca TÁCH DÒNG.
		const viec = _viec_doi_lo(dong);
		return {
			so_lo: lk.so_lo,
			dong_hang: lk.dong_hang,
			cau: _dich(CAU_LO_KHAC, [
				lk.so_lo,
				_ngay(lk.hsd) || "—",
				lk.so_lo_dang_chot || "—",
				_ngay(lk.hsd_dang_chot) || "—",
			]),
			canh_bao: lk.han_xa_hon ? _dich(CAU_HAN_XA_HON) : null,
			nhac: _dich(CAU_QUET_LAI_DE_DOI_LO, [lk.so_lo]),
			nhan_nut: _dich(viec === "tach_dong" ? NHAN_NUT_TACH_DONG : NHAN_NUT_DOI_LO, [lk.so_lo]),
			viec,
		};
	}

	// Thẻ lô ĐANG CHỜ quét ô. Trả BẢN SAO (không phải chính `cho`): lớp vẽ sửa nhầm
	// một trường trên đó sẽ không đổi được trạng thái thật của luồng.
	function _the_cho() {
		if (!cho || cho.lo_khac) return null;
		const d = _dong(cho.dong_hang) || {};
		return {
			dong_hang: cho.dong_hang,
			so_lo: cho.so_lo,
			vat_tu: cho.vat_tu,
			ten_hang: cho.ten_hang,
			don_vi: cho.don_vi,
			he_so: cho.he_so,
			so_luong: cho.so_luong,
			// `so_kien` công bố ra ngoài là số SẼ DÙNG (người dùng đặt, hoặc mặc định
			// của luồng) — lớp vẽ không phải tự biết luật "đóng gói thì mỗi đơn vị một
			// kiện" nữa (LUẬT 4).
			so_kien: cho.so_kien != null ? cho.so_kien : _so_kien_mac_dinh(cho),
			nguoi_dung_dat_so_kien: cho.so_kien != null,
			// Hàng nút đơn vị: dưới hai lựa chọn thì không có gì để chọn — kết luận đó
			// cũng là của luồng.
			don_vi_chon: d.don_vi_chon || [],
			hien_chon_don_vi: (d.don_vi_chon || []).length >= 2,
			don_vi_ton: d.don_vi_ton,
			can_lay_ton: d.can_lay_ton,
			da_lay_ton: d.da_lay_ton,
		};
	}

	// Một dòng hàng ĐÃ KẾT LUẬN sẵn cho lớp vẽ: `du` hay chưa, có hiện nút "Chốt
	// thiếu" không, câu "lô chỉ còn…", câu "nên lấy lô…", banner chốt thiếu. Bản Desk
	// tính tất cả những thứ này TRONG hàm vẽ — kể cả một câu dự phòng tự gõ khi máy
	// chủ không trả `ly_do_khong_quet` (đúng hình dạng lỗi Task 2 từng trượt:
	// `kq.du_lieu || {loai: null}`). Chuyển hết vào đây, MỘT nơi.
	function _dong_hien(d) {
		const con_ton = _con_ton(d);
		const da_lay_ton = _flt(d.da_lay_ton);
		const can_lay_ton = _flt(d.can_lay_ton);
		const thieu_trong_lo = _flt(d.thieu_trong_lo);
		const don_vi_ton = d.don_vi_ton || "";
		let cau_thieu = null;
		if (thieu_trong_lo > _SAI_SO) {
			// Máy chủ đã tự cắt gợi ý về đúng phần LẤY ĐƯỢC và trả riêng phần CÒN
			// THIẾU — hiện một DÒNG CHỮ BÌNH THƯỜNG cho nó, không phải hộp lỗi (spec
			// §6.2: màn mở phiếu phải mở được kể cả khi không đủ hàng).
			const lay_duoc = _lam_tron(con_ton - thieu_trong_lo, 3) + " " + don_vi_ton;
			const con_thieu = _lam_tron(thieu_trong_lo, 3) + " " + don_vi_ton;
			cau_thieu = d.so_lo
				? _dich(CAU_THIEU_TRONG_LO, [d.so_lo, lay_duoc, con_thieu])
				: _dich(CAU_THIEU_TRONG_KHO, [lay_duoc, con_thieu]);
		}
		const lo_nen = d.lo_nen_lay && d.lo_nen_lay !== d.so_lo;
		return {
			...d,
			da_lay_o: d.da_lay_o || [],
			o_nen_lay: d.o_nen_lay || [],
			du: da_lay_ton >= can_lay_ton - _SAI_SO,
			// Câu "vì sao dòng này không quét được" LUÔN có, kể cả khi máy chủ (bản cũ)
			// không trả khoá đó — lớp vẽ không còn phải tự nghĩ một câu dự phòng.
			ly_do_khong_quet: d.can_quet ? null : d.ly_do_khong_quet || _dich(CAU_LY_DO_KHONG_QUET_MAC_DINH),
			// Chỉ chốt thiếu được khi ĐÃ lấy được một phần và CHƯA đủ (chốt thiếu một
			// dòng chưa lấy gì là nói dối rằng đã đi tìm).
			hien_nut_chot_thieu: !d.da_chot_thieu && da_lay_ton > 0 && da_lay_ton < can_lay_ton - _SAI_SO,
			banner_chot_thieu: d.da_chot_thieu
				? _dich(CAU_BANNER_CHOT_THIEU, [d.chot_thieu_boi || "—", _ngay(d.chot_thieu_luc) || "—"])
				: null,
			cau_thieu_trong_lo: cau_thieu,
			cau_lo_nen_lay: lo_nen
				? _dich(CAU_LO_NEN_LAY, [d.lo_nen_lay]) +
				  (d.lo_nen_lay_hsd ? " · HSD " + _ngay(d.lo_nen_lay_hsd) : "")
				: null,
			canh_bao_han: lo_nen && d.lo_tren_phieu_muon_hon
				? _dich(CAU_LO_TREN_PHIEU_MUON_HON, [d.lo_nen_lay])
				: null,
			hsd_chu: _ngay(d.hsd),
			// Dòng bán theo đơn vị KHÁC đơn vị tồn: hiện thêm dòng phụ theo đơn vị tồn.
			khac_don_vi: !!(d.don_vi_dong && d.don_vi_ton && d.don_vi_dong !== d.don_vi_ton),
		};
	}

	// Trạng thái tem kiện ở chân màn. Máy in tem nối với MÁY TÍNH — PDA chỉ báo;
	// thiếu tem thì `hoan_tat` bị máy chủ chặn với câu nói rõ.
	function _trang_thai_tem() {
		if (!phieu) return null;
		const tong = _flt(phieu.tong_kien);
		if (!tong) return null;
		const da_in = _flt(phieu.so_kien_da_in);
		const thieu = da_in < tong;
		return {
			thieu,
			chu: _dich(CAU_TEM_KIEN, [da_in, tong]) + (thieu ? " — " + _dich(CAU_TEM_KIEN_THIEU) : ""),
		};
	}

	function trang_thai() {
		const dong = ((phieu && phieu.dong) || []).map(_dong_hien);
		return {
			kho,
			kho_ds: kho_ds.slice(),
			ds_phieu: ds_phieu.slice(),
			phieu,
			dong,
			cho: _the_cho(),
			lo_khac: _the_lo_khac(),
			buoc: _buoc(),
			goi_y_o_quet: _goi_y_o_quet(),
			// Nút "Hoàn tất" chỉ có nghĩa khi đã có ÍT NHẤT một lượt lấy trên phiếu —
			// kết luận của luồng, không để mỗi lớp vẽ tự dò `dong.some(...)`.
			hien_nut_hoan_tat: !!phieu && dong.some((d) => _flt(d.da_lay_ton) > 0),
			trang_thai_tem: _trang_thai_tem(),
			// Nút "Đổi" kho chỉ có nghĩa khi có nhiều kho và chưa mở phiếu nào.
			hien_doi_kho: kho_ds.length > 1 && !phieu,
			// Ba trạng thái đầu màn, KẾT LUẬN ở đây để hai lớp vẽ không mỗi nơi tự suy
			// một kiểu (và để ca "vào thẳng một phiếu, `kho_ds` còn rỗng" không bị lớp
			// vẽ đọc nhầm thành "chưa kho nào bật quản lý vị trí").
			khong_co_kho: !kho && !kho_ds.length,
			hien_chon_kho: !kho && kho_ds.length > 0,
		};
	}

	return {
		danh_sach,
		mo,
		lam_moi,
		ve_danh_sach,
		doi_kho,
		quet,
		ghi,
		xac_nhan_doi_lo,
		dat_don_vi,
		dat_so_luong,
		dat_so_kien,
		bo_lo,
		hoi_bo_luot,
		bo_luot,
		hoi_chot_thieu,
		chot_thieu,
		bo_chot_thieu,
		hoi_hoan_tat,
		hoan_tat,
		trang_thai,
	};
}

// ------------------------------------------------------------- hai môi trường
// HAI CÂU `if` ĐỘC LẬP, KHÔNG `if/else` — chép NGUYÊN lý do đầy đủ ở cuối
// `tra_cuu.js`/`xep_hang.js` (esbuild bọc `__commonJS` nên `typeof module` đúng cả
// trong trình duyệt; hai `if` rời không phụ thuộc thứ tự viết, khác `if/else`).
if (typeof frappe !== "undefined" && frappe.provide) {
	frappe.provide("erpnext.warehouse_operations.luong");
	erpnext.warehouse_operations.luong.lay_hang = { tao };
}
if (typeof module !== "undefined" && module.exports) {
	module.exports = { tao };
}
