import type {
  AdminUser,
  AdminUserCreate,
  Article,
  ArticleUpdate,
  BloggerCollectRequest,
  BloggerCollectionRun,
  BloggerDistillationRun,
  BloggerDistillRequest,
  BloggerPost,
  BloggerProfile,
  BloggerProfileCreate,
  BloggerProfileUpdate,
  BloggerSearchResult,
  BloggerSkill,
  ContentProfile,
  CurrentUser,
  LoginResponse,
  NewsItem,
  OperationTask,
  OperationTaskEvent,
  SocialPlatform,
  Tenant,
  WorkspaceConfig,
  WorkspaceConfigUpdate,
  XhsPublishPackage,
  XhsPublishPackageCreate,
  XhsPublishPackageDraft,
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

export function getProfile() {
  return request<ContentProfile>('/profile')
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

export function listBloggers(platform: SocialPlatform = 'xhs') {
  return request<BloggerProfile[]>(`/bloggers?platform=${encodeURIComponent(platform)}`)
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

export function collectBlogger(id: number, payload: BloggerCollectRequest) {
  return request<OperationTask>(`/bloggers/${id}/collect`, {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function listBloggerCollectionRuns(id: number) {
  return request<BloggerCollectionRun[]>(`/bloggers/${id}/collection-runs`)
}

export function listBloggerCollectionPosts(id: number, collectionRunId: number) {
  return request<BloggerPost[]>(`/bloggers/${id}/collection-runs/${collectionRunId}/posts`)
}

export function distillBlogger(id: number, payload: BloggerDistillRequest) {
  return request<OperationTask>(`/bloggers/${id}/distill`, {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function listBloggerRuns(id: number) {
  return request<BloggerDistillationRun[]>(`/bloggers/${id}/distillation-runs`)
}

export function confirmBloggerRun(bloggerId: number, runId: number) {
  return request<BloggerDistillationRun>(`/bloggers/${bloggerId}/distillation-runs/${runId}/confirm`, { method: 'POST' })
}

export function abandonBloggerRun(bloggerId: number, runId: number) {
  return request<BloggerDistillationRun>(`/bloggers/${bloggerId}/distillation-runs/${runId}/abandon`, { method: 'POST' })
}

export function listBloggerSkills(platform: SocialPlatform = 'xhs') {
  return request<BloggerSkill[]>(`/blogger-skills?platform=${encodeURIComponent(platform)}`)
}

export function listXhsPublishPackages() {
  return request<XhsPublishPackage[]>('/xhs/publish-packages')
}

export function createXhsPublishPackage(payload: XhsPublishPackageCreate) {
  return generateXhsPublishPackageDraft(payload)
}

export function generateXhsPublishPackageDraft(payload: XhsPublishPackageCreate) {
  return request<XhsPublishPackageDraft>('/xhs/package-drafts', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
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
