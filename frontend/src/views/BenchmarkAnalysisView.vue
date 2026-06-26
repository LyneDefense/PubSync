<script setup lang="ts">
// 对标分析:博主诊断(诊断一个号值不值得对标——硬实力×软实力×合规)+ 找差距(下一轮)。
import { computed } from 'vue'
import AppraisalCard from '../components/AppraisalCard.vue'
import {
  appraiseForm,
  appraisalRun,
  benchmarkAccounts,
  currentSocialPlatformName,
  currentSocialTab,
  handleRunAppraisal,
  isSocialPlatform,
  myAccounts,
  parseAppraisalReport,
  pendingAction
} from '../composables/useWorkspaceStore'

const report = computed(() => parseAppraisalReport(appraisalRun.value))

function pick(id: number, kind: 'benchmark' | 'self') {
  appraiseForm.blogger_id = id
  appraiseForm.kind = kind
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

    <div class="pick-grid">
      <div>
        <h3>诊断对标博主</h3>
        <div v-if="benchmarkAccounts.length" class="blogger-list compact">
          <button
            v-for="acc in benchmarkAccounts"
            :key="acc.id"
            type="button"
            :class="{ active: appraiseForm.kind === 'benchmark' && appraiseForm.blogger_id === acc.id }"
            @click="pick(acc.id, 'benchmark')"
          >
            <strong>{{ acc.display_name }}</strong><span>{{ acc.niche || '未设置领域' }} · 样本 {{ acc.sample_count }}</span>
          </button>
        </div>
        <p v-else class="empty-region">对标库还没有博主,先去「找对标博主」加一个。</p>
      </div>
      <div>
        <h3>或诊断我的账号</h3>
        <div v-if="myAccounts.length" class="blogger-list compact">
          <button
            v-for="acc in myAccounts"
            :key="acc.id"
            type="button"
            :class="{ active: appraiseForm.kind === 'self' && appraiseForm.blogger_id === acc.id }"
            @click="pick(acc.id, 'self')"
          >
            <strong>{{ acc.display_name }}</strong><span>样本 {{ acc.sample_count }}</span>
          </button>
        </div>
        <p v-else class="empty-region">还没有我的账号。</p>
      </div>
    </div>

    <label v-if="appraiseForm.kind === 'benchmark'" class="intent-row">
      你想对标什么样的博主 / 想学什么(对标意图)
      <input v-model="appraiseForm.intent" type="text" placeholder="例:想学把香港保险讲得专业、又有人看、能涨粉" />
    </label>
    <label class="intent-row">
      品类(可选,触发合规红线)
      <input v-model="appraiseForm.industry" type="text" placeholder="保险 / 金融 / 医疗 / 美妆…" />
    </label>

    <button
      type="button"
      class="primary"
      :disabled="!appraiseForm.blogger_id || Boolean(pendingAction)"
      @click="handleRunAppraisal"
    >
      {{ pendingAction === 'audit' ? '诊断中…' : '开始诊断' }}
    </button>

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
.pick-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-lg, 24px);
  align-items: start;
}
.intent-row {
  display: block;
  margin-top: var(--space-md, 16px);
}
.intent-row input {
  width: 100%;
  margin-top: 4px;
}
.result {
  margin-top: var(--space-lg, 24px);
}
.gap-placeholder {
  margin-top: var(--space-xl, 32px);
  border-top: var(--rule-hair);
  padding-top: var(--space-md, 16px);
}
@media (max-width: 900px) {
  .pick-grid {
    grid-template-columns: 1fr;
  }
}
</style>
