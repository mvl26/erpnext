/**
 * Nút logo ERP trên thanh bên trái của Raven toàn trang (/raven/...), ngay trên
 * "Later" và avatar người dùng: bấm thì quay lại Miyano ERP.
 *
 * Trang Raven là app React riêng, không nạp erpnext.bundle.js, nên file này KHÔNG
 * import trong bundle: hook `after_request` (erpnext/utilities/raven.py) chèn nguyên
 * nội dung file inline vào HTML trang Raven, kèm `data-logo` là logo trên navbar ERP.
 * Vì vậy chỉ viết JS thuần, không dùng `frappe`, `__()` hay jQuery.
 *
 * Bấm nút thì về đúng trang ERP vừa rời (raven_widget.js ghi vào localStorage mỗi
 * lần đổi trang trong Desk); chưa có thì về trang chủ ERP.
 *
 * Bám theo giao diện Raven 3.x: nút đứng ngay trước link "Later" (`a[href$="/later"]`)
 * trong nhóm dưới cùng của thanh bên. Raven render sau script này và có thể dựng lại
 * thanh bên, nên MutationObserver gắn lại nút mỗi khi nó bị mất. Không tìm thấy link
 * "Later" (giao diện mobile, hoặc Raven đổi giao diện) thì không hiện nút.
 */
(() => {
	// Trùng với RETURN_KEY trong raven_widget.js
	const RETURN_KEY = "mvl_raven_return_url";
	const HOME = "/app/home";
	const ID = "mvl-back-to-erp";
	const LABEL = "Về Miyano ERP";

	// Raven mở trong widget (iframe) thì người dùng vẫn đang ở ERP, không cần nút
	if (window.self !== window.top) return;

	const script = document.currentScript;
	const logo = script && script.dataset.logo;

	const return_url = () => {
		let url = null;
		try {
			url = window.localStorage.getItem(RETURN_KEY);
		} catch (e) {
			// localStorage bị chặn (chế độ riêng tư...) -> về trang chủ
		}
		// Chỉ nhận đường dẫn Desk trong cùng site, không nhận "//host" hay URL tuyệt đối
		return url && /^\/app(?:[/?#]|$)/.test(url) ? url : HOME;
	};

	// Cùng kích thước, màu, bo góc và tooltip với các nút IconBox trên thanh bên Raven;
	// biến màu là của Raven nên tự đổi theo chế độ sáng/tối.
	const STYLE = `
		#${ID} { position: relative; width: var(--primary-sidebar-width, 60px);
			display: flex; align-items: center; justify-content: center; }
		#${ID} > a { display: flex; align-items: center; justify-content: center;
			width: 32px; height: 32px; border-radius: var(--radius, 8px);
			background: var(--surface-gray-2, #f3f3f3); transition: background-color .2s; }
		#${ID} > a:hover { background: var(--surface-gray-3, #ededed); }
		#${ID} > a:focus-visible { outline: 2px solid var(--outline-gray-4, #3b82f6); outline-offset: 2px; }
		#${ID} img { width: 22px; height: 22px; object-fit: contain; }
		#${ID} > span { position: absolute; left: calc(100% + 4px); top: 50%; z-index: 50;
			transform: translateY(-50%); white-space: nowrap; pointer-events: none;
			padding: 4px 8px; border-radius: var(--radius, 8px); font-size: 12px; line-height: 1.4;
			background: var(--surface-gray-10, #171717); color: var(--ink-base, #fff);
			box-shadow: 0 10px 24px rgba(0, 0, 0, .18); display: none; }
		#${ID} > span::before { content: ""; position: absolute; right: 100%; top: 50%;
			transform: translateY(-50%); border: 4px solid transparent;
			border-right-color: var(--surface-gray-10, #171717); }
		#${ID} > a:hover + span, #${ID} > a:focus-visible + span { display: block; }
	`;

	const build = () => {
		const item = document.createElement("div");
		item.id = ID;

		const link = document.createElement("a");
		link.href = return_url();
		link.setAttribute("aria-label", LABEL);
		const img = document.createElement("img");
		img.src = logo;
		img.alt = "";
		link.appendChild(img);

		const tip = document.createElement("span");
		tip.setAttribute("role", "tooltip");
		tip.textContent = LABEL;

		// Tab ERP khác có thể vừa đổi trang: đọc lại ngay trước khi bấm
		// (kể cả Ctrl+click / chuột giữa mở tab mới).
		const refresh = () => {
			link.href = return_url();
		};
		link.addEventListener("pointerenter", refresh);
		link.addEventListener("pointerdown", refresh);
		link.addEventListener("focus", refresh);

		item.append(link, tip);
		return item;
	};

	const place = () => {
		const later = document.querySelector('a[href$="/later"]');
		if (!later) return;
		const item = document.getElementById(ID) || build();
		// Đã nằm trong nhóm của "Later" thì để yên (nút tin hẹn giờ có thể chen vào giữa)
		if (item.parentElement !== later.parentElement) later.before(item);
	};

	const start = () => {
		if (!logo) return;
		const style = document.createElement("style");
		style.textContent = STYLE;
		document.head.appendChild(style);

		place();
		// Gộp các thay đổi DOM trong một khung hình: chat cập nhật DOM liên tục
		let queued = false;
		new MutationObserver(() => {
			if (queued) return;
			queued = true;
			requestAnimationFrame(() => {
				queued = false;
				place();
			});
		}).observe(document.body, { childList: true, subtree: true });
	};

	if (document.body) {
		start();
	} else {
		document.addEventListener("DOMContentLoaded", start);
	}
})();
