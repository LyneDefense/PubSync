<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'

import {
  cancelTask,
  clearAuthToken,
  clearTenantId,
  createBlogger,
  distillBlogger,
  fetchNews,
  generateArticle,
  getAuthToken,
  getLatestArticle,
  getTenantId,
  getTask,
  getTaskEvents,
  getWorkspaceConfig,
  listBloggerPosts,
  listBloggerRuns,
  listBloggerSkills,
  listBloggers,
  listTenants,
  listNews,
  login,
  sendArticleToWechat,
  setTenantId,
  updateArticle,
  updateNewsSelection,
  updateWorkspaceConfig
} from './api'
import type {
  Article,
  ArticleUpdate,
  BloggerDistillationRun,
  BloggerPost,
  BloggerProfile,
  BloggerSkill,
  ContentGroup,
  ContentProfile,
  NewsItem,
  OperationTask,
  OperationTaskEvent,
  Tenant,
  WorkspaceConfig
} from './api/types'

type TaskActionName = 'fetch' | 'generate' | 'distill'
type NewsTab = string
type ArticleTab = 'edit' | 'preview'
type MainTab = 'news' | 'article' | 'distill' | 'settings'
type SettingsTab = 'general' | 'wechat' | 'automation' | 'sources' | 'generation' | 'layout'

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
const bloggerRuns = ref<BloggerDistillationRun[]>([])
const bloggerSkills = ref<BloggerSkill[]>([])
const selectedBloggerId = ref<number | null>(null)
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
const activeMainTab = ref<MainTab>('news')
const activeNewsTab = ref<NewsTab>('')
const activeArticleTab = ref<ArticleTab>('preview')
const activeSettingsTab = ref<SettingsTab>('general')
const newsPage = ref(1)
const pageSize = 5
const taskProgress = reactive<Record<TaskActionName, number>>({
  fetch: 0,
  generate: 0,
  distill: 0
})
const progressTimers: Partial<Record<TaskActionName, number>> = {}

