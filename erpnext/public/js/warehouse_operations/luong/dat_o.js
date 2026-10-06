// Lớp LUỒNG của màn "Đặt ô trên tem hàng loạt" — cùng khuôn tách lớp mà
// `tra_cuu.js`/`xep_hang.js`/`lay_hang.js` đã dựng (đọc ba file đó trước, đừng
// phát minh lại): phần QUYẾT ĐỊNH ("dòng nào tự chọn sẵn", "dòng nào cho đặt",
// nhãn và câu báo) nằm Ở ĐÂY, dùng chung cho CẢ HAI nơi — màn app PDA
// (`kho_pda/man_dat_o.js`) và trang Desk cũ
// (`warehouse_operations/page/dat_o_hang_loat/dat_o_hang_loat.js`, chuyển sang
// dùng lớp này ở Bước 6 của brief Task 5). File này KHÔNG đụng DOM, không gọi
// `frappe.*` trực tiếp — `goi` (hàm gọi máy chủ) TIÊM TỪ NGOÀI, điều kiện DUY
// NHẤT để chạy được trong Node lúc `node --test` (xem đầu `tra_cuu.js`).
//
// ĐÂY LÀ MÀN CÓ GHI (`dat_o_hang_loat`, brief Task 5): chạm một dòng để "xem lại"
// (ở đây là hỏi trước khi ghi hàng loạt) phải HỎI LẠI MÁY CHỦ — `hoi_dat()` tự
// `nap()` lại TRƯỚC khi dựng câu hỏi, cùng khuôn `hoi_bo_luot`/`hoi_hoan_tat` của
// `luong/lay_hang.js`. Khác màn Tra cứu (chỉ đọc, chạm dòng lịch sử là ảnh chụp cũ
// chấp nhận được).
//
// LỖI MÁY CHỦ (validate thật sự từ chối) KHÔNG bị nuốt ở đây — `dat()` để nguyên
// promise bị TỪ CHỐI cho lớp vẽ tự bắt. Nhưng `dat_o_hang_loat` gần như không bao
// giờ ném: mỗi dòng có SAVEPOINT riêng ở máy chủ (xem `o_tem.py`), dòng hỏng rơi
// vào mảng `loi`/`xong` (`xong` bản THẬT — brief Bước 1 gọi là `da_dat`, xem chú
// thích `_chuan_hoa_ket_qua` bên dưới) chứ không ném ngoại lệ cho CẢ LOẠT.

function _dich(chu, doi_so) {
	if (typeof __ === "function") return __(chu, doi_so);
	if (!doi_so) return chu;
	return chu.replace(/\{(\d+)\}/g, (_, i) => (doi_so[i] !== undefined ? doi_so[i] : ""));
}

// Đường dẫn máy chủ — NGUYÊN VĂN từ Interfaces của brief Task 5 cho hai hàm
// `lo_chua_co_o`/`dat_o_hang_loat`, một chỗ duy nhất để sửa nếu `vitri/o_tem.py`
// đổi tên hàm.
const _API_O_TEM = "erpnext.warehouse_operations.vitri.o_tem.";
const API_LO_CHUA_CO_O = _API_O_TEM + "lo_chua_co_o";
const API_DAT_O_HANG_LOAT = _API_O_TEM + "dat_o_hang_loat";
// Danh sách KHO đang quản lý vị trí — `o_tem.py` KHÔNG có hàm nào trả danh sách
// này (đúng: brief Task 5 chỉ liệt hai hàm ở trên, hai hàm màn này THỰC SỰ cần
// cho việc "đặt ô"). Bản Desk chọn kho qua một Link control của Frappe
// (`get_query` lọc `custom_quan_ly_vi_tri=1`) — một API riêng của Desk, cấm ở cả
// lớp luồng lẫn app (rule 3 của khuôn). App cần một nguồn khác để liệt kho.
// KHÔNG viết thêm một hàm máy chủ mới (ràng buộc toàn cục: "KHÔNG đổi bất kỳ hàm
// máy chủ nào" — thêm mới cũng tính, an toàn nhất là không đụng file `.py` nào).
// Tái dùng `xep.phieu_xep_dang_lam`: READ-ONLY, đã whitelist, đã có bài test
// (`test_xep_pda.py`), cùng vai trò được phép (`xep.VAI_TRO_DUOC_XEP` ==
// `o_tem.VAI_TRO_DAT_O`, xác minh trực tiếp trong hai file `.py`), và dùng ĐÚNG
// cùng một truy vấn `custom_quan_ly_vi_tri=1, is_group=0, disabled=0` mà Link
// filter của Desk đòi — không phải một danh sách kho khác đi. `mo()` bên dưới chỉ
// đọc `kho_ds`/`kho`, bỏ qua trường `phieu` (không liên quan màn này).
const API_KHO_QUAN_LY_VI_TRI = "erpnext.warehouse_operations.vitri.xep.phieu_xep_dang_lam";

