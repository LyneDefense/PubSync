/**
 * 工作台全局状态与业务逻辑（单例 store）。
 *
 * 原本这些状态、计算属性和方法都堆在 App.vue 的 <script setup> 里（1600+ 行）。
 * 这里以「模块级单例」的形式集中管理：模块顶层的 ref/reactive/computed 在整个应用
 * 内是同一份实例，所以 App.vue 和各视图组件 import 后拿到的是同一套响应式状态，
 * 无需 props 透传或 provide/inject，语义与原来完全一致。
 *
 * 注意：onMounted / onUnmounted 等生命周期钩子必须在组件 setup 中调用，仍保留在 App.vue。
 */
import { computed, reactive, ref, watch } from 'vue'

import { useToast } from './useToast'
import {
  bloggerCommentLabel,
  findXhsDraftFromEvents,
  parseEventPayload,
  parseJsonArray,
  parseJsonObject,
  sampledCommentCount,
  wait,
  xhsContentTypeLabel,
  xhsPackageCopyText
} from '../utils/format'
import {
  abandonBloggerRun,
  cancelTask,
  clearAuthToken,
  clearTenantId,
  collectBlogger,
  collectBloggerByUrls,
  appraiseBlogger,
  listAccountAuditRuns,
  suggestAppraisalIntent,
  fetchAppraisalIntentContext,
  confirmBloggerRun,
  createBlogger,
  deleteBlogger,
  distillBlogger,
  fetchNews,
  generateArticle,
  generateXhsTopicIdeas,
  getAuthToken,
  getCurrentUser,
  getLatestArticle,
  getTenantId,
  getTask,
  getTaskEvents,
  getWorkspaceConfig,
  listBloggerCollectionPosts,
  listBloggerPosts,
  listBloggerCollectionRuns,
  listBloggerRuns,
  listBloggerSnapshots,
  createBloggerSnapshot,
  suggestSnapshot,
  updateBloggerSnapshot,
  deleteBloggerSnapshot,
  listBloggerSkills,
  listBloggers,
  listTenants,
  listNews,
  listXhsPublishPackages,
  login,
  sendArticleToWechat,
  saveXhsPublishPackage,
  searchBloggers,
  recommendBloggers,
  listRecommendRuns,
  evaluateBlogger,
  optimizeSkill,
  listSkillTrainingRuns,
  confirmSkillTrainingRun,
  getDashboardOverview,
  getAccountDashboard,
  getAccountGrowth,
  markXhsPackagePublished,
  setTenantId,
  startXhsPublishPackageDraftTask,
  updateArticle,
  updateBlogger,
  refreshBloggerProfile,
  updateBloggerFavorite,
  updateNewsSelection,
  updateWorkspaceConfig
} from '../api'
import type {
  AccountAuditRun,
  AppraisalIntentQuestion,
  AppraisalReport,
  Article,
  ArticleUpdate,
  BenchmarkIntent,
  BloggerCollectionRun,
  BloggerDistillationRun,
  BloggerPost,
  BloggerProfile,
  BloggerSearchResult,
  BloggerSkill,
  CandidateScore,
  SkillTrainingRun,
  BloggerSnapshot,
  SnapshotSuggestItem,
  ContentGroup,
  ContentProfile,
  CurrentUser,
  NewsItem,
  OperationTask,
  OperationTaskEvent,
  DashboardAccount,
  DashboardGrowth,
  DashboardOverview,
  SocialPlatform,
  SynthesisTrace,
  Tenant,
  WorkspaceConfig,
  XhsPublishContentType,
  XhsPublishPackage,
  XhsPublishPackageDraft,
  XhsTopicIdea
} from '../api/types'


export type TaskActionName = 'fetch' | 'generate' | 'collect' | 'distill' | 'xhs-package' | 'audit' | 'recommend' | 'optimize'
export type NewsTab = string
export type ArticleTab = 'edit' | 'preview'
export type MainTab = 'wechat' | 'xhs' | 'douyin' | 'admin'
// 每个平台内部用同一套「功能阶段」二级菜单，措辞统一、用户学一次三平台通用。
// 已实现的阶段对应具体 view；未实现的（公众号的 distill/ai、社媒的 freecreate/records/settings）走统一占位。
export type WeChatTab = 'brief' | 'distill' | 'ai' | 'drafts' | 'records' | 'settings'
// 小红书与抖音结构完全相同，共用 SocialTab；XhsTab/DouyinTab 保留为别名，避免大面积改名。
export type SocialTab = 'overview' | 'find' | 'collect' | 'distill' | 'assets' | 'my-accounts' | 'self-diagnosis' | 'analysis' | 'packages' | 'history' | 'freecreate' | 'records' | 'effects' | 'skill-optimize' | 'settings'
export type XhsTab = SocialTab
export type DouyinTab = SocialTab
export type SettingsTab = 'general' | 'wechat' | 'automation' | 'sources' | 'generation' | 'layout'
export type XhsScriptSegment = {
  start?: string
  end?: string
  scene?: string
  voiceover?: string
  subtitle?: string
}

export const statusText: Record<string, string> = {
  draft: '草稿',
  generated: '已生成',
  sent_to_wechat: '已入草稿箱',
  failed: '失败'
}

export const news = ref<NewsItem[]>([])
export const article = ref<Article | null>(null)
export const bloggers = ref<BloggerProfile[]>([])
export const bloggerPosts = ref<BloggerPost[]>([])
export const bloggerCollectionRuns = ref<BloggerCollectionRun[]>([])
export const bloggerRuns = ref<BloggerDistillationRun[]>([])
// 阶段B:博主笔记池命名快照 + 自定义蒸馏勾选集 + 单篇详情抽屉。
export const bloggerSnapshots = ref<BloggerSnapshot[]>([])
export const selectedPostIds = ref<number[]>([])
export const activeNotePostId = ref<number | null>(null)
// 对标分析(诊断别人):诊断一个对标库博主 → 硬/软/合规 三区报告。kind 固定 benchmark。
export const appraiseForm = reactive<{ blogger_id: number; kind: 'benchmark'; intent: string; industry: string }>({
  blogger_id: 0,
  kind: 'benchmark',
  intent: '',
  industry: ''
})
export const appraisalRun = ref<AccountAuditRun | null>(null)
// 历史诊断:已成功且可解析的 benchmark 报告,供「历史诊断」列表查看。
export const appraisalHistory = ref<AccountAuditRun[]>([])
// 意图引导:选博主后看 TA 在做什么 → 给几道多选题帮用户明确「想学什么」(意图够清晰则不出题)。
export const intentQuestions = ref<AppraisalIntentQuestion[]>([])
export const intentSelections = reactive<Record<number, string[]>>({}) // 每题选了哪些选项
export const intentOthers = reactive<Record<number, string>>({}) // 每题「其他」填的内容
export const intentChecked = ref(false) // 已对当前博主跑过意图引导(跑过才显示「开始诊断」)
export const intentClear = ref(false) // 用户填的意图已够具体,无需出题
export const intentLoading = ref(false)
// 诊断我的账号(评估与提升):只选我的账号,kind=self(无软实力,但有「目标契合」)。
// 意图在这里是内向的——目标 / 痛点 / 阶段(跟对标的「想学什么」不同),复用同一套多选引导件但独立 state。
export const selfAppraiseForm = reactive<{ blogger_id: number; intent: string }>({ blogger_id: 0, intent: '' })
export const selfAppraisalRun = ref<AccountAuditRun | null>(null)
export const selfAppraisalHistory = ref<AccountAuditRun[]>([]) // 我的诊断记录(kind=self,成功且可解析)
export const selfIntentQuestions = ref<AppraisalIntentQuestion[]>([])
export const selfIntentSelections = reactive<Record<number, string[]>>({})
export const selfIntentOthers = reactive<Record<number, string>>({})
export const selfIntentChecked = ref(false) // 已跑过意图引导(跑过才显示「开始诊断」)
export const selfIntentClear = ref(false) // 用户填的目标已够具体,无需出题
export const selfIntentLoading = ref(false)
// 我的账号(account_type=mine)与对标账号拆分。
export const myAccounts = computed(() => bloggers.value.filter((b) => b.account_type === 'mine'))
export const benchmarkAccounts = computed(() => bloggers.value.filter((b) => b.account_type !== 'mine'))
// 各账号内容列表缓存(按 blogger id);进页面只读缓存,刷新才重采。
export const accountPosts = reactive<Record<number, BloggerPost[]>>({})
// 创建博主弹窗的账号类型上下文(benchmark / mine)。
export const bloggerModalAccountType = ref<'benchmark' | 'mine'>('benchmark')
export const bloggerSkills = ref<BloggerSkill[]>([])
export const xhsPackages = ref<XhsPublishPackage[]>([])
export const currentXhsDraft = ref<XhsPublishPackageDraft | null>(null)
export const currentUser = ref<CurrentUser | null>(null)
export const selectedBloggerId = ref<number | null>(null)
export const selectedCollectionRunId = ref<number | null>(null)
export const selectedBloggerRunId = ref<number | null>(null)
export const resultCollectionFilterId = ref<number | null>(null)
export const selectedXhsPackageId = ref<number | null>(null)
export const xhsCreatorBloggerId = ref<number | null>(null)
export const xhsCreationStep = ref(1)
export const xhsTopicIdeas = ref<XhsTopicIdea[]>([])
export const selectedXhsTopicIndex = ref<number | null>(null)
export const tenants = ref<Tenant[]>([])
export const profile = ref<ContentProfile | null>(null)
export const contentGroups = ref<ContentGroup[]>([])
export const selectedTenantId = ref(getTenantId())
export const { message, isError, showMessage } = useToast()
export const pendingAction = ref<string | null>(null)
export const runningTaskId = ref<string | null>(null)
// 最近一次任务失败(持久展示,不像 toast 一闪而过)。发起新任务时清空;视图按 action 显示错误横幅。
export const taskFailure = ref<{ action: string; message: string } | null>(null)
export const taskEvents = ref<OperationTaskEvent[]>([])
export const taskEventsAction = ref<TaskActionName | null>(null)
export const taskEventsMainTab = ref<MainTab | null>(null)
// 任务发起时所在的子页签;进度条只在「发起任务的那个页面」展开,切走只留顶部迷你条。
export const taskEventsSubTab = ref<string | null>(null)
export const showTaskEventDetails = ref(false)
export const isAuthenticated = ref(Boolean(getAuthToken()))
export const isLoggingIn = ref(false)
export const loginMessage = ref('')

// 视图状态(平台/页签)由 vue-router 路由驱动,这里只是初值;路由守卫/App 会按 URL 同步。
// 这些 ref 仍保留:大量视图沿用 currentSocialTab 等自门控逻辑,改由路由写入而非自行持久化。
export const activeMainTab = ref<MainTab>('xhs')
export const activeWechatTab = ref<WeChatTab>('brief')
export const activeXhsTab = ref<XhsTab>('overview')
export const activeDouyinTab = ref<DouyinTab>('overview')

// 只记录「最近平台」,供登录后跳回工作台(router.readLastPlatform 读同一 key)。admin 不计。
const LAST_PLATFORM_KEY = 'pubsync_last_platform'
watch(activeMainTab, (tab) => {
  if (tab === 'admin') return
  try {
    window.localStorage.setItem(LAST_PLATFORM_KEY, tab)
  } catch {
    /* localStorage 不可用时静默忽略,不影响功能 */
  }
})
export const xhsCollectStep = ref(1)
export const xhsDistillStep = ref(1)
export const wechatBriefStep = ref(1)
export const activeNewsTab = ref<NewsTab>('')
export const activeArticleTab = ref<ArticleTab>('preview')
export const activeSettingsTab = ref<SettingsTab>('general')
export const showBloggerModal = ref(false)
export const editingBloggerId = ref<number | null>(null)
export const bloggerSearchKeyword = ref('')
export const bloggerSearchResults = ref<BloggerSearchResult[]>([])
export const selectedBloggerCandidate = ref<BloggerSearchResult | null>(null)
export const showUserMenu = ref(false)
export const previewImage = ref<{ url: string; caption: string } | null>(null)
export const newsPage = ref(1)
export const pageSize = 5
export const taskProgress = reactive<Record<TaskActionName, number>>({
  fetch: 0,
  generate: 0,
  collect: 0,
  distill: 0,
  'xhs-package': 0,
  audit: 0,
  recommend: 0,
  optimize: 0,
})
export const progressTimers: Partial<Record<TaskActionName, number>> = {}

export const form = reactive<ArticleUpdate>({
  title: '',
  intro: '',
  cover_image_url: '',
  content_html: ''
})

export const bloggerForm = reactive({
  external_id: '',
  display_name: '',
  homepage_url: '',
  avatar_url: '',
  follower_count: 0,
  niche: '',
  description: '',
  tags: '' // 手动标签:逗号分隔。仅编辑时透传,自动标签不在此。
})

export const bloggerDistillForm = reactive({
  sample_limit: 50,
  comments_per_post: 20
})

// 内容模态标签(与后端 app/blogger_distillation/modality.py 对齐)。
export const SUBTYPE_LABELS: Record<string, string> = {
  image_text: '图文',
  talking_video: '口播视频',
  visual_video: '非口播视频',
  unknown: '未知',
  article: '纯文章',
  article_with_image: '配图文章'
}
export function subtypeLabel(value: string) {
  return SUBTYPE_LABELS[value] || value
}
// 可被用户勾选蒸馏的模态(口播细分在采集后判定)。
export const DISTILL_SUBTYPES = ['image_text', 'talking_video', 'visual_video'] as const
// 阶段B:自定义蒸馏的样本下限(硬:<8 拦截)与软建议(≥15 越多越准)。
export const DISTILL_MIN_SAMPLES = 8
export const DISTILL_RECOMMEND_SAMPLES = 15
// 笔记池按内容模态分组展示的顺序。
export const NOTE_GROUP_ORDER = ['image_text', 'talking_video', 'visual_video', 'unknown'] as const
// 采集拉取范围:image=图文,video=视频。
export const collectContentTypes = ref<string[]>(['image', 'video'])
// 采集选材:排序(高赞/最新)+ 数量(false=N 条,true=全部到上限)。
export const collectOrder = ref<'top_liked' | 'latest'>('top_liked')
export const collectFetchAll = ref(false)
// 兜底:粘贴链接定向采集的输入(一行一个)。
export const urlCollectInput = ref('')
// 蒸馏勾选的模态(空=全选=通用)。
export const distillSelectedSubtypes = ref<string[]>([])

