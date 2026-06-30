<script setup lang="ts">
// 对标分析(诊断别人):三步向导 —— ① 选对标博主 ② 明确意图(看 TA 在做什么 + 引导问题) ③ 诊断报告。
// 同一时间只显示一步;顶部 stepper 贯穿三步。状态机:step(1|2|3) 本地;意图/问题/报告复用 store。
import { computed, onMounted, ref } from 'vue'
import { toPng } from 'html-to-image'
import AppraisalCard from '../components/AppraisalCard.vue'
import LiveProgress from '../components/LiveProgress.vue'
import type { AccountAuditRun } from '../api/types'
import {
  appraiseForm,
  appraisalHistory,
  appraisalRun,
  benchmarkAccounts,
  bloggers,
  currentSocialPlatformName,
  currentSocialTab,
  fetchIntentSuggestions,
  formatDate,
  handleRunAppraisal,
  intentChecked,
  intentClear,
  intentLoading,
  intentOthers,
  intentQuestions,
  intentSelections,
  isSocialPlatform,
  parseAppraisalReport,
  pendingAction,
  refreshAppraisalHistory,
  resetIntentGuide,
  showMessage
} from '../composables/useWorkspaceStore'

const STEP_LABELS = ['选择对标博主', '明确意图', '诊断报告']

const report = computed(() => parseAppraisalReport(appraisalRun.value))
const step = ref<1 | 2 | 3>(report.value ? 3 : 1)
const reportEl = ref<HTMLElement | null>(null) // 导出图片的截取范围
const exporting = ref(false)

const selectedBlogger = computed(() => benchmarkAccounts.value.find((b) => b.id === appraiseForm.blogger_id) || null)
const selectedName = computed(() => selectedBlogger.value?.display_name || '')
const diagnosing = computed(() => pendingAction.value === 'audit')

function bloggerNameById(id: number | null | undefined): string {
  if (!id) return ''
  return bloggers.value.find((b) => b.id === id)?.display_name || '已删除的博主'
}
// 报告署名:用 run 自带的 blogger_id 解析(历史报告 / 新报告都对得上,不依赖当前选择)。
const reportBloggerName = computed(() =>
  bloggerNameById(appraisalRun.value?.benchmark_blogger_id || appraisalRun.value?.my_blogger_id)
)
const reportDate = computed(() => (appraisalRun.value ? formatDate(appraisalRun.value.created_at) : ''))

// 历史诊断:解析一次,带博主名 + 日期(最新在前)。
const historyItems = computed(() =>
  appraisalHistory.value
    .map((run) => ({
      run,
      report: parseAppraisalReport(run),
      name: bloggerNameById(run.benchmark_blogger_id) || '对标博主',
      date: formatDate(run.created_at)
    }))
    .filter((it) => it.report)
)

function scoreBand(n: number): string {
  return n >= 75 ? 's-ok' : n >= 60 ? 's-warn' : 's-danger'
}
function stepState(n: number): 'cur' | 'done' | 'todo' {
  return n === step.value ? 'cur' : n < step.value ? 'done' : 'todo'
}

// 文字头像:名字首字 + 按 id 取一组柔和底色。
const AVATAR_BG = ['#f0eef7', '#eef4f5', '#eaf3ee', '#eef1f6', '#f6eef2', '#eef3f7']
const AVATAR_INK = ['#5a4a86', '#3a6a72', '#2f6b54', '#44506a', '#8a4a64', '#3a5a86']
function avatarStyle(id: number) {
  const i = (((id || 0) % AVATAR_BG.length) + AVATAR_BG.length) % AVATAR_BG.length
  return { background: AVATAR_BG[i], color: AVATAR_INK[i] }
}

function pick(id: number) {
  appraiseForm.blogger_id = appraiseForm.blogger_id === id ? 0 : id
  resetIntentGuide()
}
function toggleOption(qi: number, opt: string) {
  const arr = intentSelections[qi] || (intentSelections[qi] = [])
  const i = arr.indexOf(opt)
  if (i >= 0) arr.splice(i, 1)
  else arr.push(opt)
}
function isPicked(qi: number, opt: string): boolean {
  return (intentSelections[qi] || []).includes(opt)
}

async function startDiagnose() {
  step.value = 3
  await handleRunAppraisal()
  refreshAppraisalHistory() // 新报告进历史
}
function restart() {
  resetIntentGuide()
  step.value = 1
}
// 查看一条历史报告:直接载入到第 3 步。
function viewHistoryRun(run: AccountAuditRun) {
  appraisalRun.value = run
  step.value = 3
}

