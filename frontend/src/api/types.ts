export type ArticleStatus = 'draft' | 'generated' | 'sent_to_wechat' | 'failed'
export type TaskStatus = 'queued' | 'running' | 'succeeded' | 'failed'
export type TenantStatus = 'active' | 'disabled'

export interface Tenant {
  id: number
  name: string
  slug: string
  status: TenantStatus
}

export interface ContentProfile {
  tenant_id: number
  publication_name: string
  workspace_title: string
  title_prefix: string
  content_domain: string
  editor_persona: string
  audience: string
  article_style: string
  international_label: string
  domestic_label: string
  categories_json: string
  image_style: string
}

export interface NewsItem {
  id: number
  tenant_id: number
  title: string
  source: string
  url: string
  published_at: string
  summary: string
  category: string
  region: string
  importance_score: number
  selected: boolean
  created_at: string
}

export interface Article {
  id: number
  tenant_id: number
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
  tenant_id: number
  task_type: string
  status: TaskStatus
  message: string
  article_id: number | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface OperationTaskEvent {
  id: number
  tenant_id: number
  task_id: string
  step_name: string
  status: string
  message: string
  payload_json: string | null
  created_at: string
}
