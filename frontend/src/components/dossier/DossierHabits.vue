<script setup lang="ts">
// 档案页·运营习惯:事实主体(建档算,全量池)+ 解读(从事实推的一句话,标「解读」区分)。
// 模态偏好(视频vs图文均赞)已在数据面板占比条展示,这里不重复。
import { computed } from 'vue'
import type { DossierHabits } from '../../api/types'

const props = defineProps<{ habits: DossierHabits }>()

function pct(v: number | null): string {
  return v == null ? '—' : `${Math.round(v * 100)}%`
}

const rows = computed(() => {
  const h = props.habits
  const out: { label: string; value: string; interp: string }[] = []

  const days = h.posting_rhythm?.avg_days_between
  if (h.posting_rhythm?.pattern) {
    out.push({
      label: '发布节奏',
      value: days != null ? `${h.posting_rhythm.pattern} · 均隔 ${days} 天` : h.posting_rhythm.pattern,
      interp: days == null ? '' : days > 20 ? '低频精耕，攒一篇大的而非高频铺量。' : days > 7 ? '稳定更新，保持露出。' : '高频铺量，靠量取胜。'
    })
  }

  const g = h.genre
  if (g && g.total > 0) {
    out.push({
      label: '内容体裁',
      value: `清单体 ${g.listicle} / ${g.total} 篇`,
      interp: (g.ratio ?? 0) > 0.4 ? '偏清单体，信息密度适中、便于收藏转发。' : '以非清单体为主，叙事/观点承载更多。'
    })
  }

  const cg = h.comment_guide
  if (cg && cg.total > 0) {
    out.push({
      label: '评论引导',
      value: `${pct(cg.ratio)} 笔记主动引导（${cg.count}/${cg.total}）`,
      interp: (cg.ratio ?? 0) > 0.3 ? '常在正文/口播主动引导互动。' : (cg.ratio ?? 0) > 0 ? '偶尔引导互动。' : '较少主动引导，靠内容自然发酵。'
    })
  }

  const ar = h.author_reply
  if (ar) {
    out.push({
      label: '博主回复习惯',
      value: ar.ratio == null ? '暂无数据' : `有评论的笔记 ${pct(ar.ratio)} 亲自回复（${ar.replied}/${ar.with_comments}）`,
      interp: ar.ratio == null ? '回复数据待新一轮采集补齐。' : ar.ratio > 0.3 ? '常下场回复读者，经营评论区。' : ar.ratio > 0 ? '偶尔回复读者。' : '较少回复评论。'
    })
  }
  return out
})
</script>

<template>
  <section v-if="rows.length" class="dh">
    <div class="dh__head">
      <h3>运营习惯</h3>
      <span class="dh__sub">事实 + 解读 · 依据 {{ habits.coverage?.detail ?? 0 }} 篇</span>
    </div>
    <div class="dh__list">
      <div v-for="r in rows" :key="r.label" class="dh__row">
        <div class="dh__fact">
          <span class="dh__label">{{ r.label }}</span>
          <span class="dh__value">{{ r.value }}</span>
        </div>
        <p v-if="r.interp" class="dh__interp"><em>解读</em>{{ r.interp }}</p>
      </div>
    </div>
  </section>
</template>

<style scoped>
.dh { background: var(--color-surface); border: 1px solid var(--color-rule); border-radius: 14px; padding: 20px 22px; }
.dh__head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 6px; flex-wrap: wrap; }
.dh__head h3 { margin: 0; font-size: 15px; font-weight: 650; }
.dh__sub { font-size: 12px; color: var(--color-ink-3); }
.dh__list { display: flex; flex-direction: column; }
.dh__row { padding: 12px 0; border-top: 1px solid var(--color-paper-3); }
.dh__row:first-child { border-top: 0; }
.dh__fact { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.dh__label { font-size: 12.5px; color: var(--color-ink-3); flex-shrink: 0; }
.dh__value { font-size: 13px; color: var(--color-ink); text-align: right; }
.dh__interp { display: flex; gap: 6px; align-items: baseline; margin: 5px 0 0; font-size: 12.5px; color: var(--color-ink-2); line-height: 1.5; }
.dh__interp em {
  flex-shrink: 0;
  font-style: normal;
  font-size: 10.5px;
  padding: 1px 6px;
  border-radius: 5px;
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
}
</style>
