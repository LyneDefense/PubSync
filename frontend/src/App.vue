<script setup lang="ts">
// App.vue = 应用外壳:登录门、顶栏(品牌 + 平台切换 + 搜索 + 用户菜单)、分组卡片侧栏,主区交给 <router-view>。
// 路由是平台/页签的唯一真相;这里把 URL 同步进 store。侧栏数据驱动(NAV 结构),激活态沿用 activeSocialTab/activeWechatTab。
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
  currentTenantName,
  currentUsername,
  handleGlobalKeydown,
  handleLogin,
  handleLogout,
  isAuthenticated,
  isLoggingIn,
  loadAll,
  loadTenantOptions,
  loginMessage,
  progressTimers,
  resumeRunningTaskIfAny,
  showMessage,
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
      activeDouyinTab.value = (tab as typeof activeDouyinTab.value) || 'dossier'
    } else if (platform === 'xhs') {
      activeMainTab.value = 'xhs'
      activeXhsTab.value = (tab as typeof activeXhsTab.value) || 'dossier'
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

// 顶栏「切换平台」:点品牌旁的 pill 弹出弹窗,选平台 → 进入该平台默认页签。
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

// 平台图标方块(品牌色,非主色):小红书红 / 抖音黑 / 公众号绿。
const PLATFORM_MARK: Record<string, { ch: string; bg: string }> = {
  xhs: { ch: '书', bg: '#ff2e4d' },
  douyin: { ch: '抖', bg: '#161b19' },
  wechat: { ch: '微', bg: '#07c160' }
}
const platformMark = computed(() => PLATFORM_MARK[currentPlatform.value] || { ch: '·', bg: 'var(--color-accent)' })

function switchPlatform(platform: PlatformParam) {
  if (route.name === 'workspace' && route.params.platform === platform) return
  router.push({ name: 'workspace', params: { platform, tab: DEFAULT_TAB[platform] } })
}
function choosePlatform(platform: PlatformParam) {
  showPlatformModal.value = false
  switchPlatform(platform)
}

// ── 侧栏导航:数据驱动(顶部平铺项 + 三张阶段卡 + 底部设置)。顺序与 SocialTab 一致 ──
type NavItem = { tab: string; label: string; icon: string; badge?: string }
type NavGroup = { title: string; icon: string; items: NavItem[] }
type NavConfig = { top: NavItem[]; groups: NavGroup[]; bottom: NavItem[] }

const SOCIAL_NAV: NavConfig = {
  top: [
    { tab: 'overview', label: '概览', icon: 'list' },
    { tab: 'my-accounts', label: '我的账号', icon: 'user' }
  ],
  groups: [
    {
      title: '对标蒸馏',
      icon: 'funnel',
      items: [
        { tab: 'find', label: '查找博主', icon: 'search' },
        { tab: 'dossier', label: '博主档案', icon: 'user', badge: '新' },
        { tab: 'analysis', label: '对标分析', icon: 'target' },
        { tab: 'collect', label: '数据采集', icon: 'download' },
        { tab: 'distill', label: '提炼 Skill', icon: 'funnel' }
      ]
    },
    {
      title: 'AI 创作',
      icon: 'sparkles',
      items: [
        { tab: 'packages', label: '对标博主创作', icon: 'sparkles' },
        { tab: 'freecreate', label: '自由创作', icon: 'edit' },
        { tab: 'history', label: '发布草稿', icon: 'send' }
      ]
    },
    {
      title: '评估与提升',
      icon: 'pulse',
      items: [
        { tab: 'self-diagnosis', label: '诊断我的账号', icon: 'pulse' },
        { tab: 'effects', label: '效果看板', icon: 'chart', badge: '新' },
        { tab: 'skill-optimize', label: 'Skill 优化', icon: 'arrow-up', badge: '新' }
      ]
    }
  ],
  bottom: [{ tab: 'settings', label: '设置', icon: 'settings' }]
}

const WECHAT_NAV: NavConfig = {
  top: [
    { tab: 'brief', label: '每日早报', icon: 'sun' },
    { tab: 'distill', label: '博主蒸馏', icon: 'funnel' }
  ],
  groups: [
    {
      title: 'AI 创作',
      icon: 'sparkles',
      items: [
        { tab: 'ai', label: 'AI 创作', icon: 'sparkles' },
        { tab: 'records', label: '发布草稿', icon: 'send' }
      ]
    }
  ],
  bottom: [{ tab: 'settings', label: '设置', icon: 'settings' }]
}

const nav = computed<NavConfig>(() => (activeMainTab.value === 'wechat' ? WECHAT_NAV : SOCIAL_NAV))
const activeTab = computed(() => (activeMainTab.value === 'wechat' ? activeWechatTab.value : currentSocialTab.value))
function isActive(tab: string): boolean {
  return activeTab.value === tab
}

// 侧栏项点击:在当前平台内切换二级页签(路由驱动 store)。
function goTab(tab: string) {
  const platform = route.params.platform as string
  if (!platform) return
  router.push({ name: 'workspace', params: { platform, tab } })
}

const userInitial = computed(() => (currentUsername.value || '?').slice(0, 1).toUpperCase())
// 搜索 / 通知先只做 UI,点击/⌘K 给出「即将上线」提示,不做假的未读角标。
function comingSoon(feature: string) {
  showMessage(`${feature}即将上线，敬请期待`)
}
function onGlobalSearchKey(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
    e.preventDefault()
    if (isAuthenticated.value && route.name === 'workspace') comingSoon('全局搜索')
  }
}