// 蒸馏模式：A=拆解对标博主（默认），B=诊断我的账号。
export const xhsDistillMode = ref<'A' | 'B'>('A')

export const xhsPackageForm = reactive({
  skill_id: 0,
  content_type: 'text_note' as XhsPublishContentType,
  topic: '',
  target_audience: '',
  content_goal: '知识分享',
  keywords: '',
  image_count_mode: 'auto' as 'auto' | 'manual',
  requested_image_count: 3,
  // 这篇给我的哪个账号用;null=暂不指定(没绑账号也能创作)。
  my_account_id: null as number | null
})

export const profileForm = reactive({
  publication_name: '',
  workspace_title: '',
  title_prefix: '',
  grouping_mode: 'regional' as 'regional' | 'none',
  content_domain: '',
  editor_persona: '',
  audience: '',
  article_style: '',
  categories_json: '[]',
  image_style: ''
})

export const wechatForm = reactive({
  app_id: '',
  app_secret: '',
  app_secret_configured: false
})

export const layoutForm = reactive({
  template_name: 'clean',
  primary_color: '#0f766e',
  accent_color: '#64748b',
  text_color: 'inherit',
  heading_color: 'inherit',
  body_font_size: 15,
  heading_font_size: 19,
  line_height: '1.85',
  section_spacing: 28,
  image_radius: 8,
  show_group_heading: true,
  show_source: true,
  show_editor_note: true
})

export const publishingForm = reactive({
  daily_publish_enabled: false,
  publish_frequency: 'daily' as 'daily' | 'weekly' | 'monthly',
  publish_weekday: 1,
  publish_month_day: 1,
  publish_time_hour: 8,
  publish_time_minute: 0,
  publish_time_value: '08:00',
  auto_send_wechat_draft: false,
  generate_article_images: true,
  max_article_images: 3,
  min_article_images: 1,
  news_source_urls: '',
  news_per_source_limit: 8,
  news_lookback_hours: 72,
  max_news_candidates: 80,
  dedup_lookback_days: 7,
  dedup_direct_similarity: '0.82',
  dedup_review_similarity: '0.42',
  dedup_enable_llm_review: true,
  article_news_limit: 10,
  article_news_lookback_hours: 72
})

export const contentGroupForms = ref<ContentGroup[]>([])

export const hasArticle = computed(() => Boolean(article.value))
export const workspaceTitle = computed(() => profile.value?.workspace_title || 'AI 早报')
export const publicationName = computed(() => profile.value?.publication_name || workspaceTitle.value)
export const isAdmin = computed(() => Boolean(currentUser.value?.is_admin))
export const currentTenantName = computed(() => tenants.value.find((tenant) => String(tenant.id) === selectedTenantId.value)?.name || publicationName.value)
export const canSwitchTenant = computed(() => isAdmin.value && tenants.value.length > 1)
export const currentUsername = computed(() => currentUser.value?.username || '当前用户')
export const activePlatformLabel = computed(() => {
  const labels: Record<MainTab, string> = {
    wechat: '公众号',
    xhs: '小红书',
    douyin: '抖音',
    admin: '后台管理'
  }
  return labels[activeMainTab.value] || '工作台'
})
export const isSocialPlatform = computed(() => activeMainTab.value === 'xhs' || activeMainTab.value === 'douyin')
export const currentSocialPlatform = computed<SocialPlatform>(() => (activeMainTab.value === 'douyin' ? 'douyin' : 'xhs'))
export const currentSocialPlatformName = computed(() => (currentSocialPlatform.value === 'douyin' ? '抖音' : '小红书'))
export const currentSocialTab = computed<SocialTab>(() => (activeMainTab.value === 'douyin' ? activeDouyinTab.value : activeXhsTab.value))
// 当前所在子页签(跨平台统一):用于判断进度条是否在「任务主页」。
export const activeSubTab = computed<string>(() =>
  activeMainTab.value === 'wechat' ? activeWechatTab.value : currentSocialTab.value
)
// 当前平台是否已录入「我的账号」(概览页据此二选一显示引导/已录入卡)。
export const currentMyAccount = computed(() => myAccounts.value.find((a) => a.platform === currentSocialPlatform.value) || null)
export const hasMyAccount = computed(() => Boolean(currentMyAccount.value))
// 当前平台下的「我的账号」列表(创作目标选择 + 效果看板账号切换共用)。
export const myAccountsOnPlatform = computed(() => myAccounts.value.filter((a) => a.platform === currentSocialPlatform.value))

// —— 效果看板 ——
export const dashboardRange = ref<'7d' | '30d' | 'all'>('30d')
export const dashboardOverview = ref<DashboardOverview | null>(null)
export const dashboardAccountId = ref<number | null>(null)
export const dashboardAccount = ref<DashboardAccount | null>(null)
export const dashboardGrowth = ref<DashboardGrowth | null>(null)
export const dashboardLoading = ref(false)

export async function loadDashboard() {
  dashboardLoading.value = true
  try {
    // A 层总能加载(租户级,和有没有「我的账号」无关)。
    dashboardOverview.value = await getDashboardOverview(dashboardRange.value)
    // B 层:默认选当前平台第一个「我的账号」;没有则留空(视图显示引导)。
    if (dashboardAccountId.value && !myAccountsOnPlatform.value.some((a) => a.id === dashboardAccountId.value)) {
      dashboardAccountId.value = null
    }
    if (!dashboardAccountId.value) {
      dashboardAccountId.value = myAccountsOnPlatform.value[0]?.id ?? null
    }
    await loadDashboardAccount()
  } catch (error) {
    showMessage(error instanceof Error ? error.message : '加载看板失败', true)
  } finally {
    dashboardLoading.value = false
  }
}

async function loadDashboardAccount() {
  const id = dashboardAccountId.value
  if (!id) {
    dashboardAccount.value = null
    dashboardGrowth.value = null
    return
  }
  const [acc, growth] = await Promise.all([
    getAccountDashboard(id, dashboardRange.value),
    getAccountGrowth(id, dashboardRange.value)
  ])
  dashboardAccount.value = acc
  dashboardGrowth.value = growth
}

export async function selectDashboardAccount(accountId: number | null) {
  dashboardAccountId.value = accountId
  try {
    await loadDashboardAccount()
  } catch (error) {
    showMessage(error instanceof Error ? error.message : '加载账号成果失败', true)
  }
}

export async function setDashboardRange(range: '7d' | '30d' | 'all') {
  dashboardRange.value = range
  await loadDashboard()
}

export async function handleMarkPublished(pkg: XhsPublishPackage, published: boolean) {
  try {
    const updated = await markXhsPackagePublished(pkg.id, published)
    const idx = xhsPackages.value.findIndex((p) => p.id === updated.id)
    if (idx >= 0) xhsPackages.value[idx] = updated
    showMessage(published ? '已记录:这篇已发布 ✓' : '已撤销发布标记')
  } catch (error) {
    showMessage(error instanceof Error ? error.message : '操作失败', true)
  }
}
export const usesRegionalGrouping = computed(() => profile.value?.grouping_mode !== 'none')
export const enabledContentGroups = computed(() => contentGroups.value.filter((group) => group.enabled))
export const hasNewsGroups = computed(() => enabledContentGroups.value.length > 0)
export const visibleNewsTabs = computed(() => {
  if (!hasNewsGroups.value) {
    return [{ group_key: 'all', name: '全部', count: news.value.length }]
  }
  const tabs = enabledContentGroups.value.map((group) => ({
    group_key: group.group_key,
    name: group.name,
    count: news.value.filter((item) => item.group_key === group.group_key).length
  }))
  return tabs.length ? tabs : [{ group_key: 'all', name: '全部', count: news.value.length }]
})
export const activeNews = computed(() => {
  if (!hasNewsGroups.value || activeNewsTab.value === 'all') {
    return news.value
  }
  return news.value.filter((item) => item.group_key === activeNewsTab.value)
})
export const newsTotalPages = computed(() => Math.max(1, Math.ceil(activeNews.value.length / pageSize)))
export const pagedNews = computed(() => {
  const start = (newsPage.value - 1) * pageSize
  return activeNews.value.slice(start, start + pageSize)
})
export const selectedBlogger = computed(() => bloggers.value.find((item) => item.id === selectedBloggerId.value) || null)
export const editingBlogger = computed(() => bloggers.value.find((item) => item.id === editingBloggerId.value) || null)
export const selectedCollectionRun = computed(() => bloggerCollectionRuns.value.find((run) => run.id === selectedCollectionRunId.value) || null)
// 当前采集批次各模态样本数(来自 summary_json.stats.subtype_counts;旧批次可能为空)。
export const collectionSubtypeCounts = computed<Record<string, number>>(() => {
  try {
    const summary = JSON.parse(selectedCollectionRun.value?.summary_json || '{}')
    return (summary?.stats?.subtype_counts as Record<string, number>) || {}
  } catch {
    return {}
  }
})

// 采集实时面板:逐条抓取的高频事件折叠成进度条,只把里程碑事件列进时间线。
const COLLECT_SPAM_STEPS = new Set(['笔记详情', '样本入库', '视频 ASR', '视频字幕', '评论采集'])
export const collectTimeline = computed(() =>
  taskEventsAction.value === 'collect' ? taskEvents.value.filter((event) => !COLLECT_SPAM_STEPS.has(event.step_name)) : []
)
export const collectProgress = computed(() => {
  if (taskEventsAction.value !== 'collect') return { current: 0, total: 0, pct: 0 }
  for (let index = taskEvents.value.length - 1; index >= 0; index -= 1) {
    const payload = parseEventPayload(taskEvents.value[index])
    const current = Number(payload?.current)
    const total = Number(payload?.total)
    if (current && total) {
      return { current, total, pct: Math.round((current / total) * 100) }
    }
  }
  return { current: 0, total: 0, pct: 0 }
})
export const collectLatestMessage = computed(() => {
  if (taskEventsAction.value !== 'collect') return ''
  const event = taskEvents.value[taskEvents.value.length - 1]
  return event ? event.message : ''
})
// 采集完成后的「本批摘要」(读最新一条采集批次的 summary_json)。
export const lastCollectSummary = computed(() => {
  const run = bloggerCollectionRuns.value[0]
  if (!run || run.status !== 'succeeded') return null
  try {
    const summary = JSON.parse(run.summary_json || '{}')
    const meta = summary.collect_meta || {}
    return {
      runId: run.id,
      postCount: run.post_count,
      newCount: typeof meta.new_count === 'number' ? meta.new_count : null,
      refreshedCount: typeof meta.refreshed_count === 'number' ? meta.refreshed_count : null,
      delistedCount: meta.delisted_count || 0,
      hotCount: run.hot_post_count,
      commentCount: run.comment_count,
      subtypeCounts: (summary?.stats?.subtype_counts as Record<string, number>) || {}
    }
  } catch {
    return null
  }
})
export const resultCollectionFilter = computed(() => bloggerCollectionRuns.value.find((run) => run.id === resultCollectionFilterId.value) || null)
export const selectedBloggerRun = computed(() => bloggerRuns.value.find((run) => run.id === selectedBloggerRunId.value) || null)
export const selectedBloggerSkill = computed(() => bloggerSkills.value.find((skill) => skill.run_id === selectedBloggerRunId.value) || null)
export const selectedXhsSkill = computed(() => bloggerSkills.value.find((skill) => skill.id === xhsPackageForm.skill_id) || null)
export const visibleXhsPackages = computed(() => {
  const bloggerIds = new Set(bloggers.value.map((blogger) => blogger.id))
  return xhsPackages.value.filter((item) => bloggerIds.has(item.blogger_id))
})
export const selectedXhsPackage = computed(() => visibleXhsPackages.value.find((item) => item.id === selectedXhsPackageId.value) || visibleXhsPackages.value[0] || null)
export const selectedBloggerRunCount = computed(() => bloggerRuns.value.length)
export const visibleBloggerRuns = computed(() =>
  resultCollectionFilterId.value ? bloggerRuns.value.filter((run) => run.collection_run_id === resultCollectionFilterId.value) : bloggerRuns.value
)
export const visibleBloggerRunCount = computed(() => visibleBloggerRuns.value.length)

// ── 阶段B:笔记池(按模态分组)/ 勾选 / 单篇详情抽屉 ──────────────────────────
// 仅展示未下架的笔记参与分组与选材;下架的单独提示但不进蒸馏。
export const activeNotePool = computed(() => bloggerPosts.value.filter((p) => p.status !== 'delisted'))
export const delistedNoteCount = computed(() => bloggerPosts.value.filter((p) => p.status === 'delisted').length)

export interface NoteGroup {
  subtype: string
  label: string
  posts: BloggerPost[]
}
export const bloggerNoteGroups = computed<NoteGroup[]>(() => {
  const buckets = new Map<string, BloggerPost[]>()
  for (const post of activeNotePool.value) {
    const key = post.content_subtype || 'unknown'
    if (!buckets.has(key)) buckets.set(key, [])
    buckets.get(key)!.push(post)
  }
  const order = NOTE_GROUP_ORDER as readonly string[]
  const keys = [...buckets.keys()].sort((a, b) => {
    const ia = order.indexOf(a)
    const ib = order.indexOf(b)
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib)
  })
  return keys.map((subtype) => ({ subtype, label: subtypeLabel(subtype), posts: buckets.get(subtype)! }))
})

export const selectedPostCount = computed(() => selectedPostIds.value.length)
// 已勾选的笔记对象(保持勾选顺序),供存快照弹框列出。
export const selectedPosts = computed(() =>
  selectedPostIds.value
    .map((id) => bloggerPosts.value.find((p) => p.id === id))
    .filter((p): p is BloggerPost => Boolean(p))
)
export function isPostSelected(id: number) {
  return selectedPostIds.value.includes(id)
}
export function togglePostSelection(id: number) {
  const idx = selectedPostIds.value.indexOf(id)
  if (idx >= 0) selectedPostIds.value.splice(idx, 1)
  else selectedPostIds.value.push(id)
}
export function clearPostSelection() {
  selectedPostIds.value = []
}
export function selectGroupPosts(subtype: string) {
  const group = bloggerNoteGroups.value.find((g) => g.subtype === subtype)
  if (!group) return
  const ids = new Set(selectedPostIds.value)
  for (const post of group.posts) ids.add(post.id)
  selectedPostIds.value = [...ids]
}

