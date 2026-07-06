<script setup lang="ts">
// 档案页·成长趋势(两张小图):
//   图A 互动基线走势 —— 对数 Y 轴 + 分桶中位基线 + P25–P75 分位带 + 真实时间轴(季度刻度 + 6 月日期);
//   图B 表现分布 —— 对数直方图 + 中位/分位标记,看"大部分笔记什么水平、头部多强"。
// 诚实:赞≠粉(互动代理);阶段只当一句文字,不画带;涨粉拐点概念退役。
import { computed } from 'vue'
import type { DossierTrajectory } from '../../api/types'

const props = defineProps<{ trajectory: DossierTrajectory; reachedEnd: boolean }>()

const W = 660
const H = 178
const PAD_T = 16
const PAD_B = 44
const BOTTOM = H - PAD_B // 134
const GRID_TOP = 12
const DAY = 86400000
// 图B
const BW = 644
const BX = 8
const BTOP = 12
const BBOT = 96

function fmt(v: number): string {
  return v >= 10000 ? `${(v / 10000).toFixed(1)}w` : v.toLocaleString()
}
function log10(v: number): number {
  return Math.log10(Math.max(v, 1))
}

// 图A：互动基线走势(对数 Y + 分位带)
const chartA = computed(() => {
  const t = props.trajectory
  const bk = (t.buckets || []).slice().sort((a, b) => a.start.localeCompare(b.start))
  if (bk.length < 2) return null
  const pts = t.points || []

  const times = [...bk.map((b) => Date.parse(b.start)), ...bk.map((b) => Date.parse(b.end))]
  const tMin = Math.min(...times)
  const tMax = Math.max(...times)
  const span = Math.max(tMax - tMin, 1)

  const yvals = [...bk.map((b) => b.p25), ...bk.map((b) => b.p75), ...(t.bursts || []).map((x) => x.like)].filter((v) => v > 0)
  const lmin = log10(Math.min(...yvals))
  const lmax = log10(Math.max(...yvals, 10))
  const lspan = Math.max(lmax - lmin, 0.3)

  const xOfT = (ms: number) => ((ms - tMin) / span) * (W - 10) + 5
  const xOf = (d: string) => xOfT(Date.parse(d))
  const yOf = (like: number) => PAD_T + (1 - (log10(like) - lmin) / lspan) * (BOTTOM - PAD_T)
  const cx = (b: { start: string; end: string }) => (xOf(b.start) + xOf(b.end)) / 2

  const upper = bk.map((b) => ({ x: cx(b), y: yOf(b.p75) }))
  const lower = bk.map((b) => ({ x: cx(b), y: yOf(b.p25) }))
  const med = bk.map((b) => ({ x: cx(b), y: yOf(b.median_like) }))
  const band =
    `M ${upper.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' L ')} ` +
    `L ${lower.slice().reverse().map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' L ')} Z`
  const medLine = med.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
  const dots = pts.map((p) => ({ x: xOf(p.date).toFixed(1), y: yOf(p.like).toFixed(1) }))

  const topB = (t.bursts || []).slice().sort((a, b) => b.like - a.like)[0]
  const burst = topB
    ? { x: xOf(topB.date).toFixed(1), y: yOf(topB.like).toFixed(1), ty: (yOf(topB.like) - 10).toFixed(1), label: `${fmt(topB.like)} 赞` }
    : null

  // 时间轴:季度小刻度 + 每 6 个月日期
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
  return { band, medLine, dots, burst, ticks, dateLabels }
})

// 图B：表现分布(对数直方图)
const chartB = computed(() => {
  const d = props.trajectory.distribution
  if (!d || !d.count || !d.log_bins?.length) return null
  const bins = d.log_bins
  const maxC = Math.max(...bins.map((b) => b.count), 1)
  const lmin = log10(d.min ?? 1)
  const lmax = log10(d.max ?? 10)
  const lspan = Math.max(lmax - lmin, 0.3)
  const xOf = (v: number) => BX + ((log10(v) - lmin) / lspan) * BW
  const bw = BW / bins.length
  const bars = bins.map((b, i) => {
    const h = (b.count / maxC) * (BBOT - BTOP)
    return { x: (BX + i * bw + 1).toFixed(1), w: Math.max(bw - 2, 1).toFixed(1), y: (BBOT - h).toFixed(1), h: h.toFixed(1), count: b.count, lo: b.lo, hi: b.hi }
  })
  const mark = (v: number | undefined) => (v == null ? null : xOf(v).toFixed(1))
  return {
    bars,
    medX: mark(d.median),
    p25X: mark(d.p25),
    p75X: mark(d.p75),
    p90X: mark(d.p90),
    p25: d.p25 ?? 0, median: d.median ?? 0, p75: d.p75 ?? 0, p90: d.p90 ?? 0, max: d.max ?? 0, count: d.count,
  }
})
</script>

