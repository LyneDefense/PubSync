<script setup lang="ts">
// 首页 Hub(对象驱动):接下来提示 + 两栏。
// 左栏「对标博主」= 可搜索/排序/平台筛选、收藏置顶的密列表(抗规模,取代卡片墙);每行带真实信号
// (粉丝/采集量/画像状态/草稿数,均来自 store 现有字段,不编造)。右栏 = 我的账号 + 最近草稿 + 公众号早报。
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { BloggerProfile } from '../api/types'
import { xhsContentTypeLabel } from '../utils/format'
import {
  bloggers,
  friendlyTime,
  handleToggleBloggerFavorite,
  myAccounts,
  visibleXhsPackages,
} from '../composables/useWorkspaceStore'

const router = useRouter()

const benchmarks = computed(() => bloggers.value.filter((b) => b.account_type !== 'mine'))
const distilledCount = computed(() => benchmarks.value.filter((b) => b.last_distilled_at).length)
const draftCount = computed(() => visibleXhsPackages.value.length)
const accountCount = computed(() => myAccounts.value.length)

// 接下来:按当前状态给一句提示 + 一个主行动。
const nextStep = computed(() => {
  if (!benchmarks.value.length) return { text: '先加一个想学的对标博主,开始你的第一次创作。', cta: '加对标博主', act: () => router.push({ name: 'find' }) }
  if (distilledCount.value === 0) return { text: '已有对标博主,给它建档蒸馏出创作画像。', cta: '去建档', act: () => openBlogger(benchmarks.value[0], 'dossier') }
  const parts = [`${distilledCount.value} 个博主已出画像`]
  if (draftCount.value) parts.push(`${draftCount.value} 篇草稿`)
  return { text: parts.join(' · '), cta: '开始创作', act: () => router.push({ name: 'create' }) }
})

// —— 列表:搜索 + 平台筛选 + 排序;收藏置顶(抗规模的关键) —— //
const query = ref('')
const platformFilter = ref<'all' | 'xhs' | 'douyin'>('all')
const sortBy = ref<'recent' | 'follower' | 'sample'>('recent')

const showPlatformFilter = computed(() => new Set(benchmarks.value.map((b) => b.platform)).size > 1)

const draftsByBlogger = computed(() => {
  const map: Record<number, number> = {}
  for (const p of visibleXhsPackages.value) map[p.blogger_id] = (map[p.blogger_id] || 0) + 1
  return map
})

const filteredBloggers = computed(() => {
  const q = query.value.trim().toLowerCase()
  const list = benchmarks.value.filter((b) => {
    if (platformFilter.value !== 'all' && b.platform !== platformFilter.value) return false
    if (!q) return true
    return (b.display_name || '').toLowerCase().includes(q) || (b.niche || '').toLowerCase().includes(q)
  })
  const key = sortBy.value
  return [...list].sort((a, b) => {
    if (a.is_favorite !== b.is_favorite) return a.is_favorite ? -1 : 1 // 收藏置顶
    if (key === 'follower') return (b.follower_count || 0) - (a.follower_count || 0)
    if (key === 'sample') return (b.sample_count || 0) - (a.sample_count || 0)
    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  })
})

const recentDrafts = computed(() =>
  [...visibleXhsPackages.value]
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 4),
)

function bloggerName(id: number) {
  return bloggers.value.find((b) => b.id === id)?.display_name || '未知博主'
}
function fmtNum(n: number) {
  if (!n) return '0'
  if (n >= 10000) return `${(n / 10000).toFixed(n % 10000 === 0 ? 0 : 1)}万`
  return String(n)
}
function openBlogger(b: BloggerProfile, view: 'dossier' | 'analysis') {
  router.push({ name: 'blogger', params: { id: b.id }, query: { view } })
}
function createWith(b: BloggerProfile) {
  router.push({ name: 'create', query: { blogger: b.id } })
}
function openAccount(id: number) {
  router.push({ name: 'account', params: { id } })
}
function platMeta(p: string) {
  return p === 'douyin' ? { name: '抖音', dot: '#1c2024' } : { name: '小红书', dot: '#e24b4a' }
}
</script>

