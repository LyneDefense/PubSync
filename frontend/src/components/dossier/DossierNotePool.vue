<script setup lang="ts">
// 档案页·笔记池:分类 tab(全部 / 图文 / 口播 / 测评 / 未采详情)+ 每类独立分页(每页 5 条)。
// 最新/最热排序;切分类或排序回到第 1 页。行点击开单篇详情弹窗(公共组件)。
import { computed, ref, watch } from 'vue'
import type { BloggerPost } from '../../api/types'
import { bloggerCommentLabel } from '../../utils/format'
import NoteDetailDrawer from '../NoteDetailDrawer.vue'
import {
  bloggerNoteGroups,
  delistedNoteCount,
  formatDate,
  openNote,
  selectedBloggerId
} from '../../composables/useWorkspaceStore'

const PAGE_SIZE = 5

type NoteSort = 'recent' | 'hot'
const noteSort = ref<NoteSort>('recent')
const activeType = ref<string>('')
const page = ref(0)

function interaction(p: BloggerPost): number {
  return (p.like_count || 0) + (p.favorite_count || 0) + (p.comment_count || 0)
}
function fmt(v: number): string {
  return v >= 10000 ? `${(v / 10000).toFixed(1)}w` : v.toLocaleString()
}
function rowIcon(post: BloggerPost): { ch: string; cls: string } {
  const sub = post.content_subtype || ''
  if (sub.includes('口播') || sub.includes('视频') || (!sub && post.content_type === 'video')) return { ch: '▶', cls: 'np-ico--oral' }
  if (sub.includes('测评') || sub.includes('评测')) return { ch: '⚖', cls: 'np-ico--review' }
  return { ch: '▦', cls: 'np-ico--image' }
}

const groups = computed(() => bloggerNoteGroups.value)
const poolTotal = computed(() => groups.value.reduce((n, g) => n + g.posts.length, 0))

const tabs = computed(() => [
  { key: '', label: `全部 ${poolTotal.value}` },
  ...groups.value.map((g) => ({ key: g.subtype, label: `${g.label} ${g.posts.length}` }))
])

const filtered = computed<BloggerPost[]>(() => {
  const src = activeType.value
    ? groups.value.find((g) => g.subtype === activeType.value)?.posts || []
    : groups.value.flatMap((g) => g.posts)
  return [...src].sort((a, b) =>
    noteSort.value === 'hot'
      ? interaction(b) - interaction(a)
      : (b.published_at || '').localeCompare(a.published_at || '')
  )
})

const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / PAGE_SIZE)))
const clampedPage = computed(() => Math.min(page.value, totalPages.value - 1))
const pagedNotes = computed(() => filtered.value.slice(clampedPage.value * PAGE_SIZE, (clampedPage.value + 1) * PAGE_SIZE))

// 切分类 / 排序 / 博主 → 回到第 1 页;切博主还要重置到「全部」。
watch([activeType, noteSort], () => { page.value = 0 })
watch(selectedBloggerId, () => { activeType.value = ''; page.value = 0 })

function prev() { if (clampedPage.value > 0) page.value = clampedPage.value - 1 }
function next() { if (clampedPage.value < totalPages.value - 1) page.value = clampedPage.value + 1 }
</script>

<template>
  <section class="np">
    <div class="np__head">
      <h3>笔记池</h3>
      <span class="np__count">共 {{ poolTotal }} 条<template v-if="delistedNoteCount"> · {{ delistedNoteCount }} 已下架</template></span>
      <div class="np__seg">
        <button type="button" :class="{ on: noteSort === 'recent' }" @click="noteSort = 'recent'">最新</button>
        <button type="button" :class="{ on: noteSort === 'hot' }" @click="noteSort = 'hot'">最热</button>
      </div>
    </div>

    <div v-if="poolTotal" class="np__tabs">
      <button
        v-for="t in tabs"
        :key="t.key || '__all__'"
        type="button"
        :class="{ on: activeType === t.key }"
        @click="activeType = t.key"
      >{{ t.label }}</button>
    </div>

    <div v-if="pagedNotes.length" class="np__rows">
      <button v-for="post in pagedNotes" :key="post.id" type="button" class="np__row" @click="openNote(post.id)">
        <span class="np__ico" :class="rowIcon(post).cls">{{ rowIcon(post).ch }}</span>
        <span class="np__main">
          <span class="np__title-row">
            <span class="np__title">{{ post.title || '(无标题)' }}</span>
            <span v-if="post.detail_level === 'list'" class="np__pill">列表级</span>
            <span v-if="post.status === 'delisted'" class="np__pill np__pill--del">已下架</span>
          </span>
          <span class="np__meta">收藏 {{ fmt(post.favorite_count) }} · 点赞 {{ fmt(post.like_count) }} · {{ bloggerCommentLabel(post) }}<template v-if="post.published_at"> · {{ formatDate(post.published_at) }}</template></span>
        </span>
        <span class="np__chevron">›</span>
      </button>
    </div>
    <p v-else class="np__empty">笔记池为空。用身份卡的「采集笔记 →」或去「数据采集」拉取。</p>

    <div v-if="filtered.length" class="np__pager">
      <span class="np__pager-total">共 {{ filtered.length }} 篇</span>
      <div class="np__pager-nav">
        <button type="button" class="np__pager-btn" :disabled="clampedPage <= 0" @click="prev">‹</button>
        <span class="np__pager-label">{{ clampedPage + 1 }} / {{ totalPages }}</span>
        <button type="button" class="np__pager-btn" :disabled="clampedPage >= totalPages - 1" @click="next">›</button>
      </div>
    </div>

    <NoteDetailDrawer />
  </section>