const loginForm = reactive({
  username: '',
  password: ''
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
  description: '',
  sample_limit: 50,
  comments_per_post: 20,
  asr_enabled: false
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
const latestBloggerRun = computed(() => bloggerRuns.value[0] || null)
const latestBloggerSkill = computed(
  () =>
    bloggerSkills.value.find((skill) => skill.blogger_id === selectedBloggerId.value && skill.status === 'active') ||
    bloggerSkills.value.find((skill) => skill.blogger_id === selectedBloggerId.value) ||
    null
)
const bloggerCostLabel = computed(() => {
  const run = latestBloggerRun.value
  if (!run) {
    return '暂无'
  }
  return `$${run.tikhub_estimated_cost_usd.toFixed(4)}（区间 $${run.tikhub_cost_min_usd.toFixed(4)} - $${run.tikhub_cost_max_usd.toFixed(4)}）`
})
const visibleTaskEvents = computed(() => {
  if (!taskEventsAction.value) {
    return []
  }
  return taskActionTab(taskEventsAction.value) === activeMainTab.value ? taskEvents.value : []
})
const latestTaskEvent = computed(() => visibleTaskEvents.value[visibleTaskEvents.value.length - 1] || null)
const isTaskRunning = computed(() => pendingAction.value === 'fetch' || pendingAction.value === 'generate' || pendingAction.value === 'distill')
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
    return latestTaskEvent.value.message
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
  if (name === 'fetch') {
    return 'news'
  }
  if (name === 'distill') {
    return 'distill'
  }
  return 'article'
}

function eventPayloadSummary(event: OperationTaskEvent) {
  if (!event.payload_json) {
    return ''
  }
  try {
    const payload = JSON.parse(event.payload_json) as Record<string, unknown>
    const entries = Object.entries(payload)
      .filter(([, value]) => value !== null && value !== '' && value !== undefined)
      .slice(0, 6)
      .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : String(value)}`)
    return entries.join(' · ')
  } catch {
    return event.payload_json
  }
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
  const [nextConfig, nextNews, nextArticle, nextBloggers, nextSkills] = await Promise.all([
    getWorkspaceConfig(),
    listNews(),
    getLatestArticle(),
    listBloggers(),
    listBloggerSkills()
  ])
  setWorkspaceConfig(nextConfig)
  news.value = nextNews
  newsPage.value = 1
  setArticle(nextArticle)
  bloggers.value = nextBloggers
  bloggerSkills.value = nextSkills
  selectedBloggerId.value = nextBloggers[0]?.id || null
  await refreshSelectedBlogger()
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
  const nextTenants = await listTenants()
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
  bloggerRuns.value = []
  bloggerSkills.value = []
  selectedBloggerId.value = null
  tenants.value = []
  profile.value = null
  contentGroups.value = []
  contentGroupForms.value = []
  taskEvents.value = []
  taskEventsAction.value = null
  setArticle(null)
  showMessage('')
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
  if (!selectedBloggerId.value || !bloggers.value.some((item) => item.id === selectedBloggerId.value)) {
    selectedBloggerId.value = bloggers.value[0]?.id || null
  }
  await refreshSelectedBlogger()
}

async function refreshSelectedBlogger() {
  if (!selectedBloggerId.value) {
    bloggerPosts.value = []
    bloggerRuns.value = []
    return
  }
  const [posts, runs, skills] = await Promise.all([
    listBloggerPosts(selectedBloggerId.value),
    listBloggerRuns(selectedBloggerId.value),
    listBloggerSkills()
  ])
  bloggerPosts.value = posts
  bloggerRuns.value = runs
  bloggerSkills.value = skills
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
    bloggerForm.display_name = ''
    bloggerForm.homepage_url = ''
    bloggerForm.niche = ''
    bloggerForm.description = ''
    await refreshBloggers()
  })
}

async function handleDistillBlogger() {
  if (!selectedBloggerId.value) {
    showMessage('请先选择博主', true)
    return
  }
  await runTaskAction(
    'distill',
    '已提交博主蒸馏任务',
    () =>
      distillBlogger(selectedBloggerId.value!, {
        sample_limit: bloggerForm.sample_limit,
        comments_per_post: bloggerForm.comments_per_post,
        asr_enabled: bloggerForm.asr_enabled
      }),
    refreshSelectedBlogger,
    '博主蒸馏仍在后台执行，请稍后刷新页面查看报告和 Skill'
  )
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

onUnmounted(() => {
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
          <p class="brand-context">内容自动化工作台</p>
          <h1>{{ workspaceTitle }}</h1>
        </div>
      </div>
      <div class="topbar-controls">
        <label class="tenant-switcher">
          工作空间
          <select v-model="selectedTenantId" @change="handleTenantChange">
            <option v-for="tenant in tenants" :key="tenant.id" :value="String(tenant.id)">
              {{ tenant.name }}
            </option>
          </select>
        </label>
        <button type="button" @click="handleLogout">退出登录</button>
      </div>
    </header>

    <nav class="main-tabs" role="tablist" aria-label="主模块">
      <button
        type="button"
        role="tab"
        :aria-selected="activeMainTab === 'news'"
        :class="{ active: activeMainTab === 'news' }"
        @click="activeMainTab = 'news'"
      >
        候选新闻
      </button>
      <button
        type="button"
        role="tab"
        :aria-selected="activeMainTab === 'article'"
        :class="{ active: activeMainTab === 'article' }"
        @click="activeMainTab = 'article'"
      >
        文章预览
      </button>
      <button
        type="button"
        role="tab"
        :aria-selected="activeMainTab === 'distill'"
        :class="{ active: activeMainTab === 'distill' }"
        @click="activeMainTab = 'distill'"
      >
        博主蒸馏
      </button>
      <button
        type="button"
        role="tab"
        :aria-selected="activeMainTab === 'settings'"
        :class="{ active: activeMainTab === 'settings' }"
        @click="activeMainTab = 'settings'"
      >
        设置
      </button>
    </nav>

    <main class="workspace">
      <p class="message" :class="{ error: isError }" role="status">{{ message }}</p>

      <div class="workspace-snapshot" aria-label="工作台摘要">
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
            <strong>{{ event.message }}</strong>
            <small v-if="eventPayloadSummary(event)">{{ eventPayloadSummary(event) }}</small>
            <time>{{ formatDate(event.created_at) }}</time>
          </li>
        </ol>
      </section>

      <section v-if="activeMainTab === 'news'" class="panel">
        <div class="section-header">
          <div>
            <h2>{{ workspaceTitle }}候选新闻</h2>
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

      <section v-if="activeMainTab === 'article'" class="panel">
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

      <section v-if="activeMainTab === 'distill'" class="panel">
        <div class="section-header">
          <div>
            <h2>小红书博主蒸馏</h2>
            <p class="toolbar-subtitle">通过 TikHub 采集图文笔记和 Top20 评论，生成报告与创作 Skill。</p>
          </div>
          <div class="actions">
            <button
              type="button"
              class="task-button"
              :class="{ running: pendingAction === 'distill' }"
              :style="taskButtonStyle('distill')"
              :disabled="!selectedBloggerId || Boolean(pendingAction)"
              @click="handleDistillBlogger"
            >
              <span>{{ pendingAction === 'distill' ? `蒸馏中 ${Math.round(taskProgress.distill)}%` : '采集并蒸馏' }}</span>
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

        <div class="distill-grid">
          <form class="distill-card" @submit.prevent="handleCreateBlogger">
            <h3>新增博主</h3>
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
            <div class="config-grid">
              <label>
                采样笔记数
                <input v-model.number="bloggerForm.sample_limit" type="number" min="5" max="200" />
              </label>
              <label>
                每条评论数
                <input v-model.number="bloggerForm.comments_per_post" type="number" min="0" max="100" />
              </label>
            </div>
            <label class="checkbox-line">
              <input v-model="bloggerForm.asr_enabled" type="checkbox" />
              <span>开启视频 ASR 转写</span>
            </label>
            <p class="form-hint">开启后，视频笔记会尝试走腾讯云长音频识别；失败时自动降级为标题、描述、评论和互动数据分析。</p>
            <button type="submit" class="primary" :disabled="Boolean(pendingAction)">
              {{ pendingAction === 'blogger' ? '保存中' : '保存博主' }}
            </button>
          </form>

          <div class="distill-card">
            <h3>博主列表</h3>
            <div v-if="bloggers.length" class="blogger-list">
              <button
                v-for="blogger in bloggers"
                :key="blogger.id"
                type="button"
                :class="{ active: selectedBloggerId === blogger.id }"
                @click="selectedBloggerId = blogger.id; refreshSelectedBlogger()"
              >
                <strong>{{ blogger.display_name }}</strong>
                <span>{{ blogger.niche || '未设置领域' }} · 样本 {{ blogger.sample_count }}</span>
              </button>
            </div>
            <p v-else class="empty-region">还没有博主档案。</p>
          </div>
        </div>

        <div v-if="selectedBlogger" class="distill-result">
          <div class="workspace-snapshot">
            <div>
              <span>当前博主</span>
              <strong>{{ selectedBlogger.display_name }}</strong>
            </div>
            <div>
              <span>TikHub 请求</span>
              <strong>{{ latestBloggerRun?.tikhub_request_count || 0 }}</strong>
            </div>
            <div>
              <span>本次费用</span>
              <strong>{{ bloggerCostLabel }}</strong>
            </div>
          </div>

          <div class="distill-grid">
            <article class="distill-card">
              <h3>爆款样本</h3>
              <div v-if="bloggerPosts.length" class="sample-list">
                <div v-for="post in bloggerPosts.slice(0, 5)" :key="post.id">
                  <strong>{{ post.title }}</strong>
                  <span>
                    {{ post.content_type === 'video' ? '视频' : '图文' }} · 收藏 {{ post.favorite_count }} / 点赞 {{ post.like_count }} / 评论 {{ post.comment_count }}
                    <template v-if="post.content_type === 'video'"> / ASR {{ post.asr_status }}</template>
                  </span>
                </div>
              </div>
              <p v-else class="empty-region">完成蒸馏后会显示样本。</p>
            </article>

            <article class="distill-card">
              <h3>蒸馏报告</h3>
              <div v-if="latestBloggerRun?.report_html" class="distill-report" v-html="latestBloggerRun.report_html"></div>
              <p v-else class="empty-region">完成蒸馏后会显示报告。</p>
            </article>
          </div>

          <article class="distill-card">
            <h3>Skill 输出</h3>
            <textarea
              v-if="latestBloggerSkill"
              :value="latestBloggerSkill.skill_markdown"
              readonly
              rows="18"
            ></textarea>
            <p v-else class="empty-region">完成蒸馏后会生成 SKILL.md。</p>
          </article>
        </div>
      </section>

      <section v-if="activeMainTab === 'settings'" class="panel">
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
    </main>
  </div>
</template>
