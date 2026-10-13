package vn.com.miyano.pda;

import android.os.Bundle;
import android.webkit.CookieManager;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import com.getcapacitor.Bridge;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.BridgeWebViewClient;

public class MainActivity extends BridgeActivity {

	// MẤT MẠNG GIỮA CA (spec §4): app phải hiện một màn lỗi có nút "Thử lại" thay
	// vì trang lỗi mặc định của Chrome. KHÔNG viết mới `onReceivedError` —
	// `com.getcapacitor.BridgeWebViewClient` (lớp cha của `PdaWebViewClient` bên
	// dưới) ĐÃ tự làm việc này: đọc thẳng
	// `node_modules/@capacitor/android/.../BridgeWebViewClient.java` (bản đang cài)
	// thì `onReceivedError` gọi `bridge.getErrorUrl()` — khác null VÀ
	// `request.isForMainFrame()` thì tự `view.loadUrl(errorPath)`.
	// `Bridge.getErrorUrl()` (`Bridge.java:536-549`) ghép từ `server.errorPath`
	// trong `capacitor.config.json`. Vì vậy chỉ cần khai `"errorPath": "index.html"`
	// là lỗi MẠNG THẬT ở khung chính tự nạp lại `www/index.html`.
	//
	// TOÀN BỘ LÝ DO LỚP NÀY CÒN TỒN TẠI là để GHI ĐÈ `onReceivedHttpError` —
	// `BridgeWebViewClient` dùng CHUNG đúng nhánh `errorPath` đó cho cả
	// `onReceivedError` (lỗi mạng) LẪN `onReceivedHttpError` (lỗi HTTP 4xx/5xx).
	// Chi tiết vì sao việc đó sinh vòng lặp vô hạn: xem Javadoc của chính hàm đó
	// bên dưới. Không có việc nào khác ở tầng Java nữa.
	//
	// TASK 2B — ĐÃ BỎ HẲN MẸO BẮT "/login". Đời cũ của app điều hướng WebView sang
	// trang web của máy chủ (`<máy chủ>/kho`), nên khi phiên Frappe hết hạn Desk đá
	// WebView sang "/login" — một màn đăng nhập desktop không dùng được bằng súng
	// quét — và phải chặn ở tầng Java vì JS của vỏ app đã bị điều hướng rời khỏi.
	// App đời mới KHÔNG RỜI `file:///android_asset/public/index.html` nữa: giao diện
	// nằm sẵn trong máy (`www/kho_pda.bundle.js`), mọi lời gọi máy chủ đi bằng
	// `fetch` qua cầu HTTP native (`CapacitorHttp`), và danh tính đi bằng khoá máy
	// trong header `Authorization` chứ không bằng cookie phiên. Không còn lượt điều
	// hướng nào để bắt, và 401/403 giờ do `vo.js::goi()` xử lý ngay trong trang.
	// Giữ lại đoạn mã ấy là để lại một đoạn NÓI DỐI về cách app chạy: người đọc sau
	// sẽ tin app vẫn mở trang web của máy chủ.
	//
	// Cùng lý do đó, `capacitor.config.json` đã bỏ `server.allowNavigation` (hàng
	// rào cho một lượt điều hướng không còn xảy ra) và `android.allowMixedContent`
	// (luật của trình duyệt cho nội dung nạp vào TRANG; lời gọi `CapacitorHttp` đi
	// bằng `HttpURLConnection` ở tầng Java, nơi quyết định là
	// `res/xml/network_security_config.xml`, không phải cờ đó).
	@Override
	public void onCreate(Bundle savedInstanceState) {
		super.onCreate(savedInstanceState);

		xoaSachCookie();

		// getBridge()/Bridge.setWebViewClient(BridgeWebViewClient) là API thật của
		// @capacitor/android 6.x — đọc trực tiếp từ mã nguồn đã tải về sau
		// `npx cap add android`, không viết theo trí nhớ:
		//   node_modules/@capacitor/android/capacitor/src/main/java/com/getcapacitor/Bridge.java
		//     (dòng ~1423: "public void setWebViewClient(BridgeWebViewClient client)")
		//   node_modules/@capacitor/android/capacitor/src/main/java/com/getcapacitor/BridgeWebViewClient.java
		//     (constructor "public BridgeWebViewClient(Bridge bridge)")
		// Kế thừa BridgeWebViewClient (thay vì android.webkit.WebViewClient trơn) để giữ
		// nguyên cầu nối gốc của Capacitor — shouldInterceptRequest, launchIntent() — và
		// chỉ đổi đúng một hành vi trước khi giao lại cho super.
		// BridgeActivity.onCreate() tự return sớm (không gọi this.load(), bridge ở lại null)
		// nếu setContentView(R.layout.bridge_layout_main) ném lỗi — thiết bị không có WebView
		// hệ thống, rơi về màn no_webview. Gác null ở đây để không NPE đè lên đúng màn báo lỗi
		// đó; máy không có WebView thì không có gì để gắn WebViewClient vào.
		Bridge bridge = getBridge();
		if (bridge != null) {
			bridge.setWebViewClient(new PdaWebViewClient(bridge));
		}
	}

