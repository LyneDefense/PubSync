<script setup lang="ts">
// 首页 Hub（对象驱动 · 「工作台」方向）：masthead 概览 + 两栏。
// 左栏「对标博主」= 铺满宽屏的对齐清单表（粉丝/采集/画像成列，发丝分隔行、悬停高亮、悬停浮出操作），抗规模。
// 右栏 = 我的账号 + 最近草稿 + 公众号早报。每行信号（粉丝/采集/画像/草稿数）均来自 store 现有字段，不编造。
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

const greeting = (() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 11) return '上午好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})()

// masthead 概览一句；无对标博主时给起步引导。
const mastSummary = computed(() => {
  if (!benchmarks.value.length) return '先加一个想学的对标博主，开始你的第一次创作。'
  const parts = [`${benchmarks.value.length} 位对标博主`, `${distilledCount.value} 份画像就绪`]
  if (draftCount.value) parts.push(`${draftCount.value} 篇草稿`)
  return parts.join(' · ')
})

// 主行动：按状态给 CTA。
const nextStep = computed(() => {
  if (!benchmarks.value.length) return { cta: '加对标博主', act: () => router.push({ name: 'find' }) }
  if (distilledCount.value === 0) return { cta: '去建档', act: () => openBlogger(benchmarks.value[0], 'dossier') }
  return { cta: '开始创作', act: () => router.push({ name: 'create' }) }
})

