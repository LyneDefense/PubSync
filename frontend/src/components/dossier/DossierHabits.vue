<script setup lang="ts">
// 档案页·运营习惯:博主"怎么运营"的行为事实(全量池算)。发布时段(周分布 + 时段)+ 节奏 / 体裁 /
// 话题标签 / 内容规格 / 评论引导 / 博主回复 若干指标块;每块给事实值 + 一句解读。
import { computed } from 'vue'
import type { DossierHabits } from '../../api/types'

const props = defineProps<{ habits: DossierHabits }>()

const WD = ['一', '二', '三', '四', '五', '六', '日']

function pct(v: number | null): string {
  return v == null ? '—' : `${Math.round(v * 100)}%`
}
function fmtDur(sec: number): string {
  return sec < 60 ? `${Math.round(sec)} 秒` : `${(sec / 60).toFixed(1)} 分`
}

// 发布时段(北京时间):周分布小柱 + 最常发的周几/时段。样本不足则不展示。
const time = computed(() => {
  const t = props.habits.posting_time
  if (!t || !t.weekday_counts?.length) return null
  const max = Math.max(...t.weekday_counts, 1)
  return {
    top: t.top_weekday && t.top_band ? `周${t.top_weekday} · ${t.top_band}` : '—',
    sample: t.sample,
    bars: t.weekday_counts.map((c, i) => ({ label: WD[i], h: Math.round((c / max) * 100), count: c, top: t.top_weekday === WD[i] })),
  }
})

// 指标块:事实值 + 一句解读。只放算得出的。
const tiles = computed(() => {
  const h = props.habits
  const out: { label: string; value: string; interp: string }[] = []

  const days = h.posting_rhythm?.avg_days_between
  if (h.posting_rhythm?.pattern) {
    out.push({
      label: '发布节奏',
      value: days != null ? `${h.posting_rhythm.pattern} · 均隔 ${days} 天` : h.posting_rhythm.pattern,
      interp: days == null ? '' : days > 20 ? '低频精耕,攒一篇大的' : days > 7 ? '稳定更新,保持露出' : '高频铺量,靠量取胜',
    })
  }

  const g = h.genre
  if (g && g.total > 0) {
    out.push({
      label: '内容体裁',
      value: `清单体 ${pct(g.ratio)}`,
      interp: `${g.listicle}/${g.total} 篇为清单体${(g.ratio ?? 0) > 0.4 ? ' · 密度适中易收藏' : ' · 以叙事/观点为主'}`,
    })
  }

  const hu = h.hashtag_usage
  if (hu && hu.avg_per_note != null) {
    out.push({
      label: '话题标签',
      value: `篇均 ${hu.avg_per_note} 个`,
      interp: hu.top_tags.length ? `高频:${hu.top_tags.slice(0, 3).map((x) => `#${x.tag}`).join(' ')}` : `${hu.notes_with}/${hu.total} 篇带标签`,
    })
  }

  const cf = h.content_format
  const fmtParts: string[] = []
  if (cf?.avg_images != null) fmtParts.push(`图文 ${cf.avg_images} 张/篇`)
  if (cf?.avg_video_sec != null) fmtParts.push(`视频 ${fmtDur(cf.avg_video_sec)}`)
  if (fmtParts.length) {
    out.push({ label: '内容规格', value: fmtParts.join(' · '), interp: cf?.avg_video_sec != null && cf?.avg_video_sec <= 60 ? '短平快,卡完播' : '篇幅偏重,信息量大' })
  }

  const cg = h.comment_guide
  if (cg && cg.total > 0) {
    out.push({
      label: '评论引导',
      value: `${pct(cg.ratio)} 主动引导`,
      interp: `${cg.count}/${cg.total} 篇${(cg.ratio ?? 0) > 0.3 ? ' · 常在正文/口播带互动' : ' · 靠内容自然发酵'}`,
    })
  }

  const ar = h.author_reply
  if (ar) {
    out.push({
      label: '博主回复',
      value: ar.ratio == null ? '暂无数据' : `${pct(ar.ratio)} 亲自回复`,
      interp: ar.ratio == null ? '回复数据待新一轮采集补齐' : `有评论的笔记 ${ar.replied}/${ar.with_comments} 篇${ar.ratio > 0.3 ? ' · 经营评论区' : ''}`,
    })
  }
  return out
})
</script>

