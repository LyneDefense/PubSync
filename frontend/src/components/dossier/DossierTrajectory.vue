<script setup lang="ts">
// 档案页·成长轨迹(招牌):阶段带 + 基线台阶(分桶中位) + 散点 + 涨粉拐点 + 爆文归因。
// 诚实:低频号提示粗判;赞藏替不了涨粉的量,只标拐点(台阶式跳高)。
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

const W = 640
const H = 150
const PAD_T = 20
const PAD_B = 22

function bandClass(label: string): string {
  if (label.includes('起步')) return 'phase--start'
  if (label.includes('突破')) return 'phase--break'
  if (label.includes('滑坡')) return 'phase--drop'
  return 'phase--stable'
}

const model = computed(() => {
  const t = props.trajectory
  const pts = t.points || []
  if (pts.length < 2) return null
  const times = pts.map((p) => Date.parse(p.date))
  const tMin = Math.min(...times)
  const span = Math.max(Math.max(...times) - tMin, 1)
  const maxLike = Math.max(...pts.map((p) => p.like), 1)
  const xOf = (d: string) => ((Date.parse(d) - tMin) / span) * W
  const yOf = (like: number) => PAD_T + (1 - like / maxLike) * (H - PAD_T - PAD_B)

  const dots = pts.map((p) => ({ x: xOf(p.date), y: yOf(p.like), like: p.like, date: p.date, title: p.title }))
  const burstKeys = new Set(t.bursts.map((b) => `${b.date}|${b.like}`))
  const bursts = dots.filter((d) => burstKeys.has(`${d.date}|${d.like}`))
  const base = (t.buckets || []).map((b) => ({ x: (xOf(b.start) + xOf(b.end)) / 2, y: yOf(b.median_like) }))
  const baseline = base.length > 1 ? base.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ') : ''
  const bands = (t.phases || []).map((ph) => ({
    x: xOf(ph.start), w: Math.max(xOf(ph.end) - xOf(ph.start), 3),
    label: ph.label, cls: bandClass(ph.label),
  }))
  const ups = (t.level_ups || []).map((u) => ({ x: xOf(u.date), date: u.date }))
  const years = Array.from(new Set(pts.map((p) => p.date.slice(0, 4)))).map((y) => ({ y, x: xOf(`${y}-06-15`) }))
  return { dots, bursts, baseline, bands, ups, years }
})

const levelUps = computed(() => props.trajectory.level_ups || [])
</script>