<template>
  <section class="dt">
    <div class="dt__head">
      <h3>成长趋势</h3>
      <span v-if="trajectory.low_frequency" class="dt__pill dt__pill--warn">低频号 · 阶段为粗判</span>
      <span v-else-if="reachedEnd" class="dt__pill dt__pill--ok">已覆盖到第一篇</span>
      <span v-else class="dt__pill dt__pill--warn">早期轨迹可能缺失</span>
    </div>

    <!-- 图A：互动基线走势 -->
    <div class="dt__sub">图A · 互动基线走势<span>(对数刻度 · 阴影为 P25–P75 典型区间)</span><span class="dt__info" tabindex="0" role="img" aria-label="P25–P75 是什么" title="P25–P75 = 第 25 到第 75 百分位。把这段时间的笔记按赞数从低到高排,中间那 50% 落在的赞数区间就是 P25–P75。它避开偶发爆款和个别冷门,代表这个账号「正常水平」的波动范围;区间越窄=发挥越稳。">i</span></div>
    <template v-if="chartA">
      <svg :viewBox="`0 0 ${W} ${H}`" class="dt__chart" role="img" aria-label="互动基线随发布时间的走势与典型区间">
        <line v-for="(y, i) in [0.25, 0.5, 0.75]" :key="`g${i}`" x1="0" :y1="PAD_T + y * (BOTTOM - PAD_T)" :x2="W" :y2="PAD_T + y * (BOTTOM - PAD_T)" stroke="var(--color-paper-3)" stroke-width="1" />
        <path :d="chartA.band" fill="var(--color-accent)" opacity="0.14" />
        <circle v-for="(dot, i) in chartA.dots" :key="`d${i}`" :cx="dot.x" :cy="dot.y" r="2" fill="#c4cad0" opacity="0.5" />
        <polyline :points="chartA.medLine" fill="none" stroke="var(--color-accent)" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" />
        <template v-if="chartA.burst">
          <circle :cx="chartA.burst.x" :cy="chartA.burst.y" r="4.4" fill="var(--color-accent)" stroke="#fff" stroke-width="1.5" />
          <text :x="chartA.burst.x" :y="chartA.burst.ty" text-anchor="middle" font-size="11" font-weight="700" fill="var(--color-accent-ink)">{{ chartA.burst.label }}</text>
        </template>
        <line x1="0" :y1="BOTTOM" :x2="W" :y2="BOTTOM" stroke="#d4d8dd" stroke-width="1.2" />
        <line v-for="(tk, i) in chartA.ticks" :key="`t${i}`" :x1="tk.x" :y1="BOTTOM" :x2="tk.x" :y2="BOTTOM + 4" stroke="#d4d8dd" stroke-width="1" />
        <template v-for="(dl, i) in chartA.dateLabels" :key="`l${i}`">
          <line :x1="dl.x" :y1="GRID_TOP" :x2="dl.x" :y2="BOTTOM" stroke="#eceef0" stroke-width="1" />
          <line :x1="dl.x" :y1="BOTTOM" :x2="dl.x" :y2="BOTTOM + 8" stroke="#b3b9c0" stroke-width="1.3" />
          <text :x="dl.x" :y="BOTTOM + 20" text-anchor="middle" font-size="10" font-weight="600" fill="#878f99">{{ dl.label }}</text>
        </template>
      </svg>
      <p class="dt__axis-note">横轴为<b>发布时间</b>,纵轴为<b>单篇互动量(赞,对数)</b>;绿线为互动中位基线,阴影是每段 P25–P75 典型区间。</p>
    </template>
    <p v-else class="dt__degraded">有时间的笔记太少,暂不画走势。</p>

    <!-- 图B：表现分布 -->
    <div class="dt__sub dt__sub--gap">图B · 表现分布<span>(每篇笔记按赞数落入对数区间)</span></div>
    <template v-if="chartB">
      <svg viewBox="0 0 660 118" class="dt__chart" role="img" aria-label="笔记按赞数的分布直方图">
        <rect v-for="(bar, i) in chartB.bars" :key="`b${i}`" :x="bar.x" :y="bar.y" :width="bar.w" :height="bar.h" rx="1.5" fill="var(--color-accent)" opacity="0.5">
          <title>{{ fmt(bar.lo) }}–{{ fmt(bar.hi) }} 赞 · {{ bar.count }} 篇</title>
        </rect>
        <line :x1="BX" :y1="BBOT" :x2="BX + BW" :y2="BBOT" stroke="#d4d8dd" stroke-width="1" />
        <template v-if="chartB.medX">
          <line :x1="chartB.medX" y1="6" :x2="chartB.medX" :y2="BBOT" stroke="var(--color-accent-ink)" stroke-width="1.4" stroke-dasharray="4 3" />
          <text :x="chartB.medX" y="112" text-anchor="middle" font-size="10" font-weight="700" fill="var(--color-accent-ink)">中位 {{ fmt(chartB.median) }}</text>
        </template>
        <line v-if="chartB.p90X" :x1="chartB.p90X" y1="6" :x2="chartB.p90X" :y2="BBOT" stroke="#b3b9c0" stroke-width="1" stroke-dasharray="2 3" />
        <text v-if="chartB.p90X" :x="chartB.p90X" y="112" text-anchor="middle" font-size="10" fill="#878f99">P90 {{ fmt(chartB.p90) }}</text>
      </svg>
      <p class="dt__axis-note">大部分笔记 <b>{{ fmt(chartB.p25) }}–{{ fmt(chartB.p75) }}</b> 赞(中位 {{ fmt(chartB.median) }});头部到 <b>{{ fmt(chartB.p90) }}+</b>,最高 {{ fmt(chartB.max) }}。</p>
    </template>
    <p v-else class="dt__degraded">笔记太少,暂不画分布。</p>

    <p class="dt__summary">{{ trajectory.summary }}</p>
    <p class="dt__caveat">赞是互动代理、不等于涨粉;小红书无浏览量,推流/曝光看不到。想学"怎么写"看下方创作画像。</p>
  </section>
