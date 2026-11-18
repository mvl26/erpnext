/**
 * Raven Chat Widget - nổi góc dưới bên phải trên mọi trang Desk của Miyano ERP.
 * Được import trong erpnext.bundle.js (đã nạp trên mọi trang Desk qua app_include_js).
 * Chỉ hiện khi site có cài app Raven và user có role "Raven User".
 *
 * Khác bản gốc của HDSD_Raven_Widget:
 *  - Khởi tạo sau event "app_ready" (bản gốc chạy trước khi Frappe gán
 *    frappe.user_roles -> TypeError, widget không hiện).
 *  - Phím tắt đổi sang Alt+Shift+C, đăng ký qua frappe.ui.keys
 *    (Ctrl+Shift+R đã là "Clear Cache and Reload" của Frappe).
 *  - Esc đóng panel; ẩn trên màn hình < 768px bằng CSS (kể cả khi resize).
 *  - Không tự mở lại Raven khi F5 -> không có request /raven trước khi bấm.
 *  - Ghi trang Desk đang xem vào localStorage để nút "Về ERP" trên trang Raven
 *    toàn trang (raven_back_to_erp.js) quay lại đúng chỗ.
 */
(() => {
	const WIDTH = 420; // px
	const HEIGHT = 640; // px
	const RAVEN_URL = "/raven/channel";
	// Phải đúng thứ tự frappe.ui.keys.get_key sinh ra: alt+shift+<phím>
	const SHORTCUT = "alt+shift+c";
	// Trùng với RETURN_KEY trong raven_back_to_erp.js
	const RETURN_KEY = "mvl_raven_return_url";

	const remember_page = () => {
		try {
			localStorage.setItem(RETURN_KEY, location.pathname + location.search + location.hash);
		} catch (e) {
			// localStorage bị chặn -> nút "Về ERP" về trang chủ
		}
	};

	function init() {
		// Không chạy trong chính app Raven hoặc khi bị nhúng trong iframe
		if (window.self !== window.top) return;
		if (location.pathname.startsWith("/raven")) return;
		// ERPNext chạy cả trên site không cài Raven -> không hiện nút
		if (!(frappe.boot && frappe.boot.versions && frappe.boot.versions.raven)) return;
		if (!frappe.session || !frappe.session.user || frappe.session.user === "Guest") return;
		// Chỉ hiện cho user dùng được Raven
		if (!(frappe.user_roles || []).includes("Raven User")) return;
		if (document.getElementById("mvl-raven-widget")) return;

		// Router đổi URL trước khi phát "change", nên location lúc này là trang mới.
		// Ghi thêm lúc rời tab/trang: list view đổi query (bộ lọc) bằng replaceState mà
		// không phát "change", nên chỉ nghe router thì URL ghi lại bị cũ.
		remember_page();
		frappe.router.on("change", remember_page);
		document.addEventListener("visibilitychange", () => {
			if (document.visibilityState === "hidden") remember_page();
		});
		window.addEventListener("pagehide", remember_page);

		const wrap = document.createElement("div");
		wrap.id = "mvl-raven-widget";
		wrap.innerHTML = `
			<style>
				#mvl-raven-widget { position: fixed; right: 20px; bottom: 20px; z-index: 1030;
					font-family: var(--font-stack, inherit); }
				#mvl-raven-panel { width: ${WIDTH}px; height: ${HEIGHT}px; max-height: calc(100vh - 110px);
					background: var(--card-bg, #fff); border: 1px solid var(--border-color, #e2e2e2);
					border-radius: 10px; box-shadow: 0 12px 32px rgba(0,0,0,.18);
					overflow: hidden; display: none; flex-direction: column; margin-bottom: 12px; }
				#mvl-raven-panel.open { display: flex; }
				#mvl-raven-head { display: flex; align-items: center; justify-content: space-between;
					padding: 6px 8px 6px 12px; border-bottom: 1px solid var(--border-color, #e2e2e2);
					font-size: 13px; font-weight: 600; color: var(--text-color, #1f272e); }
				#mvl-raven-head .acts { display: flex; gap: 2px; }
				#mvl-raven-head button { border: none; background: transparent; cursor: pointer;
					padding: 4px 7px; border-radius: 6px; font-size: 13px; line-height: 1;
					color: var(--text-muted, #6b7280); }
				#mvl-raven-head button:hover { background: var(--fg-hover-color, #f4f5f6); }
				#mvl-raven-frame { flex: 1 1 auto; width: 100%; border: 0; }
				#mvl-raven-toggle { width: 52px; height: 52px; border-radius: 50%; border: none;
					cursor: pointer; background: var(--primary, #171717); color: #fff;
					box-shadow: 0 6px 18px rgba(0,0,0,.25); display: flex; align-items: center;
					justify-content: center; margin-left: auto; transition: transform .15s ease; }
				#mvl-raven-toggle:hover { transform: scale(1.06); }
				#mvl-raven-toggle svg { width: 24px; height: 24px; }
				@media (max-width: 767px) { #mvl-raven-widget { display: none !important; } }
				@media print { #mvl-raven-widget { display: none !important; } }
			</style>
			<div id="mvl-raven-panel">
				<div id="mvl-raven-head">
					<span>Raven Chat</span>
					<span class="acts">
						<button type="button" data-act="expand" title="${__("Mở toàn trang")}">&#8599;</button>
						<button type="button" data-act="close" title="${__("Đóng")} (Esc)">&#10005;</button>
					</span>
				</div>
				<iframe id="mvl-raven-frame" title="Raven Chat"></iframe>
			</div>
			<button id="mvl-raven-toggle" type="button" title="Raven Chat (Alt + Shift + C)">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
					stroke-linecap="round" stroke-linejoin="round">
					<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
				</svg>
			</button>`;
		document.body.appendChild(wrap);

		const panel = wrap.querySelector("#mvl-raven-panel");
		const frame = wrap.querySelector("#mvl-raven-frame");
		const is_open = () => panel.classList.contains("open");

		const open = (state) => {
			panel.classList.toggle("open", state);
			// Lazy load: chỉ tải Raven khi mở lần đầu
			if (state && !frame.getAttribute("src")) frame.src = RAVEN_URL;
		};

		wrap.querySelector("#mvl-raven-toggle").addEventListener("click", () => open(!is_open()));
		wrap.querySelector('[data-act="close"]').addEventListener("click", () => open(false));
		wrap.querySelector('[data-act="expand"]').addEventListener("click", () => {
			open(false);
			window.open(RAVEN_URL, "_blank");
		});

		// Phím tắt: đăng ký qua Frappe để hiện trong hộp thoại Keyboard Shortcuts
		frappe.ui.keys.add_shortcut({
			shortcut: SHORTCUT,
			action: () => open(!is_open()),
			description: __("Mở/đóng Raven Chat"),
			ignore_inputs: true,
		});

		// Esc đóng panel (khi focus đang ở trang Desk)
		document.addEventListener("keydown", (e) => {
			if (e.key === "Escape" && is_open()) open(false);
		});
	}

	// app_include_js chạy TRƯỚC khi Frappe khởi động; phải đợi app_ready
	// thì frappe.session.user / frappe.user_roles mới có giá trị.
	if (window.frappe && frappe.user_roles) {
		init();
	} else {
		$(document).on("app_ready", init);
	}
})();
