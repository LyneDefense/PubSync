import type {
  BloggerPost,
  OperationTaskEvent,
  XhsPublishPackage,
  XhsPublishPackageDraft
} from '../api/types'

/**
 * Pure presentation/parsing helpers extracted from App.vue.
 *
 * These functions hold no reactive state — they only transform their arguments —
 * so they are safe to share across components and unit-test in isolation.
 */

// Returns any[] (not unknown[]) to match the original inferred type: callers and
// templates index into the parsed items directly (e.g. item.url, item.caption).
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function parseJsonArray(raw?: string | null): any[] {
  if (!raw) {
    return []
  }
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function parseJsonObject(raw?: string | null): Record<string, unknown> {
  if (!raw) {
    return {}
  }
  try {
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? (parsed as Record<string, unknown>) : {}
  } catch {
    return {}
  }
}

// 全站统一的状态语义。色调：success=墨绿 / danger=砖红 / info=蓝(进行中) /
// warn=琥珀(待确认) / neutral=中性灰。覆盖任务、采集、蒸馏、文章、账号、ASR 等所有状态值。
export type StatusTone = 'success' | 'danger' | 'info' | 'warn' | 'neutral'

const STATUS_LABELS: Record<string, string> = {
  // 任务 / 采集 / 蒸馏通用
  queued: '排队中',
  running: '进行中',
  processing: '处理中',
  cancel_requested: '停止中',
  cancelled: '已停止',
  succeeded: '已完成',
  failed: '失败',
  pending_confirmation: '待确认',
  abandoned: '已放弃',
  // 文章
  draft: '草稿',
  generated: '已生成',
  sent_to_wechat: '已入草稿箱',
  // 账号 / Skill / 租户
  active: '启用',
  disabled: '已停用',
  // 视频字幕 / ASR
  not_required: '无需转写',
  pending: '待处理',
  skipped: '已跳过',
  done: '已完成',
  error: '失败'
}

const STATUS_TONES: Record<string, StatusTone> = {
  succeeded: 'success',
  generated: 'success',
  sent_to_wechat: 'success',
  active: 'success',
  done: 'success',
  failed: 'danger',
  abandoned: 'danger',
  error: 'danger',
  running: 'info',
  queued: 'info',
  processing: 'info',
  cancel_requested: 'info',
  pending: 'info',
  pending_confirmation: 'warn',
  cancelled: 'neutral',
  cancel_request: 'neutral',
  disabled: 'neutral',
  not_required: 'neutral',
  skipped: 'neutral',
  draft: 'neutral'
}

export function statusLabel(status: string | null | undefined): string {
  if (!status) return '—'
  return STATUS_LABELS[status] || status
}

export function statusTone(status: string | null | undefined): StatusTone {
  if (!status) return 'neutral'
  return STATUS_TONES[status] || 'neutral'
}

export function sampledCommentCount(post: BloggerPost): number {
  if (typeof post.sampled_comment_count === 'number') {
    return post.sampled_comment_count
  }
  try {
    const comments = JSON.parse(post.comments_json || '[]')
    return Array.isArray(comments) ? comments.length : 0
  } catch {
    return 0
  }
}

export function bloggerCommentLabel(post: BloggerPost): string {
  if (post.comment_count > 0) {
    return `评论 ${post.comment_count}`
  }
  const sampledCount = sampledCommentCount(post)
  return sampledCount > 0 ? `评论未知 / 采样 ${sampledCount}` : '评论未知'
}

export function xhsContentTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    text_note: '图文笔记',
    image_note: '图文配图',
    spoken_script: '口播脚本',
    video_script: '视频脚本'
  }
  return labels[type] || type
}

export function xhsPackageCopyText(
  pack: Pick<XhsPublishPackage, 'title' | 'body_text' | 'hashtags_json'> | XhsPublishPackageDraft
): string {
  const tags = parseJsonArray(pack.hashtags_json)
    .map((tag) => `#${String(tag).replace(/^#/, '')}`)
    .join(' ')
  return [pack.title, pack.body_text, tags].filter(Boolean).join('\n\n')
}

export function parseEventPayload(event: OperationTaskEvent): Record<string, unknown> | null {
  if (!event.payload_json) {
    return null
  }
  try {
    return JSON.parse(event.payload_json) as Record<string, unknown>
  } catch {
    return null
  }
}

export function findXhsDraftFromEvents(events: OperationTaskEvent[]): XhsPublishPackageDraft | null {
  for (const event of [...events].reverse()) {
    const payload = parseEventPayload(event)
    const draft = payload?.draft
    if (draft && typeof draft === 'object') {
      return draft as XhsPublishPackageDraft
    }
  }
  return null
}

export function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
