<script setup lang="ts">
// 账号体检(「我的账号」页的「体检」视图):可选意图 → 一键体检 → 评分报告 + 历史。
// 复用 appraisal 引擎(kind=self,硬实力 × 合规 × 目标契合);数据吃档案已入池的列表级笔记,≥5 篇即可。
import { computed, ref, watch } from 'vue'
import { toPng } from 'html-to-image'

import type { AccountAuditRun, BloggerProfile } from '../../api/types'
import AppraisalCard from '../AppraisalCard.vue'
import LiveProgress from '../LiveProgress.vue'
import {
  formatDate,
  handleRunSelfAppraisal,
  parseAppraisalReport,
  pendingAction,
  refreshSelfAppraisalHistory,
  selfAppraisalHistory,
  selfAppraisalRun,
  selfAppraiseForm,
  showMessage
} from '../../composables/useWorkspaceStore'

const props = defineProps<{ blogger: BloggerProfile; poolTotal: number; busy: boolean }>()

const MIN_POOL = 5
const canDiagnose = computed(() => props.poolTotal >= MIN_POOL)
const diagnosing = computed(() => pendingAction.value === 'audit')
const report = computed(() => parseAppraisalReport(selfAppraisalRun.value))
const reportEl = ref<HTMLElement | null>(null)
const exporting = ref(false)
const historyRun = ref<AccountAuditRun | null>(null)
const historyReport = computed(() => parseAppraisalReport(historyRun.value))

// 本账号的历史体检(按 my_blogger_id 过滤,新→旧)。
const historyItems = computed(() =>
  selfAppraisalHistory.value
    .filter((r) => r.my_blogger_id === props.blogger.id)
    .map((run) => ({ run, report: parseAppraisalReport(run), date: formatDate(run.created_at) }))
    .filter((it) => it.report)
)

// 切账号:表单指向当前号、清意图/上次报告,展示本号最近一次体检(若有)。
watch(
  () => props.blogger.id,
  (id) => {
    selfAppraiseForm.blogger_id = id
    selfAppraiseForm.intent = ''
    const latest = selfAppraisalHistory.value.find((r) => r.my_blogger_id === id && parseAppraisalReport(r))
    selfAppraisalRun.value = latest ?? null
  },
  { immediate: true }
)

function band(n: number): string {
  return n >= 80 ? 'good' : n >= 60 ? 'mid' : 'low'
}

async function run() {
  if (!canDiagnose.value) {
    showMessage(`笔记池不足 ${MIN_POOL} 篇,先到「档案」完成全量入池`, true)
    return
  }
  await handleRunSelfAppraisal()
  await refreshSelfAppraisalHistory()
}

