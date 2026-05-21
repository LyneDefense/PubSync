<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import {
  clearAuthToken,
  fetchNews,
  generateArticle,
  getDashboard,
  getAuthToken,
  getLatestArticle,
  listNews,
  login,
  sendArticleToWechat,
  updateArticle,
  updateNewsSelection
} from './api'
import type { Article, ArticleUpdate, Dashboard, NewsItem } from './api/types'

const statusText: Record<string, string> = {
  draft: '草稿',
  generated: '已生成',
  sent_to_wechat: '已入草稿箱',
  failed: '失败'
}

const dashboard = ref<Dashboard | null>(null)
const news = ref<NewsItem[]>([])
const article = ref<Article | null>(null)
const message = ref('')
const isError = ref(false)
const pendingAction = ref<string | null>(null)
const isAuthenticated = ref(Boolean(getAuthToken()))
const isLoggingIn = ref(false)
const loginMessage = ref('')

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

const apiBaseText = computed(() => `${import.meta.env.BASE_URL}api`)
const hasArticle = computed(() => Boolean(article.value))
const articleStatus = computed(() => {
  const status = dashboard.value?.latest_article?.status
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

function setArticle(nextArticle: Article | null) {
  article.value = nextArticle
  form.title = nextArticle?.title || ''
  form.intro = nextArticle?.intro || ''
  form.cover_image_url = nextArticle?.cover_image_url || ''
  form.content_html = nextArticle?.content_html || ''
}

async function loadAll() {
  const [nextDashboard, nextNews, nextArticle] = await Promise.all([
    getDashboard(),
    listNews(),
    getLatestArticle()
  ])
  dashboard.value = nextDashboard
  news.value = nextNews
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
  dashboard.value = null
  news.value = []
  setArticle(null)
  showMessage('')
}

async function refreshDashboardAndArticle() {
  const [nextDashboard, nextArticle] = await Promise.all([getDashboard(), getLatestArticle()])
  dashboard.value = nextDashboard
  setArticle(nextArticle)
}

async function handleFetchNews() {
  await runAction('fetch', '正在抓取新闻', async () => {
    news.value = await fetchNews()
    await refreshDashboardAndArticle()
  })
}

async function handleGenerateArticle() {
  await runAction('generate', '正在生成文章', async () => {
    setArticle(await generateArticle())
    await refreshDashboardAndArticle()
  })
}

async function handleSendWechat() {
  if (!article.value) {
    return
  }
  await runAction('wechat', '正在发送到公众号草稿箱', async () => {
    setArticle(await sendArticleToWechat(article.value!.id))
    await refreshDashboardAndArticle()
  })
}

async function handleToggleNews(item: NewsItem, selected: boolean) {
  item.selected = selected
  try {
    const updated = await updateNewsSelection(item.id, selected)
    news.value = news.value.map((newsItem) => (newsItem.id === updated.id ? updated : newsItem))
    await refreshDashboardAndArticle()
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
    await refreshDashboardAndArticle()
  })
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(value))
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
      <div>
        <p class="eyebrow">PubSync</p>
        <h1>AI 早报工作台</h1>
      </div>
      <nav aria-label="主导航">
        <a href="#dashboard">总览</a>
        <a href="#news">新闻候选</a>
        <a href="#article">文章草稿</a>
        <a href="#settings">配置</a>
      </nav>
      <button type="button" @click="handleLogout">退出登录</button>
    </aside>

    <main class="workspace">
      <section id="dashboard" class="toolbar">
        <div>
          <p class="eyebrow">今日流程</p>
          <h2>抓取、筛选、生成、入草稿箱</h2>
        </div>
        <div class="actions">
          <button type="button" :disabled="Boolean(pendingAction)" @click="handleFetchNews">
            {{ pendingAction === 'fetch' ? '抓取中' : '重新抓取' }}
          </button>
          <button type="button" :disabled="Boolean(pendingAction)" @click="handleGenerateArticle">
            {{ pendingAction === 'generate' ? '生成中' : '生成文章' }}
          </button>
          <button type="button" class="primary" :disabled="!hasArticle || Boolean(pendingAction)" @click="handleSendWechat">
            {{ pendingAction === 'wechat' ? '发送中' : '发送草稿箱' }}
          </button>
        </div>
      </section>

      <section class="metrics" aria-label="任务状态">
        <article>
          <span>候选新闻</span>
          <strong>{{ dashboard?.news_count ?? '-' }}</strong>
        </article>
        <article>
          <span>已选新闻</span>
          <strong>{{ dashboard?.selected_count ?? '-' }}</strong>
        </article>
        <article>
          <span>定时任务</span>
          <strong>{{ dashboard?.scheduled_publish_time ?? '-' }}</strong>
        </article>
        <article>
          <span>文章状态</span>
          <strong>{{ articleStatus }}</strong>
        </article>
      </section>

      <p class="message" :class="{ error: isError }" role="status">{{ message }}</p>

      <section id="news" class="panel">
        <div class="section-header">
          <div>
            <p class="eyebrow">候选池</p>
            <h2>AI 大事件列表</h2>
          </div>
        </div>
        <div v-if="news.length" class="news-list">
          <article v-for="item in news" :key="item.id" class="news-card">
            <input
              type="checkbox"
              :checked="item.selected"
              :aria-label="`选择 ${item.title}`"
              @change="handleToggleNews(item, ($event.target as HTMLInputElement).checked)"
            />
            <div>
              <h3>{{ item.title }}</h3>
              <div class="meta">{{ item.category }} · {{ item.source }} · {{ formatDate(item.published_at) }}</div>
              <p>{{ item.summary }}</p>
              <a :href="item.url" target="_blank" rel="noreferrer">查看来源</a>
            </div>
            <div class="score">{{ item.importance_score }}</div>
          </article>
        </div>
        <p v-else>还没有候选新闻，点击重新抓取开始。</p>
      </section>

      <section id="article" class="editor-grid">
        <form class="panel" @submit.prevent="handleSaveArticle">
          <div class="section-header">
            <div>
              <p class="eyebrow">编辑</p>
              <h2>公众号文章</h2>
            </div>
            <button type="submit" :disabled="!hasArticle || Boolean(pendingAction)">
              {{ pendingAction === 'save' ? '保存中' : '保存修改' }}
            </button>
          </div>
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
        </form>

        <article class="panel preview-panel">
          <div class="section-header">
            <div>
              <p class="eyebrow">预览</p>
              <h2>图文效果</h2>
            </div>
          </div>
          <img v-if="form.cover_image_url" class="cover" :src="form.cover_image_url" alt="文章封面预览" />
          <h3>{{ form.title || '尚未生成文章' }}</h3>
          <p class="intro-preview">{{ form.intro }}</p>
          <div v-if="form.content_html" class="article-preview" v-html="form.content_html"></div>
          <div v-else class="article-preview">
            <p>生成文章后，这里会显示公众号图文预览。</p>
          </div>
        </article>
      </section>

      <section id="settings" class="panel settings-panel">
        <div class="section-header">
          <div>
            <p class="eyebrow">配置</p>
            <h2>运行设置</h2>
          </div>
        </div>
        <dl>
          <div>
            <dt>API 地址</dt>
            <dd>{{ apiBaseText }}</dd>
          </div>
          <div>
            <dt>新闻来源</dt>
            <dd>RSS/Atom 候选源 + 大模型筛选与改写</dd>
          </div>
          <div>
            <dt>微信接口</dt>
            <dd>真实公众号草稿箱 API，服务器出口 IP 需要加入微信白名单</dd>
          </div>
        </dl>
      </section>
    </main>
  </div>
</template>