// —— 清单：搜索 + 平台筛选 + 排序；收藏置顶（抗规模的关键）—— //
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
    if (a.is_favorite !== b.is_favorite) return a.is_favorite ? -1 : 1
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
function fmtNum(n: number | null | undefined) {
  if (!n) return '—'
  if (n >= 10000) return `${(n / 10000).toFixed(n % 10000 === 0 ? 0 : 1)}万`
  return String(n)
}
function platName(p: string) {
  return p === 'douyin' ? '抖音' : '小红书'
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
</script>

<template>
  <section class="home">
    <!-- masthead -->
    <div class="mast">
      <div class="mast-txt">
        <h1>{{ greeting }}</h1>
        <p>{{ mastSummary }}</p>
      </div>
      <button type="button" class="mast-cta" @click="nextStep.act()">
        {{ nextStep.cta }}
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
      </button>
    </div>

    <div class="grid">
      <!-- 对标博主（主） -->
      <div class="main">
        <div class="toolbar">
          <h2>博主档案</h2>
          <span class="cnt">{{ benchmarks.length }}</span>
          <template v-if="showPlatformFilter">
            <button type="button" class="chip" :class="{ on: platformFilter === 'all' }" @click="platformFilter = 'all'">全部</button>
            <button type="button" class="chip" :class="{ on: platformFilter === 'xhs' }" @click="platformFilter = 'xhs'">小红书</button>
            <button type="button" class="chip" :class="{ on: platformFilter === 'douyin' }" @click="platformFilter = 'douyin'">抖音</button>
          </template>
          <span class="sp"></span>
          <label class="search">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4-4" /></svg>
            <input v-model="query" type="search" placeholder="搜索名称 / 领域" aria-label="搜索博主档案" />
          </label>
          <button type="button" class="add" @click="router.push({ name: 'find' })">
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
            加博主
          </button>
        </div>

        <div v-if="filteredBloggers.length" class="table">
          <div class="thead">
            <div>博主</div>
            <div class="r">粉丝</div>
            <div class="r col-hide">采集</div>
            <div class="col-hide">画像</div>
            <div></div>
          </div>
          <article v-for="b in filteredBloggers" :key="b.id" class="trow">
            <div class="who">
              <button type="button" class="star" :class="{ on: b.is_favorite }" :title="b.is_favorite ? '取消收藏' : '收藏'" :aria-label="b.is_favorite ? '取消收藏' : '收藏'" @click="handleToggleBloggerFavorite(b)">
                <svg viewBox="0 0 24 24" width="14" height="14" :fill="b.is_favorite ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M12 3l2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 18.4 6.2 21.4l1.1-6.5L2.6 9.8l6.5-.9L12 3z" /></svg>
              </button>
              <button type="button" class="who-open" @click="openBlogger(b, 'dossier')">
                <span class="av" :class="{ lit: b.last_distilled_at }">{{ (b.display_name || '?').slice(0, 1) }}</span>
                <span class="who-txt">
                  <span class="nm">
                    <span class="nm-text">{{ b.display_name }}</span>
                    <span v-if="draftsByBlogger[b.id]" class="dtag">草稿 {{ draftsByBlogger[b.id] }}</span>
                  </span>
                  <span class="sm">{{ platName(b.platform) }}{{ b.niche ? ` · ${b.niche}` : '' }}</span>
                </span>
              </button>
            </div>
            <div class="cell r num">{{ fmtNum(b.follower_count) }}</div>
            <div class="cell r num col-hide">{{ b.sample_count || '—' }}</div>
            <div class="col-hide">
              <span class="stt" :class="{ pending: !b.last_distilled_at }">
                <span class="dot" :class="b.last_distilled_at ? 'ready' : 'none'"></span>{{ b.last_distilled_at ? '最新' : '未建' }}
              </span>
            </div>
            <div class="act">
              <span class="act-rest" aria-hidden="true">›</span>
              <span class="act-hover">
                <button type="button" @click="openBlogger(b, 'analysis')">分析</button>
                <button type="button" class="pri" @click="createWith(b)">用它创作</button>
              </span>
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
          <h3>我的账号<span v-if="accountCount" class="n">{{ accountCount }}</span></h3>
          <div v-if="accountCount" class="plist">
            <button v-for="a in myAccounts" :key="a.id" type="button" class="pitem" @click="openAccount(a.id)">
              <span class="pav">{{ (a.display_name || '?').slice(0, 1) }}</span>
              <span class="pt">
                <b>{{ a.display_name }}</b>
                <small>{{ platName(a.platform) }}{{ a.niche ? ` · ${a.niche}` : '' }}</small>
              </span>
              <span class="pgo" aria-hidden="true">→</span>
            </button>
          </div>
          <p v-else class="pempty">绑定你自己的账号，创作时能把对标拍法降到你做得到的版本。</p>
        </div>

        <div class="panel">
          <h3>最近草稿<button v-if="draftCount" type="button" class="all" @click="router.push({ name: 'drafts' })">全部 {{ draftCount }} →</button></h3>
          <div v-if="recentDrafts.length" class="plist">
            <button v-for="d in recentDrafts" :key="d.id" type="button" class="pitem" @click="router.push({ name: 'drafts' })">
              <span class="pt">
                <b>{{ d.title || d.topic || '未命名草稿' }}</b>
                <small>{{ xhsContentTypeLabel(d.content_type) }} · {{ bloggerName(d.blogger_id) }} · {{ friendlyTime(d.updated_at) }}</small>
              </span>
            </button>
          </div>
          <p v-else class="pempty">还没有草稿。选个博主「用它创作」就有了。</p>
        </div>

        <button type="button" class="wechat" @click="router.push({ name: 'workspace', params: { platform: 'wechat', tab: 'brief' } })">
          <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 8v4l3 2" /></svg>
          <b>公众号早报</b>
          <span class="wgo" aria-hidden="true">进入 →</span>
        </button>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.home { display: flex; flex-direction: column; }

/* —— masthead —— */
.mast { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 22px; }
.mast-txt h1 { margin: 0; font-family: var(--font-display); font-size: 23px; font-weight: 600; letter-spacing: -0.01em; color: var(--color-ink); }
.mast-txt p { margin: 5px 0 0; font-size: 13.5px; color: var(--color-ink-2); }
.mast-cta {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  background: var(--color-accent);
  color: #fff;
  border: 0;
  border-radius: 10px;
  padding: 11px 18px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 120ms var(--ease-out);
}
.mast-cta:hover { background: var(--color-accent-press); }

/* —— 两栏 —— */
.grid { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 24px; align-items: start; }

/* —— 主：工具条 —— */
.toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.toolbar h2 { margin: 0; font-family: var(--font-display); font-size: 15px; font-weight: 600; color: var(--color-ink); }
.toolbar .cnt { font-family: var(--font-display); font-size: 11.5px; font-weight: 600; color: var(--color-ink-3); background: var(--color-paper-3); border-radius: var(--radius-pill); padding: 1px 8px; }
.toolbar .sp { flex: 1; }
.chip { border: 1px solid var(--color-rule); background: var(--color-surface); color: var(--color-ink-2); border-radius: var(--radius-pill); padding: 3px 11px; font-size: 12px; cursor: pointer; }
.chip.on { border-color: var(--color-accent-soft-bd); background: var(--color-accent-soft); color: var(--color-accent-ink); }
.search { display: inline-flex; align-items: center; gap: 6px; height: 30px; padding: 0 10px; border: 1px solid var(--color-rule); border-radius: var(--radius-md); background: var(--color-surface); color: var(--color-ink-3); }
.search:focus-within { border-color: var(--color-accent-soft-bd); }
.search input { border: 0; background: none; outline: none; font-size: 12.5px; color: var(--color-ink); width: 116px; }
.search input::placeholder { color: var(--color-ink-3); }
.sort { height: 30px; border: 1px solid var(--color-rule); border-radius: var(--radius-md); background: var(--color-surface); color: var(--color-ink-2); font-size: 12.5px; padding: 0 8px; cursor: pointer; }
.add { display: grid; place-items: center; width: 30px; height: 30px; border: 1px solid var(--color-accent-soft-bd); background: var(--color-accent-tint); color: var(--color-accent-ink); border-radius: var(--radius-md); cursor: pointer; }
.add:hover { border-color: var(--color-accent); }

/* —— 清单表：单一边框容器 + 发丝分隔行（去掉一格格盒子）—— */
.table { border: 1px solid var(--color-rule); border-radius: var(--radius-lg); background: var(--color-surface); overflow: hidden; }
.thead, .trow { display: grid; grid-template-columns: minmax(240px, 1fr) 104px 88px 100px 152px; align-items: center; gap: 12px; padding: 0 16px; }
.thead { height: 34px; font-size: 11px; color: var(--color-ink-3); background: var(--color-paper-3); border-bottom: 1px solid var(--color-rule); }
.thead .r { text-align: right; }
.trow { height: 62px; border-bottom: 1px solid var(--color-paper-3); }
.trow:last-child { border-bottom: 0; }
.trow:hover { background: var(--color-accent-tint); }

.who { display: flex; align-items: center; gap: 8px; min-width: 0; }
.star { flex: 0 0 auto; display: grid; place-items: center; width: 20px; height: 20px; border: 0; background: none; color: var(--color-ink-3); cursor: pointer; padding: 0; opacity: 0; transition: opacity 120ms var(--ease-out); }
.star.on { opacity: 1; color: #cf9f2c; }
.trow:hover .star { opacity: 1; }
.who-open { flex: 1; min-width: 0; display: flex; align-items: center; gap: 11px; border: 0; background: none; cursor: pointer; text-align: left; padding: 0; }
.av { flex: 0 0 auto; display: grid; place-items: center; width: 38px; height: 38px; border-radius: 50%; background: var(--color-paper-3); color: var(--color-ink-2); font-family: var(--font-display); font-size: 14px; font-weight: 600; }
.av.lit { background: var(--color-accent-soft); color: var(--color-accent-ink); }
.who-txt { flex: 1; min-width: 0; }
.nm { display: flex; align-items: center; gap: 7px; min-width: 0; }
.nm-text { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: var(--font-display); font-size: 14.5px; font-weight: 600; color: var(--color-ink); }
.dtag { flex: 0 0 auto; font-family: var(--font-body); font-size: 10.5px; font-weight: 500; color: var(--color-accent-ink); background: var(--color-accent-soft); border-radius: var(--radius-pill); padding: 1px 7px; }
.sm { display: block; margin-top: 2px; font-size: 12px; color: var(--color-ink-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.cell { font-size: 13px; color: var(--color-ink-2); }
.cell.r { text-align: right; }
.num { font-variant-numeric: tabular-nums; }
.stt { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--color-ink-2); }
.stt.pending { color: var(--color-ink-3); }
.dot { width: 6px; height: 6px; border-radius: 50%; flex: 0 0 auto; }
.dot.ready { background: var(--color-accent); }
.dot.none { border: 1.5px solid var(--color-ink-3); box-sizing: border-box; }

.act { justify-self: end; }
.act-rest { color: var(--color-ink-3); font-size: 16px; padding-right: 6px; }
.act-hover { display: none; gap: 6px; }
.trow:hover .act-rest { display: none; }
.trow:hover .act-hover { display: inline-flex; }
.act-hover button { border: 0; background: var(--color-paper-3); color: var(--color-ink-2); border-radius: var(--radius-sm); padding: 5px 10px; font-size: 12px; cursor: pointer; white-space: nowrap; }
.act-hover button:hover { background: var(--color-rule); }
.act-hover button.pri { background: var(--color-accent-soft); color: var(--color-accent-ink); font-weight: 550; }
.act-hover button.pri:hover { background: var(--color-accent-soft-bd); }

.empty { padding: 30px 16px; text-align: center; font-size: 13px; color: var(--color-ink-3); border: 1px dashed var(--color-rule-strong); border-radius: var(--radius-lg); }
.link { border: 0; background: none; color: var(--color-accent-ink); font-size: 13px; cursor: pointer; padding: 0; }
.link:hover { text-decoration: underline; }

/* —— 右栏 —— */
.rail { display: flex; flex-direction: column; gap: 13px; }
.panel { background: var(--color-surface); border: 1px solid var(--color-rule); border-radius: var(--radius-lg); padding: 13px 14px; }
.panel h3 { margin: 0 0 10px; font-family: var(--font-display); font-size: 13px; font-weight: 600; color: var(--color-ink); display: flex; align-items: center; }
.panel h3 .n { margin-left: 7px; font-size: 11px; font-weight: 500; color: var(--color-ink-3); }
.panel h3 .all { margin-left: auto; border: 0; background: none; font-size: 11.5px; color: var(--color-ink-3); cursor: pointer; padding: 0; }
.panel h3 .all:hover { color: var(--color-accent-ink); }
.plist { display: flex; flex-direction: column; gap: 2px; }
.pitem { display: flex; align-items: center; gap: 10px; border: 0; background: none; border-radius: var(--radius-md); padding: 7px 8px; cursor: pointer; text-align: left; }
.pitem:hover { background: var(--color-paper-3); }
.pav { flex: 0 0 auto; display: grid; place-items: center; width: 28px; height: 28px; border-radius: 50%; background: var(--color-paper-3); color: var(--color-ink-2); font-family: var(--font-display); font-size: 12px; font-weight: 600; }
.pitem:hover .pav { background: var(--color-surface); }
.pt { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.pt b { font-size: 13px; font-weight: 560; color: var(--color-ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pt small { font-size: 11.5px; color: var(--color-ink-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pgo { flex: 0 0 auto; color: var(--color-ink-3); font-size: 13px; }
.pempty { margin: 0; font-size: 12px; line-height: 1.55; color: var(--color-ink-3); }

.wechat { display: flex; align-items: center; gap: 10px; background: var(--color-surface); border: 1px solid var(--color-rule); border-radius: var(--radius-lg); padding: 13px 14px; color: var(--color-ink-2); cursor: pointer; transition: border-color 120ms var(--ease-out); }
.wechat:hover { border-color: var(--color-accent-soft-bd); }
.wechat b { font-size: 13px; font-weight: 600; color: var(--color-ink); }
.wgo { margin-left: auto; font-size: 11.5px; color: var(--color-ink-3); }

/* —— 响应式:两栏先叠成一栏(让清单表拿到全宽),再窄才收起 采集/画像 列 —— */
@media (max-width: 1080px) {
  .grid { grid-template-columns: 1fr; }
}
@media (max-width: 772px) {
  .thead, .trow { grid-template-columns: minmax(0, 1fr) 76px 100px; }
  .col-hide { display: none; }
}
</style>
