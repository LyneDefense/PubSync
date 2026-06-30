<script setup lang="ts">
// 诊断我的账号(评估与提升):给自己的号做体检(硬实力 × 合规,无软实力)。诊断前自动确保 ≥20 篇笔记。
// 找差距(我 vs 对标)同属本模块,下一轮上线。
import { computed } from 'vue'
import AppraisalCard from '../components/AppraisalCard.vue'
import LiveProgress from '../components/LiveProgress.vue'
import {
  currentSocialPlatformName,
  currentSocialTab,
  fetchSelfIntentSuggestions,
  handleRunSelfAppraisal,
  isSocialPlatform,
  myAccounts,
  openCreateMyAccountModal,
  parseAppraisalReport,
  pendingAction,
  resetSelfIntentGuide,
  selfAppraiseForm,
  selfAppraisalRun,
  selfIntentChecked,
  selfIntentClear,
  selfIntentLoading,
  selfIntentOthers,
  selfIntentQuestions,
  selfIntentSelections
} from '../composables/useWorkspaceStore'

const report = computed(() => parseAppraisalReport(selfAppraisalRun.value))

// 切账号要重置意图引导(每个号目标不同,得重新理清)。
function pickAccount(id: number) {
  if (selfAppraiseForm.blogger_id === id) return
  selfAppraiseForm.blogger_id = id
  selfAppraiseForm.intent = ''
  resetSelfIntentGuide()
}
function toggleSelfChip(qi: number, opt: string) {
  const arr = selfIntentSelections[qi] || (selfIntentSelections[qi] = [])
  const i = arr.indexOf(opt)
  if (i >= 0) arr.splice(i, 1)
  else arr.push(opt)
}
// 理清意图后(出了题 / 或意图已清晰)或用户已手填一句,才放行「开始诊断」——逼着先想清诊断目标。
const canDiagnose = computed(
  () => Boolean(selfAppraiseForm.blogger_id) && (selfIntentChecked.value || selfAppraiseForm.intent.trim().length > 0)
)
</script>

<template>
  <section v-if="isSocialPlatform && currentSocialTab === 'self-diagnosis'" class="panel">
    <div class="section-header">
      <div>
        <h2>诊断我的{{ currentSocialPlatformName }}账号</h2>
        <p class="toolbar-subtitle">给自己的号做体检:硬实力(体量 / 互动 / 爆款 / 活跃 / 垂直)× 合规。诊断前会自动确保 ≥20 篇笔记。</p>
      </div>
    </div>

    <div class="block">
      <h3>① 选择我的账号</h3>
      <div v-if="myAccounts.length" class="blogger-list compact">
        <button
          v-for="acc in myAccounts"
          :key="acc.id"
          type="button"
          :class="{ active: selfAppraiseForm.blogger_id === acc.id }"
          @click="pickAccount(acc.id)"
        >
          <strong>{{ acc.display_name }}</strong><span>{{ acc.niche || '未设置领域' }} · 样本 {{ acc.sample_count }}</span>
        </button>
      </div>
      <p v-else class="empty-region">还没有「我的账号」。<a href="#" @click.prevent="openCreateMyAccountModal">去添加</a></p>
    </div>

    <!-- ② 明确诊断意图(内向:目标 / 痛点 / 阶段,跟对标分析「想学什么」不同) -->
    <div v-if="selfAppraiseForm.blogger_id" class="block intent-block">
      <h3>② 明确诊断意图 <span class="opt">可留空</span></h3>
      <p class="intent-hint">诊断「自己的号」要先知道你的目标和痛点。填一句更准,或让系统看你在做什么、出几个问题帮你理清。</p>
      <textarea
        v-model="selfAppraiseForm.intent"
        class="intent-input"
        rows="2"
        placeholder="例:想把转化做起来,现在有流量但留不下来 / 想涨粉但不知道发什么"
      ></textarea>

      <div v-if="!selfIntentChecked" class="intent-actions">
        <button type="button" class="ghost" :disabled="selfIntentLoading" @click="fetchSelfIntentSuggestions">
          {{ selfIntentLoading ? '正在看你在做什么…' : '帮我理清意图 →' }}
        </button>
      </div>
      <template v-else>
        <div v-if="!selfIntentClear && selfIntentQuestions.length" class="questions">
          <div v-for="(q, qi) in selfIntentQuestions" :key="qi" class="q">
            <p class="q-text">{{ q.q }}</p>
            <div class="chips">
              <button
                v-for="opt in q.options"
                :key="opt"
                type="button"
                class="chip"
                :class="{ on: (selfIntentSelections[qi] || []).includes(opt) }"
                @click="toggleSelfChip(qi, opt)"
              >{{ opt }}</button>
              <input v-model="selfIntentOthers[qi]" class="chip-other" type="text" placeholder="其他…" />
            </div>
          </div>
        </div>
        <p v-else class="intent-hint ok">✓ 意图已够清晰,直接开始诊断即可。</p>
        <button type="button" class="link-redo" @click="resetSelfIntentGuide">重新理清</button>
      </template>
    </div>

    <button
      type="button"
      class="primary"
      :disabled="!canDiagnose || Boolean(pendingAction)"
      :title="!canDiagnose ? '先在上方填一句目标,或点「帮我理清意图」' : ''"
      @click="handleRunSelfAppraisal"
    >
      {{ pendingAction === 'audit' ? '诊断中…' : '开始诊断' }}
    </button>

    <LiveProgress v-if="pendingAction === 'audit'" />

    <div v-if="report" class="result">
      <AppraisalCard :report="report" />
    </div>

    <div class="gap-placeholder">
      <h3>找差距(我 vs 对标)</h3>
      <p class="empty-region">下一轮上线:选一个对标博主 + 我的账号,量化差距、给整改清单。</p>
    </div>
  </section>
