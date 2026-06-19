<script setup lang="ts">
// 社媒·对标诊断:选我的账号(勾内容) + 对标账号(勾内容),比真实内容,逐维度给结论。
import StatusChip from '../components/StatusChip.vue'
import {
  accountAuditRuns,
  accountPosts,
  auditForm,
  auditRunReport,
  benchmarkAccounts,
  currentSocialPlatformName,
  currentSocialTab,
  formatDate,
  handleRunAccountAudit,
  isSocialPlatform,
  loadAccountPosts,
  myAccounts,
  openCreateBloggerModal,
  openCreateMyAccountModal,
  pendingAction,
  selectedAuditRun,
  selectedAuditRunId
} from '../composables/useWorkspaceStore'

function toggle(arr: number[], id: number) {
  const i = arr.indexOf(id)
  if (i >= 0) arr.splice(i, 1)
  else arr.push(id)
}
function pickMy(id: number) {
  auditForm.my_blogger_id = id
  auditForm.my_post_ids = []
  loadAccountPosts(id)
}
function pickBench(id: number) {
  auditForm.benchmark_blogger_id = id
  auditForm.benchmark_post_ids = []
  loadAccountPosts(id)
}
</script>

<template>
  <section v-if="isSocialPlatform && currentSocialTab === 'audit'" class="panel">
    <div class="section-header">
      <div>
        <h2>{{ currentSocialPlatformName }}对标诊断</h2>
        <p class="toolbar-subtitle">选我的账号和对标账号,各自勾选要对比的内容,AI 逐维度对比、指出差距和动作。</p>
      </div>
    </div>

    <div class="audit-grid">
      <div class="audit-col">
        <h3>我的账号</h3>
        <div v-if="myAccounts.length" class="blogger-list compact">
          <button v-for="acc in myAccounts" :key="acc.id" type="button" :class="{ active: auditForm.my_blogger_id === acc.id }" @click="pickMy(acc.id)">
            <strong>{{ acc.display_name }}</strong><span>样本 {{ acc.sample_count }}</span>
          </button>
        </div>
        <p v-else class="empty-region">还没有我的账号。<a href="#" @click.prevent="openCreateMyAccountModal">去添加</a></p>
        <div v-if="auditForm.my_blogger_id" class="check-list">
          <p class="form-hint">勾选要对比的内容({{ auditForm.my_post_ids.length }} 已选);不选则用最近内容。</p>
          <label v-for="post in accountPosts[auditForm.my_blogger_id] || []" :key="post.id" class="check-row">
            <input type="checkbox" :checked="auditForm.my_post_ids.includes(post.id)" @change="toggle(auditForm.my_post_ids, post.id)" />
            <span>{{ post.title || '(无标题)' }}</span>
          </label>
          <p v-if="!(accountPosts[auditForm.my_blogger_id] || []).length" class="empty-region">这个账号还没采集内容,去「我的账号」刷新一下。</p>
        </div>
      </div>

      <div class="audit-col">
        <h3>对标账号</h3>
        <div v-if="benchmarkAccounts.length" class="blogger-list compact">
          <button v-for="acc in benchmarkAccounts" :key="acc.id" type="button" :class="{ active: auditForm.benchmark_blogger_id === acc.id }" @click="pickBench(acc.id)">
            <strong>{{ acc.display_name }}</strong><span>{{ acc.niche || '未设置领域' }} · 样本 {{ acc.sample_count }}</span>
          </button>
        </div>
        <p v-else class="empty-region">还没有对标账号。<a href="#" @click.prevent="openCreateBloggerModal">去添加</a>(或到「数据采集」创建并采集)。</p>
        <div v-if="auditForm.benchmark_blogger_id" class="check-list">
          <p class="form-hint">勾选要对比的内容({{ auditForm.benchmark_post_ids.length }} 已选);不选则用最近内容。</p>
          <label v-for="post in accountPosts[auditForm.benchmark_blogger_id] || []" :key="post.id" class="check-row">
            <input type="checkbox" :checked="auditForm.benchmark_post_ids.includes(post.id)" @change="toggle(auditForm.benchmark_post_ids, post.id)" />
            <span>{{ post.title || '(无标题)' }}</span>
          </label>
          <p v-if="!(accountPosts[auditForm.benchmark_blogger_id] || []).length" class="empty-region">这个账号还没采集内容,去「数据采集」采一下。</p>
        </div>
      </div>
    </div>

    <p v-if="!auditForm.my_blogger_id || !auditForm.benchmark_blogger_id" class="form-hint">
      请先在上方分别选择「我的账号」和「对标账号」(没有账号可点「去添加」)。
    </p>
    <button
      type="button"
      class="primary audit-run"
      :class="{ running: pendingAction === 'audit' }"
      :disabled="!auditForm.my_blogger_id || !auditForm.benchmark_blogger_id || Boolean(pendingAction)"
      :title="!auditForm.my_blogger_id ? '请先选择我的账号' : (!auditForm.benchmark_blogger_id ? '请先选择对标账号' : '')"
      @click="handleRunAccountAudit"
    >
      <span>{{ pendingAction === 'audit' ? '对标中…' : '开始对标诊断' }}</span>
    </button>

    <div class="audit-results">
      <h3>历史对标</h3>
      <div v-if="accountAuditRuns.length" class="audit-run-list">
        <button v-for="run in accountAuditRuns" :key="run.id" type="button" :class="{ active: selectedAuditRunId === run.id }" @click="selectedAuditRunId = run.id">
          <span>{{ formatDate(run.created_at) }}</span>
          <StatusChip :status="run.status" />
          <em v-if="run.score !== null">接近度 {{ run.score }}</em>
        </button>
      </div>
      <p v-else class="empty-region">还没有对标记录。</p>
    </div>

    <div v-if="selectedAuditRun && selectedAuditRun.status === 'succeeded'" class="audit-report">
      <div class="audit-report__head">
        <h3>对标结论</h3>
        <em v-if="auditRunReport(selectedAuditRun).score !== null">对标接近度 {{ auditRunReport(selectedAuditRun).score }} / 100</em>
      </div>
      <p v-if="auditRunReport(selectedAuditRun).conclusion" class="audit-conclusion">{{ auditRunReport(selectedAuditRun).conclusion }}</p>
      <div v-if="auditRunReport(selectedAuditRun).dimensions.length" class="audit-dimensions">
        <article v-for="dim in auditRunReport(selectedAuditRun).dimensions" :key="dim.name" class="audit-dim">
          <h4>{{ dim.name }}</h4>
          <p><b>对标账号:</b>{{ dim.benchmark }}</p>
          <p><b>我现在:</b>{{ dim.mine }}</p>
          <p class="audit-dim__gap"><b>差距与改法:</b>{{ dim.gap }}</p>
        </article>
      </div>
      <div class="audit-lists">
        <div v-if="auditRunReport(selectedAuditRun).strengths.length"><h4>我已经做对的</h4><ul><li v-for="(item, i) in auditRunReport(selectedAuditRun).strengths" :key="i">{{ item }}</li></ul></div>
        <div v-if="auditRunReport(selectedAuditRun).gaps.length"><h4>明显短板</h4><ul><li v-for="(item, i) in auditRunReport(selectedAuditRun).gaps" :key="i">{{ item }}</li></ul></div>
        <div v-if="auditRunReport(selectedAuditRun).actions.length"><h4>立即可执行的动作</h4><ul><li v-for="(item, i) in auditRunReport(selectedAuditRun).actions" :key="i">{{ item }}</li></ul></div>
      </div>
    </div>
    <p v-else-if="selectedAuditRun && selectedAuditRun.status === 'failed'" class="empty-region">
      这次对标失败了:{{ selectedAuditRun.error_message || '请稍后重试' }}
    </p>
  </section>
</template>

<style scoped>
.audit-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
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
.audit-results {
  margin-top: var(--space-lg, 24px);
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
.audit-dimensions {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: var(--space-sm, 12px);
}
.audit-dim {
  border: var(--rule-hair);
  border-radius: var(--radius-md, 8px);
  padding: var(--space-sm, 12px);
}
.audit-dim h4 {
  margin: 0 0 6px;
}
.audit-dim p {
  margin: 4px 0;
  font-size: var(--text-sm);
}
.audit-dim__gap {
  color: var(--color-accent, inherit);
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
