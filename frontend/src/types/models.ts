export interface User {
  id: string;
  email: string;
  username: string;
  full_name: string | null;
  avatar_url: string | null;
  role: "user" | "admin";
  is_active: boolean;
  is_verified: boolean;
}

export interface UserUpdate {
  full_name?: string | null;
  avatar_url?: string | null;
}

export interface UserPreferences {
  preferred_categories: string[];
  preferred_sources: string[];
  preferred_languages: string[];
  preferred_regions: string[];
  notification_enabled: boolean;
  dark_mode: boolean;
  email_digest_frequency: string;
}

export interface Category {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  parent_id: string | null;
  color: string | null;
  article_count?: string;
}

export interface Source {
  id: string;
  name: string;
  url: string;
  feed_url: string | null;
  source_type: string;
  language: string;
  country: string | null;
  is_active: boolean;
  reputation_score: number;
  fetch_interval_minutes: number;
}

export interface Tag {
  id: string;
  name: string;
  slug: string;
  article_count?: string;
}

export interface ArticleList {
  id: string;
  title: string;
  slug: string;
  summary: string | null;
  source_name: string | null;
  category_name: string | null;
  image_url: string | null;
  published_at: string | null;
  sentiment: string | null;
  credibility_score: number | null;
  tags: string[];
  reason?: string | null;
}

export interface Article {
  id: string;
  title: string;
  slug: string;
  url: string;
  source_id: string | null;
  category_id: string | null;
  event_id: string | null;
  summary: string | null;
  content: string | null;
  author: string | null;
  published_at: string | null;
  language: string;
  sentiment: string | null;
  sentiment_score: number | null;
  keywords: string | null;
  entities: string | null;
  credibility_score: number | null;
  credibility_factors: string | null;
  image_url: string | null;
  view_count: string;
  is_verified: boolean;
  source_name: string | null;
  category_name: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface Event {
  id: string;
  title: string;
  slug: string;
  summary: string | null;
  description: string | null;
  category_id: string | null;
  start_date: string | null;
  end_date: string | null;
  article_count: string;
  importance_score: number;
  timeline: string | null;
  is_active: boolean;
  created_at: string;
}

export interface EventArticle {
  id: string;
  title: string;
  slug: string;
  summary: string | null;
  published_at: string | null;
  source_name: string | null;
}

export interface Bookmark {
  id: string;
  user_id: string;
  article_id: string;
  created_at: string;
  title: string | null;
  slug: string | null;
  url: string | null;
  summary: string | null;
  image_url: string | null;
  source_name: string | null;
  published_at: string | null;
}

export interface ReadingHistoryItem {
  id: string;
  article_id: string;
  read_duration_seconds: number;
  scroll_depth: number;
  created_at: string;
  title: string | null;
  slug: string | null;
  url: string | null;
  summary: string | null;
  source_name: string | null;
  image_url: string | null;
}

export interface ReadingHistoryList {
  items: ReadingHistoryItem[];
  total: number;
}

export interface Notification {
  id: string;
  title: string;
  body: string | null;
  notification_type: string;
  reference_id: string | null;
  reference_type: string | null;
  is_read: boolean;
  created_at: string;
}

export interface NotificationList {
  notifications: Notification[];
  unread_count: number;
}

export interface SearchResultItem {
  id: string;
  title: string;
  slug: string;
  summary: string | null;
  url: string;
  source_name: string | null;
  category_name: string | null;
  published_at: string | null;
  score: number;
  highlights?: Record<string, unknown> | null;
}

export interface SearchResponse {
  query: string;
  total: number;
  page: number;
  page_size: number;
  results: SearchResultItem[];
  facets: Record<string, unknown> | null;
}

export interface ChatSource {
  title: string;
  url: string;
  snippet: string;
  relevance_score: number;
}

export interface ChatResponse {
  answer: string;
  sources: ChatSource[];
  conversation_id: string;
  confidence: number;
}

export interface ChatMessageItem {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: ChatSource[] | null;
  created_at: string;
}

export interface ConversationItem {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationListResponse {
  conversations: ConversationItem[];
  total: number;
}

export interface Recommendation {
  id: string;
  title: string;
  slug: string;
  summary: string | null;
  source_name: string | null;
  category_name: string | null;
  image_url: string | null;
  published_at: string | null;
  reason: string | null;
  score: number;
}

export interface AnalyticsOverview {
  total_users: number;
  active_users_today: number;
  total_articles: number;
  articles_today: number;
  total_sources: number;
  active_sources: number;
  total_searches: number;
  total_events: number;
}

export interface UserActivityStats {
  date: string;
  active_users: number;
  page_views: number;
  searches: number;
  bookmarks: number;
}

export interface DailyCount {
  date: string;
  count: number;
}

export interface CategoryStats {
  category: string | null;
  article_count: number;
}

export interface SourceStats {
  source: string;
  article_count: number;
  avg_credibility: number;
}

export interface SentimentStats {
  sentiment: string;
  count: number;
}

export interface AnalyticsEventItem {
  id: string;
  event_type: string;
  user_id: string | null;
  article_id: string | null;
  value: number | null;
  timestamp: string;
  metadata: Record<string, unknown>;
}

export interface AnalyticsEventList {
  events: AnalyticsEventItem[];
  total: number;
}
