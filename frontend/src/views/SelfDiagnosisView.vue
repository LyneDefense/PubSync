<script setup lang="ts">
// 诊断我的账号(评估与提升):给自己的号做体检(硬实力 × 合规,无软实力)。诊断前自动确保 ≥20 篇笔记。
// 找差距(我 vs 对标)同属本模块,下一轮上线。
import { computed } from 'vue'
import AppraisalCard from '../components/AppraisalCard.vue'
import LiveProgress from '../components/LiveProgress.vue'
import {
  currentSocialPlatformName,
  currentSocialTab,
  handleRunSelfAppraisal,
  isSocialPlatform,
  myAccounts,
  openCreateMyAccountModal,
  parseAppraisalReport,
  pendingAction,
  selfAppraiseForm,
  selfAppraisalRun
} from '../composables/useWorkspaceStore'

const report = computed(() => parseAppraisalReport(selfAppraisalRun.value))
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
      <h3>选择我的账号</h3>
      <div v-if="myAccounts.length" class="blogger-list compact">
        <button
          v-for="acc in myAccounts"
          :key="acc.id"
          type="button"
          :class="{ active: selfAppraiseForm.blogger_id === acc.id }"
          @click="selfAppraiseForm.blogger_id = acc.id"
        >
          <strong>{{ acc.display_name }}</strong><span>{{ acc.niche || '未设置领域' }} · 样本 {{ acc.sample_count }}</span>
        </button>
      </div>
      <p v-else class="empty-region">还没有「我的账号」。<a href="#" @click.prevent="openCreateMyAccountModal">去添加</a></p>
    </div>

    <button
      type="button"
      class="primary"
      :disabled="!selfAppraiseForm.blogger_id || Boolean(pendingAction)"
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
</style>