</template>

<style scoped>
.np { background: var(--color-surface); border: 1px solid var(--color-rule); border-radius: 14px; padding: 20px 22px; }
.np__head { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.np__head h3 { margin: 0; font-size: 15px; font-weight: 650; }
.np__count { font-size: 12px; color: var(--color-ink-3); }
.np__seg { margin-left: auto; display: inline-flex; gap: 2px; padding: 3px; background: var(--color-paper-3); border-radius: 8px; }
.np__seg button {
  height: 26px;
  padding: 0 12px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--color-ink-2);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 120ms var(--ease-out);
}
.np__seg button.on { background: var(--color-surface); color: var(--color-accent-ink); box-shadow: 0 1px 2px var(--color-shadow); }

.np__tabs { display: flex; gap: 7px; flex-wrap: wrap; margin-bottom: 6px; }
.np__tabs button {
  height: 28px;
  padding: 0 12px;
  border: 1px solid var(--color-rule);
  border-radius: 8px;
  background: var(--color-surface);
  color: var(--color-ink-2);
  font-size: 12px;
  font-weight: 550;
  cursor: pointer;
  white-space: nowrap;
  transition: background 140ms var(--ease-out), border-color 140ms var(--ease-out), color 140ms var(--ease-out);
}
.np__tabs button.on { border-color: var(--color-accent-soft-bd); background: var(--color-accent-soft); color: var(--color-accent-ink); }

.np__rows { display: flex; flex-direction: column; }
.np__row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 10px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: background 120ms var(--ease-out);
}
.np__row:hover { background: var(--color-paper); }
.np__ico { display: grid; place-items: center; width: 26px; height: 26px; border-radius: 8px; font-size: 12px; flex: 0 0 auto; }
.np__ico--oral { background: #fdeee9; color: #bd5b34; }
.np__ico--image { background: var(--color-accent-soft); color: #2f6b54; }
.np__ico--review { background: #eef1f6; color: #44506a; }
.np__main { flex: 1; min-width: 0; }
.np__title-row { display: flex; align-items: center; gap: 8px; }
.np__title { font-size: 13.5px; color: var(--color-ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.np__pill { flex: 0 0 auto; font-size: 10px; padding: 1px 7px; border-radius: 999px; background: var(--color-paper-3); color: var(--color-ink-3); }
.np__pill--del { background: #fbeae8; color: var(--color-danger); }
.np__meta { display: block; margin-top: 3px; font-size: 12px; color: var(--color-ink-3); font-variant-numeric: tabular-nums; }
.np__chevron { flex: 0 0 auto; color: var(--color-rule-strong); font-size: 18px; }
.np__empty { margin: 8px 0; padding: 24px 0; text-align: center; font-size: 12.5px; color: var(--color-ink-3); }

.np__pager { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--color-paper-3); }
.np__pager-total { font-size: 12px; color: var(--color-ink-3); }
.np__pager-nav { display: flex; align-items: center; gap: 8px; }
.np__pager-btn {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border: 1px solid var(--color-rule);
  border-radius: 8px;
  background: var(--color-surface);
  color: var(--color-ink-2);
  font-size: 15px;
  line-height: 1;
  cursor: pointer;
  transition: background 140ms var(--ease-out);
}
.np__pager-btn:hover:not(:disabled) { background: var(--color-paper); }
.np__pager-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.np__pager-label { font-size: 12.5px; color: var(--color-ink-2); font-variant-numeric: tabular-nums; min-width: 46px; text-align: center; }
</style>
