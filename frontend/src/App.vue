<script setup lang="ts">
// App.vue = 应用外壳:登录门、顶栏(平台快速切换 + 用户菜单)、侧栏导航,主区交给 <router-view>。
// 路由是平台/页签的唯一真相;这里把 URL 同步进 store,各业务视图仍按 store 自门控显隐。
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import LoginView from './components/LoginView.vue'
import NavIcon from './components/NavIcon.vue'
import { clearAuthToken, clearTenantId } from './api'
import { DEFAULT_TAB, readLastPlatform } from './router'
import type { PlatformParam } from './router'

// 管理后台是完全独立入口(admin.html,自带登录),不在工作台顶栏放入口,管理员直接访问 /PubSync/admin/。

import {
  activeDouyinTab,
  activeMainTab,
  activeWechatTab,
  activeXhsTab,
  currentSocialTab,
  currentUsername,
  handleGlobalKeydown,
  handleLogin,
  handleLogout,
  isAuthenticated,
  isLoggingIn,
  isSocialPlatform,
  loadAll,
  loadTenantOptions,
  loginMessage,
  progressTimers,
  resumeRunningTaskIfAny,
  showUserMenu,
  toggleUserMenu
} from './composables/useWorkspaceStore'

const route = useRoute()
const router = useRouter()

// URL → store:进入工作台路由时,把 platform/tab 同步到 store(各视图据此显隐)。
watch(
  () => [route.name, route.params.platform, route.params.tab],
  () => {
    if (route.name !== 'workspace') return
    const platform = route.params.platform as string
    const tab = route.params.tab as string | undefined
    if (platform === 'wechat') {
      activeMainTab.value = 'wechat'
      activeWechatTab.value = (tab as typeof activeWechatTab.value) || 'brief'
    } else if (platform === 'douyin') {
      activeMainTab.value = 'douyin'
      activeDouyinTab.value = (tab as typeof activeDouyinTab.value) || 'assets'
    } else if (platform === 'xhs') {
      activeMainTab.value = 'xhs'
      activeXhsTab.value = (tab as typeof activeXhsTab.value) || 'assets'
    }
  },
  { immediate: true }
)

// 登录态变化驱动跳转:登录成功→跳回最近平台/选平台页;退出→回登录页。
watch(isAuthenticated, (authed) => {
  if (authed) {
    if (route.name === 'login' || !route.name) {
      const last = readLastPlatform()
      router.replace(last ? { name: 'workspace', params: { platform: last, tab: DEFAULT_TAB[last] } } : { name: 'select' })
    }
  } else if (route.name !== 'login') {
    router.replace({ name: 'login' })
  }
})

// 顶栏「切换平台」:点按钮弹出弹窗,弹窗里选平台 → 进入该平台默认页签。
const PLATFORM_OPTIONS: Array<{ id: PlatformParam; name: string; desc: string; badge?: string }> = [
  { id: 'xhs', name: '小红书', desc: '对标蒸馏 · 账号诊断 · AI 创作' },
  { id: 'douyin', name: '抖音', desc: '对标蒸馏 · 账号诊断 · AI 创作' },
  { id: 'wechat', name: '公众号', desc: '每日早报(降级)', badge: '降级' }
]
const showPlatformModal = ref(false)
const currentPlatform = computed<PlatformParam | ''>(() =>
  route.name === 'workspace' ? (route.params.platform as PlatformParam) : ''
)
const currentPlatformName = computed(() => PLATFORM_OPTIONS.find((p) => p.id === currentPlatform.value)?.name || '选择平台')

function switchPlatform(platform: PlatformParam) {
  if (route.name === 'workspace' && route.params.platform === platform) return
  router.push({ name: 'workspace', params: { platform, tab: DEFAULT_TAB[platform] } })
}

function choosePlatform(platform: PlatformParam) {
  showPlatformModal.value = false
  switchPlatform(platform)
}

// 侧栏页签点击:在当前平台内切换二级页签(路由驱动 store)。
function goTab(tab: string) {
  const platform = route.params.platform as string
  if (!platform) return
  router.push({ name: 'workspace', params: { platform, tab } })
}

// 应用挂载:注册 Esc 全局快捷键;已登录则先加载工作空间选项再拉取全部数据,失败则退回登录态。
onMounted(() => {
  window.addEventListener('keydown', handleGlobalKeydown)
  if (isAuthenticated.value) {
    loadTenantOptions()
      .then(loadAll)
      .then(() => { resumeRunningTaskIfAny() }) // 刷新后重挂进行中任务(fire-and-forget,不阻塞挂载链)
      .catch((error) => {
        clearAuthToken()
        clearTenantId()
        isAuthenticated.value = false
        loginMessage.value = error instanceof Error ? error.message : '登录已失效，请重新登录'
      })
  }
})

// 应用卸载:移除快捷键监听并清理所有伪进度定时器。
onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
  for (const timer of Object.values(progressTimers)) {
    window.clearInterval(timer)
  }
})
</script>