// 账号菜单:点击开合(见 toggleUserMenu),点菜单外部才关闭。
// 之前用 @mouseleave 关闭 → 鼠标从头像移向「退出登录」时一离开容器就把菜单关了,根本点不中(问题清单 #15)。
const userMenuRef = ref<HTMLElement | null>(null)
function onDocPointerDown(event: MouseEvent) {
  if (showUserMenu.value && userMenuRef.value && !userMenuRef.value.contains(event.target as Node)) {
    showUserMenu.value = false
  }
}

// 应用挂载:注册全局快捷键;已登录则先加载工作空间选项再拉取全部数据,失败则退回登录态。
onMounted(() => {
  window.addEventListener('keydown', handleGlobalKeydown)
  window.addEventListener('keydown', onGlobalSearchKey)
  document.addEventListener('mousedown', onDocPointerDown)
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
  window.removeEventListener('keydown', onGlobalSearchKey)
  document.removeEventListener('mousedown', onDocPointerDown)
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

  <div v-else class="sh-shell">
    <!-- 顶栏 -->
    <header class="sh-topbar">
      <div class="sh-brand">
        <span class="sh-logo" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M12 3l8 4-8 4-8-4 8-4z" /><path d="M4 12l8 4 8-4" /><path d="M4 16.5l8 4 8-4" /></svg>
        </span>
        <div class="sh-brand-txt">
          <strong>Cadence</strong>
          <span class="sh-brand-sub">内容创作工作台</span>
        </div>
      </div>

      <span class="sh-div"></span>

      <button
        type="button"
        class="sh-plat"
        aria-haspopup="dialog"
        :aria-expanded="showPlatformModal"
        @click="showPlatformModal = true"
      >
        <span class="sh-plat-mark" :style="{ background: platformMark.bg }">{{ platformMark.ch }}</span>
        <span class="sh-plat-name">{{ currentPlatformName }}</span>
        <span class="sh-plat-hint">切换平台</span>
        <NavIcon name="chevron-down" />
      </button>

      <span class="sh-spacer"></span>

      <button type="button" class="sh-search" @click="comingSoon('全局搜索')">
        <NavIcon name="search" />
        <span>搜索博主、笔记、Skill…</span>
        <kbd>⌘K</kbd>
      </button>

      <button type="button" class="sh-icon-btn" aria-label="通知" @click="comingSoon('通知')">
        <NavIcon name="bell" />
      </button>

      <span class="sh-div"></span>

      <div ref="userMenuRef" class="sh-user">
        <button
          type="button"
          class="sh-user-trigger"
          :aria-expanded="showUserMenu"
          aria-haspopup="menu"
          @click="toggleUserMenu"
        >
          <span class="sh-avatar">{{ userInitial }}</span>
          <span class="sh-user-txt">
            <strong>{{ currentUsername }}</strong>
            <span v-if="currentTenantName">{{ currentTenantName }}</span>
          </span>
          <NavIcon name="chevron-down" />
        </button>
        <div v-if="showUserMenu" class="sh-user-menu" role="menu">
          <button type="button" role="menuitem" @click="handleLogout">退出登录</button>
        </div>
      </div>
    </header>

    <!-- 侧栏 + 内容区 -->
    <div class="sh-body">
      <aside v-if="route.name === 'workspace'" class="sh-side" aria-label="功能导航">
        <!-- 顶部平铺项 -->
        <button
          v-for="it in nav.top"
          :key="it.tab"
          type="button"
          class="sh-item"
          :class="{ on: isActive(it.tab) }"
          @click="goTab(it.tab)"
        >
          <NavIcon :name="it.icon" /><span class="sh-item-label">{{ it.label }}</span>
          <span v-if="it.badge" class="sh-badge">{{ it.badge }}</span>
        </button>

        <!-- 阶段卡 -->
        <section v-for="g in nav.groups" :key="g.title" class="sh-card">
          <div class="sh-card-head">
            <span class="sh-card-ico" aria-hidden="true"><NavIcon :name="g.icon" /></span>
            {{ g.title }}
          </div>
          <button
            v-for="it in g.items"
            :key="it.tab"
            type="button"
            class="sh-item"
            :class="{ on: isActive(it.tab) }"
            @click="goTab(it.tab)"
          >
            <NavIcon :name="it.icon" /><span class="sh-item-label">{{ it.label }}</span>
            <span v-if="it.badge" class="sh-badge">{{ it.badge }}</span>
          </button>
        </section>

        <!-- 底部沉底项 -->
        <button
          v-for="it in nav.bottom"
          :key="it.tab"
          type="button"
          class="sh-item sh-bottom"
          :class="{ on: isActive(it.tab) }"
          @click="goTab(it.tab)"
        >
          <NavIcon :name="it.icon" /><span class="sh-item-label">{{ it.label }}</span>
        </button>
      </aside>

      <main class="workspace">
        <router-view />
      </main>
    </div>

    <!-- 切换平台弹窗 -->
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

<style scoped>
/* ===== 外壳:顶栏行 + 下方(侧栏 | 内容区) ===== */
.sh-shell {
  display: grid;
  grid-template-rows: 64px minmax(0, 1fr);
  height: 100vh;
  overflow: hidden;
}

/* ===== 顶栏 ===== */
.sh-topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 20px;
  background: var(--color-surface);
  border-bottom: 1px solid #eceef0;
}
.sh-brand {
  display: flex;
  align-items: center;
  gap: 11px;
}
.sh-logo {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 11px;
  background: linear-gradient(150deg, #0f8570, #0b5f50);
  color: #fff;
  flex: 0 0 auto;
}
.sh-brand-txt strong {
  display: block;
  font-size: 15.5px;
  font-weight: 700;
  color: #1b211f;
  letter-spacing: 0.01em;
  line-height: 1.15;
}
.sh-brand-sub {
  font-size: 11.5px;
  color: #9aa5a1;
}
.sh-div {
  width: 1px;
  height: 26px;
  background: #eceef0;
  flex: 0 0 auto;
}
.sh-spacer {
  flex: 1;
}
/* 平台切换 pill */
.sh-plat {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 40px;
  padding: 0 12px 0 8px;
  border: 1px solid #eceef0;
  border-radius: 11px;
  background: var(--color-surface);
  cursor: pointer;
  transition: background 140ms var(--ease-out), border-color 140ms var(--ease-out);
}
.sh-plat:hover {
  background: #f6f8f7;
}
.sh-plat-mark {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border-radius: 7px;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  flex: 0 0 auto;
}
.sh-plat-name {
  font-size: 13.5px;
  font-weight: 600;
  color: #2a3138;
}
.sh-plat-hint {
  font-size: 12px;
  color: #9aa5a1;
}
.sh-plat :deep(.nav-icon) {
  color: #9aa5a1;
  width: 15px;
  height: 15px;
}
/* 搜索 */
.sh-search {
  display: flex;
  align-items: center;
  gap: 9px;
  width: 250px;
  height: 40px;
  padding: 0 12px;
  border: 1px solid #eceef0;
  border-radius: 10px;
  background: #f4f6f5;
  color: #aab2b8;
  font-size: 13px;
  cursor: pointer;
  transition: border-color 140ms var(--ease-out), background 140ms var(--ease-out);
}
.sh-search:hover {
  background: #eef1f0;
}
.sh-search span {
  flex: 1;
  min-width: 0;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sh-search :deep(.nav-icon) {
  color: #aab2b8;
  flex: 0 0 auto;
}
.sh-search kbd {
  flex: 0 0 auto;
  padding: 2px 6px;
  border-radius: 6px;
  border: 1px solid #e2e6e4;
  background: var(--color-surface);
  font-size: 11px;
  color: #8f9a95;
  font-family: inherit;
}
/* 图标按钮(通知) */
.sh-icon-btn {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border: 1px solid #eceef0;
  border-radius: 10px;
  background: var(--color-surface);
  color: #586169;
  cursor: pointer;
  transition: background 140ms var(--ease-out);
}
.sh-icon-btn:hover {
  background: #f6f8f7;
}
/* 用户菜单 */
.sh-user {
  position: relative;
}
.sh-user-trigger {
  display: flex;
  align-items: center;
  gap: 9px;
  height: 44px;
  padding: 0 8px;
  border: 0;
  border-radius: 11px;
  background: transparent;
  cursor: pointer;
  transition: background 140ms var(--ease-out);
}
.sh-user-trigger:hover {
  background: #f6f8f7;
}
.sh-avatar {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(150deg, #0f8570, #0b5f50);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  flex: 0 0 auto;
}
.sh-user-txt {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  min-width: 0;
  line-height: 1.25;
}
.sh-user-txt strong {
  font-size: 13px;
  font-weight: 650;
  color: #1b211f;
}
.sh-user-txt span {
  font-size: 11px;
  color: #9aa5a1;
  max-width: 120px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sh-user-trigger :deep(.nav-icon) {
  color: #9aa5a1;
  width: 15px;
  height: 15px;
}
.sh-user-menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  min-width: 140px;
  padding: 6px;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: 12px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.14);
  z-index: 60;
}
.sh-user-menu button {
  width: 100%;
  padding: 9px 12px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  text-align: left;
  font-size: 13.5px;
  color: var(--color-ink-2);
  cursor: pointer;
}
.sh-user-menu button:hover {
  background: #eef1f0;
}

/* ===== 侧栏 ===== */
.sh-body {
  display: grid;
  grid-template-columns: 264px minmax(0, 1fr);
  min-height: 0;
}
.sh-side {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px 14px;
  background: #f1f4f3;
  border-right: 1px solid #e6eae8;
  overflow-y: auto;
}
/* 导航项 */
.sh-item {
  display: flex;
  align-items: center;
  gap: 11px;
  height: 42px;
  padding: 0 12px;
  border: 0;
  border-radius: 11px;
  background: transparent;
  color: #586169;
  font-size: 13.5px;
  font-weight: 500;
  cursor: pointer;
  text-align: left;
  transition: background 130ms var(--ease-out), color 130ms var(--ease-out), box-shadow 130ms var(--ease-out);
}
.sh-item :deep(.nav-icon) {
  color: #98a3a9;
  flex: 0 0 auto;
  transition: color 130ms var(--ease-out);
}
.sh-item-label {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sh-item:hover {
  background: #eef1f0;
}
.sh-item.on {
  background: var(--color-surface);
  color: #0d5a4a;
  font-weight: 620;
  box-shadow: 0 3px 10px -4px rgba(13, 90, 74, 0.28);
}
.sh-item.on :deep(.nav-icon) {
  color: var(--color-accent);
}
.sh-badge {
  flex: 0 0 auto;
  padding: 1px 7px;
  border-radius: var(--radius-pill);
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
  font-size: 10.5px;
  font-weight: 700;
}
/* 阶段卡 */
.sh-card {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px;
  border: 1px solid #e8ecea;
  border-radius: 14px;
  background: #fbfcfc;
}
.sh-card .sh-item {
  height: 38px;
  border-radius: 10px;
}
.sh-card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px 6px;
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #8f9a95;
}
.sh-card-ico {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 7px;
  background: #eef4f1;
  color: var(--color-accent);
  flex: 0 0 auto;
}
.sh-card-ico :deep(.nav-icon) {
  width: 14px;
  height: 14px;
}
/* 底部沉底 */
.sh-bottom {
  margin-top: auto;
}

@media (max-width: 960px) {
  .sh-search,
  .sh-brand-sub,
  .sh-plat-hint {
    display: none;
  }
}
@media (max-width: 720px) {
  .sh-body {
    grid-template-columns: 216px minmax(0, 1fr);
  }
  .sh-user-txt {
    display: none;
  }
}
</style>
