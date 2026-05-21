import type { Article, ArticleUpdate, Dashboard, LoginResponse, NewsItem, OperationTask } from './types'

const API_BASE = `${import.meta.env.BASE_URL}api`
const TOKEN_KEY = 'pubsync_token'

export function getAuthToken() {
  return window.localStorage.getItem(TOKEN_KEY) || ''
}

export function setAuthToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token)
}

export function clearAuthToken() {
  window.localStorage.removeItem(TOKEN_KEY)
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getAuthToken()
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
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

export function getDashboard() {
  return request<Dashboard>('/dashboard')
}

export function fetchNews() {
  return request<NewsItem[]>('/news/fetch', { method: 'POST' })
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