<template>
  <section class="home">
    <!-- 接下来 -->
    <div class="hero">
      <span class="hero-ico" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
      </span>
      <div class="hero-txt">
        <strong>接下来</strong>
        <p>{{ nextStep.text }}</p>
      </div>
      <button type="button" class="hero-cta" @click="nextStep.act()">{{ nextStep.cta }}</button>
    </div>

    <div class="grid">
      <!-- 对标博主(主) -->
      <div class="main">
        <div class="main-head">
          <h2 class="mh-title">对标博主<span class="mh-count">{{ benchmarks.length }}</span></h2>
          <div class="mh-tools">
            <label class="search">
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4-4" /></svg>
              <input v-model="query" type="search" placeholder="搜索名称 / 领域" aria-label="搜索对标博主" />
            </label>
            <select v-model="sortBy" class="sort" aria-label="排序">
              <option value="recent">最近活动</option>
              <option value="follower">粉丝多</option>
              <option value="sample">采集多</option>
            </select>
            <button type="button" class="add-btn" @click="router.push({ name: 'find' })">
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
              加对标博主
            </button>
          </div>
        </div>

        <div v-if="showPlatformFilter" class="chips">
          <button type="button" :class="{ on: platformFilter === 'all' }" @click="platformFilter = 'all'">全部</button>
          <button type="button" :class="{ on: platformFilter === 'xhs' }" @click="platformFilter = 'xhs'">小红书</button>
          <button type="button" :class="{ on: platformFilter === 'douyin' }" @click="platformFilter = 'douyin'">抖音</button>
        </div>

        <div v-if="filteredBloggers.length" class="blist">
          <article v-for="b in filteredBloggers" :key="b.id" class="brow">
            <button type="button" class="fav" :class="{ on: b.is_favorite }" :title="b.is_favorite ? '取消收藏' : '收藏'" :aria-label="b.is_favorite ? '取消收藏' : '收藏'" @click="handleToggleBloggerFavorite(b)">
              <svg viewBox="0 0 24 24" width="15" height="15" :fill="b.is_favorite ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M12 3l2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 18.4 6.2 21.4l1.1-6.5L2.6 9.8l6.5-.9L12 3z" /></svg>
            </button>
            <button type="button" class="brow-open" @click="openBlogger(b, 'dossier')">
              <span class="brow-av" :class="{ lit: b.last_distilled_at }">{{ (b.display_name || '?').slice(0, 1) }}</span>
              <span class="brow-id">
                <span class="brow-name">
                  {{ b.display_name }}
                  <span class="brow-dot" :style="{ background: platMeta(b.platform).dot }"></span>
                  <span class="brow-plat">{{ platMeta(b.platform).name }}</span>
                </span>
                <span class="brow-meta">
                  <span>{{ b.niche || '未设置领域' }}</span>
                  <span v-if="b.follower_count">粉丝 {{ fmtNum(b.follower_count) }}</span>
                  <span>{{ b.sample_count ? `采集 ${b.sample_count} 篇` : '未采集' }}</span>
                  <span class="pill" :class="b.last_distilled_at ? 'ok' : 'muted'">{{ b.last_distilled_at ? '画像最新' : '未建画像' }}</span>
                  <span v-if="draftsByBlogger[b.id]" class="pill draft">草稿 {{ draftsByBlogger[b.id] }}</span>
                </span>
              </span>
            </button>
            <div class="brow-act">
              <button type="button" @click="openBlogger(b, 'dossier')">档案</button>
              <button type="button" @click="openBlogger(b, 'analysis')">分析</button>
              <button type="button" class="lit" @click="createWith(b)">用它创作</button>
            </div>
          </article>
        </div>

        <div v-else class="empty">
          <template v-if="benchmarks.length">
            没有匹配的博主。<button type="button" class="link" @click="query = ''; platformFilter = 'all'">清除筛选</button>
          </template>
          <template v-else>
            还没有对标博主。<button type="button" class="link" @click="router.push({ name: 'find' })">去加一个 →</button>
          </template>
        </div>
      </div>

      <!-- 右栏 -->
      <aside class="rail">
        <div class="panel">
          <div class="panel-head">
            <span>我的账号<em v-if="accountCount">{{ accountCount }}</em></span>
          </div>
          <div v-if="accountCount" class="panel-list">
            <button v-for="a in myAccounts" :key="a.id" type="button" class="pitem" @click="openAccount(a.id)">
              <span class="pitem-av">{{ (a.display_name || '?').slice(0, 1) }}</span>
              <span class="pitem-main">
                <b>{{ a.display_name }}</b>
                <small>{{ platMeta(a.platform).name }}{{ a.niche ? ` · ${a.niche}` : '' }}</small>
              </span>
              <span class="pitem-go" aria-hidden="true">→</span>
            </button>
          </div>
          <p v-else class="panel-empty">绑定你自己的账号,创作时能把对标拍法降到你做得到的版本。</p>
        </div>

        <div class="panel">
          <div class="panel-head">
            <span>最近草稿</span>
            <button v-if="draftCount" type="button" class="link" @click="router.push({ name: 'drafts' })">全部 {{ draftCount }} →</button>
          </div>
          <div v-if="recentDrafts.length" class="panel-list">
            <button v-for="d in recentDrafts" :key="d.id" type="button" class="pitem draft-item" @click="router.push({ name: 'drafts' })">
              <span class="pitem-main">
                <b>{{ d.title || d.topic || '未命名草稿' }}</b>
                <small>{{ xhsContentTypeLabel(d.content_type) }} · {{ bloggerName(d.blogger_id) }} · {{ friendlyTime(d.updated_at) }}</small>
              </span>
            </button>
          </div>
          <p v-else class="panel-empty">还没有草稿。选个博主「用它创作」就有了。</p>
        </div>

        <button type="button" class="wechat" @click="router.push({ name: 'workspace', params: { platform: 'wechat', tab: 'brief' } })">
          <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 8v4l3 2" /></svg>
          <span>公众号早报</span>
          <span class="wechat-go" aria-hidden="true">进入 →</span>
        </button>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.home { display: flex; flex-direction: column; }

