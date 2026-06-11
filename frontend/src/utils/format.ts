import type {
  BloggerCollectionRun,
  BloggerDistillationRun,
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

export function runCostLabel(run: BloggerDistillationRun): string {
  return `$${run.tikhub_estimated_cost_usd.toFixed(4)}`
}

export function collectionCostLabel(run: BloggerCollectionRun): string {
  return `$${run.tikhub_estimated_cost_usd.toFixed(4)}`
}

export function distillationStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    running: '进行中',
    succeeded: '已完成',
    pending_confirmation: '待确认',
    abandoned: '已放弃',
    failed: '失败',
    cancelled: '已停止',
    cancel_requested: '停止中'
  }
  return labels[status] || status
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
