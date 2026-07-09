<script setup lang="ts">
// 社媒·发布草稿:已保存发布包的查看、复制与发布状态管理(主从工作台)。
// 纯展示重构:store 状态/方法全部沿用;仅新增本地的搜索/状态筛选 UI 态。
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import HashtagCloud from '../components/HashtagCloud.vue'
import ImagePlanList from '../components/ImagePlanList.vue'
import PublishPackageExporter from '../components/PublishPackageExporter.vue'
import { parseJsonObject, xhsContentTypeLabel, xhsPackageCopyText } from '../utils/format'
import {
  copyText,
  currentSocialPlatformName,
  currentSocialTab,
  formatDate,
  handleMarkPublished,
  isSocialPlatform,
  selectedXhsPackage,
  selectedXhsPackageBloggerName,
  selectedXhsPackageId,
  visibleXhsPackages,
  xhsPackageHashtags,
  xhsPackageImagePlan,
  xhsPackageScriptSegments
} from '../composables/useWorkspaceStore'

// 嵌入 /drafts(对象驱动新架构):守卫放行 + 页头换面包屑。
const props = defineProps<{ embedded?: boolean }>()
const router = useRouter()

// 本地筛选态(纯 UI,不入 store)。
const keyword = ref('')
const statusFilter = ref<'all' | 'draft' | 'published'>('all')

const publishedCount = computed(() => visibleXhsPackages.value.filter((p) => p.published_at).length)

const filteredPackages = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return visibleXhsPackages.value.filter((p) => {
    if (statusFilter.value === 'draft' && p.published_at) return false
    if (statusFilter.value === 'published' && !p.published_at) return false
    if (kw && !`${p.title || ''} ${p.topic || ''}`.toLowerCase().includes(kw)) return false
    return true
  })
})

// 内容类型 → 图标种类(视频/口播=播放方块,其余=图文)。
function typeKind(ct: string): 'video' | 'image' {
  return /video|spoken|script/.test(ct || '') ? 'video' : 'image'
}
</script>

