// Copyright (c) 2026, Công ty TNHH Miyano Việt Nam
//
// Trang hướng dẫn một trang (BA mục 6.5): 5 bước tạo điểm, 4 ví dụ hoàn chỉnh,
// và các lỗi thường gặp. Đặt trong hệ thống để người dùng tra ngay lúc đang
// cấu hình, thay vì phải mở file HDSD rời.

frappe.pages["huong_dan_thong_bao"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Hướng dẫn thiết lập thông báo"),
		single_column: true,
	});

	page.set_secondary_action(__("Danh sách điểm"), () =>
		frappe.set_route("List", "Supply Notification Point")
	);

	page.main.html(content());
};

function content() {
	return `
<div class="guide" style="max-width: 900px">
	<h4>5 bước tạo một thông báo mới</h4>
	<ol>
		<li><b>Chọn chứng từ và thời điểm</b> (thẻ 2). Ví dụ: <i>Phiếu nhập mua · Khi ghi sổ</i>.</li>
		<li><b>Thêm điều kiện</b> nếu chỉ muốn bắn trong một số trường hợp. Ví dụ: <i>Kho = Kho Miyano</i>.</li>
		<li><b>Chọn người nhận</b> (thẻ 3) rồi bấm <b>Xem trước người nhận</b> để thấy danh sách thật.</li>
		<li><b>Soạn tiêu đề và thân email</b> (thẻ 5) bằng nút <b>Chèn trường / Chèn khối / Chèn mẫu</b>.</li>
		<li><b>Lưu → Xem trước email với một chứng từ thật → Gửi thử cho tôi</b>, xong xuôi mới bật <b>Đang bật</b>.</li>
	</ol>

	<h4>Bốn ví dụ hoàn chỉnh</h4>
	<table class="table table-bordered">
		<thead><tr><th>Muốn gì</th><th>Cấu hình</th></tr></thead>
		<tbody>
			<tr>
				<td>Báo kho khi có đơn bán mới</td>
				<td>Đơn bán hàng · Khi ghi sổ · người nhận: phòng Kho · thân email có <code>{{ bang_mat_hang() }}</code></td>
			</tr>
			<tr>
				<td>Nhắc hạn hoá đơn</td>
				<td>Hoá đơn mua · Nhắc theo ngày · trường ngày <i>Hạn thanh toán</i> · mốc <code>-7, -3, -1</code> · điều kiện <i>Còn nợ &gt; 0</i></td>
			</tr>
			<tr>
				<td>Báo theo bước duyệt</td>
				<td>Phiếu thanh toán · Chuyển trạng thái duyệt · chọn trạng thái đích của quy trình đang bật</td>
			</tr>
			<tr>
				<td>Gửi đơn mua hàng cho NCC</td>
				<td>Đơn mua hàng · Thủ công · nhãn nút <i>Gửi cho NCC</i> · chỉ bật kênh <i>Email ra ngoài</i> · người nhận: đầu mối liên hệ NCC · CC: người tạo</td>
			</tr>
		</tbody>
	</table>

	<h4>Lỗi thường gặp</h4>
	<ul>
		<li><b>Chọn phòng ban mà không ai nhận được:</b> nhân viên trong phòng chưa gắn tài khoản (<code>user_id</code>). Nút <i>Xem trước người nhận</i> báo rõ số người bị bỏ.</li>
		<li><b>NCC/khách không nhận được thư:</b> đối tác chưa có email liên hệ. Xem báo cáo <i>Đối tác thiếu email liên hệ</i>.</li>
		<li><b>Không thư nào đi:</b> scheduler đang tắt, hoặc <i>Cài đặt thông báo</i> đang tắt toàn bộ.</li>
		<li><b>Thư chỉ về một địa chỉ lạ:</b> đang bật <b>Chế độ thử</b> trong Cài đặt thông báo.</li>
		<li><b>Điểm tự tắt:</b> vượt trần thư mỗi giờ — xem ô <i>Lý do tạm dừng</i> trên điểm.</li>
	</ul>

	<h4>Ranh giới</h4>
	<p class="text-muted">
		Nghiệp vụ tự làm được: thêm điểm trên chứng từ có sẵn, đổi người nhận, đổi câu chữ, thêm điều kiện,
		đổi mốc nhắc, đổi âm báo và giờ nhắc. Cần Dev khi muốn có <b>khối nội dung mới</b> (ví dụ bảng tuổi nợ)
		hoặc một loại thời điểm chưa có.
	</p>
</div>`;
}
