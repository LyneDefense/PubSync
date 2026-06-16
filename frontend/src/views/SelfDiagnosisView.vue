<script setup lang="ts">
// 社媒·诊断我的:只看我的账号(勾选内容),产出优势/短板/增长动作 + 结论。
import StatusChip from '../components/StatusChip.vue'
import {
  accountPosts,
  auditRunReport,
  currentSocialPlatformName,
  currentSocialTab,
  formatDate,
  handleRunSelfDiagnose,
  isSocialPlatform,
  loadAccountPosts,
  myAccounts,
  openCreateMyAccountModal,
  pendingAction,
  selectedSelfRun,
  selectedSelfRunId,
  selfDiagnoseRuns,
  selfForm,
  taskButtonStyle,
  taskProgress
} from '../composables/useWorkspaceStore'

function toggle(arr: number[], id: number) {
  const i = arr.indexOf(id)
  if (i >= 0) arr.splice(i, 1)
  else arr.push(id)
}
function pick(id: number) {
  selfForm.my_blogger_id = id
  selfForm.my_post_ids = []
  loadAccountPosts(id)
}
</script>

<template>
  <section v-if="isSocialPlatform && currentSocialTab === 'self-diagnosis'" class="panel">
    <div class="section-header">
      <div>
        <h2>诊断我的{{ currentSocialPlatformName }}账号</h2>
        <p class="toolbar-subtitle">选一个我的账号、勾选内容,AI 给出优势、明显短板和立即可执行的增长动作。</p>
      </div>
    </div>

    <div class="audit-grid">
      <div class="audit-col">
        <h3>我的账号</h3>
        <div v-if="myAccounts.length" class="blogger-list compact">
          <button v-for="acc in myAccounts" :key="acc.id" type="button" :class="{ active: selfForm.my_blogger_id === acc.id }" @click="pick(acc.id)">
            <strong>{{ acc.display_name }}</strong><span>样本 {{ acc.sample_count }}</span>
          </button>
        </div>
        <p v-else class="empty-region">还没有我的账号。<a href="#" @click.prevent="openCreateMyAccountModal">去添加</a></p>
        <div v-if="selfForm.my_blogger_id" class="check-list">
          <p class="form-hint">勾选要分析的内容({{ selfForm.my_post_ids.length }} 已选);不选则用最近内容。</p>
          <label v-for="post in accountPosts[selfForm.my_blogger_id] || []" :key="post.id" class="check-row">
            <input type="checkbox" :checked="selfForm.my_post_ids.includes(post.id)" @change="toggle(selfForm.my_post_ids, post.id)" />
            <span>{{ post.title || '(无标题)' }}</span>
          </label>
          <p v-if="!(accountPosts[selfForm.my_blogger_id] || []).length" class="empty-region">这个账号还没采集内容,去「我的账号」刷新一下。</p>
        </div>
        <p v-if="!selfForm.my_blogger_id" class="form-hint">请先在上方选择一个「我的账号」(没有就点「去添加」)。</p>
        <button
          type="button"
          class="task-button primary audit-run"
          :class="{ running: pendingAction === 'self-diagnose' }"
          :style="taskButtonStyle('self-diagnose')"
          :disabled="!selfForm.my_blogger_id || Boolean(pendingAction)"
          :title="!selfForm.my_blogger_id ? '请先选择我的账号' : ''"
          @click="handleRunSelfDiagnose"
        >
          <span>{{ pendingAction === 'self-diagnose' ? `诊断中 ${Math.round(taskProgress['self-diagnose'])}%` : '开始诊断' }}</span>
        </button>
      </div>

      <div class="audit-col">
        <h3>历史诊断</h3>
        <div v-if="selfDiagnoseRuns.length" class="audit-run-list">
          <button v-for="run in selfDiagnoseRuns" :key="run.id" type="button" :class="{ active: selectedSelfRunId === run.id }" @click="selectedSelfRunId = run.id">
            <span>{{ formatDate(run.created_at) }}</span>
            <StatusChip :status="run.status" />
            <em v-if="run.score !== null">健康度 {{ run.score }}</em>
          </button>
        </div>
        <p v-else class="empty-region">还没有诊断记录。</p>
      </div>
    </div>

    <div v-if="selectedSelfRun && selectedSelfRun.status === 'succeeded'" class="audit-report">
      <div class="audit-report__head">
        <h3>诊断结论</h3>
        <em v-if="auditRunReport(selectedSelfRun).score !== null">账号健康度 {{ auditRunReport(selectedSelfRun).score }} / 100</em>
      </div>
      <p v-if="auditRunReport(selectedSelfRun).conclusion" class="audit-conclusion">{{ auditRunReport(selectedSelfRun).conclusion }}</p>
      <div class="audit-lists">
        <div v-if="auditRunReport(selectedSelfRun).strengths.length"><h4>已经做对的</h4><ul><li v-for="(item, i) in auditRunReport(selectedSelfRun).strengths" :key="i">{{ item }}</li></ul></div>
        <div v-if="auditRunReport(selectedSelfRun).gaps.length"><h4>明显短板</h4><ul><li v-for="(item, i) in auditRunReport(selectedSelfRun).gaps" :key="i">{{ item }}</li></ul></div>
        <div v-if="auditRunReport(selectedSelfRun).actions.length"><h4>立即可执行的增长动作</h4><ul><li v-for="(item, i) in auditRunReport(selectedSelfRun).actions" :key="i">{{ item }}</li></ul></div>
      </div>
    </div>
    <p v-else-if="selectedSelfRun && selectedSelfRun.status === 'failed'" class="empty-region">
      这次诊断失败了:{{ selectedSelfRun.error_message || '请稍后重试' }}
    </p>
  </section>
</template>

<style scoped>
.audit-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr);
  gap: var(--space-lg, 24px);
  align-items: start;
}
.check-list {
  margin-top: var(--space-sm, 12px);
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 360px;
  overflow-y: auto;
}
.check-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--text-sm);
}
.audit-run {
  margin-top: var(--space-md, 16px);
}
.audit-run-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.audit-run-list button {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: space-between;
  text-align: left;
}
.audit-report {
  margin-top: var(--space-lg, 24px);
  border-top: var(--rule-hair);
  padding-top: var(--space-md, 16px);
}
.audit-report__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}
.audit-conclusion {
  margin: 8px 0 16px;
}
.audit-lists {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--space-md, 16px);
  margin-top: var(--space-md, 16px);
}
@media (max-width: 900px) {
  .audit-grid {
    grid-template-columns: 1fr;
  }
}
</style>