// 把报告区域导出成一张 PNG 图片(含署名头 + 三区报告)。
async function exportImage() {
  const el = reportEl.value
  if (!el || !report.value) return
  exporting.value = true
  try {
    const dataUrl = await toPng(el, { pixelRatio: 2, backgroundColor: '#eef0f2', cacheBust: true })
    const a = document.createElement('a')
    a.href = dataUrl
    a.download = `${reportBloggerName.value || '对标分析'}-对标分析报告.png`
    a.click()
    showMessage('已导出报告图片')
  } catch (err) {
    showMessage(err instanceof Error ? err.message : '导出图片失败,请重试', true)
  } finally {
    exporting.value = false
  }
}

onMounted(() => {
  refreshAppraisalHistory()
})
</script>

<template>
  <section v-if="isSocialPlatform && currentSocialTab === 'analysis'" class="analysis">
    <header class="page-head">
      <h1>{{ currentSocialPlatformName }}对标分析</h1>
      <p>诊断一个号到底值不值得对标 —— 硬实力 × 软实力 × 合规。诊断前会自动确保 ≥ 20 篇笔记样本。</p>
    </header>

    <!-- Stepper -->
    <div class="stepper">
      <template v-for="(label, i) in STEP_LABELS" :key="i">
        <div v-if="i > 0" class="step-line" :class="{ done: i < step }"></div>
        <div class="step-node">
          <span class="step-circle" :class="stepState(i + 1)">{{ i + 1 < step ? '✓' : i + 1 }}</span>
          <span class="step-label" :class="stepState(i + 1)">{{ label }}</span>
        </div>
      </template>
    </div>

    <!-- ===== Step 1 · 选择对标博主 (+ 历史诊断) ===== -->
    <template v-if="step === 1">
      <section class="card">
      <div class="card-head">
        <div>
          <p class="kicker">第 1 步 / 共 3 步</p>
          <h2>选择要诊断的对标博主</h2>
        </div>
        <span class="head-hint">{{ selectedBlogger ? `已选择「${selectedName}」` : '请选择一个要诊断的博主' }}</span>
      </div>
      <div v-if="benchmarkAccounts.length" class="blogger-grid">
        <button
          v-for="b in benchmarkAccounts"
          :key="b.id"
          type="button"
          class="blogger-card"
          :class="{ sel: appraiseForm.blogger_id === b.id }"
          @click="pick(b.id)"
        >
          <span class="avatar" :style="avatarStyle(b.id)">{{ (b.display_name || '?').slice(0, 1) }}</span>
          <span class="b-body">
            <span class="b-name">{{ b.display_name }}</span>
            <span class="b-meta">
              <span class="niche" :class="{ muted: !b.niche }">{{ b.niche || '未设置领域' }}</span>
              <span class="samples">样本 {{ b.sample_count }}</span>
            </span>
          </span>
          <span class="radio" :class="{ on: appraiseForm.blogger_id === b.id }">✓</span>
        </button>
      </div>
      <p v-else class="empty-region pad">对标库还没有博主,先去「找对标博主」加一个。</p>
      <div class="card-foot">
        <button type="button" class="btn-primary" :disabled="!appraiseForm.blogger_id" @click="step = 2">下一步 →</button>
      </div>
      </section>

      <!-- 历史诊断:已诊断过的报告,点一条查看 -->
      <section v-if="historyItems.length" class="card history">
        <div class="card-head">
          <div>
            <p class="kicker">历史诊断</p>
            <h2>之前诊断过的报告</h2>
          </div>
          <span class="head-hint">点一条查看</span>
        </div>
        <div class="hist-list">
          <button
            v-for="it in historyItems"
            :key="it.run.id"
            type="button"
            class="hist-row"
            @click="viewHistoryRun(it.run)"
          >
            <span class="hist-name">{{ it.name }}</span>
            <span class="hist-scores">
              <em :class="scoreBand(it.report!.hard_score)">硬 {{ it.report!.hard_score }}</em>
              <em v-if="it.report!.soft_score != null" :class="scoreBand(it.report!.soft_score ?? 0)">软 {{ it.report!.soft_score }}</em>
              <em :class="scoreBand(it.report!.compliance.score)">合规 {{ it.report!.compliance.score }}</em>
            </span>
            <span class="hist-date">{{ it.date }}</span>
          </button>
        </div>
      </section>
    </template>

    <!-- ===== Step 2 · 明确意图 ===== -->
    <section v-else-if="step === 2" class="card">
      <div class="card-head col">
        <p class="kicker">第 2 步 / 共 3 步</p>
        <h2>明确你的对标意图</h2>
        <p class="sub">
          正在诊断「<b>{{ selectedName }}</b>」。先说说你想从 TA 身上学什么,我们会看 TA 在做什么、再用几道选择题帮你把意图问清楚。
        </p>
      </div>
      <div class="card-body form">
        <label class="field">
          <span>你想学什么 / 对标意图 <em>(可不填)</em></span>
          <input v-model="appraiseForm.intent" type="text" placeholder="例:想学把香港保险讲得专业、又有人看、能涨粉" />
        </label>
        <label class="field narrow">
          <span>品类 <em>(可选,触发合规红线)</em></span>
          <input v-model="appraiseForm.industry" type="text" placeholder="保险 / 金融 / 医疗 / 美妆…" />
        </label>

        <!-- 引导问题(明确意图后出现) -->
        <template v-if="intentChecked">
          <div class="guide-rule"></div>
          <div class="guide-hint">
            <span class="tick">✓</span>
            <span>看了 TA 最近的内容,挑几个最贴近你的方向,诊断会更准。</span>
          </div>
          <p v-if="intentClear && !intentQuestions.length" class="intent-clear">你的意图已经清楚,可以直接诊断。</p>
          <div v-for="(q, qi) in intentQuestions" :key="qi" class="guide-q">
            <p class="q-title">{{ q.q }}</p>
            <div class="chips">
              <button
                v-for="opt in q.options"
                :key="opt"
                type="button"
                class="chip"
                :class="{ on: isPicked(qi, opt) }"
                @click="toggleOption(qi, opt)"
              >{{ opt }}</button>
              <input
                v-model="intentOthers[qi]"
                class="chip-other"
                type="text"
                placeholder="✎ 其他,自己填…"
              />
            </div>
          </div>
        </template>
      </div>
      <div class="card-foot split">
        <button type="button" class="btn-ghost" @click="step = 1">← 上一步</button>
        <button
          v-if="!intentChecked"
          type="button"
          class="btn-primary"
          :disabled="intentLoading"
          @click="fetchIntentSuggestions"
        >
          {{ intentLoading ? '正在看 TA 在做什么…' : '下一步:明确意图 →' }}
        </button>
        <button v-else type="button" class="btn-primary" :disabled="diagnosing" @click="startDiagnose">
          {{ diagnosing ? '诊断中…' : '开始诊断' }}
        </button>
      </div>
      <LiveProgress v-if="diagnosing" />
    </section>

    <!-- ===== Step 3 · 诊断报告 ===== -->
    <template v-else>
      <div class="report-bar">
        <h2>诊断报告</h2>
        <div class="rb-actions">
          <button type="button" class="btn-ghost sm" :disabled="!report || exporting" @click="exportImage">
            {{ exporting ? '导出中…' : '导出图片' }}
          </button>
          <button type="button" class="btn-ghost sm" @click="restart">↻ 重新诊断</button>
        </div>
      </div>

      <div v-if="report" ref="reportEl" class="report-capture">
        <div class="capture-head">
          <div class="ch-left">
            <strong>{{ reportBloggerName || '对标分析报告' }}</strong>
            <span>对标分析 · 基于 {{ report.sample_count }} 篇笔记</span>
          </div>
          <span class="ch-date">{{ reportDate }}</span>
        </div>
        <AppraisalCard :report="report" />
      </div>
      <div v-else-if="diagnosing" class="report-loading card">
        <span class="spinner"></span>
        <p>正在诊断「{{ selectedName }}」 —— 看 TA 的硬实力、软实力、合规,大约需要 1 分钟…</p>
      </div>
      <div v-else class="report-loading card">
        <p>这次诊断没有完成。可能是任务还在后台跑,或中途失败了。</p>
        <button type="button" class="btn-primary" @click="restart">重新诊断</button>
      </div>
    </template>
  </section>
