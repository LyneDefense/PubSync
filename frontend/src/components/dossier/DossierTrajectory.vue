<script setup lang="ts">
// 档案页·成长轨迹:内容表现曲线(SVG 折线,近似涨粉轨迹)+ 阶段 chips + 爆发点 + 爆文归因。
// 诚实降级:时间样本不足只给说明;没翻到底给覆盖提示;无爆发点不提供归因入口。
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
const H = 120

const chart = computed(() => {
  const pts = props.trajectory.points
  if (pts.length < 2) return null
  const maxLike = Math.max(...pts.map((p) => p.like), 1)
  const step = W / (pts.length - 1)
  const xy = pts.map((p, i) => ({ x: i * step, y: H - (p.like / maxLike) * (H - 10) - 4, like: p.like, date: p.date, title: p.title }))
  const burstIds = new Set(props.trajectory.bursts.map((b) => `${b.date}|${b.like}`))
  return {
    line: xy.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' '),
    bursts: xy.filter((p) => burstIds.has(`${p.date}|${p.like}`)),
    maxLike,
  }
})
</script>

<template>
  <section class="dossier-block">
    <header class="dossier-block__head">
      <h3>成长轨迹</h3>
      <span v-if="reachedEnd" class="dossier-chip dossier-chip--ok">已覆盖到第一篇</span>
      <span v-else class="dossier-chip dossier-chip--warn">仅覆盖最近一段，早期轨迹缺失</span>
    </header>

    <template v-if="chart">
      <svg :viewBox="`0 0 ${W} ${H}`" class="dossier-traj__chart" role="img" aria-label="笔记互动随时间曲线">
        <polyline :points="chart.line" fill="none" stroke="var(--color-accent)" stroke-width="2" stroke-linejoin="round" />
        <circle v-for="(b, i) in chart.bursts" :key="i" :cx="b.x" :cy="b.y" r="4" fill="var(--color-danger)">
          <title>{{ b.date }} · {{ b.like }} 赞 · {{ b.title }}</title>
        </circle>
      </svg>
      <div class="dossier-traj__chips">
        <span v-for="(phase, i) in trajectory.phases" :key="i" class="dossier-chip">
          {{ phase.label }} {{ phase.start.slice(0, 7) }}–{{ phase.end.slice(0, 7) }} · 均赞 {{ phase.avg_like }}
        </span>
        <span v-for="(b, i) in trajectory.bursts.slice(0, 3)" :key="`b${i}`" class="dossier-chip dossier-chip--burst">
          爆发 {{ b.date }} · {{ b.like }} 赞
        </span>
      </div>
    </template>
    <p class="dossier-traj__summary">{{ trajectory.summary }}</p>

    <div class="dossier-traj__attr">
      <template v-if="attribution">
        <h4>爆文归因（基于数据的假设，非因果结论）</h4>
        <ul>
          <li v-for="(h, i) in attribution.hypotheses" :key="i">
            <strong>{{ h.claim }}</strong>
            <span class="dossier-traj__conf">置信度 {{ h.confidence }}</span>
            <p>{{ h.evidence }}</p>
          </li>
        </ul>
        <p v-if="attribution.summary" class="dossier-traj__attr-summary">{{ attribution.summary }}</p>
        <button type="button" class="ghost" :disabled="attributionRunning || busy" @click="$emit('run-attribution')">
          {{ attributionRunning ? '重新分析中…' : '重新归因' }}
        </button>
      </template>
      <template v-else-if="trajectory.bursts.length">
        <span class="dossier-block__hint">检测到 {{ trajectory.bursts.length }} 个爆发点，可分析她做对了什么</span>
        <button type="button" class="ghost" :disabled="attributionRunning || busy" @click="$emit('run-attribution')">
          {{ attributionRunning ? '归因分析中…' : '运行爆文归因' }}
        </button>
      </template>
      <span v-else class="dossier-block__hint">未检测到显著爆发点：该账号增长平稳。</span>
    </div>
  </section>
</template>

<style scoped>
.dossier-traj__chart { width: 100%; height: auto; margin-top: 4px; }
.dossier-traj__chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.dossier-traj__summary { margin: 10px 0 0; font-size: 12px; color: var(--color-ink-2); }
.dossier-traj__attr { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--color-rule); display: flex; flex-direction: column; gap: 8px; align-items: flex-start; }
.dossier-traj__attr h4 { margin: 0; font-size: 13px; }
.dossier-traj__attr ul { margin: 0; padding: 0 0 0 16px; display: flex; flex-direction: column; gap: 8px; }
.dossier-traj__attr li p { margin: 2px 0 0; font-size: 12px; color: var(--color-ink-2); }
.dossier-traj__conf { margin-left: 8px; font-size: 11px; color: var(--color-ink-3); }
.dossier-traj__attr-summary { margin: 0; font-size: 12px; color: var(--color-ink-2); }
</style>
