<script setup lang="ts">
// 社媒·博主蒸馏：基于采集批次提炼创作方法论 Skill。
// 状态与方法来自 useWorkspaceStore 单例；本组件仅负责该面板的视图与交互。
import { computed } from 'vue'
import { sanitizeHtml } from '../utils/sanitize'
import StatusChip from '../components/StatusChip.vue'
import {
  article,
  bloggerCollectionRuns,
  bloggers,
  collectionDistillationCount,
  collectionSubtypeCounts,
  currentSocialPlatformName,
  currentSocialTab,
  distillRunMeta,
  DISTILL_MIN_SAMPLES,
  DISTILL_SUBTYPES,
  distillSelectedSubtypes,
  form,
  formatDate,
  goNextXhsDistillStep,
  goPreviousXhsDistillStep,
  handleAbandonBloggerRun,
  handleConfirmBloggerRun,
  handleDistillBlogger,
  isSocialPlatform,
  pendingAction,
  qualityTone,
  selectBlogger,
  selectCollectionRun,
  selectedBlogger,
  selectedBloggerId,
  selectedBloggerRun,
  selectedBloggerSkill,
  selectedCollectionRunId,
  subtypeLabel,
  taskButtonStyle,
  taskProgress,
  xhsDistillStep,
  xhsDistillStepLabels
} from '../composables/useWorkspaceStore'

// 当前待确认/已选蒸馏结果的模式与质量分（解析自 report_json）。
const runMeta = computed(() => distillRunMeta(selectedBloggerRun.value))

function subtypeDisabled(subtype: string) {
  return (collectionSubtypeCounts.value[subtype] || 0) < DISTILL_MIN_SAMPLES
}
function toggleSubtype(subtype: string) {
  const index = distillSelectedSubtypes.value.indexOf(subtype)
  if (index >= 0) distillSelectedSubtypes.value.splice(index, 1)
  else distillSelectedSubtypes.value.push(subtype)
}
</script>

