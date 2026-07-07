import type {
  AccountAuditRun,
  AdminTask,
  AdminTenant,
  AdminUser,
  AdminUserCreate,
  AppraisalIntentContext,
  AppraisalIntentSuggestResult,
  AppSettingRead,
  Article,
  ArticleUpdate,
  BloggerCollectRequest,
  BloggerUrlCollectRequest,
  BloggerCollectionRun,
  BenchmarkIntent,
  BenchmarkRecommendationRun,
  BloggerDistillationRun,
  BloggerDossier,
  DossierAudience,
  BloggerPost,
  BloggerProfile,
  BloggerProfileCreate,
  BloggerProfileUpdate,
  BloggerSearchResult,
  BloggerSkill,
  EvaluateResult,
  ConfigView,
  CostEvent,
  CostSummary,
  CurrentUser,
  ModelPrices,
  QueueHealth,
  LoginResponse,
  NewsItem,
  OperationTask,
  OperationTaskEvent,
  SocialPlatform,
  Tenant,
  WorkspaceConfig,
  WorkspaceConfigUpdate,
  DashboardAccount,
  DashboardGrowth,
  DashboardOverview,
  XhsPublishPackage,
  XhsPublishPackageCreate,
  XhsPublishPackageSave,
  XhsTopicIdeaRequest,
  XhsTopicIdeaResponse
} from './types'
const API_BASE = `${import.meta.env.BASE_URL}api`
const TOKEN_KEY = 'pubsync_token'
const TENANT_KEY = 'pubsync_tenant_id'

export function getAuthToken() {
  return window.localStorage.getItem(TOKEN_KEY) || ''
}

export function setAuthToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token)
}

export function clearAuthToken() {
  window.localStorage.removeItem(TOKEN_KEY)
}

export function getTenantId() {
  return window.localStorage.getItem(TENANT_KEY) || ''
}

export function setTenantId(id: number | string) {
  window.localStorage.setItem(TENANT_KEY, String(id))
}

export function clearTenantId() {
  window.localStorage.removeItem(TENANT_KEY)
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getAuthToken()
  const tenantId = getTenantId()
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(tenantId ? { 'X-Tenant-ID': tenantId } : {}),
      ...(options.headers || {})
    },
    ...options
  })

  if (!response.ok) {
    // Centralized auth handling: an expired/invalid session anywhere clears the
    // stored credentials and returns to the login screen. The login request is
    // excluded so a wrong password does not trigger a reload loop.
    if (response.status === 401 && path !== '/auth/login') {
      clearAuthToken()
      clearTenantId()
      if (typeof window !== 'undefined') {
        window.location.reload()
      }
    }
    let detail = response.statusText
    try {
      const body = (await response.json()) as { detail?: string }
      detail = body.detail || detail
    } catch {
      // Keep HTTP status text for non-JSON failures.
    }
    throw new Error(detail)
  }

  if (response.status === 204) {
    return undefined as T
  }
  return response.json() as Promise<T>
}

export async function login(username: string, password: string) {
  const result = await request<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password })
  })
  setAuthToken(result.access_token)
  return result
}

export function listTenants() {
  return request<Tenant[]>('/tenants')
}

export function getCurrentUser() {
  return request<CurrentUser>('/auth/me')
}

export function listAdminUsers() {
  return request<AdminUser[]>('/admin/users')
}