// —— 智能选材:AI 按需求预选笔记建快照 ——
export const snapshotSuggestLoading = ref(false)
export const snapshotSuggestError = ref('')
export const snapshotSuggestName = ref('') // AI 建议的快照名
export const snapshotSuggestRanked = ref<SnapshotSuggestItem[]>([]) // 覆盖全部候选,按分降序(供放宽/自动补)
export const snapshotSuggestReasons = reactive<Record<number, string>>({}) // post_id → 为什么选它
export const snapshotSuggested = computed(() => snapshotSuggestRanked.value.length > 0)
const SNAPSHOT_PICK_SCORE = 55 // 预勾选门槛:相关度 ≥ 此值自动勾上

export function resetSnapshotSuggest() {
  snapshotSuggestLoading.value = false
  snapshotSuggestError.value = ''
  snapshotSuggestName.value = ''
  snapshotSuggestRanked.value = []
  for (const k of Object.keys(snapshotSuggestReasons)) delete snapshotSuggestReasons[Number(k)]
}

// 输需求 → AI 打分 → 预勾选高分笔记(仍在当前池里的)。返回预选数量供 UI 提示;失败退化为手动挑。
export async function fetchSnapshotSuggestion(need: string): Promise<number | null> {
  if (!selectedBloggerId.value) {
    showMessage('请先选择一个博主', true)
    return null
  }
  snapshotSuggestLoading.value = true
  snapshotSuggestError.value = ''
  try {
    const res = await suggestSnapshot(selectedBloggerId.value, need)
    snapshotSuggestRanked.value = res.items
    snapshotSuggestName.value = res.suggested_name
    for (const k of Object.keys(snapshotSuggestReasons)) delete snapshotSuggestReasons[Number(k)]
    // 只给"相关"的笔记(分>0)挂标注:有理由用理由,否则显示相关度分。
    for (const it of res.items) if (it.score > 0) snapshotSuggestReasons[it.post_id] = it.reason || `相关度 ${it.score}`
    const poolIds = new Set(bloggerPosts.value.map((p) => p.id))
    const picked = res.items.filter((it) => it.score >= SNAPSHOT_PICK_SCORE && poolIds.has(it.post_id)).map((it) => it.post_id)
    selectedPostIds.value = picked
    return picked.length
  } catch (err) {
    snapshotSuggestError.value = err instanceof Error ? err.message : 'AI 选材失败,请手动挑选'
    return null
  } finally {
    snapshotSuggestLoading.value = false
  }
}

// 自动补 / 放宽:从 AI 排序结果里把没选中的按分数从高到低补进来,直到达到 target 篇。
export function topUpSelectionByScore(target: number) {
  if (!snapshotSuggestRanked.value.length) return
  const poolIds = new Set(bloggerPosts.value.map((p) => p.id))
  const selected = new Set(selectedPostIds.value)
  for (const it of snapshotSuggestRanked.value) {
    if (selected.size >= target) break
    if (!selected.has(it.post_id) && poolIds.has(it.post_id)) {
      selectedPostIds.value.push(it.post_id)
      selected.add(it.post_id)
    }
  }
}

// 详情抽屉的当前笔记:先在对标博主笔记池找,再在「我的账号」缓存里找 —— 两处笔记复用同一个抽屉。
export const activeNotePost = computed(() => {
  const id = activeNotePostId.value
  if (id == null) return null
  const inBlogger = bloggerPosts.value.find((p) => p.id === id)
  if (inBlogger) return inBlogger
  for (const arr of Object.values(accountPosts)) {
    const hit = arr.find((p) => p.id === id)
    if (hit) return hit
  }
  return null
})
export function openNote(id: number) {
  activeNotePostId.value = id
}
export function closeNote() {
  activeNotePostId.value = null
}
// 抽屉用:话题标签、TOP3 热评、正文/口播稿摘要。
export function noteHashtags(post: BloggerPost | null): string[] {
  if (!post) return []
  return parseJsonArray(post.hashtags_json)
}
export interface NoteComment {
  content: string
  like_count: number
}
export function noteTopComments(post: BloggerPost | null): NoteComment[] {
  if (!post?.comments_json) return []
  try {
    const raw = JSON.parse(post.comments_json)
    const list = Array.isArray(raw) ? raw : []
    return list
      .map((c: Record<string, unknown>) => ({
        content: String(c.content || c.text || ''),
        like_count: Number(c.like_count || 0)
      }))
      .filter((c: NoteComment) => c.content)
      .sort((a: NoteComment, b: NoteComment) => b.like_count - a.like_count)
      .slice(0, 3)
  } catch {
    return []
  }
}
export function noteBodyText(post: BloggerPost | null): string {
  if (!post) return ''
  return (post.transcript_text || post.body_text || '').trim()
}
export const xhsPackageImageUrls = computed(() => parseJsonArray(selectedXhsPackage.value?.image_urls_json))
export const xhsPackageImagePlan = computed(() => parseJsonArray(selectedXhsPackage.value?.image_plan_json))
export const xhsPackageHashtags = computed(() => parseJsonArray(selectedXhsPackage.value?.hashtags_json))
export const xhsDraftImageUrls = computed(() => parseJsonArray(currentXhsDraft.value?.image_urls_json))
export const xhsDraftImagePlan = computed(() => parseJsonArray(currentXhsDraft.value?.image_plan_json))
export const xhsDraftHashtags = computed(() => parseJsonArray(currentXhsDraft.value?.hashtags_json))
export const xhsDraftScriptSegments = computed(() => {
  const script = parseJsonObject(currentXhsDraft.value?.script_json)
  return Array.isArray(script.segments) ? (script.segments as XhsScriptSegment[]) : []
})
export const xhsPackageScriptSegments = computed(() => {
  const script = parseJsonObject(selectedXhsPackage.value?.script_json)
  return Array.isArray(script.segments) ? script.segments : []
})

// 创作草稿的「对标对比」(第5点①)。
export const xhsDraftBenchmark = computed(() => currentXhsDraft.value?.benchmark || null)

// 创作草稿的「平台限流词」合规结果。
export const xhsDraftCompliance = computed(() => currentXhsDraft.value?.compliance || null)

// 把合成轨迹翻成通俗的「创作过程」时间线(不暴露原始技术措辞)。
export interface ProcessStep {
  label: string
  detail: string
}

export function buildProcessTimeline(trace: SynthesisTrace | undefined | null): ProcessStep[] {
  if (!trace?.attempts?.length) return []
  const steps: ProcessStep[] = []
  trace.attempts.forEach((attempt) => {
    const scoreTxt = typeof attempt.score === 'number' ? `(质量打分 ${attempt.score})` : ''
    const ordinal = attempt.attempt === 1 ? '起草初稿' : `第 ${attempt.attempt} 版`
    if (attempt.passed) {
      steps.push({ label: ordinal, detail: `自检通过${scoreTxt}` })
    } else {
      const n = attempt.issues?.length || 0
      const hint = n ? `发现 ${n} 处可以更好的地方` : '感觉还能更到位'
      steps.push({ label: ordinal, detail: `自检${hint}${scoreTxt}，继续打磨` })
    }
  })
  const last = trace.attempts[trace.attempts.length - 1]
  const tail = trace.final_passed ? '最终达标' : '已尽力打磨，采用当前最好的一版'
  steps.push({ label: '完成', detail: `${tail}，共自我优化 ${trace.revisions} 次${typeof last.score === 'number' ? `(质量打分 ${last.score})` : ''}` })
  return steps
}

export const xhsDraftProcess = computed(() => buildProcessTimeline(currentXhsDraft.value?.synthesis))
export const activeXhsSkills = computed(() =>
  bloggerSkills.value.filter((skill) => skill.status === 'active').map((skill) => ({
    ...skill,
    bloggerName: bloggers.value.find((blogger) => blogger.id === skill.blogger_id)?.display_name || `博主 #${skill.blogger_id}`
  }))
)
export const xhsCreatorSkillOptions = computed(() =>
  activeXhsSkills.value.filter((skill) => !xhsCreatorBloggerId.value || skill.blogger_id === xhsCreatorBloggerId.value)
)
export const selectedXhsPackageBloggerName = computed(() => {
  const pack = selectedXhsPackage.value
  if (!pack) {
    return ''
  }
  return bloggers.value.find((blogger) => blogger.id === pack.blogger_id)?.display_name || `博主 #${pack.blogger_id}`
})
export const selectedXhsTopicIdea = computed(() =>
  selectedXhsTopicIndex.value === null ? null : xhsTopicIdeas.value[selectedXhsTopicIndex.value] || null
)
// 顶部紧凑步骤条用的简短标签，按步骤顺序排列（取代原先居中的大标题）。
export const xhsCreationStepLabels = ['选择博主', '选择 Skill', '生成选题', '生成正文', '封面配图', '确认发布']
export const xhsCollectStepLabels = ['选择博主', '配置采集', '执行采集', '查看结果']
export const xhsDistillStepLabels = ['选择博主', '选择批次', '执行蒸馏', '确认结果']
export const wechatBriefStepLabels = ['选新闻', '生成文章', '预览/编辑', '发布草稿箱']
export const canGoNextWechatBriefStep = computed(() => {
  // 第 1 步「选新闻」不强制勾选(允许用已有勾选直接生成);第 2 步要先生成出文章才能进预览。
  if (wechatBriefStep.value === 2) {
    return hasArticle.value
  }
  if (wechatBriefStep.value === 3) {
    return hasArticle.value
  }
  return wechatBriefStep.value === 1
})
export const canGoNextXhsCollectStep = computed(() => {
  if (xhsCollectStep.value === 1) {
    return Boolean(selectedBlogger.value)
  }
  if (xhsCollectStep.value === 2) {
    return Boolean(selectedBlogger.value)
  }
  if (xhsCollectStep.value === 3) {
    return Boolean(selectedBlogger.value)
  }
  return false
})
export const canGoNextXhsDistillStep = computed(() => {
  if (xhsDistillStep.value === 1) {
    return Boolean(selectedBlogger.value)
  }
  if (xhsDistillStep.value === 2) {
    return Boolean(selectedCollectionRun.value)
  }
  if (xhsDistillStep.value === 3) {
    return Boolean(selectedCollectionRun.value)
  }
  return false
})
export const canGoNextXhsCreationStep = computed(() => {
  if (xhsCreationStep.value === 1) {
    return Boolean(xhsCreatorBloggerId.value)
  }
  if (xhsCreationStep.value === 2) {
    return Boolean(selectedXhsSkill.value)
  }
  if (xhsCreationStep.value === 3) {
    return Boolean(selectedXhsTopicIdea.value)
  }
  if (xhsCreationStep.value === 4) {
    return Boolean(currentXhsDraft.value)
  }
  if (xhsCreationStep.value === 5) {
    return Boolean(currentXhsDraft.value)
  }
  return false
})
export function collectionDistillationCount(collectionRunId: number) {
  return bloggerRuns.value.filter((run) => run.collection_run_id === collectionRunId).length
}
export const visibleTaskEvents = computed(() => {
  if (!taskEventsAction.value) {
    return []
  }
  return taskEventsMainTab.value === activeMainTab.value ? taskEvents.value : []
})
export const latestTaskEvent = computed(() => visibleTaskEvents.value[visibleTaskEvents.value.length - 1] || null)
// 所有会跑一会儿、需要展示进度的动作(统一进度面板据此显示)。
const LONG_RUNNING_ACTIONS = new Set(['fetch', 'generate', 'collect', 'distill', 'xhs-package', 'xhs-topic', 'audit', 'recommend', 'optimize'])
export const isTaskRunning = computed(() => LONG_RUNNING_ACTIONS.has(pendingAction.value || ''))
// 是否就在「发起任务的那个页面」(同平台 + 同子页签)。进度条只在这里展开。
export const isOnTaskHome = computed(
  () => taskEventsMainTab.value === activeMainTab.value && taskEventsSubTab.value === activeSubTab.value
)
export const isVisibleTaskRunning = computed(
  () => isTaskRunning.value && taskEventsAction.value !== null && isOnTaskHome.value
)
// 任务在跑、但当前不在它的主页 → 顶部只显示一条迷你「xx 进行中·查看」。
export const isMiniTaskRunning = computed(
  () => isTaskRunning.value && taskEventsAction.value !== null && !isOnTaskHome.value
)
// 迷你条用:不受页签门控的最新事件(visibleTaskEvents 会按平台清空)。
export const latestEventAny = computed(() => taskEvents.value[taskEvents.value.length - 1] || null)
export const miniTaskStep = computed(() =>
  latestEventAny.value ? humanizeStepName(latestEventAny.value.step_name) : '进行中'
)
// 是否有「需要展示进度」的任务在执行(全局顶部进度卡片用)。涵盖所有会跑一会儿的动作。
export const PROGRESS_ACTIONS = ['fetch', 'generate', 'collect', 'distill', 'xhs-package', 'xhs-package-save', 'xhs-topic', 'audit'] as const
export const isProgressTaskRunning = computed(() => PROGRESS_ACTIONS.includes(pendingAction.value as (typeof PROGRESS_ACTIONS)[number]))
const TASK_NAME_MAP: Record<string, string> = {
  fetch: '抓取新闻',
  generate: '生成文章',
  collect: '采集笔记',
  distill: '提炼方法论',
  'xhs-package': '生成创作内容',
  'xhs-topic': '生成选题',
  audit: '账号诊断',
  recommend: '智能找对标',
  optimize: '优化 Skill',
}
export const runningTaskName = computed(() => TASK_NAME_MAP[pendingAction.value || ''] || '处理中')
export const hasTaskEvents = computed(() => visibleTaskEvents.value.length > 0 || isVisibleTaskRunning.value)
export const taskSummaryStep = computed(() => {
  if (latestTaskEvent.value) {
    return latestTaskEvent.value.step_name
  }
  return runningTaskName.value
})
export const taskSummaryMessage = computed(() => {
  if (latestTaskEvent.value) {
    return compactTaskMessage(latestTaskEvent.value)
  }
  return '等待任务事件同步'
})
export const taskSummaryStatus = computed(() => {
  if (isVisibleTaskRunning.value) {
    return 'running'
  }
  return latestTaskEvent.value?.status || 'running'
})
export const taskSummaryPayload = computed(() => (latestTaskEvent.value ? eventPayloadSummary(latestTaskEvent.value) : ''))

