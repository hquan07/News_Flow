export interface SocialPostPerformance {
  post_id: string;
  source: string;
  author?: string;
  title?: string;
  content?: string;
  like_count: number;
  reply_count: number;
  interactions: number;
  sentiment_label?: string;
  publish_time?: string;
}

export interface SocialContentPerformanceData {
  summary: {
    total_posts: number;
    total_interactions: number;
    avg_interactions_per_post: number;
    high_performing_posts: number;
  };
  platform_performance: Array<{
    source: string;
    post_count: number;
    total_likes: number;
    total_replies: number;
    total_interactions: number;
    avg_interactions_per_post: number;
  }>;
  top_posts: SocialPostPerformance[];
  time_range: string;
}

export interface SocialAudienceData {
  summary: {
    total_posts: number;
    unique_contributors: number;
    active_platforms: number;
    avg_posts_per_contributor: number;
    peak_hour: number | null;
  };
  activity_by_hour: Array<{
    hour: number;
    post_count: number;
    active_contributors: number;
    interactions: number;
  }>;
  contributor_segments: Array<{
    segment: string;
    contributors: number;
  }>;
  platform_audience: Array<{
    source: string;
    post_count: number;
    contributors: number;
    interactions: number;
  }>;
  time_range: string;
  methodology: string;
}

export interface SocialTopicsData {
  summary: {
    unique_hashtags: number;
    hashtag_mentions: number;
    tracked_topics: number;
    topic_interactions: number;
  };
  hashtags: Array<{
    hashtag: string;
    mentions: number;
    interactions: number;
  }>;
  top_topics: Array<{
    topic: string;
    source: string;
    post_count: number;
    interactions: number;
    sentiment_score: number;
  }>;
  time_range: string;
}

export interface SocialAlertSignalsData {
  summary: {
    active_alerts: number;
    crisis_sources: number;
    viral_posts: number;
    negative_posts: number;
  };
  source_risks: Array<{
    source: string;
    total_posts: number;
    negative_posts: number;
    negative_pct: number;
    interactions: number;
    active: boolean;
  }>;
  viral_posts: SocialPostPerformance[];
  thresholds: {
    negative_pct: number;
    min_posts: number;
    interactions: number;
  };
  window: string;
  generated_at: string;
}
