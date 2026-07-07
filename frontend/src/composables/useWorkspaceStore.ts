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
import {
  computed,
  reactive,
  ref,
  watch
} from 'vue'
import {
  useToast
} from './useToast'
import {
  findXhsDraftFromEvents,
  parseEventPayload,
  parseJsonArray,
  parseJsonObject,
  wait
} from '../utils/format'
import {
  cancelTask,
  clearAuthToken,
  clearTenantId,
  appraiseBlogger,
  listAccountAuditRuns,
  suggestAppraisalIntent,
  fetchAppraisalIntentContext,
  createBlogger,
  deleteBlogger,
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
  listBloggerPosts,
  deleteBloggerPosts,
  listBloggerCollectionRuns,
  listBloggerRuns,
  listBloggerSkills,
  listBloggers,
  listTenants,
  listNews,
  listXhsPublishPackages,
  login,
  sendArticleToWechat,
  saveXhsPublishPackage,
  searchBloggers,
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
  BloggerCollectionRun,
  BloggerDistillationRun,
  BloggerPost,
  BloggerProfile,
  BloggerSearchResult,
  BloggerSkill,
  CandidateScore,
  ContentGroup,
  ContentProfile,
  CurrentUser,
  NewsItem,
  OperationTask,
  OperationTaskEvent,
  SocialPlatform,
  SynthesisTrace,
  Tenant,
  WorkspaceConfig,
  XhsPublishContentType,
  XhsPublishPackage,
  XhsPublishPackageDraft,
  XhsTopicIdea
} from '../api/types'
export type TaskActionName = 'fetch' | 'generate' | 'collect' | 'distill' | 'xhs-package' | 'audit' | 'recommend' | 'dossier' | 'pool-sync'
export type NewsTab = string
export type ArticleTab = 'edit' | 'preview'
export type MainTab = 'wechat' | 'xhs' | 'douyin' | 'admin'
// 每个平台内部用同一套「功能阶段」二级菜单，措辞统一、用户学一次三平台通用。
// 已实现的阶段对应具体 view；未实现的（公众号的 distill/ai、社媒的 freecreate/records/settings）走统一占位。
export type WeChatTab = 'brief' | 'distill' | 'ai' | 'drafts' | 'records' | 'settings'
// 小红书与抖音结构完全相同，共用 SocialTab；XhsTab/DouyinTab 保留为别名，避免大面积改名。
export type SocialTab = 'overview' | 'find' | 'dossier' | 'collect' | 'distill' | 'assets' | 'my-accounts' | 'analysis' | 'packages' | 'history' | 'freecreate' | 'records' | 'settings'
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
// 阶段B:自定义蒸馏勾选集 + 单篇详情抽屉。
export const selectedPostIds = ref<number[]>([])
export const activeNotePostId = ref<number | null>(null)
// 对标分析(诊断别人):诊断一个对标库博主 → 硬/软/合规 三区报告。kind 固定 benchmark。
export const appraiseForm = reactive<{ blogger_id: number; kind: 'benchmark'; intent: string; industry: string; my_blogger_id: number }>({
  blogger_id: 0,
  kind: 'benchmark',
  intent: '',
  industry: '',
  my_blogger_id: 0
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
// 我的账号(account_type=mine)与对标账号拆分。
export const myAccounts = computed(() => bloggers.value.filter((b) => b.account_type === 'mine'))
export const benchmarkAccounts = computed(() => bloggers.value.filter((b) => b.account_type !== 'mine'))
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
  dossier: 0,
  'pool-sync': 0,
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
export const NOTE_GROUP_ORDER = ['image_text', 'talking_video', 'visual_video', 'unknown', '__list__'] as const
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
export const currentUsername = computed(() => currentUser.value?.username || '当前用户')
export const isSocialPlatform = computed(() => activeMainTab.value === 'xhs' || activeMainTab.value === 'douyin')
export const currentSocialPlatform = computed<SocialPlatform>(() => (activeMainTab.value === 'douyin' ? 'douyin' : 'xhs'))
export const currentSocialPlatformName = computed(() => (currentSocialPlatform.value === 'douyin' ? '抖音' : '小红书'))
export const currentSocialTab = computed<SocialTab>(() => (activeMainTab.value === 'douyin' ? activeDouyinTab.value : activeXhsTab.value))
// 当前所在子页签(跨平台统一):用于判断进度条是否在「任务主页」。
export const activeSubTab = computed<string>(() =>
  activeMainTab.value === 'wechat' ? activeWechatTab.value : currentSocialTab.value
)
// 当前平台下的「我的账号」列表(创作时选目标账号用)。
export const myAccountsOnPlatform = computed(() => myAccounts.value.filter((a) => a.platform === currentSocialPlatform.value))

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
export const selectedXhsSkill = computed(() => bloggerSkills.value.find((skill) => skill.id === xhsPackageForm.skill_id) || null)
export const visibleXhsPackages = computed(() => {
  const bloggerIds = new Set(bloggers.value.map((blogger) => blogger.id))
  return xhsPackages.value.filter((item) => bloggerIds.has(item.blogger_id))
})
export const selectedXhsPackage = computed(() => visibleXhsPackages.value.find((item) => item.id === selectedXhsPackageId.value) || visibleXhsPackages.value[0] || null)
export const activeNotePool = computed(() => bloggerPosts.value.filter((p) => p.status !== 'delisted'))
export const delistedNoteCount = computed(() => bloggerPosts.value.filter((p) => p.status === 'delisted').length)

export async function handleDeleteNote(post: BloggerPost) {
  if (!window.confirm('删除这条笔记？将从笔记池移除。')) return
  try {
    await deleteBloggerPosts(post.blogger_id, [post.id])
    showMessage('已删除该笔记')
    bloggerPosts.value = bloggerPosts.value.filter((p) => p.id !== post.id)
    closeNote()
    if (selectedBloggerId.value === post.blogger_id) await refreshSelectedBlogger()
  } catch (err) {
    showMessage(err instanceof Error ? err.message : '删除失败', true)
  }
}

// 详情抽屉的当前笔记:在对标博主笔记池里找。
export const activeNotePost = computed(() => {
  const id = activeNotePostId.value
  if (id == null) return null
  return bloggerPosts.value.find((p) => p.id === id) ?? null
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
export const xhsCreationStepLabels = ['选择对标博主', '生成选题', '生成正文', '封面配图', '确认发布']
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
export const canGoNextXhsCreationStep = computed(() => {
  // 5 步:① 选对标博主(自动带其唯一创作画像)② 选题 ③ 正文 ④ 配图/脚本 ⑤ 确认
  if (xhsCreationStep.value === 1) {
    return Boolean(xhsCreatorBloggerId.value) && Boolean(selectedXhsSkill.value)
  }
  if (xhsCreationStep.value === 2) {
    return Boolean(selectedXhsTopicIdea.value)
  }
  if (xhsCreationStep.value === 3) {
    return Boolean(currentXhsDraft.value)
  }
  if (xhsCreationStep.value === 4) {
    return Boolean(currentXhsDraft.value)
  }
  return false
})
export const visibleTaskEvents = computed(() => {
  if (!taskEventsAction.value) {
    return []
  }
  return taskEventsMainTab.value === activeMainTab.value ? taskEvents.value : []
})
export const latestTaskEvent = computed(() => visibleTaskEvents.value[visibleTaskEvents.value.length - 1] || null)
// 所有会跑一会儿、需要展示进度的动作(统一进度面板据此显示)。
const LONG_RUNNING_ACTIONS = new Set(['fetch', 'generate', 'collect', 'distill', 'xhs-package', 'xhs-topic', 'audit', 'recommend', 'dossier', 'pool-sync'])
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
const TASK_NAME_MAP: Record<string, string> = {
  fetch: '抓取新闻',
  generate: '生成文章',
  collect: '采集笔记',
  distill: '提炼方法论',
  'xhs-package': '生成创作内容',
  'xhs-topic': '生成选题',
  audit: '账号诊断',
  recommend: '智能找对标',
  dossier: '构建档案',
  'pool-sync': '同步笔记池',
}
export const runningTaskName = computed(() => TASK_NAME_MAP[pendingAction.value || ''] || '处理中')
// 把后端「技术步骤名」翻成通俗阶段名。**必须覆盖所有后端会发的 step 名**,漏一个就原样露出技术味;
// 且别和 TASK_NAME_MAP 的任务名取成一模一样(头部会显示「任务名 · 阶段名」,靠 liveHeadline 去重兜底)。
const STEP_LABEL_MAP: Record<string, string> = {
  // 采集 / 笔记池
  样本采集: '准备采集',
  采集样本: '采集账号笔记',
  增量分流: '整理笔记池',
  笔记池: '整理笔记池',
  笔记池同步: '同步笔记池',
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
  模态裁决: '判定内容形态',
  链接解析: '解析链接',
  定向采集: '定向采集',
  // 建档
  '建档·资料': '拉取账号资料',
  '建档·详情升级': '升级笔记详情',
  '建档·数据与轨迹': '统计数据与轨迹',
  '建档·创作画像': '蒸馏创作画像',
  档案信号: '汇总档案信号',
  更新画像: '更新创作画像',
  // 蒸馏
  蒸馏选材: '挑选样本',
  内核蒸馏: '提炼内核',
  认知蒸馏: '提炼内核',
  内容层: '分车道提炼',
  'Skill 生成': '生成方法论',
  博主蒸馏: '提炼方法论',
  停止蒸馏: '已停止',
  任务中断: '已中断',
  // 思考过程(通用:蒸馏/创作)
  思考过程: '思考中',
  自检: '自我检查',
  深度评审: '换视角评审',
  完成: '收尾',
  // 创作
  配图: '生成配图',
  配图方案: '生成配图方案',
  平台合规: '平台合规检查',
  对标对比: '对标对比',
  对标诊断: '对拍差距',
  发布包生成: '起草正文/脚本',
  发布包草稿: '整理成发布包',
  // 早报
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
// 面板头「任务名 · 阶段名」:阶段名和任务名相同时只显示一个,避免「提炼方法论 · 提炼方法论」这类重复。
export const liveHeadline = computed(() => {
  const name = runningTaskName.value
  const stage = liveStage.value
  return stage && stage !== name ? `${name} · ${stage}` : name
})
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

// 对象驱动新架构:社媒两平台合并展示,博主列表跨平台一次拉全(平台=属性/筛选,不再是门)。
const SOCIAL_PLATFORMS: SocialPlatform[] = ['xhs', 'douyin']
async function fetchAllSocialBloggers(): Promise<BloggerProfile[]> {
  const lists = await Promise.all(SOCIAL_PLATFORMS.map((p) => listBloggers(p)))
  return lists.flat()
}

export async function loadAll() {
  const [nextConfig, nextNews, nextArticle, nextBloggers, nextSkills, nextXhsPackages] = await Promise.all([
    getWorkspaceConfig(),
    listNews(),
    getLatestArticle(),
    fetchAllSocialBloggers(),
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

export async function refreshArticle() {
  const nextArticle = await getLatestArticle()
  setArticle(nextArticle)
}

export async function refreshBloggers() {
  bloggers.value = await fetchAllSocialBloggers()
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
  xhsCreationStep.value = Math.max(xhsCreationStep.value, 2)
}

export function goPreviousXhsCreationStep() {
  xhsCreationStep.value = Math.max(1, xhsCreationStep.value - 1)
}

export function goNextXhsCreationStep() {
  if (!canGoNextXhsCreationStep.value) {
    const messages: Record<number, string> = {
      1: '请先选择一个已蒸馏出创作画像的对标博主',
      2: '请先选择一个选题方案',
      3: '请先生成正文或脚本',
      4: '请先完成素材输出'
    }
    showMessage(messages[xhsCreationStep.value] || '当前步骤还没有完成', true)
    return
  }
  xhsCreationStep.value = Math.min(5, xhsCreationStep.value + 1)
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
    selectedPostIds.value = []
    activeNotePostId.value = null
    selectedCollectionRunId.value = null
    selectedBloggerRunId.value = null
    resultCollectionFilterId.value = null
    return
  }
  // 阶段B:博主资产以「笔记池」为中心,一次性拉全量笔记 + 蒸馏记录(不再按采集批次取样本)。
  // 采集批次仍拉取(数据采集页要用),但博主资产页不再展示「采集历史」。
  const [posts, collections, runs, skills] = await Promise.all([
    listBloggerPosts(selectedBloggerId.value),
    listBloggerCollectionRuns(selectedBloggerId.value),
    listBloggerRuns(selectedBloggerId.value),
    listBloggerSkills(currentSocialPlatform.value)
  ])
  bloggerPosts.value = posts
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
}

export function openCreateBloggerModal() {
  editingBloggerId.value = null
  bloggerModalAccountType.value = 'benchmark'
  resetBloggerForm()
  resetBloggerSearch()
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
  // 账号体检只用一个可选自由输入(目标/痛点),没有多选引导。
  return (selfAppraiseForm.intent || '').trim()
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
        industry: appraiseForm.industry || null,
        my_blogger_id: appraiseForm.my_blogger_id || null
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
      xhsCreationStep.value = 3
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
    // 绑定目标「我的账号」(可空);发布后可在发布记录里标记已发布。
    const pack = await saveXhsPublishPackage({ ...currentXhsDraft.value!, my_account_id: xhsPackageForm.my_account_id })
    await refreshXhsPackages(pack.id)
    currentXhsDraft.value = null
    activeXhsTab.value = 'history'
    showMessage('发布包已保存到历史记录')
  })
}

export function handleDiscardXhsDraft() {
  currentXhsDraft.value = null
  xhsCreationStep.value = 3
  showMessage('已放弃本次创作草稿')
}

export async function handleGenerateXhsTopicIdeas() {
  if (!xhsPackageForm.skill_id) {
    showMessage('请先选择一个已蒸馏出创作画像的对标博主', true)
    return
  }
  await runAction('xhs-topic', '正在生成选题方案', async () => {
    const result = await generateXhsTopicIdeas({
      skill_id: xhsPackageForm.skill_id,
      my_blogger_id: xhsPackageForm.my_account_id,
      seed_topic: xhsPackageForm.topic.trim(),
      target_audience: xhsPackageForm.target_audience.trim(),
      content_goal: xhsPackageForm.content_goal.trim(),
      keywords: xhsPackageForm.keywords.trim()
    })
    xhsTopicIdeas.value = result.ideas
    selectedXhsTopicIndex.value = null
    currentXhsDraft.value = null
    xhsCreationStep.value = 2
  })
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
