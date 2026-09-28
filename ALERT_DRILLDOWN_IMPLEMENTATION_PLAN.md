# Alert Drill-down Implementation Plan

## 1. Mục tiêu

Khi người dùng nhìn thấy một alert viral hoặc social-crisis, họ phải biết ngay:

- Chủ đề/bài viết nào đang gây chú ý.
- Nguồn và thời điểm xuất hiện.
- Mức độ tương tác cụ thể.
- Vì sao hệ thống đánh dấu alert.
- Có thể mở bài viết gốc ở đâu.

Giải pháp gồm hai phần:

1. Sửa pipeline để alert chứa dữ liệu thật, không dùng title placeholder như "Chủ đề đang hot trên reddit_vn".
2. Thêm drill-down: click alert card để mở modal trên desktop và bottom sheet trên mobile.

Modal không được che vấn đề dữ liệu. Nếu title, URL hoặc content thiếu, UI phải hiển thị rõ trạng thái thiếu dữ liệu.

## 2. Hiện trạng đã xác nhận

### Frontend

frontend/src/components/AlertsPanel.tsx hiện:

- Gọi GET /alerts/social.
- Render viral_alerts thành div không tương tác.
- Hiển thị source, title và interactions.
- Chưa có detail state, modal, focus management hoặc keyboard interaction.

### API

api/services/analytics.py:get_viral_post_alerts() hiện trả:

- post_id
- source
- title
- interactions
- sentiment_label

api/routers/alerts.py phản ánh các trường này qua ViralPostAlert.

### Warehouse

newspulse.social_sentiment_metrics đã có:

- post_id, source, title, content
- like_count, upvote_ratio, reply_count
- sentiment_score, sentiment_label
- publish_time, crawled_at, loaded_at

Nhưng chưa có URL và author. Spark cũng chưa giữ URL, author hoặc top comments dù một số crawler đã thu thập chúng.

Dữ liệu hiện tại chứa title placeholder:

- "Chủ đề đang hot trên reddit_vn"
- "Chủ đề đang hot trên facebook"
- "Chủ đề đang hot trên voz_forum"

Các post_id dạng live_post_uuid cho thấy một phần dữ liệu là synthetic/demo. Vì vậy chỉ làm modal là chưa đủ; phải sửa nguồn dữ liệu đồng thời.

## 3. Kiến trúc mục tiêu

Crawler/social API
→ SocialItem có metadata đầy đủ
→ Kafka/Spark social pipeline
→ ClickHouse social_sentiment_metrics
→ GET /alerts/social cho summary
→ GET /alerts/social/posts/{post_id} cho detail
→ AlertsPanel mở AlertDetailModal

GET /alerts/social chỉ trả summary tối đa 10 alert để polling/SSE nhẹ. Khi click card, frontend gọi detail endpoint theo post_id. Cách này giữ payload realtime nhỏ và cho phép lấy detail mới nhất.

Không tự suy diễn URL theo source. Chỉ hiển thị Open original post khi URL đã được crawler xác nhận.

## 4. Data contract

### Viral summary

Mở rộng summary với:

- publish_time
- alert_reason
- threshold
- data_quality.title_available

Nếu title rỗng hoặc khớp placeholder, API trả title_available=false và reason=placeholder_title. Không lặp placeholder trong UI.

### Viral detail

Tạo endpoint:

GET /api/v1/alerts/social/posts/{post_id}

Response cần có:

- post_id, source, title, content, excerpt
- url, author
- like_count, reply_count, interactions, upvote_ratio
- sentiment_score, sentiment_label
- publish_time
- alert.type, alert.threshold, alert.reason, alert.detected_at
- data_quality.title_available
- data_quality.content_available
- data_quality.url_available

Response status:

- 200 khi tìm thấy.
- 404 khi post không còn hoặc không tồn tại.
- 503 khi ClickHouse không sẵn sàng.

Không trả stack trace hoặc credential.

### Crisis detail

Phase sau có thể thêm:

GET /api/v1/alerts/social/crisis/{source}

Endpoint trả tổng post, negative ratio, sentiment distribution và top 5 posts đóng góp vào crisis.

## 5. Database migration

Tạo migration mới, không recreate bảng:

