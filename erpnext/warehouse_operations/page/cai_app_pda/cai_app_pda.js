// Trang quản trị bản cài app PDA: xem bản đang phát hành, đưa bản mới lên, và
// đường dẫn ngắn để gõ trên máy quét mới.
//
// CHIA HAI TRANG, CỐ Ý: trang NÀY (Desk, chỉ trưởng kho) để ĐƯA BẢN LÊN; còn
// `/tai-app` (website, công khai) để TẢI VỀ. Máy PDA lúc chưa cài app thì chưa có
// phiên đăng nhập nào, nên nếu nút tải nằm trong Desk thì không máy nào tải được —
// đúng cái vòng luẩn quẩn mà cách chia này gỡ ra.
//
// Bản cài để CÔNG KHAI (chủ đầu tư chốt 23/09/2026): ai biết đường dẫn đều tải
// được, và APK có mang địa chỉ máy chủ nội bộ bên trong. Không có mật khẩu/khoá
// nào trong đó. Màn hình nói thẳng điều này thay vì để người dùng tự đoán.

frappe.pages["cai-app-pda"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Cài app PDA"),
		single_column: true,
	});
	wrapper.cai_app = new CaiAppPda(page);
};

frappe.pages["cai-app-pda"].on_page_show = function (wrapper) {
	// Quay lại trang sau khi tải bản mới lên ở tab khác: nạp lại cho khỏi nhìn bản cũ.
	if (wrapper.cai_app) wrapper.cai_app.nap_lai();
};

class CaiAppPda {
	constructor(page) {
		this.page = page;
		this.$goc = $('<div class="cap"></div>').appendTo(page.main);
		this.$goc.on("click", ".cap-tai-len", () => this.tai_len());
		this.$goc.on("click", ".cap-the", () => frappe.set_route("List", "PDA Badge"));
		this.nap_lai();
	}

	nap_lai() {
		frappe.xcall("erpnext.warehouse_operations.vitri.cai_app.ban_cai_moi_nhat").then((ban) => {
			this.ban = ban;
			this.ve();
		});
	}

	/** `frappe.ui.FileUploader` không gắn file vào bản ghi nào — bản cài là tài sản
	 * của cả kho, không thuộc một chứng từ nào. `is_private: 0` là điều kiện để máy
	 * PDA chưa đăng nhập tải được (xem chú thích đầu file). */
	tai_len() {
		new frappe.ui.FileUploader({
			folder: "Home",
			make_attachments_public: true,
			restrictions: { allowed_file_types: [".apk"] },
			on_success: (file) => {
				if (file && file.is_private) {
					// Người dùng bỏ tick "công khai" trong hộp tải lên: file đã nằm trên
					// máy chủ nhưng máy PDA sẽ KHÔNG tải được, mà lỗi đó chỉ lộ ra ở tận
					// ngoài kho. Nói ngay, và nói cách sửa.
					frappe.msgprint({
						title: __("Bản cài đang để riêng tư"),
						indicator: "red",
						message: __(
							"File vừa tải lên không công khai nên máy PDA (chưa đăng nhập) sẽ không "
								+ "tải được. Mở file trong danh sách File, bỏ đánh dấu 'Private', rồi mở "
								+ "lại trang này."
						),
					});
				}
				this.nap_lai();
			},
		});
	}

	ve() {
		const e = frappe.utils.escape_html;
		const goc = window.location.origin;
		const ban = this.ban;
		const khoi_ban = ban
			? `
			<div class="cap-ban">
				<div class="cap-nhan">${__("Bản đang phát hành")}</div>
				<div class="cap-ten">${e(ban.ten)}</div>
				<div class="cap-mo">${e(String(ban.dung_luong_mb))} MB · ${__("đưa lên")}
					${e(frappe.datetime.str_to_user(ban.tai_len_luc))}</div>
				<a class="cap-lien-ket" href="${e(ban.duong_dan)}" download>${__("Tải thử về máy này")}</a>
			</div>`
			: `<div class="cap-trong">${__(
					"Chưa có bản cài nào. Dựng APK theo pda_app/README.md rồi bấm 'Đưa bản cài lên'."
			  )}</div>`;

		this.$goc.html(`
			${khoi_ban}
			<button type="button" class="btn btn-primary cap-tai-len">${__("Đưa bản cài lên")}</button>

			<div class="cap-muc">
				<div class="cap-nhan">${__("Cài lên một máy quét")}</div>
				<ol class="cap-buoc">
					<li>${__("Trên máy quét, mở trình duyệt và gõ:")}
						<b class="cap-ma">${e(goc)}/tai-app</b></li>
					<li>${__("Bấm <b>Tải bản cài</b>, mở file vừa tải để cài (máy hỏi thì cho phép cài từ nguồn này).")}</li>
					<li>${__("Mở app Miyano PDA, khai địa chỉ máy chủ:")} <b class="cap-ma">${e(goc)}</b></li>
					<li>${__("Cấp thẻ cho người dùng rồi cho họ quét để vào việc.")}</li>
				</ol>
				<button type="button" class="btn btn-default cap-the">${__("Thẻ PDA")}</button>
			</div>

			<div class="cap-canh-bao">
				<b>${__("Hai điều phải nhớ")}</b>
				<ul>
					<li>${__(
						"Bản cài để <b>công khai</b>: ai biết đường dẫn đều tải được, và bên trong APK có "
							+ "địa chỉ máy chủ của kho. Không có mật khẩu hay khoá nào trong đó."
					)}</li>
					<li>${__(
						"Chỉ đưa lên bản đã trỏ đúng <b>máy chủ thật</b>. Bản dựng để thử trỏ vào máy chủ "
							+ "thử — thủ kho cài nhầm thì mọi thao tác ghi vào dữ liệu thử mà không ai biết."
					)}</li>
				</ul>
			</div>
		`);
	}
}