</template>

<style scoped>
.dt { background: var(--color-surface); border: 1px solid var(--color-rule); border-radius: 14px; padding: 20px 22px; }
.dt__head { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; flex-wrap: wrap; }
.dt__head h3 { margin: 0; font-size: 15px; font-weight: 650; }
.dt__pill { margin-left: auto; padding: 3px 11px; border-radius: 999px; font-size: 11.5px; font-weight: 600; }
.dt__pill--ok { background: #eaf3ee; color: #2f6b54; }
.dt__pill--warn { background: #fdf3e0; color: #8a5a12; }

.dt__sub { font-size: 12.5px; font-weight: 600; color: var(--color-ink-2); margin: 4px 0 2px; }
.dt__sub--gap { margin-top: 16px; padding-top: 14px; border-top: 1px dashed var(--color-rule); }
.dt__sub span { font-weight: 400; color: var(--color-ink-3); font-size: 11.5px; margin-left: 6px; }
.dt__info {
  display: inline-grid; place-items: center; width: 14px; height: 14px; margin-left: 5px;
  border-radius: 50%; border: 1px solid var(--color-ink-3); color: var(--color-ink-3);
  font-size: 9.5px; font-weight: 700; font-style: normal; line-height: 1; cursor: help; vertical-align: middle;
}
.dt__info:hover, .dt__info:focus-visible { border-color: var(--color-accent); color: var(--color-accent); outline: none; }

.dt__chart { width: 100%; height: auto; overflow: visible; }
.dt__axis-note { margin: 6px 2px 0; font-size: 11.5px; color: var(--color-ink-3); line-height: 1.5; }
.dt__axis-note b { color: var(--color-ink-2); font-weight: 600; }
.dt__degraded { margin: 8px 0; font-size: 12px; color: var(--color-ink-3); }

.dt__summary { margin: 12px 0 0; font-size: 12.5px; color: var(--color-ink-2); line-height: 1.6; }
.dt__caveat { margin: 6px 0 0; font-size: 11.5px; color: var(--color-ink-3); line-height: 1.5; }
</style>
