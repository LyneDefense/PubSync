export type ArticleStatus = 'draft' | 'generated' | 'sent_to_wechat' | 'failed'
export type TaskStatus = 'queued' | 'running' | 'succeeded' | 'failed'

export interface NewsItem {
  id: number
  title: string
  source: string
  url: string
  published_at: string
  summary: string
  category: string
  importance_score: number
  selected: boolean
  created_at: string
}

export interface Article {
  id: number
  title: string
  intro: string
  content_html: string
  cover_image_url: string
  status: ArticleStatus
  wechat_draft_id: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface Dashboard {
  news_count: number
  selected_count: number
  latest_article: Article | null
  last_fetch_at: string | null
  scheduled_publish_time: string
}

export interface ArticleUpdate {
  title: string
  intro: string
  cover_image_url: string
  content_html: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface OperationTask {
  id: string
  task_type: string
  status: TaskStatus
  message: string
  article_id: number | null
  error_message: string | null
  created_at: string
  updated_at: string
}
