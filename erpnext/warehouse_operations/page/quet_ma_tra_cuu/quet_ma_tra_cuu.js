// Trang "Quét mã tra cứu" — dùng trên PDA cầm tay của thủ kho.
//
// VÌ SAO LÀ MỘT TRANG RIÊNG: chủ đầu tư, 17/09/2026 — "anh muốn quét mã tra cứu
// là chức năng riêng và ở trong workspace vị trí kho … màn đấy sẽ hiển thị cho
// màn hình pda". Trước đó khung quét nằm nhúng trong form `Batch Entry`, tức là
// muốn tra một thùng hàng phải mở một phiếu nhập lô bất kỳ trước.
//
// Máy chủ: `erpnext.warehouse_operations.vitri.quet.tra_cuu` — quét gì cũng trả một dict
// có khoá `loai` ("lo" / "vat_tu" / "kho" / "o" / null). Rẽ nhánh THEO KHOÁ ĐÓ,
// không dò chữ trong chuỗi hiển thị (xem docstring `quet.py`).
//
// Ô quét (giữ focus, tắt bàn phím ảo, tự gửi khi súng quét không có Enter) là
// thành phần dùng chung `public/js/warehouse_operations/o_quet.js` — xem lý do ở đó.
//
// PHẦN QUYẾT ĐỊNH ("quét mã này ra cái gì") không còn nằm ở đây (Task 2, Bước 6
// của kế hoạch app PDA `/kho`): đã chuyển sang `luong/tra_cuu.js` — CÙNG một file
// mà màn "Tra cứu" của app PDA (`kho_pda/man_tra_cuu.js`) dùng, để hai nơi không
// lệch luật. File này chỉ còn giữ TOÀN BỘ phần VẼ nguyên vẹn.
//
// VÒNG SỬA 1 (soát xét `task-2-soat-xet.md`): bản đầu tự ý LẬT NGƯỢC phán quyết
// của lớp luồng (`const d = kq.du_lieu || {loai:null}` vứt cả `kq.loai`/`kq.bao`),
// và còn giữ RIÊNG ba bản luật lẽ ra phải dùng chung — nhãn hiển thị của `loai`,
// chính sách lịch sử, ngưỡng cận date. Cả bốn đã chuyển hẳn vào `luong/tra_cuu.js`;
// phần vẽ dưới đây chỉ còn ĐỌC (`kq.loai`, `kq.bao`, `this._luong.lich_su()`,
// `nhan_loai()`/`trang_thai_han()` uỷ quyền sang lớp luồng), không tự suy lại.