<template>
  <section v-if="embedded || (isSocialPlatform && currentSocialTab === 'history')" class="history" :class="{ 'is-embedded': embedded }">
    <header v-if="!embedded" class="page-head">
      <div class="ph-l">
        <h1>{{ currentSocialPlatformName }}发布草稿</h1>
        <p>查看、复制、管理 AI 创作生成的发布包 —— 这里只浏览成品，不进入生成流程。</p>
      </div>
      <div class="ph-stats">
        <span class="stat"><b>{{ visibleXhsPackages.length }}</b><small>发布包</small></span>
        <span class="stat"><b>{{ publishedCount }}</b><small>已发布</small></span>
      </div>
    </header>
    <div v-else class="dr-top">
      <button type="button" class="dr-crumb" @click="router.push({ name: 'home' })">← 首页 / 发布草稿</button>
      <div class="ph-stats">
        <span class="stat"><b>{{ visibleXhsPackages.length }}</b><small>发布包</small></span>
        <span class="stat"><b>{{ publishedCount }}</b><small>已发布</small></span>
      </div>
    </div>

    <div class="md-grid">
      <!-- 左:列表 -->
      <aside class="list-card" aria-label="发布包记录">
        <div class="list-filters">
          <div class="search-box">
            <svg class="s-ico" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></svg>
            <input v-model="keyword" type="search" placeholder="搜索标题 / 主题…" />
          </div>
          <div class="seg">
            <button type="button" :class="{ on: statusFilter === 'all' }" @click="statusFilter = 'all'">全部</button>
            <button type="button" :class="{ on: statusFilter === 'draft' }" @click="statusFilter = 'draft'">草稿</button>
            <button type="button" :class="{ on: statusFilter === 'published' }" @click="statusFilter = 'published'">已发布</button>
          </div>
        </div>
        <div class="list-scroll">
          <button
            v-for="pack in filteredPackages"
            :key="pack.id"
            type="button"
            class="row"
            :class="{ sel: selectedXhsPackage?.id === pack.id }"
            @click="selectedXhsPackageId = pack.id"
          >
            <span class="row-ico" :class="`ty--${typeKind(pack.content_type)}`" aria-hidden="true">
              <svg v-if="typeKind(pack.content_type) === 'video'" viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
              <svg v-else viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="8.5" cy="9" r="1.5" /><path d="M21 16l-5-5L5 20" /></svg>
            </span>
            <span class="row-body">
              <span class="row-title">{{ pack.title || pack.topic }}</span>
              <span class="row-sub">{{ xhsContentTypeLabel(pack.content_type) }} · {{ formatDate(pack.created_at) }}</span>
            </span>
            <span class="row-dot" :class="{ pub: pack.published_at }" :title="pack.published_at ? '已发布' : '草稿'"></span>
          </button>
          <p v-if="!visibleXhsPackages.length" class="empty-region pad">还没有发布包。到「AI 创作」生成后会出现在这里。</p>
          <p v-else-if="!filteredPackages.length" class="empty-region pad">没有匹配的发布包，换个搜索词或筛选试试。</p>
        </div>
      </aside>

      <!-- 右:详情 -->
      <div v-if="selectedXhsPackage" class="detail">
        <!-- 头部 -->
        <section class="card head">
          <div class="head-tags">
            <span class="type-badge">{{ xhsContentTypeLabel(selectedXhsPackage.content_type) }}</span>
            <span class="status-badge" :class="selectedXhsPackage.published_at ? 'pub' : 'draft'">{{ selectedXhsPackage.published_at ? '已发布' : '草稿' }}</span>
          </div>
          <h2 class="head-title">{{ selectedXhsPackage.title }}</h2>
          <p class="head-meta">{{ selectedXhsPackageBloggerName }} · 生成于 {{ formatDate(selectedXhsPackage.created_at) }}</p>
          <div class="head-actions">
            <PublishPackageExporter :pkg="selectedXhsPackage" :blogger-name="selectedXhsPackageBloggerName" />
            <button type="button" class="btn btn--ghost" @click="copyText(xhsPackageCopyText(selectedXhsPackage), '发布文案')">复制发布文案</button>
            <button
              v-if="!selectedXhsPackage.published_at"
              type="button"
              class="btn btn--accent"
              @click="handleMarkPublished(selectedXhsPackage, true)"
            >我已发布</button>
            <button v-else type="button" class="btn btn--ghost" @click="handleMarkPublished(selectedXhsPackage, false)">已发布 ✓ · 点此撤销</button>
          </div>
          <p v-if="!selectedXhsPackage.published_at" class="head-hint">复制内容去{{ currentSocialPlatformName }}发布后，回来点「我已发布」，把这篇标记为已发布。</p>
        </section>

        <!-- 快照三栏 -->
        <section class="card snapshot">
          <article class="snap"><span>主题</span><strong>{{ selectedXhsPackage.topic || '暂无' }}</strong></article>
          <article class="snap"><span>封面文案</span><strong>{{ selectedXhsPackage.cover_text || '暂无' }}</strong></article>
          <article class="snap"><span>配图方案</span><strong>{{ xhsPackageImagePlan.length }} 张</strong></article>
        </section>

        <!-- 正文 -->
        <section class="card copy-block">
          <div class="cb-head"><h3>正文</h3><button type="button" class="btn btn--ghost slim" @click="copyText(selectedXhsPackage.body_text, '正文')">复制正文</button></div>
          <pre>{{ selectedXhsPackage.body_text }}</pre>
        </section>

        <!-- 话题标签 -->
        <section v-if="xhsPackageHashtags.length" class="card">
          <div class="cb-head plain"><h3>话题标签</h3><span class="cb-note">点击复制单个</span></div>
          <HashtagCloud :tags="xhsPackageHashtags" @copy="copyText($event, '标签')" />
        </section>

        <!-- 配图方案 -->
        <section v-if="xhsPackageImagePlan.length" class="card">
          <div class="cb-head plain"><h3>配图方案</h3><span class="cb-note">{{ xhsPackageImagePlan.length }} 张</span></div>
          <ImagePlanList :plan="xhsPackageImagePlan" />
          <p v-if="selectedXhsPackage.error_message" class="run-error">{{ selectedXhsPackage.error_message }}</p>
        </section>

        <!-- 脚本分段(视频/口播类) -->
        <section v-if="xhsPackageScriptSegments.length" class="card">
          <div class="cb-head"><h3>脚本分段</h3><button type="button" class="btn btn--ghost slim" @click="copyText(JSON.stringify(parseJsonObject(selectedXhsPackage.script_json), null, 2), '脚本')">复制脚本</button></div>
          <div class="segments">
            <article v-for="(segment, index) in xhsPackageScriptSegments" :key="index" class="segment">
              <span class="seg-time">{{ segment.start || `${index * 10}s` }} - {{ segment.end || `${(index + 1) * 10}s` }}</span>
              <strong>{{ segment.voiceover || segment.subtitle || '脚本片段' }}</strong>
              <span v-if="segment.scene" class="seg-scene">{{ segment.scene }}</span>
            </article>
          </div>
        </section>
      </div>
      <div v-else class="empty-region card pad detail-empty">
        {{ visibleXhsPackages.length ? '选择一条发布包记录后，这里会展示可复制的内容。' : '还没有发布包。到「AI 创作」生成后会出现在这里。' }}
      </div>
    </div>
  </section>
