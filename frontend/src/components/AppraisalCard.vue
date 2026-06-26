<script setup lang="ts">
// 博主诊断·三区决策卡:渲染后端 run_appraisal 的报告(硬实力 / 软实力 / 合规)。
// 纯展示组件,只吃一个 report 对象(AccountAuditRun.report_json 解析后);无 store/api 依赖。
import type { AppraisalReport } from '../api/types'

defineProps<{ report: AppraisalReport }>()

function scoreColor(score: number): string {
  if (score >= 75) return 'var(--color-ok, #1f7a45)'
  if (score >= 60) return 'var(--color-warn, #b7791f)'
  return 'var(--color-danger, #c0392b)'
}
function levelColor(level: string): string {
  return level === 'ok'
    ? 'var(--color-ok, #1f7a45)'
    : level === 'danger'
      ? 'var(--color-danger, #c0392b)'
      : level === 'warn'
        ? 'var(--color-warn, #b7791f)'
        : 'var(--color-text-soft, #888)'
}
function sevColor(sev: string): string {
  return sev === '封号级'
    ? 'var(--color-danger, #c0392b)'
    : sev === '限流级'
      ? 'var(--color-warn, #b7791f)'
      : 'var(--color-text-soft, #888)'
}
</script>

<template>
  <div class="appraisal-card">
    <!-- 醒目:采集 / 相关总览(诊断别人时) -->
    <div
      v-if="report.examined_count && report.kind === 'benchmark' && report.intent"
      class="sample-summary"
      :class="{ low: report.low_relevance }"
    >
      采集 <b>{{ report.examined_count }}</b> 篇 · 与你意图相关 <b>{{ report.relevant_count }}</b> 篇<template
        v-if="report.low_relevance"
      > — 相关内容很少,这号大概率不对你的路</template>
    </div>

    <!-- 结论 -->
    <div class="verdict" :style="{ borderColor: levelColor(report.verdict.level) }">
      <strong :style="{ color: levelColor(report.verdict.level) }">{{ report.verdict.text }}</strong>
      <div class="scores">
        <span>硬实力 <b>{{ report.hard_score }}</b></span>
        <span v-if="report.soft_score !== null">软实力 <b>{{ report.soft_score }}</b></span>
        <span>合规 <b :style="{ color: scoreColor(report.compliance.score) }">{{ report.compliance.score }}</b></span>
        <em>· 基于 {{ report.sample_count }} 篇笔记</em>
      </div>
    </div>

    <!-- 硬实力 -->
    <section class="zone">
      <h4>硬实力 · 这号本身牛不牛</h4>
      <div v-for="d in report.hard" :key="d.key" class="dim">
        <div class="dim-head"><span>{{ d.label }}</span><b :style="{ color: scoreColor(d.score) }">{{ d.score }}</b></div>
        <div class="track"><div class="fill" :style="{ width: d.score + '%', background: scoreColor(d.score) }"></div></div>
        <p class="detail">{{ d.detail }}</p>
      </div>
    </section>

    <!-- 软实力(诊断别人才有) -->
    <section v-if="report.soft.length" class="zone">
      <h4>软实力 · 你能不能学 TA</h4>
      <div v-for="d in report.soft" :key="d.key" class="dim">
        <div class="dim-head"><span>{{ d.label }}</span><b :style="{ color: scoreColor(d.score) }">{{ d.score }}</b></div>
        <div class="track"><div class="fill" :style="{ width: d.score + '%', background: scoreColor(d.score) }"></div></div>
        <p class="detail">{{ d.detail }}</p>
      </div>
    </section>

    <!-- 合规 -->
    <section class="zone">
      <h4>
        合规 · 干不干净
        <span class="grade" :style="{ color: scoreColor(report.compliance.score) }">{{ report.compliance.grade }}</span>
      </h4>
      <p v-if="!report.compliance.hits.length" class="detail clean">未发现违规打法,内容干净 ✓</p>
      <ul v-else class="hits">
        <li v-for="(h, i) in report.compliance.hits" :key="i">
          <span class="sev" :style="{ background: sevColor(h.severity) }">{{ h.severity }}</span>
          <div class="hit-body">
            <b>{{ h.category }}</b>
            <span v-if="h.quote" class="quote">「{{ h.quote }}」</span>
            <span v-if="h.suggestion" class="sugg">→ {{ h.suggestion }}</span>
          </div>
        </li>
      </ul>
    </section>

    <!-- 相关性明细:哪些笔记纳入了诊断,哪些被排除 -->
    <section v-if="report.notes_relevance && report.notes_relevance.length" class="zone">
      <h4>笔记相关性 · 哪些纳入了诊断</h4>
      <ul class="rel-list">
        <li v-for="(n, i) in report.notes_relevance" :key="i" :class="{ off: !n.relevant }">
          <span class="rel-mark">{{ n.relevant ? '✓ 纳入' : '✕ 排除' }}</span>
          <span class="rel-title">{{ n.title }}</span>
          <span v-if="n.reason" class="rel-reason">{{ n.reason }}</span>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.appraisal-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-md, 16px);
}
.verdict {
  border: 1px solid;
  border-radius: var(--radius-md, 8px);
  padding: var(--space-sm, 12px) var(--space-md, 16px);
}
.verdict strong {
  display: block;
  font-size: var(--text-md, 15px);
}
.scores {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  font-size: var(--text-sm, 13px);
  color: var(--color-text-soft, #666);
}
.scores b {
  font-size: 15px;
  color: var(--color-text, inherit);
}
.sample-summary {
  background: var(--color-surface-2, #f3f4f6);
  border-radius: var(--radius-md, 8px);
  padding: 10px 14px;
  font-size: var(--text-sm, 14px);
}
.sample-summary.low {
  background: var(--color-warn-bg, #fdf3e7);
  color: var(--color-warn, #b7791f);
}
.sample-summary b {
  font-size: 16px;
}
.rel-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 320px;
  overflow-y: auto;
}
.rel-list li {
  display: flex;
  gap: 8px;
  align-items: baseline;
  font-size: var(--text-sm, 13px);
}
.rel-list li.off {
  opacity: 0.55;
}
.rel-mark {
  flex: none;
  font-size: 12px;
  color: var(--color-ok, #1f7a45);
}
.rel-list li.off .rel-mark {
  color: var(--color-text-soft, #999);
}
.rel-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rel-reason {
  color: var(--color-text-soft, #888);
  flex: none;
  max-width: 40%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.zone h4 {
  margin: 0 0 10px;
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.grade {
  font-size: var(--text-sm, 13px);
  font-weight: 500;
}
.dim {
  margin-bottom: 12px;
}
.dim-head {
  display: flex;
  justify-content: space-between;
  font-size: var(--text-sm, 14px);
  margin-bottom: 4px;
}
.track {
  height: 7px;
  border-radius: 99px;
  background: var(--color-surface-2, #eee);
  overflow: hidden;
}
.fill {
  height: 100%;
  border-radius: 99px;
}
.detail {
  margin: 5px 0 0;
  font-size: var(--text-sm, 13px);
  color: var(--color-text-soft, #666);
  line-height: 1.5;
}
.detail.clean {
  color: var(--color-ok, #1f7a45);
}
.hits {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.hits li {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.sev {
  flex: none;
  color: #fff;
  font-size: 11px;
  padding: 1px 7px;
  border-radius: var(--radius-sm, 4px);
  white-space: nowrap;
}
.hit-body {
  font-size: var(--text-sm, 13px);
  line-height: 1.5;
}
.quote {
  color: var(--color-text-soft, #888);
  margin-left: 6px;
}
.sugg {
  display: block;
  color: var(--color-accent, #0d7361);
  margin-top: 2px;
}
</style>
