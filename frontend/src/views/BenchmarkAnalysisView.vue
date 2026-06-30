<script setup lang="ts">
// 对标分析(诊断别人):诊断一个对标库博主值不值得对标(硬实力 × 软实力 × 合规)。
// 选博主后(可选填意图)→ 系统看 TA 在做什么、给几道多选题帮你把「想学什么」问清楚 → 诊断。
// 意图已经够清晰则跳过问题、直接诊断。
import { computed } from 'vue'
import AppraisalCard from '../components/AppraisalCard.vue'
import {
  appraiseForm,
  appraisalRun,
  benchmarkAccounts,
  currentSocialPlatformName,
  currentSocialTab,
  fetchIntentSuggestions,
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
  resetIntentGuide
} from '../composables/useWorkspaceStore'

const report = computed(() => parseAppraisalReport(appraisalRun.value))

function pick(id: number) {
  appraiseForm.blogger_id = id
  resetIntentGuide() // 换了博主就重新引导意图
}
function toggleOption(qi: number, opt: string) {
  const arr = intentSelections[qi] || (intentSelections[qi] = [])
  const idx = arr.indexOf(opt)
  if (idx >= 0) arr.splice(idx, 1)
  else arr.push(opt)
}
function isPicked(qi: number, opt: string): boolean {
  return (intentSelections[qi] || []).includes(opt)
}
</script>

<template>
  <section v-if="isSocialPlatform && currentSocialTab === 'analysis'" class="panel">
    <div class="section-header">
      <div>
        <h2>{{ currentSocialPlatformName }}对标分析</h2>
        <p class="toolbar-subtitle">诊断一个号到底值不值得对标(硬实力 × 软实力 × 合规)。诊断前会自动确保 ≥20 篇笔记。</p>
      </div>
    </div>

    <div class="block">
      <h3>选择对标博主</h3>
      <div v-if="benchmarkAccounts.length" class="blogger-list compact">
        <button
          v-for="acc in benchmarkAccounts"
          :key="acc.id"
          type="button"
          :class="{ active: appraiseForm.blogger_id === acc.id }"
          @click="pick(acc.id)"
        >
          <strong>{{ acc.display_name }}</strong><span>{{ acc.niche || '未设置领域' }} · 样本 {{ acc.sample_count }}</span>
        </button>
      </div>
      <p v-else class="empty-region">对标库还没有博主,先去「找对标博主」加一个。</p>
    </div>

    <label class="intent-row">
      你想学什么 / 对标意图(可不填,下一步会帮你理清)
      <input v-model="appraiseForm.intent" type="text" placeholder="例:想学把香港保险讲得专业、又有人看、能涨粉" />
    </label>
    <label class="intent-row">
      品类(可选,触发合规红线)
      <input v-model="appraiseForm.industry" type="text" placeholder="保险 / 金融 / 医疗 / 美妆…" />
    </label>

    <!-- 第一步:看 TA 在做什么,把意图问清楚 -->
    <button
      v-if="!intentChecked"
      type="button"
      class="primary"
      :disabled="!appraiseForm.blogger_id || intentLoading"
      @click="fetchIntentSuggestions"
    >
      {{ intentLoading ? '正在看 TA 在做什么…' : '下一步:明确意图' }}
    </button>

    <!-- 第二步:引导问题(意图够清晰则跳过) -->
    <template v-else>
      <p v-if="intentClear && !intentQuestions.length" class="intent-clear">✓ 你的意图已经清楚,可以直接诊断。</p>
      <div v-for="(q, qi) in intentQuestions" :key="qi" class="intent-q">
        <p class="intent-q-title">{{ q.q }}</p>
        <div class="intent-chips">
          <button
            v-for="opt in q.options"
            :key="opt"
            type="button"
            class="intent-chip"
            :class="{ on: isPicked(qi, opt) }"
            @click="toggleOption(qi, opt)"
          >{{ opt }}</button>
        </div>
        <input v-model="intentOthers[qi]" class="intent-other" type="text" placeholder="其他(可补充)…" />
      </div>

      <div class="action-row">
        <button type="button" class="ghost" :disabled="Boolean(pendingAction)" @click="resetIntentGuide">重选意图</button>
        <button
          type="button"
          class="primary"
          :disabled="!appraiseForm.blogger_id || Boolean(pendingAction)"
          @click="handleRunAppraisal"
        >
          {{ pendingAction === 'audit' ? '诊断中…' : '开始诊断' }}
        </button>
      </div>
    </template>

    <div v-if="report" class="result">
      <AppraisalCard :report="report" />
    </div>
  </section>
</template>

<style scoped>
.block {
  margin-bottom: var(--space-md, 16px);
}
.intent-row {
  display: block;
  margin-top: var(--space-md, 16px);
}
.intent-row input {
  width: 100%;
  margin-top: 4px;
}
.intent-clear {
  margin-top: var(--space-md, 16px);
  color: var(--color-ok, #1f7a45);
  font-size: var(--text-sm, 14px);
}
.intent-q {
  margin-top: var(--space-md, 16px);
}
.intent-q-title {
  margin: 0 0 8px;
  font-size: var(--text-sm, 14px);
  font-weight: 600;
}
.intent-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.intent-chip {
  border: 1px solid var(--color-border, #d0d3d9);
  background: var(--color-surface, #fff);
  border-radius: 999px;
  padding: 5px 14px;
  font-size: var(--text-sm, 13px);
  cursor: pointer;
}
.intent-chip.on {
  border-color: var(--color-accent, #0d7361);
  background: var(--color-accent-soft, #e6f4f1);
  color: var(--color-accent, #0d7361);
}
.intent-other {
  width: 100%;
  margin-top: 8px;
}
.action-row {
  display: flex;
  gap: 12px;
  margin-top: var(--space-lg, 20px);
}
.result {
  margin-top: var(--space-lg, 24px);
}
</style>