	/**
	 * TASK 3 — XOÁ SẠCH KHO COOKIE CỦA WEBVIEW MỘT LẦN MỖI LẦN MỞ APP.
	 *
	 * <p>VÌ SAO CẦN: từ Task 3, danh tính của máy là khoá API trong header
	 * {@code Authorization}, và trạng thái "máy CHƯA được cấp quyền" là thứ cả màn
	 * quét thẻ lẫn hàm {@code the_pda.thu_hoi} dựa vào. Một cookie {@code sid} còn
	 * sót lại từ APK ĐỜI CŨ (đời đó điều hướng WebView thẳng vào trang web của máy
	 * chủ) làm máy chủ vẫn nhận ra người dùng cũ dù máy chẳng có khoá nào — app
	 * trông như chạy được, còn "chưa cấp quyền" thì bị che mất. Nguy hiểm thật nằm
	 * ở đó, không phải ở ca "hai danh tính chọn nhầm": {@code frappe/app.py} chạy
	 * {@code validate_auth()} SAU khi phiên cookie đã dựng, nên khi CÓ khoá thì khoá
	 * luôn thắng. Ca đáng sợ là ca CHƯA có khoá — và đó là trạng thái của mọi máy
	 * sau {@code KhoApp.xoa_khoa()}.
	 *
	 * <p>VÌ SAO KHÔNG LÀM CÁCH KHÁC — hai lối đã bị bác bỏ sau khi đọc mã Capacitor:
	 * <ul>
	 *   <li>Tắt plugin {@code CapacitorCookies} bằng cờ trong
	 *       {@code capacitor.config.json} KHÔNG chặn được: cờ chỉ được đọc trong
	 *       {@code isEnabled()}, phục vụ phần vá {@code document.cookie} ở tầng JS.
	 *       Dòng {@code CookieHandler.setDefault(this.cookieManager)} nằm trong
	 *       {@code load()} và chạy BẤT KỂ cờ đó — và chính nó là thứ khiến
	 *       {@code HttpURLConnection} của cầu native gắn cookie của WebView vào lời
	 *       gọi, bất kể {@code credentials}.</li>
	 *   <li>{@code removeSessionCookies()} mà {@code CapacitorCookies.load()} tự gọi
	 *       KHÔNG cứu được: {@code sid} của Frappe được đặt kèm {@code max_age}
	 *       ({@code frappe/auth.py:385}), tức là cookie CÓ HẠN chứ không phải cookie
	 *       phiên — nó sống sót lời gọi đó. Phải là {@code removeAllCookies}.</li>
	 * </ul>
	 *
	 * <p>VÌ SAO SAU {@code super.onCreate(...)} CHỨ KHÔNG TRƯỚC: {@code CookieManager
	 * .getInstance()} phải nạp WebView của hệ thống, nên trên đúng chiếc máy KHÔNG có
	 * WebView nó ném — và ném trước {@code super.onCreate()} là cướp mất màn báo lỗi
	 * {@code no_webview} mà {@code BridgeActivity} dựng cho đúng chiếc máy đó (cùng
	 * lý do với phép gác {@code bridge != null} bên dưới). Gọi sau vẫn sớm hơn mọi
	 * lời gọi mạng: {@code CapacitorCookies.load()} chỉ CÀI trình quản lý cookie, còn
	 * kho cookie chỉ bị đọc lúc {@code HttpURLConnection} chạy — tức sau khi thủ kho
	 * quét thẻ. {@code try/catch} bao ngoài vì mất cookie không phải lý do để app
	 * không mở được.
	 *
	 * <p>CHƯA ĐO ĐƯỢC TRÊN MÁY THẬT: máy dựng bản này không có thiết bị lẫn gói
	 * emulator (Task 2B §0). Điều duy nhất được kiểm tự động là đoạn mã này CÓ MẶT
	 * trong phần mã chạy ({@code test_giao_dien.test_vo_app_xoa_sach_cookie_luc_khoi_dong}).
	 */
	private void xoaSachCookie() {
		try {
			CookieManager cm = CookieManager.getInstance();
			cm.removeAllCookies(null);
			cm.flush();
		} catch (Throwable boQua) {
			// Không có WebView hệ thống (hoặc kho cookie hỏng): để BridgeActivity tự
			// hiện màn no_webview của nó. Chết ở đây là chết trước cả màn báo lỗi.
		}
	}

