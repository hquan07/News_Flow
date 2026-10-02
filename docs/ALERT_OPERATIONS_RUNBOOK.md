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
| `TELEGRAM_TIMEOUT_SECONDS` | `10` | Timeout mỗi HTTP request |
| `TELEGRAM_MAX_ATTEMPTS` | `3` | Số lần thử gửi mỗi message chunk |
| `TELEGRAM_RETRY_BASE_SECONDS` | `1` | Backoff ban đầu |
| `TELEGRAM_ALERT_COOLDOWN_MINUTES` | `120` | Thời gian chặn alert ID trùng |
| `ALERT_DASHBOARD_URL` | Không có | Link trang alert đính kèm message |

## Deploy

Kiểm tra cấu hình và test trước khi recreate Airflow:

```bash
docker compose -f infrastructure/docker/docker-compose.yml config --quiet
python3 -m pytest tests/test_telegram_alert.py tests/test_alert_dispatcher.py tests/test_daily_report.py -q
```

Sau khi cập nhật secret:

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d --force-recreate airflow-scheduler airflow-webserver
docker compose -f infrastructure/docker/docker-compose.yml run --rm --no-deps airflow-scheduler airflow dags list-import-errors
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

Không log nội dung token, URL Bot API đầy đủ hoặc raw payload có dữ liệu nhạy cảm.
