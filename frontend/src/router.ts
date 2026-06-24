import { h } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import type { RouteLocationNormalized } from 'vue-router'

import { isAuthenticated } from './composables/useWorkspaceStore'

// 三个平台 = 三个工作台入口；每个平台进入后默认落到一个二级页签。
export const PLATFORMS = ['xhs', 'douyin', 'wechat'] as const
export type PlatformParam = (typeof PLATFORMS)[number]
export const DEFAULT_TAB: Record<PlatformParam, string> = {
  xhs: 'assets',
  douyin: 'assets',
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

// 登录后默认目的地：最近平台/对应默认页签，否则选平台页。
function landingTarget() {
  const last = readLastPlatform()
  return last ? { name: 'workspace', params: { platform: last, tab: DEFAULT_TAB[last] } } : { name: 'select' }
}

const routes = [
  { path: '/', redirect: () => ({ name: 'login' }) },
  // /login 的画面由 App 外壳在未登录态直接渲染 LoginView，这里只占位用于 URL 与守卫。
  { path: '/login', name: 'login', component: { render: () => null } },
  { path: '/select', name: 'select', component: () => import('./views/SelectPlatformView.vue') },
  { path: '/:platform/:tab?', name: 'workspace', component: () => import('./views/WorkspaceView.vue') }
]

export const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

// 守卫：未登录 → 登录；已登录访问登录页 → 跳回工作台；工作台缺/错平台或缺页签 → 规整。
router.beforeEach((to: RouteLocationNormalized) => {
  if (!isAuthenticated.value) {
    return to.name === 'login' ? true : { name: 'login' }
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