</template>

<style scoped>
.history {
  max-width: 1080px;
  margin: 0 auto;
}
/* 嵌入 /drafts 时:宽度交给对象页容器;页头换成面包屑 + 统计。 */
.history.is-embedded { max-width: none; margin: 0; }
.dr-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.dr-crumb { border: 0; background: none; cursor: pointer; font-size: 12.5px; color: var(--color-ink-3); padding: 0; }
.dr-crumb:hover { color: var(--color-accent-ink); }
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 18px;
}
.ph-l h1 {
  margin: 0 0 6px;
  font-size: 21px;
  font-weight: 680;
  letter-spacing: -0.01em;
}
.ph-l p {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--color-ink-2);
}
.ph-stats {
  display: flex;
  gap: 22px;
  flex: 0 0 auto;
}
.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.stat b {
  font-size: 26px;
  font-weight: 720;
  line-height: 1;
  color: var(--color-ink);
  font-variant-numeric: tabular-nums;
}
.stat small {
  margin-top: 4px;
  font-size: 11.5px;
  color: var(--color-ink-3);
}

.md-grid {
  display: grid;
  grid-template-columns: 312px minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
}

/* 左:列表 */
.list-card {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 120px);
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.list-filters {
  padding: 14px 14px 10px;
  border-bottom: 1px solid var(--color-paper-3);
}
.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 38px;
  padding: 0 12px;
  border: 1px solid var(--color-field-border);
  border-radius: 10px;
  background: var(--color-field);
  margin-bottom: 10px;
}
.search-box:focus-within {
  border-color: var(--color-accent);
}
.s-ico {
  flex: 0 0 auto;
  color: var(--color-ink-3);
}
.search-box input {
  flex: 1;
  min-width: 0;
  border: 0;
  background: transparent;
  font-size: 13.5px;
  color: var(--color-ink);
  outline: none;
}
.search-box input:focus {
  box-shadow: none;
}
.seg {
  display: flex;
  gap: 3px;
  padding: 3px;
  background: var(--color-paper-3);
  border-radius: 9px;
}
.seg button {
  flex: 1;
  height: 28px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--color-ink-2);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  transition: background 120ms var(--ease-out);
}
.seg button.on {
  background: var(--color-surface);
  color: var(--color-ink);
  box-shadow: 0 1px 2px var(--color-shadow);
}
.list-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.row {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 9px 10px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: background 120ms var(--ease-out);
}
.row:hover {
  background: #fafbfc;
}
.row.sel {
  background: var(--color-accent-soft);
}
.row-ico {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 9px;
  flex: 0 0 auto;
}
.ty--image {
  background: var(--color-accent-soft);
  color: var(--color-accent);
}
.ty--video {
  background: #f0eef7;
  color: #5a4a86;
}
.row-body {
  flex: 1;
  min-width: 0;
}
.row-title {
  display: block;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--color-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.row.sel .row-title {
  color: var(--color-accent-ink);
}
.row-sub {
  display: block;
  margin-top: 2px;
  font-size: 11.5px;
  color: var(--color-ink-3);
  font-variant-numeric: tabular-nums;
}
.row-dot {
  flex: 0 0 auto;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-rule-strong);
}
.row-dot.pub {
  background: var(--color-accent);
}