- ADD COLUMN url String DEFAULT ''.
- ADD COLUMN author String DEFAULT ''.
- ADD COLUMN top_comments Array(String) DEFAULT [].

Giữ nguyên ORDER BY (source, publish_time, post_id).

Audit trước migration:

- Số placeholder title theo source.
- Tỷ lệ record có content.
- Tỷ lệ record có URL.
- Tỷ lệ record map được về post gốc.

Không tự động biến placeholder thành title thật nếu không có nguồn đối chiếu.

Với record map được:

1. Fetch lại metadata theo rate limit.
2. Chỉ update title/content/url/author khi xác minh được.
3. Ghi log repaired, skipped và failed.
4. Record không map được giữ nguyên nhưng API phải trả data-quality warning.

Query audit nên lọc title rỗng hoặc title LIKE "Chủ đề đang hot trên %".

## 6. Pipeline changes

### Crawler contract

Kiểm tra SocialItem và từng spider:

- Reddit: title, URL, author, selftext, top comments.
- Voz: thread title, URL, author, content, comments.
- YouTube/Facebook/nguồn khác: title, canonical URL, author/page name và description.

Nếu nguồn không có title, dùng title rỗng và cờ data quality. Không tạo title giả có vẻ như dữ liệu thật.

### Spark streaming

Mở rộng schema Kafka và phần output select trong spark/streaming/streaming_job.py để ghi:

- url
- author
- top_comments

Đảm bảo:

- top_comments luôn là Array(String), default [].
- URL được chuẩn hóa nếu crawler cung cấp.
- dropDuplicates theo post_id vẫn được giữ.
- Fallback không tạo placeholder title.

### Validation

Validation tối thiểu:

- post_id bắt buộc.
- source bắt buộc.
- Title không được là placeholder khi có title thật.
- URL phải hợp lệ nếu khác rỗng.
- Metrics không âm.

Record fail validation đi vào DLQ hoặc data-quality log, không làm sập toàn bộ stream.

## 7. Backend implementation

### Models

Mở rộng model typed:

- ViralPostAlertSummary
- ViralPostDetail
- AlertReason
- AlertDataQuality

Không để response chính dùng dict không typed.

### Analytics queries

Trong api/services/analytics.py:

1. Giữ summary giới hạn 10 records.
2. Thêm detail query theo post_id.
3. Dùng parameter binding, không nối chuỗi trực tiếp.
4. Dùng LIMIT 1 và kiểm soát duplicate.
5. Dùng cùng công thức interactions ở summary và detail.
6. Trả None rõ ràng khi không tìm thấy.
7. Tạo helper phát hiện title rỗng hoặc placeholder.

### Endpoint behavior

GET /alerts/social/posts/{post_id}:

- 200: có record.
- 404: record không còn.
- 503: ClickHouse lỗi.

Frontend cần nhận biết data-quality flags để hiển thị cảnh báo chủ động.

## 8. Frontend implementation

### Components

Tạo:

- frontend/src/components/AlertDetailModal.tsx
- frontend/src/components/ui/Modal.tsx
- frontend/src/lib/alert-types.ts

Modal nên là component dùng chung cho các detail flow sau này.

### State trong AlertsPanel

Thêm selectedAlert, alertDetail, detailLoading và detailError.

Khi click:

1. Mở modal ngay bằng summary.
2. Hiển thị skeleton detail.
3. Fetch detail theo post_id.
4. Abort request cũ nếu click alert khác.
5. Nếu 404, giữ summary và báo post không còn.
6. Khi đóng, clear detail và trả focus về card.

### Alert card

Đổi viral card thành button-like interactive card:

- type=button.
- aria-haspopup=dialog.
- aria-expanded.
- aria-label có source/title.
- Title thật tối đa 2 dòng.
- Hiển thị source, interactions và thời gian.
- Placeholder title chuyển thành Title unavailable.
- Dùng post_id làm key và deduplicate.

### Modal layout

Desktop:

- Width khoảng 560–680px.
- Header có source, badge và Close.
- Body có title, metadata, metrics, excerpt và sentiment.
- Footer có Open original post và Close.

Mobile:

- Bottom sheet hoặc gần fullscreen.
- Header sticky.
- Body cuộn độc lập.
- Nút mở bài gốc full width.

