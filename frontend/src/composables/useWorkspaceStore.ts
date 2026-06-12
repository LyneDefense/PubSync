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
  collectionCostLabel,
  findXhsDraftFromEvents,
  parseEventPayload,
  parseJsonArray,
  parseJsonObject,
  runCostLabel,
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
  confirmBloggerRun,
  createAdminUser,
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
  listAdminUsers,
  listBloggerCollectionPosts,
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
  setTenantId,
  startXhsPublishPackageDraftTask,
  updateArticle,
  updateBlogger,
  updateBloggerFavorite,
  updateNewsSelection,
  updateWorkspaceConfig
} from '../api'
import type {
  AdminUser,
  AdminUserCreate,
  Article,
  ArticleUpdate,
  BloggerCollectionRun,
  BloggerDistillationRun,
  BloggerPost,
  BloggerProfile,
  BloggerSearchResult,
  BloggerSkill,
  ContentGroup,
  ContentProfile,
  CurrentUser,
  NewsItem,
  OperationTask,
  OperationTaskEvent,
  SocialPlatform,
  Tenant,
  WorkspaceConfig,
  XhsPublishContentType,
  XhsPublishPackage,
  XhsPublishPackageDraft,
  XhsTopicIdea
} from '../api/types'


export type TaskActionName = 'fetch' | 'generate' | 'collect' | 'distill' | 'xhs-package'
export type NewsTab = string
export type ArticleTab = 'edit' | 'preview'
export type MainTab = 'wechat' | 'xhs' | 'douyin' | 'admin'
export type WeChatTab = 'brief' | 'ai' | 'drafts' | 'records' | 'settings'
export type XhsTab = 'collect' | 'distill' | 'assets' | 'packages' | 'history' | 'records' | 'settings'
export type DouyinTab = XhsTab
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
export const bloggerSkills = ref<BloggerSkill[]>([])
export const xhsPackages = ref<XhsPublishPackage[]>([])
export const currentXhsDraft = ref<XhsPublishPackageDraft | null>(null)
export const adminUsers = ref<AdminUser[]>([])
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
export const taskEvents = ref<OperationTaskEvent[]>([])
export const taskEventsAction = ref<TaskActionName | null>(null)
export const taskEventsMainTab = ref<MainTab | null>(null)
export const showTaskEventDetails = ref(false)
export const isAuthenticated = ref(Boolean(getAuthToken()))
export const isLoggingIn = ref(false)
export const loginMessage = ref('')
export const activeMainTab = ref<MainTab>('wechat')
export const activeWechatTab = ref<WeChatTab>('brief')
export const activeXhsTab = ref<XhsTab>('collect')
export const activeDouyinTab = ref<DouyinTab>('collect')
export const xhsCollectStep = ref(1)
export const xhsDistillStep = ref(1)
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
  'xhs-package': 0
})
export const progressTimers: Partial<Record<TaskActionName, number>> = {}

export const adminUserForm = reactive<AdminUserCreate>({
  username: '',
  password: '',
  tenant_name: '',
  tenant_slug: '',
  is_admin: false
})

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
  description: ''
})

export const bloggerDistillForm = reactive({
  sample_limit: 50,
  comments_per_post: 20,
  asr_enabled: false
})

