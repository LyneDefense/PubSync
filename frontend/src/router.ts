import { h } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import type { RouteLocationNormalized } from 'vue-router'

import { isAuthenticated } from './composables/useWorkspaceStore'

// 三个平台 = 三个工作台入口；每个平台进入后默认落到一个二级页签。
export const PLATFORMS = ['xhs', 'douyin', 'wechat'] as const
export type PlatformParam = (typeof PLATFORMS)[number]
export const DEFAULT_TAB: Record<PlatformParam, string> = {
  xhs: 'overview',
  douyin: 'overview',
  wechat: 'brief'
}

const LAST_PLATFORM_KEY = 'pubsync_last_platform'

// 登录后跳回最近用过的平台；没有记录则去选平台页。
export function readLastPlatform(): PlatformParam | '' {
  try {
    const raw = window.localStorage.getItem(LAST_PLATFORM_KEY)
    return raw && (PLATFORMS as readonly string[]).includes(raw) ? (raw as PlatformParam) : ''
  } catch {
    return ''
  }
}

function isPlatform(value: unknown): value is PlatformParam {
  return typeof value === 'string' && (PLATFORMS as readonly string[]).includes(value)
}

// 登录后默认目的地：对象驱动新首页(UI·9 起,不再落到选平台/旧工作台)。
function landingTarget() {
  return { name: 'home' }
}

const routes = [
  { path: '/', redirect: () => ({ name: 'login' }) },
  // /login 的画面由 App 外壳在未登录态直接渲染 LoginView，这里只占位用于 URL 与守卫。
  { path: '/login', name: 'login', component: { render: () => null } },
  { path: '/select', name: 'select', component: () => import('./views/SelectPlatformView.vue') },
  // —— 对象驱动新架构(与旧 workspace 并存;阶段4/UI·9 才把默认落地切到 /home 并下线旧壳)——
  // meta.shell='new' → App.vue 用新 AppShell 渲染(无侧栏)。未建成页面先走统一占位。
  { path: '/home', name: 'home', meta: { shell: 'new' }, component: () => import('./views/HomeView.vue') },
  { path: '/blogger/:id', name: 'blogger', meta: { shell: 'new', title: '博主档案' }, component: () => import('./views/BloggerObjectView.vue') },
  { path: '/account/:id', name: 'account', meta: { shell: 'new', title: '我的账号' }, component: () => import('./views/AccountObjectView.vue') },
  { path: '/create', name: 'create', meta: { shell: 'new', title: '创作' }, component: () => import('./views/SocialPackagesView.vue'), props: (route: RouteLocationNormalized) => ({ embedded: true, bloggerId: Number(route.query.blogger) || undefined }) },
  { path: '/drafts', name: 'drafts', meta: { shell: 'new', title: '发布草稿' }, component: () => import('./views/SocialHistoryView.vue'), props: { embedded: true } },
  { path: '/find', name: 'find', meta: { shell: 'new', title: '加对标博主' }, component: () => import('./views/FindBenchmarkView.vue'), props: { embedded: true } },
  { path: '/settings-new', name: 'settings-new', meta: { shell: 'new', title: '设置' }, component: () => import('./views/NewShellPlaceholder.vue') },
  { path: '/:platform/:tab?', name: 'workspace', component: () => import('./views/WorkspaceView.vue') },
  // 兜底:任何未匹配路径(含从落地页进来的 /login.html 初始 URL)先归到登录,守卫再分流。
  { path: '/:pathMatch(.*)*', name: 'notfound', redirect: () => ({ name: 'login' }) }
]

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

// 守卫：未登录 → 登录；已登录访问登录页 → 跳回工作台；工作台缺/错平台或缺页签 → 规整。
router.beforeEach((to: RouteLocationNormalized) => {
  if (!isAuthenticated.value) {
    // 未登录访问任意页 → 登录页,但把原目标记进 ?redirect,登录成功后跳回去(否则深链/新架构页永远到不了)。
    return to.name === 'login' ? true : { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login') {
    return landingTarget()
  }
  if (to.name === 'workspace') {
    const platform = to.params.platform
    if (!isPlatform(platform)) {
      return { name: 'select' }
    }
    if (!to.params.tab) {
      return { name: 'workspace', params: { platform, tab: DEFAULT_TAB[platform] } }
    }
  }
  return true
})

export default router
