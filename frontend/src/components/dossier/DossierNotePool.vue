<script setup lang="ts">
// 档案页·笔记池:两级分类 —— 一级 已采详情 / 未采详情,二级都按 content_type 分 图文 / 视频,每类独立分页(每页 5)。
//   视频不再拆口播/非口播(模态就一个);具体拍法(口播浓度/出镜/镜头/风格)在单篇详情的「视频拍法」里看。
// 最新/最热排序;切分类或排序回第 1 页。行点击开单篇详情弹窗(公共组件)。
import { computed, ref, watch } from 'vue'
import type { BloggerPost } from '../../api/types'
import { bloggerCommentLabel } from '../../utils/format'
import NoteDetailDrawer from '../NoteDetailDrawer.vue'
import {
  activeNotePool,
  delistedNoteCount,
  formatDate,
  openNote,
  selectedBloggerId
} from '../../composables/useWorkspaceStore'

const PAGE_SIZE = 5

type NoteSort = 'recent' | 'hot'
const noteSort = ref<NoteSort>('recent')
const primary = ref<'' | 'full' | 'list'>('') // 一级:全部 / 已采详情 / 未采详情
const secondary = ref<string>('') // 二级:模态(full)或 content_type(list)
const page = ref(0)

function interaction(p: BloggerPost): number {
  return (p.like_count || 0) + (p.favorite_count || 0) + (p.comment_count || 0)
}
function fmt(v: number): string {
  return v >= 10000 ? `${(v / 10000).toFixed(1)}w` : v.toLocaleString()
}
function isVideo(post: BloggerPost): boolean {
  return post.content_type === 'video'
}
function rowIcon(post: BloggerPost): { ch: string; cls: string } {
  return isVideo(post) ? { ch: '▶', cls: 'np-ico--oral' } : { ch: '▦', cls: 'np-ico--image' }
}

const allPosts = computed(() => activeNotePool.value)
const fullPosts = computed(() => allPosts.value.filter((p) => p.detail_level === 'full'))
const listPosts = computed(() => allPosts.value.filter((p) => p.detail_level !== 'full'))

// 一级 tab(含计数)。
const primaryTabs = computed(() => [
  { key: '' as const, label: `全部 ${allPosts.value.length}` },
  { key: 'full' as const, label: `已采详情 ${fullPosts.value.length}` },
  { key: 'list' as const, label: `未采详情 ${listPosts.value.length}` }
])

// 二级都按 content_type 分 图文 / 视频(视频不再拆口播/非口播——模态就一个,具体看笔记详情的拍法标签)。
function contentTypeGroups(posts: BloggerPost[]) {
  return [
    { key: 'image', label: '图文', count: posts.filter((p) => p.content_type !== 'video').length },
    { key: 'video', label: '视频', count: posts.filter((p) => p.content_type === 'video').length }
  ].filter((g) => g.count > 0)
}
const detailSubGroups = computed(() => contentTypeGroups(fullPosts.value))
const listSubGroups = computed(() => contentTypeGroups(listPosts.value))

const secondaryTabs = computed(() => {
  if (primary.value === 'full') return [{ key: '', label: `全部 ${fullPosts.value.length}` }, ...detailSubGroups.value.map((g) => ({ key: g.key, label: `${g.label} ${g.count}` }))]
  if (primary.value === 'list') return [{ key: '', label: `全部 ${listPosts.value.length}` }, ...listSubGroups.value.map((g) => ({ key: g.key, label: `${g.label} ${g.count}` }))]
  return []
})

const filtered = computed<BloggerPost[]>(() => {
  let src: BloggerPost[]
  if (primary.value === 'full') {
    src = secondary.value ? fullPosts.value.filter((p) => (secondary.value === 'video' ? p.content_type === 'video' : p.content_type !== 'video')) : fullPosts.value
  } else if (primary.value === 'list') {
    src = secondary.value ? listPosts.value.filter((p) => (secondary.value === 'video' ? p.content_type === 'video' : p.content_type !== 'video')) : listPosts.value
  } else {
    src = allPosts.value
  }
  return [...src].sort((a, b) =>
    noteSort.value === 'hot'
      ? interaction(b) - interaction(a)
      : (b.published_at || '').localeCompare(a.published_at || '')
  )
})

const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / PAGE_SIZE)))
const clampedPage = computed(() => Math.min(page.value, totalPages.value - 1))
const pagedNotes = computed(() => filtered.value.slice(clampedPage.value * PAGE_SIZE, (clampedPage.value + 1) * PAGE_SIZE))

