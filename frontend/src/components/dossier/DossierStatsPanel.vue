<script setup lang="ts">
// 档案页·数据面板:账号事实(全量笔记池算)。主指标大数字 + 图文vs视频对比条 + 次指标行。
import { computed } from 'vue'

const props = defineProps<{ stats: Record<string, unknown> }>()

function num(key: string): number | null {
  const v = props.stats[key]
  return typeof v === 'number' ? v : null
}
function fmt(v: number | null): string {
  if (v == null) return '—'
  return v >= 10000 ? `${(v / 10000).toFixed(1)}w` : v >= 1000 ? v.toLocaleString() : String(v)
}

const heroCards = computed(() => {
  const engagement = num('engagement_rate')
  return [
    { label: '篇均点赞', value: fmt(num('average_like')), sub: `均藏 ${fmt(num('average_favorite'))} · 均评 ${fmt(num('average_comment'))}` },
    { label: '藏赞比', value: num('favorite_like_ratio') != null ? String(num('favorite_like_ratio')) : '—', sub: '越高越"值得收藏"，干货信号' },
    { label: '互动率', value: engagement != null ? `${(engagement * 100).toFixed(1)}%` : '—', sub: engagement != null ? '（赞+藏+评）÷ 浏览' : '暂无浏览量数据' },
  ]
})

// 图文 vs 视频均赞对比条。
const modality = computed(() => {
  const by = props.stats.by_modality as Record<string, { count?: number; average_like?: number }> | undefined
  const image = by?.image
  const video = by?.video
  if (!image?.count || !video?.count) return null
  const max = Math.max(image.average_like || 0, video.average_like || 0, 1)
  return [
    { label: '图文', count: image.count, avg: image.average_like || 0, pct: ((image.average_like || 0) / max) * 100 },
    { label: '视频', count: video.count, avg: video.average_like || 0, pct: ((video.average_like || 0) / max) * 100 },
  ]
})

const secondary = computed(() => {
  const freq = props.stats.frequency_info as { pattern?: string; avg_days_between?: number } | undefined
  const trend = props.stats.growth_trend as { summary?: string } | undefined
  const items: { label: string; value: string }[] = []
  if (num('note_count') != null) items.push({ label: '入池笔记', value: `${num('note_count')} 篇（详情级 ${num('full_count') ?? 0}）` })
  if (freq?.pattern) items.push({ label: '发布节奏', value: freq.avg_days_between != null ? `${freq.pattern} · 均隔 ${freq.avg_days_between} 天` : freq.pattern })
  if (trend?.summary) items.push({ label: '近期趋势', value: trend.summary })
  return items
})
</script>

<template>
  <section class="dossier-block">
    <header class="dossier-block__head">
      <h3>数据面板</h3>
      <span class="dossier-block__hint">按全量笔记池计算 · 池更新后自动重算</span>
    </header>

    <div class="ds-hero">
      <div v-for="card in heroCards" :key="card.label" class="ds-hero__card">
        <span class="ds-hero__label">{{ card.label }}</span>
        <strong class="ds-hero__value">{{ card.value }}</strong>
        <span class="ds-hero__sub">{{ card.sub }}</span>
      </div>
    </div>

    <div v-if="modality" class="ds-modality">
      <div v-for="m in modality" :key="m.label" class="ds-modality__row">
        <span class="ds-modality__label">{{ m.label }} · {{ m.count }} 篇</span>
        <span class="ds-modality__track"><span class="ds-modality__bar" :style="{ width: `${Math.max(m.pct, 4)}%` }"></span></span>
        <span class="ds-modality__value">均赞 {{ fmt(m.avg) }}</span>
      </div>
    </div>

    <div v-if="secondary.length" class="ds-secondary">
      <span v-for="item in secondary" :key="item.label" class="ds-secondary__item">
        <em>{{ item.label }}</em>{{ item.value }}
      </span>
    </div>
  </section>
</template>

<style scoped>
.ds-hero { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }
.ds-hero__card {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 14px 16px;
  border-radius: 12px;
  background: linear-gradient(180deg, var(--color-paper-2), var(--color-paper-3));
  border: 1px solid var(--color-rule);
  border-left: 3px solid var(--color-accent);
}
.ds-hero__label { font-size: 12px; color: var(--color-ink-3); letter-spacing: 0.02em; }
.ds-hero__value { font-size: 26px; font-weight: 700; color: var(--color-ink); font-family: var(--font-display); line-height: 1.2; }
.ds-hero__sub { font-size: 11.5px; color: var(--color-ink-3); }

.ds-modality { display: flex; flex-direction: column; gap: 8px; margin-top: 14px; }
.ds-modality__row { display: flex; align-items: center; gap: 10px; }
.ds-modality__label { width: 92px; font-size: 12px; color: var(--color-ink-2); flex-shrink: 0; }
.ds-modality__track { flex: 1; height: 8px; border-radius: 999px; background: var(--color-paper-3); overflow: hidden; }
.ds-modality__bar { display: block; height: 100%; border-radius: 999px; background: var(--color-accent); opacity: 0.85; }
.ds-modality__value { width: 96px; font-size: 12px; color: var(--color-ink-2); text-align: right; flex-shrink: 0; }

.ds-secondary { display: flex; flex-wrap: wrap; gap: 8px 18px; margin-top: 14px; padding-top: 12px; border-top: 1px dashed var(--color-rule); }
.ds-secondary__item { font-size: 12.5px; color: var(--color-ink-2); }
.ds-secondary__item em { font-style: normal; color: var(--color-ink-3); margin-right: 6px; font-size: 12px; }
</style>
