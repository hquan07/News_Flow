export const mockData = {
  overview: {
    total_articles: 154320,
    active_sources: 42,
    top_category: "technology",
    avg_latency_min: 2.5,
    publication_trend: Array.from({ length: 24 }).map((_, i) => ({
      hour: `${String(i).padStart(2, '0')}:00`,
      count: Math.floor(Math.random() * 500) + 200
    })),
    category_dist: [
      { category: "technology", count: 45000 },
      { category: "business", count: 32000 },
      { category: "sports", count: 28000 },
      { category: "entertainment", count: 25000 },
      { category: "politics", count: 24320 },
    ]
  },
  socialOverview: {
    total_posts: 890432,
    active_sources: 4,
    avg_engagement: 1450.5,
    top_category: "viral",
    publication_trend: Array.from({ length: 24 }).map((_, i) => ({
      hour: `${String(i).padStart(2, '0')}:00`,
      count: Math.floor(Math.random() * 2000) + 1000
    })),
    category_dist: [
      { category: "viral", count: 350000 },
      { category: "discussion", count: 280000 },
      { category: "news", count: 150000 },
      { category: "memes", count: 110432 },
    ]
  },
  sentimentDist: {
    data: [
      { sentiment: "positive", count: 65000, percentage: 42 },
      { sentiment: "neutral", count: 58000, percentage: 38 },
      { sentiment: "negative", count: 31320, percentage: 20 },
    ]
  },
  sentimentTimeline: {
    data: Array.from({ length: 24 }).map((_, i) => ({
      hour: `${String(i).padStart(2, '0')}:00`,
      positive: Math.floor(Math.random() * 300) + 100,
      neutral: Math.floor(Math.random() * 200) + 100,
      negative: Math.floor(Math.random() * 150) + 50,
    }))
  },
  sentimentSources: {
    data: [
      { source: "VnExpress", positive: 45, neutral: 40, negative: 15 },
      { source: "Tuổi Trẻ", positive: 38, neutral: 45, negative: 17 },
      { source: "Thanh Niên", positive: 50, neutral: 35, negative: 15 },
      { source: "Dân Trí", positive: 42, neutral: 42, negative: 16 },
    ]
  },
  socialSentiment: {
    sentiment_distribution: [
      { sentiment: "positive", count: 350000, percentage: 39 },
      { sentiment: "neutral", count: 200000, percentage: 23 },
      { sentiment: "negative", count: 340432, percentage: 38 },
    ],
    sentiment_timeline: Array.from({ length: 24 }).map((_, i) => ({
      hour: `${String(i).padStart(2, '0')}:00`,
      positive: Math.floor(Math.random() * 1500) + 500,
      neutral: Math.floor(Math.random() * 800) + 300,
      negative: Math.floor(Math.random() * 1200) + 400,
    })),
    sentiment_by_source: [
      { source: "Facebook", positive: 40, neutral: 20, negative: 40 },
      { source: "TikTok", positive: 55, neutral: 30, negative: 15 },
      { source: "Voz", positive: 15, neutral: 25, negative: 60 },
      { source: "Reddit", positive: 35, neutral: 45, negative: 20 },
    ]
  },
  socialDebates: {
    top_debates: [
      { topic: "Giá vàng SJC hôm nay", comments_count: 15420, controversy_score: 8.5 },
      { topic: "Tuyển VN thay HLV trưởng", comments_count: 12350, controversy_score: 9.2 },
      { topic: "Luật Giao thông mới", comments_count: 9840, controversy_score: 7.8 },
      { topic: "Review iPhone 16", comments_count: 8520, controversy_score: 6.5 },
    ]
  },
  entityDist: [
    { type: "PERSON", count: 12500 },
    { type: "ORG", count: 18400 },
    { type: "LOC", count: 9600 },
    { type: "PRODUCT", count: 5400 },
    { type: "EVENT", count: 4200 },
  ],
  entitySentiment: [
    { entity: "Apple", type: "ORG", positive: 85, neutral: 10, negative: 5 },
    { entity: "Trí tuệ nhân tạo", type: "CONCEPT", positive: 65, neutral: 25, negative: 10 },
    { entity: "Hà Nội", type: "LOC", positive: 45, neutral: 40, negative: 15 },
    { entity: "VinFast", type: "ORG", positive: 55, neutral: 25, negative: 20 },
    { entity: "Elon Musk", type: "PERSON", positive: 40, neutral: 30, negative: 30 },
  ],
  trending: [
    { keyword: "AI", count: 1540, velocity: 2.5 },
    { keyword: "Bất động sản", count: 1250, velocity: 1.8 },
    { keyword: "Giá vàng", count: 1100, velocity: 3.2 },
    { keyword: "Lãi suất", count: 950, velocity: -0.5 },
    { keyword: "Xe điện", count: 820, velocity: 1.2 },
  ],
  entities: [
    { name: "Apple", type: "ORG", frequency: 15200 },
    { name: "Hà Nội", type: "LOC", frequency: 12300 },
    { name: "Việt Nam", type: "LOC", frequency: 11500 },
    { name: "Samsung", type: "ORG", frequency: 9400 },
    { name: "Chính phủ", type: "ORG", frequency: 8200 },
    { name: "TP.HCM", type: "LOC", frequency: 7800 },
    { name: "AI", type: "CONCEPT", frequency: 6500 },
  ],
  knowledgeGraph: {
    nodes: [
      { id: "Apple", group: 1, type: "ORG", radius: 25 },
      { id: "iPhone 16", group: 2, type: "PRODUCT", radius: 15 },
      { id: "Tim Cook", group: 3, type: "PERSON", radius: 12 },
      { id: "Samsung", group: 1, type: "ORG", radius: 20 },
      { id: "Galaxy S24", group: 2, type: "PRODUCT", radius: 15 },
      { id: "AI", group: 4, type: "CONCEPT", radius: 22 },
      { id: "Microsoft", group: 1, type: "ORG", radius: 24 },
      { id: "OpenAI", group: 1, type: "ORG", radius: 18 },
      { id: "Việt Nam", group: 5, type: "LOC", radius: 30 },
      { id: "Hà Nội", group: 5, type: "LOC", radius: 20 },
      { id: "Đầu tư", group: 6, type: "EVENT", radius: 18 },
    ],
    links: [
      { source: "Apple", target: "iPhone 16", value: 5 },
      { source: "Apple", target: "Tim Cook", value: 4 },
      { source: "Apple", target: "AI", value: 3 },
      { source: "Samsung", target: "Galaxy S24", value: 5 },
      { source: "Samsung", target: "AI", value: 4 },
      { source: "Microsoft", target: "OpenAI", value: 5 },
      { source: "Microsoft", target: "AI", value: 5 },
      { source: "OpenAI", target: "AI", value: 5 },
      { source: "Apple", target: "Việt Nam", value: 2 },
      { source: "Samsung", target: "Việt Nam", value: 4 },
      { source: "Việt Nam", target: "Hà Nội", value: 5 },
      { source: "Việt Nam", target: "Đầu tư", value: 3 },
    ]
  },
  articles: {
    data: Array.from({ length: 20 }).map((_, i) => ({
      title: `[Mock] Bài viết mẫu số ${i + 1} về công nghệ và đời sống`,
      url: "#",
      source: ["VnExpress", "Tuổi Trẻ", "Thanh Niên", "Dân Trí"][i % 4],
      category: ["technology", "business", "sports", "general"][i % 4],
      publication_date: new Date(Date.now() - i * 3600000).toISOString(),
      sentiment_score: Math.random() * 2 - 1
    })),
    total: 100,
    page: 1,
    page_size: 20
  }
};
