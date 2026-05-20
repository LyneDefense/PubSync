import type { Article, ArticleUpdate, Dashboard, NewsItem } from './types'

const API_BASE = `${import.meta.env.BASE_URL}api`

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
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
  return request<Article>('/articles/generate', { method: 'POST' })
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