### Accessibility

Modal phải có role=dialog, aria-modal=true và aria-labelledby.

Khi mở:

- Focus vào Close.
- Focus trap trong modal.
- Escape đóng modal.
- Click backdrop đóng modal.
- Đóng xong trả focus về card.
- Badge luôn có text, không phụ thuộc riêng vào màu.

Phải phân biệt detail loading, success, not found, API error và field unavailable. Không hiển thị undefined hoặc link giả.

## 9. SSE và realtime

Khi SSE gửi alert mới:

- Deduplicate theo post_id.
- Giữ tối đa 10 alert mới nhất.
- Không đóng modal đang mở khi list refresh.
- Không để response detail cũ ghi đè post mới.
- Detail đang mở chỉ refresh khi user yêu cầu hoặc hết TTL.

## 10. Test plan

### Backend unit tests

- Placeholder title detection.
- Summary và detail query mapping.
- Detail 404.
- Interactions bằng like_count + reply_count.
- URL rỗng không tạo link.
- Data-quality flags.

### API integration tests

- GET /alerts/social trả summary.
- GET /alerts/social/posts/{post_id} trả detail.
- Post không tồn tại trả 404.
- ClickHouse lỗi trả lỗi chuẩn hóa.
- Response không chứa raw exception hoặc credential.

### Frontend tests

- Click card mở modal.
- Skeleton xuất hiện trước detail.
- Success render title, source, metrics và sentiment.
- Placeholder title hiện cảnh báo.
- Link gốc ẩn/disable khi URL rỗng.
- Escape đóng modal.
- Focus quay lại card.
- Click nhanh hai card không bị stale response.
- SSE không tạo duplicate.

### Responsive/accessibility

Kiểm tra viewport 320x568, 375x812, 768x1024 và 1366x768.

Keyboard checklist:

- Tab tới alert card.
- Enter/Space mở detail.
- Tab trong modal không thoát ra ngoài.
- Escape đóng.
- Focus trở về card.

## 11. Rollout plan

### Phase A: Data quality audit

- Đếm placeholder title theo source.
- Xác định nguồn synthetic.
- Đo tỷ lệ title/content/url thật.
- Chưa bật drill-down nếu detail chưa có dữ liệu tối thiểu.

### Phase B: Schema và pipeline

- Chạy migration add columns.
- Deploy crawler/Spark changes.
- Theo dõi DLQ và placeholder ratio.
- Backfill record map được.

### Phase C: API

- Deploy models và detail endpoint.
- Chạy contract/integration tests.
- Theo dõi p95 latency và 404 rate.

### Phase D: Frontend modal

- Deploy modal sau khi API ổn định.
- Có thể dùng feature flag alert_drilldown_enabled.
- Theo dõi click rate và modal error rate.

### Phase E: Cleanup

- Xóa producer/seed tạo placeholder.
- Cập nhật README/runbook.
- Thêm metric title thật và URL availability.

## 12. Observability

Theo dõi:

- alert_detail_requests_total
- alert_detail_not_found_total
- alert_detail_latency_ms
- viral_alert_placeholder_title_total
- viral_alert_url_available_ratio
- viral_alert_modal_open_total

Log chỉ nên chứa post_id và source, không log toàn bộ content hoặc dữ liệu nhạy cảm.

## 13. Definition of Done

- Card hiển thị title thật hoặc data-unavailable state.
- Click card mở modal/bottom sheet.
- Có loading, success, not-found và error state.
- Detail có source, title, thời gian, metrics, sentiment và lý do alert.
- Link gốc chỉ xuất hiện khi URL xác minh được.
- Keyboard navigation và focus return hoạt động.
- Summary không duplicate theo post ID.
- Pipeline giữ title, URL và metadata cần thiết.
- Placeholder title bằng 0 trong dữ liệu mới.
- Backend/API/frontend tests đạt.
- Docker production build và smoke test đạt.
- Có metric theo dõi data quality và detail failures.

## 14. Commit plan đề xuất

1. feat(data): preserve social alert metadata
2. feat(api): add social alert detail endpoint
3. feat(ui): add alert drill-down modal
4. test(alerts): cover detail and keyboard flows
5. docs(alerts): document drill-down and data quality runbook