<template>
  <section class="dossier-block">
    <header class="dossier-block__head">
      <h3>成长趋势</h3>
      <span v-if="trajectory.low_frequency" class="dossier-chip dossier-chip--warn">低频号 · 阶段为粗判</span>
      <span v-else-if="reachedEnd" class="dossier-chip dossier-chip--ok">已覆盖到第一篇</span>
      <span v-else class="dossier-chip dossier-chip--warn">早期轨迹可能缺失</span>
    </header>

    <template v-if="model">
      <svg :viewBox="`0 0 ${W} ${H}`" class="dt-chart" role="img" aria-label="笔记互动随时间的阶段与拐点">
        <g>
          <rect v-for="(b, i) in model.bands" :key="`band${i}`" :x="b.x" :y="PAD_T - 6" :width="b.w" :height="H - PAD_T - PAD_B + 6" class="dt-band" :class="b.cls" />
          <text v-for="(b, i) in model.bands" :key="`bl${i}`" :x="b.x + b.w / 2" :y="PAD_T - 9" text-anchor="middle" class="dt-band-label">{{ b.label }}</text>
        </g>
        <polyline v-if="model.baseline" :points="model.baseline" fill="none" stroke="var(--color-accent)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
        <g>
          <circle v-for="(d, i) in model.dots" :key="`d${i}`" :cx="d.x" :cy="d.y" r="2.4" fill="var(--color-ink-3)" opacity="0.55" />
        </g>
        <g>
          <line v-for="(u, i) in model.ups" :key="`ul${i}`" :x1="u.x" :y1="PAD_T - 6" :x2="u.x" :y2="H - PAD_B" stroke="var(--color-accent)" stroke-width="1" stroke-dasharray="3 3" opacity="0.6" />
        </g>
        <g>
          <circle v-for="(b, i) in model.bursts" :key="`b${i}`" :cx="b.x" :cy="b.y" r="4" fill="var(--color-accent)">
            <title>{{ b.date }} · {{ b.like }} 赞 · {{ b.title }}</title>
          </circle>
        </g>
        <text v-for="(yr, i) in model.years" :key="`y${i}`" :x="yr.x" :y="H - 6" text-anchor="middle" class="dt-year">{{ yr.y }}</text>
      </svg>

      <div v-for="(u, i) in levelUps" :key="`up${i}`" class="dt-levelup">
        <i class="dt-levelup__mark">↑</i>
        <span>
          <strong>{{ u.date }} 涨粉拐点</strong>：基线 {{ u.from_avg }} → {{ u.to_avg }}
          <template v-if="u.trigger">，疑似由《{{ u.trigger.title }}》（{{ u.trigger.like }} 赞）带动</template>
        </span>
      </div>
    </template>

    <p class="dt-summary">{{ trajectory.summary }}</p>
    <p v-if="model" class="dt-caveat">曲线尾部近月仍在发酵，偏低属正常；拐点为“台阶式跳高”，赞藏替不了涨粉的量、只定位涨粉的时机。</p>

    <div class="dt-attr">
      <template v-if="attribution">
        <h4>爆文归因（有据的假设，非因果结论）</h4>
        <ul>
          <li v-for="(h, i) in attribution.hypotheses" :key="i">
            <strong>{{ h.claim }}</strong>
            <span class="dt-conf">置信度 {{ h.confidence }}</span>
            <p>{{ h.evidence }}</p>
          </li>
        </ul>
        <button type="button" class="ghost" :disabled="attributionRunning || busy" @click="$emit('run-attribution')">
          {{ attributionRunning ? '重新分析中…' : '重新归因' }}
        </button>
      </template>
      <template v-else-if="trajectory.bursts.length">
        <span class="dossier-block__hint">检测到 {{ trajectory.bursts.length }} 个爆发点，可分析每个阶段“为什么起来”</span>
        <button type="button" class="ghost" :disabled="attributionRunning || busy" @click="$emit('run-attribution')">
          {{ attributionRunning ? '归因分析中…' : '运行爆文归因' }}
        </button>
      </template>
      <span v-else class="dossier-block__hint">未检测到显著爆发点：该账号表现平稳。</span>
    </div>
  </section>
</template>

<style scoped>
.dt-chart { width: 100%; height: auto; margin-top: 8px; }
.dt-band { opacity: 0.4; }
.dt-band.phase--start { fill: var(--color-paper-3); }
.dt-band.phase--break { fill: #fbeecf; }
.dt-band.phase--stable { fill: var(--color-ok-bg); }
.dt-band.phase--drop { fill: #fceceb; }
.dt-band-label { font-size: 10px; fill: var(--color-ink-3); }
.dt-year { font-size: 9.5px; fill: var(--color-ink-3); }
.dt-levelup { display: flex; gap: 8px; align-items: flex-start; margin-top: 10px; padding: 9px 12px; background: var(--color-accent-soft); border-radius: 8px; font-size: 12.5px; color: var(--color-accent-ink); line-height: 1.5; }
.dt-levelup__mark { font-style: normal; font-weight: 700; flex-shrink: 0; }
.dt-summary { margin: 10px 0 0; font-size: 12.5px; color: var(--color-ink-2); }
.dt-caveat { margin: 6px 0 0; font-size: 11.5px; color: var(--color-ink-3); line-height: 1.5; }
.dt-attr { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--color-rule); display: flex; flex-direction: column; gap: 8px; align-items: flex-start; }
.dt-attr h4 { margin: 0; font-size: 13px; }
.dt-attr ul { margin: 0; padding: 0 0 0 16px; display: flex; flex-direction: column; gap: 8px; }
.dt-attr li p { margin: 2px 0 0; font-size: 12px; color: var(--color-ink-2); }
.dt-conf { margin-left: 8px; font-size: 11px; color: var(--color-ink-3); }
</style>
