<script setup lang="ts">
// 对标分析(诊断别人):三步向导 —— ① 选对标博主 ② 明确意图 ③ 诊断报告。
// 第 2 步是「意图录入 → 内嵌进度卡 → 答题打卡」三小阶段的状态机(intentPhase),一次只问一道题;
// 进度卡由两次真实后端往返(读笔记 / 模型出题)点亮,不按时间假装分阶段完成。
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { toPng } from 'html-to-image'
import AppraisalCard from '../components/AppraisalCard.vue'
import LiveProgress from '../components/LiveProgress.vue'
import type { AccountAuditRun, AppraisalIntentQuestion } from '../api/types'
import {
  appraiseForm,
  appraisalHistory,
  appraisalRun,
  benchmarkAccounts,
  bloggers,
  myAccountsOnPlatform,
  currentSocialPlatformName,
  currentSocialTab,
  fetchIntentContext,
  fetchIntentSuggestions,
  formatDate,
  handleRunAppraisal,
  intentOthers,
  intentQuestions,
  intentSelections,
  isSocialPlatform,
  markIntentSkipped,
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

// —— 第 2 步·意图状态机(本地) ——
type IntentPhase = 'intro' | 'analyzing' | 'quiz'
const intentPhase = ref<IntentPhase>('intro')
const stageStep = ref(0) // 进度卡阶段:0=读取笔记(context 在飞) 1=拆解/出题(suggest 在飞)
const noteCount = ref<number | null>(null) // context 返回的真实近期笔记数
const analyzeError = ref('')
const quizIndex = ref(0) // 当前第几题(0-based)
const analyzeStartMs = ref(0)
const elapsedMs = ref(0)
let elapsedTimer: number | undefined

// 进度卡三段(第一段带真实笔记数)。接真实事件推进,不按 elapsed 假装完成。
const analyzeStages: ((n: number | null) => string)[] = [
  (n) => `读取 TA 最近 ${n ?? '…'} 篇笔记`,
  () => '拆解 TA 的选题与风格方向',
  () => '生成帮你明确意图的问题'
]
const elapsedLabel = computed(() => `${(elapsedMs.value / 1000).toFixed(1)}s`)

function stageStatus(i: number): 'done' | 'active' | 'pending' {
  if (i < stageStep.value) return 'done'
  if (i === stageStep.value) return 'active'
  return 'pending'
}
function startElapsedTimer() {
  stopElapsedTimer()
  elapsedMs.value = 0
  analyzeStartMs.value = Date.now()
  elapsedTimer = window.setInterval(() => {
    elapsedMs.value = Date.now() - analyzeStartMs.value
  }, 200)
}
function stopElapsedTimer() {
  if (elapsedTimer) {
    window.clearInterval(elapsedTimer)
    elapsedTimer = undefined
  }
}

// 点「明确意图」→ 两次真实往返:读笔记(点亮第一段)→ 模型出题(点亮后两段)→ 进答题。
async function checkIntent() {
  if (!appraiseForm.blogger_id) {
    showMessage('请先选择要诊断的博主', true)
    return
  }
  analyzeError.value = ''
  noteCount.value = null
  stageStep.value = 0
  intentPhase.value = 'analyzing'
  startElapsedTimer()
  try {
    const ctx = await fetchIntentContext(appraiseForm.blogger_id)
    noteCount.value = ctx.note_count
    stageStep.value = 1
    await fetchIntentSuggestions()
    quizIndex.value = 0
    intentPhase.value = 'quiz'
  } catch (err) {
    // 失败态:留在进度卡展示重试 / 跳过,不卡在转圈。
    analyzeError.value = err instanceof Error ? err.message : '分析失败,请重试'
  } finally {
    stopElapsedTimer()
  }
}
// 引导失败时「跳过,直接诊断」:视为意图已明确,进 quiz(0 题)直接可开始诊断。
function skipGuide() {
  markIntentSkipped()
  analyzeError.value = ''
  quizIndex.value = 0
  intentPhase.value = 'quiz'
}

// —— 答题打卡 ——
const curQuestion = computed<AppraisalIntentQuestion | null>(() => intentQuestions.value[quizIndex.value] || null)
const answeredQuestions = computed(() => intentQuestions.value.slice(0, quizIndex.value))
const pendingQuestions = computed(() => intentQuestions.value.slice(quizIndex.value + 1))
const isLastQuestion = computed(() => quizIndex.value >= intentQuestions.value.length - 1)
const curAnswered = computed(() => {
  if (!curQuestion.value) return false
  const sel = intentSelections[quizIndex.value] || []
  const other = (intentOthers[quizIndex.value] || '').trim()
  return sel.length > 0 || other.length > 0
})

function isPicked(qi: number, opt: string): boolean {
  return (intentSelections[qi] || []).includes(opt)
}
function pickOption(q: AppraisalIntentQuestion, opt: string) {
  const qi = quizIndex.value
  const arr = intentSelections[qi] || (intentSelections[qi] = [])
  const idx = arr.indexOf(opt)
  if (q.multi === false) {
    intentSelections[qi] = idx >= 0 ? [] : [opt] // 单选:点已选取消,点别的替换
  } else if (idx >= 0) {
    arr.splice(idx, 1)
  } else {
    arr.push(opt)
  }
}
function answerOf(qi: number): string[] {
  const picked = [...(intentSelections[qi] || [])]
  const other = (intentOthers[qi] || '').trim()
  if (other) picked.push(other)
  return picked
}
function segClass(i: number): 'done' | 'cur' | 'todo' {
  return i < quizIndex.value ? 'done' : i === quizIndex.value ? 'cur' : 'todo'
}
function prevQuiz() {
  if (quizIndex.value === 0) intentPhase.value = 'intro'
  else quizIndex.value -= 1
}
function nextQuiz() {
  if (quizIndex.value < intentQuestions.value.length - 1) quizIndex.value += 1
}
function editAnswer(qi: number) {
  quizIndex.value = qi
}

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
// 只显示「当前选中博主」的历史诊断(选中某个博主后才出现该博主的历史)。
const selectedHistory = computed(() =>
  appraiseForm.blogger_id
    ? historyItems.value.filter((it) => it.run.benchmark_blogger_id === appraiseForm.blogger_id)
    : []
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

// 第 2 步意图状态机复位(换博主 / 重新诊断时)。
function resetIntentFlow() {
  stopElapsedTimer()
  intentPhase.value = 'intro'
  stageStep.value = 0
  noteCount.value = null
  analyzeError.value = ''
  quizIndex.value = 0
}

function pick(id: number) {
  appraiseForm.blogger_id = appraiseForm.blogger_id === id ? 0 : id
  resetIntentGuide()
  resetIntentFlow()
}

async function startDiagnose() {
  step.value = 3
  await handleRunAppraisal()
  refreshAppraisalHistory() // 新报告进历史
}
function restart() {
  resetIntentGuide()
  resetIntentFlow()
  step.value = 1
}
// 查看一条历史报告:弹框展示(不动向导当前步、不覆盖当前 appraisalRun)。
const historyModalRun = ref<AccountAuditRun | null>(null)
const historyModalReport = computed(() => (historyModalRun.value ? parseAppraisalReport(historyModalRun.value) : null))
const historyModalName = computed(() => (historyModalRun.value ? bloggerNameById(historyModalRun.value.benchmark_blogger_id) : ''))
const historyModalDate = computed(() => (historyModalRun.value ? formatDate(historyModalRun.value.created_at) : ''))
function openHistoryRun(run: AccountAuditRun) {
  historyModalRun.value = run
}
function closeHistoryModal() {
  historyModalRun.value = null
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
onUnmounted(() => {
  stopElapsedTimer()
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
      <p v-else class="empty-region pad">对标库还没有博主,先去「查找博主」加一个。</p>
      <div
        v-if="myAccountsOnPlatform.length"
        style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:14px;font-size:13px;color:var(--color-ink-2)"
      >
        <label>结合我的账号(可选)</label>
        <select
          v-model.number="appraiseForm.my_blogger_id"
          style="height:32px;padding:0 10px;border:1px solid var(--color-field-border);border-radius:8px;background:var(--color-field);font-size:13px"
        >
          <option :value="0">不结合</option>
          <option v-for="a in myAccountsOnPlatform" :key="a.id" :value="a.id">{{ a.display_name }}</option>
        </select>
        <span style="font-size:12px;color:var(--color-ink-3)">绑定后报告会多出「我 vs TA 差距」</span>
      </div>
      <div class="card-foot">
        <button type="button" class="btn-primary" :disabled="!appraiseForm.blogger_id" @click="step = 2">下一步 →</button>
      </div>
      </section>

      <!-- 历史诊断:仅当前选中博主,点一条弹框查看 -->
      <section v-if="selectedBlogger && selectedHistory.length" class="card history">
        <div class="card-head">
          <h2>历史诊断</h2>
          <span class="head-hint">点一条查看「{{ selectedName }}」的历史报告</span>
        </div>
        <div class="hist-list">
          <button
            v-for="it in selectedHistory"
            :key="it.run.id"
            type="button"
            class="hist-row"
            @click="openHistoryRun(it.run)"
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

    <!-- ===== Step 2 · 明确意图(意图录入 → 内嵌进度 → 答题打卡) ===== -->
    <section v-else-if="step === 2" class="card">
      <div class="card-head col">
        <p class="kicker">第 2 步 / 共 3 步</p>
        <h2>明确你的对标意图</h2>
        <p class="sub">
          正在诊断「<b>{{ selectedName }}</b>」。先说说你想从 TA 身上学什么,我们会看 TA 在做什么、再用几道选择题帮你把意图问清楚。
        </p>
      </div>

      <!-- 阶段 A · 意图录入 -->
      <template v-if="intentPhase === 'intro'">
        <div class="card-body form">
          <label class="field">
            <span>你想学什么 / 对标意图 <em>(可不填)</em></span>
            <input v-model="appraiseForm.intent" type="text" placeholder="例:想学把香港保险讲得专业、又有人看、能涨粉" />
          </label>
          <label class="field narrow">
            <span>品类 <em>(可选,触发合规红线)</em></span>
            <input v-model="appraiseForm.industry" type="text" placeholder="保险 / 金融 / 医疗 / 美妆…" />
          </label>
        </div>
        <div class="card-foot split">
          <button type="button" class="btn-ghost" @click="step = 1">← 上一步</button>
          <button type="button" class="btn-primary" @click="checkIntent">下一步:明确意图 →</button>
        </div>
      </template>

      <!-- 阶段 B · 分析中(内嵌进度卡,真实事件驱动) -->
      <div v-else-if="intentPhase === 'analyzing'" class="card-body analyze">
        <div class="progress-card" :class="{ failed: !!analyzeError }" role="status" aria-live="polite">
          <div class="pc-head">
            <span v-if="!analyzeError" class="pc-spin" aria-hidden="true"></span>
            <span v-else class="pc-fail" aria-hidden="true">!</span>
            <span class="pc-title">{{ analyzeError ? '分析没能完成' : '正在看 TA 最近在做什么…' }}</span>
            <span v-if="!analyzeError" class="pc-elapsed">{{ elapsedLabel }}</span>
          </div>

          <ol v-if="!analyzeError" class="pc-stages">
            <li v-for="(s, i) in analyzeStages" :key="i" :class="stageStatus(i)">
              <span class="pc-dot" aria-hidden="true"><span v-if="stageStatus(i) === 'done'" class="pc-check">✓</span></span>
              <span class="pc-step">{{ s(noteCount) }}</span>
            </li>
          </ol>

          <template v-if="!analyzeError">
            <div class="pc-bar" aria-hidden="true"><i></i></div>
            <p class="pc-hint">通常需要 5–10 秒;TA 的笔记越多,问得越准。</p>
          </template>
          <template v-else>
            <p class="pc-error">{{ analyzeError }}</p>
            <div class="pc-actions">
              <button type="button" class="btn-primary" @click="checkIntent">↻ 重试</button>
              <button type="button" class="btn-ghost" @click="skipGuide">跳过,直接诊断 →</button>
            </div>
          </template>
        </div>
      </div>

      <!-- 阶段 C · 答题打卡(一次一题) -->
      <div v-else class="card-body quiz">
        <!-- 顶部进度 -->
        <div v-if="intentQuestions.length" class="quiz-progress">
          <span class="qp-label">明确意图 · 已答 {{ quizIndex }} / {{ intentQuestions.length }}</span>
          <div class="qp-track">
            <i v-for="i in intentQuestions.length" :key="i" :class="segClass(i - 1)"></i>
          </div>
        </div>

        <!-- 已答堆叠 -->
        <button
          v-for="(q, qi) in answeredQuestions"
          :key="'a' + qi"
          type="button"
          class="answered"
          @click="editAnswer(qi)"
        >
          <span class="ans-dot" aria-hidden="true">✓</span>
          <span class="ans-body">
            <span class="ans-q">{{ q.q }}</span>
            <span class="ans-chips">
              <em v-for="a in answerOf(qi)" :key="a" class="ans-chip">{{ a }}</em>
              <em v-if="!answerOf(qi).length" class="ans-chip skipped">已跳过</em>
            </span>
          </span>
          <span class="ans-edit">修改</span>
        </button>

        <!-- 当前题 -->
        <div v-if="curQuestion" class="current">
          <div class="cur-head">
            <span class="cur-pill">第 {{ quizIndex + 1 }} 题</span>
            <span class="cur-hint">{{ curQuestion.multi === false ? '单选' : '可多选' }}</span>
          </div>
          <p class="cur-q">{{ curQuestion.q }}</p>
          <div class="cur-options">
            <button
              v-for="opt in curQuestion.options"
              :key="opt"
              type="button"
              class="opt"
              :class="{ on: isPicked(quizIndex, opt) }"
              @click="pickOption(curQuestion, opt)"
            >
              <span class="opt-dot" aria-hidden="true"><span v-if="isPicked(quizIndex, opt)">✓</span></span>
              <span>{{ opt }}</span>
            </button>
          </div>
          <input
            v-if="curQuestion.allow_other !== false"
            v-model="intentOthers[quizIndex]"
            class="cur-other"
            type="text"
            placeholder="✎ 其他,自己填…"
          />
        </div>

        <!-- 无需追问(意图已清楚) -->
        <div v-else class="cur-clear">
          <span class="cc-tick" aria-hidden="true">✓</span>
          <p>你的意图已经清楚,可以直接开始诊断。</p>
        </div>

        <!-- 未答占位 -->
        <div v-for="(q, pi) in pendingQuestions" :key="'p' + pi" class="pending">
          <span class="pend-n">{{ quizIndex + 2 + pi }}</span>
          <span class="pend-q">{{ q.q }}</span>
        </div>

        <!-- 底部导航 -->
        <div class="quiz-foot">
          <button type="button" class="btn-ghost" @click="prevQuiz">{{ quizIndex === 0 ? '← 上一步' : '← 上一题' }}</button>
          <button
            v-if="!isLastQuestion"
            type="button"
            class="btn-primary"
            :disabled="!curAnswered"
            @click="nextQuiz"
          >下一题 →</button>
          <button v-else type="button" class="btn-primary" :disabled="diagnosing" @click="startDiagnose">
            {{ diagnosing ? '诊断中…' : '开始诊断' }}
          </button>
        </div>
      </div>
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
      <LiveProgress v-else-if="diagnosing" />
      <div v-else class="report-loading card">
        <p>这次诊断没有完成。可能是任务还在后台跑,或中途失败了。</p>
        <button type="button" class="btn-primary" @click="restart">重新诊断</button>
      </div>
    </template>

    <!-- 历史诊断弹框:点历史条目在此查看,不跳向导步骤、也不覆盖当前诊断 -->
    <div v-if="historyModalRun && historyModalReport" class="hist-modal-overlay" @click.self="closeHistoryModal">
      <div class="hist-modal">
        <div class="hm-head">
          <div class="hm-title">
            <strong>{{ historyModalName || '对标分析报告' }}</strong>
            <span>对标分析 · 基于 {{ historyModalReport.sample_count }} 篇笔记 · {{ historyModalDate }}</span>
          </div>
          <button type="button" class="hm-close" aria-label="关闭" @click="closeHistoryModal">✕</button>
        </div>
        <div class="hm-body">
          <AppraisalCard :report="historyModalReport" />
        </div>
      </div>
    </div>
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

/* Step 2 · intro 表单 */
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

/* Step 2 · analyzing — 内嵌进度卡(真实事件驱动) */
.card-body.analyze {
  padding: 18px 22px;
}
.progress-card {
  background: var(--color-accent-tint);
  border: 1px solid var(--color-accent-soft-bd);
  border-radius: 12px;
  padding: 16px 18px;
}
.progress-card.failed {
  background: #fdf3f2;
  border-color: #f0d3d0;
}
.pc-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.pc-spin {
  width: 18px;
  height: 18px;
  flex: 0 0 auto;
  border: 2px solid var(--color-accent-soft-bd);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
.pc-fail {
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: var(--color-danger);
  color: #fff;
  font-size: 13px;
  font-weight: 800;
}
.pc-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
}
.pc-elapsed {
  margin-left: auto;
  font-size: 12.5px;
  color: var(--color-ink-3);
  font-variant-numeric: tabular-nums;
}
.pc-stages {
  list-style: none;
  margin: 14px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 11px;
}
.pc-stages li {
  display: flex;
  align-items: center;
  gap: 10px;
}
.pc-dot {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  flex: 0 0 auto;
  border-radius: 50%;
  border: 1.5px solid #cfd6d2;
  background: transparent;
  transition: all 160ms var(--ease-out);
}
.pc-stages li.active .pc-dot {
  border-color: var(--color-accent);
  animation: pulse 1.4s ease-in-out infinite;
}
.pc-stages li.done .pc-dot {
  border-color: var(--color-accent);
  background: var(--color-accent);
}
.pc-check {
  color: #fff;
  font-size: 10px;
  font-weight: 800;
  line-height: 1;
}
.pc-step {
  font-size: 13.5px;
  color: #9aa1aa;
}
.pc-stages li.active .pc-step {
  color: var(--color-ink);
  font-weight: 600;
}
.pc-stages li.done .pc-step {
  color: var(--color-ink-2);
}
.pc-bar {
  margin-top: 16px;
  height: 4px;
  border-radius: 999px;
  background: #e0eee7;
  overflow: hidden;
}
.pc-bar i {
  display: block;
  width: 38%;
  height: 100%;
  border-radius: 999px;
  background: var(--color-accent);
  animation: indet 1.3s ease-in-out infinite;
}
.pc-hint {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--color-ink-3);
}
.pc-error {
  margin: 12px 0 0;
  font-size: 13px;
  color: var(--color-danger);
  line-height: 1.6;
}
.pc-actions {
  margin-top: 14px;
  display: flex;
  gap: 10px;
}

/* Step 2 · quiz — 答题打卡 */
.card-body.quiz {
  padding: 18px 22px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.quiz-progress {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.qp-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-accent-ink);
  font-variant-numeric: tabular-nums;
}
.qp-track {
  display: flex;
  gap: 6px;
}
.qp-track i {
  flex: 1;
  height: 5px;
  border-radius: 999px;
  background: #e6e8eb;
  transition: background 200ms var(--ease-out);
}
.qp-track i.done {
  background: var(--color-accent);
}
.qp-track i.cur {
  background: var(--color-accent-soft-bd);
}

/* 已答堆叠 */
.answered {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
  padding: 12px 14px;
  border: 1px solid #eef0f2;
  border-radius: 12px;
  background: #fafbfc;
  text-align: left;
  cursor: pointer;
  transition:
    background 120ms var(--ease-out),
    border-color 120ms var(--ease-out);
}
.answered:hover {
  background: #f5f7f8;
  border-color: var(--color-rule);
}
.ans-dot {
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  flex: 0 0 auto;
  margin-top: 1px;
  border-radius: 50%;
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
  font-size: 11px;
  font-weight: 800;
}
.ans-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.ans-q {
  font-size: 13px;
  color: var(--color-ink-3);
}
.ans-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.ans-chip {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-style: normal;
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
}
.ans-chip.skipped {
  background: #f1f2f4;
  color: var(--color-ink-3);
}
.ans-edit {
  flex: 0 0 auto;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--color-accent-ink);
}

/* 当前题(聚焦) */
.current {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 18px;
  background: var(--color-surface);
  border: 1px solid var(--color-accent-soft-bd);
  border-radius: 14px;
  box-shadow: 0 2px 12px -7px rgba(13, 90, 74, 0.35);
}
.cur-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.cur-pill {
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--color-accent);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}
.cur-hint {
  font-size: 12px;
  color: var(--color-ink-3);
}
.cur-q {
  margin: 0;
  font-size: 16px;
  font-weight: 650;
  color: var(--color-ink);
  line-height: 1.5;
}
.cur-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.opt {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 9px 14px;
  border: 1px solid var(--color-field-border);
  border-radius: 10px;
  background: var(--color-surface);
  color: var(--color-ink-2);
  font-size: 13.5px;
  font-weight: 550;
  cursor: pointer;
  transition:
    border-color 120ms var(--ease-out),
    background 120ms var(--ease-out),
    color 120ms var(--ease-out);
}
.opt:hover {
  border-color: var(--color-rule-strong);
}
.opt.on {
  border-color: var(--color-accent);
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
}
.opt-dot {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  flex: 0 0 auto;
  border-radius: 50%;
  border: 1.5px solid #d4d8dd;
  color: #fff;
  font-size: 10px;
  font-weight: 800;
  transition: all 120ms var(--ease-out);
}
.opt.on .opt-dot {
  border-color: var(--color-accent);
  background: var(--color-accent);
}
.cur-other {
  width: 100%;
  height: 40px;
  padding: 0 14px;
  border: 1px dashed var(--color-rule-strong);
  border-radius: 10px;
  background: var(--color-surface);
  font-size: 13.5px;
  color: var(--color-ink);
  transition: border-color 120ms var(--ease-out);
}
.cur-other::placeholder {
  color: var(--color-placeholder);
}
.cur-other:focus {
  border-style: solid;
  border-color: var(--color-accent);
  outline: none;
}

/* 意图已清楚(0 题) */
.cur-clear {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 18px;
  background: var(--color-accent-tint);
  border: 1px solid var(--color-accent-soft-bd);
  border-radius: 14px;
}
.cc-tick {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: var(--color-accent-soft);
  color: var(--color-accent-ink);
  font-size: 13px;
  font-weight: 800;
}
.cur-clear p {
  margin: 0;
  font-size: 14px;
  color: var(--color-ink-2);
}

/* 未答占位 */
.pending {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 14px;
  border: 1px dashed #e6e8eb;
  border-radius: 10px;
  opacity: 0.65;
}
.pend-n {
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  flex: 0 0 auto;
  border-radius: 50%;
  border: 1.5px solid #dfe2e6;
  color: #9aa1aa;
  font-size: 11px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.pend-q {
  font-size: 13.5px;
  color: #9aa1aa;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.quiz-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 4px;
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
@keyframes pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(13, 115, 97, 0.35);
  }
  50% {
    box-shadow: 0 0 0 4px rgba(13, 115, 97, 0);
  }
}
@keyframes indet {
  0% {
    transform: translateX(-120%);
  }
  100% {
    transform: translateX(360%);
  }
}
@media (prefers-reduced-motion: reduce) {
  .spinner,
  .pc-spin {
    animation-duration: 1.6s;
  }
  .pc-stages li.active .pc-dot {
    animation: none;
  }
  .pc-bar i {
    animation: none;
    width: 100%;
    opacity: 0.5;
  }
}

/* 历史诊断弹框 */
.hist-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(20, 24, 28, 0.4);
  animation: hm-fade 160ms var(--ease-out);
}
.hist-modal {
  width: min(920px, 100%);
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  background: var(--color-paper);
  border-radius: 16px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.25);
  overflow: hidden;
}
.hm-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 20px;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-rule);
  flex: 0 0 auto;
}
.hm-title {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.hm-title strong {
  font-size: 16px;
  font-weight: 680;
  color: var(--color-ink);
}
.hm-title span {
  font-size: 12.5px;
  color: var(--color-ink-3);
  font-variant-numeric: tabular-nums;
}
.hm-close {
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 50%;
  background: var(--color-paper-3);
  color: var(--color-ink-2);
  font-size: 14px;
  cursor: pointer;
  transition: background 120ms var(--ease-out);
}
.hm-close:hover {
  background: var(--color-rule-strong);
}
.hm-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 18px 20px;
}
@keyframes hm-fade {
  from { opacity: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .hist-modal-overlay {
    animation: none;
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