<template>
  <LoginView v-if="!isAuthenticated" :loading="isLoggingIn" :message="loginMessage" @submit="handleLogin" />

  <!-- 选平台是一个干净的独立页面:不带顶栏/侧栏/用户菜单,只让用户挑一个平台。 -->
  <div v-else-if="route.name === 'select'" class="select-shell">
    <router-view />
  </div>

  <div v-else class="app-shell">
    <header class="topbar">
      <h1 class="topbar-title">多平台内容自动化</h1>
      <div class="topbar-controls">
        <button
          type="button"
          class="platform-switch-btn"
          aria-haspopup="dialog"
          :aria-expanded="showPlatformModal"
          @click="showPlatformModal = true"
        >
          <span class="platform-switch-current">{{ currentPlatformName }}</span>
          <span class="platform-switch-hint">切换平台</span>
        </button>
        <div class="user-menu" @mouseleave="showUserMenu = false">
          <button
            type="button"
            class="user-menu-trigger"
            :aria-expanded="showUserMenu"
            aria-haspopup="menu"
            @click="toggleUserMenu"
          >
            <strong>{{ currentUsername }}</strong>
          </button>
          <div v-if="showUserMenu" class="user-menu-popover" role="menu">
            <button type="button" role="menuitem" @click="handleLogout">退出登录</button>
          </div>
        </div>
      </div>
    </header>

    <div class="app-body">
      <aside v-if="route.name === 'workspace'" class="side-nav" aria-label="功能导航">
        <template v-if="activeMainTab === 'wechat'">
          <p class="side-group">每日早报</p>
          <button type="button" :class="{ active: activeWechatTab === 'brief' }" @click="goTab('brief')"><NavIcon name="sun" />每日早报</button>
          <p class="side-group">博主蒸馏</p>
          <button type="button" :class="{ active: activeWechatTab === 'distill' }" @click="goTab('distill')"><NavIcon name="funnel" />博主蒸馏</button>
          <p class="side-group">AI 创作</p>
          <button type="button" :class="{ active: activeWechatTab === 'ai' }" @click="goTab('ai')"><NavIcon name="sparkles" />AI 创作</button>
          <button type="button" :class="{ active: activeWechatTab === 'records' }" @click="goTab('records')"><NavIcon name="send" />发布草稿</button>
          <hr class="side-sep" />
          <button type="button" :class="{ active: activeWechatTab === 'settings' }" @click="goTab('settings')"><NavIcon name="settings" />设置</button>
        </template>
        <template v-else-if="isSocialPlatform">
          <button type="button" :class="{ active: currentSocialTab === 'overview' }" @click="goTab('overview')"><NavIcon name="list" />概览</button>
          <button type="button" :class="{ active: currentSocialTab === 'my-accounts' }" @click="goTab('my-accounts')"><NavIcon name="user" />我的账号<span class="side-tag">可选</span></button>
          <p class="side-group">对标蒸馏</p>
          <button type="button" :class="{ active: currentSocialTab === 'find' }" @click="goTab('find')"><NavIcon name="search" />找对标博主</button>
          <button type="button" :class="{ active: currentSocialTab === 'assets' }" @click="goTab('assets')"><NavIcon name="folder" />博主资产</button>
          <button type="button" :class="{ active: currentSocialTab === 'collect' }" @click="goTab('collect')"><NavIcon name="download" />数据采集</button>
          <button type="button" :class="{ active: currentSocialTab === 'distill' }" @click="goTab('distill')"><NavIcon name="funnel" />提炼 Skill</button>
          <p class="side-group">AI 创作</p>
          <button type="button" :class="{ active: currentSocialTab === 'packages' }" @click="goTab('packages')"><NavIcon name="sparkles" />对标博主创作</button>
          <button type="button" :class="{ active: currentSocialTab === 'freecreate' }" @click="goTab('freecreate')"><NavIcon name="edit" />自由创作</button>
          <button type="button" :class="{ active: currentSocialTab === 'history' }" @click="goTab('history')"><NavIcon name="send" />发布草稿</button>
          <p class="side-group">评估与提升</p>
          <button type="button" :class="{ active: currentSocialTab === 'audit' }" @click="goTab('audit')"><NavIcon name="target" />对标诊断</button>
          <button type="button" :class="{ active: currentSocialTab === 'self-diagnosis' }" @click="goTab('self-diagnosis')"><NavIcon name="pulse" />诊断我的</button>
          <button type="button" :class="{ active: currentSocialTab === 'effects' }" @click="goTab('effects')"><NavIcon name="chart" />效果看板<span class="side-tag side-tag-new">新</span></button>
          <button type="button" :class="{ active: currentSocialTab === 'skill-optimize' }" @click="goTab('skill-optimize')"><NavIcon name="arrow-up" />Skill 优化<span class="side-tag side-tag-new">新</span></button>
          <hr class="side-sep" />
          <button type="button" :class="{ active: currentSocialTab === 'settings' }" @click="goTab('settings')"><NavIcon name="settings" />设置</button>
        </template>
      </aside>

      <main class="workspace">
        <router-view />
      </main>
    </div>

    <div v-if="showPlatformModal" class="modal-backdrop" role="presentation" @click.self="showPlatformModal = false">
      <div class="modal-panel platform-modal" role="dialog" aria-modal="true" aria-label="切换平台">
        <div class="section-header">
          <div>
            <h2>切换平台</h2>
            <p class="toolbar-subtitle">选择要进入的平台工作台。</p>
          </div>
          <button type="button" class="ghost" @click="showPlatformModal = false">关闭</button>
        </div>
        <div class="platform-modal-list">
          <button
            v-for="option in PLATFORM_OPTIONS"
            :key="option.id"
            type="button"
            class="platform-modal-item"
            :class="{ active: option.id === currentPlatform }"
            :aria-current="option.id === currentPlatform"
            @click="choosePlatform(option.id)"
          >
            <span class="platform-modal-item-main">
              <strong>{{ option.name }}</strong>
              <small>{{ option.desc }}</small>
            </span>
            <span v-if="option.id === currentPlatform" class="platform-modal-current">当前</span>
            <span v-else class="platform-modal-go">进入 →</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
