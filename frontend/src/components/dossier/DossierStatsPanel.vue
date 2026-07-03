<script setup lang="ts">
// 档案页·数据面板:账号事实(全量池算)。覆盖率对 + 主指标 + 图文/视频环图。互动率已下线(小红书无浏览量)。
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

// 共 N · 已收录 M · 覆盖率。总数拿不到时:翻到底=已全部,否则=未翻到底(诚实)。
const coverage = computed(() => {
  const total = num('note_total')
  const got = num('note_count') ?? 0
  const pct = total && total > 0 ? Math.min(100, Math.round((got / total) * 100)) : null
  return { total, got, pct, reachedEnd: props.stats.reached_end === true }
})

const tiles = computed(() => [
  { label: '获赞与收藏', value: fmt(num('liked_collected_count')), sub: '账号累计（全部笔记）' },
  { label: '篇均点赞', value: fmt(num('average_like')), sub: `均藏 ${fmt(num('average_favorite'))} · 均评 ${fmt(num('average_comment'))}` },
  { label: '赞藏比', value: num('favorite_like_ratio') != null ? String(num('favorite_like_ratio')) : '—', sub: '越高越"值得收藏"' },
])

// 图文 vs 视频环图(按已收录计)。
const modality = computed(() => {
  const by = props.stats.by_modality as Record<string, { count?: number; average_like?: number }> | undefined
  const image = by?.image?.count || 0
  const video = by?.video?.count || 0
  const total = image + video
  if (!total) return null
  const videoPct = (video / total) * 100
  const C = 2 * Math.PI * 46
  return {
    total, image, video,
    imageAvg: by?.image?.average_like || 0,
    videoAvg: by?.video?.average_like || 0,
    videoDash: (videoPct / 100) * C,
    imageDash: ((100 - videoPct) / 100) * C,
    imageOffset: -(videoPct / 100) * C,
    circumference: C,
    videoPctLabel: Math.round(videoPct),
  }
})
</script>

<template>
  <section class="dossier-block">
    <header class="dossier-block__head">
      <h3>数据面板</h3>
      <span class="dossier-block__hint">按全量笔记池计算 · 池更新后自动重算</span>
    </header>

    <div class="ds-coverage">
      <span class="ds-coverage__text">
        <template v-if="coverage.total != null">共 {{ coverage.total }} 篇 · 已收录 {{ coverage.got }} 篇</template>
        <template v-else-if="coverage.reachedEnd">已收录 {{ coverage.got }} 篇 · 已翻到底（即全部）</template>
        <template v-else>已收录 {{ coverage.got }} 篇 · 未翻到底</template>
      </span>
      <span v-if="coverage.pct != null" class="ds-coverage__track"><span class="ds-coverage__bar" :style="{ width: `${coverage.pct}%` }"></span></span>
      <span v-if="coverage.pct != null" class="ds-coverage__pct">覆盖 {{ coverage.pct }}%</span>
    </div>

    <div class="ds-tiles">
      <div v-for="t in tiles" :key="t.label" class="ds-tile">
        <span class="ds-tile__label">{{ t.label }}</span>
        <strong class="ds-tile__value">{{ t.value }}</strong>
        <span class="ds-tile__sub">{{ t.sub }}</span>
      </div>
    </div>

    <div v-if="modality" class="ds-modality">
      <svg viewBox="0 0 120 120" class="ds-donut" role="img" :aria-label="`内容形态：视频 ${modality.video} 篇，图文 ${modality.image} 篇`">
        <g transform="rotate(-90 60 60)" fill="none" stroke-width="15">
          <circle cx="60" cy="60" r="46" stroke="#3d84d6" :stroke-dasharray="`${modality.videoDash} ${modality.circumference}`"></circle>
          <circle cx="60" cy="60" r="46" stroke="#1d9e75" :stroke-dasharray="`${modality.imageDash} ${modality.circumference}`" :stroke-dashoffset="modality.imageOffset"></circle>
        </g>
        <text x="60" y="57" text-anchor="middle" font-size="19" font-weight="700" fill="var(--color-ink)">{{ modality.total }}</text>
        <text x="60" y="73" text-anchor="middle" font-size="10" fill="var(--color-ink-3)">已收录</text>
      </svg>
      <div class="ds-legend">
        <span class="ds-legend__row"><i class="ds-dot ds-dot--v"></i>视频笔记 · {{ modality.video }} 篇 · 均赞 {{ fmt(modality.videoAvg) }}</span>
        <span class="ds-legend__row"><i class="ds-dot ds-dot--i"></i>图文笔记 · {{ modality.image }} 篇 · 均赞 {{ fmt(modality.imageAvg) }}</span>
        <span class="ds-legend__hint">类型随列表逐篇判定 · 按已收录 {{ modality.total }} 篇计</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.ds-coverage { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.ds-coverage__text { font-size: 13px; color: var(--color-ink); white-space: nowrap; }
.ds-coverage__track { flex: 1; height: 6px; border-radius: 999px; background: var(--color-paper-3); overflow: hidden; }
.ds-coverage__bar { display: block; height: 100%; border-radius: 999px; background: var(--color-accent); }
.ds-coverage__pct { font-size: 12px; color: var(--color-ink-3); font-variant-numeric: tabular-nums; white-space: nowrap; }

.ds-tiles { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.ds-tile {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 12px 14px;
  border-radius: 10px;
  background: linear-gradient(180deg, var(--color-paper-2), var(--color-paper-3));
  border: 1px solid var(--color-rule);
  border-left: 3px solid var(--color-accent);
}
.ds-tile__label { font-size: 12px; color: var(--color-ink-3); }
.ds-tile__value { font-size: 24px; font-weight: 700; color: var(--color-ink); font-family: var(--font-display); line-height: 1.25; }
.ds-tile__sub { font-size: 11.5px; color: var(--color-ink-3); }

.ds-modality { display: flex; align-items: center; gap: 20px; margin-top: 16px; padding-top: 14px; border-top: 1px dashed var(--color-rule); }
.ds-donut { width: 96px; height: 96px; flex-shrink: 0; }
.ds-legend { display: flex; flex-direction: column; gap: 8px; font-size: 13px; }
.ds-legend__row { display: flex; align-items: center; gap: 8px; color: var(--color-ink-2); }
.ds-dot { width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0; }
.ds-dot--v { background: #3d84d6; }
.ds-dot--i { background: #1d9e75; }
.ds-legend__hint { font-size: 11.5px; color: var(--color-ink-3); }

@media (max-width: 560px) {
  .ds-tiles { grid-template-columns: 1fr; }
}
</style>
