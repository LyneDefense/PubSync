<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'

import {
  cancelTask,
  clearAuthToken,
  clearTenantId,
  collectBlogger,
  createAdminUser,
  createBlogger,
  distillBlogger,
  fetchNews,
  generateArticle,
  generateXhsPublishPackageDraft,
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
  setTenantId,
  updateArticle,
  updateNewsSelection,
  updateWorkspaceConfig
} from './api'
import type {
  AdminUser,
  AdminUserCreate,
  Article,
  ArticleUpdate,
  BloggerCollectionRun,
  BloggerDistillationRun,
  BloggerPost,
  BloggerProfile,
  BloggerSkill,
  ContentGroup,
  ContentProfile,
  CurrentUser,
  NewsItem,
  OperationTask,
  OperationTaskEvent,
  Tenant,
  WorkspaceConfig,
  XhsPublishContentType,
  XhsPublishPackage,
  XhsPublishPackageDraft,
  XhsTopicIdea
} from './api/types'

type TaskActionName = 'fetch' | 'generate' | 'collect' | 'distill'
type NewsTab = string
type ArticleTab = 'edit' | 'preview'
type MainTab = 'wechat' | 'xhs' | 'douyin' | 'admin'
type WeChatTab = 'brief' | 'ai' | 'drafts' | 'records' | 'settings'
type XhsTab = 'ai' | 'packages' | 'history' | 'records' | 'settings'
type DouyinTab = 'ai' | 'packages' | 'records' | 'settings'
type SettingsTab = 'general' | 'wechat' | 'automation' | 'sources' | 'generation' | 'layout'
type XhsWorkflowTab = 'bloggers' | 'collect' | 'distill' | 'assets'
type XhsScriptSegment = {
  start?: string
  end?: string
  scene?: string
  voiceover?: string
  subtitle?: string
}

const statusText: Record<string, string> = {
  draft: '草稿',
  generated: '已生成',
  sent_to_wechat: '已入草稿箱',
  failed: '失败'
}

const news = ref<NewsItem[]>([])
const article = ref<Article | null>(null)
const bloggers = ref<BloggerProfile[]>([])
const bloggerPosts = ref<BloggerPost[]>([])
const bloggerCollectionRuns = ref<BloggerCollectionRun[]>([])
const bloggerRuns = ref<BloggerDistillationRun[]>([])
const bloggerSkills = ref<BloggerSkill[]>([])
const xhsPackages = ref<XhsPublishPackage[]>([])
const currentXhsDraft = ref<XhsPublishPackageDraft | null>(null)
const adminUsers = ref<AdminUser[]>([])
const currentUser = ref<CurrentUser | null>(null)
const selectedBloggerId = ref<number | null>(null)
const selectedCollectionRunId = ref<number | null>(null)
const selectedBloggerRunId = ref<number | null>(null)
const resultCollectionFilterId = ref<number | null>(null)
const selectedXhsPackageId = ref<number | null>(null)
const xhsCreatorBloggerId = ref<number | null>(null)
const xhsCreationStep = ref(1)
const xhsTopicIdeas = ref<XhsTopicIdea[]>([])
const selectedXhsTopicIndex = ref<number | null>(null)
const tenants = ref<Tenant[]>([])
const profile = ref<ContentProfile | null>(null)
const contentGroups = ref<ContentGroup[]>([])
const selectedTenantId = ref(getTenantId())
const message = ref('')
const isError = ref(false)
const pendingAction = ref<string | null>(null)
const runningTaskId = ref<string | null>(null)
const taskEvents = ref<OperationTaskEvent[]>([])
const taskEventsAction = ref<TaskActionName | null>(null)
const showTaskEventDetails = ref(false)
const isAuthenticated = ref(Boolean(getAuthToken()))
const isLoggingIn = ref(false)
const loginMessage = ref('')
const activeMainTab = ref<MainTab>('wechat')
const activeWechatTab = ref<WeChatTab>('brief')
const activeXhsTab = ref<XhsTab>('ai')
const activeDouyinTab = ref<DouyinTab>('ai')
const activeXhsWorkflowTab = ref<XhsWorkflowTab>('bloggers')
const activeNewsTab = ref<NewsTab>('')
const activeArticleTab = ref<ArticleTab>('preview')
const activeSettingsTab = ref<SettingsTab>('general')
const showBloggerModal = ref(false)
const showUserMenu = ref(false)
const previewImage = ref<{ url: string; caption: string } | null>(null)
const newsPage = ref(1)
const pageSize = 5
const taskProgress = reactive<Record<TaskActionName, number>>({
  fetch: 0,
  generate: 0,
  collect: 0,
  distill: 0
})
const progressTimers: Partial<Record<TaskActionName, number>> = {}

const loginForm = reactive({
  username: '',
  password: ''
})

const adminUserForm = reactive<AdminUserCreate>({
  username: '',
  password: '',
  tenant_name: '',
  tenant_slug: '',
  is_admin: false
})

const form = reactive<ArticleUpdate>({
  title: '',
  intro: '',
  cover_image_url: '',
  content_html: ''
})

const bloggerForm = reactive({
  display_name: '',
  homepage_url: '',
  niche: '',
  description: ''
})

const bloggerDistillForm = reactive({
  sample_limit: 50,
  comments_per_post: 20,
  asr_enabled: false
})

const xhsPackageForm = reactive({
  skill_id: 0,
  content_type: 'text_note' as XhsPublishContentType,
  topic: '',
  target_audience: '',
  content_goal: '知识分享',
  keywords: '',
  image_count_mode: 'auto' as 'auto' | 'manual',
  requested_image_count: 3
})