<template>
      <section v-if="isSocialPlatform && currentSocialTab === 'distill'" class="panel">
        <div class="section-header">
          <div>
            <h2>{{ currentSocialPlatformName }}博主蒸馏</h2>
            <p class="toolbar-subtitle">选择博主和采集批次，生成报告与 Skill；保存后才进入 AI 创作可选列表。</p>
          </div>
        </div>
        <div class="creator-shell">
          <div class="creator-main">
            <ol class="creator-steps" aria-label="步骤进度">
              <li
                v-for="(label, index) in xhsDistillStepLabels"
                :key="label"
                class="creator-steps__item"
                :class="{ current: xhsDistillStep === index + 1, done: xhsDistillStep > index + 1 }"
              >
                <span class="creator-steps__dot">{{ index + 1 }}</span>
                <span class="creator-steps__label">{{ label }}</span>
              </li>
            </ol>
            <section v-if="xhsDistillStep === 1" class="creation-stage-card active">
              <div class="inline-card-header"><div><span>01 选择博主</span><h3>选择要蒸馏的博主</h3></div></div>
              <div v-if="bloggers.length" class="blogger-list compact">
                <button v-for="blogger in bloggers" :key="blogger.id" type="button" :class="{ active: selectedBloggerId === blogger.id }" @click="selectBlogger(blogger.id)">
                  <strong>{{ blogger.display_name }}</strong><span>{{ blogger.niche || '未设置领域' }} · 采集批次 {{ bloggerCollectionRuns.length }}</span>
                </button>
              </div>
              <p v-else class="empty-region">还没有博主档案。请先到“数据采集”创建博主。</p>
            </section>
            <section v-if="xhsDistillStep === 2" class="creation-stage-card active">
              <div class="inline-card-header"><div><span>02 选择批次</span><h3>选择一次已完成采集</h3></div></div>
              <div v-if="selectedBlogger" class="run-list collection-list">
                <div class="run-list-header"><strong>可蒸馏批次</strong><span>{{ bloggerCollectionRuns.length }} 次</span></div>
                <button v-for="run in bloggerCollectionRuns" :key="run.id" type="button" :disabled="run.status !== 'succeeded'" :class="{ active: selectedCollectionRunId === run.id }" @click="selectCollectionRun(run.id)">
                  <strong>#{{ run.id }} · {{ formatDate(run.created_at) }}</strong>
                  <span><StatusChip :status="run.status" /> 样本 {{ run.post_count }} · 已蒸馏 {{ collectionDistillationCount(run.id) }} 次</span>
                </button>
              </div>
              <p v-else class="empty-region">请先选择博主。</p>
            </section>
            <section v-if="xhsDistillStep === 3" class="creation-stage-card active">
              <div class="inline-card-header">
                <div><span>03 执行蒸馏</span><h3>基于采集批次生成 Skill</h3></div>
                <button type="button" class="task-button primary" :class="{ running: pendingAction === 'distill' }" :style="taskButtonStyle('distill')" :disabled="!selectedBloggerId || !selectedCollectionRunId || Boolean(pendingAction)" :title="!selectedBloggerId ? '请先在第 1 步选择博主' : (!selectedCollectionRunId ? '请先在第 2 步选择采集批次' : '')" @click="handleDistillBlogger">
                  <span>{{ pendingAction === 'distill' ? `蒸馏中 ${Math.round(taskProgress.distill)}%` : '开始蒸馏' }}</span>
                </button>
              </div>
              <p v-if="!selectedBloggerId || !selectedCollectionRunId" class="form-hint">
                {{ !selectedBloggerId ? '还没选择博主——请回到第 1 步选择。' : '还没选择采集批次——请回到第 2 步选择一次已完成的采集。' }}
              </p>
              <div v-if="selectedCollectionRunId" class="subtype-picker">
                <p class="form-hint">蒸馏内容模态（不勾选 = 全选 = 通用 Skill；少于 {{ DISTILL_MIN_SAMPLES }} 条的模态不可单独蒸馏）：</p>
                <div class="subtype-options">
                  <label v-for="st in DISTILL_SUBTYPES" :key="st" class="subtype-option" :class="{ disabled: subtypeDisabled(st) }">
                    <input type="checkbox" :checked="distillSelectedSubtypes.includes(st)" :disabled="subtypeDisabled(st)" @change="toggleSubtype(st)" />
                    {{ subtypeLabel(st) }}（{{ collectionSubtypeCounts[st] || 0 }}）
                  </label>
                </div>
                <p class="form-hint">将蒸馏：<strong>{{ distillSelectedSubtypes.length ? distillSelectedSubtypes.map(subtypeLabel).join(' + ') : '通用（全部模态）' }}</strong></p>
              </div>
              <p class="form-hint">把对标博主的公开内容提炼成可迁移的创作方法论 Skill。蒸馏完成后进入结果确认页并给出质量自检评分；保存后 Skill 才会生效。</p>
            </section>
            <section v-if="xhsDistillStep === 4" class="creation-stage-card active">
              <div class="inline-card-header">
                <div>
                  <span>04 确认结果</span><h3>预览报告和 Skill</h3>
                  <p v-if="selectedBloggerRun" class="distill-result-meta">
                    <span class="status-chip status-chip--neutral">{{ runMeta.mode === 'B' ? '诊断我的账号' : '拆解对标博主' }}</span>
                    <span v-if="runMeta.qualityScore !== null" class="status-chip" :class="`status-chip--${qualityTone(runMeta.qualityGrade)}`">质量自检 {{ runMeta.qualityScore }} 分 · {{ runMeta.qualityGrade }}</span>
                    <span v-if="runMeta.revisions > 0" class="status-chip status-chip--info">已自我修订 {{ runMeta.revisions }} 次</span>
                  </p>
                </div>
                <div class="actions">
                  <button type="button" class="primary" :disabled="Boolean(pendingAction) || selectedBloggerRun?.status !== 'pending_confirmation'" @click="handleConfirmBloggerRun">{{ pendingAction === 'distill-confirm' ? '保存中' : '保存结果' }}</button>
                  <button type="button" :disabled="Boolean(pendingAction) || selectedBloggerRun?.status !== 'pending_confirmation'" @click="handleAbandonBloggerRun">{{ pendingAction === 'distill-abandon' ? '放弃中' : '放弃本次蒸馏' }}</button>
                </div>
              </div>
              <div v-if="selectedBloggerRun" class="distill-grid compact-result">
                <article class="distill-card"><h3>蒸馏报告</h3><div v-if="selectedBloggerRun.report_html" class="distill-report" v-html="sanitizeHtml(selectedBloggerRun.report_html)"></div><p v-else class="empty-region">暂无报告。</p></article>
                <article class="distill-card"><h3>Skill 输出</h3><textarea v-if="selectedBloggerSkill" :value="selectedBloggerSkill.skill_markdown" readonly rows="18"></textarea><p v-else class="empty-region">暂无 Skill。</p></article>
              </div>
              <p v-else class="empty-region">完成一次蒸馏后，这里会显示待确认结果。</p>
            </section>
            <div class="creator-nav">
              <button v-if="xhsDistillStep > 1" type="button" @click="goPreviousXhsDistillStep">← 上一步</button>
              <button v-if="xhsDistillStep < 4" type="button" class="creator-nav__next primary" @click="goNextXhsDistillStep">下一步 →</button>
            </div>
          </div>
        </div>
      </section>
</template>
