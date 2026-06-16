export type ArticleStatus = 'draft' | 'generated' | 'sent_to_wechat' | 'failed'
export type TaskStatus = 'queued' | 'running' | 'cancel_requested' | 'cancelled' | 'succeeded' | 'failed'
export type TenantStatus = 'active' | 'disabled'
export type SocialPlatform = 'xhs' | 'douyin'

export interface Tenant {
  id: number
  name: string
  slug: string
  status: TenantStatus
}

export interface CurrentUser {
  username: string
  is_admin: boolean
  tenant_id: number | null
}

export interface AdminUser {
  id: number
  username: string
  is_admin: boolean
  tenant_id: number | null
  status: string
  created_at: string
  updated_at: string
}

export interface AdminUserCreate {
  username: string
  password: string
  tenant_name: string
  tenant_slug?: string
  is_admin: boolean
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

export interface BloggerProfile {
  id: number
  tenant_id: number
  platform: string
  external_id: string | null
  display_name: string
  homepage_url: string
  avatar_url: string
  follower_count: number
  niche: string
  description: string
  is_favorite: boolean
  sample_count: number
  last_distilled_at: string | null
  created_at: string
  updated_at: string
}

export interface BloggerProfileCreate {
  platform?: SocialPlatform
  external_id?: string | null
  display_name: string
  homepage_url: string
  avatar_url?: string
  follower_count?: number
  niche: string
  description: string
}

export interface BloggerProfileUpdate {
  external_id?: string | null
  display_name?: string
  homepage_url?: string
  avatar_url?: string
  follower_count?: number
  niche?: string
  description?: string
}

export interface BloggerSearchResult {
  platform: SocialPlatform
  external_id: string
  display_name: string
  homepage_url: string
  avatar_url: string
  description: string
  follower_count: number
  raw: Record<string, unknown>
}

export interface BloggerDistillRequest {
  collection_run_id: number
  mode?: string
}

export interface BloggerCollectRequest {
  sample_limit: number
  comments_per_post: number
  asr_enabled: boolean
}

export interface CollectEstimate {
  sample_limit: number
  comments_per_post: number
  request_estimate: number
  cost_usd: number
  cost_usd_min: number
  cost_usd_max: number
}

export interface BloggerPost {
  id: number
  tenant_id: number
  blogger_id: number
  platform: string
  external_id: string
  url: string
  title: string
  body_text: string
  content_type: string
  hashtags_json: string
  cover_url: string
  media_urls_json: string
  transcript_text: string
  asr_status: string
  asr_error: string
  published_at: string | null
  like_count: number
  favorite_count: number
  comment_count: number
  sampled_comment_count?: number
  share_count: number
  score: number
  comments_json: string
  created_at: string
  updated_at: string
}

export interface BloggerDistillationRun {
  id: number
  tenant_id: number
  blogger_id: number
  collection_run_id: number | null
  task_id: string | null
  status: string
  sample_count: number
  hot_post_count: number
  comment_count: number
  tikhub_request_count: number
  tikhub_estimated_cost_usd: number
  tikhub_cost_min_usd: number
  tikhub_cost_max_usd: number
  report_json: string
  report_html: string
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface BloggerCollectionRun {
  id: number
  tenant_id: number
  blogger_id: number
  task_id: string | null
  status: string
  sample_limit: number
  comments_per_post: number
  asr_enabled: boolean
  post_count: number
  hot_post_count: number
  comment_count: number
  tikhub_request_count: number
  tikhub_estimated_cost_usd: number
  tikhub_cost_min_usd: number
  tikhub_cost_max_usd: number
  summary_json: string
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface BloggerSkill {
  id: number
  tenant_id: number
  blogger_id: number
  run_id: number
  name: string
  description: string
  skill_markdown: string
  status: string
  created_at: string
  updated_at: string
}

export type XhsPublishContentType = 'text_note' | 'image_note' | 'spoken_script' | 'video_script'
export type XhsImageCountMode = 'auto' | 'manual'

export interface XhsPublishPackageCreate {
  skill_id: number
  content_type: XhsPublishContentType
  topic: string
  target_audience: string
  content_goal: string
  keywords: string
  image_count_mode: XhsImageCountMode
  requested_image_count: number | null
}

export interface XhsPublishPackageDraft {
  tenant_id: number
  blogger_id: number
  skill_id: number
  content_type: XhsPublishContentType
  topic: string
  target_audience: string
  content_goal: string
  keywords: string
  image_count_mode: XhsImageCountMode
  requested_image_count: number | null
  title: string
  body_text: string
  hashtags_json: string
  cover_text: string
  image_plan_json: string
  image_urls_json: string
  script_json: string
  status: string
  error_message: string | null
  // 过程与评判(随草稿透传,不入库)。
  synthesis?: SynthesisTrace
  benchmark?: BenchmarkComparison
  quality?: { score?: number; grade?: string; issues?: string[] }
  compliance?: ComplianceResult
}

export interface ComplianceHit {
  word: string
  field: string
  category: string
}

export interface ComplianceResult {
  enabled?: boolean
  passed: boolean
  hits: ComplianceHit[]
}

export interface SynthesisAttempt {
  attempt: number
  score: number | null
  passed: boolean
  issues: string[]
  revised_with: string
}

export interface SynthesisTrace {
  task: string
  revisions: number
  final_attempt: number
  final_score: number | null
  final_passed: boolean
  attempts: SynthesisAttempt[]
}

export interface BenchmarkComparison {
  title_fit?: string
  language_fit?: string
  formula_fit?: string
  gaps?: string[]
  summary?: string
}

export type XhsPublishPackageSave = XhsPublishPackageDraft

export interface AccountAuditCreate {
  platform: SocialPlatform
  benchmark_skill_id: number
  my_content_text: string
}

export interface AccountAuditRun {
  id: number
  tenant_id: number
  platform: string
  benchmark_blogger_id: number | null
  benchmark_skill_id: number | null
  task_id: string | null
  status: string
  input_snapshot: string
  report_json: string
  score: number | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface XhsTopicIdeaRequest {
  skill_id: number
  seed_topic: string
  target_audience: string
  content_goal: string
  keywords: string
}

export interface XhsTopicIdea {
  title: string
  angle: string
  target_audience: string
  content_goal: string
  keywords: string[]
  reason: string
}

export interface XhsTopicIdeaResponse {
  ideas: XhsTopicIdea[]
}

export interface XhsPublishPackage {
  id: number
  tenant_id: number
  blogger_id: number
  skill_id: number
  content_type: XhsPublishContentType
  topic: string
  target_audience: string
  content_goal: string
  keywords: string
  image_count_mode: XhsImageCountMode
  requested_image_count: number | null
  title: string
  body_text: string
  hashtags_json: string
  cover_text: string
  image_plan_json: string
  image_urls_json: string
  script_json: string
  status: string
  error_message: string | null
  created_at: string
  updated_at: string
}