export function createAdminUser(payload: AdminUserCreate) {
  return request<AdminUser>('/admin/users', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function listAdminTenants() {
  return request<AdminTenant[]>('/admin/tenants')
}

export function disableAdminUser(userId: number) {
  return request<AdminUser>(`/admin/users/${userId}/disable`, { method: 'POST' })
}

export function enableAdminUser(userId: number) {
  return request<AdminUser>(`/admin/users/${userId}/enable`, { method: 'POST' })
}

export function resetAdminUserPassword(userId: number, password: string) {
  return request<AdminUser>(`/admin/users/${userId}/reset-password`, {
    method: 'POST',
    body: JSON.stringify({ password })
  })
}

export function getAdminConfig() {
  return request<ConfigView>('/admin/config')
}

export function updateAdminConfig(key: string, value: string) {
  return request<ConfigView>('/admin/config', {
    method: 'PUT',
    body: JSON.stringify({ key, value })
  })
}

export function clearAdminConfig(key: string) {
  return request<ConfigView>(`/admin/config/${encodeURIComponent(key)}`, { method: 'DELETE' })
}

export function listAdminTasks(params: { status?: string; task_type?: string; limit?: number } = {}) {
  const search = new URLSearchParams()
  if (params.status) search.set('status', params.status)
  if (params.task_type) search.set('task_type', params.task_type)
  if (params.limit) search.set('limit', String(params.limit))
  const qs = search.toString()
  return request<AdminTask[]>(`/admin/tasks${qs ? `?${qs}` : ''}`)
}

export function getAdminTaskEvents(taskId: string) {
  return request<OperationTaskEvent[]>(`/admin/tasks/${taskId}/events`)
}

export function cancelAdminTask(taskId: string) {
  return request<AdminTask>(`/admin/tasks/${taskId}/cancel`, { method: 'POST' })
}

export function retryAdminTask(taskId: string) {
  return request<AdminTask>(`/admin/tasks/${taskId}/retry`, { method: 'POST' })
}

export function getAdminQueueHealth() {
  return request<QueueHealth>('/admin/queue')
}

export function getAdminCosts(params: { provider?: string; tenant_id?: number; days?: number; limit?: number } = {}) {
  const search = new URLSearchParams()
  if (params.provider) search.set('provider', params.provider)
  if (params.tenant_id) search.set('tenant_id', String(params.tenant_id))
  if (params.days) search.set('days', String(params.days))
  if (params.limit) search.set('limit', String(params.limit))
  const qs = search.toString()
  return request<CostEvent[]>(`/admin/costs${qs ? `?${qs}` : ''}`)
}

export function getAdminCostSummary(days: number) {
  return request<CostSummary>(`/admin/costs/summary?days=${days}`)
}

export function getModelPrices() {
  return request<ModelPrices>('/admin/costs/prices')
}

export function putModelPrices(payload: ModelPrices) {
  return request<ModelPrices>('/admin/costs/prices', { method: 'PUT', body: JSON.stringify(payload) })
}

export function listAppSettings() {
  return request<AppSettingRead[]>('/settings')
}

export function upsertAppSetting(key: string, value: string) {
  return request<AppSettingRead>(`/settings/${encodeURIComponent(key)}`, {
    method: 'PUT',
    body: JSON.stringify({ value })
  })
}

export function getWorkspaceConfig() {
  return request<WorkspaceConfig>('/workspace/config')
}

export function updateWorkspaceConfig(payload: WorkspaceConfigUpdate) {
  return request<WorkspaceConfig>('/workspace/config', {
    method: 'PUT',
    body: JSON.stringify(payload)
  })
}

export function fetchNews() {
  return request<OperationTask>('/news/fetch', { method: 'POST' })
}

export function listNews() {
  return request<NewsItem[]>('/news')
}

export function updateNewsSelection(id: number, selected: boolean) {
  return request<NewsItem>(`/news/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ selected })
  })
}

export function generateArticle() {
  return request<OperationTask>('/articles/generate', { method: 'POST' })
}

export function getTask(id: string) {
  return request<OperationTask>(`/tasks/${id}`)
}

export function getTaskEvents(id: string) {
  return request<OperationTaskEvent[]>(`/tasks/${id}/events`)
}

export function cancelTask(id: string) {
  return request<OperationTask>(`/tasks/${id}/cancel`, { method: 'POST' })
}

export function getLatestArticle() {
  return request<Article | null>('/articles/latest')
}

export function updateArticle(id: number, payload: ArticleUpdate) {
  return request<Article>(`/articles/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload)
  })
}

export function sendArticleToWechat(id: number) {
  return request<Article>(`/articles/${id}/send-to-wechat`, { method: 'POST' })
}

export function listBloggers(platform: SocialPlatform = 'xhs', accountType?: 'benchmark' | 'mine') {
  const qs = accountType ? `&account_type=${accountType}` : ''
  return request<BloggerProfile[]>(`/bloggers?platform=${encodeURIComponent(platform)}${qs}`)
}

export function searchBloggers(platform: SocialPlatform, keyword: string, page = 1) {
  return request<BloggerSearchResult[]>(
    `/bloggers/search?platform=${encodeURIComponent(platform)}&keyword=${encodeURIComponent(keyword)}&page=${page}`
  )
}

