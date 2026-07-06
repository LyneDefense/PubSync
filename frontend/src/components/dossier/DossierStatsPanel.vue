<script setup lang="ts">
// 档案页·数据面板(账号事实,全量池算):编辑体大数字指标行 + 水平占比条(内容形态 / 详情覆盖)。
// 互动率已下线(小红书无浏览量);环图/色块去掉。数字用 tabular-nums,不套显示字体。
import { computed } from 'vue'

const props = defineProps<{ stats: Record<string, unknown> }>()

function num(key: string): number | null {
  const v = props.stats[key]
  return typeof v === 'number' ? v : null
}
// 大数字拆成「数值 + 单位」:≥1w 用 w,否则千分位。
function split(v: number | null): { value: string; unit: string } {
  if (v == null) return { value: '—', unit: '' }
  if (v >= 10000) return { value: (v / 10000).toFixed(1), unit: 'w' }
  return { value: v.toLocaleString(), unit: '' }
}
function fmt(v: number | null): string {
  if (v == null) return '—'
  return v >= 10000 ? `${(v / 10000).toFixed(1)}w` : v.toLocaleString()
}

// 覆盖 + 详情深度。翻到底 / 已收录≥平台标称 → 视为覆盖全部(不显示会溢出的百分比)。
const coverage = computed(() => {
  const total = num('note_total')
  const got = num('note_count') ?? 0
  const full = num('full_count') ?? 0
  const list = num('list_count') ?? 0
  const covered = props.stats.reached_end === true || (total != null && got >= total)
  const platformPct = !covered && total && total > 0 ? Math.round((got / total) * 100) : null
  const detailPct = got > 0 ? Math.round((full / got) * 100) : 0
  return { total, got, full, list, covered, platformPct, detailPct }
})

const metrics = computed(() => {
  const lc = split(num('liked_collected_count'))
  const contentVal = coverage.value.total ?? coverage.value.got
  const ratio = num('favorite_like_ratio')
  return [
    { label: '获赞与收藏', value: lc.value, unit: lc.unit, sub: '账号累计（全部笔记）' },
    { label: '篇均点赞', value: fmt(num('average_like')), unit: '', sub: `均藏 ${fmt(num('average_favorite'))} · 均评 ${fmt(num('average_comment'))}` },
    { label: '赞藏比', value: ratio != null ? String(ratio) : '—', unit: '', sub: '越高越「值得收藏」' },
    { label: '内容量', value: String(contentVal), unit: '篇', sub: `已采详情 ${coverage.value.full}（${coverage.value.detailPct}%）` }
  ]
})

// 内容形态:图文 vs 视频(按已收录计)。
const modality = computed(() => {
  const by = props.stats.by_modality as Record<string, { count?: number; average_like?: number }> | undefined
  const image = by?.image?.count || 0
  const video = by?.video?.count || 0
  const total = image + video
  if (!total) return null
  return {
    total,
    image,
    video,
    imagePct: (image / total) * 100,
    videoPct: (video / total) * 100,
    imageAvg: by?.image?.average_like || 0,
    videoAvg: by?.video?.average_like || 0
  }
})
</script>

