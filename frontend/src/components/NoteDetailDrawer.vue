<script setup lang="ts">
// 单篇笔记详情·居中大弹窗。公共组件:博主资产 / 我的账号 共用。
// 纯展示,状态全在 store —— 由调用方 openNote(post.id) 打开;这里读 activeNotePost 渲染、closeNote 关闭。
// 左侧多图画廊(主图 + 缩略图切换 + 点图放大看原图),右侧正文 / 图片解析 / 标签 / 评论。
import { computed, ref, watch } from 'vue'
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

function isImageUrl(u: unknown): u is string {
  return typeof u === 'string' && u.startsWith('http') && !/(\.mp4|\.m3u8|\.mov)(\?|$)/i.test(u) && !/\/video\//i.test(u)
}

// 图片列表:从 media_urls_json 取所有图片(过滤视频直链);封面若是图片补到最前。视频笔记可能没有静态图。
const images = computed<string[]>(() => {
  const post = activeNotePost.value
  if (!post) return []
  let urls: unknown[] = []
  try {
    urls = JSON.parse(post.media_urls_json || '[]')
  } catch {
    urls = []
  }
  const imgs = urls.filter(isImageUrl)
  if (isImageUrl(post.cover_url) && !imgs.includes(post.cover_url)) imgs.unshift(post.cover_url)
  return imgs
})

const activeImageIndex = ref(0)
const activeImage = computed(() => images.value[activeImageIndex.value] || '')
const lightboxOpen = ref(false)

// 换笔记时重置到第一张、关灯箱。
watch(activeNotePost, () => {
  activeImageIndex.value = 0
  lightboxOpen.value = false
})

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
  const style = (digest.style || '').trim()
  if (!text && !hook && !layout && !style) return null
  return { text, hook, layout, style }
})
</script>

<template>
  <div v-if="activeNotePost" class="nm-overlay" @click.self="closeNote">
    <div class="nm-modal" role="dialog" aria-modal="true" aria-label="笔记详情">
      <div class="nm-head">
        <strong>笔记详情</strong>
        <button type="button" class="modal-close" aria-label="关闭" @click="closeNote"><TIcon name="x" /></button>
      </div>

      <div class="nm-body">
        <!-- 左:多图画廊 -->
        <div class="nm-gallery">
          <button v-if="activeImage" type="button" class="nm-main" :aria-label="`放大第 ${activeImageIndex + 1} 张`" @click="lightboxOpen = true">
            <img :src="activeImage" alt="笔记图片" referrerpolicy="no-referrer" />
            <span v-if="images.length > 1" class="nm-counter">{{ activeImageIndex + 1 }} / {{ images.length }}</span>
            <span class="nm-zoom"><TIcon name="external-link" /> 看原图</span>
          </button>
          <div v-else class="nm-main nm-main--empty">
            <TIcon name="image" />
            <span>{{ activeNotePost.content_type === 'video' ? '视频笔记' : '暂无图片' }}</span>
          </div>
          <div v-if="images.length > 1" class="nm-thumbs">
            <button
              v-for="(img, i) in images"
              :key="i"
              type="button"
              class="nm-thumb"
              :class="{ on: i === activeImageIndex }"
              @click="activeImageIndex = i"
            >
              <img :src="img" alt="" referrerpolicy="no-referrer" />
            </button>
          </div>
        </div>

        <!-- 右:内容(可滚动) -->
        <div class="nm-content">
          <h3 class="nm-title">{{ activeNotePost.title || '(无标题)' }}</h3>
          <p class="nm-meta">
            {{ subtypeLabel(activeNotePost.content_subtype) }} · 收藏 {{ activeNotePost.favorite_count }} · 点赞 {{ activeNotePost.like_count }} · {{ bloggerCommentLabel(activeNotePost) }}<template v-if="activeNotePost.published_at"> · {{ formatDate(activeNotePost.published_at) }}</template>
          </p>
          <a v-if="activeNotePost.url" :href="activeNotePost.url" target="_blank" rel="noopener noreferrer" class="nm-link">打开原帖 <TIcon name="external-link" /></a>

          <div class="nm-section">
            <h4>{{ activeNotePost.transcript_text ? '口播逐字稿' : '正文' }}</h4>
            <p v-if="noteBodyText(activeNotePost)" class="nm-text">{{ noteBodyText(activeNotePost) }}</p>
            <p v-else class="empty-region">这篇笔记没有可展示的文字内容。</p>
          </div>

          <div v-if="noteVisual" class="nm-section nm-visual">
            <h4>图片解析</h4>
            <p v-if="noteVisual.hook" class="nm-text"><strong>封面文案：</strong>{{ noteVisual.hook }}</p>
            <p v-if="noteVisual.layout" class="nm-sub">版式：{{ noteVisual.layout }}</p>
            <p v-if="noteVisual.style" class="nm-sub">视觉风格：{{ noteVisual.style }}</p>
            <p v-if="noteVisual.text" class="nm-text"><strong>图内文字：</strong>{{ noteVisual.text }}</p>
          </div>

          <div v-if="noteHashtags(activeNotePost).length" class="nm-section">
            <h4>话题标签</h4>
            <div class="tag-chips">
              <span v-for="tag in noteHashtags(activeNotePost)" :key="tag" class="tag-chip tag-chip--auto">#{{ tag }}</span>
            </div>
          </div>

          <div v-if="noteTopComments(activeNotePost).length" class="nm-section">
            <h4>热门评论 TOP{{ noteTopComments(activeNotePost).length }}</h4>
            <ul class="nm-comments">
              <li v-for="(c, i) in noteTopComments(activeNotePost)" :key="i">
                <span class="dc-like"><TIcon name="heart" /> {{ c.like_count }}</span>
                <span>{{ c.content }}</span>
              </li>
            </ul>
          </div>
        </div>
      </div>

      <div class="nm-foot">
        <a v-if="activeNotePost.url" :href="activeNotePost.url" target="_blank" rel="noopener noreferrer" class="nm-link">打开原帖 <TIcon name="external-link" /></a>
        <span v-else></span>
        <button type="button" class="nm-del" @click="handleDeleteNote(activeNotePost)">删除这条笔记</button>
      </div>
    </div>

    <!-- 灯箱:点主图放大看原图 -->
    <div v-if="lightboxOpen && activeImage" class="nm-lightbox" @click="lightboxOpen = false">
      <button type="button" class="nm-lightbox-close" aria-label="关闭大图"><TIcon name="x" /></button>
      <img :src="activeImage" alt="原图" referrerpolicy="no-referrer" @click.stop />
    </div>
  </div>