/* —— 接下来 —— */
.hero {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--color-accent-tint);
  border: 1px solid var(--color-accent-soft-bd);
  border-radius: 12px;
  padding: 13px 15px;
  margin-bottom: 18px;
}
.hero-ico { color: var(--color-accent); flex: 0 0 auto; display: inline-flex; }
.hero-txt { flex: 1; min-width: 0; }
.hero-txt strong { display: block; font-size: 14px; font-weight: 640; color: var(--color-accent-ink); }
.hero-txt p { margin: 1px 0 0; font-size: 13px; color: var(--color-accent-ink); }
.hero-cta {
  flex: 0 0 auto;
  border: 1px solid var(--color-accent-soft-bd);
  background: var(--color-surface);
  color: var(--color-accent-ink);
  border-radius: 8px;
  padding: 7px 14px;
  font-size: 13px;
  font-weight: 550;
  cursor: pointer;
  transition: border-color 120ms var(--ease-out);
}
.hero-cta:hover { border-color: var(--color-accent); }

/* —— 两栏 —— */
.grid { display: grid; grid-template-columns: minmax(0, 1fr) 316px; gap: 20px; align-items: start; }

/* —— 主:对标博主 —— */
.main-head { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
.mh-title { margin: 0; font-size: 15px; font-weight: 650; color: var(--color-ink); display: inline-flex; align-items: center; }
.mh-count {
  margin-left: 7px;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-ink-3);
  background: var(--color-paper-3);
  border-radius: 999px;
  padding: 1px 8px;
}
.mh-tools { margin-left: auto; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.search {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: 8px;
  padding: 0 10px;
  height: 32px;
  color: var(--color-ink-3);
}
.search:focus-within { border-color: var(--color-accent-soft-bd); }
.search input { border: 0; background: none; outline: none; font-size: 13px; color: var(--color-ink); width: 132px; }
.search input::placeholder { color: var(--color-ink-3); }
.sort {
  height: 32px;
  border: 1px solid var(--color-rule);
  border-radius: 8px;
  background: var(--color-surface);
  color: var(--color-ink-2);
  font-size: 13px;
  padding: 0 8px;
  cursor: pointer;
}
.add-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 32px;
  padding: 0 12px;
  border: 1px solid var(--color-accent-soft-bd);
  background: var(--color-accent-tint);
  color: var(--color-accent-ink);
  border-radius: 8px;
  font-size: 13px;
  font-weight: 550;
  cursor: pointer;
}
.add-btn:hover { border-color: var(--color-accent); }

.chips { display: flex; gap: 6px; margin-bottom: 12px; }
.chips button {
  border: 1px solid var(--color-rule);
  background: var(--color-surface);
  color: var(--color-ink-2);
  border-radius: 999px;
  padding: 3px 12px;
  font-size: 12px;
  cursor: pointer;
}
.chips button.on { border-color: var(--color-accent-soft-bd); background: var(--color-accent-soft); color: var(--color-accent-ink); }