/* 右:详情 */
.detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.detail-empty {
  text-align: center;
  padding: 56px 24px;
}

.head {
  padding: 20px 22px;
}
.head-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.type-badge {
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
  font-size: 12px;
  font-weight: 650;
}
.status-badge {
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  font-weight: 650;
}
.status-badge.pub {
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
}
.status-badge.draft {
  background: var(--color-paper-3);
  color: var(--color-ink-3);
}
.head-title {
  margin: 0 0 6px;
  font-size: 19px;
  font-weight: 680;
  line-height: 1.4;
}
.head-meta {
  margin: 0 0 14px;
  font-size: 12.5px;
  color: var(--color-ink-3);
  font-variant-numeric: tabular-nums;
}
.head-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.head-hint {
  margin: 14px 0 0;
  padding: 10px 13px;
  border: 1px solid var(--color-accent-soft-bd);
  border-radius: 10px;
  background: var(--color-accent-tint);
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--color-accent-ink);
}

/* 按钮 */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 38px;
  padding: 0 16px;
  border-radius: 10px;
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: background 140ms var(--ease-out), border-color 140ms var(--ease-out);
}
.btn--accent {
  border: 0;
  background: var(--color-accent);
  color: #fff;
}
.btn--accent:hover {
  background: var(--color-accent-press);
}
.btn--ghost {
  border: 1px solid var(--color-field-border);
  background: var(--color-surface);
  color: var(--color-ink-2);
}
.btn--ghost:hover {
  background: #f7f8f9;
}
.btn.slim {
  height: 30px;
  padding: 0 12px;
  font-size: 12.5px;
  border-radius: 8px;
}

/* 快照三栏 */
.snapshot {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1px;
  background: var(--color-rule);
  overflow: hidden;
  padding: 0;
}
.snap {
  background: var(--color-surface);
  padding: 14px 16px;
}
.snap span {
  display: block;
  font-size: 11.5px;
  color: var(--color-ink-3);
  margin-bottom: 5px;
}
.snap strong {
  font-size: 13.5px;
  font-weight: 620;
  color: var(--color-ink);
  line-height: 1.5;
}

/* 卡头(正文/脚本带复制) */
.cb-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--color-paper-3);
}
.cb-head.plain {
  border-bottom: 0;
  padding-bottom: 4px;
}
.cb-head h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 650;
}
.cb-note {
  font-size: 12px;
  color: var(--color-ink-3);
}
.copy-block pre {
  margin: 0;
  padding: 14px 16px;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.75;
  color: var(--color-ink-2);
  font-family: inherit;
}
.card > :deep(.tag-cloud) {
  padding: 0 16px 16px;
}
.card > :deep(.image-output-grid) {
  padding: 0 16px 16px;
}

.run-error {
  margin: 0 16px 14px;
  font-size: 12.5px;
  color: var(--color-danger);
}

/* 脚本分段 */
.segments {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px;
}
.segment {
  display: grid;
  gap: 2px;
  padding-left: 12px;
  border-left: 2px solid var(--color-accent-soft-bd);
}
.seg-time {
  font-size: 11.5px;
  color: var(--color-ink-3);
  font-variant-numeric: tabular-nums;
}
.segment strong {
  font-size: 13px;
  color: var(--color-ink);
}
.seg-scene {
  font-size: 12.5px;
  color: var(--color-ink-3);
}

.empty-region.pad {
  padding: 26px 18px;
  text-align: center;
}

@media (max-width: 900px) {
  .md-grid {
    grid-template-columns: 1fr;
  }
  .list-card {
    position: static;
    max-height: none;
  }
  .list-scroll {
    max-height: 360px;
  }
}
@media (max-width: 560px) {
  .snapshot {
    grid-template-columns: 1fr;
  }
}
</style>