	private static class PdaWebViewClient extends BridgeWebViewClient {

		PdaWebViewClient(Bridge bridge) {
			super(bridge);
		}

		/**
		 * CỐ Ý KHÔNG gọi {@code super.onReceivedHttpError(...)}: xem chú thích dài ở
		 * {@link MainActivity#onCreate}. {@code BridgeWebViewClient.onReceivedHttpError} nạp lại
		 * `errorPath` cho MỌI lỗi HTTP ở khung chính — dùng chung nhánh với lỗi mạng thật — và với
		 * lỗi HTTP (máy chủ vẫn ping được) việc đó gây vòng lặp vô hạn (ping thành công → điều
		 * hướng lại đúng trang lỗi → lỗi lại → errorPath → ping lại...) mà không có nút nào bấm
		 * được ở giữa hai lần tải.
		 *
		 * Không có "super.super" trong Java để nhảy thẳng qua {@code BridgeWebViewClient} tới
		 * {@code android.webkit.WebViewClient} — nhưng hành vi mặc định của lớp gốc đó vốn không
		 * làm gì cả (không override {@code onReceivedHttpError}), nên bỏ hẳn thân hàm ở đây tương
		 * đương với hành vi mặc định đó: WebView tự hiện nội dung lỗi mà máy chủ trả về — xấu
		 * nhưng ĐỨNG YÊN, không lặp, còn bấm Back thoát được.
		 *
		 * Cũng vì vậy bỏ qua việc thông báo `WebViewListener` mà bản gốc làm qua
		 * `bridge.getWebViewListeners()`: hàm đó có visibility package-private trong
		 * `com.getcapacitor`, không gọi được từ package `vn.com.miyano.pda` này — và app này
		 * không đăng ký WebViewListener nào (kiểm `pda_app/package.json`: chỉ có
		 * `@capacitor/core` + `@capacitor/android`), nên bỏ qua không mất chức năng nào đang dùng.
		 *
		 * GHI CHÚ TASK 2B: từ khi app không rời `index.html` nữa, khung chính gần như không còn
		 * đường nào ăn một lỗi HTTP — mọi lời gọi máy chủ đi bằng `fetch` (CapacitorHttp), không
		 * phải bằng một lượt tải trang. Nhánh này vì vậy là một cái lưới, không phải một đường
		 * chạy thường xuyên; giữ lại vì `errorPath` VẪN còn và nó là thứ duy nhất chặn vòng lặp
		 * nếu có ai thêm lại một lượt điều hướng ra ngoài.
		 */
		@Override
		public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse errorResponse) {
			// Thân hàm để trống có chủ đích — xem Javadoc ở trên.
		}
	}
}