export function createBlogger(payload: BloggerProfileCreate) {
  return request<BloggerProfile>('/bloggers', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function updateBlogger(id: number, payload: BloggerProfileUpdate) {
  return request<BloggerProfile>(`/bloggers/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload)
  })
}

export function refreshBloggerProfile(id: number) {
  return request<BloggerProfile>(`/bloggers/${id}/refresh-profile`, { method: 'POST' })
}

export function updateBloggerFavorite(id: number, isFavorite: boolean) {
  return request<BloggerProfile>(`/bloggers/${id}/favorite`, {
    method: 'PATCH',
    body: JSON.stringify({ is_favorite: isFavorite })
  })
}

export function deleteBlogger(id: number) {
  return request<void>(`/bloggers/${id}`, { method: 'DELETE' })
}

export function listBloggerPosts(id: number) {
  return request<BloggerPost[]>(`/bloggers/${id}/posts`)
}

export function deleteBloggerPosts(id: number, postIds: number[]) {
  return request<{ excluded: number }>(`/bloggers/${id}/posts/delete`, {
    method: 'POST',
    body: JSON.stringify({ post_ids: postIds })
  })
}

export function collectBlogger(id: number, payload: BloggerCollectRequest) {
  return request<OperationTask>(`/bloggers/${id}/collect`, {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function collectBloggerByUrls(id: number, payload: BloggerUrlCollectRequest) {
  return request<OperationTask>(`/bloggers/${id}/collect-by-urls`, {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function listBloggerCollectionRuns(id: number) {
  return request<BloggerCollectionRun[]>(`/bloggers/${id}/collection-runs`)
}

export function listBloggerRuns(id: number) {
  return request<BloggerDistillationRun[]>(`/bloggers/${id}/distillation-runs`)
}

export function listBloggerSkills(platform: SocialPlatform = 'xhs') {
  return request<BloggerSkill[]>(`/blogger-skills?platform=${encodeURIComponent(platform)}`)
}

export function listXhsPublishPackages() {
  return request<XhsPublishPackage[]>('/xhs/publish-packages')
}

export function markXhsPackagePublished(packageId: number, published: boolean) {
  return request<XhsPublishPackage>(`/xhs/publish-packages/${packageId}/mark-published`, {
    method: 'POST',
    body: JSON.stringify({ published })
  })
}

// —— 效果看板 ——
export function getDashboardOverview(range = '30d') {
  return request<DashboardOverview>(`/dashboard/overview?range=${range}`)
}

export function getAccountDashboard(accountId: number, range = '30d') {
  return request<DashboardAccount>(`/dashboard/account/${accountId}?range=${range}`)
}

export function getAccountGrowth(accountId: number, range = '30d') {
  return request<DashboardGrowth>(`/dashboard/account/${accountId}/growth?range=${range}`)
}

export function startXhsPublishPackageDraftTask(payload: XhsPublishPackageCreate) {
  return request<OperationTask>('/xhs/package-drafts/generate', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function saveXhsPublishPackage(payload: XhsPublishPackageSave) {
  return request<XhsPublishPackage>('/xhs/publish-packages', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function generateXhsTopicIdeas(payload: XhsTopicIdeaRequest) {
  return request<XhsTopicIdeaResponse>('/xhs/topic-ideas', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}


export function recommendBloggers(payload: {
  platform: SocialPlatform
  intent: BenchmarkIntent
  my_account_id?: number | null
}) {
  return request<OperationTask>('/bloggers/recommend', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function listRecommendRuns(taskId?: string, platform: SocialPlatform = 'xhs') {
  const qs = taskId ? `&task_id=${encodeURIComponent(taskId)}` : ''
  return request<BenchmarkRecommendationRun[]>(
    `/bloggers/recommend/runs?platform=${encodeURIComponent(platform)}${qs}&limit=1`
  )
}

export function evaluateBlogger(payload: {
  platform: SocialPlatform
  intent: BenchmarkIntent
  my_account_id?: number | null
  candidate?: BloggerSearchResult | null
  homepage_url?: string | null
}) {
  return request<EvaluateResult>('/bloggers/evaluate', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function listAccountAuditRuns(platform: SocialPlatform = 'xhs', kind?: 'benchmark' | 'self') {
  const qs = kind ? `&kind=${kind}` : ''
  return request<AccountAuditRun[]>(`/account-audit/runs?platform=${encodeURIComponent(platform)}${qs}`)
}

export function appraiseBlogger(payload: {
  blogger_id: number
  kind: 'benchmark' | 'self'
  intent?: string
  industry?: string | null
  my_blogger_id?: number | null
}) {
  return request<OperationTask>('/account-audit/appraise', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

// 意图引导:看选中账号在做什么 → 判断意图够不够具体 → 不够给几道多选题。同步返回。
// kind=benchmark(默认,对标别人「想学什么」)/ self(诊断自己「目标·痛点·阶段」)。
export function suggestAppraisalIntent(payload: { blogger_id: number; intent?: string; kind?: 'benchmark' | 'self' }) {
  return request<AppraisalIntentSuggestResult>('/account-audit/intent-suggest', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

// 答题打卡第一段「读取 TA 最近笔记」的真实事件:只做便宜的 DB 读,返回将喂给模型的近期笔记数。
export function fetchAppraisalIntentContext(payload: { blogger_id: number; kind?: 'benchmark' | 'self' }) {
  return request<AppraisalIntentContext>('/account-audit/intent-context', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

// ============================ 博主档案(Dossier) ============================

export function getBloggerDossier(bloggerId: number): Promise<BloggerDossier> {
  return request(`/bloggers/${bloggerId}/dossier`)
}

export function buildBloggerDossier(bloggerId: number): Promise<OperationTask> {
  return request(`/bloggers/${bloggerId}/dossier/build`, { method: 'POST', body: JSON.stringify({}) })
}

export function redistillBloggerDossier(bloggerId: number): Promise<OperationTask> {
  return request(`/bloggers/${bloggerId}/dossier/redistill`, { method: 'POST', body: JSON.stringify({}) })
}

export function syncBloggerPool(bloggerId: number, mode: 'incremental' | 'full'): Promise<OperationTask> {
  return request(`/bloggers/${bloggerId}/dossier/pool/sync`, { method: 'POST', body: JSON.stringify({ mode }) })
}

export function runBloggerAudience(bloggerId: number): Promise<DossierAudience> {
  return request(`/bloggers/${bloggerId}/dossier/audience`, { method: 'POST', body: JSON.stringify({}) })
}
