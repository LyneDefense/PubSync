<script setup lang="ts">
// 诊断报告卡:渲染 run_appraisal 的三区报告 —— 结论 Hero + 分数 tile + 硬/软实力维度条 + 合规 + 笔记相关性。
// 纯展示组件,只吃一个 report 对象;无 store/api 依赖。对标分析与诊断我的账号共用。
import { computed } from 'vue'
import type { AppraisalReport } from '../api/types'

const props = defineProps<{ report: AppraisalReport }>()

// 分数色带:≥75 绿 / ≥60 琥珀 / else 红。返回 class,颜色全在 token 化的 CSS 里。
function band(score: number): string {
  return score >= 75 ? 's-ok' : score >= 60 ? 's-warn' : 's-danger'
}
function sevClass(sev: string): string {
  return sev === '封号级' ? 'sev-ban' : sev === '限流级' ? 'sev-warn' : 'sev-notice'
}

// 合规:新架构分「违规(需处置) / 提示(优化建议)」两档 + 赛道标签;旧报告回落到扁平 hits。
const comp = computed(() => props.report.compliance)
const cViolations = computed(() => comp.value.violations || [])
const cAdvisories = computed(() => comp.value.advisories || [])
const cVerticalLabels = computed(() => comp.value.vertical_labels || [])
const legacyHits = computed(() =>
  cViolations.value.length || cAdvisories.value.length ? [] : comp.value.hits || []
)
const complianceClean = computed(
  () => !cViolations.value.length && !cAdvisories.value.length && !legacyHits.value.length
)

const BADGE: Record<string, Record<string, string>> = {
  benchmark: { ok: '值得对标', warn: '可以选学', danger: '慎选 · 有风险', muted: '不太建议对标' },
  self: { ok: '基本面不错', warn: '有提升空间', danger: '需尽快整改', muted: '有提升空间' }
}
const verdictBadge = computed(
  () => BADGE[props.report.kind === 'self' ? 'self' : 'benchmark'][props.report.verdict.level] || props.report.verdict.text
)
const showSample = computed(
  () => Boolean(props.report.examined_count && props.report.kind === 'benchmark' && props.report.intent)
)
</script>

