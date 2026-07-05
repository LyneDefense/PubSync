<script setup lang="ts">
// 档案页·成长趋势(招牌图):真实时间轴(每 6 个月 YYYY.MM 日期刻度 + 竖网格 + 季度小刻度)的面积趋势图。
// 阶段带 + 互动基线(分桶中位)+ 散点 + 涨粉拐点 + 爆发点 + 爆文归因。诚实:低频粗判;赞藏定位涨粉时机、替不了量。
import { computed } from 'vue'
import type { DossierAttribution, DossierTrajectory } from '../../api/types'

const props = defineProps<{
  trajectory: DossierTrajectory
  attribution: DossierAttribution | null
  attributionRunning: boolean
  reachedEnd: boolean
  busy: boolean
}>()
defineEmits<{ (e: 'run-attribution'): void }>()

const W = 660
const H = 236
const PAD_T = 20
const PAD_B = 48
const BOTTOM = H - PAD_B // 188
const GRID_TOP = 18
const DAY = 86400000

function fmt(v: number): string {
  return v >= 10000 ? `${(v / 10000).toFixed(1)}w` : v.toLocaleString()
}
function bandFill(label: string): string {
  if (label.includes('起步')) return '#eef1f4'
  if (label.includes('突破')) return '#fbeecf'
  if (label.includes('滑坡')) return '#fceceb'
  return '#e7f2ec'
}

