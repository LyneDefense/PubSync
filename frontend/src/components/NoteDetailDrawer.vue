<script setup lang="ts">
// 单篇笔记详情·右侧抽屉。公共组件:博主资产 / 我的账号 共用。
// 纯展示,状态全在 store —— 由调用方 openNote(post.id) 打开;这里读 activeNotePost 渲染、closeNote 关闭。
// activeNotePost 会在 bloggerPosts + accountPosts 里找,所以对标博主与我的账号的笔记都能显示。
import { computed } from 'vue'
import { bloggerCommentLabel } from '../utils/format'
import TIcon from './TIcon.vue'
import {
  activeNotePost,
  closeNote,
  handleDeleteNote,
  formatDate,
  noteBodyText,
  noteHashtags,
  noteTopComments,
  subtypeLabel
} from '../composables/useWorkspaceStore'

// 视觉层:图内文字(OCR) + 封面解析(visual_digest)。有值才展示这一段。
const noteVisual = computed(() => {
  const post = activeNotePost.value
  if (!post) return null
  const text = (post.image_text || '').trim()
  let digest: { cover_hook?: string; layout?: string; style?: string } = {}
  try {
    digest = post.visual_digest ? JSON.parse(post.visual_digest) : {}
  } catch {
    digest = {}
  }
  const hook = (digest.cover_hook || '').trim()
  const layout = (digest.layout || '').trim()
  if (!text && !hook && !layout) return null
  return { text, hook, layout }
})
</script>

<template>
  <div v-if="activeNotePost" class="drawer-overlay" @click.self="closeNote">
    <aside class="drawer">
      <div class="drawer-head">
        <strong>笔记详情</strong>
        <button type="button" class="modal-close" aria-label="关闭" @click="closeNote"><TIcon name="x" /></button>
      </div>
      <div class="drawer-body">
        <img v-if="activeNotePost.cover_url" :src="activeNotePost.cover_url" alt="封面" class="drawer-cover" referrerpolicy="no-referrer" />
        <div v-else class="drawer-cover placeholder"></div>
        <h3 class="drawer-title">{{ activeNotePost.title || '(无标题)' }}</h3>
        <p class="drawer-meta">
          {{ subtypeLabel(activeNotePost.content_subtype) }} · 收藏 {{ activeNotePost.favorite_count }} · 点赞 {{ activeNotePost.like_count }} · {{ bloggerCommentLabel(activeNotePost) }}<template v-if="activeNotePost.published_at"> · {{ formatDate(activeNotePost.published_at) }}</template>
        </p>
        <a v-if="activeNotePost.url" :href="activeNotePost.url" target="_blank" rel="noopener noreferrer" class="drawer-link">打开原帖 <TIcon name="external-link" /></a>

        <div class="drawer-section">
          <h4>{{ activeNotePost.transcript_text ? '口播逐字稿' : '正文' }}</h4>
          <p v-if="noteBodyText(activeNotePost)" class="drawer-text">{{ noteBodyText(activeNotePost) }}</p>
          <p v-else class="empty-region">这篇笔记没有可展示的文字内容。</p>
        </div>

        <div v-if="noteVisual" class="drawer-section">
          <h4>图片解析</h4>
          <p v-if="noteVisual.hook" class="drawer-text"><strong>封面文案：</strong>{{ noteVisual.hook }}</p>
          <p v-if="noteVisual.layout" class="drawer-meta">版式：{{ noteVisual.layout }}</p>
          <p v-if="noteVisual.text" class="drawer-text">{{ noteVisual.text }}</p>
        </div>

        <div v-if="noteHashtags(activeNotePost).length" class="drawer-section">
          <h4>话题标签</h4>
          <div class="tag-chips">
            <span v-for="tag in noteHashtags(activeNotePost)" :key="tag" class="tag-chip tag-chip--auto">#{{ tag }}</span>
          </div>
        </div>

        <div v-if="noteTopComments(activeNotePost).length" class="drawer-section">
          <h4>热门评论 TOP{{ noteTopComments(activeNotePost).length }}</h4>
          <ul class="drawer-comments">
            <li v-for="(c, i) in noteTopComments(activeNotePost)" :key="i">
              <span class="dc-like"><TIcon name="heart" /> {{ c.like_count }}</span>
              <span>{{ c.content }}</span>
            </li>
          </ul>
        </div>
        <div class="drawer-danger">
          <button type="button" class="drawer-del" @click="handleDeleteNote(activeNotePost)">删除这条笔记</button>
        </div>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.drawer-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  justify-content: flex-end;
  background: rgba(20, 24, 28, 0.4);
  animation: fade 180ms var(--ease-out);
}
.drawer {
  width: min(460px, 92vw);
  height: 100%;
  background: var(--color-surface);
  box-shadow: -8px 0 24px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  animation: slide-in 220ms var(--ease-out);
}
@keyframes fade {
  from { opacity: 0; }
}
@keyframes slide-in {
  from { transform: translateX(24px); opacity: 0.6; }
}
@media (prefers-reduced-motion: reduce) {
  .drawer-overlay,
  .drawer {
    animation: none;
  }
}
.drawer-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  border-bottom: 1px solid var(--color-paper-3);
}
.drawer-head strong {
  font-size: 15px;
  font-weight: 650;
}
.modal-close {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 50%;
  background: var(--color-paper-3);
  color: var(--color-ink-2);
  cursor: pointer;
}
.modal-close:hover {
  background: var(--color-rule-strong);
}
.drawer-body {
  padding: 18px;
  overflow-y: auto;
}
.drawer-cover {
  width: 100%;
  max-height: 240px;
  object-fit: cover;
  border-radius: 12px;
  margin-bottom: 12px;
}
.drawer-cover.placeholder {
  height: 140px;
  background: linear-gradient(135deg, var(--color-paper-3), var(--color-accent-soft));
}
.drawer-title {
  margin: 0 0 6px;
  font-size: 16px;
  font-weight: 650;
}
.drawer-meta {
  margin: 0 0 10px;
  font-size: 12px;
  color: var(--color-ink-3);
  font-variant-numeric: tabular-nums;
}
.drawer-link {
  font-size: 13px;
  color: var(--color-accent);
  font-weight: 600;
}
.drawer-section {
  margin-top: 18px;
}
.drawer-section h4 {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 650;
}
.drawer-text {
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.7;
  color: var(--color-ink-2);
}
.drawer-comments {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.drawer-comments li {
  display: flex;
  gap: 8px;
  font-size: 13px;
  line-height: 1.5;
}
.dc-like {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  color: #e0496b;
  font-variant-numeric: tabular-nums;
}
.drawer-danger {
  margin-top: 20px;
  padding-top: 14px;
  border-top: 0.5px solid var(--color-line, #e5e7eb);
}
.drawer-del {
  border: 0;
  background: transparent;
  color: var(--color-danger, #dc2626);
  font-size: 13px;
  font-weight: 550;
  cursor: pointer;
  padding: 4px 0;
}
.drawer-del:hover {
  text-decoration: underline;
}
</style>