<template>
  <div class="appraisal">
    <!-- 结论 Hero -->
    <section class="verdict" :class="'lv-' + report.verdict.level">
      <div class="v-left">
        <span class="v-badge" :class="'lv-' + report.verdict.level">{{ verdictBadge }}</span>
        <p class="v-summary">{{ report.verdict.text }}</p>
        <div v-if="showSample" class="v-sample" :class="{ low: report.low_relevance }">
          采集 <b>{{ report.examined_count }}</b> 篇 · 与你意图相关 <b class="rel">{{ report.relevant_count }}</b> 篇<template
            v-if="report.low_relevance"
          > — 相关内容很少,这号大概率不对你的路</template>
        </div>
      </div>
      <div class="v-tiles">
        <div class="tile" :class="band(report.hard_score)">
          <span>硬实力</span><b>{{ report.hard_score }}</b>
        </div>
        <div v-if="report.soft_score !== null" class="tile" :class="band(report.soft_score ?? 0)">
          <span>软实力</span><b>{{ report.soft_score }}</b>
        </div>
        <div class="tile" :class="band(report.compliance.score)">
          <span>合规</span><b>{{ report.compliance.score }}</b>
        </div>
      </div>
    </section>

    <!-- 硬实力 -->
    <section class="zone">
      <div class="zone-head"><h3>硬实力</h3><span>这号本身牛不牛</span></div>
      <div class="dims">
        <div v-for="d in report.hard" :key="d.key" class="dim">
          <div class="dim-top"><span class="dim-label">{{ d.label }}</span><b :class="band(d.score)">{{ d.score }}</b></div>
          <div class="track"><div class="fill" :class="band(d.score)" :style="{ width: d.score + '%' }"></div></div>
          <p class="dim-detail">{{ d.detail }}</p>
        </div>
      </div>
    </section>

    <!-- 软实力(诊断别人才有) -->
    <section v-if="report.soft.length" class="zone">
      <div class="zone-head"><h3>软实力</h3><span>你能不能学 TA</span></div>
      <div class="dims">
        <div v-for="d in report.soft" :key="d.key" class="dim">
          <div class="dim-top"><span class="dim-label">{{ d.label }}</span><b :class="band(d.score)">{{ d.score }}</b></div>
          <div class="track"><div class="fill" :class="band(d.score)" :style="{ width: d.score + '%' }"></div></div>
          <p class="dim-detail">{{ d.detail }}</p>
        </div>
      </div>
    </section>

    <!-- 目标契合(诊断自己 + 填了目标才有) -->
    <section v-if="report.goal_fit" class="zone">
      <div class="zone-head">
        <h3>目标契合</h3><span>离你的目标还差多少</span>
        <span class="grade" :class="band(report.goal_fit.score)">{{ report.goal_fit.grade }} · {{ report.goal_fit.score }}</span>
      </div>
      <p class="gf-summary">{{ report.goal_fit.summary }}</p>
      <div v-if="report.goal_fit.gaps.length" class="gf-block">
        <h4>关键短板</h4>
        <ul class="gf-gaps"><li v-for="(g, i) in report.goal_fit.gaps" :key="i">{{ g }}</li></ul>
      </div>
      <div v-if="report.goal_fit.actions.length" class="gf-block">
        <h4>整改清单</h4>
        <ol class="gf-actions"><li v-for="(a, i) in report.goal_fit.actions" :key="i">{{ a }}</li></ol>
      </div>
    </section>

    <!-- 合规 -->
    <section class="zone">
      <div class="zone-head">
        <h3>合规</h3><span>干不干净</span>
        <span class="grade" :class="band(report.compliance.score)">{{ report.compliance.grade }}</span>
      </div>
      <p v-if="cVerticalLabels.length" class="c-verticals">按「{{ cVerticalLabels.join(' · ') }} · 通用」规则检测</p>
      <p v-if="complianceClean" class="clean">未发现违规打法,内容干净 ✓</p>

      <!-- 违规(需处置) -->
      <div v-if="cViolations.length" class="hits">
        <div v-for="(g, i) in cViolations" :key="'v' + i" class="hit" :class="sevClass(g.severity)">
          <span class="sev" :class="sevClass(g.severity)">{{ g.severity }}</span>
          <div class="hit-body">
            <b>{{ g.category }}</b>
            <span v-if="g.coverage && g.coverage.total_notes > 1" class="cover">命中 {{ g.coverage.hit_notes }}/{{ g.coverage.total_notes }} 篇</span>
            <span v-if="g.matched && g.matched.length" class="quote">{{ g.matched.join('、') }}</span>
            <span v-if="g.hint" class="sugg">→ {{ g.hint }}</span>
            <span v-if="g.basis" class="basis">依据:{{ g.basis }}</span>
          </div>
        </div>
      </div>

      <!-- 优化提示(折叠,不计入违规) -->
      <details v-if="cAdvisories.length" class="advisories">
        <summary>{{ cAdvisories.length }} 条优化提示(不算违规,酌情调整)</summary>
        <div v-for="(g, i) in cAdvisories" :key="'a' + i" class="adv-row">
          <b>{{ g.category }}</b>
          <span v-if="g.matched && g.matched.length" class="quote">{{ g.matched.join('、') }}</span>
          <span v-if="g.hint" class="sugg">→ {{ g.hint }}</span>
        </div>
      </details>

      <!-- 兼容:旧报告只有扁平 hits -->
      <div v-if="legacyHits.length" class="hits">
        <div v-for="(h, i) in legacyHits" :key="'l' + i" class="hit" :class="sevClass(h.severity)">
          <span class="sev" :class="sevClass(h.severity)">{{ h.severity }}</span>
          <div class="hit-body">
            <b>{{ h.category }}</b>
            <span v-if="h.quote" class="quote">「{{ h.quote }}」</span>
            <span v-if="h.suggestion" class="sugg">→ {{ h.suggestion }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 笔记相关性 -->
    <section v-if="report.notes_relevance && report.notes_relevance.length" class="zone">
      <div class="zone-head">
        <h3>笔记相关性</h3>
        <span>哪些纳入了诊断<template v-if="report.examined_count"> · {{ report.relevant_count }} / {{ report.examined_count }}</template></span>
      </div>
      <div class="notes">
        <div v-for="(n, i) in report.notes_relevance" :key="i" class="note" :class="{ off: !n.relevant }">
          <span class="note-mark" :class="{ on: n.relevant }">{{ n.relevant ? '✓ 纳入' : '✕ 排除' }}</span>
          <span class="note-title">{{ n.title }}</span>
          <span v-if="n.reason" class="note-reason">{{ n.reason }}</span>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.appraisal {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* —— 结论 Hero —— */
.verdict {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 24px;
  align-items: center;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-left: 4px solid var(--color-ink-3);
  border-radius: var(--radius-lg);
  padding: 22px 24px;
}
.verdict.lv-ok {
  border-color: var(--color-accent-soft-bd);
  border-left-color: var(--color-accent);
}
.verdict.lv-warn {
  border-color: var(--color-score-warn-bd);
  border-left-color: var(--color-warn);
}
.verdict.lv-danger {
  border-color: var(--color-score-danger-bd);
  border-left-color: var(--color-danger);
}
.v-left {
  min-width: 0;
}
.v-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: var(--radius-pill);
  font-size: 12.5px;
  font-weight: 650;
  margin-bottom: 12px;
  background: var(--color-paper-3);
  color: var(--color-ink-3);
}
.v-badge.lv-ok {
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
}
.v-badge.lv-warn {
  background: var(--color-score-warn-bg);
  color: var(--color-warn);
}
.v-badge.lv-danger {
  background: var(--color-score-danger-bg);
  color: var(--color-danger);
}
.v-summary {
  margin: 0 0 12px;
  font-size: 16px;
  font-weight: 650;
  line-height: 1.5;
  color: var(--color-ink);
}
.v-sample {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 8px 14px;
  border-radius: 10px;
  background: #f7f8f9;
  font-size: 13px;
  color: var(--color-ink-2);
}
.v-sample b {
  font-size: 15px;
  color: var(--color-ink);
  font-variant-numeric: tabular-nums;
}
.v-sample b.rel {
  color: var(--color-accent-ink);
}
.v-sample.low {
  background: var(--color-warn-card-bg);
  border: 1px solid var(--color-warn-card-bd);
  color: var(--color-warn);
}
.v-tiles {
  display: flex;
  gap: 10px;
  flex: 0 0 auto;
}
.tile {
  text-align: center;
  min-width: 78px;
  padding: 14px 12px;
  border-radius: 12px;
  border: 1px solid var(--color-rule);
  background: var(--color-paper-3);
}
.tile span {
  display: block;
  font-size: 11.5px;
  color: var(--color-ink-2);
  font-weight: 600;
  margin-bottom: 5px;
}
.tile b {
  font-size: 28px;
  font-weight: 720;
  line-height: 1;
  font-variant-numeric: tabular-nums;
  color: var(--color-ink);
}
.tile.s-ok {
  background: var(--color-score-ok-bg);
  border-color: var(--color-score-ok-bd);
}
.tile.s-ok b {
  color: var(--color-ok);
}
.tile.s-warn {
  background: var(--color-score-warn-bg);
  border-color: var(--color-score-warn-bd);
}
.tile.s-warn b {
  color: var(--color-warn);
}
.tile.s-danger {
  background: var(--color-score-danger-bg);
  border-color: var(--color-score-danger-bd);
}
.tile.s-danger b {
  color: var(--color-danger);
}

/* —— Zone —— */
.zone {
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
  padding: 20px 22px;
}
.zone-head {
  display: flex;
  align-items: baseline;
  gap: 9px;
  margin-bottom: 16px;
}
.zone-head h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 650;
}
.zone-head > span {
  font-size: 12.5px;
  color: var(--color-ink-3);
}
.grade {
  margin-left: auto;
  padding: 3px 12px;
  border-radius: var(--radius-pill);
  font-size: 12.5px;
  font-weight: 700;
}
.grade.s-ok {
  background: var(--color-score-ok-bg);
  color: var(--color-ok);
}
.grade.s-warn {
  background: var(--color-score-warn-bg);
  color: var(--color-warn);
}
.grade.s-danger {
  background: var(--color-score-danger-bg);
  color: var(--color-danger);
}

