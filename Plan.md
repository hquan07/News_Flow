# NewsPulse UI & Data Visualization Improvement Plan

## 1. Mục tiêu

Kế hoạch này cải thiện giao diện NewsPulse từ một dashboard có hình thức tốt trên desktop thành một sản phẩm:

- Hoạt động ổn định trên desktop, tablet và mobile.
- Không hiển thị số liệu hoặc trạng thái gây hiểu nhầm.
- Có bộ lọc nhất quán giữa các màn hình.
- Giúp người dùng hiểu chart mà không phải tự suy luận đơn vị, thời gian hay trạng thái dữ liệu.
- Có thể sử dụng bằng bàn phím, screen reader và không phụ thuộc hoàn toàn vào màu sắc.
- Có ngôn ngữ, component và trạng thái UI nhất quán.

Phạm vi chính nằm trong:

- `frontend/src/app/page.tsx`
- `frontend/src/app/globals.css`
- `frontend/src/components/LandingHero.tsx`
- `frontend/src/components/KnowledgeGraph.tsx`
- `frontend/src/components/AlertsPanel.tsx`
- `frontend/src/components/views/*.tsx`
- Các API health, metrics và analytics tương ứng trong `api/`

## 2. Nguyên tắc triển khai

1. Không hard-code số liệu có vẻ là dữ liệu thật.
2. Mọi filter được hiển thị phải có tác dụng hoặc được disable kèm giải thích.
3. Mọi khối dữ liệu phải phân biệt rõ `loading`, `empty`, `error` và `success`.
4. Chart phải trả lời một câu hỏi cụ thể, không chỉ dùng để trang trí.
5. Không dùng màu sắc làm tín hiệu duy nhất.
6. Mobile là một layout riêng có chủ đích, không chỉ là desktop bị thu nhỏ.
7. Các thay đổi phải giữ ESLint, TypeScript và production build ở trạng thái xanh.

## 3. Mức độ ưu tiên

### UI-P0 — Ảnh hưởng trực tiếp tới khả năng sử dụng

- Responsive mobile và tablet.
- Loại bỏ số liệu/trạng thái hard-code.
- Sửa phạm vi hoạt động của global filters.
- Phân biệt loading, error và empty state.

### UI-P1 — Nâng chất lượng phân tích dữ liệu

- Bổ sung context, đơn vị, freshness và tooltip cho chart.
- Cải tiến các chart category, sentiment, word cloud và entity.
- Bổ sung controls và legend cho Knowledge Graph.

### UI-P2 — Hoàn thiện trải nghiệm sản phẩm

- Accessibility.
- Chuẩn hóa ngôn ngữ/i18n.
- Chuẩn hóa design system và giảm inline style.
- Tối ưu animation, rendering và visual regression testing.

---

## 4. UI-P0 — Responsive mobile và tablet

### 4.1. Vấn đề

- Landing page luôn dùng layout hai cột.
- Tiêu đề `3.5rem`, khoảng cách `60px` và padding `40px` gây tràn ngang ở mobile.
- Header dashboard chứa mode switcher, source filter, export, user và logout trên cùng một hàng.
- Tabs không wrap hoặc scroll hợp lý.
- Bảng articles không có chiến lược hiển thị cho màn hình hẹp.
- Một số chart dùng chiều cao và kích thước label cố định.
- `EntitiesView` override grid thành ba cột bằng inline style nên media query `.charts-grid` không luôn có hiệu lực như mong muốn.

### 4.2. Cách sửa

#### Landing page

Refactor inline styles trong `LandingHero.tsx` thành các class:

- `.landing-layout`
- `.landing-copy`
- `.landing-stats`
- `.auth-card`
- `.landing-title`

Thêm breakpoint:

```css
@media (max-width: 768px) {
  .landing-layout {
    grid-template-columns: 1fr;
    padding: 1.25rem;
    gap: 2rem;
  }

  .landing-title {
    font-size: clamp(2.25rem, 12vw, 3rem);
  }

  .landing-stats {
    grid-template-columns: 1fr;
  }

  .auth-card {
    width: 100%;
    padding: 1.5rem;
  }
}
```

#### Dashboard header