// Câu báo — MỘT NƠI. Cặp `**…**` đánh dấu phần lớp vẽ nên TÔ ĐẬM (số dòng, mã ô,
// mã lô); lớp vẽ escape TOÀN BỘ TRƯỚC rồi mới đổi `**x**` thành `<b>x</b>` CỦA
// RIÊNG NÓ (xem `vo.js::_dam()`), nên máy chủ không có cách nào nhét một thẻ thật.
const CAU_CHUA_CHON_KHO = "Chọn kho để xem các lô chưa có ô trên tem.";
const CAU_KHONG_CO_KHO = "Chưa kho nào bật quản lý vị trí.";
const CAU_TRONG = "Mọi lô đang có tồn ở kho **{0}** đều đã có ô trên tem.";
const CAU_MO_DAU =
	"**{0}** lô đang có tồn mà chưa có ô trên tem — chưa xếp hay chuyển được. Soát ô đề xuất, " +
	"sửa nếu cần, rồi đặt ô. Đặt xong nhớ IN TEM và dán lên thùng.";
const CAU_KHONG_CO_DONG_DAT_DUOC = "Chưa có dòng nào chọn đủ ô để đặt.";
const NHAN_DAT_O = "Đặt ô";
const HOI_DAT_O = "Đặt ô cho {0} dòng đã chọn? Đặt xong nhớ IN TEM và dán lên thùng.";
const CAU_DA_DAT = "Đã đặt ô cho **{0}** lô.";
const CAU_CON_LOI = " **{0}** lô không đặt được — xem lý do trên từng dòng.";
// Hai TIÊU ĐỀ riêng cho Desk (không có dải báo như app — thay bằng tiêu đề hộp
// thoại/msgprint) — CÙNG SỐ LIỆU với `bao` (đếm trong `dat()`, MỘT NƠI), không
// đi qua tô đậm `**` (tiêu đề `msgprint`/`Dialog` không đi qua `KhoApp.bao()`
// nên không có ai đổi `**` thành `<b>` cho chúng). Soát xét: bản đầu của Task 5
// để Desk tự gõ lại "Đã đặt ô cho {0} lô"/"{0} lô không đặt được" TRONG
// `dat_o_hang_loat.js` — đúng loại nợ "lặp câu ở nhiều nơi" mà soát xét Task 2
// (P4) đã chỉ ra, và đúng thứ phép thử bọc `tao()` của người soát sẽ bắt được
// (luồng trả câu giả thì Desk vẫn hiện câu THẬT do chính nó gõ). Chuyển vào
// đây, `dat()` trả sẵn — Desk chỉ đọc.
const CAU_TIEU_DE_THANH_CONG = "Đã đặt ô cho {0} lô";
const CAU_TIEU_DE_LOI = "{0} lô không đặt được";
const CAU_NHAC_MAY_TINH = "Bảng rộng — nên làm trên máy tính.";
// Nhãn nút chính + câu cảnh báo "thiếu ô" — MỘT NƠI cho CẢ HAI lớp vẽ (rule 2).
// Trước bản gộp lớp này, Desk gốc tự gõ "Đặt ô cho {0} dòng ĐÃ CHỌN" ngay trong
// `cap_nhat_nut()` — brief Task 5 (Bước 5) lại đặt tên nút "Đặt ô cho N dòng" cho
// bản app. QUYẾT ĐỊNH (ghi trong báo cáo): dùng NGUYÊN VĂN chữ brief đặt cho nút
// — brief là đặc tả cho CẢ màn được thiết kế lại lẫn hành vi chung của Task này,
// và một nút chỉ có MỘT cách gọi tên trên cả hai lớp vẽ mới đúng tinh thần "lớp
// vẽ chỉ đọc kết luận của luồng, không tự quyết câu chữ" (khoá bằng phép thử bọc
// `tao()` mà brief mô tả: cả hai lớp vẽ phải hiện đúng câu luồng trả về).
const NHAN_NUT_DAT_NHIEU = "Đặt ô cho {0} dòng";
const NHAN_NUT_DAT_TRONG = "Đặt ô cho dòng đã chọn";
// Nguyên văn Desk gốc — phần "giàu hơn" phải giữ lại khi gộp lớp (rule 7).
const CAU_THIEU_O = "{0} dòng đã chọn chưa có ô — chọn ô hoặc bỏ chọn dòng đó.";
// Câu cho ca "ô lọc không khớp dòng nào" — vào đây cùng lúc với chính Ô LỌC (xem
// `dat_bo_loc()`): câu nào nói về một tập dòng thì phải đứng cạnh nơi quyết định
// tập dòng đó, không thì lại là một câu sống ở lớp vẽ.
const CAU_LOC_TRONG = "Không có dòng nào khớp bộ lọc.";