// ===== 统一实时进度(全站任务通用) =====
// 步骤名通俗化:内部术语 → 用户能看懂的话。命中映射就替换,否则原样(如「{对标账号}准备」这类动态名)。
const STEP_LABEL_MAP: Record<string, string> = {
  样本采集: '准备采集',
  增量分流: '整理笔记池',
  笔记详情: '获取笔记内容',
  样本入库: '保存笔记',
  样本清洗: '去重校验',
  样本质量: '质量检查',
  '视频 ASR': '视频转文字',
  视频字幕: '读取字幕',
  图片理解: '识别图片',
  评论采集: '抓取评论',
  内容标签: '提炼标签',
  基础统计: '统计分析',
  下架对账: '核对在架',
  链接解析: '解析链接',
  定向采集: '定向采集',
  蒸馏选材: '挑选样本',
  认知蒸馏: '提炼方法论',
  思考过程: '思考中',
  自检: '自我检查',
  深度评审: '换视角评审',
  完成: '收尾',
  'Skill 生成': '生成方法论',
  配图: '生成配图',
  平台合规: '平台合规检查',
  对标对比: '对标对比',
  发布包生成: '生成创作内容',
  流程: '总体进度',
  新闻后处理: '筛选评分新闻',
  文章素材准备: '整理素材',
  正文配图: '生成配图',
  正文生成: '撰写正文',
  公众号排版: '排版美化',
  封面生成: '生成封面',
  公众号草稿: '发送草稿'
}
export function humanizeStepName(step: string): string {
  return STEP_LABEL_MAP[step] || step
}

// 已用时:任务开始后每秒 +1,结束清零;用于"算不准百分比"的任务展示真实耗时。
export const taskElapsedSeconds = ref(0)
let elapsedTimer: number | undefined
export function startElapsed() {
  taskElapsedSeconds.value = 0
  window.clearInterval(elapsedTimer)
  elapsedTimer = window.setInterval(() => {
    taskElapsedSeconds.value += 1
  }, 1000)
}
export function stopElapsed() {
  window.clearInterval(elapsedTimer)
  elapsedTimer = undefined
}
export const taskElapsedLabel = computed(() => {
  const s = taskElapsedSeconds.value
  if (s < 60) return `已用 ${s} 秒`
  return `已用 ${Math.floor(s / 60)} 分 ${s % 60} 秒`
})

// 时间线时刻:只显示 时:分:秒。
function formatClock(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(new Date(value))
}

// 通用计数进度:从最新事件反向找 current/total(目前采集会发),有就显示真实进度条。
export const taskCountProgress = computed(() => {
  for (let index = visibleTaskEvents.value.length - 1; index >= 0; index -= 1) {
    const payload = parseEventPayload(visibleTaskEvents.value[index])
    const current = Number(payload?.current)
    const total = Number(payload?.total)
    if (current && total) {
      return { current, total, pct: Math.round((current / total) * 100) }
    }
  }
  return { current: 0, total: 0, pct: 0 }
})

// 逐条高频事件(采集那几个)折叠进进度条,不进时间线,避免刷屏。
const TIMELINE_SPAM_STEPS = new Set(['笔记详情', '样本入库', '视频 ASR', '视频字幕', '评论采集'])
// 统一时间线:通俗步骤名 + 原始文案,最新在上。
export const liveTimeline = computed(() =>
  visibleTaskEvents.value
    .filter((event) => !TIMELINE_SPAM_STEPS.has(event.step_name))
    .map((event) => ({
      id: event.id,
      step: humanizeStepName(event.step_name),
      message: event.message,
      status: event.status,
      time: formatClock(event.created_at)
    }))
    .reverse()
)
// 顶部当前阶段(最新事件,通俗化);没有事件时回退到任务名。
export const liveStage = computed(() => (latestTaskEvent.value ? humanizeStepName(latestTaskEvent.value.step_name) : runningTaskName.value))
export const liveStageMessage = computed(() => latestTaskEvent.value?.message || '正在准备…')

export const articleStateLabel = computed(() => {
  const status = article.value?.status
  return status ? statusText[status] || status : '未生成'
})
export const layoutPreviewStyle = computed(() => ({
  color: layoutForm.text_color === 'inherit' ? 'var(--color-ink)' : layoutForm.text_color,
  fontSize: `${layoutForm.body_font_size}px`,
  lineHeight: layoutForm.line_height
}))
export const layoutPreviewHeadingStyle = computed(() => ({
  color: layoutForm.heading_color === 'inherit' ? 'var(--color-ink)' : layoutForm.heading_color,
  fontSize: `${layoutForm.heading_font_size}px`,
  borderBottomColor: layoutForm.accent_color
}))
export const layoutPreviewImageStyle = computed(() => ({
  borderRadius: `${layoutForm.image_radius}px`
}))
export const layoutPreviewSectionStyle = computed(() => ({
  marginBottom: `${layoutForm.section_spacing}px`
}))

export async function copyText(text: string, label: string) {
  try {
    await navigator.clipboard.writeText(text)
    showMessage(`${label}已复制`)
  } catch {
    showMessage('复制失败，请手动选择文本复制', true)
  }
}

export function openImagePreview(url: unknown, caption: string) {
  const imageUrl = String(url || '').trim()
  if (!imageUrl) {
    return
  }
  previewImage.value = { url: imageUrl, caption }
}

export function closeImagePreview() {
  previewImage.value = null
}

export function handleGlobalKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    closeImagePreview()
    showUserMenu.value = false
  }
}

export function compactTaskMessage(event: OperationTaskEvent) {
  const payload = parseEventPayload(event)
  const progress = payload?.current && payload?.total ? `${payload.current}/${payload.total}` : ''
  if (taskEventsAction.value === 'collect' && progress) {
    return progress
  }
  if (taskEventsAction.value === 'collect') {
    return latestCollectionProgressText() || '采集中'
  }
  const message = progress ? `${event.message} ${progress}` : event.message
  return message.length > 42 ? `${message.slice(0, 42)}...` : message
}

export function latestCollectionProgressText() {
  for (let index = taskEvents.value.length - 1; index >= 0; index -= 1) {
    const payload = parseEventPayload(taskEvents.value[index])
    if (payload?.current && payload?.total) {
      return `${payload.current}/${payload.total}`
    }
  }
  return ''
}

export async function runAction(name: string, label: string, action: () => Promise<void>) {
  pendingAction.value = name
  showMessage(label)
  try {
    await action()
    showMessage('操作完成')
  } catch (error) {
    showMessage(error instanceof Error ? error.message : '操作失败', true)
  } finally {
    pendingAction.value = null
  }
}

export function startFakeProgress(name: TaskActionName) {
  window.clearInterval(progressTimers[name])
  taskProgress[name] = 4
  progressTimers[name] = window.setInterval(() => {
    const current = taskProgress[name]
    if (current < 68) {
      taskProgress[name] = Math.min(68, current + 4)
      return
    }
    if (current < 90) {
      taskProgress[name] = Math.min(90, current + 1.5)
      return
    }
    taskProgress[name] = Math.min(95, current + 0.3)
  }, 700)
}

export function stopFakeProgress(name: TaskActionName, completed: boolean) {
  window.clearInterval(progressTimers[name])
  progressTimers[name] = undefined
  taskProgress[name] = completed ? 100 : 0
}

export function resetFakeProgress(name: TaskActionName) {
  taskProgress[name] = 0
}

export function taskButtonStyle(name: TaskActionName) {
  return { '--progress': `${taskProgress[name]}%` }
}