- Tách header thành `DashboardHeader` component.
- Desktop giữ layout hiện tại.
- Tablet cho controls wrap thành hai hàng.
- Mobile hiển thị title + menu button; controls đặt trong collapsible panel hoặc bottom sheet.
- Đảm bảo mỗi control có label ngắn và vùng bấm tối thiểu 44×44px.

#### Tabs

- Dùng `overflow-x: auto`, `scroll-snap-type: x proximity` trên mobile.
- Không để tab co nhỏ tới mức chữ bị xuống dòng.
- Thêm gradient/fade ở cạnh phải để báo hiệu còn nội dung có thể cuộn.
- Đánh dấu tab hiện tại bằng `aria-current="page"`.

#### Articles

- Desktop tiếp tục dùng table.
- Dưới 768px chuyển sang card list với title, source, category, publish date và sentiment.
- Nếu vẫn giữ table, bọc bằng `.table-scroll-container` và cố định cột title.

#### Charts

- Dùng chiều cao responsive, ví dụ 240px mobile, 300px desktop.
- Giảm số tick trên mobile bằng `interval="preserveStartEnd"` hoặc tick formatter rút gọn.
- Giảm outer radius của pie/donut theo chiều rộng container.
- Entity labels dài cần truncate và hiển thị đầy đủ trong tooltip.

### 4.3. Tiêu chí nghiệm thu

- Không xuất hiện horizontal scrollbar ở viewport 320px, 375px, 768px và 1024px.
- Form đăng nhập hiển thị đầy đủ ở 320px.
- Header và tabs không che hoặc đẩy nội dung khỏi viewport.
- Chart không bị cắt legend, axis label hoặc tooltip.
- Articles đọc được mà không cần zoom trình duyệt.

---

## 5. UI-P0 — Loại bỏ dữ liệu và trạng thái hard-code

### 5.1. Vấn đề

Landing page đang hiển thị:

- `System Online & Processing`
- `150K+ Articles Processed`
- `Real-time Anomaly Alerts`

Các giá trị này trông như dữ liệu production nhưng không được lấy từ hệ thống thật. Admin dashboard cũng đang hiển thị `Healthy` cố định.

### 5.2. Cách sửa

#### API

Tạo hoặc mở rộng endpoint public summary:

```text
GET /api/v1/public/summary
```

Response đề xuất:

```json
{
  "status": "healthy",
  "articles_processed": 152340,
  "active_sources": 6,
  "alerts_last_24h": 3,
  "last_updated_at": "2026-09-27T10:30:00Z"
}
```

Nguồn dữ liệu:

- Status lấy từ readiness/dependency health.
- Article count lấy từ ClickHouse.
- Alert count lấy từ anomaly query hoặc alert table.
- Có cache TTL 30–60 giây để landing không gây tải lớn.

#### Frontend

- Tạo `usePublicSummary` hook.
- Trong lúc tải hiển thị skeleton hoặc `Checking system…`.
- Nếu endpoint lỗi, hiển thị `Status unavailable`, không tự suy diễn `Online`.
- Admin system health phải dựa trên `/health/ready` hoặc endpoint admin health.
- Hiển thị `Last updated` ở khu vực phù hợp.

### 5.3. Tiêu chí nghiệm thu

- Không còn số liệu vận hành cố định trong component.
- Khi ClickHouse/MongoDB lỗi, UI không hiển thị `Healthy`.
- Landing vẫn render được nếu summary API lỗi.
- Summary API được cache và không truy vấn warehouse trên mỗi render.

---

## 6. UI-P0 — Global filter phải nhất quán

### 6.1. Vấn đề

Source selector được hiển thị ở header cho mọi tab, nhưng hiện chỉ một số request sử dụng `selectedSource`. Các tab Articles, Entities và Network có thể không đổi khi người dùng chọn nguồn.

### 6.2. Cách sửa

#### Xác định filter contract

Tạo một cấu hình khả năng filter theo màn hình:

```ts
const TAB_FILTER_CAPABILITIES = {
  overview: { source: true, timeRange: true },
  sentiment: { source: true, timeRange: true },
  entities: { source: true, timeRange: true },
  network: { source: true, timeRange: true },
  articles: { source: true, timeRange: true, category: true },
  foryou: { source: false, timeRange: false },
};
```

#### Frontend