// Bọc IIFE: script trang Frappe chạy ở phạm vi TOÀN CỤC. Hằng `const` và các hàm
// nhỏ (`e`, `so`, `ngay`…) của hai trang PDA mà để trần thì mở trang thứ hai
// trong cùng phiên sẽ nổ "Identifier has already been declared".
(function () {
	frappe.pages["quet-ma-tra-cuu"].on_page_load = function (wrapper) {
		const page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Quét mã tra cứu"),
			single_column: true,
		});
		// Nạp lớp LUỒNG trước — brief đòi tường minh ("nạp file luồng ... trước khi
		// dựng trang"), và constructor bên dưới gọi
		// `erpnext.warehouse_operations.luong.tra_cuu.tao(...)` ngay lập tức nên
		// namespace đó phải tồn tại trước khi `new QuetMaTraCuu(page)` chạy.
		frappe.require(LUONG_TRA_CUU, () => {
			frappe.require(O_QUET, () => {
				wrapper.quet_ma = new erpnext.warehouse_operations.QuetMaTraCuu(page);
			});
		});
	};

	frappe.pages["quet-ma-tra-cuu"].on_page_show = function (wrapper) {
		wrapper.quet_ma && wrapper.quet_ma.giu_focus();
	};

	frappe.provide("erpnext.warehouse_operations");

	const O_QUET = ["/assets/erpnext/js/warehouse_operations/o_quet.js", "/assets/erpnext/js/warehouse_operations/o_quet.css"];
	const LUONG_TRA_CUU = "/assets/erpnext/js/warehouse_operations/luong/tra_cuu.js";
	// THỂ HIỆN luồng của trang đang mở. Cần ở cấp module vì các hàm dựng HTML bên
	// dưới (`the_lo`, `dong_hang`, `ve_lich_su`...) là hàm cấp module, không có
	// `this` — mà `trang_thai_han` nay là PHƯƠNG THỨC của thể hiện (nó đọc ngày
	// TIÊM VÀO, xem `luong/tra_cuu.js`). Gán trong constructor; chỉ có đúng một
	// trang "Quét mã tra cứu" mở tại một thời điểm.
	let _luong_cua_trang = null;
	// Ngưỡng "cận date" + `SO_LAN_QUET_NHO` (trần lịch sử) đã CHUYỂN vào lớp luồng
	// (vòng sửa 1, mục 3 và 5) — không còn hằng số nào ở đây để đọc lệch với app.

	erpnext.warehouse_operations.QuetMaTraCuu = class QuetMaTraCuu {
		constructor(page) {
			this.page = page;
			// KHÔNG còn `this.lich_su` riêng — vòng sửa 1 (mục 3) hợp nhất chính sách
			// lịch sử vào lớp luồng; `ve_lich_su()` đọc thẳng `this._luong.lich_su()`.
			// Số thứ tự lần quét: quét dồn hai mã liền nhau thì câu trả lời của mã
			// TRƯỚC có thể về SAU — không có số này thì màn hình hiện nhầm mã cũ.
			this.lan = 0;
			// Phần QUYẾT ĐỊNH ("quét mã này ra cái gì") — CÙNG một luồng mà màn "Tra
			// cứu" của app PDA dùng (xem đầu file). `goi: frappe.xcall` đúng nguyên
			// văn Bước 6 của brief: `frappe.xcall` đã tự hiện câu báo máy chủ cho lỗi
			// quyền/mất mạng (Desk có `frappe.app`, khác app PDA — xem `kho_pda/vo.js`
			// vì sao đường đó KHÔNG dùng được ở đấy), nên trang này không cần tự bắt
			// lại hai ca đó, y như trước khi tách lớp.
			//
			// `gio` (vòng sửa 2, M4): TRƯỚC khi gộp lớp (trước Task 2), trang này ghi
			// giờ vào lịch sử bằng `frappe.datetime.now_time()` — GIỜ SITE, không phải
			// giờ trình duyệt. Lớp luồng mặc định giờ MÁY TRẠM (đúng cho app, chạy
			// ngay trên máy quét trong kho) — không tiêm lại đúng giờ site ở đây thì
			// một máy tính văn phòng lệch múi giờ với server sẽ thấy dấu giờ trong
			// lịch sử Desk ĐỔI NGHĨA mà không ai biết (cùng múi giờ thì im lặng khớp,
			// không lộ ra khác biệt).
			//
			// `ngay` (soát xét tổng, M2): CÙNG lý do với `gio`, nhưng đắt hơn nhiều —
			// đây là ngày dùng để phán "lô hết hạn / cận date / còn hạn". Trước khi
			// gộp lớp trang này tính bằng `frappe.datetime.get_day_diff(hsd,
			// frappe.datetime.get_today())`, tức MÚI GIỜ SITE; bản gộp lớp đầu tiên
			// lỡ để lớp luồng gọi thẳng `new Date()` (múi giờ MÁY). Tiêm lại ngày
			// site ở đây để giữ đúng nghĩa CŨ.
			this._luong = erpnext.warehouse_operations.luong.tra_cuu.tao({
				goi: frappe.xcall,
				gio: () => frappe.datetime.now_time(),
				ngay: () => frappe.datetime.get_today(),
			});
			_luong_cua_trang = this._luong;
			this.dung();
		}

		dung() {
			this.$goc = $(`
				<div class="qmtc">
					<div class="qmtc-cho-o-quet"></div>
					<div class="qmtc-ket-qua"></div>
					<div class="qmtc-lich-su"></div>
				</div>
			`).appendTo(this.page.main);

			this.$ket_qua = this.$goc.find(".qmtc-ket-qua");
			this.$lich_su = this.$goc.find(".qmtc-lich-su");
			this.o_quet = new erpnext.warehouse_operations.OQuet({
				cha: this.$goc.find(".qmtc-cho-o-quet"),
				vung: this.$goc,
				placeholder: __("Quét tem lô, tem vị trí…"),
				goi_y: __("Bấm nút quét trên PDA và chiếu vào tem"),
				khi_quet: (ma) => this.tra_cuu(ma),
			});

			this.$lich_su.on("click", ".qmtc-dong-lich-su", (ev) => {
				this.tra_cuu(String($(ev.currentTarget).attr("data-ma")));
			});

			this.ve_cho();
			this.giu_focus();
		}

		giu_focus() {
			this.o_quet.giu_focus();
		}

		tra_cuu(ma) {
			const lan = ++this.lan;
			this.ve_dang_tra(ma);
			// Đang cuộn xuống cuối danh sách lô của lần quét trước mà bóp cò quét
			// tiếp thì kết quả mới phải hiện ngay trước mắt, không nằm khuất phía trên.
			window.scrollTo({ top: 0 });
			this._luong
				.quet(ma)
				.then((kq) => {
					if (lan !== this.lan) return;
					// `kq.loai`/`kq.bao` là phán quyết CỦA LỚP LUỒNG — nguồn sự thật DUY
					// NHẤT (vòng sửa 1, mục 1: bản trước tự suy lại mọi thứ từ
					// `kq.du_lieu`, im lặng vứt cả hai — đo được: ép lớp luồng trả
					// `loai:"khong_ro"` + một câu báo tuỳ ý trong khi vẫn giữ `du_lieu`
					// của một lô THẬT, trang vẫn vẽ thẻ "Lô" đầy đủ như không có chuyện
					// gì). `ve_ket_qua`/`ve_lich_su` bên dưới đọc thẳng `kq`, không tự
					// suy `loai` từ `du_lieu` nữa. Lịch sử cũng không còn `this.nho(...)`
					// riêng — `this._luong.quet()` đã tự ghi vào bộ nhớ DÙNG CHUNG.
					this.ve_ket_qua(ma, kq);
					this.ve_lich_su();
					rung(kq.loai !== "khong_ro" ? [40] : [80, 60, 80]);
				})
				.catch(() => {
					// Lỗi quyền / mất mạng: `frappe.xcall` đã tự hiện câu báo của máy
					// chủ. Chỉ gỡ khung "đang tra" để màn hình không treo mãi.
					if (lan === this.lan) this.ve_cho();
				})
				.finally(() => {
					if (lan === this.lan) this.giu_focus();
				});
		}

		// ----------------------------------------------------------------- vẽ

		ve_cho() {
			this.$ket_qua.html(`
				<div class="qmtc-the qmtc-cho">
					<div class="qmtc-cho-hinh">${frappe.utils.icon("scan", "xl")}</div>
					<div class="qmtc-cho-chu">${__("Sẵn sàng quét")}</div>
					<div class="qmtc-mo">${__("Tem lô · tem vị trí · mã vật tư · mã kho")}</div>
				</div>`);
		}

		ve_dang_tra(ma) {
			this.$ket_qua.html(`
				<div class="qmtc-the qmtc-dang-tra">
					<div class="qmtc-ma-to">${e(ma)}</div>
					<div class="qmtc-mo">${__("Đang tra cứu…")}</div>
					<div class="qmtc-thanh-cho"></div>
				</div>`);
		}

		// `kq` = phán quyết nguyên vẹn của lớp luồng (`{loai, du_lieu, bao}`). Ca
		// THƯỜNG NGÀY (`kq.loai` không nhận diện được) tự có `kq.bao` làm tiêu đề
		// thẻ "không nhận ra" — không lặp một dải cảnh báo thứ hai. Dải
		// `.qmtc-canh-bao` CHỈ hiện khi lớp luồng gắn `bao` đi kèm một `loai` ĐÃ
		// nhận diện được (vòng sửa 1, mục 1 — ca không xảy ra hôm nay ở Tra cứu,
		// nhưng phán quyết đó KHÔNG ĐƯỢC im lặng biến mất nếu một ngày lớp luồng
		// bắt đầu gắn thêm cảnh báo cho dữ liệu đã biết, ví dụ "lô sắp hết hạn").
		ve_ket_qua(ma, kq) {
			const ve = { lo: the_lo, vat_tu: the_vat_tu, o: the_o, kho: the_kho }[kq.loai];
			if (ve) {
				const canh_bao = kq.bao ? `<div class="qmtc-canh-bao">${e(kq.bao)}</div>` : "";
				this.$ket_qua.html(canh_bao + ve(kq.du_lieu));
			} else {
				this.$ket_qua.html(the_khong_thay(ma, kq.bao));
			}
		}

		ve_lich_su() {
			const ds = this._luong.lich_su();
			if (!ds.length) return this.$lich_su.empty();
			this.$lich_su.html(`
				<div class="qmtc-tieu-de-muc">${__("Vừa quét")}</div>
				${ds
					.map((x) => {
						const khong_thay = x.loai === "khong_ro";
						const ten = x.du_lieu ? tieu_de_ngan(x.du_lieu) : "";
						return `
					<div class="qmtc-dong-lich-su ${khong_thay ? "khong-thay" : ""}" data-ma="${e(x.ma)}" role="button">
						<span class="qmtc-nhan-loai loai-${khong_thay ? "khong" : x.loai}">${nhan_loai(x.loai)}</span>
						<span class="qmtc-lich-su-chu">
							<span class="qmtc-lich-su-ma">${e(x.ma)}</span>
							${ten ? `<span class="qmtc-lich-su-ten">${e(ten)}</span>` : ""}
						</span>
						<span class="qmtc-lich-su-luc">${e(x.luc.slice(0, 5))}</span>
					</div>`;
					})
					.join("")}`);
		}
	};

	// ------------------------------------------------------------------- thẻ

	function the_lo(d) {
		const han = trang_thai_han(d.hsd);
		const ton = d.ton_theo_o || [];
		const tong = ton.reduce((t, x) => t + flt(x.so_luong), 0);
		return `
			<div class="qmtc-the qmtc-the-lo muc-${han.muc}">
				<div class="qmtc-dau">
					<span class="qmtc-nhan-loai loai-lo">${nhan_loai("lo")}</span>
					<a class="qmtc-ma-to" href="${lien_ket("batch", d.so_lo)}">${e(d.so_lo)}</a>
					<div class="qmtc-ten-hang">${e(d.ten_hang || d.vat_tu)}</div>
					<div class="qmtc-mo">${e(d.vat_tu)}${d.don_vi ? " · " + e(d.don_vi) : ""}</div>
				</div>

				<div class="qmtc-han muc-${han.muc}">
					<div>
						<div class="qmtc-nhan">${__("Hạn dùng")}</div>
						<div class="qmtc-han-ngay">${d.hsd ? e(ngay(d.hsd)) : __("Không có")}</div>
					</div>
					${han.chu ? `<span class="qmtc-han-con">${e(han.chu)}</span>` : ""}
				</div>

				<div class="qmtc-luoi">
					${o_luoi(__("Ngày SX"), d.ngay_san_xuat && ngay(d.ngay_san_xuat))}
					${o_luoi(__("Ngày nhập"), d.ngay_nhap && ngay(d.ngay_nhap))}
					${o_luoi(__("Số gói"), d.so_goi)}
					${o_luoi(
						__("Phiếu nhập"),
						d.so_phieu_nhap &&
							`<a href="${lien_ket("purchase-receipt", d.so_phieu_nhap)}">${e(d.so_phieu_nhap)}</a>`,
						true
					)}
					${o_luoi(__("Nhà cung cấp"), d.nha_cung_cap, false, true)}
				</div>

				<div class="qmtc-muc">
					<div class="qmtc-tieu-de-muc">${__("Vị trí")}</div>
					<div class="qmtc-chip-hang">
						${chip(__("Cố định"), d.vi_tri_co_dinh, "storage-location")}
						${chip(__("Tem in"), d.o_in_tem, "storage-location")}
					</div>
					${
						ton.length
							? `<div class="qmtc-bang">
								${ton
									.map(
										(x) => `
									<div class="qmtc-dong">
										<a class="qmtc-dong-chinh qmtc-ma-o" href="${lien_ket("storage-location", x.o)}">${e(
											x.o
										)}</a>
										<span class="qmtc-so">${so(x.so_luong)}${don_vi(d.don_vi)}</span>
									</div>`
									)
									.join("")}
								${
									ton.length > 1
										? `<div class="qmtc-dong qmtc-tong"><span class="qmtc-dong-chinh">${__(
												"Tổng"
										  )}</span><span class="qmtc-so">${so(tong)}${don_vi(d.don_vi)}</span></div>`
										: ""
								}
							</div>`
							: `<div class="qmtc-trong">${__("Lô này chưa xếp vào ô nào")}</div>`
					}
				</div>
			</div>`;
	}

	function the_vat_tu(d) {
		const lo = d.lo_con_ton || [];
		const tong = lo.reduce((t, x) => t + flt(x.so_luong), 0);
		return `
			<div class="qmtc-the qmtc-the-vat-tu">
				<div class="qmtc-dau">
					<span class="qmtc-nhan-loai loai-vat_tu">${nhan_loai("vat_tu")}</span>
					<div class="qmtc-ten-hang qmtc-ten-to">${e(d.ten_hang || d.vat_tu)}</div>
					<div class="qmtc-mo"><a href="${lien_ket("item", d.vat_tu)}">${e(d.vat_tu)}</a>${
			d.don_vi ? " · " + e(d.don_vi) : ""
		}</div>
				</div>
				<div class="qmtc-muc">
					<div class="qmtc-chip-hang">
						${chip(__("Vị trí cố định"), d.vi_tri_co_dinh, "storage-location", __("Chưa gán"))}
					</div>
				</div>
				<div class="qmtc-muc">
					<div class="qmtc-tieu-de-muc">
						${d.co_lo ? __("Lô còn tồn · hạn gần trước") : __("Tồn theo ô")}
						${lo.length ? `<span class="qmtc-tong-nho">${so(tong)} ${e(d.don_vi || "")}</span>` : ""}
					</div>
					${
						lo.length
							? `<div class="qmtc-bang">${lo
									.map((x) => dong_hang({ ...x, don_vi: d.don_vi }, { hien_lo: d.co_lo }))
									.join("")}</div>`
							: `<div class="qmtc-trong">${__("Không còn tồn ở ô nào")}</div>`
					}
				</div>
			</div>`;
	}

	function the_o(d) {
		const hang = d.hang_trong_o || [];
		const nhan = [
			d.la_nhom ? `<span class="qmtc-co">${__("Nhóm ô")}</span>` : "",
			d.ngung_dung ? `<span class="qmtc-co co-do">${__("Ngừng dùng")}</span>` : "",
			d.loai_vi_tri ? `<span class="qmtc-co">${e(d.loai_vi_tri)}</span>` : "",
		].join("");
		const mh = d.mat_hang_co_dinh;
		return `
			<div class="qmtc-the qmtc-the-o">
				<div class="qmtc-dau">
					<span class="qmtc-nhan-loai loai-o">${nhan_loai("o")}</span>
					<a class="qmtc-ma-to" href="${lien_ket("storage-location", d.ma_o)}">${e(d.ma_in_nhan || d.ma_o)}</a>
					<div class="qmtc-mo">${e(d.kho)}${d.ten_o ? " · " + e(d.ten_o) : ""}</div>
					${nhan ? `<div class="qmtc-co-hang">${nhan}</div>` : ""}
				</div>
				<div class="qmtc-muc">
					<div class="qmtc-tieu-de-muc">${__("Mặt hàng cố định")}</div>
					${
						mh
							? `<a class="qmtc-hop-hang" href="${lien_ket("item", mh.vat_tu)}">
								<span class="qmtc-ten-hang">${e(mh.ten_hang || mh.vat_tu)}</span>
								<span class="qmtc-mo">${e(mh.vat_tu)} · ${__("gán ở {0}", [e(mh.vi_tri)])}</span>
							</a>`
							: `<div class="qmtc-trong">${__("Chưa mặt hàng nào giữ vị trí này")}</div>`
					}
				</div>
				<div class="qmtc-muc">
					<div class="qmtc-tieu-de-muc">${__("Đang chứa")}</div>
					${
						hang.length
							? `<div class="qmtc-bang">${hang
									.map((x) => dong_hang(x, { hien_ten: true, hien_lo: !!x.so_lo, hien_o: d.la_nhom }))
									.join("")}</div>
							${
								d.so_dong_hang > hang.length
									? `<div class="qmtc-trong">${__("… và {0} dòng nữa — xem báo cáo Tồn kho theo vị trí", [
											d.so_dong_hang - hang.length,
									  ])}</div>`
									: ""
							}`
							: `<div class="qmtc-trong">${__("Ô trống")}</div>`
					}
				</div>
			</div>`;
	}

	function the_kho(d) {
		return `
			<div class="qmtc-the qmtc-the-kho">
				<div class="qmtc-dau">
					<span class="qmtc-nhan-loai loai-kho">${nhan_loai("kho")}</span>
					<a class="qmtc-ten-hang qmtc-ten-to" href="${lien_ket("warehouse", d.kho)}">${e(d.ten_kho || d.kho)}</a>
					${d.ten_kho && d.ten_kho !== d.kho ? `<div class="qmtc-mo">${e(d.kho)}</div>` : ""}
					<div class="qmtc-co-hang">
						${
							d.quan_ly_vi_tri
								? `<span class="qmtc-co co-xanh">${__("Đang quản lý vị trí")}</span>`
								: `<span class="qmtc-co">${__("Chưa bật quản lý vị trí")}</span>`
						}
					</div>
				</div>
				${
					d.quan_ly_vi_tri
						? `<div class="qmtc-thong-ke">
							<div><div class="qmtc-so-to">${so(d.so_o)}</div><div class="qmtc-nhan">${__("ô đang dùng")}</div></div>
							<div><div class="qmtc-so-to">${so(d.so_o_co_hang)}</div><div class="qmtc-nhan">${__(
								"ô có hàng"
						  )}</div></div>
						</div>`
						: ""
				}
			</div>`;
	}

	// `bao` là câu của LỚP LUỒNG (vòng sửa 1, mục 1/2) — hiện ĐÚNG chuỗi đó, không
	// tự chép lại "Không nhận ra mã này" ở đây nữa (soát xét, P4: chuỗi đó từng nằm
	// ở BA nơi). Phòng hờ `bao` rỗng (gọi `the_khong_thay` từ một đường nào khác
	// không đi qua lớp luồng) mới rơi về câu MẶC ĐỊNH.
	//
	// VÒNG SỬA 2 (soát xét, M5): hai câu dưới đây gõ NGUYÊN VĂN bằng `__("...")`,
	// KHÔNG đọc qua `erpnext.warehouse_operations.luong.tra_cuu.CAU_KHONG_RO`/
	// `MO_TA_KHONG_RO` như vòng trước — `__(<biến>)` chạy đúng lúc thi hành (biến
	// đó vẫn giữ đúng chữ), nhưng bộ rút chuỗi dịch của Frappe chỉ nhận diện được
	// `__(` đi NGAY SAU bởi một chuỗi chữ, không lần theo được giá trị của một
	// biến — hai câu này sẽ biến mất khỏi catalog dịch, không ai biết. Cái giá:
	// chữ NGUYÊN VĂN nay có ở ba nơi (hằng số trong lớp luồng + hai lớp vẽ) thay
	// vì một — đổi lại để công cụ dịch nhìn thấy được câu, đúng đánh đổi người
	// soát chọn. Hằng số trong lớp luồng vẫn là NGUỒN Ý NGHĨA (đổi câu thì sửa ở
	// đó trước, hai chỗ `__("...")` dưới đây phải tự tay khớp lại theo).
	function the_khong_thay(ma, bao) {
		return `
			<div class="qmtc-the qmtc-khong-thay">
				<div class="qmtc-cho-hinh">${frappe.utils.icon("search", "xl")}</div>
				<div class="qmtc-cho-chu">${e(bao || __("Không nhận ra mã này."))}</div>
				<div class="qmtc-ma-to">${e(ma)}</div>
				<div class="qmtc-mo">${__(
					"Không phải tem lô, tem vị trí, mã vật tư hay mã kho. Có thể vừa quét nhầm mã trên vỏ thùng."
				)}</div>
			</div>`;
	}

	// ---------------------------------------------------------------- mẩu nhỏ

	function dong_hang(x, { hien_ten = false, hien_lo = false, hien_o = true } = {}) {
		const han = trang_thai_han(x.hsd);
		return `
			<div class="qmtc-dong qmtc-dong-hang">
				<div class="qmtc-dong-chinh">
					${hien_ten ? `<div class="qmtc-dong-ten">${e(x.ten_hang || x.vat_tu)}</div>` : ""}
					${hien_lo ? `<div class="qmtc-dong-lo">${e(x.so_lo)}</div>` : ""}
					<div class="qmtc-dong-phu">
						${hien_o ? `<span class="qmtc-ma-o">${e(x.o)}</span>` : ""}
						${x.hsd ? `<span class="qmtc-han-nho muc-${han.muc}">HSD ${e(ngay(x.hsd))}</span>` : ""}
					</div>
				</div>
				<span class="qmtc-so">${so(x.so_luong)}${don_vi(x.don_vi)}</span>
			</div>`;
	}

	function don_vi(dvt) {
		return dvt ? ` <small>${e(dvt)}</small>` : "";
	}

	function o_luoi(nhan, gia_tri, la_html = false, rong = false) {
		if (gia_tri === undefined || gia_tri === null || gia_tri === "") return "";
		return `<div class="qmtc-o-luoi ${rong ? "rong" : ""}">
			<div class="qmtc-nhan">${e(nhan)}</div>
			<div class="qmtc-gia-tri">${la_html ? gia_tri : e(gia_tri)}</div>
		</div>`;
	}

	function chip(nhan, gia_tri, duong, khi_trong) {
		if (!gia_tri && !khi_trong) return "";
		const than = gia_tri
			? `<a href="${lien_ket(duong, gia_tri)}" class="qmtc-chip-gia-tri">${e(gia_tri)}</a>`
			: `<span class="qmtc-chip-gia-tri trong">${e(khi_trong)}</span>`;
		return `<div class="qmtc-chip"><span class="qmtc-chip-nhan">${e(nhan)}</span>${than}</div>`;
	}

	// `trang_thai_han`/`nhan_loai` UỶ QUYỀN thẳng cho lớp luồng (vòng sửa 1, mục 2
	// và 5) — không còn tính/ánh xạ RIÊNG ở đây nữa. Giữ lại làm HÀM CHUYỂN TIẾP
	// (không đổi tên) để mọi lời gọi cũ trong file này (`the_lo`, `dong_hang`...)
	// không phải sửa — chỉ đổi phần THÂN hàm.
	// Qua THỂ HIỆN, không qua namespace (soát xét tổng, M2): phán quyết hết hạn
	// đọc ngày TIÊM VÀO `tao()` (`ngay: () => frappe.datetime.get_today()` ở
	// constructor) — giờ SITE, đúng như trang này vẫn tính trước khi gộp lớp. Lấy
	// thể hiện qua `_luong_cua_trang` vì các hàm dựng HTML ở file này là hàm cấp
	// module (không có `this`), giữ nguyên tên để không phải sửa hàng chục lời gọi.
	function trang_thai_han(hsd) {
		return _luong_cua_trang.trang_thai_han(hsd);
	}

	function nhan_loai(loai) {
		return erpnext.warehouse_operations.luong.tra_cuu.nhan_loai(loai);
	}

	function tieu_de_ngan(d) {
		if (d.loai === "lo" || d.loai === "vat_tu") return d.ten_hang || d.vat_tu;
		if (d.loai === "o") return d.kho;
		if (d.loai === "kho") return d.ten_kho !== d.kho ? d.ten_kho : "";
		return "";
	}

	function lien_ket(duong, ten) {
		return `/app/${duong}/${encodeURIComponent(ten)}`;
	}

	function ngay(gia_tri) {
		return frappe.datetime.str_to_user(gia_tri);
	}

	function so(gia_tri) {
		return e(flt(gia_tri).toLocaleString("vi-VN", { maximumFractionDigits: 3 }));
	}

	function e(gia_tri) {
		return frappe.utils.escape_html(String(gia_tri));
	}

	function rung(mau) {
		try {
			navigator.vibrate && navigator.vibrate(mau);
		} catch (err) {
			// Trình duyệt chặn rung (chưa có thao tác người dùng) — không sao.
		}
	}
})();