</template>

<style scoped>
.analysis {
  max-width: 1040px;
  margin: 0 auto;
}
.page-head {
  margin-bottom: 18px;
}
.page-head h1 {
  margin: 0 0 6px;
  font-size: 21px;
  font-weight: 680;
  letter-spacing: -0.01em;
}
.page-head p {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--color-ink-2);
  max-width: 560px;
}

/* Stepper */
.stepper {
  display: flex;
  align-items: center;
  padding: 14px 20px;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: 12px;
  margin-bottom: 18px;
}
.step-line {
  flex: 1;
  height: 1px;
  min-width: 18px;
  margin: 0 16px;
  background: #e3e5e8;
}
.step-line.done {
  background: var(--color-accent-soft-bd);
}
.step-node {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 0 0 auto;
}
.step-circle {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  font-size: 12.5px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.step-circle.cur {
  background: var(--color-accent);
  color: #fff;
}
.step-circle.done {
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
}
.step-circle.todo {
  background: var(--color-paper-3);
  color: var(--color-ink-3);
}
.step-label {
  font-size: 13.5px;
  white-space: nowrap;
}
.step-label.cur {
  color: var(--color-ink);
  font-weight: 620;
}
.step-label.done {
  color: #3a4048;
}
.step-label.todo {
  color: var(--color-ink-3);
}

/* Card shell */
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-paper-3);
}
.card-head.col {
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
  border-bottom: 0;
  padding-bottom: 4px;
}
.kicker {
  margin: 0 0 2px;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-accent-ink);
}
.card-head h2 {
  margin: 0;
  font-size: 15.5px;
  font-weight: 650;
}
.head-hint {
  font-size: 12.5px;
  color: var(--color-ink-3);
}
.card-head .sub {
  margin: 0;
  font-size: 12.5px;
  color: var(--color-ink-3);
  line-height: 1.6;
}
.card-head .sub b {
  color: #3a4048;
}

