<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'

import {
  clearAuthToken,
  clearTenantId,
  fetchNews,
  generateArticle,
  getAuthToken,
  getLatestArticle,
  getTenantId,
  getTask,
  getTaskEvents,
  getWorkspaceConfig,
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
  ContentProfile,
  NewsItem,
  OperationTask,
  OperationTaskEvent,
  Tenant,
  WorkspaceConfig
} from './api/types'

type TaskActionName = 'fetch' | 'generate'
type NewsTab = 'international' | 'domestic'
type ArticleTab = 'edit' | 'preview'

const statusText: Record<string, string> = {
  draft: '草稿',
  generated: '已生成',
  sent_to_wechat: '已入草稿箱',
  failed: '失败'
}

const news = ref<NewsItem[]>([])
const article = ref<Article | null>(null)
const tenants = ref<Tenant[]>([])
const profile = ref<ContentProfile | null>(null)
const selectedTenantId = ref(getTenantId())
const message = ref('')
const isError = ref(false)
const pendingAction = ref<string | null>(null)
const taskEvents = ref<OperationTaskEvent[]>([])
const isAuthenticated = ref(Boolean(getAuthToken()))
const isLoggingIn = ref(false)
const loginMessage = ref('')
const activeNewsTab = ref<NewsTab>('international')
const activeArticleTab = ref<ArticleTab>('preview')
const newsPage = ref(1)
const pageSize = 5
const taskProgress = reactive<Record<TaskActionName, number>>({
  fetch: 0,
  generate: 0
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

const profileForm = reactive({
  publication_name: '',
  workspace_title: '',
  title_prefix: '',
  grouping_mode: 'regional' as 'regional' | 'none',
  content_domain: '',
  editor_persona: '',
  audience: '',
  article_style: '',
  international_label: '',
  domestic_label: '',
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
  publish_time_hour: 8,
  publish_time_minute: 0,
  auto_send_wechat_draft: false,
  generate_article_images: true,
  max_article_images: 3,
  min_article_images: 1,
  news_source_urls: '',
  international_news_source_urls: '',
  domestic_news_source_urls: '',
  news_per_source_limit: 8,
  international_news_candidates: 40,
  domestic_news_candidates: 40,
  news_lookback_hours: 72,
  max_news_candidates: 80,
  dedup_lookback_days: 7,
  dedup_direct_similarity: '0.82',
  dedup_review_similarity: '0.42',
  dedup_enable_llm_review: true,
  article_news_limit: 10,
  article_news_lookback_hours: 72,
  article_domestic_min: 1,
  article_domestic_target: 3,
  article_domestic_max: 4,
  article_international_min: 3,
  article_international_target: 6,
  article_international_max: 7
})

const hasArticle = computed(() => Boolean(article.value))
const workspaceTitle = computed(() => profile.value?.workspace_title || 'AI 早报')
const publicationName = computed(() => profile.value?.publication_name || workspaceTitle.value)
const internationalLabel = computed(() => profile.value?.international_label || '国际动态')
const domesticLabel = computed(() => profile.value?.domestic_label || '国内动态')
const usesRegionalGrouping = computed(() => profile.value?.grouping_mode !== 'none')
const domesticNews = computed(() => news.value.filter((item) => item.region === 'domestic'))
const internationalNews = computed(() => news.value.filter((item) => item.region !== 'domestic'))
const activeNews = computed(() => {
  if (!usesRegionalGrouping.value) {
    return news.value
  }
  return activeNewsTab.value === 'domestic' ? domesticNews.value : internationalNews.value
})
const newsTotalPages = computed(() => Math.max(1, Math.ceil(activeNews.value.length / pageSize)))
const pagedNews = computed(() => {
  const start = (newsPage.value - 1) * pageSize
  return activeNews.value.slice(start, start + pageSize)
})
const hasTaskEvents = computed(() => taskEvents.value.length > 0)
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

async function runTaskAction(
  name: TaskActionName,
  label: string,
  startTask: () => Promise<OperationTask>,
  onSuccess: () => Promise<void>,
  timeoutMessage: string
) {
  pendingAction.value = name
  startFakeProgress(name)
  showMessage(label)
  try {
    const task = await startTask()
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
    window.setTimeout(() => resetFakeProgress(name), 300)
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
  const [nextConfig, nextNews, nextArticle] = await Promise.all([getWorkspaceConfig(), listNews(), getLatestArticle()])
  setWorkspaceConfig(nextConfig)
  news.value = nextNews
  newsPage.value = 1
  setArticle(nextArticle)
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
  profileForm.international_label = config.profile.international_label
  profileForm.domestic_label = config.profile.domestic_label
  profileForm.categories_json = config.profile.categories_json
  profileForm.image_style = config.profile.image_style
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
  tenants.value = []
  profile.value = null
  taskEvents.value = []
  setArticle(null)
  showMessage('')
}

async function handleTenantChange() {
  if (!selectedTenantId.value) {
    return
  }
  setTenantId(selectedTenantId.value)
  taskEvents.value = []
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
    const payload = {
      profile: {
        publication_name: profileForm.publication_name,
        workspace_title: profileForm.workspace_title,
        title_prefix: profileForm.title_prefix,
        grouping_mode: profileForm.grouping_mode,
        international_label: profileForm.international_label,
        domestic_label: profileForm.domestic_label
      },
      wechat: {
        app_id: wechatForm.app_id,
        ...(wechatForm.app_secret.trim() ? { app_secret: wechatForm.app_secret.trim() } : {})
      },
      layout: { ...layoutForm },
      publishing: { ...publishingForm }
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

function changeNewsPage(delta: number) {
  newsPage.value = Math.min(newsTotalPages.value, Math.max(1, newsPage.value + delta))
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(value))
}

function regionLabel(region: string) {
  return region === 'domestic' ? '国内' : '国际'
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
        <p class="eyebrow">PubSync</p>
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
    <aside class="sidebar">
      <div class="brand-block">
        <div class="brand-mark" aria-hidden="true">PS</div>
        <div>
          <p class="eyebrow">PubSync</p>
          <h1>{{ workspaceTitle }}</h1>
        </div>
      </div>
      <label class="tenant-switcher">
        工作空间
        <select v-model="selectedTenantId" @change="handleTenantChange">
          <option v-for="tenant in tenants" :key="tenant.id" :value="String(tenant.id)">
            {{ tenant.name }}
          </option>
        </select>
      </label>
      <nav aria-label="主导航">
        <a href="#news">新闻候选</a>
        <a href="#article">文章草稿</a>
        <a href="#config">工作空间配置</a>
      </nav>
      <div class="sidebar-footer">
        <div>
          <span>工作台</span>
          <strong>已登录</strong>
        </div>
        <button type="button" @click="handleLogout">退出</button>
      </div>
    </aside>

    <main class="workspace">
      <section class="toolbar">
        <div>
          <p class="eyebrow">{{ publicationName }}</p>
          <h2>抓取、筛选、生成、入草稿箱</h2>
          <p class="toolbar-subtitle">当前文章状态：{{ articleStateLabel }}</p>
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
      </section>

      <p class="message" :class="{ error: isError }" role="status">{{ message }}</p>

      <section v-if="hasTaskEvents" class="panel task-events" aria-label="任务执行日志">
        <div class="section-header">
          <div>
            <p class="eyebrow">流程日志</p>
            <h2>流程执行进度</h2>
          </div>
        </div>
        <ol>
          <li v-for="event in taskEvents" :key="event.id" :class="`event-${event.status}`">
            <span>{{ event.step_name }}</span>
            <strong>{{ event.message }}</strong>
            <time>{{ formatDate(event.created_at) }}</time>
          </li>
        </ol>
      </section>

      <section id="news" class="panel">
        <div class="section-header">
          <div>
            <p class="eyebrow">候选池</p>
            <h2>{{ workspaceTitle }}候选新闻</h2>
          </div>
          <div v-if="usesRegionalGrouping" class="tabs" role="tablist" aria-label="新闻区域">
            <button
              type="button"
              role="tab"
              :aria-selected="activeNewsTab === 'international'"
              :class="{ active: activeNewsTab === 'international' }"
              @click="setNewsTab('international')"
            >
              {{ internationalLabel }}
              <span>{{ internationalNews.length }}</span>
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeNewsTab === 'domestic'"
              :class="{ active: activeNewsTab === 'domestic' }"
              @click="setNewsTab('domestic')"
            >
              {{ domesticLabel }}
              <span>{{ domesticNews.length }}</span>
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
                <span v-if="usesRegionalGrouping" class="region-pill" :class="{ domestic: item.region === 'domestic' }">
                  {{ regionLabel(item.region) }}
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

      <section id="article" class="panel">
        <div class="section-header">
          <div>
            <p class="eyebrow">文章草稿</p>
            <h2>公众号文章</h2>
          </div>
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

      <section id="config" class="panel">
        <div class="section-header">
          <div>
            <p class="eyebrow">配置中心</p>
            <h2>工作空间配置</h2>
          </div>
        </div>
        <form class="config-form" @submit.prevent="handleSaveConfig">
          <div class="config-subsection">
            <p class="eyebrow">基础信息</p>
            <h3>工作空间与文章标题</h3>
          </div>
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
            <label>
              内容分组
              <select v-model="profileForm.grouping_mode">
                <option value="regional">按国内/国际分组</option>
                <option value="none">不分组</option>
              </select>
            </label>
            <label>
              国际分组名
              <input v-model="profileForm.international_label" type="text" :disabled="profileForm.grouping_mode === 'none'" required />
            </label>
            <label>
              国内分组名
              <input v-model="profileForm.domestic_label" type="text" :disabled="profileForm.grouping_mode === 'none'" required />
            </label>
            <label>
              微信 AppID
              <input v-model="wechatForm.app_id" type="text" autocomplete="off" />
            </label>
          </div>

          <div class="config-subsection">
            <p class="eyebrow">公众号</p>
            <h3>微信草稿箱配置</h3>
          </div>
          <label>
            微信 AppSecret
            <input
              v-model="wechatForm.app_secret"
              type="password"
              autocomplete="new-password"
              :placeholder="wechatForm.app_secret_configured ? '已配置，留空则不修改' : '未配置'"
            />
          </label>
          <div class="config-subsection">
            <p class="eyebrow">自动化</p>
            <h3>定时发布</h3>
          </div>
          <div class="config-grid">
            <label class="toggle-row">
              <input v-model="publishingForm.daily_publish_enabled" type="checkbox" />
              启用每日定时任务
            </label>
            <label class="toggle-row">
              <input v-model="publishingForm.auto_send_wechat_draft" type="checkbox" />
              生成后自动发送草稿箱
            </label>
            <label>
              发布时间：小时
              <input v-model.number="publishingForm.publish_time_hour" type="number" min="0" max="23" />
            </label>
            <label>
              发布时间：分钟
              <input v-model.number="publishingForm.publish_time_minute" type="number" min="0" max="59" />
            </label>
          </div>

          <div class="config-subsection">
            <p class="eyebrow">新闻抓取</p>
            <h3>来源与候选池</h3>
          </div>
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
              国际候选数量
              <input v-model.number="publishingForm.international_news_candidates" type="number" min="0" max="200" />
            </label>
            <label>
              国内候选数量
              <input v-model.number="publishingForm.domestic_news_candidates" type="number" min="0" max="200" />
            </label>
            <label>
              总候选上限
              <input v-model.number="publishingForm.max_news_candidates" type="number" min="1" max="300" />
            </label>
          </div>
          <label>
            通用新闻源
            <textarea v-model="publishingForm.news_source_urls" rows="3"></textarea>
          </label>
          <label>
            国际新闻源
            <textarea v-model="publishingForm.international_news_source_urls" rows="3"></textarea>
          </label>
          <label>
            国内新闻源
            <textarea v-model="publishingForm.domestic_news_source_urls" rows="3"></textarea>
          </label>

          <div class="config-subsection">
            <p class="eyebrow">生成策略</p>
            <h3>文章、图片与去重</h3>
          </div>
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
          <div v-if="usesRegionalGrouping" class="config-grid">
            <label>
              国内最少
              <input v-model.number="publishingForm.article_domestic_min" type="number" min="0" max="50" />
            </label>
            <label>
              国内目标
              <input v-model.number="publishingForm.article_domestic_target" type="number" min="0" max="50" />
            </label>
            <label>
              国内最多
              <input v-model.number="publishingForm.article_domestic_max" type="number" min="0" max="50" />
            </label>
            <label>
              国际最少
              <input v-model.number="publishingForm.article_international_min" type="number" min="0" max="50" />
            </label>
            <label>
              国际目标
              <input v-model.number="publishingForm.article_international_target" type="number" min="0" max="50" />
            </label>
            <label>
              国际最多
              <input v-model.number="publishingForm.article_international_max" type="number" min="0" max="50" />
            </label>
          </div>
          <div class="config-subsection">
            <p class="eyebrow">排版</p>
            <h3>视觉参数与实时预览</h3>
          </div>
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
                <h3 :style="layoutPreviewHeadingStyle">{{ usesRegionalGrouping ? internationalLabel : '精选内容' }}</h3>
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
          <button type="submit" class="primary" :disabled="Boolean(pendingAction)">
            {{ pendingAction === 'config' ? '保存中' : '保存配置' }}
          </button>
        </form>
      </section>
    </main>
  </div>
</template>
