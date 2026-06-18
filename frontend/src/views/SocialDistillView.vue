<script setup lang="ts">
// 社媒·蒸馏(阶段B)：选博主 → 自动蒸馏(高赞 top-N) 或 选快照蒸馏 → 报告/Skill + 蒸馏历史。
import { computed } from 'vue'
import { sanitizeHtml } from '../utils/sanitize'
import StatusChip from '../components/StatusChip.vue'
import {
  benchmarkAccounts,
  bloggerRuns,
  bloggerSnapshots,
  currentSocialPlatformName,
  currentSocialTab,
  distillRunMeta,
  distillRunOrdinal,
  DISTILL_MIN_SAMPLES,
  DISTILL_RECOMMEND_SAMPLES,
  friendlyTime,
  handleAbandonBloggerRun,
  handleAutoDistill,
  handleConfirmBloggerRun,
  handleDistillFromSnapshot,
  isSocialPlatform,
  pendingAction,
  qualityTone,
  selectBlogger,
  selectBloggerRun,
  selectedBlogger,
  selectedBloggerId,
  selectedBloggerRun,
  selectedBloggerRunCount,
  selectedBloggerRunId,
  selectedBloggerSkill,
  subtypeLabel,
  taskProgress
} from '../composables/useWorkspaceStore'

const distilling = computed(() => pendingAction.value === 'distill')
const runMeta = computed(() => distillRunMeta(selectedBloggerRun.value))
const selectedSkillScope = computed(() => {
  try {
    const scope = JSON.parse(selectedBloggerSkill.value?.scope_json || '["__all__"]')
    const items = (Array.isArray(scope) ? scope : []).filter((s: string) => s && s !== '__all__')
    return items.length ? items.map((s: string) => subtypeLabel(s)).join(' + ') : '通用（全部模态）'
  } catch {
    return '通用（全部模态）'
  }
})
</script>