- Tạo helper xây query string bằng `URLSearchParams`.
- Mọi fetch function nhận một object filter thống nhất.
- Không tự ghép query bằng `replace("?", "&...")`.
- Nếu tab không hỗ trợ source filter, ẩn hoặc disable selector và thêm tooltip giải thích.
- Khi filter đổi:
  - Reset pagination về trang 1.
  - Cancel request cũ bằng `AbortController`.
  - Hiển thị loading state cục bộ.

#### Backend

- Bổ sung `source`, `time_range`, `category` cho entities và knowledge graph nếu chưa có.
- Đảm bảo filter được parameter hóa trong ClickHouse query.
- Thêm test xác nhận từng filter thực sự thay đổi SQL parameters.

### 6.3. Tiêu chí nghiệm thu

- Chọn một source làm thay đổi tất cả màn hình được đánh dấu hỗ trợ.
- Không có filter “trang trí” không tác động dữ liệu.
- Thay source ở Articles đưa người dùng về page 1.
- Request cũ không thể ghi đè dữ liệu của filter mới.

---

## 7. UI-P0 — Chuẩn hóa trạng thái dữ liệu

### 7.1. Vấn đề

`No data available` hiện có thể đồng nghĩa với:

- Request đang tải.
- API trả mảng rỗng hợp lệ.
- API lỗi.
- User chọn filter không có dữ liệu.

Điều này làm người dùng không biết cần chờ, đổi filter hay báo lỗi hệ thống.

### 7.2. Cách sửa

Tạo state model dùng chung:

```ts
type AsyncState<T> =
  | { status: "idle" }
  | { status: "loading"; previousData?: T }
  | { status: "success"; data: T; updatedAt: string }
  | { status: "empty"; data: T; updatedAt: string }
  | { status: "error"; message: string; requestId?: string; previousData?: T };
```

Tạo các component dùng chung:

- `ChartSkeleton`
- `EmptyState`
- `ErrorState`
- `StaleDataBadge`
- `LastUpdated`

Quy tắc:

- Loading lần đầu: skeleton.
- Refresh nền: giữ dữ liệu cũ và hiển thị indicator nhỏ.
- Empty: giải thích filter hiện tại không có dữ liệu và có nút clear filter.
- Error: có nút retry, request ID và thông báo ngắn.
- Dữ liệu cũ: hiển thị `Showing cached data` hoặc `Last updated ...`.

### 7.3. Tiêu chí nghiệm thu

- Mỗi chart có đủ bốn trạng thái loading/success/empty/error.
- API error không bị hiển thị như dữ liệu rỗng.
- Retry không reload toàn trang.
- Request ID được hiển thị hoặc có thể copy khi API trả lỗi.

---

## 8. UI-P1 — Chuẩn hóa chart context

### 8.1. Vấn đề

Chart hiện thiếu tên trục, đơn vị, thời gian, tổng mẫu và freshness.

### 8.2. Cách sửa

Tạo `ChartCard` component:

```tsx
<ChartCard
  title="Publication trend"
  description="Number of articles published per hour"
  timeRange="Last 24 hours"
  updatedAt={updatedAt}
  actions={<ExportButton />}
>
  {chart}
</ChartCard>
```

Mỗi chart phải khai báo:

- Câu hỏi mà chart trả lời.
- Time range.
- Unit của X/Y.
- Tổng số mẫu hoặc tổng bản ghi.
- Thời điểm cập nhật.
- Tooltip formatter.
- Empty/error behavior.

Tạo formatter dùng chung:

- `formatCompactNumber`: `1.2K`, `3.4M`.
- `formatPercent`: `32.5%`.
- `formatDuration`: `2.4 min`.
- `formatDateTime` theo locale.
- `formatSourceName` và `formatCategoryName`.

Y-axis cho dữ liệu đếm phải đặt `allowDecimals={false}`.

### 8.3. Tiêu chí nghiệm thu

- Không còn chart mà người dùng phải đoán đơn vị.
- Tooltip không hiển thị raw field name khó hiểu.
- Time range trên card khớp request API.
- Số lớn được format dễ đọc nhưng tooltip vẫn có giá trị chính xác.

---

## 9. UI-P1 — Publication Trend

### Hiện trạng

Area chart là lựa chọn phù hợp cho số bài theo giờ, nhưng 24 tick có thể dày trên mobile và đường `monotone` có thể tạo cảm giác dữ liệu liên tục hơn thực tế.

### Cách sửa