</template>

<style scoped>
.block {
  margin-bottom: var(--space-md, 16px);
}
.result {
  margin-top: var(--space-lg, 24px);
}
.gap-placeholder {
  margin-top: var(--space-xl, 32px);
  border-top: var(--rule-hair);
  padding-top: var(--space-md, 16px);
}

/* —— 明确诊断意图 —— */
.intent-block h3 .opt {
  margin-left: 6px;
  font-size: 12px;
  font-weight: 400;
  color: var(--color-ink-3);
}
.intent-hint {
  margin: 0 0 10px;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--color-ink-3);
}
.intent-hint.ok {
  color: var(--color-accent-ink);
}
.intent-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--color-field-border);
  border-radius: 10px;
  font-size: 13.5px;
  font-family: inherit;
  line-height: 1.6;
  resize: vertical;
  box-sizing: border-box;
}
.intent-actions {
  margin-top: 10px;
}
.intent-actions .ghost {
  height: 36px;
  padding: 0 16px;
  border: 1px solid var(--color-field-border);
  border-radius: 9px;
  background: var(--color-surface);
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink-2);
  cursor: pointer;
}
.intent-actions .ghost:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.questions {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.q-text {
  margin: 0 0 8px;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--color-ink);
}
.chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.chip {
  padding: 7px 13px;
  border: 1px solid var(--color-field-border);
  border-radius: var(--radius-pill);
  background: var(--color-surface);
  font-size: 13px;
  color: var(--color-ink-2);
  cursor: pointer;
  transition: border-color 120ms var(--ease-out), background 120ms var(--ease-out);
}
.chip:hover {
  border-color: var(--color-accent-soft-bd);
}
.chip.on {
  border-color: var(--color-accent);
  background: var(--color-accent-tint);
  color: var(--color-accent-ink);
  font-weight: 600;
}
.chip-other {
  width: 130px;
  padding: 7px 12px;
  border: 1px dashed var(--color-field-border);
  border-radius: var(--radius-pill);
  font-size: 13px;
  font-family: inherit;
}
.link-redo {
  margin-top: 12px;
  border: 0;
  background: none;
  padding: 0;
  font-size: 12.5px;
  color: var(--color-accent);
  cursor: pointer;
}
</style>