async function exportImage() {
  const el = reportEl.value
  if (!el || !report.value) return
  exporting.value = true
  try {
    const url = await toPng(el, { pixelRatio: 2, backgroundColor: '#fff' })
    const a = document.createElement('a')
    a.download = `${props.blogger.display_name}-账号体检.png`
    a.href = url
    a.click()
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <section class="au">
    <!-- 门控:池不足 5 篇不能体检 -->
    <div v-if="!canDiagnose" class="au__gate">
      笔记池还不足 {{ MIN_POOL }} 篇 —— 先到「档案」页把「笔记池」全量入池,就能体检了。
    </div>

    <template v-else>
      <!-- 运行栏:可选意图 + 一键体检 -->
      <div class="au__run">
        <label class="au__intent">
          <span>这轮想重点看什么?<em>可留空</em></span>
          <textarea
            v-model="selfAppraiseForm.intent"
            rows="2"
            placeholder="例:涨粉卡住 / 转化低 / 想做垂类…(填了才多出「目标契合」一维)"
            :disabled="busy"
          ></textarea>
        </label>
        <button type="button" class="au__go" :disabled="busy" @click="run">
          {{ diagnosing ? '体检中…' : report ? '重新体检' : '运行体检' }}
        </button>
      </div>

      <LiveProgress v-if="diagnosing" />

      <!-- 报告 -->
      <template v-else-if="report">
        <div class="au__rbar">
          <h3>体检报告</h3>
          <button type="button" class="au__ghost" :disabled="exporting" @click="exportImage">
            {{ exporting ? '导出中…' : '导出图片' }}
          </button>
        </div>
        <div ref="reportEl" class="au__capture">
          <div class="au__caphead">
            <strong>{{ blogger.display_name }}</strong>
            <span>账号体检 · 基于 {{ report.sample_count }} 篇笔记 · {{ formatDate(selfAppraisalRun!.created_at) }}</span>
          </div>
          <AppraisalCard :report="report" />
        </div>
      </template>

      <p v-else class="au__empty">还没体检过这个账号。填上(可选)想看的重点,点「运行体检」。</p>

      <!-- 体检记录(>1 条才显示;点开看历史报告,不覆盖当前) -->
      <div v-if="historyItems.length > 1" class="au__hist">
        <h4>体检记录</h4>
        <ul>
          <li v-for="it in historyItems" :key="it.run.id">
            <button type="button" class="au__histrow" @click="historyRun = it.run">
              <span class="au__histdate">{{ it.date }}</span>
              <span class="au__histscores">
                <em :class="band(it.report!.hard_score)">实力 {{ it.report!.hard_score }}</em>
                <em v-if="it.report!.goal_fit" :class="band(it.report!.goal_fit.score)">契合 {{ it.report!.goal_fit.score }}</em>
                <em :class="band(it.report!.compliance.score)">合规 {{ it.report!.compliance.score }}</em>
              </span>
            </button>
          </li>
        </ul>
      </div>
    </template>

    <!-- 历史弹框 -->
    <div v-if="historyRun && historyReport" class="au__overlay" @click.self="historyRun = null">
      <div class="au__modal">
        <div class="au__mhead">
          <div>
            <strong>{{ blogger.display_name }}</strong>
            <span>账号体检 · 基于 {{ historyReport.sample_count }} 篇 · {{ formatDate(historyRun.created_at) }}</span>
          </div>
          <button type="button" class="au__mclose" aria-label="关闭" @click="historyRun = null">✕</button>
        </div>
        <div class="au__mbody"><AppraisalCard :report="historyReport" /></div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.au { display: flex; flex-direction: column; gap: 14px; }
.au__gate {
  padding: 16px 18px; border: 1px dashed var(--color-rule-strong); border-radius: 12px;
  font-size: 13px; color: var(--color-ink-2); background: var(--color-surface);
}
.au__run {
  display: flex; gap: 12px; align-items: flex-end;
  border: 1px solid var(--color-rule); border-radius: var(--radius-lg); background: var(--color-surface); padding: 14px 16px;
}
.au__intent { flex: 1; display: flex; flex-direction: column; gap: 6px; }
.au__intent span { font-size: 12.5px; color: var(--color-ink-2); }
.au__intent em { font-style: normal; margin-left: 6px; color: var(--color-ink-3); }
.au__intent textarea {
  width: 100%; resize: vertical; border: 1px solid var(--color-field-border); border-radius: 9px;
  padding: 8px 10px; font-size: 13px; font-family: inherit; color: var(--color-ink); background: var(--color-surface);
}
.au__go {
  flex: 0 0 auto; height: 38px; padding: 0 18px; border: 0; border-radius: 9px;
  background: var(--color-accent); color: #fff; font-size: 13.5px; font-weight: 620; cursor: pointer;
}
.au__go:disabled { opacity: 0.45; cursor: not-allowed; }
.au__rbar { display: flex; align-items: center; justify-content: space-between; }
.au__rbar h3 { margin: 0; font-size: 15px; font-weight: 680; }
.au__ghost {
  height: 30px; padding: 0 12px; border: 1px solid var(--color-field-border); border-radius: 8px;
  background: var(--color-surface); color: var(--color-ink-2); font-size: 12.5px; cursor: pointer;
}
.au__ghost:disabled { opacity: 0.45; cursor: not-allowed; }
.au__capture { display: flex; flex-direction: column; gap: 12px; }
.au__caphead { display: flex; flex-direction: column; gap: 2px; }
.au__caphead strong { font-size: 15px; }
.au__caphead span { font-size: 12px; color: var(--color-ink-3); }
.au__empty { font-size: 13px; color: var(--color-ink-3); margin: 0; }
.au__hist h4 { margin: 4px 0 8px; font-size: 13px; font-weight: 640; color: var(--color-ink-2); }
.au__hist ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.au__histrow {
  width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 12px;
  border: 1px solid var(--color-rule); border-radius: 9px; background: var(--color-surface);
  padding: 9px 12px; cursor: pointer; font-size: 12.5px; color: var(--color-ink-2);
}
.au__histrow:hover { border-color: var(--color-accent); }
.au__histscores { display: flex; gap: 8px; }
.au__histscores em { font-style: normal; font-weight: 600; }
.au__histscores em.good { color: #2e7d32; }
.au__histscores em.mid { color: #b7791f; }
.au__histscores em.low { color: #c0392b; }
.au__overlay {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.4); display: grid; place-items: center; z-index: 60; padding: 20px;
}
.au__modal {
  width: min(920px, 96vw); max-height: 90vh; overflow: auto; background: var(--color-surface);
  border-radius: 14px; padding: 18px 20px;
}
.au__mhead { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.au__mhead strong { font-size: 15px; display: block; }
.au__mhead span { font-size: 12px; color: var(--color-ink-3); }
.au__mclose {
  flex: 0 0 auto; width: 30px; height: 30px; border: 1px solid var(--color-field-border); border-radius: 8px;
  background: var(--color-surface); color: var(--color-ink-2); cursor: pointer; font-size: 14px;
}
</style>