- Dùng `type="linear"` hoặc bar chart theo giờ nếu dữ liệu là bucket rời rạc.
- X-axis chỉ hiển thị một số tick đại diện trên mobile.
- Tooltip: `14:00 — 126 articles`.
- Y-axis: integer, tên `Articles`.
- Highlight giờ hiện tại hoặc điểm spike.
- Có option so sánh kỳ trước bằng một line nét đứt.
- Nếu có khoảng giờ bị thiếu, điền rõ `0` hoặc đánh dấu missing; không nối ngầm qua khoảng trống.

### Tiêu chí nghiệm thu

- Đọc được ở màn hình 320px.
- Không có tick chồng nhau.
- Phân biệt được giá trị 0 và dữ liệu bị thiếu.

---

## 10. UI-P1 — Category Distribution

### Hiện trạng

Vertical bar không tối ưu khi category có tên dài, và không thể hiện thứ tự rõ ràng nếu API không sort.

### Cách sửa

- Đổi thành horizontal bar.
- Sort giảm dần theo count.
- Giới hạn Top 8–10; gộp phần còn lại thành `Other` nếu cần.
- Hiển thị count và percentage ở cuối bar.
- Tooltip gồm category, count, tỷ lệ trên tổng.
- Dùng một hue nhất quán; không cần mỗi category một màu nếu màu không mang nghĩa.

### Tiêu chí nghiệm thu

- Label dài không bị cắt khó hiểu.
- Tổng percentage gần 100% sau khi tính rounding.
- Thứ tự luôn giảm dần.

---

## 11. UI-P1 — Sentiment charts

### 11.1. Overall Sentiment

#### Cách sửa

- Chuyển pie thành donut hoặc 100% stacked bar.
- Hiển thị tổng mẫu ở giữa donut.
- Label hiển thị cả tên và phần trăm, hoặc chỉ hiển thị trong legend nếu mobile.
- Chuẩn hóa giá trị sentiment từ API thành enum `positive`, `neutral`, `negative` trước khi render.

### 11.2. Sentiment by Source

#### Vấn đề

Raw counts làm nguồn có nhiều bài luôn có bar lớn hơn, nên khó so sánh cơ cấu sentiment.

#### Cách sửa

- Mặc định dùng 100% stacked bar để so sánh tỷ lệ.
- Cho phép toggle `Percentage | Count`.
- Tooltip hiển thị cả count, percentage và total source volume.
- Sort nguồn theo total volume hoặc negative percentage tùy mục tiêu.

### 11.3. Sentiment Timeline

#### Cách sửa

- Dùng line `linear` cho bucket thời gian.
- Có thể toggle series qua legend.
- Thêm brush hoặc zoom khi time range dài.
- Nếu mục tiêu là theo dõi tone, cân nhắc thêm đường `average sentiment score` thay vì chỉ ba dòng count.

### 11.4. Màu sắc

- Không dựa chỉ vào đỏ/xanh.
- Bổ sung icon, text hoặc line pattern:
  - Positive: xanh + `+`.
  - Neutral: xám + `●`.
  - Negative: cam/đỏ + `−`.
- Kiểm tra contrast tối thiểu WCAG AA.

### Tiêu chí nghiệm thu

- So sánh cơ cấu sentiment giữa hai nguồn không bị nhiễu bởi tổng volume.
- Chart vẫn hiểu được ở chế độ grayscale.
- Legend và tooltip dùng cùng thuật ngữ/ngôn ngữ.

---

## 12. UI-P1 — Entity và Keyword visualization

### 12.1. Top Entities

- Giữ horizontal bar vì phù hợp với ranking.
- Chỉ hiển thị Top N và cho chọn 10/20/50.
- Truncate label trên trục nhưng tooltip hiển thị đầy đủ.
- Bar có value label và entity type badge.
- Cho click entity để drill-down hoặc mở article list đã filter.

### 12.2. Word Cloud

#### Vấn đề

- Không so sánh chính xác được count.
- `Math.random()` trong render làm opacity thay đổi và có thể gây flicker/hydration inconsistency.
- Màu hiện tại mang tính trang trí, không biểu diễn biến dữ liệu.

#### Cách sửa ưu tiên

Phương án khuyến nghị: thay word cloud bằng ranked keyword bar chart.

Nếu vẫn giữ word cloud:

