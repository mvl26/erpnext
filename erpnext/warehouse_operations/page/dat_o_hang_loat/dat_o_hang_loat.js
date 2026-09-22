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
// Trang chạy trên máy tính nên KHÔNG dính bẫy súng quét + `frappe.confirm`
// (xem `xep_hang_pda.js`): ở đây không có ô quét nào.
(function () {
	const API = "erpnext.warehouse_operations.vitri.o_tem.";
	const DUONG_IN_NHAN = "/assets/erpnext/js/warehouse_operations/in_nhan_lo.js";

	frappe.pages["dat-o-hang-loat"].on_page_load = function (wrapper) {
		const page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Đặt ô trên tem hàng loạt"),
			single_column: true,
		});
		wrapper.dat_o = new DatOHangLoat(page);
	};

	frappe.pages["dat-o-hang-loat"].on_page_show = function (wrapper) {
		// Quay lại trang: nạp lại — người khác có thể vừa đặt ô cho vài lô.
		if (wrapper.dat_o && wrapper.dat_o.kho) wrapper.dat_o.nap();
	};

	class DatOHangLoat {
		constructor(page) {
			this.page = page;
			this.dong = [];
			// { số lô: ô đang chọn } — giữ ngoài `this.dong` để nạp lại không mất
			// những ô người dùng vừa sửa tay.
			this.chon = {};
			// { số lô: có tick không } — cũng phải sống qua một lần vẽ lại, vì
			// `ve()` dựng lại toàn bộ bảng.
			this.tick = {};
			// Số thứ tự lần nạp. Kết quả của lần nạp CŨ về sau lần mới thì bỏ —
			// ô Kho của Frappe bắn `change` hai lần (chọn gợi ý, rồi rời ô), và
			// lần nạp đến sau từng vẽ lại bảng, xoá sạch tick người dùng vừa bấm
			// (đo trên erptest 20/09: bấm "chọn tất cả" lần đầu như không ăn).
			this.lan_nap = 0;
			this.dung();
		}

		dung() {
			this.chon_kho = this.page.add_field({
				fieldname: "kho",
				label: __("Kho"),
				fieldtype: "Link",
				options: "Warehouse",
				get_query: () => ({ filters: { custom_quan_ly_vi_tri: 1, is_group: 0, disabled: 0 } }),
				change: () => {
					this.kho = this.chon_kho.get_value();
					this.chon = {};
					this.nap();
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
				const d = this.dong[Number($(ev.currentTarget).attr("data-i"))];
				if (d) this.tick[d.so_lo] = ev.currentTarget.checked;
				this.cap_nhat_nut();
			});
			// `change`, KHÔNG `click`: với hộp kiểm, `click` bắt được cả những cú
			// bấm KHÔNG đổi trạng thái (bấm vào viền ô, bấm lúc trình duyệt đang
			// giữ focus) — đo trên erptest 20/09: lần bấm đầu tiên vào "chọn tất
			// cả" không đổi gì, phải bấm lần hai mới ăn.
			this.$goc.on("change", ".dohl-chon-het", (ev) => {
				const bat = ev.currentTarget.checked;
				this.dong.forEach((d) => (this.tick[d.so_lo] = bat));
				this.$goc.find(".dohl-chon").prop("checked", bat);
				this.cap_nhat_nut();
			});
			this.ve();
		}

		nap() {
			if (!this.kho) return this.ve();
			const lan = ++this.lan_nap;
			this.page.main.addClass("dohl-dang-nap");
			return frappe
				.xcall(API + "lo_chua_co_o", { kho: this.kho })
				.then((ds) => {
					if (lan !== this.lan_nap) return; // lần nạp cũ về muộn — bỏ
					this.dong = ds || [];
					this.ve();
				})
				.finally(() => {
					if (lan === this.lan_nap) this.page.main.removeClass("dohl-dang-nap");
				});
		}

		// Ô đang chọn của một dòng: người dùng đã sửa thì lấy của họ, chưa thì lấy đề xuất.
		o_cua(d) {
			return this.chon[d.so_lo] !== undefined ? this.chon[d.so_lo] : d.o_de_xuat || "";
		}

		// Dòng có tick không: người dùng đã bấm thì theo họ, chưa thì mặc định
		// tick những dòng đã có ô đề xuất.
		co_tick(d) {
			return this.tick[d.so_lo] !== undefined ? this.tick[d.so_lo] : !!this.o_cua(d);
		}

		ve() {
			const e = frappe.utils.escape_html;
			const $b = this.$goc.find(".dohl-bang");
			const $mo = this.$goc.find(".dohl-mo-dau");
			if (!this.kho) {
				$mo.html(__("Chọn kho để xem các lô chưa có ô trên tem."));
				$b.empty();
				return this.cap_nhat_nut();
			}
			if (!this.dong.length) {
				$mo.html(
					`<div class="dohl-xong">${__("Mọi lô đang có tồn ở kho {0} đều đã có ô trên tem.", [
						e(this.kho),
					])}</div>`
				);
				$b.empty();
				return this.cap_nhat_nut();
			}
			$mo.html(
				__(
					"{0} lô đang có tồn mà chưa có ô trên tem — chưa xếp hay chuyển được. Soát ô đề xuất, sửa nếu cần, rồi bấm Đặt ô. Đặt xong nhớ IN TEM và dán lên thùng.",
					[this.dong.length]
				)
			);
			$b.html(`
				<table class="table table-bordered dohl-bang-lo">
					<thead>
						<tr>
							<th style="width: 34px"><input type="checkbox" class="dohl-chon-het" ${
								this.dong.every((d) => this.co_tick(d)) ? "checked" : ""
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
			this.dong.forEach((d, i) => {
				const $tr = $(`
					<tr data-lo="${e(d.so_lo)}">
						<td><input type="checkbox" class="dohl-chon" data-i="${i}" ${this.co_tick(d) ? "checked" : ""}></td>
						<td><b>${e(d.so_lo)}</b>${
					d.hsd ? `<div class="dohl-mo">HSD ${e(frappe.datetime.str_to_user(d.hsd))}</div>` : ""
				}</td>
						<td>${e(d.ten_hang || "")}<div class="dohl-mo">${e(d.vat_tu)}</div></td>
						<td class="text-right">${format_number(d.ton, null, 3)}</td>
						<td>${e(d.dang_o || "")}</td>
						<td class="dohl-o"></td>
					</tr>`).appendTo($tb);
				// Một Link control THẬT cho mỗi dòng: gõ mã ô là có gợi ý, và mã sai
				// bị chặn ngay trên màn hình thay vì đợi máy chủ trả lỗi cả loạt.
				const control = frappe.ui.form.make_control({
					df: {
						fieldtype: "Link",
						options: "Storage Location",
						fieldname: `o_${i}`,
						placeholder: d.ly_do || __("Chọn ô"),
						get_query: () => ({
							filters: { kho: this.kho, is_group: 0, la_o_chua_xep: 0, disabled: 0 },
						}),
						change: () => {
							this.chon[d.so_lo] = control.get_value() || "";
							if (this.chon[d.so_lo] && this.tick[d.so_lo] === undefined) {
								this.tick[d.so_lo] = true;
								$tr.find(".dohl-chon").prop("checked", true);
							}
							this.cap_nhat_nut();
						},
					},
					parent: $tr.find(".dohl-o"),
					render_input: true,
				});
				control.set_value(this.o_cua(d));
				control.$wrapper.find(".control-label, .help-box").remove();
			});
			this.cap_nhat_nut();
		}

		dang_chon() {
			const ds = [];
			this.$goc.find(".dohl-chon:checked").each((_i, el) => {
				const d = this.dong[Number($(el).attr("data-i"))];
				if (d) ds.push({ so_lo: d.so_lo, o: this.o_cua(d) });
			});
			return ds;
		}

		cap_nhat_nut() {
			const ds = this.dang_chon();
			const thieu = ds.filter((x) => !x.o).length;
			this.page.set_primary_action(
				ds.length
					? __("Đặt ô cho {0} dòng đã chọn", [ds.length])
					: __("Đặt ô cho dòng đã chọn"),
				() => this.dat()
			);
			this.page.btn_primary.prop("disabled", !ds.length || !!thieu);
			this.$goc.find(".dohl-thieu-o").remove();
			if (thieu) {
				$(
					`<div class="dohl-thieu-o text-danger">${__("{0} dòng đã chọn chưa có ô — chọn ô hoặc bỏ chọn dòng đó.", [thieu])}</div>`
				).appendTo(this.$goc.find(".dohl-mo-dau"));
			}
		}

		dat() {
			const ds = this.dang_chon().filter((x) => x.o);
			if (!ds.length) return;
			this.page.btn_primary.prop("disabled", true);
			frappe
				.xcall(API + "dat_o_hang_loat", { dong: ds })
				.then((kq) => {
					this.chon = {};
					this.tick = {};
					const xong = kq.xong || [];
					const loi = kq.loi || [];
					if (loi.length) {
						frappe.msgprint({
							title: __("{0} lô không đặt được", [loi.length]),
							indicator: "red",
							message:
								"<ul>" +
								loi
									.map(
										(x) =>
											`<li><b>${frappe.utils.escape_html(x.so_lo)}</b>: ${frappe.utils.escape_html(
												x.loi
											)}</li>`
									)
									.join("") +
								"</ul>",
						});
					}
					return this.nap().then(() => {
						if (xong.length) this.hoi_in(xong);
					});
				})
				.finally(() => this.cap_nhat_nut());
		}

		hoi_in(xong) {
			const d = new frappe.ui.Dialog({
				title: __("Đã đặt ô cho {0} lô", [xong.length]),
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
