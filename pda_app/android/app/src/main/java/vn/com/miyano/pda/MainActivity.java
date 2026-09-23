package vn.com.miyano.pda;

import android.net.Uri;
import android.os.Bundle;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import com.getcapacitor.Bridge;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.BridgeWebViewClient;

public class MainActivity extends BridgeActivity {

	// MẤT MẠNG GIỮA CA (đợt sửa cuối, mục 7): spec §4 hứa một màn lỗi riêng có nút
	// "Thử lại" thay vì trang lỗi mặc định của Chrome. KHÔNG viết mới `onReceivedError`
	// — `com.getcapacitor.BridgeWebViewClient` (lớp cha của `PdaLoginRedirectWebViewClient`
	// bên dưới) ĐÃ tự làm việc này: đọc thẳng
	// `node_modules/@capacitor/android/.../BridgeWebViewClient.java` (bản đang cài) thì
	// `onReceivedError` gọi `bridge.getErrorUrl()` — khác null VÀ `request.isForMainFrame()`
	// thì tự `view.loadUrl(errorPath)`. `Bridge.getErrorUrl()` (`Bridge.java:536-549`) ghép
	// từ `server.errorPath` trong `capacitor.config.json`. Vì vậy chỉ cần khai
	// `"errorPath": "index.html"` trong `server` của `capacitor.config.json` là lỗi MẠNG
	// THẬT (mất wifi, DNS hỏng, `ERR_CLEARTEXT_NOT_PERMITTED`...) ở khung chính tự nạp lại
	// `www/index.html` (màn khai/nối máy chủ, đã có nút "Thử lại" + "Đổi máy chủ").
	//
	// PHẢI GHI ĐÈ `onReceivedHttpError` ĐỂ CHẶN VÒNG LẶP: `BridgeWebViewClient` dùng CHUNG
	// đúng nhánh `errorPath` đó cho cả `onReceivedError` (lỗi mạng) LẪN `onReceivedHttpError`
	// (lỗi HTTP 4xx/5xx từ chính máy chủ Frappe, ví dụ site đang lỗi 500). Với lỗi HTTP, máy
	// chủ VẪN ping được (`/api/method/ping` vẫn trả 200) — nạp lại `errorPath` thì
	// `www/index.html` tự ping thành công, tự điều hướng lại đúng trang đang lỗi đó, lỗi lại,
	// nạp lại `errorPath`... một VÒNG LẶP VÔ HẠN không có nút nào bấm được ở giữa hai lần tải.
	// Trước khi có `errorPath`, một lỗi HTTP chỉ hiện trang lỗi xấu của Frappe — xấu nhưng
	// đứng yên, còn bấm Back được; đừng để `errorPath` biến nó thành một vòng lặp không thoát
	// ra được. `PdaLoginRedirectWebViewClient` ghi đè `onReceivedHttpError` bên dưới để giữ
	// nguyên hành vi "đứng yên" đó, chỉ để nhánh `errorPath` cho đúng lỗi mạng thật.
	//
	// Việc bắt "/login" dưới đây vẫn phải tự viết vì đó là một luật nghiệp vụ riêng (Frappe
	// không có khái niệm "errorPath cho /login"), nhưng lỗi mạng thì Capacitor đã lo.

	// VIỆC THÊM NGOÀI BRIEF (Ruling 12, .superpowers/sdd/2026-09-23-app-pda-apk/task-5-brief.md):
	// phiên đăng nhập Frappe sống 12 tiếng (xem trang /pda, Task 3). Hết phiên giữa ca,
	// Desk tự chuyển hướng WebView sang "/login" — màn hình không dùng được bằng súng quét.
	//
	// VÌ SAO PHẢI CHẶN Ở TẦNG JAVA, KHÔNG PHẢI JS CỦA VỎ APP:
	// JS đóng gói trong www/index.html chỉ sống trong khi WebView còn hiển thị đúng
	// file:///android_asset/public/index.html (nguồn của vỏ app). Ngay khi người dùng bấm
	// "Kiểm tra & lưu", trang đó tự điều hướng sang <máy chủ>/pda — từ đó WebView hiển thị
	// nguồn của máy chủ Frappe thật, và JS của index.html không còn chạy nữa (đã bị điều
	// hướng rời khỏi, không phải iframe). Không có cách nào cứu bằng script tiêm vào trang
	// máy chủ vì trang máy chủ không có script như vậy (spec §4 chỉ giao việc này cho vỏ app).
	// Vì vậy việc bắt điều hướng "/login" phải chặn ở WebViewClient gốc, tầng native.
	//
	// KHÔNG LÀM Ở MÁY CHỦ: đã kiểm — Frappe chỉ xử lý frappe.Redirect trong tầng render
	// trang web (apps/frappe/frappe/website/serve.py:28); handle_exception của
	// apps/frappe/frappe/app.py không có nhánh Redirect, nên chặn từ hook before_request
	// sẽ ra trang lỗi thay vì chuyển hướng sạch.
	@Override
	public void onCreate(Bundle savedInstanceState) {
		super.onCreate(savedInstanceState);

		// getBridge()/Bridge.setWebViewClient(BridgeWebViewClient) là API thật của
		// @capacitor/android 6.x — đọc trực tiếp từ mã nguồn đã tải về sau
		// `npx cap add android`, không viết theo trí nhớ:
		//   node_modules/@capacitor/android/capacitor/src/main/java/com/getcapacitor/Bridge.java
		//     (dòng ~1423: "public void setWebViewClient(BridgeWebViewClient client)")
		//   node_modules/@capacitor/android/capacitor/src/main/java/com/getcapacitor/BridgeWebViewClient.java
		//     (constructor "public BridgeWebViewClient(Bridge bridge)")
		// Kế thừa BridgeWebViewClient (thay vì android.webkit.WebViewClient trơn) để giữ
		// nguyên cầu nối gốc của Capacitor — shouldInterceptRequest, launchIntent(), hàng rào
		// allowNavigation trong capacitor.config.json — và chỉ chen thêm đúng một luật trước
		// khi giao lại cho super.
		// BridgeActivity.onCreate() tự return sớm (không gọi this.load(), bridge ở lại null)
		// nếu setContentView(R.layout.bridge_layout_main) ném lỗi — thiết bị không có WebView
		// hệ thống, rơi về màn no_webview. Gác null ở đây để không NPE đè lên đúng màn báo lỗi
		// đó; máy không có WebView thì không có gì để gắn WebViewClient vào.
		Bridge bridge = getBridge();
		if (bridge != null) {
			bridge.setWebViewClient(new PdaLoginRedirectWebViewClient(bridge));
		}
	}