/* Step 1 grid */
.blogger-grid {
  padding: 14px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(248px, 1fr));
  gap: 10px;
}
.blogger-card {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 13px 15px;
  border: 1px solid var(--color-rule);
  border-radius: 12px;
  background: var(--color-surface);
  cursor: pointer;
  text-align: left;
  transition:
    border-color 140ms var(--ease-out),
    background 140ms var(--ease-out),
    box-shadow 140ms var(--ease-out);
}
.blogger-card:hover {
  border-color: var(--color-rule-strong);
}
.blogger-card.sel {
  border-color: var(--color-accent);
  background: var(--color-accent-tint);
  box-shadow: 0 1px 3px var(--color-shadow);
}
.avatar {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 11px;
  font-size: 17px;
  font-weight: 600;
  flex: 0 0 auto;
}
.b-body {
  flex: 1;
  min-width: 0;
}
.b-name {
  display: block;
  font-size: 14.5px;
  font-weight: 620;
  color: var(--color-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 6px;
}
.b-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.niche {
  flex: 0 0 auto;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11.5px;
  font-weight: 550;
  color: #2f6b54;
  background: var(--color-accent-soft);
}
.niche.muted {
  color: var(--color-ink-3);
  background: #f1f2f4;
}
.samples {
  font-size: 12px;
  color: var(--color-ink-3);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.radio {
  display: grid;
  place-items: center;
  width: 21px;
  height: 21px;
  border-radius: 50%;
  border: 1.5px solid #d4d8dd;
  font-size: 11px;
  font-weight: 800;
  flex: 0 0 auto;
  color: transparent;
  transition: all 140ms var(--ease-out);
}
.radio.on {
  border-color: var(--color-accent);
  background: var(--color-accent);
  color: #fff;
}

/* Step 2 form */
.card-body.form {
  padding: 18px 22px;
  display: grid;
  gap: 14px;
}
.field span {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #3a4048;
  margin-bottom: 7px;
}
.field em {
  color: var(--color-placeholder);
  font-weight: 500;
  font-style: normal;
}
.field input {
  width: 100%;
  height: 42px;
  padding: 0 14px;
  border: 1px solid var(--color-field-border);
  border-radius: 10px;
  background: var(--color-field);
  font-size: 14px;
  color: var(--color-ink);
}
.field.narrow {
  max-width: 320px;
}
.guide-rule {
  border-top: 1px dashed var(--color-rule);
  margin: 4px 0 2px;
}
.guide-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #3a4048;
}
.guide-hint .tick {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
  font-size: 13px;
  font-weight: 800;
  flex: 0 0 auto;
}
.intent-clear {
  margin: 0;
  font-size: 13px;
  color: var(--color-ok);
}
.guide-q .q-title {
  margin: 0 0 9px;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--color-ink);
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  padding: 7px 15px;
  border: 1px solid var(--color-field-border);
  border-radius: var(--radius-pill);
  background: var(--color-surface);
  color: var(--color-ink-2);
  font-size: 13px;
  font-weight: 550;
  cursor: pointer;
  transition:
    border-color 120ms var(--ease-out),
    background 120ms var(--ease-out),
    color 120ms var(--ease-out);
}
.chip:hover {
  border-color: var(--color-rule-strong);
}
.chip.on {
  border-color: var(--color-accent);
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
}
/* 「其他」做成虚线胶囊,和选项 chip 同排,一眼能看出是「选项 + 自己填」。 */
.chip-other {
  min-width: 150px;
  flex: 0 1 200px;
  padding: 7px 15px;
  border: 1px dashed var(--color-rule-strong);
  border-radius: var(--radius-pill);
  background: var(--color-surface);
  font-size: 13px;
  color: var(--color-ink);
  transition: border-color 120ms var(--ease-out);
}
.chip-other::placeholder {
  color: var(--color-placeholder);
}
.chip-other:focus {
  border-style: solid;
  border-color: var(--color-accent);
}