const model = computed(() => {
  const t = props.trajectory
  const pts = t.points || []
  if (pts.length < 2) return null
  const times = pts.map((p) => Date.parse(p.date))
  const tMin = Math.min(...times)
  const tMax = Math.max(...times)
  const span = Math.max(tMax - tMin, 1)
  const maxLike = Math.max(...pts.map((p) => p.like), 1)
  const xOfT = (ms: number) => ((ms - tMin) / span) * (W - 10) + 5
  const xOf = (d: string) => xOfT(Date.parse(d))
  const yOf = (like: number) => PAD_T + (1 - like / maxLike) * (BOTTOM - PAD_T)

  const dots = pts.map((p) => ({ x: xOf(p.date).toFixed(1), y: yOf(p.like).toFixed(1) }))

  // 互动基线 = 每分桶中位;面积填充到底轴。
  const base = (t.buckets || [])
    .map((b) => ({ x: (xOf(b.start) + xOf(b.end)) / 2, y: yOf(b.median_like) }))
    .sort((a, b) => a.x - b.x)
  const baseline = base.length > 1 ? base.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ') : ''
  const area = base.length > 1
    ? `M ${base[0].x.toFixed(1)},${BOTTOM} ` + base.map((p) => `L ${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ') + ` L ${base[base.length - 1].x.toFixed(1)},${BOTTOM} Z`
    : ''

  const bands = (t.phases || []).map((ph) => {
    const x = xOf(ph.start)
    return { x: x.toFixed(1), w: Math.max(xOf(ph.end) - x, 3).toFixed(1), fill: bandFill(ph.label) }
  })
  const grid = [0, 0.33, 0.66, 1].map((f) => (PAD_T + f * (BOTTOM - PAD_T)).toFixed(1))

  const ups = (t.level_ups || []).map((u) => ({ x: xOf(u.date).toFixed(1) }))

  const burstDots = (t.bursts || []).map((b) => ({ x: xOf(b.date).toFixed(1), y: yOf(b.like).toFixed(1), like: b.like }))
  const topB = (t.bursts || []).slice().sort((a, b) => b.like - a.like)[0]
  const topBurst = topB ? { x: xOf(topB.date).toFixed(1), y: (yOf(topB.like) - 12).toFixed(1), label: `${fmt(topB.like)} 赞` } : null

  // 时间轴:季度小刻度 + 每 6 个月日期(竖网格 + 大刻度 + YYYY.MM)。
  const dMin = new Date(tMin)
  const ticks: { x: string }[] = []
  let dq = new Date(dMin.getFullYear(), Math.floor(dMin.getMonth() / 3) * 3, 1)
  while (dq.getTime() <= tMax) {
    const ts = dq.getTime()
    if (ts >= tMin - 5 * DAY) ticks.push({ x: xOfT(Math.max(ts, tMin)).toFixed(1) })
    dq = new Date(dq.getFullYear(), dq.getMonth() + 3, 1)
  }
  const dateLabels: { x: string; label: string }[] = []
  let dm = new Date(dMin.getFullYear(), 0, 1)
  while (dm.getTime() <= tMax) {
    const ts = dm.getTime()
    if (ts >= tMin - 5 * DAY) {
      const mm = String(dm.getMonth() + 1).padStart(2, '0')
      dateLabels.push({ x: xOfT(Math.max(ts, tMin)).toFixed(1), label: `${dm.getFullYear()}.${mm}` })
    }
    dm = new Date(dm.getFullYear(), dm.getMonth() + 6, 1)
  }

  return { dots, baseline, area, bands, grid, ups, burstDots, topBurst, ticks, dateLabels }
})

const levelUps = computed(() => props.trajectory.level_ups || [])
</script>

<template>
  <section class="dt">
    <div class="dt__head">
      <h3>成长趋势</h3>
      <span v-if="trajectory.low_frequency" class="dt__pill dt__pill--warn">低频号 · 阶段为粗判</span>
      <span v-else-if="reachedEnd" class="dt__pill dt__pill--ok">已覆盖到第一篇</span>
      <span v-else class="dt__pill dt__pill--warn">早期轨迹可能缺失</span>
    </div>

    <template v-if="model">
      <div class="dt__legend">
        <span class="dt__leg"><i class="dt__sw" style="background:#c9d3db"></i>起步期</span>
        <span class="dt__leg"><i class="dt__sw" style="background:#e8c874"></i>突破期</span>
        <span class="dt__leg"><i class="dt__sw" style="background:#8fc7ab"></i>平稳期</span>
        <span class="dt__leg dt__leg--end"><i class="dt__sw dt__sw--dot"></i>爆发点</span>
      </div>

      <svg :viewBox="`0 0 ${W} ${H}`" class="dt__chart" role="img" aria-label="笔记互动随发布时间的阶段趋势与涨粉拐点">
        <defs>
          <linearGradient id="dtTrendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="var(--color-accent)" stop-opacity="0.16" />
            <stop offset="1" stop-color="var(--color-accent)" stop-opacity="0" />
          </linearGradient>
        </defs>

        <rect v-for="(b, i) in model.bands" :key="`band${i}`" :x="b.x" y="18" :width="b.w" height="170" :fill="b.fill" opacity="0.5" rx="4" />
        <line v-for="(y, i) in model.grid" :key="`grid${i}`" x1="0" :y1="y" :x2="W" :y2="y" stroke="var(--color-paper-3)" stroke-width="1" />

        <path v-if="model.area" :d="model.area" fill="url(#dtTrendFill)" />
        <polyline v-if="model.baseline" :points="model.baseline" fill="none" stroke="var(--color-accent)" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" />

        <circle v-for="(d, i) in model.dots" :key="`dot${i}`" :cx="d.x" :cy="d.y" r="2.3" fill="#c4cad0" />

        <template v-for="(u, i) in model.ups" :key="`up${i}`">
          <line :x1="u.x" y1="10" :x2="u.x" :y2="BOTTOM" stroke="var(--color-accent)" stroke-width="1.2" stroke-dasharray="4 3" opacity="0.55" />
          <rect :x="`${(+u.x - 35).toFixed(1)}`" y="6" width="70" height="17" rx="8.5" fill="var(--color-accent)" />
          <text :x="u.x" y="18" text-anchor="middle" font-size="10.5" font-weight="600" fill="#fff">涨粉拐点</text>
        </template>

        <circle v-for="(b, i) in model.burstDots" :key="`burst${i}`" :cx="b.x" :cy="b.y" r="4.6" fill="var(--color-accent)" stroke="#fff" stroke-width="1.5">
          <title>{{ fmt(b.like) }} 赞</title>
        </circle>
        <text v-if="model.topBurst" :x="model.topBurst.x" :y="model.topBurst.y" text-anchor="middle" font-size="11" font-weight="700" fill="var(--color-accent-ink)">{{ model.topBurst.label }}</text>

        <line x1="0" :y1="BOTTOM" :x2="W" :y2="BOTTOM" stroke="#d4d8dd" stroke-width="1.2" />
        <line v-for="(t, i) in model.ticks" :key="`tick${i}`" :x1="t.x" :y1="BOTTOM" :x2="t.x" :y2="BOTTOM + 4" stroke="#d4d8dd" stroke-width="1" />
        <template v-for="(d, i) in model.dateLabels" :key="`dl${i}`">
          <line :x1="d.x" :y1="GRID_TOP" :x2="d.x" :y2="BOTTOM" stroke="#eceef0" stroke-width="1" />
          <line :x1="d.x" :y1="BOTTOM" :x2="d.x" :y2="BOTTOM + 8" stroke="#b3b9c0" stroke-width="1.3" />
          <text :x="d.x" :y="BOTTOM + 20" text-anchor="middle" font-size="10" font-weight="600" fill="#878f99">{{ d.label }}</text>
        </template>
      </svg>

      <p class="dt__axis-note">横轴为<b>发布时间</b>，纵轴为<b>单篇互动量（赞）</b>；每个圆点是一篇笔记，绿线为互动基线。</p>

      <div v-for="(u, i) in levelUps" :key="`lu${i}`" class="dt__levelup">
        <span class="dt__levelup-mark">↑</span>
        <span>
          <b>{{ u.date }} 涨粉拐点</b>：互动基线 {{ u.from_avg }} → {{ u.to_avg }}
          <template v-if="u.trigger">，疑似由《{{ u.trigger.title }}》（{{ fmt(u.trigger.like) }} 赞）带动。</template>
        </span>
      </div>
    </template>

    <p class="dt__summary">{{ trajectory.summary }}</p>
    <p v-if="model" class="dt__caveat">尾部近月仍在发酵，偏低属正常；拐点为“台阶式跳高”，赞藏替不了涨粉的量、只定位涨粉的时机。</p>

    <div class="dt__attr">
      <template v-if="attribution">
        <div class="dt__attr-cards">
          <p class="dt__attr-title">爆文归因 · 有据的假设，非因果结论</p>
          <div v-for="(h, i) in attribution.hypotheses" :key="i" class="dt__attr-card">
            <div class="dt__attr-claim"><b>{{ h.claim }}</b><span>置信度 {{ h.confidence }}</span></div>
            <p>{{ h.evidence }}</p>
          </div>
        </div>
        <button type="button" class="dt__btn" :disabled="attributionRunning || busy" @click="$emit('run-attribution')">
          {{ attributionRunning ? '重新分析中…' : '重新归因' }}
        </button>
      </template>
      <template v-else-if="trajectory.bursts.length">
        <span class="dt__attr-hint">检测到 {{ trajectory.bursts.length }} 个爆发点，可分析每个阶段“为什么起来”</span>
        <button type="button" class="dt__btn" :disabled="attributionRunning || busy" @click="$emit('run-attribution')">
          {{ attributionRunning ? '归因分析中…' : '运行爆文归因' }}
        </button>
      </template>
      <span v-else class="dt__attr-hint">未检测到显著爆发点：该账号表现平稳。</span>
    </div>
  </section>
</template>

<style scoped>
.dt { background: var(--color-surface); border: 1px solid var(--color-rule); border-radius: 14px; padding: 20px 22px; }
.dt__head { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
.dt__head h3 { margin: 0; font-size: 15px; font-weight: 650; }
.dt__pill { margin-left: auto; padding: 3px 11px; border-radius: 999px; font-size: 11.5px; font-weight: 600; }
.dt__pill--ok { background: #eaf3ee; color: #2f6b54; }
.dt__pill--warn { background: #fdf3e0; color: #8a5a12; }

.dt__legend { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 6px; }
.dt__leg { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--color-ink-2); }
.dt__leg--end { margin-left: auto; }
.dt__sw { width: 9px; height: 9px; border-radius: 2px; flex: 0 0 auto; }
.dt__sw--dot { border-radius: 50%; background: var(--color-accent); }

.dt__chart { width: 100%; height: auto; overflow: visible; }
.dt__axis-note { margin: 8px 2px 0; font-size: 11.5px; color: var(--color-ink-3); line-height: 1.5; }
.dt__axis-note b { color: var(--color-ink-3); font-weight: 600; }

.dt__levelup {
  display: flex;
  gap: 9px;
  align-items: flex-start;
  margin-top: 8px;
  padding: 11px 13px;
  background: var(--color-accent-soft);
  border-radius: 10px;
  font-size: 12.5px;
  color: var(--color-accent-ink);
  line-height: 1.55;
}
.dt__levelup-mark { font-weight: 700; flex: 0 0 auto; line-height: 1.4; }

.dt__summary { margin: 11px 0 0; font-size: 12.5px; color: var(--color-ink-2); line-height: 1.6; }
.dt__caveat { margin: 6px 0 0; font-size: 11.5px; color: var(--color-ink-3); line-height: 1.5; }

.dt__attr { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--color-paper-3); display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.dt__attr-hint { font-size: 12px; color: var(--color-ink-3); }
.dt__btn {
  margin-left: auto;
  height: 32px;
  padding: 0 13px;
  border: 1px solid var(--color-rule);
  border-radius: 9px;
  background: var(--color-surface);
  font-size: 12.5px;
  font-weight: 600;
  color: var(--color-ink-2);
  cursor: pointer;
  transition: background 140ms var(--ease-out);
}
.dt__btn:hover { background: var(--color-paper); }
.dt__btn:disabled { opacity: 0.55; cursor: not-allowed; }
.dt__attr-cards { flex: 1 1 100%; display: flex; flex-direction: column; gap: 9px; }
.dt__attr-title { margin: 0; font-size: 12.5px; font-weight: 650; color: var(--color-ink-2); }
.dt__attr-card { padding: 11px 13px; border: 1px solid var(--color-paper-3); background: var(--color-paper); border-radius: 10px; }
.dt__attr-claim { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.dt__attr-claim b { font-size: 13px; color: var(--color-ink); }
.dt__attr-claim span { font-size: 11px; color: var(--color-ink-3); }
.dt__attr-card p { margin: 4px 0 0; font-size: 12px; color: var(--color-ink-2); line-height: 1.55; }
</style>
