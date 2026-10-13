// Trang "Đặt ô trên tem hàng loạt" — máy tính, không phải PDA.
//
// VÌ SAO CÓ: luật 19/09/2026 ("lô chỉ xếp vào đúng ô in trên tem") khoá cứng
// mọi lô chưa có ô trên tem. Trên site thử, ngay lúc luật ra đời đã có 60 lô
// đang có tồn ở tình trạng đó — đặt tay từng lô là 60 lần mở form Lô. Trang này
// làm một lượt, rồi in tem cho đúng những lô vừa đặt.
//
// CHỈ ĐẶT cho lô CHƯA có ô (máy chủ cũng chặn, xem `vitri/o_tem.py`). Đổi ô đã
// có là quyền trưởng kho, từng lô một, có lý do — một màn hình "đổi hàng loạt"
// chính là cửa sau mà luật này sinh ra để đóng.
//
// PHẦN QUYẾT ĐỊNH ("dòng nào tự chọn sẵn", "dòng nào cho đặt", câu chữ đầu/chân
// trang, nhãn nút) KHÔNG còn nằm ở đây (Task 5, Bước 6 của brief app PDA `/kho`)
// — đã chuyển sang `luong/dat_o.js`, CÙNG một file mà màn "Đặt ô" của app PDA
// (`kho_pda/man_dat_o.js`) dùng, để hai nơi không lệch luật. File này chỉ còn
// giữ TOÀN BỘ phần VẼ của Desk — bảng rộng với một Link control THẬT (autocomplete
// tới `Storage Location`) trên mỗi dòng, hộp kiểm chọn hết, và hộp mời in tem sau
// khi đặt xong.
//
// LƯỢT GHI ĐI QUA `hoi_dat()` CỦA LUỒNG, CÙNG ĐƯỜNG VỚI APP (soát xét tổng, T7).
// Bản trước gọi thẳng `_luong.dat()`, nên ràng buộc riêng của màn có GHI — "hỏi
// lại máy chủ TRƯỚC khi ghi, không quyết trên số liệu cũ" — chỉ sống ở bản app.
// Đó là chuyện ĐÚNG SỐ LIỆU (một lô vừa bị người khác đặt mất ô trong lúc trang
// mở thì không còn nằm trong lượt ghi này nữa), KHÔNG phải chuyện có hộp xác nhận
// hay không — và trang này vẫn KHÔNG có hộp xác nhận nào chắn giữa nút chính và
// lượt ghi, đúng như Desk gốc. Xem `dat()` bên dưới: vòng sửa 1 có cắm một hộp
// vào đây, vòng sửa 2 gỡ ra vì chính nó đẻ ra một lỗi bấm-hai-lần.
(function () {
	const DUONG_IN_NHAN = "/assets/erpnext/js/warehouse_operations/in_nhan_lo.js";
	const LUONG_DAT_O = "/assets/erpnext/js/warehouse_operations/luong/dat_o.js";

	frappe.pages["dat-o-hang-loat"].on_page_load = function (wrapper) {
		const page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Đặt ô trên tem hàng loạt"),
			single_column: true,
		});
		// Nạp lớp LUỒNG trước — constructor bên dưới gọi
		// `erpnext.warehouse_operations.luong.dat_o.tao(...)` ngay lập tức, đúng
		// tinh thần `lay_hang_pda.js` (Task 4, Bước 6).
		frappe.require(LUONG_DAT_O, () => {
			wrapper.dat_o = new DatOHangLoat(page);
		});
	};

	frappe.pages["dat-o-hang-loat"].on_page_show = function (wrapper) {
		// Quay lại trang: nạp lại — người khác có thể vừa đặt ô cho vài lô.
		if (wrapper.dat_o) wrapper.dat_o.nap_lai();
	};

	class DatOHangLoat {
		constructor(page) {
			this.page = page;
			// Phần QUYẾT ĐỊNH — CÙNG một luồng mà màn "Đặt ô" của app PDA dùng.
			// `goi: frappe.xcall` — đã tự hiện câu báo máy chủ cho lỗi quyền/mất
			// mạng/ghi bị từ chối, cùng lẽ `lay_hang_pda.js`.
			this._luong = erpnext.warehouse_operations.luong.dat_o.tao({ goi: frappe.xcall });
			// Bản sao ĐỌC của trạng thái luồng — làm mới bằng `_dong_bo()` ngay sau
			// MỌI lời gọi luồng, trước khi `ve()` đọc nó (cùng khuôn `lay_hang_pda.js`).
			this.st = this._luong.trang_thai();
			this.dung();
			this.khoi_dong();
		}

		_dong_bo() {
			this.st = this._luong.trang_thai();
		}

		dung() {
			this.chon_kho = this.page.add_field({
				fieldname: "kho",
				label: __("Kho"),
				fieldtype: "Link",
				options: "Warehouse",
				get_query: () => ({ filters: { custom_quan_ly_vi_tri: 1, is_group: 0, disabled: 0 } }),
				change: () => {
					const kho = this.chon_kho.get_value();
					// Bỏ qua nếu ĐÃ ĐÚNG kho đang xem — `khoi_dong()` có thể vừa tự đặt
					// giá trị này (kho quản lý vị trí duy nhất), và ô Link của Frappe bắn
					// `change` thêm một lần khi mất focus dù giá trị không đổi (Desk gốc,
					// chú thích cũ: "ô Kho của Frappe bắn `change` hai lần"). Không chặn
					// thì một lượt nạp THỪA chạy song song, đúng con bug `lan_nap` từng
					// vá — nay lưới an toàn đó sống trong CHÍNH `luong/dat_o.js::nap()`
					// (số thứ tự lượt nạp, bỏ phản hồi cũ về muộn), Desk không cần giữ
					// bản riêng nữa.
					if (kho === this.st.kho) return;
					this.nap(kho);
				},
			});
			this.page.set_primary_action(__("Đặt ô cho dòng đã chọn"), () => this.dat());
			this.$goc = $(`
				<div class="dohl">
					<div class="dohl-mo-dau text-muted"></div>
					<div class="dohl-bang"></div>
				</div>
			`).appendTo(this.page.main);

			this.$goc.on("change", ".dohl-chon", (ev) => {
				const so_lo = $(ev.currentTarget).attr("data-lo");
				this._luong.chon(so_lo, ev.currentTarget.checked);
				this._dong_bo();
				this.cap_nhat_nut();
			});
			// `change`, KHÔNG `click`: với hộp kiểm, `click` bắt được cả những cú
			// bấm KHÔNG đổi trạng thái (bấm vào viền ô, bấm lúc trình duyệt đang
			// giữ focus) — đo trên erptest 20/09: lần bấm đầu tiên vào "chọn tất
			// cả" không đổi gì, phải bấm lần hai mới ăn.
			this.$goc.on("change", ".dohl-chon-het", (ev) => {
				const bat = ev.currentTarget.checked;
				// "Chọn hết" của Desk tick TẤT CẢ các dòng, KỂ CẢ dòng chưa có ô (rồi
				// hiện `dohl-thieu-o` đỏ nhắc người dùng tự chọn/bỏ chọn) — khác nút
				// "Chọn tất cả dòng CÓ Ô" của bản app (brief Task 5, thiết kế lại cho
				// màn hẹp: chỉ tick dòng đã sẵn có ô, tránh một cú bấm làm chặn cứng
				// nút chính trên màn 4 inch). Hai hành vi khác nhau CÓ CHỦ ĐÍCH — giữ
				// đúng Desk gốc ở đây (rule 7: không cắt tính năng đang chạy), vòng lặp
				// gọi thẳng `chon()` cho từng dòng thay vì `chon_tat_ca()` (hàm đó dành
				// riêng cho nút của app, xem `luong/dat_o.js`).
				this.st.dong.forEach((d) => this._luong.chon(d.so_lo, bat));
				this._dong_bo();
				this.ve();
			});
			this.ve();
		}

		// Nạp danh sách KHO quản lý vị trí một lần lúc mở trang — CHỈ để câu mở đầu
		// ("Chưa kho nào bật quản lý vị trí."/"N lô...") có đúng số liệu: `cau_dau`
		// của luồng phân biệt "chưa có kho nào quản lý vị trí" với "có kho, chưa
		// chọn" bằng `kho_ds.length` (xem `luong/dat_o.js::trang_thai`) — số đó chỉ
		// có khi gọi `mo()`. Desk vẫn dùng Link control CỦA RIÊNG NÓ (autocomplete
		// đầy đủ của Frappe) để CHỌN kho, không đổi UI này (rule "giữ nguyên phần
		// vẽ") — `mo()` ở đây không vẽ nút chọn kho nào, chỉ mượn số liệu của nó.
		// TIỆN ÍCH THÊM hợp lý, không cắt gì đang có: `mo()` có thể tự chọn sẵn một
		// kho, và giá trị đó được đặt luôn vào ô Link để người dùng khỏi phải chọn
		// tay (Desk gốc TRƯỚC bản vá luôn bắt tự chọn dù chỉ có một lựa chọn).
		//
		// `mo()` TỰ CHỌN THEO HAI LUẬT, không phải một (soát xét tổng, T6 — chú thích
		// cũ ở đây chỉ kể luật thứ nhất nên HẸP HƠN điều mã thật sự làm). Nguồn là
		// `xep.phieu_xep_dang_lam` (`xep.py:245-256`):
		//   1. có ĐÚNG MỘT kho quản lý vị trí  → chọn luôn kho đó;
		//   2. có NHIỀU kho                     → lấy kho của PHIẾU XẾP NHÁP GẦN NHẤT
		//      của chính người dùng (`docstatus = 0`, `owner = người đang đăng nhập`,
		//      `order_by modified desc`), nếu kho đó còn nằm trong danh sách kho quản
		//      lý vị trí; không có phiếu nháp nào thì để trống cho người dùng chọn.
		// Luật 2 nghĩa là trang có thể tự nạp một kho người dùng CHƯA HỀ chọn trên
		// màn này, suy từ một việc khác (lần xếp hàng gần nhất của họ). Giữ nguyên
		// hành vi — nó tái dùng đúng hàm máy chủ đã có và thường đoán đúng ý — nhưng
		// ghi ra đây để không ai đọc chú thích rồi tưởng "nhiều kho thì luôn trống".
		khoi_dong() {
			this.page.main.addClass("dohl-dang-nap");
			return this._luong
				.mo()
				.then((st) => {
					this.st = st;
					if (st.kho) this.chon_kho.set_value(st.kho);
					this.ve();
				})
				.finally(() => this.page.main.removeClass("dohl-dang-nap"));
		}

		// Tải lại danh sách của một kho ĐÃ CHỌN (đổi kho, hoặc quay lại trang qua
		// `nap_lai()`). `kho` rỗng (người dùng xoá ô Link) thì về màn "chọn kho" —
		// không gọi máy chủ (Desk gốc: `if (!this.kho) return this.ve();`).
		nap(kho) {
			if (!kho) {
				this.st = this._luong.doi_kho();
				this.ve();
				return Promise.resolve();
			}
			this.page.main.addClass("dohl-dang-nap");
			return this._luong
				.nap(kho)
				.then((st) => {
					this.st = st;
					this.ve();
				})
				.finally(() => this.page.main.removeClass("dohl-dang-nap"));
		}

		nap_lai() {
			if (!this.st.kho) return;
			return this.nap(this.st.kho);
		}

		ve() {
			const e = frappe.utils.escape_html;
			const $b = this.$goc.find(".dohl-bang");
			const $mo = this.$goc.find(".dohl-mo-dau");
			// `cau_dau` là câu CỦA LUỒNG (rule 2) — bốn nhánh cũ ("chọn kho"/"chưa
			// kho nào"/"xong hết"/"còn N lô") đọc thẳng từ đó, trang không tự suy.
			// Tô đậm `**…**` của luồng đổi thành `<b>` Ở ĐÂY (đúng khuôn `_dam()` của
			// PDA — escape trước, đổi dấu sau — nhưng Desk chưa từng cần `_e()` cho
			// việc này vì `__()` bọc chuỗi ĐÃ escape sẵn; đơn giản hoá bằng cách bỏ
			// `**` cho các câu chỉ hiện trên Desk, giữ nguyên số liệu động).
			const cau_dau_desk = (this.st.cau_dau || "").replace(/\*\*/g, "");
			if (!this.st.kho_ds.length || !this.st.kho) {
				$mo.text(cau_dau_desk);
				$b.empty();
				return this.cap_nhat_nut();
			}
			if (this.st.trong) {
				$mo.html(`<div class="dohl-xong">${e(cau_dau_desk)}</div>`);
				$b.empty();
				return this.cap_nhat_nut();
			}
			$mo.text(cau_dau_desk);
			$b.html(`
				<table class="table table-bordered dohl-bang-lo">
					<thead>
						<tr>
							<th style="width: 34px"><input type="checkbox" class="dohl-chon-het" ${
								this.st.dong.every((d) => d.chon) ? "checked" : ""
							}></th>
							<th>${__("Số lô")}</th>
							<th>${__("Mặt hàng")}</th>
							<th class="text-right">${__("Tồn")}</th>
							<th>${__("Đang ở ô")}</th>
							<th style="width: 260px">${__("Ô trên tem")}</th>
						</tr>
					</thead>
					<tbody></tbody>
				</table>`);
			const $tb = $b.find("tbody");
			this.st.dong.forEach((d, i) => {
				const $tr = $(`
					<tr data-lo="${e(d.so_lo)}">
						<td><input type="checkbox" class="dohl-chon" data-lo="${e(d.so_lo)}" ${d.chon ? "checked" : ""}></td>
						<td><b>${e(d.so_lo)}</b>${
					d.hsd ? `<div class="dohl-mo">HSD ${e(frappe.datetime.str_to_user(d.hsd))}</div>` : ""
				}</td>
						<td>${e(d.ten_hang || "")}<div class="dohl-mo">${e(d.vat_tu)}</div></td>
						<td class="text-right">${format_number(d.ton, null, 3)}</td>
						<td>${e(d.dang_o || "")}</td>
						<td class="dohl-o"></td>
					</tr>`).appendTo($tb);
				if (d.loi_dat) {
					$(`<div class="dohl-mo text-danger">${e(d.loi_dat)}</div>`).appendTo($tr.find("td").eq(1));
				}
				// Một Link control THẬT cho mỗi dòng: gõ mã ô là có gợi ý, và mã sai
				// bị chặn ngay trên màn hình thay vì đợi máy chủ trả lỗi cả loạt.
				const control = frappe.ui.form.make_control({
					df: {
						fieldtype: "Link",
						options: "Storage Location",
						fieldname: `o_${i}`,
						placeholder: d.ly_do || __("Chọn ô"),
						get_query: () => ({
							filters: { kho: this.st.kho, is_group: 0, la_o_chua_xep: 0, disabled: 0 },
						}),
						change: () => {
							this._luong.dat_o_cho_dong(d.so_lo, control.get_value() || "");
							this._dong_bo();
							// Cập nhật TẠI CHỖ, không vẽ lại cả bảng — vẽ lại xoá mất mọi
							// Link control khác đang mở/đã gõ dở (cùng lẽ Desk gốc: hàm này
							// vốn không gọi `ve()` lại, chỉ đụng đúng ô kiểm của dòng mình).
							const d2 = this.st.dong.find((x) => x.so_lo === d.so_lo);
							if (d2 && d2.chon) $tr.find(".dohl-chon").prop("checked", true);
							this.cap_nhat_nut();
						},
					},
					parent: $tr.find(".dohl-o"),
					render_input: true,
				});
				control.set_value(d.o || "");
				control.$wrapper.find(".control-label, .help-box").remove();
			});
			this.cap_nhat_nut();
		}

		cap_nhat_nut() {
			// `nhan_nut_dat`/`canh_bao_thieu_o`/`dat_duoc` đều là kết luận CỦA LUỒNG
			// (rule 2) — trang không tự đếm `dang_chon()` để lắp câu nữa (khác Desk
			// gốc: hàm này TỪNG tự đọc DOM (`.dohl-chon:checked`) để đếm và tự gõ
			// câu "Đặt ô cho {0} dòng ĐÃ CHỌN"/"{0} dòng đã chọn chưa có ô…" — hai
			// việc đó nay là việc của luồng, dùng NGUYÊN VĂN cùng câu mà bản app
			// hiện, đúng phép thử người soát mô tả ở Bước 2 của khuôn).
			this.page.set_primary_action(this.st.nhan_nut_dat, () => this.dat());
			this.page.btn_primary.prop("disabled", !this.st.dat_duoc);
			this.$goc.find(".dohl-thieu-o").remove();
			if (this.st.canh_bao_thieu_o) {
				$(`<div class="dohl-thieu-o text-danger">${frappe.utils.escape_html(this.st.canh_bao_thieu_o)}</div>`).appendTo(
					this.$goc.find(".dohl-mo-dau")
				);
			}
		}

		// Hỏi lại máy chủ (`hoi_dat()` tự `nap()` lại) rồi mới hỏi người dùng rồi mới
		// ghi — cùng đường với `man_dat_o.js`. `hoi_dat()` nạp lại nên `this.st` ở đây
		// đã CŨ so với luồng: `_dong_bo()` + `ve()` ngay khi nó trả về, không thì bảng
		// trên màn (và các hộp kiểm trong đó) nói khác luồng.
		//
		// KHÔNG CÓ HỘP XÁC NHẬN — và đó là một quyết định, không phải một thiếu sót.
		// Vòng sửa 1 có cắm một `frappe.confirm` mang câu `h.cau` của luồng vào giữa;
		// soát xét tổng lần 2 (MỚI-1) đo được nó ĐẺ RA một lỗi mới: `.finally()` chạy
		// ngay khi hộp VỪA HIỆN chứ không phải khi được trả lời, nên nút chính bật
		// lại trong lúc hộp còn mở — bấm hai lần ra HAI hộp chồng nhau, đồng ý cả hai
		// thì `dat()` chạy HAI LẦN. Máy chủ từ chối lượt sau nên dữ liệu không hỏng,
		// nhưng thủ kho nhận câu đỏ "lô đã có ô trên tem (người khác vừa đặt)" —
		// NÓI SAI SỰ THẬT, "người khác" chính là cú bấm thứ hai của họ.
		//
		// Bỏ hẳn hộp, giữ nguyên phần BẮT BUỘC: `hoi_dat()` vẫn nạp lại từ máy chủ
		// trước khi ghi (ràng buộc riêng của màn có GHI — chuyện ĐÚNG SỐ LIỆU, không
		// phải chuyện có hộp thoại hay không). Và Desk gốc chưa từng đòi cú bấm thêm
		// đó, nên bỏ nó cũng là trả trang về đúng số thao tác cũ.
		//
		// Nút chính tắt SUỐT cả lượt (`dat()` tắt, `.finally()` bật lại sau khi ghi
		// xong) — nay không còn hộp thoại chen giữa nên không còn khoảng hở nào để
		// một cú bấm thứ hai lọt vào.
		dat() {
			if (!this.st.dat_duoc) return;
			this.page.btn_primary.prop("disabled", true);
			return this._luong
				.hoi_dat()
				.then((h) => {
					this._dong_bo();
					if (!h.ok) {
						// `h.bao` là câu CỦA LUỒNG — không còn dòng nào đặt được sau khi nạp
						// lại (người khác vừa đặt mất, lần này là "người khác" THẬT). Vẽ lại
						// cho khớp số liệu vừa nạp, rồi dừng: không ghi gì.
						this.ve();
						if (h.bao) frappe.show_alert({ message: h.bao, indicator: "orange" });
						return;
					}
					// KHÔNG `ve()` ở nhánh này: `_ghi_that()` vẽ lại ngay sau khi ghi xong.
					// Vẽ thêm một lượt ở đây chỉ để bật lại nút chính giữa chừng — đúng cái
					// khoảng hở mà MỚI-1 chui qua.
					return this._ghi_that();
				})
				.finally(() => this.cap_nhat_nut());
		}

		_ghi_that() {
			this.page.btn_primary.prop("disabled", true);
			return this._luong
				.dat()
				.then((kq) => {
					this._dong_bo();
					this.ve();
					// `kq.tieu_de_loi`/`kq.tieu_de_thanh_cong` là câu CỦA LUỒNG (rule 2) —
					// `dat()` tự trả sẵn (MỘT nơi, dùng chung với dải báo của app). Trước
					// bản sửa này (soát xét sau Playwright, brief Task 5), trang tự gõ lại
					// đúng hai câu đó — đúng loại nợ "lặp câu ở nhiều nơi" mà soát xét
					// Task 2 (P4) đã chỉ ra, và lọt qua phép thử bọc `tao()` cho luồng trả
					// câu giả (một hàm nằm NGOÀI những gì `tao()` trả không bị phép thử
					// đó chạm tới).
					if (kq.loi.length) {
						frappe.msgprint({
							title: kq.tieu_de_loi,
							indicator: "red",
							message:
								"<ul>" +
								kq.loi
									.map(
										(x) =>
											`<li><b>${frappe.utils.escape_html(x.so_lo)}</b>: ${frappe.utils.escape_html(
												x.ly_do
											)}</li>`
									)
									.join("") +
								"</ul>",
						});
					}
					if (kq.da_dat.length) this.hoi_in(kq.da_dat, kq.tieu_de_thanh_cong);
				})
				.finally(() => this.cap_nhat_nut());
		}

		hoi_in(xong, tieu_de) {
			const d = new frappe.ui.Dialog({
				title: tieu_de || __("Đã đặt ô cho {0} lô", [xong.length]),
				fields: [
					{
						fieldtype: "HTML",
						options: `<p>${__(
							"Tem cũ trên thùng chưa có ô này. In tem mới và dán lên thùng, nếu không thủ kho vẫn không biết xếp vào đâu."
						)}</p><ul>${xong
							.map(
								(x) =>
									`<li>${frappe.utils.escape_html(x.so_lo)} → <b>${frappe.utils.escape_html(
										x.ma_in_nhan || x.o
									)}</b></li>`
							)
							.join("")}</ul>`,
					},
				],
				primary_action_label: __("In tem {0} lô", [xong.length]),
				primary_action: () => {
					d.hide();
					frappe.require(DUONG_IN_NHAN, () => {
						erpnext.warehouse_operations.in_nhan.in_cho_cac_lo(xong.map((x) => x.so_lo));
					});
				},
				secondary_action_label: __("Để sau"),
				secondary_action: () => d.hide(),
			});
			d.show();
		}
	}
})();
