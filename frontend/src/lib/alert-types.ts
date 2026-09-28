// Types for Alert Drill-down feature

export interface AlertDataQuality {
  title_available: boolean;
  content_available?: boolean;
  url_available?: boolean;
  synthetic?: boolean;
}

export interface ViralPostAlertSummary {
  post_id: string;
  source: string;
  title: string;
  interactions: number;
  sentiment_label?: string;
  publish_time?: string;
  threshold?: number;
  alert_reason?: string;
  data_quality: AlertDataQuality;
}

export interface ViralPostDetail {
  post_id: string;
  source: string;
  title: string;
  content: string;
  excerpt: string;
  url: string;
  author: string;
  like_count: number;
  reply_count: number;
  interactions: number;
  upvote_ratio: number;
  sentiment_score: number;
  sentiment_label: string;
  top_comments: string[];
  publish_time?: string;
  crawled_at?: string;
  data_quality: AlertDataQuality;
}

export interface SocialCrisisAlert {
  source: string;
  total_posts: number;
  negative_posts: number;
  negative_pct: number;
  negative_pct_threshold?: number;
  min_posts_threshold?: number;
  alert_reason?: string;
}

export interface SpikeAlert {
  hour_slot: string;
  article_count: number;
  avg_count: number;
  std_count?: number;
  z_score?: number;
  threshold?: number;
  alert_reason?: string;
}

export interface SocialCrisisDetail extends SocialCrisisAlert {
  sentiment_distribution: Array<{ label: string; count: number }>;
  top_negative_posts: ViralPostAlertSummary[];
}

export interface VolumeArticle {
  article_id: string;
  title: string;
  url: string;
  source: string;
  category: string;
  publish_time: string;
}

export interface VolumeSpikeDetail extends SpikeAlert {
  window_end: string;
  std_count: number;
  z_score: number;
  threshold: number;
  is_active: boolean;
  alert_reason: string;
  articles: VolumeArticle[];
}

export interface ArticleAlertFilter {
  publishedFrom: string;
  publishedTo: string;
  label: string;
}