function tao({ goi }) {
	// -------------------------------------------------------------- trạng thái
	let kho = null;
	let kho_ds = [];
	// Dòng từ `lo_chua_co_o`, đã CHUẨN HOÁ tên trường (xem `_chuan_hoa_dong`).
	let dong = [];
	// { số lô: có tick không } — sống QUA một lượt `nap()` lại CÙNG MỘT KHO (Desk
	// gốc: "giữ ngoài `this.dong` để nạp lại không mất những ô người dùng vừa sửa
	// tay"/"tick vừa bấm"). Bị xoá khi KHO ĐỔI (`_doi_sang_kho()`, gọi từ CẢ `nap()`
	// lẫn `mo()` — xem vì sao ở đó), và bị xoá CHỌN LỌC theo từng dòng sau một lượt
	// `dat()` (xem cuối `dat()`: dòng đặt xong xoá hẳn, dòng LỖI bị hạ tick).
	let da_chon = {};
	// { số lô: ô người dùng tự chọn/sửa tay } — cùng lý do sống qua `nap()` lại.
	let o_dat = {};
	// { số lô: lý do lần ĐẶT GẦN NHẤT của dòng đó bị máy chủ từ chối } — phần
	// GIÀU HƠN so với hộp `msgprint` liệt cả loạt của Desk gốc (rule 7): mỗi thẻ
	// dòng trên màn hẹp tự hiện lý do của CHÍNH nó, không bắt thủ kho đối chiếu
	// một danh sách rời với bảng. Desk vẫn giữ hộp liệt cả loạt của riêng nó
	// (đọc từ `loi` mà `dat()` trả về) — đây chỉ là dữ liệu THÊM cho ai muốn dùng.
	let loi_dat_gan_day = {};
	// Số thứ tự lượt nạp — dùng để bỏ một phản hồi CŨ về muộn (Desk gốc,
	// `dohl_hang_loat.js`: "ô Kho của Frappe bắn `change` hai lần…, lần nạp đến
	// sau từng vẽ lại bảng, xoá sạch tick người dùng vừa bấm"). Chép lại đúng
	// khuôn `lan`/`lan_nay` của các màn app khác — sự cố đã ĐO ĐƯỢC trên erptest
	// 20/09, không phải phòng xa suông.
	let _lan_nap = 0;
	// Ô LỌC (chuỗi người dùng gõ để thu hẹp danh sách đang hiện). SỐNG Ở ĐÂY, không
	// ở lớp vẽ — soát xét tổng (M5) đo được: khi lớp vẽ giữ riêng bộ lọc, "Chọn tất
	// cả dòng có ô" đếm TOÀN BỘ `dong` còn màn hình chỉ hiện tập đã lọc, nên lọc còn
	// một thẻ rồi bấm nút đó là ghi cho cả những lô KHÔNG NHÌN THẤY. "Đang hiện dòng
	// nào" và "chọn tất cả tác động lên dòng nào" là MỘT quyết định, không thể nằm ở
	// hai lớp. Desk không có ô lọc — `bo_loc` ở đó luôn rỗng, `_khop_loc` trả `true`
	// cho mọi dòng, nên hành vi Desk không đổi một chút nào.
	let bo_loc = "";

	// ---------------------------------------------------------------- nội bộ

	// `lo_chua_co_o` THẬT (xem `vitri/o_tem.py`) trả `o_de_xuat`/`ma_in_nhan_de_xuat`
	// — KHÔNG phải `o_goi_y` mà Bước 1 của brief (bài test mẫu) dùng. Hai tên khác
	// nhau vì brief tự lệch với máy chủ thật (không phải lỗi chép) — QUYẾT ĐỊNH
	// (ghi trong báo cáo Task 5): chấp nhận CẢ HAI, ưu tiên `o_goi_y` khi có (giữ
	// bài mẫu chạy nguyên văn), rơi về `o_de_xuat` khi không (giữ sản xuất thật
	// chạy đúng) — không sửa máy chủ, không sửa bài test mẫu.
	function _chuan_hoa_dong(ds) {
		return (ds || []).map((d) => ({
			...d,
			o_goi_y: d.o_goi_y !== undefined && d.o_goi_y !== null ? d.o_goi_y : d.o_de_xuat || null,
			ma_in_nhan_goi_y:
				d.ma_in_nhan_goi_y !== undefined && d.ma_in_nhan_goi_y !== null
					? d.ma_in_nhan_goi_y
					: d.ma_in_nhan_de_xuat || null,
		}));
	}

	// Ô đang dùng cho một dòng: người dùng đã sửa thì lấy của họ, chưa thì lấy gợi
	// ý — cùng luật `o_cua()` của Desk gốc.
	function _o_cua(d) {
		return o_dat[d.so_lo] !== undefined ? o_dat[d.so_lo] : d.o_goi_y || "";
	}

	// Dòng có tick không: người dùng đã bấm thì theo họ; CHƯA bấm thì mặc định
	// theo "dòng NÀY hiện có đang mang một ô hay không" — cùng luật `co_tick()`
	// của Desk gốc (không phải "dòng có `o_goi_y` gốc hay không": một dòng ban đầu
	// KHÔNG có gợi ý mà người dùng vừa tự gõ một ô cho nó thì tự tick NGAY, không
	// bắt bấm thêm hộp kiểm).
	function _co_chon(d) {
		return da_chon[d.so_lo] !== undefined ? da_chon[d.so_lo] : !!_o_cua(d);
	}

	function _xoa_lua_chon() {
		da_chon = {};
		o_dat = {};
	}

	// Một dòng có khớp ô lọc không — so trên số lô, tên hàng, mã vật tư. Bộ lọc
	// rỗng khớp MỌI dòng (đường Desk, và app lúc chưa gõ gì).
	function _khop_loc(d) {
		if (!bo_loc) return true;
		const gop = `${d.so_lo || ""} ${d.ten_hang || ""} ${d.vat_tu || ""}`.toLowerCase();
		return gop.includes(bo_loc.trim().toLowerCase());
	}

	// ĐỔI KHO thì lựa chọn của kho CŨ hết nghĩa — một ô của kho A gõ dở cho `LO-9`
	// mà theo sang kho B sẽ được GHI LÊN TEM lô ở kho B (`o_tem.doi_o_tren_tem` chỉ
	// kiểm ô thuộc MỘT kho đang quản lý vị trí, KHÔNG so với kho đang giữ tồn — lỗ
	// hổng máy chủ có sẵn, ghi trong báo cáo, không sửa ở đợt này). Từ đó `xep_hang`
	// trả SAI Ô vĩnh viễn cho lô đó, chỉ Stock Manager gỡ được.
	//
	// VÌ SAO Ở ĐÂY chứ không ở mỗi lớp vẽ: hai lớp vẽ tới cùng một chỗ bằng HAI
	// đường — app đổi kho qua `mo()`, Desk đổi kho bằng chính `nap()` (ô Link "Kho"
	// của `dat_o_hang_loat.js`). Soát xét tổng (N1) dựng lại được lỗi ghi sai dữ
	// liệu đúng vì `mo()` dọn còn `nap()` thì không. Đặt luật vào ĐÂY — nơi cả hai
	// đường bắt buộc đi qua — thay vì bắt mỗi lớp vẽ tự nhớ dọn.
	//
	// CÓ ĐIỀU KIỆN (`kho_moi !== kho`), không phải dọn vô điều kiện: `hoi_dat()` và
	// `dat()` đều `nap()` lại CÙNG một kho, dọn vô điều kiện ở đó là xoá sạch tick
	// ngay trước khi hỏi/ghi. Ô lọc cũng theo kho (một chuỗi lọc của kho A không nói
	// gì về kho B) nên reset cùng lúc.
	function _doi_sang_kho(kho_moi) {
		if (kho_moi !== kho) {
			_xoa_lua_chon();
			bo_loc = "";
		}
		kho = kho_moi;
	}

	// Tải lại DANH SÁCH LÔ CHƯA CÓ Ô của một kho. CHỈ gọi `lo_chua_co_o` — không gì
	// khác (việc HỎI xem có những kho nào là của `mo()`). Nạp lại CÙNG MỘT KHO không
	// đụng `da_chon`/`o_dat`: không được xoá lựa chọn người dùng vừa làm dở (Desk
	// gốc, xem khai báo `da_chon`/`o_dat` ở trên) — dùng cho cả lượt vào màn LẪN cho
	// `hoi_dat()` (ràng buộc riêng Task 5: hỏi lại máy chủ trước khi hỏi người
	// dùng). Nạp một kho KHÁC thì `_doi_sang_kho()` dọn (xem hàm đó).
	async function nap(kho_muon) {
		_doi_sang_kho(kho_muon);
		const lan = ++_lan_nap;
		const r = await goi(API_LO_CHUA_CO_O, { kho });
		if (lan !== _lan_nap) return trang_thai(); // lần nạp cũ về muộn — bỏ (đo được trên erptest)
		dong = _chuan_hoa_dong(r);
		return trang_thai();
	}

	// Chọn kho: không truyền `kho` thì hỏi máy chủ danh sách kho đang quản lý vị
	// trí (tái dùng `xep.phieu_xep_dang_lam`, xem hằng số `API_KHO_QUAN_LY_VI_TRI`
	// ở trên). Đúng MỘT kho thì tự nạp luôn — cùng quyết định Desk gốc để "kho để
	// xếp" tự chọn khi chỉ có một lựa chọn, không bắt bấm thêm một bước thừa.
	async function mo(kho_muon) {
		const r = await goi(API_KHO_QUAN_LY_VI_TRI, { kho: kho_muon || null });
		kho_ds = r.kho_ds || [];
		const kho_moi = r.kho || null;
		// Không có kho nào: `_doi_sang_kho(null)` dọn nếu ta đang đứng ở một kho —
		// KHÔNG kiểm `kho_moi !== kho` lần nữa ở đây (luật đó sống ĐÚNG MỘT NƠI, xem
		// `_doi_sang_kho`); nhánh có kho đi qua `nap()`, cũng gọi chính hàm đó.
		if (!kho_moi) {
			_doi_sang_kho(null);
			dong = [];
			return trang_thai();
		}
		return nap(kho_moi);
	}

	// "Đổi kho": về màn chọn kho — cùng lý do `doi_kho()` của các luồng khác.
	function doi_kho() {
		_doi_sang_kho(null);
		dong = [];
		return trang_thai();
	}

	// Ô LỌC — quyết định "đang hiện dòng nào", và vì thế cũng quyết định "chọn tất
	// cả tác động lên dòng nào" (xem `chon_tat_ca`). Trả `trang_thai()` như mọi
	// hành động khác để lớp vẽ chỉ việc vẽ lại.
	function dat_bo_loc(chu) {
		bo_loc = chu == null ? "" : String(chu);
		return trang_thai();
	}

	function chon(so_lo, co_chon) {
		da_chon[so_lo] = !!co_chon;
		return trang_thai();
	}

	// "Chọn tất cả dòng có ô" (thiết kế lại cho màn hẹp, brief Bước 5) — CHỌN chỉ
	// tick những dòng ĐANG CÓ Ô (gợi ý hoặc đã tự gõ), không kéo theo dòng còn
	// thiếu ô: khác Desk gốc (hộp kiểm đầu bảng tick TẤT CẢ bất kể có ô hay
	// không, rồi hiện dòng cảnh báo đỏ "N dòng chưa có ô"). QUYẾT ĐỊNH (ghi trong
	// báo cáo): đúng chữ trên nút mà brief đặt tên — "có ô" là điều kiện, không
	// phải một mô tả suông. BỎ chọn (`co_chon = false`) thì vẫn bỏ hết, kể cả
	// dòng có ô — đối xứng với "chọn tất cả", và giữ đúng Desk gốc cho chiều này.
	//
	// KHÔNG ghi đè một lượt BỎ CHỌN TAY trước đó (`da_chon[so_lo] === false`):
	// đo được trên trình duyệt thật (Playwright, kịch bản Task 5) — bỏ tick một
	// dòng rồi bấm "Chọn tất cả dòng có ô" khiến dòng đó BẬT TRỞ LẠI, một cú bấm
	// "tiện" âm thầm xoá quyết định người dùng VỪA làm. Chỉ tự chọn những dòng
	// NGƯỜI DÙNG CHƯA TỪNG ĐỤNG (`da_chon[so_lo] === undefined`) — đúng ý nút
	// "chọn thêm những dòng còn lại đang có ô", không phải "ép chọn lại tất cả".
	//
	// CHỈ TÁC ĐỘNG LÊN TẬP ĐANG LỌC (soát xét tổng, M5): nút này đứng ngay cạnh ô
	// lọc trên màn 4 inch, người dùng đọc nó là "chọn những thẻ tôi ĐANG NHÌN THẤY".
	// Trước bản sửa này nó duyệt TOÀN BỘ `dong`, nên lọc còn một thẻ rồi bấm nút này
	// và bấm nút chính là GHI cho cả những lô không nhìn thấy. Chiều BỎ chọn cũng
	// theo tập đang lọc — đối xứng, và cùng một câu trả lời cho "nút này nói về
	// những dòng nào".
	function chon_tat_ca(co_chon) {
		dong.filter(_khop_loc).forEach((d) => {
			if (co_chon) {
				if (_o_cua(d) && da_chon[d.so_lo] === undefined) da_chon[d.so_lo] = true;
			} else {
				da_chon[d.so_lo] = false;
			}
		});
		return trang_thai();
	}

	// Người dùng tự chọn/sửa ô cho một dòng. Dòng vừa được cho một ô mà CHƯA từng
	// bị người dùng đụng tới tick (`da_chon[so_lo] === undefined`) thì tự chọn
	// NGAY qua `_co_chon()` (không cần set tường minh ở đây, xem hàm đó) — cùng
	// hiệu ứng nút "chọn ô" của Desk gốc tự tick dòng vừa gán ô. Xoá lý do lỗi lần
	// đặt TRƯỚC của dòng này: người dùng đang SỬA, giữ một lý do cũ trên một ô
	// MỚI là nói dối về việc vừa làm.
	function dat_o_cho_dong(so_lo, o) {
		o_dat[so_lo] = o || "";
		// Dòng này vừa bị máy chủ TỪ CHỐI ở lượt `dat()` trước: chính `dat()` đã hạ
		// tick của nó xuống `false` (xem cuối `dat()`) — đó là quyết định CỦA TA,
		// không phải một lượt bỏ chọn tay của người dùng. Người dùng đang SỬA ô để
		// chữa đúng dòng đó, nên trả nó về mặc định (`_co_chon`: có ô thì tick) thay
		// vì bắt bấm thêm một cú vào hộp kiểm. Chỉ đụng khi CÓ lý do lỗi — dòng
		// thường mà người dùng đã tự bỏ tick vẫn giữ nguyên quyết định của họ.
		if (loi_dat_gan_day[so_lo] !== undefined) delete da_chon[so_lo];
		delete loi_dat_gan_day[so_lo];
		return trang_thai();
	}

	function so_dong_chon() {
		return dong.filter(_co_chon).length;
	}

	function dat_duoc() {
		const ds = dong.filter(_co_chon);
		return ds.length > 0 && ds.every((d) => !!_o_cua(d));
	}

	function _dong_se_dat() {
		return dong.filter(_co_chon).filter((d) => _o_cua(d));
	}

	// RÀNG BUỘC RIÊNG CỦA TASK 5 (màn có GHI): hỏi lại máy chủ TRƯỚC khi dựng câu
	// hỏi — cùng khuôn `hoi_bo_luot`/`hoi_hoan_tat` của `luong/lay_hang.js`. Số
	// dòng nói trong câu hỏi phải là số liệu MỚI (một dòng vừa bị người khác đặt
	// mất ô trong lúc màn hình mở thì không còn tự chọn được ở đây nữa, câu hỏi
	// phải phản ánh đúng điều đó — không hỏi về một dòng sắp bị máy chủ từ chối).
	async function hoi_dat() {
		if (!kho) return { ok: false, bao: _dich(CAU_CHUA_CHON_KHO), muc: "cam" };
		await nap(kho);
		const ds = _dong_se_dat();
		if (!ds.length) return { ok: false, bao: _dich(CAU_KHONG_CO_DONG_DAT_DUOC), muc: "cam" };
		return { ok: true, nhan: _dich(NHAN_DAT_O), cau: _dich(HOI_DAT_O, [ds.length]) };
	}

	// `dat_o_hang_loat` THẬT (xem `vitri/o_tem.py`) trả `{xong, loi}` — `xong` là
	// mảng ĐỐI TƯỢNG `{so_lo, o, ma_in_nhan}`, `loi` là mảng `{so_lo, loi}` (câu
	// bằng chuỗi, khoá `loi` — TRÙNG TÊN với chính mảng cha, dễ nhầm). Bước 1 của
	// brief (bài test mẫu) lại đặt tên `da_dat`/`ly_do` — CÙNG kiểu lệch tên với
	// `lo_chua_co_o` ở trên, không phải lỗi chép. QUYẾT ĐỊNH (ghi trong báo cáo):
	// `dat()` trả ra NGOÀI đúng hình dạng `{da_dat, loi}` mà Interfaces của brief
	// đặt tên (rule của Produces), nhưng ĐỌC VÀO từ CẢ HAI tên trường của máy chủ
	// — không đổi máy chủ, không đổi bài test mẫu.
	//
	// KHÔNG rút gọn `da_dat` về một mảng CHUỖI mã lô: `xong` thật mang cả `o`/
	// `ma_in_nhan` — thứ màn cần để mời in tem đúng NHỮNG lô vừa đặt (Desk gốc,
	// `hoi_in()`). Rút gọn ở đây là đúng kiểu đánh rơi tính năng mà Task 3 từng
	// mắc khi gộp lớp (rule 7) — thay vào đó, một mục DẠNG CHUỖI của bài mẫu được
	// NÂNG lên thành đối tượng `{so_lo}` (chiều ngược lại, không mất thông tin).
	function _chuan_hoa_ket_qua(r) {
		const nguon_dat = r.xong || r.da_dat || [];
		const da_dat = nguon_dat.map((x) => (typeof x === "string" ? { so_lo: x } : x));
		const loi = (r.loi || []).map((x) => ({
			so_lo: x.so_lo,
			ly_do: x.ly_do != null ? x.ly_do : x.loi || "",
		}));
		return { da_dat, loi };
	}

	// Đặt ô cho các dòng ĐÃ CHỌN VÀ ĐÃ CÓ Ô (dòng chọn mà thiếu ô bị LOẠI ở đây,
	// không đẩy xuống máy chủ — `dat_duoc()` đã chặn nút, nhưng hàm này tự lọc lại
	// một lần nữa, không tin tưởng mù quáng vào việc lớp vẽ đã gọi đúng thứ tự).
	async function dat() {
		const ds = _dong_se_dat().map((d) => ({ so_lo: d.so_lo, o: _o_cua(d) }));
		const r = await goi(API_DAT_O_HANG_LOAT, { dong: ds });
		const { da_dat, loi } = _chuan_hoa_ket_qua(r);
		loi_dat_gan_day = {};
		loi.forEach((x) => {
			loi_dat_gan_day[x.so_lo] = x.ly_do;
		});
		// Dọn CHỌN LỌC theo từng dòng, KHÔNG xoá sạch như Desk gốc ("this.chon = {};
		// this.tick = {};"). Soát xét tổng (T1): xoá sạch thì dòng LỖI rơi về mặc
		// định của `_co_chon` ("có ô thì tick") và TỰ TICK LẠI ngay — bấm nút lần hai
		// là gửi lại đúng những dòng máy chủ vừa từ chối, với đúng cái ô vừa bị từ
		// chối. Thay bằng:
		// - dòng ĐẶT XONG: xoá hẳn (nó biến khỏi `lo_chua_co_o` lần nạp sau, tick/ô
		//   còn lại chỉ là rác);
		// - dòng LỖI: HẠ tick xuống `false` tường minh (không phải `delete`, để mặc
		//   định "có ô thì tick" không bật nó lên lại), nhưng GIỮ ô người dùng đã gõ
		//   — ô đó đứng cạnh lý do từ chối trên cùng một thẻ, xoá đi là bắt thủ kho
		//   đoán mình vừa gõ gì. Sửa ô của dòng đó sẽ tự trả tick về mặc định (xem
		//   `dat_o_cho_dong`).
		da_dat.forEach((x) => {
			delete da_chon[x.so_lo];
			delete o_dat[x.so_lo];
		});
		loi.forEach((x) => {
			da_chon[x.so_lo] = false;
		});
		if (kho) await nap(kho);
		// Câu kết quả — MỘT NƠI cho CẢ HAI lớp vẽ (rule 2). `bao`/`muc` cho dải báo
		// của app (`KhoApp.bao()`, có `**`); `tieu_de_thanh_cong`/`tieu_de_loi` cho
		// hai tiêu đề riêng của Desk (không `**` — xem hằng số ở đầu file). Trước
		// bản sửa này (soát xét, sau Playwright mục 7 của báo cáo Task 5), câu này
		// SỐNG Ở HAI NƠI KHÁC NHAU — một hàm phụ `cau_ket_qua_dat()` xuất cạnh
		// `tao()` cho app gọi, còn Desk tự gõ lại "Đã đặt ô cho {0} lô"/"{0} lô
		// không đặt được" ngay trong `hoi_in()`/`dat()` của chính nó. Một hàm phụ
		// đứng NGOÀI namespace mà người soát bọc (`tao()`) không thể bị phép thử
		// "bọc `tao()` cho luồng trả câu giả" chạm tới — CHỈ những gì `dat()` (một
		// phương thức của namespace ĐÃ BỌC) tự trả mới đi qua được phép thử đó.
		let bao = _dich(CAU_DA_DAT, [String(da_dat.length)]);
		if (loi.length) bao += _dich(CAU_CON_LOI, [String(loi.length)]);
		return {
			da_dat,
			loi,
			bao,
			muc: loi.length ? "cam" : "xanh",
			tieu_de_thanh_cong: da_dat.length ? _dich(CAU_TIEU_DE_THANH_CONG, [String(da_dat.length)]) : null,
			tieu_de_loi: loi.length ? _dich(CAU_TIEU_DE_LOI, [String(loi.length)]) : null,
		};
	}

	function trang_thai() {
		const the_dong = dong.map((d) => ({
			so_lo: d.so_lo,
			vat_tu: d.vat_tu,
			ten_hang: d.ten_hang,
			ton: d.ton,
			dang_o: d.dang_o || null,
			hsd: d.hsd || null,
			chon: _co_chon(d),
			o: _o_cua(d),
			o_goi_y: d.o_goi_y,
			ma_in_nhan_goi_y: d.ma_in_nhan_goi_y,
			// Lý do KHÔNG có gợi ý (mặt hàng chưa gán vị trí, lỗi tính gợi ý…) —
			// nguyên văn máy chủ. Lý do lần ĐẶT vừa rồi bị từ chối (nếu có) đứng
			// riêng ở `loi_dat`, không đè lên câu này — hai câu nói về hai việc
			// khác nhau (một câu về VÌ SAO không có gợi ý, một câu về VÌ SAO một
			// lần bấm "Đặt ô" vừa thất bại).
			ly_do: d.ly_do || null,
			loi_dat: loi_dat_gan_day[d.so_lo] || null,
		}));
		const chon_ds = the_dong.filter((d) => d.chon);
		const thieu_o = chon_ds.filter((d) => !d.o).length;
		// `dong` là TOÀN BỘ danh sách (Desk vẽ hết, không có ô lọc); `dong_hien` là
		// tập sau ô lọc — thứ app VẼ RA và cũng đúng tập mà `chon_tat_ca()` tác động.
		// Hai tên riêng, cùng một nguồn: lớp vẽ không tự lọc lại nữa nên không còn
		// cách nào để "đang hiện" lệch với "chọn tất cả sẽ chạm vào".
		//
		// `nhan_nut_dat`/`so_dong_chon`/`dat_duoc` CỐ Ý vẫn đếm trên TOÀN BỘ: một
		// dòng đã tick rồi bị ô lọc che đi vẫn là một dòng NGƯỜI DÙNG ĐÃ CHỌN, và
		// nhãn nút nói đúng con số ấy. Bỏ chúng khỏi lượt ghi chỉ vì bộ lọc mới là
		// cắt giảm lén lút — cái phải sửa là "chọn tất cả" âm thầm tick thêm dòng
		// không nhìn thấy, và đó là chỗ đã sửa.
		const dong_hien = the_dong.filter(_khop_loc);
		return {
			kho,
			kho_ds: kho_ds.slice(),
			dong: the_dong,
			dong_hien,
			bo_loc,
			cau_loc_trong: the_dong.length && !dong_hien.length ? _dich(CAU_LOC_TRONG) : null,
			trong: !the_dong.length,
			so_dong_chon: chon_ds.length,
			so_dong_thieu_o: thieu_o,
			dat_duoc: chon_ds.length > 0 && thieu_o === 0,
			// Câu chữ đầu/chân màn — MỘT NƠI (rule 2), CẢ HAI lớp vẽ (app + Desk) chỉ
			// ghép vào khung, không tự gõ lại. `nhan_nut_dat`/`canh_bao_thieu_o` thay
			// cho việc mỗi lớp vẽ tự lắp ráp một câu số-đếm riêng (Desk gốc: "Đặt ô
			// cho {0} dòng ĐÃ CHỌN"; brief app: "Đặt ô cho {0} dòng") — phép thử người
			// soát bọc `tao()` cho luồng trả câu giả sẽ đòi CẢ HAI lớp vẽ hiện đúng
			// câu đó, một chỗ lắp câu ở mỗi lớp vẽ là trượt ngay phép thử này.
			cau_dau: !kho_ds.length
				? _dich(CAU_KHONG_CO_KHO)
				: !kho
				? _dich(CAU_CHUA_CHON_KHO)
				: the_dong.length
				? _dich(CAU_MO_DAU, [String(the_dong.length)])
				: _dich(CAU_TRONG, [kho]),
			nhac_may_tinh: _dich(CAU_NHAC_MAY_TINH),
			nhan_nut_dat: chon_ds.length
				? _dich(NHAN_NUT_DAT_NHIEU, [String(chon_ds.length)])
				: _dich(NHAN_NUT_DAT_TRONG),
			canh_bao_thieu_o: thieu_o ? _dich(CAU_THIEU_O, [String(thieu_o)]) : null,
		};
	}

	return {
		mo,
		nap,
		doi_kho,
		chon,
		chon_tat_ca,
		dat_bo_loc,
		dat_o_cho_dong,
		so_dong_chon,
		dat_duoc,
		hoi_dat,
		dat,
		trang_thai,
	};
}

// ------------------------------------------------------------- hai môi trường
// HAI CÂU `if` ĐỘC LẬP, KHÔNG `if/else` — chép NGUYÊN lý do đầy đủ ở cuối
// `tra_cuu.js`/`xep_hang.js`/`lay_hang.js` (esbuild bọc `__commonJS` nên `typeof
// module` đúng cả trong trình duyệt; hai `if` rời không phụ thuộc thứ tự viết,
// khác `if/else`).
if (typeof frappe !== "undefined" && frappe.provide) {
	frappe.provide("erpnext.warehouse_operations.luong");
	erpnext.warehouse_operations.luong.dat_o = { tao };
}
if (typeof module !== "undefined" && module.exports) {
	module.exports = { tao };
}