- Loại bỏ `Math.random()`.
- Tính size, opacity và màu hoàn toàn deterministic từ count/rank.
- Sort theo count.
- Tooltip hiển thị keyword, count và trend.
- Có bảng hoặc ranked list thay thế cho accessibility.

### 12.3. Entity Type Distribution

- Giảm số label trực tiếp trên pie/donut.
- Hiển thị percentage trong legend/tooltip.
- Dùng mapping màu cố định cho `PER`, `LOC`, `ORG`.
- Không gán màu theo index vì thứ tự dữ liệu có thể thay đổi giữa các request.

### 12.4. Sentiment by Entity

- Dùng horizontal 100% stacked bar cho entity name dài.
- Chỉ hiển thị Top N theo mention count.
- Tooltip có total mentions và tỷ lệ từng sentiment.

---

## 13. UI-P1 — Knowledge Graph

### 13.1. Điểm đang làm tốt

- Canvas tự resize bằng `ResizeObserver`.
- Node size dùng logarithmic scaling.
- Click node highlight hàng xóm và dim phần còn lại.
- Có tự động `zoomToFit`.

### 13.2. Vấn đề

- Không có legend cho màu PER/LOC/ORG.
- Không có nút reset, zoom-to-fit hoặc search.
- Không có panel chi tiết cho selected node.
- Label có thể chồng nhau khi graph lớn.
- Canvas graph không có nội dung thay thế cho screen reader.
- State dùng nhiều `any` và `Set` không có generic rõ ràng.

### 13.3. Cách sửa

- Thêm legend cố định cho entity types.
- Thêm controls:
  - Zoom in/out.
  - Fit graph.
  - Reset selection.
  - Search entity.
  - Filter entity type.
- Thêm side panel khi chọn node:
  - Entity name/type.
  - Mention count.
  - Số connections.
  - Top related entities.
  - Link tới filtered articles.
- Chỉ hiển thị label cho node quan trọng hoặc khi zoom đủ gần.
- Giới hạn số node/link theo Top N hoặc threshold.
- Cung cấp bảng dữ liệu quan hệ bên dưới canvas cho accessibility.
- Thay `any` bằng `GraphNode` và `GraphLink` interfaces.

### 13.4. Tiêu chí nghiệm thu

- Người dùng biết ý nghĩa từng màu mà không cần đoán.
- Có thể tìm và focus một entity.
- Graph với dữ liệu lớn không đóng băng UI.
- Có cách tiếp cận dữ liệu mà không cần thao tác canvas.

---

## 14. UI-P1 — Admin charts

### Vấn đề

- Các bar chart có hình thức gần giống nhau nhưng thiếu đơn vị và ngữ cảnh.
- `System Health` đang có nguy cơ hiển thị cố định.
- Một số metric cộng array ở frontend thay vì API trả aggregate rõ ràng.

### Cách sửa

- API trả metric summary đã aggregate và timestamp.
- Crawl latency:
  - Đơn vị `minutes` hoặc `seconds` rõ ràng.
  - Thêm target/SLA line.
  - Màu bar đổi khi vượt threshold.
- Volume charts:
  - Sort source giảm dần.
  - Hiển thị total và tỷ lệ.
- User role distribution:
  - Dùng donut hoặc compact stats; tránh pie nếu chỉ có hai số nhỏ.
- Health:
  - Lấy từ readiness endpoint.
  - Hiển thị từng dependency và latency.
  - Có trạng thái `healthy`, `degraded`, `unhealthy`, `unknown`.

---

## 15. UI-P2 — Accessibility

### 15.1. Vấn đề

- KPI card dùng `div onClick`.
- Label form chưa liên kết với input bằng `htmlFor/id`.
- Chuyển Login/Register dùng clickable `span`.
- Thiếu `focus-visible`.
- Chart SVG/canvas thiếu mô tả và data alternative.
- Animation không xét `prefers-reduced-motion`.

### 15.2. Cách sửa

- Dùng `<button>` cho KPI card, mode switch và auth switch.
- Thêm `id`, `name`, `autoComplete`, `htmlFor` cho form.
- Error message dùng `role="alert"` và `aria-live="polite"`.
- Tabs dùng semantics phù hợp:
  - `role="tablist"`
  - `role="tab"`
  - `aria-selected`
  - keyboard ArrowLeft/ArrowRight nếu triển khai tab chuẩn.