<template>
  <section class="ds">
    <div class="ds__head">
      <h3>账号数据</h3>
      <span class="ds__head-sub">表现如何</span>
      <span class="ds__head-note">池更新后自动重算</span>
    </div>

    <div class="ds__metrics">
      <div v-for="(m, i) in metrics" :key="m.label" class="ds__metric" :class="{ 'ds__metric--div': i > 0 }">
        <span class="ds__metric-label">{{ m.label }}</span>
        <span class="ds__metric-value"><b>{{ m.value }}</b><i v-if="m.unit">{{ m.unit }}</i></span>
        <span class="ds__metric-sub">{{ m.sub }}</span>
      </div>
    </div>

    <div class="ds__bars">
      <div v-if="modality" class="ds__bar-block">
        <div class="ds__bar-head">
          <span class="ds__bar-title">内容形态</span>
          <span class="ds__bar-note">按已收录 {{ modality.total }} 篇计</span>
        </div>
        <div class="ds__track">
          <span class="ds__seg ds__seg--image" :style="{ width: `${modality.imagePct}%` }"></span>
          <span class="ds__seg ds__seg--video" :style="{ width: `${modality.videoPct}%` }"></span>
        </div>
        <div class="ds__legend">
          <span class="ds__legend-row"><i class="ds__dot ds__dot--image"></i>图文 <b>{{ modality.image }}</b> 篇 · 均赞 {{ fmt(modality.imageAvg) }}</span>
          <span class="ds__legend-row"><i class="ds__dot ds__dot--video"></i>视频 <b>{{ modality.video }}</b> 篇 · 均赞 {{ fmt(modality.videoAvg) }}</span>
        </div>
      </div>

      <div class="ds__bar-block">
        <div class="ds__bar-head">
          <span class="ds__bar-title">详情覆盖</span>
          <span v-if="coverage.covered" class="ds__bar-ok">已覆盖全部</span>
          <span v-else-if="coverage.platformPct != null" class="ds__bar-note">已收录 {{ coverage.platformPct }}%</span>
          <span v-else class="ds__bar-note">未翻到底</span>
        </div>
        <div class="ds__track">
          <span class="ds__seg ds__seg--accent" :style="{ width: `${coverage.detailPct}%` }"></span>
        </div>
        <p class="ds__cover-note">已采详情 <b>{{ coverage.full }}</b> 篇（{{ coverage.detailPct }}%）· 仅列表 {{ coverage.list }} 篇 —— 只有已采详情进创作画像。</p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.ds { background: var(--color-surface); border: 1px solid var(--color-rule); border-radius: 14px; overflow: hidden; }
.ds__head { display: flex; align-items: baseline; gap: 10px; padding: 18px 22px 0; flex-wrap: wrap; }
.ds__head h3 { margin: 0; font-size: 15px; font-weight: 650; }
.ds__head-sub { font-size: 12px; color: var(--color-ink-3); }
.ds__head-note { margin-left: auto; font-size: 11.5px; color: var(--color-ink-3); }

.ds__metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; padding: 16px 22px 18px; }
.ds__metric { display: flex; flex-direction: column; gap: 5px; padding: 0 4px; }
.ds__metric--div { border-left: 1px solid var(--color-paper-3); padding-left: 16px; }
.ds__metric-label { font-size: 12px; color: var(--color-ink-3); }
.ds__metric-value { display: flex; align-items: baseline; gap: 3px; }
.ds__metric-value b { font-size: 28px; font-weight: 720; color: var(--color-ink); line-height: 1; letter-spacing: -0.01em; font-variant-numeric: tabular-nums; }
.ds__metric-value i { font-size: 12.5px; font-weight: 600; font-style: normal; color: var(--color-ink-3); }
.ds__metric-sub { font-size: 11.5px; color: var(--color-ink-3); line-height: 1.4; }

.ds__bars { display: flex; gap: 28px; align-items: flex-start; flex-wrap: wrap; padding: 16px 22px; background: var(--color-paper); border-top: 1px solid var(--color-paper-3); }
.ds__bar-block { flex: 1 1 260px; min-width: 240px; }
.ds__bar-head { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 8px; }
.ds__bar-title { font-size: 12.5px; font-weight: 600; color: var(--color-ink-2); }
.ds__bar-note { font-size: 11.5px; color: var(--color-ink-3); }
.ds__bar-ok { font-size: 11.5px; font-weight: 600; color: #2f6b54; }
.ds__track { display: flex; height: 12px; border-radius: 999px; overflow: hidden; background: var(--color-paper-3); }
.ds__seg { display: block; height: 100%; }
.ds__seg--image { background: #1d9e75; }
.ds__seg--video { background: #3d84d6; }
.ds__seg--accent { background: var(--color-accent); }
.ds__legend { display: flex; gap: 18px; margin-top: 10px; flex-wrap: wrap; }
.ds__legend-row { display: flex; align-items: center; gap: 7px; font-size: 12.5px; color: var(--color-ink-2); }
.ds__legend-row b { font-weight: 650; color: var(--color-ink); }
.ds__dot { width: 9px; height: 9px; border-radius: 3px; flex: 0 0 auto; }
.ds__dot--image { background: #1d9e75; }
.ds__dot--video { background: #3d84d6; }
.ds__cover-note { margin: 10px 0 0; font-size: 12px; color: var(--color-ink-3); line-height: 1.5; }
.ds__cover-note b { color: var(--color-accent-ink); }

@media (max-width: 560px) {
  .ds__metrics { grid-template-columns: repeat(2, 1fr); gap: 16px 4px; }
  .ds__metric:nth-child(3) { border-left: 0; padding-left: 4px; }
}
</style>
