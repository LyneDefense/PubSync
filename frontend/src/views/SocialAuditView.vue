<script setup lang="ts">
// 社媒·账号对标体检:粘贴自己账号的内容,选一个对标博主的 Skill,AI 逐维度对比给结论。
// 状态与方法来自 useWorkspaceStore 单例;本组件仅负责视图与交互。
import { watchEffect } from 'vue'
import InlineTaskProgress from '../components/InlineTaskProgress.vue'
import StatusChip from '../components/StatusChip.vue'
import {
  accountAuditRuns,
  activeXhsSkills,
  auditForm,
  auditRunReport,
  currentSocialPlatformName,
  currentSocialTab,
  formatDate,
  handleRunAccountAudit,
  isSocialPlatform,
  pendingAction,
  selectedAuditRun,
  selectedAuditRunId,
  taskButtonStyle,
  taskProgress
} from '../composables/useWorkspaceStore'

// 进入页面时,若还没选对标 Skill,默认选中第一个可用的。
watchEffect(() => {
  if (!auditForm.benchmark_skill_id && activeXhsSkills.value.length) {
    auditForm.benchmark_skill_id = activeXhsSkills.value[0].id
  }
})
</script>

<template>
  <section v-if="isSocialPlatform && currentSocialTab === 'audit'" class="panel">
    <div class="section-header">
      <div>
        <h2>{{ currentSocialPlatformName }}账号对标体检</h2>
        <p class="toolbar-subtitle">粘贴你自己账号的内容,选一个对标博主,AI 逐维度对比、指出差距并给出可执行动作。</p>
      </div>
    </div>

    <div class="audit-grid">
      <div class="audit-form">
        <label class="audit-field">
          <span>对标博主(选一个已蒸馏的 Skill)</span>
        </label>
        <div v-if="activeXhsSkills.length" class="topic-idea-grid">
          <button
            v-for="skill in activeXhsSkills"
            :key="skill.id"
            type="button"
            :class="{ active: auditForm.benchmark_skill_id === skill.id }"
            :disabled="Boolean(pendingAction)"
            @click="auditForm.benchmark_skill_id = skill.id"
          >
            <strong>{{ skill.name }}</strong>
            <span>{{ skill.description }}</span>
            <small>{{ formatDate(skill.created_at) }}</small>
          </button>
        </div>
        <p v-else class="empty-region">还没有可对标的 Skill。请先到“博主蒸馏”完成一次风格蒸馏。</p>

        <label class="audit-field">
          <span>粘贴你自己账号的内容(可放多篇,标题+正文都行)</span>
          <textarea
            v-model="auditForm.my_content_text"
            rows="10"
            :disabled="Boolean(pendingAction)"
            placeholder="把你最近发布的几篇笔记/脚本的标题和正文粘进来,越真实越准。"
          ></textarea>
        </label>

        <button
          type="button"
          class="task-button primary"
          :class="{ running: pendingAction === 'audit' }"
          :style="taskButtonStyle('audit')"
          :disabled="!auditForm.benchmark_skill_id || !auditForm.my_content_text.trim() || Boolean(pendingAction)"
          @click="handleRunAccountAudit"
        >
          <span>{{ pendingAction === 'audit' ? `体检中 ${Math.round(taskProgress.audit)}%` : '开始体检对标' }}</span>
        </button>
        <InlineTaskProgress :active="pendingAction === 'audit'" title="正在体检对标" fallback="正在对照对标博主分析你的内容…" />
      </div>

      <div class="audit-results">
        <h3>历史体检</h3>
        <div v-if="accountAuditRuns.length" class="audit-run-list">
          <button
            v-for="run in accountAuditRuns"
            :key="run.id"
            type="button"
            :class="{ active: selectedAuditRunId === run.id }"
            @click="selectedAuditRunId = run.id"
          >
            <span>{{ formatDate(run.created_at) }}</span>
            <StatusChip :status="run.status" />
            <em v-if="run.score !== null">接近度 {{ run.score }}</em>
          </button>
        </div>
        <p v-else class="empty-region">还没有体检记录。填好左边、点“开始体检对标”。</p>
      </div>
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
          <p><b>对标博主:</b>{{ dim.benchmark }}</p>
          <p><b>你现在:</b>{{ dim.mine }}</p>
          <p class="audit-dim__gap"><b>差距与改法:</b>{{ dim.gap }}</p>
        </article>
      </div>

      <div class="audit-lists">
        <div v-if="auditRunReport(selectedAuditRun).strengths.length">
          <h4>你已经做对的</h4>
          <ul><li v-for="(item, i) in auditRunReport(selectedAuditRun).strengths" :key="i">{{ item }}</li></ul>
        </div>
        <div v-if="auditRunReport(selectedAuditRun).gaps.length">
          <h4>明显短板</h4>
          <ul><li v-for="(item, i) in auditRunReport(selectedAuditRun).gaps" :key="i">{{ item }}</li></ul>
        </div>
        <div v-if="auditRunReport(selectedAuditRun).actions.length">
          <h4>立即可执行的动作</h4>
          <ul><li v-for="(item, i) in auditRunReport(selectedAuditRun).actions" :key="i">{{ item }}</li></ul>
        </div>
      </div>
    </div>
    <p v-else-if="selectedAuditRun && selectedAuditRun.status === 'failed'" class="empty-region">
      这次体检失败了:{{ selectedAuditRun.error_message || '请稍后重试' }}
    </p>
  </section>
</template>

<style scoped>
.audit-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
  gap: var(--space-lg, 24px);
  align-items: start;
}

.audit-field {
  display: block;
  margin-top: var(--space-md, 16px);
}

.audit-field > span {
  display: block;
  margin-bottom: 6px;
  font-size: var(--text-sm);
  color: var(--color-ink-2, inherit);
}

.audit-field textarea {
  width: 100%;
  resize: vertical;
}

.task-button {
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