/* —— 维度条 —— */
.dims {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 18px 32px;
}
.dim-top {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 13.5px;
  margin-bottom: 6px;
}
.dim-label {
  font-weight: 550;
  color: #3a4048;
}
.dim-top b {
  font-size: 15px;
  font-variant-numeric: tabular-nums;
}
.dim-top b.s-ok {
  color: var(--color-ok);
}
.dim-top b.s-warn {
  color: var(--color-warn);
}
.dim-top b.s-danger {
  color: var(--color-danger);
}
.track {
  height: 7px;
  border-radius: 99px;
  background: var(--color-paper-3);
  overflow: hidden;
}
.fill {
  height: 100%;
  border-radius: 99px;
  transition: width 420ms var(--ease-out);
}
.fill.s-ok {
  background: var(--color-ok);
}
.fill.s-warn {
  background: var(--color-warn);
}
.fill.s-danger {
  background: var(--color-danger);
}
.dim-detail {
  margin: 7px 0 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--color-ink-2);
}
@media (prefers-reduced-motion: reduce) {
  .fill {
    transition: none;
  }
}

/* —— 合规命中 —— */
.clean {
  margin: 0;
  font-size: 13.5px;
  color: var(--color-ok);
}
.hits {
  display: grid;
  gap: 10px;
}
.hit {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 13px 15px;
  border-radius: 11px;
  border: 1px solid var(--color-rule);
  background: #fafbfc;
}
.hit.sev-ban {
  border-color: var(--color-score-danger-bd);
  background: var(--color-score-danger-bg);
}
.hit.sev-warn {
  border-color: var(--color-warn-card-bd);
  background: var(--color-warn-card-bg);
}
.sev {
  flex: 0 0 auto;
  margin-top: 1px;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 9px;
  border-radius: 6px;
  white-space: nowrap;
}
.sev.sev-ban {
  background: var(--color-danger);
}
.sev.sev-warn {
  background: var(--color-warn);
}
.sev.sev-notice {
  background: var(--color-ink-3);
}
.hit-body {
  min-width: 0;
  font-size: 13.5px;
  line-height: 1.55;
}
.hit-body b {
  font-size: 13.5px;
  color: var(--color-ink);
}
.quote {
  display: block;
  margin-top: 3px;
  font-size: 12.5px;
  color: var(--color-ink-3);
}
.sugg {
  display: block;
  margin-top: 5px;
  font-size: 12.5px;
  color: var(--color-accent-ink);
}
.c-verticals {
  margin: 0 0 10px;
  font-size: 12px;
  color: var(--color-ink-3);
}
.cover {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 7px;
  border-radius: 6px;
  background: var(--color-paper-3);
  font-size: 11.5px;
  color: var(--color-ink-2);
  font-variant-numeric: tabular-nums;
}
.basis {
  display: block;
  margin-top: 4px;
  font-size: 11.5px;
  color: var(--color-ink-3);
}
/* 优化提示:折叠,弱化,不与违规同权 */
.advisories {
  margin-top: 10px;
  border: 1px dashed var(--color-rule);
  border-radius: 11px;
  background: #fbfcfc;
  padding: 4px 14px;
}
.advisories > summary {
  cursor: pointer;
  padding: 8px 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink-2);
  list-style: none;
}
.advisories > summary::-webkit-details-marker {
  display: none;
}
.advisories > summary::before {
  content: '▸ ';
  color: var(--color-ink-3);
}
.advisories[open] > summary::before {
  content: '▾ ';
}
.adv-row {
  padding: 8px 0;
  border-top: 1px solid var(--color-paper-3);
  font-size: 13px;
  line-height: 1.55;
}
.adv-row b {
  color: var(--color-ink);
}

/* —— 笔记相关性 —— */
.notes {
  display: flex;
  flex-direction: column;
}
.note {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid #f1f3f4;
}
.note:last-child {
  border-bottom: 0;
}
.note.off {
  opacity: 0.6;
}
.note-mark {
  flex: 0 0 auto;
  font-size: 11.5px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 6px;
  background: #f1f2f4;
  color: var(--color-ink-3);
}
.note-mark.on {
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
}
.note-title {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: #3a4048;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.note-reason {
  flex: 0 0 auto;
  max-width: 42%;
  font-size: 12px;
  color: var(--color-ink-3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* —— 目标契合 —— */
.gf-summary {
  margin: 0 0 14px;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.6;
  color: var(--color-ink);
}
.gf-block {
  margin-top: 12px;
}
.gf-block h4 {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 650;
  color: var(--color-ink-2);
}
.gf-gaps,
.gf-actions {
  margin: 0;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.gf-gaps li {
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-ink-2);
}
.gf-actions li {
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-accent-ink);
}

/* —— 响应式 —— */
@media (max-width: 720px) {
  .verdict {
    grid-template-columns: 1fr;
    gap: 16px;
  }
  .v-tiles {
    width: 100%;
  }
  .tile {
    flex: 1;
  }
}
</style>