- Bổ sung global focus style:

```css
:focus-visible {
  outline: 3px solid var(--accent-blue);
  outline-offset: 3px;
}
```

- Mỗi chart có heading, description và bảng dữ liệu thay thế có thể mở rộng.
- Không chỉ dùng màu để phân biệt series.
- Thêm:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

### 15.3. Tiêu chí nghiệm thu

- Toàn bộ luồng login và dashboard dùng được chỉ bằng bàn phím.
- Không có focus trap hoặc focus indicator bị ẩn.
- Axe/Lighthouse không có lỗi accessibility nghiêm trọng.
- Chart có text/table alternative.

---

## 16. UI-P2 — Ngôn ngữ và nội dung

### 16.1. Vấn đề

UI trộn tiếng Anh và tiếng Việt trong cùng màn hình.

### 16.2. Cách sửa

Chọn một trong hai hướng:

1. Tiếng Việt làm mặc định, phù hợp nguồn tin và người dùng mục tiêu.
2. Triển khai i18n với `vi` và `en`.

Khuyến nghị tạo dictionary đơn giản trước:

```ts
const messages = {
  vi: {
    overview: "Tổng quan",
    noData: "Không có dữ liệu",
    retry: "Thử lại",
  },
  en: {
    overview: "Overview",
    noData: "No data available",
    retry: "Retry",
  },
};
```

Chuẩn hóa:

- Chart titles.
- Tooltip labels.
- Empty/error messages.
- KPI labels.
- Date/number format.
- Button labels.

Không dịch tên nguồn hoặc proper noun.

---

## 17. UI-P2 — Design system và maintainability

### 17.1. Vấn đề

- Nhiều inline styles lặp lại.
- Tooltip style, chart colors và panel sizes được khai báo nhiều nơi.
- Component props còn nhiều `any`.
- Chart colors dùng cả CSS variables và hex rải rác.

### 17.2. Cách sửa

Tạo các module:

```text
frontend/src/components/ui/
  ChartCard.tsx
  EmptyState.tsx
  ErrorState.tsx
  LoadingSkeleton.tsx
  MetricCard.tsx
  FilterBar.tsx

frontend/src/lib/
  api.ts
  chart-theme.ts
  formatters.ts
  filters.ts
  types.ts
```

Tạo chart theme:

```ts
export const chartTheme = {
  grid: "rgba(255,255,255,0.1)",
  axis: "#94a3b8",
  tooltipBackground: "rgba(30,41,59,0.96)",
  positive: "#10b981",
  neutral: "#94a3b8",
  negative: "#f97316",
};
```

Tạo types theo API response và xóa dần `any` khỏi:

- `page.tsx`
- `OverviewNewsView`
- `OverviewSocialView`
- `SentimentView`
- `EntitiesView`
- `AdminView`
- `KnowledgeGraph`

Ưu tiên CSS classes hoặc CSS modules cho style ổn định; chỉ giữ inline style cho giá trị thật sự động.

---

## 18. Hiệu năng và rendering

### Vấn đề

- Dashboard poll mỗi 15 giây và có thể tạo request trùng khi tab/filter đổi.
- Word cloud dùng random trong render.
- Knowledge Graph có thể nặng khi số node/link lớn.
- Các component chart lớn nằm trong cùng client bundle.

### Cách sửa

- Dùng `AbortController` cho request cũ.
- Pause polling khi tab bị ẩn bằng Page Visibility API.
- Chỉ poll endpoint của tab đang active.
- Không poll khi SSE đã cung cấp cùng loại dữ liệu realtime.
- Dynamic import các view/graph nặng.
- Memoize data transformations.
- Loại bỏ randomness trong render.
- Giới hạn graph dataset từ API và hỗ trợ progressive loading.
- Cân nhắc React Query/SWR nếu muốn chuẩn hóa cache, retry và stale state.

### Tiêu chí nghiệm thu

- Không có request trùng không cần thiết khi chuyển tab nhanh.
- Dashboard nền không tiếp tục poll mạnh khi browser tab hidden.
- Graph Top 100 nodes tương tác mượt trên máy phổ thông.

---

## 19. Kế hoạch test

### 19.1. Automated checks

Chạy bắt buộc:

