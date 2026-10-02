# Alert Operations Runbook

Tài liệu này mô tả cách vận hành alert NewsPulse qua Telegram. Telegram chỉ là
kênh phân phối; dữ liệu alert, cooldown và trạng thái gửi được lưu trong MongoDB.

## Kiến trúc luồng alert

1. `anomaly_alerting_dag` chạy mỗi 30 phút và phát hiện volume spike, trend
   spike, sentiment tiêu cực.
2. `gx_validation_dag` tạo critical alert khi data-quality expectation thất bại.
3. Mỗi alert được chuẩn hóa thành `AlertEvent` có ID, loại, severity, tiêu đề
   và chi tiết.
4. Dispatcher claim ID trong collection `telegram_alert_deliveries`. Alert đang trong
   cooldown sẽ không được gửi lại.
5. Notifier gửi Telegram với timeout, exponential backoff và xử lý HTTP 429.
   Gửi thất bại sẽ nhả claim và làm Airflow task fail để retry.
6. `telegram_daily_report_dag` chạy 08:00 theo `Asia/Ho_Chi_Minh`, báo cáo ngày
   liền trước bằng metric thật từ ClickHouse, MongoDB và Airflow.
7. Service `telegram-bot` dùng long polling để nhận truy vấn read-only từ
   chat/user trong allowlist và tái sử dụng analytics service của API.

## Tra cứu trong Telegram

Bot hỗ trợ menu lệnh:

| Lệnh | Ví dụ | Kết quả |
| --- | --- | --- |
| `/alerts` | `/alerts 5` | Volume spike theo baseline 7 ngày |
| `/trend` | `/trend 24h 5` | Từ khóa nổi bật |
| `/source` | `/source vnexpress 7d` | Thống kê một nguồn |
| `/report` | `/report 30d` | Tổng quan bài viết, nguồn, category và latency |
| `/status` | `/status` | Health ClickHouse và MongoDB |
| `/help` | `/help` | Danh sách lệnh |

Các câu hỏi tiếng Việt sau cũng được hỗ trợ:

- `Có cảnh báo nào không?`
- `Từ khóa nổi bật 24 giờ`
- `Thống kê vnexpress 7 ngày`
- `Báo cáo tháng này`
- `Hệ thống ổn không?`

Bot không hỗ trợ lệnh ghi, trigger crawler, thay đổi threshold hay acknowledge
alert. Những thao tác này tiếp tục phải được thực hiện qua API/dashboard có
xác thực và confirmation.

## Secret và cấu hình

Không commit `.env`, bot token hoặc chat ID. Nếu token từng xuất hiện trong log,
terminal, chat hoặc artifact, hãy coi token đã bị lộ.

Rotate token:

1. Mở BotFather, chọn bot và revoke token cũ.
2. Tạo token mới.
3. Cập nhật `TELEGRAM_BOT_TOKEN` trong secret store hoặc `.env` của máy chạy.
4. Recreate Airflow scheduler/webserver; không ghi token vào lệnh shell hay log.

Các biến cấu hình:

| Biến | Mặc định | Ý nghĩa |
| --- | ---: | --- |
| `TELEGRAM_BOT_TOKEN` | Bắt buộc | Token mới từ BotFather |
| `TELEGRAM_CHAT_ID` | Bắt buộc | User, group hoặc channel nhận alert |
| `TELEGRAM_ALLOWED_CHAT_IDS` | Rỗng | Danh sách chat ID được tra cứu, phân tách bằng dấu phẩy |
| `TELEGRAM_ALLOWED_USER_IDS` | Rỗng | Danh sách user ID được tra cứu, phân tách bằng dấu phẩy |
| `TELEGRAM_TIMEOUT_SECONDS` | `10` | Timeout mỗi HTTP request |
| `TELEGRAM_MAX_ATTEMPTS` | `3` | Số lần thử gửi mỗi message chunk |
| `TELEGRAM_RETRY_BASE_SECONDS` | `1` | Backoff ban đầu |
| `TELEGRAM_ALERT_COOLDOWN_MINUTES` | `120` | Thời gian chặn alert ID trùng |
| `ALERT_DASHBOARD_URL` | Không có | Link trang alert đính kèm message |
| `TELEGRAM_POLL_TIMEOUT_SECONDS` | `25` | Timeout cho mỗi long-poll request |
| `TELEGRAM_RATE_LIMIT_PER_MINUTE` | `20` | Số truy vấn tối đa theo user/chat mỗi phút |
| `TELEGRAM_AUDIT_RETENTION_DAYS` | `90` | Thời gian lưu audit metadata trong MongoDB |