// 切一级 → 二级归全部;切任意分类 / 排序 → 回第 1 页;切博主 → 全部重置。
watch(primary, () => { secondary.value = ''; page.value = 0 })
watch([secondary, noteSort], () => { page.value = 0 })
watch(selectedBloggerId, () => { primary.value = ''; secondary.value = ''; page.value = 0 })

function prev() { if (clampedPage.value > 0) page.value = clampedPage.value - 1 }
function next() { if (clampedPage.value < totalPages.value - 1) page.value = clampedPage.value + 1 }
</script>

<template>
  <section class="np">
    <div class="np__head">
      <h3>笔记池</h3>
      <span class="np__count">共 {{ allPosts.length }} 条<template v-if="delistedNoteCount"> · {{ delistedNoteCount }} 已下架</template></span>
      <div class="np__seg">
        <button type="button" :class="{ on: noteSort === 'recent' }" @click="noteSort = 'recent'">最新</button>
        <button type="button" :class="{ on: noteSort === 'hot' }" @click="noteSort = 'hot'">最热</button>
      </div>
    </div>

    <template v-if="allPosts.length">
      <div class="np__tabs">
        <button
          v-for="t in primaryTabs"
          :key="t.key || '__all__'"
          type="button"
          :class="{ on: primary === t.key }"
          @click="primary = t.key"
        >{{ t.label }}</button>
      </div>
      <div v-if="secondaryTabs.length" class="np__subtabs">
        <button
          v-for="t in secondaryTabs"
          :key="t.key || '__sub_all__'"
          type="button"
          :class="{ on: secondary === t.key }"
          @click="secondary = t.key"
        >{{ t.label }}</button>
      </div>
    </template>

    <div v-if="pagedNotes.length" class="np__rows">
      <button v-for="post in pagedNotes" :key="post.id" type="button" class="np__row" @click="openNote(post.id)">
        <span class="np__ico" :class="rowIcon(post).cls">{{ rowIcon(post).ch }}</span>
        <span class="np__main">
          <span class="np__title-row">
            <span class="np__title">{{ post.title || '(无标题)' }}</span>
            <span v-if="post.detail_level !== 'full'" class="np__pill">列表级</span>
          </span>
          <span class="np__meta">收藏 {{ fmt(post.favorite_count) }} · 点赞 {{ fmt(post.like_count) }} · {{ bloggerCommentLabel(post) }}<template v-if="post.published_at"> · {{ formatDate(post.published_at) }}</template></span>
        </span>
        <span class="np__chevron">›</span>
      </button>
    </div>
    <p v-else class="np__empty">这个分类下暂无笔记。用身份卡的「采集笔记 →」或去「数据采集」拉取。</p>

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

.np__tabs { display: flex; gap: 7px; flex-wrap: wrap; margin-bottom: 8px; }
.np__tabs button {
  height: 28px;
  padding: 0 13px;
  border: 1px solid var(--color-rule);
  border-radius: 8px;
  background: var(--color-surface);
  color: var(--color-ink-2);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: background 140ms var(--ease-out), border-color 140ms var(--ease-out), color 140ms var(--ease-out);
}
.np__tabs button.on { border-color: var(--color-accent-soft-bd); background: var(--color-accent-soft); color: var(--color-accent-ink); }

/* 二级(模态)tab:淡底容器 + 左缩进,读作「一级下的细分」。 */
.np__subtabs {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin: 0 0 6px 14px;
  padding: 6px 8px;
  background: var(--color-paper);
  border-radius: 10px;
}
.np__subtabs button {
  height: 25px;
  padding: 0 11px;
  border: 1px solid transparent;
  border-radius: 7px;
  background: transparent;
  color: var(--color-ink-3);
  font-size: 12px;
  font-weight: 550;
  cursor: pointer;
  white-space: nowrap;
  transition: background 140ms var(--ease-out), color 140ms var(--ease-out);
}
.np__subtabs button:hover { color: var(--color-ink-2); }
.np__subtabs button.on { background: var(--color-surface); border-color: var(--color-accent-soft-bd); color: var(--color-accent-ink); box-shadow: 0 1px 2px var(--color-shadow); }

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
.np__main { flex: 1; min-width: 0; }
.np__title-row { display: flex; align-items: center; gap: 8px; }
.np__title { font-size: 13.5px; color: var(--color-ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.np__pill { flex: 0 0 auto; font-size: 10px; padding: 1px 7px; border-radius: 999px; background: var(--color-paper-3); color: var(--color-ink-3); }
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