	/**
	 * Bắt điều hướng có đường dẫn bắt đầu bằng "/login" (Desk đá về đây khi phiên hết hạn)
	 * và nạp thẳng "<máy chủ>/pda" (trang quét thẻ, Task 3) thay vì để WebView mở /login —
	 * màn đăng nhập desktop của Frappe không dùng được bằng súng quét PDA (spec §4).
	 *
	 * Override cả hai overload của shouldOverrideUrlLoading: overload nhận WebResourceRequest
	 * chỉ được gọi từ API 24 trở lên; android/variables.gradle của bản Capacitor 6 sinh ra
	 * đặt minSdkVersion = 22, nên overload String (deprecated nhưng vẫn là đường gọi thật trên
	 * API 22–23) phải được chặn cùng một luật, không được bỏ sót.
	 */
	private static class PdaLoginRedirectWebViewClient extends BridgeWebViewClient {

		PdaLoginRedirectWebViewClient(Bridge bridge) {
			super(bridge);
		}

		@Override
		public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
			Uri url = request.getUrl();
			if (laDuongDangNhap(url)) {
				dieuHuongVeQuetThe(view, url);
				return true;
			}
			return super.shouldOverrideUrlLoading(view, request);
		}

		@Deprecated
		@Override
		public boolean shouldOverrideUrlLoading(WebView view, String urlString) {
			Uri url = Uri.parse(urlString);
			if (laDuongDangNhap(url)) {
				dieuHuongVeQuetThe(view, url);
				return true;
			}
			return super.shouldOverrideUrlLoading(view, urlString);
		}

		private boolean laDuongDangNhap(Uri url) {
			String path = url.getPath();
			return path != null && path.startsWith("/login");
		}

		private void dieuHuongVeQuetThe(WebView view, Uri url) {
			String goc = url.getScheme() + "://" + url.getAuthority();
			view.loadUrl(goc + "/pda");
		}

		/**
		 * CỐ Ý KHÔNG gọi {@code super.onReceivedHttpError(...)}: xem chú thích dài ở
		 * {@link MainActivity#onCreate}. {@code BridgeWebViewClient.onReceivedHttpError} nạp lại
		 * `errorPath` cho MỌI lỗi HTTP ở khung chính — dùng chung nhánh với lỗi mạng thật — và với
		 * lỗi HTTP (máy chủ vẫn ping được) việc đó gây vòng lặp vô hạn (ping thành công → điều
		 * hướng lại đúng trang lỗi → lỗi lại → errorPath → ping lại...).
		 *
		 * Không có "super.super" trong Java để nhảy thẳng qua {@code BridgeWebViewClient} tới
		 * {@code android.webkit.WebViewClient} — nhưng hành vi mặc định của lớp gốc đó vốn không
		 * làm gì cả (không override {@code onReceivedHttpError}), nên bỏ hẳn thân hàm ở đây tương
		 * đương với hành vi mặc định đó: WebView tự hiện nội dung lỗi mà máy chủ trả về (trang lỗi
		 * xấu của Frappe) — xấu nhưng ĐỨNG YÊN, không lặp, còn bấm Back thoát được.
		 *
		 * Cũng vì vậy bỏ qua việc thông báo `WebViewListener` mà bản gốc làm qua
		 * `bridge.getWebViewListeners()`: hàm đó có visibility package-private trong
		 * `com.getcapacitor`, không gọi được từ package `vn.com.miyano.pda` này — và app này
		 * không đăng ký WebViewListener/plugin nào (kiểm `pda_app/package.json`: chỉ có
		 * `@capacitor/core` + `@capacitor/android`), nên bỏ qua không mất chức năng nào đang dùng.
		 */
		@Override
		public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse errorResponse) {
			// Thân hàm để trống có chủ đích — xem Javadoc ở trên.
		}
	}
}