const profileForm = reactive({
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

const wechatForm = reactive({
  app_id: '',
  app_secret: '',
  app_secret_configured: false
})

const layoutForm = reactive({
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

const publishingForm = reactive({
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

const contentGroupForms = ref<ContentGroup[]>([])

const hasArticle = computed(() => Boolean(article.value))
const workspaceTitle = computed(() => profile.value?.workspace_title || 'AI 早报')
const publicationName = computed(() => profile.value?.publication_name || workspaceTitle.value)
const isAdmin = computed(() => Boolean(currentUser.value?.is_admin))
const currentTenantName = computed(() => tenants.value.find((tenant) => String(tenant.id) === selectedTenantId.value)?.name || publicationName.value)
const canSwitchTenant = computed(() => isAdmin.value && tenants.value.length > 1)
const currentUsername = computed(() => currentUser.value?.username || '当前用户')
const activePlatformLabel = computed(() => {
  const labels: Record<MainTab, string> = {
    wechat: '公众号',
    xhs: '小红书',
    douyin: '抖音',
    admin: '后台管理'
  }
  return labels[activeMainTab.value] || '工作台'
})
const usesRegionalGrouping = computed(() => profile.value?.grouping_mode !== 'none')
const enabledContentGroups = computed(() => contentGroups.value.filter((group) => group.enabled))
const hasNewsGroups = computed(() => enabledContentGroups.value.length > 0)
const visibleNewsTabs = computed(() => {
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
const activeNews = computed(() => {
  if (!hasNewsGroups.value || activeNewsTab.value === 'all') {
    return news.value
  }
  return news.value.filter((item) => item.group_key === activeNewsTab.value)
})
const newsTotalPages = computed(() => Math.max(1, Math.ceil(activeNews.value.length / pageSize)))
const pagedNews = computed(() => {
  const start = (newsPage.value - 1) * pageSize
  return activeNews.value.slice(start, start + pageSize)
})
const selectedBlogger = computed(() => bloggers.value.find((item) => item.id === selectedBloggerId.value) || null)
const selectedCollectionRun = computed(() => bloggerCollectionRuns.value.find((run) => run.id === selectedCollectionRunId.value) || null)
const resultCollectionFilter = computed(() => bloggerCollectionRuns.value.find((run) => run.id === resultCollectionFilterId.value) || null)
const selectedBloggerRun = computed(() => bloggerRuns.value.find((run) => run.id === selectedBloggerRunId.value) || null)
const selectedBloggerSkill = computed(() => bloggerSkills.value.find((skill) => skill.run_id === selectedBloggerRunId.value) || null)
const selectedXhsSkill = computed(() => bloggerSkills.value.find((skill) => skill.id === xhsPackageForm.skill_id) || null)
const selectedXhsPackage = computed(() => xhsPackages.value.find((item) => item.id === selectedXhsPackageId.value) || xhsPackages.value[0] || null)
const selectedBloggerRunCount = computed(() => bloggerRuns.value.length)
const visibleBloggerRuns = computed(() =>
  resultCollectionFilterId.value ? bloggerRuns.value.filter((run) => run.collection_run_id === resultCollectionFilterId.value) : bloggerRuns.value
)
const visibleBloggerRunCount = computed(() => visibleBloggerRuns.value.length)
const selectedRunCostLabel = computed(() => {
  const run = selectedBloggerRun.value
  if (!run) {
    return '暂无'
  }
  return `$${run.tikhub_estimated_cost_usd.toFixed(4)}（区间 $${run.tikhub_cost_min_usd.toFixed(4)} - $${run.tikhub_cost_max_usd.toFixed(4)}）`
})
const xhsPackageImageUrls = computed(() => parseJsonArray(selectedXhsPackage.value?.image_urls_json))
const xhsPackageImagePlan = computed(() => parseJsonArray(selectedXhsPackage.value?.image_plan_json))
const xhsPackageHashtags = computed(() => parseJsonArray(selectedXhsPackage.value?.hashtags_json))
const xhsDraftImageUrls = computed(() => parseJsonArray(currentXhsDraft.value?.image_urls_json))
const xhsDraftImagePlan = computed(() => parseJsonArray(currentXhsDraft.value?.image_plan_json))
const xhsDraftHashtags = computed(() => parseJsonArray(currentXhsDraft.value?.hashtags_json))
const xhsDraftScriptSegments = computed(() => {
  const script = parseJsonObject(currentXhsDraft.value?.script_json)
  return Array.isArray(script.segments) ? (script.segments as XhsScriptSegment[]) : []
})
const xhsPackageScriptSegments = computed(() => {
  const script = parseJsonObject(selectedXhsPackage.value?.script_json)
  return Array.isArray(script.segments) ? script.segments : []
})
const activeXhsSkills = computed(() =>
  bloggerSkills.value.filter((skill) => skill.status === 'active').map((skill) => ({
    ...skill,
    bloggerName: bloggers.value.find((blogger) => blogger.id === skill.blogger_id)?.display_name || `博主 #${skill.blogger_id}`
  }))
)
const xhsCreatorSkillOptions = computed(() =>
  activeXhsSkills.value.filter((skill) => !xhsCreatorBloggerId.value || skill.blogger_id === xhsCreatorBloggerId.value)
)
const selectedXhsPackageBloggerName = computed(() => {
  const pack = selectedXhsPackage.value
  if (!pack) {
    return ''
  }
  return bloggers.value.find((blogger) => blogger.id === pack.blogger_id)?.display_name || `博主 #${pack.blogger_id}`
})
const selectedXhsTopicIdea = computed(() =>
  selectedXhsTopicIndex.value === null ? null : xhsTopicIdeas.value[selectedXhsTopicIndex.value] || null
)
const xhsCreationStepTitle = computed(() => {
  const titles: Record<number, string> = {
    1: '选择博主',
    2: '选择 Skill',
    3: '生成/选择选题',
    4: '生成正文/脚本',
    5: '封面、配图、标签',
    6: '确认发布包'
  }
  return titles[xhsCreationStep.value] || 'AI 创作'
})
const canGoNextXhsCreationStep = computed(() => {
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
function runCostLabel(run: BloggerDistillationRun) {
  return `$${run.tikhub_estimated_cost_usd.toFixed(4)}`
}
function collectionCostLabel(run: BloggerCollectionRun) {
  return `$${run.tikhub_estimated_cost_usd.toFixed(4)}`
}
function collectionDistillationCount(collectionRunId: number) {
  return bloggerRuns.value.filter((run) => run.collection_run_id === collectionRunId).length
}
function distillationStatusLabel(status: string) {
  const labels: Record<string, string> = {
    running: '进行中',
    succeeded: '已完成',
    failed: '失败',
    cancelled: '已停止',
    cancel_requested: '停止中'
  }
  return labels[status] || status
}
function bloggerCommentLabel(post: BloggerPost) {
  if (post.comment_count > 0) {
    return `评论 ${post.comment_count}`
  }
  const sampledCount = sampledCommentCount(post)
  return sampledCount > 0 ? `评论未知 / 采样 ${sampledCount}` : '评论未知'
}
function sampledCommentCount(post: BloggerPost) {
  if (typeof post.sampled_comment_count === 'number') {
    return post.sampled_comment_count
  }
  try {
    const comments = JSON.parse(post.comments_json || '[]')
    return Array.isArray(comments) ? comments.length : 0
  } catch {
    return 0
  }
}
const visibleTaskEvents = computed(() => {
  if (!taskEventsAction.value) {
    return []
  }
  return taskActionTab(taskEventsAction.value) === activeMainTab.value ? taskEvents.value : []
})
const latestTaskEvent = computed(() => visibleTaskEvents.value[visibleTaskEvents.value.length - 1] || null)
const isTaskRunning = computed(
  () => pendingAction.value === 'fetch' || pendingAction.value === 'generate' || pendingAction.value === 'collect' || pendingAction.value === 'distill'
)
const isVisibleTaskRunning = computed(
  () => isTaskRunning.value && taskEventsAction.value !== null && taskActionTab(taskEventsAction.value) === activeMainTab.value
)
const runningTaskName = computed(() => {
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
const hasTaskEvents = computed(() => visibleTaskEvents.value.length > 0 || isVisibleTaskRunning.value)
const taskSummaryStep = computed(() => {
  if (latestTaskEvent.value) {
    return latestTaskEvent.value.step_name
  }
  return runningTaskName.value
})
const taskSummaryMessage = computed(() => {
  if (latestTaskEvent.value) {
    return compactTaskMessage(latestTaskEvent.value)
  }
  return '等待任务事件同步'
})
const taskSummaryStatus = computed(() => {
  if (isVisibleTaskRunning.value) {
    return 'running'
  }
  return latestTaskEvent.value?.status || 'running'
})
const taskSummaryPayload = computed(() => (latestTaskEvent.value ? eventPayloadSummary(latestTaskEvent.value) : ''))
const articleStateLabel = computed(() => {
  const status = article.value?.status
  return status ? statusText[status] || status : '未生成'
})
const layoutPreviewStyle = computed(() => ({
  color: layoutForm.text_color === 'inherit' ? '#e7eefc' : layoutForm.text_color,
  fontSize: `${layoutForm.body_font_size}px`,
  lineHeight: layoutForm.line_height
}))
const layoutPreviewHeadingStyle = computed(() => ({
  color: layoutForm.heading_color === 'inherit' ? '#e7eefc' : layoutForm.heading_color,
  fontSize: `${layoutForm.heading_font_size}px`,
  borderBottomColor: layoutForm.accent_color
}))
const layoutPreviewImageStyle = computed(() => ({
  borderRadius: `${layoutForm.image_radius}px`
}))
const layoutPreviewSectionStyle = computed(() => ({
  marginBottom: `${layoutForm.section_spacing}px`
}))

function showMessage(text: string, error = false) {
  message.value = text
  isError.value = error
}

function parseJsonArray(raw?: string | null) {
  if (!raw) {
    return []
  }
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function parseJsonObject(raw?: string | null) {
  if (!raw) {
    return {} as Record<string, unknown>
  }
  try {
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? (parsed as Record<string, unknown>) : {}
  } catch {
    return {}
  }
}

function xhsContentTypeLabel(type: string) {
  const labels: Record<string, string> = {
    text_note: '图文笔记',
    image_note: '图文配图',
    spoken_script: '口播脚本',
    video_script: '视频脚本'
  }
  return labels[type] || type
}

function xhsPackageCopyText(pack: Pick<XhsPublishPackage, 'title' | 'body_text' | 'hashtags_json'> | XhsPublishPackageDraft) {
  const tags = parseJsonArray(pack.hashtags_json)
    .map((tag) => `#${String(tag).replace(/^#/, '')}`)
    .join(' ')
  return [pack.title, pack.body_text, tags].filter(Boolean).join('\n\n')
}

async function copyText(text: string, label: string) {
  try {
    await navigator.clipboard.writeText(text)
    showMessage(`${label}已复制`)
  } catch {
    showMessage('复制失败，请手动选择文本复制', true)
  }
}

function openImagePreview(url: unknown, caption: string) {
  const imageUrl = String(url || '').trim()
  if (!imageUrl) {
    return
  }
  previewImage.value = { url: imageUrl, caption }
}

function closeImagePreview() {
  previewImage.value = null
}

function handleGlobalKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    closeImagePreview()
    showUserMenu.value = false
  }
}

function compactTaskMessage(event: OperationTaskEvent) {
  const payload = parseEventPayload(event)
  const progress = payload?.current && payload?.total ? `${payload.current}/${payload.total}` : ''
  const message = progress ? `${event.message} ${progress}` : event.message
  return message.length > 42 ? `${message.slice(0, 42)}...` : message
}

function parseEventPayload(event: OperationTaskEvent) {
  if (!event.payload_json) {
    return null
  }
  try {
    return JSON.parse(event.payload_json) as Record<string, unknown>
  } catch {
    return null
  }
}

async function runAction(name: string, label: string, action: () => Promise<void>) {
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

function startFakeProgress(name: TaskActionName) {
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

function stopFakeProgress(name: TaskActionName, completed: boolean) {
  window.clearInterval(progressTimers[name])
  progressTimers[name] = undefined
  taskProgress[name] = completed ? 100 : 0
}

function resetFakeProgress(name: TaskActionName) {
  taskProgress[name] = 0
}

function taskButtonStyle(name: TaskActionName) {
  return { '--progress': `${taskProgress[name]}%` }
}

function taskActionTab(name: TaskActionName): MainTab {
  if (name === 'collect' || name === 'distill') {
    return 'xhs'
  }
  return 'wechat'
}

function eventPayloadSummary(event: OperationTaskEvent) {
  const payload = parseEventPayload(event)
  if (!payload) {
    return ''
  }
  const entries = Object.entries(payload)
    .filter(([key]) => !['current', 'total'].includes(key))
    .filter(([, value]) => value !== null && value !== '' && value !== undefined)
    .slice(0, 3)
    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : String(value)}`)
  return entries.join(' · ')
}

async function runTaskAction(
  name: TaskActionName,
  label: string,
  startTask: () => Promise<OperationTask>,
  onSuccess: () => Promise<void>,
  timeoutMessage: string
) {
  pendingAction.value = name
  taskEventsAction.value = name
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

    await onSuccess()
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

async function handleCancelDistillation() {
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

function setArticle(nextArticle: Article | null) {
  article.value = nextArticle
  form.title = nextArticle?.title || ''
  form.intro = nextArticle?.intro || ''
  form.cover_image_url = nextArticle?.cover_image_url || ''
  form.content_html = nextArticle?.content_html || ''
}

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

async function loadAll() {
  const [nextConfig, nextNews, nextArticle, nextBloggers, nextSkills, nextXhsPackages] = await Promise.all([
    getWorkspaceConfig(),
    listNews(),
    getLatestArticle(),
    listBloggers(),
    listBloggerSkills(),
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

function setWorkspaceConfig(config: WorkspaceConfig) {
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

async function loadTenantOptions() {
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

async function handleLogin() {
  isLoggingIn.value = true
  loginMessage.value = ''
  try {
    await login(loginForm.username, loginForm.password)
    isAuthenticated.value = true
    await loadTenantOptions()
    await loadAll()
  } catch (error) {
    loginMessage.value = error instanceof Error ? error.message : '登录失败'
  } finally {
    isLoggingIn.value = false
  }
}

function handleLogout() {
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

function toggleUserMenu() {
  showUserMenu.value = !showUserMenu.value
}

async function handleTenantChange() {
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

async function refreshArticle() {
  const nextArticle = await getLatestArticle()
  setArticle(nextArticle)
}

async function refreshBloggers() {
  bloggers.value = await listBloggers()
  bloggerSkills.value = await listBloggerSkills()
  syncXhsPackageSelection()
  if (selectedBloggerId.value && !bloggers.value.some((item) => item.id === selectedBloggerId.value)) {
    selectedBloggerId.value = null
    selectedCollectionRunId.value = null
    selectedBloggerRunId.value = null
    resultCollectionFilterId.value = null
  }
  await refreshSelectedBlogger()
}

function syncXhsPackageSelection() {
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

function resetXhsTopicIdeas() {
  xhsTopicIdeas.value = []
  selectedXhsTopicIndex.value = null
  currentXhsDraft.value = null
}

function handleXhsCreatorBloggerChange() {
  xhsPackageForm.skill_id = xhsCreatorSkillOptions.value[0]?.id || 0
  resetXhsTopicIdeas()
  xhsCreationStep.value = 1
}

function handleXhsCreatorSkillChange() {
  resetXhsTopicIdeas()
  xhsCreationStep.value = 1
}

function selectXhsTopicIdea(index: number) {
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

function goPreviousXhsCreationStep() {
  xhsCreationStep.value = Math.max(1, xhsCreationStep.value - 1)
}

function goNextXhsCreationStep() {
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

async function refreshSelectedBlogger() {
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
    listBloggerSkills()
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

async function refreshXhsPackages(selectedId?: number) {
  xhsPackages.value = await listXhsPublishPackages()
  selectedXhsPackageId.value = selectedId || xhsPackages.value[0]?.id || null
}

async function handleCreateBlogger() {
  await runAction('blogger', '正在保存博主档案', async () => {
    const blogger = await createBlogger({
      display_name: bloggerForm.display_name,
      homepage_url: bloggerForm.homepage_url,
      niche: bloggerForm.niche,
      description: bloggerForm.description
    })
    selectedBloggerId.value = blogger.id
    selectedBloggerRunId.value = null
    resultCollectionFilterId.value = null
    activeXhsWorkflowTab.value = 'assets'
    bloggerForm.display_name = ''
    bloggerForm.homepage_url = ''
    bloggerForm.niche = ''
    bloggerForm.description = ''
    showBloggerModal.value = false
    await refreshBloggers()
  })
}

async function handleCreateAdminUser() {
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

async function handleDistillBlogger() {
  if (!selectedBloggerId.value) {
    showMessage('请先选择博主', true)
    return
  }
  if (!selectedCollectionRunId.value) {
    showMessage('请先选择一个已完成的采集批次', true)
    activeXhsWorkflowTab.value = 'collect'
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
      showCollectionResults(selectedCollectionRunId.value)
      activeXhsWorkflowTab.value = 'assets'
    },
    '博主蒸馏仍在后台执行，请稍后刷新页面查看报告和 Skill'
  )
}

async function handleCreateXhsPackage() {
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
  await runAction('xhs-package', '正在生成小红书发布包草稿', async () => {
    const draft = await generateXhsPublishPackageDraft({
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
    })
    currentXhsDraft.value = draft
    xhsCreationStep.value = 4
  })
}

async function handleSaveXhsPackage() {
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

function handleDiscardXhsDraft() {
  currentXhsDraft.value = null
  xhsCreationStep.value = 4
  showMessage('已放弃本次创作草稿')
}

async function handleGenerateXhsTopicIdeas() {
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

async function handleCollectBlogger() {
  if (!selectedBloggerId.value) {
    showMessage('请先选择博主', true)
    activeXhsWorkflowTab.value = 'bloggers'
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
      activeXhsWorkflowTab.value = 'collect'
    },
    '样本采集仍在后台执行，请稍后刷新页面查看采集批次'
  )
}

async function selectBlogger(id: number) {
  selectedBloggerId.value = id
  selectedCollectionRunId.value = null
  selectedBloggerRunId.value = null
  resultCollectionFilterId.value = null
  activeXhsWorkflowTab.value = 'collect'
  await refreshSelectedBlogger()
}

async function selectCollectionRun(id: number) {
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

function selectBloggerRun(id: number) {
  selectedBloggerRunId.value = id
}

function selectLatestRunForCollection(collectionRunId = selectedCollectionRunId.value) {
  if (!collectionRunId) {
    selectedBloggerRunId.value = null
    return
  }
  const latestRun = bloggerRuns.value.find((run) => run.collection_run_id === collectionRunId)
  selectedBloggerRunId.value = latestRun?.id || null
}

function showCollectionResults(collectionRunId: number | null) {
  resultCollectionFilterId.value = collectionRunId
  activeXhsWorkflowTab.value = 'assets'
  if (collectionRunId) {
    selectLatestRunForCollection(collectionRunId)
  } else {
    selectedBloggerRunId.value = bloggerRuns.value[0]?.id || null
  }
}

function showAllBloggerRuns() {
  showCollectionResults(null)
}

async function handleFetchNews() {
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

async function handleGenerateArticle() {
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

async function handleSendWechat() {
  if (!article.value) {
    return
  }
  await runAction('wechat', '正在发送到公众号草稿箱', async () => {
    setArticle(await sendArticleToWechat(article.value!.id))
    await refreshArticle()
  })
}

async function handleToggleNews(item: NewsItem, selected: boolean) {
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

async function handleSaveArticle() {
  if (!article.value) {
    return
  }
  await runAction('save', '正在保存文章', async () => {
    setArticle(await updateArticle(article.value!.id, { ...form }))
    await refreshArticle()
  })
}

async function handleSaveConfig() {
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

function setNewsTab(tab: NewsTab) {
  activeNewsTab.value = tab
  newsPage.value = 1
}

function addContentGroup() {
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

function removeContentGroup(index: number) {
  if (contentGroupForms.value.length <= 1) {
    showMessage('至少保留 1 个内容分组', true)
    return
  }
  contentGroupForms.value.splice(index, 1)
}

function changeNewsPage(delta: number) {
  newsPage.value = Math.min(newsTotalPages.value, Math.max(1, newsPage.value + delta))
}

function formatScheduleTime(hour: number, minute: number) {
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
}

function parseScheduleTime(value: string) {
  const [rawHour, rawMinute] = value.split(':')
  const hour = Math.max(0, Math.min(23, Number(rawHour) || 0))
  const minute = Math.max(0, Math.min(59, Number(rawMinute) || 0))
  return { hour, minute }
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(value))
}

function groupLabel(groupKey: string) {
  return contentGroups.value.find((group) => group.group_key === groupKey)?.name || groupKey || '未分组'
}

onMounted(() => {
  window.addEventListener('keydown', handleGlobalKeydown)
  if (isAuthenticated.value) {
    loadTenantOptions()
      .then(loadAll)
      .catch((error) => {
        clearAuthToken()
        clearTenantId()
        isAuthenticated.value = false
        loginMessage.value = error instanceof Error ? error.message : '登录已失效，请重新登录'
      })
  }
})

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

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
  window.clearInterval(progressTimers.fetch)
  window.clearInterval(progressTimers.generate)
})
</script>

<template>
  <main v-if="!isAuthenticated" class="login-shell">
    <form class="login-panel" @submit.prevent="handleLogin">
      <div>
        <p class="brand-context">PubSync</p>
        <h1>登录工作台</h1>
      </div>
      <label>
        用户名
        <input v-model="loginForm.username" type="text" autocomplete="username" required />
      </label>
      <label>
        密码
        <input v-model="loginForm.password" type="password" autocomplete="current-password" required />
      </label>
      <button type="submit" class="primary" :disabled="isLoggingIn">
        {{ isLoggingIn ? '登录中' : '登录' }}
      </button>
      <p v-if="loginMessage" class="message error" role="alert">{{ loginMessage }}</p>
    </form>
  </main>

  <div v-else class="app-shell">
    <header class="topbar">
      <div class="brand-block">
        <div class="brand-mark" aria-hidden="true">PS</div>
        <div>
          <p class="brand-context">PubSync 工作台</p>
          <h1>多平台内容自动化</h1>
          <p class="brand-subtitle">采集、蒸馏、创作与发布管理</p>
        </div>
      </div>
      <div class="topbar-controls">
        <div class="platform-context">
          <span>当前模块</span>
          <strong>{{ activePlatformLabel }}</strong>
        </div>
        <label v-if="canSwitchTenant" class="tenant-switcher">
          工作空间
          <select v-model="selectedTenantId" @change="handleTenantChange">
            <option v-for="tenant in tenants" :key="tenant.id" :value="String(tenant.id)">
              {{ tenant.name }}
            </option>
          </select>
        </label>
        <div v-else class="tenant-badge">
          <span>工作空间</span>
          <strong>{{ currentTenantName }}</strong>
        </div>
        <div class="user-menu" @mouseleave="showUserMenu = false">
          <button
            type="button"
            class="user-menu-trigger"
            :aria-expanded="showUserMenu"
            aria-haspopup="menu"
            @click="toggleUserMenu"
          >
            <span>当前用户</span>
            <strong>{{ currentUsername }}</strong>
          </button>
          <div v-if="showUserMenu" class="user-menu-popover" role="menu">
            <button type="button" role="menuitem" @click="handleLogout">退出登录</button>
          </div>
        </div>
      </div>
    </header>

    <nav class="main-tabs" role="tablist" aria-label="媒体平台">
      <button
        type="button"
        role="tab"
        :aria-selected="activeMainTab === 'wechat'"
        :class="{ active: activeMainTab === 'wechat' }"
        @click="activeMainTab = 'wechat'"
      >
        公众号
      </button>
      <button
        type="button"
        role="tab"
        :aria-selected="activeMainTab === 'xhs'"
        :class="{ active: activeMainTab === 'xhs' }"
        @click="activeMainTab = 'xhs'"
      >
        小红书
      </button>
      <button
        type="button"
        role="tab"
        :aria-selected="activeMainTab === 'douyin'"
        :class="{ active: activeMainTab === 'douyin' }"
        @click="activeMainTab = 'douyin'"
      >
        抖音
      </button>
      <button
        v-if="isAdmin"
        type="button"
        role="tab"
        :aria-selected="activeMainTab === 'admin'"
        :class="{ active: activeMainTab === 'admin' }"
        @click="activeMainTab = 'admin'"
      >
        后台管理
      </button>
    </nav>

    <main class="workspace">
      <p class="message" :class="{ error: isError }" role="status">{{ message }}</p>

      <div v-if="activeMainTab === 'wechat'" class="module-subnav platform-subnav">
        <div class="tabs" role="tablist" aria-label="公众号模块">
          <button type="button" :class="{ active: activeWechatTab === 'brief' }" @click="activeWechatTab = 'brief'">每日早报</button>
          <button type="button" :class="{ active: activeWechatTab === 'ai' }" @click="activeWechatTab = 'ai'">AI 创作</button>
          <button type="button" :class="{ active: activeWechatTab === 'drafts' }" @click="activeWechatTab = 'drafts'">文章草稿</button>
          <button type="button" :class="{ active: activeWechatTab === 'records' }" @click="activeWechatTab = 'records'">发布记录</button>
          <button type="button" :class="{ active: activeWechatTab === 'settings' }" @click="activeWechatTab = 'settings'">设置</button>
        </div>
      </div>

      <div v-if="activeMainTab === 'xhs'" class="module-subnav platform-subnav">
        <div class="tabs" role="tablist" aria-label="小红书模块">
          <button type="button" :class="{ active: activeXhsTab === 'ai' }" @click="activeXhsTab = 'ai'">博主蒸馏</button>
          <button type="button" :class="{ active: activeXhsTab === 'packages' }" @click="activeXhsTab = 'packages'">AI 创作</button>
          <button type="button" :class="{ active: activeXhsTab === 'history' }" @click="activeXhsTab = 'history'">发布包历史</button>
          <button type="button" :class="{ active: activeXhsTab === 'records' }" @click="activeXhsTab = 'records'">发布记录</button>
          <button type="button" :class="{ active: activeXhsTab === 'settings' }" @click="activeXhsTab = 'settings'">设置</button>
        </div>
      </div>

      <div v-if="activeMainTab === 'douyin'" class="module-subnav platform-subnav">
        <div class="tabs" role="tablist" aria-label="抖音模块">
          <button type="button" :class="{ active: activeDouyinTab === 'ai' }" @click="activeDouyinTab = 'ai'">AI 创作</button>
          <button type="button" :class="{ active: activeDouyinTab === 'packages' }" @click="activeDouyinTab = 'packages'">发布包</button>
          <button type="button" :class="{ active: activeDouyinTab === 'records' }" @click="activeDouyinTab = 'records'">发布记录</button>
          <button type="button" :class="{ active: activeDouyinTab === 'settings' }" @click="activeDouyinTab = 'settings'">设置</button>
        </div>
      </div>

      <section v-if="hasTaskEvents" class="panel task-events" aria-label="任务执行日志">
        <div class="section-header">
          <div>
            <h2>流程执行进度</h2>
          </div>
          <button type="button" class="ghost" @click="showTaskEventDetails = !showTaskEventDetails">
            {{ showTaskEventDetails ? '收起详细日志' : `展开详细日志（${visibleTaskEvents.length}）` }}
          </button>
        </div>
        <div class="task-summary" :class="`event-${taskSummaryStatus}`" aria-live="polite">
          <span>{{ taskSummaryStep }}</span>
          <strong>{{ taskSummaryMessage }}</strong>
          <small v-if="taskSummaryPayload">{{ taskSummaryPayload }}</small>
          <time>{{ latestTaskEvent ? formatDate(latestTaskEvent.created_at) : '同步中' }}</time>
          <strong v-if="isVisibleTaskRunning" class="live-tail" aria-label="流程仍在执行">
            <i aria-hidden="true"></i>
            <i aria-hidden="true"></i>
            <i aria-hidden="true"></i>
            <b aria-hidden="true"></b>
          </strong>
        </div>
        <ol v-if="showTaskEventDetails">
          <li v-for="event in visibleTaskEvents" :key="event.id" :class="`event-${event.status}`">
            <span>{{ event.step_name }}</span>
            <strong>{{ compactTaskMessage(event) }}</strong>
            <small v-if="eventPayloadSummary(event)">{{ eventPayloadSummary(event) }}</small>
            <time>{{ formatDate(event.created_at) }}</time>
          </li>
        </ol>
      </section>

      <section v-if="activeMainTab === 'wechat' && activeWechatTab === 'brief'" class="panel">
        <div class="workspace-snapshot scoped-snapshot" aria-label="公众号每日早报摘要">
          <div>
            <span>候选内容</span>
            <strong>{{ news.length }}</strong>
          </div>
          <div>
            <span>当前文章</span>
            <strong>{{ articleStateLabel }}</strong>
          </div>
          <div>
            <span>工作区</span>
            <strong>{{ publicationName }}</strong>
          </div>
        </div>
        <div class="section-header">
          <div>
            <h2>{{ workspaceTitle }}每日早报</h2>
            <p class="toolbar-subtitle">新闻采集、候选筛选和早报生成是独立链路，最终进入公众号文章草稿。</p>
          </div>
          <div class="actions">
            <button
              type="button"
              class="task-button"
              :class="{ running: pendingAction === 'fetch' }"
              :style="taskButtonStyle('fetch')"
              :disabled="Boolean(pendingAction)"
              @click="handleFetchNews"
            >
              <span>{{ pendingAction === 'fetch' ? `抓取中 ${Math.round(taskProgress.fetch)}%` : '重新抓取' }}</span>
            </button>
          </div>
        </div>
        <div class="module-subnav">
          <div class="tabs" role="tablist" aria-label="新闻分组">
            <button
              v-for="tab in visibleNewsTabs"
              :key="tab.group_key"
              type="button"
              role="tab"
              :aria-selected="activeNewsTab === tab.group_key"
              :class="{ active: activeNewsTab === tab.group_key }"
              @click="setNewsTab(tab.group_key)"
            >
              {{ tab.name }}
              <span>{{ tab.count }}</span>
            </button>
          </div>
        </div>
        <div v-if="activeNews.length" class="news-list">
          <article v-for="item in pagedNews" :key="item.id" class="news-card">
            <input
              type="checkbox"
              :checked="item.selected"
              :aria-label="`选择 ${item.title}`"
              @change="handleToggleNews(item, ($event.target as HTMLInputElement).checked)"
            />
            <div>
              <h3>{{ item.title }}</h3>
              <div class="meta">
                <span v-if="hasNewsGroups" class="region-pill">
                  {{ groupLabel(item.group_key) }}
                </span>
                {{ item.category }} · {{ item.source }} · {{ formatDate(item.published_at) }}
              </div>
              <p>{{ item.summary }}</p>
              <a :href="item.url" target="_blank" rel="noreferrer">查看来源</a>
            </div>
            <div class="score">{{ item.importance_score }}</div>
          </article>
          <div class="pagination">
            <button type="button" :disabled="newsPage <= 1" @click="changeNewsPage(-1)">上一页</button>
            <span>第 {{ newsPage }} / {{ newsTotalPages }} 页</span>
            <button type="button" :disabled="newsPage >= newsTotalPages" @click="changeNewsPage(1)">下一页</button>
          </div>
        </div>
        <p v-else class="empty-region">当前分类还没有候选新闻。</p>
      </section>

      <section v-if="activeMainTab === 'wechat' && activeWechatTab === 'ai'" class="panel">
        <div class="section-header">
          <div>
            <h2>公众号 AI 创作</h2>
            <p class="toolbar-subtitle">博主风格创作和自主 AI 创作会生成公众号文章，并复用预览与草稿箱发布能力。</p>
          </div>
        </div>
        <div class="feature-grid">
          <article class="feature-card locked">
            <span>博主风格创作</span>
            <h3>公众号博主蒸馏</h3>
            <p>未来流程：采集公众号文章样本，蒸馏风格资产，再应用风格生成公众号文章。</p>
            <strong>暂未开放</strong>
          </article>
          <article class="feature-card locked">
            <span>自主 AI 创作</span>
            <h3>输入主题生成文章</h3>
            <p>未来流程：输入主题、目标读者和内容目标，由 AI 自主规划并生成公众号文章。</p>
            <strong>暂未开放</strong>
          </article>
        </div>
      </section>

      <section v-if="activeMainTab === 'wechat' && activeWechatTab === 'drafts'" class="panel">
        <div class="section-header">
          <div>
            <h2>公众号文章</h2>
            <p class="toolbar-subtitle">当前文章状态：{{ articleStateLabel }}</p>
          </div>
          <div class="actions">
            <button
              type="button"
              class="task-button"
              :class="{ running: pendingAction === 'generate' }"
              :style="taskButtonStyle('generate')"
              :disabled="Boolean(pendingAction)"
              @click="handleGenerateArticle"
            >
              <span>{{ pendingAction === 'generate' ? `生成中 ${Math.round(taskProgress.generate)}%` : '生成文章' }}</span>
            </button>
            <button type="button" class="primary" :disabled="!hasArticle || Boolean(pendingAction)" @click="handleSendWechat">
              {{ pendingAction === 'wechat' ? '发送中' : '发送草稿箱' }}
            </button>
          </div>
        </div>
        <div class="module-subnav">
          <div class="tabs" role="tablist" aria-label="文章草稿">
            <button
              type="button"
              role="tab"
              :aria-selected="activeArticleTab === 'preview'"
              :class="{ active: activeArticleTab === 'preview' }"
              @click="activeArticleTab = 'preview'"
            >
              预览
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeArticleTab === 'edit'"
              :class="{ active: activeArticleTab === 'edit' }"
              @click="activeArticleTab = 'edit'"
            >
              编辑
            </button>
          </div>
        </div>

        <form v-if="activeArticleTab === 'edit'" class="article-form" @submit.prevent="handleSaveArticle">
          <label>
            标题
            <input v-model="form.title" type="text" :disabled="!hasArticle" />
          </label>
          <label>
            导语
            <textarea v-model="form.intro" rows="4" :disabled="!hasArticle"></textarea>
          </label>
          <label>
            封面图 URL
            <input v-model="form.cover_image_url" type="url" :disabled="!hasArticle" />
          </label>
          <label>
            正文 HTML
            <textarea v-model="form.content_html" rows="16" :disabled="!hasArticle"></textarea>
          </label>
          <button type="submit" :disabled="!hasArticle || Boolean(pendingAction)">
            {{ pendingAction === 'save' ? '保存中' : '保存修改' }}
          </button>
        </form>

        <article v-else class="preview-panel">
          <img v-if="form.cover_image_url" class="cover" :src="form.cover_image_url" alt="文章封面预览" />
          <h3>{{ form.title || '尚未生成文章' }}</h3>
          <p class="intro-preview">{{ form.intro }}</p>
          <div v-if="form.content_html" class="article-preview" v-html="form.content_html"></div>
          <div v-else class="article-preview">
            <p>生成文章后，这里会显示公众号图文预览。</p>
          </div>
        </article>
      </section>

      <section v-if="activeMainTab === 'wechat' && activeWechatTab === 'records'" class="panel">
        <div class="section-header">
          <div>
            <h2>公众号发布记录</h2>
            <p class="toolbar-subtitle">这里会汇总每日早报和 AI 创作文章的草稿箱推送记录。</p>
          </div>
        </div>
        <p class="empty-region">发布记录模块暂未开放。</p>
      </section>

      <section v-if="activeMainTab === 'xhs' && activeXhsTab === 'ai'" class="panel">
        <div class="section-header">
          <div>
            <h2>小红书博主蒸馏</h2>
            <p class="toolbar-subtitle">先维护博主档案，再配置样本采集和风格蒸馏；蒸馏出的 Skill 会进入 AI 创作流程。</p>
          </div>
        </div>

        <div class="xhs-workbench">
          <div class="xhs-flow-map" aria-label="小红书创作流程">
            <button
              type="button"
              :class="{ active: activeXhsWorkflowTab === 'bloggers' }"
              @click="activeXhsWorkflowTab = 'bloggers'"
            >
              <span>01</span>
              <strong>博主档案</strong>
              <small>{{ bloggers.length }} 个博主</small>
            </button>
            <span aria-hidden="true">→</span>
            <button
              type="button"
              :class="{ active: activeXhsWorkflowTab === 'collect' }"
              @click="activeXhsWorkflowTab = 'collect'"
            >
              <span>02</span>
              <strong>样本采集</strong>
              <small>{{ selectedBlogger ? `${bloggerCollectionRuns.length} 个批次` : '笔记与评论数量' }}</small>
            </button>
            <span aria-hidden="true">→</span>
            <button
              type="button"
              :class="{ active: activeXhsWorkflowTab === 'distill' }"
              @click="activeXhsWorkflowTab = 'distill'"
            >
              <span>03</span>
              <strong>风格蒸馏</strong>
              <small>{{ selectedCollectionRun ? `基于批次 #${selectedCollectionRun.id}` : '选择采集批次' }}</small>
            </button>
            <span aria-hidden="true">→</span>
            <button
              type="button"
              :class="{ active: activeXhsWorkflowTab === 'assets' }"
              @click="activeXhsWorkflowTab = 'assets'"
            >
              <span>04</span>
              <strong>结果资产</strong>
              <small>{{ selectedBlogger ? `${selectedBloggerRunCount} 次记录` : '报告与 Skill' }}</small>
            </button>
          </div>

          <div class="xhs-stage">
            <section v-if="activeXhsWorkflowTab === 'bloggers'" class="stage-panel">
              <div class="stage-header">
                <div>
                  <span>博主档案</span>
                  <h3>选择要蒸馏的博主</h3>
                </div>
                <button type="button" class="primary" @click="showBloggerModal = true">创建博主</button>
              </div>
              <div v-if="bloggers.length" class="blogger-list compact">
                <button
                  v-for="blogger in bloggers"
                  :key="blogger.id"
                  type="button"
                  :class="{ active: selectedBloggerId === blogger.id }"
                  @click="selectBlogger(blogger.id)"
                >
                  <strong>{{ blogger.display_name }}</strong>
                  <span>{{ blogger.niche || '未设置领域' }} · 样本 {{ blogger.sample_count }} · {{ blogger.last_distilled_at ? formatDate(blogger.last_distilled_at) : '未蒸馏' }}</span>
                </button>
              </div>
              <p v-else class="empty-region">还没有博主档案。点击“创建博主”添加小红书主页。</p>
            </section>

            <section v-if="activeXhsWorkflowTab === 'collect'" class="stage-panel">
              <div class="stage-header">
                <div>
                  <span>样本采集</span>
                  <h3>配置采集范围</h3>
                </div>
                <button
                  type="button"
                  class="task-button primary"
                  :class="{ running: pendingAction === 'collect' }"
                  :style="taskButtonStyle('collect')"
                  :disabled="!selectedBloggerId || Boolean(pendingAction)"
                  @click="handleCollectBlogger"
                >
                  <span>{{ pendingAction === 'collect' ? `采集中 ${Math.round(taskProgress.collect)}%` : '开始采集' }}</span>
                </button>
              </div>
              <div class="config-grid">
                <label>
                  采样笔记数
                  <input v-model.number="bloggerDistillForm.sample_limit" type="number" min="5" max="200" />
                </label>
                <label>
                  每条评论数
                  <input v-model.number="bloggerDistillForm.comments_per_post" type="number" min="0" max="100" />
                </label>
              </div>
              <label class="asr-callout">
                <input v-model="bloggerDistillForm.asr_enabled" type="checkbox" />
                <span>
                  <strong>启用视频字幕/ASR 分析</strong>
                  <small>采集视频笔记时优先提取字幕；没有字幕时尝试转写音频。这个开关会影响本次采集批次的样本质量。</small>
                </span>
              </label>
              <p class="form-hint">采集会读取公开笔记、互动数据和评论样本。评论数是每条笔记最多采集多少条评论，不代表平台真实评论总数。</p>
              <div v-if="selectedBlogger" class="run-list collection-list" aria-label="采集批次">
                <div class="run-list-header">
                  <strong>采集批次</strong>
                  <span>{{ bloggerCollectionRuns.length }} 次</span>
                </div>
                <button
                  v-for="run in bloggerCollectionRuns"
                  :key="run.id"
                  type="button"
                  :class="{ active: selectedCollectionRunId === run.id }"
                  @click="selectCollectionRun(run.id)"
                >
                  <strong>#{{ run.id }} · {{ formatDate(run.created_at) }}</strong>
                  <span>{{ run.status }} · 样本 {{ run.post_count }} · 蒸馏结果 {{ collectionDistillationCount(run.id) }} · ASR {{ run.asr_enabled ? '开启' : '关闭' }} · {{ collectionCostLabel(run) }}</span>
                </button>
                <p v-if="!bloggerCollectionRuns.length" class="empty-region">这个博主还没有采集批次。</p>
              </div>
              <div v-if="selectedBlogger" class="stage-result-grid">
                <article class="stage-metric">
                  <span>当前博主</span>
                  <strong>{{ selectedBlogger.display_name }}</strong>
                </article>
                <article class="stage-metric">
                  <span>当前批次样本</span>
                  <strong>{{ selectedCollectionRun?.post_count || 0 }}</strong>
                </article>
              </div>
              <article v-if="selectedBlogger && selectedCollectionRun" class="distill-card">
                <div class="inline-card-header">
                  <h3>爆款样本</h3>
                  <button
                    v-if="collectionDistillationCount(selectedCollectionRun.id)"
                    type="button"
                    @click="showCollectionResults(selectedCollectionRun.id)"
                  >
                    查看对应结果
                  </button>
                </div>
                <div v-if="bloggerPosts.length" class="sample-list">
                  <div v-for="post in bloggerPosts.slice(0, 5)" :key="post.id">
                    <strong>{{ post.title }}</strong>
                    <span>
                      {{ post.content_type === 'video' ? '视频' : '图文' }} · 收藏 {{ post.favorite_count }} / 点赞 {{ post.like_count }} / {{ bloggerCommentLabel(post) }}
                      <template v-if="post.content_type === 'video'"> / ASR {{ post.asr_status }}</template>
                    </span>
                  </div>
                </div>
                <p v-else class="empty-region">这个采集批次还没有可展示样本。</p>
              </article>
              <p v-if="selectedBlogger && !selectedCollectionRun" class="empty-region">选择一个采集批次后，这里会显示该批次的爆款样本。</p>
              <p v-if="!selectedBlogger" class="empty-region">请先在“博主档案”里选择一个博主，再查看样本采集结果。</p>
            </section>

            <section v-if="activeXhsWorkflowTab === 'distill'" class="stage-panel">
              <div class="stage-header">
                <div>
                  <span>风格蒸馏</span>
                  <h3>选择采集批次并蒸馏</h3>
                </div>
                <div class="actions">
                  <button
                    type="button"
                    class="task-button primary"
                    :class="{ running: pendingAction === 'distill' }"
                    :style="taskButtonStyle('distill')"
                    :disabled="!selectedBloggerId || !selectedCollectionRunId || Boolean(pendingAction)"
                    @click="handleDistillBlogger"
                  >
                    <span>{{ pendingAction === 'distill' ? `蒸馏中 ${Math.round(taskProgress.distill)}%` : '开始蒸馏' }}</span>
                  </button>
                  <button
                    v-if="pendingAction === 'distill'"
                    type="button"
                    class="ghost danger"
                    :disabled="!runningTaskId"
                    @click="handleCancelDistillation"
                  >
                    停止蒸馏
                  </button>
                </div>
              </div>
              <div v-if="selectedBlogger" class="run-list collection-list" aria-label="可蒸馏采集批次">
                <div class="run-list-header">
                  <strong>选择采集批次</strong>
                  <span>{{ bloggerCollectionRuns.length }} 次</span>
                </div>
                <button
                  v-for="run in bloggerCollectionRuns"
                  :key="run.id"
                  type="button"
                  :disabled="run.status !== 'succeeded'"
                  :class="{ active: selectedCollectionRunId === run.id }"
                  @click="selectCollectionRun(run.id)"
                >
                  <strong>#{{ run.id }} · {{ formatDate(run.created_at) }}</strong>
                  <span>{{ run.status }} · 样本 {{ run.post_count }} · ASR {{ run.asr_enabled ? '开启' : '关闭' }} · 已生成 {{ collectionDistillationCount(run.id) }} 个蒸馏结果</span>
                </button>
                <p v-if="!bloggerCollectionRuns.length" class="empty-region">还没有采集批次，请先完成样本采集。</p>
              </div>
              <p class="form-hint">蒸馏会基于选中的采集批次执行；同一个采集批次可以生成多次不同蒸馏结果。</p>
            </section>

            <section v-if="activeXhsWorkflowTab === 'assets'" class="stage-panel">
              <div class="stage-header">
                <div>
                  <span>结果资产</span>
                  <h3>{{ selectedBlogger ? selectedBlogger.display_name : '蒸馏报告与 Skill' }}</h3>
                </div>
              </div>

              <div v-if="selectedBlogger" class="result-browser">
                <aside class="run-list" aria-label="蒸馏记录">
                  <div class="run-list-header">
                    <strong>{{ resultCollectionFilter ? `采集批次 #${resultCollectionFilter.id} 的蒸馏结果` : '全部蒸馏记录' }}</strong>
                    <span>{{ resultCollectionFilter ? `${visibleBloggerRunCount} / ${selectedBloggerRunCount} 次` : `${selectedBloggerRunCount} 次记录` }}</span>
                  </div>
                  <div v-if="resultCollectionFilter" class="filter-bar">
                    <span>已筛选：批次 #{{ resultCollectionFilter.id }}</span>
                    <button type="button" @click="showAllBloggerRuns">查看全部记录</button>
                  </div>
                  <button
                    v-for="run in visibleBloggerRuns"
                    :key="run.id"
                    type="button"
                    :class="{ active: selectedBloggerRunId === run.id, failed: run.status === 'failed' }"
                    @click="selectBloggerRun(run.id)"
                  >
                    <strong>{{ formatDate(run.created_at) }}</strong>
                    <span>来源批次 #{{ run.collection_run_id || '旧数据' }} · {{ distillationStatusLabel(run.status) }} · 样本 {{ run.sample_count }} · {{ runCostLabel(run) }}</span>
                    <em v-if="run.status === 'failed'" class="run-error">失败原因：{{ run.error_message || '未记录失败原因' }}</em>
                  </button>
                  <p v-if="!visibleBloggerRuns.length && resultCollectionFilter" class="empty-region">这个采集批次还没有蒸馏结果。</p>
                  <p v-else-if="!visibleBloggerRuns.length" class="empty-region">这个博主还没有蒸馏记录。</p>
                </aside>

                <div class="run-detail">
                  <div v-if="selectedBloggerRun" class="workspace-snapshot scoped-snapshot">
                    <div>
                      <span>样本数量</span>
                      <strong>{{ selectedBloggerRun.sample_count }}</strong>
                    </div>
                    <div>
                      <span>TikHub 请求</span>
                      <strong>{{ selectedBloggerRun.tikhub_request_count }}</strong>
                    </div>
                    <div>
                      <span>本次费用</span>
                      <strong>{{ selectedRunCostLabel }}</strong>
                    </div>
                  </div>

                  <div v-if="selectedBloggerRun" class="distill-grid compact-result">
                    <article class="distill-card">
                      <h3>蒸馏报告</h3>
                      <div v-if="selectedBloggerRun.status === 'failed'" class="failure-panel">
                        <strong>蒸馏失败</strong>
                        <p>{{ selectedBloggerRun.error_message || '这次蒸馏没有记录失败原因，请查看任务日志。' }}</p>
                      </div>
                      <div v-else-if="selectedBloggerRun.report_html" class="distill-report" v-html="selectedBloggerRun.report_html"></div>
                      <p v-else class="empty-region">这次蒸馏没有生成报告。</p>
                    </article>

                    <article class="distill-card">
                      <h3>Skill 输出</h3>
                      <textarea
                        v-if="selectedBloggerSkill"
                        :value="selectedBloggerSkill.skill_markdown"
                        readonly
                        rows="18"
                      ></textarea>
                      <p v-else-if="selectedBloggerRun.status === 'failed'" class="empty-region">蒸馏失败后不会生成 Skill。</p>
                      <p v-else class="empty-region">这次蒸馏没有生成 Skill。</p>
                    </article>
                  </div>

                  <p v-if="!selectedBloggerRun" class="empty-region result-placeholder">请选择左侧的一次蒸馏记录查看报告和 Skill。</p>
                </div>
              </div>
              <p v-else class="empty-region">请先在“博主档案”里选择一个博主。</p>
            </section>
          </div>
        </div>

        <div v-if="showBloggerModal" class="modal-backdrop" role="presentation" @click.self="showBloggerModal = false">
          <form class="modal-panel" role="dialog" aria-modal="true" aria-label="创建小红书博主" @submit.prevent="handleCreateBlogger">
            <div class="section-header">
              <div>
                <h2>创建博主</h2>
                <p class="toolbar-subtitle">只保存主页和领域信息；采集数量与 ASR 在后续步骤配置。</p>
              </div>
              <button type="button" class="ghost" @click="showBloggerModal = false">关闭</button>
            </div>
            <label>
              博主名称
              <input v-model="bloggerForm.display_name" type="text" required />
            </label>
            <label>
              小红书主页链接
              <input v-model="bloggerForm.homepage_url" type="url" required placeholder="https://www.xiaohongshu.com/user/profile/..." />
            </label>
            <label>
              领域/赛道
              <input v-model="bloggerForm.niche" type="text" placeholder="宠物、母婴、美妆、AI工具..." />
            </label>
            <label>
              备注
              <textarea v-model="bloggerForm.description" rows="3"></textarea>
            </label>
            <div class="actions">
              <button type="button" @click="showBloggerModal = false">取消</button>
              <button type="submit" class="primary" :disabled="Boolean(pendingAction)">
                {{ pendingAction === 'blogger' ? '保存中' : '保存博主' }}
              </button>
            </div>
          </form>
        </div>
      </section>

      <section v-if="activeMainTab === 'xhs' && activeXhsTab === 'packages'" class="panel">
        <div class="section-header">
          <div>
            <h2>小红书 AI 创作</h2>
            <p class="toolbar-subtitle">按步骤生成一条新内容；历史结果请到“发布包历史”查看。</p>
          </div>
        </div>
        <div class="creator-shell">
          <button
            v-if="xhsCreationStep > 1"
            type="button"
            class="creator-arrow previous"
            aria-label="上一步"
            @click="goPreviousXhsCreationStep"
          >
            ←
          </button>
          <div class="creator-main">
            <div class="creator-step-header">
              <h3>{{ xhsCreationStepTitle }}</h3>
              <span>步骤 {{ xhsCreationStep }} / 6</span>
              <div class="creator-progress" aria-hidden="true">
                <i :style="{ width: `${(xhsCreationStep / 6) * 100}%` }"></i>
              </div>
            </div>

            <section v-if="xhsCreationStep === 1" class="creation-stage-card active">
              <div class="inline-card-header">
                <div>
                  <span>01 选择博主</span>
                  <h3>选择要借鉴风格的博主</h3>
                </div>
                <button type="button" class="primary" @click="showBloggerModal = true">创建博主</button>
              </div>
              <div v-if="bloggers.length" class="blogger-list compact">
                <button
                  v-for="blogger in bloggers"
                  :key="blogger.id"
                  type="button"
                  :class="{ active: xhsCreatorBloggerId === blogger.id }"
                  @click="xhsCreatorBloggerId = blogger.id; handleXhsCreatorBloggerChange()"
                >
                  <strong>{{ blogger.display_name }}</strong>
                  <span>{{ blogger.niche || '未设置领域' }} · 样本 {{ blogger.sample_count }} · {{ blogger.last_distilled_at ? formatDate(blogger.last_distilled_at) : '未蒸馏' }}</span>
                </button>
              </div>
              <p v-else class="empty-region">还没有博主档案。点击“创建博主”添加小红书主页。</p>
            </section>

            <section v-if="xhsCreationStep === 2" class="creation-stage-card active">
              <div class="inline-card-header">
                <div>
                  <span>02 选择 Skill</span>
                  <h3>选择该博主的风格资产</h3>
                </div>
              </div>
              <div v-if="xhsCreatorSkillOptions.length" class="topic-idea-grid">
                <button
                  v-for="skill in xhsCreatorSkillOptions"
                  :key="skill.id"
                  type="button"
                  :class="{ active: xhsPackageForm.skill_id === skill.id }"
                  @click="xhsPackageForm.skill_id = skill.id; handleXhsCreatorSkillChange()"
                >
                  <strong>{{ skill.name }}</strong>
                  <span>{{ skill.description }}</span>
                  <small>{{ formatDate(skill.created_at) }}</small>
                </button>
              </div>
              <p v-else class="empty-region">这个博主还没有可用 Skill。请先到“博主蒸馏”完成一次风格蒸馏。</p>
              <div v-if="selectedXhsSkill" class="skill-mini-card">
                <strong>{{ selectedXhsSkill.name }}</strong>
                <span>{{ selectedXhsSkill.description }}</span>
              </div>
            </section>

            <section v-if="xhsCreationStep === 3" class="creation-stage-card active">
              <div class="inline-card-header">
                <div>
                  <span>03 生成/选择选题</span>
                  <h3>先确定这次要写什么</h3>
                </div>
                <button type="button" class="primary" :disabled="Boolean(pendingAction) || !selectedXhsSkill" @click="handleGenerateXhsTopicIdeas">
                  {{ pendingAction === 'xhs-topic' ? '生成中' : xhsTopicIdeas.length ? '重新生成选题' : '生成选题方案' }}
                </button>
              </div>
              <label>
                种子主题
                <input v-model="xhsPackageForm.topic" type="text" placeholder="可以留空，也可以输入你想写的大方向" />
              </label>
              <div class="config-grid">
                <label>
                  目标人群
                  <input v-model="xhsPackageForm.target_audience" type="text" placeholder="例如：第一次养猫的年轻人" />
                </label>
                <label>
                  内容目的
                  <select v-model="xhsPackageForm.content_goal">
                    <option value="知识分享">知识分享</option>
                    <option value="避坑科普">避坑科普</option>
                    <option value="种草转化">种草转化</option>
                    <option value="观点表达">观点表达</option>
                    <option value="经验复盘">经验复盘</option>
                  </select>
                </label>
              </div>
              <label>
                关键词
                <input v-model="xhsPackageForm.keywords" type="text" placeholder="用逗号分隔，例如：猫粮, 配料表, 蛋白质" />
              </label>
              <div v-if="pendingAction === 'xhs-topic'" class="inline-progress-card" aria-live="polite">
                <div>
                  <strong>正在生成选题</strong>
                  <span>大模型正在结合 Skill、主题和目标人群整理方向。</span>
                </div>
                <i aria-hidden="true"></i>
              </div>
              <div v-if="xhsTopicIdeas.length" class="topic-idea-grid">
                <button
                  v-for="(idea, index) in xhsTopicIdeas"
                  :key="`${idea.title}-${index}`"
                  type="button"
                  :class="{ active: selectedXhsTopicIndex === index }"
                  @click="selectXhsTopicIdea(index)"
                >
                  <strong>{{ idea.title }}</strong>
                  <span>{{ idea.angle }}</span>
                  <small>{{ idea.reason }}</small>
                </button>
              </div>
              <p v-else class="empty-region">生成后，这里会显示多个可选择的选题方案。</p>
            </section>

            <section v-if="xhsCreationStep === 4" class="creation-stage-card active">
              <div class="inline-card-header">
                <div>
                  <span>04 生成正文/脚本</span>
                  <h3>选择内容类型并生成</h3>
                </div>
                <button type="button" class="primary" :disabled="Boolean(pendingAction) || !selectedXhsSkill || !xhsPackageForm.topic.trim()" @click="handleCreateXhsPackage">
                  {{ pendingAction === 'xhs-package' ? '生成中' : currentXhsDraft ? '重新生成' : '开始生成' }}
                </button>
              </div>
              <div v-if="selectedXhsTopicIdea" class="selected-idea-card">
                <span>已选方向</span>
                <strong>{{ selectedXhsTopicIdea.title }}</strong>
                <p>{{ selectedXhsTopicIdea.angle }}</p>
              </div>
              <div class="package-type-grid" role="radiogroup" aria-label="内容类型">
                <label :class="{ active: xhsPackageForm.content_type === 'text_note' }">
                  <input v-model="xhsPackageForm.content_type" type="radio" value="text_note" />
                  <strong>图文笔记</strong>
                  <span>标题、正文、标签、封面文案</span>
                </label>
                <label :class="{ active: xhsPackageForm.content_type === 'image_note' }">
                  <input v-model="xhsPackageForm.content_type" type="radio" value="image_note" />
                  <strong>图文配图</strong>
                  <span>额外规划并生成配图</span>
                </label>
                <label :class="{ active: xhsPackageForm.content_type === 'spoken_script' }">
                  <input v-model="xhsPackageForm.content_type" type="radio" value="spoken_script" />
                  <strong>口播脚本</strong>
                  <span>按时间段输出口播稿</span>
                </label>
                <label :class="{ active: xhsPackageForm.content_type === 'video_script' }">
                  <input v-model="xhsPackageForm.content_type" type="radio" value="video_script" />
                  <strong>视频脚本</strong>
                  <span>分镜、旁白、字幕建议</span>
                </label>
              </div>
              <div v-if="pendingAction === 'xhs-package'" class="inline-progress-card" aria-live="polite">
                <div>
                  <strong>正在生成正文/脚本</strong>
                  <span>会先生成内容结构；如果选择配图，会继续规划并生成图片。</span>
                </div>
                <i aria-hidden="true"></i>
              </div>
              <section v-if="currentXhsDraft" class="package-copy-block">
                <div class="inline-card-header">
                  <h3>{{ currentXhsDraft.title }}</h3>
                  <button type="button" @click="copyText(currentXhsDraft.body_text, '正文')">复制正文</button>
                </div>
                <pre>{{ currentXhsDraft.body_text }}</pre>
              </section>
            </section>

            <section v-if="xhsCreationStep === 5" class="creation-stage-card active">
              <div class="inline-card-header">
                <div>
                  <span>05 封面、配图与标签</span>
                  <h3>检查素材输出</h3>
                </div>
              </div>
              <div v-if="currentXhsDraft" class="asset-output-grid">
                <article>
                  <span>封面文案</span>
                  <strong>{{ currentXhsDraft.cover_text || '暂无' }}</strong>
                </article>
                <article>
                  <span>标签</span>
                  <strong>{{ xhsDraftHashtags.length }} 个</strong>
                </article>
                <article>
                  <span>配图</span>
                  <strong>{{ xhsDraftImageUrls.length || xhsDraftImagePlan.length }} 张</strong>
                </article>
              </div>
              <section v-if="xhsDraftHashtags.length" class="tag-cloud">
                <button v-for="tag in xhsDraftHashtags" :key="String(tag)" type="button" @click="copyText(`#${String(tag).replace(/^#/, '')}`, '标签')">
                  #{{ String(tag).replace(/^#/, '') }}
                </button>
              </section>
              <div v-if="xhsDraftImageUrls.length" class="image-output-grid">
                <figure v-for="(url, index) in xhsDraftImageUrls" :key="url">
                  <button
                    type="button"
                    class="image-preview-trigger"
                    @click="openImagePreview(url, xhsDraftImagePlan[index]?.caption || `配图 ${index + 1}`)"
                  >
                    <img :src="String(url)" alt="小红书发布包配图" />
                  </button>
                  <figcaption>{{ xhsDraftImagePlan[index]?.caption || `配图 ${index + 1}` }}</figcaption>
                </figure>
              </div>
              <p v-if="!currentXhsDraft" class="empty-region">生成内容后，这里会展示封面、标签和配图输出。</p>
            </section>

            <section v-if="xhsCreationStep === 6" class="creation-stage-card active">
              <div class="inline-card-header">
                <div>
                  <span>06 最终发布包</span>
                  <h3>预览并决定是否保存</h3>
                </div>
                <div class="actions compact-actions">
                  <button type="button" :disabled="!currentXhsDraft" @click="currentXhsDraft && copyText(xhsPackageCopyText(currentXhsDraft), '发布文案')">复制发布文案</button>
                  <button type="button" class="primary" :disabled="Boolean(pendingAction) || !currentXhsDraft" @click="handleSaveXhsPackage">
                    {{ pendingAction === 'xhs-package-save' ? '保存中' : '保存发布包' }}
                  </button>
                  <button type="button" :disabled="!currentXhsDraft" @click="handleDiscardXhsDraft">放弃本次创作</button>
                </div>
              </div>
              <div v-if="pendingAction === 'xhs-package-save'" class="inline-progress-card" aria-live="polite">
                <div>
                  <strong>正在保存发布包</strong>
                  <span>保存后会进入发布包历史，方便后续查看和复制。</span>
                </div>
                <i aria-hidden="true"></i>
              </div>
              <p v-if="!currentXhsDraft" class="empty-region">生成内容后，这里会显示本次创作的最终预览。保存后才会进入发布包历史。</p>
              <div v-else class="package-preview draft-preview">
                <div class="package-preview-head">
                  <div>
                    <span>{{ xhsContentTypeLabel(currentXhsDraft.content_type) }}</span>
                    <h3>{{ currentXhsDraft.title }}</h3>
                  </div>
                </div>
                <div class="package-meta-grid">
                  <article>
                    <span>主题</span>
                    <strong>{{ currentXhsDraft.topic }}</strong>
                  </article>
                  <article>
                    <span>封面文案</span>
                    <strong>{{ currentXhsDraft.cover_text || '暂无' }}</strong>
                  </article>
                  <article>
                    <span>标签</span>
                    <strong>{{ xhsDraftHashtags.length }} 个</strong>
                  </article>
                </div>
                <section v-if="xhsDraftHashtags.length" class="tag-cloud">
                  <button v-for="tag in xhsDraftHashtags" :key="String(tag)" type="button" @click="copyText(`#${String(tag).replace(/^#/, '')}`, '标签')">
                    #{{ String(tag).replace(/^#/, '') }}
                  </button>
                </section>
                <section class="package-copy-block">
                  <div class="inline-card-header">
                    <h3>正文预览</h3>
                    <button type="button" @click="copyText(currentXhsDraft.body_text, '正文')">复制正文</button>
                  </div>
                  <pre>{{ currentXhsDraft.body_text }}</pre>
                </section>
                <div v-if="xhsDraftImageUrls.length" class="image-output-grid">
                  <figure v-for="(url, index) in xhsDraftImageUrls" :key="url">
                    <button
                      type="button"
                      class="image-preview-trigger"
                      @click="openImagePreview(url, xhsDraftImagePlan[index]?.caption || `配图 ${index + 1}`)"
                    >
                      <img :src="String(url)" alt="小红书发布包配图" />
                    </button>
                    <figcaption>{{ xhsDraftImagePlan[index]?.caption || `配图 ${index + 1}` }}</figcaption>
                  </figure>
                </div>
                <section v-if="xhsDraftScriptSegments.length" class="script-segments">
                  <div class="inline-card-header">
                    <h3>脚本预览</h3>
                    <button type="button" @click="copyText(JSON.stringify(parseJsonObject(currentXhsDraft.script_json), null, 2), '脚本')">复制脚本</button>
                  </div>
                  <article v-for="(segment, index) in xhsDraftScriptSegments" :key="index">
                    <span>{{ segment.start || `${index * 5}s` }} - {{ segment.end || '' }}</span>
                    <strong>{{ segment.subtitle || segment.scene || '脚本片段' }}</strong>
                    <p>{{ segment.voiceover || segment.scene }}</p>
                  </article>
                </section>
                <p v-if="currentXhsDraft.error_message" class="run-error">{{ currentXhsDraft.error_message }}</p>
              </div>
            </section>
          </div>
          <button
            v-if="xhsCreationStep < 6"
            type="button"
            class="creator-arrow next"
            aria-label="下一步"
            @click="goNextXhsCreationStep"
          >
            →
          </button>
        </div>
      </section>

      <section v-if="activeMainTab === 'xhs' && activeXhsTab === 'history'" class="panel">
        <div class="section-header">
          <div>
            <h2>小红书发布包历史</h2>
            <p class="toolbar-subtitle">这里专门查看、复制和管理历史生成结果，不进入生成流程。</p>
          </div>
        </div>
        <div class="package-browser history-browser">
          <aside class="run-list package-list" aria-label="发布包记录">
            <div class="run-list-header">
              <strong>发布包记录</strong>
              <span>{{ xhsPackages.length }} 条</span>
            </div>
            <button
              v-for="pack in xhsPackages"
              :key="pack.id"
              type="button"
              :class="{ active: selectedXhsPackage?.id === pack.id }"
              @click="selectedXhsPackageId = pack.id"
            >
              <strong>{{ pack.title || pack.topic }}</strong>
              <span>{{ xhsContentTypeLabel(pack.content_type) }} · {{ formatDate(pack.created_at) }}</span>
            </button>
            <p v-if="!xhsPackages.length" class="empty-region">还没有发布包。到“AI 创作”生成后会出现在这里。</p>
          </aside>

          <article v-if="selectedXhsPackage" class="package-preview">
            <div class="inline-card-header">
              <div>
                <span>{{ selectedXhsPackageBloggerName }} · {{ xhsContentTypeLabel(selectedXhsPackage.content_type) }}</span>
                <h3>{{ selectedXhsPackage.title }}</h3>
              </div>
              <button type="button" @click="copyText(xhsPackageCopyText(selectedXhsPackage), '发布文案')">复制发布文案</button>
            </div>
            <div class="workspace-snapshot scoped-snapshot">
              <div>
                <span>主题</span>
                <strong>{{ selectedXhsPackage.topic }}</strong>
              </div>
              <div>
                <span>封面文案</span>
                <strong>{{ selectedXhsPackage.cover_text || '暂无' }}</strong>
              </div>
              <div>
                <span>配图</span>
                <strong>{{ xhsPackageImageUrls.length || xhsPackageImagePlan.length }} 张</strong>
              </div>
            </div>
            <section class="package-copy-block">
              <div class="inline-card-header">
                <h3>正文</h3>
                <button type="button" @click="copyText(selectedXhsPackage.body_text, '正文')">复制正文</button>
              </div>
              <pre>{{ selectedXhsPackage.body_text }}</pre>
            </section>
            <section v-if="xhsPackageHashtags.length" class="tag-cloud">
              <button
                v-for="tag in xhsPackageHashtags"
                :key="String(tag)"
                type="button"
                @click="copyText(`#${String(tag).replace(/^#/, '')}`, '标签')"
              >
                #{{ String(tag).replace(/^#/, '') }}
              </button>
            </section>
            <section v-if="xhsPackageImageUrls.length || xhsPackageImagePlan.length" class="package-images">
              <div class="inline-card-header">
                <h3>配图</h3>
              </div>
              <div class="image-output-grid">
                <figure v-for="(url, index) in xhsPackageImageUrls" :key="url">
                  <button
                    type="button"
                    class="image-preview-trigger"
                    @click="openImagePreview(url, xhsPackageImagePlan[index]?.caption || `配图 ${index + 1}`)"
                  >
                    <img :src="String(url)" alt="小红书发布包配图" />
                  </button>
                  <figcaption>{{ xhsPackageImagePlan[index]?.caption || `配图 ${index + 1}` }}</figcaption>
                </figure>
              </div>
              <div v-if="!xhsPackageImageUrls.length" class="sample-list">
                <div v-for="item in xhsPackageImagePlan" :key="String(item.slot)">
                  <strong>{{ item.caption || `配图 ${item.slot}` }}</strong>
                  <span>{{ item.purpose }}</span>
                </div>
              </div>
              <p v-if="selectedXhsPackage.error_message" class="run-error">{{ selectedXhsPackage.error_message }}</p>
            </section>
            <section v-if="xhsPackageScriptSegments.length" class="script-timeline">
              <div class="inline-card-header">
                <h3>脚本分段</h3>
                <button type="button" @click="copyText(JSON.stringify(parseJsonObject(selectedXhsPackage.script_json), null, 2), '脚本')">复制脚本</button>
              </div>
              <div v-for="(segment, index) in xhsPackageScriptSegments" :key="index">
                <time>{{ segment.start || `${index * 10}s` }} - {{ segment.end || `${(index + 1) * 10}s` }}</time>
                <strong>{{ segment.voiceover || segment.subtitle }}</strong>
                <span>{{ segment.scene }}</span>
              </div>
            </section>
          </article>
          <p v-else class="empty-region result-placeholder">选择一条发布包记录后，这里会展示可复制的内容。</p>
        </div>
      </section>

      <section v-if="activeMainTab === 'xhs' && (activeXhsTab === 'records' || activeXhsTab === 'settings')" class="panel">
        <div class="section-header">
          <div>
            <h2>{{ activeXhsTab === 'records' ? '小红书发布记录' : '小红书设置' }}</h2>
            <p class="toolbar-subtitle">发布记录和平台设置能力后续开放。</p>
          </div>
        </div>
        <p class="empty-region">该模块暂未开放。</p>
      </section>

      <section v-if="activeMainTab === 'douyin'" class="panel">
        <div class="section-header">
          <div>
            <h2>抖音{{ activeDouyinTab === 'ai' ? ' AI 创作' : activeDouyinTab === 'packages' ? '发布包' : activeDouyinTab === 'records' ? '发布记录' : '设置' }}</h2>
            <p class="toolbar-subtitle">抖音会复用“样本采集、风格蒸馏、脚本生成、发布包”的结构，当前先预留入口。</p>
          </div>
        </div>
        <p class="empty-region">该模块暂未开放。</p>
      </section>

      <section v-if="activeMainTab === 'wechat' && activeWechatTab === 'settings'" class="panel">
        <div class="section-header">
          <div>
            <h2>工作空间配置</h2>
          </div>
          <button type="submit" form="workspace-config-form" class="primary" :disabled="Boolean(pendingAction)">
            {{ pendingAction === 'config' ? '保存中' : '保存配置' }}
          </button>
        </div>
        <div class="module-subnav">
          <div class="tabs" role="tablist" aria-label="设置模块">
            <button
              type="button"
              role="tab"
              :aria-selected="activeSettingsTab === 'general'"
              :class="{ active: activeSettingsTab === 'general' }"
              @click="activeSettingsTab = 'general'"
            >
              通用设置
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeSettingsTab === 'wechat'"
              :class="{ active: activeSettingsTab === 'wechat' }"
              @click="activeSettingsTab = 'wechat'"
            >
              公众号设置
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeSettingsTab === 'automation'"
              :class="{ active: activeSettingsTab === 'automation' }"
              @click="activeSettingsTab = 'automation'"
            >
              自动化设置
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeSettingsTab === 'sources'"
              :class="{ active: activeSettingsTab === 'sources' }"
              @click="activeSettingsTab = 'sources'"
            >
              新闻源设置
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeSettingsTab === 'generation'"
              :class="{ active: activeSettingsTab === 'generation' }"
              @click="activeSettingsTab = 'generation'"
            >
              生成策略
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeSettingsTab === 'layout'"
              :class="{ active: activeSettingsTab === 'layout' }"
              @click="activeSettingsTab = 'layout'"
            >
              排版设置
            </button>
          </div>
        </div>

        <form id="workspace-config-form" class="config-form" @submit.prevent="handleSaveConfig">
          <div v-if="activeSettingsTab === 'general'" class="settings-pane">
            <h3>工作空间与文章标题</h3>
            <div class="config-grid">
              <label>
                公众号/栏目名称
                <input v-model="profileForm.publication_name" type="text" required />
              </label>
              <label>
                工作台标题
                <input v-model="profileForm.workspace_title" type="text" required />
              </label>
              <label>
                文章标题前缀
                <input v-model="profileForm.title_prefix" type="text" required />
              </label>
            </div>
            <label>
              内容领域
              <textarea v-model="profileForm.content_domain" rows="3" readonly></textarea>
            </label>
            <label>
              编辑人设
              <textarea v-model="profileForm.editor_persona" rows="3" readonly></textarea>
            </label>
            <label>
              目标读者
              <textarea v-model="profileForm.audience" rows="3" readonly></textarea>
            </label>
            <label>
              文章风格
              <textarea v-model="profileForm.article_style" rows="3" readonly></textarea>
            </label>
            <label>
              图片风格
              <textarea v-model="profileForm.image_style" rows="3" readonly></textarea>
            </label>
            <label>
              分类 JSON
              <textarea v-model="profileForm.categories_json" rows="3" readonly></textarea>
            </label>
          </div>

          <div v-if="activeSettingsTab === 'wechat'" class="settings-pane">
            <h3>微信草稿箱配置</h3>
            <div class="config-grid">
              <label>
                微信 AppID
                <input v-model="wechatForm.app_id" type="text" autocomplete="off" />
              </label>
              <label>
                微信 AppSecret
                <input
                  v-model="wechatForm.app_secret"
                  type="password"
                  autocomplete="new-password"
                  :placeholder="wechatForm.app_secret_configured ? '已配置，留空则不修改' : '未配置'"
                />
              </label>
            </div>
          </div>

          <div v-if="activeSettingsTab === 'automation'" class="settings-pane">
            <h3>定时发布</h3>
            <div class="config-grid">
              <label class="toggle-row">
                <input v-model="publishingForm.daily_publish_enabled" type="checkbox" />
                启用定时任务
              </label>
              <label class="toggle-row">
                <input v-model="publishingForm.auto_send_wechat_draft" type="checkbox" />
                生成后自动发送草稿箱
              </label>
              <label>
                发布周期
                <select v-model="publishingForm.publish_frequency">
                  <option value="daily">每日</option>
                  <option value="weekly">每周</option>
                  <option value="monthly">每月</option>
                </select>
              </label>
              <label v-if="publishingForm.publish_frequency === 'weekly'">
                每周执行日
                <select v-model.number="publishingForm.publish_weekday">
                  <option :value="1">周一</option>
                  <option :value="2">周二</option>
                  <option :value="3">周三</option>
                  <option :value="4">周四</option>
                  <option :value="5">周五</option>
                  <option :value="6">周六</option>
                  <option :value="7">周日</option>
                </select>
              </label>
              <label v-if="publishingForm.publish_frequency === 'monthly'">
                每月执行日
                <input v-model.number="publishingForm.publish_month_day" type="number" min="1" max="31" />
              </label>
              <label>
                时间点
                <input v-model="publishingForm.publish_time_value" type="time" step="60" />
              </label>
            </div>
          </div>

          <div v-if="activeSettingsTab === 'sources'" class="settings-pane">
            <h3>来源与候选池</h3>
            <div class="config-grid">
              <label>
                每个源最多抓取
                <input v-model.number="publishingForm.news_per_source_limit" type="number" min="1" max="50" />
              </label>
              <label>
                新闻回看小时
                <input v-model.number="publishingForm.news_lookback_hours" type="number" min="1" max="168" />
              </label>
              <label>
                总候选上限
                <input v-model.number="publishingForm.max_news_candidates" type="number" min="1" max="300" />
              </label>
            </div>
            <div class="group-editor">
              <article v-for="(group, index) in contentGroupForms" :key="`${group.group_key}-${index}`" class="group-card">
                <div class="group-card-header">
                  <strong>{{ group.name || `内容分组 ${index + 1}` }}</strong>
                  <button type="button" @click="removeContentGroup(index)">移除</button>
                </div>
                <div class="config-grid">
                  <label>
                    分组 Key
                    <input v-model="group.group_key" type="text" required />
                  </label>
                  <label>
                    分组名称
                    <input v-model="group.name" type="text" required />
                  </label>
                  <label>
                    内容形态
                    <select v-model="group.content_mode">
                      <option value="news">新闻资讯</option>
                      <option value="knowledge">知识分享</option>
                      <option value="analysis">行业观察</option>
                    </select>
                  </label>
                  <label>
                    候选数量
                    <input v-model.number="group.candidate_limit" type="number" min="0" max="300" />
                  </label>
                  <label class="toggle-row">
                    <input v-model="group.enabled" type="checkbox" />
                    启用分组
                  </label>
                  <label>
                    文章最少
                    <input v-model.number="group.article_min" type="number" min="0" max="50" />
                  </label>
                  <label>
                    文章目标
                    <input v-model.number="group.article_target" type="number" min="0" max="50" />
                  </label>
                  <label>
                    文章最多
                    <input v-model.number="group.article_max" type="number" min="0" max="50" />
                  </label>
                </div>
                <label>
                  新闻源
                  <textarea
                    v-model="group.source_urls"
                    rows="3"
                    placeholder="格式：名称|RSS地址,名称|RSS地址"
                  ></textarea>
                </label>
              </article>
              <button type="button" class="secondary" @click="addContentGroup">新增内容分组</button>
            </div>
          </div>

          <div v-if="activeSettingsTab === 'generation'" class="settings-pane">
            <h3>文章、图片与去重</h3>
            <div class="config-grid">
              <label class="toggle-row">
                <input v-model="publishingForm.generate_article_images" type="checkbox" />
                生成正文配图
              </label>
              <label class="toggle-row">
                <input v-model="publishingForm.dedup_enable_llm_review" type="checkbox" />
                启用大模型去重复核
              </label>
              <label>
                最少正文图
                <input v-model.number="publishingForm.min_article_images" type="number" min="0" max="10" />
              </label>
              <label>
                最多正文图
                <input v-model.number="publishingForm.max_article_images" type="number" min="0" max="10" />
              </label>
              <label>
                文章新闻数量
                <input v-model.number="publishingForm.article_news_limit" type="number" min="1" max="50" />
              </label>
              <label>
                文章回看小时
                <input v-model.number="publishingForm.article_news_lookback_hours" type="number" min="1" max="168" />
              </label>
              <label>
                去重回看天数
                <input v-model.number="publishingForm.dedup_lookback_days" type="number" min="1" max="30" />
              </label>
              <label>
                直接判重阈值
                <input v-model="publishingForm.dedup_direct_similarity" type="number" min="0" max="1" step="0.01" />
              </label>
              <label>
                大模型复核阈值
                <input v-model="publishingForm.dedup_review_similarity" type="number" min="0" max="1" step="0.01" />
              </label>
            </div>
          </div>

          <div v-if="activeSettingsTab === 'layout'" class="settings-pane">
            <h3>视觉参数与实时预览</h3>
            <div class="layout-editor">
              <div class="layout-controls">
                <div class="config-grid">
                  <label>
                    版式模板
                    <select v-model="layoutForm.template_name">
                      <option value="clean">清爽资讯</option>
                      <option value="warm">温和科普</option>
                      <option value="compact">紧凑早报</option>
                    </select>
                  </label>
                  <label>
                    主色
                    <input v-model="layoutForm.primary_color" type="color" />
                  </label>
                  <label>
                    强调线颜色
                    <input v-model="layoutForm.accent_color" type="color" />
                  </label>
                  <label>
                    正文字号
                    <input v-model.number="layoutForm.body_font_size" type="number" min="12" max="20" />
                  </label>
                  <label>
                    标题字号
                    <input v-model.number="layoutForm.heading_font_size" type="number" min="14" max="26" />
                  </label>
                  <label>
                    行高
                    <input v-model="layoutForm.line_height" type="number" min="1.4" max="2.2" step="0.05" />
                  </label>
                  <label>
                    段落间距
                    <input v-model.number="layoutForm.section_spacing" type="number" min="12" max="48" />
                  </label>
                  <label>
                    图片圆角
                    <input v-model.number="layoutForm.image_radius" type="number" min="0" max="24" />
                  </label>
                </div>
                <label class="toggle-row">
                  <input v-model="layoutForm.show_group_heading" type="checkbox" />
                  显示分组标题
                </label>
                <label class="toggle-row">
                  <input v-model="layoutForm.show_editor_note" type="checkbox" />
                  显示编辑观察
                </label>
                <label class="toggle-row">
                  <input v-model="layoutForm.show_source" type="checkbox" />
                  显示来源
                </label>
              </div>
              <div class="layout-preview" :style="layoutPreviewStyle" aria-label="排版预览">
                <p class="layout-preview-kicker">公众号预览</p>
                <section v-if="layoutForm.show_group_heading" :style="layoutPreviewSectionStyle">
                  <h3 :style="layoutPreviewHeadingStyle">{{ usesRegionalGrouping ? contentGroupForms[0]?.name || '内容分组' : '精选内容' }}</h3>
                </section>
                <section :style="layoutPreviewSectionStyle">
                  <h2 :style="layoutPreviewHeadingStyle">01｜一条适合当前工作空间的内容标题</h2>
                  <p>这里展示正文段落的字号、行高和整体阅读密度。实际生成文章时，后端会用同一套参数渲染公众号 HTML。</p>
                  <div class="layout-preview-image" :style="layoutPreviewImageStyle"></div>
                  <blockquote v-if="layoutForm.show_editor_note" :style="{ borderLeftColor: layoutForm.accent_color }">
                    编辑观察：这里展示强调块的颜色和间距。
                  </blockquote>
                  <p v-if="layoutForm.show_source">
                    来源：<a :style="{ color: layoutForm.primary_color, borderBottomColor: layoutForm.primary_color }">示例来源</a>
                  </p>
                </section>
              </div>
            </div>
          </div>
        </form>
      </section>

      <section v-if="activeMainTab === 'admin' && isAdmin" class="panel">
        <div class="section-header">
          <div>
            <h2>后台管理</h2>
            <p class="toolbar-subtitle">管理员创建账号和工作空间；普通账号登录后只进入自己的工作空间。</p>
          </div>
        </div>
        <div class="distill-grid">
          <form class="distill-card" @submit.prevent="handleCreateAdminUser">
            <h3>创建账号</h3>
            <div class="config-grid">
              <label>
                用户名
                <input v-model="adminUserForm.username" type="text" autocomplete="off" required />
              </label>
              <label>
                初始密码
                <input v-model="adminUserForm.password" type="password" autocomplete="new-password" required />
              </label>
              <label>
                工作空间名称
                <input v-model="adminUserForm.tenant_name" type="text" required />
              </label>
              <label>
                工作空间标识
                <input v-model="adminUserForm.tenant_slug" type="text" placeholder="留空则使用用户名" />
              </label>
            </div>
            <label class="toggle-row">
              <input v-model="adminUserForm.is_admin" type="checkbox" />
              创建为管理员账号
            </label>
            <button type="submit" class="primary" :disabled="Boolean(pendingAction)">
              {{ pendingAction === 'admin-user' ? '创建中' : '创建账号' }}
            </button>
          </form>

          <article class="distill-card">
            <h3>账号列表</h3>
            <div v-if="adminUsers.length" class="admin-user-list">
              <div v-for="user in adminUsers" :key="user.id">
                <strong>{{ user.username }}</strong>
                <span>{{ user.is_admin ? '管理员' : '普通用户' }} · 工作空间 ID {{ user.tenant_id || '未绑定' }} · {{ user.status }}</span>
              </div>
            </div>
            <p v-else class="empty-region">暂无账号。</p>
          </article>
        </div>
      </section>

      <div v-if="previewImage" class="image-preview-backdrop" role="presentation" @click.self="closeImagePreview">
        <figure class="image-preview-panel" role="dialog" aria-modal="true" aria-label="配图预览">
          <button type="button" class="ghost image-preview-close" @click="closeImagePreview">关闭</button>
          <img :src="previewImage.url" alt="小红书发布包配图大图预览" />
          <figcaption>{{ previewImage.caption }}</figcaption>
        </figure>
      </div>
    </main>
  </div>
</template>
