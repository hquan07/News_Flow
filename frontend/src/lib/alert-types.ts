// Types for Alert Drill-down feature

export interface AlertDataQuality {
  title_available: boolean;
  content_available?: boolean;
  url_available?: boolean;
}

export interface ViralPostAlertSummary {
  post_id: string;
  source: string;
  title: string;
  interactions: number;
  sentiment_label?: string;
  publish_time?: string;
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
}

export interface SpikeAlert {
  hour_slot: string;
  article_count: number;
  avg_count: number;
}
