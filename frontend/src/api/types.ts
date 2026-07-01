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

export interface AdminTenant {
  id: number
  name: string
  slug: string
  status: TenantStatus
  created_at: string
}

export interface ConfigFieldView {
  key: string
  label: string
  type: 'str' | 'int' | 'bool' | 'float'
  is_secret: boolean
  source: 'env' | 'db' | 'unset'
  value?: string | number | boolean | null
  configured?: boolean | null
}

export interface ConfigGroupView {
  key: string
  label: string
  fields: ConfigFieldView[]
}

export interface ConfigView {
  groups: ConfigGroupView[]
}

export interface AdminTask {
  id: string
  tenant_id: number
  task_type: string
  status: TaskStatus
  message: string
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface QueueHealth {
  use_task_queue: boolean
  queue_name?: string | null
  queued?: number | null
  failed?: number | null
  note?: string | null
}

export interface AppSettingRead {
  key: string
  value: string
  updated_at?: string
}

export interface CostEvent {
  id: number
  created_at: string
  tenant_id: number | null
  tenant_name: string | null
  task_id: string | null
  provider: string
  kind: string
  model: string | null
  quantity: number
  unit: string
  cost_usd: number
  meta_json: string | null
}

export interface CostByKey {
  key: string
  label: string
  cost_usd: number
  count: number
}

export interface CostSummary {
  days: number
  total_usd: number
  event_count: number
  by_provider: CostByKey[]
  by_tenant: CostByKey[]
}

export interface ModelPrices {
  text: Record<string, { input_per_1k: number; output_per_1k: number }>
  image: Record<string, number>
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

export interface BloggerTag {
  name: string
  source: string
}

export interface BloggerProfile {
  id: number
  tenant_id: number
  platform: string
  account_type: string
  external_id: string | null
  display_name: string
  homepage_url: string
  avatar_url: string
  follower_count: number
  note_total: number | null
  niche: string
  description: string
  tags: BloggerTag[]
  is_favorite: boolean
  sample_count: number
  last_distilled_at: string | null
  created_at: string
  updated_at: string
}

export interface BloggerProfileCreate {
  platform?: SocialPlatform
  account_type?: 'benchmark' | 'mine'
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
  tags?: string[]
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
  // 火爆度速览(仅按粉丝数粗算,免费);完整四项指标要点「评估」才跑。
  quick_popularity?: number
}

// 对标博主搜寻:意图 + 候选评分 + 推荐运行。
export interface BenchmarkIntent {
  niche: string
  audience?: string
  goal?: string
  content_form?: 'image_text' | 'video' | 'any'
}

export interface CandidateScore {
  platform: SocialPlatform
  external_id: string
  display_name: string
  homepage_url: string
  avatar_url: string
  description: string
  follower_count: number
  popularity: number
  relevance: number
  learnability: number
  transferability: number | null
  overall: number
  active: boolean
  reasons: { relevance?: string; learnability?: string; summary?: string }
  existing_blogger_id: number | null
}

export interface BenchmarkRecommendationRun {
  id: number
  platform: SocialPlatform
  kind: string
  status: string
  my_account_id: number | null
  intent: Record<string, unknown>
  candidates: CandidateScore[]
  error_message?: string | null
  created_at: string
}

export interface EvaluateResult {
  candidate: CandidateScore
}


// Skill 优化(训练)
export interface SkillTrainingSample {
  topic: string
  seed_text: string
  seed_sim: number
  optimized_text: string
  optimized_sim: number
  real_text: string
}
export interface SkillTrainingReport {
  anchors?: { floor: number; ceiling: number }
  counts?: { train: number; val: number; test: number; dropped_minority: number }
  epochs?: Array<{ step: number | null; action: string; val_score: number | null; edits: string[] }>
  changelog?: string[]
  samples?: SkillTrainingSample[]
  process_note?: string
}
export interface SkillTrainingRun {
  id: number
  blogger_id: number
  base_skill_id: number | null
  result_skill_id: number | null
  status: string
  modality: string
  before_score: number
  after_score: number
  before_gap: number
  after_gap: number
  delta: number
  verdict: string
  recommend_adopt: boolean
  optimized_skill_markdown: string
  report: SkillTrainingReport
  error_message?: string | null
  created_at: string
}

export interface BloggerDistillRequest {
  // auto=自动蒸馏(高赞 top-N);custom=自定义(选快照 或 手选 N 篇)
  source: 'auto' | 'custom'
  post_ids?: number[]
  snapshot_id?: number | null
  snapshot_name?: string
  mode?: string
}

export interface BloggerSnapshot {
  id: number
  tenant_id: number
  blogger_id: number
  name: string
  post_ids: number[]
  post_count: number
  created_at: string
  updated_at: string | null
}

// 智能选材:AI 按需求给博主笔记打相关度分(覆盖全部候选,按分降序)。
export interface SnapshotSuggestItem {
  post_id: number
  score: number
  reason: string
}
export interface SnapshotSuggestResult {
  suggested_name: string
  items: SnapshotSuggestItem[]
}

export interface BloggerCollectRequest {
  sample_limit: number
  comments_per_post: number
  content_types?: string[]
  order?: 'top_liked' | 'latest'
  fetch_all?: boolean
}

export interface BloggerUrlCollectRequest {
  urls: string[]
  comments_per_post?: number
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
  content_subtype: string
  hashtags_json: string
  cover_url: string
  media_urls_json: string
  transcript_text: string
  asr_status: string
  asr_error: string
  image_text?: string
  visual_digest?: string
  vision_status?: string
  published_at: string | null
  like_count: number
  favorite_count: number
  comment_count: number
  sampled_comment_count?: number
  share_count: number
  score: number
  comments_json: string
  status: string
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
  scope_json: string
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
  my_account_id?: number | null
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
  my_blogger_id: number
  my_post_ids: number[]
  benchmark_blogger_id: number
  benchmark_post_ids: number[]
}

export interface SelfDiagnoseCreate {
  platform: SocialPlatform
  my_blogger_id: number
  my_post_ids: number[]
}

export interface AccountAuditRun {
  id: number
  tenant_id: number
  platform: string
  kind: string
  my_blogger_id: number | null
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
  my_account_id: number | null
  published_at: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

// —— 效果看板 ——
export interface DashboardActivity {
  key: string
  label: string
  count: number
  attempts: number
  avg_seconds: number
}
export interface DashboardSimilarityPoint {
  date: string | null
  blogger_id: number
  before: number
  after: number
  gap_closed: number
  floor: number
  ceiling: number
  verdict: string
}
export interface DashboardOverview {
  range: string
  activities: DashboardActivity[]
  creation: { created: number; published: number; conversion: number }
  library: { benchmark_count: number; my_account_count: number; post_count: number }
  saved_minutes: number
  similarity_trend: DashboardSimilarityPoint[]
  recent: Array<{ task_type: string; label: string; status: string; at: string | null }>
}
export interface DashboardAccount {
  account: { id: number; display_name: string; follower_count: number; note_total: number | null; platform: string }
  range: string
  creation: { created: number; published: number; conversion: number }
  saved_minutes: number
  content: {
    post_count: number
    avg_interactions: number
    viral_count: number
    viral_rate: number
    by_modality: Record<string, number>
  }
}
export interface DashboardGrowthPoint {
  date: string
  follower_count: number
  note_total: number | null
  total_interactions: number
}
export interface DashboardGrowth {
  account_id: number
  range: string
  points: DashboardGrowthPoint[]
  events: Array<{ date: string; type: string; label: string }>
  comparison: {
    active_avg_daily: number | null
    silent_avg_daily: number | null
    active_weeks: number
    silent_weeks: number
  }
  disclaimer: string
}

// —— 博主诊断·三区报告(后端 run_appraisal 的 report_json 结构)——
export interface AppraisalDim {
  key: string
  label: string
  score: number
  detail: string
  metric?: Record<string, unknown>
  extra?: Record<string, unknown>
  evidence?: string[]
}
export interface AppraisalComplianceHit {
  category: string
  matched: string
  severity: string
  basis: string
  suggestion: string
  layer?: string
  quote: string
}
// 归并后的一条命中(违规/提示共用):同类合并 + 命中占比 + 样例。
export interface AppraisalComplianceGroup {
  category: string
  severity: string
  basis: string
  hint: string
  matched: string[]
  coverage?: { hit_notes: number; total_notes: number }
  samples?: string[]
}
export interface AppraisalComplianceResult {
  score: number
  grade: string
  hits: AppraisalComplianceHit[] // 兼容:旧报告扁平命中
  by_severity?: Record<string, number>
  has_ban: boolean
  // 新架构(赛道感知 + 两档):违规(需处置) / 提示(优化建议,不计入违规)
  violations?: AppraisalComplianceGroup[]
  advisories?: AppraisalComplianceGroup[]
  verticals?: string[]
  vertical_labels?: string[]
}
export interface AppraisalReport {
  kind: string
  intent?: string
  industry?: string | null
  sample_count: number
  hard: AppraisalDim[]
  hard_score: number
  soft: AppraisalDim[]
  soft_score: number | null
  // 目标契合(仅诊断自己 + 填了目标时有):账号现状离用户目标多近 + 针对该目标的整改清单。
  goal_fit?: { score: number; grade: string; summary: string; gaps: string[]; actions: string[] } | null
  compliance: AppraisalComplianceResult
  verdict: { level: string; text: string }
  score?: number
  examined_count?: number
  relevant_count?: number
  low_relevance?: boolean
  notes_relevance?: { title: string; relevant: boolean; reason: string }[]
}

// 对标分析·意图引导:选博主后,系统看 TA 在做什么 → 给几道多选题帮用户明确「想学什么」。
export interface AppraisalIntentQuestion {
  q: string
  options: string[]
  multi?: boolean // 可多选(缺省 true);false=单选(互斥)
  allow_other?: boolean // 是否允许「其他,自己填」(缺省 true)
}

export interface AppraisalIntentSuggestResult {
  clear: boolean // 用户填的意图已够具体 → 前端直接放行诊断,不展示问题
  questions: AppraisalIntentQuestion[]
}

// 答题打卡「读取 TA 最近笔记」阶段的真实返回:note_count 为实际喂给模型的近期笔记数。
export interface AppraisalIntentContext {
  note_count: number
  has_material: boolean
}
