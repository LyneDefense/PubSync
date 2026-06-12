<script setup lang="ts">
// 社媒·博主蒸馏：基于采集批次提炼创作方法论 Skill。
// 状态与方法来自 useWorkspaceStore 单例；本组件仅负责该面板的视图与交互。
import { sanitizeHtml } from '../utils/sanitize'
import {
  article,
  bloggerCollectionRuns,
  bloggers,
  collectionDistillationCount,
  currentSocialPlatformName,
  currentSocialTab,
  form,
  formatDate,
  goNextXhsDistillStep,
  goPreviousXhsDistillStep,
  handleAbandonBloggerRun,
  handleConfirmBloggerRun,
  handleDistillBlogger,
  isSocialPlatform,
  pendingAction,
  selectBlogger,
  selectCollectionRun,
  selectedBlogger,
  selectedBloggerId,
  selectedBloggerRun,
  selectedBloggerSkill,
  selectedCollectionRunId,
  taskButtonStyle,
  taskProgress,
  xhsDistillStep,
  xhsDistillStepTitle
} from '../composables/useWorkspaceStore'
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
          <button v-if="xhsDistillStep > 1" type="button" class="creator-arrow previous" aria-label="上一步" @click="goPreviousXhsDistillStep">←</button>
          <div class="creator-main">
            <div class="creator-step-header">
              <h3>{{ xhsDistillStepTitle }}</h3>
              <span>步骤 {{ xhsDistillStep }} / 4</span>
              <div class="creator-progress" aria-hidden="true"><i :style="{ width: `${(xhsDistillStep / 4) * 100}%` }"></i></div>
            </div>
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
                  <span>{{ run.status }} · 样本 {{ run.post_count }} · 已蒸馏 {{ collectionDistillationCount(run.id) }} 次</span>
                </button>
              </div>
              <p v-else class="empty-region">请先选择博主。</p>
            </section>
            <section v-if="xhsDistillStep === 3" class="creation-stage-card active">
              <div class="inline-card-header">
                <div><span>03 执行蒸馏</span><h3>基于采集批次生成 Skill</h3></div>
                <button type="button" class="task-button primary" :class="{ running: pendingAction === 'distill' }" :style="taskButtonStyle('distill')" :disabled="!selectedBloggerId || !selectedCollectionRunId || Boolean(pendingAction)" @click="handleDistillBlogger">
                  <span>{{ pendingAction === 'distill' ? `蒸馏中 ${Math.round(taskProgress.distill)}%` : '开始蒸馏' }}</span>
                </button>
              </div>
              <div v-if="pendingAction === 'distill'" class="inline-progress-card" aria-live="polite">
                <div><strong>正在蒸馏风格</strong><span>大模型正在提炼选题、结构、标题、表达和禁区。</span></div><i aria-hidden="true"></i>
              </div>
              <p class="form-hint">蒸馏完成后会进入结果确认页，保存后 Skill 才会生效。</p>
            </section>
            <section v-if="xhsDistillStep === 4" class="creation-stage-card active">
              <div class="inline-card-header">
                <div><span>04 确认结果</span><h3>预览报告和 Skill</h3></div>
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
          </div>
          <button v-if="xhsDistillStep < 4" type="button" class="creator-arrow next" aria-label="下一步" @click="goNextXhsDistillStep">→</button>
        </div>
      </section>
</template>
