<script setup lang="ts">
// 独立管理后台外壳:自带登录门禁(必须 is_admin),左侧导航 + 右侧面板。
// 与用户端 App 完全分离,但同源复用 api 客户端与 pubsync_token。
import { computed, onMounted, ref } from 'vue'
import LoginView from '../components/LoginView.vue'
import { clearAuthToken, clearTenantId, getAuthToken, getCurrentUser, login } from '../api'
import type { CurrentUser } from '../api/types'
import AccountsPanel from './panels/AccountsPanel.vue'
import ConfigPanel from './panels/ConfigPanel.vue'
import SystemSettingsPanel from './panels/SystemSettingsPanel.vue'
import TaskQueuePanel from './panels/TaskQueuePanel.vue'

type Section = 'accounts' | 'models' | 'collect' | 'tasks' | 'settings'

const NAV: { key: Section; label: string }[] = [
  { key: 'accounts', label: '账号与工作空间' },
  { key: 'models', label: '模型与生成' },
  { key: 'collect', label: '采集 / ASR' },
  { key: 'tasks', label: '任务队列' },
  { key: 'settings', label: '系统设置' }
]

const currentUser = ref<CurrentUser | null>(null)
const section = ref<Section>('accounts')
const loginLoading = ref(false)
const loginMessage = ref('')
const ready = ref(false)

const isAdmin = computed(() => Boolean(currentUser.value?.is_admin))
const userAppUrl = `${import.meta.env.BASE_URL}`

async function refreshUser() {
  try {
    currentUser.value = await getCurrentUser()
  } catch {
    currentUser.value = null
  }
}

onMounted(async () => {
  if (getAuthToken()) await refreshUser()
  ready.value = true
})

async function onLogin(credentials: { username: string; password: string }) {
  loginLoading.value = true
  loginMessage.value = ''
  try {
    await login(credentials.username, credentials.password)
    await refreshUser()
    if (!isAdmin.value) loginMessage.value = '该账号不是管理员，无法进入后台。'
  } catch (e) {
    loginMessage.value = (e as Error).message || '登录失败'
  } finally {
    loginLoading.value = false
  }
}

function logout() {
  clearAuthToken()
  clearTenantId()
  currentUser.value = null
}
</script>

<template>
  <div v-if="!ready" class="admin-loading">加载中…</div>

  <LoginView v-else-if="!currentUser" :loading="loginLoading" :message="loginMessage" @submit="onLogin" />

  <main v-else-if="!isAdmin" class="admin-denied">
    <h1>无权限</h1>
    <p>当前账号 <strong>{{ currentUser.username }}</strong> 不是管理员，无法访问管理后台。</p>
    <div class="admin-denied__actions">
      <a :href="userAppUrl" class="primary-link">返回工作台</a>
      <button type="button" @click="logout">退出登录</button>
    </div>
  </main>

  <div v-else class="admin-shell">
    <aside class="admin-aside">
      <div class="admin-brand">
        <strong>PubSync</strong>
        <span>管理后台</span>
      </div>
      <nav class="admin-nav">
        <button
          v-for="item in NAV"
          :key="item.key"
          type="button"
          :class="{ active: section === item.key }"
          @click="section = item.key"
        >
          {{ item.label }}
        </button>
      </nav>
      <div class="admin-aside__footer">
        <a :href="userAppUrl">← 用户工作台</a>
        <span class="admin-user">{{ currentUser.username }}</span>
        <button type="button" @click="logout">退出</button>
      </div>
    </aside>

    <div class="admin-content">
      <AccountsPanel v-if="section === 'accounts'" />
      <ConfigPanel v-else-if="section === 'models'" title="模型与生成" :group-keys="['model']" />
      <ConfigPanel v-else-if="section === 'collect'" title="采集 / ASR" :group-keys="['tikhub', 'asr']" />
      <TaskQueuePanel v-else-if="section === 'tasks'" />
      <SystemSettingsPanel v-else-if="section === 'settings'" />
    </div>
  </div>
</template>

<style scoped>
.admin-loading,
.admin-denied {
  padding: 48px;
  text-align: center;
}
.admin-denied__actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 16px;
}
.primary-link {
  text-decoration: none;
}
.admin-shell {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  min-height: 100vh;
}
.admin-aside {
  border-right: var(--rule-hair);
  padding: var(--space-md, 16px);
  display: flex;
  flex-direction: column;
  gap: var(--space-md, 16px);
}
.admin-brand {
  display: flex;
  flex-direction: column;
}
.admin-brand span {
  color: var(--color-ink-2, inherit);
  font-size: var(--text-sm);
}
.admin-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.admin-nav button {
  text-align: left;
  padding: 8px 12px;
  border-radius: var(--radius-md, 8px);
  background: transparent;
  border: none;
  cursor: pointer;
}
.admin-nav button.active {
  background: var(--color-surface-2, #f1f5f9);
  font-weight: 600;
}
.admin-aside__footer {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: var(--text-sm);
}
.admin-user {
  color: var(--color-ink-2, inherit);
}
.admin-content {
  padding: var(--space-lg, 24px);
  overflow: auto;
}
@media (max-width: 760px) {
  .admin-shell {
    grid-template-columns: 1fr;
  }
}
</style>