<template>
  <section v-if="isSocialPlatform && currentSocialTab === 'distill'" class="panel">
    <div class="section-header">
      <div>
        <h2>{{ currentSocialPlatformName }}博主蒸馏</h2>
        <p class="toolbar-subtitle">把对标博主的公开内容提炼成可迁移的创作方法论 Skill。先选博主，再一键自动蒸馏或选一个快照蒸馏。</p>
      </div>
    </div>

    <div class="xhs-assets-browser">
      <aside class="asset-sidebar" aria-label="博主列表">
        <div class="run-list-header"><strong>博主</strong><span>{{ benchmarkAccounts.length }} 个</span></div>
        <button
          v-for="blogger in benchmarkAccounts"
          :key="blogger.id"
          type="button"
          :class="{ active: selectedBloggerId === blogger.id }"
          @click="selectBlogger(blogger.id)"
        >
          <strong>{{ blogger.display_name }}</strong>
          <span>{{ blogger.niche || '未设置领域' }} · 样本 {{ blogger.sample_count }}</span>
        </button>
        <p v-if="!benchmarkAccounts.length" class="empty-region">还没有博主。请先到「博主资产」创建并采集。</p>
      </aside>

      <div v-if="selectedBlogger" class="asset-detail">
        <!-- 自动蒸馏 -->
        <section class="asset-panel">
          <div class="run-list-header"><strong>自动蒸馏</strong><span>高赞优先</span></div>
          <div class="distill-row">
            <button type="button" class="primary" :disabled="distilling" @click="handleAutoDistill">
              {{ distilling ? `蒸馏中 ${Math.round(taskProgress.distill)}%` : '一键自动蒸馏' }}
            </button>
            <span class="form-hint">系统自动取该博主笔记池里赞藏最高的若干篇，按模态分车道，产出通用 Skill（不依赖快照）。</span>
          </div>
        </section>

        <!-- 选快照蒸馏 -->
        <section class="asset-panel">
          <div class="run-list-header"><strong>用快照蒸馏</strong><span>{{ bloggerSnapshots.length }} 个</span></div>
          <p class="form-hint">快照在「博主资产」勾选笔记后保存（需 ≥{{ DISTILL_MIN_SAMPLES }} 篇，建议 ≥{{ DISTILL_RECOMMEND_SAMPLES }} 篇）。</p>
          <div v-if="bloggerSnapshots.length" class="snapshot-list">
            <div v-for="snap in bloggerSnapshots" :key="snap.id" class="snapshot-row">
              <div class="snapshot-info">
                <strong>{{ snap.name }}</strong>
                <span>{{ snap.post_count }} 篇 · {{ friendlyTime(snap.created_at) }}</span>
              </div>
              <button type="button" class="primary" :disabled="distilling" @click="handleDistillFromSnapshot(snap.id)">用此快照蒸馏</button>
            </div>
          </div>
          <p v-else class="empty-region">还没有快照。去「博主资产」勾选笔记存一个。</p>
        </section>

        <!-- 蒸馏历史 -->
        <section class="asset-panel">
          <div class="run-list-header"><strong>蒸馏历史</strong><span>{{ selectedBloggerRunCount }} 次</span></div>
          <div class="asset-run-list">
            <button
              v-for="run in bloggerRuns"
              :key="run.id"
              type="button"
              :class="{ active: selectedBloggerRunId === run.id, failed: run.status === 'failed' }"
              @click="selectBloggerRun(run.id)"
            >
              <span class="asset-run-row"><strong>第 {{ distillRunOrdinal(run.id) }} 次蒸馏</strong><StatusChip :status="run.status" /></span>
              <span class="asset-run-meta">{{ friendlyTime(run.created_at) }} · 样本 {{ run.sample_count }}</span>
              <em v-if="run.status === 'failed'" class="run-error">失败原因：{{ run.error_message || '未记录失败原因' }}</em>
            </button>
            <p v-if="!bloggerRuns.length" class="empty-region">这个博主还没有蒸馏记录。</p>
          </div>
        </section>

        <!-- 选中蒸馏的报告 / Skill -->
        <section v-if="selectedBloggerRun" class="asset-panel">
          <div class="stage-header">
            <div>
              <span><StatusChip :status="selectedBloggerRun.status" /></span>
              <h3>第 {{ distillRunOrdinal(selectedBloggerRun.id) }} 次蒸馏</h3>
              <p class="distill-result-meta">
                <span class="status-chip status-chip--neutral">{{ runMeta.mode === 'B' ? '诊断我的账号' : '拆解对标博主' }}</span>
                <span v-if="selectedBloggerSkill" class="status-chip status-chip--info">适用：{{ selectedSkillScope }}</span>
                <span v-if="runMeta.qualityScore !== null" class="status-chip" :class="`status-chip--${qualityTone(runMeta.qualityGrade)}`">质量自检 {{ runMeta.qualityScore }} 分 · {{ runMeta.qualityGrade }}</span>
                <span v-if="runMeta.revisions > 0" class="status-chip status-chip--info">已自我修订 {{ runMeta.revisions }} 次</span>
              </p>
            </div>
            <div v-if="selectedBloggerRun.status === 'pending_confirmation'" class="actions">
              <button type="button" class="primary" :disabled="Boolean(pendingAction)" @click="handleConfirmBloggerRun">
                {{ pendingAction === 'distill-confirm' ? '保存中' : '保存结果' }}
              </button>
              <button type="button" :disabled="Boolean(pendingAction)" @click="handleAbandonBloggerRun">
                {{ pendingAction === 'distill-abandon' ? '放弃中' : '放弃本次蒸馏' }}
              </button>
            </div>
          </div>
          <div class="distill-grid compact-result">
            <article class="distill-card">
              <h3>蒸馏报告</h3>
              <div v-if="selectedBloggerRun.status === 'failed'" class="failure-panel">
                <strong>蒸馏失败</strong>
                <p>{{ selectedBloggerRun.error_message || '这次蒸馏没有记录失败原因，请查看任务日志。' }}</p>
              </div>
              <div v-else-if="selectedBloggerRun.report_html" class="distill-report" v-html="sanitizeHtml(selectedBloggerRun.report_html)"></div>
              <p v-else class="empty-region">这次蒸馏没有生成报告。</p>
            </article>
            <article class="distill-card">
              <h3>Skill 输出</h3>
              <textarea v-if="selectedBloggerSkill" :value="selectedBloggerSkill.skill_markdown" readonly rows="18"></textarea>
              <p v-else-if="selectedBloggerRun.status === 'failed'" class="empty-region">蒸馏失败后不会生成 Skill。</p>
              <p v-else class="empty-region">这次蒸馏没有生成 Skill。</p>
            </article>
          </div>
        </section>
      </div>
      <p v-else class="empty-region">请选择一个博主开始蒸馏。</p>
    </div>
  </section>
</template>

<style scoped>
.distill-row { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.snapshot-list { display: flex; flex-direction: column; gap: 6px; }
.snapshot-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 8px 10px;
  border: var(--rule-hair);
  border-radius: var(--radius-sm);
  background: var(--color-paper-2);
}
.snapshot-info { display: flex; flex-direction: column; min-width: 0; }
.snapshot-info span { font-size: 12px; color: var(--color-ink-soft); }
.snapshot-row button { flex: 0 0 auto; }
</style>