export const xhsPackageForm = reactive({
  skill_id: 0,
  content_type: 'text_note' as XhsPublishContentType,
  topic: '',
  target_audience: '',
  content_goal: '知识分享',
  keywords: '',
  image_count_mode: 'auto' as 'auto' | 'manual',
  requested_image_count: 3
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
export const currentSocialTab = computed<XhsTab>(() => (activeMainTab.value === 'douyin' ? activeDouyinTab.value : activeXhsTab.value))
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
export const selectedRunCostLabel = computed(() => {
  const run = selectedBloggerRun.value
  if (!run) {
    return '暂无'
  }
  return `$${run.tikhub_estimated_cost_usd.toFixed(4)}（区间 $${run.tikhub_cost_min_usd.toFixed(4)} - $${run.tikhub_cost_max_usd.toFixed(4)}）`
})
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
export const isTaskRunning = computed(
  () => pendingAction.value === 'fetch' || pendingAction.value === 'generate' || pendingAction.value === 'collect' || pendingAction.value === 'distill'
)
export const isVisibleTaskRunning = computed(
  () => isTaskRunning.value && taskEventsAction.value !== null && taskEventsMainTab.value === activeMainTab.value
)
export const runningTaskName = computed(() => {
  if (pendingAction.value === 'fetch') {
    return '新闻抓取'
  }
  if (pendingAction.value === 'distill') {
    return '博主蒸馏'
  }
  if (pendingAction.value === 'collect') {
    return '样本采集'
  }
  return '文章生成'
})
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

export async function runTaskAction(
  name: TaskActionName,
  label: string,
  startTask: () => Promise<OperationTask>,
  onSuccess: () => Promise<void>,
  timeoutMessage: string
) {
  pendingAction.value = name
  taskEventsAction.value = name
  taskEventsMainTab.value = activeMainTab.value
  showTaskEventDetails.value = false
  startFakeProgress(name)
  showMessage(label)
  try {
    const task = await startTask()
    runningTaskId.value = task.id
    showMessage(task.message)
    taskEvents.value = await getTaskEvents(task.id)

    for (let attempt = 0; attempt < 180; attempt += 1) {
      await wait(5000)
      const [latestTask, latestEvents] = await Promise.all([getTask(task.id), getTaskEvents(task.id)])
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
  } catch (error) {
    stopFakeProgress(name, false)
    showMessage(error instanceof Error ? error.message : '操作失败', true)
  } finally {
    pendingAction.value = null
    runningTaskId.value = null
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
  if (isAdmin.value) {
    adminUsers.value = await listAdminUsers()
  }
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
  adminUsers.value = []
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

export async function refreshSelectedBlogger() {
  if (!selectedBloggerId.value) {
    bloggerPosts.value = []
    bloggerCollectionRuns.value = []
    bloggerRuns.value = []
    selectedCollectionRunId.value = null
    selectedBloggerRunId.value = null
    resultCollectionFilterId.value = null
    return
  }
  const [collections, runs, skills] = await Promise.all([
    listBloggerCollectionRuns(selectedBloggerId.value),
    listBloggerRuns(selectedBloggerId.value),
    listBloggerSkills(currentSocialPlatform.value)
  ])
  bloggerCollectionRuns.value = collections
  bloggerRuns.value = runs
  bloggerSkills.value = skills
  if (selectedCollectionRunId.value && !collections.some((run) => run.id === selectedCollectionRunId.value)) {
    selectedCollectionRunId.value = null
    selectedBloggerRunId.value = null
  }
  if (resultCollectionFilterId.value && !collections.some((run) => run.id === resultCollectionFilterId.value)) {
    resultCollectionFilterId.value = null
  }
  if (selectedCollectionRunId.value) {
    bloggerPosts.value = await listBloggerCollectionPosts(selectedBloggerId.value, selectedCollectionRunId.value)
  } else {
    bloggerPosts.value = []
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
}

export function closeBloggerModal() {
  showBloggerModal.value = false
  editingBloggerId.value = null
  resetBloggerSearch()
  resetBloggerForm()
}

export function openCreateBloggerModal() {
  editingBloggerId.value = null
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
  resetBloggerSearch()
  showBloggerModal.value = true
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
    const blogger = isEditing
      ? await updateBlogger(editingBloggerId.value!, payload)
      : await createBlogger({
          platform: currentSocialPlatform.value,
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

export async function handleCreateAdminUser() {
  await runAction('admin-user', '正在创建账号和工作空间', async () => {
    const user = await createAdminUser({
      username: adminUserForm.username,
      password: adminUserForm.password,
      tenant_name: adminUserForm.tenant_name,
      tenant_slug: adminUserForm.tenant_slug || undefined,
      is_admin: adminUserForm.is_admin
    })
    adminUsers.value = await listAdminUsers()
    tenants.value = await listTenants()
    adminUserForm.username = ''
    adminUserForm.password = ''
    adminUserForm.tenant_name = ''
    adminUserForm.tenant_slug = ''
    adminUserForm.is_admin = false
    showMessage(`账号 ${user.username} 已创建`)
  })
}

export async function handleDistillBlogger() {
  if (!selectedBloggerId.value) {
    showMessage('请先选择博主', true)
    return
  }
  if (!selectedCollectionRunId.value) {
    showMessage('请先选择一个已完成的采集批次', true)
    setCurrentSocialTab('distill')
    xhsDistillStep.value = 2
    return
  }
  await runTaskAction(
    'distill',
    '已提交博主蒸馏任务',
    () =>
      distillBlogger(selectedBloggerId.value!, {
        collection_run_id: selectedCollectionRunId.value!
      }),
    async () => {
      await refreshSelectedBlogger()
      selectLatestRunForCollection(selectedCollectionRunId.value)
      xhsDistillStep.value = 4
    },
    '博主蒸馏仍在后台执行，请稍后刷新页面查看待确认结果'
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
    const pack = await saveXhsPublishPackage(currentXhsDraft.value!)
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
        asr_enabled: bloggerDistillForm.asr_enabled
      }),
    async () => {
      await refreshSelectedBlogger()
      xhsCollectStep.value = 4
    },
    '样本采集仍在后台执行，请稍后刷新页面查看采集批次'
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
  await runTaskAction(
    'generate',
    '已提交后台生成任务',
    generateArticle,
    async () => {
      await refreshArticle()
      activeArticleTab.value = 'preview'
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

export function setCurrentSocialTab(tab: XhsTab) {
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
    resetXhsTopicIdeas()
    await refreshBloggers()
  }
)