</template>

<style scoped>
.nm-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(20, 24, 28, 0.45);
  animation: nm-fade 160ms var(--ease-out);
}
@keyframes nm-fade {
  from { opacity: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .nm-overlay { animation: none; }
}
.nm-modal {
  width: min(880px, 96vw);
  max-height: 88vh;
  background: var(--color-surface);
  border-radius: 16px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.22);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.nm-head,
.nm-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 18px;
  flex: 0 0 auto;
}
.nm-head { border-bottom: 1px solid var(--color-paper-3); }
.nm-foot { border-top: 1px solid var(--color-paper-3); }
.nm-head strong { font-size: 15px; font-weight: 650; }
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
.modal-close:hover { background: var(--color-rule-strong); }

.nm-body {
  flex: 1;
  min-height: 0;
  display: flex;
  gap: 18px;
  padding: 16px 18px;
  overflow: hidden;
}
/* 左:画廊 */
.nm-gallery {
  flex: 0 0 44%;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}
.nm-main {
  position: relative;
  width: 100%;
  border: 0;
  padding: 0;
  border-radius: 12px;
  overflow: hidden;
  background: var(--color-paper-2, #f3f3f0);
  cursor: zoom-in;
  aspect-ratio: 3 / 4;
}
.nm-main img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}
.nm-main--empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--color-ink-3);
  font-size: 13px;
  cursor: default;
}
.nm-counter {
  position: absolute;
  right: 8px;
  bottom: 8px;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(20, 24, 28, 0.55);
  color: #fff;
}
.nm-zoom {
  position: absolute;
  left: 8px;
  top: 8px;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 12px;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(20, 24, 28, 0.5);
  color: #fff;
  opacity: 0;
  transition: opacity 140ms var(--ease-out);
}
.nm-main:hover .nm-zoom { opacity: 1; }
.nm-thumbs {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 2px;
}
.nm-thumb {
  flex: 0 0 auto;
  width: 46px;
  height: 46px;
  border: 1.5px solid transparent;
  border-radius: 8px;
  padding: 0;
  overflow: hidden;
  cursor: pointer;
  background: var(--color-paper-2, #f3f3f0);
}
.nm-thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
.nm-thumb.on { border-color: var(--color-accent); }

/* 右:内容 */
.nm-content {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
}
.nm-title { margin: 0 0 6px; font-size: 17px; font-weight: 650; line-height: 1.4; }
.nm-meta { margin: 0 0 10px; font-size: 12px; color: var(--color-ink-3); font-variant-numeric: tabular-nums; }
.nm-link { font-size: 13px; color: var(--color-accent); font-weight: 600; }
.nm-section { margin-top: 16px; }
.nm-section h4 { margin: 0 0 8px; font-size: 13px; font-weight: 650; }
.nm-text { white-space: pre-wrap; font-size: 13px; line-height: 1.7; color: var(--color-ink-2); margin: 0 0 4px; }
.nm-sub { margin: 0 0 4px; font-size: 12px; color: var(--color-ink-3); }
.nm-visual {
  background: var(--color-accent-soft);
  border-radius: 10px;
  padding: 10px 12px;
}
.nm-visual h4 { color: var(--color-accent-ink); }
.nm-comments { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 10px; }
.nm-comments li { display: flex; gap: 8px; font-size: 13px; line-height: 1.5; }
.dc-like { flex: 0 0 auto; display: inline-flex; align-items: center; gap: 3px; color: #e0496b; font-variant-numeric: tabular-nums; }
.nm-del { border: 0; background: transparent; color: var(--color-danger, #dc2626); font-size: 13px; font-weight: 550; cursor: pointer; padding: 4px 0; }
.nm-del:hover { text-decoration: underline; }

/* 灯箱 */
.nm-lightbox {
  position: fixed;
  inset: 0;
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.82);
  cursor: zoom-out;
}
.nm-lightbox img { max-width: 96vw; max-height: 92vh; object-fit: contain; border-radius: 4px; }
.nm-lightbox-close {
  position: absolute;
  top: 16px;
  right: 16px;
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  cursor: pointer;
}

/* 移动端:上下堆叠 */
@media (max-width: 720px) {
  .nm-overlay { padding: 0; align-items: stretch; }
  .nm-modal { width: 100%; max-height: 100vh; border-radius: 0; }
  .nm-body { flex-direction: column; overflow-y: auto; }
  .nm-gallery { flex: 0 0 auto; }
  .nm-main { aspect-ratio: 4 / 3; max-height: 44vh; }
  .nm-content { overflow: visible; }
  .nm-foot .nm-link { display: none; }
}
</style>
