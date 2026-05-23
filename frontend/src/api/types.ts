export type ArticleStatus = 'draft' | 'generated' | 'sent_to_wechat' | 'failed'
export type TaskStatus = 'queued' | 'running' | 'succeeded' | 'failed'
export type TenantStatus = 'active' | 'disabled'

export interface Tenant {
  id: number
  name: string
  slug: string
  status: TenantStatus
}

export interface ContentProfile {
  tenant_id: number
  publication_name: string
  workspace_title: string
  title_prefix: string
  content_domain: string
  editor_persona: string
  audience: string
  article_style: string
  grouping_mode: 'regional' | 'none'
  categories_json: string
  image_style: string
}

export interface ContentProfileUpdate {
  publication_name?: string
  workspace_title?: string
  title_prefix?: string
  content_domain?: string
  editor_persona?: string
  audience?: string
  article_style?: string
  grouping_mode?: 'regional' | 'none'
  categories_json?: string
  image_style?: string
}

export interface WeChatAccount {
  tenant_id: number
  app_id: string
  app_secret_configured: boolean
}

export interface WeChatAccountUpdate {
  app_id?: string
  app_secret?: string
}

export interface ContentGroup {
  id: number
  tenant_id: number
  group_key: string
  name: string
  content_mode: 'news' | 'knowledge' | 'analysis'
  source_urls: string
  candidate_limit: number
  article_min: number
  article_target: number
  article_max: number
  position: number
  enabled: boolean
}

export type ContentGroupUpdate = Partial<Omit<ContentGroup, 'id' | 'tenant_id'>>

export interface LayoutSettings {
  tenant_id: number
  template_name: string
  primary_color: string
  accent_color: string
  text_color: string
  heading_color: string
  body_font_size: number
  heading_font_size: number
  line_height: string
  section_spacing: number
  image_radius: number
  show_group_heading: boolean
  show_source: boolean
  show_editor_note: boolean
}

export interface LayoutSettingsUpdate {
  template_name?: string
  primary_color?: string
  accent_color?: string
  text_color?: string
  heading_color?: string
  body_font_size?: number
  heading_font_size?: number
  line_height?: string
  section_spacing?: number
  image_radius?: number
  show_group_heading?: boolean
  show_source?: boolean
  show_editor_note?: boolean
}

export interface PublishingSettings {
  tenant_id: number
  daily_publish_enabled: boolean
  publish_frequency: 'daily' | 'weekly' | 'monthly'
  publish_weekday: number
  publish_month_day: number
  publish_time_hour: number
  publish_time_minute: number
  auto_send_wechat_draft: boolean
  generate_article_images: boolean
  max_article_images: number
  min_article_images: number
  news_source_urls: string
  news_per_source_limit: number
  news_lookback_hours: number
  max_news_candidates: number
  dedup_lookback_days: number
  dedup_direct_similarity: string
  dedup_review_similarity: string
  dedup_enable_llm_review: boolean
  article_news_limit: number
  article_news_lookback_hours: number
}

export type PublishingSettingsUpdate = Partial<Omit<PublishingSettings, 'tenant_id'>>

export interface WorkspaceConfig {
  profile: ContentProfile
  wechat: WeChatAccount
  layout: LayoutSettings
  publishing: PublishingSettings
  content_groups: ContentGroup[]
}

export interface WorkspaceConfigUpdate {
  profile?: ContentProfileUpdate
  wechat?: WeChatAccountUpdate
  layout?: LayoutSettingsUpdate
  publishing?: PublishingSettingsUpdate
  content_groups?: ContentGroupUpdate[]
}

export interface NewsItem {
  id: number
  tenant_id: number
  title: string
  source: string
  url: string
  published_at: string
  summary: string
  category: string
  region: string
  group_key: string
  importance_score: number
  selected: boolean
  created_at: string
}

export interface Article {
  id: number
  tenant_id: number
  title: string
  intro: string
  content_html: string
  cover_image_url: string
  status: ArticleStatus
  wechat_draft_id: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface ArticleUpdate {
  title: string
  intro: string
  cover_image_url: string
  content_html: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface OperationTask {
  id: string
  tenant_id: number
  task_type: string
  status: TaskStatus
  message: string
  article_id: number | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface OperationTaskEvent {
  id: number
  tenant_id: number
  task_id: string
  step_name: string
  status: string
  message: string
  payload_json: string | null
  created_at: string
}