<template>
  <section v-if="tiles.length || time" class="hb">
    <div class="hb__head">
      <h3>运营习惯</h3>
      <span class="hb__hint">行为事实 · 全量 {{ habits.coverage?.pool ?? 0 }} 篇(需正文的项按详情级 {{ habits.coverage?.detail ?? 0 }} 篇)</span>
    </div>

    <!-- 发布时段:招牌块 -->
    <div v-if="time" class="hb-time">
      <div class="hb-time__lead">
        <span class="hb-time__label">最常发布</span>
        <strong class="hb-time__val">{{ time.top }}</strong>
        <span class="hb-time__sub">按 {{ time.sample }} 篇发布时间(北京时间)</span>
      </div>
      <div class="hb-time__bars">
        <div v-for="(b, i) in time.bars" :key="i" class="hb-bar" :title="`周${b.label} · ${b.count} 篇`">
          <span class="hb-bar__track"><span class="hb-bar__fill" :class="{ top: b.top }" :style="{ height: `${Math.max(b.h, 4)}%` }"></span></span>
          <span class="hb-bar__label" :class="{ top: b.top }">{{ b.label }}</span>
        </div>
      </div>
    </div>

    <!-- 指标块 -->
    <div class="hb-tiles">
      <div v-for="t in tiles" :key="t.label" class="hb-tile">
        <span class="hb-tile__label">{{ t.label }}</span>
        <strong class="hb-tile__value">{{ t.value }}</strong>
        <span v-if="t.interp" class="hb-tile__interp">{{ t.interp }}</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.hb { background: var(--color-surface); border: 1px solid var(--color-rule); border-radius: 14px; padding: 20px 22px; }
.hb__head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
.hb__head h3 { margin: 0; font-size: 15px; font-weight: 650; }
.hb__hint { font-size: 12px; color: var(--color-ink-3); }

/* 发布时段招牌块 */
.hb-time {
  display: flex;
  align-items: stretch;
  gap: 20px;
  padding: 14px 16px;
  margin-bottom: 14px;
  border-radius: 12px;
  background: linear-gradient(180deg, var(--color-accent-tint, var(--color-accent-soft)), var(--color-paper));
  border: 1px solid var(--color-accent-soft-bd);
  flex-wrap: wrap;
}
.hb-time__lead { display: flex; flex-direction: column; gap: 3px; justify-content: center; min-width: 120px; }
.hb-time__label { font-size: 11.5px; color: var(--color-ink-3); }
.hb-time__val { font-size: 20px; font-weight: 700; color: var(--color-accent-ink); letter-spacing: -0.01em; }
.hb-time__sub { font-size: 11px; color: var(--color-ink-3); }
.hb-time__bars { flex: 1; min-width: 200px; display: flex; align-items: flex-end; gap: 6px; }
.hb-bar { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 5px; }
.hb-bar__track { width: 100%; height: 48px; display: flex; align-items: flex-end; justify-content: center; }
.hb-bar__fill { width: 68%; max-width: 22px; border-radius: 4px 4px 2px 2px; background: var(--color-accent-soft-bd); transition: height 0.2s var(--ease-out); }
.hb-bar__fill.top { background: var(--color-accent); }
.hb-bar__label { font-size: 11px; color: var(--color-ink-3); }
.hb-bar__label.top { color: var(--color-accent-ink); font-weight: 700; }

/* 指标块网格 */
.hb-tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }
.hb-tile {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--color-paper);
  border: 1px solid var(--color-rule);
  border-left: 3px solid var(--color-accent-soft-bd);
}
.hb-tile__label { font-size: 11.5px; color: var(--color-ink-3); }
.hb-tile__value { font-size: 14.5px; font-weight: 620; color: var(--color-ink); line-height: 1.35; }
.hb-tile__interp { font-size: 11.5px; color: var(--color-ink-3); line-height: 1.5; }

@media (max-width: 560px) {
  .hb-tiles { grid-template-columns: 1fr 1fr; }
}
</style>
