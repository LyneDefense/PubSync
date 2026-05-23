<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'

import {
  clearAuthToken,
  fetchNews,
  generateArticle,
  getAuthToken,
  getLatestArticle,
  getTask,
  getTaskEvents,
  listNews,
  login,
  sendArticleToWechat,
  updateArticle,
  updateNewsSelection
} from './api'
import type { Article, ArticleUpdate, NewsItem, OperationTask, OperationTaskEvent } from './api/types'

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

const hasArticle = computed(() => Boolean(article.value))
const domesticNews = computed(() => news.value.filter((item) => item.region === 'domestic'))
const internationalNews = computed(() => news.value.filter((item) => item.region !== 'domestic'))
const activeNews = computed(() => (activeNewsTab.value === 'domestic' ? domesticNews.value : internationalNews.value))
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
  const [nextNews, nextArticle] = await Promise.all([listNews(), getLatestArticle()])
  news.value = nextNews
  newsPage.value = 1
  setArticle(nextArticle)
}

async function handleLogin() {
  isLoggingIn.value = true
  loginMessage.value = ''
  try {
    await login(loginForm.username, loginForm.password)
    isAuthenticated.value = true
    await loadAll()
  } catch (error) {
    loginMessage.value = error instanceof Error ? error.message : '登录失败'
  } finally {
    isLoggingIn.value = false
  }
}

function handleLogout() {
  clearAuthToken()
  isAuthenticated.value = false
  news.value = []
  taskEvents.value = []
  setArticle(null)
  showMessage('')
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
    loadAll().catch((error) => {
      clearAuthToken()
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
          <h1>AI 早报</h1>
        </div>
      </div>
      <nav aria-label="主导航">
        <a href="#news">新闻候选</a>
        <a href="#article">文章草稿</a>
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
          <p class="eyebrow">今日流程</p>
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
            <h2>AI 大事件列表</h2>
          </div>
          <div class="tabs" role="tablist" aria-label="新闻区域">
            <button
              type="button"
              role="tab"
              :aria-selected="activeNewsTab === 'international'"
              :class="{ active: activeNewsTab === 'international' }"
              @click="setNewsTab('international')"
            >
              国际动态
              <span>{{ internationalNews.length }}</span>
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeNewsTab === 'domestic'"
              :class="{ active: activeNewsTab === 'domestic' }"
              @click="setNewsTab('domestic')"
            >
              国内动态
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
                <span class="region-pill" :class="{ domestic: item.region === 'domestic' }">{{ regionLabel(item.region) }}</span>
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
    </main>
  </div>
</template>