`TELEGRAM_CHAT_ID` tự động được thêm vào chat allowlist. Với group chat,
nên cấu hình thêm `TELEGRAM_ALLOWED_USER_IDS` để chỉ admin được tra cứu.
Khi user allowlist có giá trị, cả chat ID và user ID đều phải khớp.

## Deploy

Kiểm tra cấu hình và test trước khi recreate Airflow:

```bash
docker compose -f infrastructure/docker/docker-compose.yml config --quiet
python3 -m pytest tests/test_telegram_alert.py tests/test_alert_dispatcher.py tests/test_daily_report.py tests/test_telegram_foundation.py tests/test_telegram_queries.py tests/test_telegram_worker.py tests/test_telegram_runtime.py -q
```

Sau khi cập nhật secret:

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d --force-recreate airflow-scheduler airflow-webserver
docker compose -f infrastructure/docker/docker-compose.yml run --rm --no-deps airflow-scheduler airflow dags list-import-errors
docker compose -f infrastructure/docker/docker-compose.yml up -d --build telegram-bot
```

Xác nhận trong Airflow UI có hai DAG `anomaly_alerting_dag` và
`telegram_daily_report_dag`. Chỉ trigger thủ công sau khi token mới và chat ID đã được
cấu hình.

## Smoke test

1. Trigger `anomaly_alerting_dag` một lần.
2. Kiểm tra task log có `Đã gửi ... cảnh báo Telegram mới` hoặc
   `Các cảnh báo đang trong thời gian cooldown`.
3. Trigger lại trong thời gian cooldown. Telegram không được nhận message trùng.
4. Kiểm tra collection `telegram_alert_deliveries`: alert thành công phải có
   `status=sent`, `sent_at` và `next_allowed_at`.
5. Trigger `telegram_daily_report_dag` và đối chiếu số bài với ClickHouse cho
   ngày liền trước.
6. Gửi `/status` trong Telegram và xác nhận bot trả về health của ClickHouse,
   MongoDB.
7. Gửi `Từ khóa nổi bật 24 giờ` và xác nhận câu hỏi tự nhiên
   được map sang truy vấn trend.
8. Kiểm tra collection `telegram_bot_audit` có outcome/latency nhưng không có
   raw message text.

## Xử lý sự cố

- `Telegram credentials are not configured`: kiểm tra secret đã được inject vào
  cả scheduler lẫn webserver, sau đó recreate container.
- HTTP 400: thường do chat ID sai, bot chưa được add vào group/channel hoặc bot
  không có quyền gửi.
- HTTP 401: token không hợp lệ hoặc đã bị revoke.
- HTTP 429: notifier tự dùng `retry_after`; nếu lặp lại, tăng cooldown hoặc giảm
  số alert theo severity.
- Task thành công nhưng không có message: kiểm tra log cooldown và document
  `telegram_alert_deliveries`.
- Alert bị kẹt `pending`: chờ hết `next_allowed_at`; không xóa document trừ khi đã
  xác nhận không có task nào đang gửi.
- Bot không trả lời: kiểm tra `docker compose logs telegram-bot`, allowlist và
  collection `telegram_bot_state`. Tin từ chat/user không được phép sẽ bị bỏ qua.
- Lỗi `Conflict: terminated by other getUpdates request`: có nhiều polling worker dùng
  cùng token. Chỉ chạy một replica `telegram-bot`.
- Khi khởi động lần đầu, worker bỏ pending backlog cũ. Các lần restart sau
  sẽ tiếp tục từ offset lưu trong `telegram_bot_state`.

Không log nội dung token, URL Bot API đầy đủ hoặc raw payload có dữ liệu nhạy cảm.