export function eventPayloadSummary(event: OperationTaskEvent) {
  const payload = parseEventPayload(event)
  if (!payload) {
    return ''
  }
  const entries = Object.entries(payload)
    .filter(([key]) => !['current', 'total'].includes(key))
    .filter(() => taskEventsAction.value !== 'collect')
    .filter(([, value]) => value !== null && value !== '' && value !== undefined)
    .slice(0, 3)
    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : String(value)}`)
  return entries.join(' · ')
}

// 进行中任务持久化:后台任务(RQ/Redis)本身持久,但前端轮询循环和 pendingAction 是内存态,
// 刷新即丢 → 任务从界面消失、还能重复发起。这里把 runningTaskId 落 localStorage,刷新后重挂轮询。
const RUNNING_TASK_KEY = 'pubsync_running_task'
type PersistedTask = { id: string; name: TaskActionName; mainTab: MainTab; subTab?: string | null }
const TERMINAL_TASK_STATUS: string[] = ['succeeded', 'cancelled', 'failed']

function persistRunningTask(name: TaskActionName, id: string) {
  try {
    window.localStorage.setItem(RUNNING_TASK_KEY, JSON.stringify({ id, name, mainTab: activeMainTab.value, subTab: taskEventsSubTab.value }))
  } catch {
    /* localStorage 不可用时静默忽略 */
  }
}
function clearPersistedTask() {
  try {
    window.localStorage.removeItem(RUNNING_TASK_KEY)
  } catch {
    /* 忽略 */
  }
}

// 轮询后台任务直至结束:succeeded/cancelled 调 onSuccess,failed 抛错,超时抛 timeoutMessage。
async function pollTaskUntilDone(
  taskId: string,
  name: TaskActionName,
  onSuccess: () => Promise<void>,
  timeoutMessage: string
) {
  // 最多轮询 2 小时(1440 × 5s):采集/蒸馏/Skill优化等长任务动辄几十分钟,旧的 15 分钟上限会让
  // 进度过早消失、让人误以为任务断了。真正卡死的任务由后端看门狗标记失败,这里轮询时会读到。
  for (let attempt = 0; attempt < 1440; attempt += 1) {
    await wait(5000)
    const [latestTask, latestEvents] = await Promise.all([getTask(taskId), getTaskEvents(taskId)])
    taskEvents.value = latestEvents
    showMessage(latestTask.message)

    if (latestTask.status === 'succeeded') {
      stopFakeProgress(name, true)
      await onSuccess()
      await wait(350)
      showMessage('操作完成')
      return
    }

    if (latestTask.status === 'cancel_requested') {
      showMessage(latestTask.message)
    }

    if (latestTask.status === 'cancelled') {
      stopFakeProgress(name, false)
      await onSuccess()
      showMessage(latestTask.message || '任务已停止')
      return
    }

    if (latestTask.status === 'failed') {
      throw new Error(latestTask.error_message || latestTask.message || '任务失败')
    }
  }

  throw new Error(timeoutMessage)
}

export async function runTaskAction(
  name: TaskActionName,
  label: string,
  startTask: () => Promise<OperationTask>,
  onSuccess: () => Promise<void>,
  timeoutMessage: string
) {
  pendingAction.value = name
  taskFailure.value = null
  taskEventsAction.value = name
  taskEventsMainTab.value = activeMainTab.value
  taskEventsSubTab.value = activeSubTab.value
  showTaskEventDetails.value = false
  startFakeProgress(name)
  startElapsed()
  showMessage(label)
  try {
    const task = await startTask()
    runningTaskId.value = task.id
    persistRunningTask(name, task.id)
    showMessage(task.message)
    taskEvents.value = await getTaskEvents(task.id)
    await pollTaskUntilDone(task.id, name, onSuccess, timeoutMessage)
  } catch (error) {
    stopFakeProgress(name, false)
    const msg = error instanceof Error ? error.message : '操作失败'
    taskFailure.value = { action: name, message: msg }  // 持久错误横幅,视图据此显示
    showMessage(msg, true)
  } finally {
    pendingAction.value = null
    runningTaskId.value = null
    clearPersistedTask()
    stopElapsed()
    window.setTimeout(() => resetFakeProgress(name), 300)
  }
}

// 刷新后恢复:若 localStorage 记录了进行中任务,重新挂上轮询并恢复运行态(pendingAction 一并恢复,
// 从而禁用采集/蒸馏按钮、避免重复发起)。任务已结束或不存在则清掉记录。
export async function resumeRunningTaskIfAny() {
  let persisted: PersistedTask | null = null
  try {
    const raw = window.localStorage.getItem(RUNNING_TASK_KEY)
    persisted = raw ? (JSON.parse(raw) as PersistedTask) : null
  } catch {
    persisted = null
  }
  if (!persisted || !persisted.id || !persisted.name) return

  const { id, name, mainTab } = persisted
  let task: OperationTask
  try {
    task = await getTask(id)
  } catch {
    clearPersistedTask() // 任务已不存在(可能被清理),清掉记录即可
    return
  }
  if (TERMINAL_TASK_STATUS.includes(task.status)) {
    clearPersistedTask()
    return
  }

  pendingAction.value = name
  taskEventsAction.value = name
  taskEventsMainTab.value = (mainTab as MainTab) || activeMainTab.value
  taskEventsSubTab.value = persisted.subTab ?? null
  showTaskEventDetails.value = false
  startFakeProgress(name)
  startElapsed()
  runningTaskId.value = id
  showMessage('检测到后台仍有任务在执行，正在恢复进度…')
  try {
    taskEvents.value = await getTaskEvents(id)
    await pollTaskUntilDone(id, name, async () => { await loadAll() }, '任务仍在后台执行，请稍后刷新页面查看结果')
  } catch (error) {
    stopFakeProgress(name, false)
    showMessage(error instanceof Error ? error.message : '任务执行失败', true)
  } finally {
    pendingAction.value = null
    runningTaskId.value = null
    clearPersistedTask()
    stopElapsed()
    window.setTimeout(() => resetFakeProgress(name), 300)
  }
}

export async function handleCancelDistillation() {
  if (!runningTaskId.value || pendingAction.value !== 'distill') {
    return
  }
  try {
    const task = await cancelTask(runningTaskId.value)
    showMessage(task.message || '已请求停止蒸馏')
  } catch (error) {
    showMessage(error instanceof Error ? error.message : '停止蒸馏失败', true)
  }
}

export function setArticle(nextArticle: Article | null) {
  article.value = nextArticle
  form.title = nextArticle?.title || ''
  form.intro = nextArticle?.intro || ''
  form.cover_image_url = nextArticle?.cover_image_url || ''
  form.content_html = nextArticle?.content_html || ''
}

export async function loadAll() {
  const [nextConfig, nextNews, nextArticle, nextBloggers, nextSkills, nextXhsPackages] = await Promise.all([
    getWorkspaceConfig(),
    listNews(),
    getLatestArticle(),
    listBloggers(currentSocialPlatform.value),
    listBloggerSkills(currentSocialPlatform.value),
    listXhsPublishPackages()
  ])
  setWorkspaceConfig(nextConfig)
  news.value = nextNews
  newsPage.value = 1
  setArticle(nextArticle)
  bloggers.value = nextBloggers
  bloggerSkills.value = nextSkills
  xhsPackages.value = nextXhsPackages
  syncXhsPackageSelection()
  if (selectedBloggerId.value && !nextBloggers.some((blogger) => blogger.id === selectedBloggerId.value)) {
    selectedBloggerId.value = null
    selectedCollectionRunId.value = null
    selectedBloggerRunId.value = null
    resultCollectionFilterId.value = null
  }
  await refreshSelectedBlogger()
  await refreshAppraisalRun()
  await refreshSelfAppraisalRun()
}

export function setWorkspaceConfig(config: WorkspaceConfig) {
  profile.value = config.profile
  profileForm.publication_name = config.profile.publication_name
  profileForm.workspace_title = config.profile.workspace_title
  profileForm.title_prefix = config.profile.title_prefix
  profileForm.grouping_mode = config.profile.grouping_mode
  profileForm.content_domain = config.profile.content_domain
  profileForm.editor_persona = config.profile.editor_persona
  profileForm.audience = config.profile.audience
  profileForm.article_style = config.profile.article_style
  profileForm.categories_json = config.profile.categories_json
  profileForm.image_style = config.profile.image_style
  contentGroups.value = [...config.content_groups].sort((a, b) => a.position - b.position)
  contentGroupForms.value = contentGroups.value.map((group) => ({ ...group }))
  activeNewsTab.value = visibleNewsTabs.value[0]?.group_key || 'all'
  wechatForm.app_id = config.wechat.app_id
  wechatForm.app_secret = ''
  wechatForm.app_secret_configured = config.wechat.app_secret_configured
  layoutForm.template_name = config.layout.template_name
  layoutForm.primary_color = config.layout.primary_color
  layoutForm.accent_color = config.layout.accent_color
  layoutForm.text_color = config.layout.text_color
  layoutForm.heading_color = config.layout.heading_color
  layoutForm.body_font_size = config.layout.body_font_size
  layoutForm.heading_font_size = config.layout.heading_font_size
  layoutForm.line_height = config.layout.line_height
  layoutForm.section_spacing = config.layout.section_spacing
  layoutForm.image_radius = config.layout.image_radius
  layoutForm.show_group_heading = config.layout.show_group_heading
  layoutForm.show_source = config.layout.show_source
  layoutForm.show_editor_note = config.layout.show_editor_note
  Object.assign(publishingForm, config.publishing)
  publishingForm.publish_time_value = formatScheduleTime(config.publishing.publish_time_hour, config.publishing.publish_time_minute)
}

export async function loadTenantOptions() {
  const [nextUser, nextTenants] = await Promise.all([getCurrentUser(), listTenants()])
  currentUser.value = nextUser
  tenants.value = nextTenants
  const current = selectedTenantId.value
  const selected = nextTenants.find((tenant) => String(tenant.id) === current) || nextTenants[0]
  if (selected) {
    selectedTenantId.value = String(selected.id)
    setTenantId(selected.id)
  }
}

export async function handleLogin(credentials: { username: string; password: string }) {
  isLoggingIn.value = true
  loginMessage.value = ''
  try {
    await login(credentials.username, credentials.password)
    isAuthenticated.value = true
    await loadTenantOptions()
    await loadAll()
  } catch (error) {
    loginMessage.value = error instanceof Error ? error.message : '登录失败'
  } finally {
    isLoggingIn.value = false
  }
}

export function handleLogout() {
  clearAuthToken()
  clearTenantId()
  isAuthenticated.value = false
  news.value = []
  bloggers.value = []
  bloggerPosts.value = []
  bloggerCollectionRuns.value = []
  bloggerRuns.value = []
  bloggerSkills.value = []
  xhsPackages.value = []
  currentXhsDraft.value = null
  selectedBloggerId.value = null
  selectedCollectionRunId.value = null
  selectedBloggerRunId.value = null
  resultCollectionFilterId.value = null
  selectedXhsPackageId.value = null
  currentUser.value = null
  tenants.value = []
  profile.value = null
  contentGroups.value = []
  contentGroupForms.value = []
  showUserMenu.value = false
  taskEvents.value = []
  taskEventsAction.value = null
  setArticle(null)
  showMessage('')
}

export function toggleUserMenu() {
  showUserMenu.value = !showUserMenu.value
}

export async function handleTenantChange() {
  if (!selectedTenantId.value) {
    return
  }
  setTenantId(selectedTenantId.value)
  taskEvents.value = []
  taskEventsAction.value = null
  showMessage('正在切换工作空间')
  try {
    await loadAll()
    showMessage('工作空间已切换')
  } catch (error) {
    showMessage(error instanceof Error ? error.message : '切换工作空间失败', true)
  }
}

export async function refreshArticle() {
  const nextArticle = await getLatestArticle()
  setArticle(nextArticle)
}

export async function refreshBloggers() {
  bloggers.value = await listBloggers(currentSocialPlatform.value)
  bloggerSkills.value = await listBloggerSkills(currentSocialPlatform.value)
  syncXhsPackageSelection()
  if (selectedBloggerId.value && !bloggers.value.some((item) => item.id === selectedBloggerId.value)) {
    selectedBloggerId.value = null
    selectedCollectionRunId.value = null
    selectedBloggerRunId.value = null
    resultCollectionFilterId.value = null
  }
  await refreshSelectedBlogger()
}

export function syncXhsPackageSelection() {
  if (!xhsCreatorBloggerId.value && activeXhsSkills.value.length) {
    xhsCreatorBloggerId.value = activeXhsSkills.value[0].blogger_id
  }
  if (
    !xhsPackageForm.skill_id ||
    !xhsCreatorSkillOptions.value.some((skill) => skill.id === xhsPackageForm.skill_id && skill.status === 'active')
  ) {
    xhsPackageForm.skill_id = xhsCreatorSkillOptions.value[0]?.id || activeXhsSkills.value[0]?.id || 0
  }
  if (selectedXhsPackageId.value && !xhsPackages.value.some((item) => item.id === selectedXhsPackageId.value)) {
    selectedXhsPackageId.value = null
  }
}

export function resetXhsTopicIdeas() {
  xhsTopicIdeas.value = []
  selectedXhsTopicIndex.value = null
  currentXhsDraft.value = null
}

export function handleXhsCreatorBloggerChange() {
  xhsPackageForm.skill_id = xhsCreatorSkillOptions.value[0]?.id || 0
  resetXhsTopicIdeas()
  xhsCreationStep.value = 1
}

export function handleXhsCreatorSkillChange() {
  resetXhsTopicIdeas()
  xhsCreationStep.value = 1
}

export function selectXhsTopicIdea(index: number) {
  const idea = xhsTopicIdeas.value[index]
  if (!idea) {
    return
  }
  selectedXhsTopicIndex.value = index
  xhsPackageForm.topic = idea.title
  xhsPackageForm.target_audience = idea.target_audience || xhsPackageForm.target_audience
  xhsPackageForm.content_goal = idea.content_goal || xhsPackageForm.content_goal
  xhsPackageForm.keywords = idea.keywords.join(', ')
  currentXhsDraft.value = null
  xhsCreationStep.value = Math.max(xhsCreationStep.value, 3)
}

export function goPreviousXhsCreationStep() {
  xhsCreationStep.value = Math.max(1, xhsCreationStep.value - 1)
}

export function goNextXhsCreationStep() {
  if (!canGoNextXhsCreationStep.value) {
    const messages: Record<number, string> = {
      1: '请先选择博主',
      2: '请先选择 Skill',
      3: '请先选择一个选题方案',
      4: '请先生成正文或脚本',
      5: '请先完成素材输出'
    }
    showMessage(messages[xhsCreationStep.value] || '当前步骤还没有完成', true)
    return
  }
  xhsCreationStep.value = Math.min(6, xhsCreationStep.value + 1)
}

export function goPreviousXhsCollectStep() {
  xhsCollectStep.value = Math.max(1, xhsCollectStep.value - 1)
}

export function goNextXhsCollectStep() {
  if (!canGoNextXhsCollectStep.value) {
    showMessage(xhsCollectStep.value === 1 ? '请先选择博主' : '当前步骤还没有完成', true)
    return
  }
  xhsCollectStep.value = Math.min(4, xhsCollectStep.value + 1)
}

export function goPreviousXhsDistillStep() {
  xhsDistillStep.value = Math.max(1, xhsDistillStep.value - 1)
}

export function goNextXhsDistillStep() {
  if (!canGoNextXhsDistillStep.value) {
    showMessage(xhsDistillStep.value === 1 ? '请先选择博主' : '请先选择已完成的采集批次', true)
    return
  }
  xhsDistillStep.value = Math.min(4, xhsDistillStep.value + 1)
}

export function goPreviousWechatBriefStep() {
  wechatBriefStep.value = Math.max(1, wechatBriefStep.value - 1)
}

export function goNextWechatBriefStep() {
  if (!canGoNextWechatBriefStep.value) {
    showMessage('请先生成文章再进入预览', true)
    return
  }
  wechatBriefStep.value = Math.min(4, wechatBriefStep.value + 1)
}

export async function refreshSelectedBlogger() {
  if (!selectedBloggerId.value) {
    bloggerPosts.value = []
    bloggerCollectionRuns.value = []
    bloggerRuns.value = []
    bloggerSnapshots.value = []
    selectedPostIds.value = []
    activeNotePostId.value = null
    selectedCollectionRunId.value = null
    selectedBloggerRunId.value = null
    resultCollectionFilterId.value = null
    return
  }
  // 阶段B:博主资产以「笔记池」为中心,一次性拉全量笔记 + 快照 + 蒸馏记录(不再按采集批次取样本)。
  // 采集批次仍拉取(数据采集页要用),但博主资产页不再展示「采集历史」。
  const [posts, snapshots, collections, runs, skills] = await Promise.all([
    listBloggerPosts(selectedBloggerId.value),
    listBloggerSnapshots(selectedBloggerId.value),
    listBloggerCollectionRuns(selectedBloggerId.value),
    listBloggerRuns(selectedBloggerId.value),
    listBloggerSkills(currentSocialPlatform.value)
  ])
  bloggerPosts.value = posts
  bloggerSnapshots.value = snapshots
  bloggerCollectionRuns.value = collections
  bloggerRuns.value = runs
  bloggerSkills.value = skills
  // 选中集只保留仍在池中的笔记(下架/被删的剔除)。
  const poolIds = new Set(posts.map((p) => p.id))
  selectedPostIds.value = selectedPostIds.value.filter((id) => poolIds.has(id))
  if (activeNotePostId.value && !poolIds.has(activeNotePostId.value)) {
    activeNotePostId.value = null
  }
  if (selectedBloggerRunId.value && !runs.some((run) => run.id === selectedBloggerRunId.value)) {
    selectedBloggerRunId.value = null
  }
}

export async function refreshXhsPackages(selectedId?: number) {
  xhsPackages.value = await listXhsPublishPackages()
  selectedXhsPackageId.value = selectedId || xhsPackages.value[0]?.id || null
}

export function resetBloggerSearch() {
  bloggerSearchKeyword.value = ''
  bloggerSearchResults.value = []
  selectedBloggerCandidate.value = null
}

export function resetBloggerForm() {
  bloggerForm.external_id = ''
  bloggerForm.display_name = ''
  bloggerForm.homepage_url = ''
  bloggerForm.avatar_url = ''
  bloggerForm.follower_count = 0
  bloggerForm.niche = ''
  bloggerForm.description = ''
  bloggerForm.tags = ''
}

export function closeBloggerModal() {
  showBloggerModal.value = false
  editingBloggerId.value = null
  resetBloggerSearch()
  resetBloggerForm()
  resetBenchmarkFinder()
}

export function openCreateBloggerModal() {
  editingBloggerId.value = null
  bloggerModalAccountType.value = 'benchmark'
  resetBloggerForm()
  resetBloggerSearch()
  resetBenchmarkFinder()
  showBloggerModal.value = true
}

export function openEditBloggerModal(blogger: BloggerProfile) {
  editingBloggerId.value = blogger.id
  bloggerForm.external_id = blogger.external_id || ''
  bloggerForm.display_name = blogger.display_name
  bloggerForm.homepage_url = blogger.homepage_url
  bloggerForm.avatar_url = blogger.avatar_url
  bloggerForm.follower_count = blogger.follower_count
  bloggerForm.niche = blogger.niche
  bloggerForm.description = blogger.description
  // 只把手动标签放进可编辑输入框;自动标签只读展示、不在此编辑。
  bloggerForm.tags = (blogger.tags || [])
    .filter((tag) => tag.source === 'manual')
    .map((tag) => tag.name)
    .join('，')
  resetBloggerSearch()
  showBloggerModal.value = true
}


// —— 对标博主搜寻:智能推荐 / 单博主评分(共用意图 + 可选「我的账号」)——
export const benchmarkIntent = reactive<BenchmarkIntent>({ niche: '', audience: '', goal: '', content_form: 'any' })
export const benchmarkMyAccountId = ref<number | null>(null)
export const benchmarkCandidates = ref<CandidateScore[]>([])
// 搜索 tab:按 external_id 缓存「评估」结果。
export const benchmarkSearchScores = reactive<Record<string, CandidateScore>>({})
export const benchmarkEvaluatingId = ref<string | null>(null)
export const benchmarkLinkUrl = ref('')
export const benchmarkLinkResult = ref<CandidateScore | null>(null)

function benchmarkIntentValid(): boolean {
  if (!benchmarkIntent.niche.trim()) {
    showMessage('请先填写你的领域/赛道', true)
    return false
  }
  return true
}

function benchmarkPayloadIntent(): BenchmarkIntent {
  return {
    niche: benchmarkIntent.niche.trim(),
    audience: benchmarkIntent.audience?.trim() || '',
    goal: benchmarkIntent.goal?.trim() || '',
    content_form: benchmarkIntent.content_form || 'any'
  }
}

export function resetBenchmarkFinder() {
  benchmarkCandidates.value = []
  benchmarkLinkUrl.value = ''
  benchmarkLinkResult.value = null
  benchmarkEvaluatingId.value = null
  for (const key of Object.keys(benchmarkSearchScores)) delete benchmarkSearchScores[key]
}

// 智能推荐:按意图找一批对标博主(异步任务 + 进度面板),完成后取最新一次运行的候选。
export async function handleRecommendBloggers() {
  if (!benchmarkIntentValid()) return
  benchmarkCandidates.value = []
  let taskId = ''
  await runTaskAction(
    'recommend',
    '正在帮你找对标博主',
    async () => {
      const task = await recommendBloggers({
        platform: currentSocialPlatform.value,
        intent: benchmarkPayloadIntent(),
        my_account_id: benchmarkMyAccountId.value
      })
      taskId = task.id
      return task
    },
    async () => {
      const runs = await listRecommendRuns(taskId, currentSocialPlatform.value)
      benchmarkCandidates.value = runs[0]?.candidates || []
    },
    '推荐仍在后台执行，请稍后刷新查看'
  )
}

// 搜索 tab:对某一条搜索结果单独「评估」(同步,跑完整四项指标)。
export async function handleEvaluateSearchCandidate(candidate: BloggerSearchResult) {
  if (!benchmarkIntentValid()) return
  benchmarkEvaluatingId.value = candidate.external_id
  try {
    const res = await evaluateBlogger({
      platform: currentSocialPlatform.value,
      intent: benchmarkPayloadIntent(),
      my_account_id: benchmarkMyAccountId.value,
      candidate
    })
    benchmarkSearchScores[candidate.external_id] = res.candidate
  } catch (error) {
    showMessage(error instanceof Error ? error.message : '评估失败', true)
  } finally {
    benchmarkEvaluatingId.value = null
  }
}

// 链接评分 tab:粘贴主页链接,评估这一个博主。
export async function handleEvaluateLink() {
  if (!benchmarkIntentValid()) return
  const url = benchmarkLinkUrl.value.trim()
  if (!url) {
    showMessage('请粘贴博主主页链接', true)
    return
  }
  benchmarkLinkResult.value = null
  await runAction('benchmark-evaluate', '正在评估该博主', async () => {
    const res = await evaluateBlogger({
      platform: currentSocialPlatform.value,
      intent: benchmarkPayloadIntent(),
      my_account_id: benchmarkMyAccountId.value,
      homepage_url: url
    })
    benchmarkLinkResult.value = res.candidate
  })
}

// 采用候选 → 打开「确认对标博主」弹窗(仅确认表单,候选已选好),用户补领域/备注后保存。
// 接受 CandidateScore(已评估)或 BloggerSearchResult(搜索未评估),只用两者共有字段。
export function adoptBenchmarkCandidate(candidate: CandidateScore | BloggerSearchResult) {
  editingBloggerId.value = null
  bloggerModalAccountType.value = 'benchmark'
  resetBloggerForm()
  selectBloggerCandidate({
    platform: candidate.platform,
    external_id: candidate.external_id,
    display_name: candidate.display_name,
    homepage_url: candidate.homepage_url,
    avatar_url: candidate.avatar_url,
    description: candidate.description,
    follower_count: candidate.follower_count,
    raw: {}
  })
  showBloggerModal.value = true
  showMessage(`已选「${candidate.display_name}」,补充领域/备注后点保存即可`)
}

// —— Skill 优化 ——
export const optimizeBloggerId = ref<number | null>(null)
export const optimizeSkillId = ref<number | null>(null)
export const currentTrainingRun = ref<SkillTrainingRun | null>(null)
export const trainingRuns = ref<SkillTrainingRun[]>([]) // 该博主的历史优化记录(新→旧)
export const optimizeConfirming = ref(false)

// 所选博主下的 Skill 版本(active 在前);用于让用户选具体哪个 Skill 来优化。
export const optimizeSkillOptions = computed(() =>
  bloggerSkills.value
    .filter((s) => s.blogger_id === optimizeBloggerId.value)
    .sort((a, b) => (a.status === 'active' ? -1 : b.status === 'active' ? 1 : 0))
)

async function loadTrainingRuns(bloggerId: number | null) {
  if (!bloggerId) {
    trainingRuns.value = []
    return
  }
  try {
    trainingRuns.value = await listSkillTrainingRuns(bloggerId)
  } catch {
    trainingRuns.value = []
  }
}

// 切博主时:把 Skill 选择重置到 active 版本,并加载该博主的历史优化记录。
watch(optimizeBloggerId, async (bloggerId) => {
  const opts = optimizeSkillOptions.value
  const active = opts.find((s) => s.status === 'active')
  optimizeSkillId.value = active?.id ?? opts[0]?.id ?? null
  currentTrainingRun.value = null
  await loadTrainingRuns(bloggerId)
})

export function selectTrainingRun(run: SkillTrainingRun) {
  currentTrainingRun.value = run
}

export async function handleOptimizeSkill() {
  const bloggerId = optimizeBloggerId.value
  if (!bloggerId) {
    showMessage('请先选择要优化的对标博主', true)
    return
  }
  const skillId = optimizeSkillId.value
  currentTrainingRun.value = null
  await runTaskAction(
    'optimize',
    '正在优化 Skill',
    async () => optimizeSkill(bloggerId, 2, skillId),
    async () => {
      await loadTrainingRuns(bloggerId)
      currentTrainingRun.value = trainingRuns.value[0] || null
    },
    '优化仍在后台执行，请稍后刷新查看'
  )
}

export async function handleConfirmOptimize(adopt: boolean) {
  const run = currentTrainingRun.value
  if (!run) return
  optimizeConfirming.value = true
  try {
    const updated = await confirmSkillTrainingRun(run.id, adopt)
    currentTrainingRun.value = updated
    // 历史列表里同步这条记录的最新状态。
    const idx = trainingRuns.value.findIndex((r) => r.id === updated.id)
    if (idx >= 0) trainingRuns.value[idx] = updated
    showMessage(adopt ? '已采纳:优化版已设为当前 Skill' : '已放弃:保留原 Skill')
    if (adopt) {
      bloggerSkills.value = await listBloggerSkills(currentSocialPlatform.value)
    }
  } catch (error) {
    showMessage(error instanceof Error ? error.message : '操作失败', true)
  } finally {
    optimizeConfirming.value = false
  }
}

export async function handleSearchBloggerCandidates() {
  const keyword = bloggerSearchKeyword.value.trim()
  if (!keyword) {
    showMessage('请输入博主名称或关键词', true)
    return
  }
  await runAction('blogger-search', '正在搜索博主', async () => {
    bloggerSearchResults.value = await searchBloggers(currentSocialPlatform.value, keyword)
    selectedBloggerCandidate.value = null
    if (!bloggerSearchResults.value.length) {
      showMessage('没有搜索到匹配的博主', true)
    }
  })
}

export function selectBloggerCandidate(candidate: BloggerSearchResult) {
  selectedBloggerCandidate.value = candidate
  bloggerForm.external_id = candidate.external_id
  bloggerForm.display_name = candidate.display_name
  bloggerForm.homepage_url = candidate.homepage_url
  bloggerForm.avatar_url = candidate.avatar_url
  bloggerForm.follower_count = candidate.follower_count
  bloggerForm.description = candidate.description || bloggerForm.description
}

export async function handleCreateBlogger() {
  if (!bloggerForm.display_name.trim() || !bloggerForm.homepage_url.trim()) {
    showMessage('请先搜索并选择一个博主', true)
    return
  }
  await runAction('blogger', '正在保存博主档案', async () => {
    const payload = {
      external_id: bloggerForm.external_id || null,
      display_name: bloggerForm.display_name,
      homepage_url: bloggerForm.homepage_url,
      avatar_url: bloggerForm.avatar_url,
      follower_count: bloggerForm.follower_count,
      niche: bloggerForm.niche,
      description: bloggerForm.description
    }
    const isEditing = Boolean(editingBloggerId.value)
    const manualTags = bloggerForm.tags
      .split(/[，,、\n]/)
      .map((tag) => tag.trim())
      .filter(Boolean)
    const blogger = isEditing
      ? await updateBlogger(editingBloggerId.value!, { ...payload, tags: manualTags })
      : await createBlogger({
          platform: currentSocialPlatform.value,
          account_type: bloggerModalAccountType.value,
          ...payload
        })
    selectedBloggerId.value = blogger.id
    selectedBloggerRunId.value = null
    resultCollectionFilterId.value = null
    if (!isEditing) {
      xhsCollectStep.value = 2
    }
    closeBloggerModal()
    await refreshBloggers()
    showMessage(isEditing ? '博主信息已更新' : '博主档案已保存')
  })
}

export async function handleToggleBloggerFavorite(blogger: BloggerProfile) {
  await runAction('blogger-favorite', blogger.is_favorite ? '正在取消标记' : '正在标记博主', async () => {
    const updated = await updateBloggerFavorite(blogger.id, !blogger.is_favorite)
    await refreshBloggers()
    selectedBloggerId.value = updated.id
    showMessage(updated.is_favorite ? '已标记博主' : '已取消标记')
  })
}

export async function handleRefreshBlogger(blogger: BloggerProfile) {
  await runAction('blogger-refresh', '正在刷新博主资料', async () => {
    const updated = await refreshBloggerProfile(blogger.id)
    await refreshBloggers()
    selectedBloggerId.value = updated.id
    showMessage('博主资料已刷新')
  })
}

export async function handleDeleteBlogger(blogger: BloggerProfile) {
  const confirmed = window.confirm(
    `确认删除“${blogger.display_name}”吗？\n\n删除后会同时删除这个博主的采集批次、样本、蒸馏记录、Skill 和发布包，且无法在页面内恢复。`
  )
  if (!confirmed) {
    return
  }
  await runAction('blogger-delete', '正在删除博主资产', async () => {
    await deleteBlogger(blogger.id)
    if (selectedBloggerId.value === blogger.id) {
      selectedBloggerId.value = null
      selectedCollectionRunId.value = null
      selectedBloggerRunId.value = null
      resultCollectionFilterId.value = null
      bloggerPosts.value = []
      bloggerCollectionRuns.value = []
      bloggerRuns.value = []
    }
    await refreshBloggers()
    await refreshXhsPackages()
    showMessage('博主及关联资产已删除')
  })
}

// 蒸馏完成后选中最新一次蒸馏记录(后端按 created_at 倒序返回,取首个)。
function selectNewestBloggerRun() {
  selectedBloggerRunId.value = bloggerRuns.value[0]?.id ?? null
}

// 自动蒸馏:一键,系统取高赞 top-N(服务端算),不建快照。
export async function handleAutoDistill() {
  if (!selectedBloggerId.value) {
    showMessage('请先选择博主', true)
    return
  }
  if (activeNotePool.value.length < DISTILL_MIN_SAMPLES) {
    showMessage(`笔记池不足 ${DISTILL_MIN_SAMPLES} 篇，先去「数据采集」多采一些再蒸馏`, true)
    return
  }
  await runTaskAction(
    'distill',
    '已提交自动蒸馏任务（高赞 top-N）',
    () => distillBlogger(selectedBloggerId.value!, { source: 'auto', mode: 'A' }),
    async () => {
      await refreshSelectedBlogger()
      selectNewestBloggerRun()
    },
    '博主蒸馏仍在后台执行，请稍后刷新页面查看待确认结果'
  )
}

// 自定义蒸馏:用当前勾选的 N 篇(手选会自动存一个快照)。
export async function handleCustomDistill(snapshotName?: string) {
  if (!selectedBloggerId.value) {
    showMessage('请先选择博主', true)
    return
  }
  if (selectedPostIds.value.length < DISTILL_MIN_SAMPLES) {
    showMessage(`自定义蒸馏至少需勾选 ${DISTILL_MIN_SAMPLES} 篇（建议 ≥${DISTILL_RECOMMEND_SAMPLES} 篇，越多越准）`, true)
    return
  }
  const postIds = [...selectedPostIds.value]
  await runTaskAction(
    'distill',
    '已提交自定义蒸馏任务',
    () =>
      distillBlogger(selectedBloggerId.value!, {
        source: 'custom',
        post_ids: postIds,
        snapshot_name: (snapshotName || '').trim() || undefined,
        mode: 'A'
      }),
    async () => {
      await refreshSelectedBlogger()
      selectNewestBloggerRun()
    },
    '博主蒸馏仍在后台执行，请稍后刷新页面查看待确认结果'
  )
}

// 自定义蒸馏:复用一个已有快照。
export async function handleDistillFromSnapshot(snapshotId: number) {
  if (!selectedBloggerId.value) {
    showMessage('请先选择博主', true)
    return
  }
  await runTaskAction(
    'distill',
    '已提交自定义蒸馏任务（来自快照）',
    () => distillBlogger(selectedBloggerId.value!, { source: 'custom', snapshot_id: snapshotId, mode: 'A' }),
    async () => {
      await refreshSelectedBlogger()
      selectNewestBloggerRun()
    },
    '博主蒸馏仍在后台执行，请稍后刷新页面查看待确认结果'
  )
}

// 把当前勾选保存为命名快照(可复用/回看)。
export async function handleSaveSnapshot(name?: string) {
  if (!selectedBloggerId.value) return
  if (!selectedPostIds.value.length) {
    showMessage('请先勾选要存入快照的笔记', true)
    return
  }
  await runAction('snapshot-save', '正在保存快照', async () => {
    await createBloggerSnapshot(selectedBloggerId.value!, {
      name: (name || '').trim() || undefined,
      post_ids: [...selectedPostIds.value]
    })
    await refreshSelectedBlogger()
    selectedPostIds.value = []
    showMessage('已保存快照')
  })
}

// 改名 / 重选笔记(name、postIds 可单独或一起传)。
export async function handleUpdateSnapshot(snapshotId: number, payload: { name?: string; postIds?: number[] }) {
  if (!selectedBloggerId.value) return
  const body: { name?: string; post_ids?: number[] } = {}
  if (payload.name !== undefined) body.name = payload.name.trim()
  if (payload.postIds !== undefined) body.post_ids = payload.postIds
  if (body.name === undefined && body.post_ids === undefined) return
  await runAction('snapshot-update', '正在更新快照', async () => {
    await updateBloggerSnapshot(selectedBloggerId.value!, snapshotId, body)
    await refreshSelectedBlogger()
    showMessage('已更新快照')
  })
}

export async function handleDeleteSnapshot(snapshotId: number) {
  if (!selectedBloggerId.value) return
  await runAction('snapshot-delete', '正在删除快照', async () => {
    await deleteBloggerSnapshot(selectedBloggerId.value!, snapshotId)
    await refreshSelectedBlogger()
    showMessage('已删除快照')
  })
}

// 把某快照的笔记载入当前勾选集(便于在此基础上微调后再存/蒸馏)。
export function loadSnapshotIntoSelection(snapshotId: number) {
  const snapshot = bloggerSnapshots.value.find((s) => s.id === snapshotId)
  if (!snapshot) return
  const poolIds = new Set(activeNotePool.value.map((p) => p.id))
  selectedPostIds.value = snapshot.post_ids.filter((id) => poolIds.has(id))
}

// 从蒸馏 run 的 report_json 里解析模式与质量分，供前端清晰展示（不改后端 schema）。
export interface DistillRunMeta {
  mode: 'A' | 'B'
  qualityScore: number | null
  qualityGrade: string
  qualityIssues: string[]
  revisions: number
}

export function distillRunMeta(run: BloggerDistillationRun | null | undefined): DistillRunMeta {
  const empty: DistillRunMeta = { mode: 'A', qualityScore: null, qualityGrade: '', qualityIssues: [], revisions: 0 }
  if (!run?.report_json) return empty
  try {
    const parsed = JSON.parse(run.report_json) as {
      mode?: string
      quality?: { score?: number; grade?: string; issues?: string[]; revisions?: number }
    }
    const quality = parsed.quality || {}
    return {
      mode: parsed.mode === 'B' ? 'B' : 'A',
      qualityScore: typeof quality.score === 'number' ? quality.score : null,
      qualityGrade: typeof quality.grade === 'string' ? quality.grade : '',
      qualityIssues: Array.isArray(quality.issues) ? quality.issues : [],
      revisions: typeof quality.revisions === 'number' ? quality.revisions : 0
    }
  } catch {
    return empty
  }
}

// 质量评分对应的语义色调（复用 StatusChip 的色片样式）。
export function qualityTone(grade: string): string {
  if (grade === '优') return 'success'
  if (grade === '良') return 'info'
  if (grade === '待改进') return 'warn'
  return 'neutral'
}

// 账号内容缓存:有缓存就不重拉;force=true 强制重拉。
export async function loadAccountPosts(id: number, force = false) {
  if (!id) return
  // 注意:空数组也是 truthy,不能用它当"已加载"。只有真正有内容才跳过(避免账号在无内容时被缓存成空、之后采集了也不刷新)。
  if (!force && accountPosts[id]?.length) return
  try {
    accountPosts[id] = await listBloggerPosts(id)
  } catch (error) {
    accountPosts[id] = []
    // 不再静默吞错:取内容失败时给提示并打日志,便于定位"选了账号却没内容"的问题。
    console.error('加载账号内容失败 blogger_id=' + id, error)
    showMessage(error instanceof Error ? `加载账号内容失败：${error.message}` : '加载账号内容失败', true)
  }
}

// 刷新某账号内容 = 重新采集一次(消耗 TikHub),完成后重载该账号 posts。
export async function handleCollectAccount(id: number) {
  if (!id) return
  await runTaskAction(
    'collect',
    '已提交内容采集任务',
    () => collectBlogger(id, { sample_limit: 30, comments_per_post: 0 }),
    async () => {
      await loadAccountPosts(id, true)
    },
    '内容采集仍在后台执行，请稍后点刷新查看'
  )
}

export function openCreateMyAccountModal() {
  openCreateBloggerModal()
  bloggerModalAccountType.value = 'mine'
}

// 博主诊断(对标分析 / 诊断我的账号):新版三区报告。诊断 runs 落 AccountAuditRun,按 report 形状区分新旧。
export function parseAppraisalReport(run: AccountAuditRun | null): AppraisalReport | null {
  if (!run?.report_json) return null
  try {
    const p = JSON.parse(run.report_json)
    if (!Array.isArray(p?.hard) || typeof p?.hard_score !== 'number') return null
    return p as AppraisalReport
  } catch {
    return null
  }
}

// 进页面/切平台时回填最近一次「新版」诊断(跳过旧版 audit 记录:旧版 parse 为 null)。
export async function refreshAppraisalRun() {
  try {
    const runs = await listAccountAuditRuns(currentSocialPlatform.value, 'benchmark')
    appraisalRun.value = runs.find((r) => parseAppraisalReport(r)) ?? null
  } catch {
    appraisalRun.value = null
  }
}

// 历史诊断列表:已成功且报告可解析的 benchmark runs(最新在前)。
export async function refreshAppraisalHistory() {
  try {
    const runs = await listAccountAuditRuns(currentSocialPlatform.value, 'benchmark')
    appraisalHistory.value = runs.filter((r) => r.status === 'succeeded' && parseAppraisalReport(r))
  } catch {
    appraisalHistory.value = []
  }
}

export async function refreshSelfAppraisalRun() {
  try {
    const runs = await listAccountAuditRuns(currentSocialPlatform.value, 'self')
    selfAppraisalRun.value = runs.find((r) => parseAppraisalReport(r)) ?? null
  } catch {
    selfAppraisalRun.value = null
  }
}

// 我的诊断记录:已成功且报告可解析的 self runs(最新在前)。
export async function refreshSelfAppraisalHistory() {
  try {
    const runs = await listAccountAuditRuns(currentSocialPlatform.value, 'self')
    selfAppraisalHistory.value = runs.filter((r) => r.status === 'succeeded' && parseAppraisalReport(r))
  } catch {
    selfAppraisalHistory.value = []
  }
}

// —— 意图引导(对标分析诊断别人时)——
export function resetIntentGuide() {
  intentQuestions.value = []
  intentChecked.value = false
  intentClear.value = false
  for (const k of Object.keys(intentSelections)) delete intentSelections[Number(k)]
  for (const k of Object.keys(intentOthers)) delete intentOthers[Number(k)]
}

// —— 意图引导(诊断我的账号:目标 / 痛点 / 阶段)——
export function resetSelfIntentGuide() {
  selfIntentQuestions.value = []
  selfIntentChecked.value = false
  selfIntentClear.value = false
  for (const k of Object.keys(selfIntentSelections)) delete selfIntentSelections[Number(k)]
  for (const k of Object.keys(selfIntentOthers)) delete selfIntentOthers[Number(k)]
}

// 选我的账号后(可选已填目标)→ 看我自己在做什么,出几道「目标/痛点/阶段」多选题(够清晰则不出题)。
// 失败会抛出:由答题打卡进度卡展示「重试 / 跳过直接诊断」,不再静默放行。
export async function fetchSelfIntentSuggestions() {
  if (!selfAppraiseForm.blogger_id) {
    throw new Error('请先选择我的账号')
  }
  selfIntentLoading.value = true
  try {
    const res = await suggestAppraisalIntent({ blogger_id: selfAppraiseForm.blogger_id, intent: selfAppraiseForm.intent, kind: 'self' })
    selfIntentClear.value = res.clear
    selfIntentQuestions.value = res.questions || []
    for (const k of Object.keys(selfIntentSelections)) delete selfIntentSelections[Number(k)]
    for (const k of Object.keys(selfIntentOthers)) delete selfIntentOthers[Number(k)]
    selfIntentQuestions.value.forEach((_, i) => {
      selfIntentSelections[i] = []
      selfIntentOthers[i] = ''
    })
    selfIntentChecked.value = true
  } finally {
    selfIntentLoading.value = false
  }
}

// 自诊断引导失败时「跳过,直接诊断」:清空问题、视为目标已明确,放行诊断。
export function markSelfIntentSkipped() {
  selfIntentClear.value = true
  selfIntentQuestions.value = []
  for (const k of Object.keys(selfIntentSelections)) delete selfIntentSelections[Number(k)]
  for (const k of Object.keys(selfIntentOthers)) delete selfIntentOthers[Number(k)]
  selfIntentChecked.value = true
}

// 答题打卡第一段「读取最近笔记」的真实事件:返回将喂给模型的近期笔记数(真实,≤30)。对标 / 自诊共用。
export async function fetchIntentContext(bloggerId: number) {
  return await fetchAppraisalIntentContext({ blogger_id: bloggerId })
}

// 选博主后(可选已填意图)→ 看 TA 在做什么,判断意图够不够具体;不够则给几道多选题。
// 失败会抛出:由答题打卡进度卡展示「重试 / 跳过直接诊断」,不再静默放行。
export async function fetchIntentSuggestions() {
  if (!appraiseForm.blogger_id) {
    throw new Error('请先选择要诊断的博主')
  }
  intentLoading.value = true
  try {
    const res = await suggestAppraisalIntent({ blogger_id: appraiseForm.blogger_id, intent: appraiseForm.intent })
    intentClear.value = res.clear
    intentQuestions.value = res.questions || []
    for (const k of Object.keys(intentSelections)) delete intentSelections[Number(k)]
    for (const k of Object.keys(intentOthers)) delete intentOthers[Number(k)]
    intentQuestions.value.forEach((_, i) => {
      intentSelections[i] = []
      intentOthers[i] = ''
    })
    intentChecked.value = true
  } finally {
    intentLoading.value = false
  }
}

// 引导失败时用户选择「跳过,直接诊断」:清空问题、视为意图已明确,放行诊断(保留「引导失败不挡诊断」)。
export function markIntentSkipped() {
  intentClear.value = true
  intentQuestions.value = []
  for (const k of Object.keys(intentSelections)) delete intentSelections[Number(k)]
  for (const k of Object.keys(intentOthers)) delete intentOthers[Number(k)]
  intentChecked.value = true
}

// 把「用户填的意图 + 各题所选 / 补充」拼成一句意图。对标(想学什么)与自诊(目标/痛点/阶段)共用。
function composeIntent(
  typed: string,
  questions: AppraisalIntentQuestion[],
  selections: Record<number, string[]>,
  others: Record<number, string>
): string {
  const parts: string[] = []
  const t = (typed || '').trim()
  if (t) parts.push(t)
  questions.forEach((q, i) => {
    const picked = [...(selections[i] || [])]
    const other = (others[i] || '').trim()
    if (other) picked.push(other)
    if (picked.length) parts.push(`${q.q.replace(/[?？]\s*$/, '')}:${picked.join('、')}`)
  })
  return parts.join(';')
}
function buildBenchmarkIntent(): string {
  return composeIntent(appraiseForm.intent, intentQuestions.value, intentSelections, intentOthers)
}
function buildSelfIntent(): string {
  return composeIntent(selfAppraiseForm.intent, selfIntentQuestions.value, selfIntentSelections, selfIntentOthers)
}

export async function handleRunAppraisal() {
  if (!appraiseForm.blogger_id) {
    showMessage('请先选择要诊断的博主', true)
    return
  }
  appraisalRun.value = null
  const intent = buildBenchmarkIntent()
  await runTaskAction(
    'audit',
    '已提交博主诊断任务（会自动确保 ≥20 篇笔记）',
    () =>
      appraiseBlogger({
        blogger_id: appraiseForm.blogger_id,
        kind: 'benchmark',
        intent,
        industry: appraiseForm.industry || null
      }),
    async () => {
      const runs = await listAccountAuditRuns(currentSocialPlatform.value, 'benchmark')
      appraisalRun.value = runs.find((r) => parseAppraisalReport(r)) ?? null
    },
    '博主诊断仍在后台执行，请稍后刷新页面查看结果'
  )
}

// 诊断我的账号(评估与提升):kind=self,无软实力;意图=目标/痛点/阶段,驱动「目标契合」专项。
export async function handleRunSelfAppraisal() {
  if (!selfAppraiseForm.blogger_id) {
    showMessage('请先选择我的账号', true)
    return
  }
  selfAppraisalRun.value = null
  const intent = buildSelfIntent()
  await runTaskAction(
    'audit',
    '已提交账号诊断任务（会自动确保 ≥20 篇笔记）',
    () =>
      appraiseBlogger({
        blogger_id: selfAppraiseForm.blogger_id,
        kind: 'self',
        intent,
        industry: null
      }),
    async () => {
      const runs = await listAccountAuditRuns(currentSocialPlatform.value, 'self')
      selfAppraisalRun.value = runs.find((r) => parseAppraisalReport(r)) ?? null
    },
    '账号诊断仍在后台执行，请稍后刷新页面查看结果'
  )
}

export async function handleCreateXhsPackage() {
  if (!xhsPackageForm.skill_id) {
    showMessage('请先选择一个 Skill', true)
    return
  }
  if (!xhsPackageForm.topic.trim()) {
    showMessage('请填写创作主题', true)
    return
  }
  if (xhsPackageForm.content_type === 'image_note' && xhsPackageForm.image_count_mode === 'manual' && !xhsPackageForm.requested_image_count) {
    showMessage('请选择配图数量', true)
    return
  }
  await runTaskAction(
    'xhs-package',
    '已提交小红书发布包生成任务',
    () =>
      startXhsPublishPackageDraftTask({
        skill_id: xhsPackageForm.skill_id,
        content_type: xhsPackageForm.content_type,
        topic: xhsPackageForm.topic.trim(),
        target_audience: xhsPackageForm.target_audience.trim(),
        content_goal: xhsPackageForm.content_goal.trim(),
        keywords: xhsPackageForm.keywords.trim(),
        image_count_mode: xhsPackageForm.content_type === 'image_note' ? xhsPackageForm.image_count_mode : 'auto',
        requested_image_count:
          xhsPackageForm.content_type === 'image_note' && xhsPackageForm.image_count_mode === 'manual'
            ? xhsPackageForm.requested_image_count
            : null
      }),
    async () => {
      const draft = findXhsDraftFromEvents(taskEvents.value)
      if (!draft) {
        throw new Error('发布包草稿生成完成，但没有返回草稿内容')
      }
      currentXhsDraft.value = draft
      xhsCreationStep.value = 4
    },
    '小红书发布包仍在后台生成，请稍后查看任务进度'
  )
}

export async function handleSaveXhsPackage() {
  if (!currentXhsDraft.value) {
    showMessage('请先生成当前发布包草稿', true)
    return
  }
  await runAction('xhs-package-save', '正在保存发布包', async () => {
    // 绑定目标「我的账号」(可空);用于效果看板按账号统计创作/发布/省时。
    const pack = await saveXhsPublishPackage({ ...currentXhsDraft.value!, my_account_id: xhsPackageForm.my_account_id })
    await refreshXhsPackages(pack.id)
    currentXhsDraft.value = null
    activeXhsTab.value = 'history'
    showMessage('发布包已保存到历史记录')
  })
}

export function handleDiscardXhsDraft() {
  currentXhsDraft.value = null
  xhsCreationStep.value = 4
  showMessage('已放弃本次创作草稿')
}

export async function handleGenerateXhsTopicIdeas() {
  if (!xhsPackageForm.skill_id) {
    showMessage('请先选择博主和 Skill', true)
    return
  }
  await runAction('xhs-topic', '正在生成选题方案', async () => {
    const result = await generateXhsTopicIdeas({
      skill_id: xhsPackageForm.skill_id,
      seed_topic: xhsPackageForm.topic.trim(),
      target_audience: xhsPackageForm.target_audience.trim(),
      content_goal: xhsPackageForm.content_goal.trim(),
      keywords: xhsPackageForm.keywords.trim()
    })
    xhsTopicIdeas.value = result.ideas
    selectedXhsTopicIndex.value = null
    currentXhsDraft.value = null
    xhsCreationStep.value = 3
  })
}

export async function handleCollectBlogger() {
  if (!selectedBloggerId.value) {
    showMessage('请先选择博主', true)
    xhsCollectStep.value = 1
    return
  }
  await runTaskAction(
    'collect',
    '已提交样本采集任务',
    () =>
      collectBlogger(selectedBloggerId.value!, {
        sample_limit: bloggerDistillForm.sample_limit,
        comments_per_post: bloggerDistillForm.comments_per_post,
        content_types: collectContentTypes.value.length ? collectContentTypes.value : ['image', 'video'],
        order: collectOrder.value,
        fetch_all: collectFetchAll.value
      }),
    async () => {
      await refreshSelectedBlogger()
      xhsCollectStep.value = 4
    },
    '样本采集仍在后台执行，请稍后刷新页面查看采集批次'
  )
}

export async function handleCollectByUrls() {
  if (!selectedBloggerId.value) {
    showMessage('请先选择博主', true)
    xhsCollectStep.value = 1
    return
  }
  const urls = urlCollectInput.value
    .split(/[\n\r]+/)
    .map((line) => line.trim())
    .filter(Boolean)
  if (!urls.length) {
    showMessage('请粘贴至少一条笔记链接', true)
    return
  }
  if (urls.length > 20) {
    showMessage('一次最多 20 条链接', true)
    return
  }
  await runTaskAction(
    'collect',
    '已提交定向采集任务',
    () =>
      collectBloggerByUrls(selectedBloggerId.value!, {
        urls,
        comments_per_post: bloggerDistillForm.comments_per_post
      }),
    async () => {
      urlCollectInput.value = ''
      await refreshSelectedBlogger()
      xhsCollectStep.value = 4
    },
    '定向采集仍在后台执行，请稍后刷新页面查看采集批次'
  )
}

export async function selectBlogger(id: number) {
  selectedBloggerId.value = id
  selectedCollectionRunId.value = null
  selectedBloggerRunId.value = null
  resultCollectionFilterId.value = null
  if (currentSocialTab.value === 'distill') {
    xhsDistillStep.value = 2
  } else if (currentSocialTab.value === 'collect') {
    xhsCollectStep.value = 2
  }
  await refreshSelectedBlogger()
}

export async function selectCollectionRun(id: number) {
  if (selectedCollectionRunId.value === id) {
    selectedCollectionRunId.value = null
    selectedBloggerRunId.value = null
    bloggerPosts.value = []
    return
  }
  selectedCollectionRunId.value = id
  selectedBloggerRunId.value = null
  if (selectedBloggerId.value) {
    bloggerPosts.value = await listBloggerCollectionPosts(selectedBloggerId.value, id)
  }
  selectLatestRunForCollection()
}

export function selectBloggerRun(id: number) {
  selectedBloggerRunId.value = id
}

export async function handleConfirmBloggerRun() {
  if (!selectedBloggerId.value || !selectedBloggerRun.value) {
    showMessage('请先选择待确认的蒸馏结果', true)
    return
  }
  await runAction('distill-confirm', '正在保存蒸馏结果', async () => {
    const run = await confirmBloggerRun(selectedBloggerId.value!, selectedBloggerRun.value!.id)
    await refreshSelectedBlogger()
    selectedBloggerRunId.value = run.id
    setCurrentSocialTab('assets')
    showMessage('蒸馏结果已保存，Skill 已进入 AI 创作')
  })
}

export async function handleAbandonBloggerRun() {
  if (!selectedBloggerId.value || !selectedBloggerRun.value) {
    showMessage('请先选择待确认的蒸馏结果', true)
    return
  }
  await runAction('distill-abandon', '正在放弃本次蒸馏结果', async () => {
    const run = await abandonBloggerRun(selectedBloggerId.value!, selectedBloggerRun.value!.id)
    await refreshSelectedBlogger()
    selectedBloggerRunId.value = run.id
    setCurrentSocialTab('assets')
    showMessage('已放弃本次蒸馏结果')
  })
}

export function selectLatestRunForCollection(collectionRunId = selectedCollectionRunId.value) {
  if (!collectionRunId) {
    selectedBloggerRunId.value = null
    return
  }
  const latestRun = bloggerRuns.value.find((run) => run.collection_run_id === collectionRunId)
  selectedBloggerRunId.value = latestRun?.id || null
}

export function showCollectionResults(collectionRunId: number | null) {
  resultCollectionFilterId.value = collectionRunId
  setCurrentSocialTab('assets')
  if (collectionRunId) {
    selectLatestRunForCollection(collectionRunId)
  } else {
    selectedBloggerRunId.value = bloggerRuns.value[0]?.id || null
  }
}

export function showAllBloggerRuns() {
  showCollectionResults(null)
}

export async function handleFetchNews() {
  await runTaskAction(
    'fetch',
    '已提交后台抓取任务',
    fetchNews,
    async () => {
      news.value = await listNews()
      newsPage.value = 1
      await refreshArticle()
    },
    '新闻仍在后台抓取，请稍后刷新页面查看最新候选新闻'
  )
}

export async function handleGenerateArticle() {
  if (!news.value.some((item) => item.selected)) {
    showMessage('请先在第 1 步勾选要写进文章的新闻', true)
    wechatBriefStep.value = 1
    return
  }
  await runTaskAction(
    'generate',
    '已提交后台生成任务',
    generateArticle,
    async () => {
      await refreshArticle()
      activeArticleTab.value = 'preview'
      // 生成成功后自动进入「预览/编辑」步骤(第 3 步)。
      if (hasArticle.value) {
        wechatBriefStep.value = 3
      }
    },
    '文章还在后台生成，请稍后刷新页面查看最新文章'
  )
}

export async function handleSendWechat() {
  if (!article.value) {
    return
  }
  await runAction('wechat', '正在发送到公众号草稿箱', async () => {
    setArticle(await sendArticleToWechat(article.value!.id))
    await refreshArticle()
  })
}

export async function handleToggleNews(item: NewsItem, selected: boolean) {
  item.selected = selected
  try {
    const updated = await updateNewsSelection(item.id, selected)
    news.value = news.value.map((newsItem) => (newsItem.id === updated.id ? updated : newsItem))
    await refreshArticle()
  } catch (error) {
    item.selected = !selected
    showMessage(error instanceof Error ? error.message : '更新新闻失败', true)
  }
}

export async function handleSaveArticle() {
  if (!article.value) {
    return
  }
  await runAction('save', '正在保存文章', async () => {
    setArticle(await updateArticle(article.value!.id, { ...form }))
    await refreshArticle()
  })
}

export async function handleSaveConfig() {
  await runAction('config', '正在保存工作空间配置', async () => {
    const { hour, minute } = parseScheduleTime(publishingForm.publish_time_value)
    const publishingPayload = {
      ...publishingForm,
      publish_time_hour: hour,
      publish_time_minute: minute,
      publish_weekday: Number(publishingForm.publish_weekday),
      publish_month_day: Number(publishingForm.publish_month_day)
    }
    delete (publishingPayload as Partial<typeof publishingForm>).publish_time_value
    const payload = {
      profile: {
        publication_name: profileForm.publication_name,
        workspace_title: profileForm.workspace_title,
        title_prefix: profileForm.title_prefix,
        grouping_mode: profileForm.grouping_mode,
        content_domain: profileForm.content_domain,
        editor_persona: profileForm.editor_persona,
        audience: profileForm.audience,
        article_style: profileForm.article_style,
        categories_json: profileForm.categories_json,
        image_style: profileForm.image_style
      },
      wechat: {
        app_id: wechatForm.app_id,
        ...(wechatForm.app_secret.trim() ? { app_secret: wechatForm.app_secret.trim() } : {})
      },
      layout: { ...layoutForm },
      publishing: publishingPayload,
      content_groups: contentGroupForms.value.map((group, index) => ({
        group_key: group.group_key,
        name: group.name,
        content_mode: group.content_mode,
        source_urls: group.source_urls,
        candidate_limit: group.candidate_limit,
        article_min: group.article_min,
        article_target: group.article_target,
        article_max: group.article_max,
        position: index,
        enabled: group.enabled
      }))
    }
    const nextConfig = await updateWorkspaceConfig(payload)
    setWorkspaceConfig(nextConfig)
    const matchedTenant = tenants.value.find((tenant) => String(tenant.id) === selectedTenantId.value)
    if (matchedTenant) {
      matchedTenant.name = nextConfig.profile.publication_name
    }
  })
}

export function setNewsTab(tab: NewsTab) {
  activeNewsTab.value = tab
  newsPage.value = 1
}

export function addContentGroup() {
  if (contentGroupForms.value.length >= 6) {
    showMessage('最多配置 6 个内容分组', true)
    return
  }
  const nextIndex = contentGroupForms.value.length + 1
  contentGroupForms.value.push({
    id: 0,
    tenant_id: Number(selectedTenantId.value || 0),
    group_key: `group-${nextIndex}`,
    name: `内容分组 ${nextIndex}`,
    content_mode: 'news',
    source_urls: '',
    candidate_limit: 40,
    article_min: 0,
    article_target: 5,
    article_max: 8,
    position: nextIndex - 1,
    enabled: true
  })
}

export function removeContentGroup(index: number) {
  if (contentGroupForms.value.length <= 1) {
    showMessage('至少保留 1 个内容分组', true)
    return
  }
  contentGroupForms.value.splice(index, 1)
}

export function changeNewsPage(delta: number) {
  newsPage.value = Math.min(newsTotalPages.value, Math.max(1, newsPage.value + delta))
}

// 友好时间:今天 14:30 / 昨天 14:30 / 6月16日 14:30(跨年补年份)。比裸日期更直观。
export function friendlyTime(value: string) {
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  const now = new Date()
  const hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  const sameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (sameDay(d, now)) return `今天 ${hm}`
  if (sameDay(d, yesterday)) return `昨天 ${hm}`
  const yearPrefix = d.getFullYear() === now.getFullYear() ? '' : `${d.getFullYear()}年`
  return `${yearPrefix}${d.getMonth() + 1}月${d.getDate()}日 ${hm}`
}

// 「第 N 次」序号:按 created_at 升序(同刻按 id)给每条 run 排名,N=1 最早。
function buildOrdinalMap(runs: { id: number; created_at: string }[]) {
  const sorted = [...runs].sort((a, b) => {
    const diff = new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    return diff !== 0 ? diff : a.id - b.id
  })
  const map = new Map<number, number>()
  sorted.forEach((run, index) => map.set(run.id, index + 1))
  return map
}

export const collectionRunOrdinals = computed(() => buildOrdinalMap(bloggerCollectionRuns.value))
export const distillRunOrdinals = computed(() => buildOrdinalMap(bloggerRuns.value))

export function collectionRunOrdinal(id: number | null | undefined): number | null {
  return id == null ? null : collectionRunOrdinals.value.get(id) ?? null
}

export function distillRunOrdinal(id: number | null | undefined): number | null {
  return id == null ? null : distillRunOrdinals.value.get(id) ?? null
}

export function formatScheduleTime(hour: number, minute: number) {
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
}

export function parseScheduleTime(value: string) {
  const [rawHour, rawMinute] = value.split(':')
  const hour = Math.max(0, Math.min(23, Number(rawHour) || 0))
  const minute = Math.max(0, Math.min(59, Number(rawMinute) || 0))
  return { hour, minute }
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(value))
}

export function groupLabel(groupKey: string) {
  return contentGroups.value.find((group) => group.group_key === groupKey)?.name || groupKey || '未分组'
}

export function setCurrentSocialTab(tab: SocialTab) {
  if (activeMainTab.value === 'douyin') {
    activeDouyinTab.value = tab
    return
  }
  activeXhsTab.value = tab
}


// 表单变更后作废已生成的草稿；切换平台时重置博主相关选择并刷新列表（注册一次，随 store 模块常驻）。
watch(
  () => [
    xhsPackageForm.skill_id,
    xhsPackageForm.content_type,
    xhsPackageForm.topic,
    xhsPackageForm.target_audience,
    xhsPackageForm.content_goal,
    xhsPackageForm.keywords,
    xhsPackageForm.image_count_mode,
    xhsPackageForm.requested_image_count
  ],
  () => {
    currentXhsDraft.value = null
  }
)

watch(
  () => currentSocialPlatform.value,
  async () => {
    if (!isAuthenticated.value || !isSocialPlatform.value) {
      return
    }
    selectedBloggerId.value = null
    selectedCollectionRunId.value = null
    selectedBloggerRunId.value = null
    resultCollectionFilterId.value = null
    bloggerPosts.value = []
    bloggerCollectionRuns.value = []
    bloggerRuns.value = []
    appraisalRun.value = null
    selfAppraisalRun.value = null
    resetIntentGuide()
    resetXhsTopicIdeas()
    await refreshBloggers()
    await refreshAppraisalRun()
    await refreshSelfAppraisalRun()
  }
)