/* Card footer */
.card-foot {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding: 14px 20px;
  border-top: 1px solid var(--color-paper-3);
  background: #fafbfc;
}
.card-foot.split {
  justify-content: space-between;
}
.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 40px;
  padding: 0 20px;
  background: var(--color-accent);
  color: #fff;
  border: 0;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 620;
  cursor: pointer;
  transition: background 140ms var(--ease-out);
}
.btn-primary:hover {
  background: var(--color-accent-press);
}
.btn-primary:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.btn-ghost {
  height: 40px;
  padding: 0 16px;
  background: var(--color-surface);
  border: 1px solid var(--color-field-border);
  border-radius: 10px;
  font-size: 13.5px;
  font-weight: 550;
  color: var(--color-ink-2);
  cursor: pointer;
  transition: background 140ms var(--ease-out);
}
.btn-ghost:hover {
  background: #f7f8f9;
}
.btn-ghost.sm {
  height: 36px;
  padding: 0 14px;
  font-size: 13px;
  font-weight: 600;
}
.btn-ghost:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.empty-region.pad {
  padding: 28px 20px;
}

/* Step 3 report bar */
.report-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.report-bar h2 {
  margin: 0;
  font-size: 17px;
  font-weight: 680;
  letter-spacing: -0.01em;
}
.rb-actions {
  display: flex;
  gap: 8px;
}

/* 历史诊断列表 */
.hist-list {
  display: flex;
  flex-direction: column;
}
.hist-row {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  padding: 13px 20px;
  border: 0;
  border-top: 1px solid var(--color-paper-3);
  background: var(--color-surface);
  text-align: left;
  cursor: pointer;
  transition: background 120ms var(--ease-out);
}
.hist-row:first-child {
  border-top: 0;
}
.hist-row:hover {
  background: #fafbfc;
}
.hist-name {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hist-scores {
  display: flex;
  gap: 12px;
  flex: 0 0 auto;
  font-size: 12.5px;
  font-variant-numeric: tabular-nums;
}
.hist-scores em {
  font-style: normal;
  font-weight: 650;
}
.hist-scores .s-ok {
  color: var(--color-ok);
}
.hist-scores .s-warn {
  color: var(--color-warn);
}
.hist-scores .s-danger {
  color: var(--color-danger);
}
.hist-date {
  flex: 0 0 auto;
  font-size: 12px;
  color: var(--color-ink-3);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

/* 报告导出截取容器(导出图片时连这块一起渲染) */
.report-capture {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.capture-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 20px;
  background: var(--color-surface);
  border: 1px solid var(--color-rule);
  border-radius: var(--radius-lg);
}
.ch-left {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.ch-left strong {
  font-size: 16px;
  font-weight: 680;
  color: var(--color-ink);
}
.ch-left span {
  font-size: 12.5px;
  color: var(--color-ink-3);
}
.ch-date {
  flex: 0 0 auto;
  font-size: 12.5px;
  color: var(--color-ink-3);
  font-variant-numeric: tabular-nums;
}
.report-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 48px 24px;
  text-align: center;
  color: var(--color-ink-2);
  font-size: 13.5px;
  line-height: 1.6;
}
.spinner {
  width: 26px;
  height: 26px;
  border: 3px solid var(--color-paper-3);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
@media (prefers-reduced-motion: reduce) {
  .spinner {
    animation-duration: 1.6s;
  }
}

@media (max-width: 560px) {
  .step-label {
    display: none;
  }
  .step-line {
    margin: 0 8px;
  }
}
</style>