.blist { display: flex; flex-direction: column; gap: 8px; }
.brow {
  display: flex;
  align-items: center;
  gap: 4px;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
  padding: 10px 12px;
  transition: border-color 120ms var(--ease-out);
}
.brow:hover { border-color: var(--color-accent-soft-bd); }
.fav {
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border: 0;
  background: none;
  color: var(--color-ink-3);
  border-radius: 7px;
  cursor: pointer;
}
.fav:hover { background: var(--color-paper-3); color: var(--color-ink-2); }
.fav.on { color: #d8a72a; }
.brow-open {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  border: 0;
  background: none;
  cursor: pointer;
  text-align: left;
  padding: 0;
}
.brow-av {
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--color-paper-3);
  color: var(--color-ink-2);
  font-size: 14px;
  font-weight: 600;
}
.brow-av.lit { background: var(--color-accent-soft); color: var(--color-accent-ink); }
.brow-id { flex: 1; min-width: 0; }
.brow-name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 620;
  color: var(--color-ink);
  white-space: nowrap;
  overflow: hidden;
}
.brow-name > :first-child { overflow: hidden; text-overflow: ellipsis; }
.brow-dot { flex: 0 0 auto; width: 6px; height: 6px; border-radius: 50%; }
.brow-plat { flex: 0 0 auto; font-size: 11px; font-weight: 500; color: var(--color-ink-3); }
.brow-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px 9px;
  margin-top: 3px;
  font-size: 12px;
  color: var(--color-ink-3);
}
.pill { border-radius: 999px; padding: 1px 8px; font-size: 11px; font-weight: 500; }
.pill.ok { background: var(--color-accent-soft); color: var(--color-accent-ink); }
.pill.muted { background: var(--color-paper-3); color: var(--color-ink-3); }
.pill.draft { background: var(--color-paper-3); color: var(--color-ink-2); }
.brow-act { flex: 0 0 auto; display: flex; gap: 6px; }
.brow-act button {
  border: 0;
  background: var(--color-paper-3);
  color: var(--color-ink-2);
  border-radius: 7px;
  padding: 5px 11px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}
.brow-act button:hover { background: var(--color-rule); }
.brow-act button.lit { background: var(--color-accent-soft); color: var(--color-accent-ink); }
.brow-act button.lit:hover { background: var(--color-accent-soft-bd); }

.empty {
  padding: 28px 16px;
  text-align: center;
  font-size: 13px;
  color: var(--color-ink-3);
  border: 1px dashed var(--color-rule-strong);
  border-radius: var(--radius-lg);
}
.link { border: 0; background: none; color: var(--color-accent-ink); font-size: 13px; cursor: pointer; padding: 0; }
.link:hover { text-decoration: underline; }

/* —— 右栏 —— */
.rail { display: flex; flex-direction: column; gap: 12px; }
.panel { background: var(--color-surface); border: 1px solid var(--color-rule); border-radius: var(--radius-lg); padding: 13px 14px; }
.panel-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.panel-head > span { font-size: 13px; font-weight: 640; color: var(--color-ink); display: inline-flex; align-items: center; }
.panel-head em {
  margin-left: 6px;
  font-style: normal;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-ink-3);
  background: var(--color-paper-3);
  border-radius: 999px;
  padding: 0 7px;
}
.panel-list { display: flex; flex-direction: column; gap: 2px; }
.pitem {
  display: flex;
  align-items: center;
  gap: 9px;
  border: 0;
  background: none;
  border-radius: 8px;
  padding: 7px 8px;
  cursor: pointer;
  text-align: left;
}
.pitem:hover { background: var(--color-paper-3); }
.pitem-av {
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--color-paper-3);
  color: var(--color-ink-2);
  font-size: 12px;
  font-weight: 600;
}
.pitem:hover .pitem-av { background: var(--color-surface); }
.pitem-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.pitem-main b { font-size: 13px; font-weight: 560; color: var(--color-ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pitem-main small { font-size: 11.5px; color: var(--color-ink-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pitem-go { flex: 0 0 auto; color: var(--color-ink-3); font-size: 13px; }
.draft-item { padding-left: 8px; }
.panel-empty { margin: 0; font-size: 12px; line-height: 1.5; color: var(--color-ink-3); }

.wechat {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
  padding: 13px 14px;
  color: var(--color-ink-2);
  cursor: pointer;
  transition: border-color 120ms var(--ease-out);
}
.wechat:hover { border-color: var(--color-accent-soft-bd); }
.wechat > span:nth-of-type(1) { font-size: 13.5px; font-weight: 600; color: var(--color-ink); }
.wechat-go { margin-left: auto; font-size: 12px; color: var(--color-ink-3); }

/* —— 响应式:窄屏叠成一栏,右栏移到下方 —— */
@media (max-width: 860px) {
  .grid { grid-template-columns: 1fr; }
}
@media (max-width: 560px) {
  .mh-tools { width: 100%; }
  .search { flex: 1; }
  .search input { width: 100%; }
  .brow { flex-wrap: wrap; }
  .brow-act { width: 100%; padding-left: 30px; }
}
</style>
