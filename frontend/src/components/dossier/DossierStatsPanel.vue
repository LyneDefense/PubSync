<script setup lang="ts">
// 档案页·数据面板:账号事实(全量笔记池算,非蒸馏样本)。stats 为 null 时父级不渲染本组件。
import { computed } from 'vue'

const props = defineProps<{ stats: Record<string, unknown> }>()

function num(key: string): number | null {
  const v = props.stats[key]
  return typeof v === 'number' ? v : null
}

const engagement = computed(() => {
  const v = num('engagement_rate')
  return v == null ? null : `${(v * 100).toFixed(1)}%`
})
const freqPattern = computed(() => {
  const info = props.stats.frequency_info as { pattern?: string; avg_days_between?: number } | undefined
  if (!info?.pattern) return null
  return info.avg_days_between != null ? `${info.pattern}（均隔 ${info.avg_days_between} 天）` : info.pattern
})
const trendSummary = computed(() => {
  const info = props.stats.growth_trend as { summary?: string } | undefined
  return info?.summary || null
})
const modalityCompare = computed(() => (props.stats.modality_comparison as string) || null)

const cards = computed(() => {
  const items: { label: string; value: string }[] = []
  const push = (label: string, value: string | number | null) => {
    if (value != null && value !== '') items.push({ label, value: String(value) })
  }
  push('入池笔记', num('note_count'))
  push('均赞', num('average_like'))
  push('均藏', num('average_favorite'))
  push('藏赞比', num('favorite_like_ratio'))
  push('互动率', engagement.value)
  push('发布节奏', freqPattern.value)
  return items
})
</script>

<template>
  <section class="dossier-block">
    <header class="dossier-block__head">
      <h3>数据面板</h3>
      <span class="dossier-block__hint">从全量笔记池计算，笔记池更新后自动重算</span>
    </header>
    <div class="dossier-stats__grid">
      <div v-for="card in cards" :key="card.label" class="dossier-stats__card">
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
      </div>
    </div>
    <p v-if="modalityCompare || trendSummary" class="dossier-stats__footnote">
      <template v-if="modalityCompare">{{ modalityCompare }}。</template>
      <template v-if="trendSummary">{{ trendSummary }}。</template>
    </p>
  </section>
</template>

<style scoped>
.dossier-stats__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 10px;
}
.dossier-stats__card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--color-paper-3);
}
.dossier-stats__card span { font-size: 12px; color: var(--color-ink-3); }
.dossier-stats__card strong { font-size: 17px; color: var(--color-ink); font-weight: 600; }
.dossier-stats__footnote { margin: 10px 0 0; font-size: 12px; color: var(--color-ink-2); }
</style>