```bash
cd frontend
npm run lint
./node_modules/.bin/tsc --noEmit
npm run build
```

Backend:

```bash
pytest -q
```

### 19.2. Component tests

Thêm test cho:

- Loading/empty/error/success của `ChartCard`.
- Filter query builder.
- Mobile articles card.
- Deterministic keyword visualization.
- Percentage normalization của sentiment.
- Locale formatters.

### 19.3. End-to-end scenarios

1. Login thành công và thất bại.
2. Chuyển News/Social/Admin.
3. Đổi source và xác nhận request/chart cập nhật.
4. Đổi tab nhanh, không bị stale response ghi đè.
5. API offline hiển thị error state và retry.
6. Empty filter có nút clear filter.
7. Export CSV/PDF giữ đúng dữ liệu và layout.
8. Knowledge Graph search/select/reset.

### 19.4. Responsive matrix

Kiểm tra tối thiểu:

| Viewport | Mục tiêu |
|---|---|
| 320×568 | Mobile nhỏ |
| 375×812 | Mobile phổ biến |
| 768×1024 | Tablet portrait |
| 1024×768 | Tablet landscape |
| 1366×768 | Laptop |
| 1440×900 | Desktop |

### 19.5. Accessibility checks

- Keyboard-only navigation.
- Screen reader smoke test.
- Axe hoặc Lighthouse accessibility.
- Contrast checker.
- `prefers-reduced-motion`.
- Zoom trình duyệt 200%.

### 19.6. Visual regression

Chụp snapshot cho:

- Landing login/register.
- Dashboard overview news/social.
- Sentiment.
- Entities.
- Network empty/loaded/selected.
- Articles desktop/mobile.
- Alerts empty/error/active.

---

## 20. Kế hoạch triển khai theo pull request

### PR 1 — Responsive foundation

- Refactor landing styles.
- Responsive header/tabs/table.
- Mobile chart sizing.
- Không thay đổi logic dữ liệu.

### PR 2 — Truthful status and async states

- Public summary API.
- Real health status.
- Loading/empty/error/stale components.
- Last updated metadata.

### PR 3 — Filter consistency

- Filter capability map.
- Query builder.
- Backend filter support.
- Abort stale requests.
- Filter tests.

### PR 4 — Core chart improvements

- Publication trend.
- Category ranking.
- Sentiment normalized views.
- Shared tooltip/formatters/theme.

### PR 5 — Entities and graph

- Deterministic keyword visualization.
- Entity chart improvements.
- Graph legend, controls, search và detail panel.

### PR 6 — Accessibility and i18n

- Semantic controls.
- Keyboard navigation.
- Reduced motion.
- Chart data alternatives.
- Chuẩn hóa ngôn ngữ.

### PR 7 — Performance and regression coverage

- Dynamic imports.
- Polling visibility behavior.
- Memoization/caching.
- E2E và visual regression suite.

---

## 21. Definition of Done

Kế hoạch được xem là hoàn thành khi:

- Không có horizontal overflow tại các viewport mục tiêu.
- Không còn status hoặc metric production bị hard-code.
- Mọi filter hiển thị đều có tác dụng rõ ràng.
- Mọi chart có loading, empty, error, success và freshness state.
- Chart có unit, time range và tooltip có ý nghĩa.
- Sentiment có count/percentage rõ ràng và không phụ thuộc chỉ vào đỏ/xanh.
- Word cloud deterministic hoặc được thay bằng chart so sánh chính xác hơn.
- Knowledge Graph có legend, controls, node details và data alternative.
- Luồng chính dùng được bằng keyboard.
- ESLint có 0 warning/error.
- TypeScript check thành công.
- Frontend production build thành công.
- Backend test và filter tests thành công.
- Responsive, accessibility và visual regression matrix đều đạt.

## 22. Kết quả kỳ vọng

Sau khi hoàn thành, NewsPulse vẫn giữ được phong cách dark/glass hiện tại nhưng sẽ:

- Đáng tin hơn vì mọi trạng thái đều phản ánh dữ liệu thật.
- Dễ hiểu hơn vì chart có context và đơn vị rõ ràng.
- Dễ dùng hơn trên mobile và bằng bàn phím.
- Ít gây hiểu nhầm khi filter, request hoặc dependency gặp lỗi.
- Dễ mở rộng hơn nhờ component, types và chart theme dùng chung.
